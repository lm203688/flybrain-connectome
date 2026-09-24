"""v2.6.0 外部 ESN 基准套件 —— G2 单元库外部锚点。

背景
  v2.5.0 首次让 101 单元跑 ESN，但只有 delay-line 单任务——不是标准
  ESN benchmark 套件。PROJECT_VISION.md §六 明确要求「有基准测试证明
  虚拟生物可以超越生物学限制」，delay-line 只是内部数字。

  本套件实现 4 个标准 ESN 任务（文献经典）：
    1. **binary_parity**    —— XOR 链（3-tap），记忆 + 非线性判别
    2. **noisy_parity**     —— 加噪版本，噪声下的鲁棒性
    3. **logistic_predict** —— 混沌时间序列 (r=3.7) 一步前预测
    4. **double_pole**      —— 二阶 LP 滤波器系统识别

  每任务用 accuracy / MSE 度量，与 delay-line 互补。任务错配（记忆
  vs 感知 vs 预测）是 v2.5.0 的关键混淆源——本套件把它打开。

对照臂
  Arm A — unit_composed  (5 个代表性单元)
  Arm B — bio_motif      (design_organism module_rep 层)
  Arm C — random_matched (密度匹配随机)
  Arm D — textbook_random (高斯储备池)

判定
  单元在具体任务上系统性优于 bio_motif → G2 里程碑成立
  持平 → 单元库和 motif 在多个 ESN 任务族上等价
  更差 → 诚实登记，不宣称

用法
  python external_benchmark_experiment.py --quick   # 3 units × 4 tasks × 5 seeds
  python external_benchmark_experiment.py           # 5 units × 4 tasks × 20 seeds
"""
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

from unit_composition_experiment import (  # noqa: E402
    build_unit_topology, build_motif_topology, build_random_topology,
    pick_representative_units,
)
from dyn_calibration_probe import random_W  # noqa: E402
from functional_units import load_units  # noqa: E402


# --------------------------------------------------------------------------- #
# Reservoir runner + linear readout
# --------------------------------------------------------------------------- #
def run_reservoir_full(W, X, rho=0.95, leakage=0.95, seed=20260925):
    """One reservoir pass over the whole input; returns state trajectory S."""
    rng = np.random.default_rng(seed)
    N = W.shape[0]
    try:
        s_max = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return None
    if s_max < 1e-12:
        return None
    Wc = W / s_max * rho
    Win = rng.normal(0.0, 1.0, size=(N, X.shape[1]))
    bias = rng.normal(0.0, 0.5, size=(N,))
    x = np.zeros(N)
    T = len(X)
    S = np.zeros((T, N))
    for t in range(T):
        x = leakage * np.tanh(Wc @ x + Win @ X[t] + bias)
        S[t] = x
    return S


def ridge_solve(S_tr, y_tr, S_te, y_te, alpha=1e-3):
    """Ridge regression; returns predicted y for S_te."""
    S_tr_aug = np.hstack([np.ones((S_tr.shape[0], 1)), S_tr])
    S_te_aug = np.hstack([np.ones((S_te.shape[0], 1)), S_te])
    lam = alpha * S_tr_aug.shape[1]
    W_out = np.linalg.solve(S_tr_aug.T @ S_tr_aug + lam * np.eye(S_tr_aug.shape[1]),
                            S_tr_aug.T @ y_tr)
    return S_te_aug @ W_out


def mse(a, b):
    return float(np.mean((a - b) ** 2))


# --------------------------------------------------------------------------- #
# Task 1: binary parity — XOR of last 3 input bits
# --------------------------------------------------------------------------- #
def task_binary_parity(W, T=1500, n_seeds=5, alpha=1e-3):
    """XOR of 3-bit window. Higher accuracy is better."""
    delay = 3
    accs = []
    for s in range(n_seeds):
        rng = np.random.default_rng(20260925 + s * 17)
        bits = (rng.random(T + delay) > 0.5).astype(float)
        # X_t = bits[t], target y_t = XOR(bits[t], bits[t-1], bits[t-2])
        X = bits[:-1].reshape(-1, 1)                       # length T-1
        # aligned y: y_t = XOR(bits[t], bits[t-1], bits[t-2]) for t in [delay-1, T-2]
        y = np.zeros(len(bits) - 1)
        for i in range(delay - 1, len(bits) - 1):
            y[i] = 2 * (bits[i] * bits[i - 1] * bits[i - 2]) - 1
        # reservoir on full X, then align: S[i-delay] predicts y[i]
        # we want S[t] to predict y[t+delay], so use S[:-delay] against y[delay:]
        # equivalently: use y[delay:] as target and S[:-delay] as source
        S = run_reservoir_full(W, X, seed=20260925 + s * 101)
        if S is None:
            continue
        # aligned pair: source S[:len(y)-delay], target y[delay:]
        y_aligned = y[delay:]
        S_src = S[:len(y_aligned)]
        # split train/test
        cut = int(len(S_src) * 0.6)
        S_tr, S_te = S_src[:cut], S_src[cut:]
        y_tr, y_te = y_aligned[:cut], y_aligned[cut:]
        if cut < 50:
            continue
        y_pred = ridge_solve(S_tr, y_tr, S_te, y_te, alpha=alpha)
        y_pred_bin = np.sign(y_pred).flatten()
        accs.append(float(np.mean(y_pred_bin == y_te)))
    return {"parity_d3": float(np.mean(accs)) if accs else 0.0}


