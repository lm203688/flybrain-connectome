#!/usr/bin/env python3
"""R1 Mechanism Hypothesis A — Critical edge sparsity.

Tests the hypothesis: "92.6% fault isolation comes from critical edge sparsity."

Specifically: the number of bridges (edges whose removal disconnects the graph)
and the fraction of critical edges should correlate with isolation effect size.

This is the FOURTH mechanism hypothesis tested after R1's three were all falsified:
  - P1: feature_addition (module→readout reachability) — R²=0.025, FALSIFIED
  - P2: task_alignment (readout module choice) — std=0.0, FALSIFIED  
  - P3: edge_density_correlation — slope=+0.226, R²=0.003, FALSIFIED

Hypothesis A: critical_edge_count / bridge_fraction correlates with isolation effect.
  - R² > 0.5 → hypothesis SUPPORTED (first mechanism to explain 92.6%)
  - R² < 0.1 → hypothesis FALSIFIED (fourth mechanism falsified, L3 remains open)

Usage:
    python scripts/r1_mechanism_a.py
    python scripts/r1_mechanism_a.py --n-topologies 100
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP_DIR))

from llm_tasks import (  # noqa: E402
    Blueprint,
    MOTIF_FAMILY_LABELS,
    build_evidence_blueprint,
    build_random_blueprint,
    _bfs_hops,
    _pick_hub,
)


# ============================================================ topology generation

def generate_topologies(
    n_topologies: int,
    n_nodes: int = 6,
    seed: int = 42,
) -> list[Blueprint]:
    """Generate n_topologies blueprints — SAME LOGIC AS r1_expansion.py."""
    rng = random.Random(seed)
    blueprints = []
    for i in range(n_topologies):
        if i % 3 == 0:
            bp = build_evidence_blueprint(rng, {"n_nodes": n_nodes, "n_edges": n_nodes + 1})
        elif i % 3 == 1:
            bp = build_random_blueprint(rng, {"n_nodes": n_nodes, "n_edges": n_nodes + 1})
        else:
            motif = rng.choice(MOTIF_FAMILY_LABELS)
            nodes = tuple(f"n{j}" for j in range(n_nodes))
            n_edges = rng.randint(n_nodes, n_nodes * 2)
            all_pairs = [(a, b) for a in nodes for b in nodes if a != b]
            edges = tuple(rng.sample(all_pairs, k=min(n_edges, len(all_pairs))))
            bp = Blueprint(
                name=f"mix_{motif}_{i}_{rng.randint(0, 99999)}",
                nodes=nodes,
                edges=edges,
                motif_family=motif,
                capability_distribution={"mixed": n_nodes},
                origin="mixed",
            )
        blueprints.append(bp)
    return blueprints


# ============================================================ BFS utilities

def _bfs_all(nodes, edges, src: str) -> dict[str, int]:
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        if a in adj:
            adj[a].append(b)
    dist = {n: -1 for n in nodes}
    if src not in dist:
        return dist
    dist[src] = 0
    frontier = [src]
    depth = 0
    while frontier:
        depth += 1
        nxt: list[str] = []
        for u in frontier:
            for v in adj.get(u, []):
                if v in dist and dist[v] == -1:
                    dist[v] = depth
                    nxt.append(v)
        frontier = nxt
    return dist


# ============================================================ isolation effect

def compute_isolation_effect_size(bp: Blueprint, n_trials: int = 10) -> float:
    """Multi-trial isolation effect: average over random hub choices.
    
    Single-trial version (as in r1_expansion.py) produces zero variance
    because _pick_hub always selects the same node. Multi-trial version
    varies the damaged hub to expose structural differences.
    """
    rng = random.Random(42)
    sizes = []
    for _ in range(n_trials):
        node = rng.choice(bp.nodes)
        orig_dist = _bfs_all(bp.nodes, bp.edges, node)
        orig_reachable = sum(1 for d in orig_dist.values() if d > 0)

        perturbed_edges = [(a, b) for a, b in bp.edges if a != node]
        perturbed_dist = _bfs_all(bp.nodes, perturbed_edges, node)
        perturbed_reachable = sum(1 for d in perturbed_dist.values() if d > 0)

        if orig_reachable > 0:
            isolated = orig_reachable - perturbed_reachable
            sizes.append(isolated / orig_reachable)

    return sum(sizes) / len(sizes) if sizes else 0.0


# ============================================================ critical edge analysis

@dataclass
class CriticalEdgeFeatures:
    """Critical edge (bridge) features for mechanism hypothesis A."""
    n_nodes: int
    n_edges: int
    n_bridges: int          # edges whose removal disconnects the graph
    bridge_fraction: float  # n_bridges / n_edges
    n_articulation_points: int  # vertices whose removal disconnects the graph
    edge_connectivity: int  # min edges to remove to disconnect (0 if already disconnected)
    n_weakly_connected_components: int


def _count_weakly_connected_components(nodes: list[str], edges: list[tuple[str, str]]) -> int:
    """Count weakly connected components (treating edges as undirected)."""
    undirected: dict[str, set[str]] = {n: set() for n in nodes}
    for a, b in edges:
        if a in undirected and b in undirected:
            undirected[a].add(b)
            undirected[b].add(a)
    visited: set[str] = set()
    n_comp = 0
    for node in nodes:
        if node not in visited:
            n_comp += 1
            queue = deque([node])
            while queue:
                u = queue.popleft()
                if u in visited:
                    continue
                visited.add(u)
                for v in undirected.get(u, []):
                    if v not in visited:
                        queue.append(v)
    return n_comp


def _find_bridges(nodes: list[str], edges: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """Find all bridges in the directed graph.
    
    A bridge is an edge (u, v) such that removing it increases the number
    of weakly connected components. We use Tarjan's algorithm adapted for
    directed graphs (edge connectivity via incremental removal test).
    
    For efficiency on small graphs (n≤6), we use the direct removal test.
    """
    if not edges:
        return set()
    
    bridges: set[tuple[str, str]] = set()
    base_ncc = _count_weakly_connected_components(nodes, edges)
    
    for edge in edges:
        # Test if removing this edge disconnects the graph
        remaining_edges = [e for e in edges if e != edge]
        new_ncc = _count_weakly_connected_components(nodes, remaining_edges)
        if new_ncc > base_ncc:
            bridges.add(edge)
    
    return bridges


def _find_articulation_points(nodes: list[str], edges: list[tuple[str, str]]) -> set[str]:
    """Find all articulation points (cut vertices) in the graph.
    
    An articulation point is a vertex whose removal increases the number
    of weakly connected components.
    """
    if not edges:
        return set()
    
    base_ncc = _count_weakly_connected_components(nodes, edges)
    articulation_points: set[str] = set()
    
    for node in nodes:
        remaining_nodes = [n for n in nodes if n != node]
        remaining_edges = [(a, b) for a, b in edges if a != node and b != node]
        if not remaining_nodes:
            continue
        new_ncc = _count_weakly_connected_components(remaining_nodes, remaining_edges)
        if new_ncc > base_ncc:
            articulation_points.add(node)
    
    return articulation_points


def _compute_edge_connectivity(nodes: list[str], edges: list[tuple[str, str]]) -> int:
    """Compute edge connectivity: minimum number of edges to remove to disconnect.
    
    For small graphs, uses brute-force subset enumeration.
    Returns 0 if the graph is already disconnected.
    """
    base_ncc = _count_weakly_connected_components(nodes, edges)
    if base_ncc > 1:
        return 0  # already disconnected
    
    if not edges:
        return 0
    
    m = len(edges)
    # Try k=1, 2, 3... edges
    for k in range(1, m + 1):
        # Check all combinations of k edges to remove
        for combo in _combinations(edges, k):
            remaining = [e for e in edges if e not in combo]
            new_ncc = _count_weakly_connected_components(nodes, remaining)
            if new_ncc > base_ncc:
                return k
    
    return m  # graph is complete (can't disconnect by removing edges)


def _combinations(lst, k):
    """Generate all k-combinations of a list (for small lists)."""
    if k == 0:
        yield ()
        return
    if len(lst) < k:
        return
    for i in range(len(lst)):
        for rest in _combinations(lst[i+1:], k-1):
            yield (lst[i],) + rest


def compute_critical_edge_features(bp: Blueprint) -> CriticalEdgeFeatures:
    """Compute all critical edge features for a blueprint."""
    nodes = list(bp.nodes)
    edges = list(bp.edges)
    n = len(nodes)
    m = len(edges)
    
    # Bridge detection
    bridges = _find_bridges(nodes, edges)
    n_bridges = len(bridges)
    bridge_fraction = n_bridges / m if m > 0 else 0.0
    
    # Articulation points
    articulation_points = _find_articulation_points(nodes, edges)
    
    # Edge connectivity
    edge_connectivity = _compute_edge_connectivity(nodes, edges)
    
    # Weakly connected components
    n_wcc = _count_weakly_connected_components(nodes, edges)
    
    return CriticalEdgeFeatures(
        n_nodes=n,
        n_edges=m,
        n_bridges=n_bridges,
        bridge_fraction=bridge_fraction,
        n_articulation_points=len(articulation_points),
        edge_connectivity=edge_connectivity,
        n_weakly_connected_components=n_wcc,
    )


# ============================================================ linear regression

def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """OLS linear regression. Returns (slope, intercept, r_squared)."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, 0.0
    
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    
    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    ss_yy = sum((y - mean_y) ** 2 for y in ys)
    
    if ss_xx == 0 or ss_yy == 0:
        return 0.0, mean_y, 0.0
    
    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1.0 - ss_res / ss_yy if ss_yy > 0 else 0.0
    
    return slope, intercept, r_squared


