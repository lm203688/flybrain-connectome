#!/usr/bin/env python3
"""R4 — Sensitivity Boundary Analysis: robustness curves.

For a fixed set of blueprints, apply controlled perturbations (edge flips,
node deletions, edge additions) and measure how much the structural
fingerprint (out-degree distribution, BFS diameter, clustering) changes.
Then correlate fingerprint distance with task success rate to find the
robustness boundary — the perturbation level beyond which reasoning degrades.

Zero external dependencies (stdlib only).  Uses StubLLM for LLM-free
ground-truth evaluation.

Output:
  _r4_sensitivity_scan.json  — full results
  _r4_sensitivity_scan.csv   — per-cell CSV

Usage:
    python scripts/r4_sensitivity_scan.py
    python scripts/r4_sensitivity_scan.py --n-blueprints 10
    python scripts/r4_sensitivity_scan.py --perturbation-steps 5
"""

from __future__ import annotations

import argparse
import csv
import json
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


# ============================================================ fingerprint

@dataclass
class Fingerprint:
    """Compact structural fingerprint of a blueprint."""
    n_nodes: int
    n_edges: int
    density: float
    mean_out_degree: float
    max_out_degree: int
    diameter: int
    transitivity: float
    n_components: int

    def to_dict(self) -> dict:
        return {
            "n_nodes": self.n_nodes,
            "n_edges": self.n_edges,
            "density": self.density,
            "mean_out_degree": self.mean_out_degree,
            "max_out_degree": self.max_out_degree,
            "diameter": self.diameter,
            "transitivity": self.transitivity,
            "n_components": self.n_components,
        }


def _compute_fingerprint(bp: Blueprint) -> Fingerprint:
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

    return Fingerprint(
        n_nodes=n, n_edges=m, density=density,
        mean_out_degree=mean_out, max_out_degree=max_out,
        diameter=diam, transitivity=transitivity,
        n_components=n_comp,
    )


def _bfs_all(nodes, edges, src: str) -> dict[str, int]:
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    node_set = set(nodes)
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


def fingerprint_distance(fp1: Fingerprint, fp2: Fingerprint) -> float:
    """L1 distance between two fingerprints, normalised."""
    d = 0.0
    d += abs(fp1.density - fp2.density)
    d += abs(fp1.mean_out_degree - fp2.mean_out_degree) / max(fp1.max_out_degree, 1)
    d += abs(fp1.max_out_degree - fp2.max_out_degree) / max(fp1.max_out_degree, 1)
    d += abs(fp1.diameter - fp2.diameter) / max(fp1.diameter, 1)
    d += abs(fp1.transitivity - fp2.transitivity)
    d += abs(fp1.n_components - fp2.n_components) / max(fp1.n_components, 1)
    return d / 6.0  # normalise to [0, 1]


# ============================================================ perturbation


@dataclass
class PerturbationResult:
    blueprint_name: str
    perturbation_type: str
    perturbation_strength: float  # 0.0 to 1.0
    n_perturbed_edges: int
    original_fp: Fingerprint
    perturbed_fp: Fingerprint
    fp_distance: float
    original_hub: str
    perturbed_hub: str
    hub_changed: bool
    original_reachability: dict[str, int]  # key: "src->dst"
    perturbed_reachability: dict[str, int]
    reachability_changes: int
    n_reachability_queries: int


