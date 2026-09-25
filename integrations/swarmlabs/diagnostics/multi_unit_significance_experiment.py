"""v2.10.0 显著性判定实验 —— 回答"效果是叠加了还是提高了"。

背景
  v2.5–v2.7 的实验只做 win/loss 计数（如 "3/3 全胜 bio_motif"），但没保留
  per-seed 数据 → 无法回答用户核心问题："测试通过了，但不知道效果是
  叠加了（噪声）还是真提高了"。

方法
  对每个 arm × 任务，跑 n_seeds 次独立 reservoir 迭代（每次独立 reservoir
  权重），收集 per-seed score 数组。对 (candidate, bio_motif) 做 4 种统计
  检验：
    1. Welch's t-test   — 参数检验（近似正态）
    2. Mann-Whitney U   — 非参数秩和（不假设分布）
    3. Bootstrap 95% CI — 均值差的百分位 CI（不假设分布）
    4. Cohen's d        — 标准化效应量

判定矩阵
    p<0.05 且 |d|≥0.5     → **real_gain**     真提高（值得宣称）
    p<0.05 且 0.2≤|d|<0.5 → **marginal_gain** 边际提高（谨慎）
    p<0.05 且 |d|<0.2     → **noise_only**    统计显著但效应微小（叠加噪音）
    p≥0.05                → **indistinguishable** 与 bio_motif 不可区分

用法
    python multi_unit_significance_experiment.py --quick   # n_seeds=15
    python multi_unit_significance_experiment.py            # n_seeds=30
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP))
sys.path.insert(0, str(HERE))

from unit_composition_experiment import (  # noqa: E402
    build_unit_topology, build_motif_topology, build_random_topology,
)
from dyn_calibration_probe import random_W  # noqa: E402
from functional_units import compose_from_units, load_units  # noqa: E402
from external_benchmark_experiment import (  # noqa: E402
    run_reservoir_full, ridge_solve, mse,
    task_binary_parity, task_noisy_parity, task_logistic_predict,
    task_double_pole,
)
from multi_unit_benchmark_experiment import (  # noqa: E402
    task_narma10,
    composition_olfactory_to_steering,
    composition_visual_to_escape,
    composition_gustatory_to_motion,
    build_composed_topology,
)


# --------------------------------------------------------------------------- #
# Per-seed runner: run task with n_seeds=1, seed_offset=k for each seed.
# This forces a distinct RNG stream per seed, giving us true per-seed data.
# --------------------------------------------------------------------------- #
def run_task_per_seed(W, task_name: str, n_seeds: int,
                      base_offset: int = 20260925) -> list:
    """Run a single task with n_seeds distinct RNG streams; return per-seed
    score array (length == n_seeds, or shorter if any seed produced NaN)."""
    scores = []
    for s in range(n_seeds):
        seed_offset = base_offset + s * 1009  # distinct stream per seed
        try:
            r = _call_task(task_name, W, n_seeds=1, seed_offset=seed_offset)
            scores.append(float(next(iter(r.values()))))
        except Exception:
            scores.append(float("nan"))
    return scores


def _call_task(task_name: str, W, n_seeds: int, seed_offset: int) -> dict:
    """Dispatch a task by name and pass seed_offset for independent RNG."""
    if task_name.startswith("parity_d3"):
        return task_binary_parity(W, n_seeds=n_seeds, seed_offset=seed_offset)
    if task_name.startswith("noisy_parity"):
        return task_noisy_parity(W, n_seeds=n_seeds, seed_offset=seed_offset)
    if task_name.startswith("logistic"):
        return task_logistic_predict(W, n_seeds=n_seeds, seed_offset=seed_offset)
    if task_name.startswith("double_pole"):
        return task_double_pole(W, n_seeds=n_seeds, seed_offset=seed_offset)
    if task_name.startswith("narma10"):
        return task_narma10(W, n_seeds=n_seeds, seed_offset=seed_offset)
    raise ValueError(f"unknown task: {task_name}")


# --------------------------------------------------------------------------- #
# Statistics helpers (no scipy dependency)
# --------------------------------------------------------------------------- #
def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def welch_ttest(a: np.ndarray, b: np.ndarray):
    """Welch's t-test. Returns (t, p) two-sided."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan"), float("nan")
    va = a.var(ddof=1)
    vb = b.var(ddof=1)
    denom = math.sqrt(va / na + vb / nb)
    if denom < 1e-14:
        # Both have zero variance — perfect tie, p=1
        if a.mean() == b.mean():
            return 0.0, 1.0
        # One differs from the other — but no variance to estimate SE.
        # Return extreme t but p=nan.
        return math.copysign(999.0, a.mean() - b.mean()), float("nan")
    t = (a.mean() - b.mean()) / denom
    z = abs(t)
    p = 2 * (1 - _normal_cdf(z))
    return float(t), float(p)


