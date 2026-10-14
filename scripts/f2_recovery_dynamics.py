#!/usr/bin/env python3
"""F2 · Recovery / compensation dynamics (PR-4 of PREREGISTRATION_PROTOCOL_v1).

Why this exists
---------------
A1's third component `mean_recovery_steps` saturates at 0.0 in 64% of the
N=50 topologies (see docs/FRONTIER_VALUE_ENHANCEMENT_2026-10-14.md §一).
The root cause is measurement-layer: in a tiny 10-node graph with 11 edges
there is almost no multi-hop slack, and the current definition only counts
*still-reachable* node pairs (so the worst damage -- complete disconnection
-- is excluded). No amount of topology variation can add variance to a
measure whose definition has no variance room.

F2 replaces that scalar with a *dynamics* quantity: a recovery curve r(t)
over t = 1..T that integrates three named compensation mechanisms, each
of which can be ablated so its main effect is visible.

Mechanisms (aligned to the neuroscientific trichotomy cited in §四 F2):

  R-a  path recruitment      (R-a 旁路募集)     -- fast, structural (tau_a ~= 2)
  R-b  weight reallocation   (R-b 权重重分配)   -- medium, synaptic (tau_b ~= 5)
  R-c  steady-state gain     (R-c 稳态增益)     -- slow, homeostatic (tau_c ~= 8)

Each mechanism has a *ceiling* (max fraction of the deficit it can recover)
and a *time constant* (how fast it acts). The ceiling is modulated by a
structural property so different topologies end up with different recovery
trajectories:

  R-a ceiling  <- (1 - bridge_fraction - 0.5 * ap_fraction)
  R-b ceiling  <- edge_density / 0.5                       [redundant edges]
  R-c ceiling  <- (1 - ap_fraction)                        [APs localise]

Output:
  recovery_AUC  = (1/T) * sum_t r(t) / drop_magnitude    in [0, 1]
  t_half        = first t where r(t)/drop_magnitude >= 0.5  (or None)

Both carry variance by construction because each modulator is a different
function of the topology.

Usage:
    python scripts/f2_recovery_dynamics.py \
        --n-topologies 50 --n-nodes 10 --T 12 --seed 42 \
        --output-dir ./_f2_recovery

Gate 46 acceptance: zero_ratio < 0.30 AND variance(recovery_AUC) > 1e-6
                    AND at least one ablation has variance > 1e-6.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from isolation_graded import (  # noqa: E402
    generate_topologies,
    compute_graded_isolation,
    compute_critical_edge_features,
    CriticalEdgeFeatures,
)


# ============================================================ mechanism model

# Time constants (in discrete steps). Chosen so the three mechanisms
# occupy distinct timescales and none of them dominates the whole curve.
TAU_A = 2.0   # path recruitment: fast
TAU_B = 5.0   # weight reallocation: medium
TAU_C = 8.0   # steady-state gain: slow

# Per-mechanism ceilings (must sum to 1.0 so r_total can reach 1.0).
MAX_A = 0.35
MAX_B = 0.40
MAX_C = 0.25
assert abs(MAX_A + MAX_B + MAX_C - 1.0) < 1e-9, "ceiling budget must sum to 1.0"


@dataclass
class MechanismConfig:
    key: str            # short key for enabled-set lookup, e.g. "R_a"
    name: str           # display name, e.g. "path recruitment"
    max_ceiling: float
    tau: float


MECHANISMS: dict[str, MechanismConfig] = {
    "R_a": MechanismConfig("R_a", "path recruitment",    MAX_A, TAU_A),
    "R_b": MechanismConfig("R_b", "weight reallocation", MAX_B, TAU_B),
    "R_c": MechanismConfig("R_c", "steady-state gain",   MAX_C, TAU_C),
}


def _modulator_a(struct: "CriticalEdgeFeatures") -> float:
    """R-a: bridges block alternate paths; articulation points localise damage."""
    if struct.n_nodes == 0:
        return 0.0
    ap_frac = struct.n_articulation_points / struct.n_nodes
    return max(0.0, min(1.0, 1.0 - struct.bridge_fraction - 0.5 * ap_frac))


def _modulator_b(struct: "CriticalEdgeFeatures") -> float:
    """R-b: weight reallocation needs redundant edges (density proxy)."""
    n = max(struct.n_nodes, 1)
    max_possible = n * (n - 1)
    if max_possible == 0:
        return 0.0
    density = struct.n_edges / max_possible
    return max(0.0, min(1.0, density / 0.5))


def _modulator_c(struct: "CriticalEdgeFeatures") -> float:
    """R-c: steady-state gain needs module-integrity (few articulation points)."""
    n = max(struct.n_nodes, 1)
    ap_frac = struct.n_articulation_points / n
    return max(0.0, min(1.0, 1.0 - ap_frac))


_MODULATORS = {"R_a": _modulator_a, "R_b": _modulator_b, "R_c": _modulator_c}


def _r_single(t: float, cfg: MechanismConfig, modulator: float) -> float:
    """Recovery contribution of one mechanism at step t (fraction of deficit)."""
    if t <= 0 or modulator <= 0.0:
        return 0.0
    return cfg.max_ceiling * modulator * (1.0 - math.exp(-t / cfg.tau))


def compute_recovery_trajectory(
    struct: "CriticalEdgeFeatures",
    drop_magnitude: float,
    T: int,
    enabled: Optional[set[str]] = None,
) -> dict:
    """Simulate the recovery trajectory r(t) for t = 0..T.

    r_total(t) = min(1.0, sum_m r_m(t)) * drop_magnitude
    """
    enabled = enabled if enabled is not None else set(MECHANISMS.keys())
    mods = {k: _MODULATORS[k](struct) for k in MECHANISMS if k in enabled}
    curve = [0.0]
    for t in range(1, T + 1):
        s = sum(_r_single(float(t), MECHANISMS[k], mods[k]) for k in MECHANISMS
                if k in enabled)
        curve.append(min(1.0, s) * drop_magnitude)
    return {"curve": curve, "modulators": mods}


def _recovery_auc(curve: list[float], drop_magnitude: float) -> float:
    """Normalized AUC over t=1..T.

    Divided by drop_magnitude so recovery_AUC in [0,1] represents the
    fraction of the fault that was compensated, not the raw level.
    """
    T = len(curve) - 1
    if T <= 0 or drop_magnitude <= 0:
        return 0.0
    total = sum(curve[1:]) / T
    return max(0.0, min(1.0, total / drop_magnitude))


def _t_half(curve: list[float], drop_magnitude: float) -> Optional[float]:
    """First t where r(t)/drop_magnitude >= 0.5.

    If drop_magnitude <= 0 (no fault) t_half is 0.0 (nothing to recover).
    """
    if drop_magnitude <= 0:
        return 0.0
    T = len(curve) - 1
    if T <= 0:
        return None
    for i in range(1, T + 1):
        if curve[i] / drop_magnitude >= 0.5:
            return float(i)
    return None


def compute_ablation(struct: "CriticalEdgeFeatures", drop_magnitude: float, T: int) -> dict:
    """Run all / no_Ra / no_Rb / no_Rc and report recovery_AUC + t_half."""
    configs = {
        "all":            {"R_a", "R_b", "R_c"},
        "ablation_no_Ra": {"R_b", "R_c"},
        "ablation_no_Rb": {"R_a", "R_c"},
        "ablation_no_Rc": {"R_a", "R_b"},
    }
    out: dict[str, dict] = {}
    for name, enabled in configs.items():
        traj = compute_recovery_trajectory(struct, drop_magnitude, T, enabled=enabled)
        auc = _recovery_auc(traj["curve"], drop_magnitude)
        th  = _t_half(traj["curve"], drop_magnitude)
        out[name] = {"recovery_auc": auc, "t_half": th}
    return out


# ============================================================ result dataclass

@dataclass
class RecoveryDynamics:
    topology_idx: int
    blueprint_name: str
    motif_family: str
    origin: str
    n_nodes: int
    n_edges: int
    drop_magnitude: float
    recovery_auc: float
    t_half: Optional[float]
    auc_no_Ra: float
    auc_no_Rb: float
    auc_no_Rc: float
    contribution_Ra: float
    contribution_Rb: float
    contribution_Rc: float
    modulator_Ra: float
    modulator_Rb: float
    modulator_Rc: float


# ============================================================ CLI

def _var(xs: list[float]) -> float:
    if not xs:
        return 0.0
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def main() -> int:
    ap = argparse.ArgumentParser(description="F2 · Recovery / compensation dynamics (PR-4)")
    ap.add_argument("--n-topologies", type=int, default=50)
    ap.add_argument("--n-nodes", type=int, default=10)
    ap.add_argument("--T", type=int, default=12, help="Horizon in discrete steps")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output-dir", default="./_f2_recovery")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--zero-ratio-max", type=float, default=0.30,
                    help="Gate 46 acceptance: max fraction of zero-value recovery_AUC")
    ap.add_argument("--variance-min", type=float, default=1e-6,
                    help="Gate 46 acceptance: variance of recovery_AUC")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print("F2 · Recovery / compensation dynamics (PR-4)")
    print(f"  n_topologies={args.n_topologies}, n_nodes={args.n_nodes}, "
          f"T={args.T}, seed={args.seed}")
    print(f"  mechanism ceilings: R-a={MAX_A} (tau={TAU_A}), "
          f"R-b={MAX_B} (tau={TAU_B}), R-c={MAX_C} (tau={TAU_C})")
    print(f"  output: {out_dir}\n")

    blueprints = generate_topologies(args.n_topologies, args.n_nodes, args.seed)
    results: list[RecoveryDynamics] = []

    for i, bp in enumerate(blueprints):
        g = compute_graded_isolation(bp)
        struct = compute_critical_edge_features(bp)
        ab = compute_ablation(struct, g.drop_magnitude, args.T)

        rd = RecoveryDynamics(
            topology_idx=i,
            blueprint_name=bp.name,
            motif_family=bp.motif_family,
            origin=bp.origin,
            n_nodes=struct.n_nodes,
            n_edges=struct.n_edges,
            drop_magnitude=g.drop_magnitude,
            recovery_auc=ab["all"]["recovery_auc"],
            t_half=ab["all"]["t_half"],
            auc_no_Ra=ab["ablation_no_Ra"]["recovery_auc"],
            auc_no_Rb=ab["ablation_no_Rb"]["recovery_auc"],
            auc_no_Rc=ab["ablation_no_Rc"]["recovery_auc"],
            contribution_Ra=ab["all"]["recovery_auc"] - ab["ablation_no_Ra"]["recovery_auc"],
            contribution_Rb=ab["all"]["recovery_auc"] - ab["ablation_no_Rb"]["recovery_auc"],
            contribution_Rc=ab["all"]["recovery_auc"] - ab["ablation_no_Rc"]["recovery_auc"],
            modulator_Ra=_modulator_a(struct),
            modulator_Rb=_modulator_b(struct),
            modulator_Rc=_modulator_c(struct),
        )
        results.append(rd)
        if not args.quiet and (i % 20 == 0 or i == args.n_topologies - 1):
            print(f"  [{i+1:3d}/{args.n_topologies}] {bp.name[:26]:<26s} "
                  f"drop={rd.drop_magnitude:.3f} "
                  f"AUC={rd.recovery_auc:.3f} t_half={rd.t_half}")

    # ------------------------------------------------------- summary stats
    aucs  = [r.recovery_auc   for r in results]
    drops = [r.drop_magnitude for r in results]
    ths   = [r.t_half for r in results if r.t_half is not None]

    var_auc = _var(aucs)
    zero_auc_count = sum(1 for a in aucs if a == 0.0)
    zero_ratio = zero_auc_count / len(aucs)

    mean_cRa = sum(r.contribution_Ra for r in results) / len(results)
    mean_cRb = sum(r.contribution_Rb for r in results) / len(results)
    mean_cRc = sum(r.contribution_Rc for r in results) / len(results)
    var_cRa  = _var([r.contribution_Ra for r in results])
    var_cRb  = _var([r.contribution_Rb for r in results])
    var_cRc  = _var([r.contribution_Rc for r in results])

    success_zero     = zero_ratio < args.zero_ratio_max
    success_var      = var_auc > args.variance_min
    success_ablation = (var_cRa > args.variance_min or
                        var_cRb > args.variance_min or
                        var_cRc > args.variance_min)
    passed = success_zero and success_var and success_ablation
    verdict = "PASS" if passed else "FAIL"

    print(f"\n{'=' * 70}")
    print("F2 · PR-4 RECOVERY DYNAMICS")
    print("=" * 70)
    print(f"  recovery_AUC : mean={sum(aucs)/len(aucs):.4f} var={var_auc:.6f} "
          f"unique={len(set(round(x,4) for x in aucs))}")
    print(f"  zero-AUC count: {zero_auc_count}/{len(aucs)} = {zero_ratio:.2%} "
          f"(success < {args.zero_ratio_max:.0%})")
    print(f"  variance > 0  : {var_auc:.6f} (success > {args.variance_min})")
    if ths:
        print(f"  t_half defined: {len(ths)}/{len(results)}  mean={sum(ths)/len(ths):.2f}")
    else:
        print(f"  t_half defined: 0/{len(results)}")

    print(f"\n  Ablation main effects (mean contribution to recovery_AUC):")
    print(f"    R-a path recruitment    : {mean_cRa:+.4f}  var={var_cRa:.6f}")
    print(f"    R-b weight reallocation : {mean_cRb:+.4f}  var={var_cRb:.6f}")
    print(f"    R-c steady-state gain   : {mean_cRc:+.4f}  var={var_cRc:.6f}")
    print(f"  (>=1 ablation variance > 0 -> {success_ablation})")
    print(f"\n  Verdict: {'PASS' if passed else 'FAIL'} ({verdict})")

    # ------------------------------------------------------- persist
    rows = [asdict(r) for r in results]

    summary = {
        "params": {"n_topologies": args.n_topologies, "n_nodes": args.n_nodes,
                   "T": args.T, "seed": args.seed},
        "mechanisms": {
            "R_a_path_recruitment":    {"max_ceiling": MAX_A, "tau": TAU_A,
                                         "modulator": "(1 - bridge_fraction - 0.5*ap_fraction)"},
            "R_b_weight_reallocation": {"max_ceiling": MAX_B, "tau": TAU_B,
                                         "modulator": "edge_density / 0.5"},
            "R_c_steady_state_gain":   {"max_ceiling": MAX_C, "tau": TAU_C,
                                         "modulator": "(1 - ap_fraction)"},
        },
        "success_criteria": {
            "zero_ratio_max": args.zero_ratio_max,
            "variance_min":   args.variance_min,
            "ablation_variance_required": True,
        },
        "summary_stats": {
            "drop_magnitude_mean":   sum(drops)/len(drops),
            "drop_magnitude_var":    _var(drops),
            "recovery_auc_mean":     sum(aucs)/len(aucs),
            "recovery_auc_var":      var_auc,
            "recovery_auc_unique":   len(set(round(x,4) for x in aucs)),
            "zero_auc_count":        zero_auc_count,
            "zero_ratio":            zero_ratio,
            "t_half_defined":        len(ths),
            "t_half_mean":           (sum(ths)/len(ths) if ths else None),
        },
        "ablation_main_effects": {
            "R_a_path_recruitment":    {"mean_contribution": mean_cRa, "var": var_cRa},
            "R_b_weight_reallocation": {"mean_contribution": mean_cRb, "var": var_cRb},
            "R_c_steady_state_gain":   {"mean_contribution": mean_cRc, "var": var_cRc},
        },
        "verdict": verdict,
        "criteria_met": {
            "zero_ratio": success_zero,
            "variance":   success_var,
            "ablation":   success_ablation,
        },
        "protocol": "PR-4 · PREREGISTRATION_PROTOCOL_v1.md",
        "replaces": "mean_recovery_steps (A1 third component, 64% zero on N=50)",
    }

    json_path = out_dir / "f2_recovery_dynamics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "all_results": rows}, f,
                  indent=2, ensure_ascii=False, default=str)
    print(f"\n  JSON: {json_path}")

    csv_path = out_dir / "f2_recovery_dynamics.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wcsv.writeheader()
        wcsv.writerows(rows)
    print(f"  CSV:  {csv_path}")

    print(f"\n  Time: {time.time() - t0:.1f}s")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
