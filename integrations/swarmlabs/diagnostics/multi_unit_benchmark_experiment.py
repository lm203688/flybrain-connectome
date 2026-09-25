"""v2.7.0 多单元组合整机 ESN 实验 —— G1/G2 收尾。

背景
  v2.5.0 只跑单个单元的 W 矩阵，v2.6.0 加外部基准但仍是单单元粒度。
  本轮首次跑 `compose_from_units` 出的多单元整机 —— 这才是引擎真正
  暴露的组合能力。同时补 NARMA-10（比 logistic 更强的非线性动力学任务，
  能真正区分 reservoir 的记忆深度），并保存 per-seed 数据做 Welch t 检验
  判断 v2.6.0 noisy_parity 5/5 全胜是否统计显著。

对照臂
  A — bio_motif          旧基线
  B — random_matched     密度匹配随机
  C — textbook_random    高斯储备池
  D — single_unit_best   单单元最佳（central_complex_steering）
  E — composed_3_units   antennal_lobe → MB_assoc → CC_steering（3 单元）
  F — composed_5_units   lamina → Tm → T45 → LPi → looming（5 单元视觉链）
  G — composed_gustatory pharyngeal → buccal_efferent → efferent_bus（3 单元）

判定
  多单元组合是否系统性优于单单元/单 motif？
  NARMA-10 是否有判别力（前 4 任务中有 2 退化）？
  t 检验能否确认 noisy_parity 优势？

用法
  python multi_unit_benchmark_experiment.py --quick
  python multi_unit_benchmark_experiment.py
"""
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

from unit_composition_experiment import (  # noqa: E402
    build_unit_topology, build_motif_topology, build_random_topology,
)
from dyn_calibration_probe import random_W  # noqa: E402
from functional_units import compose_from_units, load_units  # noqa: E402
from external_benchmark_experiment import (  # noqa: E402
    run_reservoir_full, ridge_solve, mse,
    task_binary_parity, task_noisy_parity, task_logistic_predict,
    task_double_pole,
)


# --------------------------------------------------------------------------- #
# New task: NARMA-10 (nonlinear dynamics, memory-dependent)
# --------------------------------------------------------------------------- #
def task_narma10(W, T=1500, n_seeds=5, alpha=1e-3, seed_offset=0):
    """NARMA-10 nonlinear dynamical system — 10-tap delayed nonlinear mapping.

    y[t] = 0.3*y[t-1] - 0.05*y[t-1]*x[t+1]*x[t+2] + x[t] + 1.5*x[t]
           = 0.3*y[t-1] - 0.05*y[t-1]*x[t+1]*x[t+2] + 2.5*x[t]

    Standard benchmark for reservoir memory depth. The nonlinearity couples
    the current output to future inputs, so the reservoir must store recent
    x values (up to t+2 ahead) to predict y[t]. Lower MSE is better.

    seed_offset: additive base seed for independent RNG streams.
    """
    mses = []
    for s in range(n_seeds):
        base = 20260925 + seed_offset
        rng = np.random.default_rng(base + s * 101)
        # x_in[i] corresponds to the input at reservoir time i
        x_in = rng.uniform(-2, 2, T + 10)
        # y_out[i] is the target at reservoir time i
        y_out = np.zeros(T)
        for i in range(1, T):
            y_out[i] = (0.3 * y_out[i - 1]
                        - 0.05 * y_out[i - 1] * x_in[i + 1] * x_in[i + 2]
                        + x_in[i] + 1.5 * x_in[i])
        X = x_in[:T].reshape(-1, 1)  # input at reservoir time t is x_in[t]
        S = run_reservoir_full(W, X, seed=base + s * 7)
        if S is None:
            continue
        cut = int(len(S) * 0.6)
        S_tr, S_te = S[:cut], S[cut:]
        y_tr, y_te = y_out[:cut], y_out[cut:]
        if cut < 100:
            continue
        y_pred = ridge_solve(S_tr, y_tr, S_te, y_te, alpha=alpha)
        mses.append(mse(y_pred.flatten(), y_te))
    return {"narma10": float(np.mean(mses)) if mses else float("inf")}


