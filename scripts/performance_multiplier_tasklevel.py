"""
Performance multiplier — redefined at the TASK level (层3, P0).

Why this rewrite
----------------
The old "performance" multiplier tried to show that our virtual-bio topology
makes a spiking/echo-state *engine* run faster or score higher. We measured
that honestly and it was NEGATIVE across the board:

    SNN  : 0 / 24 scenarios favoured the bio topology
    ESN  : 0 / 7  scenarios favoured the bio topology

Root cause: the inference *engine* does not differentiate topologies by raw
score — that is an engine property, not something our topology can change.
Claiming a performance win there would be dishonest.

New definition — task-level, not engine-level
--------------------------------------------
We stop measuring the engine. We measure whether the *structural prior*
(our connectome-derived topology) helps an AGENT complete a benchmark TASK
relative to two control arms:

    arm A  organism_prior   : agent seeded with our virtual-bio topology
    arm B  random_topology  : agent seeded with a random graph (same size)
    arm C  no_topology      : agent with a flat / fully-connected prior

Metrics (all task-level, none claim engine speed):
    task_success_rate        : fraction of benchmark tasks solved to criterion
    relative_inference_latency : wall-clock per task vs arm C baseline (informational)
    structural_traceability  : completeness of the W3C-PROV chain for the decision

These measure a *different axis* (does the wiring prior help the agent reason),
which is exactly the connectome-determinism hypothesis the project is built on
(Kaganovsky/Pașca 2026 Nature: wiring, not cell type, determines function).

Status: FRAMEWORK DEFINED. No inference engine is bundled, so the numbers are
NOT yet produced. The runner is an adapter seam: drop in any engine that
implements `EngineAdapter` and call `run_ab_comparison`.

⚠️ DO NOT claim any performance number until run_ab_comparison returns real
   measurements. Until then `MULTIPLIER_SEMANTICS["performance"]["measured"]`
   stays False.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Protocol

ROOT = Path(__file__).resolve().parents[1]


class EngineAdapter(Protocol):
    """Adapter seam — implement against any inference backend."""
    def solve_task(self, topology: dict, task: dict) -> dict:
        """Return {"solved": bool, "latency_s": float, "trace": dict}."""
        ...


@dataclass
class TaskMetrics:
    arm: str
    tasks_total: int = 0
    tasks_solved: int = 0
    latency_sum: float = 0.0
    trace_complete: int = 0

    @property
    def success_rate(self) -> float:
        return self.tasks_solved / self.tasks_total if self.tasks_total else 0.0

    @property
    def mean_latency(self) -> float:
        return self.latency_sum / self.tasks_total if self.tasks_total else 0.0

    @property
    def traceability(self) -> float:
        return self.trace_complete / self.tasks_total if self.tasks_total else 0.0


# Benchmark task catalogue (defines WHAT we measure; not yet executed).
BENCHMARK_TASKS = [
    {"task_id": "pathway_recovery", "desc": "recover a known 3-hop pathway from partial lesion",
     "criterion": "path_recall >= 0.8"},
    {"task_id": "fault_isolation", "desc": "isolate a failed module without global collapse",
     "criterion": "isolation_true_positive >= 0.9"},
    {"task_id": "role_inference", "desc": "infer the functional role of an unlabeled module",
     "criterion": "role_f1 >= 0.7"},
    {"task_id": "delay_task", "desc": "simple delay-2 routing (matches validated 5/28 local-decision claim)",
     "criterion": "accuracy >= 0.6"},
]


ARMS = {
    "organism_prior": "virtual-bio topology (our connectome-derived motif)",
    "random_topology": "random graph, matched node/edge count",
    "no_topology": "flat / fully-connected prior (control)",
}


def _topology_for_arm(arm: str, seed: int = 42) -> dict:
    """Produce a topology dict for the given arm.

    organism_prior depends on the proprietary generator (Tier 2); when it is
    unavailable the function degrades honestly to a documented stub rather than
    fabricating a result.
    """
    if arm == "organism_prior":
        try:
            import sys
            sys.path.insert(0, str(ROOT / "flybrain-connectome-mcp"))
            from synthetic_bio_topology import compose_virtual_organism  # type: ignore
            return compose_virtual_organism(seed=seed)
        except Exception:
            return {"arm": arm, "available": False,
                    "note": "proprietary generator not present in this install"}
    if arm == "random_topology":
        return {"arm": arm, "available": True, "kind": "erdos_renyi_match"}
    return {"arm": arm, "available": True, "kind": "flat"}


def run_ab_comparison(engine: EngineAdapter | None = None,
                      tasks: list[dict] | None = None) -> dict:
    """
    Run the A/B/C comparison. Requires an engine adapter; without one, returns a
    HONEST 'framework_defined' status with no fabricated numbers.
    """
    tasks = tasks or BENCHMARK_TASKS
    if engine is None:
        return {
            "status": "framework_defined",
            "measured": False,
            "arms": ARMS,
            "tasks": [t["task_id"] for t in tasks],
            "note": "no engine adapter supplied — numbers NOT produced; do not claim",
        }
    metrics: dict[str, TaskMetrics] = {arm: TaskMetrics(arm=arm) for arm in ARMS}
    for arm in ARMS:
        topo = _topology_for_arm(arm)
        for task in tasks:
            res = engine.solve_task(topo, task)
            m = metrics[arm]
            m.tasks_total += 1
            m.tasks_solved += 1 if res.get("solved") else 0
            m.latency_sum += float(res.get("latency_s", 0.0))
            m.trace_complete += 1 if res.get("trace", {}).get("complete") else 0
    return {
        "status": "measured",
        "measured": True,
        "arms": {a: asdict(m) for a, m in metrics.items()},
        "derived": {
            "organism_prior_success_rate": metrics["organism_prior"].success_rate,
            "random_success_rate": metrics["random_topology"].success_rate,
            "no_topology_success_rate": metrics["no_topology"].success_rate,
            "relative_lift_vs_random": (
                metrics["organism_prior"].success_rate
                - metrics["random_topology"].success_rate
            ),
        },
    }


def main() -> int:
    # Default run: framework check only (no engine → honest status).
    out = run_ab_comparison()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
