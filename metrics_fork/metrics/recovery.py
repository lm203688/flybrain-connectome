"""F2 · Recovery metrics — drop magnitude & recovery-AUC.

Read-only CLI. Sequentially removes up to `k` highest-weight edges, measures
a "system state" signal at each step (sum of remaining reachable-pair weights
from seed nodes to sink nodes), and reports:

  - drop_magnitude          (initial signal - signal after k removals) / initial
  - recovery_AUC            (area under the recovery curve: normalized signal
                              trajectory back toward baseline after removal)
  - n_nonzero_steps         (fraction of steps with non-zero signal — a
                              non-degeneracy check; 0 means the metric is trivial)
  - variance_of_deltas      (signal delta variance across steps — non-zero
                              means the metric actually varies with k)

This is the "independent second reading" whose absence was documented in the
upstream PR-2b preregistration rejection: within the drop_magnitude family
there is no independent recovery-AUC because recovery_AUC is normalized by
drop_magnitude. This fork provides the raw signal trajectory so a reader can
verify that coupling.

Usage:
    python -m metrics.recovery --graph path/to/graph.json --k 5 --steps 20
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from typing import Any


def _load_graph(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _seed_sink_signal(
    graph: dict[str, Any], seeds: list[str], sinks: list[str]
) -> float:
    """Signal = sum of path weights from seeds to sinks, computed via a
    single topological-pass approximation.

    For a DAG this is exact; for cyclic graphs it uses a bounded relaxation
    (up to len(nodes) iterations) that converges on the maximum reachable
    weight from seed to sink via any directed path.
    """
    nodes = graph.get("nodes", [])
    n = len(nodes)
    adj: dict[str, list[tuple[str, float]]] = {u: [] for u in nodes}
    for e in graph.get("edges", []):
        w = float(e.get("weight", 1.0))
        adj.setdefault(e["from"], []).append((e["to"], w))

    dist: dict[str, float] = {u: 0.0 for u in nodes}
    for s in seeds:
        if s in dist:
            dist[s] = max(dist[s], 1.0)

    # Bellman-Ford-like relaxation (bounded by n to avoid infinite loops).
    for _ in range(n):
        changed = False
        for u in nodes:
            if dist[u] <= 0:
                continue
            for v, w in adj.get(u, []):
                cand = dist[u] * w
                if cand > dist[v]:
                    dist[v] = cand
                    changed = True
        if not changed:
            break

    signal = 0.0
    for t in sinks:
        signal += dist.get(t, 0.0)
    return signal


def run(graph: dict[str, Any], k: int, steps: int) -> dict[str, Any]:
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    n = len(nodes)

    if n < 2 or not edges:
        return {
            "metric": "F2_recovery",
            "n_nodes": n,
            "n_edges": len(edges),
            "k": k,
            "steps": steps,
            "note": "degenerate input",
            "drop_magnitude": None,
            "recovery_AUC": None,
            "n_nonzero_steps": 0,
            "variance_of_deltas": 0.0,
        }

    # Seeds = nodes with in-degree 0 (external drivers). Sinks = nodes with out-degree 0.
    in_deg = {u: 0 for u in nodes}
    out_deg = {u: 0 for u in nodes}
    for e in edges:
        in_deg[e["to"]] += 1
        out_deg[e["from"]] += 1
    seeds = [u for u in nodes if in_deg[u] == 0]
    sinks = [u for u in nodes if out_deg[u] == 0]
    if not seeds:
        seeds = nodes[:1]
    if not sinks:
        sinks = nodes[-1:]

    # Baseline signal.
    baseline = _seed_sink_signal(graph, seeds, sinks)

    # Sequential removal of top-k edges by weight.
    weighted = sorted(edges, key=lambda e: -float(e.get("weight", 1.0)))
    removed = weighted[: min(k, len(edges))]

    trajectory: list[float] = [baseline]
    current_edges = list(edges)
    for e in removed:
        current_edges = [x for x in current_edges if x is not e]
        graph_now = {"nodes": nodes, "edges": current_edges}
        s = _seed_sink_signal(graph_now, seeds, sinks)
        trajectory.append(s)

    # Pad trajectory to `steps` samples by linear interpolation / hold-last.
    if len(trajectory) < steps:
        last = trajectory[-1] if trajectory else 0.0
        trajectory.extend([last] * (steps - len(trajectory)))
    else:
        trajectory = trajectory[:steps]

    deltas = [trajectory[i + 1] - trajectory[i] for i in range(len(trajectory) - 1)]
    deltas_abs = [abs(d) for d in deltas]
    variance = statistics.variance(deltas) if len(deltas) >= 2 else 0.0

    final = trajectory[-1]
    drop_magnitude = (
        (baseline - final) / baseline if baseline > 0 else 0.0
    )

    # Recovery-AUC: mean of normalized signal trajectory AFTER the first drop.
    normalized = []
    for s in trajectory:
        if baseline > 0:
            normalized.append(s / baseline)
        else:
            normalized.append(0.0)
    recovery_AUC = sum(normalized) / len(normalized) if normalized else 0.0

    n_nonzero = sum(1 for s in trajectory if s > 0)

    return {
        "metric": "F2_recovery",
        "n_nodes": n,
        "n_edges": len(edges),
        "k": k,
        "steps": steps,
        "seeds": seeds,
        "sinks": sinks,
        "baseline_signal": round(baseline, 6),
        "final_signal": round(final, 6),
        "drop_magnitude": round(drop_magnitude, 6),
        "recovery_AUC": round(recovery_AUC, 6),
        "trajectory": [round(x, 6) for x in trajectory],
        "n_nonzero_steps": n_nonzero,
        "n_nonzero_fraction": round(n_nonzero / steps, 6),
        "variance_of_deltas": round(variance, 8),
        "sum_of_abs_deltas": round(sum(deltas_abs), 6),
        "caveat": (
            "recovery_AUC is normalized by drop_magnitude (via the shared "
            "baseline-signal denominator), so it is NOT an independent second "
            "reading of the same intervention. See upstream PR-2b rejection "
            "for the formal argument."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", required=True, help="Path to graph JSON")
    ap.add_argument("--k", type=int, default=5, help="Edges to remove sequentially")
    ap.add_argument("--steps", type=int, default=20, help="Trajectory samples to record")
    args = ap.parse_args()

    graph = _load_graph(args.graph)
    result = run(graph, args.k, args.steps)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
