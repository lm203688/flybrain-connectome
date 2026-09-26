"""v2.11.0 连接拓扑效率实验 —— 回答"哪种连接方式能像生物反射弧那样快速反应"。

背景
  v2.10.0 的显著性实验确认 1/15 项对比是真提高：`olfactory_to_steering`
  在 NARMA-10 上的 real_gain（d=−0.93, p=0.025）。这个 3 单元组合的实际
  连接形态就是"链式 + 反馈跳"，接近 NARMA-10 的 skip_recurrence 结构。

  本实验直接测试 6 种抽象连接拓扑（对齐 CONNECTION_TYPES family 的宏观层），
  看哪种能让 ESN 具备"复杂 + 快速反应"的生物反射弧特征。

方法
  对每个拓扑：
    1. **memory_depth**   —— 10-tap 记忆深度（delay 2..12 的 R² 曲线，
       记录 R²>0.5 的最大 delay = 有效记忆深度）
    2. **reaction_latency** —— 从阶跃输入到输出稳定 (|Δout|<0.02 for 20
       步) 的 timesteps
    3. **convergence_speed** —— step response 到 90% 目标值的 timesteps

对照臂
  - **feedforward_chain**      — 链式（当前 3 组合的实际形态）
  - **feedforward_parallel**   — 并联分叉（多路输入汇聚到输出）
  - **feedback_loop**          — 链式 + 端到端反馈环
  - **hierarchical**           — 3 层堆叠（树状分叉+收敛）
  - **skip_recurrence**        — NARMA-10 天然结构（多层跳）
  - **modulatory_hub**         — 一个中枢 hub + 从 hub 广播回所有层
  - **bio_motif**              — 基线
  - **random_matched**         — 密度匹配随机
  - **textbook_random**        — 高斯储备池

判定（生物反射弧特征）
  反射弧 = 短延迟 + 中等记忆 + 快收敛（不能全 0，也不能过慢）
  对每个拓扑打分：
    - reaction_latency < 5     加分（快）
    - memory_depth ∈ [4, 10]   加分（有但不冗余）
    - convergence < 8          加分（响应快）

用法
  python connectivity_topology_efficiency_experiment.py --quick   # n_seeds=5
  python connectivity_topology_efficiency_experiment.py            # n_seeds=20
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

from unit_composition_experiment import (  # noqa: E402
    build_motif_topology, build_random_topology,
)
from dyn_calibration_probe import random_W  # noqa: E402
from external_benchmark_experiment import (  # noqa: E402
    run_reservoir_full, ridge_solve, mse,
)
from multi_unit_benchmark_experiment import task_narma10  # noqa: E402


# --------------------------------------------------------------------------- #
# Topology builders — 6 abstract connection patterns
# --------------------------------------------------------------------------- #
def _perturb(rng, block, noise_scale=0.5):
    """Add Gaussian noise to break rank-1 collapse."""
    return noise_scale * rng.normal(0, 1, size=block.shape)


def build_feedforward_chain(n_nodes=60, n_blocks=5, seed=42,
                             noise_scale=0.5) -> np.ndarray:
    """5 blocks in series: block i → block i+1. No feedback.
    Represents the current 3-composition topology (actual form)."""
    W = np.zeros((n_nodes, n_nodes))
    block_size = n_nodes // n_blocks
    rng = np.random.default_rng(seed)
    for i in range(n_blocks - 1):
        s = i * block_size
        t = (i + 1) * block_size
        W[s:s + block_size, t:t + block_size] += 1.0 + rng.normal(
            0, noise_scale, size=(block_size, block_size))
    # Small within-block recurrence to give each node some local dynamics
    for i in range(n_blocks):
        s = i * block_size
        W[s:s + block_size, s:s + block_size] += 0.3 + rng.normal(
            0, noise_scale * 0.3, size=(block_size, block_size))
    return W


def build_feedforward_parallel(n_nodes=60, n_inputs=4, seed=42,
                                noise_scale=0.5) -> np.ndarray:
    """4 parallel input blocks all fan into one output block.
    Multi-modal integration. No feedback."""
    W = np.zeros((n_nodes, n_nodes))
    out_start = n_nodes - n_nodes // 3
    input_size = (out_start) // n_inputs
    rng = np.random.default_rng(seed)
    for i in range(n_inputs):
        s = i * input_size
        t_end = s + input_size
        W[s:t_end, out_start:n_nodes] += 0.7 + rng.normal(
            0, noise_scale, size=(input_size, n_nodes - out_start))
    # Small within-block recurrence
    for i in range(n_inputs):
        s = i * input_size
        t_end = s + input_size
        W[s:t_end, s:t_end] += 0.3 + rng.normal(0, 0.2, size=(input_size, input_size))
    # Output block self-recurrence
    W[out_start:n_nodes, out_start:n_nodes] += 0.3 + rng.normal(
        0, 0.2, size=(n_nodes - out_start, n_nodes - out_start))
    return W


def build_feedback_loop(n_nodes=60, n_blocks=5, seed=42,
                          noise_scale=0.5) -> np.ndarray:
    """Chain with a back-edge: block last → block first.
    Feedback loop structure."""
    W = build_feedforward_chain(n_nodes, n_blocks=n_blocks, seed=seed,
                                 noise_scale=noise_scale)
    rng = np.random.default_rng(seed + 1)
    block_size = n_nodes // n_blocks
    # Feedback edge from last block to first block
    W[:block_size, (n_blocks - 1) * block_size:] += (
        0.6 + rng.normal(0, noise_scale * 0.5,
                         size=(block_size, block_size)))
    # Self-loops within first block (stabilization)
    W[:block_size, :block_size] += 0.3 + rng.normal(0, 0.2,
                                                    size=(block_size, block_size))
    return W


def build_hierarchical(n_nodes=60, n_layers=3, seed=42,
                        noise_scale=0.5) -> np.ndarray:
    """3-layer hierarchy: L0 → L1 → L2 (tree-fan-out then fan-in).
    Each layer has ~equal block count."""
    W = np.zeros((n_nodes, n_nodes))
    rng = np.random.default_rng(seed)
    # Split into 3 layers with equal size
    l0_end = n_nodes // 3
    l1_end = 2 * n_nodes // 3
    layers = [(0, l0_end), (l0_end, l1_end), (l1_end, n_nodes)]
    for i in range(len(layers) - 1):
        s_lo, s_hi = layers[i]
        t_lo, t_hi = layers[i + 1]
        W[s_lo:s_hi, t_lo:t_hi] += 1.0 + rng.normal(0, noise_scale,
                                                    size=(s_hi - s_lo, t_hi - t_lo))
    # Small within-layer recurrent for stability
    for s_lo, s_hi in layers:
        W[s_lo:s_hi, s_lo:s_hi] += 0.3 + rng.normal(0, 0.2,
                                                    size=(s_hi - s_lo, s_hi - s_lo))
    return W


def build_skip_recurrence(n_nodes=60, n_taps=10, seed=42,
                            noise_scale=0.5) -> np.ndarray:
    """Skip-recurrence: each block skips to block+2 (2-tap skip),
    like NARMA-10's skip structure. This is the topology that won on NARMA-10."""
    W = np.zeros((n_nodes, n_nodes))
    rng = np.random.default_rng(seed)
    # Split into n_taps "taps" each of size n_nodes/n_taps
    tap_size = n_nodes // n_taps
    for i in range(n_taps - 1):
        s = i * tap_size
        t = (i + 1) * tap_size
        # Forward connection
        W[s:s + tap_size, t:t + tap_size] += 1.0 + rng.normal(0, noise_scale,
                                                              size=(tap_size, tap_size))
    # Skip connections (tap i → tap i+2) — this is what makes NARMA-10 work
    for i in range(n_taps - 2):
        s = i * tap_size
        t = (i + 2) * tap_size
        t_end = t + tap_size
        if t_end > n_nodes:
            t_end = n_nodes
        W[s:s + tap_size, t:t_end] += 0.5 + rng.normal(0, noise_scale * 0.5,
                                                       size=(tap_size, t_end - t))
    # Last tap loops back to first (long-term recurrence)
    W[0:tap_size, (n_taps - 1) * tap_size:] += 0.6 + rng.normal(0, noise_scale * 0.5,
                                                                size=(tap_size, tap_size))
    return W


