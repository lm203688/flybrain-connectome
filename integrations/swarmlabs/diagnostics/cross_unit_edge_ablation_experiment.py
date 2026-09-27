"""v2.18.0 跨单元涌现的边消融实验。

背景
  v2.17.0 首次证实 mammal × NARMA-10 跨单元涌现（d=+0.54, p<0.0001）——
  9 个神经单元组合产生的 MSE 显著优于各单元单独跑。

  但那只回答了「是否涌现」，没有回答「为什么涌现」。生物学的核心问题是
  机制：哪些边支撑了涌现？如果去掉一条边涌现消失，那条边就是「涌现必需
  边」；如果全部去掉涌现都保持，那说明涌现来自单元本身的能力叠加，不是
  组合结构。

  本实验对 mammal 组合的 10 条边做 one-ablation-at-a-time：
    · 每条边去掉一次（9 条会剩下 9 条；剩下 9 条 → N=60 W 矩阵 → NARMA-10）
    · 计算 ablated MSE vs baseline 单元均值 → ablated_emergence
    · 与 full-mammal emergence（v2.17 的 +0.0061）比较
    · 消融后 emergence 显著下降 → 该边是「涌现关键边」

显著性
  每条边 1 次比较 → 10 次比较，Bonferroni α = 0.05/10 = 0.005
  与 v2.17 的 α=0.00625 类似严格度
  判据：|d| ≥ 0.5 AND p < 0.005

诚实边界
  · 只测 mammal 一个组合（v2.17 唯一涌现组合）——避免多重组合叠加混淆
  · 只测 NARMA-10 一个指标（v2.17 唯一涌现指标；conv90 全部无涌现）
  · N=60 与 v2.17 一致（不引入 N 维度混淆）
  · n_seeds=50 与 v2.17 一致（跨单元比较最低门槛 n≥50）
  · 复用 v2.17 n=50 结果里 mammal 的 per_seed baseline 数据做对照，
    避免重新跑 9 个单元 × 50 seeds

用法
  python cross_unit_edge_ablation_experiment.py --quick   # n=5 sanity
  python cross_unit_edge_ablation_experiment.py            # n=50 完整
  python cross_unit_edge_ablation_experiment.py --n-seeds 30
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

from functional_units import DEMO, compose_from_units, load_units  # noqa: E402
from multi_unit_benchmark_experiment import build_composed_topology  # noqa: E402
from topology_capacity_experiment import (  # noqa: E402
    _task_narma10_per_seed,
    welch_cohens_d,
)


EDGE_DESCRIPTIONS = [
    # E0 retinal → thalamic
    "retinal→thalamic relay（感觉→丘脑）",
    # E1 thalamic → L4
    "thalamic→L4（丘脑→初级皮层）",
    # E2 L4 → L2/3
    "L4→L2/3（皮层内上升）",
    # E3 L2/3 → L5
    "L2/3→L5（皮层内输出）",
    # E4 L5 → basal ganglia
    "L5→BG（皮层→基底节，动作选择）",
    # E5 BG → motor thalamus
    "BG→运动丘脑（动作→运动输出）",
    # E6 dopamine → BG
    "多巴胺→BG（调节性扩散）",
    # E7 L5 → cerebellum
    "L5→小脑（皮层→小脑，divergent_fanout）",
    # E8 cerebellum → motor thalamus
    "小脑→运动丘脑（小脑调节）",
    # E9 motor thalamus → L5 (feedback)
    "运动丘脑→L5（反馈环路）",
]


def build_ablated_composition(drop_edge_idx: int, N: int = 60):
    """去掉一条边，返回 (W, composed)."""
    connections = [
        c for i, c in enumerate(DEMO["connections"])
        if i != drop_edge_idx
    ]
    composed = compose_from_units(
        DEMO["units"],
        connections,
        name="mammal_ablation_E{}".format(drop_edge_idx),
    )
    W, edges_placed, ok = build_composed_topology(
        composed, N, seed=42, noise_scale=0.5,
    )
    return W, composed, edges_placed, ok


def load_v217_baselines():
    """从 v2.17 n=50 结果加载 mammal 的 9 个 baseline 单元 MSE per_seed 数据。"""
    path = HERE / "cross_unit_collaboration_n50_results.json"
    if not path.exists():
        path = HERE / "cross_unit_collaboration_results.json"
    d = json.load(open(path, "r", encoding="utf-8"))
    # meta 是 list；每个 entry 有 kind/name/per_seed
    meta = d.get("meta", [])
    mammal_member_names = set(units_of_mammal())
    baselines = []
    for e in meta:
        if e.get("kind") == "baseline" and e.get("name") in mammal_member_names:
            if e.get("status") == "ok":
                baselines.append(e)
    return baselines


def units_of_mammal():
    seen, out = set(), []
    for item in DEMO["units"]:
        name = item["unit"] if isinstance(item, dict) else item
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def run(n_seeds=50, N=60):
    """运行边消融实验。返回结果字典。"""
    t0 = time.time()
    baselines = load_v217_baselines()
    baseline_pooled = []
    for b in baselines:
        baseline_pooled.extend(b["per_seed"]["narma10"])
    baseline_arr = np.array(baseline_pooled, dtype=float)
    baseline_mean = float(np.mean(baseline_arr))
    print("[baseline] mammal 9 单元 n=50 pooled MSE = {:.6f}  "
          "(n_seeds_pooled={})".format(baseline_mean, len(baseline_arr)))
    if len(baselines) < 5:
        print("[warn] fewer than 5 baselines loaded — baseline may be incomplete")

    n_edges = len(DEMO["connections"])
    ablations = []

    for edge_idx in range(n_edges):
        desc = EDGE_DESCRIPTIONS[edge_idx] if edge_idx < len(EDGE_DESCRIPTIONS) else "E?"
        t1 = time.time()
        try:
            W, comp, edges_placed, ok = build_ablated_composition(edge_idx, N=N)
        except Exception as e:
            print("  E{:02d} FAILED: {}".format(edge_idx, e))
            ablations.append({
                "edge_idx": edge_idx,
                "edge_desc": desc,
                "status": "failed",
                "error": str(e)[:200],
            })
            continue

        # per-seed MSE
        mse_per_seed = _task_narma10_per_seed(W, n_seeds=n_seeds)
        mse_arr = np.array(mse_per_seed, dtype=float)
        ablation_mean = float(np.nanmean(mse_arr))

        # emergence: mean(baseline) - ablation_mse  (正数=涌现提效)
        ablation_emergence = baseline_mean - ablation_mean

        # 与 baseline 比较：ablation_mse vs baseline_pooled
        stat = welch_cohens_d(mse_arr, baseline_arr, higher_is_better=False)

        ablations.append({
            "edge_idx": edge_idx,
            "edge_desc": desc,
            "status": "ok",
            "validation_ok": bool(ok),
            "mse_mean": ablation_mean,
            "mse_per_seed": [float(x) for x in mse_arr],
            "ablation_emergence": float(ablation_emergence),
            "welch_p": stat.get("p"),
            "welch_d": stat.get("d"),
            "n_a": stat.get("n_a"),
            "n_b": stat.get("n_b"),
            "elapsed_s": round(time.time() - t1, 2),
            "edges_placed": int(edges_placed),
            "comp_nodes": len(comp["organism"]["nodes"]),
            "comp_edges": len(comp["organism"]["edges"]),
        })
        print("  E{:02d} mse={:.4f}  em={:+.4f}  d={:+.2f}  p={:.4f}  "
              "({:.1f}s)".format(
                  edge_idx, ablation_mean, ablation_emergence,
                  stat.get("d") or 0,
                  stat.get("p") if stat.get("p") is not None else -1,
                  ablations[-1]["elapsed_s"]))

    return {
        "n_edges": n_edges,
        "n_seeds": n_seeds,
        "N": N,
        "baseline_units": [b["name"] for b in baselines],
        "baseline_mean_mse": baseline_mean,
        "ablations": ablations,
        "elapsed_s": round(time.time() - t0, 2),
    }


def summarize(results, full_mammal_emergence=0.0061,
              full_mammal_d=0.54, full_mammal_p=5e-5):
    """产出关键边判定。"""
    n_edges = results["n_edges"]
    alpha_bonf = 0.05 / n_edges  # 10 边 = 0.005

    verdicts = []
    for a in results["ablations"]:
        if a.get("status") != "ok":
            verdicts.append({"edge_idx": a["edge_idx"], "status": a["status"]})
            continue

        em = a["ablation_emergence"]
        d = a["welch_d"]
        p = a["welch_p"]
        d_ok = d is not None and not np.isnan(d) and abs(d) >= 0.5
        p_ok = p is not None and not np.isnan(p) and p < alpha_bonf

        # 关键边：去掉后 emergence 掉到 <=0 或远低于 full 值
        critical_strong = (em <= 0.0)  # 直接反转到负涌现
        critical_moderate = (em < full_mammal_emergence * 0.5)  # 掉一半以上

        verdicts.append({
            "edge_idx": a["edge_idx"],
            "edge_desc": a["edge_desc"],
            "mse_mean": round(a["mse_mean"], 5),
            "ablation_emergence": round(em, 5),
            "emergence_vs_full_delta": round(em - full_mammal_emergence, 5),
            "welch_p": p,
            "welch_d": d,
            "bonferroni_survives": bool(d_ok and p_ok),
            "is_critical_strong": bool(critical_strong),
            "is_critical_moderate": bool(critical_moderate),
            "verdict": (
                "CRITICAL_STRONG" if critical_strong else
                "CRITICAL_MODERATE" if critical_moderate else
                "NOT_CRITICAL"
            ),
        })

    return {
        "alpha_bonferroni": alpha_bonf,
        "n_edges": n_edges,
        "n_comparisons": n_edges,
        "verdicts": verdicts,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="n_seeds=5 for fast sanity")
    ap.add_argument("--n-seeds", type=int, default=50)
    args = ap.parse_args()

    n_seeds = 5 if args.quick else args.n_seeds
    out_path = HERE / ("cross_unit_edge_ablation_quick.json"
                       if args.quick else "cross_unit_edge_ablation_n50_results.json")

    print("cross_unit_edge_ablation_experiment  n_seeds={} quick={}".format(
        n_seeds, args.quick))
    results = run(n_seeds=n_seeds)
    summary = summarize(results)

    # 关键边统计
    n_strong = sum(1 for v in summary["verdicts"]
                   if v.get("is_critical_strong"))
    n_moderate = sum(1 for v in summary["verdicts"]
                     if v.get("is_critical_moderate") and not v.get("is_critical_strong"))
    n_not = sum(1 for v in summary["verdicts"]
                if v.get("verdict") == "NOT_CRITICAL")
    print()
    print("=== 关键边判定 (n_seeds={}) ===".format(n_seeds))
    print("  CRITICAL_STRONG  (去掉后涌现消失): {} / {}".format(
        n_strong, summary["n_edges"]))
    print("  CRITICAL_MODERATE (掉一半以上):  {} / {}".format(
        n_moderate, summary["n_edges"]))
    print("  NOT_CRITICAL (去掉后涌现保持):   {} / {}".format(
        n_not, summary["n_edges"]))
    print()
    for v in summary["verdicts"]:
        if v.get("status"):
            print("  E{:02d}  STATUS={}".format(v["edge_idx"], v["status"]))
            continue
        mark = "★" if v["verdict"].startswith("CRITICAL") else " "
        print("  {} E{:02d}  {}  em={:+.4f}  d={:+.2f}  p={:.4f}  {}".format(
            mark, v["edge_idx"], v.get("edge_desc", "")[:30],
            v["ablation_emergence"],
            v.get("welch_d") or 0,
            v.get("welch_p") if v.get("welch_p") is not None else -1,
            v["verdict"]))

    payload = {
        "version": "2.18.0",
        "experiment": "cross_unit_edge_ablation",
        "target_composition": "mammal",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "config": {
            "n_edges": summary["n_edges"],
            "n_seeds": n_seeds,
            "N": 60,
            "metric": "narma10",
            "alpha_bonferroni": summary["alpha_bonferroni"],
        },
        "summary": summary,
        "raw": results,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print()
    print("[out] {}".format(out_path))
    print("[elapsed] {:.1f}s".format(results["elapsed_s"]))


if __name__ == "__main__":
    main()
