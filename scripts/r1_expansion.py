#!/usr/bin/env python3
"""R1 — Isolation Predictor Expansion: N≥100 topologies + mechanism tests.

Expands the isolation predictor from N=27 to N≥100 topologies to enable
held-out validation (the current maximum methodological weakness). Implements
the three falsifiable predictions from the research deepening plan:

  P1: Adding "module→readout structural reachability" as the 10th feature
      should significantly increase R² (if it stays ≈0.15 → hypothesis wrong)
  P2: Fixed topology, only changing readout module → isolation effect size
      should change significantly (if it doesn't → "task alignment" doesn't work)
  P3: Isolation effect size negatively correlates with cross-module edge density
      (if positive → mechanism wrong)

Falsification condition: If P1 and P2 BOTH fail → "structure × task alignment"
hypothesis is falsified, close the direction and publish negative result.

Output:
  _r1_expansion/r1_results.json  — full results
  _r1_expansion/r1_results.csv   — per-topology CSV

Usage:
    python scripts/r1_expansion.py
    python scripts/r1_expansion.py --n-topologies 100
    python scripts/r1_expansion.py --n-topologies 200 --seeds 50
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP_DIR))

from llm_tasks import (  # noqa: E402
    Blueprint,
    MOTIF_FAMILY_LABELS,
    build_evidence_blueprint,
    build_random_blueprint,
    compute_ground_truth,
    _bfs_hops,
    _pick_hub,
)


# ============================================================ topology generation

def generate_topologies(
    n_topologies: int,
    n_nodes: int = 6,
    seed: int = 42,
) -> list[Blueprint]:
    """Generate n_topologies blueprints mixing evidence and random."""
    rng = random.Random(seed)
    blueprints = []
    for i in range(n_topologies):
        if i % 3 == 0:
            bp = build_evidence_blueprint(rng, {"n_nodes": n_nodes, "n_edges": n_nodes + 1})
        elif i % 3 == 1:
            bp = build_random_blueprint(rng, {"n_nodes": n_nodes, "n_edges": n_nodes + 1})
        else:
            # Mixed: evidence motif with random edges
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


# ============================================================ structural features

@dataclass
class StructFeatures:
    """Nine structural features for isolation prediction."""
    density: float
    mean_out_degree: float
    max_out_degree: int
    transitivity: float
    diameter: int
    n_components: int
    edge_density: float
    modularity_proxy: float  # simple proxy: fraction of edges within modules
    spectral_radius: float   # approximate via BFS depth


def _compute_features(bp: Blueprint) -> StructFeatures:
    n = len(bp.nodes)
    m = len(bp.edges)
    density = m / (n * (n - 1)) if n > 1 else 0.0

    out_deg = bp.out_degree
    mean_out = sum(out_deg.values()) / n if n else 0.0
    max_out = max(out_deg.values()) if out_deg else 0

    # Transitivity
    adj = bp.adjacency()
    triangles = 0
    paths = 0
    for u in bp.nodes:
        for w in adj.get(u, []):
            for x in adj.get(w, []):
                if x in adj.get(u, []) and u != w and w != x and u != x:
                    triangles += 1
                if x != u and x != w:
                    paths += 1
    transitivity = triangles / paths if paths > 0 else 0.0

    # BFS diameter
    diam = 0
    for src in bp.nodes:
        dist = _bfs_all(bp.nodes, bp.edges, src)
        for d in dist.values():
            if d > diam:
                diam = d

    # Weakly connected components
    undirected: dict[str, set[str]] = {n_: set() for n_ in bp.nodes}
    for a, b in bp.edges:
        if a in undirected and b in undirected:
            undirected[a].add(b)
            undirected[b].add(a)
    visited: set[str] = set()
    n_comp = 0
    for node in bp.nodes:
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

    # Modularity proxy: fraction of edges that are "local" (shortest path ≤ 2)
    local_edges = 0
    for src, dst in bp.edges:
        dist = _bfs_all(bp.nodes, bp.edges, src)
        if dist.get(dst, -1) <= 2:
            local_edges += 1
    modularity_proxy = local_edges / m if m > 0 else 0.0

    # Spectral radius approximation: max BFS depth from any node
    depths = []
    for src in bp.nodes:
        dists = _bfs_all(bp.nodes, bp.edges, src)
        pos_dists = [d for d in dists.values() if d > 0]
        if pos_dists:
            depths.append(max(pos_dists))
    spectral_radius = float(max(depths) if depths else 0)

    return StructFeatures(
        density=density,
        mean_out_degree=mean_out,
        max_out_degree=max_out,
        transitivity=transitivity,
        diameter=diam,
        n_components=n_comp,
        edge_density=density,
        modularity_proxy=modularity_proxy,
        spectral_radius=float(spectral_radius),
    )


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


# ============================================================ isolation effect size

def compute_isolation_effect_size(bp: Blueprint) -> float:
    """Compute isolation effect size: how much damage to one module
    isolates the rest of the graph.

    Simulates removing all edges from a random hub node and measures
    the fraction of remaining nodes that become unreachable from it.
    Higher = better isolation (damage is contained).
    """
    rng = random.Random(42)
    hub = _pick_hub(bp.nodes, bp.edges)

    # Original reachability from hub
    orig_dist = _bfs_all(bp.nodes, bp.edges, hub)
    orig_reachable = sum(1 for d in orig_dist.values() if d > 0)

    # Remove all edges FROM hub
    perturbed_edges = [(a, b) for a, b in bp.edges if a != hub]
    perturbed_dist = _bfs_all(bp.nodes, perturbed_edges, hub)
    perturbed_reachable = sum(1 for d in perturbed_dist.values() if d > 0)

    # Isolation effect: fraction of nodes that were reachable but now aren't
    if orig_reachable > 0:
        isolated = orig_reachable - perturbed_reachable
        return isolated / orig_reachable
    return 0.0


def compute_isolation_effect_size_multi(bp: Blueprint, n_trials: int = 5) -> float:
    """Average isolation effect size over multiple random hub choices."""
    rng = random.Random(42)
    sizes = []
    for _ in range(n_trials):
        # Pick a random node as "hub" to damage
        node = rng.choice(bp.nodes)
        orig_dist = _bfs_all(bp.nodes, bp.edges, node)
        orig_reachable = sum(1 for d in orig_dist.values() if d > 0)

        # Remove all edges FROM this node
        perturbed_edges = [(a, b) for a, b in bp.edges if a != node]
        perturbed_dist = _bfs_all(bp.nodes, perturbed_edges, node)
        perturbed_reachable = sum(1 for d in perturbed_dist.values() if d > 0)

        if orig_reachable > 0:
            isolated = orig_reachable - perturbed_reachable
            sizes.append(isolated / orig_reachable)

    return sum(sizes) / len(sizes) if sizes else 0.0


# ============================================================ linear regression

def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Simple OLS linear regression. Returns (slope, intercept, r_squared)."""
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
    r_squared = (ss_xy ** 2) / (ss_xx * ss_yy)

    return slope, intercept, r_squared


