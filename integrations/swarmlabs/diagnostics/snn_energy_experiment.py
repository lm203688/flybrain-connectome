"""Phase 5.1 · SNN 能耗指标实验

核心问题：某些拓扑在能耗上是否优于随机基线？
能耗代理 = 总尖峰数 × 突触数 × 时间步（事件驱动 SNN 的能量模型）

实验设计：
- 简易 SNN 模拟器（IF 神经元 + leaky integration + 事件驱动）
- 加载 3 拓扑：随机基线 / modular_isolation / hierarchical
- 给每拓扑跑 Bernoulli 延迟线任务，测总尖峰数、每步尖峰、能耗代理
- 对照：相同任务下 3 拓扑能耗对比

验收：至少一个拓扑在能耗上优于随机基线，或在能耗/精度权衡上出现新信号。

运行：
  python snn_energy_experiment.py --quick    # 3 拓扑 × 1 任务，~5s
  python snn_energy_experiment.py            # 7 拓扑 × 3 任务，~30s
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
ORG_DIR = MCP / "generated_organisms" / "swarmlabs"

# 复用 cell_densify_experiment 的 load_org / pick_nodes
import importlib.util as _ilu
_cd_spec = _ilu.spec_from_file_location("_cd", HERE / "cell_densify_experiment.py")
_cd = _ilu.module_from_spec(_cd_spec)
sys.modules["_cd"] = _cd
_cd_spec.loader.exec_module(_cd)

NODE_CAP = 64
TARGET_DENSITY = 0.15
FILL_MODE = "intra_ring"

# SNN 参数
LEAK = 0.9          # 漏电系数
THRESHOLD = 1.0     # 发射阈值
RESET = 0.0         # 复位值
SPIKE_COST = 1e-9   # 每次尖峰能耗（J，参考 IBM TrueNorth 神经元能耗）
SYNAPSE_COST = 1e-12  # 每次突触激活能耗（J）


# ---------- SNN 模拟器 ---------------------------------------------- #


def _snn_simulate(W: np.ndarray, seq: np.ndarray, n_steps: int,
                  input_gate: float = 1.0, seed: int = 0) -> tuple[np.ndarray, np.ndarray, float]:
    """事件驱动 SNN 模拟器。

    输入注入：只有前 k=N//4 个神经元接收输入（模拟感觉输入层）。
    返回：
      spikes: [n_steps, N] 布尔矩阵
      total_spikes: 总尖峰数
      energy_proxy: 能耗代理（总尖峰 × 突触激活数 × 时间步）
    """
    rng = np.random.default_rng(seed)
    N = W.shape[0]
    n_input = max(2, N // 4)  # 输入层神经元数
    V = np.zeros(N)
    spikes = np.zeros((n_steps, N), dtype=bool)
    total_spikes = 0
    total_synapse_activations = 0

    for t in range(n_steps):
        if t > 0:
            presynaptic = spikes[t - 1].astype(float)
            V = LEAK * V + W.T @ presynaptic
            total_synapse_activations += int((np.abs(W.T @ presynaptic) > 1e-12).sum())
        # 输入注入：只有输入层神经元接收，且方向由输入信号决定
        input_signal = seq[t] * input_gate
        input_noise = rng.normal(0, 0.1, size=n_input)  # 小幅噪声打破对称
        V[:n_input] = LEAK * V[:n_input] + input_signal + input_noise
        # 发射判定
        spikes[t] = V >= THRESHOLD
        total_spikes += int(spikes[t].sum())
        # 复位
        V[spikes[t]] = RESET

    energy_proxy = total_spikes * SPIKE_COST + total_synapse_activations * SYNAPSE_COST
    return spikes, total_spikes, energy_proxy


def _snn_readout(spikes: np.ndarray, y: np.ndarray, t_start: int, t_end: int,
                 alpha: float = 1e-3) -> float:
    """从尖峰模式训练线性读出器，返回 R²。

    使用逐时间步的尖峰向量作为状态，训练线性读出器预测目标。
    """
    S = spikes[t_start:t_end].astype(float)  # [T, N]
    y_sub = y[t_start:t_end]
    if len(np.unique(y_sub)) < 2 or S.shape[0] == 0:
        return 0.0
    X = np.column_stack([S, np.ones(S.shape[0])])  # [T, N+1]
    beta = np.linalg.solve(X.T @ X + alpha * np.eye(X.shape[1]), X.T @ y_sub)
    pred = X @ beta
    mse = float(np.mean((pred - y_sub) ** 2))
    var = float(np.var(y_sub))
    if var < 1e-9:
        return 0.0
    return max(0.0, min(1.0, 1.0 - mse / var))


# ---------- 拓扑加载 ------------------------------------------------ #


def _build_W(path: Path) -> tuple[np.ndarray, int, str]:
    """加载拓扑，返回 (W, K, label)。"""
    agents, edges, label = _cd.load_org(path)
    nodes, _ = _cd.pick_nodes(agents, cap=NODE_CAP)
    mods, reps, sizes = _cd.node_meta(nodes)
    n = len(nodes)
    W = _cd.motif_layer(nodes, edges)
    d_max = _cd.max_intra_density(n, sizes, len(sizes))
    frac = min(1.0, TARGET_DENSITY / max(d_max, 1e-9))
    W, K, _, _ = _cd.densify(nodes, edges, frac, FILL_MODE, seed=7, keep_motif=True)
    return W, K, label


def _pick_targets(quick: bool = False) -> list[tuple[Path, str]]:
    candidates = [
        "bp_hierarchical.swarm.json",
        "bp_predictive_coding.swarm.json",
        "modular_isolation.swarm.json",
        "robust_redundant.swarm.json",
        "decoupled_hierarchical.swarm.json",
        "sample_10module.swarm.json",
    ]
    if quick:
        candidates = candidates[:3]
    targets = []
    for name in candidates:
        p = ORG_DIR / name
        if p.exists():
            targets.append((p, p.stem))
    return targets


def _random_baseline(N: int, K: int, seed: int = 42) -> np.ndarray:
    """生成同 N、同 K 的随机基线。"""
    rng = np.random.default_rng(seed)
    W = np.zeros((N, N))
    flat = np.arange(N * N)
    diag = flat % N != flat // N
    pool = np.where(diag)[0]
    k = min(K, len(pool))
    W.flat[rng.choice(pool, size=k, replace=False)] = rng.normal(0.4, 0.3, size=k)
    return W


# ---------- 主实验 -------------------------------------------------- #


def probe_main(targets: list[tuple[Path, str]], delays: list[int],
               n_seeds: int = 10, n_steps: int = 500) -> list[dict]:
    rows = []
    for path, label in targets:
        t0 = time.time()
        W, K, label2 = _build_W(path)
        N = W.shape[0]
        # SVD 归一化到谱半径 1.0
        try:
            s_max = np.linalg.svd(W, compute_uv=False)[0]
            Wc = W / s_max * 1.0 if s_max > 1e-12 else W
        except np.linalg.LinAlgError:
            Wc = W
        # 随机基线
        W_rand = _random_baseline(N, K, seed=42)
        try:
            s_max_r = np.linalg.svd(W_rand, compute_uv=False)[0]
            W_rand_c = W_rand / s_max_r * 1.0 if s_max_r > 1e-12 else W_rand
        except np.linalg.LinAlgError:
            W_rand_c = W_rand

        print(f"\n  {label2}  N={N}  K={K}")

        for d in delays:
            results = {"spikes_topo": [], "spikes_rand": [], "energy_topo": [],
                       "energy_rand": [], "r2_topo": [], "r2_rand": []}
            for s in range(n_seeds):
                # 生成输入序列
                rng = np.random.default_rng(1000 + s)
                n_total = d + 1 + n_steps
                seq = (rng.random(n_total) > 0.5).astype(float) * 2 - 1
                y = seq[:n_steps]  # 目标：delay 步前
                # 拓扑运行
                spikes_t, tot_spikes_t, energy_t = _snn_simulate(Wc, seq[d:], n_steps, seed=s)
                # 随机基线运行
                spikes_r, tot_spikes_r, energy_r = _snn_simulate(W_rand_c, seq[d:], n_steps, seed=s)
                results["spikes_topo"].append(tot_spikes_t)
                results["spikes_rand"].append(tot_spikes_r)
                results["energy_topo"].append(energy_t)
                results["energy_rand"].append(energy_r)
                # 简单读出（尖峰计数）
                results["r2_topo"].append(_snn_readout(spikes_t, y, 0, n_steps))
                results["r2_rand"].append(_snn_readout(spikes_r, y, 0, n_steps))

            avg_spikes_t = float(np.mean(results["spikes_topo"]))
            avg_spikes_r = float(np.mean(results["spikes_rand"]))
            avg_energy_t = float(np.mean(results["energy_topo"]))
            avg_energy_r = float(np.mean(results["energy_rand"]))
            avg_r2_t = float(np.mean(results["r2_topo"]))
            avg_r2_r = float(np.mean(results["r2_rand"]))
            # 能耗比
            energy_ratio = avg_energy_t / avg_energy_r if avg_energy_r > 1e-15 else 0.0
            # 精度差
            r2_diff = avg_r2_t - avg_r2_r
            # 判定
            if avg_energy_t < avg_energy_r * 0.8 and avg_r2_t >= avg_r2_r * 0.5:
                verdict = "H1 能耗优势（低能耗不降精度）"
            elif avg_energy_t < avg_energy_r * 0.5:
                verdict = "H1 能耗优势（大幅节能）"
            elif avg_energy_t > avg_energy_r * 1.2 and avg_r2_t > avg_r2_r * 1.5:
                verdict = "H2 高精度高能耗"
            else:
                verdict = "H3 无显著差异"

            print(f"    delay={d}: 尖峰 拓扑={avg_spikes_t:.0f} 随机={avg_spikes_r:.0f} | "
                  f"能耗比={energy_ratio:.3f} | R² 拓扑={avg_r2_t:.3f} 随机={avg_r2_r:.3f} | {verdict}")
            rows.append({
                "label": label2, "delay": d, "N": N, "K": K,
                "avg_spikes_topo": round(avg_spikes_t, 1),
                "avg_spikes_rand": round(avg_spikes_r, 1),
                "avg_energy_topo": round(avg_energy_t, 6),
                "avg_energy_rand": round(avg_energy_r, 6),
                "energy_ratio": round(energy_ratio, 4),
                "avg_r2_topo": round(avg_r2_t, 4),
                "avg_r2_rand": round(avg_r2_r, 4),
                "r2_diff": round(r2_diff, 4),
                "verdict": verdict,
                "elapsed_s": round(time.time() - t0, 2),
            })
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Phase 5.1 SNN 能耗指标实验")
    ap.add_argument("--quick", action="store_true", help="快速验证（3 拓扑 × 1 delay）")
    ap.add_argument("--seeds", type=int, default=10, help="每 run 的种子数（默认 10）")
    ap.add_argument("--steps", type=int, default=500, help="时间步数（默认 500）")
    ap.add_argument("--out", default="snn_energy_results.json", help="结果 JSON 输出路径")
    args = ap.parse_args(argv)

    targets = _pick_targets(quick=args.quick)
    delays = [3] if args.quick else [1, 2, 3, 5]
    print("\nflybrain-connectome · Phase 5.1 SNN 能耗指标实验")
    print(f"  拓扑: {len(targets)}  延迟: {delays}  种子: {args.seeds}  时间步: {args.steps}")
    print(f"  SNN 参数: leak={LEAK} threshold={THRESHOLD} spike_cost={SPIKE_COST}J")
    t0 = time.time()
    rows = probe_main(targets, delays, n_seeds=args.seeds, n_steps=args.steps)
    elapsed = time.time() - t0

    # 汇总
    n_h1 = sum(1 for r in rows if r["verdict"].startswith("H1"))
    n_h2 = sum(1 for r in rows if r["verdict"].startswith("H2"))
    n_h3 = sum(1 for r in rows if r["verdict"].startswith("H3"))
    print(f"\n--- 汇总 ---")
    print(f"  总 run: {len(rows)}  H1: {n_h1}  H2: {n_h2}  H3: {n_h3}  耗时: {elapsed:.1f}s")
    if rows:
        energy_ratios = [r["energy_ratio"] for r in rows if r["energy_ratio"] > 0]
        if energy_ratios:
            print(f"  能耗比范围: {min(energy_ratios):.3f} - {max(energy_ratios):.3f} "
                  f"(中位 {float(np.median(energy_ratios)):.3f})")
        print(f"  H1 命中率: {n_h1}/{len(rows)} = {n_h1/len(rows)*100:.1f}%")

    # 保存
    out_path = HERE / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"  结果: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