def mann_whitney_u(a: np.ndarray, b: np.ndarray):
    """Mann-Whitney U test via rank-sum. Returns (U, z, p) two-sided.

    Implementation: rank all 2n values (tie-average), compute U1 = R1 - n1(n1+1)/2,
    then U = min(U1, n1*n2 - U1), then normal-approx z and two-sided p.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan"), float("nan"), float("nan")
    combined = np.concatenate([a, b])
    order = np.argsort(combined, kind="mergesort")
    ranks = np.empty_like(combined)
    # Tie handling: average ranks for equal values
    sorted_vals = combined[order]
    i = 0
    while i < len(sorted_vals):
        j = i
        while j + 1 < len(sorted_vals) and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-indexed average
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    R1 = ranks[:na].sum()
    U1 = R1 - na * (na + 1) / 2
    U2 = na * nb - U1
    U = min(U1, U2)
    mu = na * nb / 2
    sigma = math.sqrt(na * nb * (na + nb + 1) / 12)
    if sigma < 1e-14:
        # All identical values
        if U == 0:
            # Perfect tie, p=1
            return 0.0, 0.0, 1.0
        return float(U), float("nan"), float("nan")
    # Continuity correction
    z = (abs(U - mu) - 0.5) / sigma
    p = 2 * (1 - _normal_cdf(abs(z)))
    return float(U), float(z), float(p)


def bootstrap_mean_diff_ci(a: np.ndarray, b: np.ndarray, n_boot: int = 10000,
                           ci: float = 0.95, seed: int = 20260925) -> tuple:
    """Bootstrap 95% percentile CI for mean(a) - mean(b)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        ai = rng.choice(a, size=len(a), replace=True)
        bi = rng.choice(b, size=len(b), replace=True)
        diffs[i] = ai.mean() - bi.mean()
    lo = float(np.quantile(diffs, (1 - ci) / 2))
    hi = float(np.quantile(diffs, 1 - (1 - ci) / 2))
    return lo, hi


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Pooled-SD Cohen's d. Positive = a > b."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if pooled < 1e-14:
        if a.mean() == b.mean():
            return 0.0
        return math.copysign(999.0, a.mean() - b.mean())
    return float((a.mean() - b.mean()) / pooled)


def classify_significance(p_val, d, higher_better: bool) -> str:
    """Classify a comparison as real_gain / marginal_gain / noise_only /
    indistinguishable / worse.

    `higher_better=True` means larger score is better (accuracy-like tasks).
    `higher_better=False` means smaller is better (MSE-like tasks).
    d is Cohen's d of candidate - baseline.
    """
    if p_val != p_val or d != d:  # NaN
        return "insufficient_data"
    abs_d = abs(d)
    # Direction: for higher-better, "gain" means d>0; for lower-better, d<0.
    same_direction_as_gain = (d > 0) if higher_better else (d < 0)
    if p_val < 0.05:
        if abs_d >= 0.5:
            return "real_gain" if same_direction_as_gain else "real_loss"
        elif abs_d >= 0.2:
            return "marginal_gain" if same_direction_as_gain else "marginal_loss"
        else:
            return "noise_only"
    else:
        if abs_d < 0.2:
            return "indistinguishable"
        # p≥0.05 but large d — likely underpowered. Mark as "trend".
        return "trend_gain" if same_direction_as_gain else "trend_loss"


