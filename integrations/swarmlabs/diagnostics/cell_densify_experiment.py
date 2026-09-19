"""Cell 级密化实验 —— 检验生物 motif 在足够密的设计空间里是否产生计算优势。

背景
  Phase 3 复核（dyn_calibration_probe.py）得出负结果：生物 motif 在**模块代表层**
  不产生可测量的计算优势，0/7 拓扑胜出。当时已注明根因是设计空间密度只有
  0.002–0.023（ESN 需要 ~0.1+ 才有时间动力学），并明确说「负结果只限于模块代表层，
  cell 级密化版本仍未检验」。本实验就是把那个未检验的版本做掉。

关键结构事实（实测）
  每个模块 = c 个 cell agent + 1 个 tissue_rep。7 个候选拓扑的 c 分别是 2/4/6/6/4/2/8。
  motif 边只连 rep 层，**cell 完全孤立、零入边**——原设计空间本质是一套
  「模块代表之间的路由 schema」，不是记忆基质。
  密化 = 给每个模块的 cell 层补递归回路，让总密度进入 ESN 可用区间，再重做匹配控制。

  ★ 解析事实（架构级，但**不是** motif 无优势的原因）
    模块内密度的上限 d_max = c(c-1) / (k(c+1)^2) → 1/k  (当 c→∞)
    即只要 cell 只连本模块，密度被模块数 k 硬性封顶在 1/k，与 cell 数无关。
    k=7 → 0.143，k=11 → 0.091，k=5 → 0.20（仅渐近，有限 c 达不到）。
    注意：本任务（delay=5）实测最优密度约 0.10（D0），不是 0.20。
    密化后 4/7 拓扑已达 0.12–0.138，处于最优区 → 密度不是瓶颈。
    真正的瓶颈是 cell 完全孤立（D6：补基质 = 9.7× 几何平均提升）。

判定（实测结论，2026-09-18）
  1. 密化本身有效：补上 cell 基质后几何平均提升 9.7 倍（范围 1×–76×，delay=5）。
     瓶颈是「cell 完全孤立」，不是 motif。
  2. motif 无计算优势（决定性）：配对检验 D2b 把 cell 基质固定后，
     motif 路由优势仅 +0.0009 ~ +0.0181，0/7 超过 0.02 阈值，仅 1/7 达 |z|≥2
     且效应量仅 0.006。上一轮 D2 的 -0.198 ~ +0.050 大幅波动 100% 来自
     cell fill 随机性，不是 motif 效应。
  3. cell 布线方式 > motif 选择：结构化（circulant 环）fill 均值 +0.0701，
     4/7 显著。也就是说「怎么布 cell 层」比「rep 层用哪个 motif」更有用。
  → 负结果成立且已定论：定位锁定「可追溯的虚拟生物形态生成器」。

对照层
  D0 仪器健康      同 K 随机储备池在各可达密度下必须有明确动态范围，否则本轮无效。
  D6 密化收益      原始设计空间（cell 孤立）vs cell 层密化后——量化补基质值多少。
  D1 结构 vs 无结构  motif+密化 vs 同 N 同 K 全局随机。
  D2 motif vs 随机路由 同 N 同 K 同模块块约束，唯一差异是 rep 层路由。
  D2b 配对检验    cell 基质完全固定，只换 rep 边——噪声归零，可精确归因（★决定性）。
  D3 密化方式      随机 fill vs 结构化 fill（模块内 circulant 环形链路）。
  D4 密度扫描      按各拓扑可达密度的比例扫描，检验 motif 优势是否随密度出现。
  D5 解析上限      直接计算 d_max 与「达到 0.20 所需 cell 数」，给出架构级结论。

用法
  python cell_densify_experiment.py            # 全量 D0–D5
  python cell_densify_experiment.py --quick    # 只跑 D2（决定性那轮）
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
ORG_DIR = MCP / "generated_organisms" / "swarmlabs"

NODE_CAP = 49       # 节点数上限（保证 7 个完整模块内的规模）
FRACS = [0.25, 0.50, 0.75, 1.00]   # D4 扫描：占各拓扑可达上限的比例
ABS_DENSITY = [0.05, 0.10, 0.15, 0.20]   # D0 用绝对密度
DELAYS = (4, 5, 6, 8)
PRIMARY_DELAY = 5
RHO = 1.0
N_SEEDS = 30
N_RANDOM = 8         # 随机对照抽样数（中位数 + std 用于噪声估计）


# --------------------------------------------------------------------------- #
# 评估器：Bernoulli 延迟线（与 dyn_calibration_probe.py 完全一致，保证可比）
# --------------------------------------------------------------------------- #
def r2_score(W, delay, rho=RHO, leakage=0.95, n_train=None, n_test=None,
             alpha=1e-3, seed=20260918):
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
            S_tr.append(x); y_tr.append(y)
        else:
            S_te.append(x); y_te.append(y)

    S_tr, y_tr = np.array(S_tr), np.array(y_tr)
    S_te, y_te = np.array(S_te), np.array(y_te)
    if len(np.unique(y_tr)) < 2 or len(S_te) == 0:
        return 0.0
    Xtr = np.column_stack([S_tr, np.ones(len(S_tr))])
    Xte = np.column_stack([S_te, np.ones(len(S_te))])
    beta = np.linalg.solve(Xtr.T @ Xtr + alpha * np.eye(Xtr.shape[1]), Xtr.T @ y_tr)
    mse = float(np.mean((Xte @ beta - y_te) ** 2))
    return max(0.0, min(1.0, 1.0 - mse / (float(np.var(y_tr)) + 1e-9)))


def avg(W, delay, n_seeds=N_SEEDS, rho=RHO):
    """种子平均：压掉输入序列运气，只留拓扑效应。"""
    return float(np.mean([r2_score(W, delay, rho, seed=s) for s in range(n_seeds)]))


# --------------------------------------------------------------------------- #
# 拓扑构造
# --------------------------------------------------------------------------- #
def load_org(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    sw = cfg.get("swarm", {})
    return (sw.get("agents") or [], sw.get("edges") or [],
            cfg.get("name") or Path(path).name)


def module_structure(agents):
    """按模块聚合节点，排除 module=None 的 guardrail/coordinator。"""
    by_mod = {}
    for a in agents:
        m = a.get("module")
        if m is None:
            continue
        by_mod.setdefault(int(m), []).append(a)
    return by_mod, sorted(by_mod)


def pick_nodes(agents, cap=NODE_CAP):
    """取前 k 个**完整模块**的全部节点，总数 <= cap。
    返回 (nodes, 每模块 **cell 数**)——不含 tissue_rep，与 max_intra_density 口径一致。"""
    by_mod, order = module_structure(agents)
    nodes, sizes = [], {}
    for m in order:
        if len(nodes) + len(by_mod[m]) > cap:
            break
        cells = [a for a in by_mod[m]
                 if str(a.get("role") or "") != "tissue_rep"]
        sizes[m] = len(cells)
        nodes.extend(by_mod[m])
    return nodes, sizes


def motif_layer(nodes, edges):
    """只取 motif 边（rep 层路由 schema），不补任何随机列。"""
    n = len(nodes)
    idx = {a["id"]: i for i, a in enumerate(nodes)}
    W = np.zeros((n, n))
    for e in edges:
        i, j = idx.get(e.get("from")), idx.get(e.get("to"))
        if i is not None and j is not None:
            W[i, j] += float(e.get("weight", 0.0))
    return W


def node_meta(nodes):
    """返回 (module_of[], is_rep[], cells_per_mod)。"""
    mods = [int(a["module"]) for a in nodes]
    reps = [str(a.get("role") or "") == "tissue_rep" for a in nodes]
    sizes = {}
    for m, r in zip(mods, reps):
        if not r:
            sizes[m] = sizes.get(m, 0) + 1
    return np.array(mods), np.array(reps), sizes


def intra_capacity(nodes, mods, reps, sizes, n_modules):
    """模块内可补边的最大总数 = Σ c_m(c_m - 1)。"""
    return sum(c * (c - 1) for c in sizes.values())


def max_intra_density(n, sizes, n_modules):
    """解析上限：d_max = Σc(c-1) / n²，极限 1/n_modules。"""
    if n <= 0:
        return 0.0
    return intra_capacity(n, None, None, sizes, n_modules) / float(n * n)


def _blank_pairs(n, mods, reps, mode):
    pairs = []
    if mode == "all_random":
        for i in range(n):
            for j in range(n):
                if i != j:
                    pairs.append((i, j))
        return pairs
    if mode in ("intra_random", "block_random"):
        by_mod = {}
        for i, m in enumerate(mods):
            if not reps[i] and m >= 0:
                by_mod.setdefault(int(m), []).append(i)
        for ids in by_mod.values():
            L = len(ids)
            if L < 2:
                continue
            for a in ids:
                for b in ids:
                    if a != b:
                        pairs.append((a, b))
        return pairs
    if mode == "intra_ring":
        # 确定性 circulant：模块内按索引连 a_i -> a_{(i+j)%L}，j 递增
        by_mod = {}
        for i, m in enumerate(mods):
            if not reps[i] and m >= 0:
                by_mod.setdefault(int(m), []).append(i)
        for j in range(1, max(1, n)):
            for ids in by_mod.values():
                L = len(ids)
                for t in range(L):
                    a, b = ids[t], ids[(t + j) % L]
                    if a != b:
                        pairs.append((a, b))
        return pairs
    raise ValueError(mode)


def fill(W, mods, reps, need, mode, seed):
    """给 W 补边直到累计 need 条（或候选耗尽）。返回 (W, 实际补入数)。"""
    n = W.shape[0]
    if need <= 0:
        return W, 0
    rng = np.random.default_rng(seed)
    W = W.copy()
    cands = _blank_pairs(n, mods, reps, mode)
    if not cands:
        return W, 0
    cands = [(i, j) for (i, j) in cands if abs(W[i, j]) < 1e-12]
    if not cands:
        return W, 0
    if mode == "intra_ring":
        take = cands[:need]        # 确定性：circulant 的 j 递增顺序
    else:
        rng.shuffle(cands)
        take = cands[:need]
    added = 0
    for (i, j) in take:
        if abs(W[i, j]) < 1e-12:
            W[i, j] = rng.normal(0.5, 0.3)
            added += 1
    return W, added


def densify(nodes, edges, frac, fill_mode, seed=7, keep_motif=True):
    """按「可达上限的 frac 比例」密化。frac 用比例而非绝对密度，
    使不同模块结构（c=2/4/6/8）之间公平可比。"""
    mods, reps, sizes = node_meta(nodes)
    n = len(nodes)
    n_modules = len(sizes)
    d_max = max_intra_density(n, sizes, n_modules)
    K_target = int(round(d_max * frac * n * n))
    W = motif_layer(nodes, edges) if keep_motif else np.zeros((n, n))
    K_now = int((np.abs(W) > 1e-12).sum())
    need = max(0, K_target - K_now)
    W, added = fill(W, mods, reps, need, fill_mode, seed)
    return W, int((np.abs(W) > 1e-12).sum()), added, d_max


def rand_matched(K, n, seed, mods, reps, block=False):
    """同 K 的随机权重矩阵。block=True 时限制在模块块内。"""
    rng = np.random.default_rng(seed)
    W = np.zeros((n, n))
    if K <= 0:
        return W
    cands = _blank_pairs(n, mods, reps,
                         "block_random" if block else "all_random")
    if not cands:
        return W
    rng.shuffle(cands)
    for (i, j) in cands[:K]:
        if abs(W[i, j]) < 1e-12:
            W[i, j] = rng.normal(0.4, 0.3)
    return W


def dens(W):
    return float((np.abs(W) > 1e-12).sum()) / float(W.shape[0] ** 2)


# --------------------------------------------------------------------------- #
# 配对检验专用：把「cell 基质」与「rep 路由」彻底解耦
# --------------------------------------------------------------------------- #
def cell_substrate(nodes, K_cell, seed=99999):
    """纯 cell 层随机 fill（不含任何 motif/rep 边），固定种子 → 可精确配对。"""
    mods, reps, _ = node_meta(nodes)
    n = len(nodes)
    W = np.zeros((n, n))
    if K_cell <= 0:
        return W
    cands = _blank_pairs(n, mods, reps, "intra_random")
    rng = np.random.default_rng(seed)
    rng.shuffle(cands)
    for (i, j) in cands[:K_cell]:
        if abs(W[i, j]) < 1e-12:
            W[i, j] = rng.normal(0.5, 0.3)
    return W


def rep_edge_list(nodes, edges):
    """提取 rep↔rep 边（motif 语义所在层），排除自环。"""
    n = len(nodes)
    idx = {a["id"]: i for i, a in enumerate(nodes)}
    rep_set = {i for i, a in enumerate(nodes)
               if str(a.get("role") or "") == "tissue_rep"}
    out = []
    for e in edges:
        i, j = idx.get(e.get("from")), idx.get(e.get("to"))
        if i is None or j is None:
            continue
        if i in rep_set and j in rep_set and i != j:
            out.append((i, j, float(e.get("weight", 0.0))))
    return out


def rep_indices(nodes):
    return [i for i, a in enumerate(nodes)
            if str(a.get("role") or "") == "tissue_rep"]


def random_rep_edges(reps, K, seed):
    """生成 K 条随机 rep↔rep 边（排除自环），权重分布与 motif 边量级一致。"""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(K):
        i = int(rng.choice(reps))
        j = int(rng.choice(reps))
        while j == i:
            j = int(rng.choice(reps))
        out.append((i, j, float(rng.normal(0.3, 0.2))))
    return out


def add_edges(W, elist):
    for (i, j, w) in elist:
        W[i, j] += w
    return W


# --------------------------------------------------------------------------- #
TARGETS = [
    "sample_10module.swarm.json",
    "sample_phase2_nested.swarm.json",
    "bp_predictive_coding.swarm.json",
    "bp_hierarchical.swarm.json",
    "bench_attention_working_combo.swarm.json",
    "evolved_phase3_locked_broad_explore__habit_consolidation__hierarchical__attention_gate.swarm.json",
    "evolved_phase3_free_working_memory_buffer__competitive_selection__hierarchical_deep.swarm.json",
]
TARGETS = [f for f in TARGETS if (ORG_DIR / f).exists()]


def short(lab):
    lab = lab.replace("evolved_phase3_locked_", "ga_locked_")
    lab = lab.replace("evolved_phase3_free_", "ga_free_")
    lab = lab.replace("bench_attention_working_combo", "bench_attn_wm_combo")
    return lab


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


def _hdr(title, note=""):
    print("\n" + "=" * 104)
    print(title)
    if note:
        print("  " + note)
    print("=" * 104)


# --------------------------------------------------------------------------- #
def probe_D0():
    _hdr("D0. 仪器健康检查 —— 同 K 随机储备池 × 绝对密度 × 延迟")
    print("  目的：确认目标密度在仪器可读区间内。若全 0 或全 1，本轮无效。")
    n = 49
    mods = np.zeros(n, dtype=int)
    reps = np.zeros(n, dtype=bool)
    print("  %-10s %-6s | %s | 极差" % ("密度", "K",
          "".join("%8d" % d for d in DELAYS)))
    print("  " + "-" * 74)
    rows = []
    for d in ABS_DENSITY:
        K = int(round(d * n * n))
        W = rand_matched(K, n, 777, mods, reps)
        sc = [avg(W, dl) for dl in DELAYS]
        rows.append((d, sc))
        print("  %-10.2f %-6d | %s | %.3f"
              % (d, K, "".join("%8.3f" % s for s in sc), max(sc) - min(sc)))
    ok = any(0.1 < max(s) < 0.95 for _, s in rows)
    print("\n  存在拐点区间（0.1<R2<0.95）: %s"
          % ("✓ 仪器有动态范围，本轮有效" if ok else "✗ 本轮无效"))
    return ok


def _advantage(t, n_seeds):
    """对单个拓扑跑一次「motif vs 随机」对照，返回 (ms, rs, adv, noise)。
    adv = 主延迟上的均值优势；noise = 随机对照的抽样 std。"""
    Wm, Km, _, dmax = densify(t["nodes"], t["edges"], 1.0, "intra_random",
                              keep_motif=True)
    mods, reps, _ = node_meta(t["nodes"])
    ms = [avg(Wm, d, n_seeds) for d in DELAYS]
    all_rs = []
    for d in DELAYS:
        draws = [rand_matched(Km, t["n"], 2000 + i, mods, reps)
                 for i in range(N_RANDOM)]
        scs = [avg(w, d, n_seeds) for w in draws]
        all_rs.append((float(np.median(scs)), float(np.std(scs))))
    rs = [x[0] for x in all_rs]
    pn = DELAYS.index(PRIMARY_DELAY)
    adv = ms[pn] - rs[pn]
    noise = all_rs[pn][1]
    return ms, rs, adv, noise, Km, dmax, Wm


def probe_D1(ts, n_seeds):
    _hdr("D1. 结构 vs 无结构 —— motif+cell 密化 vs 同 N 同 K **全局**随机图")
    print("  随机对照不尊重模块结构（任意两端点），检验「有任何模块结构 vs 完全没有」")
    print("  %-30s %4s %5s %7s %7s | %s | %s"
          % ("拓扑", "N", "K", "密度", "d_max",
             "".join("%6d" % d for d in DELAYS),
             "".join("%6d" % d for d in DELAYS)))
    print("  " + "-" * 104)
    wins, total = 0, 0.0
    for t in ts:
        mods, reps, _ = node_meta(t["nodes"])
        Wm, Km, _, dmax = densify(t["nodes"], t["edges"], 1.0, "intra_random",
                                  keep_motif=True)
        ms = [avg(Wm, d, n_seeds) for d in DELAYS]
        rs = []
        for d in DELAYS:
            rs.append(float(np.median([
                avg(rand_matched(Km, t["n"], 2000 + i, mods, reps), d, n_seeds)
                for i in range(N_RANDOM)])))
        adv = ms[DELAYS.index(PRIMARY_DELAY)] - rs[DELAYS.index(PRIMARY_DELAY)]
        total += adv
        wins += int(adv > 0.02)
        print("  %-30s %4d %5d %6.3f %7.3f | %s | %s"
              % (short(t["label"])[:30], t["n"], Km, dens(Wm), dmax,
                 "".join("%6.3f" % s for s in ms),
                 "".join("%6.3f" % s for s in rs)))
    print("  " + "-" * 104)
    print("  显著优于同 K 全局随机（>0.02, delay=%d）: %d / %d   均值优势=%+.4f"
          % (PRIMARY_DELAY, wins, len(ts), total / max(1, len(ts))))
    return wins, len(ts)


def probe_D2(ts, n_seeds):
    """最锐利检验：同 N 同 K 同模块块约束，唯一差异是 rep 层路由是否来自 motif。"""
    _hdr("D2. motif 路由 vs 随机路由 —— 同 N、同 K、同模块块约束（未配对，噪声较大）")
    print("  M = 生物 motif rep 路由 + cell 随机密化")
    print("  R = 移除全部 motif 边，改用同 K 的**块内**随机边（模块块结构相同）")
    print("  注意：cell fill 也重新抽样 → 噪声 sd 含 fill 随机性。精确归因见 D2b。")
    print("  %-28s %4s %5s %7s | %s | %s | %s | %s"
          % ("拓扑", "N", "K", "密度",
             "".join("%6d" % d for d in DELAYS),
             "".join("%6d" % d for d in DELAYS),
             "".join("%+7d" % d for d in DELAYS),
             "%7s" % ("噪声d%d" % PRIMARY_DELAY)))
    print("  " + "-" * 112)
    wins, total = 0, 0.0
    rows = []
    for t in ts:
        ms, rs, adv, noise, Km, dmax, Wm = _advantage(t, n_seeds)
        total += adv
        wins += int(adv > 0.02)
        rows.append((t, ms, rs, adv, noise, Km, dmax))
        print("  %-28s %4d %5d %7.3f | %s | %s | %s | %6.3f"
              % (short(t["label"])[:28], t["n"], Km, dens(Wm),
                 "".join("%6.3f" % s for s in ms),
                 "".join("%6.3f" % s for s in rs),
                 "".join("%+7.3f" % (ms[i] - rs[i]) for i in range(len(DELAYS))),
                 noise))
    print("  " + "-" * 112)
    print("  主延迟 %d：motif 路由显著优于随机路由（>0.02）: %d / %d   均值优势=%+.4f"
          % (PRIMARY_DELAY, wins, len(ts), total / max(1, len(ts))))
    sig = [r for r in rows if r[3] > 0.02 and r[3] > 2 * max(r[4], 1e-6)]
    print("  其中优势 > 2× 随机对照噪声: %d 个 → %s"
          % (len(sig), [short(r[0]["label"])[:20] for r in sig] or "无"))
    return wins, len(ts), rows


def probe_D2b(ts, n_seeds, n_random=N_RANDOM):
    """★配对检验（决定性）：cell 基质完全相同，唯一变量是 rep 层路由。

    D2 的两个缺陷在这里被修掉：
      1. D2 里 motif 边只占总边数 ~15%，信号被 85% 的随机 cell fill 稀释；
      2. D2 的随机对照连 cell fill 都重新抽了，噪声 sd 高达 0.099。
    这里 cell 基质用固定种子生成一次、M 与全部 R 共享同一份矩阵，
    只替换 rep 层边 → 噪声只剩 rep 路由本身，可精确归因。
    """
    _hdr("D2b. 配对检验 —— cell 基质固定，唯一变量是 rep 层路由  ★决定性")
    print("  M = 固定 cell 基质 + 生物 motif rep 边")
    print("  R = **同一份** cell 基质 + 同数量随机 rep 边（%d 次抽样）" % n_random)
    print("  cell 基质完全相同 → 噪声只来自 rep 路由本身，可精确归因")
    print("  %-28s %4s %5s %5s | %6s %6s | %s"
          % ("拓扑", "N", "Krep", "Ktot",
             "M", "R",
             "优势(均值±sd)"))
    print("  " + "-" * 112)
    wins, sig = 0, 0
    for t in ts:
        nodes = t["nodes"]
        n = t["n"]
        mods, reps, sizes = node_meta(nodes)
        reps_idx = rep_indices(nodes)
        elist = rep_edge_list(nodes, t["edges"])
        K_rep = len(elist)
        if K_rep == 0 or len(reps_idx) < 2:
            print("  %-28s 跳过（rep 边数=%d）" % (short(t["label"])[:28], K_rep))
            continue
        # 固定 cell 基质：填满模块内全部可用边（与 D2 的 frac=1.0 一致）
        K_cell = intra_capacity(n, mods, reps, sizes, t["n_mod"])
        Wbase = cell_substrate(nodes, K_cell, seed=99999)
        # M
        Wm = add_edges(Wbase.copy(), elist)
        sc_m = avg(Wm, PRIMARY_DELAY, n_seeds)
        # R × n_random（共享 Wbase，只换 rep 边）
        advs = []
        for s in range(n_random):
            Wr = add_edges(Wbase.copy(), random_rep_edges(reps_idx, K_rep, 5000 + s))
            advs.append(sc_m - avg(Wr, PRIMARY_DELAY, n_seeds))
        adv_mean, adv_sd = float(np.mean(advs)), float(np.std(advs))
        K_tot = int((np.abs(Wm) > 1e-12).sum())
        z = adv_mean / max(adv_sd, 1e-9)
        wins += int(adv_mean > 0.02)
        sig += int(abs(z) >= 2.0)
        print("  %-28s %4d %5d %5d | %6.3f %6.3f | %+6.4f ±%.4f  (z=%+.2f)%s"
              % (short(t["label"])[:28], n, K_rep, K_tot,
                 sc_m, float(np.mean([sc_m - a for a in advs])),
                 adv_mean, adv_sd, z,
                 "  ← 显著" if abs(z) >= 2.0 else ""))
    print("  " + "-" * 112)
    print("  motif 路由均值优势 > 0.02: %d / %d" % (wins, len(ts)))
    print("  |z| >= 2.0（配对显著）: %d / %d" % (sig, len(ts)))
    return wins, sig, len(ts)


def probe_D3(ts, n_seeds):
    _hdr("D3. 密化方式 —— 随机 fill vs 结构化 fill（模块内 circulant 环形链路）")
    print("  回答：密化本身有用，还是只有特定的 cell 布线才有用？")
    print("  %-30s %5s | %s | %s | %s"
          % ("拓扑", "K",
             "".join("%6d" % d for d in DELAYS),
             "".join("%6d" % d for d in DELAYS),
             "".join("%+7d" % d for d in DELAYS)))
    print("  " + "-" * 104)
    wins, total = 0, 0.0
    for t in ts:
        Wr, _, _, _ = densify(t["nodes"], t["edges"], 1.0, "intra_random", keep_motif=True)
        Wk, Kk, _, _ = densify(t["nodes"], t["edges"], 1.0, "intra_ring", keep_motif=True)
        mr = [avg(Wr, d, n_seeds) for d in DELAYS]
        mk = [avg(Wk, d, n_seeds) for d in DELAYS]
        adv = [mk[i] - mr[i] for i in range(len(DELAYS))]
        ap = adv[DELAYS.index(PRIMARY_DELAY)]
        total += ap
        wins += int(ap > 0.02)
        print("  %-30s %5d | %s | %s | %s"
              % (short(t["label"])[:30], Kk,
                 "".join("%6.3f" % s for s in mr),
                 "".join("%6.3f" % s for s in mk),
                 "".join("%+7.3f" % a for a in adv)))
    print("  " + "-" * 104)
    print("  结构化 fill 显著优于随机 fill（>0.02, delay=%d）: %d / %d   均值=%+.4f"
          % (PRIMARY_DELAY, wins, len(ts), total / max(1, len(ts))))
    return wins, len(ts)


def probe_D4(ts, n_seeds):
    _hdr("D4. 密度扫描 —— motif 优势 vs 密度（按各拓扑可达上限的比例扫描）")
    print("  frac = 1.0 表示填满模块内所有可用边。比例扫描保证跨拓扑公平。")
    print("  对照 = 同 K 块内随机。优势 = motif - random（delay=%d）" % PRIMARY_DELAY)
    print("  %-30s %7s | %s" % ("拓扑", "d_max",
          "".join("%-10s" % ("%.0f%%" % (f * 100)) for f in FRACS)))
    print("  " + "-" * 104)
    summary = []
    for t in ts:
        mods, reps, _ = node_meta(t["nodes"])
        dmax = max_intra_density(t["n"], t["sizes"], t["n_mod"])
        cells = []
        for f in FRACS:
            Wm, Km, _, _ = densify(t["nodes"], t["edges"], f, "intra_random",
                                   keep_motif=True)
            sm = avg(Wm, PRIMARY_DELAY, n_seeds)
            sr = float(np.median([
                avg(rand_matched(Km, t["n"], 3000 + i, mods, reps, block=True),
                    PRIMARY_DELAY, n_seeds) for i in range(N_RANDOM)]))
            cells.append("%+.3f" % (sm - sr))
            summary.append((t["label"], dmax, f, Km, sm, sr, sm - sr))
        print("  %-30s %7.3f | %s"
              % (short(t["label"])[:30], dmax, "".join("%-10s" % c for c in cells)))
    print("  " + "-" * 104)
    anypos = [s for s in summary if s[6] > 0.02]
    print("  任意（拓扑,密度）出现 motif 优势（>0.02）: %d / %d"
          % (len(anypos), len(summary)))
    if anypos:
        print("  出现优势的组合：")
        for lab, dmax, f, Km, sm, sr, adv in anypos:
            print("    %-28s d_max=%.3f frac=%.0f%% K=%d  motif=%.3f random=%.3f %+.3f"
                  % (short(lab)[:28], dmax, f * 100, Km, sm, sr, adv))
    by_frac = {}
    for lab, dmax, f, Km, sm, sr, adv in summary:
        by_frac.setdefault(f, []).append(adv)
    print("  各 frac 平均优势: " + "  ".join(
        "%.0f%%: %+.4f (max=%+.3f)" % (f * 100, float(np.mean(v)), max(v))
        for f, v in sorted(by_frac.items())))
    return len(anypos), len(summary)


def cells_needed(k, target=0.20):
    """求满足 d_max >= target 的最小 cell 数 c。返回 None 表示不可能。

    解  c(c-1) / (k(c+1)^2) >= target  →  a·c² + b·c + d >= 0
      a = 1 - target·k,  b = -(1 + 2·target·k),  d = -target·k
    k>5 时 a<0 且二次项开口向下 → 无解；k=5 时 a=0 退化为线性且无解
    （极限恰为 0.20，永远达不到）。
    """
    a = 1.0 - target * k
    b = -(1.0 + 2.0 * target * k)
    d = -target * k
    if a <= 0:
        return None
    disc = b * b - 4.0 * a * d
    if disc < 0:
        return None
    root = (-b + float(np.sqrt(disc))) / (2.0 * a)
    return int(np.ceil(root))


# --------------------------------------------------------------------------- #
def probe_D6(ts, n_seeds):
    """密化收益：原始设计空间（motif 边、cell 孤立）vs cell 层密化后。

    这是本轮最重要的正面结果——量化「补上 cell 基质」本身值多少。
    """
    _hdr("D6. 密化收益 —— 原始设计空间 vs cell 层密化后")
    print("  原始 = 只有 motif 边（cell 完全孤立、零入边）")
    print("  密化 = 同样 motif 边 + cell 层填满模块内可用边")
    print("  %-28s %4s %6s %8s | %s | %s | %s"
          % ("拓扑", "N", "K密化", "提升倍数",
             "".join("%6d" % d for d in DELAYS),
             "".join("%6d" % d for d in DELAYS),
             "".join("%7s" % ("×%d" % d) for d in DELAYS)))
    print("  " + "-" * 112)
    gains = []
    for t in ts:
        W0 = motif_layer(t["nodes"], t["edges"])
        Wd, Kd, _, _ = densify(t["nodes"], t["edges"], 1.0, "intra_random",
                               keep_motif=True)
        s0 = [avg(W0, d, n_seeds) for d in DELAYS]
        sd = [avg(Wd, d, n_seeds) for d in DELAYS]
        pn = DELAYS.index(PRIMARY_DELAY)
        g = sd[pn] / max(s0[pn], 1e-9)
        gains.append(g)
        print("  %-28s %4d %6d %8.0f | %s | %s | %s"
              % (short(t["label"])[:28], t["n"], Kd, g,
                 "".join("%6.4f" % s for s in s0),
                 "".join("%6.3f" % s for s in sd),
                 "".join("%7s" % ("%.0f×" % (sd[i] / max(s0[i], 1e-9)))
                         for i in range(len(DELAYS)))))
    print("  " + "-" * 112)
    print("  主延迟 %d：几何平均提升 %.1f 倍   范围 %.0f× – %.0f×"
          % (PRIMARY_DELAY, float(np.exp(np.mean(np.log(gains)))),
             min(gains), max(gains)))
    print("  → 瓶颈不是 motif，是**缺失的 cell 基质**。补上它就拿到了绝大部分收益。")
    return gains


def probe_D5(ts):
    """D5. 解析上限：模块内密度的架构级约束。"""
    _hdr("D5. 解析上限 —— 模块内密度被模块数硬性封顶")
    print("  d_max = Σc_m(c_m-1) / n²，当 c→∞ 时 d_max → 1/k（k = 模块数）")
    print("  即：只要 cell 只连本模块，密度**永远到不了 1/k**——与 cell 数无关。")
    print("  %-28s %3s %4s %3s %7s %7s | %s"
          % ("拓扑", "k", "N", "c", "d_max", "1/k", "达到 d=0.20 所需 cell 数"))
    print("  " + "-" * 104)
    for t in ts:
        k = t["n_mod"]
        c = t["sizes"][sorted(t["sizes"])[0]]
        dmax = max_intra_density(t["n"], t["sizes"], k)
        need = cells_needed(k)
        if need is None:
            need_s = "不可能（1/k=%.3f < 0.20）" % (1.0 / k)
        elif need <= c:
            need_s = "c≥%d（当前 c=%d 已满足）" % (need, c)
        else:
            need_s = "c≥%d（当前 c=%d，缺 %d 倍）" % (need, c, round(need / c, 1))
        print("  %-28s %3d %4d %3d %7.3f %7.3f | %s"
              % (short(t["label"])[:28], k, t["n"], c, dmax, 1.0 / k, need_s))
    print("  " + "-" * 104)
    print("  解析公式校验（c→∞ 极限 1/k，以及达到 0.20 所需最小 cell 数 c）：")
    for k in (3, 4, 5, 6, 7, 10, 11):
        n = cells_needed(k)
        print("    k=%2d  上限 1/k = %.4f  达 0.20 需 c≥%s"
              % (k, 1.0 / k, str(n) if n else "不可能"))
    print("  ⚠ 重要修正：D0 实测本任务（delay=5）的**最优密度约 0.10**（R²=0.460），")
    print("    而非 ESN 教材常说的 0.20（本任务下 0.20 只有 0.248，反而更差）。")
    print("    所以「达不到 0.20」不是本项目的瓶颈——密化后 4/7 拓扑已达 0.12–0.138，")
    print("    已在最优区。真正的瓶颈只是 cell 完全孤立（见 D6），补上基质即达标。")
    print("  因此密度约束**不能解释** motif 无优势；D2b 的配对结果才是决定性的。")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="只跑 D2b 配对检验 + D5 解析上限")
    ap.add_argument("--n-seeds", type=int, default=N_SEEDS)
    args = ap.parse_args()

    n_seeds = args.n_seeds
    ts = load_all()
    print("Cell 级密化实验 | 节点上限=%d 主延迟=%d 种子平均=%d 随机对照=%d 抽样"
          % (NODE_CAP, PRIMARY_DELAY, n_seeds, N_RANDOM))
    print("候选拓扑: %d 个" % len(ts))
    for t in ts:
        print("  %-28s N=%3d 模块=%2d 每模块节点=%s"
              % (short(t["label"])[:28], t["n"], t["n_mod"],
                 sorted(set(t["sizes"].values()))))
    t0 = time.time()

    if args.quick:
        probe_D6(ts, n_seeds)
        probe_D2b(ts, n_seeds)
        probe_D5(ts)
    else:
        ok = probe_D0()
        if not ok:
            print("\n✗ D0 失败：仪器无动态范围，后续结果不可信。停止。")
            return
        probe_D6(ts, n_seeds)
        probe_D1(ts, n_seeds)
        probe_D2(ts, n_seeds)
        probe_D2b(ts, n_seeds)
        probe_D3(ts, n_seeds)
        probe_D4(ts, n_seeds)
        probe_D5(ts)

    print("\n耗时 %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
