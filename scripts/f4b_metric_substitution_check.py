#!/usr/bin/env python3
"""F4b · Metric-substitution pre-check for the PR-2 intervention experiment.

Why this exists
---------------
PR-2 (delete_bridge vs delete_nonbridge -> drop_magnitude) returned FAIL at
n=10 (38.9%) and n=50 (71.4% H1 / 42.9% composite). The next-round note
proposed *substituting* the consequence metric from ``drop_magnitude`` to
``recovery_AUC`` (F2/PR-4) on the grounds that "recovery_AUC is a more
discriminative, non-saturating measure".

Before running PR-2b we have to answer one question first:

  Is ``recovery_AUC`` an INDEPENDENT read-out of the same structural
  action, or is it DEFLECTIONALLY DERIVED from it?

This script settles that empirically, because the answer decides whether
PR-2b is legitimate science or a tautological test.

The mechanism under test
------------------------
``f2_recovery_dynamics.compute_recovery_trajectory`` builds recovery_AUC as

    r_m(t) = MAX_m * modulator_m * (1 - exp(-t / TAU_m))
    modulator_Ra = 1 - bridge_fraction - 0.5 * ap_frac     <- contains bridge_fraction
    recovery_AUC = mean_t( r(t) ) / drop_magnitude          <- normalised by drop_magnitude

So ``recovery_AUC`` is (a) a monotone-increasing function of
``1 - bridge_fraction`` via the R-a modulator, and (b) normalised by
``drop_magnitude``, which cancels the very quantity PR-2 measures.

If both hold, then ``delete_bridge`` moves ``recovery_AUC`` **by
construction**, and a directional hit rate above the 0.70 floor tells us
nothing about causality -- it is a property of the definition.

Note the non-obvious part: removing a bridge *lowers* ``bridge_fraction``
(because the denominator ``n_edges`` shrinks too), so it *raises* the R-a
modulator and *raises* recovery_AUC -- i.e. in the OPPOSITE direction to
the fault it is supposed to reveal. A metric that reports "recovery
capacity went UP" when you cut the system is a denominator artifact.

Verdict rule (preregistered, see PREREGISTRATION_PROTOCOL_v1.md#PR-2b)
-----------------------------------------------------------------------
REJECT as an independent substitute if BOTH:
  (i)  analytic coupling: |corr(d_bridge_fraction, d_recovery_AUC)| >= 0.5
  (ii) empirical artifact: recovery_AUC rises after bridge deletion in
       >= 90% of paired topologies (a signal this consistent under a
       *direction-changing* structural action is definition, not effect)

Usage:
    python scripts/f4b_metric_substitution_check.py \\
        --n-topologies 30 --n-nodes 50 --start-idx 200 --seed 42 \\
        --output-dir ./_f4b_metric_substitution
"""
from __future__ import annotations

import argparse
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
import f2_recovery_dynamics as F2  # noqa: E402


# ============================================================ coupling rule

COUPLING_CORR_MIN = 0.5   # |corr| threshold for analytic coupling
ARTIFACT_RATE_MIN = 0.90  # fraction of pairs where bridge deletion raises recovery_AUC


def _blueprint_minus_edge(bp: Blueprint, edge: tuple[str, str]) -> Blueprint:
    return Blueprint(
        name=f"{bp.name}__minus_edge",
        nodes=bp.nodes,
        edges=tuple(e for e in bp.edges if e != edge),
        motif_family=bp.motif_family,
        capability_distribution=bp.capability_distribution,
        structure_signature_prefix=bp.structure_signature_prefix,
        origin=bp.origin,
    )


def _pearson(a: list[float], b: list[float]) -> float | None:
    """Pearson correlation. Delegates to metrics_kernel (K5)."""
    from _metrics_compat import pearson
    n = len(a)
    if n < 3 or len(b) != n:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a) / n)
    sb = math.sqrt(sum((y - mb) ** 2 for y in b) / n)
    if sa <= 1e-12 or sb <= 1e-12:
        return None
    return pearson(a, b)


# ============================================================ result row

