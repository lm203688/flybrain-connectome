"""v2.20.0 · 跨单元涌现反向实验 v2：N=200 尺度 + conv90 度量。

背景
  v2.19 已在 N=60 narma10 上反向证伪 v2.17 的"mammal 独特涌现"结论——30 随机
  9 单元组合涌现率 50%，2/30 Bonferroni 存活，em magnitude 与 mammal 相当。

  但 v2.19 只测了单一 N=60 尺度、单一 narma10 指标。留下两个未回答问题：
    (1) **N=200 尺度**：v2.18 测得 mammal N=200 涌现 d=0.47（方向正但未过 |d|≥0.5）。
        随机 9 单元组合在 N=200 下涌现率是否仍是 50%？
        - 若仍 50%+ → v2.17 结论在所有规模上都是"规模效应"，无法复活。
        - 若降至 <20% → 更大规模下 mammal 才显现独特性（v2.17 部分复活）。
    (2) **conv90 度量**：v2.17/v2.18/v2.19 反复显示 conv90 全无涌现。
        随机 9 单元组合在 conv90 上是否也无涌现？

设计
  Experiment C (主)：N=200, 30 random 9-unit combos vs 9 mammal units baseline,
                     narma10, n_seeds=50.
  Experiment D (辅)：N=60, 同一 30 random 组合测 conv90 vs 9 mammal baseline conv90,
                     n_seeds=50.

显著性
  Experiment C: 30 combos × 1 metric = 30 comparisons, Bonferroni α = 0.05/30
  Experiment D: 30 combos × 1 metric = 30 comparisons, Bonferroni α = 0.05/30

诚实边界
  · 只测 mammal 一个"生物"组合（其他 3 组合无涌现，反证无意义）
  · 只测 30 随机组合（大样本会收敛到 50/50）
  · 涌现度量沿用 v2.17：emergence = baseline_unit_mean - composed_metric
    （正数=提效涌现；对 narma10 与 conv90 都适用，都是越低越好）
  · memory_depth 在 N=60 全部饱和 60（延拓上限），已跳过

用法
  python cross_unit_falsification_v2_experiment.py --quick           # n_seeds=5
  python cross_unit_falsification_v2_experiment.py                   # n_seeds=50
  python cross_unit_falsification_v2_experiment.py --n-random 20
"""
from __future__ import annotations

import argparse
import json
import random
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
from unit_composition_experiment import build_unit_topology  # noqa: E402
from topology_capacity_experiment import (  # noqa: E402
    _task_narma10_per_seed,
    welch_cohens_d,
)
from cross_unit_collaboration_experiment import (  # noqa: E402
    _measure_convergence_90_per_seed,
)


# =========================================================================== #
# 通用连接类型（复用 v2.19，避开带端口 pattern 约束的类型）
# =========================================================================== #

_CONN_TYPES = (
    "feedforward_excitatory",
    "feedforward_inhibitory",
    "feedback_excitatory",
    "feedback_inhibitory",
    "lateral_inhibitory",
    "recurrent_excitatory",
    "recurrent_inhibitory",
    "divergent_fanout",
    "convergent_fanin",
)


def build_compatible_edges(unit_names, units_index, max_edges=10,
                          rng=None):
    """在 unit_names 之间构建兼容端口连接，最多 max_edges 条."""
    if rng is None:
        rng = random
    edges = []
    tried = set()
    attempts = 0
    while len(edges) < max_edges and attempts < max_edges * 20:
        attempts += 1
        u_a = rng.choice(unit_names)
        u_b = rng.choice(unit_names)
        if u_a == u_b:
            continue
        key = (u_a, u_b)
        if key in tried:
            continue
        tried.add(key)
        ua = units_index.get(u_a)
        ub = units_index.get(u_b)
        if not ua or not ub:
            continue
        out_ports = ua.get("ports", {}).get("out", [])
        in_ports = ub.get("ports", {}).get("in", [])
        if not out_ports or not in_ports:
            continue
        op = rng.choice(out_ports)
        ip = rng.choice(in_ports)
        ct = rng.choice(_CONN_TYPES)
        edges.append({
            "from": "{}.{}".format(u_a, op["name"]),
            "to": "{}.{}".format(u_b, ip["name"]),
            "type": ct,
        })
    return edges


def mammal_unit_names():
    seen, out = set(), []
    for u in DEMO["units"]:
        n = u["unit"] if isinstance(u, dict) else u
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _generate_random_specs(n_random, n_units_per_comp=9, seed=20260927):
    """用固定 seed 生成 n_random 个 9 单元组合 spec（与 v2.19 完全对齐）."""
    units_all = load_units()["units"]
    units_index = {u["name"]: u for u in units_all}
    all_unit_names = [u["name"] for u in units_all]
    rng = random.Random(seed)
    specs = []
    for i in range(n_random):
        picked = rng.sample(all_unit_names, n_units_per_comp)
        edges = build_compatible_edges(picked, units_index,
                                       max_edges=n_units_per_comp, rng=rng)
        specs.append({"idx": i, "units": picked, "edges": edges})
    return specs, units_index