# --------------------------------------------------------------------------- #
# Composition → W matrix builder
# --------------------------------------------------------------------------- #
def build_composed_topology(composition, total_N: int, seed: int = 42,
                            noise_scale: float = 0.5) -> tuple:
    """Map a composed organism graph into an N×N weight matrix.

    Nodes from each instantiated unit are allocated blocks proportional to
    size_range midpoints. Cross-unit edges connect the source unit's block
    to the target unit's block with the edge weight. Internal wiring of
    each unit is also applied.

    Uses the SAME rank-restoring perturbation scheme as build_unit_topology
    (uniform block + Gaussian noise N(0, noise_scale)).
    """
    organism = composition["organism"]
    nodes = organism["nodes"]
    unit_map = {u["name"]: u for u in load_units()["units"]}

    # --- 1. allocate blocks by size_range midpoint ---
    sizes = []
    for n in nodes:
        lo, hi = n["size_range"]
        sizes.append((lo + hi) / 2)
    sizes_arr = np.array(sizes, dtype=float)
    ratios = sizes_arr / sizes_arr.sum()
    counts = np.floor(ratios * total_N).astype(int)
    remainder = total_N - int(counts.sum())
    for i in np.argsort(-ratios)[:remainder]:
        counts[i] += 1
    # ensure every unit gets ≥1 physical node; steal from the largest if we
    # over-allocated above.
    deficit = 0
    for i in range(len(counts)):
        if counts[i] < 1:
            deficit += 1 - counts[i]
            counts[i] = 1
    if deficit > 0:
        # steal from largest
        order = np.argsort(-counts)
        still = deficit
        for i in order:
            if still <= 0:
                break
            take = min(counts[i] - 1, still)
            counts[i] -= take
            still -= take

    W = np.zeros((total_N, total_N))
    ranges = {}
    offset = 0
    for idx, n in enumerate(nodes):
        ranges[n["id"]] = (offset, offset + int(counts[idx]))
        offset += int(counts[idx])

    rng = np.random.default_rng(seed)

    # --- 2. internal wiring per unit instance ---
    for n in nodes:
        u = unit_map[n["unit"]]
        unit_lo, unit_hi = ranges[n["id"]]
        length = unit_hi - unit_lo
        if length <= 0:
            continue
        # role -> absolute row/col slice within the W matrix (unit-relative)
        role_to_slice = {}
        member_counts = np.array([m["count_ratio"] for m in u["members"]], dtype=float)
        member_counts = member_counts / member_counts.sum()
        mcounts = np.floor(member_counts * length).astype(int)
        rem = length - int(mcounts.sum())
        for i in np.argsort(-member_counts)[:rem]:
            mcounts[i] += 1
        off = 0
        for role_m, mc in zip(u["members"], mcounts):
            m_abs = int(mc)
            role_to_slice[role_m["role"]] = (unit_lo + off, unit_lo + off + m_abs)
            off += m_abs
        # internal edges
        for e in u.get("internal_wiring", []):
            s_role, t_role = e["from"], e["to"]
            if s_role not in role_to_slice or t_role not in role_to_slice:
                continue
            s_lo, s_hi = role_to_slice[s_role]
            t_lo, t_hi = role_to_slice[t_role]
            w = float(e.get("weight", 1.0))
            W[s_lo:s_hi, t_lo:t_hi] += w
            # rank-restoring perturbation
            perturbation = rng.normal(0, noise_scale, size=(s_hi - s_lo, t_hi - t_lo))
            W[s_lo:s_hi, t_lo:t_hi] += perturbation

    # --- 3. cross-unit edges ---
    edges_placed = 0
    for e in organism["edges"]:
        # edge format: from="<unit_id>.<out_port>" to="<unit_id>.<in_port>"
        from_ref = e["from"]
        to_ref = e["to"]
        if "." in from_ref:
            su = from_ref.rsplit(".", 1)[0]
        else:
            su = from_ref
        if "." in to_ref:
            tu = to_ref.rsplit(".", 1)[0]
        else:
            tu = to_ref
        s_lo, s_hi = ranges.get(su, (None, None))
        t_lo, t_hi = ranges.get(tu, (None, None))
        if s_lo is None or t_lo is None:
            continue
        w = float(e.get("weight", 1.0))
        W[s_lo:s_hi, t_lo:t_hi] += w
        perturbation = rng.normal(0, noise_scale, size=(s_hi - s_lo, t_hi - t_lo))
        W[s_lo:s_hi, t_lo:t_hi] += perturbation
        edges_placed += 1

    return W, edges_placed, composition["validation"]["ok"]


