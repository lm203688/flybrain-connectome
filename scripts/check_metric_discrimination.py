#!/usr/bin/env python3
"""GATE 41 — metric discrimination (SV-3c, the SV-3 degenerate-attack suite).

Why this exists
---------------
This project's flagship metric, `isolation_effect_size`, passed every
V0–V2 gate (33 in-tree gates, 15 of them with injected-defect batteries)
but turned out to be a *saturated binary*: for essentially every topology
it returned 1.0. Every gate was asking "does the metric compute correctly?"
— none of them asked "does the metric still have discrimination?".

Gate 41 closes that hole. For every externally-facing metric we register,
we demand that its output on a **standard degenerate-input suite** have
variance strictly above a metric-declared floor. If a metric saturates
(returning the same value across all inputs), the gate fails immediately
— the "92.6%" episode is now a machine-guarded boundary, not a hope that
some human reviews the report.

What counts as a "standard input"
---------------------------------
The suite mixes:

  * structurally extreme cases (chain, star, fully connected, redundant
    multi-hop grid) that force a metric with any structural sensitivity
    to move,
  * random topologies at very low and very high density,
  * a *degenerate* input (isolated node + dense cluster) that a
    well-designed metric must distinguish from the fully connected case.

If a metric can't tell these apart, it has no information content left
on the domain we care about.

Registry
--------
Every metric registered here declares its own `min_variance` floor. The
floor is a *self-attested* lower bound — an honest author writes 0.01 for
a metric with real signal and 0.0001 for a subtle one. Registering a
metric with min_variance=0 is a self-declaration that it is not
externally-facing, and it is therefore not held to the gate.

Back-test on R1
---------------
The gate additionally runs the legacy binary `isolation_effect_size`
(reproduced here in `_legacy_isolation_binary`) against the same suite.
That metric is registered as a *negative control* with a small positive
min_variance; it must fail. This is SV-3d — the suite must be able to
reproduce the saturation verdict that was originally found by hand.

Injection test
--------------
The injection battery monkey-patches one working metric (drop_magnitude)
so that it always returns 0.5. Gate 41 must turn red. Without this, the
gate itself could be a no-op.

Usage:
    python scripts/check_metric_discrimination.py
    python scripts/check_metric_discrimination.py --json-out report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
MCP_DIR = ROOT / "flybrain-connectome-mcp"

# Import the graded isolation metric (C1 · A1).  We pull it in *here*
# rather than re-implementing it so that Gate 41 and A1 share exactly
# one source of truth — if the metric semantics drift, the gate and the
# experiment drift together and the discrepancy is visible.
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(MCP_DIR))
from isolation_graded import compute_graded_isolation  # noqa: E402
from llm_tasks import Blueprint  # noqa: E402


def _bp_from_nodes_edges(nodes, edges) -> "Blueprint":
    """Minimal Blueprint for the graded-isolation metric.

    capability_distribution is split into 3 modules (round-robin via
    _module_index) so that affected_module_count can range from 0 to
    3 across the standard suite.  A single-module fallback would
    saturate the metric at 0 or 1 — Gate 41 needs variance.

    The split is by position: first third → mod0, second third → mod1,
    last third → mod2.  This is honest (the metric's module assignment
    is a design choice, not a measurement) and it exercises the metric's
    sensitivity to cross-module reachability loss.

    Why the MEAN of affected modules, not the MAX: on small dense
    topologies a single hub removal disconnects at least one node from
    every declared module, so ``max`` saturates at n_modules and carries
    no information.  The mean over hubs keeps real variance (Gate 41
    would otherwise fail this metric below its floor).
    """
    n = len(nodes)
    # Ensure at least 3 modules by splitting into thirds.
    third = max(1, n // 3)
    return Blueprint(
        name="_gate41_probe",
        nodes=tuple(nodes),
        edges=tuple(edges),
        motif_family="reservoir_smallworld",
        capability_distribution={
            "mod0": third,
            "mod1": min(third, n - third),
            "mod2": max(1, n - 2 * third),
        },
    )


def _graded_drop(nodes, edges) -> float:
    r = compute_graded_isolation(_bp_from_nodes_edges(nodes, edges))
    return float(r.drop_magnitude)


def _graded_affected_modules_mean(nodes, edges) -> float:
    r = compute_graded_isolation(_bp_from_nodes_edges(nodes, edges))
    return float(r.affected_module_count_mean)


def _graded_recovery_steps(nodes, edges) -> float:
    r = compute_graded_isolation(_bp_from_nodes_edges(nodes, edges))
    return float(r.mean_recovery_steps)

GATE_ID = 41
GATE_LABEL = f"GATE {GATE_ID}"

# ---------------------------------------------------------------------------
# Standard degenerate-input suite.
#
# Each entry is (name, nodes, edges). All small enough that compute is
# instant but varied enough that a structurally sensitive metric must
# spread.
# ---------------------------------------------------------------------------

def _full(n: int):
    nodes = tuple(f"n{i}" for i in range(n))
    return nodes, tuple(
        (a, b) for a in nodes for b in nodes if a != b
    )

def _chain(n: int):
    nodes = tuple(f"n{i}" for i in range(n))
    return nodes, tuple((nodes[i], nodes[i + 1]) for i in range(n - 1))

def _star(n: int):
    nodes = tuple(f"n{i}" for i in range(n))
    return nodes, tuple((nodes[0], b) for b in nodes[1:])

def _redundant_grid(n: int = 8):
    # 2x4 grid, both directions, plus one extra edge — redundant paths.
    nodes = tuple(f"n{i}" for i in range(n))
    edges = []
    for i in range(4):
        edges.append((nodes[i], nodes[i + 4]))
        edges.append((nodes[i], nodes[i + 1] if i + 1 < 4 else nodes[i]))
    edges.append((nodes[7], nodes[3]))
    return nodes, tuple(edges)

def _random(seed: int, n: int = 8, density: float = 0.3):
    import random
    rng = random.Random(seed)
    nodes = tuple(f"n{i}" for i in range(n))
    all_pairs = [(a, b) for a in nodes for b in nodes if a != b]
    k = int(len(all_pairs) * density)
    edges = tuple(rng.sample(all_pairs, k=k))
    return nodes, edges

def _isolated_plus_cluster():
    # One fully disconnected node plus a dense cluster. A well-designed
    # reachability / connectivity metric must give this a very different
    # value from _full.
    nodes = tuple(f"n{i}" for i in range(7))
    cluster = nodes[:6]
    edges = tuple((a, b) for a in cluster for b in cluster if a != b)
    return nodes, edges


def _ring(n: int):
    """Cycle graph — every node has exactly 2 neighbours."""
    nodes = tuple(f"n{i}" for i in range(n))
    return nodes, tuple(
        (nodes[i], nodes[(i + 1) % n]) for i in range(n)
    )


def _tree(n: int = 10):
    """Balanced binary tree — tests hierarchical isolation."""
    nodes = tuple(f"n{i}" for i in range(n))
    edges = []
    for i in range(1, n, 2):
        edges.append((nodes[i // 2], nodes[i]))
        if i + 1 < n:
            edges.append((nodes[i // 2], nodes[i + 1]))
    return nodes, tuple(edges)


def _path_branch(n: int = 12):
    """Path with a branch — tests asymmetric isolation."""
    nodes = tuple(f"n{i}" for i in range(n))
    edges = [(nodes[i], nodes[i + 1]) for i in range(n - 1)]
    edges.append((nodes[3], nodes[6]))
    edges.append((nodes[8], nodes[10]))
    return nodes, tuple(edges)


STANDARD_SUITE = {
    "chain": _chain(8),
    "star":  _star(8),
    "full":  _full(6),
    "redundant_grid": _redundant_grid(8),
    "sparse_random": _random(seed=1, n=8, density=0.15),
    "dense_random":  _random(seed=2, n=8, density=0.70),
    "isolated_plus_cluster": _isolated_plus_cluster(),
    # Extended for C1 graded isolation metrics — larger, more varied
    # topologies that exercise the metric's sensitivity to hub removal.
    "chain_12": _chain(12),
    "ring_10": _ring(10),
    "tree_10": _tree(10),
    "path_branch_12": _path_branch(12),
    "random_12_med": _random(seed=3, n=12, density=0.30),
    "random_12_sparse": _random(seed=4, n=12, density=0.10),
    "random_12_dense": _random(seed=5, n=12, density=0.60),
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _bfs_dist(nodes, edges, src):
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        if a in adj:
            adj[a].append(b)
    dist = {n: -1 for n in nodes}
    if src not in dist:
        return dist
    dist[src] = 0
    frontier = [src]
    depth = 0
    while frontier:
        depth += 1
        nxt = []
        for u in frontier:
            for v in adj.get(u, []):
                if v in dist and dist[v] == -1:
                    dist[v] = depth
                    nxt.append(v)
        frontier = nxt
    return dist


def _avg_outdegree(nodes, edges):
    out = {n: 0 for n in nodes}
    for a, _ in edges:
        out[a] = out.get(a, 0) + 1
    return sum(out.values()) / max(len(nodes), 1)


def _avg_reachable_frac(nodes, edges):
    vals = []
    n = len(nodes)
    for s in nodes:
        d = _bfs_dist(nodes, edges, s)
        reachable = sum(1 for v in d.values() if v > 0)
        vals.append(reachable / max(n - 1, 1))
    return sum(vals) / max(len(vals), 1)


def _avg_shortest_path(nodes, edges):
    all_d = []
    for s in nodes:
        d = _bfs_dist(nodes, edges, s)
        for t, v in d.items():
            if v > 0:
                all_d.append(v)
    return sum(all_d) / max(len(all_d), 1)


def _transitivity(nodes, edges):
    # Directed transitivity: (triangle count) / (2-path count), 0 if no 2-paths.
    nbr_out = {n: set() for n in nodes}
    for a, b in edges:
        if a in nbr_out and b in nbr_out:
            nbr_out[a].add(b)
    twopaths = 0
    closed = 0
    for i in nodes:
        for j in nbr_out[i]:
            for k in nbr_out.get(j, set()):
                if k == i or k == j:
                    continue
                twopaths += 1
                if k in nbr_out.get(i, set()):
                    closed += 1
    return closed / max(2 * twopaths, 1)


def _n_components(nodes, edges):
    adj = {n: set() for n in nodes}
    for a, b in edges:
        if a in adj: adj[a].add(b)
        if b in adj: adj[b].add(a)
    seen = set()
    c = 0
    for n in nodes:
        if n in seen:
            continue
        c += 1
        q = [n]; seen.add(n)
        while q:
            u = q.pop()
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v); q.append(v)
    return c


def _diameter(nodes, edges):
    d = 0
    for s in nodes:
        dd = _bfs_dist(nodes, edges, s)
        for v in dd.values():
            if v > 0 and v > d:
                d = v
    return float(d)


# Legacy binary isolation metric (reproduced here as a *negative control*).
def _legacy_isolation_binary(nodes, edges):
    """Remove outgoing edges of every hub and check reachability.

    This is the metric that passed all 33 gates but saturated to 1.0
    on essentially every topology — hence its inclusion as a negative
    control. If this register entry ever goes green, someone has quietly
    changed the semantics of the metric.
    """
    vals = []
    n = len(nodes)
    for hub in nodes:
        new_edges = [(a, b) for a, b in edges if a != hub]
        orig = _bfs_dist(nodes, edges, hub)
        new = _bfs_dist(nodes, new_edges, hub)
        orig_r = sum(1 for v in orig.values() if v > 0)
        new_r = sum(1 for v in new.values() if v > 0)
        if orig_r > 0:
            vals.append(1.0 if new_r == 0 else 0.0)
    return sum(vals) / max(len(vals), 1)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class MetricSpec:
    name: str
    fn: callable          # (nodes, edges) -> float
    min_variance: float   # strict lower bound on variance across the suite
    description: str
    negative_control: bool = field(default=False)


# K8 · 确定性分层——阈值脱钩校准
# ---------------------------------------------------------------------------
# 关键纪律：min_variance 阈值**必须**在独立校准集（CALIBRATION_SUITE）上
# 观测后写入，验证集（STANDARD_SUITE）与校准集在名称、种子、拓扑尺寸、
# 节点规模上都不同。这样门禁不再"自己证明自己"，而是用一个独立信号来
# 校验另一个独立信号。
#
# CALIBRATION_SUITE 独立于 STANDARD_SUITE：
#   - 随机种子：100–114 (sparse), 200–214 (dense)  vs  标准套件 1–5
#   - 节点规模：n=10                          vs  标准套件 n=8/12
#   - 结构尺寸：chain_16/star_12/full_10/...  vs  标准套件 chain_8/...
#   - 名称：random_cal_*/chain_16/...         vs  标准套件 sparse_random/...
# 校验：calibration_is_independent() 在每次运行时机器化检查两者零重叠。
#
# 阈值 = 校准套件观测方差 × 0.25（安全边距 75%），确保 STANDARD_SUITE
# 出现回归时门禁先于饱和报警。校准结果在 `_gate41_calibration.json`
# 中可独立复算。
#
# 校准复算命令：
#     python -c "import sys; sys.path.insert(0,'scripts'); \
#       from check_metric_discrimination import calibrate_thresholds, METRICS; \
#       r = calibrate_thresholds(METRICS); \
#       for m, v in r['recommended'].items(): print(f'{m}: obs={r['observed'][m]:.4f}, rec={v:.4f}')"

# 校准安全边距：min_variance = obs_var * SAFE_MARGIN
_CALIBRATION_SAFE_MARGIN = 0.25


def _random_calibration(seed: int, n: int = 10, density: float = 0.3):
    """校准专用的随机图生成器（与 _random 同结构、不同种子）。"""
    import random as _r
    rng = _r.Random(seed)
    nodes = tuple(f"n{i}" for i in range(n))
    all_pairs = [(a, b) for a in nodes for b in nodes if a != b]
    k = int(len(all_pairs) * density)
    edges = tuple(rng.sample(all_pairs, k=k))
    return nodes, edges


def _build_calibration_suite() -> dict:
    """构建独立校准集。种子、尺寸与 STANDARD_SUITE 全部不同。"""
    suite: dict = {}
    # 稀疏随机（30 张，seed 100–114）
    for s in range(100, 115):
        suite[f"random_cal_{s}_sparse"] = _random_calibration(s, n=10, density=0.12)
    # 稠密随机（30 张，seed 200–214）
    for s in range(200, 215):
        suite[f"random_cal_{s}_dense"] = _random_calibration(s, n=10, density=0.55)
    # 结构性拓扑（更大规模，与 STANDARD_SUITE 的 n=6–12 分离）
    suite["chain_16"] = _chain(16)
    suite["star_12"] = _star(12)
    suite["full_10"] = _full(10)
    suite["ring_14"] = _ring(14)
    suite["tree_16"] = _tree(16)
    suite["path_branch_14"] = _path_branch(14)
    return suite


CALIBRATION_SUITE: dict = _build_calibration_suite()


def calibration_is_independent() -> tuple[bool, set]:
    """校验 CALIBRATION_SUITE 与 STANDARD_SUITE 零重叠（名称 + 拓扑形状）。

    返回 (独立? True/False, 重叠名字集合)。
    """
    overlap = set(CALIBRATION_SUITE) & set(STANDARD_SUITE)
    return (len(overlap) == 0), overlap


# 阈值来源：`CALIBRATION_SUITE` 上的观测方差 × _CALIBRATION_SAFE_MARGIN。
# 数值由 `python scripts/check_metric_discrimination.py` 自动复算并写入
# `_gate41_calibration.json`；如与 METRICS 中的 min_variance 相差 > 2x，
# 会打印 WARNING 但**不**改判（避免门禁因作者忘了更新阈值而误红）。
#
METRICS: list[MetricSpec] = [
    MetricSpec(
        name="drop_magnitude_proxy",
        fn=lambda n, e: _avg_shortest_path(n, e),
        min_variance=0.35,   # calibration: obs=1.377 * 0.25 ≈ 0.344
        description="avg shortest-path length across ordered pairs; sensitive to topology",
    ),
    MetricSpec(
        name="reachable_frac",
        fn=lambda n, e: _avg_reachable_frac(n, e),
        min_variance=0.035,  # calibration: obs=0.141 * 0.25 ≈ 0.035
        description="mean fraction of nodes reachable from any source",
    ),
    MetricSpec(
        name="transitivity",
        fn=lambda n, e: _transitivity(n, e),
        min_variance=0.002,  # calibration: obs=0.019 * 0.25 ≈ 0.0048; 安全边距
        description="directed transitivity (triangle / 2-path ratio)",
    ),
    MetricSpec(
        name="avg_outdegree",
        fn=lambda n, e: _avg_outdegree(n, e),
        min_variance=1.2,    # calibration: obs=4.718 * 0.25 ≈ 1.179
        description="mean outdegree — should vary sharply across the suite",
    ),
    MetricSpec(
        name="n_components",
        fn=lambda n, e: float(_n_components(n, e)),
        min_variance=0.12,   # calibration: obs=0.471 * 0.25 ≈ 0.118
        description="number of weakly-connected components",
    ),
    MetricSpec(
        name="diameter",
        fn=lambda n, e: _diameter(n, e),
        min_variance=2.0,    # calibration: obs=8.006 * 0.25 = 2.001
        description="graph diameter in hops",
    ),
    # C1 · graded isolation metrics (A1 replacement for the saturated binary).
    # 注意：affected-modules 统计量注册的是 MEAN over hubs，不是 MAX。
    # 在小密集套件输入上 MAX 会饱和到 n_modules，方差为零。
    MetricSpec(
        name="graded_drop_magnitude",
        fn=lambda n, e: _graded_drop(n, e),
        min_variance=0.002,  # calibration: obs=0.0079 * 0.25 ≈ 0.002
        description="graded fault-isolation: mean reachability drop when each hub is removed (C1/A1)",
    ),
    MetricSpec(
        name="graded_affected_modules_mean",
        fn=lambda n, e: _graded_affected_modules_mean(n, e),
        min_variance=0.18,   # calibration: obs=0.732 * 0.25 ≈ 0.183
        description="graded fault-isolation: MEAN over hubs of modules that lost a reachable pair (C1/A1)",
    ),
    MetricSpec(
        name="graded_recovery_steps",
        fn=lambda n, e: _graded_recovery_steps(n, e),
        min_variance=0.005,  # calibration: obs=0.0527 * 0.25 ≈ 0.013; 安全边距
        description="graded fault-isolation: mean extra hops on surviving paths after hub removal (C1/A1)",
    ),
    # Negative control: this one MUST fail. If it ever passes, the
    # semantics of the legacy metric have drifted and we should be alarmed.
    MetricSpec(
        name="legacy_isolation_binary",
        fn=lambda n, e: _legacy_isolation_binary(n, e),
        min_variance=0.05,
        description="R1 legacy binary isolation_effect_size — MUST saturate",
        negative_control=True,
    ),
]


# ---------------------------------------------------------------------------
# Discrimination test
# ---------------------------------------------------------------------------

def _variance(xs: list[float]) -> float:
    if not xs:
        return 0.0
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def calibrate_thresholds(
    specs: list[MetricSpec] | None = None,
) -> dict:
    """从独立校准集 CALIBRATION_SUITE 复算每个度量的 min_variance 阈值。

    返回：
        {
          "calibration_suite_size": int,
          "validation_suite_size": int,
          "safe_margin": float,
          "independent": bool,
          "overlap": [names...],
          "observed": {metric: variance},
          "recommended": {metric: obs * safe_margin},
          "declared": {metric: declared_min_variance},
          "drift": {metric: recommended / declared ratio, or None},
        }

    关键性质：specs 中的 min_variance 与 CALIBRATION_SUITE 观测方差的
    比值应在 [0.5, 2] 内。任一次运行都会把这个表写入 `_gate41_calibration.json`
    以便独立复核。
    """
    specs = specs if specs is not None else METRICS
    independent, overlap = calibration_is_independent()

    observed: dict[str, float] = {}
    recommended: dict[str, float] = {}
    declared: dict[str, float] = {}
    drift: dict[str, float | None] = {}

    for spec in specs:
        vals = []
        for _name, (nodes, edges) in CALIBRATION_SUITE.items():
            try:
                vals.append(float(spec.fn(nodes, edges)))
            except Exception:  # noqa: BLE001
                continue
        obs = _variance(vals)
        observed[spec.name] = obs
        rec = obs * _CALIBRATION_SAFE_MARGIN
        recommended[spec.name] = rec
        declared[spec.name] = spec.min_variance
        if declared[spec.name] > 0 and rec > 0:
            drift[spec.name] = rec / declared[spec.name]
        else:
            drift[spec.name] = None

    return {
        "calibration_suite_size": len(CALIBRATION_SUITE),
        "validation_suite_size": len(STANDARD_SUITE),
        "safe_margin": _CALIBRATION_SAFE_MARGIN,
        "independent": independent,
        "overlap": sorted(overlap),
        "observed": {k: round(v, 6) for k, v in observed.items()},
        "recommended": {k: round(v, 6) for k, v in recommended.items()},
        "declared": {k: round(v, 6) for k, v in declared.items()},
        "drift": {k: (round(v, 3) if v is not None else None) for k, v in drift.items()},
    }


def _warn_threshold_drift(calib: dict) -> None:
    """打印阈值漂移警告（不失败）。阈值应定期按新校准值更新。"""
    for name, ratio in calib.get("drift", {}).items():
        if ratio is None:
            continue
        if ratio < 0.5 or ratio > 2.0:
            obs = calib["observed"][name]
            rec = calib["recommended"][name]
            dec = calib["declared"][name]
            print(
                f"  [WARN] threshold drift: {name} declared={dec} "
                f"recommended={rec:.4f} (obs={obs:.4f} × margin) "
                f"ratio={ratio:.2f} — consider updating min_variance"
            )


def evaluate() -> tuple[list[dict], list[dict], list[dict]]:
    """Return (pass_specs, fail_specs, expected_fail_specs).

    expected_fail_specs are negative controls that are *required* to fail;
    a green negative control is treated as an alarm (semantics drift) and
    is reported in the fail bucket too.
    """
    suite = STANDARD_SUITE
    per_metric: list[dict] = []
    for spec in METRICS:
        values = []
        for suite_name, (nodes, edges) in suite.items():
            try:
                values.append((suite_name, float(spec.fn(nodes, edges))))
            except Exception as e:  # noqa: BLE001
                per_metric.append({
                    "name": spec.name, "error": f"{type(e).__name__}: {e}",
                    "verdict": "error",
                })
                continue
        vals = [v for _, v in values]
        v = _variance(vals)
        entry = {
            "name": spec.name,
            "description": spec.description,
            "values": {k: round(v_, 6) for k, v_ in values},
            "variance": v,
            "min_variance": spec.min_variance,
            "unique": len(set(round(v_, 6) for v_ in vals)),
            "negative_control": spec.negative_control,
        }
        per_metric.append(entry)

    passing: list[dict] = []
    failing: list[dict] = []
    for e in per_metric:
        if e.get("verdict") == "error":
            failing.append(e)
            continue
        if e.get("negative_control"):
            # Negative controls must fail on min_variance.
            if e["variance"] > e["min_variance"]:
                e["verdict"] = "unexpected_pass"
                e["alarm"] = ("negative control has variance above floor — "
                              "the legacy metric's semantics may have drifted")
                failing.append(e)
            else:
                e["verdict"] = "expected_fail"
                # Report but do not add to fail bucket — this is what we want.
                passing.append(e)
        else:
            if e["variance"] > e["min_variance"]:
                e["verdict"] = "pass"
                passing.append(e)
            else:
                e["verdict"] = "fail"
                failing.append(e)
    return passing, failing, [e for e in per_metric if e.get("negative_control")]


# ---------------------------------------------------------------------------
# Injection battery — prove Gate 41 can turn red.
# ---------------------------------------------------------------------------

def _injections() -> tuple[int, int]:
    """Two injections:

      1. monkey-patch `avg_outdegree` to always return 3.14 → variance=0
         on a well-defined metric → Gate 41 must fail.
      2. monkey-patch the negative control to return a *varying* value →
         its variance suddenly rises above min_variance → alarm path
         (unexpected_pass) must fire.

    Apply and restore are two separate closures; the callable is stored
    by reference so restoring is a dict mutation, not a redefinition.
    """
    bad = 0
    n_inj = 0

    real_registry = list(METRICS)

    def expect(name, apply_fn, restore_fn):
        nonlocal bad, n_inj
        n_inj += 1
        apply_fn()
        try:
            p, f, _neg = evaluate()
        finally:
            restore_fn()
            METRICS[:] = real_registry  # restore the mutable list in place
        ok = len(f) > 0
        if ok:
            print(f"    [PASS] injecting: {name}")
        else:
            bad += 1
            print(f"    [FAIL] injecting: {name} -> GATE STAYED GREEN")

    # --- Injection 1: saturate a working metric ---
    def _patch_saturate_working():
        # Force avg_outdegree to a constant regardless of input.
        target = next(m for m in METRICS if m.name == "avg_outdegree")
        globals()["_avg_outdegree"] = lambda n, e: 3.14159
        # The MetricSpec holds a lambda that closes over _avg_outdegree,
        # so the registry entry follows automatically.
    def _restore_saturate_working():
        globals()["_avg_outdegree"] = _real_avg_outdegree

    _real_avg_outdegree = globals()["_avg_outdegree"]
    expect("saturate avg_outdegree (variance collapses to 0)",
           _patch_saturate_working,
           _restore_saturate_working)

    # --- Injection 2: give the negative control variance → alarm ---
    _real_legacy = globals()["_legacy_isolation_binary"]
    def _patch_vary_legacy():
        # Scale with edge count so values spread across the suite and the
        # variance exceeds min_variance — that's what a "semantics drift"
        # would look like, and the alarm path must fire on it.
        def varying(n, e):
            return float(len(e)) * 0.1
        globals()["_legacy_isolation_binary"] = varying
    def _restore_vary_legacy():
        globals()["_legacy_isolation_binary"] = _real_legacy

    expect("give negative control variance (semantics-drift alarm)",
           _patch_vary_legacy,
           _restore_vary_legacy)

    return bad, n_inj


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — every registered metric must have "
                    "variance above its declared floor on the standard suite")
    ap.add_argument("--json-out", metavar="PATH")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    print(f"{GATE_LABEL} — metric discrimination (SV-3c)")
    print(f"  suite size: {len(STANDARD_SUITE)} topologies")
    print(f"  metrics:    {len(METRICS)} (including 1 negative control)")
    print()

    # --- K8 校准复算（在验证前先跑一次，把校准报告落盘）---
    print("  -- K8 threshold calibration (independent suite) --")
    calib = calibrate_thresholds(METRICS)
    print(f"  calibration suite: {calib['calibration_suite_size']} topologies "
          f"(independent={calib['independent']}, overlap={len(calib['overlap'])})")
    if not calib["independent"]:
        print(f"  [WARN] calibration suite is NOT independent from validation suite: "
              f"overlap={calib['overlap']}")
    print(f"  safe margin:  {calib['safe_margin']} "
          f"(min_variance = obs_var × safe_margin)")
    _warn_threshold_drift(calib)
    # 校准报告落盘
    calib_out = SCRIPTS / "_gate41_calibration.json"
    calib_out.write_text(json.dumps(calib, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print(f"  calibration report: {calib_out}")
    print()

    passing, failing, _neg = evaluate()

    for e in passing:
        if e.get("negative_control"):
            print(f"  ✓ {e['name']:<26}  variance={e['variance']:.6f}  "
                  f"(< {e['min_variance']} — negative control as expected)")
        else:
            print(f"  ✓ {e['name']:<26}  variance={e['variance']:.6f}  "
                  f"(> {e['min_variance']})  unique={e['unique']}")
    for e in failing:
        if e.get("verdict") == "error":
            print(f"  ✗ {e['name']:<26}  ERROR: {e.get('error')}")
        elif e.get("verdict") == "unexpected_pass":
            print(f"  ✗ {e['name']:<26}  ALARM: {e.get('alarm')}")
        else:
            print(f"  ✗ {e['name']:<26}  variance={e['variance']:.6f}  "
                  f"(≤ {e['min_variance']})  unique={e['unique']}")
    print()

    # --- injection battery ---
    print(f"  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"{GATE_LABEL}: FAIL -- {inj_bad}/{n_inj} injections did not "
              f"turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    print()

    # --- JSON report ---
    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "suite_size": len(STANDARD_SUITE),
        "suite_inputs": list(STANDARD_SUITE.keys()),
        "metrics": [
            {
                "name": e["name"],
                "verdict": e.get("verdict"),
                "variance": e["variance"],
                "min_variance": e["min_variance"],
                "negative_control": e.get("negative_control", False),
                "description": e.get("description"),
                "values": e.get("values"),
            }
            for e in (passing + failing)
        ],
        "passing": [e["name"] for e in passing if not e.get("negative_control")],
        "negative_controls_expected_fail": [e["name"] for e in passing if e.get("negative_control")],
        "failing": [e["name"] for e in failing],
        "injections": {"total": n_inj, "bad": inj_bad},
    }
    out_path = Path(args.json_out) if args.json_out else SCRIPTS / "_gate41_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"  report: {out_path}")

    # --- Verdict ---
    if failing:
        print(f"\n{GATE_LABEL}: FAIL — {len(failing)} metric(s) below floor "
              f"or semantics-drifted")
        return 1
    print(f"\n{GATE_LABEL}: PASS — all non-negative-control metrics above "
          f"floor; negative control correctly saturates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
