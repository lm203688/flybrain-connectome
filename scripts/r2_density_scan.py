#!/usr/bin/env python3
"""R2 — Density Scan: structure–function curves and d* threshold.

For each edge density d in a sweep, generate N random directed graphs of
fixed size, compute structural metrics (mean out-degree, transitivity /
clustering, BFS diameter), and evaluate task success on hub + reachability
ground truth. The goal is to find the density d* where structural reason-
ability collapses — the "capability cliff" the research deepening plan
(I-2) asked about.

Zero external dependencies (stdlib only, no LLM calls).  Task success is
measured via ground-truth recomputation, not LLM inference, so this is a
pure structure→function characterisation.

Output:
  _r2_density_scan.json   — full results (per-cell metrics)
  _r2_density_scan.csv    — per-cell CSV for spreadsheet analysis

Usage:
    python scripts/r2_density_scan.py                     # default sweep
    python scripts/r2_density_scan.py --sweep 0.05,0.1,... # custom
    python scripts/r2_density_scan.py --n-samples 200      # more graphs
    python scripts/r2_density_scan.py --n-nodes 8          # bigger graphs
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
    score_answer,
    _bfs_hops,
    _pick_hub,
)


# ============================================================ structural metrics

@dataclass
class StructMetrics:
    n_nodes: int
    n_edges: int
    density: float
    mean_out_degree: float
    transitivity: float        # global clustering coefficient (triangles / paths)
    diameter: int               # longest shortest path (BFS), -1 if disconnected
    n_components: int           # number of weakly connected components
    hub_node: str               # node with max out-degree
    avg_bfs_hops: float         # mean BFS hops over all reachable pairs


def _compute_struct_metrics(bp: Blueprint) -> StructMetrics:
    n = len(bp.nodes)
    m = len(bp.edges)
    density = m / (n * (n - 1)) if n > 1 else 0.0

    out_deg = bp.out_degree
    mean_out = sum(out_deg.values()) / n if n else 0.0

    # Transitivity: count triangles / paths (global clustering)
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

    # BFS: all-pairs shortest path
    diam = 0
    total_hops = 0
    reachable = 0
    for src in bp.nodes:
        dist = _bfs_all(bp.nodes, bp.edges, src)
        for dst, d in dist.items():
            if d >= 0 and src != dst:
                total_hops += d
                reachable += 1
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

    hub = _pick_hub(bp.nodes, bp.edges)
    avg_hops = total_hops / reachable if reachable > 0 else 0.0

    return StructMetrics(
        n_nodes=n, n_edges=m, density=density,
        mean_out_degree=mean_out, transitivity=transitivity,
        diameter=diam, n_components=n_comp,
        hub_node=hub, avg_bfs_hops=avg_hops,
    )


def _bfs_all(
    nodes, edges, src: str,
) -> dict[str, int]:
    """BFS from src to all nodes. Returns {node: dist} with -1 for unreachable."""
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


# ============================================================ task evaluation

@dataclass
class TaskResult:
    task_type: str
    correct: bool
    predicted: str
    ground_truth: str | int
    blueprint_name: str
    density: float


# -------------------------------------------------------------- proxy evaluators
#
# These are DELIBERATELY separate code paths from llm_tasks.compute_ground_truth.
# A task evaluator that copies the ground truth is not measuring anything: the
# correctness rate is pinned to 1.0 by construction, on every topology, at every
# sample size.  R2's original run did exactly that (see the previous
# implementation, where `predicted = gt` and the comment read
# "correct by definition in this scan"), which is why hub_ok and reach_ok came
# out as 100% on 21/21 cells across n_nodes in {6, 20, 40}.
#
# A proxy that never sees the ground truth measures whether a consumer that
# reads only the prompt's exposed information can solve the task.  That is the
# question R2 actually asked for.


def _proxy_hub_from_degrees(nodes, edges) -> str:
    """Hub from the out-degree table alone.

    `_hub_prompt` exposes every node's out_degree to the model, so a solver
    that only reads the prompt has the full evidence.  This function uses
    exactly that evidence and nothing else -- it does not call `_pick_hub`.
    Ties break alphabetically, matching the prompt's stated convention.
    """
    counts: dict[str, int] = {n: 0 for n in nodes}
    for a, _b in edges:
        counts[a] = counts.get(a, 0) + 1
    best: str | None = None
    for n in sorted(counts):
        if best is None or counts[n] > counts[best]:
            best = n
    return best  # type: ignore[return-value]


def _proxy_reach_hops(nodes, edges, src: str, dst: str) -> int:
    """BFS hop count via a separate implementation.

    Breadth-first layer expansion written independently of
    llm_tasks._bfs_hops (which builds its adjacency as a default dict and
    walks a frontier list).  Same algorithm family, no shared code -- so a
    mismatch between proxy and ground truth is information, not noise.
    """
    if src == dst:
        return 0
    succ: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        if a in succ:
            succ[a].append(b)
    seen = {src}
    queue = deque([(src, 0)])
    while queue:
        node, dist = queue.popleft()
        for nxt in succ.get(node, []):
            if nxt == dst:
                return dist + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return -1


# -------------------------------------------------------------- evaluation


def _eval_hub_task(bp: Blueprint, rng: random.Random) -> TaskResult:
    """Ground-truth vs proxy. No LLM involved, no copying of the truth."""
    gt = compute_ground_truth(bp, "hub")
    predicted = _proxy_hub_from_degrees(bp.nodes, bp.edges)
    return TaskResult("hub", predicted == gt, str(predicted), gt, bp.name, 0.0)


def _eval_reachability_task(bp: Blueprint, rng: random.Random) -> TaskResult:
    src = rng.choice(bp.nodes)
    dst = rng.choice(bp.nodes)
    gt = compute_ground_truth(bp, "reachability", src=src, dst=dst)
    predicted = _proxy_reach_hops(bp.nodes, bp.edges, src, dst)
    return TaskResult("reachability", predicted == gt, str(predicted), gt, bp.name, 0.0)


def _eval_motif_task(bp: Blueprint, rng: random.Random) -> TaskResult:
    gt = compute_ground_truth(bp, "motif_family")
    # The motif_family prompt exposes only nodes/edges; the family label is a
    # generator-side property that is NOT visible in the prompt.  A proxy
    # therefore must guess, and guessing correctly is informative.
    predicted = rng.choice(MOTIF_FAMILY_LABELS)
    return TaskResult("motif_family", predicted == gt, str(predicted), gt, bp.name, 0.0)


# ============================================================ density sweep

@dataclass
class DensityCell:
    density: float
    n_samples: int
    # structural metrics (averaged)
    mean_density_actual: float = 0.0
    mean_out_degree: float = 0.0
    mean_transitivity: float = 0.0
    mean_diameter: float = 0.0
    mean_avg_bfs_hops: float = 0.0
    mean_n_components: float = 0.0
    # task success rates (ground-truth only, no LLM)
    hub_success: float = 0.0
    reachability_success: float = 0.0
    motif_family_success: float = 0.0
    # per-cell details for CSV
    cells: list[dict] = field(default_factory=list)


def run_density_scan(
    densities: list[float],
    n_nodes: int,
    n_samples: int,
    seed: int = 42,
) -> list[DensityCell]:
    rng = random.Random(seed)
    results: list[DensityCell] = []

    for d in densities:
        print(f"  density={d:.2f}  ({n_samples} samples)...")
        cell = DensityCell(density=d, n_samples=n_samples, cells=[])

        for i in range(n_samples):
            bp = build_random_blueprint(rng, {"n_nodes": n_nodes, "n_edges": max(n_nodes, int(d * n_nodes * (n_nodes - 1)))})
            sm = _compute_struct_metrics(bp)

            # Task evaluation (ground-truth only)
            tr_hub = _eval_hub_task(bp, rng)
            tr_reach = _eval_reachability_task(bp, rng)
            tr_motif = _eval_motif_task(bp, rng)

            cell.cells.append({
                "density": d,
                "sample_idx": i,
                "actual_density": sm.density,
                "mean_out_degree": sm.mean_out_degree,
                "transitivity": sm.transitivity,
                "diameter": sm.diameter,
                "avg_bfs_hops": sm.avg_bfs_hops,
                "n_components": sm.n_components,
                "hub_node": sm.hub_node,
                "hub_correct": tr_hub.correct,
                "reachability_correct": tr_reach.correct,
                "motif_correct": tr_motif.correct,
                "blueprint_name": bp.name,
            })

        # Aggregate
        cell.mean_density_actual = sum(c["actual_density"] for c in cell.cells) / n_samples
        cell.mean_out_degree = sum(c["mean_out_degree"] for c in cell.cells) / n_samples
        cell.mean_transitivity = sum(c["transitivity"] for c in cell.cells) / n_samples
        cell.mean_diameter = sum(c["diameter"] for c in cell.cells) / n_samples
        cell.mean_avg_bfs_hops = sum(c["avg_bfs_hops"] for c in cell.cells) / n_samples
        cell.mean_n_components = sum(c["n_components"] for c in cell.cells) / n_samples
        cell.hub_success = sum(1 for c in cell.cells if c["hub_correct"]) / n_samples
        cell.reachability_success = sum(1 for c in cell.cells if c["reachability_correct"]) / n_samples
        cell.motif_family_success = sum(1 for c in cell.cells if c["motif_correct"]) / n_samples

        results.append(cell)

    return results


# ============================================================ capability cliff

def find_capability_cliff(cells: list[DensityCell]) -> dict:
    """Find the density d* where reachability success drops below 50%.

    This is the "capability cliff" — the density below which BFS-based
    reasoning becomes unreliable because graphs fragment.
    """
    reachable_cells = [c for c in cells if c.reachability_success > 0]
    if not reachable_cells:
        return {"d_star": None, "reason": "no reachability data"}

    # Find first cell where reachability < 0.5
    for c in cells:
        if c.reachability_success < 0.5:
            return {
                "d_star": c.density,
                "reachability_success_at_d_star": c.reachability_success,
                "n_components_at_d_star": c.mean_n_components,
                "transitivity_at_d_star": c.mean_transitivity,
            }

    return {
        "d_star": None,
        "reason": "no cliff found in sweep range",
        "highest_density": cells[-1].density if cells else None,
    }


# ============================================================ density drift

def check_density_drift(
    cells: list[DensityCell],
    max_abs_drift: float = 0.02,
    max_rel_drift: float = 0.5,
) -> dict:
    """Detect silent clamping between requested and actual density.

    Why this exists
    ---------------
    `run_density_scan` derives the edge count with
    `max(n_nodes, int(d * n_nodes * (n_nodes - 1)))`. The `max()` pins the
    edge count to at least a spanning set of edges, so on small graphs a
    requested density of 0.05 silently becomes 0.20.

    The original R2 run (n_nodes=6, see `_gate31_r2/`) clamped **4 of 7
    cells** -- the low-density third of the axis collapsed onto a single
    value. The capability cliff came out as "not found", and that verdict
    is still correct at n_nodes=20 (where the axis tracks the request), so
    the conclusion survived the fix. But the density axis the original
    report was *plotted against* was not the axis it claimed, and nothing
    in the pipeline said so. A measurement report that silently rescales
    its own x-axis is the same class of defect as the saturated binary
    metric that broke R1: the number is printed, the semantics are not.

    This check makes the drift machine-visible. Any cell whose mean actual
    density deviates from its target by more than either threshold is
    listed, and `axis_trustworthy` is set False so a downstream consumer
    cannot treat the sweep as covering the requested range.
    """
    clamped: list[dict] = []
    for c in cells:
        drift = abs(c.mean_density_actual - c.density)
        rel = drift / c.density if c.density > 0 else 0.0
        if drift > max_abs_drift or rel > max_rel_drift:
            clamped.append({
                "density_requested": c.density,
                "density_actual": round(c.mean_density_actual, 6),
                "abs_drift": round(drift, 6),
                "rel_drift": round(rel, 4),
            })

    worst = max((e["abs_drift"] for e in clamped), default=0.0)
    return {
        "threshold": {"max_abs_drift": max_abs_drift, "max_rel_drift": max_rel_drift},
        "n_cells": len(cells),
        "n_cells_clamped": len(clamped),
        "max_abs_drift_observed": round(worst, 6),
        "clamped_cells": clamped,
        "axis_trustworthy": len(clamped) == 0,
        "note": ("all requested densities realised within threshold"
                 if not clamped else
                 "density axis NOT trustworthy: some requested densities were "
                 "clamped; the sweep did not cover the range the report claims"),
    }


# ============================================================ evidence vs random

def compare_evidence_vs_random(
    densities: list[float],
    n_nodes: int,
    n_samples: int,
    seed: int = 42,
) -> list[dict]:
    """At each density, compare evidence-flavoured vs random blueprints."""
    rng = random.Random(seed)
    comparison: list[dict] = []

    for d in densities:
        ev_cells: list[dict] = []
        rd_cells: list[dict] = []

        for i in range(n_samples):
            # Evidence blueprint at given density
            bp_ev = build_evidence_blueprint(rng, {"n_nodes": n_nodes, "n_edges": max(n_nodes, int(d * n_nodes * (n_nodes - 1)))})
            sm_ev = _compute_struct_metrics(bp_ev)
            ev_cells.append({
                "actual_density": sm_ev.density,
                "transitivity": sm_ev.transitivity,
                "diameter": sm_ev.diameter,
                "motif": bp_ev.motif_family,
            })

            # Random blueprint at given density
            bp_rd = build_random_blueprint(rng, {"n_nodes": n_nodes, "n_edges": max(n_nodes, int(d * n_nodes * (n_nodes - 1)))})
            sm_rd = _compute_struct_metrics(bp_rd)
            rd_cells.append({
                "actual_density": sm_rd.density,
                "transitivity": sm_rd.transitivity,
                "diameter": sm_rd.diameter,
                "motif": bp_rd.motif_family,
            })

        comparison.append({
            "density": d,
            "evidence": {
                "mean_density_actual": sum(c["actual_density"] for c in ev_cells) / n_samples,
                "mean_transitivity": sum(c["transitivity"] for c in ev_cells) / n_samples,
                "mean_diameter": sum(c["diameter"] for c in ev_cells) / n_samples,
                "motif_distribution": {m: sum(1 for c in ev_cells if c["motif"] == m) for m in set(c["motif"] for c in ev_cells)},
            },
            "random": {
                "mean_density_actual": sum(c["actual_density"] for c in rd_cells) / n_samples,
                "mean_transitivity": sum(c["transitivity"] for c in rd_cells) / n_samples,
                "mean_diameter": sum(c["diameter"] for c in rd_cells) / n_samples,
                "motif_distribution": {"mixed": n_samples},
            },
        })

    return comparison


# ============================================================ main

def main() -> int:
    ap = argparse.ArgumentParser(description="R2 — Density Scan")
    ap.add_argument("--sweep", default="0.05,0.10,0.15,0.20,0.30,0.50,0.80",
                    help="comma-separated densities")
    ap.add_argument("--n-nodes", type=int, default=6)
    ap.add_argument("--n-samples", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output-dir", default=str(REPO_ROOT / "_r2_density_scan"))
    ap.add_argument(
        "--strict-axis", action="store_true",
        help="exit non-zero if the requested density axis was not realised "
             "(check_density_drift reports a clamped cell). Makes silent "
             "clamping a gate failure instead of a printed note.",
    )
    args = ap.parse_args()

    densities = [float(x.strip()) for x in args.sweep.split(",")]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 68)
    print("R2 — Density Scan: structure-function curves and d* threshold")
    print("=" * 68)
    print(f"  densities: {[f'{d:.2f}' for d in densities]}")
    print(f"  n_nodes: {args.n_nodes}")
    print(f"  n_samples per density: {args.n_samples}")
    print(f"  seed: {args.seed}")
    print()

    t0 = time.perf_counter()

    # Part 1: Density sweep
    print("Phase 1: Density sweep (random blueprints)")
    print("-" * 60)
    cells = run_density_scan(densities, args.n_nodes, args.n_samples, args.seed)
    print()

    # Part 2: Find capability cliff
    print("Phase 2: Finding capability cliff d*")
    print("-" * 60)
    cliff = find_capability_cliff(cells)
    if cliff.get("d_star") is not None:
        print(f"  ★ d* = {cliff['d_star']:.2f} (reachability success = {cliff['reachability_success_at_d_star']:.1%})")
        print(f"  ★ at d*: n_components={cliff['n_components_at_d_star']:.1f}, "
              f"transitivity={cliff['transitivity_at_d_star']:.3f}")
    else:
        print(f"  No cliff found: {cliff.get('reason')}")
    print()

    # Part 2b: was the requested density axis actually realised?
    print("Phase 2b: Density drift check (requested vs actual)")
    print("-" * 60)
    drift = check_density_drift(cells)
    if drift["axis_trustworthy"]:
        print(f"  Density axis trustworthy: {drift['n_cells']} cells within "
              f"threshold (max abs drift {drift['max_abs_drift_observed']:.4f})")
    else:
        print(f"  ⚠ DENSITY AXIS NOT TRUSTWORTHY: "
              f"{drift['n_cells_clamped']}/{drift['n_cells']} cells clamped")
        for e in drift["clamped_cells"]:
            print(f"    requested {e['density_requested']:.2f} -> actual "
                  f"{e['density_actual']:.4f}  (abs drift {e['abs_drift']:.4f})")
        print("  The capability-cliff verdict above is computed on the REALISED")
        print("  axis, not the requested one.")
    print()

    # Part 3: Evidence vs random comparison
    print("Phase 3: Evidence vs random comparison")
    print("-" * 60)
    comparison = compare_evidence_vs_random(densities, args.n_nodes, args.n_samples, args.seed)
    for c in comparison:
        ev_t = c["evidence"]["mean_transitivity"]
        rd_t = c["random"]["mean_transitivity"]
        ev_d = c["evidence"]["mean_diameter"]
        rd_d = c["random"]["mean_diameter"]
        print(f"  d={c['density']:.2f}: ev transitivity={ev_t:.3f} diameter={ev_d:.1f} | "
              f"rd transitivity={rd_t:.3f} diameter={rd_d:.1f}")
    print()

    # Summary table
    print("=" * 68)
    print("SUMMARY: Structure-Function Curves")
    print("=" * 68)
    print(f"{'density':>8} {'actual':>8} {'out_deg':>8} {'transit':>8} "
          f"{'diam':>6} {'avg_bfs':>8} {'n_comp':>7} {'hub_ok':>7} {'reach_ok':>9}")
    print("-" * 78)
    for c in cells:
        print(f"{c.density:>8.2f} {c.mean_density_actual:>8.3f} "
              f"{c.mean_out_degree:>8.2f} {c.mean_transitivity:>8.3f} "
              f"{c.mean_diameter:>6.1f} {c.mean_avg_bfs_hops:>8.2f} "
              f"{c.mean_n_components:>7.1f} {c.hub_success:>7.1%} "
              f"{c.reachability_success:>9.1%}")
    print()

    # Save results
    result = {
        "params": {
            "densities": densities,
            "n_nodes": args.n_nodes,
            "n_samples": args.n_samples,
            "seed": args.seed,
        },
        "capability_cliff": cliff,
        "density_drift": drift,
        "density_cells": [
            {k: v for k, v in c.__dict__.items() if k != "cells"}
            for c in cells
        ],
        "comparison": comparison,
        "all_cells": [cell for c in cells for cell in c.cells],
    }
    json_path = out_dir / "r2_density_scan.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"  JSON: {json_path}")

    # CSV (per-cell)
    csv_path = out_dir / "r2_density_scan.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["density", "sample_idx", "actual_density", "mean_out_degree",
                    "transitivity", "diameter", "avg_bfs_hops", "n_components",
                    "hub_node", "hub_correct", "reachability_correct", "motif_correct",
                    "blueprint_name"])
        for c in cells:
            for cell in c.cells:
                w.writerow([cell["density"], cell["sample_idx"], cell["actual_density"],
                            cell["mean_out_degree"], cell["transitivity"], cell["diameter"],
                            cell["avg_bfs_hops"], cell["n_components"], cell["hub_node"],
                            cell["hub_correct"], cell["reachability_correct"], cell["motif_correct"],
                            cell["blueprint_name"]])
    print(f"  CSV:  {csv_path}")

    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.1f}s")

    if args.strict_axis and not drift["axis_trustworthy"]:
        print(
            f"\nFAIL: requested density axis not realised "
            f"({drift['n_cells_clamped']}/{drift['n_cells']} cells clamped, "
            f"max abs drift {drift['max_abs_drift_observed']:.4f}). "
            f"The capability-cliff verdict cannot be trusted at this n_nodes."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
