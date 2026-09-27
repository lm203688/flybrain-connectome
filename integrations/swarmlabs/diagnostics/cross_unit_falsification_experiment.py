"""v2.19.0 跨单元涌现反向实验 + 涌现规模阈值扫描。

背景
  v2.17 首次证实 mammal 组合（9 单元）在 NARMA-10 上有跨单元涌现（d=+0.54,
  p<0.0001 Bonferroni 存活）。v2.18 的边消融进一步证明「涌现不是边驱动，
  是多单元系统结构驱动」——0/10 边 CRITICAL，甚至部分边去掉后涌现更强。

  但 v2.18 只回答了「为什么涌现」的一半：**结构驱动 = 需要至少 9 个单元
  组合的系统**。这个结论留下了一个致命问题——

      「是不是任何 9 单元组合都涌现？」

  如果答案是「是」，那 mammal 涌现不是生物性的贡献，只是「9 单元系统」的
  规模效应——v2.17 的核心结论就必须撤回，改成「任意 ≥9 单元组合的规模
  涌现」。如果答案是「否」，mammal 涌现才是"生物结构独特"的证据。

  本实验设计两个对照：
    实验 A（反向证伪）：随机抽 9 单元组合 × 30 次 → 涌现率
    实验 B（规模扫描）：mammal 减到 8/7/6/5 单元 → 涌现阈值

显著性
  实验 A：30 次比较，Bonferroni α = 0.05/30 = 0.00167；|d|≥0.5 双阈值
  实验 B：4 个规模 × 1 指标 = 4 比较，Bonferroni α = 0.05/4 = 0.0125

诚实边界
  · 只测 NARMA-10（v2.17 唯一涌现指标）
  · N=60 与 v2.17 一致
  · n_seeds=50（v2.17/v2.18 已确认最低门槛）
  · 随机连接只用 pattern=*" 的 9 种通用连接类型，避开带端口 pattern 约束
    的类型（如 modulatory_diffuse 要求 from_port=modulatory.*）
  · 涌现度量沿用 v2.17：emergence = baseline_unit_mean - composed_MSE
    （正数=提效涌现）
  · baseline pool = 本脚本内直接跑 9 个 mammal 单元的 n=50 MSE，
    避免与 v2.18 N=200 结果的尺度不匹配

用法
  python cross_unit_falsification_experiment.py --quick     # n_seeds=5
  python cross_unit_falsification_experiment.py             # n_seeds=50
  python cross_unit_falsification_experiment.py --n-seeds 30
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


# =========================================================================== #
# 连接构造辅助
# =========================================================================== #

# 只用 pattern=*" 的通用连接类型（from_port / to_port 都是 "*"）。
# 带 pattern 约束的（如 modulatory_diffuse from_port=modulatory.*）会被
# 随机端口拒绝，触发 validation fail——本实验要最大化随机成功，只用这 9 种。
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
                          rng=random):
    """在 unit_names 之间构建兼容端口连接，最多 max_edges 条.

    返回 dict 列表，符合 compose_from_units._norm_conns 期望格式：
    {"from": "unitA.portA", "to": "unitB.portB", "type": "feedforward_excitatory"}
    """
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


def _edge_touches(spec_str, dropped_set):
    """判断一条边（字符串）的端点是否有任何一个单元被 dropped."""
    if ":" in spec_str:
        head, _ = spec_str.rsplit(":", 1)
    else:
        head = spec_str
    if "->" not in head:
        return True
    src, dst = head.split("->", 1)
    su = src.rsplit(".", 1)[0]
    du = dst.rsplit(".", 1)[0]
    return su in dropped_set or du in dropped_set


# =========================================================================== #
# 内联跑 mammal 单元 baseline（避免与 v2.18 N=200 结果混用）
# =========================================================================== #

def build_baseline_pool(n_seeds=50, N=60, units_index=None):
    """对 mammal 9 单元跑 build_unit_topology 得到 per-seed MSE 池."""
    if units_index is None:
        units_index = {u["name"]: u for u in load_units()["units"]}
    mammal_names = mammal_unit_names()
    pooled = []
    per_unit = {}
    for u_name in mammal_names:
        unit = units_index[u_name]
        W, _, _ = build_unit_topology(unit, N, seed=42, noise_scale=0.5)
        mse = _task_narma10_per_seed(W, n_seeds=n_seeds)
        mse = [float(x) for x in mse]
        per_unit[u_name] = mse
        pooled.extend(mse)
        print("  [BASELINE] {:<40s} mean={:.4f}".format(
            u_name, float(np.mean(mse))))
    arr = np.array(pooled, dtype=float)
    return arr, float(np.mean(arr)), per_unit


# =========================================================================== #
# 实验 A: 随机 9 单元组合（反向证伪）
# =========================================================================== #

def run_random_combinations(n_random=30, n_units_per_comp=9,
                            n_seeds=50, N=60,
                            baseline_pool_arr=None,
                            baseline_pool_mean=0.0,
                            seed=20260927):
    """跑 n_random 个随机 9 单元组合，测涌现率."""
    units_all = load_units()["units"]
    units_index = {u["name"]: u for u in units_all}
    all_unit_names = [u["name"] for u in units_all]
    rng = random.Random(seed)

    combos = []
    t0 = time.time()
    for i in range(n_random):
        picked = rng.sample(all_unit_names, n_units_per_comp)
        edges = build_compatible_edges(picked, units_index,
                                       max_edges=n_units_per_comp,
                                       rng=rng)
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
            entry["errors"] = errs[:5]
            combos.append(entry)
            print("  [RANDOM{:02d}] FAIL  ({})".format(
                i, errs[0][:70] if errs else "?"))
            continue

        t1 = time.time()
        try:
            W, edges_placed, _ = build_composed_topology(
                composed, N, seed=42, noise_scale=0.5)
        except Exception as e:
            entry["status"] = "build_failed"
            entry["error"] = str(e)[:200]
            combos.append(entry)
            print("  [RANDOM{:02d}] BUILD_FAIL  {}".format(i, e))
            continue

        mse_arr = np.array(
            _task_narma10_per_seed(W, n_seeds=n_seeds), dtype=float)
        composed_mean = float(np.nanmean(mse_arr))
        em = float(baseline_pool_mean) - composed_mean
        stat = welch_cohens_d(mse_arr, baseline_pool_arr,
                              higher_is_better=False)

        entry.update({
            "status": "ok",
            "edges_placed": int(edges_placed),
            "mse_mean": composed_mean,
            "mse_per_seed": [float(x) for x in mse_arr],
            "emergence": float(em),
            "welch_p": stat.get("p"),
            "welch_d": stat.get("d"),
            "elapsed_s": round(time.time() - t1, 2),
        })
        combos.append(entry)
        print("  [RANDOM{:02d}] ok  mse={:.4f}  em={:+.4f}  "
              "d={:+.2f}  p={:.4f}  ({:.1f}s)".format(
                  i, composed_mean, em,
                  stat.get("d") or 0,
                  stat.get("p") if stat.get("p") is not None else -1,
                  entry["elapsed_s"]))

    return {"combos": combos, "elapsed_s": round(time.time() - t0, 2)}


# =========================================================================== #
# 实验 B: mammal 规模扫描（9→5）
# =========================================================================== #

def run_size_sweep(sizes=(9, 8, 7, 6, 5), n_seeds=50, N=60,
                   baseline_pool_arr=None, baseline_pool_mean=0.0):
    """从 mammal 完整 9 单元逐次随机移除单元，测涌现是否保持."""
    all_mammal_edges = DEMO["connections"]  # 保留原始字符串形式

    sweep = []
    t0 = time.time()
    for size in sizes:
        mammal_names = mammal_unit_names()
        if size >= len(mammal_names):
            picked = mammal_names[:]  # full mammal
        else:
            rng = random.Random(20260927 + size)
            picked = sorted(rng.sample(mammal_names, size),
                            key=lambda x: mammal_names.index(x))
        dropped = set(mammal_names) - set(picked)
        picked_edges = [e for e in all_mammal_edges
                        if not _edge_touches(e, dropped)]

        spec = {"units": picked, "connections": picked_edges}
        composed = compose_from_units(spec["units"], spec["connections"],
                                      name="mammal_size{}".format(size))
        ok = composed["validation"]["ok"]
        entry = {
            "size": size,
            "units": picked,
            "n_edges_spec": len(picked_edges),
            "n_edges_spec_dropped": len(all_mammal_edges) - len(picked_edges),
            "validation_ok": bool(ok),
        }
        if not ok:
            entry["status"] = "validation_failed"
            entry["errors"] = composed["validation"].get("errors", [])[:5]
            sweep.append(entry)
            print("  [SIZE{:02d}] FAIL  ({})".format(
                size, entry["errors"][0][:70] if entry["errors"] else "?"))
            continue

        t1 = time.time()
        try:
            W, edges_placed, _ = build_composed_topology(
                composed, N, seed=42, noise_scale=0.5)
        except Exception as e:
            entry["status"] = "build_failed"
            entry["error"] = str(e)[:200]
            sweep.append(entry)
            print("  [SIZE{:02d}] BUILD_FAIL  {}".format(size, e))
            continue

        mse_arr = np.array(
            _task_narma10_per_seed(W, n_seeds=n_seeds), dtype=float)
        composed_mean = float(np.nanmean(mse_arr))
        em = float(baseline_pool_mean) - composed_mean
        stat = welch_cohens_d(mse_arr, baseline_pool_arr,
                              higher_is_better=False)

        entry.update({
            "status": "ok",
            "edges_placed": int(edges_placed),
            "mse_mean": composed_mean,
            "emergence": float(em),
            "welch_p": stat.get("p"),
            "welch_d": stat.get("d"),
            "elapsed_s": round(time.time() - t1, 2),
        })
        sweep.append(entry)
        print("  [SIZE{:02d}] ok  mse={:.4f}  em={:+.4f}  "
              "d={:+.2f}  p={:.4f}  ({:.1f}s)".format(
                  size, composed_mean, em,
                  stat.get("d") or 0,
                  stat.get("p") if stat.get("p") is not None else -1,
                  entry["elapsed_s"]))

    return {"sweep": sweep, "elapsed_s": round(time.time() - t0, 2)}


# =========================================================================== #
# 汇总
# =========================================================================== #

def summarize_random(random_results, alpha_bonf=0.05 / 30):
    combos_ok = [c for c in random_results["combos"]
                 if c.get("status") == "ok"]
    combos_fail = [c for c in random_results["combos"]
                   if c.get("status") != "ok"]
    emergent_count = sum(1 for c in combos_ok if c["emergence"] > 0)
    strong_emergent = sum(
        1 for c in combos_ok
        if c.get("welch_d") is not None and not np.isnan(c["welch_d"])
        and c["welch_d"] >= 0.5 and c.get("welch_p") is not None
        and not np.isnan(c["welch_p"]) and c["welch_p"] < alpha_bonf
    )
    em_arr = np.array([c["emergence"] for c in combos_ok], dtype=float)
    return {
        "n_random": len(random_results["combos"]),
        "n_ok": len(combos_ok),
        "n_fail": len(combos_fail),
        "n_emergent": emergent_count,
        "emergent_rate": (emergent_count / len(combos_ok)) if combos_ok else 0.0,
        "n_bonferroni_survives": strong_emergent,
        "bonferroni_survive_rate": (strong_emergent / len(combos_ok)) if combos_ok else 0.0,
        "em_mean": float(np.mean(em_arr)) if len(em_arr) else float("nan"),
        "em_min": float(np.min(em_arr)) if len(em_arr) else float("nan"),
        "em_max": float(np.max(em_arr)) if len(em_arr) else float("nan"),
        "em_median": float(np.median(em_arr)) if len(em_arr) else float("nan"),
        "alpha_bonferroni": alpha_bonf,
        "verdict": (
            "RANDOM_ALSO_EMERGENT" if emergent_count >= max(1, len(combos_ok) // 2)
            else "RANDOM_DOES_NOT_EMERGE"
        ),
    }


def summarize_sweep(sweep_results, alpha_bonf=0.05 / 5):
    entries = [s for s in sweep_results["sweep"] if s.get("status") == "ok"]
    out = []
    for e in entries:
        d = e.get("welch_d")
        p = e.get("welch_p")
        d_ok = d is not None and not np.isnan(d) and d >= 0.5
        p_ok = p is not None and not np.isnan(p) and p < alpha_bonf
        out.append({
            "size": e["size"],
            "mse_mean": e["mse_mean"],
            "emergence": e["emergence"],
            "welch_d": d,
            "welch_p": p,
            "bonferroni_survives": bool(d_ok and p_ok),
            "direction": "emergent" if e["emergence"] > 0 else "no_emergence",
        })
    # 涌现消失的阈值：找到从正涌现变为非涌现的最小 size
    threshold = None
    for i, e in enumerate(out):
        curr = e["emergence"] > 0
        if i > 0 and out[i - 1]["emergence"] > 0 and not curr:
            threshold = e["size"]
            break
    return {
        "alpha_bonferroni": alpha_bonf,
        "entries": out,
        "emergence_threshold_size": threshold,
    }


# =========================================================================== #
# main
# =========================================================================== #

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--n-seeds", type=int, default=50)
    ap.add_argument("--n-random", type=int, default=30)
    ap.add_argument("--sizes", type=str, default="9,8,7,6,5")
    ap.add_argument("--N", type=int, default=60)
    args = ap.parse_args()

    n_seeds = 5 if args.quick else args.n_seeds
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]

    print("[setup] computing mammal 9-unit baseline at N={} n_seeds={}".format(
        args.N, n_seeds))
    baseline_arr, baseline_mean, baseline_per_unit = build_baseline_pool(
        n_seeds=n_seeds, N=args.N)
    print("[baseline] pooled mean = {:.6f}  n={}".format(
        baseline_mean, len(baseline_arr)))

    print("\n=== EXPERIMENT A: Random 9-unit compositions ({} trials) ===".format(
        args.n_random))
    random_res = run_random_combinations(
        n_random=args.n_random,
        n_units_per_comp=9,
        n_seeds=n_seeds,
        N=args.N,
        baseline_pool_arr=baseline_arr,
        baseline_pool_mean=baseline_mean,
        seed=20260927,
    )
    summary_random = summarize_random(random_res)

    print("\n=== EXPERIMENT B: Mammal size sweep {} ===".format(sizes))
    sweep_res = run_size_sweep(
        sizes=tuple(sizes),
        n_seeds=n_seeds,
        N=args.N,
        baseline_pool_arr=baseline_arr,
        baseline_pool_mean=baseline_mean,
    )
    summary_sweep = summarize_sweep(sweep_res)

    print("\n=== VERDICTS ===")
    print("[A] Random 9-unit emergence: {}/{} ({:.0%})  Bonferroni survives: "
          "{}/{}  verdict={}".format(
              summary_random["n_emergent"], summary_random["n_ok"],
              summary_random["emergent_rate"],
              summary_random["n_bonferroni_survives"], summary_random["n_ok"],
              summary_random["verdict"]))
    if summary_random["n_ok"] > 0:
        print("    em range: [{:+.4f}, {:+.4f}]  median={:+.4f}  mean={:+.4f}".format(
            summary_random["em_min"], summary_random["em_max"],
            summary_random["em_median"], summary_random["em_mean"]))
    print("[B] Mammal size sweep:")
    for e in summary_sweep["entries"]:
        mark = "★" if e["bonferroni_survives"] else " "
        print("    {} size={:2d}  em={:+.4f}  d={:+.2f}  p={:.4f}  {}".format(
            mark, e["size"], e["emergence"],
            e["welch_d"] if e["welch_d"] is not None else float("nan"),
            e["welch_p"] if e["welch_p"] is not None else -1,
            e["direction"]))
    print("    emergence_threshold_size: {}".format(
        summary_sweep["emergence_threshold_size"]))

    out_path = HERE / ("cross_unit_falsification_quick.json" if args.quick
                       else "cross_unit_falsification_n50_results.json")
    payload = {
        "version": "2.19.0",
        "experiment": "cross_unit_falsification",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "config": {
            "n_random": args.n_random,
            "n_units_per_comp": 9,
            "n_seeds": n_seeds,
            "N": args.N,
            "metric": "narma10",
            "sizes": sizes,
            "conn_types_pool": list(_CONN_TYPES),
            "baseline_pool_n": int(len(baseline_arr)),
            "baseline_pool_mean": baseline_mean,
            "baseline_per_unit_mean": {
                u: float(np.mean(v)) for u, v in baseline_per_unit.items()
            },
        },
        "experiment_A": {"summary": summary_random, "raw": random_res},
        "experiment_B": {"summary": summary_sweep, "raw": sweep_res},
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print("\n[out] {}".format(out_path))


if __name__ == "__main__":
    main()
