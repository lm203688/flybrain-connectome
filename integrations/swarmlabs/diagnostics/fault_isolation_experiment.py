"""模块故障隔离实验 —— 检验合成模块化拓扑能否做到生物学至今未证实的模块隔离。

背景
  神经科学的核心悬案之一：大脑是否真的是模块化的？(Friston 2008, "A taxonomy of
  brain research") 经典观点认为模块（如视觉皮层 V1/V2/V4）在解剖上存在，但功能上
  通过广泛串扰耦合，因此一个模块的损伤往往级联到全脑（临床中风损伤学研究）。
  合成拓扑的模块是通过明确定义的边连接关系构造的，理论上可以做到"物理上隔离"。

判定假设
  H1（模块化成立）：关停一个完整模块后的性能降幅 **显著小于** 随机关停等量节点
                    —— 其他模块内部动力学完好，跨模块路由边数量少不足以级联。
  H2（生物式耦合）：关停一个完整模块后的性能降幅 **大于** 随机关停等量节点
                    —— 该模块承载了核心功能，其他模块依赖它的路由/信息。
  H3（无结构）    ：两者相近 —— 该拓扑本质上是随机图，"模块"只是命名。

对照设计
  对每个拓扑：
    1) 基线 R²(d=5) 种子平均
    2) 对每个模块 m：关停 m 的全部节点（出边置零），测 R² 与相对降幅
    3) 对每个模块 m：随机关停 m.size 个节点（同样数目的随机破坏），测 R² 与相对降幅
    4) 若"模块关停降幅中位数 < 随机关停降幅中位数" → H1 成立（生物学做不到）
    5) 若"模块关停降幅中位数 > 随机关停降幅中位数" → H2 成立（生物学式）
    6) 若相近 → H3

同时报告谱半径变化：关停模块后 ρ 的变化 —— 生物学网络在关停后往往进入不稳定区。

用法
  python fault_isolation_experiment.py             # 全量
  python fault_isolation_experiment.py --quick     # 只跑决定性比较
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
ORG_DIR = MCP / "generated_organisms" / "swarmlabs"

NODE_CAP = 49
DELAY = 5
RHO = 1.0
N_SEEDS = 30
N_RANDOM = 15          # 随机关停的对照抽样数
DENSIFY_FRAC = 0.75    # 补边到模块内可达密度的 75%
SEED = 7


# --------------------------------------------------------------------------- #
# ESN 评估器（与 cell_densify_experiment.py / dyn_calibration_probe.py 一致）
# --------------------------------------------------------------------------- #
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


def avg(W, delay=DELAY, n_seeds=N_SEEDS):
    return float(np.mean([r2_score(W, delay, seed=s) for s in range(n_seeds)]))


def spectral_radius(W):
    try:
        return float(np.linalg.svd(W, compute_uv=False)[0])
    except np.linalg.LinAlgError:
        return 0.0


# --------------------------------------------------------------------------- #
# 拓扑构造（复用 cell_densify_experiment.py 的接口，直接 import）
# --------------------------------------------------------------------------- #
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "cdens", HERE / "cell_densify_experiment.py")
_cd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cd)

load_org = _cd.load_org
pick_nodes = _cd.pick_nodes
node_meta = _cd.node_meta
max_intra_density = _cd.max_intra_density
motif_layer = _cd.motif_layer
fill = _cd.fill
_blank_pairs = _cd._blank_pairs

TARGETS = [
    # bench 系列（4 个有实质结构的）
    "bench_attention_gate.swarm.json",
    "bench_attention_working_combo.swarm.json",
    "bench_working_memory_buffer.swarm.json",
    "bench_sequential.swarm.json",
    # bp_* 蓝图（5 单 + 3 组合 = 8）
    "bp_broad_explore.swarm.json",
    "bp_competitive.swarm.json",
    "bp_competitive_selection.swarm.json",
    "bp_deep_reasoning.swarm.json",
    "bp_fast_reflex.swarm.json",
    "bp_hierarchical.swarm.json",
    "bp_lateral_inhibition.swarm.json",
    "bp_orchestrated.swarm.json",
    "bp_predictive_coding.swarm.json",
    "bp_hierarchical__predictive_coding.swarm.json",
    "bp_deep_reasoning__competitive_selection.swarm.json",
    "bp_lateral_inhibition__competitive_selection.swarm.json",
    # sample_* 4
    "sample_10module.swarm.json",
    "sample_organism.swarm.json",
    "sample_phase2_habit_meta.swarm.json",
    "sample_phase2_nested.swarm.json",
    "sample_phase2_rl.swarm.json",
    # evolved 3 + special 2
    "evolved_phase3_locked_broad_explore__habit_consolidation__hierarchical__attention_gate.swarm.json",
    "evolved_phase3_free_working_memory_buffer__competitive_selection__hierarchical_deep.swarm.json",
    "evolved_target200.swarm.json",
    "evolved_target40.swarm.json",
    "memory_dominant.swarm.json",
    "specialized_cycled.swarm.json",
]
TARGETS = [f for f in TARGETS if (ORG_DIR / f).exists()]


def short(lab):
    return (lab.replace("evolved_phase3_locked_", "ga_locked_")
               .replace("evolved_phase3_free_", "ga_free_")
               .replace("bench_attention_working_combo", "bench_attn_wm_combo")
               .replace("sample_phase2_nested", "phase2_nested"))


def load_all():
    out = []
    for f in TARGETS:
        agents, edges, label = load_org(ORG_DIR / f)
        nodes, sizes = pick_nodes(agents)
        if len(nodes) < 10 or len(sizes) < 2:
            continue
        out.append({"file": f, "label": label, "nodes": nodes, "edges": edges,
                    "sizes": sizes, "n": len(nodes), "n_mod": len(sizes)})
    return out


def densify_full(nodes, edges, frac=DENSIFY_FRAC, seed=SEED):
    """给 cell 层补模块内随机边，直到达到 intra density cap 的 frac。"""
    W, _K, _added, _dmax = _cd.densify(nodes, edges, frac, "intra_random", seed=seed)
    mods, reps, _sizes = node_meta(nodes)
    return W, mods, reps


def disable_module(W, mods, reps, m):
    """关停模块 m：把该模块内所有节点（含 rep）的出边置零。
    保留入边（其他模块仍"看到"它的存在，但无法从它获得输出）。"""
    Wd = W.copy()
    mask = (mods == m)  # 模块 m 的节点索引
    Wd[mask, :] = 0.0
    return Wd, int(mask.sum())


def disable_random(W, n_cells, seed):
    """随机关停 n_cells 个节点（等量对照）。"""
    Wd = W.copy()
    rng = np.random.default_rng(seed)
    idx = rng.choice(W.shape[0], size=n_cells, replace=False)
    Wd[idx, :] = 0.0
    return Wd


def _hdr(title, note=""):
    print("\n" + "=" * 108)
    print(title)
    if note:
        print("  " + note)
    print("=" * 108)


# --------------------------------------------------------------------------- #
def probe_main(ts, quick=False):
    """决定性比较：模块关停 vs 随机关停。"""
    _hdr("F1. 模块级故障隔离 —— 决定性比较",
         "关停完整模块 vs 随机关停等量节点（同 N_SEEDS=30 种子平均）")
    print("  判据：模块关停降幅 < 随机关停降幅 → 拓扑具备模块化隔离能力（生物学至今未证实）")
    print("        模块关停降幅 > 随机关停降幅 → 生物学式耦合")
    print("        两者相近                   → 无结构（随机图）")
    print("  " + "-" * 106)

    header = ("  %-24s %3s %3s %6s | %14s | %14s | %s" %
              ("拓扑", "k", "N", "d", "模块关停降幅", "随机关停降幅", "判定"))
    print(header)
    print("  " + "-" * 106)

    rows = []
    h1_wins, h2_wins, h3_wins = 0, 0, 0
    for t in ts:
        W, mods, reps = densify_full(t["nodes"], t["edges"])
        n = W.shape[0]
        d = (np.abs(W) > 1e-12).sum() / (n * n)
        rho0 = spectral_radius(W)

        # 基线（种子平均）
        r2_base = avg(W)
        if r2_base < 1e-3:
            # 基线太弱，跳过（无判别力）
            print("  %-24s %3d %3d %6.3f | 跳过（基线 R²=%.4f 过弱）" %
                  (short(t["label"])[:24], t["n_mod"], n, d, r2_base))
            continue

        # 每个模块的关停降幅
        mod_drops = []
        for m in sorted(set(mods.tolist())):
            Wd, k_removed = disable_module(W, mods, reps, m)
            r2_after = avg(Wd)
            drop = max(0.0, (r2_base - r2_after) / r2_base)
            mod_drops.append((m, k_removed, r2_after, drop))

        # 随机关停对照（取每模块大小中位数为关停量）
        med_size = int(np.median([d[1] for d in mod_drops]))
        rand_drops = []
        for i in range(N_RANDOM):
            Wd = disable_random(W, med_size, seed=1000 + i)
            r2_after = avg(Wd)
            drop = max(0.0, (r2_base - r2_after) / r2_base)
            rand_drops.append(drop)

        # 谱半径变化
        rho_after_mod = spectral_radius(disable_module(W, mods, reps,
                                                       mod_drops[0][0])[0])
        rho_after_rand = spectral_radius(disable_random(W, med_size, seed=2000))

        # 汇总
        mod_median = float(np.median([d[3] for d in mod_drops]))
        rand_median = float(np.median(rand_drops))
        mod_std = float(np.std([d[3] for d in mod_drops]))

        # 判定
        diff = mod_median - rand_median
        if diff < -0.05:
            verdict = "H1 模块化"
            h1_wins += 1
        elif diff > 0.05:
            verdict = "H2 耦合"
            h2_wins += 1
        else:
            verdict = "H3 无结构"
            h3_wins += 1

        rows.append({
            "label": t["label"], "n": n, "n_mod": t["n_mod"], "density": d,
            "rho0": rho0, "rho_mod": rho_after_mod, "rho_rand": rho_after_rand,
            "r2_base": r2_base, "med_size": med_size,
            "mod_median_drop": mod_median, "mod_std": mod_std,
            "rand_median_drop": rand_median,
            "diff": diff, "verdict": verdict,
        })
        print("  %-24s %3d %3d %6.3f | %14.4f | %14.4f | %s" %
              (short(t["label"])[:24], t["n_mod"], n, d,
               mod_median, rand_median, verdict))

    print("  " + "-" * 106)
    print("  汇总：H1 模块化 %d / H2 耦合 %d / H3 无结构 %d  → %s" %
          (h1_wins, h2_wins, h3_wins,
           "具备模块隔离能力" if h1_wins > h2_wins else
           ("生物学式耦合" if h2_wins > h1_wins else "结果混合")))

    # 详细表：每个拓扑的模块级降幅 vs 随机降幅
    _hdr("F2. 逐模块降幅（相对基线 R² 的百分比）")
    print("  每行 = 关停一个模块；对照 = 随机关停同样数目的节点")
    print("  " + "-" * 106)
    print("  %-24s %4s %4s %6s | %10s | %10s | %s" %
          ("拓扑", "N", "k", "d", "模块降幅", "随机降幅", "判定"))
    print("  " + "-" * 106)
    for r in rows:
        print("  %-24s %4d %4d %6.3f | %9.1f%% | %9.1f%% | %s" %
              (short(r["label"])[:24], r["n"], r["n_mod"], r["density"],
               r["mod_median_drop"] * 100, r["rand_median_drop"] * 100,
               r["verdict"]))

    # 谱稳定性
    _hdr("F3. 谱半径变化 —— 关停后是否仍稳定（ρ < 1 为稳定）")
    print("  生物学网络在区域损伤后容易进入不稳定区（癫痫态/混沌态）；")
    print("  合成模块化拓扑的 ρ 应该变化更小（模块内动力学独立）。")
    print("  " + "-" * 106)
    print("  %-24s | %8s | %10s | %10s | %s" %
          ("拓扑", "ρ_基线", "ρ_模块关停", "ρ_随机关停", "谱稳定性保持"))
    print("  " + "-" * 106)
    for r in rows:
        # 关停后 ρ 与基线 ρ 的比值
        dr_mod = r["rho_mod"] / (r["rho0"] + 1e-9) - 1
        dr_rand = r["rho_rand"] / (r["rho0"] + 1e-9) - 1
        stability = "保持" if abs(dr_mod) < abs(dr_rand) else "更差"
        print("  %-24s | %8.4f | %9.4f (%+.2f%%) | %9.4f (%+.2f%%) | %s" %
              (short(r["label"])[:24], r["rho0"], r["rho_mod"], dr_mod * 100,
               r["rho_rand"], dr_rand * 100, stability))
    return rows


def probe_critical_nodes(ts):
    """敏感性测试：关停单个节点时性能降幅的分布。
    若拓扑"分散"（无核心节点），单节点关停的降幅应该方差小、无异常值。
    若拓扑"集中"（有 hub），单节点关停的降幅会呈重尾分布。"""
    _hdr("F4. 单节点关停敏感性 —— 是否有不可替代的 hub 节点")
    print("  生物学网络有 hub 节点（如 APL body 10540 fan-out 102,263），"
          "关停这些节点会大伤；")
    print("  合成模块化拓扑理论上应该没有不可替代的节点（每个模块内部对称）。")
    print("  " + "-" * 106)
    print("  %-24s %3s %6s | %10s %10s %10s %10s | %s" %
          ("拓扑", "N", "d", "降幅均值", "降幅 std", "降幅 max", "降幅 min",
           "分布形状"))
    print("  " + "-" * 106)

    for t in ts:
        W, mods, reps = densify_full(t["nodes"], t["edges"])
        n = W.shape[0]
        d = (np.abs(W) > 1e-12).sum() / (n * n)
        r2_base = avg(W)
        if r2_base < 1e-3:
            print("  %-24s 跳过（基线弱）" % short(t["label"])[:24])
            continue

        drops = []
        for i in range(n):
            Wd = W.copy()
            Wd[i, :] = 0.0
            r2_after = avg(Wd)
            drops.append(max(0.0, (r2_base - r2_after) / r2_base))
        drops = np.array(drops)
        mean_d, std_d, max_d, min_d = (float(drops.mean()), float(drops.std()),
                                       float(drops.max()), float(drops.min()))
        shape = "平坦" if std_d < 0.10 else ("重尾" if max_d > mean_d * 3 else "集中")
        print("  %-24s %3d %6.3f | %9.3f%% %9.3f%% %9.3f%% %9.3f%% | %s" %
              (short(t["label"])[:24], n, d,
               mean_d * 100, std_d * 100, max_d * 100, min_d * 100, shape))


def probe_biological_baseline(ts):
    """对照：全连接随机图（Erdős-Rényi）作为"无结构"基线。"""
    _hdr("F5. 无结构基线 —— 全连接随机图的关停行为")
    print("  目的：作为『完全没有模块化』的对照。随机图的关停降幅应介于模块/随机之间。")
    print("  " + "-" * 106)
    print("  %-24s %4s %6s | %10s | %10s" %
          ("对照", "N", "d", "模块降幅", "随机降幅"))
    print("  " + "-" * 106)
    for t in ts:
        # 用 rand_matched 生成同 N 同 K 的全局随机图
        W, mods, reps = densify_full(t["nodes"], t["edges"])
        n = W.shape[0]
        K = int((np.abs(W) > 1e-12).sum())
        # 完全随机：所有对都可选（不限制模块内）
        mods_flat = np.zeros(n, dtype=int)
        reps_flat = np.zeros(n, dtype=bool)
        W_rand = _cd.rand_matched(K, n, seed=31337, mods=mods_flat, reps=reps_flat,
                                  block=False)
        d = (np.abs(W_rand) > 1e-12).sum() / (n * n)
        r2_base = avg(W_rand)
        if r2_base < 1e-3:
            print("  %-24s 跳过（基线弱）" % short(t["label"])[:24])
            continue
        # 随机关停对照
        med_size = int(n / max(1, t["n_mod"]))  # 用相同关停量
        rand_drops = []
        for i in range(N_RANDOM):
            Wd = disable_random(W_rand, med_size, seed=1000 + i)
            r2_after = avg(Wd)
            rand_drops.append(max(0.0, (r2_base - r2_after) / r2_base))
        rand_median = float(np.median(rand_drops))
        print("  %-24s %4d %6.3f | %10s | %9.1f%%" %
              (short(t["label"])[:24] + "_随机", n, d, "—", rand_median * 100))


def _hdr(title, note=""):
    print("\n" + "=" * 108)
    print(title)
    if note:
        print("  " + note)
    print("=" * 108)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="只跑 F1 决定性比较")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 108)
    print("模块故障隔离实验 —— 合成模块化拓扑 vs 生物学（Friston 2008 争议）")
    print("=" * 108)
    print("  拓扑数：%d  种子平均：N=%d  随机对照：N=%d  密化比例：%.2f" %
          (len(TARGETS), N_SEEDS, N_RANDOM, DENSIFY_FRAC))
    print("  任务：Bernoulli 延迟线 delay=%d  谱半径 ρ=%.2f" % (DELAY, RHO))

    ts = load_all()
    if not ts:
        print("  ✗ 无候选拓扑，终止")
        return

    rows = probe_main(ts, quick=args.quick)

    if not args.quick:
        probe_critical_nodes(ts)
        probe_biological_baseline(ts)

    # 最终结论
    _hdr("结论")
    if rows:
        h1 = sum(1 for r in rows if r["verdict"].startswith("H1"))
        h2 = sum(1 for r in rows if r["verdict"].startswith("H2"))
        h3 = sum(1 for r in rows if r["verdict"].startswith("H3"))
        print("  F1 判定分布：H1 模块化 %d / H2 耦合 %d / H3 无结构 %d（共 %d 拓扑）"
              % (h1, h2, h3, len(rows)))
        if h1 > h2 and h1 > h3:
            print("  ★ 合成模块化拓扑**具备**模块级故障隔离能力。")
            print("    这是生物学至今未证实的能力（Friston 2008, modularity of brain）。")
            print("    定位新增主张：超越生物学 → 结构稳定性维度成立。")
        elif h2 > h1:
            print("  合成拓扑表现为**生物学式耦合**：模块关停伤害大于随机关停。")
            print("  「超越生物学」在模块隔离维度**不成立**；需要更多结构改进。")
        else:
            print("  结果混合：部分拓扑模块化，部分表现为耦合。")
            print("  下一步：分析 H1 与 H2 拓扑的模块结构差异（rep 边密度？cell 分布？）。")
        print("  方法学约束：使用 ESN + 线性读出器 + 单任务 delay=%d，" % DELAY)
        print("  无法涵盖生物学意识/无意识行为的多种读出方式（同 dyn_calibration 的局限）。")

    print("\n  耗时 %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