# --------------------------------------------------------------------------- #
# Task 2: noisy parity — same as parity but input has Gaussian noise
# --------------------------------------------------------------------------- #
def task_noisy_parity(W, T=1500, n_seeds=5, noise_std=0.4, alpha=1e-3):
    """Noisy parity — noise injection tests robustness."""
    delay = 3
    accs = []
    for s in range(n_seeds):
        rng = np.random.default_rng(20260925 + s * 31)
        raw = (rng.random(T + delay) > 0.5).astype(float) * 2 - 1
        noisy = raw + rng.normal(0, noise_std, size=T + delay)
        X = noisy[:-1].reshape(-1, 1)
        # target from the noisy input's signs (still binary)
        y = np.zeros(len(noisy) - 1)
        for i in range(delay - 1, len(noisy) - 1):
            y[i] = np.sign(noisy[i]) * np.sign(noisy[i - 1]) * np.sign(noisy[i - 2])
        S = run_reservoir_full(W, X, seed=20260925 + s * 101)
        if S is None:
            continue
        y_aligned = y[delay:]
        S_src = S[:len(y_aligned)]
        cut = int(len(S_src) * 0.6)
        S_tr, S_te = S_src[:cut], S_src[cut:]
        y_tr, y_te = y_aligned[:cut], y_aligned[cut:]
        if cut < 50:
            continue
        y_pred = ridge_solve(S_tr, y_tr, S_te, y_te, alpha=alpha)
        y_pred_bin = np.sign(y_pred).flatten()
        accs.append(float(np.mean(y_pred_bin == y_te)))
    return {"noisy_parity_d3": float(np.mean(accs)) if accs else 0.0}


# --------------------------------------------------------------------------- #
# Task 3: logistic map prediction (chaotic time series)
# --------------------------------------------------------------------------- #
def task_logistic_predict(W, T=1500, n_seeds=5, alpha=1e-3, r=3.7):
    """Predict x_{t+1} from current x via chaotic logistic map (standard form).
    x_{t+1} = r * x_t * (1 - x_t), r=3.7 chaotic.
    Lower MSE is better; textbook random target typically 0.02-0.1."""
    mses = []
    for s in range(n_seeds):
        rng = np.random.default_rng(20260925 + s * 43)
        x = np.zeros(T + 2)
        x[0] = rng.random() * 0.9 + 0.05
        for t in range(1, T + 2):
            x[t] = r * x[t - 1] * (1 - x[t - 1])
        # X_t = x[t], y_t = x[t+1]
        X = x[:-1].reshape(-1, 1)
        y = x[1:]  # shifted by 1
        S = run_reservoir_full(W, X, seed=20260925 + s * 101)
        if S is None:
            continue
        # S[t] is the state after processing X[t] = x[t], so S[t] ↔ y[t] = x[t+1]
        cut = int(len(S) * 0.6)
        S_tr, S_te = S[:cut], S[cut:]
        y_tr, y_te = y[:cut], y[cut:]
        if cut < 50:
            continue
        y_pred = ridge_solve(S_tr, y_tr, S_te, y_te, alpha=alpha)
        mses.append(mse(y_pred.flatten(), y_te))
    return {"logistic_r3.7": float(np.mean(mses)) if mses else float("inf")}


# --------------------------------------------------------------------------- #
# Task 4: double-pole LP filter identification
# --------------------------------------------------------------------------- #
def task_double_pole(W, T=1500, n_seeds=5, alpha=1e-3, r1=0.9, r2=-0.5):
    """Identify a stable 2nd-order recurrence with two poles r1, r2:
        y[t] = -(r1+r2) * y[t-1] + r1*r2 * y[t-2] + x[t]
    For r1=0.9, r2=-0.5 this becomes y[t] = 0.4*y[t-1] + 0.45*y[t-2] + x[t],
    which is asymptotically stable. Lower MSE is better."""
    a1 = -(r1 + r2)
    a2 = r1 * r2
    mses = []
    for s in range(n_seeds):
        rng = np.random.default_rng(20260925 + s * 59)
        x_in = rng.normal(0, 1, T)
        y = np.zeros(T)
        for t in range(2, T):
            y[t] = a1 * y[t - 1] + a2 * y[t - 2] + x_in[t]
        # input at time t: [y[t-1], y[t-2], x[t]]
        X = np.zeros((T - 2, 3))
        X[:, 0] = y[:-2]
        X[:, 1] = y[1:-1]
        X[:, 2] = x_in[2:]
        # target: y[2:]
        y_target = y[2:]
        S = run_reservoir_full(W, X, seed=20260925 + s * 101)
        if S is None:
            continue
        cut = int(len(S) * 0.6)
        S_tr, S_te = S[:cut], S[cut:]
        y_tr, y_te = y_target[:cut], y_target[cut:]
        if cut < 50:
            continue
        y_pred = ridge_solve(S_tr, y_tr, S_te, y_te, alpha=alpha)
        mses.append(mse(y_pred.flatten(), y_te))
    return {"double_pole_p0.9_m0.5": float(np.mean(mses)) if mses else float("inf")}


