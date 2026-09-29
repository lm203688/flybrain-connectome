"""v2.21.0 · 跨单元涌现反向实验 v3：反应速度（reaction_latency）维度。

背景
  用户核心目标：「像生物一样复杂+快速反应」。
  v2.17-v2.20 涌现链只在 MSE（准确度）和 conv90（收敛）上测过，
  结论：涌现是"任务依赖+规模效应"，生物学贡献=0，涌现链断。

  但**反应速度（reaction_latency）从未在跨单元层测过**——
  这是"快速反应"目标的直接度量，也是用户核心目标里唯一空白维度。

  现有度量接口：connectivity_topology_efficiency_experiment.
  measure_reaction_latency(W, ...) 度量"步输入后输出稳定所需步数"，
  已在单点拓扑层验证过（v2.8-v2.11），但未在跨单元层做涌现分析。

设计
  Part E1：4 个 DEMO 组合（insect/mammal/electrosensory/swim）×
         2 个 N（60/200），组合 vs 组成单元均值，n_seeds=50，
         Bonferroni α = 0.05 / 8。
  Part E2：30 随机 9 单元组合 vs 9 mammal 单元 baseline，
         N=60（对齐 v2.19 主结果规模），n_seeds=50，
         Bonferroni α = 0.05 / 30 ≈ 0.00167。

涌现方向
  latency 越低越好：
    emergence = mean(baseline_latency) - mean(composed_latency)
  正数 = 组合比 baseline 单元均值更快 = 涌现提效。

度量选择（方法学教训）
  · 主度量：convergence_90（step 到 90% asymptote 的步数，0-200 范围）
  · 不用 measure_reaction_latency（settle_thresh=0.02 过松、tanh 压缩
    后几乎立即稳定，n_seeds=5 quick 实测值域仅 {0, 0.2, 0.4, 0.6}，
    跨单元层无法分辨——v2.21 quick 首次跑已证伪）
  · convergence_90 在单点拓扑层（v2.11 connectivity_topology_efficiency_
    experiment）已验证跨 topology 可分辨

显著性
  welch_cohens_d(a=composed, b=baseline, higher_is_better=False)
  |d| ≥ 0.5 AND p < α_bonf。

诚实边界
  · 只测 1 个度量维度（latency）避免多重比较
  · E2 随机组合种子 seed=20260927（与 v2.19 完全一致，可直接对比同一批
    组合在不同维度上的涌现率，验证"涌现是不是 narma10 特有"）
  · measure_reaction_latency 内部已做 per-seed 平均，本实验在 n_seeds=50
    下取一次聚合值再进入统计——但为了 Welch t 需要 variance，
    这里改用 per-seed 版本
  · 若 mammal latency 涌现 → v2.20 定论后唯一可能存活的涌现维度
  · 若随机也涌现 → 涌现链彻底死
  · 若都不涌现 → "像生物一样快速反应"整体 fail-closed

用法
  python cross_unit_reaction_latency_experiment.py --quick         # n_seeds=5
  python cross_unit_reaction_latency_experiment.py                 # n_seeds=50
  python cross_unit_reaction_latency_experiment.py --n-random 20   # 缩减 E2
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

from functional_units import (  # noqa: E402
    compose_from_units, load_units,
    DEMO, DEMO_INSECT, DEMO_ESCAPE, DEMO_SWIM,
)
from multi_unit_benchmark_experiment import build_composed_topology  # noqa: E402
from unit_composition_experiment import build_unit_topology  # noqa: E402
from topology_capacity_experiment import welch_cohens_d  # noqa: E402
from connectivity_topology_efficiency_experiment import (  # noqa: E402
    measure_reaction_latency,
    measure_convergence_90,
)
from cross_unit_falsification_experiment import build_compatible_edges  # noqa: E402
from cross_unit_collaboration_experiment import units_of_composition  # noqa: E402


# =========================================================================== #
# Reaction latency · per-seed 版本
# =========================================================================== #

def _reaction_latency_per_seed(W, n_seeds=50, seed_offset=0):
    """Return per-seed reaction-latency array.

    度量策略：使用 measure_convergence_90 作为主度量（step input 到 90%
    asymptote 的步数，0-200 范围），而不是 measure_reaction_latency
    （后者 settle_thresh=0.02 过松、tanh 压缩后几乎立即稳定，分辨率
    仅 0/0.2/0.4/0.6，跨单元层无法分辨）。

    convergence_90 的分辨率 0-200 步，跨 topology 差异在 v2.11
    connectivity_topology_efficiency_experiment 已被验证可分辨。

    每次传 n_seeds=1，seed_base=base 得到单一 per-seed 样本。
    """
    latencies = []
    for s in range(n_seeds):
        base = 20260925 + seed_offset + s * 101
        try:
            lat = measure_convergence_90(W, n_seeds=1,
                                         seed_base=int(base))
        except Exception:
            lat = float("nan")
        if lat is None or (isinstance(lat, float) and np.isnan(lat)):
            latencies.append(float("nan"))
        else:
            latencies.append(float(lat))
    return np.array(latencies, dtype=float)


# =========================================================================== #
# 4 个跨单元组合
# =========================================================================== #

COMPOSITIONS = {
    "insect": DEMO_INSECT,
    "mammal": DEMO,
    "electrosensory": DEMO_ESCAPE,
    "swim": DEMO_SWIM,
}


# =========================================================================== #
# 单单元 baseline · latency
# =========================================================================== #

def _baseline_unit_latency(unit_name, N, n_seeds, seed_offset=0):
    """给单个单元构建 topology 并测 reaction_latency per-seed."""
    units_all = load_units()["units"]
    units_index = {u["name"]: u for u in units_all}
    unit = units_index.get(unit_name)
    if unit is None:
        raise KeyError("unit not found: {}".format(unit_name))
    try:
        W, _, _ = build_unit_topology(unit, N, seed=42, noise_scale=0.5)
    except Exception as e:
        return {"unit": unit_name, "build_error": str(e)[:120],
                "latency_per_seed": [], "latency_mean": float("nan")}
    arr = _reaction_latency_per_seed(W, n_seeds=n_seeds,
                                     seed_offset=seed_offset)
    valid = arr[~np.isnan(arr)]
    return {
        "unit": unit_name,
        "latency_per_seed": [float(x) for x in arr],
        "latency_mean": float(np.nanmean(arr)),
        "n_valid": int(len(valid)),
    }


# =========================================================================== #
# Part E1: 4 DEMO × 2 N · 组合 latency vs 组成单元均值 latency
# =========================================================================== #

def run_part_e1(n_seeds=50, sizes=(60, 200)):
    print("\n=== Part E1: 4 DEMO × 2 N, reaction_latency ===")
    units_index = {u["name"]: u for u in load_units()["units"]}
    results = []
    for cname, spec in COMPOSITIONS.items():
        unit_names = units_of_composition(spec)
        composed = compose_from_units(spec["units"], spec["connections"],
                                      name="demo_{}".format(cname))
        ok = composed["validation"]["ok"]
        if not ok:
            print("  [{}] SKIP composition validation failed".format(cname))
            continue
        for N in sizes:
            t0 = time.time()
            try:
                W, edges_placed, _ = build_composed_topology(
                    composed, N, seed=42, noise_scale=0.5)
            except Exception as e:
                print("  [{}] N={} BUILD_FAIL {}".format(cname, N, e))
                continue
            lat_arr = _reaction_latency_per_seed(W, n_seeds=n_seeds,
                                                seed_offset=N * 7)
            composed_mean = float(np.nanmean(lat_arr))

            # 组成单元均值 baseline：每个单元独立 W 独立测 latency
            unit_latencies = []
            unit_seeds = []
            for un in unit_names:
                ub = _baseline_unit_latency(un, N, n_seeds,
                                            seed_offset=N * 7)
                if ub["latency_per_seed"]:
                    unit_latencies.append(ub["latency_mean"])
                    unit_seeds.extend(ub["latency_per_seed"])

            baseline_mean = float(np.nanmean(unit_latencies))
            emergence = baseline_mean - composed_mean
            stat = welch_cohens_d(lat_arr, unit_seeds,
                                 higher_is_better=False)

            entry = {
                "composition": cname,
                "N": N,
                "n_units": len(unit_names),
                "edges_placed": int(edges_placed),
                "composed_latency_mean": composed_mean,
                "composed_latency_per_seed": [float(x) for x in lat_arr],
                "baseline_unit_latencies": dict(
                    zip(unit_names, unit_latencies)),
                "baseline_pool_mean": baseline_mean,
                "baseline_pool_n_seeds": len(unit_seeds),
                "emergence": float(emergence),
                "welch_p": stat.get("p"),
                "welch_d": stat.get("d"),
                "elapsed_s": round(time.time() - t0, 2),
            }
            results.append(entry)
            print("  [{:>13s}] N={:>3d} lat={:6.2f} base={:6.2f} "
                  "em={:+.2f} d={:+.2f} p={:.4f} ({:.1f}s)".format(
                      cname, N, composed_mean, baseline_mean, emergence,
                      stat.get("d") or 0,
                      stat.get("p") if stat.get("p") is not None else -1,
                      entry["elapsed_s"]))
    return {"results": results}


# =========================================================================== #
# Part E2: 30 随机 9 单元组合 vs mammal 9 单元 baseline
# =========================================================================== #

def run_part_e2(n_seeds=50, n_random=30, N=60,
                seed=20260927, sizes=(60,)):
    print("\n=== Part E2: 30 random 9-unit combos, reaction_latency ===")
    units_all = load_units()["units"]
    units_index = {u["name"]: u for u in units_all}
    all_unit_names = [u["name"] for u in units_all]
    rng = random.Random(seed)

    # 先把 mammal baseline 单元池 latency 算好（复用到所有 30 组合）
    mammal_units = units_of_composition(DEMO)
    print("  mammal baseline units ({}): {}".format(
        len(mammal_units), mammal_units))
    unit_latencies = []
    unit_seeds_pool = []
    for un in mammal_units:
        ub = _baseline_unit_latency(un, N, n_seeds)
        if ub["latency_per_seed"]:
            unit_latencies.append(ub["latency_mean"])
            unit_seeds_pool.extend(ub["latency_per_seed"])
            print("    unit={} latency={:.2f}  (n={})".format(
                un, ub["latency_mean"], ub["n_valid"]))
    baseline_pool_arr = np.array(unit_seeds_pool, dtype=float)
    baseline_pool_mean = float(np.nanmean(unit_latencies))
    print("  mammal baseline pool: mean={:.2f} n_seeds={}".format(
        baseline_pool_mean, len(unit_seeds_pool)))

    combos = []
    t0 = time.time()
    for i in range(n_random):
        picked = rng.sample(all_unit_names, 9)
        edges = build_compatible_edges(picked, units_index,
                                       max_edges=9, rng=rng)
        spec = {"units": picked, "connections": edges}
        composed = compose_from_units(spec["units"], spec["connections"],
                                      name="random9_{}".format(i))
        ok = composed["validation"]["ok"]
        errs = composed["validation"].get("errors", [])

        entry = {
            "idx": i,
            "units": picked,
            "n_edges_spec": len(edges),
            "n_nodes": len(composed["organism"]["nodes"]),
            "n_edges_organism": len(composed["organism"]["edges"]),
            "validation_ok": bool(ok),
        }

        if not ok:
            entry["status"] = "validation_failed"
            entry["errors"] = errs[:3]
            combos.append(entry)
            print("  [RAND{:02d}] VALIDATION_FAIL".format(i))
            continue

        t1 = time.time()
        try:
            W, edges_placed, _ = build_composed_topology(
                composed, N, seed=42, noise_scale=0.5)
        except Exception as e:
            entry["status"] = "build_failed"
            entry["error"] = str(e)[:200]
            combos.append(entry)
            print("  [RAND{:02d}] BUILD_FAIL {}".format(i, e))
            continue

        lat_arr = _reaction_latency_per_seed(W, n_seeds=n_seeds)
        composed_mean = float(np.nanmean(lat_arr))
        em = float(baseline_pool_mean) - composed_mean
        stat = welch_cohens_d(lat_arr, baseline_pool_arr,
                             higher_is_better=False)

        entry.update({
            "status": "ok",
            "edges_placed": int(edges_placed),
            "latency_mean": composed_mean,
            "latency_per_seed": [float(x) for x in lat_arr],
            "emergence": float(em),
            "welch_p": stat.get("p"),
            "welch_d": stat.get("d"),
            "elapsed_s": round(time.time() - t1, 2),
        })
        combos.append(entry)
        print("  [RAND{:02d}] lat={:6.2f} em={:+.2f} d={:+.2f} "
              "p={:.4f} ({:.1f}s)".format(
                  i, composed_mean, em,
                  stat.get("d") or 0,
                  stat.get("p") if stat.get("p") is not None else -1,
                  entry["elapsed_s"]))

    return {
        "n_random": len(combos),
        "mammal_units": mammal_units,
        "baseline_pool_mean": baseline_pool_mean,
        "baseline_pool_n_seeds": len(unit_seeds_pool),
        "combos": combos,
        "elapsed_s": round(time.time() - t0, 2),
    }


# =========================================================================== #
# Bonferroni 分析
# =========================================================================== #

def analyze_bonferroni(e1, e2, n_seeds):
    e1_alpha = 0.05 / 8          # 4 combos × 2 N
    e2_alpha = 0.05 / 30         # 30 random combos

    print("\n=== Bonferroni 分析 (α_E1={}, α_E2={:.5f}) ===".format(
        e1_alpha, e2_alpha))

    e1_survivors = []
    for r in e1["results"]:
        p = r.get("welch_p")
        d = r.get("welch_d")
        if p is None or d is None:
            continue
        survived = (d is not None and abs(d) >= 0.5
                    and p is not None and p < e1_alpha)
        r["bonferroni_survive"] = bool(survived)
        r["alpha"] = e1_alpha
        if survived:
            e1_survivors.append(r["composition"] + "_N" + str(r["N"]))

    e2_survivors = []
    e2_emergent = 0
    e2_total = 0
    for c in e2["combos"]:
        if c.get("status") != "ok":
            continue
        e2_total += 1
        p = c.get("welch_p")
        d = c.get("welch_d")
        if p is None or d is None:
            continue
        survived = abs(d) >= 0.5 and p < e2_alpha
        c["bonferroni_survive"] = bool(survived)
        c["alpha"] = e2_alpha
        if c.get("emergence", 0) > 0:
            e2_emergent += 1
        if survived:
            e2_survivors.append(c["idx"])

    print("  E1 Bonferroni survivors: {} / {}".format(
        e1_survivors, len(e1["results"])))
    print("  E2 Bonferroni survivors: {} / {} combos".format(
        e2_survivors, e2_total))
    print("  E2 emergence rate (em>0): {} / {} = {:.1%}".format(
        e2_emergent, e2_total,
        (e2_emergent / e2_total) if e2_total else 0))

    return {
        "e1_alpha": e1_alpha,
        "e2_alpha": e2_alpha,
        "e1_survivors": e1_survivors,
        "e2_survivors": e2_survivors,
        "e2_emergent_count": e2_emergent,
        "e2_total_ok": e2_total,
    }


# =========================================================================== #
# 主流程
# =========================================================================== #

def main():
    parser = argparse.ArgumentParser(
        description="v2.21.0 · 跨单元涌现反向实验 v3 · 反应速度维度")
    parser.add_argument("--quick", action="store_true",
                        help="n_seeds=5 快速验证")
    parser.add_argument("--n-seeds", type=int, default=50,
                        help="n_seeds (default 50)")
    parser.add_argument("--n-random", type=int, default=30,
                        help="E2 随机组合数 (default 30)")
    parser.add_argument("--output", type=str, default=None,
                        help="输出 JSON 路径")
    args = parser.parse_args()

    n_seeds = 5 if args.quick else args.n_seeds
    quick = args.quick
    out_path = args.output or str(HERE / (
        "cross_unit_reaction_latency_quick.json"
        if quick else "cross_unit_reaction_latency_results.json"))

    t0 = time.time()
    print("=" * 70)
    print("v2.21.0 · Cross-Unit Emergence on Reaction Latency")
    print("  n_seeds={}, quick={}, output={}".format(
        n_seeds, quick, out_path))
    print("=" * 70)

    # 跑 E1
    e1 = run_part_e1(n_seeds=n_seeds, sizes=(60, 200))

    # 跑 E2（N=60 对齐 v2.19/v2.20 主结果）
    e2 = run_part_e2(n_seeds=n_seeds, n_random=args.n_random, N=60,
                     seed=20260927)

    # Bonferroni
    bonf = analyze_bonferroni(e1, e2, n_seeds)

    # 汇总
    verdict = {
        "e1_mammal_emergent": None,
        "e2_any_bonferroni": bool(bonf["e2_survivors"]),
        "e2_emergence_rate": (
            bonf["e2_emergent_count"] / bonf["e2_total_ok"]
            if bonf["e2_total_ok"] else 0),
        "chain_status": None,
    }
    for r in e1["results"]:
        if r["composition"] == "mammal":
            verdict["e1_mammal_emergent"] = r.get("bonferroni_survive")

    if verdict["e1_mammal_emergent"]:
        verdict["chain_status"] = (
            "mammal reaction_latency 涌现，生物学结构确实带来更快反应")
    elif bonf["e2_survivors"]:
        verdict["chain_status"] = (
            "随机组合 latency 涌现，生物学贡献=0 进一步确认")
    elif bonf["e2_emergent_count"] == 0:
        verdict["chain_status"] = (
            "latency 维度全体无涌现，'快速反应'目标 fail-closed")
    else:
        verdict["chain_status"] = (
            "方向涌现但 Bonferroni 存活=0，与 v2.20 MSE 一致")

    results = {
        "version": "2.21.0",
        "n_seeds": n_seeds,
        "quick_mode": quick,
        "elapsed_s": round(time.time() - t0, 2),
        "e1_demos": e1,
        "e2_random": e2,
        "bonferroni": bonf,
        "verdict": verdict,
    }
    Path(out_path).write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n→ 写入 {}".format(out_path))
    print("\n>>> Verdict: {}".format(verdict["chain_status"]))
    return results


if __name__ == "__main__":
    main()
