"""
ga_evolve_topology.py — Phase 3 自动优化：遗传算法在 22 蓝图设计空间内进化虚拟生物形态

设计原则（诚实性第一）
----------------------
1. **不用 SwarmLabs 的 score 当梯度**。对照实验（BIO_ADVANTAGE_REPORT.md /
   MODULE_STACKING_REPORT.md）已证实引擎对拓扑**不按 score 区分**：所有配置
   score=100 / converged=1.0。把零信号量当适应度等于让 GA 在噪声里随机游走。
2. 因此 Phase 3 的适应度是 **flybrain 本地可计算的多目标结构指标**：
       - 线成本       n_edges                        （越小越好）
       - 能力覆盖     distinct profiles / 10          （越大越好）
       - motif 多样   distinct 真实 motif / 3         （越大越好）
       - 动态丰富度   recurrent + reservoir 边数      （越大越好）
       - 语义多样     distinct semantic_hint / 12     （越大越好）
   这五个量都是拓扑本身的属性，与引擎无关，梯度真实存在。
3. **决策 2「进化速度」指标**：固定评估预算下，达到阈值所需代数。
   GA vs 随机搜索（同预算）vs 人工设计（0 代）三方对照。
4. 适应度景观**确定性**：所有评估用固定 EVAL_SEED，保证 GA / 随机搜索
   在完全相同的目标函数下比较，否则对比无意义。

产出
----
  ga_phase3_log.csv        逐代最佳/均值适应度 + 阈值命中代数
  ga_phase3_runs.csv       每 seed 的 run 汇总（GA vs random vs manual）
  evolved_phase3_best.swarm.json   GA 最优个体（schema v1.1.1，可实例化）

跑法（minimind venv，路径传 C:/...）
------------------------------------
  python ga_evolve_topology.py --quick          # 快速验证
  python ga_evolve_topology.py                  # 默认 8 seeds
  python ga_evolve_topology.py --engine-check   # 额外跑 SwarmLabs 确认 score 仍无信号
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time
from pathlib import Path

from _local_key import local_api_key  # same-directory helper; keeps keys out of the repo

import numpy as np

HERE = Path(__file__).resolve().parent          # .../integrations/swarmlabs
ROOT = HERE.parent.parent                       # flybrain-connectome/
MCP_DIR = ROOT / "flybrain-connectome-mcp"
OUT_DIR = MCP_DIR / "generated_organisms" / "swarmlabs"
sys.path.insert(0, str(MCP_DIR))

import synthetic_bio_topology as c1  # noqa: E402

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
EVAL_SEED = 7          # 确定性适应度景观
N_PROFILES = 10        # 模块库上限（Phase 1 决策 1）
N_REAL_MOTIFS = 3      # MaleCNS v1.0 三个真实 motif
N_SEM_REF = 12         # 语义多样度归一化参考值
DYN_REF = 100          # 动态丰富度归一化参考值
COST_REF = 260.0       # 线成本归一化参考值

# 阈值（决策 2 的“进化速度”判定线）：同时满足才算命中
THRESHOLD = {"profiles": 10, "motifs": 3, "semantics": 5}

# 目标函数权重（用于标量化选择；Pareto 前沿单独报告）
W = {"cost": 0.22, "profiles": 0.26, "motifs": 0.18,
     "dynamics": 0.18, "semantics": 0.16}
PENALTY = 5.0       # 每个未满足的阈值项扣 5.0（远大于线成本差异，构成硬门槛）
WIRE_COST = 0.0008  # 每根边扣 0.0008（次要目标：同等计算力下选更省的形态）
DYN_WEIGHT = 0.0    # 动态适应度权重；0.0 = 实测无判别力，详见 dyn_score 说明
FIX_FLAGS = True    # 锁定三大架构开关为 True，保证与人工设计同物种可比

# ---- Phase 4.2 新增：结构稳定性作为第三适应度维度 ----
# stability = 1 - cross_module_edge_ratio  (1.0 = 完全模块内隔离)
# 惩罚：max(0, target - stability)  → 越接近目标越无惩罚
STABILITY_WEIGHT = 0.5     # 稳定性惩罚权重（可与 WIRE_COST 组合调优）
STABILITY_TARGET = 0.30    # 期望 cross_module_edge_ratio 上界（v1.2.0 实测 0.29-0.33）

# 基因组边界
R_N_MODULES = (3, 14)
R_APM = (2, 8)
R_COMBO_LEN = (1, 4)


# --------------------------------------------------------------------------- #
# 基因组操作
# --------------------------------------------------------------------------- #
def random_genome(rng: random.Random, all_bp: list[str]) -> dict:
    """默认锁定三大架构开关（抑制协调 / 储备库缓冲 / 递归记忆）为 True。

    理由：人工设计参考点全部开启这三项。若让 GA 关掉它们来省线，
    对比就是「精简版 vs 完整版」，不是同一物种内的效率比较。
    用 --allow-flags 可放开，作为「无架构约束的最小可行形态」的对照点。
    """
    if FIX_FLAGS:
        inh, res, rec = True, True, True
    else:
        inh = rng.random() < 0.8
        res = rng.random() < 0.7
        rec = rng.random() < 0.7
    return {
        "n_modules": rng.randint(*R_N_MODULES),
        "apm": rng.randint(*R_APM),
        "use_inh": inh,
        "use_res": res,
        "use_rec": rec,
        "blueprints": rng.sample(
            all_bp, rng.randint(*R_COMBO_LEN)),
    }


def mutate(rng: random.Random, g: dict, all_bp: list[str]) -> dict:
    n = dict(g)
    n["blueprints"] = list(g["blueprints"])
    r = rng.random()
    if r < 0.30:
        n["n_modules"] = rng.randint(*R_N_MODULES)
    elif r < 0.50:
        n["apm"] = rng.randint(*R_APM)
    elif r < 0.60:
        n["use_inh"] = not g["use_inh"]
    elif r < 0.70:
        n["use_res"] = not g["use_res"]
    elif r < 0.80:
        n["use_rec"] = not g["use_rec"]
    else:
        # 蓝图扰动：替换 / 增删，保持长度在界内且去重
        if n["blueprints"] and rng.random() < 0.6:
            n["blueprints"][rng.randrange(len(n["blueprints"]))] = rng.choice(all_bp)
        elif rng.random() < 0.5:
            n["blueprints"].append(rng.choice(all_bp))
        elif len(n["blueprints"]) > R_COMBO_LEN[0]:
            n["blueprints"].pop(rng.randrange(len(n["blueprints"])))
    if FIX_FLAGS:
        n["use_inh"] = n["use_res"] = n["use_rec"] = True
    L = R_COMBO_LEN
    n["blueprints"] = list(dict.fromkeys(n["blueprints"]))[: L[1] + 1]
    while len(n["blueprints"]) < L[0]:
        cand = rng.choice(all_bp)
        if cand not in n["blueprints"]:
            n["blueprints"].append(cand)
    return n


def crossover(rng: random.Random, a: dict, b: dict) -> dict:
    """算术混合标量 + 蓝图列表均匀交叉。"""
    child = {
        "n_modules": round(statistics.mean((a["n_modules"], b["n_modules"]))
                           + rng.randint(-1, 1)),
        "apm": round(statistics.mean((a["apm"], b["apm"])) + rng.randint(-1, 1)),
        "use_inh": a["use_inh"] if rng.random() < 0.5 else b["use_inh"],
        "use_res": a["use_res"] if rng.random() < 0.5 else b["use_res"],
        "use_rec": a["use_rec"] if rng.random() < 0.5 else b["use_rec"],
        "blueprints": [],
    }
    pool = list(a["blueprints"]) + list(b["blueprints"])
    child["blueprints"] = list(dict.fromkeys(
        rng.sample(pool, min(len(pool), R_COMBO_LEN[1]))))
    if len(child["blueprints"]) < R_COMBO_LEN[0]:
        for cand in (a["blueprints"] + b["blueprints"]):
            if cand not in child["blueprints"]:
                child["blueprints"].append(cand)
            if len(child["blueprints"]) >= R_COMBO_LEN[0]:
                break
    return child


def clamp(rng: random.Random, g: dict, all_bp: list[str]) -> dict:
    g = dict(g)
    g["n_modules"] = min(max(int(round(g["n_modules"])), *R_N_MODULES), R_N_MODULES[1])
    g["apm"] = min(max(int(round(g["apm"])), *R_APM), R_APM[1])
    g["use_inh"] = bool(g["use_inh"])
    g["use_res"] = bool(g["use_res"])
    g["use_rec"] = bool(g["use_rec"])
    if FIX_FLAGS:
        g["use_inh"] = g["use_res"] = g["use_rec"] = True
    L = R_COMBO_LEN
    bp = list(dict.fromkeys(g["blueprints"]))[: L[1] + 1]
    # 修复：组合为空或过短时补齐（保证基因组合法）
    while len(bp) < L[0]:
        cand = rng.choice(all_bp)
        if cand not in bp:
            bp.append(cand)
    g["blueprints"] = bp
    return g


# --------------------------------------------------------------------------- #
# 动态适应度：这棵拓扑当储备池能不能算（delayed-XOR 记忆任务）
# --------------------------------------------------------------------------- #
# 设计动机：仅靠结构指标（边数/profiles/motifs）时，阈值是低维的，
# 随机搜索就能命中 —— GA 无处发挥。于是尝试把拓扑的边当储备池权重 W，
# 跑一个非线性递归 + 线性读出器，让“拓扑会不会算”成为真实可优化的量。
#
# ⚠️ 标定结论（2026-09-18，probe_dyn*.py 实测）：这个仪器**当前不可用**，
#    因此 DYN_WEIGHT = 0.0，dyn 只作为诊断列记录，不进适应度。证据：
#    1) delayed-XOR + 单快照 ridge：教科书储备池(ρ=0.9,N=60)最高 0.373，
#       其余配置 ≤0.16 → 无动态范围。
#    2) 模式回忆 + 未归一化 1-MSE：所有 W（含 W=0）都是 0.981 —— 因为
#       目标方差只有 ~1/pres，"恒预测 0" 就能赢。
#    3) 模式回忆 + R² 归一化：基线 0.087、最好 0.282；gap≥20 时**所有**
#       W（含 ρ=0.9 教科书储备池）都退回 0.087 → 储备池留不住 40 步 ±1
#       模式均值。
#    结论：需要一个真正标定的储备池基准（任务设计 + 机制控制 + 训练协议），
#    这是一项独立的子工程，不是 Phase 3 顺手能补的。
def dyn_score(org: dict, n_units: int = 80, pres: int = 40, gap: int = 20,
              alpha: float = 0.2, leakage: float = 0.9,
              n_train: int = 8, n_test: int = 8) -> float:
    """返回 [0,1]：储备池模式回忆的 R² 分数（1 - test MSE / var(y)）。

    确定性（固定 rng），保证适应度景观可复现。

    注意：见上方标定结论，本函数当前**不参与适应度**（DYN_WEIGHT=0.0），
    仅作为诊断信号保留，避免把噪声当证据。
    """
    g = org.get("organism") or {}
    nodes = g.get("nodes", [])
    idx = {n["id"]: i for i, n in enumerate(nodes[:n_units])}
    N = len(idx)
    if N < 6:
        return 0.0
    W = np.zeros((N, N))
    for e in g.get("edges", []):
        i = idx.get(e.get("from"))
        j = idx.get(e.get("to"))
        if i is not None and j is not None:
            W[i, j] += e.get("weight", 0.0)
    # 列归一化（避免 tanh 饱和或爆炸）
    col = np.abs(W).sum(axis=0, keepdims=True)
    W = W / (col + 1e-8)

    rng = np.random.default_rng(20260918)  # 确定性
    U = rng.normal(0.0, 1.0, size=(N, 1))  # 固定输入投影
    S_tr, y_tr, S_te, y_te = [], [], [], []
    for k in range(n_train + n_test):
        pat = rng.choice([-1.0, 1.0], size=(pres, 1))
        y = float(pat.mean())
        x = np.zeros(N)
        for t in range(pres + gap):
            u = pat[t] if t < pres else np.zeros(1)
            x = leakage * np.tanh(W @ x + U @ u)
        (S_tr if k < n_train else S_te).append(x)
        (y_tr if k < n_train else y_te).append(y)

    S_tr, y_tr = np.array(S_tr), np.array(y_tr)
    S_te, y_te = np.array(S_te), np.array(y_te)
    Xtr = np.column_stack([S_tr, np.ones(n_train)])
    beta = np.linalg.solve(Xtr.T @ Xtr + alpha * np.eye(N + 1), Xtr.T @ y_tr)
    Xte = np.column_stack([S_te, np.ones(n_test)])
    mse_te = float(np.mean((Xte @ beta - y_te) ** 2))
    # R² 归一化，否则“恒预测 0”就能拿 0.975
    y_var = float(np.var(np.concatenate([y_tr, y_te]))) + 1e-9
    return max(0.0, 1.0 - mse_te / y_var)


# --------------------------------------------------------------------------- #
# 评估：本地多目标结构指标（不依赖 SwarmLabs）
# --------------------------------------------------------------------------- #
def cross_module_edge_ratio(org: dict) -> float:
    """Fraction of edges spanning different modules (Phase 4.2 stability metric).

    Node structure (C1): {'id': 'm0_rep', 'role': 'tissue_rep', 'module': 0, ...}
    Cross-module edges = edges whose from/to endpoints belong to different modules.
    Lower = stronger isolation = better fault containment.
    """
    nodes = org.get("organism", {}).get("nodes", [])
    edges = org.get("organism", {}).get("edges", [])
    if not edges:
        return 0.0
    node_to_mod: dict[str, int] = {}
    for nd in nodes:
        nid = nd.get("id") or nd.get("name")
        mod = nd.get("module", nd.get("module_id", 0))
        if nid:
            node_to_mod[nid] = mod
    cross = 0
    for e in edges:
        fm = node_to_mod.get(e.get("from"))
        tm = node_to_mod.get(e.get("to"))
        if fm is not None and tm is not None and fm != tm:
            cross += 1
    return round(cross / len(edges), 4)


def evaluate(g: dict, doc: dict, prov: dict) -> dict:
    spec = {
        "n_modules": g["n_modules"],
        "agents_per_module": g["apm"],
        "module_profiles": "cycled",
        "blueprint": list(g["blueprints"]),
        "use_inhibitory_coordinator": g["use_inh"],
        "use_reservoir_buffer": g["use_res"],
        "use_recurrent_memory": g["use_rec"],
    }
    org = c1.design_organism(spec, motifs=doc, seed=EVAL_SEED)
    cfg = c1.build_swarmlabs_config(org, name="ga_probe", provenance=prov)
    v = cfg["swarm"]["validation"]
    mp = org.get("motif_provenance") or {}

    profiles = len({m["name"] for m in org["module_profiles"].values()})
    b2m = mp.get("blueprint_to_motif") or {}
    motifs = len({e.get("source_motif") for e in b2m.values()
                  if e.get("source_motif") not in ("none", "unknown", None)})
    edges = org["organism"]["edges"]
    semantics = len({e["semantic_hint"] for e in edges if e.get("semantic_hint")})
    n_rec = sum(1 for e in edges if e.get("kind") == "recurrent")
    n_res = sum(1 for e in edges if e.get("kind") == "reservoir")
    n_edges = v["n_edges"]

    feasible = bool(v["ok"]) and org["blueprint_edges_added"] > 0

    if not feasible:
        richness = 0.0
    else:
        objectives = {
            "cost": min(n_edges / COST_REF, 1.0),
            "profiles": profiles / N_PROFILES,
            "motifs": motifs / N_REAL_MOTIFS,
            "dynamics": min((n_rec + n_res) / DYN_REF, 1.0),
            "semantics": min(semantics / N_SEM_REF, 1.0),
        }
        richness = (W["cost"] * (1 - objectives["cost"])
                    + W["profiles"] * objectives["profiles"]
                    + W["motifs"] * objectives["motifs"]
                    + W["dynamics"] * objectives["dynamics"]
                    + W["semantics"] * objectives["semantics"])

    hit = (feasible and profiles >= THRESHOLD["profiles"]
           and motifs >= THRESHOLD["motifs"]
           and semantics >= THRESHOLD["semantics"])

    # ---- 动态适应度：这棵拓扑当储备池能不能算 delayed-XOR ----
    dyn = dyn_score(org)

    # ---- 主目标：计算力优先，线成本次之，阈值作硬门槛 ----
    # 若不满足阈值，按缺项数量施加惩罚，使“砍线”无法绕过能力门槛
    v_prof = max(0, THRESHOLD["profiles"] - profiles)
    v_mot = max(0, THRESHOLD["motifs"] - motifs)
    v_sem = max(0, THRESHOLD["semantics"] - semantics)
    violations = v_prof + v_mot + v_sem

    # ---- Phase 4.2: 稳定性惩罚（cross_module_edge_ratio 超目标即扣分）----
    stability_ratio = cross_module_edge_ratio(org)
    stability_penalty = max(0.0, stability_ratio - STABILITY_TARGET)

    fitness = (-1.0 if not feasible
               else round(DYN_WEIGHT * dyn - WIRE_COST * n_edges
                          - PENALTY * violations
                          - STABILITY_WEIGHT * stability_penalty, 4))

    return {
        "genome": g, "feasible": feasible, "hit": hit,
        "fitness": fitness, "dyn": round(dyn, 4),
        "richness": round(richness, 4),
        "violations": violations,
        "n_edges": n_edges, "n_agents": v["n_agents"], "n_modules": g["n_modules"],
        "apm": g["apm"], "profiles": profiles, "motifs": motifs,
        "semantics": semantics, "recurrent": n_rec, "reservoir": n_res,
        "blueprint_edges": org["blueprint_edges_added"],
        "blueprints": "+".join(g["blueprints"]),
        "use_res": g["use_res"], "use_rec": g["use_rec"], "use_inh": g["use_inh"],
        "stability_ratio": stability_ratio,
        "stability_penalty": round(stability_penalty, 4),
        "org": org, "cfg": cfg,
    }


# --------------------------------------------------------------------------- #
# 遗传算法
# --------------------------------------------------------------------------- #
def run_ga(doc, prov, all_bp, pop, gens, seed, log_rows=None):
    rng = random.Random(seed)
    popg = [random_genome(rng, all_bp) for _ in range(pop)]
    results = [evaluate(g, doc, prov) for g in popg]
    # 世代约定：gen=0 是初始随机种群；命中代数从 0 计数
    best_hit_gen = 0 if any(r["hit"] for r in results) else None
    t0 = time.time()

    for gen in range(1, gens + 1):
        feasible = [r for r in results if r["feasible"]]
        mean_f = statistics.mean([r["fitness"] for r in results]) if results else 0.0
        mean_r = statistics.mean([r["richness"] for r in results]) if results else 0.0
        mean_d = statistics.mean([r["dyn"] for r in results]) if results else 0.0
        best = max(results, key=lambda r: r["fitness"])
        if log_rows is not None:
            log_rows.append({
                "seed": seed, "gen": gen - 1,  # 记录的是本循环开始时已在手的种群
                "best_fitness": best["fitness"], "mean_fitness": round(mean_f, 4),
                "best_dyn": best["dyn"], "mean_dyn": round(mean_d, 4),
                "best_richness": best["richness"],
                "mean_richness": round(mean_r, 4),
                "n_feasible": len(feasible), "hit": best["hit"],
                "best_edges": best["n_edges"], "best_profiles": best["profiles"],
                "best_motifs": best["motifs"], "best_semantics": best["semantics"],
                "best_blueprint": best["blueprints"],
                "elapsed_s": round(time.time() - t0, 2),
            })

        # 精英保留 + 锦标赛选择 + 交叉 + 变异
        results_sorted = sorted(results, key=lambda r: r["fitness"], reverse=True)
        new_pop = [results_sorted[i]["genome"] for i in range(min(2, pop))]
        while len(new_pop) < pop:
            a = tournament(rng, results, k=3)
            b = tournament(rng, results, k=3)
            child = clamp(rng, crossover(rng, a["genome"], b["genome"]), all_bp)
            if rng.random() < 0.35:
                child = mutate(rng, child, all_bp)
            new_pop.append(child)
        popg = new_pop
        results = [evaluate(g, doc, prov) for g in popg]
        if best_hit_gen is None and any(r["hit"] for r in results):
            best_hit_gen = gen

    best = max(results, key=lambda r: r["fitness"])
    return {"best": best, "hit_gen": best_hit_gen,
            "all": results, "elapsed_s": round(time.time() - t0, 2)}


def tournament(rng, results, k=3):
    """从可行个体中做锦标赛选择；全体不可行时退化为全种群选择（保留精英基因）。"""
    pool = [r for r in results if r["feasible"]] or results
    cand = rng.sample(pool, min(k, len(pool)))
    return max(cand, key=lambda r: r["fitness"])


# --------------------------------------------------------------------------- #
# 随机搜索对照（同评估预算）
# --------------------------------------------------------------------------- #
def run_random_search(doc, prov, all_bp, budget, seed):
    rng = random.Random(seed)
    best = None
    best_hit_eval = None
    t0 = time.time()
    for i in range(1, budget + 1):
        g = random_genome(rng, all_bp)
        r = evaluate(g, doc, prov)
        if r["feasible"] and (best is None or r["fitness"] > best["fitness"]):
            best = r
        if r["hit"] and best_hit_eval is None:
            best_hit_eval = i
    return {"best": best, "hit_eval": best_hit_eval, "budget": budget,
            "elapsed_s": round(time.time() - t0, 2)}


# --------------------------------------------------------------------------- #
# 人工设计参考点（既有样本，0 代进化）
# --------------------------------------------------------------------------- #
MANUAL_REFS = [
    ("manual_sample_10module", {"n_modules": 10, "agents_per_module": 6,
                                "module_profiles": "cycled",
                                "blueprint": ["predictive_coding"],
                                "use_inhibitory_coordinator": True,
                                "use_reservoir_buffer": True,
                                "use_recurrent_memory": True}),
    ("manual_phase2_nested", {"n_modules": 10, "agents_per_module": 6,
                              "module_profiles": "cycled",
                              "blueprint": ["hierarchical_deep", "predictive_coding_v2",
                                            "reward_gated_selection"],
                              "use_inhibitory_coordinator": True,
                              "use_reservoir_buffer": True,
                              "use_recurrent_memory": True}),
    ("manual_bp_hierarchical", {"n_modules": 6, "agents_per_module": 6,
                                "module_profiles": "cycled",
                                "blueprint": ["hierarchical"],
                                "use_inhibitory_coordinator": True,
                                "use_reservoir_buffer": True,
                                "use_recurrent_memory": True}),
]


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 3/4 遗传算法进化虚拟生物形态")
    ap.add_argument("--quick", action="store_true", help="快速验证（3 seeds, pop16, 20 代）")
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--pop", type=int, default=24)
    ap.add_argument("--gens", type=int, default=40)
    ap.add_argument("--engine-check", action="store_true",
                    help="对 GA 最优个体跑一次 SwarmLabs 确认 score 仍无信号")
    ap.add_argument("--allow-flags", action="store_true",
                    help="放开三大架构开关参与优化（默认锁定 True，与人工设计可比）")
    ap.add_argument("--tag", default=None,
                    help="产物文件名后缀（默认按架构开关自动取 locked/free）")
    # ---- Phase 4.2: 稳定性作为第三适应度维度 ----
    # 注意：default 硬编码常量值，因为 global 声明必须在首次使用前
    ap.add_argument("--stability-weight", type=float, default=0.5,
                    help="稳定性惩罚权重（默认 0.5）")
    ap.add_argument("--stability-target", type=float, default=0.30,
                    help="目标 cross_module_edge_ratio 上界（默认 0.30）")
    args = ap.parse_args(argv)

    global FIX_FLAGS, STABILITY_WEIGHT, STABILITY_TARGET
    FIX_FLAGS = not args.allow_flags
    args.tag = args.tag or ("free" if args.allow_flags else "locked")
    STABILITY_WEIGHT = args.stability_weight
    STABILITY_TARGET = args.stability_target

    if args.quick:
        args.seeds, args.pop, args.gens = 3, 16, 20

    doc, prov = c1.resolve_motifs(source="local", verbose=False)
    all_bp = list(c1.BLUEPRINTS.keys())
    print("=" * 74)
    print("Phase 3 自动优化 · 遗传算法")
    print("  设计空间: %d 蓝图 × n_modules %d-%d × apm %d-%d × 组合 1-%d 个"
          % (len(all_bp), *R_N_MODULES, *R_APM, R_COMBO_LEN[1]))
    print("  阈值(命中线): profiles>=%d, motifs>=%d, semantics>=%d"
          % (THRESHOLD["profiles"], THRESHOLD["motifs"], THRESHOLD["semantics"]))
    print("  主目标: 最小线成本(%.5f/边) + 阈值硬惩罚(%.1f/项) + 稳定性惩罚(%.2f×(ratio-%.2f)) | 动态权重=%.1f | 架构开关: %s"
          % (WIRE_COST, PENALTY, STABILITY_WEIGHT, STABILITY_TARGET, DYN_WEIGHT,
             "锁定 True（与人工设计同物种）" if FIX_FLAGS else "参与优化（精简对照）"))
    print("  seeds=%d pop=%d gens=%d  →  GA 预算 %d 次评估/seed"
          % (args.seeds, args.pop, args.gens, args.pop * args.gens))
    print("=" * 74)

    log_rows = []
    runs = []
    best_overall = None
    for s in range(1, args.seeds + 1):
        ga = run_ga(doc, prov, all_bp, args.pop, args.gens, seed=100 + s,
                    log_rows=log_rows)
        rs = run_random_search(doc, prov, all_bp, args.pop * args.gens, seed=900 + s)
        runs.append({
            "seed": s,
            "ga_fitness": ga["best"]["fitness"],
            "ga_dyn": ga["best"]["dyn"],
            "ga_edges": ga["best"]["n_edges"],
            "ga_profiles": ga["best"]["profiles"],
            "ga_motifs": ga["best"]["motifs"],
            "ga_semantics": ga["best"]["semantics"],
            "ga_richness": ga["best"]["richness"],
            "ga_stability_ratio": ga["best"]["stability_ratio"],
            "ga_stability_penalty": ga["best"]["stability_penalty"],
            "ga_hit_gen": ga["hit_gen"] if ga["hit_gen"] is not None else "miss",
            "ga_blueprint": ga["best"]["blueprints"],
            "ga_apm": ga["best"]["apm"],
            "ga_use_res": ga["best"]["use_res"],
            "ga_use_rec": ga["best"]["use_rec"],
            "rs_fitness": rs["best"]["fitness"] if rs["best"] else -1.0,
            "rs_dyn": rs["best"]["dyn"] if rs["best"] else None,
            "rs_edges": rs["best"]["n_edges"] if rs["best"] else None,
            "rs_richness": rs["best"]["richness"] if rs["best"] else None,
            "rs_stability_ratio": rs["best"]["stability_ratio"] if rs["best"] else None,
            "rs_stability_penalty": rs["best"]["stability_penalty"] if rs["best"] else None,
            "rs_hit_eval": rs["hit_eval"] if rs["hit_eval"] is not None else "miss",
            "ga_elapsed_s": ga["elapsed_s"],
            "rs_elapsed_s": rs["elapsed_s"],
        })
        if best_overall is None or ga["best"]["fitness"] > best_overall["fitness"]:
            best_overall = ga["best"]
        print("  seed %-2d GA fit=%.4f dyn=%.4f rich=%.3f (edges=%d prof=%d mot=%d sem=%d hit=%s, %.1fs) | "
              "RS fit=%.4f dyn=%s (edges=%s hit=%s, %.1fs)"
              % (s, ga["best"]["fitness"], ga["best"]["dyn"], ga["best"]["richness"],
                 ga["best"]["n_edges"], ga["best"]["profiles"],
                 ga["best"]["motifs"], ga["best"]["semantics"], ga["hit_gen"],
                 ga["elapsed_s"],
                 rs["best"]["fitness"] if rs["best"] else -1.0,
                 ("%.4f" % rs["best"]["dyn"]) if rs["best"] else "-",
                 rs["best"]["n_edges"] if rs["best"] else "-",
                 rs["hit_eval"], rs["elapsed_s"]))

    # ---- 人工设计参考点 ----
    print("\n人工设计参考点（0 代进化）：")
    manual_rows = []
    for label, spec in MANUAL_REFS:
        g = {"n_modules": spec["n_modules"], "apm": spec["agents_per_module"],
             "use_inh": spec["use_inhibitory_coordinator"],
             "use_res": spec["use_reservoir_buffer"],
             "use_rec": spec["use_recurrent_memory"],
             "blueprints": spec["blueprint"]}
        r = evaluate(g, doc, prov)
        manual_rows.append({"ref": label, "fitness": r["fitness"],
                            "dyn": r["dyn"], "richness": r["richness"],
                            "n_edges": r["n_edges"], "profiles": r["profiles"],
                            "motifs": r["motifs"], "semantics": r["semantics"],
                            "hit": r["hit"], "blueprints": r["blueprints"]})
        print("  %-22s fit=%.4f dyn=%.4f rich=%.3f edges=%3d prof=%d mot=%d sem=%d hit=%s"
              % (label, r["fitness"], r["dyn"], r["richness"], r["n_edges"],
                 r["profiles"], r["motifs"], r["semantics"], r["hit"]))

    # ---- 写 CSV ----
    log_p = HERE / ("ga_phase3_log_%s.csv" % args.tag)
    if log_rows:
        with open(log_p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(log_rows[0].keys()))
            w.writeheader()
            w.writerows(log_rows)
    runs_p = HERE / ("ga_phase3_runs_%s.csv" % args.tag)
    with open(runs_p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(runs[0].keys()))
        w.writeheader()
        w.writerows(runs)

    # ---- 写 GA 最优个体的 swarm.json ----
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bp_label = best_overall["blueprints"].replace("+", "__")
    out_name = "evolved_phase3_%s_%s.swarm.json" % (args.tag, bp_label)
    cfg = best_overall["cfg"]
    (OUT_DIR / out_name).write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 结论 ----
    ga_hits = [r["ga_hit_gen"] for r in runs if r["ga_hit_gen"] != "miss"]
    rs_hits = [r["rs_hit_eval"] for r in runs if r["rs_hit_eval"] != "miss"]
    print("\n" + "=" * 74)
    print("结论摘要")
    print("=" * 74)
    print("  GA  命中阈值: %d/%d seeds" % (len(ga_hits), args.seeds),
          ("(中位代数=%d)" % statistics.median(ga_hits)) if ga_hits else "(全部未命中)")
    print("  随机 命中阈值: %d/%d seeds" % (len(rs_hits), args.seeds),
          ("(中位评估数=%d)" % statistics.median(rs_hits)) if rs_hits else "(全部未命中)")
    print("  GA 最优: fit=%.4f  dyn=%.4f  edges=%d  profiles=%d  motifs=%d  semantics=%d  richness=%.3f"
          % (best_overall["fitness"], best_overall["dyn"], best_overall["n_edges"],
             best_overall["profiles"], best_overall["motifs"],
             best_overall["semantics"], best_overall["richness"]))
    print("  GA 基因组: n_modules=%d apm=%d res=%s rec=%s inh=%s blueprint=%s"
          % (best_overall["n_modules"], best_overall["apm"], best_overall["use_res"],
             best_overall["use_rec"], best_overall["use_inh"], best_overall["blueprints"]))

    # ---- 决定性比较 A：计算力（拓扑当储备池能解 delayed-XOR 的质量）----
    ga_dyn = max(r["ga_dyn"] for r in runs)
    rs_dyn = max(r["rs_dyn"] for r in runs if r["rs_dyn"] is not None)
    man_dyn = max(m["dyn"] for m in manual_rows)
    print("\n决定性比较 A —— 记忆能力 dyn（储备池模式回忆 R²，0=与恒预测0等价；仅诊断，权重=0）：")
    print("  GA    : %.4f" % ga_dyn)
    print("  随机  : %.4f" % rs_dyn)
    print("  人工  : %.4f" % man_dyn)
    print("  → GA 相对人工 %+.1f%%  |  相对随机 %+.1f%%"
          % ((ga_dyn - man_dyn) / man_dyn * 100 if man_dyn else float("nan"),
             (ga_dyn - rs_dyn) / rs_dyn * 100 if rs_dyn else float("nan")))

    # ---- 决定性比较 B：满足完整阈值所需的最少边数 ----
    ga_min = best_overall["n_edges"] if best_overall["hit"] else None
    rs_min = min([r["rs_edges"] for r in runs
                  if r["rs_hit_eval"] != "miss" and r["rs_edges"]], default=None)
    man_min = min([m["n_edges"] for m in manual_rows if m["hit"]], default=None)
    print("\n决定性比较 B —— 满足完整阈值(profiles>=%d, motifs>=%d, semantics>=%d)所需最少边数："
          % (THRESHOLD["profiles"], THRESHOLD["motifs"], THRESHOLD["semantics"]))
    print("  GA    : %s" % (ga_min if ga_min is not None else "未命中"))
    print("  随机  : %s" % (rs_min if rs_min is not None else "未命中"))
    print("  人工  : %s" % (man_min if man_min is not None else "无人工设计命中"))
    if ga_min and man_min:
        print("  → GA 比人工最少线设计少 %.1f%% 边数"
              % ((man_min - ga_min) / man_min * 100))
    if ga_min and rs_min:
        print("  → GA 比随机搜索最少线设计少 %.1f%% 边数"
              % ((rs_min - ga_min) / rs_min * 100))
    print("  产物: %s / %s / %s" % (log_p.name, runs_p.name, out_name))

    # ---- 决定性比较 C：Phase 4.2 新增，稳定性（cross_module_edge_ratio 越低越好）----
    ga_stab = best_overall["stability_ratio"]
    rs_stab = min([r["rs_stability_ratio"] for r in runs
                   if r["rs_stability_ratio"] is not None], default=None)
    man_stabs = [r for r in manual_rows]  # 需要 evaluate 结果
    man_stab_vals = []
    for label, spec in MANUAL_REFS:
        g = {"n_modules": spec["n_modules"], "apm": spec["agents_per_module"],
             "use_inh": spec["use_inhibitory_coordinator"],
             "use_res": spec["use_reservoir_buffer"],
             "use_rec": spec["use_recurrent_memory"],
             "blueprints": spec["blueprint"]}
        r = evaluate(g, doc, prov)
        man_stab_vals.append((label, r["stability_ratio"]))
    man_stab = min(s for _, s in man_stab_vals)
    print("\n决定性比较 C —— Phase 4.2 新增：稳定性（cross_module_edge_ratio，越低越隔离）：")
    print("  目标上界: %.2f" % STABILITY_TARGET)
    print("  GA    : %.4f" % ga_stab)
    if rs_stab is not None:
        print("  随机  : %.4f" % rs_stab)
    print("  人工  : %.4f (最好 %s)" % (man_stab, man_stab_vals[man_stab_vals.index(min(man_stab_vals, key=lambda x: x[1]))][0]))
    if ga_stab <= STABILITY_TARGET:
        print("  → GA 最优个体达标（ratio≤目标）")
    else:
        print("  → GA 最优个体未达标（ratio=%.4f > 目标 %.2f）" % (ga_stab, STABILITY_TARGET))

    # ---- 可选：SwarmLabs 引擎复核（确认 score 仍无信号）----
    if args.engine_check:
        # 对齐 e2e_bio_advantage.py 的引擎调用方式，确认 GA 最优个体在
        # SwarmLabs 上仍然 score 无信号（结构性优势的引擎对照）
        print("\n[engine-check] 对 GA 最优个体跑一次 SwarmLabs（确认 score 仍无信号）...")
        import subprocess
        import os
        sw = r"C:\Users\xing\Desktop\swarmlabs"
        py = r"C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe"
        samples = Path(sw) / "agentteams" / "samples"
        samples.mkdir(parents=True, exist_ok=True)
        req = {"goal": "Phase 3 engine-check（GA 最优个体）",
               "scenarios": ["surrogate_forrester"], "max_scenarios": 1,
               "top_n": 5, "allow_correction": True,
               "thresholds": {"rel_converged": 0.05, "cov_min": 0.8, "cal_max": 0.08}}
        req_path = samples / "_ga_phase3_check.json"
        req_path.write_text(json.dumps(req, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        env = os.environ.copy()
        env["FLYBRAIN_DATA_DIR"] = str(ROOT / "male_cns")
        env["FLYBRAIN_API_KEY"] = os.environ.get("FLYBRAIN_API_KEY") or local_api_key()
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
            env.pop(k, None)
        env["NO_PROXY"] = "127.0.0.1,localhost"
        cmd = [py, str(Path(sw) / "agentteams" / "run.py"),
               "--request", str(req_path), "--no-local-model",
               "--topology", str(OUT_DIR / out_name)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               cwd=sw, timeout=180, env=env)
            print("  exit=%s" % p.returncode)
            print("  stdout=%.500s" % (p.stdout or "").strip())
            print("  stderr=%.300s" % (p.stderr or "").strip())
        except Exception as e:  # noqa: BLE001
            print("  engine-check 失败（不阻塞本地结论）: %s" % e)

    print("\n完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