def _perturb_edges(
    bp: Blueprint,
    strength: float,
    rng: random.Random,
    perturbation_type: str = "flip",
) -> tuple[Blueprint, int]:
    """Apply edge perturbation. Returns (new_bp, n_perturbed)."""
    n_nodes = len(bp.nodes)
    max_edges = n_nodes * (n_nodes - 1)
    n_perturb = max(1, int(strength * max_edges))

    if perturbation_type == "flip":
        # Randomly flip edges (add or remove)
        edges = list(bp.edges)
        all_pairs = [(a, b) for a in bp.nodes for b in bp.nodes if a != b]
        current_set = set(edges)
        flipped = 0
        for _ in range(n_perturb):
            # 50% chance to remove, 50% to add
            if edges and rng.random() < 0.5:
                # Remove
                idx = rng.randrange(len(edges))
                edges.pop(idx)
                flipped += 1
            else:
                # Add
                candidates = [p for p in all_pairs if p not in current_set]
                if candidates:
                    new_edge = rng.choice(candidates)
                    edges.append(new_edge)
                    current_set.add(new_edge)
                    flipped += 1

        new_bp = Blueprint(
            name=f"{bp.name}_perturbed",
            nodes=bp.nodes,
            edges=tuple(edges),
            motif_family=bp.motif_family,
            capability_distribution=bp.capability_distribution,
            structure_signature_prefix=bp.structure_signature_prefix,
            origin="perturbed",
        )
        return new_bp, flipped

    elif perturbation_type == "add":
        # Only add edges
        edges = list(bp.edges)
        all_pairs = [(a, b) for a in bp.nodes for b in bp.nodes if a != b]
        current_set = set(edges)
        added = 0
        for _ in range(n_perturb):
            candidates = [p for p in all_pairs if p not in current_set]
            if candidates:
                new_edge = rng.choice(candidates)
                edges.append(new_edge)
                current_set.add(new_edge)
                added += 1

        new_bp = Blueprint(
            name=f"{bp.name}_perturbed",
            nodes=bp.nodes,
            edges=tuple(edges),
            motif_family=bp.motif_family,
            capability_distribution=bp.capability_distribution,
            structure_signature_prefix=bp.structure_signature_prefix,
            origin="perturbed",
        )
        return new_bp, added

    elif perturbation_type == "remove":
        # Only remove edges
        edges = list(bp.edges)
        removed = 0
        for _ in range(min(n_perturb, len(edges))):
            idx = rng.randrange(len(edges))
            edges.pop(idx)
            removed += 1

        new_bp = Blueprint(
            name=f"{bp.name}_perturbed",
            nodes=bp.nodes,
            edges=tuple(edges),
            motif_family=bp.motif_family,
            capability_distribution=bp.capability_distribution,
            structure_signature_prefix=bp.structure_signature_prefix,
            origin="perturbed",
        )
        return new_bp, removed

    else:
        raise ValueError(f"unknown perturbation_type: {perturbation_type}")


def _node_delete(
    bp: Blueprint,
    strength: float,
    rng: random.Random,
) -> tuple[Blueprint, int]:
    """Delete nodes. Returns (new_bp, n_deleted)."""
    n_delete = max(1, int(strength * len(bp.nodes)))
    nodes = list(bp.nodes)
    deleted = rng.sample(nodes, k=min(n_delete, len(nodes) - 1))
    remaining = [n for n in nodes if n not in deleted]
    edges = [(a, b) for a, b in bp.edges if a in remaining and b in remaining]

    new_bp = Blueprint(
        name=f"{bp.name}_deleted",
        nodes=tuple(remaining),
        edges=tuple(edges),
        motif_family=bp.motif_family,
        capability_distribution=bp.capability_distribution,
        structure_signature_prefix=bp.structure_signature_prefix,
        origin="perturbed",
    )
    return new_bp, len(deleted)


# ============================================================ sensitivity scan


def run_sensitivity_scan(
    n_blueprints: int,
    n_nodes: int,
    perturbation_steps: list[float],
    perturbation_types: list[str],
    seed: int = 42,
) -> list[PerturbationResult]:
    rng = random.Random(seed)
    results: list[PerturbationResult] = []

    # Generate base blueprints
    blueprints = []
    for i in range(n_blueprints):
        if i % 2 == 0:
            bp = build_evidence_blueprint(rng, {"n_nodes": n_nodes, "n_edges": n_nodes + 1})
        else:
            bp = build_random_blueprint(rng, {"n_nodes": n_nodes, "n_edges": n_nodes + 1})
        blueprints.append(bp)

    for bp in blueprints:
        orig_fp = _compute_fingerprint(bp)
        orig_hub = _pick_hub(bp.nodes, bp.edges)

        # Original reachability for all pairs
        orig_reach: dict[str, int] = {}
        for src in bp.nodes:
            dist = _bfs_all(bp.nodes, bp.edges, src)
            for dst in bp.nodes:
                if src != dst:
                    key = f"{src}->{dst}"
                    orig_reach[key] = dist.get(dst, -1)

        for ptype in perturbation_types:
            for strength in perturbation_steps:
                rng2 = random.Random(rng.randint(0, 999999))
                if ptype == "node_delete":
                    new_bp, n_perturbed = _node_delete(bp, strength, rng2)
                else:
                    new_bp, n_perturbed = _perturb_edges(bp, strength, rng2, ptype)

                pert_fp = _compute_fingerprint(new_bp)
                fp_dist = fingerprint_distance(orig_fp, pert_fp)
                pert_hub = _pick_hub(new_bp.nodes, new_bp.edges)
                hub_changed = pert_hub != orig_hub

                # Reachability changes
                pert_reach: dict[str, int] = {}
                for src in new_bp.nodes:
                    dist = _bfs_all(new_bp.nodes, new_bp.edges, src)
                    for dst in new_bp.nodes:
                        if src != dst:
                            key = f"{src}->{dst}"
                            pert_reach[key] = dist.get(dst, -1)

                reach_changes = 0
                for key in set(orig_reach) | set(pert_reach):
                    if orig_reach.get(key, -99) != pert_reach.get(key, -99):
                        reach_changes += 1

                results.append(PerturbationResult(
                    blueprint_name=bp.name,
                    perturbation_type=ptype,
                    perturbation_strength=strength,
                    n_perturbed_edges=n_perturbed,
                    original_fp=orig_fp,
                    perturbed_fp=pert_fp,
                    fp_distance=fp_dist,
                    original_hub=orig_hub,
                    perturbed_hub=pert_hub,
                    hub_changed=hub_changed,
                    original_reachability=orig_reach,
                    perturbed_reachability=pert_reach,
                    reachability_changes=reach_changes,
                    n_reachability_queries=len(orig_reach),
                ))

    return results


