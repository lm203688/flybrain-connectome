#!/usr/bin/env python3
"""F4 · Self-Interventional experiment (PR-2 of PREREGISTRATION_PROTOCOL_v1).

Methodology: Self-Interventional Learning (arXiv:2608.14894), four-tuple:
  self-intervention -> consequence learning -> held-out generalization ->
  structural action

The 30 intervention topologies are HELD OUT from any fitting set (train 0..59,
held-out 60..99 in PR-1). The intervention is one atomic structural action
per topology: delete_edge(e) with e drawn either from the bridge set (H1) or
from the non-bridge set (H2 control).

Predictions (preregistered):
  H1: delete bridge      -> drop_magnitude INCREASES
  H2: delete non-bridge  -> drop_magnitude changes LESS than H1

Success:
  direction_hit_rate >= 0.70   (21/30)
  AND  paired (delta_bridge - delta_nonbridge) test significant

Failure is a real negative result (per R-0.4) and is written to the JSON;
this script does NOT adjust thresholds to force a pass.

Usage:
    python scripts/f4_intervention_test.py \
        --n-topologies 30 --start-idx 100 --seed 42 \
        --output-dir ./_f4_intervention
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from isolation_graded import (  # noqa: E402
    generate_topologies,
    compute_graded_isolation,
    compute_critical_edge_features,
    _find_bridges,
)
from llm_tasks import Blueprint  # noqa: E402


# ============================================================ intervention

def _blueprint_without_edge(bp: Blueprint, edge: tuple[str, str]) -> Blueprint:
    """Return a Blueprint with a single edge removed (atomic structural action)."""
    return Blueprint(
        name=f"{bp.name}__minus_edge",
        nodes=bp.nodes,
        edges=tuple(e for e in bp.edges if e != edge),
        motif_family=bp.motif_family,
        capability_distribution=bp.capability_distribution,
        structure_signature_prefix=bp.structure_signature_prefix,
        origin=bp.origin,
    )


def _pick_edge(rng: random.Random, candidates: list[tuple[str, str]]) -> tuple[str, str]:
    """Deterministic single-edge pick under the shared RNG."""
    return rng.choice(candidates)


# ============================================================ result

@dataclass
class InterventionResult:
    topology_idx: int
    blueprint_name: str
    n_nodes: int
    n_edges: int
    n_bridges: int
    drop_before: float
    edge_removed_bridge: tuple | None
    drop_after_bridge: float | None
    delta_bridge: float | None
    edge_removed_nonbridge: tuple | None
    drop_after_nonbridge: float | None
    delta_nonbridge: float | None
    direction_hit_h1: bool | None     # delta_bridge > 0
    direction_hit_h1_gt_h2: bool | None  # delta_bridge > delta_nonbridge
    direction_hit_composite: bool | None  # H1 AND H1>H2


# ============================================================ paired test

def _paired_test(x: list[float], y: list[float]) -> dict:
    """Wilcoxon-style signed-rank-like paired test (rank of |x-y|).

    Falls back to a paired t-like z on mean difference when ties dominate.
    Returns a small dict with the test statistic and effect direction.
    """
    n = len(x)
    if n < 2 or len(y) != n:
        return {"n": n, "mean_delta": None, "z": None, "n_pos": None, "n_neg": None}
    d = [a - b for a, b in zip(x, y)]
    m = sum(d) / n
    var = sum((v - m) ** 2 for v in d) / n if n > 1 else 0.0
    se = math.sqrt(var / n) if n > 0 and var > 0 else None
    z = (m / se) if se and se > 0 else None
    n_pos = sum(1 for v in d if v > 1e-9)
    n_neg = sum(1 for v in d if v < -1e-9)
    return {
        "n": n,
        "mean_delta": m,
        "mean_delta_se": se,
        "z": z,
        "n_pos": n_pos,
        "n_neg": n_neg,
    }


# ============================================================ CLI

def main() -> int:
    ap = argparse.ArgumentParser(description="F4 · Self-Interventional experiment (PR-2)")
    ap.add_argument("--n-topologies", type=int, default=30)
    ap.add_argument("--n-nodes", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start-idx", type=int, default=100,
                    help="Start index in the extended topology stream; must "
                         "be outside the preregistered train (0..59) and "
                         "held-out (60..99) slices so held-out generalization "
                         "holds.")
    ap.add_argument("--success-rate", type=float, default=0.70)
    ap.add_argument("--min-z", type=float, default=1.96,
                    help="Paired-test z threshold for direction dominance")
    ap.add_argument("--output-dir", default="./_f4_intervention")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_needed = args.start_idx + args.n_topologies
    t0 = time.time()
    print("F4 · Self-Interventional experiment (PR-2)")
    print(f"  n_topologies={args.n_topologies}, start_idx={args.start_idx}, "
          f"n_nodes={args.n_nodes}, seed={args.seed}")
    print(f"  success_rate>={args.success_rate}, paired z>={args.min_z}")
    print(f"  output: {out_dir}\n")

    # Generate enough topologies so idx in [start, start+n) is available.
    all_bps = generate_topologies(total_needed, args.n_nodes, args.seed)
    slice_bps = all_bps[args.start_idx:args.start_idx + args.n_topologies]

    rng = random.Random(args.seed + 1)  # separate RNG for intervention picks
    results: list[InterventionResult] = []
    skipped_no_bridge = 0
    skipped_no_nonbridge = 0

    for off, bp in enumerate(slice_bps):
        idx = args.start_idx + off
        struct = compute_critical_edge_features(bp)
        g0 = compute_graded_isolation(bp)

        bridges = _find_bridges(list(bp.nodes), list(bp.edges))
        non_bridges = [e for e in bp.edges if e not in bridges]

        row = InterventionResult(
            topology_idx=idx,
            blueprint_name=bp.name,
            n_nodes=struct.n_nodes,
            n_edges=struct.n_edges,
            n_bridges=len(bridges),
            drop_before=g0.drop_magnitude,
            edge_removed_bridge=None,
            drop_after_bridge=None,
            delta_bridge=None,
            edge_removed_nonbridge=None,
            drop_after_nonbridge=None,
            delta_nonbridge=None,
            direction_hit_h1=None,
            direction_hit_h1_gt_h2=None,
            direction_hit_composite=None,
        )

        # --- H1: delete a bridge ---
        if bridges:
            e_bridge = _pick_edge(rng, list(bridges))
            bp_modified = _blueprint_without_edge(bp, e_bridge)
            g_b = compute_graded_isolation(bp_modified)
            row.edge_removed_bridge = e_bridge
            row.drop_after_bridge = g_b.drop_magnitude
            row.delta_bridge = g_b.drop_magnitude - g0.drop_magnitude
        else:
            skipped_no_bridge += 1

        # --- H2: delete a non-bridge ---
        if non_bridges:
            e_non = _pick_edge(rng, non_bridges)
            bp_modified_non = _blueprint_without_edge(bp, e_non)
            g_n = compute_graded_isolation(bp_modified_non)
            row.edge_removed_nonbridge = e_non
            row.drop_after_nonbridge = g_n.drop_magnitude
            row.delta_nonbridge = g_n.drop_magnitude - g0.drop_magnitude
        else:
            skipped_no_nonbridge += 1

        # --- direction hits (only where BOTH interventions ran) ---
        if row.delta_bridge is not None and row.delta_nonbridge is not None:
            row.direction_hit_h1 = row.delta_bridge > 0
            row.direction_hit_h1_gt_h2 = row.delta_bridge > row.delta_nonbridge
            row.direction_hit_composite = (
                row.direction_hit_h1 and row.direction_hit_h1_gt_h2
            )

        results.append(row)
        if not args.quiet and (off % 10 == 0 or off == args.n_topologies - 1):
            db = f"{row.delta_bridge:+.3f}" if row.delta_bridge is not None else "  -- "
            dn = f"{row.delta_nonbridge:+.3f}" if row.delta_nonbridge is not None else "  -- "
            print(f"  [{idx}] {bp.name[:24]:<24s} bridges={row.n_bridges} "
                  f"before={row.drop_before:.3f} "
                  f"d_brid={db} d_nonbr={dn} hit={row.direction_hit_composite}")

    # ------------------------------------------------------- summary
    usable = [r for r in results
              if r.delta_bridge is not None and r.delta_nonbridge is not None]
    n_pair = len(usable)

    if n_pair == 0:
        print("\nF4 · PR-2 INTERVENTION: SKIPPED (no topology had both "
              "bridge and non-bridge edges)")
        verdict = "SKIP"
        hit_rate = 0.0
        paired = {"n": 0}
    else:
        d_br = [r.delta_bridge for r in usable]
        d_nb = [r.delta_nonbridge for r in usable]
        hit_h1 = sum(1 for r in usable if r.direction_hit_h1)
        hit_gt = sum(1 for r in usable if r.direction_hit_h1_gt_h2)
        hit_composite = sum(1 for r in usable if r.direction_hit_composite)

        hit_rate = hit_composite / n_pair
        hit_rate_h1_only = hit_h1 / n_pair
        hit_rate_gt_only = hit_gt / n_pair
        paired = _paired_test(d_br, d_nb)

        print(f"\n{'=' * 70}")
        print("F4 · PR-2 SELF-INTERVENTIONAL EXPERIMENT")
        print("=" * 70)
        print(f"  n topologies (paired)     = {n_pair}")
        print(f"  H1 hit rate (d_brid>0)    = {hit_h1}/{n_pair} "
              f"= {hit_rate_h1_only:.2%}")
        print(f"  H1>H2 hit rate (d_br>d_nb)= {hit_gt}/{n_pair} "
              f"= {hit_rate_gt_only:.2%}")
        print(f"  Composite hit rate        = {hit_composite}/{n_pair} "
              f"= {hit_rate:.2%}  (success >= {args.success_rate:.0%})")
        print(f"  mean d_bridge      = {sum(d_br)/n_pair:+.4f}")
        print(f"  mean d_nonbridge   = {sum(d_nb)/n_pair:+.4f}")
        print(f"  paired (d_br-d_nb) mean={paired['mean_delta']:+.4f} "
              f"z={paired['z']} n_pos={paired['n_pos']} n_neg={paired['n_neg']}")

        passed = (hit_rate >= args.success_rate and
                  paired["z"] is not None and paired["z"] >= args.min_z)
        verdict = "PASS" if passed else "FAIL"
        print(f"\n  Verdict: {'PASS' if passed else 'FAIL'} ({verdict})")

    print(f"\n  Skipped (no bridge)    : {skipped_no_bridge}")
    print(f"  Skipped (no non-bridge): {skipped_no_nonbridge}")

    # ------------------------------------------------------- persist
    rows = [asdict(r) for r in results]

    summary = {
        "params": {
            "n_topologies": args.n_topologies,
            "start_idx": args.start_idx,
            "n_nodes": args.n_nodes,
            "seed": args.seed,
        },
        "predict_direction": "increase",
        "action": "delete_bridge",
        "control": "delete_nonbridge",
        "success_criteria": {
            "direction_hit_rate_min": args.success_rate,
            "paired_z_min": args.min_z,
        },
        "held_out_generalization": {
            "prereg_train_slice": "0:60",
            "prereg_held_out_slice": "60:100",
            "intervention_slice": f"{args.start_idx}:{args.start_idx + args.n_topologies}",
            "overlap_with_prereg": False,
        },
        "protocol": "PR-2 · PREREGISTRATION_PROTOCOL_v1.md",
        "methodology": "Self-Interventional Learning (arXiv:2608.14894)",
        "counts": {
            "n_pair": n_pair,
            "skipped_no_bridge": skipped_no_bridge,
            "skipped_no_nonbridge": skipped_no_nonbridge,
        },
        "hits": {
            "h1_hit_rate":      (sum(1 for r in usable if r.direction_hit_h1) / n_pair
                                  if n_pair else 0.0),
            "h1_gt_h2_hit_rate": (sum(1 for r in usable if r.direction_hit_h1_gt_h2) / n_pair
                                   if n_pair else 0.0),
            "composite_hit_rate": hit_rate if n_pair else 0.0,
        },
        "paired_test": paired,
        "verdict": verdict,
    }

    json_path = out_dir / "f4_intervention.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "all_results": rows}, f,
                  indent=2, ensure_ascii=False, default=str)
    print(f"\n  JSON: {json_path}")

    csv_path = out_dir / "f4_intervention.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wcsv.writeheader()
        wcsv.writerows(rows)
    print(f"  CSV:  {csv_path}")

    print(f"\n  Time: {time.time() - t0:.1f}s")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