# --------------------------------------------------------------------------- #
# Task registry
# --------------------------------------------------------------------------- #
# (name, fn, higher_is_better, textbook_reference)
TASKS = [
    ("parity_d3", task_binary_parity, True, None),
    ("noisy_parity_d3", task_noisy_parity, True, None),
    ("logistic_r3.7", task_logistic_predict, False, None),
    ("double_pole_p0.9_m0.5", task_double_pole, False, None),
]


def run_all_tasks(W, n_seeds=5):
    """Run all 4 tasks; return dict {task_name: score}."""
    results = {}
    for name, fn, _dir, _cap in TASKS:
        try:
            r = fn(W, n_seeds=n_seeds)
            results.update(r)
        except Exception as e:
            results[f"{name}_error"] = str(e)[:80]
    return results


def is_better(a_val, b_val, higher_is_better):
    if isinstance(a_val, str) or isinstance(b_val, str):
        return False
    if higher_is_better:
        return a_val > b_val
    return a_val < b_val


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
    units = load_units()["units"]
    picked = pick_representative_units(units, quick=args.quick)
    n_nodes = args.n_nodes
    n_seeds = args.n_seeds or (5 if args.quick else 20)

    print(f"external ESN benchmark suite   N={n_nodes}  n_seeds={n_seeds}  "
          f"quick={args.quick}   units={len(picked)}")
    for u in picked:
        print(f"  unit: {u['name']:45s}")
    print()

    W_textbook = random_W(n_nodes, seed=42)
    W_motif, e_motif = build_motif_topology(n_nodes=n_nodes, n_modules=4, seed=7)
    W_rand, _ = build_random_topology(n_nodes=W_motif.shape[0],
                                      n_edges=e_motif, seed=7)

    rows = []

    def record(arm, unit_name, W, results):
        for task_name, score in results.items():
            rows.append({
                "arm": arm, "unit": unit_name,
                "N": W.shape[0],
                "density": float((W != 0).sum()) / (W.shape[0] ** 2),
                "task": task_name,
                "score": score,
            })

    for arm_name, W in [("textbook_random", W_textbook),
                        ("bio_motif", W_motif),
                        ("random_matched", W_rand)]:
        r = run_all_tasks(W, n_seeds=n_seeds)
        record(arm_name, arm_name, W, r)

    for u in picked:
        W_u, _, _ = build_unit_topology(u, total_N=n_nodes, seed=42)
        r = run_all_tasks(W_u, n_seeds=n_seeds)
        record("unit_composed", u["name"], W_u, r)

    # Print results table
    print(f"\n{'arm':<18} {'unit':<45} {'task':<26} {'score':>10}")
    print("-" * 100)
    for r in rows:
        s = r["score"]
        if isinstance(s, str):
            print(f"{r['arm']:<18} {r['unit'][:44]:<45} {r['task']:<26} {s:>10}")
        elif s == float("inf"):
            print(f"{r['arm']:<18} {r['unit'][:44]:<45} {r['task']:<26} {'inf':>10}")
        else:
            print(f"{r['arm']:<18} {r['unit'][:44]:<45} {r['task']:<26} {s:>10.4f}")

    # Summary vs bio_motif
    print("\n=== summary vs bio_motif ===")
    tasks = list(dict.fromkeys([r["task"] for r in rows if not r["task"].endswith("_error")]))
    for tname in tasks:
        higher_better = dict((n, b) for n, _fn, b, _ in TASKS).get(tname, True)
        bio = next((r for r in rows if r["arm"] == "bio_motif" and r["task"] == tname), None)
        tb = next((r for r in rows if r["arm"] == "textbook_random" and r["task"] == tname), None)
        unit_rows = [r for r in rows if r["arm"] == "unit_composed" and r["task"] == tname]
        if not bio or not unit_rows:
            continue
        b_val = bio["score"]
        tb_val = tb["score"] if tb else float("nan")
        vals = [u["score"] for u in unit_rows if isinstance(u["score"], (int, float))]
        if not vals:
            continue
        wins = sum(1 for v in vals if is_better(v, b_val, higher_better))
        direction = "↑" if higher_better else "↓"
        tb_str = f"{tb_val:.4f}" if not isinstance(tb_val, str) and tb_val == tb_val else str(tb_val)[:6]
        print(f"  {tname:<24} bio={b_val:>10.4f}  textbook={tb_str:>10}  "
              f"unit {direction} wins {wins}/{len(vals)}  "
              f"[{min(vals):.4f} .. {max(vals):.4f}]")

    elapsed = time.time() - t0
    print(f"\nelapsed {elapsed:.1f}s")

    out = args.out or str(HERE / "external_benchmark_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "elapsed_s": elapsed,
                   "args": vars(args)}, f, indent=2, ensure_ascii=False)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
