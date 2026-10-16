"""F1 · Controllability metrics — minimum control set & reachability.

Read-only CLI. Takes a graph JSON and reports:

  - n_control_nodes           (nodes that must be externally driven to reach
                                every other node via directed reachability)
  - controllability_density   (|control set| / |nodes|)
  - reachability_matrix_stats (mean, max, and count of nodes reachable from each node)
  - unreachability_pairs      (number of (u,v) pairs with no directed path u→v)

Uses a simple directed reachability expansion (BFS on outgoing edges).
Reads `weight` for reporting only; the reachability metric is structural,
not weighted.

Usage:
    python -m metrics.controllability --graph path/to/graph.json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _load_graph(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _out_adjacency(graph: dict[str, Any]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {}
    for n in graph.get("nodes", []):
        adj.setdefault(n, [])
    for e in graph.get("edges", []):
        adj.setdefault(e["from"], []).append(e["to"])
    return adj


def _reachables(adj: dict[str, list[str]]) -> dict[str, set[str]]:
    """Directed reachability: reach(u) = {v : there exists a directed path u→v}."""
    result: dict[str, set[str]] = {}
    for u in adj:
        seen: set[str] = set()
        stack = list(adj[u])
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            stack.extend(adj.get(v, []))
        result[u] = seen
    return result


def run(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = list(graph.get("nodes", []))
    n = len(nodes)
    edges = graph.get("edges", [])

    out_adj = _out_adjacency(graph)
    reach = _reachables(out_adj)

    # A node is in the minimum control set if it has in-degree 0 (nothing points to it)
    # OR if it has strictly greater out-reachability than all of its predecessors.
    # This is the classical "no incoming edges → must be driven" plus the
    # "reachability expansion" heuristic that produces an upper bound on
    # the true minimum control set. Documented as a bound, not the exact value.
    in_deg: dict[str, int] = {u: 0 for u in nodes}
    for e in edges:
        in_deg[e["to"]] = in_deg.get(e["to"], 0) + 1

    control_set: set[str] = set()
    for u in nodes:
        if in_deg.get(u, 0) == 0:
            control_set.add(u)
    # Add any node whose reach is strictly larger than the union of its predecessors' reach.
    in_adj: dict[str, list[str]] = {u: [] for u in nodes}
    for e in edges:
        in_adj[e["from"]].append(e["to"])
        # build in-edges for the "predecessor" check
    in_edges: dict[str, list[str]] = {u: [] for u in nodes}
    for e in edges:
        in_edges[e["to"]].append(e["from"])
    for u in nodes:
        if u in control_set:
            continue
        preds_reach: set[str] = set()
        for p in in_edges.get(u, []):
            preds_reach.update(reach.get(p, set()))
        preds_reach.add(u)
        if reach.get(u, set()) != preds_reach:
            control_set.add(u)

    # Reachability matrix stats
    reach_sizes = [len(reach[u]) for u in nodes]
    mean_reach = sum(reach_sizes) / n if n else 0.0
    max_reach = max(reach_sizes) if n else 0
    total_pairs = n * (n - 1)
    reached_pairs = sum(reach_sizes)
    unreachable_pairs = total_pairs - reached_pairs

    return {
        "metric": "F1_controllability",
        "n_nodes": n,
        "n_edges": len(edges),
        "n_control_nodes_bound": len(control_set),
        "controllability_density_bound": round(len(control_set) / n, 6) if n else 0.0,
        "control_set_members": sorted(control_set),
        "reachability": {
            "mean_outreach_size": round(mean_reach, 4),
            "max_outreach_size": max_reach,
            "total_ordered_pairs": total_pairs,
            "reachable_pairs": reached_pairs,
            "unreachable_pairs": unreachable_pairs,
            "reachability_fraction": round(reached_pairs / total_pairs, 6) if total_pairs else 0.0,
        },
        "caveat": (
            "n_control_nodes_bound is an upper bound (structural heuristic), "
            "not the exact minimum control set in the Liu-Somarriba sense. "
            "The exact value requires structural controllability theory which is "
            "not implemented here; see Liu et al., Science 332 (2011)."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", required=True, help="Path to graph JSON")
    args = ap.parse_args()

    graph = _load_graph(args.graph)
    result = run(graph)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
