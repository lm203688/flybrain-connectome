"""v2.17.0 跨单元协作涌现实验。

背景
  v2.14 之后项目反复确认「更多边=更差」，但那些实验全部是「单单元+拓扑
  变体」——即把 motif 单元当成不可拆分的黑盒。用户 2026-09-27 明确重新锁
  核心目标：「像生物一样复杂+快速反应」，并追问三点：①最小功能模块是否
  全？②连接件/连接方式是否齐？③提效是否可验证？

  本轮直接对准这三点里最硬的一块：跨单元组合是否会**涌现**单单元所没有
  的能力。已有 4 个跨单元组合（DEMOS 里的 insect/mammal/electrosensory/
  swim），从未被真正测过「组合性能 vs 各组成单元单独性能」的对比。

  如果涌现，就是项目 17 个版本里第一个跨单元 emergent 正向证据。
  如果无涌现，就是 v2.15 结论的跨单元层级延伸——「组合不加东西只是
  搬运，不是提效」。两种结果都是 Bonferroni 校正下的方向级证据。

方法
  对每个组合 G（4 个）：
    1. 用 build_composed_topology 在 N=60 下跑出组合 W_G
    2. 对 G 里的每个单元 u_i 单独跑 build_unit_topology 在 N=60 下得到 W_u_i
    3. 度量：narma10 MSE（越低越好）、memory_eff_depth（越高越好）
    4. 涌现度量：
       · emergence_narma = mean(单单元 narma10) - 组合 narma10  >0 表示提效
       · emergence_memory = 组合 memory - mean(单单元 memory)  >0 表示增强

显著性
  对每个组合 × 每个指标，组合 vs 该组合内单单元均值做 Welch's t + Cohen's d。
  4 组合 × 2 指标 = 8 个比较，Bonferroni α = 0.05/8 = 0.00625。
  判据：|d| ≥ 0.5 AND p < 0.00625（比 v2.15 更严，因比较次数少）

诚实边界
  · N=60 与 v2.12/v2.13/v2.15 一致，不引入 N=200 变量避免混淆
  · n_seeds 默认 20（v2.15 教训：n_seeds<20 会样本偏差膨胀效应）
  · 只测 2 个「硬」指标（NARMA-10、memory_eff_depth）避免多重比较失控
  · 如果涌现但 |d|<0.5，明确写「方向存在但强度弱」，不宣称提效

用法
  python cross_unit_collaboration_experiment.py --quick   # n_seeds=5 验证
  python cross_unit_collaboration_experiment.py            # n_seeds=20
  python cross_unit_collaboration_experiment.py --n-seeds 50  # 完全确认
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

from functional_units import (  # noqa: E402
    compose_from_units, load_units,
    DEMO, DEMO_INSECT, DEMO_ESCAPE, DEMO_SWIM,
)
from multi_unit_benchmark_experiment import (  # noqa: E402
    build_composed_topology, task_narma10,
)
from unit_composition_experiment import build_unit_topology  # noqa: E402
from connectivity_topology_efficiency_experiment import (  # noqa: E402
    measure_memory_depth,
    measure_convergence_90,
    measure_reaction_latency,
)
from topology_capacity_experiment import (  # noqa: E402
    _task_narma10_per_seed,
    _measure_memory_depth_per_seed,
    welch_cohens_d,
)


# =========================================================================== #
# 4 个跨单元组合 + 各组合的组成单元（去重得 baseline 集合）
# =========================================================================== #

COMPOSITIONS = {
    "insect": DEMO_INSECT,       # 6 units, 6 conns — antennal_lobe → MB → CC → ...
    "mammal": DEMO,              # 9 units, 10 conns — thalamus → cortex → BG
    "electrosensory": DEMO_ESCAPE,  # 4 units, 3 conns — electroreception ↔ escape
    "swim": DEMO_SWIM,           # 3 units, 3 conns — leech → ascidian → frog
}


def units_of_composition(comp_spec: dict) -> list:
    """从 spec 抽取单元名列表（去重、按出现顺序）."""
    seen, out = set(), []
    for item in comp_spec["units"]:
        name = item["unit"] if isinstance(item, dict) else item
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


# =========================================================================== #
# Per-seed 度量（用于 Welch t 的原始样本）
# =========================================================================== #

def _measure_convergence_90_per_seed(W, rho=0.7, leakage=0.90,
                                     n_seeds=10, seed_base=20260925,
                                     max_steps=200):
    """Per-seed version of measure_convergence_90 — mirrors upstream impl."""
    N = W.shape[0]
    try:
        s_max = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return [float("nan")] * n_seeds
    if s_max < 1e-12:
        return [float("nan")] * n_seeds
    Wc = W / s_max * rho
    times = []
    for s in range(n_seeds):
        seed = seed_base + s * 29
        rng = np.random.default_rng(seed)
        T = 300
        X = np.zeros((T, 1))
        X[50:, 0] = 1.0
        X[:50, 0] += rng.normal(0, 0.05, 50)
        Win = rng.normal(0, 1, size=(N, 1))
        bias = rng.normal(0, 0.5, size=(N,))
        x = np.zeros(N)
        out = np.zeros(T)
        for t in range(T):
            x = leakage * np.tanh(Wc @ x + Win @ X[t] + bias)
            out[t] = x.mean()
        asymptote = out[-50:].mean()
        threshold = 0.9 * asymptote
        if abs(asymptote) < 0.01:
            times.append(max_steps)
            continue
        t_90 = None
        if asymptote > 0:
            for t in range(50, len(out)):
                if out[t] >= threshold:
                    t_90 = t - 50
                    break
        else:
            for t in range(50, len(out)):
                if out[t] <= threshold:
                    t_90 = t - 50
                    break
        times.append(t_90 if t_90 is not None else max_steps)
    return times


def per_seed_measures(W, n_seeds, seed_offset=0):
    """返回 dict with lists of per-seed metrics.

    N=60 下 memory_eff_depth 全部饱和在 60（延拓上限），无区分度。
    保留 memory 数据但不参与显著性比较；主比较指标 = narma10 + conv90。
    """
    return {
        "narma10": _task_narma10_per_seed(W, n_seeds=n_seeds,
                                          seed_offset=seed_offset),
        "conv90": _measure_convergence_90_per_seed(
            W, n_seeds=n_seeds, seed_base=20260925 + seed_offset),
        "memory": _measure_memory_depth_per_seed(W, n_seeds=n_seeds),
    }


# 显著性比较指标（memory 因饱和被排除）
SIG_METRICS = ("narma10", "conv90")


# =========================================================================== #
# 主流程：跑组合 + 各组成单元 baseline
# =========================================================================== #

def run_experiment(n_seeds, N=60, seed_offset=0):
    units_index = {u["name"]: u for u in load_units()["units"]}
    all_experiments = {}   # name -> {metrics per seed}
    meta = []

    # 1. 每个组合
    for cname, spec in COMPOSITIONS.items():
        comp = compose_from_units(spec["units"], spec["connections"],
                                  name=cname + "_cross_unit")
        ok = comp["validation"]["ok"]
        errs = comp["validation"].get("errors", [])
        n_nodes = len(comp["organism"]["nodes"])
        n_edges = len(comp["organism"]["edges"])
        member_units = units_of_composition(spec)

        entry = {
            "kind": "composition",
            "name": cname,
            "member_units": member_units,
            "validation_ok": ok,
            "errors": errs,
            "n_nodes": n_nodes,
            "n_edges": n_edges,
            "N": N,
            "n_seeds": n_seeds,
        }
        if not ok:
            entry["status"] = "validation_failed"
            meta.append(entry)
            continue

        t0 = time.time()
        W, edges_placed, _ = build_composed_topology(
            comp, N, seed=42, noise_scale=0.5)
        ms = per_seed_measures(W, n_seeds, seed_offset=seed_offset)
        entry["status"] = "ok"
        entry["edges_placed"] = edges_placed
        entry["narma10_mean"] = float(np.nanmean(ms["narma10"]))
        entry["conv90_mean"] = float(np.nanmean(ms["conv90"]))
        entry["memory_mean"] = float(np.nanmean(ms["memory"]))
        entry["per_seed"] = {
            "narma10": [float(x) for x in ms["narma10"]],
            "conv90": [float(x) for x in ms["conv90"]],
            "memory": [float(x) for x in ms["memory"]],
        }
        entry["elapsed_s"] = round(time.time() - t0, 2)
        print("  [COMPOSED] {:<14s} edges={} narma10={:.4f} conv90={:.2f} "
              "mem={:.2f} ({:.1f}s)".format(cname, edges_placed,
                                            entry["narma10_mean"],
                                            entry["conv90_mean"],
                                            entry["memory_mean"],
                                            entry["elapsed_s"]))
        all_experiments[cname] = entry
        meta.append(entry)

    # 2. 每个 baseline 单元（去重）
    all_baseline_names = sorted({u for spec in COMPOSITIONS.values()
                                 for u in units_of_composition(spec)})
    print("\n  [baselines] {} unique units".format(len(all_baseline_names)))

    for u_name in all_baseline_names:
        unit = units_index.get(u_name)
        if unit is None:
            print("  [BASELINE] {:<50s}  MISSING".format(u_name))
            continue
        entry = {
            "kind": "baseline",
            "name": u_name,
            "validation_ok": True,
            "n_nodes": 1,
            "n_edges": len(unit.get("internal_wiring", [])),
            "N": N,
            "n_seeds": n_seeds,
        }
        t0 = time.time()
        try:
            W, _, edges_placed = build_unit_topology(
                unit, N, seed=42, noise_scale=0.5)
            ms = per_seed_measures(W, n_seeds,
                                   seed_offset=seed_offset + 9973)
            entry["edges_placed"] = edges_placed
            entry["narma10_mean"] = float(np.nanmean(ms["narma10"]))
            entry["conv90_mean"] = float(np.nanmean(ms["conv90"]))
            entry["memory_mean"] = float(np.nanmean(ms["memory"]))
            entry["per_seed"] = {
                "narma10": [float(x) for x in ms["narma10"]],
                "conv90": [float(x) for x in ms["conv90"]],
                "memory": [float(x) for x in ms["memory"]],
            }
            entry["status"] = "ok"
        except Exception as e:
            entry["status"] = "failed"
            entry["error"] = str(e)[:200]
            print("  [BASELINE] {:<50s}  FAILED {}".format(u_name, e))
        entry["elapsed_s"] = round(time.time() - t0, 2)
        print("  [BASELINE] {:<50s}  narma10={:.4f} conv90={:.2f} mem={:.2f} "
              "({:.1f}s)".format(
                  u_name,
                  entry.get("narma10_mean", float("nan")),
                  entry.get("conv90_mean", float("nan")),
                  entry.get("memory_mean", float("nan")),
                  entry["elapsed_s"]))
        all_experiments[u_name] = entry
        meta.append(entry)

    return all_experiments, meta


# =========================================================================== #
# 涌现度量 + Bonferroni 校正显著性
# =========================================================================== #

def compute_emergence(all_experiments):
    """每个组合 vs 其成员单元均值做涌现度量 + Welch t + Bonferroni.

    显著性比较只用 SIG_METRICS（narma10 + conv90）—— N=60 下 memory
    全部饱和在 60，方差=0，任何 t 检验都是 NaN/0，没有信息量。
    """
    n_comps = len(COMPOSITIONS)
    n_metrics = len(SIG_METRICS)
    alpha_bonf = 0.05 / (n_comps * n_metrics)

    results = []
    for cname, spec in COMPOSITIONS.items():
        composed = all_experiments.get(cname)
        if not composed or composed.get("status") != "ok":
            results.append({
                "composition": cname, "status": "skip_composition_failed",
            })
            continue

        member_names = units_of_composition(spec)
        baselines = [all_experiments.get(u) for u in member_names]
        baselines = [b for b in baselines if b and b.get("status") == "ok"]
        if not baselines:
            results.append({
                "composition": cname, "status": "skip_no_baseline",
                "n_baselines": 0,
            })
            continue

        for metric in SIG_METRICS:
            comp_arr = np.array(composed["per_seed"][metric], dtype=float)
            baseline_pooled = []
            for b in baselines:
                baseline_pooled.extend(b["per_seed"][metric])
            base_arr = np.array(baseline_pooled, dtype=float)
            if len(base_arr) < 2:
                continue

            # higher_is_better: narma10 越低越好, conv90 越少步越快
            higher_is_better = False   # 两个指标都是"越低越好"
            stat = welch_cohens_d(comp_arr, base_arr,
                                  higher_is_better=higher_is_better)
            mean_comp = float(np.nanmean(comp_arr))
            mean_base = float(np.nanmean(base_arr))
            # 涌现：base - comp > 0 表示涌现提效（对"越低越好"）
            emergent = mean_base - mean_comp
            stat["composition"] = cname
            stat["metric"] = metric
            stat["n_composed_seeds"] = int(len(comp_arr))
            stat["n_baseline_pooled"] = int(len(base_arr))
            stat["n_baseline_units"] = len(baselines)
            stat["mean_composed"] = mean_comp
            stat["mean_baseline"] = mean_base
            stat["emergent_score"] = float(emergent)
            stat["direction"] = "emergent" if emergent > 0 else "no_emergence"
            stat["alpha_bonf"] = alpha_bonf
            p_val = stat.get("p")
            d_val = stat.get("d")
            stat["bonferroni_survives"] = bool(
                p_val is not None and not np.isnan(p_val)
                and p_val < alpha_bonf
                and d_val is not None and not np.isnan(d_val)
                and abs(d_val) >= 0.5
            )
            results.append(stat)

    return {
        "alpha_bonferroni": alpha_bonf,
        "n_comparisons": n_comps * n_metrics,
        "metrics_used": list(SIG_METRICS),
        "results": results,
    }


# =========================================================================== #
# CLI
# =========================================================================== #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="n_seeds=5 for fast sanity check")
    ap.add_argument("--n-seeds", type=int, default=20)
    ap.add_argument("--N", type=int, default=60)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    n_seeds = 5 if args.quick else args.n_seeds
    out_path = Path(args.out) if args.out else HERE / (
        "cross_unit_collaboration_quick.json" if args.quick
        else ("cross_unit_collaboration_results.json" if n_seeds != 50
              else "cross_unit_collaboration_n50_results.json"))

    print("cross_unit_collaboration_experiment  N={} n_seeds={} quick={}".format(
        args.N, n_seeds, args.quick))

    t0 = time.time()
    all_experiments, meta = run_experiment(n_seeds, N=args.N)
    emergence = compute_emergence(all_experiments)

    output = {
        "config": {
            "N": args.N,
            "n_seeds": n_seeds,
            "quick": args.quick,
            "compositions": list(COMPOSITIONS.keys()),
        },
        "meta": meta,
        "emergence": emergence,
        "elapsed_total_s": round(time.time() - t0, 2),
    }
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print("\n  wrote {}  total {:.1f}s".format(out_path.name,
                                               output["elapsed_total_s"]))

    # summary
    print("\n=== emergence summary ===")
    for r in emergence["results"]:
        if r.get("status", "").startswith("skip"):
            print("  {:<14s}  SKIP ({})".format(r["composition"], r["status"]))
            continue
        d = r.get("d") or 0
        p = r.get("p")
        pstr = "{:.4f}".format(p) if p is not None and not np.isnan(p) else "NaN"
        dstr = "{:+.2f}".format(d) if d is not None and not np.isnan(d) else "NaN"
        mark = "★ BONUS" if r.get("bonferroni_survives") else ""
        print("  {:<14s} {:<8s}  emergent={:+.4f}  d={}  p={}  {}"
              .format(r["composition"], r["metric"],
                      r["emergent_score"], dstr, pstr, mark))

    survivors = [r for r in emergence["results"]
                 if r.get("bonferroni_survives")]
    print("\n  Bonferroni survivors (|d|>=0.5 & p<{:.4f}): {}"
          .format(emergence["alpha_bonferroni"], len(survivors)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
