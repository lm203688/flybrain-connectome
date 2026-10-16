"""F4a · Robustness metrics — bridge fraction & removal impact.

Read-only CLI. Takes a graph JSON (nodes/edges shape) and a removal count k,
removes the k highest-weight edges (the intervention), and reports:

  - bridge_fraction_before / bridge_fraction_after
  - removal_drop_per_edge  (mean weight removed per edge in k)
  - n_components_before / n_components_after

No side effects. Prints a single JSON object to stdout.

Usage:
    python -m metrics.robustness --graph path/to/graph.json --k 3
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _load_graph(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _adjacency(graph: dict[str, Any]) -> dict[str, list[tuple[str, float]]]:
    adj: dict[str, list[tuple[str, float]]] = {}
    for n in graph.get("nodes", []):
        adj.setdefault(n, [])
    for e in graph.get("edges", []):
        w = float(e.get("weight", 1.0))
        u, v = e["from"], e["to"]
        adj.setdefault(u, []).append((v, w))
        adj.setdefault(v, []).append((u, w))
    return adj


def _n_components(adj: dict[str, list[tuple[str, float]]]) -> int:
    """Count connected components via BFS (undirected view)."""
    seen: set[str] = set()
    count = 0
    for start in adj:
        if start in seen:
            continue
        count += 1
        stack = [start]
        seen.add(start)
        while stack:
            node = stack.pop()
            for nxt, _ in adj.get(node, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
    return count


def _bridge_edges(
    adj: dict[str, list[tuple[str, float]]], n_nodes: int
) -> int:
    """Tarjan bridge count. Returns number of edges whose removal
    strictly increases the connected-component count.

    This is the classical O(V+E) algorithm, adapted to an adjacency
    multimap (parallel edges do not count as bridges).
    """
    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    timer = [0]
    bridges = [0]

    def dfs(u: str) -> None:
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        for v, _w in adj[u]:
            if v not in disc:
                parent[v] = u
                dfs(v)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    bridges[0] += 1
            elif v != parent.get(u):
                low[u] = min(low[u], disc[v])

    for node in adj:
        if node not in disc:
            parent[node] = None
            dfs(node)
    return bridges[0]


def run(graph: dict[str, Any], k: int) -> dict[str, Any]:
    n_edges = len(graph.get("edges", []))
    adj_before = _adjacency(graph)
    n_nodes = len(graph.get("nodes", []))

    if k <= 0:
        return {
            "metric": "F4a_robustness",
            "n_nodes": n_nodes,
            "n_edges": n_edges,
            "k": k,
            "note": "k <= 0: no intervention performed",
            "bridge_fraction_before": None,
            "bridge_fraction_after": None,
            "removal_drop_per_edge": 0.0,
        }

    # Intervention: remove the top-k edges by weight (ties broken by first occurrence).
    weighted = sorted(graph["edges"], key=lambda e: -float(e.get("weight", 1.0)))
    removed = weighted[:k]
    removed_weights = [float(e.get("weight", 1.0)) for e in removed]

    remaining_edges = [e for e in graph["edges"] if e not in removed]
    graph_after = {
        "nodes": graph.get("nodes", []),
        "edges": remaining_edges,
    }
    adj_after = _adjacency(graph_after)

    b_before = _bridge_edges(adj_before, n_nodes)
    b_after = _bridge_edges(adj_after, n_nodes)
    n_edges_after = len(graph_after["edges"])

    bf_before = b_before / n_edges if n_edges else 0.0
    bf_after = b_after / n_edges_after if n_edges_after else 0.0

    return {
        "metric": "F4a_robustness",
        "n_nodes": n_nodes,
        "n_edges_before": n_edges,
        "n_edges_after": n_edges_after,
        "k": k,
        "bridge_count_before": b_before,
        "bridge_count_after": b_after,
        "bridge_fraction_before": round(bf_before, 6),
        "bridge_fraction_after": round(bf_after, 6),
        "delta_bridge_fraction": round(bf_after - bf_before, 6),
        "removed_edge_weights": removed_weights,
        "removal_drop_per_edge": round(sum(removed_weights) / k, 6) if k else 0.0,
        "n_components_before": _n_components(adj_before),
        "n_components_after": _n_components(adj_after),
        "inputs": {"graph_sha256_hint": "not computed; see README for verification policy"},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graph", required=True, help="Path to graph JSON")
    ap.add_argument("--k", type=int, default=3, help="Number of highest-weight edges to remove")
    args = ap.parse_args()

    graph = _load_graph(args.graph)
    result = run(graph, args.k)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