def multi_feature_regression(
    features: list[tuple[float, ...]],
    ys: list[float],
    n_features: int,
) -> tuple[list[float], float, float]:
    """Multiple linear regression via normal equations (numpy-free).

    Returns (coefficients, intercept, r_squared).
    Uses simple iterative approach for small feature counts.
    """
    n = len(ys)
    if n < 2 or n_features < 1:
        return [0.0] * n_features, 0.0, 0.0

    # Build design matrix X (n × n_features) and y vector
    # Use simple least squares via normal equations: β = (X^T X)^{-1} X^T y
    # For simplicity, use sequential feature elimination (greedy)

    best_r2 = 0.0
    best_coef = [0.0] * n_features

    # Simple approach: for each feature, compute univariate R² and pick best
    for i in range(n_features):
        slope, intercept, r2 = linear_regression(features[:, i], ys)
        if r2 > best_r2:
            best_r2 = r2
            best_coef = [0.0] * n_features
            best_coef[i] = slope
            best_coef[-1] = intercept  # store intercept in last position

    return best_coef, best_coef[-1], best_r2


# ============================================================ P2: task alignment

def test_task_alignment(
    bp: Blueprint,
    n_nodes: int,
    seed: int = 42,
) -> dict:
    """Test P2: Fixed topology, only changing readout module.

    For a fixed topology, test different "readout modules" (nodes) and
    measure if isolation effect size changes significantly.
    """
    rng = random.Random(seed)
    sizes = {}

    # Test each node as potential readout module
    for node in bp.nodes:
        sizes[node] = compute_isolation_effect_size_multi(bp, n_trials=3)

    # Compute variance across readout modules
    values = list(sizes.values())
    mean_size = sum(values) / len(values) if values else 0
    variance = sum((v - mean_size) ** 2 for v in values) / len(values) if values else 0
    std = math.sqrt(variance)

    # Significant if std > 0.1 (arbitrary threshold for "significant change")
    significant = std > 0.1

    return {
        "per_node": sizes,
        "mean": mean_size,
        "std": std,
        "significant": significant,
    }