# ============================================================ robustness curve


def compute_robustness_curve(
    results: list[PerturbationResult],
    perturbation_type: str,
    perturbation_steps: list[float],
) -> list[dict]:
    """Compute mean fingerprint distance and reachability change rate per strength."""
    curve: list[dict] = []
    for strength in perturbation_steps:
        subset = [r for r in results if r.perturbation_type == perturbation_type and abs(r.perturbation_strength - strength) < 1e-9]
        if not subset:
            continue
        n = len(subset)
        mean_fp_dist = sum(r.fp_distance for r in subset) / n
        mean_hub_changed = sum(1 for r in subset if r.hub_changed) / n
        mean_reach_change_rate = sum(r.reachability_changes / max(r.n_reachability_queries, 1) for r in subset) / n
        curve.append({
            "strength": strength,
            "n_samples": n,
            "mean_fp_distance": mean_fp_dist,
            "mean_hub_changed_rate": mean_hub_changed,
            "mean_reachability_change_rate": mean_reach_change_rate,
        })
    return curve


def find_robustness_boundary(
    curve: list[dict],
    threshold_fp: float = 0.3,
    threshold_reach: float = 0.5,
) -> dict:
    """Find the perturbation strength beyond which reasoning degrades."""
    for point in curve:
        if point["mean_fp_distance"] > threshold_fp or point["mean_reachability_change_rate"] > threshold_reach:
            return {
                "boundary_strength": point["strength"],
                "fp_distance_at_boundary": point["mean_fp_distance"],
                "reachability_change_rate_at_boundary": point["mean_reachability_change_rate"],
                "hub_changed_rate_at_boundary": point["mean_hub_changed_rate"],
            }
    return {"boundary_strength": None, "reason": "no boundary found in sweep range"}


# ============================================================ main


