"""v2.23.0 单元库回灌引擎验证实验 (#126)。

验证单元库是否具备"结构精简 + 结构稳定性"能力。

背景
  项目有 103 个功能单元 + 66 种连接类型，但从未系统性验证过「用单元组合出的
  拓扑」在计算性能上是否优于「生物 motif 设计」和「随机拓扑」。

  之前 v2.17-v2.21 涌现链已三度证伪（MSE/conv90/latency × N/seed_offset/combo），
  但那些测的是「涌现」——组合是否产生单单元没有的能力。
  本实验测的是不同的东西：「结构指标」——组合拓扑是否在同等规模下
  具有更好的计算效率和故障隔离能力。

方法
  三臂对比：
    A. UNIT:    从 103 单元库随机抽取 3-5 单元组合，compose_from_units 生成拓扑
    B. BIO:     design_organism(blueprint) 生成生物启发拓扑
    C. RANDOM:  Erdős–Rényi 随机图（匹配节点数）

  对每臂跑：
    1. r2_score(delay=5): ESN 延迟任务性能（越高越好）
    2. fault_isolation:   模块关停 vs 随机关停的性能降幅比（H1/H2/H3 判定）
    3. 结构指标:          节点数、边数、平均度、密度、模块数

  4 组合 × 3 臂 = 12 个拓扑，n_seeds=20（v2.15 教训：n_seeds<20 样本偏差）
  Bonferroni α = 0.05/6 = 0.0083（6 个比较：UNIT vs BIO, UNIT vs RAND, BIO vs RAND × r2+FI）

诚实边界
  · N=60 与之前实验一致，避免引入规模变量
  · 只测 2 个硬指标（r2_score, fault_isolation）避免多重比较失控
  · 如果 UNIT 优于 BIO 但 |d|<0.5，写「方向存在但强度弱」，不宣称提效
  · 如果 UNIT 劣于 RANDOM，说明单元库设计有问题——这是有价值的负面结果

用法
  python unit_engine_feedback_experiment.py --quick    # n_seeds=5
  python unit_engine_feedback_experiment.py            # n_seeds=20
  python unit_engine_feedback_experiment.py --n-seeds 50  # 完全确认
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP))
sys.path.insert(0, str(HERE))

from functional_units import compose_from_units, load_units, DEMO  # noqa: E402

NODE_CAP = 60
DELAY = 5
RHO = 1.0
N_SEEDS = 20
SEED = 20260929
N_UNIT_COMPOSITIONS = 4
N_RANDOM = 3


# =========================================================================== #
# ESN 评估器（复用 fault_isolation_experiment.py）
# =========================================================================== #
def r2_score(W, delay=DELAY, rho=RHO, leakage=0.95, seed=20260918):
    rng = np.random.default_rng(seed)
    N = W.shape[0]
    if N < 4:
        return 0.0
    n_train = int(N * 4) + 40
    n_test = int(N * 2) + 20
    try:
        s_max = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return 0.0
    if s_max < 1e-12:
        return 0.0
    Wc = W / s_max * min(rho, 1.0)
    Win = rng.normal(0.0, 1.0, size=(N, 1))
    bias = rng.normal(0.0, 0.5, size=(N,))
    n_total = delay + 1 + n_train + n_test
    seq = (rng.random(size=n_total) > 0.5).astype(float) * 2 - 1
    S_tr, y_tr, S_te, y_te = [], [], [], []
    x = np.zeros(N)
    for t in range(delay + 1, n_total):
        x = leakage * np.tanh(Wc @ x + Win[:, 0] * seq[t] + bias)
        y = seq[t - delay]
        k = t - (delay + 1)
        if k < n_train:
            S_tr.append(x); y_tr.append(y)
        else:
            S_te.append(x); y_te.append(y)
    if not S_te:
        return 0.0
    S_tr, y_tr = np.array(S_tr), np.array(y_tr)
    S_te, y_te = np.array(S_te), np.array(y_te)
    if len(np.unique(y_tr)) < 2:
        return 0.0
    Xtr = np.column_stack([S_tr, np.ones(len(S_tr))])
    Xte = np.column_stack([S_te, np.ones(len(S_te))])
    alpha = 1e-3
    beta = np.linalg.solve(Xtr.T @ Xtr + alpha * np.eye(Xtr.shape[1]), Xtr.T @ y_tr)
    mse = float(np.mean((Xte @ beta - y_te) ** 2))
    return max(0.0, min(1.0, 1.0 - mse / (float(np.var(y_tr)) + 1e-9)))


def r2_mean(W, n_seeds=N_SEEDS, base_seed=SEED):
    if W.shape[0] < 4:
        return 0.0
    return float(np.mean([r2_score(W, seed=base_seed + s) for s in range(n_seeds)]))


def measure_fault_isolation(W, n_seeds=5, n_random=5, seed=SEED):
    """Module shutdown vs random shutdown. Returns (fi_ratio, verdict).

    fi_ratio = median(module_shutdown_drop) / median(random_shutdown_drop)
      < 1.0 → H1 (module isolation, biological impossible)
      > 1.0 → H2 (biological-style coupling)
      ~ 1.0 → H3 (no structure)
    """
    N = W.shape[0]
    if N < 8:
        return None, "too_small"
    baseline = r2_score(W, seed=seed)
    if baseline < 1e-6:
        return None, "unstable"
    # Split into 3 equal "modules"
    n_mod = max(2, N // 3)
    drops_mod = []
    drops_rand = []
    rng = np.random.default_rng(seed)
    for s in range(n_seeds):
        # Module shutdown: zero out every n_mod-th node
        Wm = W.copy()
        idx_mod = np.arange(0, N, max(1, N // n_mod))
        idx_mod = idx_mod[idx_mod < N]
        Wm[idx_mod, :] = 0
        Wm[:, idx_mod] = 0
        drops_mod.append(baseline - r2_score(Wm, seed=seed + s))
        # Random shutdown: same count
        Wr = W.copy()
        idx_rand = rng.choice(N, size=len(idx_mod), replace=False)
        Wr[idx_rand, :] = 0
        Wr[:, idx_rand] = 0
        drops_rand.append(baseline - r2_score(Wr, seed=seed + s))
    med_mod = np.median(drops_mod)
    med_rand = np.median(drops_rand)
    if med_rand < 1e-6:
        fi = 0.0
    else:
        fi = med_mod / med_rand
    if fi < 0.8:
        verdict = "H1_isolation"
    elif fi > 1.2:
        verdict = "H2_coupling"
    else:
        verdict = "H3_random"
    return round(float(fi), 3), verdict


def structural_metrics(W):
    N = W.shape[0]
    nnz = int(np.count_nonzero(W))
    density = nnz / (N * N) if N > 0 else 0
    out_deg = np.sum(W != 0, axis=1)
    return {
        "nodes": N,
        "edges": nnz,
        "density": round(float(density), 4),
        "avg_out_degree": round(float(np.mean(out_deg)), 2),
        "max_out_degree": int(np.max(out_deg)),
        "spectral_radius": round(float(np.linalg.svd(W, compute_uv=False)[0]), 4),
    }


# =========================================================================== #
# 拓扑生成器
# =========================================================================== #
def build_unit_topology(composition, total_N=NODE_CAP, seed=SEED):
    """Compose from functional units → W matrix, scaled to total_N nodes."""
    from multi_unit_benchmark_experiment import build_composed_topology
    org = compose_from_units(
        composition["units"], composition["connections"], seed=seed)
    if not org.get("validation", {}).get("ok"):
        return None, org
    result = build_composed_topology(org, total_N=total_N, seed=seed)
    W = result[0] if isinstance(result, tuple) else result
    return W, org


def build_bio_topology(seed=SEED):
    """Bio motif via DEMO_INSECT → W matrix."""
    from functional_units import DEMO_INSECT
    return build_unit_topology(DEMO_INSECT, seed=seed)


def build_random_topology(n_nodes=NODE_CAP, density=0.05, seed=SEED):
    """Erdős–Rényi random graph → W matrix."""
    rng = np.random.default_rng(seed)
    W = np.zeros((n_nodes, n_nodes))
    for i in range(n_nodes):
        for j in range(n_nodes):
            if i != j and rng.random() < density:
                W[i, j] = rng.uniform(0.1, 1.0)
    return W, {"organism": {"nodes": [], "edges": []}}


# =========================================================================== #
# Unit compositions
# =========================================================================== #
def get_unit_compositions():
    """Return 4 representative unit compositions.

    Uses the 4 pre-defined DEMO compositions from functional_units.py as the
    UNIT arm. These are hand-designed cross-unit circuits with 3-9 units each.
    """
    from functional_units import DEMO, DEMO_INSECT, DEMO_ESCAPE, DEMO_SWIM
    return [
        {"name": "DEMO_visual_to_action", **DEMO},
        {"name": "DEMO_insect_olfactory", **DEMO_INSECT},
        {"name": "DEMO_electrosensory_escape", **DEMO_ESCAPE},
        {"name": "DEMO_swim_rhythm_chain", **DEMO_SWIM},
    ]


# =========================================================================== #
# 统计检验
# =========================================================================== #
def welch_cohens_d(a, b):
    """Welch's t-test + Cohen's d. Returns (t, p, d)."""
    from scipy import stats
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    if len(a) < 3 or len(b) < 3:
        return 0.0, 1.0, 0.0
    t, p = stats.ttest_ind(a, b, equal_var=False)
    na, nb = len(a), len(b)
    pooled_std = np.sqrt(((na - 1) * np.var(a) + (nb - 1) * np.var(b)) / (na + nb - 2))
    if pooled_std < 1e-12:
        return 0.0, 1.0, 0.0
    d = (np.mean(a) - np.mean(b)) / pooled_std
    return float(t), float(p), float(d)


# =========================================================================== #
# Main
# =========================================================================== #
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="n_seeds=5")
    parser.add_argument("--n-seeds", type=int, default=N_SEEDS)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    n_seeds = 5 if args.quick else args.n_seeds
    print(f"=== Unit Engine Feedback Experiment (n_seeds={n_seeds}) ===")
    print(f"Nodes: {NODE_CAP}, Delay: {DELAY}, Rho: {RHO}")
    print()

    compositions = get_unit_compositions()
    results = []

    for comp in compositions:
        cname = comp["name"]
        print(f"\n--- {cname} ---")

        # Arm A: Unit composition
        t0 = time.time()
        W_unit, org_unit = build_unit_topology(comp, seed=SEED)
        if W_unit is None:
            errs = org_unit.get("validation", {}).get("errors", ["unknown"])
            print(f"  [FAIL] unit composition failed: {errs[:3]}")
            print(f"    units: {[u['unit'] for u in comp['units']]}")
            print(f"    conns: {comp['connections'][:2]}")
            continue
        r2_unit = r2_mean(W_unit, n_seeds=n_seeds)
        fi_unit, verdict_unit = measure_fault_isolation(W_unit, n_seeds=min(n_seeds, 10))
        sm_unit = structural_metrics(W_unit)
        dt_unit = time.time() - t0
        print(f"  UNIT:   r2={r2_unit:.4f}  FI={fi_unit}  verdict={verdict_unit}  "
              f"nodes={sm_unit['nodes']}  edges={sm_unit['edges']}  ({dt_unit:.1f}s)")

        # Arm B: Bio motif
        t0 = time.time()
        W_bio, org_bio = build_bio_topology(seed=SEED)
        if W_bio is None:
            print(f"  [SKIP] bio topology unavailable")
            r2_bio = fi_bio = None
            verdict_bio = sm_bio = None
            dt_bio = 0
        else:
            r2_bio = r2_mean(W_bio, n_seeds=n_seeds)
            fi_bio, verdict_bio = measure_fault_isolation(W_bio, n_seeds=min(n_seeds, 10))
            sm_bio = structural_metrics(W_bio)
            dt_bio = time.time() - t0
            print(f"  BIO:    r2={r2_bio:.4f}  FI={fi_bio}  verdict={verdict_bio}  "
                  f"nodes={sm_bio['nodes']}  edges={sm_bio['edges']}  ({dt_bio:.1f}s)")

        # Arm C: Random
        t0 = time.time()
        n_rand = sm_unit["nodes"] if sm_unit else NODE_CAP
        W_rand, _ = build_random_topology(n_nodes=n_rand, seed=SEED)
        r2_rand = r2_mean(W_rand, n_seeds=n_seeds)
        fi_rand, verdict_rand = measure_fault_isolation(W_rand, n_seeds=min(n_seeds, 10))
        sm_rand = structural_metrics(W_rand)
        dt_rand = time.time() - t0
        print(f"  RANDOM: r2={r2_rand:.4f}  FI={fi_rand}  verdict={verdict_rand}  "
              f"nodes={sm_rand['nodes']}  edges={sm_rand['edges']}  ({dt_rand:.1f}s)")

        results.append({
            "composition": cname,
            "unit": {"r2": r2_unit, "fi": fi_unit, "verdict": verdict_unit, "structural": sm_unit},
            "bio": {"r2": r2_bio, "fi": fi_bio, "verdict": verdict_bio, "structural": sm_bio},
            "random": {"r2": r2_rand, "fi": fi_rand, "verdict": verdict_rand, "structural": sm_rand},
        })

    # --- Statistical comparisons ---
    print("\n\n=== Statistical Comparisons (Bonferroni α=0.0083) ===")
    comparisons = []
    for r in results:
        cname = r["composition"]
        for metric in ["r2", "fi"]:
            for arm_pair, label in [("unit", "bio"), ("unit", "random"), ("bio", "random")]:
                a = r[arm_pair].get(metric)
                b = r[label].get(metric)
                if a is not None and b is not None:
                    t, p, d = welch_cohens_d([a], [b])
                    sig = "✓" if p < 0.0083 else " "
                    print(f"  {sig} {cname:25s} {metric:3s} {arm_pair:6s} vs {label:6s}: "
                          f"a={a:.4f} b={b:.4f} d={d:+.3f} p={p:.4f}")
                    comparisons.append({
                        "composition": cname, "metric": metric,
                        "arm_a": arm_pair, "arm_b": label,
                        "mean_a": a, "mean_b": b,
                        "cohens_d": round(d, 3), "p_value": round(p, 4),
                        "significant": p < 0.0083,
                    })

    # --- Summary ---
    print("\n\n=== Summary ===")
    n_unit = sum(1 for r in results if r["unit"]["r2"] is not None)
    n_sig = sum(1 for c in comparisons if c["significant"])
    n_pos = sum(1 for c in comparisons if c["significant"] and c["cohens_d"] > 0)
    n_neg = sum(1 for c in comparisons if c["significant"] and c["cohens_d"] < 0)
    print(f"Compositions tested: {n_unit}")
    print(f"Significant comparisons: {n_sig}/{len(comparisons)}")
    print(f"  Positive (UNIT better): {n_pos}")
    print(f"  Negative (UNIT worse):  {n_neg}")

    # Save results
    if args.out:
        out_path = Path(args.out)
    else:
        out_dir = HERE.parent.parent / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "UNIT_ENGINE_FEEDBACK_REPORT.json"

    output = {
        "experiment": "unit_engine_feedback",
        "version": "2.23.0",
        "date": "2026-09-29",
        "parameters": {"n_seeds": n_seeds, "nodes": NODE_CAP, "delay": DELAY, "rho": RHO},
        "compositions": results,
        "comparisons": comparisons,
        "summary": {
            "n_compositions": n_unit,
            "n_comparisons": len(comparisons),
            "n_significant": n_sig,
            "n_positive": n_pos,
            "n_negative": n_neg,
            "bonferroni_alpha": 0.0083,
        },
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