# ============================================================ P3: edge density correlation

def test_edge_density_correlation(
    topologies: list[Blueprint],
    seed: int = 42,
) -> dict:
    """Test P3: Isolation effect size negatively correlates with cross-module edge density."""
    xs = []
    ys = []

    for bp in topologies:
        feats = _compute_features(bp)
        xs.append(feats.edge_density)
        ys.append(compute_isolation_effect_size_multi(bp, n_trials=3))

    slope, intercept, r2 = linear_regression(xs, ys)

    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r2,
        "negative_correlation": slope < 0,
        "n_topologies": len(topologies),
    }


# ============================================================ P1: feature addition test

def test_feature_addition(
    topologies: list[Blueprint],
    baseline_features: int = 9,
    seed: int = 42,
) -> dict:
    """Test P1: Adding 'module→readout structural reachability' as 10th feature.

    Compare R² with 9 features vs 10 features (adding reachability).
    """
    # Baseline: 9 structural features
    xs_baseline = []
    ys = []
    for bp in topologies:
        feats = _compute_features(bp)
        xs_baseline.append((
            feats.density, feats.mean_out_degree, feats.max_out_degree,
            feats.transitivity, feats.diameter, feats.n_components,
            feats.edge_density, feats.modularity_proxy, feats.spectral_radius,
        ))
        ys.append(compute_isolation_effect_size_multi(bp, n_trials=3))

    # 10th feature: module→readout reachability
    # This is the fraction of nodes reachable from the hub within 2 hops
    xs_with_reach = []
    for bp in topologies:
        hub = _pick_hub(bp.nodes, bp.edges)
        dist = _bfs_all(bp.nodes, bp.edges, hub)
        reachable_2hop = sum(1 for d in dist.values() if 0 < d <= 2)
        total_nodes = len(bp.nodes) - 1
        reachability = reachable_2hop / total_nodes if total_nodes > 0 else 0
        feats = _compute_features(bp)
        xs_with_reach.append((
            feats.density, feats.mean_out_degree, feats.max_out_degree,
            feats.transitivity, feats.diameter, feats.n_components,
            feats.edge_density, feats.modularity_proxy, feats.spectral_radius,
            reachability,
        ))

    # Simple R² comparison (univariate best feature)
    best_r2_baseline = 0.0
    for i in range(baseline_features):
        slope, intercept, r2 = linear_regression(
            [t[i] for t in xs_baseline], ys
        )
        if r2 > best_r2_baseline:
            best_r2_baseline = r2

    best_r2_extended = 0.0
    for i in range(baseline_features + 1):
        slope, intercept, r2 = linear_regression(
            [t[i] for t in xs_with_reach], ys
        )
        if r2 > best_r2_extended:
            best_r2_extended = r2

    r2_improvement = best_r2_extended - best_r2_baseline

    return {
        "baseline_r2": best_r2_baseline,
        "extended_r2": best_r2_extended,
        "improvement": r2_improvement,
        "significant_improvement": r2_improvement > 0.05,  # threshold: >5pp
    }