# =========================================================================== #
# Per-combination 度量入口
# =========================================================================== #

def measure_combination(spec, units_index, N, n_seeds,
                        metrics=("narma10", "conv90"), seed_offset=0):
    """给定一个 spec，返回 per-seed 度量字典."""
    composed = compose_from_units(spec["units"], spec["edges"],
                                  name="rand{}_{}".format(N, spec["idx"]))
    if not composed["validation"]["ok"]:
        return {"status": "validation_failed",
                "errors": composed["validation"].get("errors", [])[:5]}
    W, edges_placed, _ = build_composed_topology(
        composed, N, seed=42, noise_scale=0.5)
    out = {
        "status": "ok",
        "edges_placed": int(edges_placed),
        "n_nodes": len(composed["organism"]["nodes"]),
        "n_edges_organism": len(composed["organism"]["edges"]),
    }
    if "narma10" in metrics:
        mse = _task_narma10_per_seed(W, n_seeds=n_seeds)
        out["narma10"] = [float(x) for x in mse]
    if "conv90" in metrics:
        cv = _measure_convergence_90_per_seed(
            W, n_seeds=n_seeds, seed_base=20260927 + seed_offset)
        out["conv90"] = [float(x) if not np.isnan(x) else None for x in cv]
    return out


def measure_mammal_baseline(N, n_seeds, units_index=None,
                            metrics=("narma10", "conv90")):
    """跑 mammal 9 单元 baseline，返回 per-seed 池 + 单元均值."""
    if units_index is None:
        units_index = {u["name"]: u for u in load_units()["units"]}
    mammal_names = mammal_unit_names()
    pooled = {m: [] for m in metrics}
    per_unit = {}
    t0 = time.time()
    for u_name in mammal_names:
        unit = units_index[u_name]
        W, _, _ = build_unit_topology(unit, N, seed=42, noise_scale=0.5)
        per_unit[u_name] = {}
        if "narma10" in metrics:
            arr = _task_narma10_per_seed(W, n_seeds=n_seeds)
            arr = [float(x) for x in arr]
            per_unit[u_name]["narma10"] = arr
            pooled["narma10"].extend(arr)
        if "conv90" in metrics:
            arr = _measure_convergence_90_per_seed(W, n_seeds=n_seeds)
            arr = [float(x) if not np.isnan(x) else None for x in arr]
            per_unit[u_name]["conv90"] = arr
            pooled["conv90"].extend(
                [x for x in arr if x is not None])
        per_unit_means = {m: float(np.mean(v))
                          for m, v in per_unit[u_name].items()
                          if v and any(x is not None for x in v)}
        print("  [BASELINE] {:<40s} {}  ({:.1f}s)".format(
            u_name,
            " ".join("{:8s}={:.4f}".format(m, v) for m, v in per_unit_means.items()),
            time.time() - t0))
    return pooled, per_unit


# =========================================================================== #
# 汇总与 Bonferroni
# =========================================================================== #

def summarize_combinations(combos, metric, alpha_bonf,
                           baseline_pool_arr, baseline_pool_mean,
                           higher_is_better=False):
    """对每个 combination 做 Welch's t 检验（vs 单元池 baseline）。"""
    entries = []
    for c in combos:
        if c.get("status") != "ok":
            continue
        arr = [x for x in c.get(metric, [])
               if x is not None and not np.isnan(x)]
        if len(arr) < 2:
            entries.append({
                "idx": c["idx"], "units": c["units"],
                "status": "insufficient_data",
            })
            continue
        arr = np.array(arr, dtype=float)
        stat = welch_cohens_d(arr, baseline_pool_arr,
                              higher_is_better=higher_is_better)
        mean_c = float(np.mean(arr))
        em = float(baseline_pool_mean - mean_c)  # narma10/conv90 都是 lower better
        d = stat.get("d")
        p = stat.get("p")
        bonf_ok = (
            d is not None and not np.isnan(d)
            and p is not None and not np.isnan(p)
            and p < alpha_bonf
            and abs(d) >= 0.5
        )
        entries.append({
            "idx": c["idx"],
            "units": c["units"],
            "status": "ok",
            "metric": metric,
            "mean": mean_c,
            "emergence": em,
            "welch_p": p,
            "welch_d": d,
            "bonferroni_survives": bool(bonf_ok),
        })
    emergent_count = sum(1 for e in entries
                         if e.get("status") == "ok" and e.get("emergence", 0) > 0)
    strong_emergent = sum(1 for e in entries
                          if e.get("status") == "ok" and e.get("bonferroni_survives"))
    ems = [e["emergence"] for e in entries if e.get("status") == "ok"]
    return {
        "n_combos_ok": len([e for e in entries if e.get("status") == "ok"]),
        "n_emergent": emergent_count,
        "emergent_rate": (emergent_count / len(entries)) if entries else 0.0,
        "n_bonferroni_survives": strong_emergent,
        "bonferroni_survive_rate": (strong_emergent / len(entries)) if entries else 0.0,
        "em_mean": float(np.mean(ems)) if ems else float("nan"),
        "em_min": float(np.min(ems)) if ems else float("nan"),
        "em_max": float(np.max(ems)) if ems else float("nan"),
        "em_median": float(np.median(ems)) if ems else float("nan"),
        "alpha_bonferroni": alpha_bonf,
        "metric": metric,
    }


