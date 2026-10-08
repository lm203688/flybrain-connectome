#!/usr/bin/env python3
"""Structural fault-isolation predictor — calibration experiment.

QUESTION
--------
The project measured, on 27 topologies, whether shutting down a whole module
hurts less than shutting down the same number of random nodes (H1 modular
isolation). Those 27 numbers live in `FAULT_ISOLATION_REPORT.md` as prose.
Nobody has asked the follow-up: **can the outcome be predicted from the
wiring diagram alone, without running the ESN at all?**

If yes, "structural stability" stops being a post-hoc measurement and becomes
a *design-time* property — which is the whole point of the topology-aware
track (and the bridge toward fast structural judgement).

METHOD
------
For each of the 27 topologies (loaded exactly as `fault_isolation_experiment`
loads them, then densified to the same 75% intra cap):

  ground truth  = mod_shutdown_drop - random_shutdown_drop   (the F1 verdict)
  features      = structural profile from `topology_profile.py`
                  (module count, density, intra/inter ratio, modularity Q,
                   mean intra-module density, spectral radius)

Then it reports the correlation of each feature with the ground truth, and
fits a deliberately tiny, interpretable linear model. No black boxes: if a
single structural quantity tracks the verdict, say so; if none does, say that
too — a clean negative is a result.

Output: `isolation_predictor_results.json` + a printed report.

    python isolation_predictor.py --quick     # 8 topologies, faster
    python isolation_predictor.py             # all 27
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MCP = ROOT / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP))

import topology_profile as tp  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fie = _load("fie", HERE / "fault_isolation_experiment.py")


def features_from_W(W: np.ndarray, mods: np.ndarray) -> dict:
    """Structural features of the densified matrix, via topology_profile."""
    n = W.shape[0]
    nodes = [{"id": "n%d" % i, "module": int(mods[i])} for i in range(n)]
    edges = []
    ii, jj = np.nonzero(np.abs(W) > 1e-12)
    for i, j in zip(ii.tolist(), jj.tolist()):
        edges.append({"from": "n%d" % i, "to": "n%d" % j,
                      "weight": float(W[i, j])})
    prof = tp.profile({"nodes": nodes, "edges": edges})

    # extra: intra/inter edge ratio + mean intra-module density
    intra = inter = 0
    for i, j in zip(ii.tolist(), jj.tolist()):
        if i == j:
            continue
        if mods[i] == mods[j]:
            intra += 1
        else:
            inter += 1
    sizes = np.bincount(mods)
    intra_cap = sum(int(s) * (int(s) - 1) for s in sizes if s > 1) or 1
    nz = sizes[sizes > 0]
    med_size = float(np.median(nz)) if len(nz) else 0.0
    return {
        "k": prof["size"]["n_modules"],
        "n": prof["size"]["n_nodes"],
        "density": prof["size"]["density"],
        "modularity_q": prof["modularity_q"],
        "spectral_radius": prof["spectral_radius"],
        "intra_edges": intra,
        "inter_edges": inter,
        "intra_inter_ratio": round(intra / inter, 4) if inter else float("inf"),
        "mean_intra_density": round(intra / intra_cap, 4),
        "med_size_over_n": round(med_size / n, 4) if n else 0.0,
        "module_size_cv": round(float(nz.std() / nz.mean()), 4) if len(nz) and nz.mean() else 0.0,
    }


def measure_ground_truth(t: dict) -> dict | None:
    """Replicate fault_isolation_experiment.probe_main's F1 for one topology."""
    W, mods, reps = fie.densify_full(t["nodes"], t["edges"])
    n = W.shape[0]
    r2_base = fie.avg(W)
    if r2_base < 1e-3:
        return None
    mod_drops = []
    for m in sorted(set(mods.tolist())):
        Wd, _k = fie.disable_module(W, mods, reps, m)
        mod_drops.append(max(0.0, (r2_base - fie.avg(Wd)) / r2_base))
    med_size = int(np.median([int((mods == m).sum())
                              for m in sorted(set(mods.tolist()))]))
    rand_drops = []
    for i in range(fie.N_RANDOM):
        Wd = fie.disable_random(W, med_size, seed=1000 + i)
        rand_drops.append(max(0.0, (r2_base - fie.avg(Wd)) / r2_base))
    mod_med = float(np.median(mod_drops))
    rand_med = float(np.median(rand_drops))
    diff = mod_med - rand_med
    verdict = "H1" if diff < -0.05 else ("H2" if diff > 0.05 else "H3")
    feats = features_from_W(W, mods)
    return {"label": t["label"], "mod_drop": round(mod_med, 4),
            "rand_drop": round(rand_med, 4), "diff": round(diff, 4),
            "verdict": verdict, **feats}


FEATURES = ["k", "n", "density", "modularity_q", "spectral_radius",
            "intra_inter_ratio", "mean_intra_density",
            "med_size_over_n", "module_size_cv"]