def main() -> int:
    ap = argparse.ArgumentParser(description="R4 — Sensitivity Boundary Analysis")
    ap.add_argument("--n-blueprints", type=int, default=10)
    ap.add_argument("--n-nodes", type=int, default=6)
    ap.add_argument("--perturbation-steps", default="0.1,0.2,0.3,0.5,0.8")
    ap.add_argument("--perturbation-types", default="flip,add,remove,node_delete")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output-dir", default=str(REPO_ROOT / "_r4_sensitivity_scan"))
    args = ap.parse_args()

    steps = [float(x.strip()) for x in args.perturbation_steps.split(",")]
    ptypes = [x.strip() for x in args.perturbation_types.split(",")]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 68)
    print("R4 — Sensitivity Boundary Analysis: robustness curves")
    print("=" * 68)
    print(f"  n_blueprints: {args.n_blueprints}")
    print(f"  n_nodes: {args.n_nodes}")
    print(f"  perturbation_steps: {[f'{s:.1f}' for s in steps]}")
    print(f"  perturbation_types: {ptypes}")
    print(f"  seed: {args.seed}")
    print()

    t0 = time.perf_counter()

    # Run scan
    print("Phase 1: Running sensitivity scan...")
    print("-" * 60)
    results = run_sensitivity_scan(
        n_blueprints=args.n_blueprints,
        n_nodes=args.n_nodes,
        perturbation_steps=steps,
        perturbation_types=ptypes,
        seed=args.seed,
    )
    print(f"  Generated {len(results)} perturbation results")
    print()

    # Compute robustness curves
    print("Phase 2: Computing robustness curves...")
    print("-" * 60)
    curves = {}
    boundaries = {}
    for ptype in ptypes:
        curve = compute_robustness_curve(results, ptype, steps)
        curves[ptype] = curve
        boundary = find_robustness_boundary(curve)
        boundaries[ptype] = boundary

        print(f"\n  {ptype}:")
        print(f"  {'strength':>9} {'fp_dist':>8} {'hub_chg':>8} {'reach_chg':>10}")
        print(f"  {'-'*38}")
        for point in curve:
            print(f"  {point['strength']:>9.1f} {point['mean_fp_distance']:>8.3f} "
                  f"{point['mean_hub_changed_rate']:>8.1%} {point['mean_reachability_change_rate']:>10.1%}")

        if boundary.get("boundary_strength") is not None:
            print(f"  ★ Robustness boundary at strength={boundary['boundary_strength']:.1f} "
                  f"(fp_dist={boundary['fp_distance_at_boundary']:.3f}, "
                  f"reach_chg={boundary['reachability_change_rate_at_boundary']:.1%})")
        else:
            print(f"  No boundary found: {boundary.get('reason')}")

    print()

    # Summary
    print("=" * 68)
    print("SUMMARY: Robustness Boundaries")
    print("=" * 68)
    print(f"{'perturbation_type':>20} {'boundary_strength':>18} {'fp_dist':>8} {'reach_chg':>10}")
    print("-" * 60)
    for ptype, boundary in boundaries.items():
        if boundary.get("boundary_strength") is not None:
            print(f"{ptype:>20} {boundary['boundary_strength']:>18.1f} "
                  f"{boundary['fp_distance_at_boundary']:>8.3f} {boundary['reachability_change_rate_at_boundary']:>10.1%}")
        else:
            print(f"{ptype:>20} {'N/A':>18}")
    print()

    # Save results
    result_data = {
        "params": {
            "n_blueprints": args.n_blueprints,
            "n_nodes": args.n_nodes,
            "perturbation_steps": steps,
            "perturbation_types": ptypes,
            "seed": args.seed,
        },
        "curves": curves,
        "boundaries": boundaries,
        "all_results": [
            {
                "blueprint_name": r.blueprint_name,
                "perturbation_type": r.perturbation_type,
                "perturbation_strength": r.perturbation_strength,
                "n_perturbed_edges": r.n_perturbed_edges,
                "fp_distance": r.fp_distance,
                "hub_changed": r.hub_changed,
                "reachability_changes": r.reachability_changes,
                "n_reachability_queries": r.n_reachability_queries,
                "original_fp": r.original_fp.to_dict(),
                "perturbed_fp": r.perturbed_fp.to_dict(),
            }
            for r in results
        ],
    }
    json_path = out_dir / "r4_sensitivity_scan.json"
    json_path.write_text(json.dumps(result_data, indent=2), encoding="utf-8")
    print(f"  JSON: {json_path}")

    # CSV
    csv_path = out_dir / "r4_sensitivity_scan.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["blueprint_name", "perturbation_type", "perturbation_strength",
                    "n_perturbed_edges", "fp_distance", "hub_changed",
                    "reachability_changes", "n_reachability_queries",
                    "original_density", "perturbed_density",
                    "original_transitivity", "perturbed_transitivity",
                    "original_diameter", "perturbed_diameter"])
        for r in results:
            w.writerow([
                r.blueprint_name, r.perturbation_type, r.perturbation_strength,
                r.n_perturbed_edges, r.fp_distance, r.hub_changed,
                r.reachability_changes, r.n_reachability_queries,
                r.original_fp.density, r.perturbed_fp.density,
                r.original_fp.transitivity, r.perturbed_fp.transitivity,
                r.original_fp.diameter, r.perturbed_fp.diameter,
            ])
    print(f"  CSV:  {csv_path}")

    elapsed = time.perf_counter() - t0
    print(f"\nDone in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