def build_modulatory_hub(n_nodes=60, n_sources=4, seed=42,
                          noise_scale=0.5) -> np.ndarray:
    """Hub topology: many sources converge to 1 hub, hub broadcasts back.
    Represents modulatory neuron (e.g. dopamine, octopamine) pattern."""
    W = np.zeros((n_nodes, n_nodes))
    rng = np.random.default_rng(seed)
    # Reserve central block for hub
    hub_start = n_nodes // 2 - n_nodes // 20
    hub_end = hub_start + n_nodes // 10  # hub is 10% of nodes
    # Sources feed into hub
    for i in range(n_sources):
        src_start = int(i * (hub_start) / n_sources)
        src_end = int((i + 1) * (hub_start) / n_sources)
        W[src_start:src_end, hub_start:hub_end] += 1.0 + rng.normal(
            0, noise_scale, size=(src_end - src_start, hub_end - hub_start))
    # Hub broadcasts back to all sources
    for i in range(n_sources):
        src_start = int(i * (hub_start) / n_sources)
        src_end = int((i + 1) * (hub_start) / n_sources)
        W[hub_start:hub_end, src_start:src_end] += 0.7 + rng.normal(
            0, noise_scale * 0.7, size=(hub_end - hub_start, src_end - src_start))
    # Right side: output block
    out_start = hub_end
    W[hub_start:hub_end, out_start:n_nodes] += 1.0 + rng.normal(
        0, noise_scale, size=(hub_end - hub_start, n_nodes - out_start))
    # Within-hub recurrent
    W[hub_start:hub_end, hub_start:hub_end] += 0.5 + rng.normal(
        0, 0.3, size=(hub_end - hub_start, hub_end - hub_start))
    return W