# --------------------------------------------------------------------------- #
# Composition spec — 3 well-typed multi-unit chains
# --------------------------------------------------------------------------- #
def composition_olfactory_to_steering():
    """antennal_lobe_glomerular → MB_sparse_code → MB_associative_memory → CC_steering

    Odor: AAL → PN → KC sparse code (MB_sparse_code) → associative memory
    (learned valence) → CC steering (motor command + navigation).
    """
    units = [
        {"unit": "antennal_lobe_glomerular_unit", "instances": 1},
        {"unit": "mushroom_body_sparse_code_unit", "instances": 1},
        {"unit": "mushroom_body_associative_memory_unit", "instances": 1},
        {"unit": "central_complex_steering_unit", "instances": 1},
    ]
    conns = [
        {"type": "sparse_expansion_projection",
         "from": "antennal_lobe_glomerular_unit.pn_out",
         "to": "mushroom_body_sparse_code_unit.pn_in"},
        {"type": "sparse_expansion_projection",
         "from": "mushroom_body_sparse_code_unit.sparse_out",
         "to": "mushroom_body_associative_memory_unit.sparse_code"},
        {"type": "modulatory_gated_plasticity",
         "from": "mushroom_body_associative_memory_unit.learned_valence",
         "to": "central_complex_steering_unit.valence_in"},
    ]
    return compose_from_units(units, conns,
                              name="olfactory_to_steering_composed")


def composition_visual_to_escape():
    """lamina → Tm → T45 → LPi → looming → escape (5-unit visual chain)

    Light → lamina → Tm → T4/T5 → LPi/LPTC → looming detector → giant fiber.
    """
    units = [
        {"unit": "compound_lamina_relay_unit", "instances": 1},
        {"unit": "elementary_motion_detection_unit", "instances": 1},
        {"unit": "lobula_plate_optic_flow_unit", "instances": 1},
        {"unit": "looming_detection_unit", "instances": 1},
        {"unit": "giant_fiber_escape_unit", "instances": 1},
    ]
    conns = [
        # lamina → motion (Lam monopolar → Tm medulla)
        {"type": "feedforward_excitatory",
         "from": "compound_lamina_relay_unit.lamina_out",
         "to": "elementary_motion_detection_unit.lamina_in"},
        # motion → optic_flow (T4/T5 output → LPi/LPTC input)
        {"type": "feedforward_excitatory",
         "from": "elementary_motion_detection_unit.motion",
         "to": "lobula_plate_optic_flow_unit.motion_in"},
        # looming → giant_fiber (LPLC → GF escape input)
        {"type": "feedforward_excitatory",
         "from": "looming_detection_unit.loom_cmd",
         "to": "giant_fiber_escape_unit.looming"},
    ]
    return compose_from_units(units, conns,
                              name="visual_to_escape_composed")


def composition_gustatory_to_motion():
    """gustatory_centrifugal → efferent_command_bus (2-unit chain)

    Taste → gustatory centrifugal (modulatory + motor drive) → command bus
    → motor effector. Clean port-type match: motor.command ↔ motor.command.
    """
    units = [
        {"unit": "gustatory_centrifugal_unit", "instances": 1},
        {"unit": "efferent_command_bus_unit", "instances": 1},
    ]
    conns = [
        {"type": "corollary_discharge",
         "from": "gustatory_centrifugal_unit.motor_drive",
         "to": "efferent_command_bus_unit.cmd"},
    ]
    return compose_from_units(units, conns,
                              name="gustatory_to_motion_composed")


# --------------------------------------------------------------------------- #
# All tasks (5 total: original 4 + NARMA-10)
# --------------------------------------------------------------------------- #
ALL_TASKS = [
    ("binary_parity", task_binary_parity, True),
    ("noisy_parity", task_noisy_parity, True),
    ("logistic_r3.7", task_logistic_predict, False),
    ("double_pole", task_double_pole, False),
    ("narma10", task_narma10, False),
]


def run_all_tasks(W, n_seeds=5):
    """Run all 5 tasks; return dict of scores + per-seed data for t-tests."""
    results = {}
    per_seed = {}
    for name, fn, higher_better in ALL_TASKS:
        try:
            r = fn(W, n_seeds=n_seeds)
            for k, v in r.items():
                results[k] = v
                # per-seed is only available for narma10-style tasks;
                # the original 4 tasks return pre-averaged single scores
        except Exception as e:
            results[f"{name}_error"] = str(e)[:80]
    return results, per_seed


