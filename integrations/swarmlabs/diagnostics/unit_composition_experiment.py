"""v2.5.0 单元组合拓扑实验 —— G1 单元回灌引擎。

背景
  v2.4.0 之前所有 diagnostics 都跑在 design_organism 的「module_rep 层」
  （4-10 个模块代表节点，密度 0.002-0.023）；101 个功能单元一直躺在数据
  库，从未真正跑过 ESN 实验。本项目 Phase 3 已实测「结构精简」在锁定
  形态下随机搜索严格优于 GA，唯一可能翻盘的实验方向 = cell 级密化。
  本实验是首次让单元库直接参与引擎级实验。

方法
  对每个单元：members 按 count_ratio 缩放到 total_N 节点，internal_wiring
  的每条边按两端 count_ratio 均匀加权到 W 矩阵（保留 feedback/feedforward
  的原始权重语义）。得到「单元级 W」而不是「模块代表层 W」，密度显著更高。

对照臂
  Arm A — unit-composed W（本实验新增）
  Arm B — design_organism motif W（原 bio 先验，n_modules=4）
  Arm C — 匹配节点/边数的随机 W

指标
  1. delay-task R²（r2_score，delay ∈ {5, 10, 20}）
  2. 故障隔离率（模块关停 vs 随机关停）
  3. 谱半径稳定性（fault_isolation_experiment 里的 ρ 变化）

判定
  若 Arm A 在 R² 或故障隔离率上系统性优于 Arm B → 单元库回灌成立，
  说明 101 单元的 cell 级结构具备 Phase 3 未验证的潜力。
  若相近 → 单元库和 motif 在 ESN 层等价，需要更强的动力学任务或更大的
  cell 密化才能真正拉开。
  若更差 → 诚实登记，不宣称。

用法
  python unit_composition_experiment.py --quick   # 3 units × 3 delay × 10 seeds
  python unit_composition_experiment.py           # 6 units × 3 delay × 30 seeds
"""
import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP))
sys.path.insert(0, str(HERE))

from dyn_calibration_probe import r2_score, random_W  # noqa: E402
from functional_units import load_units  # noqa: E402
from synthetic_bio_topology import design_organism, load_motifs  # noqa: E402


# --------------------------------------------------------------------------- #
# Unit-composed topology builder
# --------------------------------------------------------------------------- #
def build_unit_topology(unit: dict, total_N: int, seed: int = 42,
                        noise_scale: float = 0.5) -> tuple:
    """Map one functional unit onto an N×N weight matrix.

    - each member gets nodes proportional to count_ratio
    - each internal_wiring edge connects ALL source-member nodes to ALL
      target-member nodes with the base weight plus Gaussian perturbation
    - self-loops (from==to) are intra-member loops with the original weight

    Why noise_scale: dense uniform blocks (weight=w) are RANK-1, so a W
    made only of uniform blocks has singular rank ≤ #edges (~3-7), which
    collapses ESN dynamics — that's why the v2.5.0 initial test showed
    identical scores across arms. Adding Gaussian noise restores
    full-rank dynamics while preserving the block STRUCTURE.

    Returns (W, member_ranges, edge_count) where member_ranges maps
    member role -> (start, end) node-index slice.
    """
    members = unit["members"]
    ratios = np.array([m["count_ratio"] for m in members], dtype=float)
    ratios = ratios / ratios.sum()
    # integer assignment
    counts = np.floor(ratios * total_N).astype(int)
    remainder = total_N - int(counts.sum())
    for i in np.argsort(-ratios)[:remainder]:
        counts[i] += 1

    W = np.zeros((total_N, total_N))
    ranges = {}
    offset = 0
    for role_m, cnt in zip(members, counts):
        ranges[role_m["role"]] = (offset, offset + cnt)
        offset += cnt

    rng = np.random.default_rng(seed)
    edges_list = unit.get("internal_wiring", [])
    edges_placed = 0
    for e in edges_list:
        s_role, t_role = e["from"], e["to"]
        if s_role not in ranges or t_role not in ranges:
            continue
        s_lo, s_hi = ranges[s_role]
        t_lo, t_hi = ranges[t_role]
        w = float(e.get("weight", 1.0))
        s_len = s_hi - s_lo
        t_len = t_hi - t_lo
        # base weight + Gaussian perturbation to break rank-1 collapse
        perturbation = rng.normal(0, noise_scale, size=(s_len, t_len))
        W[s_lo:s_hi, t_lo:t_hi] += w + perturbation
        edges_placed += 1
    return W, ranges, edges_placed


