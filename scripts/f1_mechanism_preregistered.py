#!/usr/bin/env python3
"""F1 · PR-1 preregistered mechanism test (报告 docs/PREREGISTRATION_PROTOCOL_v1.md §PR-1).

Why this exists
---------------
The A2 script (`mechanism_binary.py`) used a *median split* label:
`drop_magnitude < median(drops)` on the same 100 topologies being tested.
That is data-dependent (threshold moves if the sample moves) and throws
away continuous information (a topology with drop=0.20 and one with
drop=0.22 are in different classes even though the difference is noise).

PR-1 replaces that with an absolute, preregistered threshold
(`drop_magnitude > 0.25`), splits the 100 topologies into a fixed
train (idx 0..59) / held-out (idx 60..99) partition, fits logistic
regression on train, evaluates on held-out once, and reports a
permutation z-score for the held-out AUC.

The preregistered value of `--threshold` is read from the command line
and echoed into the JSON output; Gate 43 (`check_preregistered_claims.py`)
reads it back and FAILs if it does not match `research_claims.json.preregistered.PR1.threshold`.

Decision rule (predeclared, non-negotiable):
  held-out AUC ≥ 0.70 AND z ≥ 3.0  →  PR-1 PASS (R1 goes to L3)
  held-out AUC < 0.70              →  PR-1 FAIL (R1 stays at L2)

Usage:
    python scripts/f1_mechanism_preregistered.py \
        --threshold 0.25 \
        --train-idx 0:60 --held-out-idx 60:100 \
        --permutations 200 --seed 42 \
        --output-dir ./_r1_mechanism_prereg
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from isolation_graded import (  # noqa: E402
    generate_topologies,
    compute_graded_isolation,
    compute_critical_edge_features,
)
from mechanism_binary import (  # noqa: E402
    logistic_regression,
    predict_proba,
    auc_score,
)


# ============================================================ slice helpers

def _parse_slice(s: str, max_idx: int) -> tuple[int, int]:
    """Parse 'a:b' (half-open) into (start, end), validated against max_idx."""
    try:
        a, b = s.split(":")
        start, end = int(a), int(b)
    except (ValueError, AttributeError):
        raise SystemExit(f"--*-idx must be 'a:b', got {s!r}")
    if not (0 <= start < end <= max_idx):
        raise SystemExit(
            f"slice {s} out of range [0, {max_idx}] (need 0 ≤ a < b ≤ {max_idx})"
        )
    return start, end


# ============================================================ main

def main() -> int:
    ap = argparse.ArgumentParser(
        description="F1 · PR-1 preregistered mechanism test (logistic + held-out AUC)"
    )
    ap.add_argument("--threshold", type=float, default=0.25,
                    help="Absolute cutoff for the positive class "
                         "(label = 1 iff drop_magnitude > threshold). PR-1 default: 0.25.")
    ap.add_argument("--n-topologies", type=int, default=100)
    ap.add_argument("--n-nodes", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train-idx", default="0:60",
                    help="Half-open [start:end) slice of topology_idx for train")
    ap.add_argument("--held-out-idx", default="60:100",
                    help="Half-open [start:end) slice of topology_idx for held-out")
    ap.add_argument("--permutations", type=int, default=200,
                    help="Number of label-permutation nulls for z-score")
    ap.add_argument("--output-dir", default="./_r1_mechanism_prereg")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--preregistered-json",
                    default=str(REPO_ROOT / "research_claims.json"),
                    help="Path to research_claims.json (used for cross-check only; "
                         "the *source of truth* for --threshold is this CLI arg, "
                         "checked against research_claims.json by Gate 43).")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print("F1 · PR-1 preregistered mechanism test")
    print(f"  threshold       = {args.threshold}  (absolute, preregistered)")
    print(f"  n_topologies    = {args.n_topologies}, n_nodes={args.n_nodes}, seed={args.seed}")
    print(f"  train slice     = {args.train_idx}")
    print(f"  held-out slice  = {args.held_out_idx}")
    print(f"  permutations    = {args.permutations}")
    print(f"  output          = {out_dir}\n")

    # ------------------------------------------------------- generate + measure
    blueprints = generate_topologies(args.n_topologies, args.n_nodes, args.seed)

    rows = []
    for i, bp in enumerate(blueprints):
        g = compute_graded_isolation(bp)
        c = compute_critical_edge_features(bp)
        rows.append({
            "topology_idx": i,
            "blueprint_name": bp.name,
            "origin": bp.origin,
            "motif_family": bp.motif_family,
            "drop_magnitude": g.drop_magnitude,
            "affected_module_count": g.affected_module_count,
            "mean_recovery_steps": g.mean_recovery_steps,
            "n_bridges": c.n_bridges,
            "bridge_fraction": c.bridge_fraction,
            "n_articulation_points": c.n_articulation_points,
            "edge_connectivity": c.edge_connectivity,
            "n_weakly_connected_components": c.n_weakly_connected_components,
        })
        if not args.quiet and (i % 20 == 0 or i == args.n_topologies - 1):
            print(f"  [{i+1:3d}/{args.n_topologies}] {bp.name[:28]:<28s} "
                  f"drop={g.drop_magnitude:.3f} bridges={c.n_bridges}")

    # ------------------------------------------------------- apply absolute threshold
    # PR-1 label definition: 1 = drop_magnitude > threshold (positive = "high isolation")
    for r in rows:
        r["label"] = 1 if r["drop_magnitude"] > args.threshold else 0

    n_pos = sum(r["label"] for r in rows)
    drops = [r["drop_magnitude"] for r in rows]
    print(f"\n  Label: drop_magnitude > {args.threshold} → {n_pos}/{len(rows)} positive "
          f"(min={min(drops):.4f}, max={max(drops):.4f})")

    # ------------------------------------------------------- slice partition
    tr_start, tr_end = _parse_slice(args.train_idx, args.n_topologies)
    ho_start, ho_end = _parse_slice(args.held_out_idx, args.n_topologies)
    if not (tr_end <= ho_start):
        raise SystemExit(f"train [{tr_start},{tr_end}) overlaps held-out [{ho_start},{ho_end})")

    features = ["n_bridges", "bridge_fraction", "n_articulation_points", "edge_connectivity"]

    tr_rows = rows[tr_start:tr_end]
    ho_rows = rows[ho_start:ho_end]
    X_tr = [[float(r[f]) for f in features] for r in tr_rows]
    y_tr = [r["label"] for r in tr_rows]
    X_ho = [[float(r[f]) for f in features] for r in ho_rows]
    y_ho = [r["label"] for r in ho_rows]

    # Standardise using ONLY train statistics (this is what the null also uses).
    k = len(features)
    n = len(X_tr)
    means = [sum(X_tr[i][j] for i in range(n)) / n for j in range(k)]
    stds = [math.sqrt(sum((X_tr[i][j] - means[j]) ** 2 for i in range(n)) / n) or 1.0
            for j in range(k)]

    if not args.quiet:
        print(f"\n  Train set: n={n}, pos={sum(y_tr)}, features={features}")
        print(f"  Held-out:  n={len(ho_rows)}, pos={sum(y_ho)}")
        if sum(y_tr) == 0 or sum(y_tr) == n:
            print("  ⚠ Train set is degenerate (single class) — result will be AUC=0.5.")
        if sum(y_ho) == 0 or sum(y_ho) == len(y_ho):
            print("  ⚠ Held-out set is degenerate (single class) — AUC undefined.")

    # ------------------------------------------------------- fit + score held-out
    w = logistic_regression(X_tr, y_tr, lr=0.1, epochs=2000)
    proba_ho = predict_proba(w, X_ho, means, stds)
    auc_ho = auc_score(y_ho, proba_ho)

    # ------------------------------------------------------- permutation null
    rng = random.Random(args.seed)
    null_aucs = []
    for k_perm in range(args.permutations):
        y_null = y_tr[:]
        rng.shuffle(y_null)
        w_null = logistic_regression(X_tr, y_null, lr=0.1, epochs=400)
        proba_null = predict_proba(w_null, X_ho, means, stds)
        null_aucs.append(auc_score(y_ho, proba_null))

    null_mean = sum(null_aucs) / len(null_aucs)
    null_std = math.sqrt(sum((a - null_mean) ** 2 for a in null_aucs) / len(null_aucs)) or 1e-9
    z = (auc_ho - null_mean) / null_std

    # ------------------------------------------------------- verdict
    SUCCESS_AUC = 0.70
    SUCCESS_Z = 3.0
    if auc_ho >= SUCCESS_AUC and z >= SUCCESS_Z:
        verdict = "PASS"
        emoji = "✅"
    elif auc_ho >= SUCCESS_AUC:
        verdict = "WEAK_PASS"
        emoji = "🟡"
    else:
        verdict = "FAIL"
        emoji = "❌"

    print(f"\n{'=' * 70}")
    print("PR-1 PREREGISTERED MECHANISM TEST (F1)")
    print("=" * 70)
    print(f"  Threshold (absolute)    = {args.threshold}")
    print(f"  Features                = {features}")
    print(f"  Held-out AUC            = {auc_ho:.4f}   (success ≥ {SUCCESS_AUC})")
    print(f"  Null (perm, {args.permutations}x)     = {null_mean:.4f} ± {null_std:.4f}")
    print(f"  z-score                 = {z:.2f}         (success ≥ {SUCCESS_Z})")
    print(f"  Verdict                 = {emoji} {verdict}")

    # ------------------------------------------------------- persist
    summary = {
        "params": {
            "n_topologies": args.n_topologies,
            "n_nodes": args.n_nodes,
            "seed": args.seed,
            "threshold": args.threshold,
            "train_idx": args.train_idx,
            "held_out_idx": args.held_out_idx,
            "permutations": args.permutations,
        },
        "label_definition": f"drop_magnitude > {args.threshold} (absolute, preregistered)",
        "success_criteria": {
            "held_out_auc_min": SUCCESS_AUC,
            "z_min": SUCCESS_Z,
        },
        "features": features,
        "n_train": n,
        "n_held_out": len(ho_rows),
        "n_positive_train": sum(y_tr),
        "n_positive_held_out": sum(y_ho),
        "auc_held_out": auc_ho,
        "null_auc_mean": null_mean,
        "null_auc_std": null_std,
        "z_score": z,
        "verdict": verdict,
        "protocol": "PR-1 · PREREGISTRATION_PROTOCOL_v1.md",
        "method_note": ("Absolute threshold (not median split) applied once; "
                        "features frozen to critical-edge set; logistic + AUC; "
                        "permutation null on train labels, evaluation on held-out only."),
    }

    json_path = out_dir / "f1_preregistered.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "all_results": rows,
                   "train_rows": tr_rows, "held_out_rows": ho_rows,
                   "weights": w, "null_aucs": null_aucs}, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON: {json_path}")

    csv_path = out_dir / "f1_preregistered.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(f, fieldnames=rows[0].keys())
        wcsv.writeheader()
        wcsv.writerows(rows)
    print(f"  CSV:  {csv_path}")

    print(f"\n  Time: {time.time() - t0:.1f}s")
    print(f"  Verdict: {verdict}")
    # Non-zero exit only on hard failure so CI can see it.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
