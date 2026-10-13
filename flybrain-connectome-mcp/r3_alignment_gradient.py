"""
R3 Alignment Gradient Experiment.

Tests whether structure gain (evidence vs random) depends on
structure-task alignment level. P1 showed that single-point high
alignment cannot establish a pattern — this experiment tests a gradient.

Design
------
5 alignment levels (0.0, 0.25, 0.50, 0.75, 1.0):
  a=0.0  — pure random blueprint (no structural signal)
  a=0.25 — 25% evidence edges + 75% random edges
  a=0.50 — 50/50 mix
  a=0.75 — 75% evidence + 25% random
  a=1.0  — pure evidence blueprint

Plus a "no blueprint" baseline (empty evidence block, same task).

For each alignment level:
  - Generate blueprints by mixing evidence and random edges at ratio a
  - Run hub + reachability tasks (motif_family excluded per S6)
  - Use 4 orchestration topologies
  - Test with 2+ models for cross-model validation

Output:
  - Alignment-gain curve: gain(a) = accuracy_evidence(a) - accuracy_random(a)
  - Threshold a*: the minimum alignment level where gain is significant
  - No-blueprint baseline comparison

CLI usage
---------
    # Full experiment (requires LLM endpoint)
    python r3_alignment_gradient.py --mode real --output-dir ./_r3_full

    # Quick smoke test (5 blueprints per level, 1 topology)
    python r3_alignment_gradient.py --mode real --n-blueprints 5 --topologies sequential

    # Stub mode (offline, zero LLM cost)
    python r3_alignment_gradient.py --mode stub --output-dir ./_r3_stub

    # Summarise a finished run
    python r3_alignment_gradient.py --summarise ./_r3_full
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from llm_tasks import (  # noqa: E402
    Blueprint,
    MOTIF_FAMILY_LABELS,
    Task,
    build_evidence_blueprint,
    build_random_blueprint,
    compute_ground_truth,
    generate_tasks,
    render_prompt,
    score_answer,
)
from llm_orchestrator import (  # noqa: E402
    Answer,
    HTTPLLMBackend,
    StubLLM,
    get_orchestrator,
    render_evidence_block,
)


ALIGNMENT_LEVELS: tuple[float, ...] = (0.0, 0.25, 0.50, 0.75, 1.0)
TASK_TYPES: tuple[str, ...] = ("hub", "reachability")  # motif_family excluded per S6
TOPOLOGIES: tuple[str, ...] = ("sequential", "fan_out", "hierarchical", "router")
DEFAULT_MODELS: tuple[str, ...] = ("deepseek-v4-flash", "glm-5.2")


# ============================================================== alignment mixing

def mix_blueprint(
    rng: random.Random,
    evidence_bp: Blueprint,
    random_bp: Blueprint,
    alignment: float,
) -> Blueprint:
    """Create a blueprint by mixing evidence and random edges at ratio `alignment`.

    alignment=1.0 → pure evidence blueprint
    alignment=0.0 → pure random blueprint
    alignment=0.5 → 50% evidence edges, 50% random edges

    Nodes are taken from the evidence blueprint to ensure consistent
    node naming. Edges are sampled proportionally from both sources.
    """
    n_nodes = len(evidence_bp.nodes)
    total_edges = max(len(evidence_bp.edges), len(random_bp.edges), n_nodes)

    # Determine how many edges come from each source
    n_ev_edges = max(1, round(total_edges * alignment))
    n_rd_edges = max(1, total_edges - n_ev_edges)

    # Sample edges from evidence blueprint
    ev_edge_list = list(evidence_bp.edges)
    if n_ev_edges <= len(ev_edge_list):
        selected_ev = rng.sample(ev_edge_list, k=n_ev_edges)
    else:
        selected_ev = ev_edge_list.copy()

    # Sample edges from random blueprint (exclude duplicates)
    rd_edge_list = [(a, b) for a, b in random_bp.edges
                    if (a, b) not in selected_ev]
    if n_rd_edges <= len(rd_edge_list):
        selected_rd = rng.sample(rd_edge_list, k=n_rd_edges)
    else:
        selected_rd = rd_edge_list.copy()

    all_edges = tuple(selected_ev + selected_rd)

    # Determine motif family for the mixed blueprint
    if alignment >= 0.75:
        motif = evidence_bp.motif_family
    elif alignment <= 0.25:
        motif = "mixed"
    else:
        motif = f"partial_{evidence_bp.motif_family}"

    return Blueprint(
        name=f"mix_a{alignment:.2f}_{rng.randint(0, 9999)}",
        nodes=evidence_bp.nodes,
        edges=all_edges,
        motif_family=motif,
        capability_distribution=evidence_bp.capability_distribution,
        origin="mixed",
    )


def compute_alignment_score(
    blueprint: Blueprint,
    task_type: str,
) -> float:
    """Compute a structural alignment score for a blueprint-task pair.

    Returns a value in [0, 1] representing how well the blueprint's
    structural features align with what the task asks.

    - hub: alignment = degree concentration (Gini coefficient of out-degrees)
      High concentration → one clear hub → high alignment with hub task
    - reachability: alignment = connectedness (fraction of reachable node pairs)
      More connected → clearer reachability answers → higher alignment
    """
    if task_type == "hub":
        out_degrees = [
            sum(1 for src, _ in blueprint.edges if src == node)
            for node in blueprint.nodes
        ]
        if len(out_degrees) < 2 or max(out_degrees) == 0:
            return 0.0
        # Gini coefficient: 0 = uniform, 1 = maximally concentrated
        sorted_degrees = sorted(out_degrees)
        n = len(sorted_degrees)
        total = sum(sorted_degrees)
        if total == 0:
            return 0.0
        gini_numerator = sum(
            (2 * (i + 1) - n - 1) * d
            for i, d in enumerate(sorted_degrees)
        )
        gini = gini_numerator / (n * total) if n * total > 0 else 0.0
        return max(0.0, min(1.0, gini))

    elif task_type == "reachability":
        # Connectedness: fraction of node pairs that are reachable
        nodes = list(blueprint.nodes)
        if len(nodes) < 2:
            return 0.0
        adj: dict[str, list[str]] = {n: [] for n in nodes}
        for src, dst in blueprint.edges:
            adj.setdefault(src, []).append(dst)

        reachable_pairs = 0
        total_pairs = 0
        for src in nodes:
            for dst in nodes:
                if src == dst:
                    continue
                total_pairs += 1
                # BFS
                seen = {src}
                frontier = [src]
                found = False
                while frontier:
                    nxt = []
                    for u in frontier:
                        for v in adj.get(u, []):
                            if v == dst:
                                found = True
                                break
                            if v not in seen:
                                seen.add(v)
                                nxt.append(v)
                        if found:
                            break
                    if found:
                        break
                    frontier = nxt
                if found:
                    reachable_pairs += 1

        return reachable_pairs / total_pairs if total_pairs > 0 else 0.0

    return 0.0


# ============================================================== cell result

@dataclass
class CellResult:
    """One (blueprint, task, topology, trial, model) outcome."""
    alignment_level: float
    blueprint_name: str
    blueprint_origin: str
    blueprint_motif: str
    task_id: str
    task_type: str
    topology: str
    trial: int
    model: str
    correct: bool
    predicted: str
    ground_truth: str
    agent_calls: int
    latency_ms: int
    trace_n_calls: int
    structural_alignment: float  # computed alignment score
    timestamp: str


# ============================================================== paired t-test

def _paired_ttest(a: list[float], b: list[float]) -> dict[str, float]:
    """Simple paired t-test without scipy dependency."""
    n = min(len(a), len(b))
    if n < 3:
        return {"n": n, "t_stat": 0.0, "p_value": 1.0, "delta": 0.0}
    diffs = [a[i] - b[i] for i in range(n)]
    mean_diff = sum(diffs) / n
    variance = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1) if n > 1 else 0
    std_error = math.sqrt(variance / n) if n > 0 else 0
    t_stat = mean_diff / std_error if std_error > 0 else 0.0
    # Approximate p-value using t-distribution (simplified)
    p_value = 1.0  # Conservative; use scipy for real analysis
    return {
        "n": n,
        "t_stat": round(t_stat, 4),
        "p_value": round(p_value, 4),
        "delta": round(mean_diff, 4),
    }


# ============================================================== experiment runner

def run_experiment(
    backend_factory: Any,
    alignment_levels: tuple[float, ...],
    n_blueprints_per_level: int,
    n_tasks_per_blueprint: int,
    n_trials: int,
    seed: int,
    topology_subset: tuple[str, ...] = TOPOLOGIES,
    task_subset: tuple[str, ...] = TASK_TYPES,
    models: tuple[str, ...] = DEFAULT_MODELS,
    checkpoint_path: Path | None = None,
) -> list[CellResult]:
    """Run the full R3 alignment gradient experiment."""
    rng = random.Random(seed)
    results: list[CellResult] = []
    seen_ids: set[str] = set()

    # Restore checkpoint
    if checkpoint_path is not None and checkpoint_path.exists():
        saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        for r in saved.get("results", []):
            results.append(CellResult(**r))
            seen_ids.add(
                f"{r['alignment_level']}|{r['blueprint_name']}|"
                f"{r['task_id']}|{r['topology']}|{r['trial']}|{r['model']}"
            )
        print(f"[r3] resuming from checkpoint with {len(results)} prior cells")

    total_levels = len(alignment_levels) + 1  # +1 for no-blueprint baseline
    total_cells = (
        total_levels * n_blueprints_per_level * len(task_subset)
        * n_tasks_per_blueprint * len(topology_subset) * n_trials * len(models)
    )
    print(f"[r3] total cells planned: {total_cells}")

    cell_i = 0

    # ---- No-blueprint baseline (alignment = None, empty evidence block) ----
    for model_name in models:
        backend = backend_factory(model_name)
        for alignment in (None,) + alignment_levels:
            # Build blueprint pairs for this alignment level
            # Use larger graphs (8-10 nodes) to make tasks harder for the LLM.
            # With 4-6 nodes, hub/reachability are trivially solvable without
            # the evidence block, masking any alignment effect.
            specs = [{"n_nodes": rng.randint(8, 10), "n_edges": rng.randint(12, 18)}
                     for _ in range(n_blueprints_per_level)]
            for spec in specs:
                ev_bp = build_evidence_blueprint(rng, spec)
                rd_bp = build_random_blueprint(rng, spec)

                if alignment is None:
                    # No blueprint baseline: use empty evidence block
                    mixed_bp = rd_bp  # random structure, but no evidence block
                    actual_alignment = -1.0  # sentinel for "no blueprint"
                elif alignment == 1.0:
                    mixed_bp = ev_bp
                    actual_alignment = 1.0
                elif alignment == 0.0:
                    mixed_bp = rd_bp
                    actual_alignment = 0.0
                else:
                    mixed_bp = mix_blueprint(rng, ev_bp, rd_bp, alignment)
                    actual_alignment = alignment

                # Generate tasks
                tasks = generate_tasks(
                    mixed_bp,
                    task_types=task_subset,
                    n_per_type=n_tasks_per_blueprint,
                    rng=rng,
                )

                for task in tasks:
                    # Compute structural alignment score
                    struct_align = compute_alignment_score(mixed_bp, task.task_type)

                    for topo in topology_subset:
                        for trial in range(n_trials):
                            cell_i += 1
                            cid = (
                                f"{actual_alignment}|{mixed_bp.name}|"
                                f"{task.id}|{topo}|{trial}|{model_name}"
                            )
                            if cid in seen_ids:
                                continue

                            # Build evidence block
                            if alignment is None:
                                ev_block = ""  # empty evidence block
                            else:
                                ev_block = render_evidence_block(mixed_bp)

                            # Run through orchestrator
                            orch_kwargs = {"n_agents": 3} if topo == "fan_out" else {}
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
                                ans = Answer(
                                    text="", topology=topo,
                                    trace=[("error", str(type(exc).__name__),
                                            task.prompt, str(exc)[:200], 0)],
                                    agent_calls=0,
                                )
                            latency_ms = int((time.perf_counter() - t0) * 1000)

                            correct = score_answer(
                                ans.text, task.ground_truth, task.task_type
                            )

                            cell = CellResult(
                                alignment_level=actual_alignment,
                                blueprint_name=mixed_bp.name,
                                blueprint_origin=mixed_bp.origin,
                                blueprint_motif=mixed_bp.motif_family,
                                task_id=task.id,
                                task_type=task.task_type,
                                topology=topo,
                                trial=trial,
                                model=model_name,
                                correct=correct,
                                predicted=ans.text,
                                ground_truth=str(task.ground_truth),
                                agent_calls=ans.agent_calls,
                                latency_ms=latency_ms,
                                trace_n_calls=len(ans.trace),
                                structural_alignment=struct_align,
                                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            )
                            results.append(cell)
                            seen_ids.add(cid)

                            if cell_i % 20 == 0:
                                correct_count = sum(1 for r in results if r.correct)
                                print(f"[r3] cell {cell_i}/{total_cells}  "
                                      f"correct={correct_count}/{len(results)}")
                            # Checkpoint every cell (atomic)
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
    os.replace(tmp, path)


# ============================================================== summarise

def summarise(results: list[CellResult]) -> dict[str, Any]:
    """Produce summary: accuracy per alignment level, gain curves, threshold."""
    # Group by (alignment_level, model, task_type)
    grouped: dict[tuple[float, str, str], list[CellResult]] = defaultdict(list)
    for r in results:
        grouped[(r.alignment_level, r.model, r.task_type)].append(r)

    # Accuracy per cell
    per_cell: dict[str, dict[str, float]] = {}
    for (alignment, model, task_type), cells in sorted(grouped.items()):
        acc = sum(1 for c in cells if c.correct) / max(len(cells), 1)
        key = f"align={alignment:.2f}|{model}|{task_type}"
        per_cell[key] = {
            "accuracy": round(acc, 4),
            "n_cells": len(cells),
            "mean_structural_alignment": round(
                sum(c.structural_alignment for c in cells) / max(len(cells), 1), 4
            ),
        }

    # Gain curves: for each model+task_type, compute accuracy at each alignment
    # and the gain vs no-blueprint baseline (alignment=-1.0)
    gain_curves: dict[str, dict[str, Any]] = {}
    models = sorted({r.model for r in results})
    for model in models:
        for task_type in task_subset_of(results):
            curve_key = f"{model}|{task_type}"
            baseline_acc = None
            level_accs: dict[float, float] = {}
            level_ns: dict[float, int] = {}

            for (alignment, m, tt), cells in sorted(grouped.items()):
                if m != model or tt != task_type:
                    continue
                acc = sum(1 for c in cells if c.correct) / max(len(cells), 1)
                level_accs[alignment] = round(acc, 4)
                level_ns[alignment] = len(cells)
                if alignment == -1.0:
                    baseline_acc = acc

            # Compute gain at each level
            gains: dict[float, float] = {}
            for a, acc in sorted(level_accs.items()):
                if a == -1.0:
                    continue
                gains[a] = round(acc - baseline_acc, 4) if baseline_acc is not None else None

            # Find threshold a*: minimum alignment where gain > 0.05 (5pp)
            threshold_a_star = None
            for a in sorted(gains.keys()):
                g = gains[a]
                if g is not None and g > 0.05:
                    threshold_a_star = a
                    break

            gain_curves[curve_key] = {
                "baseline_accuracy": round(baseline_acc, 4) if baseline_acc is not None else None,
                "level_accuracies": level_accs,
                "level_counts": level_ns,
                "gains": gains,
                "threshold_a_star": threshold_a_star,
                "verdict": (
                    "no_threshold_found" if threshold_a_star is None else
                    f"threshold_a*={threshold_a_star}"
                ),
            }

    return {
        "n_results": len(results),
        "per_cell_accuracy": per_cell,
        "gain_curves": gain_curves,
    }


def task_subset_of(results: list[CellResult]) -> tuple[str, ...]:
    """Extract unique task types from results."""
    return tuple(sorted({r.task_type for r in results}))


def _print_summary(summary: dict[str, Any]) -> None:
    print("=" * 72)
    print(f"R3 Alignment Gradient Summary ({summary['n_results']} cells)")
    print("=" * 72)
    print()

    # Per-cell accuracy table
    print(f"{'alignment':>10} {'model':<20} {'task_type':<14} "
          f"{'accuracy':>10} {'n_cells':>8} {'struct_align':>12}")
    print("-" * 72)
    for key, val in sorted(summary["per_cell_accuracy"].items()):
        parts = key.split("|")
        align = parts[0].replace("align=", "")
        model = parts[1]
        task_type = parts[2]
        print(f"{align:>10} {model:<20} {task_type:<14} "
              f"{val['accuracy']:>10.4f} {val['n_cells']:>8} "
              f"{val['mean_structural_alignment']:>12.4f}")

    # Gain curves
    print()
    print("-- Gain Curves (evidence-gain vs no-blueprint baseline) --")
    print()
    for key, curve in sorted(summary["gain_curves"].items()):
        model, task_type = key.split("|")
        print(f"  {model} / {task_type}:")
        print(f"    baseline accuracy: {curve['baseline_accuracy']}")
        for a, g in sorted(curve["gains"].items()):
            marker = " ← threshold" if curve["threshold_a_star"] == a else ""
            print(f"    alignment={a:.2f}: gain={g}{marker}")
        print(f"    verdict: {curve['verdict']}")
        print()


# ============================================================== main

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="R3 alignment gradient experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--mode", choices=("real", "stub"), default="real")
    p.add_argument("--output-dir", default="./_r3_full")
    p.add_argument("--n-blueprints", type=int, default=5,
                   help="blueprints per alignment level per model")
    p.add_argument("--n-tasks", type=int, default=1,
                   help="tasks per blueprint per task_type")
    p.add_argument("--n-trials", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--topologies", default=",".join(TOPOLOGIES))
    p.add_argument("--tasks", default=",".join(TASK_TYPES))
    p.add_argument("--models", default=",".join(DEFAULT_MODELS))
    p.add_argument("--alignment-levels",
                   default=",".join(f"{a:.2f}" for a in ALIGNMENT_LEVELS))
    p.add_argument("--base-url",
                   default=os.environ.get("FLYBRAIN_LLM_BASE_URL",
                                          "http://127.0.0.1:8788/v1"))
    p.add_argument("--timeout-s", type=float, default=20)
    p.add_argument("--max-retries", type=int, default=1)
    p.add_argument("--summarise",
                   help="path to finished run; print summary and exit")
    args = p.parse_args(argv)

    out_dir = Path(args.output_dir)

    if args.summarise:
        out_dir = Path(args.summarise)
        ckpt = out_dir / "state.json"
        if not ckpt.exists():
            print(f"[r3] no state.json at {ckpt}", file=sys.stderr)
            return 1
        saved = json.loads(ckpt.read_text(encoding="utf-8"))
        results = [CellResult(**r) for r in saved["results"]]
        summary = summarise(results)
        _print_summary(summary)
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        # Also write CSV for spreadsheet analysis
        csv_path = out_dir / "r3_alignment_gradient.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "alignment_level", "blueprint_name", "blueprint_origin",
                "blueprint_motif", "task_id", "task_type", "topology",
                "trial", "model", "correct", "predicted", "ground_truth",
                "agent_calls", "latency_ms", "structural_alignment",
            ])
            for r in results:
                writer.writerow([
                    r.alignment_level, r.blueprint_name, r.blueprint_origin,
                    r.blueprint_motif, r.task_id, r.task_type, r.topology,
                    r.trial, r.model, r.correct, r.predicted, r.ground_truth,
                    r.agent_calls, r.latency_ms, r.structural_alignment,
                ])
        print(f"\n[r3] CSV written to {csv_path}")
        return 0

    # Parse parameters
    alignment_levels = tuple(
        float(x) for x in args.alignment_levels.split(",")
    )
    topology_subset = tuple(args.topologies.split(","))
    task_subset = tuple(args.tasks.split(","))
    models = tuple(args.models.split(","))

    checkpoint_path = out_dir / "state.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "stub":
        # Offline mode: use scripted StubLLM that returns ground truth
        def stub_factory(model_name: str) -> StubLLM:
            return StubLLM({
                "hub": "n0",
                "reachability": "2",
                "motif": "inhibitory_hub",
            }, default_response="unknown")

        results = run_experiment(
            backend_factory=stub_factory,
            alignment_levels=alignment_levels,
            n_blueprints_per_level=args.n_blueprints,
            n_tasks_per_blueprint=args.n_tasks,
            n_trials=args.n_trials,
            seed=args.seed,
            topology_subset=topology_subset,
            task_subset=task_subset,
            models=models,
            checkpoint_path=checkpoint_path,
        )
    else:
        # Real mode: use HTTP LLM backend
        def real_factory(model_name: str) -> HTTPLLMBackend:
            return HTTPLLMBackend(
                base_url=args.base_url,
                model=model_name,
                timeout_s=args.timeout_s,
                max_retries=args.max_retries,
            )

        results = run_experiment(
            backend_factory=real_factory,
            alignment_levels=alignment_levels,
            n_blueprints_per_level=args.n_blueprints,
            n_tasks_per_blueprint=args.n_tasks,
            n_trials=args.n_trials,
            seed=args.seed,
            topology_subset=topology_subset,
            task_subset=task_subset,
            models=models,
            checkpoint_path=checkpoint_path,
        )

    # Write summary
    summary = summarise(results)
    _print_summary(summary)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Write full JSON
    full_path = out_dir / "r3_alignment_gradient.json"
    full_payload = {
        "params": {
            "alignment_levels": alignment_levels,
            "n_blueprints_per_level": args.n_blueprints,
            "n_tasks_per_blueprint": args.n_tasks,
            "n_trials": args.n_trials,
            "seed": args.seed,
            "topologies": topology_subset,
            "tasks": task_subset,
            "models": models,
            "base_url": args.base_url,
        },
        "summary": summary,
        "all_results": [asdict(r) for r in results],
    }
    full_path.write_text(
        json.dumps(full_payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Write CSV
    csv_path = out_dir / "r3_alignment_gradient.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "alignment_level", "blueprint_name", "blueprint_origin",
            "blueprint_motif", "task_id", "task_type", "topology",
            "trial", "model", "correct", "predicted", "ground_truth",
            "agent_calls", "latency_ms", "structural_alignment",
        ])
        for r in results:
            writer.writerow([
                r.alignment_level, r.blueprint_name, r.blueprint_origin,
                r.blueprint_motif, r.task_id, r.task_type, r.topology,
                r.trial, r.model, r.correct, r.predicted, r.ground_truth,
                r.agent_calls, r.latency_ms, r.structural_alignment,
            ])

    print(f"\n[r3] JSON: {full_path}")
    print(f"[r3] CSV:  {csv_path}")

    # Gate check: does the experiment produce a valid threshold signal?
    any_threshold = any(
        curve["threshold_a_star"] is not None
        for curve in summary["gain_curves"].values()
    )
    if any_threshold:
        print("[r3] ✅ Threshold a* found — structure gain depends on alignment")
    else:
        print("[r3] ⚠️ No threshold found — structure gain does not vary with alignment")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