# --------------------------------------------------------------------------- #
# Metric 1: memory depth via R² across delays
# --------------------------------------------------------------------------- #
def measure_memory_depth(W, delays=(4, 8, 12, 16, 20, 30, 40, 60), rho=0.7,
                          leakage=0.90, n_seeds=5, seed_base=20260925):
    """Delay-line task: R² across increasing delays.
    Uses lower rho (0.7) and leakage (0.90) so slow dynamics are
    actually distinguishable between topologies.

    Returns dict of delay→R² and effective_depth (max delay with R²>0.5)."""
    rng = np.random.default_rng(seed_base)
    N = W.shape[0]
    try:
        s_max = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return {d: float("nan") for d in delays}, 0
    if s_max < 1e-12:
        return {d: float("nan") for d in delays}, 0
    Wc = W / s_max * rho

    results = {}
    for delay in delays:
        rs = []
        for s in range(n_seeds):
            seed = seed_base + s * 17
            rng = np.random.default_rng(seed)
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
            # target = input at time t-delay
            y = X[:, 0].copy()
            y_shifted = np.zeros_like(y)
            y_shifted[:delay] = y[0]
            y_shifted[delay:] = y[:-delay]
            # Train on S[:-delay] predicting y[delay:], test similarly
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
            rs.append(r2)
        results[delay] = float(np.mean(rs)) if rs else float("nan")

    # Effective depth = max delay with R² > 0.5
    eff_depth = 0
    for d in delays:
        if results.get(d, float("nan")) > 0.5 and d > eff_depth:
            eff_depth = d
    return results, eff_depth


