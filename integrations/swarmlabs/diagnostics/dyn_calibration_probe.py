"""动态适应度诊断套件 —— Phase 3 复核用。

背景：Phase 3 初判 `dyn_score`「无判别力」，据此把 DYN_WEIGHT 归零并宣布项目降级。
用户质疑该判定，本套件做了三轮复核，结论完全推翻初判。

复核链条：
  A. 标定探针 —— 初判错在**任务标定**，不在仪器。
     原实现三个 bug：① delay=20–40 已过能力悬崖（全 0）；② 列归一化抹掉了
     谱半径 ρ（ESN 唯一关键动力学参数）；③ 80 样本回归 61 参数，读出器欠定过拟合。
     修正后：教科书储备池在 delay=5 时 R² 从 0.000 平滑升到 0.856（跨 ρ）→ 有真实动态范围。

  B. 稳健性探针 —— 单种子分数 std 高达 0.19–0.23，是在测输入序列运气。
     必须种子平均（≥20 seeds）才把拓扑效应和运气分离。

  C. 匹配控制实验（决定性）—— 隔离「结构」与「连通量」两个混淆变量。
     上一轮看似 motif 优势 +60~220%，其实是**随机补边量**造成的伪影
     （稀疏候选补的随机列更多 = 随机结构更多）。
     匹配非零元素总数 K 后：**0/7 拓扑显著优于随机**，差值 0.001~0.018，全在噪声内。

最终结论：生物 motif 在**模块代表层**（flybrain 实际产出的设计空间）
不产生可测量的计算优势；根因是该设计空间密度只有 0.002–0.023，
结构上不足以承载时间动力学。这是设计空间的局限，不是"计算力问题已关闭"——
cell 级密化的版本仍未检验，是真实的后续研究方向。

用法：
  python dyn_calibration_probe.py            # 全量（A+B+C）
  python dyn_calibration_probe.py --quick    # 只跑 C（决定性那轮）
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
ORG_DIR = MCP / "generated_organisms" / "swarmlabs"


# --------------------------------------------------------------------------- #
# 核心评估器：Bernoulli 延迟线（ESN 文献标准记忆基准）
# --------------------------------------------------------------------------- #
def r2_score(W, delay, rho, leakage=0.95, n_train=None, n_test=None,
             alpha=1e-3, seed=20260918):
    """预测 delay 步前的单个 ±1 比特。难度随 delay 平滑上升。

    与原 dyn_score 的关键差异：
      · 谱半径显式标定（SVD 归一 × ρ），而非列归一化
      · 训练样本数按 N 缩放（N*4+40），避免欠定过拟合
      · 任务为延迟线而非 XOR（XOR 难度是悬崖不是斜坡）
    """
    rng = np.random.default_rng(seed)
    N = W.shape[0]
    if N < 4:
        return 0.0
    n_train = int(N * 4) + 40 if n_train is None else n_train
    n_test = int(N * 2) + 20 if n_test is None else n_test

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
            S_tr.append(x)
            y_tr.append(y)
        else:
            S_te.append(x)
            y_te.append(y)

    S_tr, y_tr = np.array(S_tr), np.array(y_tr)
    S_te, y_te = np.array(S_te), np.array(y_te)
    if len(np.unique(y_tr)) < 2 or len(S_te) == 0:
        return 0.0
    Xtr = np.column_stack([S_tr, np.ones(len(S_tr))])
    Xte = np.column_stack([S_te, np.ones(len(S_te))])
    beta = np.linalg.solve(Xtr.T @ Xtr + alpha * np.eye(Xtr.shape[1]), Xtr.T @ y_tr)
    mse = float(np.mean((Xte @ beta - y_te) ** 2))
    return max(0.0, min(1.0, 1.0 - mse / (float(np.var(y_tr)) + 1e-9)))


def random_W(N, seed):
    return np.random.default_rng(seed).normal(0.0, 1.0, size=(N, N))


def load_org(path):
    import json
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    sw = cfg.get("swarm", {})
    agents = sw.get("agents") or []
    edges = sw.get("edges") or []
    org = {"organism": {"nodes": [{"id": a.get("id")} for a in agents], "edges": edges}}
    return org, len(agents), len(edges), cfg.get("name") or Path(path).name


def motif_only_W(org, N=48):
    """只取 motif 边，不补任何随机列（关键：消除补边伪影）。"""
    g = org.get("organism") or org
    nodes = g.get("nodes") or []
    idx = {n["id"]: i for i, n in enumerate(nodes)}
    n = min(N, len(nodes))
    W = np.zeros((n, n))
    for e in g.get("edges") or []:
        i, j = idx.get(e.get("from")), idx.get(e.get("to"))
        if i is not None and j is not None and i < n and j < n:
            W[i, j] += float(e.get("weight", 0.0))
    return W, int((np.abs(W) > 1e-12).sum())


def random_matched(K, n, seed):
    """恰好 K 个非零元素的随机权重矩阵（排除自环）。"""
    rng = np.random.default_rng(seed)
    W = np.zeros((n, n))
    if K <= 0:
        return W
    flat = np.arange(n * n)
    diag = flat % n != flat // n
    pool = np.where(diag)[0]
    k = min(K, len(pool))
    W.flat[rng.choice(pool, size=k, replace=False)] = rng.normal(0.4, 0.3, size=k)
    return W


def avg_score(W, delay, rho=1.0, n_seeds=30):
    """种子平均：压掉输入序列运气，只留拓扑效应。"""
    return float(np.mean([r2_score(W, delay, rho, seed=s) for s in range(n_seeds)]))


# --------------------------------------------------------------------------- #
def probe_A(N=60):
    """A. 标定探针：教科书储备池的 (ρ, delay) 网格 —— 找拐点区间。"""
    print("=" * 78)
    print("A. 教科书储备池 (随机 W, N=%d) —— 谱半径 ρ × 延迟 delay" % N)
    print("=" * 78)
    W = random_W(N, 7)
    rhos, delays = [0.5, 0.7, 0.8, 0.9, 0.95, 1.0, 1.2], [1, 3, 5, 8, 12, 20, 30]
    print("  rho\\delay " + "".join("%8d" % d for d in delays))
    grid = {}
    for rho in rhos:
        row = ["%8.2f" % rho]
        for d in delays:
            s = r2_score(W, d, rho, n_train=240, n_test=120, seed=7)
            grid[(rho, d)] = s
            row.append("%8.3f" % s)
        print("  ".join(row))
    sc = list(grid.values())
    print("\n  范围: min=%.3f max=%.3f 极差=%.3f  非零点: %d/%d"
          % (min(sc), max(sc), max(sc) - min(sc), sum(1 for v in sc if v > 0.01), len(sc)))
    knee = [s for (rho, d), s in grid.items() if 0.1 < s < 0.9]
    print("  拐点区间（0.1<R2<0.9）: %d 个点 → %s"
          % (len(knee), "存在真实动态范围" if knee else "不存在"))
    return grid


def probe_B(Wref, label, n_seeds=5):
    """B. 稳健性探针：单种子 vs 种子平均的方差对比。"""
    print("\n" + "=" * 78)
    print("B. 稳健性 —— 单种子分数 vs 种子平均")
    print("=" * 78)
    for d in (3, 4, 5):
        single = [r2_score(Wref, d, 1.0, seed=s, n_train=240, n_test=120)
                  for s in range(n_seeds)]
        print("  %-24s delay=%d  单种子: %s  std=%.4f  均值=%.4f"
              % (label[:24], d, "/".join("%.3f" % v for v in single),
                 float(np.std(single)), float(np.mean(single))))


def probe_C(n_seeds=30):
    """C. 匹配控制实验（决定性）：匹配非零数 K，隔离结构效应。"""
    print("\n" + "=" * 90)
    print("C. 匹配控制实验 —— motif 结构 vs 随机结构（同 N、同非零数 K、种子平均 %d）"
          % n_seeds)
    print("=" * 90)
    print("%-34s %4s %5s | %6s %6s %6s | %6s %6s %6s | %s" %
          ("拓扑", "N", "K", "m d=4", "m d=5", "m d=6",
           "r d=4", "r d=5", "r d=6", "motif 优势(d=5)"))
    print("-" * 90)
    files = [
        ORG_DIR / "sample_10module.swarm.json",
        ORG_DIR / "sample_phase2_nested.swarm.json",
        ORG_DIR / "bp_predictive_coding.swarm.json",
        ORG_DIR / "bp_hierarchical.swarm.json",
        ORG_DIR / "bench_attention_working_combo.swarm.json",
        ORG_DIR / "evolved_phase3_locked_broad_explore__habit_consolidation__hierarchical__attention_gate.swarm.json",
        ORG_DIR / "evolved_phase3_free_working_memory_buffer__competitive_selection__hierarchical_deep.swarm.json",
    ]
    files = [f for f in files if f.exists()]
    wins = 0
    for f in files:
        org, n_agents, n_edges, label = load_org(f)
        W, K = motif_only_W(org, N=min(48, n_agents))
        n = W.shape[0]
        if K == 0:
            continue
        ms = [avg_score(W, d, n_seeds=n_seeds) for d in (4, 5, 6)]
        rs = []
        for d in (4, 5, 6):
            rs.append(float(np.median([
                avg_score(random_matched(K, n, seed=1000 + i), d, n_seeds=n_seeds)
                for i in range(5)])))
        adv = ms[1] - rs[1]
        if adv > 0.02:
            wins += 1
        print("%-34s %4d %5d | %6.3f %6.3f %6.3f | %6.3f %6.3f %6.3f | %+.3f %s"
              % (label[:34], n, K, *ms, *rs, adv, "✓" if adv > 0.02 else ""))
    print("-" * 90)
    print("motif 结构显著优于随机匹配（>0.02）: %d / %d" % (wins, len(files)))
    print("结论: %s" % ("存在 motif 结构计算优势" if wins else
                       "生物 motif 在该设计空间无可测量的计算优势"))
    return wins, len(files)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="只跑决定性实验 C")
    ap.add_argument("--n-seeds", type=int, default=30)
    args = ap.parse_args()

    t0 = time.time()
    if args.quick:
        probe_C(n_seeds=args.n_seeds)
    else:
        probe_A()
        org, _, _, lab = load_org(ORG_DIR / "sample_10module.swarm.json")
        W, K = motif_only_W(org, N=48)
        probe_B(W, lab)
        probe_C(n_seeds=args.n_seeds)
    print("\n耗时 %.1fs" % (time.time() - t0))