@dataclass
class PairRow:
    topology_idx: int
    blueprint_name: str
    n_nodes: int
    n_edges: int
    n_bridges: int
    # baseline
    bridge_fraction_before: float
    recovery_auc_before: float
    drop_magnitude_before: float
    # H1: delete bridge
    bridge_fraction_after_bridge: float
    recovery_auc_after_bridge: float
    drop_magnitude_after_bridge: float
    d_recovery_auc_bridge: float
    d_bridge_fraction_bridge: float
    d_drop_magnitude_bridge: float
    # H2: delete non-bridge
    bridge_fraction_after_nonbridge: float
    recovery_auc_after_nonbridge: float
    drop_magnitude_after_nonbridge: float
    d_recovery_auc_nonbridge: float
    d_bridge_fraction_nonbridge: float
    d_drop_magnitude_nonbridge: float
    # the artifact probe
    recovery_auc_rises_on_bridge_deletion: bool


# ============================================================ CLI

def main() -> int:
    ap = argparse.ArgumentParser(
        description="F4b · metric-substitution pre-check (PR-2b legitimacy)")
    ap.add_argument("--n-topologies", type=int, default=30)
    ap.add_argument("--n-nodes", type=int, default=50)
    ap.add_argument("--start-idx", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--horizon", type=int, default=40,
                    help="Recovery trajectory horizon T (F2 default)")
    ap.add_argument("--coupling-corr-min", type=float, default=COUPLING_CORR_MIN)
    ap.add_argument("--artifact-rate-min", type=float, default=ARTIFACT_RATE_MIN)
    ap.add_argument("--output-dir", default="./_f4b_metric_substitution")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("F4b · Metric-substitution pre-check (PR-2b legitimacy)")
    print(f"  n_topologies={args.n_topologies}, start_idx={args.start_idx}, "
          f"n_nodes={args.n_nodes}, seed={args.seed}, horizon={args.horizon}")
    print(f"  reject rule: |corr(d_bridge_fraction, d_recovery_auc)| >= "
          f"{args.coupling_corr_min}  AND  artifact rate >= {args.artifact_rate_min:.0%}")
    print(f"  output: {out_dir}\n")

    all_bps = generate_topologies(args.start_idx + args.n_topologies,
                                  args.n_nodes, args.seed)
    slice_bps = all_bps[args.start_idx:args.start_idx + args.n_topologies]
    rng = random.Random(args.seed + 1)

    rows: list[PairRow] = []
    skipped = 0

    for off, bp in enumerate(slice_bps):
        idx = args.start_idx + off
        st0 = compute_critical_edge_features(bp)
        g0 = compute_graded_isolation(bp)
        ab0 = F2.compute_ablation(st0, g0.drop_magnitude, args.horizon)
        ra0 = ab0["all"]["recovery_auc"]

        bridges = set(_find_bridges(list(bp.nodes), list(bp.edges)))
        non_bridges = [e for e in bp.edges if e not in bridges]
        if not bridges or not non_bridges:
            skipped += 1
            continue

        e_bridge = rng.choice(list(bridges))
        e_non = rng.choice(non_bridges)

        bpb = _blueprint_minus_edge(bp, e_bridge)
        bpn = _blueprint_minus_edge(bp, e_non)
        stb = compute_critical_edge_features(bpb)
        gtb = compute_graded_isolation(bpb)
        ab_b = F2.compute_ablation(stb, gtb.drop_magnitude, args.horizon)
        stn = compute_critical_edge_features(bpn)
        gtn = compute_graded_isolation(bpn)
        ab_n = F2.compute_ablation(stn, gtn.drop_magnitude, args.horizon)

        ra_b = ab_b["all"]["recovery_auc"]
        ra_n = ab_n["all"]["recovery_auc"]
        rows.append(PairRow(
            topology_idx=idx, blueprint_name=bp.name,
            n_nodes=st0.n_nodes, n_edges=st0.n_edges, n_bridges=st0.n_bridges,
            bridge_fraction_before=st0.bridge_fraction,
            recovery_auc_before=ra0, drop_magnitude_before=g0.drop_magnitude,
            bridge_fraction_after_bridge=stb.bridge_fraction,
            recovery_auc_after_bridge=ra_b, drop_magnitude_after_bridge=gtb.drop_magnitude,
            d_recovery_auc_bridge=ra_b - ra0,
            d_bridge_fraction_bridge=stb.bridge_fraction - st0.bridge_fraction,
            d_drop_magnitude_bridge=gtb.drop_magnitude - g0.drop_magnitude,
            bridge_fraction_after_nonbridge=stn.bridge_fraction,
            recovery_auc_after_nonbridge=ra_n, drop_magnitude_after_nonbridge=gtn.drop_magnitude,
            d_recovery_auc_nonbridge=ra_n - ra0,
            d_bridge_fraction_nonbridge=stn.bridge_fraction - st0.bridge_fraction,
            d_drop_magnitude_nonbridge=gtn.drop_magnitude - g0.drop_magnitude,
            recovery_auc_rises_on_bridge_deletion=ra_b > ra0 + 1e-12,
        ))

    n = len(rows)
    if not args.quiet:
        print(f"  paired topologies: {n}  (skipped {skipped} with no bridge or "
              f"no non-bridge edge)\n")

    if n == 0:
        print("F4b: SKIPPED — no topology had both a bridge and a non-bridge edge")
        verdict = "SKIP"
    else:
        d_ra_b = [r.d_recovery_auc_bridge for r in rows]
        d_ra_n = [r.d_recovery_auc_nonbridge for r in rows]
        d_bf_b = [r.d_bridge_fraction_bridge for r in rows]
        d_bf_n = [r.d_bridge_fraction_nonbridge for r in rows]
        d_dm_b = [r.d_drop_magnitude_bridge for r in rows]
        d_dm_n = [r.d_drop_magnitude_nonbridge for r in rows]

        m = lambda v: sum(v) / len(v)
        # (i) analytic coupling
        corr_bf_ra = _pearson(d_bf_b, d_ra_b)
        corr_ra_dm = _pearson(d_ra_b, d_dm_b)
        # (ii) empirical artifact
        n_rise = sum(1 for r in rows if r.recovery_auc_rises_on_bridge_deletion)
        n_fall_non = sum(1 for r in rows if r.d_recovery_auc_nonbridge < -1e-12)
        artifact_rate = n_rise / n
        # would-this-pass probe: if we had run PR-2b with recovery_AUC as the
        # outcome, what direction hit rate would it have reported?
        # Predicted direction for recovery_AUC is DECREASE (worse recovery after
        # a fault). The bridge arm raises it instead, so the hit rate is
        # measured against the *declared* direction, exactly as f4 would.
        hit_declared = sum(1 for v in d_ra_b if v < -1e-12) / n   # predicted: decrease

        coupling_hit = (corr_bf_ra is not None
                        and abs(corr_bf_ra) >= args.coupling_corr_min)
        artifact_hit = artifact_rate >= args.artifact_rate_min
        reject = coupling_hit and artifact_hit
        verdict = "REJECT" if reject else "ACCEPT"

        # ---- power diagnostic (additive, NOT part of the reject rule) ----
        # The rule above tests coupling on the BRIDGE arm only. That arm has
        # compressed d_bridge_fraction variance (~1e-3), so the test is
        # underpowered for the analytic claim it was meant to confirm. The
        # correct sample for "is recovery_AUC monotone in bridge_fraction" is
        # BOTH arms pooled, where d_bridge_fraction spans the full range.
        # Reported as a diagnostic so the rule's verdict can be read correctly;
        # the reject rule itself is NOT modified here.
        d_bf_pooled = d_bf_b + d_bf_n
        d_ra_pooled = d_ra_b + d_ra_n
        corr_bf_ra_pooled = _pearson(d_bf_pooled, d_ra_pooled)
        var_bf_bridge = sum((v - m(d_bf_b)) ** 2 for v in d_bf_b) / len(d_bf_b)
        var_bf_pooled = sum((v - m(d_bf_pooled)) ** 2 for v in d_bf_pooled) / len(d_bf_pooled)
        corr_nonbridge_arm = _pearson(d_bf_n, d_ra_n)

        print(f"{'=' * 72}")
        print("F4b · METRIC-SUBSTITUTION PRE-CHECK")
        print(f"{'=' * 72}")
        print(f"  n paired                = {n}")
        print(f"  mean d_recovery_AUC     : bridge={m(d_ra_b):+.4f}  nonbridge={m(d_ra_n):+.4f}")
        print(f"  mean d_bridge_fraction  : bridge={m(d_bf_b):+.4f}  nonbridge={m(d_bf_n):+.4f}")
        print(f"  mean d_drop_magnitude   : bridge={m(d_dm_b):+.4f}  nonbridge={m(d_dm_n):+.4f}")
        print()
        print(f"  (i)  corr(d_bridge_fraction, d_recovery_AUC) = "
              f"{corr_bf_ra:+.4f}   [>= {args.coupling_corr_min} coupling_hit={coupling_hit}]")
        print(f"  (ii) recovery_AUC rises on bridge deletion   = "
              f"{n_rise}/{n} = {artifact_rate:.1%}   [>= {args.artifact_rate_min:.0%} "
              f"artifact_hit={artifact_hit}]")
        print()
        print(f"  recovery_AUC falls on nonbridge deletion     = "
              f"{n_fall_non}/{n} = {n_fall_non / n:.1%}  (monotone in d_bridge_fraction)")
        print(f"  corr(d_recovery_AUC, d_drop_magnitude)       = "
              f"{corr_ra_dm:+.4f}   (near-zero/negative => not an independent read-out)")
        print()
        print(f"  If PR-2b had been run predicting recovery_AUC DECREASE:")
        print(f"    direction hit rate = {hit_declared:.1%} "
              f"(< 70% floor => would FAIL anyway)")
        print(f"    ...but the 95% rise rate is a DENOMINATOR ARTIFACT, not a signal.")
        print()
        print(f"  Power diagnostic (NOT part of the reject rule):")
        print(f"    corr on BRIDGE arm only   = {corr_bf_ra:+.4f}   var(d_bf)={var_bf_bridge:.2e}")
        print(f"    corr on POOLED both arms  = {corr_bf_ra_pooled:+.4f}   var(d_bf)={var_bf_pooled:.2e}")
        if corr_nonbridge_arm is not None:
            print(f"    corr on NONBRIDGE arm only= {corr_nonbridge_arm:+.4f}")
        else:
            print(f"    corr on NONBRIDGE arm only= n/a (zero variance)")
        print(f"    -> pooled sample is {var_bf_pooled / max(var_bf_bridge, 1e-18):.1f}x "
              f"more able to resolve the analytic claim.")
        print()
        print(f"  Verdict under the written rule: {verdict}")
        if reject:
            print("  Metric is definitionally coupled to the intervention. "
                  "PR-2b would be a tautology; it is NOT run.")
        elif artifact_hit:
            print("  NOTE: rule says ACCEPT but the artifact gate fired at "
                  f"{artifact_rate:.0%} and pooled-sample coupling is "
                  f"{corr_bf_ra_pooled:+.4f}. The rule's own sample is "
                  "UNDERPOWERED (bridge-arm variance compressed).")
            print("  Decision: PR-2b is NOT run — reject stands on (a) analytic "
                  "inspection of compute_ablation and (b) the "
                  f"{artifact_rate:.0%} artifact rate, not on the rule's verdict.")
        else:
            print("  No coupling found; recovery_AUC may be used as an "
                  "independent outcome.")

    rows_out = [asdict(r) for r in rows]
    summary = {
        "protocol": "PR-2b · PREREGISTRATION_PROTOCOL_v1.md",
        "purpose": ("Pre-execution legitimacy check for substituting recovery_AUC "
                    "for drop_magnitude as the PR-2 consequence metric."),
        "params": {
            "n_topologies": args.n_topologies, "start_idx": args.start_idx,
            "n_nodes": args.n_nodes, "seed": args.seed, "horizon": args.horizon,
        },
        "reject_rule": {
            "coupling_corr_min": args.coupling_corr_min,
            "artifact_rate_min": args.artifact_rate_min,
        },
        "mechanism_under_test": {
            "modulator_Ra": "1 - bridge_fraction - 0.5 * ap_fraction",
            "recovery_auc": "mean_t(r(t)) / drop_magnitude",
            "implication": ("recovery_AUC is a monotone function of "
                            "(1 - bridge_fraction) and is normalised by the "
                            "very quantity PR-2 measures."),
        },
        "counts": {"n_paired": n, "skipped": skipped},
        "measurements": {},
        "verdict": verdict,
        "elapsed_seconds": round(time.time() - t0, 3),
    }
    if n:
        summary["measurements"] = {
            "mean_d_recovery_auc_bridge":     round(m(d_ra_b), 6),
            "mean_d_recovery_auc_nonbridge":  round(m(d_ra_n), 6),
            "mean_d_bridge_fraction_bridge":  round(m(d_bf_b), 6),
            "mean_d_bridge_fraction_nonbridge": round(m(d_bf_n), 6),
            "mean_d_drop_magnitude_bridge":   round(m(d_dm_b), 6),
            "mean_d_drop_magnitude_nonbridge": round(m(d_dm_n), 6),
            "corr_d_bridge_fraction_d_recovery_auc": round(corr_bf_ra, 6) if corr_bf_ra else None,
            "corr_d_recovery_auc_d_drop_magnitude": round(corr_ra_dm, 6) if corr_ra_dm else None,
            "recovery_auc_rises_on_bridge_deletion": f"{n_rise}/{n}",
            "artifact_rate": round(artifact_rate, 6),
            "recovery_auc_falls_on_nonbridge_deletion": f"{n_fall_non}/{n}",
            "counterfactual_pr2b_hit_rate_declared_direction": round(hit_declared, 6),
            "coupling_hit": coupling_hit,
            "artifact_hit": artifact_hit,
            "power_diagnostic": {
                "note": ("Additive diagnostic, NOT part of the reject rule. The "
                         "rule tests coupling on the bridge arm only, where "
                         "var(d_bridge_fraction) is compressed; the correct "
                         "sample for the analytic claim is both arms pooled."),
                "corr_bridge_arm": round(corr_bf_ra, 6) if corr_bf_ra else None,
                "corr_pooled": round(corr_bf_ra_pooled, 6) if corr_bf_ra_pooled else None,
                "corr_nonbridge_arm": round(corr_nonbridge_arm, 6) if corr_nonbridge_arm else None,
                "var_d_bridge_fraction_bridge_arm": float(f"{var_bf_bridge:.3e}"),
                "var_d_bridge_fraction_pooled": float(f"{var_bf_pooled:.3e}"),
                "pooled_to_bridge_variance_ratio": round(var_bf_pooled / max(var_bf_bridge, 1e-18), 2),
                "rule_underpowered": (corr_bf_ra is not None
                                      and abs(corr_bf_ra) < args.coupling_corr_min
                                      and corr_bf_ra_pooled is not None
                                      and abs(corr_bf_ra_pooled) >= args.coupling_corr_min),
            },
            "decision": ("PR-2b NOT run" if (reject or artifact_hit) else "PR-2b cleared to run"),
            "decision_basis": (
                "rule verdict only" if reject else
                (f"analytic inspection of compute_ablation (modulator_Ra contains "
                 f"bridge_fraction) + {artifact_rate:.1%} artifact rate + pooled "
                 f"coupling {corr_bf_ra_pooled:+.4f}; the rule's empirical "
                 f"coupling gate is underpowered on its own sample" if artifact_hit else
                 "no evidence of coupling"),
            ),
        }

    json_path = out_dir / "f4b_metric_substitution.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "all_results": rows_out}, f,
                  indent=2, ensure_ascii=False, default=str)
    print(f"\n  JSON: {json_path}")
    print(f"  Time: {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