# --------------------------------------------------------------------------- #
# Task registry
# --------------------------------------------------------------------------- #
TASK_REGISTRY = [
    ("parity_d3", True),        # accuracy, higher is better
    ("noisy_parity_d3", True),  # accuracy, higher is better
    ("logistic_r3.7", False),   # MSE, lower is better
    ("double_pole_p0.9_m0.5", False),  # MSE, lower is better
    ("narma10", False),         # MSE, lower is better
]


# --------------------------------------------------------------------------- #
# Arm builders
# --------------------------------------------------------------------------- #
def build_all_arms(n_nodes: int):
    """Build the 7 arms: 4 baselines + 3 composed multi-unit organisms."""
    W_textbook = random_W(n_nodes, seed=42)
    W_motif, e_motif = build_motif_topology(n_nodes=n_nodes, n_modules=4, seed=7)
    W_rand, _ = build_random_topology(n_nodes=W_motif.shape[0],
                                       n_edges=e_motif, seed=7)

    units = load_units()["units"]
    cc = next(u for u in units if u["name"] == "central_complex_steering_unit")
    W_cc, _, _ = build_unit_topology(cc, total_N=n_nodes, seed=42)

    arms = [
        ("textbook_random", "textbook_random", W_textbook),
        ("bio_motif", "bio_motif", W_motif),
        ("random_matched", "random_matched", W_rand),
        ("single_unit_best", "central_complex_steering_unit", W_cc),
    ]

    # 3 multi-unit compositions
    for label, comp_fn in [
        ("olfactory_to_steering", composition_olfactory_to_steering),
        ("visual_to_escape", composition_visual_to_escape),
        ("gustatory_to_motion", composition_gustatory_to_motion),
    ]:
        c = comp_fn()
        W_c, _, _ = build_composed_topology(c, total_N=n_nodes, seed=42)
        arms.append(("multi_unit_composed", label, W_c))

    return arms


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="n_seeds=15 (default: 30)")
    ap.add_argument("--n-nodes", type=int, default=60)
    ap.add_argument("--n-seeds", type=int, default=None)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    t0 = time.time()
    n_nodes = args.n_nodes
    n_seeds = args.n_seeds or (15 if args.quick else 30)
    print(f"multi-unit SIGNIFICANCE experiment   N={n_nodes}  "
          f"n_seeds={n_seeds}  quick={args.quick}")

    # --- Build arms ---
    print("\n=== building arms ===")
    arms = build_all_arms(n_nodes)
    for arm_name, label, W in arms:
        sv = np.linalg.svd(W, compute_uv=False)
        rank = int((np.abs(sv) > 1e-10).sum())
        print(f"  {arm_name:22s} {label:32s} "
              f"N={W.shape[0]}  density={(W != 0).mean():.3f}  rank={rank}")

    # --- Run every task per-seed for every arm ---
    print(f"\n=== running tasks per-seed (n_seeds={n_seeds}) ===")
    per_seed_store = {}   # {task: {label: [score_0..n_seeds-1]}}
    means = {}            # {task: {label: mean}}
    sds = {}              # {task: {label: sd}}
    for arm_name, label, W in arms:
        for tname, _hb in TASK_REGISTRY:
            if tname not in per_seed_store:
                per_seed_store[tname] = {}
            print(f"  {label:32s}  {tname:26s} ... ", end="", flush=True)
            scores = run_task_per_seed(W, tname, n_seeds=n_seeds)
            valid = [s for s in scores if not math.isnan(s)]
            if not valid:
                print(f"ALL NaN ({len(scores)} attempts failed)")
                per_seed_store[tname][label] = scores
                means[tname] = means.get(tname, {})
                means[tname][label] = float("nan")
                sds[tname] = sds.get(tname, {})
                sds[tname][label] = float("nan")
                continue
            m = float(np.mean(valid))
            sd = float(np.std(valid, ddof=1)) if len(valid) >= 2 else 0.0
            per_seed_store[tname][label] = scores
            means.setdefault(tname, {})[label] = m
            sds.setdefault(tname, {})[label] = sd
            print(f"mean={m:.6f}  sd={sd:.6f}")

    # --- Comparison table: each candidate vs bio_motif ---
    print("\n=== significance vs bio_motif ===")
    comparisons = []
    bio_labels = {"bio_motif"}
    for tname, higher_better in TASK_REGISTRY:
        if "bio_motif" not in per_seed_store[tname]:
            continue
        bio_scores = np.asarray(
            [s for s in per_seed_store[tname]["bio_motif"]
             if not math.isnan(s)], dtype=float)
        if len(bio_scores) < 3:
            continue
        for arm_name, label, _W in arms:
            if label in bio_labels:
                continue
            if label not in per_seed_store[tname]:
                continue
            cand_scores = np.asarray(
                [s for s in per_seed_store[tname][label]
                 if not math.isnan(s)], dtype=float)
            if len(cand_scores) < 3:
                continue
            t_stat, p_t = welch_ttest(cand_scores, bio_scores)
            U, z_u, p_u = mann_whitney_u(cand_scores, bio_scores)
            ci_lo, ci_hi = bootstrap_mean_diff_ci(cand_scores, bio_scores,
                                                  n_boot=5000, seed=20260925)
            d = cohens_d(cand_scores, bio_scores)
            verdict = classify_significance(p_u, d, higher_better)
            row = {
                "task": tname,
                "arm": arm_name,
                "label": label,
                "higher_better": higher_better,
                "cand_mean": float(cand_scores.mean()),
                "cand_sd": float(cand_scores.std(ddof=1)),
                "bio_mean": float(bio_scores.mean()),
                "bio_sd": float(bio_scores.std(ddof=1)),
                "diff": float(cand_scores.mean() - bio_scores.mean()),
                "welch_t": t_stat,
                "welch_p": p_t,
                "mwu_U": U,
                "mwu_z": z_u,
                "mwu_p": p_u,
                "ci95_lo": ci_lo,
                "ci95_hi": ci_hi,
                "cohens_d": d,
                "verdict": verdict,
            }
            comparisons.append(row)
            direction = "↑" if higher_better else "↓"
            print(f"  {label:32s}  {tname:26s} {direction} "
                  f"Δ={row['diff']:+.4f}  MWU p={p_u:.4f}  "
                  f"d={d:+.3f}  [{ci_lo:+.4f}, {ci_hi:+.4f}]  → {verdict}")

    # --- Aggregate: how many real_gain per arm? ---
    print("\n=== verdict summary per arm ===")
    arm_summary = {}
    for arm_name, label, _ in arms:
        if label in bio_labels:
            continue
        rows = [c for c in comparisons if c["label"] == label]
        if not rows:
            continue
        counts = {}
        for r in rows:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        arm_summary[label] = counts
        print(f"  {label:32s}  {counts}")

    # --- Aggregate: per task ---
    print("\n=== verdict summary per task ===")
    task_summary = {}
    for tname, _hb in TASK_REGISTRY:
        rows = [c for c in comparisons if c["task"] == tname]
        if not rows:
            continue
        counts = {}
        for r in rows:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        task_summary[tname] = counts
        print(f"  {tname:26s}  {counts}")

    elapsed = time.time() - t0
    print(f"\nelapsed {elapsed:.1f}s")

    out = args.out or str(HERE / "significance_results.json")
    payload = {
        "args": vars(args),
        "n_nodes": n_nodes,
        "n_seeds": n_seeds,
        "elapsed_s": elapsed,
        "arms": [{"arm": a, "label": l, "N": int(W.shape[0]),
                  "density": float((W != 0).sum()) / (W.shape[0] ** 2),
                  "rank": int((np.abs(np.linalg.svd(W, compute_uv=False)) > 1e-10).sum())}
                 for a, l, W in arms],
        "per_seed": per_seed_store,
        "means": means,
        "sds": sds,
        "comparisons": comparisons,
        "arm_summary": arm_summary,
        "task_summary": task_summary,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
