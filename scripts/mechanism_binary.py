#!/usr/bin/env python3
"""A2 · Binary-outcome mechanism test (报告 §九 A2).

The previous mechanism analysis used OLS linear regression on a binary outcome
(isolated = 0/1). On a 0/1 variable OLS has R² → 0 by construction (the variance
of a Bernoulli is bounded by 0.25 and a linear fit cannot capture the step),
so "no mechanism explains isolation" was a foregone conclusion of the wrong
method, not evidence about the mechanism.

This module re-runs the test with the *correct* tool for a binary outcome:
a logistic regression (classification) on the critical-edge features, and
reports AUC (area under the ROC curve) instead of R².

Decision rule:
  AUC ≈ 0.5      → features carry no signal (mechanism not supported)
  AUC > 0.7      → features discriminate (mechanism supported)
  AUC in between → weak signal, needs more data

Usage:
    python scripts/mechanism_binary.py --n-topologies 100 --n-nodes 10
    python scripts/mechanism_binary.py --summarise ./_r1_mechanism_a/mechanism_binary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
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


# ============================================================ tiny logistic regression
# (pure-python, no sklearn dependency — the repo gates run with stdlib only)

def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def logistic_regression(X: list[list[float]], y: list[int],
                        lr: float = 0.1, epochs: int = 2000) -> list[float]:
    """Fit a logistic regression via batch gradient descent.

    Returns the weight vector (bias last). Standardises features first so the
    learning rate is meaningful across scales.
    """
    n = len(X)
    if n == 0:
        return []
    k = len(X[0])

    # Standardise each feature (mean 0, std 1) so gradient descent is stable.
    means = [sum(X[i][j] for i in range(n)) / n for j in range(k)]
    stds = []
    for j in range(k):
        var = sum((X[i][j] - means[j]) ** 2 for i in range(n)) / n
        stds.append(math.sqrt(var) or 1.0)
    Xs = [[(X[i][j] - means[j]) / stds[j] for j in range(k)] for i in range(n)]

    w = [0.0] * (k + 1)  # last weight is the bias
    for _ in range(epochs):
        grad = [0.0] * (k + 1)
        for i in range(n):
            z = w[-1] + sum(w[j] * Xs[i][j] for j in range(k))
            p = _sigmoid(z)
            err = p - y[i]
            for j in range(k):
                grad[j] += err * Xs[i][j]
            grad[-1] += err
        for j in range(k + 1):
            w[j] -= lr * grad[j] / n
    return w


def predict_proba(w: list[float], X: list[list[float]],
                  means: list[float], stds: list[float]) -> list[float]:
    out = []
    for row in X:
        xs = [(row[j] - means[j]) / stds[j] for j in range(len(row))]
        z = w[-1] + sum(w[j] * xs[j] for j in range(len(row)))
        out.append(_sigmoid(z))
    return out


def auc_score(y_true: list[int], y_score: list[float]) -> float:
    """Rank-based AUC (Mann-Whitney U)."""
    pos = [s for s, t in zip(y_score, y_true) if t == 1]
    neg = [s for s, t in zip(y_score, y_true) if t == 0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


# ============================================================ main

def main() -> int:
    ap = argparse.ArgumentParser(description="A2 · Binary-outcome mechanism test")
    ap.add_argument("--n-topologies", type=int, default=100)
    ap.add_argument("--n-nodes", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output-dir", default="./_r1_mechanism_a")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    print(f"A2 · Binary-outcome mechanism test (logistic regression / AUC)")
    print(f"  n_topologies={args.n_topologies}, n_nodes={args.n_nodes}, seed={args.seed}")
    print(f"  output: {out_dir}\n")

    blueprints = generate_topologies(args.n_topologies, args.n_nodes, args.seed)

    rows = []
    for i, bp in enumerate(blueprints):
        g = compute_graded_isolation(bp)
        c = compute_critical_edge_features(bp)
        # Binary label: "well-isolated" = drop_magnitude below the median.
        # We use the *graded* drop magnitude (A1) so the label is meaningful.
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
        if not args.quiet:
            print(f"  [{i+1:2d}/{args.n_topologies}] {bp.name[:28]:<28s} "
                  f"drop={g.drop_magnitude:.3f} bridges={c.n_bridges}")

    # Binary label: high-isolation = drop_magnitude below median
    drops = sorted(r["drop_magnitude"] for r in rows)
    median = drops[len(drops) // 2]
    for r in rows:
        r["label"] = 1 if r["drop_magnitude"] < median else 0  # 1 = well-isolated

    n_pos = sum(r["label"] for r in rows)
    print(f"\n  Label: well-isolated (drop < median {median:.3f}) → {n_pos}/{len(rows)} positive")

    features = ["n_bridges", "bridge_fraction", "n_articulation_points", "edge_connectivity"]
    X = [[float(r[f]) for f in features] for r in rows]
    y = [r["label"] for r in rows]

    # Standardise (same as in logistic_regression)
    k = len(features)
    n = len(X)
    means = [sum(X[i][j] for i in range(n)) / n for j in range(k)]
    stds = [math.sqrt(sum((X[i][j] - means[j]) ** 2 for i in range(n)) / n) or 1.0 for j in range(k)]

    w = logistic_regression(X, y)
    proba = predict_proba(w, X, means, stds)
    auc = auc_score(y, proba)

    # Permutation baseline: shuffle labels, refit, report AUC.
    import random as _rnd
    rng = _rnd.Random(0)
    null_aucs = []
    for _ in range(200):
        y_null = y[:]
        rng.shuffle(y_null)
        w_null = logistic_regression(X, y_null, epochs=400)
        proba_null = predict_proba(w_null, X, means, stds)
        null_aucs.append(auc_score(y_null, proba_null))
    null_mean = sum(null_aucs) / len(null_aucs)
    null_std = math.sqrt(sum((a - null_mean) ** 2 for a in null_aucs) / len(null_aucs))

    print(f"\n{'=' * 70}")
    print(f"BINARY MECHANISM TEST (A2)")
    print(f"{'=' * 70}")
    print(f"  Features: {features}")
    print(f"  AUC (real)      = {auc:.4f}")
    print(f"  AUC (null mean) = {null_mean:.4f} ± {null_std:.4f}")
    z = (auc - null_mean) / (null_std or 1.0)
    print(f"  z-score         = {z:.2f}")

    if auc > 0.7 and z > 2.0:
        verdict = "SUPPORTED"
        print(f"\n  ✅ MECHANISM SUPPORTED: critical-edge features discriminate "
              f"well-isolated vs poorly-isolated topologies (AUC={auc:.3f}, z={z:.1f})")
    elif auc > 0.6 and z > 1.0:
        verdict = "WEAK_SIGNAL"
        print(f"\n  🟡 WEAK SIGNAL: features carry some signal but not decisive "
              f"(AUC={auc:.3f}, z={z:.1f})")
    else:
        verdict = "FALSIFIED"
        print(f"\n  ❌ MECHANISM FALSIFIED: critical-edge features do not discriminate "
              f"(AUC={auc:.3f}, z={z:.1f} ≈ random)")

    print(f"\n  Method note: OLS R² on a 0/1 outcome is bounded by the Bernoulli")
    print(f"  variance and cannot exceed 0.25; AUC is the correct metric here.")

    summary = {
        "params": {"n_topologies": args.n_topologies, "n_nodes": args.n_nodes, "seed": args.seed},
        "label_definition": f"drop_magnitude < median({median:.4f})",
        "n_positive": n_pos,
        "n_total": len(rows),
        "features": features,
        "auc": auc,
        "null_auc_mean": null_mean,
        "null_auc_std": null_std,
        "z_score": z,
        "verdict": verdict,
        "method_note": "Logistic regression + AUC (correct for binary outcome); "
                       "OLS R² on 0/1 is bounded by Bernoulli variance and is invalid.",
    }

    json_path = out_dir / "mechanism_binary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "all_results": rows}, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON: {json_path}")

    csv_path = out_dir / "mechanism_binary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(f, fieldnames=rows[0].keys())
        wcsv.writeheader()
        wcsv.writerows(rows)
    print(f"  CSV:  {csv_path}")
    print(f"\n  Time: {time.time() - t0:.1f}s")
    print(f"  Verdict: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())