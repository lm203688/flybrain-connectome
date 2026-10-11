"""
E2-P1 experiment driver: does an evidence-anchored blueprint measurably
improve multi-agent LLM reasoning compared to a random same-size blueprint?

This is the "P1" from the project's positioning strategy — the only
experiment that can close out the 0/7 negative result recorded back in
v1.x. The design mirrors AdaptOrch (arXiv:2602.16873), which showed
that multi-agent orchestration topology contributes +12–23% on
SWE-bench / GPQA / RAG for the *same* underlying LLM. Our analogue
question here is orthogonal: **does the blueprint we inject into the
prompt carry signal that the LLM can exploit**, over and above a random
same-size blueprint?

Experiment design
-----------------
25 evidence blueprints drawn from the real 3-family motif vocabulary
+ 25 random same-size blueprints, × 3 task types, × 4 topologies,
× N trials.

Each cell is scored by binary correct/incorrect against exact ground
truth from llm_tasks.compute_ground_truth. Accuracy is computed per
(topology, blueprint_source) cell; a paired t-test compares evidence
vs random within each topology.

Design properties
-----------------
* Deterministic given a fixed seed — every blueprint, task, and
  answer is reproducible.
* Checkpointed — a long run can be interrupted and resumed from the
  `state.json` on disk.
* Fully local — no server, no database; the checkpoint is a single
  JSON file with all per-cell traces for audit.

CLI usage
---------
    # Real run against the local SenseNova proxy (default)
    python p1_experiment.py --mode real --output-dir ./p1_run_01

    # Smoke test with 3 blueprints per arm
    python p1_experiment.py --mode real --n-blueprints-per-arm 3

    # Offline smoke test with a scripted stub (zero LLM cost)
    python p1_experiment.py --mode stub --output-dir ./p1_smoke

    # Summarise a finished run
    python p1_experiment.py --summarise ./p1_run_01
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from llm_tasks import (  # noqa: E402
    Blueprint,
    Task,
    build_evidence_blueprint,
    build_random_blueprint,
    generate_tasks,
    score_answer,
)
from llm_orchestrator import (  # noqa: E402
    Answer,
    HTTPLLMBackend,
    StubLLM,
    get_orchestrator,
    render_evidence_block,
)


TASK_TYPES: tuple[str, ...] = ("motif_family", "hub", "reachability")
TOPOLOGIES: tuple[str, ...] = ("sequential", "fan_out", "hierarchical", "router")


# ============================================================== experiment cell


@dataclass
class CellResult:
    """One (blueprint, task, topology, trial) outcome."""
    blueprint_name: str
    blueprint_source: str   # 'evidence' | 'random'
    blueprint_origin: str
    blueprint_motif: str
    task_id: str
    task_type: str
    topology: str
    trial: int
    correct: bool
    predicted: str
    ground_truth: str
    agent_calls: int
    latency_ms: int
    trace_n_calls: int
    timestamp: str


# ============================================================== run


def _make_stub_backend(script: dict[str, str], default: str = "unknown") -> StubLLM:
    return StubLLM(script=script, default_response=default)


def _stub_script_for_ground_truth(tasks: list[Task]) -> dict[str, str]:
    """Build a script that always returns the ground-truth value.

    This is used ONLY for offline smoke testing the harness plumbing —
    it makes the answer always correct by construction, so we can
    verify trace discipline and scoring without any external LLM.
    """
    script: list[tuple[str, str]] = []
    for t in tasks:
        # Match the ground-truth task's own prompt prefix
        head = t.prompt.split("\n")[0]
        script.append((head, str(t.ground_truth)))
    # Fan-out judge fallback: pick a common label
    script.append(("Return the candidate that appears most often", "inhibitory_hub"))
    # Router fallback
    script.append(("You are a task router", "motif"))
    script.append(("You are a task planner", "Which motif family is the graph?"))
    script.append(("Verify against", "inhibitory_hub"))
    return dict(script)


def _paired_ttest(a: list[float], b: list[float]) -> dict[str, float]:
    """Paired Student's t-test with Welch correction off (paired is
    exact when n is small). Returns {t, df, p_approx, mean_diff}.

    `p_approx` is a two-sided normal approximation when n>=8, else
    reported as `float('nan')` so the caller knows the CI is not
    trustworthy at small n.
    """
    n = min(len(a), len(b))
    if n < 2:
        return {"t": float("nan"), "df": float("nan"), "p_approx": float("nan"),
                "mean_diff": float("nan")}
    diffs = [a[i] - b[i] for i in range(n)]
    mean_diff = statistics.mean(diffs)
    var = statistics.variance(diffs) if n >= 2 else 0.0
    se = math.sqrt(var / n) if n > 0 and var > 0 else 0.0
    if se == 0:
        return {"t": float("nan"), "df": n - 1, "p_approx": 0.0,
                "mean_diff": mean_diff}
    t_stat = mean_diff / se
    df = n - 1
    # Two-sided normal approximation (accurate for df >= 8; flagged otherwise)
    if df < 8:
        p_approx = float("nan")
    else:
        # Standard normal CDF approximation via error function
        from math import erf, sqrt
        p_approx = 2.0 * (1.0 - 0.5 * (1.0 + erf(abs(t_stat) / sqrt(2.0))))
    return {"t": t_stat, "df": df, "p_approx": p_approx, "mean_diff": mean_diff}


def run_experiment(
    backend: Any,
    n_blueprints_per_arm: int,
    n_tasks_per_blueprint: int,
    n_trials: int,
    seed: int,
    topology_subset: tuple[str, ...] = TOPOLOGIES,
    task_subset: tuple[str, ...] = TASK_TYPES,
    fan_out_n: int = 3,
    checkpoint_path: Path | None = None,
) -> list[CellResult]:
    """Run the full experiment and return all cell results."""
    rng = random.Random(seed)

    # ---- build blueprint arms
    ev_specs = [{"n_nodes": rng.randint(4, 7), "n_edges": rng.randint(5, 9)}
                for _ in range(n_blueprints_per_arm)]
    rd_specs = [{"n_nodes": rng.randint(4, 7), "n_edges": rng.randint(5, 9)}
                for _ in range(n_blueprints_per_arm)]
    ev_blueprints = [build_evidence_blueprint(rng, s) for s in ev_specs]
    rd_blueprints = [build_random_blueprint(rng, s) for s in rd_specs]

    # ---- enumerate all cells
    blueprints: list[Blueprint] = []
    for bp in ev_blueprints:
        bp2 = Blueprint(
            name=bp.name, nodes=bp.nodes, edges=bp.edges,
            motif_family=bp.motif_family,
            capability_distribution=bp.capability_distribution,
            structure_signature_prefix=f"sha256:{hash(bp.name) & 0xFFFFFFFF:08x}...",
            origin=bp.origin,
        )
        blueprints.append(bp2)
    for bp in rd_blueprints:
        blueprints.append(bp)

    tasks_by_bp: dict[str, list[Task]] = {}
    for bp in blueprints:
        tasks = generate_tasks(
            bp, task_types=task_subset, n_per_type=n_tasks_per_blueprint, rng=rng,
        )
        tasks_by_bp[bp.name] = tasks

    # ---- restore checkpoint
    results: list[CellResult] = []
    seen_ids: set[str] = set()
    if checkpoint_path is not None and checkpoint_path.exists():
        saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        for r in saved.get("results", []):
            results.append(CellResult(**r))
            seen_ids.add(r["task_id"] + "|" + r["topology"] + "|" + str(r["trial"]))
        print(f"[p1] resuming from checkpoint with {len(results)} prior cells")

    # ---- run each cell
    total_cells = len(blueprints) * sum(len(tasks_by_bp[bp.name]) for bp in [blueprints[0]]) * len(topology_subset) * n_trials
    print(f"[p1] total cells planned: {total_cells}  "
          f"(blueprints={len(blueprints)} task_types={task_subset} "
          f"topologies={topology_subset} trials={n_trials})")

    cell_i = 0
    for bp in blueprints:
        ev_block = render_evidence_block(bp)
        for task in tasks_by_bp[bp.name]:
            for topo in topology_subset:
                for trial in range(n_trials):
                    cid = f"{task.id}|{topo}|{trial}"
                    cell_i += 1
                    if cid in seen_ids:
                        continue
                    # Every trial gets a fresh backend for statefulness reasons
                    if isinstance(backend, StubLLM) and backend.__dict__.get("calls"):
                        # reset stub state between cells
                        backend.calls.clear()
                    orch_kwargs = {"n_agents": fan_out_n} if topo == "fan_out" else {}
                    orch = get_orchestrator(
                        topo,
                        backend=backend,
                        evidence=ev_block,
                        **orch_kwargs,
                    )
                    t0 = time.perf_counter()
                    try:
                        ans: Answer = orch.run(task.prompt)
                    except Exception as exc:  # noqa: BLE001
                        # Log the failure as an incorrect cell; do not
                        # kill the whole run over a transient backend error.
                        ans = Answer(
                            text="", topology=topo,
                            trace=[("error", str(type(exc).__name__), task.prompt,
                                   str(exc)[:200], 0)],
                            agent_calls=0,
                        )
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    correct = score_answer(ans.text, task.ground_truth, task.task_type)
                    cell = CellResult(
                        blueprint_name=bp.name,
                        blueprint_source=bp.origin,
                        blueprint_origin=bp.origin,
                        blueprint_motif=bp.motif_family,
                        task_id=task.id,
                        task_type=task.task_type,
                        topology=topo,
                        trial=trial,
                        correct=correct,
                        predicted=ans.text,
                        ground_truth=str(task.ground_truth),
                        agent_calls=ans.agent_calls,
                        latency_ms=latency_ms,
                        trace_n_calls=len(ans.trace),
                        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    )
                    results.append(cell)
                    seen_ids.add(cid)
                    if cell_i % 25 == 0:
                        print(f"[p1] cell {cell_i}/{total_cells}  "
                              f"correct={sum(1 for r in results if r.correct)}/{len(results)}")
                        if checkpoint_path is not None:
                            _write_checkpoint(checkpoint_path, results, seed)
                    else:
                        # lightweight incremental write every cell so a
                        # crash never loses more than one cell
                        if checkpoint_path is not None:
                            _write_checkpoint(checkpoint_path, results, seed)

    if checkpoint_path is not None:
        _write_checkpoint(checkpoint_path, results, seed)
    return results


def _write_checkpoint(path: Path, results: list[CellResult], seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "schema_version": "1.0.0",
        "seed": seed,
        "n_results": len(results),
        "results": [asdict(r) for r in results],
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)  # atomic on POSIX; acceptable on Windows for this scale


# ============================================================== summarise


def summarise(results: list[CellResult]) -> dict[str, Any]:
    """Produce a summary report grouped by topology × blueprint_source."""
    from collections import defaultdict

    grouped: dict[tuple[str, str], list[CellResult]] = defaultdict(list)
    for r in results:
        grouped[(r.topology, r.blueprint_source)].append(r)

    per_cell: dict[str, dict[str, float]] = {}
    for (topo, src), cells in grouped.items():
        acc = sum(1 for c in cells if c.correct) / max(len(cells), 1)
        per_cell[f"{topo}|{src}"] = {"accuracy": acc, "n_cells": len(cells)}

    # Per-cell correctness arrays aligned by (blueprint, task, trial)
    # so we can run a paired t-test across evidence vs random.
    per_cell_index: dict[tuple[str, str, str], list[bool]] = defaultdict(list)
    for r in results:
        key = (r.topology, r.blueprint_name.replace("ev_", "").replace("rnd_", ""),
               r.trial)
        per_cell_index[(r.topology, r.blueprint_name.split("_")[0] + "_arm",
                        r.task_type)].append((r.blueprint_source, r.correct))

    paired_tests: dict[str, dict[str, float]] = {}
    for topo in sorted({r.topology for r in results}):
        ev_correct: list[bool] = []
        rd_correct: list[bool] = []
        for r in results:
            if r.topology != topo:
                continue
            if r.blueprint_source == "evidence":
                ev_correct.append(r.correct)
            elif r.blueprint_source == "random":
                rd_correct.append(r.correct)
        # Pad shorter arm to match (paired test with unequal n is invalid;
        # we report the min-length paired result)
        n = min(len(ev_correct), len(rd_correct))
        paired_tests[topo] = _paired_ttest(
            [float(x) for x in ev_correct[:n]],
            [float(x) for x in rd_correct[:n]],
        )

    return {
        "n_results": len(results),
        "per_cell_accuracy": per_cell,
        "paired_tests": paired_tests,
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print("=" * 60)
    print(f"P1 experiment summary ({summary['n_results']} cells)")
    print("=" * 60)
    print()
    print(f"{'topology':<14} {'evidence':>10} {'random':>10} {'Δ (ev-rd)':>12}")
    print("-" * 50)
    for topo in TOPOLOGIES:
        ev_key = f"{topo}|evidence"
        rd_key = f"{topo}|random"
        ev = summary["per_cell_accuracy"].get(ev_key, {}).get("accuracy", float("nan"))
        rd = summary["per_cell_accuracy"].get(rd_key, {}).get("accuracy", float("nan"))
        delta = ev - rd
        mark = "  <-- top" if delta >= max(
            summary["per_cell_accuracy"].get(f"{t}|evidence", {}).get("accuracy", 0)
            - summary["per_cell_accuracy"].get(f"{t}|random", {}).get("accuracy", 0)
            for t in TOPOLOGIES
            if f"{t}|evidence" in summary["per_cell_accuracy"] and f"{t}|random" in summary["per_cell_accuracy"]
        ) else ""
        print(f"{topo:<14} {ev:>10.3f} {rd:>10.3f} {delta:>+12.3f}{mark}")
    print()
    print("Paired t-tests (evidence vs random within each topology):")
    print("-" * 50)
    for topo, stats in summary["paired_tests"].items():
        p = stats["p_approx"]
        p_str = f"{p:.4f}" if isinstance(p, float) and p == p else "n/a (df<8)"
        t = stats["t"]
        t_str = f"{t:+.3f}" if isinstance(t, float) and t == t else "n/a"
        print(f"  {topo:<14}  t={t_str}  p={p_str}")


# ============================================================== CLI


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="E2-P1 experiment driver")
    p.add_argument("--mode", choices=("real", "stub"), default="real")
    p.add_argument("--output-dir", default="./p1_run_default")
    p.add_argument("--n-blueprints-per-arm", type=int, default=25)
    p.add_argument("--n-tasks-per-blueprint", type=int, default=1)
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--fan-out-n", type=int, default=3)
    p.add_argument("--topologies", default=",".join(TOPOLOGIES))
    p.add_argument("--tasks", default=",".join(TASK_TYPES))
    p.add_argument("--base-url", default=os.environ.get("FLYBRAIN_LLM_BASE_URL",
                                                         "http://127.0.0.1:8788/v1"))
    p.add_argument("--model", default=os.environ.get("FLYBRAIN_LLM_MODEL",
                                                     "deepseek-v4-flash"))
    p.add_argument("--timeout-s", type=float, default=15,
                   help="per-request HTTP timeout in seconds (default 15)")
    p.add_argument("--max-retries", type=int, default=1,
                   help="retries on transient HTTP failure (default 1; "
                        "longer = more latency under rate-limiting)")
    p.add_argument("--summarise", help="path to a finished run directory; print summary and exit")
    args = p.parse_args(argv)

    out_dir = Path(args.output_dir)

    if args.summarise:
        out_dir = Path(args.summarise)
        ckpt = out_dir / "state.json"
        if not ckpt.exists():
            print(f"[p1] no state.json at {ckpt}", file=sys.stderr)
            return 1
        saved = json.loads(ckpt.read_text(encoding="utf-8"))
        results = [CellResult(**r) for r in saved["results"]]
        summary = summarise(results)
        _print_summary(summary)
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return 0

    if args.mode == "stub":
        # Build a script that returns ground-truth for every prompt we'll issue
        # (this lets us test the plumbing offline with zero tokens).
        # We do it lazily by pre-generating blueprints + tasks below and
        # populating the script, then passing the stub in.
        rng = random.Random(args.seed)
        ev_specs = [{"n_nodes": rng.randint(4, 7), "n_edges": rng.randint(5, 9)}
                    for _ in range(args.n_blueprints_per_arm)]
        rd_specs = [{"n_nodes": rng.randint(4, 7), "n_edges": rng.randint(5, 9)}
                    for _ in range(args.n_blueprints_per_arm)]
        preview_tasks: list[Task] = []
        ev_specs_set = set(id(s) for s in ev_specs)
        for spec in ev_specs + rd_specs:
            is_ev = id(spec) in ev_specs_set
            bp = (build_evidence_blueprint if is_ev else build_random_blueprint)(rng, spec)
            preview_tasks.extend(generate_tasks(
                bp,
                task_types=tuple(args.tasks.split(",")),
                n_per_type=args.n_tasks_per_blueprint,
                rng=rng,
            ))
        script = _stub_script_for_ground_truth(preview_tasks)
        backend = _make_stub_backend(script)
    else:
        backend = HTTPLLMBackend(
            base_url=args.base_url,
            model=args.model,
            timeout_s=args.timeout_s,
            max_retries=args.max_retries,
        )
        # quick reachability probe
        try:
            probe = backend.chat("test", "Return the single token 'pong' and nothing else.")
            print(f"[p1] backend probe OK: {probe!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"[p1] backend probe FAILED: {exc}", file=sys.stderr)
            return 2

    topology_subset = tuple(args.topologies.split(","))
    task_subset = tuple(args.tasks.split(","))

    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    results = run_experiment(
        backend=backend,
        n_blueprints_per_arm=args.n_blueprints_per_arm,
        n_tasks_per_blueprint=args.n_tasks_per_blueprint,
        n_trials=args.n_trials,
        seed=args.seed,
        topology_subset=topology_subset,
        task_subset=task_subset,
        fan_out_n=args.fan_out_n,
        checkpoint_path=out_dir / "state.json",
    )
    wall = time.perf_counter() - t0

    summary = summarise(results)
    summary["wall_seconds"] = wall
    summary["backend"] = "stub" if args.mode == "stub" else f"http/{args.model}"
    summary["seed"] = args.seed
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    _print_summary(summary)

    # CSV export
    csv_path = out_dir / "cells.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].__dict__.keys()))
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))
    print(f"\n[p1] wrote {csv_path}  and  {out_dir/'summary.json'}  and  {out_dir/'state.json'}")
    print(f"[p1] wall clock: {wall:.1f}s   cells/sec: {len(results) / max(wall, 1e-6):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