# --------------------------------------------------------------------------- #
# Reference topologies
# --------------------------------------------------------------------------- #
def build_motif_topology(n_nodes=30, n_modules=4, seed=7) -> tuple:
    """Bio-prior topology (control B)."""
    motifs = load_motifs()
    doc = design_organism({
        "n_modules": n_modules,
        "agents_per_module": max(2, n_nodes // n_modules),
        "use_inhibitory_coordinator": True,
        "use_reservoir_buffer": True,
        "use_recurrent_memory": True,
        "recurrent_pct": 0.287,
    }, motifs, seed=seed)
    inner = doc["organism"]
    nodes, edges = inner["nodes"], inner["edges"]
    N = len(nodes)
    id_to_idx = {n["id"]: i for i, n in enumerate(nodes)}
    W = np.zeros((N, N))
    for e in edges:
        i = id_to_idx.get(e["from"])
        j = id_to_idx.get(e["to"])
        if i is not None and j is not None:
            W[i, j] = e.get("weight", 1.0)
    return W, len(edges)


def build_random_topology(n_nodes: int, n_edges: int, seed: int = 7) -> tuple:
    """Random topology matching node count and edge count (control C)."""
    rng = random.Random(seed)
    W = np.zeros((n_nodes, n_nodes))
    placed = 0
    while placed < n_edges:
        i = rng.randint(0, n_nodes - 1)
        j = rng.randint(0, n_nodes - 1)
        if i != j and W[i, j] == 0:
            W[i, j] = 1.0
            placed += 1
    return W, placed


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def measure_task_success(W, delay=5, rho=1.0, n_seeds=30, seed_base=20260924):
    N = W.shape[0]
    if N < 4:
        return 0.0, 0.0
    successes, r2s = 0, []
    for s in range(n_seeds):
        r2 = r2_score(W, delay=delay, rho=rho, leakage=0.95,
                      seed=seed_base + s)
        r2s.append(r2)
        if r2 > 0.5:
            successes += 1
    return successes / n_seeds, float(np.mean(r2s))


def measure_fault_isolation(W, n_modules=4, delay=5, rho=1.0,
                            n_seeds=20, seed_base=20260924):
    N = W.shape[0]
    if N < 4 or n_modules < 2:
        return 0.0, 0.0
    modules = [list(range(i, N, n_modules)) for i in range(n_modules)]
    baseline_r2 = r2_score(W, delay=delay, rho=rho, leakage=0.95,
                           seed=seed_base)
    h1 = 0
    effects = []
    for m_idx, module_nodes in enumerate(modules):
        W_ko = W.copy()
        for n in module_nodes:
            if n < N:
                W_ko[n, :] = 0
        ko_r2 = r2_score(W_ko, delay=delay, rho=rho, leakage=0.95,
                         seed=seed_base)
        rng = random.Random(seed_base + m_idx)
        W_rand = W.copy()
        rand_nodes = sorted(rng.sample(range(N), len(module_nodes)))
        for n in rand_nodes:
            W_rand[n, :] = 0
        rand_r2 = r2_score(W_rand, delay=delay, rho=rho, leakage=0.95,
                           seed=seed_base)
        if (baseline_r2 - ko_r2) < (baseline_r2 - rand_r2):
            h1 += 1
        effects.append(baseline_r2 - ko_r2)
    return h1 / n_modules, float(np.mean(effects))


def spectral_radius(W):
    try:
        s = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return 0.0
    return float(s)


# --------------------------------------------------------------------------- #
# Unit selection
# --------------------------------------------------------------------------- #
def pick_representative_units(units, quick=False):
    """Pick 3-6 embodied units covering different systems."""
    embodied = [u for u in units if u["provenance"].get("embodied_in_malecns")]
    # Curated list — pick one per distinct system for diversity
    targets = [
        "wing_flight_steering_unit",                    # motor
        "mushroom_body_lateral_horn_reciprocal_unit",   # olfactory learning
        "antennal_lobe_central_complex_feedback_unit",  # navigation
        "gustatory_centrifugal_unit",                   # chemosensory centrifugal
        "central_complex_steering_unit",                # steering
        "phototransduction_cascade_unit",               # vision
    ]
    by_name = {u["name"]: u for u in embodied}
    picked = [by_name[t] for t in targets if t in by_name]
    if quick:
        picked = picked[:3]
    return picked


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--n-nodes", type=int, default=30)
    ap.add_argument("--n-seeds", type=int, default=None)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    t0 = time.time()
    units = load_units()["units"]
    picked = pick_representative_units(units, quick=args.quick)
    if not picked:
        print("no embodied units found")
        return 1

    n_nodes = args.n_nodes
    n_seeds = args.n_seeds or (10 if args.quick else 30)
    delays = [3, 5] if not args.quick else [3]

    print(f"unit-composition experiment  n_nodes={n_nodes}  n_seeds={n_seeds}  "
          f"delays={delays}  quick={args.quick}")
    print(f"units under test ({len(picked)}):")
    for u in picked:
        print(f"  {u['name']:45s} members={len(u['members']):2d} "
              f"wiring={len(u['internal_wiring']):2d}")
    print()

    rows = []
    # ---- Arm D: textbook reservoir baseline (random Gaussian) ----
    W_textbook = random_W(n_nodes, seed=42)
    for d in delays:
        succ, r2 = measure_task_success(W_textbook, delay=d, n_seeds=n_seeds)
        fi, effect = measure_fault_isolation(W_textbook, n_modules=4, delay=d,
                                             n_seeds=n_seeds)
        rows.append({
            "arm": "textbook_random",
            "unit": "textbook_random",
            "N": W_textbook.shape[0],
            "density": float((W_textbook != 0).sum()) / (W_textbook.shape[0] ** 2),
            "rho_max": spectral_radius(W_textbook),
            "delay": d,
            "r2_mean": r2,
            "task_success": succ,
            "fault_isolation": fi,
            "fault_effect_pp": effect,
        })

    # ---- Arm B / C reference ----
    W_motif, e_motif = build_motif_topology(n_nodes=n_nodes, n_modules=4, seed=7)
    W_rand, e_rand = build_random_topology(n_nodes=W_motif.shape[0],
                                           n_edges=e_motif, seed=7)
    for arm_name, W in [("bio_motif", W_motif), ("random_matched", W_rand)]:
        for d in delays:
            succ, r2 = measure_task_success(W, delay=d, n_seeds=n_seeds)
            fi, effect = measure_fault_isolation(W, n_modules=4, delay=d,
                                                 n_seeds=n_seeds)
            rows.append({
                "arm": arm_name,
                "unit": arm_name,
                "N": W.shape[0],
                "density": float((W != 0).sum()) / (W.shape[0] ** 2),
                "rho_max": spectral_radius(W),
                "delay": d,
                "r2_mean": r2,
                "task_success": succ,
                "fault_isolation": fi,
                "fault_effect_pp": effect,
            })

    # ---- Arm A: unit-composed ----
    for u in picked:
        W_unit, ranges, edges = build_unit_topology(u, total_N=n_nodes, seed=42)
        for d in delays:
            succ, r2 = measure_task_success(W_unit, delay=d, n_seeds=n_seeds)
            fi, effect = measure_fault_isolation(W_unit, n_modules=4, delay=d,
                                                 n_seeds=n_seeds)
            rows.append({
                "arm": "unit_composed",
                "unit": u["name"],
                "N": W_unit.shape[0],
                "density": float((W_unit != 0).sum()) / (W_unit.shape[0] ** 2),
                "rho_max": spectral_radius(W_unit),
                "edges_placed": edges,
                "delay": d,
                "r2_mean": r2,
                "task_success": succ,
                "fault_isolation": fi,
                "fault_effect_pp": effect,
            })

    # ---- Report ----
    print()
    print(f"{'arm':<15} {'unit':<45} {'N':>3} {'dens':>6} {'delay':>5} "
          f"{'r2':>7} {'succ':>6} {'fi':>5} {'eff_pp':>7}")
    print("-" * 100)
    for r in rows:
        print(f"{r['arm']:<15} {r['unit'][:44]:<45} {r['N']:>3} "
              f"{r['density']:>6.3f} {r['delay']:>5} "
              f"{r['r2_mean']:>7.3f} {r['task_success']:>6.2f} "
              f"{r['fault_isolation']:>5.2f} {r['fault_effect_pp']*100:>7.2f}")

    # ---- Summary vs bio motif (primary delay) ----
    print()
    print("=== summary at primary delay=3 ===")
    d_ref = delays[0]
    bio_ref = [r for r in rows if r["arm"] == "bio_motif" and r["delay"] == d_ref]
    tb_ref = [r for r in rows if r["arm"] == "textbook_random" and r["delay"] == d_ref]
    unit_ref = [r for r in rows if r["arm"] == "unit_composed" and r["delay"] == d_ref]
    if bio_ref and unit_ref:
        b_r2 = bio_ref[0]["r2_mean"]
        tb_r2 = tb_ref[0]["r2_mean"] if tb_ref else float("nan")
        b_succ = bio_ref[0]["task_success"]
        b_fi = bio_ref[0]["fault_isolation"]
        wins = {"r2": 0, "succ": 0, "fi": 0}
        ratios = []
        for u in unit_ref:
            if u["r2_mean"] > b_r2:
                wins["r2"] += 1
            if u["task_success"] > b_succ:
                wins["succ"] += 1
            if u["fault_isolation"] > b_fi:
                wins["fi"] += 1
            if b_r2 > 0:
                ratios.append(u["r2_mean"] / b_r2)
        print(f"textbook_random (delay={d_ref}): r2={tb_r2:.3f}")
        print(f"bio_motif       (delay={d_ref}): r2={b_r2:.3f}  "
              f"success={b_succ:.2f}  fault_isolation={b_fi:.2f}")
        if ratios:
            print(f"unit_composed r2 ratio to bio_motif: "
                  f"min={min(ratios):.2f}x  "
                  f"max={max(ratios):.2f}x  "
                  f"mean={np.mean(ratios):.2f}x  "
                  f"(n={len(unit_ref)})")
        print(f"unit_composed wins over bio_motif: "
              f"r2 {wins['r2']}/{len(unit_ref)}, "
              f"success {wins['succ']}/{len(unit_ref)}, "
              f"fault_isolation {wins['fi']}/{len(unit_ref)}")

    elapsed = time.time() - t0
    print(f"\nelapsed {elapsed:.1f}s")

    out = args.out or str(HERE / "unit_composition_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "elapsed_s": elapsed,
                   "args": vars(args)}, f, indent=2, ensure_ascii=False)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
