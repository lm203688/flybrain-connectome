"""v2.12.0 组合拓扑 × 储备池尺寸 双维度扩容实验。

背景
  v2.7-v2.11 一直只做 A→B→C 链式组合（olfactory_to_steering /
  visual_to_escape / gustatory_to_motion）+ 3 种抽象拓扑
  （chain / parallel / feedback / hierarchical / skip_recurrence /
  modulatory_hub）。真实生物神经系统的主要形态不是链式，而是：

  · tree_fanout          —— 1 个中央单元 fan-out 到 3-4 下游
  · converging_funnel    —— 3-4 上游汇聚到 1 个整合者
  · hierarchical_pipeline —— 3 层：感觉 → 中间 → 运动
  · reciprocal_feedback  —— 双向/回环电路（A↔B）

  本轮把 4 种非链式组合加进来，同时在 N=60 和 N=200 两个尺寸下都跑，
  用同一个 memory_depth / convergence_90 / NARMA-10 度量看：

  1. 非链式组合是否比链式好？
  2. N=60→200 扩容是否突破 v2.11.0 的 memory/NARMA 天花板？
  3. 拓扑形状与尺寸有没有交互效应？

度量（复用 connectivity_topology_efficiency_experiment 的三件套）
  memory_depth      —— delay-line R²，eff_depth = max delay with R²>0.5
  convergence_90    —— step response 收敛到 90% 稳态的步数
  reaction_latency  —— 步输入后输出稳定的步数
  NARMA-10          —— 非线性动力学任务，越低越好

显著性
  Welch's t + Cohen's d，n_seeds=10（比 v2.11.0 的 n_seeds=5 多一倍），
  对比每种新拓扑 vs 对应链式组合在 N=60 和 N=200 下的差异。

用法
  python topology_capacity_experiment.py --quick    # n_seeds=5
  python topology_capacity_experiment.py            # n_seeds=10
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

from functional_units import compose_from_units  # noqa: E402
from multi_unit_benchmark_experiment import (  # noqa: E402
    build_composed_topology,
    composition_olfactory_to_steering,
    composition_visual_to_escape,
    composition_gustatory_to_motion,
    task_narma10,
)
from connectivity_topology_efficiency_experiment import (  # noqa: E402
    measure_memory_depth,
    measure_convergence_90,
    measure_reaction_latency,
)


# =========================================================================== #
# 4 种非链式组合
# =========================================================================== #

def composition_tree_fanout():
    """tree_fanout：1 中央 hub fan-out 到 3 个异构下游。

    生物学参照：hypothalamic_arousal_unit（下丘脑觉醒中心）向外广播
    orexin / histamine / arousal 三种调制信号到不同系统。
    这是一个 1→3 的 tree，不是链式。
    """
    units = [
        {"unit": "hypothalamic_arousal_unit", "instances": 1},
        {"unit": "cortical_l23_association_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
    ]
    conns = [
        # arousal_out (arousal.state) → cortical gate (arousal.state)
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.arousal_out",
         "to": "cortical_l23_association_unit.gate"},
        # orexin_out (modulatory.orexin) → CC steering orexin_in
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.orexin_out",
         "to": "central_complex_steering_unit.orexin_in"},
        # histamine_out (modulatory.histamine) → antennal_lobe histamine_in
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.histamine_out",
         "to": "antennal_lobe_glomerular_unit.histamine_in"},
    ]
    return compose_from_units(units, conns,
                              name="tree_fanout_composed")


def composition_converging_funnel():
    """converging_funnel：3 感觉输入汇聚到 1 个整合者。

    生物学参照：3 类感觉（视觉 lamina / 嗅觉 antennal_lobe / 味觉 pharyngeal）
    汇聚到 cortical_l23_association_unit 的 l4_in 通道做跨模态整合。
    这是一个 3→1 的 funnel，不是链式。
    """
    units = [
        {"unit": "compound_lamina_relay_unit", "instances": 1},
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "pharyngeal_gustatory_unit", "instances": 1},
        {"unit": "cortical_l23_association_unit", "instances": 1},
    ]
    conns = [
        {"type": "convergent_fanin",
         "from": "compound_lamina_relay_unit.lamina_out",
         "to": "cortical_l23_association_unit.l4_in"},
        {"type": "convergent_fanin",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "cortical_l23_association_unit.l4_in"},
        {"type": "convergent_fanin",
         "from": "pharyngeal_gustatory_unit.feed_drive",
         "to": "cortical_l23_association_unit.l4_in"},
    ]
    return compose_from_units(units, conns,
                              name="converging_funnel_composed")


def composition_hierarchical_pipeline():
    """hierarchical_pipeline：3 层（感觉 → 中间 → 运动）。

    生物学参照：果蝇多模态感觉整合 + 中央复合物转向。
    Layer 1（感觉）：antennal_lobe（嗅觉）+ compound_lamina（视觉）
    Layer 2（中间）：mushroom_body_associative_memory（嗅觉整合）
                    + central_complex_heading（视觉导航）
    Layer 3（运动）：central_complex_steering（导航转向）

    层间是"fan-out + fan-in 交错"，不是单一链式。
    """
    units = [
        # Layer 1: sensory
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "compound_lamina_relay_unit", "instances": 1},
        # Layer 2: intermediate
        {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
        {"unit": "central_complex_heading_unit", "instances": 1},
        # Layer 3: motor
        {"unit": "central_complex_steering_unit", "instances": 1},
    ]
    conns = [
        # olfactory path: AAL → MB associative
        {"type": "sparse_expansion_projection",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "mushroom_body_associative_memory_unit.sparse_code"},
        # visual path: lamina → central complex heading (compass)
        {"type": "topographic_mapping",
         "from": "compound_lamina_relay_unit.lamina_out",
         "to": "central_complex_heading_unit.compass_in"},
        # MB → steering (valence)
        {"type": "modulatory_gated_plasticity",
         "from": "mushroom_body_associative_memory_unit.learned_valence",
         "to": "central_complex_steering_unit.valence_in"},
        # MB → steering (associative memory)
        {"type": "topographic_mapping",
         "from": "mushroom_body_associative_memory_unit.memory_trace",
         "to": "central_complex_steering_unit.assoc_mem_in"},
        # Heading → steering
        {"type": "feedforward_excitatory",
         "from": "central_complex_heading_unit.heading_out",
         "to": "central_complex_steering_unit.heading_in"},
    ]
    return compose_from_units(units, conns,
                              name="hierarchical_pipeline_composed")


def composition_reciprocal_feedback():
    """reciprocal_feedback：多单元间的双向/回环电路。

    生物学参照：中央复合物的双向回路——antennal_lobe_central_complex_feedback_unit
    天然就是"反馈"型单元（OUT 有 heading_set 和 steering_out），与
    antennal_lobe_glomerular_unit 形成前馈 + 反馈双通路，再由
    mushroom_body_associative_memory_unit 学习并反馈给 steering。

    edges:
      A. feedforward: antennal_lobe → central_complex_feedback (sensory.olfactory)
      B. feedforward: antennal_lobe → mushroom_body_assoc_memory (via sparse_code)
      C. feedback:    central_complex_feedback.heading_set → steering_unit.heading_in
      D. feedback:    mushroom_body_assoc_memory.learned_valence → steering_unit.valence_in
      E. feedback loop: steering_unit.turn_cmd → central_complex_feedback.heading_in
    """
    units = [
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "antennal_lobe_central_complex_feedback_unit", "instances": 1},
        {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
    ]
    conns = [
        # A: AAL → feedback_unit (odour input)
        {"type": "feedforward_excitatory",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "antennal_lobe_central_complex_feedback_unit.odour_in"},
        # B: AAL → MB associative memory (sparse_code)
        {"type": "sparse_expansion_projection",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "mushroom_body_associative_memory_unit.sparse_code"},
        # C: feedback_unit → steering (heading)
        {"type": "topographic_mapping",
         "from": "antennal_lobe_central_complex_feedback_unit.heading_set",
         "to": "central_complex_steering_unit.heading_in"},
        # D: MB → steering (valence)
        {"type": "modulatory_gated_plasticity",
         "from": "mushroom_body_associative_memory_unit.learned_valence",
         "to": "central_complex_steering_unit.valence_in"},
        # E: feedback loop — steering output back to feedback_unit
        {"type": "feedback_excitatory",
         "from": "central_complex_steering_unit.turn_cmd",
         "to": "antennal_lobe_central_complex_feedback_unit.heading_in"},
    ]
    return compose_from_units(units, conns,
                              name="reciprocal_feedback_composed")


# =========================================================================== #
# 汇总所有组合
# =========================================================================== #

ALL_COMPOSITIONS = {
    "olfactory_to_steering":  composition_olfactory_to_steering,
    "visual_to_escape":       composition_visual_to_escape,
    "gustatory_to_motion":    composition_gustatory_to_motion,
    "tree_fanout":            composition_tree_fanout,
    "converging_funnel":      composition_converging_funnel,
    "hierarchical_pipeline":  composition_hierarchical_pipeline,
    "reciprocal_feedback":    composition_reciprocal_feedback,
}

NEW_COMPOSITIONS = ["tree_fanout", "converging_funnel",
                    "hierarchical_pipeline", "reciprocal_feedback"]
CHAINED_COMPOSITIONS = ["olfactory_to_steering", "visual_to_escape",
                        "gustatory_to_motion"]


# =========================================================================== #
# 单拓扑的度量采集
# =========================================================================== #

def measure_one_composition(comp_name, total_N, n_seeds, seed_offset=0):
    """Build composition W and measure all 4 metrics."""
    fn = ALL_COMPOSITIONS[comp_name]
    composition = fn()
    ok = composition["validation"]["ok"]
    n_edges = len(composition["organism"]["edges"])
    n_nodes = len(composition["organism"]["nodes"])

    if not ok:
        return {
            "composition": comp_name, "N": total_N,
            "validation_ok": False,
            "errors": composition["validation"].get("errors", []),
            "n_nodes": n_nodes, "n_edges": n_edges,
        }

    W, edges_placed, _ = build_composed_topology(
        composition, total_N, seed=42, noise_scale=0.5)

    mem_r2, eff_depth = measure_memory_depth(
        W, delays=(4, 8, 12, 16, 20, 30, 40, 60), rho=0.7,
        leakage=0.90, n_seeds=n_seeds)

    conv90 = measure_convergence_90(W, rho=0.7, leakage=0.90, n_seeds=n_seeds)
    lat = measure_reaction_latency(W, rho=0.7, leakage=0.90, n_seeds=n_seeds)
    narma = task_narma10(W, T=1500, n_seeds=n_seeds, alpha=1e-3,
                         seed_offset=seed_offset)

    return {
        "composition": comp_name,
        "N": total_N,
        "validation_ok": True,
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "edges_placed": edges_placed,
        "memory_eff_depth": int(eff_depth),
        "memory_r2_60": mem_r2.get(60, float("nan")),
        "convergence_90": float(conv90) if not np.isnan(conv90) else None,
        "reaction_latency": float(lat) if not np.isnan(lat) else None,
        "narma10_mse": narma.get("narma10", float("inf")),
    }


# =========================================================================== #
# Welch t + Cohen's d（复用现有实现）
# =========================================================================== #

def _normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def welch_cohens_d(a, b, higher_is_better=True):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 3 or len(b) < 3:
        return {"t": float("nan"), "p": float("nan"),
                "d": float("nan"), "mean_a": float("nan"),
                "mean_b": float("nan"), "n_a": len(a), "n_b": len(b)}
    va, vb = a.var(ddof=1), b.var(ddof=1)
    denom = math.sqrt(va / len(a) + vb / len(b))
    if denom < 1e-12:
        pooled = math.sqrt(((va + vb) / 2) or 1e-12)
        d = (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0
        return {"t": float("nan"), "p": 0.0, "d": float(d),
                "mean_a": a.mean(), "mean_b": b.mean(),
                "n_a": len(a), "n_b": len(b)}
    t = (a.mean() - b.mean()) / denom
    p = 2 * (1 - _normal_cdf(abs(t)))
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) /
                       (len(a) + len(b) - 2))
    d = (a.mean() - b.mean()) / pooled if pooled > 1e-12 else 0.0
    if not higher_is_better:
        d = -d
    return {"t": t, "p": float(p), "d": float(d),
            "mean_a": float(a.mean()), "mean_b": float(b.mean()),
            "n_a": len(a), "n_b": len(b)}


# =========================================================================== #
# 显著性：per-seed 结果收集 + Welch
# =========================================================================== #

def _measure_memory_depth_per_seed(W, delays=(4, 8, 12, 16, 20, 30, 40, 60),
                                   rho=0.7, leakage=0.90,
                                   n_seeds=10, seed_base=20260925):
    """Return per-seed eff_depth array."""
    try:
        s_max = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return []
    if s_max < 1e-12:
        return []
    Wc = W / s_max * rho
    N = W.shape[0]
    per_seed = []
    for s in range(n_seeds):
        seed = seed_base + s * 17
        rng = np.random.default_rng(seed)
        best_depth = 0
        for delay in delays:
            T = 500 + 8 * delay
            n_train = int(T * 0.6)
            n_test = T - n_train
            X = rng.uniform(-1, 1, (T, 1))
            Win = rng.normal(0, 1, size=(N, 1))
            bias = rng.normal(0, 0.5, size=(N,))
            x = np.zeros(N)
            S = np.zeros((T, N))
            for t in range(T):
                x = leakage * np.tanh(Wc @ x + Win @ X[t] + bias)
                S[t] = x
            y = X[:, 0].copy()
            y_shifted = np.zeros_like(y)
            y_shifted[:delay] = y[0]
            y_shifted[delay:] = y[:-delay]
            S_tr, S_te = S[:n_train - delay], S[n_train - delay:n_train - delay + n_test]
            y_tr, y_te = y_shifted[delay:n_train], y_shifted[n_train:n_train + n_test]
            if len(S_tr) < 20 or len(S_te) < 10:
                continue
            S_tr_aug = np.hstack([np.ones((S_tr.shape[0], 1)), S_tr])
            S_te_aug = np.hstack([np.ones((S_te.shape[0], 1)), S_te])
            lam = 1e-3 * S_tr_aug.shape[1]
            W_out = np.linalg.solve(S_tr_aug.T @ S_tr_aug + lam * np.eye(S_tr_aug.shape[1]),
                                    S_tr_aug.T @ y_tr)
            y_pred = S_te_aug @ W_out
            ss_res = float(np.sum((y_te - y_pred) ** 2))
            ss_tot = float(np.sum((y_te - y_te.mean()) ** 2))
            r2 = 1 - ss_res / ss_tot if ss_tot > 1e-12 else float("nan")
            if r2 > 0.5 and delay > best_depth:
                best_depth = delay
        per_seed.append(best_depth)
    return per_seed


def _task_narma10_per_seed(W, T=1500, n_seeds=10, alpha=1e-3,
                           seed_offset=0):
    """Return per-seed NARMA-10 MSE."""
    from external_benchmark_experiment import run_reservoir_full, ridge_solve, mse
    per_seed = []
    for s in range(n_seeds):
        base = 20260925 + seed_offset
        rng = np.random.default_rng(base + s * 101)
        x_in = rng.uniform(-2, 2, T + 10)
        y_out = np.zeros(T)
        for i in range(1, T):
            y_out[i] = (0.3 * y_out[i - 1]
                        - 0.05 * y_out[i - 1] * x_in[i + 1] * x_in[i + 2]
                        + x_in[i] + 1.5 * x_in[i])
        X = x_in[:T].reshape(-1, 1)
        S = run_reservoir_full(W, X, seed=base + s * 7)
        if S is None:
            continue
        cut = int(len(S) * 0.6)
        S_tr, S_te = S[:cut], S[cut:]
        y_tr, y_te = y_out[:cut], y_out[cut:]
        if cut < 100:
            continue
        y_pred = ridge_solve(S_tr, y_tr, S_te, y_te, alpha=alpha)
        per_seed.append(mse(y_pred.flatten(), y_te))
    return per_seed


# =========================================================================== #
# 主流程
# =========================================================================== #

def run_experiment(n_seeds, sizes=(60, 200), compositions=None):
    if compositions is None:
        compositions = list(ALL_COMPOSITIONS.keys())
    results = []
    t0 = time.time()
    for N in sizes:
        for cname in compositions:
            t1 = time.time()
            r = measure_one_composition(cname, N, n_seeds,
                                        seed_offset=N * 7)
            r["elapsed_s"] = round(time.time() - t1, 2)
            results.append(r)
            print("  [{}] N={:>4d} edges={} eff_depth={} conv90={} "
                  "latency={} narma10={:.4f} ({:.1f}s)".format(
                      cname, N, r.get("edges_placed", "-"),
                      r.get("memory_eff_depth", "-"),
                      r.get("convergence_90"),
                      r.get("reaction_latency"),
                      r.get("narma10_mse", float("nan")),
                      r["elapsed_s"]))
    total = time.time() - t0
    return results, total


def compare_new_vs_chained(all_results):
    """对每种非链式组合，找对应 N 下的链式均值，做 Welch t + Cohen's d。"""
    per_seed_data = {}
    # 重新构造 W 收集 per-seed
    for N in {r["N"] for r in all_results}:
        for cname in ALL_COMPOSITIONS:
            if not any(r["composition"] == cname and r["N"] == N
                       and r.get("validation_ok") for r in all_results):
                continue
            fn = ALL_COMPOSITIONS[cname]
            composition = fn()
            W, _, _ = build_composed_topology(composition, N, seed=42,
                                              noise_scale=0.5)
            md = _measure_memory_depth_per_seed(W, n_seeds=5)
            nm = _task_narma10_per_seed(W, n_seeds=5, seed_offset=N * 7)
            per_seed_data[(cname, N)] = {"memory": md, "narma10": nm}

    comparisons = []
    # 4 新拓扑 vs 3 链式的组均值（per-seed）
    for N in sorted({r["N"] for r in all_results}):
        new_names = [n for n in NEW_COMPOSITIONS
                     if (n, N) in per_seed_data]
        chained_names = [n for n in CHAINED_COMPOSITIONS
                         if (n, N) in per_seed_data]
        for metric_key, higher_is_better in [
                ("memory", True), ("narma10", False)]:
            for nn in new_names:
                for cn in chained_names:
                    a = np.array(per_seed_data[(nn, N)][metric_key], dtype=float)
                    b = np.array(per_seed_data[(cn, N)][metric_key], dtype=float)
                    stat = welch_cohens_d(a, b, higher_is_better=higher_is_better)
                    comparisons.append({
                        "N": N, "new": nn, "chained": cn,
                        "metric": metric_key,
                        **stat,
                    })
    return comparisons