def _threshold_scan(rows):
    """For each feature, the best single-split rule separating H1 from not-H1.

    Honest, interpretable, and impossible to overfit into a black box: one
    feature, one threshold, one direction. The class balance is reported
    alongside so a reader can see how much of the accuracy is just "always
    predict H1".
    """
    out = {}
    for f in FEATURES:
        vals = [(r[f], r["verdict"]) for r in rows if np.isfinite(r[f])]
        if len(vals) < 4:
            continue
        uniq = sorted({v for v, _ in vals})
        cands = ([(uniq[i] + uniq[i + 1]) / 2 for i in range(len(uniq) - 1)]
                 if len(uniq) > 1 else [uniq[0]])
        best = (0, None, None)
        for t in cands:
            for direction in (">", "<"):
                correct = sum(
                    1 for v, vd in vals
                    if (((v > t) if direction == ">" else (v < t)) == (vd == "H1")))
                if correct > best[0]:
                    best = (correct, t, direction)
        out[f] = {"best_correct": best[0], "n": len(vals),
                  "threshold": round(best[1], 4) if best[1] is not None else None,
                  "direction": best[2]}
    return out


def _pearson(xs, ys):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    if xs.std() < 1e-12 or ys.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(xs, ys)[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="only the first 8 topologies")
    ap.add_argument("--out", default=str(HERE / "isolation_predictor_results.json"))
    args = ap.parse_args()

    ts = fie.load_all()
    if args.quick:
        ts = ts[:8]
    print("=" * 92)
    print("STRUCTURAL FAULT-ISOLATION PREDICTOR — calibration")
    print("  %d topologies · ground truth = mod_shutdown_drop - random_shutdown_drop" % len(ts))
    print("=" * 92)

    rows = []
    for t in ts:
        r = measure_ground_truth(t)
        if r is None:
            print("  skip (weak baseline): %s" % t["label"])
            continue
        rows.append(r)
        print("  %-30s k=%-2d d=%.3f Q=%.3f | mod %.3f rand %.3f diff %+.3f %s"
              % (t["label"][:30], r["k"], r["density"],
                 r["modularity_q"] if r["modularity_q"] is not None else -1,
                 r["mod_drop"], r["rand_drop"], r["diff"], r["verdict"]))

    if len(rows) < 4:
        print("\nNot enough rows to fit anything (%d)." % len(rows))
        return 0

    diffs = [r["diff"] for r in rows]
    print("\n-- feature correlation with ground-truth diff (Pearson) --")
    corr = {}
    for f in FEATURES:
        xs = [r[f] for r in rows if np.isfinite(r[f])]
        ys = [r["diff"] for r in rows if np.isfinite(r[f])]
        corr[f] = round(_pearson(xs, ys), 3)
        print("  %-20s r = %+.3f" % (f, corr[f]))

    scan = _threshold_scan(rows)
    print("\n-- best single-feature threshold (predict H1 vs not-H1) --")
    for f, s in sorted(scan.items(), key=lambda kv: -kv[1]["best_correct"]):
        print("  %-20s %2d/%2d   rule: H1 iff x %s %.4f"
              % (f, s["best_correct"], s["n"], s["direction"], s["threshold"]))

    # Structural indeterminacy: near-identical wiring, opposite verdict. If this
    # fires, no structural feature can ever separate the pair.
    print("\n-- structural indeterminacy check (near-identical structure) --")
    indet = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            if (a["k"] == b["k"] and abs(a["density"] - b["density"]) < 0.02
                    and abs((a["modularity_q"] or 0) - (b["modularity_q"] or 0)) < 0.03
                    and a["verdict"] != b["verdict"]):
                indet.append([a["label"], a["verdict"], b["label"], b["verdict"]])
                print("  %s (%s) vs %s (%s) — k=%d d=%.3f/%.3f Q=%.3f/%.3f"
                      % (a["label"][:26], a["verdict"], b["label"][:26], b["verdict"],
                         a["k"], a["density"], b["density"],
                         a["modularity_q"] or 0, b["modularity_q"] or 0))
    if not indet:
        print("  none found at this tolerance")

    # Tiny interpretable linear model on the two strongest features.
    ranked = sorted(corr.items(), key=lambda kv: -abs(kv[1]))
    top = [f for f, _ in ranked[:2]]
    X = np.array([[r[f] for f in top] for r in rows], float)
    y = np.array(diffs, float)
    X1 = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(X1, y, rcond=None)
    pred = X1 @ coef
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # verdict accuracy using the fitted line + the same ±0.05 rule
    ok = sum(1 for p, r in zip(pred, rows)
             if ("H1" if p < -0.05 else ("H2" if p > 0.05 else "H3")) == r["verdict"])
    print("\n-- linear model on %s --" % top)
    print("  coef = %s" % [round(float(c), 5) for c in coef])
    print("  in-sample R² = %.3f   verdict accuracy = %d/%d" % (r2, ok, len(rows)))

    h1 = sum(1 for r in rows if r["verdict"] == "H1")
    print("\n  class balance: H1=%d H2=%d H3=%d"
          % (h1, sum(1 for r in rows if r["verdict"] == "H2"),
             sum(1 for r in rows if r["verdict"] == "H3")))
    print("  baseline (always predict H1) accuracy = %d/%d" % (h1, len(rows)))

    out = {"rows": rows, "correlations": corr, "threshold_scan": scan,
           "indeterminate_pairs": indet,
           "model_features": top, "model_coef": [float(c) for c in coef],
           "in_sample_r2": round(r2, 4), "verdict_accuracy": [ok, len(rows)],
           "caveat": ("in-sample fit on %d topologies; features are structural "
                      "only; a held-out set requires more topologies" % len(rows))}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