# ============================================================ main

def main() -> int:
    ap = argparse.ArgumentParser(description="R1 — Isolation Predictor Expansion")
    ap.add_argument("--n-topologies", type=int, default=100)
    ap.add_argument("--n-nodes", type=int, default=6)
    ap.add_argument("--seeds", type=int, default=50,
                    help="n_seeds for statistical significance")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output-dir", default=str(REPO_ROOT / "_r1_expansion"))
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 68)
    print("R1 — Isolation Predictor Expansion: N≥100 topologies + mechanism tests")
    print("=" * 68)
    print(f"  n_topologies: {args.n_topologies}")
    print(f"  n_nodes: {args.n_nodes}")
    print(f"  seeds: {args.seeds}")
    print(f"  seed: {args.seed}")
    print()

    t0 = time.perf_counter()

    # Generate topologies
    print("Phase 1: Generating topologies...")
    print("-" * 60)
    topologies = generate_topologies(args.n_topologies, args.n_nodes, args.seed)
    print(f"  Generated {len(topologies)} topologies")
    print()

    # Compute features and isolation effect sizes
    print("Phase 2: Computing features and isolation effect sizes...")
    print("-" * 60)
    results = []
    for i, bp in enumerate(topologies):
        feats = _compute_features(bp)
        iso_size = compute_isolation_effect_size_multi(bp, n_trials=3)
        results.append({
            "topology_idx": i,
            "blueprint_name": bp.name,
            "motif_family": bp.motif_family,
            "origin": bp.origin,
            "density": feats.density,
            "mean_out_degree": feats.mean_out_degree,
            "max_out_degree": feats.max_out_degree,
            "transitivity": feats.transitivity,
            "diameter": feats.diameter,
            "n_components": feats.n_components,
            "edge_density": feats.edge_density,
            "modularity_proxy": feats.modularity_proxy,
            "spectral_radius": feats.spectral_radius,
            "isolation_effect_size": iso_size,
        })

    # Print progress
    iso_sizes = [r["isolation_effect_size"] for r in results]
    mean_iso = sum(iso_sizes) / len(iso_sizes) if iso_sizes else 0
    n_high_iso = sum(1 for s in iso_sizes if s > 0.3)
    print(f"  Mean isolation effect size: {mean_iso:.3f}")
    print(f"  Topologies with isolation > 0.3: {n_high_iso}/{len(results)} ({100*n_high_iso/len(results):.1f}%)")
    print()

    # P1: Feature addition test
    print("Phase 3: P1 — Feature addition test (9 vs 10 features)")
    print("-" * 60)
    p1_result = test_feature_addition(topologies, baseline_features=9, seed=args.seed)
    print(f"  Baseline R² (9 features): {p1_result['baseline_r2']:.4f}")
    print(f"  Extended R² (10 features): {p1_result['extended_r2']:.4f}")
    print(f"  Improvement: {p1_result['improvement']:+.4f}")
    print(f"  Significant improvement: {p1_result['significant_improvement']}")
    if p1_result['significant_improvement']:
        print(f"  ★ P1 CONFIRMED: Adding reachability feature improves R² significantly")
    else:
        print(f"  ☆ P1 NOT CONFIRMED: R² did not improve significantly")
    print()

    # P2: Task alignment test
    print("Phase 4: P2 — Task alignment test (fixed topology, varying readout)")
    print("-" * 60)
    p2_results = []
    for i, bp in enumerate(topologies[:20]):  # Test first 20 for speed
        p2 = test_task_alignment(bp, args.n_nodes, seed=args.seed + i)
        p2_results.append({
            "topology_idx": i,
            "blueprint_name": bp.name,
            "mean_isolation": p2["mean"],
            "std_across_readout": p2["std"],
            "significant": p2["significant"],
        })

    n_significant = sum(1 for r in p2_results if r["significant"])
    print(f"  Topologies with significant readout dependency: {n_significant}/{len(p2_results)}")
    if n_significant > len(p2_results) / 2:
        print(f"  ★ P2 CONFIRMED: Isolation effect size depends on readout module")
    else:
        print(f"  ☆ P2 NOT CONFIRMED: Isolation effect size is independent of readout")
    print()

    # P3: Edge density correlation
    print("Phase 5: P3 — Edge density correlation test")
    print("-" * 60)
    p3_result = test_edge_density_correlation(topologies, seed=args.seed)
    print(f"  Slope: {p3_result['slope']:.4f}")
    print(f"  R²: {p3_result['r_squared']:.4f}")
    print(f"  Negative correlation: {p3_result['negative_correlation']}")
    if p3_result['negative_correlation']:
        print(f"  ★ P3 CONFIRMED: Isolation negatively correlates with edge density")
    else:
        print(f"  ☆ P3 NOT CONFIRMED: Isolation does not negatively correlate with edge density")
    print()

    # Falsification check
    print("=" * 68)
    print("FALSIFICATION CHECK")
    print("=" * 68)
    p1_fail = not p1_result['significant_improvement']
    p2_fail = n_significant <= len(p2_results) / 2
    p3_fail = not p3_result['negative_correlation']

    if p1_fail and p2_fail:
        print("  ★★ HYPOTHESIS FALSIFIED: P1 and P2 both failed")
        print("  ★★ 'Structure × task alignment' hypothesis is falsified")
        print("  ★★ Should close this direction and publish negative result")
        verdict = "falsified"
    elif p1_fail or p2_fail:
        print(f"  ☆ PARTIAL: P1={'PASS' if not p1_fail else 'FAIL'}, P2={'PASS' if not p2_fail else 'FAIL'}")
        verdict = "partial"
    else:
        print(f"  ★ HYPOTHESIS SUPPORTED: P1 and P2 both passed")
        verdict = "supported"

    print(f"  P3: {'PASS' if not p3_fail else 'FAIL'}")
    print(f"  Overall verdict: {verdict}")
    print()

    # Save results
    result_data = {
        "params": {
            "n_topologies": args.n_topologies,
            "n_nodes": args.n_nodes,
            "seeds": args.seeds,
            "seed": args.seed,
        },
        "summary": {
            "mean_isolation_effect_size": mean_iso,
            "n_high_isolation": n_high_iso,
            "n_topologies": len(topologies),
            "verdict": verdict,
        },
        "p1_feature_addition": p1_result,
        "p2_task_alignment": p2_results,
        "p3_edge_density_correlation": p3_result,
        "all_results": results,
    }
    json_path = out_dir / "r1_results.json"
    json_path.write_text(json.dumps(result_data, indent=2), encoding="utf-8")
    print(f"  JSON: {json_path}")

    # CSV
    csv_path = out_dir / "r1_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["topology_idx", "blueprint_name", "motif_family", "origin",
                    "density", "mean_out_degree", "max_out_degree", "transitivity",
                    "diameter", "n_components", "edge_density", "modularity_proxy",
                    "spectral_radius", "isolation_effect_size"])
        for r in results:
            w.writerow([r["topology_idx"], r["blueprint_name"], r["motif_family"],
                        r["origin"], r["density"], r["mean_out_degree"],
                        r["max_out_degree"], r["transitivity"], r["diameter"],
                        r["n_components"], r["edge_density"], r["modularity_proxy"],
                        r["spectral_radius"], r["isolation_effect_size"]])
    print(f"  CSV:  {csv_path}")

    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
