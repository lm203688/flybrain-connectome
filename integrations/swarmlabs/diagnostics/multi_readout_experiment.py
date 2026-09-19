"""Phase 5.2 · 多读出无意识决策实验

核心问题：每个模块能否**独立**支持子任务决策（不通过中央整合）？
这是"无意识快速决策"（Kahneman System 1）的可操作定义。

实验设计：
- 复用 ESN 底物（Bernoulli 延迟线 + SVD 谱半径标定 + 种子平均 30）
- 任务改造：3 个子任务（delay=3 / delay=5 / delay=7），每个模块只看自己
  的神经元子集，训一个独立线性读出器
- 对照组：中央读出器（用全部神经元）作为上限基线
- 判定：
    * H1（模块化）：某模块独立读出 R² ≥ 中央 × 0.8 → 该模块"知道自己那部分答案"
    * H2（中央依赖）：所有模块独立读出 < 中央 × 0.5 → 需要中央整合
    * H3（无结构）：模块读出差异 > 中央 × 0.3 → 无模块分工

验收：至少一个拓扑的某模块在子任务上达到中央 × 0.8，即可主张"该模块能
独立快速决策"——这是生物学至今未量化的能力。

运行：
  python multi_readout_experiment.py --quick    # 3 拓扑 × 1 子任务，~10s
  python multi_readout_experiment.py            # 7 拓扑 × 3 子任务，~2min
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
# diagnostics → swarmlabs → integrations → flybrain-connectome（项目根）→ flybrain-connectome-mcp
MCP = HERE.parent.parent.parent / "flybrain-connectome-mcp"
ORG_DIR = MCP / "generated_organisms" / "swarmlabs"

# 复用 cell_densify_experiment 的 load_org / pick_nodes（已验证口径）
import importlib.util as _ilu
_cd_spec = _ilu.spec_from_file_location(
    "_cd", HERE / "cell_densify_experiment.py")
_cd = _ilu.module_from_spec(_cd_spec)
sys.modules["_cd"] = _cd
_cd_spec.loader.exec_module(_cd)
NODE_CAP = 64       # ESN 节点上限
TARGET_DENSITY = 0.20  # cell 层密化目标密度（cell_densify D0 实测最优区）
FILL_MODE = "intra_ring"  # 环形布线（cell_densify D3 证明最优）


# ---------- 核心：多读出 ESN ----------------------------------------- #


def _build_W_from_org(org: dict, nodes: list[dict]) -> tuple[np.ndarray, dict, int]:
    """从 org JSON + nodes 构建 (W, module_of_node, K)。

    步骤：(1) motif_layer 取原始边 → (2) densify 补 cell 层密化到 TARGET_DENSITY
    返回密化后的 W（保留 motif 边 + 模块内 cell fill）。
    """
    mods, reps, sizes = _cd.node_meta(nodes)
    n_modules = len(sizes)
    n = len(nodes)
    # motif layer（原始边）
    W = _cd.motif_layer(nodes, org.get("edges") or [])
    # densify：补到目标密度（模块内，不跨模块）
    d_max = _cd.max_intra_density(n, sizes, n_modules)
    frac = min(1.0, TARGET_DENSITY / max(d_max, 1e-9))
    W, K, added, _ = _cd.densify(nodes, org.get("edges") or [], frac, FILL_MODE,
                                  seed=7, keep_motif=True)
    module_of_node = {i: int(a.get("module", 0)) for i, a in enumerate(nodes)}
    return W, module_of_node, K


def _normalize_rho(W: np.ndarray, rho: float = 1.0) -> np.ndarray:
    """SVD 谱半径标定：把 W 缩放到最大奇异值 = rho。"""
    try:
        s_max = np.linalg.svd(W, compute_uv=False)[0]
    except np.linalg.LinAlgError:
        return W
    if s_max < 1e-12:
        return W
    return W / s_max * min(rho, 1.0)


def _run_esn(Wc: np.ndarray, Win: np.ndarray, bias: np.ndarray,
             seq: np.ndarray, t_start: int, n_out: int,
             leakage: float = 0.95) -> np.ndarray:
    """跑 ESN 得到 [n_out, N] 状态矩阵。"""
    N = Wc.shape[0]
    x = np.zeros(N)
    S = []
    for t in range(t_start, t_start + n_out):
        x = leakage * np.tanh(Wc @ x + Win[:, 0] * seq[t] + bias)
        S.append(x)
    return np.array(S)


def _train_linear_readout(S: np.ndarray, y: np.ndarray, alpha: float = 1e-3) -> np.ndarray:
    """岭回归读出器。"""
    X = np.column_stack([S, np.ones(len(S))])
    return np.linalg.solve(X.T @ X + alpha * np.eye(X.shape[1]), X.T @ y)


def _r2(pred: np.ndarray, y: np.ndarray) -> float:
    mse = float(np.mean((pred - y) ** 2))
    var = float(np.var(y))
    if var < 1e-9:
        return 0.0
    return max(0.0, min(1.0, 1.0 - mse / var))


def _single_run(Wc: np.ndarray, module_of_node: dict, delay: int,
                rho: float, seed: int, n_train: int = 240, n_test: int = 120) -> dict:
    """单次运行：返回 central_r2 + 每模块 module_r2。"""
    rng = np.random.default_rng(seed)
    N = Wc.shape[0]
    if N < 4:
        return {"central_r2": 0.0, "module_r2": {}, "n_modules": 0}
    n_total = delay + 1 + n_train + n_test
    seq = (rng.random(size=n_total) > 0.5).astype(float) * 2 - 1
    Win = rng.normal(0.0, 1.0, size=(N, 1))
    bias = rng.normal(0.0, 0.5, size=(N,))
    S = _run_esn(Wc, Win, bias, seq, t_start=delay + 1, n_out=n_train + n_test, leakage=0.95)
    y = seq[delay + 1 - delay:delay + 1 + n_train + n_test - delay]  # = seq[:n_train+n_test]
    S_tr, y_tr = S[:n_train], y[:n_train]
    S_te, y_te = S[n_train:], y[n_train:]
    if len(np.unique(y_tr)) < 2:
        return {"central_r2": 0.0, "module_r2": {}, "n_modules": 0}
    # 中央读出（全部神经元）
    beta_c = _train_linear_readout(S_tr, y_tr)
    central_r2 = _r2(S_te @ beta_c[:N], y_te)
    # 模块独立读出
    module_r2: dict[int, float] = {}
    n_mod = max(module_of_node.values()) + 1 if module_of_node else 1
    for mid in range(n_mod):
        idx = np.array([i for i, m in module_of_node.items() if m == mid])
        if len(idx) < 2:
            module_r2[mid] = 0.0
            continue
        S_tr_m = S_tr[:, idx]
        S_te_m = S_te[:, idx]
        beta_m = _train_linear_readout(S_tr_m, y_tr)
        module_r2[mid] = _r2(S_te_m @ beta_m[:len(idx)], y_te)
    return {"central_r2": central_r2, "module_r2": module_r2, "n_modules": n_mod}


def _avg_run(Wc: np.ndarray, module_of_node: dict, delay: int, rho: float,
             n_seeds: int = 30) -> dict:
    """种子平均：压掉输入序列运气。"""
    results = [_single_run(Wc, module_of_node, delay, rho, seed=s)
               for s in range(n_seeds)]
    central = float(np.mean([r["central_r2"] for r in results]))
    n_mod = results[0]["n_modules"]
    module_r2: dict[int, float] = {}
    for mid in range(n_mod):
        module_r2[mid] = float(np.mean([r["module_r2"].get(mid, 0.0) for r in results]))
    return {"central_r2": central, "module_r2": module_r2, "n_modules": n_mod}


# ---------- 拓扑加载 ------------------------------------------------ #


def _load_org(path: Path) -> tuple[dict, str]:
    """加载拓扑，返回 ({"agents": [...], "edges": [...]}, label)。"""
    agents, edges, label = _cd.load_org(path)
    # 排除 guardrail / coordinator（module=None）
    nodes, _ = _cd.pick_nodes(agents, cap=NODE_CAP)
    return {"agents": nodes, "edges": edges}, label


def _pick_targets(quick: bool = False) -> list[tuple[Path, str]]:
    """挑代表性拓扑：随机基线 + 模块化 + 层级 + 冗余 + 故障隔离。"""
    candidates = [
        "bp_hierarchical.swarm.json",
        "bp_predictive_coding.swarm.json",
        "modular_isolation.swarm.json",
        "robust_redundant.swarm.json",
        "decoupled_hierarchical.swarm.json",
        "bench_attention_working_combo.swarm.json",
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


# ---------- 主实验 -------------------------------------------------- #


def probe_main(targets: list[tuple[Path, str]], delays: list[int],
               rho: float = 1.0, n_seeds: int = 30) -> list[dict]:
    rows = []
    for path, label in targets:
        t0 = time.time()
        org, label2 = _load_org(path)
        nodes = org["agents"]
        W, module_of_node, K = _build_W_from_org(org, nodes)
        Wc = _normalize_rho(W, rho)
        if K == 0:
            print(f"  [SKIP] {label2}: W 全零")
            continue
        n_mod = max(module_of_node.values()) + 1 if module_of_node else 1
        dens = K / (Wc.shape[0] ** 2)
        print(f"\n  {label2}  N={Wc.shape[0]}  K={K}  dens={dens:.3f}  模块数={n_mod}")
        for d in delays:
            r = _avg_run(Wc, module_of_node, delay=d, rho=rho, n_seeds=n_seeds)
            central = r["central_r2"]
            mrs = r["module_r2"]
            # 判定 H1/H2/H3
            if not mrs:
                verdict = "H3 无模块"
            else:
                best_local = max(mrs.values())
                # H1: 某模块能到中央 × 0.8 → 该模块能独立支持子任务
                # H2: 所有模块 < 中央 × 0.5 → 需要中央整合
                # H3: 模块差异巨大（方差大）→ 模块分工不明确
                if best_local >= central * 0.8 and central > 0.05:
                    verdict = "H1 模块化（局部可独立决策）"
                elif central > 0.05 and best_local < central * 0.5:
                    verdict = "H2 中央依赖"
                else:
                    verdict = "H3 混合/弱模块化"
            mrs_str = ", ".join(f"m{m}={v:.3f}" for m, v in sorted(mrs.items()))
            print(f"    delay={d}: 中央 R²={central:.3f} | 模块 R²: {mrs_str} | {verdict}")
            rows.append({
                "label": label2, "delay": d, "K": K, "n_mod": n_mod,
                "central_r2": round(central, 4),
                "module_r2": {int(k): round(v, 4) for k, v in mrs.items()},
                "best_local_r2": round(max(mrs.values()) if mrs else 0.0, 4),
                "local_vs_central_ratio": round((max(mrs.values()) / central) if (mrs and central > 1e-9) else 0.0, 4),
                "verdict": verdict,
                "elapsed_s": round(time.time() - t0, 2),
            })
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Phase 5.2 多读出无意识决策实验")
    ap.add_argument("--quick", action="store_true", help="快速验证（3 拓扑 × 1 delay）")
    ap.add_argument("--seeds", type=int, default=30, help="每 run 的种子数（默认 30）")
    ap.add_argument("--rho", type=float, default=1.0, help="谱半径目标（默认 1.0）")
    ap.add_argument("--out", default="multi_readout_results.json", help="结果 JSON 输出路径")
    args = ap.parse_args(argv)

    targets = _pick_targets(quick=args.quick)
    delays = [2] if args.quick else [1, 2, 3, 5]
    print("\nflybrain-connectome · Phase 5.2 多读出无意识决策实验")
    print(f"  拓扑: {len(targets)}  延迟: {delays}  种子: {args.seeds}  谱半径: {args.rho}")
    print(f"  判定: H1=某模块独立达中央×0.8 / H2=全模块<中央×0.5 / H3=混合")
    t0 = time.time()
    rows = probe_main(targets, delays, rho=args.rho, n_seeds=args.seeds)
    elapsed = time.time() - t0

    # 汇总
    n_h1 = sum(1 for r in rows if r["verdict"].startswith("H1"))
    n_h2 = sum(1 for r in rows if r["verdict"].startswith("H2"))
    n_h3 = sum(1 for r in rows if r["verdict"].startswith("H3"))
    print(f"\n--- 汇总 ---")
    print(f"  总 run: {len(rows)}  H1: {n_h1}  H2: {n_h2}  H3: {n_h3}  耗时: {elapsed:.1f}s")
    print(f"  H1 命中率: {n_h1}/{len(rows)} = {n_h1/len(rows)*100:.1f}%" if rows else "  无数据")

    # 保存
    out_path = HERE / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"  结果: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