# --------------------------------------------------------------------------- #
# Metric 2: reaction latency — steps to stabilize after a step change
# --------------------------------------------------------------------------- #
def measure_reaction_latency(W, rho=0.7, leakage=0.90, n_seeds=5,
                              seed_base=20260925, max_steps=200,
                              settle_thresh=0.02, settle_window=30):
    """Feed a step input at t=T/2, measure how many timesteps until output
    stabilizes (|Δout|<settle_thresh for settle_window consecutive steps).
    Uses lower rho + leakage so slower-dynamics topologies actually
    differ in reaction time."""
    rng = np.random.default_rng(seed_base)
    N = W.shape[0]
    try:
        s_max = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return float("nan")
    if s_max < 1e-12:
        return float("nan")
    Wc = W / s_max * rho

    latencies = []
    for s in range(n_seeds):
        seed = seed_base + s * 23
        rng = np.random.default_rng(seed)
        T = 400
        T_half = T // 2
        X = np.zeros((T, 1))
        X[T_half:, 0] = 1.0
        # Small noise before the step to break symmetry
        X[:T_half, 0] += rng.normal(0, 0.05, T_half)
        Win = rng.normal(0, 1, size=(N, 1))
        bias = rng.normal(0, 0.5, size=(N,))
        x = np.zeros(N)
        out = np.zeros(T)
        for t in range(T):
            x = leakage * np.tanh(Wc @ x + Win @ X[t] + bias)
            out[t] = x.mean()
        # Detect settling after the step
        post = out[T_half:]
        diffs = np.abs(np.diff(post))
        settle_idx = None
        for i in range(len(diffs) - settle_window):
            if (diffs[i:i + settle_window] < settle_thresh).all():
                settle_idx = i
                break
        latencies.append(settle_idx if settle_idx is not None else max_steps)
    return float(np.mean(latencies))


# --------------------------------------------------------------------------- #
# Metric 3: convergence speed — time to reach 90% of target value
# --------------------------------------------------------------------------- #
def measure_convergence_90(W, rho=0.7, leakage=0.90, n_seeds=5,
                             seed_base=20260925, max_steps=200):
    """Time to reach 90% of asymptotic output value after step input.
    Uses lower rho + leakage so slower-dynamics topologies differ."""
    rng = np.random.default_rng(seed_base)
    N = W.shape[0]
    try:
        s_max = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return float("nan")
    if s_max < 1e-12:
        return float("nan")
    Wc = W / s_max * rho

    times = []
    for s in range(n_seeds):
        seed = seed_base + s * 29
        rng = np.random.default_rng(seed)
        T = 300
        X = np.zeros((T, 1))
        X[50:, 0] = 1.0  # step at t=50
        X[:50, 0] += rng.normal(0, 0.05, 50)
        Win = rng.normal(0, 1, size=(N, 1))
        bias = rng.normal(0, 0.5, size=(N,))
        x = np.zeros(N)
        out = np.zeros(T)
        for t in range(T):
            x = leakage * np.tanh(Wc @ x + Win @ X[t] + bias)
            out[t] = x.mean()
        # Asymptotic value = last 50 samples mean
        asymptote = out[-50:].mean()
        threshold = 0.9 * asymptote
        if abs(asymptote) < 0.01:
            times.append(max_steps)
            continue
        # First t > 50 where out[t] >= threshold (or <= for negative)
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
    return float(np.mean(times))


