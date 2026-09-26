"""v2.13.0 Tree-fanout 变体精修实验。

背景
  v2.12.0 组合拓扑扩容实验发现 **tree_fanout 是唯一在 N=60→200 扩容下
  双维度（NARMA-10 MSE 与 convergence_90）都稳健的组合拓扑**：
  MSE 0.0621 → 0.0636，收敛 20.7 → 20.5 步。

  其他所有拓扑在扩容后要么精度退化（visual_to_escape -17%,
  hierarchical -13%），要么精度退但速度膨胀（reciprocal_feedback 收敛
  膨胀 3×，hierarchical 膨胀 50×），要么扩容严重退化（converging_funnel
  -22%）。

  本轮的核心问题：
  1. 这种"稳健性"是 tree_fanout 结构本身赋予的，还是偶然？
  2. 如果在 tree_fanout 基础上加更多生物性元素（侧向抑制 / 反馈 /
     下游链式延展 / 更宽的 fan-out），稳健性会不会保持？

  4 种变体设计（每个都是 tree_fanout 的最小增量扩展）：

  · tree_fanout_with_inhibition    tree_fanout + 下游侧向抑制边
  · tree_fanout_with_feedback      tree_fanout + 下游→hub 反馈边
  · tree_fanout_extended_chain     tree_fanout + 一条分支继续链式到 MB 记忆
  · wide_tree_fanout_5_downstream  1 hub → 5 下游（复用 arousal_out）

度量（复用 v2.12.0）
  memory_depth, convergence_90, reaction_latency, NARMA-10 MSE。

显著性
  Welch's t + Cohen's d（每个变体 vs 原 tree_fanout 参照，n_seeds=10）。

判定
  一个变体算"稳健"需要：
  · N=60 → N=200 的 NARMA-10 MSE 相对变化 < 20%
  · N=60 → N=200 的 convergence_90 相对变化 < 100%

用法
  python tree_fanout_variants_experiment.py              # N=60,200 n=10
  python tree_fanout_variants_experiment.py --quick      # N=60,200 n=5
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
    task_narma10,
)
from connectivity_topology_efficiency_experiment import (  # noqa: E402
    measure_memory_depth,
    measure_convergence_90,
    measure_reaction_latency,
)
from topology_capacity_experiment import (  # noqa: E402
    composition_tree_fanout,
    _measure_memory_depth_per_seed,
    _task_narma10_per_seed,
    welch_cohens_d,
)


# =========================================================================== #
# 4 种 tree_fanout 变体
# =========================================================================== #

def composition_tree_fanout_with_inhibition():
    """tree_fanout + 下游侧向抑制（cortical_l23 → inhibitory_gain）。

    生物学参照：皮层 L2/3 兴奋性输出驱动 GABA 中间神经元，中间神经元
    对下游做侧向抑制——这是"选择性放大"的经典机制。
    """
    units = [
        {"unit": "hypothalamic_arousal_unit", "instances": 1},
        {"unit": "cortical_l23_association_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "cortical_inhibitory_gain_unit", "instances": 1},
    ]
    conns = [
        # tree_fanout 3 条
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.arousal_out",
         "to": "cortical_l23_association_unit.gate"},
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.orexin_out",
         "to": "central_complex_steering_unit.orexin_in"},
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.histamine_out",
         "to": "antennal_lobe_glomerular_unit.histamine_in"},
        # 新增：L2/3 excitatory → inhibitory gain (cortex.association→cortex.association)
        {"type": "feedforward_excitatory",
         "from": "cortical_l23_association_unit.assoc_out",
         "to": "cortical_inhibitory_gain_unit.excitatory_drive"},
        # 新增：inhibitory gain → downstream lateral inhibition
        {"type": "lateral_inhibitory",
         "from": "cortical_inhibitory_gain_unit.inhibitory_tone",
         "to": "central_complex_steering_unit.speed_in"},
    ]
    return compose_from_units(units, conns,
                              name="tree_fanout_with_inhibition_composed")


def composition_tree_fanout_with_feedback():
    """tree_fanout + 下游→hub 反馈边（cc_steering → hypothalamic sleep_pressure）。

    生物学参照：下丘脑唤醒中心接收来自运动系统的反馈以调节觉醒水平。
    这是"前馈+反馈"的双通道结构。
    """
    units = [
        {"unit": "hypothalamic_arousal_unit", "instances": 1},
        {"unit": "cortical_l23_association_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
    ]
    conns = [
        # tree_fanout 3 条
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.arousal_out",
         "to": "cortical_l23_association_unit.gate"},
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.orexin_out",
         "to": "central_complex_steering_unit.orexin_in"},
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.histamine_out",
         "to": "antennal_lobe_glomerular_unit.histamine_in"},
        # 新增：steering output → hypothalamic sleep_pressure (feedback)
        {"type": "feedback_excitatory",
         "from": "central_complex_steering_unit.turn_cmd",
         "to": "hypothalamic_arousal_unit.sleep_pressure"},
    ]
    return compose_from_units(units, conns,
                              name="tree_fanout_with_feedback_composed")


def composition_tree_fanout_extended_chain():
    """tree_fanout + 嗅觉分支继续链式延展到 MB 稀疏码 → MB 联想记忆。

    生物学参照：下丘脑 histamine 调制到 AAL（触角叶）→ AAL 的 PN 投射到
    MB（蘑菇体）稀疏编码 → MB 联想记忆做 valence 学习 → 反馈给中央复合物
    转向。这是"树状扇出 + 一条分支深度延展"的真实果蝇回路。
    """
    units = [
        {"unit": "hypothalamic_arousal_unit", "instances": 1},
        {"unit": "cortical_l23_association_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "mushroom_body_sparse_code_unit", "instances": 1},
        {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
    ]
    conns = [
        # tree_fanout 3 条
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.arousal_out",
         "to": "cortical_l23_association_unit.gate"},
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.orexin_out",
         "to": "central_complex_steering_unit.orexin_in"},
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.histamine_out",
         "to": "antennal_lobe_glomerular_unit.histamine_in"},
        # 新增：AAL → MB sparse code (olfactory path extends)
        {"type": "sparse_expansion_projection",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "mushroom_body_sparse_code_unit.pn_in"},
        # 新增：MB sparse → MB associative memory
        {"type": "sparse_expansion_projection",
         "from": "mushroom_body_sparse_code_unit.sparse_out",
         "to": "mushroom_body_associative_memory_unit.sparse_code"},
        # 新增：MB learned valence → CC steering valence_in
        {"type": "modulatory_gated_plasticity",
         "from": "mushroom_body_associative_memory_unit.learned_valence",
         "to": "central_complex_steering_unit.valence_in"},
    ]
    return compose_from_units(units, conns,
                              name="tree_fanout_extended_chain_composed")


def composition_wide_tree_fanout_5_downstream():
    """wide_tree_fanout：1 hub 3 OUT → 5 下游（复用 arousal_out 分给 3 下游）。

    生物学参照：hypothalamic arousal 通路实际扇出到多个系统
    （皮层唤醒门控 / 胆碱能唤醒 / 皮层抑制控制）——同一个觉醒信号复用
    到多个异质下游。

    对比 4 下游的 tree_fanout，这里 5 下游 + 2 个下游共享 arousal_out。
    """
    units = [
        {"unit": "hypothalamic_arousal_unit", "instances": 1},
        {"unit": "cortical_l23_association_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "cholinergic_arousal_unit", "instances": 1},
        {"unit": "cortical_inhibitory_gain_unit", "instances": 1},
    ]
    conns = [
        # 3 arousal_out 复用（3 下游共享）
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.arousal_out",
         "to": "cortical_l23_association_unit.gate"},
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.arousal_out",
         "to": "cholinergic_arousal_unit.state_in"},
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.arousal_out",
         "to": "cortical_inhibitory_gain_unit.state"},
        # orexin_out → cc_steering
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.orexin_out",
         "to": "central_complex_steering_unit.orexin_in"},
        # histamine_out → antennal_lobe
        {"type": "divergent_fanout",
         "from": "hypothalamic_arousal_unit.histamine_out",
         "to": "antennal_lobe_glomerular_unit.histamine_in"},
    ]
    return compose_from_units(units, conns,
                              name="wide_tree_fanout_5_downstream_composed")


# =========================================================================== #
# 变体注册
# =========================================================================== #

VARIANT_COMPOSITIONS = {
    "tree_fanout_ref":                   composition_tree_fanout,
    "tree_fanout_with_inhibition":       composition_tree_fanout_with_inhibition,
    "tree_fanout_with_feedback":         composition_tree_fanout_with_feedback,
    "tree_fanout_extended_chain":        composition_tree_fanout_extended_chain,
    "wide_tree_fanout_5_downstream":     composition_wide_tree_fanout_5_downstream,
}

VARIANT_NAMES = [k for k in VARIANT_COMPOSITIONS if k != "tree_fanout_ref"]
REFERENCE = "tree_fanout_ref"


# =========================================================================== #
# 度量采集（复用 v2.12.0 的实现）
# =========================================================================== #

def measure_variant(name, total_N, n_seeds, seed_offset=0):
    fn = VARIANT_COMPOSITIONS[name]
    comp = fn()
    ok = comp["validation"]["ok"]
    errs = comp["validation"].get("errors", [])
    n_edges = len(comp["organism"]["edges"])
    n_nodes = len(comp["organism"]["nodes"])

    if not ok:
        return {"variant": name, "N": total_N, "validation_ok": False,
                "errors": errs, "n_nodes": n_nodes, "n_edges": n_edges}

    W, edges_placed, _ = build_composed_topology(
        comp, total_N, seed=42, noise_scale=0.5)

    mem_r2, eff_depth = measure_memory_depth(
        W, delays=(4, 8, 12, 16, 20, 30, 40, 60), rho=0.7,
        leakage=0.90, n_seeds=n_seeds)
    conv90 = measure_convergence_90(W, rho=0.7, leakage=0.90, n_seeds=n_seeds)
    lat = measure_reaction_latency(W, rho=0.7, leakage=0.90, n_seeds=n_seeds)
    narma = task_narma10(W, T=1500, n_seeds=n_seeds, alpha=1e-3,
                         seed_offset=seed_offset)

    return {
        "variant": name,
        "N": total_N,
        "validation_ok": True,
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "edges_placed": edges_placed,
        "memory_eff_depth": int(eff_depth),
        "convergence_90": float(conv90) if not np.isnan(conv90) else None,
        "reaction_latency": float(lat) if not np.isnan(lat) else None,
        "narma10_mse": narma.get("narma10", float("inf")),
    }


# =========================================================================== #
# 显著性：变体 vs 参照
# =========================================================================== #

def compare_variants(all_results, n_seeds=10):
    """对每个变体 × 每个尺寸，与参照 tree_fanout_ref 做 Welch t + d。"""
    per_seed = {}
    for N in {r["N"] for r in all_results}:
        for vname in VARIANT_COMPOSITIONS:
            if not any(r["variant"] == vname and r["N"] == N
                       and r.get("validation_ok") for r in all_results):
                continue
            comp = VARIANT_COMPOSITIONS[vname]()
            W, _, _ = build_composed_topology(comp, N, seed=42, noise_scale=0.5)
            per_seed[(vname, N)] = {
                "narma10": _task_narma10_per_seed(W, n_seeds=n_seeds,
                                                  seed_offset=N * 7),
                "memory": _measure_memory_depth_per_seed(W, n_seeds=n_seeds),
            }

    comparisons = []
    for N in sorted({r["N"] for r in all_results}):
        if (REFERENCE, N) not in per_seed:
            continue
        ref_narma = np.array(per_seed[(REFERENCE, N)]["narma10"], dtype=float)
        ref_mem = np.array(per_seed[(REFERENCE, N)]["memory"], dtype=float)
        for vname in VARIANT_NAMES:
            if (vname, N) not in per_seed:
                continue
            v_narma = np.array(per_seed[(vname, N)]["narma10"], dtype=float)
            v_mem = np.array(per_seed[(vname, N)]["memory"], dtype=float)
            comparisons.append({
                "N": N, "variant": vname, "reference": REFERENCE,
                "metric": "narma10",
                **welch_cohens_d(v_narma, ref_narma, higher_is_better=False),
            })
            comparisons.append({
                "N": N, "variant": vname, "reference": REFERENCE,
                "metric": "memory",
                **welch_cohens_d(v_mem, ref_mem, higher_is_better=True),
            })
    return comparisons


# =========================================================================== #
# 稳健性打分
# =========================================================================== #

def robustness_score(result_60, result_200, ref_60, ref_200):
    """打分：变体相对参照的稳健性。

    返回 (mse_ratio_delta, conv_ratio_delta, is_robust)
    · mse_ratio_delta = |mse_200 - mse_60| / mse_60  （<20% 算稳）
    · conv_ratio_delta = |conv_200 - conv_60| / max(conv_60, 1e-6)
    """
    if result_60 is None or result_200 is None:
        return (None, None, False)
    mse_60 = result_60["narma10_mse"]
    mse_200 = result_200["narma10_mse"]
    conv_60 = result_60["convergence_90"] or 0.1
    conv_200 = result_200["convergence_90"] or 0.1
    mse_ratio_delta = abs(mse_200 - mse_60) / mse_60
    conv_ratio_delta = abs(conv_200 - conv_60) / max(conv_60, 1e-6)
    is_robust = (mse_ratio_delta < 0.20) and (conv_ratio_delta < 1.00)
    return mse_ratio_delta, conv_ratio_delta, is_robust


# =========================================================================== #
# 主流程
# =========================================================================== #

def run_experiment(n_seeds, sizes=(60, 200)):
    results = []
    for N in sizes:
        for vname in VARIANT_COMPOSITIONS:
            t0 = time.time()
            r = measure_variant(vname, N, n_seeds, seed_offset=N * 7)
            r["elapsed_s"] = round(time.time() - t0, 2)
            results.append(r)
            print("  [{}] N={:>4d} edges={} eff_depth={} conv90={} "
                  "latency={} narma10={:.4f} ({:.1f}s)".format(
                      vname, N, r.get("edges_placed", "-"),
                      r.get("memory_eff_depth", "-"),
                      r.get("convergence_90"),
                      r.get("reaction_latency"),
                      r.get("narma10_mse", float("nan")),
                      r["elapsed_s"]))
    return results


def build_robustness_table(results):
    """生成稳健性对比表。"""
    ref_60 = next((r for r in results
                   if r["variant"] == REFERENCE and r["N"] == 60
                   and r.get("validation_ok")), None)
    ref_200 = next((r for r in results
                    if r["variant"] == REFERENCE and r["N"] == 200
                    and r.get("validation_ok")), None)

    table = []
    for vname in VARIANT_COMPOSITIONS:
        v_60 = next((r for r in results
                     if r["variant"] == vname and r["N"] == 60
                     and r.get("validation_ok")), None)
        v_200 = next((r for r in results
                      if r["variant"] == vname and r["N"] == 200
                      and r.get("validation_ok")), None)
        mse_delta, conv_delta, is_robust = robustness_score(
            v_60, v_200, ref_60, ref_200)
        table.append({
            "variant": vname,
            "mse_60": v_60["narma10_mse"] if v_60 else None,
            "mse_200": v_200["narma10_mse"] if v_200 else None,
            "conv_60": v_60["convergence_90"] if v_60 else None,
            "conv_200": v_200["convergence_90"] if v_200 else None,
            "mse_ratio_delta": mse_delta,
            "conv_ratio_delta": conv_delta,
            "is_robust": is_robust,
        })
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="n_seeds=5 instead of 10")
    ap.add_argument("--n-seeds", type=int, default=None,
                    help="override n_seeds (default 10; --quick sets to 5)")
    ap.add_argument("--sizes", default="60,200")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.n_seeds is not None:
        n_seeds = args.n_seeds
    else:
        n_seeds = 5 if args.quick else 10
    sizes = tuple(int(x) for x in args.sizes.split(","))

    print("=" * 72)
    print("v2.13.0 Tree-fanout variants experiment")
    print("  n_seeds: {}".format(n_seeds))
    print("  N sizes: {}".format(sizes))
    print("  variants: {}".format(list(VARIANT_COMPOSITIONS.keys())))
    print("=" * 72)

    t_start = time.time()
    results = run_experiment(n_seeds, sizes)

    print()
    print("Running per-seed significance tests ...")
    comparisons = compare_variants(results, n_seeds=n_seeds)

    print()
    print("-" * 72)
    print("Significance: variant vs tree_fanout_ref")
    print("-" * 72)
    for c in comparisons:
        if np.isnan(c["p"]) or np.isnan(c["d"]):
            continue
        if c["metric"] == "memory":
            continue  # memory depth 无区分度，跳过
        tag = ("WINNER" if c["d"] > 0.5 and c["p"] < 0.05 else
               "WORSE" if c["d"] < -0.5 and c["p"] < 0.05 else
               "TREND" if abs(c["d"]) > 0.3 and c["p"] < 0.15 else
               "no_effect")
        print("  {} vs ref [N={}, NARMA-10]: d={:+.3f} p={:.4f} "
              "var_mean={:.4f} ref_mean={:.4f}  -> {}".format(
                  c["variant"], c["N"], c["d"], c["p"],
                  c["mean_a"], c["mean_b"], tag))

    print()
    print("-" * 72)
    print("Robustness under N=60→200 scaling")
    print("-" * 72)
    table = build_robustness_table(results)
    for row in table:
        tag = "ROBUST" if row["is_robust"] else "DEGRADED"
        mse_delta = row["mse_ratio_delta"]
        conv_delta = row["conv_ratio_delta"]
        mse_delta_s = "N/A" if mse_delta is None else "{:+.1%}".format(mse_delta)
        conv_delta_s = "N/A" if conv_delta is None else "{:+.1%}".format(conv_delta)
        print("  {:40s} mse Δ={}  conv Δ={}  {}  (mse {:.4f}→{:.4f}, "
              "conv {:.1f}→{:.1f})".format(
                  row["variant"], mse_delta_s, conv_delta_s, tag,
                  row["mse_60"] or 0, row["mse_200"] or 0,
                  row["conv_60"] or 0, row["conv_200"] or 0))

    elapsed = time.time() - t_start
    out_path = args.out or (HERE / "tree_fanout_variants_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "schema": "tree_fanout_variants_results_v1",
            "n_seeds": n_seeds,
            "elapsed_s": round(elapsed, 2),
            "variants_measured": results,
            "comparisons_vs_ref": comparisons,
            "robustness_table": table,
        }, f, indent=2, ensure_ascii=False)
    print()
    print("Saved: {}".format(out_path))


if __name__ == "__main__":
    main()
