#!/usr/bin/env python3
"""A1 · Graded fault-isolation metric (报告 §九 A1).

The current "isolation_effect_size" is a saturated binary metric: for every
topology it returns exactly 1.0 (full isolation) because removing the damaged
hub's *outgoing* edges always leaves the rest of the graph reachable. This
metric cannot distinguish topologies, so it cannot support any mechanism
analysis — and it is the only thing standing between L2 and "usable".

This module replaces the binary verdict with a *graded* triple:

  1. drop_magnitude       — how much reachability actually drops when a hub
                            is damaged (0 = no damage, 1 = total loss)
  2. affected_module_count— how many modules lose at least one reachable node
  3. mean_recovery_steps  — how many extra hops the surviving paths take to
                            reach the same targets (0 = unaffected)

Each is a continuous / ordinal quantity with real variance across topologies.
The binary verdict is *derived* from the triple (drop == 1.0 → "isolated"),
not the other way around.

Usage:
    python scripts/isolation_graded.py --n-topologies 50 --n-nodes 10
    python scripts/isolation_graded.py --summarise ./_r1_mechanism_a/graded_isolation.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections import deque
from dataclasses import dataclass, asdict
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
)


# ============================================================ topology generation
# Same generator as r1_mechanism_a.py / r1_expansion.py so results are comparable.

def generate_topologies(
    n_topologies: int,
    n_nodes: int = 10,
    seed: int = 42,
) -> list[Blueprint]:
    rng = random.Random(seed)
    blueprints: list[Blueprint] = []
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


# ============================================================ graph helpers

def _bfs_all(nodes, edges, src: str) -> dict[str, int]:
    """Unweighted shortest-path distances from src (directed). -1 = unreachable."""
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


def _module_index(bp: Blueprint) -> dict[str, int]:
    """Map node -> module index. If the blueprint carries an explicit
    capability_distribution we use it as a proxy for module membership;
    otherwise we derive modules from motif_family so the metric still
    decomposes by structural role."""
    # Blueprint.capability_distribution is a dict like {"sensory": 2, "motor": 3};
    # we assign nodes round-robin to the declared capabilities.
    caps = list(bp.capability_distribution.keys()) or ["core"]
    mods: dict[str, int] = {}
    for i, node in enumerate(bp.nodes):
        mods[node] = i % len(caps)
    return mods


# ============================================================ A1 · graded isolation

@dataclass
class GradedIsolation:
    """Graded (non-binary) fault-isolation metric for one topology."""
    drop_magnitude: float          # mean reachability drop across hubs, [0,1]
    affected_module_count: int     # MAX over hubs of modules that lost ≥1 reachable node
    affected_module_count_mean: float  # MEAN over hubs of modules that lost ≥1 reachable node
    mean_recovery_steps: float     # mean extra hops to reach same targets
    n_hubs_tested: int
    n_nodes: int
    n_edges: int


def compute_graded_isolation(bp: Blueprint, seed: int = 42) -> GradedIsolation:
    """Compute the graded isolation triple for a blueprint.

    Damage model: remove the hub *entirely* (it can neither send nor receive).
    The metric then measures, for every ordered (source, target) pair that was
    reachable in the intact graph, whether it survives once the hub is gone.

      - drop_magnitude: fraction of reachable (src, dst) pairs lost
      - affected_module_count: distinct modules that lost at least one pair
      - mean_recovery_steps: extra hops on the pairs that survive but got longer

    This is a graded metric because it depends on how much of the graph's
    connectivity flowed *through* the failed hub. A chain loses a lot; a fully
    connected graph loses only the hub itself; a redundant graph loses nothing.
    """
    mods = _module_index(bp)
    nodes = list(bp.nodes)

    drops: list[float] = []
    affected_counts: list[int] = []
    recovery_steps: list[int] = []

    for hub in nodes:
        damaged_nodes = [n for n in nodes if n != hub]
        damaged_edges = [(a, b) for a, b in bp.edges if a != hub and b != hub]

        lost_pairs = 0
        total_pairs = 0
        affected: set[int] = set()
        extra = 0
        n_still = 0

        for src in nodes:
            orig_dist = _bfs_all(nodes, bp.edges, src)
            damaged_dist = _bfs_all(damaged_nodes, damaged_edges, src) if src != hub else {}
            for dst in nodes:
                if dst == src or dst == hub:
                    continue
                d_orig = orig_dist.get(dst, -1)
                if d_orig <= 0:
                    continue  # not reachable in the intact graph
                total_pairs += 1
                d_new = damaged_dist.get(dst, -1)
                if d_new <= 0:
                    lost_pairs += 1
                    affected.add(mods[dst])
                elif d_new > d_orig:
                    extra += d_new - d_orig
                    n_still += 1

        if total_pairs == 0:
            continue
        drops.append(lost_pairs / total_pairs)
        affected_counts.append(len(affected))
        recovery_steps.append(extra / n_still if n_still else 0)

    return GradedIsolation(
        drop_magnitude=sum(drops) / len(drops) if drops else 0.0,
        affected_module_count=max(affected_counts) if affected_counts else 0,
        affected_module_count_mean=(
            sum(affected_counts) / len(affected_counts) if affected_counts else 0.0
        ),
        mean_recovery_steps=sum(recovery_steps) / len(recovery_steps) if recovery_steps else 0.0,
        n_hubs_tested=len(drops),
        n_nodes=len(bp.nodes),
        n_edges=len(bp.edges),
    )


# ============================================================ critical-edge features
# (Re-exported from r1_mechanism_a.py so A2 can use them without a new import.)

def _count_weakly_connected_components(nodes: list[str], edges: list[tuple[str, str]]) -> int:
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
    if not edges:
        return set()
    bridges: set[tuple[str, str]] = set()
    base_ncc = _count_weakly_connected_components(nodes, edges)
    for edge in edges:
        remaining = [e for e in edges if e != edge]
        if _count_weakly_connected_components(nodes, remaining) > base_ncc:
            bridges.add(edge)
    return bridges


def _find_articulation_points(nodes: list[str], edges: list[tuple[str, str]]) -> set[str]:
    if not edges:
        return set()
    base_ncc = _count_weakly_connected_components(nodes, edges)
    out: set[str] = set()
    for node in nodes:
        rem_nodes = [n for n in nodes if n != node]
        rem_edges = [(a, b) for a, b in edges if a != node and b != node]
        if not rem_nodes:
            continue
        if _count_weakly_connected_components(rem_nodes, rem_edges) > base_ncc:
            out.add(node)
    return out


def _compute_edge_connectivity(nodes: list[str], edges: list[tuple[str, str]]) -> int:
    base_ncc = _count_weakly_connected_components(nodes, edges)
    if base_ncc > 1:
        return 0
    if not edges:
        return 0
    m = len(edges)
    for k in range(1, m + 1):
        for combo in _combinations(edges, k):
            remaining = [e for e in edges if e not in combo]
            if _count_weakly_connected_components(nodes, remaining) > base_ncc:
                return k
    return m


def _combinations(lst, k):
    if k == 0:
        yield ()
        return
    if len(lst) < k:
        return
    for i in range(len(lst)):
        for rest in _combinations(lst[i + 1:], k - 1):
            yield (lst[i],) + rest


@dataclass
class CriticalEdgeFeatures:
    n_nodes: int
    n_edges: int
    n_bridges: int
    bridge_fraction: float
    n_articulation_points: int
    edge_connectivity: int
    n_weakly_connected_components: int


def compute_critical_edge_features(bp: Blueprint) -> CriticalEdgeFeatures:
    nodes = list(bp.nodes)
    edges = list(bp.edges)
    n = len(nodes)
    m = len(edges)
    bridges = _find_bridges(nodes, edges)
    aps = _find_articulation_points(nodes, edges)
    ec = _compute_edge_connectivity(nodes, edges)
    n_wcc = _count_weakly_connected_components(nodes, edges)
    return CriticalEdgeFeatures(
        n_nodes=n, n_edges=m, n_bridges=len(bridges),
        bridge_fraction=len(bridges) / m if m else 0.0,
        n_articulation_points=len(aps), edge_connectivity=ec,
        n_weakly_connected_components=n_wcc,
    )


# ============================================================ CLI

def main() -> int:
    ap = argparse.ArgumentParser(description="A1 · Graded fault-isolation metric")
    ap.add_argument("--n-topologies", type=int, default=50)
    ap.add_argument("--n-nodes", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output-dir", default="./_r1_mechanism_a")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print(f"A1 · Graded fault-isolation metric")
    print(f"  n_topologies={args.n_topologies}, n_nodes={args.n_nodes}, seed={args.seed}")
    print(f"  output: {out_dir}\n")

    blueprints = generate_topologies(args.n_topologies, args.n_nodes, args.seed)
    results = []
    for i, bp in enumerate(blueprints):
        g = compute_graded_isolation(bp)
        results.append({
            "topology_idx": i,
            "blueprint_name": bp.name,
            "motif_family": bp.motif_family,
            "origin": bp.origin,
            "drop_magnitude": round(g.drop_magnitude, 4),
            "affected_module_count": g.affected_module_count,
            "affected_module_count_mean": round(g.affected_module_count_mean, 4),
            "mean_recovery_steps": round(g.mean_recovery_steps, 4),
            "n_hubs_tested": g.n_hubs_tested,
            "n_nodes": g.n_nodes,
            "n_edges": g.n_edges,
        })
        if not args.quiet:
            print(f"  [{i+1:2d}/{args.n_topologies}] {bp.name[:28]:<28s} "
                  f"drop={g.drop_magnitude:.3f} affected={g.affected_module_count} "
                  f"recovery={g.mean_recovery_steps:.2f}")

    # --- variance check (the whole point of A1) ---
    drops = [r["drop_magnitude"] for r in results]
    affected = [r["affected_module_count"] for r in results]
    affected_mean = [r["affected_module_count_mean"] for r in results]
    recovery = [r["mean_recovery_steps"] for r in results]

    def _var(xs):
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / len(xs)

    var_drop = _var(drops)
    var_affected = _var(affected)
    var_affected_mean = _var(affected_mean)
    var_recovery = _var(recovery)

    print(f"\n{'=' * 70}")
    print(f"VARIANCE CHECK (A1 acceptance criterion)")
    print(f"{'=' * 70}")
    print(f"  drop_magnitude       : mean={sum(drops)/len(drops):.4f} var={var_drop:.6f} "
          f"unique={len(set(round(x,4) for x in drops))}")
    print(f"  affected_modules MAX : mean={sum(affected)/len(affected):.2f} var={var_affected:.4f} "
          f"unique={len(set(affected))}  (saturates on small topologies -- reference only)")
    print(f"  affected_modules MEAN: mean={sum(affected_mean)/len(affected_mean):.4f} "
          f"var={var_affected_mean:.4f} unique={len(set(round(x,4) for x in affected_mean))}")
    print(f"  mean_recovery_steps  : mean={sum(recovery)/len(recovery):.4f} var={var_recovery:.6f} "
          f"unique={len(set(round(x,4) for x in recovery))}")

    # NOTE: the acceptance criterion uses the MEAN statistic, not MAX.  MAX is a
    # saturated statistic (it pins to n_modules on small dense topologies), which
    # is exactly the kind of silent saturation A1 exists to avoid.
    saturated = var_drop == 0.0 and var_affected_mean == 0.0 and var_recovery == 0.0
    verdict = "SATURATED" if saturated else "GRADED"
    print(f"\n  Verdict: {verdict}")
    if saturated:
        print("  ❌ All three graded quantities are constant across topologies.")
        print("     Even the graded metric cannot distinguish structures here.")
        print("     This is itself a negative result: the topology generator is too uniform.")
    else:
        print("  ✅ Graded metric has variance — L2 is usable for mechanism analysis.")

    summary = {
        "params": {"n_topologies": args.n_topologies, "n_nodes": args.n_nodes, "seed": args.seed},
        "variance": {
            "drop_magnitude": var_drop,
            "affected_module_count": var_affected,
            "affected_module_count_mean": var_affected_mean,
            "mean_recovery_steps": var_recovery,
        },
        "verdict": verdict,
        "note": "Graded isolation metric (A1). Replaces the saturated binary metric.",
    }

    json_path = out_dir / "graded_isolation.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "all_results": results}, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON: {json_path}")

    csv_path = out_dir / "graded_isolation.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader()
        w.writerows(results)
    print(f"  CSV:  {csv_path}")
    print(f"\n  Time: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())