# =========================================================================== #
# main
# =========================================================================== #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--n-seeds", type=int, default=50)
    ap.add_argument("--n-random", type=int, default=30)
    ap.add_argument("--N", type=int, default=60)
    ap.add_argument("--N-conv90", type=int, default=60,
                    help="Experiment D 用的 N 值（默认 60）")
    ap.add_argument("--skip-conv90", action="store_true",
                    help="跳过 Experiment D (conv90)")
    ap.add_argument("--skip-narma10", action="store_true",
                    help="跳过 Experiment C (narma10)")
    args = ap.parse_args()

    n_seeds = 5 if args.quick else args.n_seeds

    print("=" * 70)
    print("v2.20.0 cross-unit emergence falsification v2")
    print("  N={}/{}  n_seeds={}  n_random={}".format(
        args.N, args.N_conv90, n_seeds, args.n_random))
    print("=" * 70)

    # 预生成 30 random specs（固定 seed 与 v2.19 对齐）
    specs, units_index = _generate_random_specs(
        args.n_random, n_units_per_comp=9, seed=20260927)
    print("\n[prep] generated {} random 9-unit specs at seed=20260927".format(
        len(specs)))

    results = {
        "version": "2.20.0",
        "experiment": "cross_unit_falsification_v2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "config": {
            "n_random": args.n_random,
            "n_seeds": n_seeds,
            "N_narma10": args.N,
            "N_conv90": args.N_conv90,
            "n_units_per_comp": 9,
            "seed": 20260927,
            "conn_types_pool": list(_CONN_TYPES),
        },
        "experiment_C": {},
        "experiment_D": {},
    }

    # ---- Experiment C: N=200 narma10 reverse ---- #
    if not args.skip_narma10:
        print("\n=== EXPERIMENT C: N={} narma10 reverse ({} random combos) ===".format(
            args.N, args.n_random))
        N_c = args.N
        t0 = time.time()
        print("[baseline] building mammal 9-unit baseline at N={}".format(N_c))
        pooled_c, per_unit_c = measure_mammal_baseline(
            N=N_c, n_seeds=n_seeds, units_index=units_index,
            metrics=("narma10",))
        baseline_arr_c = np.array(pooled_c["narma10"], dtype=float)
        baseline_mean_c = float(np.mean(baseline_arr_c))
        print("[baseline] N={} pooled mean narma10 = {:.6f}  n={}".format(
            N_c, baseline_mean_c, len(baseline_arr_c)))

        combos_c = []
        for i, spec in enumerate(specs):
            t1 = time.time()
            print("  [C-{}/{}] running N={} narma10...".format(
                i + 1, args.n_random, N_c))
            res = measure_combination(spec, units_index, N_c, n_seeds,
                                       metrics=("narma10",), seed_offset=0)
            res["idx"] = spec["idx"]
            res["units"] = spec["units"]
            res["N"] = N_c
            res["n_edges_spec"] = len(spec["edges"])
            res["elapsed_s"] = round(time.time() - t1, 2)
            combos_c.append(res)
            if res.get("status") == "ok":
                mse_arr = res.get("narma10", [])
                mean = float(np.mean(mse_arr)) if mse_arr else float("nan")
                print("    ok mse={:.4f}  em={:+.4f}  ({:.1f}s)".format(
                    mean, baseline_mean_c - mean, res["elapsed_s"]))
            else:
                print("    {}  {}".format(
                    res["status"],
                    res.get("errors", [""])[0][:60] if res.get("errors") else ""))

        summary_c = summarize_combinations(
            combos_c, metric="narma10", alpha_bonf=0.05 / args.n_random,
            baseline_pool_arr=baseline_arr_c,
            baseline_pool_mean=baseline_mean_c,
            higher_is_better=False,
        )
        results["experiment_C"] = {
            "N": N_c,
            "metric": "narma10",
            "baseline_pool_n": int(len(baseline_arr_c)),
            "baseline_pool_mean": baseline_mean_c,
            "baseline_per_unit_mean": {
                u: float(np.mean(v["narma10"]))
                for u, v in per_unit_c.items() if v.get("narma10")
            },
            "summary": summary_c,
            "combos": combos_c,
            "elapsed_s": round(time.time() - t0, 2),
        }
        print("\n[C] Summary: {}/{} emergent  {}/{} Bonferroni-survives".format(
            summary_c["n_emergent"], summary_c["n_combos_ok"],
            summary_c["n_bonferroni_survives"], summary_c["n_combos_ok"]))

    # ---- Experiment D: N=60 conv90 reverse ---- #
    if not args.skip_conv90:
        print("\n=== EXPERIMENT D: N={} conv90 reverse ({} random combos) ===".format(
            args.N_conv90, args.n_random))
        N_d = args.N_conv90
        t0 = time.time()
        print("[baseline] building mammal 9-unit baseline at N={}".format(N_d))
        pooled_d, per_unit_d = measure_mammal_baseline(
            N=N_d, n_seeds=n_seeds, units_index=units_index,
            metrics=("conv90",))
        baseline_arr_d = np.array(pooled_d["conv90"], dtype=float)
        baseline_mean_d = float(np.mean(baseline_arr_d))
        print("[baseline] N={} pooled mean conv90 = {:.6f}  n={}".format(
            N_d, baseline_mean_d, len(baseline_arr_d)))

        combos_d = []
        for i, spec in enumerate(specs):
            t1 = time.time()
            print("  [D-{}/{}] running N={} conv90...".format(
                i + 1, args.n_random, N_d))
            res = measure_combination(spec, units_index, N_d, n_seeds,
                                       metrics=("conv90",), seed_offset=1729)
            res["idx"] = spec["idx"]
            res["units"] = spec["units"]
            res["N"] = N_d
            res["n_edges_spec"] = len(spec["edges"])
            res["elapsed_s"] = round(time.time() - t1, 2)
            combos_d.append(res)
            if res.get("status") == "ok":
                cv_arr = res.get("conv90", [])
                valid = [x for x in cv_arr if x is not None]
                mean = float(np.mean(valid)) if valid else float("nan")
                print("    ok conv90={:.4f}  em={:+.4f}  ({:.1f}s)".format(
                    mean, baseline_mean_d - mean, res["elapsed_s"]))
            else:
                print("    {}  {}".format(
                    res["status"],
                    res.get("errors", [""])[0][:60] if res.get("errors") else ""))

        summary_d = summarize_combinations(
            combos_d, metric="conv90", alpha_bonf=0.05 / args.n_random,
            baseline_pool_arr=baseline_arr_d,
            baseline_pool_mean=baseline_mean_d,
            higher_is_better=False,
        )
        results["experiment_D"] = {
            "N": N_d,
            "metric": "conv90",
            "baseline_pool_n": int(len(baseline_arr_d)),
            "baseline_pool_mean": baseline_mean_d,
            "baseline_per_unit_mean": {
                u: float(np.mean([x for x in v["conv90"] if x is not None]))
                for u, v in per_unit_d.items()
                if v.get("conv90") and any(x is not None for x in v["conv90"])
            },
            "summary": summary_d,
            "combos": combos_d,
            "elapsed_s": round(time.time() - t0, 2),
        }
        print("\n[D] Summary: {}/{} emergent  {}/{} Bonferroni-survives".format(
            summary_d["n_emergent"], summary_d["n_combos_ok"],
            summary_d["n_bonferroni_survives"], summary_d["n_combos_ok"]))

    # ---- Final verdict ---- #
    print("\n" + "=" * 70)
    print("FINAL VERDICTS")
    print("=" * 70)
    if "experiment_C" in results and results["experiment_C"].get("summary"):
        c = results["experiment_C"]["summary"]
        print("C · N={} narma10 · emergent_rate={:.0%}  "
              "Bonferroni={}/{}  em_range=[{:+.4f},{:+.4f}]".format(
                  results["experiment_C"]["N"],
                  c["emergent_rate"],
                  c["n_bonferroni_survives"], c["n_combos_ok"],
                  c["em_min"], c["em_max"]))
    if "experiment_D" in results and results["experiment_D"].get("summary"):
        d = results["experiment_D"]["summary"]
        print("D · N={} conv90   · emergent_rate={:.0%}  "
              "Bonferroni={}/{}  em_range=[{:+.4f},{:+.4f}]".format(
                  results["experiment_D"]["N"],
                  d["emergent_rate"],
                  d["n_bonferroni_survives"], d["n_combos_ok"],
                  d["em_min"], d["em_max"]))

    out_path = HERE / ("cross_unit_falsification_v2_quick.json" if args.quick
                       else "cross_unit_falsification_v2_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\n[out] {}".format(out_path))


if __name__ == "__main__":
    main()