# --------------------------------------------------------------------------- #
# Topology scorecard: rate each topology on "biological reflex-arc fitness"
# --------------------------------------------------------------------------- #
def score_topology(memory_depth: int, reaction_latency: float,
                    convergence_90: float) -> dict:
    """Rate a topology on biological reflex-arc fit.

    Biological reflex arc profile (based on fly giant-fiber escape reflex,
    ~10-100 ms reaction in real biology):
      - Fast reaction latency (input → output change happens fast)
      - Fast convergence to asymptote (no long oscillation / settling)
      - Sufficient memory depth (not <4, so it can recognize patterns)

    We measure memory depth up to 30. Anything ≥20 is "saturated" for the
    test (indistinguishable at this resolution).
    """
    scores = {}
    # Reaction latency (fast is good)
    if reaction_latency < 1.0:
        scores["latency_score"] = 3
    elif reaction_latency < 5:
        scores["latency_score"] = 2
    elif reaction_latency < 20:
        scores["latency_score"] = 1
    else:
        scores["latency_score"] = 0
    # Memory depth — saturated at 30 for this test, so anything ≥20 is
    # considered "sufficient memory" (score 3). Below 4 is too shallow.
    if memory_depth >= 20:
        scores["memory_score"] = 3  # saturated / excellent
    elif memory_depth >= 10:
        scores["memory_score"] = 2
    elif memory_depth >= 4:
        scores["memory_score"] = 1
    else:
        scores["memory_score"] = 0
    # Convergence 90 (fast is good, big difference here)
    if convergence_90 < 2.0:
        scores["convergence_score"] = 3  # near-instant (bio-like)
    elif convergence_90 < 8.0:
        scores["convergence_score"] = 2
    elif convergence_90 < 20.0:
        scores["convergence_score"] = 1
    else:
        scores["convergence_score"] = 0  # sluggish
    total = sum(scores.values())
    scores["total"] = total
    if total >= 8:
        scores["class"] = "biological_reflex_like"
    elif total >= 5:
        scores["class"] = "partial_reflex"
    else:
        scores["class"] = "slow_or_overpower"
    return scores


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def build_all_topologies(n_nodes=60, noise_scale=0.2):
    """Build all 9 topologies: 6 abstract + 3 baselines.

    noise_scale=0.2 is deliberately small: at noise_scale=0.5 the topology
    structure is washed out by Gaussian noise and every topology converges
    to the same behavior. Lower noise preserves structural differences.
    """
    topo_builders = [
        ("feedforward_chain", "chain", build_feedforward_chain),
        ("feedforward_parallel", "parallel", build_feedforward_parallel),
        ("feedback_loop", "feedback", build_feedback_loop),
        ("hierarchical", "hierarchical", build_hierarchical),
        ("skip_recurrence", "skip", build_skip_recurrence),
        ("modulatory_hub", "hub", build_modulatory_hub),
    ]

    arms = []
    for label, short, builder in topo_builders:
        W = builder(n_nodes=n_nodes, seed=42, noise_scale=noise_scale)
        arms.append((label, W))

    # Baselines
    W_textbook = random_W(n_nodes, seed=42)
    arms.append(("textbook_random", W_textbook))
    W_motif, _e = build_motif_topology(n_nodes=n_nodes, n_modules=4, seed=7)
    arms.append(("bio_motif", W_motif))
    W_rand, _ = build_random_topology(n_nodes=W_motif.shape[0],
                                       n_edges=int((W_motif != 0).sum()), seed=7)
    arms.append(("random_matched", W_rand))
    return arms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="n_seeds=5 (default: 20)")
    ap.add_argument("--n-nodes", type=int, default=60)
    ap.add_argument("--n-seeds", type=int, default=None)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    t0 = time.time()
    n_nodes = args.n_nodes
    n_seeds = args.n_seeds or (5 if args.quick else 20)
    print(f"connectivity topology EFFICIENCY experiment   N={n_nodes}  "
          f"n_seeds={n_seeds}  quick={args.quick}")

    # --- Build all topologies ---
    print("\n=== building topologies ===")
    arms = build_all_topologies(n_nodes)
    for label, W in arms:
        sv = np.linalg.svd(W, compute_uv=False)
        rank = int((np.abs(sv) > 1e-10).sum())
        print(f"  {label:22s} N={W.shape[0]}  density={(W != 0).mean():.3f}  rank={rank}")

    # --- Run 3 metrics for each topology ---
    print(f"\n=== measuring metrics (n_seeds={n_seeds}) ===")
    results = {}
    for label, W in arms:
        print(f"\n  --- {label} ---")
        # Memory depth
        print("    memory_depth ...", end=" ", flush=True)
        mem_curve, eff_depth = measure_memory_depth(W, n_seeds=n_seeds)
        print(f"eff_depth={eff_depth}  R²={ {k: round(v, 3) for k, v in mem_curve.items()} }")

        # Reaction latency
        print("    reaction_latency ...", end=" ", flush=True)
        latency = measure_reaction_latency(W, n_seeds=n_seeds)
        print(f"{latency:.1f} steps")

        # Convergence 90
        print("    convergence_90 ...", end=" ", flush=True)
        conv90 = measure_convergence_90(W, n_seeds=n_seeds)
        print(f"{conv90:.1f} steps")

        # NARMA-10 (the task where v2.10.0 found real_gain)
        print("    narma10 mse ...", end=" ", flush=True)
        narma_result = task_narma10(W, n_seeds=n_seeds)
        narma_mse = narma_result.get("narma10", float("nan"))
        print(f"{narma_mse:.6f}")

        # Score
        scores = score_topology(eff_depth, latency, conv90)
        print(f"    scores: {scores}")

        results[label] = {
            "memory_curve": mem_curve,
            "effective_memory_depth": eff_depth,
            "reaction_latency": latency,
            "convergence_90": conv90,
            "narma10_mse": narma_mse,
            "scores": scores,
        }

    # --- Summary table ---
    print("\n=== SUMMARY: topology fitness ranking ===")
    ranking = sorted(results.items(),
                     key=lambda x: (-x[1]["scores"]["total"],
                                    x[1]["narma10_mse"] if not math.isnan(x[1]["narma10_mse"]) else 1e9))
    print(f"{'topology':<22s} {'depth':>6s} {'latency':>8s} {'conv90':>7s} "
          f"{'lat':>4s} {'mem':>4s} {'con':>4s} {'tot':>4s} {'narma_mse':>10s} class")
    print("-" * 100)
    for label, r in ranking:
        s = r["scores"]
        nm = f"{r['narma10_mse']:.4f}" if not math.isnan(r['narma10_mse']) else "n/a"
        print(f"{label:<22s} {r['effective_memory_depth']:>6d} "
              f"{r['reaction_latency']:>8.1f} {r['convergence_90']:>7.1f} "
              f"{s['latency_score']:>4d} {s['memory_score']:>4d} "
              f"{s['convergence_score']:>4d} {s['total']:>4d} {nm:>10s} {s['class']}")

    # --- NARMA-10 ranking ---
    print("\n=== NARMA-10 MSE ranking (lower = better, from v2.10.0 real_gain task) ===")
    narma_sorted = sorted(
        [(label, r["narma10_mse"]) for label, r in results.items()
         if not math.isnan(r["narma10_mse"])],
        key=lambda x: x[1])
    for label, mse_val in narma_sorted:
        print(f"  {label:<22s}  MSE={mse_val:.6f}")
    if narma_sorted:
        best = narma_sorted[0]
        worst = narma_sorted[-1]
        if worst[1] > 1e-12:
            speedup = worst[1] / best[1]
            print(f"\n  best / worst speedup: {speedup:.2f}×")

    # --- Answer the core question ---
    print("\n=== CORE QUESTION: which topology is most 'biological reflex-arc-like'? ===")
    reflex_like = [(label, r) for label, r in ranking
                   if r["scores"]["class"] == "biological_reflex_like"]
    if reflex_like:
        print(f"  {len(reflex_like)} topology(ies) match biological reflex-arc profile:")
        for label, r in reflex_like:
            print(f"    - {label}: depth={r['effective_memory_depth']}, "
                  f"latency={r['reaction_latency']:.1f}, conv90={r['convergence_90']:.1f}")
    else:
        print("  NONE match the strict biological reflex-arc profile.")
        print("  Best partial matches:")
        for label, r in ranking[:3]:
            if r["scores"]["class"] == "partial_reflex":
                print(f"    - {label}: depth={r['effective_memory_depth']}, "
                      f"latency={r['reaction_latency']:.1f}, "
                      f"conv90={r['convergence_90']:.1f} "
                      f"(total={r['scores']['total']})")

    elapsed = time.time() - t0
    print(f"\nelapsed {elapsed:.1f}s")

    out = args.out or str(HERE / "connectivity_topology_results.json")
    payload = {
        "args": vars(args),
        "n_nodes": n_nodes,
        "n_seeds": n_seeds,
        "elapsed_s": elapsed,
        "results": results,
        "ranking": [{"label": label, **r} for label, r in ranking],
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
