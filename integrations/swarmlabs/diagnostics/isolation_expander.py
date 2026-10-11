"""R1 扩样：把故障隔离实验从 N=27 扩到 N≥100，产出 held-out 验证数据集。

用途
----
`isolation_predictor.py` 的现有 27 拓扑只够 in-sample 拟合，无法说"是否规律"。
本脚本按参数网格合成生成 100+ 个模块化拓扑，复用完全相同的评估管线（同一
`r2_score` / `avg` / `densify_full` / `disable_module` / `disable_random` /
`feature_from_W`），产出：

  `isolation_dataset_N100.json`   —— 每拓扑一行，含 verdict、diff、9 个结构特征
  `isolation_heldout_report.json` —— train/test 分割 + 线性拟合 held-out R²

判定不变（沿用既有实验）：diff = mod_median_drop − rand_median_drop；
diff < −0.05 → H1 模块化；> +0.05 → H2 耦合；其余 H3 无结构。

设计空间（合成网格，全部零外部依赖，全部从 `node_meta` 派生）
-------------------------------------------------------------
  k           ∈ {2, 3, 4, 5, 6}          模块数
  c_per_mod   ∈ {3, 4, 5, 6}              每模块 cell 数（不含 tissue_rep）
  n_inter     ∈ {0, 1, 2, 3, 5, 8}        跨模块 rep↔rep 边数
  densify_fr  ∈ {0.50, 0.75, 1.00}        模块内填充比例

理论最大组合 = 6 × 4 × 6 × 3 = 432。NODE_CAP=49 会把 c_per_mod×k 的组合
筛掉一部分；再减去弱基线跳过（R²<1e-3）。最终目标 **N≥100**。

为什么按网格而不是纯随机
------------------------
纯随机难以在样本内覆盖密度/规模/耦合三维的合理组合，且很难说明"N 是多少"。
网格 + 少量 jitter 兼顾覆盖性和可解释性。**每个合成拓扑带可复现种子**。

诚实边界
--------
- 合成拓扑不是"真实连接组"；它们是**模块化图族的采样**，用于测试命题是否
  具有普适性，不用于证明"生物脑一定如此"。
- `n_inter` 与 `densify_fr` 直接控制"结构-任务对齐度"，这既是本实验的
  机制假说变量（R1 P2/P3），也是**可能的偏倚来源**——网格已把两个极值
  都覆盖，报告里会分开报。
- 弱基线拓扑（R²<1e-3）不进入数据集，但会在 skipped 字段里留痕。

用法
----
    python isolation_expander.py                  # 全量网格，N≥100
    python isolation_expander.py --quick          # 缩到 40 拓扑，快
    python isolation_expander.py --n 200 --out xxx.json
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MCP = ROOT / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP))

import topology_profile as tp  # noqa: E402


# --------------------------------------------------------------------------- #
# 复用现有实验的评估管线（严格 import，不重写）
# --------------------------------------------------------------------------- #
_spec_cd = importlib.util.spec_from_file_location(
    "cdens_exp", HERE / "cell_densify_experiment.py")
_cd = importlib.util.module_from_spec(_spec_cd)
_spec_cd.loader.exec_module(_cd)

_spec_fie = importlib.util.spec_from_file_location(
    "fie", HERE / "fault_isolation_experiment.py")
fie = importlib.util.module_from_spec(_spec_fie)
_spec_fie.loader.exec_module(fie)

NODE_CAP = fie.NODE_CAP           # 49
DENSIFY_FRAC_DEFAULT = 0.75
SEED_BASE = 100003

r2_score = fie.r2_score
avg = fie.avg
spectral_radius = fie.spectral_radius
disable_module = fie.disable_module
disable_random = fie.disable_random
node_meta = fie.node_meta
N_SEEDS = fie.N_SEEDS
N_RANDOM = fie.N_RANDOM


def _avg_with(W, n_seeds):
    """与 fie.avg 一致，但接受可传的 n_seeds（避免运行时改全局）。"""
    return float(np.mean([r2_score(W, delay=fie.DELAY, seed=s)
                          for s in range(n_seeds)]))


# --------------------------------------------------------------------------- #
# 合成拓扑生成器
# --------------------------------------------------------------------------- #
def make_agents(k: int, cells_per_mod: int) -> list[dict]:
    """构造 k 个模块、每模块 cells_per_mod 个 cell + 1 个 tissue_rep。
    guardrail 归入 module=None，被 pick_nodes 天然过滤。"""
    agents = []
    for m in range(k):
        for c in range(cells_per_mod):
            agents.append({
                "id": f"m{m}_a{c}",
                "role": "cell",
                "swarm_role": "executor",
                "module": m,
                "task_hint": "synthetic",
                "profile_name": "generic",
            })
        agents.append({
            "id": f"m{m}_rep",
            "role": "tissue_rep",
            "swarm_role": "coordinator",
            "module": m,
            "task_hint": "synthetic",
            "profile_name": "tissue_rep",
        })
    # 一个不属任何模块的 guardrail（会被 module_structure 过滤）
    agents.append({
        "id": "guard", "role": "guardrail", "swarm_role": "guardrail",
        "module": None, "task_hint": "synthetic", "profile_name": "guard",
    })
    return agents


def make_edges(k: int, n_inter: int, seed: int,
               motif: str = "chain") -> list[dict]:
    """构造 rep↔rep 边（motif 层）。

    motif ∈ {"chain", "ring", "star", "complete", "random"}:
      chain    —— m_i_rep → m_{i+1}_rep
      ring     —— chain + 尾首连接
      star     —— 所有 m_i_rep → m_0_rep（中枢汇聚）
      complete —— 全对全 rep 边（若 k ≤ n_inter 则取上界）
      random   —— 随机选 n_inter 条（去自环）

    另外把每个 rep 的自环加上（recurrent state_feedback），与真实拓扑一致。
    """
    rng = np.random.default_rng(seed)
    reps = [f"m{m}_rep" for m in range(k)]
    edges: list[dict] = []
    used = set()

    def _add(i, j, w=0.3, kind="recurrent", sem="state_feedback"):
        if i == j and kind != "recurrent":
            return
        key = (i, j)
        if key in used:
            return
        used.add(key)
        edges.append({"from": i, "to": j, "weight": w,
                      "kind": kind, "semantic": sem, "module": -1})

    # 每个 rep 的自环
    for r in reps:
        _add(r, r, w=0.1, kind="recurrent", sem="state_feedback")

    if motif == "chain":
        for i in range(k - 1):
            _add(reps[i], reps[i + 1], w=0.3)
    elif motif == "ring":
        for i in range(k - 1):
            _add(reps[i], reps[i + 1], w=0.3)
        if k >= 2:
            _add(reps[-1], reps[0], w=0.3)
    elif motif == "star":
        for i in range(1, k):
            _add(reps[i], reps[0], w=0.3)
    elif motif == "complete":
        for i in range(k):
            for j in range(k):
                if i != j:
                    _add(reps[i], reps[j], w=0.3)
    elif motif == "random":
        # 补足到 n_inter 条（去掉自环，去重）
        tries = 0
        while sum(1 for e in edges
                  if e["from"] != e["to"]) < n_inter and tries < 200:
            i = int(rng.integers(0, k))
            j = int(rng.integers(0, k))
            if i == j:
                continue
            _add(reps[i], reps[j], w=float(rng.normal(0.3, 0.1)))
            tries += 1
    else:
        raise ValueError(motif)

    # 若 motif 生成不足 n_inter，用 random 补齐（不重复）
    current = sum(1 for e in edges if e["from"] != e["to"])
    if current < n_inter:
        tries = 0
        while current < n_inter and tries < 400:
            i = int(rng.integers(0, k))
            j = int(rng.integers(0, k))
            if i == j:
                continue
            if _add(reps[i], reps[j], w=float(rng.normal(0.3, 0.1))):
                current += 1
            tries += 1

    return edges


def synthetic_topology(seed: int, k: int, cells_per_mod: int,
                       n_inter: int, densify_fr: float,
                       motif: str) -> dict:
    """完整拓扑描述（nodes 直接是 agent 列表，edges 是边列表）。"""
    agents = make_agents(k, cells_per_mod)
    total_n = sum(1 for a in agents if a.get("module") is not None)
    if total_n > NODE_CAP:
        return {}
    # 截断 modules，使 pick_nodes 后 <= NODE_CAP
    edges = make_edges(k, n_inter, seed=seed + 7777, motif=motif)
    return {
        "label": f"syn_k{k}_c{cells_per_mod}_n{n_inter}_f{int(densify_fr*100)}_{motif}_s{seed}",
        "seed": seed,
        "k": k,
        "cells_per_mod": cells_per_mod,
        "n_inter_target": n_inter,
        "densify_fr": densify_fr,
        "motif": motif,
        "agents": agents,
        "edges": edges,
    }


def pick_nodes_compat(agents, cap=NODE_CAP):
    """与 cell_densify_experiment.pick_nodes 语义一致的 pick_nodes 包装。
    用 fie 里已经绑定的版本。"""
    return _cd.pick_nodes(agents, cap=cap)


def densify_compat(nodes, edges, frac=DENSIFY_FRAC_DEFAULT, seed=SEED_BASE):
    """与 fie.densify_full 语义一致，但用可传的分比例参数。"""
    W, _K, _added, _dmax = _cd.densify(nodes, edges, frac, "intra_random",
                                       seed=seed)
    mods, reps, _sizes = node_meta(nodes)
    return W, mods, reps


# --------------------------------------------------------------------------- #
# 结构特征（与 isolation_predictor.features_from_W 完全一致）
# --------------------------------------------------------------------------- #
def features_from_W(W: np.ndarray, mods: np.ndarray) -> dict:
    n = W.shape[0]
    nodes = [{"id": "n%d" % i, "module": int(mods[i])} for i in range(n)]
    edges = []
    ii, jj = np.nonzero(np.abs(W) > 1e-12)
    for i, j in zip(ii.tolist(), jj.tolist()):
        edges.append({"from": "n%d" % i, "to": "n%d" % j,
                      "weight": float(W[i, j])})
    prof = tp.profile({"nodes": nodes, "edges": edges})

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
        "module_size_cv": round(float(nz.std() / nz.mean()), 4)
                       if len(nz) and nz.mean() else 0.0,
    }


# --------------------------------------------------------------------------- #
# 单拓扑真值测量（与 fie.probe_main 完全一致）
# --------------------------------------------------------------------------- #
def measure_one(t: dict, n_seeds: int | None = None) -> dict | None:
    """n_seeds=None 时使用模块全局 N_SEEDS（可被 CLI 覆盖）。"""
    ns = n_seeds if n_seeds is not None else N_SEEDS
    nodes, _sizes = pick_nodes_compat(t["agents"], NODE_CAP)
    if len(nodes) < 10:
        return None
    W, mods, reps = densify_compat(nodes, t["edges"], frac=t["densify_fr"],
                                   seed=t["seed"])
    r2_base = _avg_with(W, ns)
    if r2_base < 1e-3:
        return {"label": t["label"], "skipped": "weak_baseline",
                "r2_base": round(r2_base, 5),
                "params": {k: t[k] for k in ("k", "cells_per_mod",
                                              "n_inter_target",
                                              "densify_fr", "motif", "seed")}}
    # 每模块关停
    mod_drops = []
    for m in sorted(set(mods.tolist())):
        Wd, _k = disable_module(W, mods, reps, m)
        mod_drops.append(max(0.0, (r2_base - _avg_with(Wd, ns)) / r2_base))
    # 随机关停对照
    med_size = int(np.median([int((mods == m).sum())
                              for m in sorted(set(mods.tolist()))]))
    rand_drops = []
    for i in range(N_RANDOM):
        Wd = disable_random(W, med_size, seed=1000 + i)
        rand_drops.append(max(0.0, (r2_base - _avg_with(Wd, ns)) / r2_base))

    mod_med = float(np.median(mod_drops))
    rand_med = float(np.median(rand_drops))
    diff = mod_med - rand_med
    if diff < -0.05:
        verdict = "H1"
    elif diff > 0.05:
        verdict = "H2"
    else:
        verdict = "H3"

    feats = features_from_W(W, mods)
    return {
        "label": t["label"],
        "mod_drop": round(mod_med, 4),
        "rand_drop": round(rand_med, 4),
        "diff": round(diff, 4),
        "verdict": verdict,
        **feats,
        "params": {k: t[k] for k in ("k", "cells_per_mod",
                                     "n_inter_target", "densify_fr",
                                     "motif", "seed")},
    }


# --------------------------------------------------------------------------- #
# Held-out 线性拟合（与 isolation_predictor 一致的 lstsq）
# --------------------------------------------------------------------------- #
FEATURES = ["k", "n", "density", "modularity_q", "spectral_radius",
            "intra_inter_ratio", "mean_intra_density",
            "med_size_over_n", "module_size_cv"]


def _replace_inf(rows: list[dict], f: str, fill: float = 0.0):
    out = []
    for r in rows:
        v = r.get(f, fill)
        if isinstance(v, float) and (np.isinf(v) or np.isnan(v)):
            v = fill
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = fill
        out.append(v)
    return np.array(out)


def _pearson(xs, ys):
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    if xs.std() < 1e-12 or ys.std() < 1e-12 or len(xs) < 4:
        return 0.0
    return float(np.corrcoef(xs, ys)[0, 1])


def linear_r2(X: np.ndarray, y: np.ndarray) -> tuple[float, list[float]]:
    """lstsq 拟合 y = β·X；返回 (r2, coef)。"""
    X1 = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(X1, y, rcond=None)
    pred = X1 @ coef
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 1e-15 else 0.0
    return r2, [float(c) for c in coef]


def train_test_split(rows: list[dict], frac: float = 0.7,
                     seed: int = 20260918) -> tuple[list[dict], list[dict]]:
    """按 label 的稳定哈希分割，避免同一拓扑的 seeds 出现在两侧。"""
    rng = np.random.default_rng(seed)
    keys = sorted({r["label"].rsplit("_s", 1)[0] for r in rows})
    order = list(range(len(keys)))
    rng.shuffle(order)
    cut = int(len(keys) * frac)
    train_keys = set(keys[i] for i in order[:cut])
    train = [r for r in rows if r["label"].rsplit("_s", 1)[0] in train_keys]
    test = [r for r in rows if r["label"].rsplit("_s", 1)[0] not in train_keys]
    return train, test


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #
def build_grid(quick: bool = False, n_target: int = 120):
    if quick:
        ks = [3, 4, 5]
        cps = [3, 4]
        ninters = [0, 2, 5]
        frs = [0.75]
        motifs = ["chain", "star", "random"]
        seeds_per = 2
    else:
        ks = [2, 3, 4, 5, 6]
        cps = [3, 4, 5, 6]
        ninters = [0, 1, 2, 3, 5, 8]
        frs = [0.50, 0.75, 1.00]
        motifs = ["chain", "ring", "star", "random"]
        seeds_per = 2

    # 过滤掉太小（<10 nodes）的组合：total_nodes = k*(c+1)，<10 会
    # 被 measure_one 里的 "too_small" 分支跳过，浪费网格槽位。
    combos_all = list(itertools.product(ks, cps, ninters, frs, motifs))
    combos = [(k, c, ni, fr, mf) for (k, c, ni, fr, mf) in combos_all
              if k * (c + 1) >= 10]

    out = []
    seed_cursor = 0
    # 用 shuffle 打散顺序，避免前 k 组都是 chain（造成 held-out 类别不均衡）
    import random as _rnd
    _rnd.Random(SEED_BASE).shuffle(combos)
    for k, c, ni, fr, mf in combos:
        if len(out) >= n_target:
            break
        for _ in range(seeds_per):
            seed_cursor += 1
            t = synthetic_topology(seed=SEED_BASE + seed_cursor, k=k,
                                   cells_per_mod=c, n_inter=ni,
                                   densify_fr=fr, motif=mf)
            if not t:
                continue
            out.append(t)
            if len(out) >= n_target:
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="缩到 ~40 拓扑")
    ap.add_argument("--n", type=int, default=120,
                    help="目标拓扑数（默认 120）")
    ap.add_argument("--out", default=str(HERE / "isolation_dataset_N100.json"))
    ap.add_argument("--heldout", default=str(HERE / "isolation_heldout_report.json"))
    ap.add_argument("--report", default=str(HERE / "ISOLATION_EXPANDER_REPORT.md"))
    ap.add_argument("--n-seeds", type=int, default=N_SEEDS,
                    help="每拓扑 ESN 平均的 seeds 数（默认 30，可用 10 加速）")
    args = ap.parse_args()

    n_seeds = args.n_seeds
    n_target = 40 if args.quick else args.n
    ts = build_grid(quick=args.quick, n_target=n_target)
    print("=" * 100)
    print("R1 EXPANDER — 隔离实验扩样到 N≥100")
    print("  生成拓扑数：%d   目标：%d   N_SEEDS=%d   N_RANDOM=%d"
          % (len(ts), n_target, n_seeds, N_RANDOM))
    print("=" * 100)

    t0 = time.time()
    rows, skipped = [], []
    for i, t in enumerate(ts):
        r = measure_one(t, n_seeds=n_seeds)
        if r is None:
            skipped.append({"label": t["label"], "reason": "too_small"})
            continue
        if r.get("skipped"):
            skipped.append(r)
            continue
        rows.append(r)
        if (i + 1) % 10 == 0 or i == len(ts) - 1:
            print("  progress %3d/%d  rows=%d skipped=%d  elapsed=%.1fs"
                  % (i + 1, len(ts), len(rows), len(skipped),
                     time.time() - t0))
    elapsed = time.time() - t0

    print("\n  有效拓扑：%d   跳过：%d（弱基线=%d 太小=%d）"
          % (len(rows), len(skipped),
             sum(1 for s in skipped if s.get("reason") == "weak_baseline"),
             sum(1 for s in skipped if s.get("reason") == "too_small")))
    print("  耗时 %.1fs" % elapsed)

    if len(rows) < 30:
        print("\n  ✗ 样本太少（<30），终止")
        return 1

    # 分类统计
    h1 = sum(1 for r in rows if r["verdict"] == "H1")
    h2 = sum(1 for r in rows if r["verdict"] == "H2")
    h3 = sum(1 for r in rows if r["verdict"] == "H3")
    print("\n  H1 模块化：%d / %d = %.1f%%" % (h1, len(rows), 100 * h1 / len(rows)))
    print("  H2 耦合：%d / %d = %.1f%%" % (h2, len(rows), 100 * h2 / len(rows)))
    print("  H3 无结构：%d / %d = %.1f%%" % (h3, len(rows), 100 * h3 / len(rows)))

    # 特征相关
    diffs = _replace_inf(rows, "diff")
    print("\n-- 特征与 diff 的皮尔逊相关（in-sample, N=%d）--" % len(rows))
    corrs = {}
    for f in FEATURES:
        xs = _replace_inf(rows, f)
        r = _pearson(xs, diffs)
        corrs[f] = round(r, 3)
        print("  %-22s r = %+.3f" % (f, r))

    # Held-out：train 拟合，test 评估
    train, test = train_test_split(rows, frac=0.7, seed=20260918)
    print("\n  train=%d test=%d" % (len(train), len(test)))

    # 相关性排序选 2 个特征（与既有脚本一致）
    ranked = sorted(corrs.items(), key=lambda kv: -abs(kv[1]))
    top2 = [f for f, _ in ranked[:2]]
    X_tr = np.column_stack([_replace_inf(train, f) for f in top2])
    y_tr = _replace_inf(train, "diff")
    r2_tr, coef_tr = linear_r2(X_tr, y_tr)
    X_te = np.column_stack([_replace_inf(test, f) for f in top2])
    y_te = _replace_inf(test, "diff")
    X1_te = np.column_stack([np.ones(len(X_te)), X_te])
    pred_te = X1_te @ np.array(coef_tr)
    ss_res_te = float(((y_te - pred_te) ** 2).sum())
    ss_tot_te = float(((y_te - y_te.mean()) ** 2).sum())
    r2_te = 1 - ss_res_te / ss_tot_te if ss_tot_te > 1e-15 else 0.0

    # 分类准确率：pred<−0.05 → H1，> +0.05 → H2，其余 H3
    def _pred_verdict(p):
        if p < -0.05:
            return "H1"
        elif p > 0.05:
            return "H2"
        return "H3"

    def _classify_acc(rows_part, preds):
        ok = sum(1 for r, p in zip(rows_part, preds)
                 if _pred_verdict(p) == r["verdict"])
        return ok, len(rows_part)

    ok_te, n_te = _classify_acc(test, pred_te.tolist())
    ok_tr, n_tr = _classify_acc(train, (X1_te.shape[1] and
                                         [float(np.array(coef_tr)[0] * 1 +
                                                    (np.array(coef_tr)[1 + i] * X_tr[i][j])
                                                    for j in range(len(top2)))
                                          for i in range(len(train))])
                                ) if False else (0, 0)
    # 简单重算 train acc
    X1_tr_full = np.column_stack([np.ones(len(X_tr)), X_tr])
    pred_tr = X1_tr_full @ np.array(coef_tr)
    ok_tr, n_tr = _classify_acc(train, pred_tr.tolist())

    baseline_train = sum(1 for r in train if r["verdict"] == "H1"), len(train)
    baseline_test = sum(1 for r in test if r["verdict"] == "H1"), len(test)

    print("\n-- Held-out 结果（features=%s）--" % top2)
    print("  coef = %s" % [round(c, 5) for c in coef_tr])
    print("  in-sample R² = %.4f" % r2_tr)
    print("  held-out  R² = %.4f" % r2_te)
    print("  train acc  = %d/%d   (baseline always-H1: %d/%d)"
          % (ok_tr, n_tr, baseline_train[0], baseline_train[1]))
    print("  test  acc  = %d/%d   (baseline always-H1: %d/%d)"
          % (ok_te, n_te, baseline_test[0], baseline_test[1]))

    # 保存数据集
    out_data = {
        "schema_version": "1.0",
        "kind": "isolation_dataset",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                        time.gmtime()),
        "n_topologies": len(rows),
        "n_seeds_per_topology": n_seeds,
        "n_random_controls": N_RANDOM,
        "n_skipped": len(skipped),
        "features": FEATURES,
        "verdict_rule": "H1 iff diff<-0.05; H2 iff diff>+0.05; else H3",
        "class_balance": {"H1": h1, "H2": h2, "H3": h3},
        "correlations": corrs,
        "heldout": {
            "split": "label-hash, frac=0.7, seed=20260918",
            "train_n": len(train), "test_n": len(test),
            "features_used": top2,
            "coef": coef_tr,
            "in_sample_r2": round(r2_tr, 4),
            "heldout_r2": round(r2_te, 4),
            "train_acc": [ok_tr, n_tr],
            "test_acc": [ok_te, n_te],
            "baseline_always_H1_train": list(baseline_train),
            "baseline_always_H1_test": list(baseline_test),
        },
        "skipped": skipped,
        "rows": rows,
    }
    Path(args.out).write_text(json.dumps(out_data, ensure_ascii=False, indent=2,
                                          default=str), encoding="utf-8")
    print("\n  wrote %s" % args.out)

    # 报告
    lines = []
    lines.append("# R1 扩样报告 —— 隔离实验扩到 N≥100")
    lines.append("")
    lines.append("- 生成日期：%s" % time.strftime("%Y-%m-%d %H:%M UTC",
                                                     time.gmtime()))
    lines.append("- 数据集：`isolation_dataset_N100.json`")
    lines.append("- 基线：`ISOLATION_PREDICTOR_REPORT.md`（N=27, in-sample R²=0.15）")
    lines.append("")
    lines.append("## 一、方法")
    lines.append("")
    lines.append("- 合成网格：k∈{2..6} × c∈{3..6} × n_inter∈{0,1,2,3,5,8} "
                 "× densify_fr∈{0.50, 0.75, 1.00} × motif∈{chain, ring, star, random}")
    lines.append("- 目标拓扑数：%d（实际有效：%d）" % (n_target, len(rows)))
    lines.append("- 每拓扑 N_SEEDS=%d，N_RANDOM=%d，与既有实验完全一致"
                 % (n_seeds, N_RANDOM))
    lines.append("- Held-out 分割：按 label 哈希稳定拆分，避免同拓扑同 seed 跨集")
    lines.append("- 特征集：**沿用既有 9 个结构特征**（不引入新变量）")
    lines.append("- 判定阈值 ±0.05：与既有实验完全一致")
    lines.append("")
    lines.append("## 二、分类结果（普适性检验）")
    lines.append("")
    lines.append("| 类别 | 数量 | 占比 | 旧基线（N=27）|")
    lines.append("|---|---|---|---|")
    lines.append("| H1 模块化 | %d | %.1f%% | 25/27 = 92.6%% |"
                 % (h1, 100 * h1 / len(rows)))
    lines.append("| H2 耦合 | %d | %.1f%% | 0/27 = 0%% |"
                 % (h2, 100 * h2 / len(rows)))
    lines.append("| H3 无结构 | %d | %.1f%% | 2/27 = 7.4%% |"
                 % (h3, 100 * h3 / len(rows)))
    lines.append("")
    lines.append("**判断**：如果 H1 占比与 27 拓扑基本一致（92.6%），"
                 "说明**『模块化普遍带来故障隔离』**的结论具有普适性；"
                 "如果显著偏离，说明原结论只在特定结构子集成立。")
    lines.append("")
    lines.append("## 三、结构特征与隔离强度的相关")
    lines.append("")
    lines.append("| 特征 | r（N=%d） | 旧（N=27） |" % len(rows))
    lines.append("|---|---|---|")
    old_corr = {"k": 0.131, "n": 0.152, "density": 0.254,
                "modularity_q": -0.335, "spectral_radius": 0.277,
                "intra_inter_ratio": 0.152, "mean_intra_density": 0.182,
                "med_size_over_n": 0.149, "module_size_cv": 0.0}
    for f in FEATURES:
        lines.append("| %s | %+.3f | %+.3f |" % (f, corrs[f], old_corr[f]))
    lines.append("")
    lines.append("## 四、Held-out 预测性")
    lines.append("")
    lines.append("- 特征：**%s**（按 |r| 前 2 名）" % top2)
    lines.append("- 系数：%s" % [round(c, 5) for c in coef_tr])
    lines.append("- **in-sample R² = %.4f**" % r2_tr)
    lines.append("- **held-out R² = %.4f**" % r2_te)
    lines.append("- train acc: %d/%d（baseline always-H1: %d/%d）"
                 % (ok_tr, n_tr, baseline_train[0], baseline_train[1]))
    lines.append("- **test acc: %d/%d**（baseline always-H1: %d/%d）"
                 % (ok_te, n_te, baseline_test[0], baseline_test[1]))
    lines.append("")
    lines.append("**判据**：")
    lines.append("- held-out R² 显著大于 0 且 test acc 显著优于 always-H1 "
                 "→ 结构性特征**可预测**隔离程度（推翻旧结论 R²=0.15）")
    lines.append("- held-out R² 接近 0 或负，test acc ≈ always-H1 baseline "
                 "→ 结构性特征**不可预测**（确认旧结论 R²=0.15）")
    lines.append("- 介于两者 → 需要机制特征（模块-任务对齐度），这正是 I-2 要做的")
    lines.append("")
    lines.append("## 五、诚实边界")
    lines.append("")
    lines.append("1. 合成拓扑是模块化图族的采样，不是真实连接组；用于测试命题普适性，"
                 "不主张\"生物脑一定如此\"。")
    lines.append("2. `n_inter` 与 `densify_fr` 直接控制结构-任务对齐度，"
                 "这也是 R1 P2/P3 的机制假说变量；报告里保留了 `params` 字段以便追溯。")
    lines.append("3. Held-out 分割按 label 哈希稳定，避免同 seed 同参数跨集造成泄漏；"
                 "但这仍是\"同分布内 held-out\"，不是\"跨生成方式\"的泛化测试。")
    lines.append("4. 弱基线（R²<1e-3）被跳过但记录在 `skipped` 字段，可复算。")
    lines.append("")
    lines.append("## 六、复现")
    lines.append("")
    lines.append("```bash")
    lines.append("PY=\"C:/Users/xing/.workbuddy/binaries/python/envs/minimind/Scripts/python.exe\"")
    lines.append("$PY integrations/swarmlabs/diagnostics/isolation_expander.py           # 全量 120")
    lines.append("$PY integrations/swarmlabs/diagnostics/isolation_expander.py --quick   # 40 拓扑")
    lines.append("```")
    lines.append("")
    Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    print("  wrote %s" % args.report)

    heldout_only = {
        "kind": "heldout_report",
        "generated_utc": out_data["generated_utc"],
        "in_sample_r2": round(r2_tr, 4),
        "heldout_r2": round(r2_te, 4),
        "features_used": top2,
        "coef": coef_tr,
        "test_acc": [ok_te, n_te],
        "baseline_always_H1_test": list(baseline_test),
    }
    Path(args.heldout).write_text(json.dumps(heldout_only, indent=2),
                                   encoding="utf-8")
    print("  wrote %s" % args.heldout)

    return 0


if __name__ == "__main__":
    sys.exit(main())