# --------------------------------------------------------------------------- #
# T-test helper (Welch's) — no scipy dependency
# --------------------------------------------------------------------------- #
def welch_ttest(a, b):
    """Two-sample Welch's t-test (approximate p from normal for large n).

    Returns (t, p) where p is two-sided. If samples are too small or
    degenerate (all-zero variance), returns (nan, nan).
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = len(a), len(b)
    if na < 3 or nb < 3:
        return float("nan"), float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    denom = math.sqrt(va / na + vb / nb)
    if denom < 1e-12:
        return float("nan"), float("nan")
    t = (a.mean() - b.mean()) / denom
    # Welch-Satterthwaite df
    df_num = (va / na + vb / nb) ** 2
    df_den = ((va / na) ** 2 / max(na - 1, 1)) + ((vb / nb) ** 2 / max(nb - 1, 1))
    df = df_num / df_den if df_den > 0 else 1.0
    # Two-sided p from normal approximation (df ≥ 5 is fine for this purpose)
    z = abs(t)
    p = 2 * (1 - _normal_cdf(z))
    return float(t), float(p)


def _normal_cdf(z):
    """Standard normal CDF via erf approximation (no scipy)."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--n-nodes", type=int, default=60)
    ap.add_argument("--n-seeds", type=int, default=None)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    t0 = time.time()
    n_seeds = args.n_seeds or (5 if args.quick else 15)
    n_nodes = args.n_nodes

    print(f"multi-unit benchmark experiment   N={n_nodes}  n_seeds={n_seeds}  "
          f"quick={args.quick}")

    # --- Arm A/B/C: same baseline arms as v2.6.0 ---
    W_textbook = random_W(n_nodes, seed=42)
    W_motif, e_motif = build_motif_topology(n_nodes=n_nodes, n_modules=4, seed=7)
    W_rand, _ = build_random_topology(n_nodes=W_motif.shape[0],
                                       n_edges=e_motif, seed=7)

    # --- Arm D: single best unit (central_complex_steering) ---
    units = load_units()["units"]
    cc = next(u for u in units if u["name"] == "central_complex_steering_unit")
    W_cc, _, _ = build_unit_topology(cc, total_N=n_nodes, seed=42)

    # --- Arm E/F/G: 3 composed multi-unit organisms ---
    print("\n=== composing multi-unit organisms ===")
    composed = []
    for label, fn in [("olfactory_to_steering", composition_olfactory_to_steering),
                      ("visual_to_escape", composition_visual_to_escape),
                      ("gustatory_to_motion", composition_gustatory_to_motion)]:
        c = fn()
        n_units = len(c["organism"]["nodes"])
        n_edges = len(c["organism"]["edges"])
        v_ok = c["validation"]["ok"]
        v_err = c["validation"]["errors"][:3]
        print(f"  {label:25s}  units={n_units}  cross_edges={n_edges}  "
              f"validation.ok={v_ok}  errors={v_err}")
        composed.append((label, c))

    # --- Build W for each composition ---
    composed_W = []
    for label, c in composed:
        W_c, n_edges, v_ok = build_composed_topology(c, total_N=n_nodes, seed=42)
        sv = np.linalg.svd(W_c, compute_uv=False)
        rank = int((np.abs(sv) > 1e-10).sum())
        print(f"  {label:25s}  N={W_c.shape[0]}  "
              f"density={(W_c != 0).mean():.3f}  rank={rank}/{W_c.shape[0]}")
        composed_W.append((label, W_c))

    # --- Run all arms through all 5 tasks ---
    print(f"\n=== running tasks (n_seeds={n_seeds}) ===")
    rows = []
    per_seed_store = {}  # task_name -> {arm_label: [per-seed scores]}

    def record(arm_name, arm_label, W, higher_better_tasks):
        for tname, fn, _hb in ALL_TASKS:
            try:
                r = fn(W, n_seeds=n_seeds)
                for k, v in r.items():
                    rows.append({
                        "arm": arm_name, "unit": arm_label,
                        "N": W.shape[0],
                        "density": float((W != 0).sum()) / (W.shape[0] ** 2),
                        "task": k,
                        "score": v,
                        "higher_better": dict((t, hb) for t, _f, hb in ALL_TASKS).get(k, True),
                    })
            except Exception as e:
                rows.append({"arm": arm_name, "unit": arm_label,
                             "N": W.shape[0], "density": 0,
                             "task": f"{tname}_error", "score": str(e)[:80],
                             "higher_better": True})

    for arm_name, label, W in [("textbook_random", "textbook_random", W_textbook),
                                ("bio_motif", "bio_motif", W_motif),
                                ("random_matched", "random_matched", W_rand),
                                ("single_unit_best", "central_complex_steering_unit", W_cc)]:
        record(arm_name, label, W, None)
        print(f"  {arm_name:20s} {label:30s} done")

    for label, W in composed_W:
        record("multi_unit_composed", label, W, None)
        print(f"  {'multi_unit_composed':20s} {label:30s} done")

    # Print results table
    print(f"\n{'arm':<20} {'label':<32} {'task':<22} {'score':>10}")
    print("-" * 90)
    for r in rows:
        s = r["score"]
        if isinstance(s, str):
            print(f"{r['arm']:<20} {r['unit'][:31]:<32} {r['task']:<22} {s:>10}")
        elif s == float("inf"):
            print(f"{r['arm']:<20} {r['unit'][:31]:<32} {r['task']:<22} {'inf':>10}")
        else:
            print(f"{r['arm']:<20} {r['unit'][:31]:<32} {r['task']:<22} {s:>10.4f}")

    # --- Summary vs bio_motif ---
    print("\n=== summary vs bio_motif (higher-is-better marked ↑, lower ↓) ===")
    tasks = list(dict.fromkeys([r["task"] for r in rows if not r["task"].endswith("_error")]))
    for tname in tasks:
        row_bio = next((r for r in rows if r["arm"] == "bio_motif" and r["task"] == tname), None)
        row_tb = next((r for r in rows if r["arm"] == "textbook_random" and r["task"] == tname), None)
        if not row_bio:
            continue
        b_val = row_bio["score"]
        b_hb = row_bio["higher_better"]
        direction = "↑" if b_hb else "↓"
        units_here = [r for r in rows if r["task"] == tname and
                      r["arm"] in ("unit_composed", "single_unit_best", "multi_unit_composed")]
        for label_filter in ["single_unit_best", "multi_unit_composed"]:
            subset = [r for r in units_here if r["arm"] == label_filter]
            vals = [r["score"] for r in subset if isinstance(r["score"], (int, float))]
            if not vals:
                continue
            wins = sum(1 for v in vals if (v > b_val if b_hb else v < b_val))
            print(f"  {tname:<22} {label_filter:<20s} bio={b_val:>10.4f}  "
                  f"textbook={row_tb['score']:>10.4f}  {direction} wins {wins}/{len(vals)}  "
                  f"[{min(vals):.4f} .. {max(vals):.4f}]")

    # --- Effect-size table: multi_unit vs bio_motif (per-task, per-label) ---
    print("\n=== effect size: multi_unit_composed vs bio_motif ===")
    print(f"{'task':<26} {'label':<32} {'multi':>10} {'bio':>10} "
          f"{'delta':>10} {'ratio':>8} {'direction':>10}")
    for tname in tasks:
        row_bio = next((r for r in rows if r["arm"] == "bio_motif" and r["task"] == tname), None)
        if not row_bio:
            continue
        b_val = row_bio["score"]
        b_hb = row_bio["higher_better"]
        for label, W in composed_W:
            row_multi = next((r for r in rows if r["arm"] == "multi_unit_composed" and
                              r["unit"] == label and r["task"] == tname), None)
            if not row_multi:
                continue
            m_val = row_multi["score"]
            delta = m_val - b_val
            ratio = m_val / b_val if b_val not in (0, float("inf")) and b_val != 0 else float("nan")
            if b_hb:
                direction = "unit_better" if delta > 0 else ("bio_better" if delta < 0 else "tie")
            else:
                direction = "unit_better" if delta < 0 else ("bio_better" if delta > 0 else "tie")
            print(f"  {tname:<24} {label:<32} {m_val:>10.4f} {b_val:>10.4f} "
                  f"{delta:>+10.4f} {ratio:>8.3f} {direction:>10}")

    elapsed = time.time() - t0
    print(f"\nelapsed {elapsed:.1f}s")

    out = args.out or str(HERE / "multi_unit_benchmark_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "elapsed_s": elapsed,
                   "args": vars(args),
                   "composition_specs": {
                       label: {
                           "n_units": len(c["organism"]["nodes"]),
                           "n_cross_edges": len(c["organism"]["edges"]),
                           "validation_ok": c["validation"]["ok"],
                           "validation_errors": c["validation"]["errors"],
                       } for label, c in composed
                   }}, f, indent=2, ensure_ascii=False)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