def save(json_path, results, comparisons, elapsed_total):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "schema": "topology_capacity_results_v1",
            "n_seeds_per_metric": 5,
            "n_seeds_narma10": 5,
            "elapsed_s": elapsed_total,
            "compositions_measured": results,
            "comparisons_new_vs_chained": comparisons,
        }, f, indent=2, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="n_seeds=5 instead of 10")
    ap.add_argument("--sizes", default="60,200",
                    help="comma-separated N values")
    ap.add_argument("--out", default=None,
                    help="output JSON path")
    args = ap.parse_args()
    n_seeds = 5 if args.quick else 10
    sizes = tuple(int(x) for x in args.sizes.split(","))

    print("=" * 72)
    print("v2.12.0 Topology × Capacity experiment")
    print("  n_seeds per metric: {}".format(n_seeds))
    print("  N sizes: {}".format(sizes))
    print("  compositions: {}".format(list(ALL_COMPOSITIONS.keys())))
    print("=" * 72)

    results, elapsed_total = run_experiment(n_seeds, sizes)

    print()
    print("Running per-seed significance tests ...")
    comparisons = compare_new_vs_chained(results)

    # Summary
    print()
    print("-" * 72)
    print("SIGNIFICANT EFFECTS (|d|>=0.5 and p<0.05, no correction)")
    print("-" * 72)
    for c in comparisons:
        if np.isnan(c["p"]) or np.isnan(c["d"]):
            continue
        sig = "REAL_GAIN" if (abs(c["d"]) >= 0.5 and c["p"] < 0.05) else (
              "TREND" if (abs(c["d"]) >= 0.3 and c["p"] < 0.15) else "no_effect")
        print("  {} vs {} [N={}, {}]: d={:+.3f} p={:.4f} mean_new={:.4f} "
              "mean_chained={:.4f}  -> {}".format(
                  c["new"], c["chained"], c["N"], c["metric"],
                  c["d"], c["p"], c["mean_a"], c["mean_b"], sig))

    out_path = args.out or (HERE / "topology_capacity_results.json")
    save(out_path, results, comparisons, elapsed_total)
    print()
    print("Saved: {}".format(out_path))


if __name__ == "__main__":
    main()