# ============================================================ main

def main() -> int:
    ap = argparse.ArgumentParser(description="R1 Mechanism Hypothesis A: critical edge sparsity")
    ap.add_argument("--n-topologies", type=int, default=30,
                    help="number of topologies to test (default: 30, matching R1)")
    ap.add_argument("--n-nodes", type=int, default=10,
                    help="nodes per topology (default: 10 — n=6 saturates isolation to 0/1)")
    ap.add_argument("--seed", type=int, default=42,
                    help="random seed (default: 42, matching R1)")
    ap.add_argument("--output-dir", default="./_r1_mechanism_a",
                    help="output directory")
    ap.add_argument("--quiet", action="store_true", help="suppress per-topology output")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print(f"R1 Mechanism Hypothesis A — Critical Edge Sparsity")
    print(f"  n_topologies={args.n_topologies}, n_nodes={args.n_nodes}, seed={args.seed}")
    print(f"  output: {out_dir}")
    print("=" * 70)

    # Generate topologies (same as R1)
    blueprints = generate_topologies(args.n_topologies, args.n_nodes, args.seed)

    # Compute features and isolation for each topology
    results = []
    for i, bp in enumerate(blueprints):
        # Isolation effect
        isolation = compute_isolation_effect_size(bp)
        
        # Critical edge features
        crit = compute_critical_edge_features(bp)
        
        result = {
            "topology_idx": i,
            "blueprint_name": bp.name,
            "motif_family": bp.motif_family,
            "origin": bp.origin,
            "n_nodes": crit.n_nodes,
            "n_edges": crit.n_edges,
            "isolation_effect_size": isolation,
            "n_bridges": crit.n_bridges,
            "bridge_fraction": crit.bridge_fraction,
            "n_articulation_points": crit.n_articulation_points,
            "edge_connectivity": crit.edge_connectivity,
            "n_weakly_connected_components": crit.n_weakly_connected_components,
        }
        results.append(result)
        
        if not args.quiet:
            print(f"  [{i+1:2d}/{args.n_topologies}] {bp.name[:30]:<30s} "
                  f"iso={isolation:.3f} bridges={crit.n_bridges}/{crit.n_edges} "
                  f"frac={crit.bridge_fraction:.3f} ec={crit.edge_connectivity}")

    # ============================================================ analysis
    
    print(f"\n{'=' * 70}")
    print(f"MECHANISM ANALYSIS")
    print(f"{'=' * 70}")
    
    isolation_values = [r["isolation_effect_size"] for r in results]
    mean_iso = sum(isolation_values) / len(isolation_values)
    n_high = sum(1 for x in isolation_values if x > 0.3)
    print(f"\nIsolation effect: mean={mean_iso:.3f}, "
          f"n_high(>0.3)={n_high}/{len(isolation_values)} "
          f"({100*n_high/len(isolation_values):.1f}%)")
    
    # Test 1: bridge_fraction vs isolation
    print(f"\n--- Test 1: bridge_fraction vs isolation_effect_size ---")
    xf = [r["bridge_fraction"] for r in results]
    yf = [r["isolation_effect_size"] for r in results]
    slope_f, intercept_f, r2_f = linear_regression(xf, yf)
    print(f"  slope={slope_f:.4f}, intercept={intercept_f:.4f}, R²={r2_f:.4f}")
    
    # Test 2: n_bridges vs isolation
    print(f"\n--- Test 2: n_bridges vs isolation_effect_size ---")
    xb = [float(r["n_bridges"]) for r in results]
    yb = [r["isolation_effect_size"] for r in results]
    slope_b, intercept_b, r2_b = linear_regression(xb, yb)
    print(f"  slope={slope_b:.4f}, intercept={intercept_b:.4f}, R²={r2_b:.4f}")
    
    # Test 3: n_articulation_points vs isolation
    print(f"\n--- Test 3: n_articulation_points vs isolation_effect_size ---")
    xa = [float(r["n_articulation_points"]) for r in results]
    ya = [r["isolation_effect_size"] for r in results]
    slope_a, intercept_a, r2_a = linear_regression(xa, ya)
    print(f"  slope={slope_a:.4f}, intercept={intercept_a:.4f}, R²={r2_a:.4f}")
    
    # Test 4: edge_connectivity vs isolation
    print(f"\n--- Test 4: edge_connectivity vs isolation_effect_size ---")
    xe = [float(r["edge_connectivity"]) for r in results]
    ye = [r["isolation_effect_size"] for r in results]
    slope_e, intercept_e, r2_e = linear_regression(xe, ye)
    print(f"  slope={slope_e:.4f}, intercept={intercept_e:.4f}, R²={r2_e:.4f}")
    
    # ============================================================ verdict
    
    print(f"\n{'=' * 70}")
    print(f"VERDICT")
    print(f"{'=' * 70}")
    
    best_r2 = max(r2_f, r2_b, r2_a, r2_e)
    best_test = max(
        ("bridge_fraction", r2_f),
        ("n_bridges", r2_b),
        ("n_articulation_points", r2_a),
        ("edge_connectivity", r2_e),
        key=lambda x: x[1]
    )
    
    print(f"\n  Best predictor: {best_test[0]} (R²={best_test[1]:.4f})")
    print(f"\n  Compared to R1's three falsified mechanisms:")
    print(f"    P1 feature_addition:    R²=0.0249")
    print(f"    P2 task_alignment:      std=0.0 (no signal)")
    print(f"    P3 edge_density:        R²=0.0031")
    print(f"    Hypothesis A best:      R²={best_r2:.4f}")
    
    if best_r2 > 0.5:
        verdict = "SUPPORTED"
        print(f"\n  ✅ HYPOTHESIS A SUPPORTED (R²={best_r2:.4f} > 0.5)")
        print(f"     Critical edge sparsity EXPLAINS 92.6% fault isolation!")
        print(f"     This is the first mechanism to successfully predict isolation.")
    elif best_r2 > 0.2:
        verdict = "PARTIALLY_SUPPORTED"
        print(f"\n  🟡 HYPOTHESIS A PARTIALLY SUPPORTED (R²={best_r2:.4f} > 0.2)")
        print(f"     Critical edge sparsity explains some, but not most, variance.")
        print(f"     Other mechanisms likely contribute.")
    elif best_r2 > 0.1:
        verdict = "WEAK_SIGNAL"
        print(f"\n  🟡 HYPOTHESIS A WEAK SIGNAL (R²={best_r2:.4f} > 0.1)")
        print(f"     Marginal correlation — may need larger sample or different features.")
    else:
        verdict = "FALSIFIED"
        print(f"\n  ❌ HYPOTHESIS A FALSIFIED (R²={best_r2:.4f} < 0.1)")
        print(f"     Critical edge sparsity does NOT explain isolation.")
        print(f"     FOURTH mechanism falsified. L3 theoretical layer remains open.")
        print(f"     This strengthens the negative result: isolation is robust to")
        print(f"     all four tested structural mechanisms.")
    
    # ============================================================ output
    
    summary = {
        "params": {
            "n_topologies": args.n_topologies,
            "n_nodes": args.n_nodes,
            "seed": args.seed,
        },
        "isolation_summary": {
            "mean": mean_iso,
            "n_high": n_high,
            "n_total": len(isolation_values),
            "fraction_high": n_high / len(isolation_values),
        },
        "tests": {
            "bridge_fraction": {"slope": slope_f, "intercept": intercept_f, "r_squared": r2_f},
            "n_bridges": {"slope": slope_b, "intercept": intercept_b, "r_squared": r2_b},
            "n_articulation_points": {"slope": slope_a, "intercept": intercept_a, "r_squared": r2_a},
            "edge_connectivity": {"slope": slope_e, "intercept": intercept_e, "r_squared": r2_e},
        },
        "best_predictor": {"feature": best_test[0], "r_squared": best_test[1]},
        "verdict": verdict,
        "comparison_with_r1": {
            "p1_feature_addition_r2": 0.0249,
            "p2_task_alignment_std": 0.0,
            "p3_edge_density_r2": 0.0031,
            "hypothesis_a_best_r2": best_r2,
        },
    }
    
    json_path = out_dir / "mechanism_a_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "all_results": results}, f, 
                  indent=2, ensure_ascii=False)
    print(f"\n  JSON: {json_path}")
    
    csv_path = out_dir / "mechanism_a_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader()
        w.writerows(results)
    print(f"  CSV:  {csv_path}")
    
    elapsed = time.time() - t0
    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Verdict: {verdict}")
    
    return 0 if verdict != "FALSIFIED" else 0  # always return 0 (negative result is valid)


if __name__ == "__main__":
    raise SystemExit(main())
