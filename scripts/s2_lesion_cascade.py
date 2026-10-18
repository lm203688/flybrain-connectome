#!/usr/bin/env python3
"""s2_lesion_cascade.py — PR-S2: lesion cascade theoretical bridge.

Links Xu 2026 Science (dendritic compartmentation → decision making) to
a computable proposition in this project:

  H1: Modular/topological compartmentation predicts higher lesion tolerance.
  H2: Lesion tolerance significantly exceeds degree-preserving null model.
  H3: Lesion tolerance negatively correlates with bridge_fraction (ρ ≤ -0.3).

Writes:
  _s2_lesion_cascade/results.json

Preregistered: docs/PR_S2_LESION_CASCADE_2026-10-18.md
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "_s2_lesion_cascade"
sys.path.insert(0, str(SCRIPTS))


# ---------- graph utilities ----------

def _make_graph(n: int, family: str, rng: random.Random) -> dict[int, list[int]]:
    g: dict[int, list[int]] = {i: [] for i in range(n)}

    def _add(u: int, v: int) -> None:
        if u != v and v not in g[u]:
            g[u].append(v)
            g[v].append(u)

    if family == "malecns_subgraph":
        for u in range(n):
            _add(u, (u + 1) % n)
            _add(u, (u + 2) % n)
        for _ in range(n // 2):
            u, v = rng.sample(range(n), 2)
            _add(u, v)
    else:
        raise ValueError(f"unknown family: {family}")
    return g


def _wiring_null(g: dict[int, list[int]], rng: random.Random) -> dict[int, list[int]]:
    n = len(g)
    degrees = [len(g[i]) for i in range(n)]
    total = sum(degrees) // 2
    if total == 0:
        return {i: [] for i in range(n)}
    stubs: list[int] = []
    for i, d in enumerate(degrees):
        stubs.extend([i] * d)
    rng.shuffle(stubs)
    new_g: dict[int, set[int]] = {i: set() for i in range(n)}
    for a, b in zip(stubs[::2], stubs[1::2]):
        if a != b:
            new_g[a].add(b)
            new_g[b].add(a)
    return {i: list(s) for i, s in new_g.items()}


# ---------- structural metrics ----------

def _bridges(g: dict[int, list[int]]) -> list[tuple[int, int]]:
    """Find bridges via DFS."""
    n = len(g)
    visited = [False] * n
    tin = [-1] * n
    low = [-1] * n
    parent = [-1] * n
    bridges: list[tuple[int, int]] = []

    def dfs(v: int, p: int) -> None:
        visited[v] = True
        tin[v] = low[v] = _tin_counter[0]
        _tin_counter[0] += 1
        parent[v] = p
        for u in g[v]:
            if u == p:
                continue
            if visited[u]:
                low[v] = min(low[v], tin[u])
            else:
                dfs(u, v)
                low[v] = min(low[v], low[u])
                if low[u] > tin[v]:
                    bridges.append((v, u))

    _tin_counter = [0]
    for start in range(n):
        if not visited[start]:
            dfs(start, -1)
    return bridges


def _bridge_fraction(g: dict[int, list[int]]) -> float:
    edges = sum(len(g[i]) for i in g) // 2
    if edges == 0:
        return 0.0
    return len(_bridges(g)) / edges


def _articulation_points(g: dict[int, list[int]]) -> int:
    n = len(g)
    visited = [False] * n
    tin = [-1] * n
    low = [-1] * n
    parent = [-1] * n
    is_ap = [False] * n
    tin_counter = [0]

    def dfs(v: int) -> None:
        visited[v] = True
        tin[v] = low[v] = tin_counter[0]
        tin_counter[0] += 1
        children = 0
        for u in g[v]:
            if u == parent[v]:
                continue
            if visited[u]:
                low[v] = min(low[v], tin[u])
            else:
                dfs(u)
                parent[u] = v
                low[v] = min(low[v], low[u])
                if low[u] >= tin[v] and parent[v] != -1:
                    is_ap[v] = True
                children += 1
        if parent[v] == -1 and children > 1:
            is_ap[v] = True

    for start in range(n):
        if not visited[start]:
            parent[start] = -1
            dfs(start)
    return sum(1 for x in is_ap if x)


def _edge_connectivity(g: dict[int, list[int]]) -> int:
    """Naive edge connectivity: min degree (lower bound)."""
    if not g:
        return 0
    return min(len(g[i]) for i in g)


def _module_score(g: dict[int, list[int]]) -> float:
    """Simplified module score: 1 - (external_edges / total_edges).

    For a single-community reference, higher = more modular.
    """
    edges = sum(len(g[i]) for i in g) // 2
    if edges == 0:
        return 0.0
    # Approximate: use bridge_fraction as inverse module proxy
    return 1 - _bridge_fraction(g)


# ---------- lesion cascade ----------

def _largest_component_size(g: dict[int, list[int]], start: int) -> int:
    id_map = {old: new for new, old in enumerate(g.keys())}
    visited = [False] * len(id_map)
    start_new = id_map[start]
    visited[start_new] = True
    size = 0
    stack = [start_new]
    while stack:
        v_new = stack.pop()
        v_old = next(k for k, v in id_map.items() if v == v_new)
        size += 1
        for u_old in g[v_old]:
            u_new = id_map.get(u_old)
            if u_new is not None and not visited[u_new]:
                visited[u_new] = True
                stack.append(u_new)
    return size


def _max_component_size(g: dict[int, list[int]]) -> int:
    nodes = list(g.keys())
    n = len(nodes)
    if n == 0:
        return 0
    # Re-index to dense 0..n-1 for visited array
    id_map = {old: new for new, old in enumerate(nodes)}
    reverse = [0] * n
    for old, new in id_map.items():
        reverse[new] = old
    visited = [False] * n
    max_size = 0
    for start_new in range(n):
        if visited[start_new]:
            continue
        start_old = reverse[start_new]
        stack = [start_new]
        visited[start_new] = True
        size = 0
        while stack:
            v_new = stack.pop()
            v_old = reverse[v_new]
            size += 1
            for u_old in g.get(v_old, []):
                u_new = id_map.get(u_old)
                if u_new is not None and not visited[u_new]:
                    visited[u_new] = True
                    stack.append(u_new)
        max_size = max(max_size, size)
    return max_size


def _lesion_cascade(
    g: dict[int, list[int]],
    k_max: int,
    deletion_strategy: str = "highest_degree",
    rng: random.Random | None = None,
) -> dict:
    """Progressively delete k nodes, tracking max component size."""
    n = len(g)
    if n == 0:
        return {"cascade_trace": [], "k_max_reached": 0, "final_mcs": 0, "lesion_tolerance": 1.0}
    cur = {i: list(g[i]) for i in g}
    rng = rng or random.Random(0)
    k_max = min(k_max, n - 1)
    trace: list[dict] = []
    for k in range(k_max + 1):
        mcs = _max_component_size(cur)
        trace.append({
            "k": k,
            "n_remaining": len(cur),
            "mcs": mcs,
            "cascade_reach": 1 - mcs / n,
        })
        # Choose next node to delete
        if k == k_max:
            break
        if deletion_strategy == "highest_degree":
            victim = max(cur.keys(), key=lambda x: len(cur[x]))
        elif deletion_strategy == "random":
            victim = rng.choice(list(cur.keys()))
        else:
            raise ValueError(deletion_strategy)
        # Remove victim
        for u in cur[victim]:
            if victim in cur[u]:
                cur[u].remove(victim)
        del cur[victim]
    final_mcs = trace[-1]["mcs"] if trace else 0
    # Lesion tolerance = average (1 - cascade_reach) across k
    avg_tolerance = sum(1 - t["cascade_reach"] for t in trace) / max(1, len(trace))
    return {
        "cascade_trace": trace,
        "k_max_reached": trace[-1]["k"] if trace else 0,
        "final_mcs": final_mcs,
        "lesion_tolerance": avg_tolerance,
        "final_cascade_reach": trace[-1]["cascade_reach"] if trace else 0.0,
    }


# ---------- statistics ----------

def _cohens_d(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    ma, mb = statistics.mean(a), statistics.mean(b)
    va, vb = statistics.variance(a), statistics.variance(b)
    n_a, n_b = len(a), len(b)
    sp = math.sqrt(((n_a - 1) * va + (n_b - 1) * vb) / (n_a + n_b - 2))
    if sp == 0:
        return 0.0
    return (ma - mb) / sp


def _bootstrap_diff_ci(
    obs: list[float], null: list[float], n_boot: int = 1000, seed: int = 42
) -> tuple[float, float, float, float]:
    """Bootstrap 95% CI for mean(obs) - mean(null). Returns (diff, ci_lo, ci_hi, p)."""
    rng = random.Random(seed)
    diff = statistics.mean(obs) - statistics.mean(null)
    diffs = []
    n_o, n_n = len(obs), len(null)
    for _ in range(n_boot):
        o = [obs[rng.randrange(n_o)] for _ in range(n_o)]
        nu = [null[rng.randrange(n_n)] for _ in range(n_n)]
        diffs.append(statistics.mean(o) - statistics.mean(nu))
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]
    hi = diffs[int(0.975 * len(diffs))]
    # One-sided p: P(diff <= 0)
    p = sum(1 for d in diffs if d <= 0) / len(diffs)
    return diff, lo, hi, p


def _spearman(x: list[float], y: list[float]) -> tuple[float, float]:
    n = len(x)
    if n < 3:
        return float("nan"), 1.0

    def _rank(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        for r, i in enumerate(order):
            ranks[i] = r + 1
        return ranks

    rx, ry = _rank(x), _rank(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return float("nan"), 1.0
    rho = num / (dx * dy)
    # Approx p from t-statistic
    t = rho * math.sqrt((n - 2) / max(1e-12, 1 - rho * rho))
    # Use a simple two-sided p approximation
    # For n >= 10, p ≈ 2 * (1 - Phi(|t|)) where Phi is standard normal CDF
    abs_t = abs(t)
    # Normal CDF approximation
    z = abs_t / math.sqrt(2)
    p_approx = math.erfc(z)
    return rho, p_approx


# ---------- main pipeline ----------

def run(
    n_nodes_set: list[int],
    seeds: int,
    k_max_ratio: float,
    bootstrap: int,
    out_dir: Path,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    per_n: dict[str, dict] = {}
    all_tolerances: list[float] = []
    all_bridges: list[float] = []

    for n in n_nodes_set:
        obs_tolerances: list[float] = []
        null_tolerances: list[float] = []
        obs_bridges: list[float] = []
        obs_module_scores: list[float] = []
        traces_sample: list[dict] = []

        for seed in range(seeds):
            rng = random.Random(seed)
            g = _make_graph(n, "malecns_subgraph", rng)
            k_max = max(1, int(k_max_ratio * n))

            # Observed lesion cascade
            obs = _lesion_cascade(g, k_max, deletion_strategy="highest_degree", rng=rng)
            obs_tolerances.append(obs["lesion_tolerance"])
            obs_bridges.append(_bridge_fraction(g))
            obs_module_scores.append(_module_score(g))

            # Null model: degree-preserving rewiring
            null_rng = random.Random(seed + 1000)
            null_g = _wiring_null(g, null_rng)
            null = _lesion_cascade(null_g, k_max, deletion_strategy="highest_degree", rng=null_rng)
            null_tolerances.append(null["lesion_tolerance"])

            if seed < 3:
                traces_sample.append({
                    "seed": seed,
                    "obs_trace": obs["cascade_trace"],
                    "null_trace": null["cascade_trace"],
                })

        all_tolerances.extend(obs_tolerances)
        all_bridges.extend(obs_bridges)

        diff, lo, hi, p = _bootstrap_diff_ci(obs_tolerances, null_tolerances, n_boot=bootstrap)
        d = _cohens_d(obs_tolerances, null_tolerances)
        rho, rho_p = _spearman(obs_tolerances, obs_bridges)

        per_n[f"n={n}"] = {
            "n_seeds": seeds,
            "k_max": int(k_max_ratio * n),
            "obs_tolerance_mean": round(statistics.mean(obs_tolerances), 4),
            "obs_tolerance_sd": round(statistics.stdev(obs_tolerances) if len(obs_tolerances) > 1 else 0, 4),
            "null_tolerance_mean": round(statistics.mean(null_tolerances), 4),
            "null_tolerance_sd": round(statistics.stdev(null_tolerances) if len(null_tolerances) > 1 else 0, 4),
            "diff_obs_minus_null": round(diff, 4),
            "diff_ci_low": round(lo, 4),
            "diff_ci_high": round(hi, 4),
            "diff_bootstrap_p": round(p, 4),
            "cohens_d": round(d, 4),
            "obs_bridge_fraction_mean": round(statistics.mean(obs_bridges), 4),
            "obs_module_score_mean": round(statistics.mean(obs_module_scores), 4),
            "lesion_bridge_spearman_rho": round(rho, 4),
            "lesion_bridge_spearman_p": round(rho_p, 4),
            "traces_sample": traces_sample,
        }

    # Global H3 across all n
    global_rho, global_rho_p = _spearman(all_tolerances, all_bridges)

    # Aggregate verdict per preregistered criteria
    h1_pass = False
    h2_pass = False
    h3_pass = False
    reasons: list[str] = []

    for label, stats in per_n.items():
        rel_improve = stats["diff_obs_minus_null"]
        if rel_improve >= 0.05:
            h1_pass = True
        if stats["diff_bootstrap_p"] < 0.05 and stats["cohens_d"] >= 0.3:
            h2_pass = True
        if stats["lesion_bridge_spearman_rho"] <= -0.3 and stats["lesion_bridge_spearman_p"] < 0.05:
            h3_pass = True

    verdict = "PASS" if (h1_pass and h2_pass and h3_pass) else (
        "PARTIAL" if (h1_pass and h2_pass) else "FAIL"
    )
    if not h1_pass:
        reasons.append("H1 FAIL: relative improvement < 0.05 in at least one n")
    if not h2_pass:
        reasons.append("H2 FAIL: p >= 0.05 or Cohen's d < 0.3")
    if not h3_pass:
        reasons.append("H3 FAIL: bridge-lesion ρ > -0.3 or p >= 0.05")

    return {
        "schema": "s2_lesion_cascade_v1",
        "prereg": "PR_S2",
        "prereg_doc": "docs/PR_S2_LESION_CASCADE_2026-10-18.md",
        "family": "malecns_subgraph",
        "k_max_ratio": k_max_ratio,
        "bootstrap_iterations": bootstrap,
        "per_n": per_n,
        "global_lesion_bridge_spearman_rho": round(global_rho, 4) if not math.isnan(global_rho) else None,
        "global_lesion_bridge_spearman_p": round(global_rho_p, 4) if not math.isnan(global_rho_p) else None,
        "h1_pass": h1_pass,
        "h2_pass": h2_pass,
        "h3_pass": h3_pass,
        "verdict": verdict,
        "verdict_reasons": reasons,
        "preregistered_criteria": {
            "h1_relative_improvement_min": 0.05,
            "h2_bootstrap_p_max": 0.05,
            "h2_cohens_d_min": 0.3,
            "h3_bridge_lesion_spearman_rho_max": -0.3,
            "h3_p_max": 0.05,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-nodes", default="20,50,100")
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--max-deletion-ratio", type=float, default=0.3)
    ap.add_argument("--bootstrap", type=int, default=500)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    n_nodes_set = [int(x.strip()) for x in args.n_nodes.split(",") if x.strip()]
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    rep = run(
        n_nodes_set=n_nodes_set,
        seeds=args.seeds,
        k_max_ratio=args.max_deletion_ratio,
        bootstrap=args.bootstrap,
        out_dir=out_dir,
    )
    with open(out_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print("S2 Lesion Cascade — PR-S2 (theoretical bridge to Xu 2026)")
    print(f"  family: malecns_subgraph")
    print(f"  n_nodes: {n_nodes_set}  seeds: {args.seeds}  k_max_ratio: {args.max_deletion_ratio}")
    print()
    for label, stats in rep["per_n"].items():
        print(f"  {label}: obs_tol={stats['obs_tolerance_mean']:.4f} "
              f"null_tol={stats['null_tolerance_mean']:.4f} "
              f"diff={stats['diff_obs_minus_null']:.4f} "
              f"CI=[{stats['diff_ci_low']:.4f},{stats['diff_ci_high']:.4f}] "
              f"p={stats['diff_bootstrap_p']:.4f} "
              f"d={stats['cohens_d']:.4f}")
        print(f"           bridge_mean={stats['obs_bridge_fraction_mean']:.4f} "
              f"rho(lesion,bridge)={stats['lesion_bridge_spearman_rho']:.4f} "
              f"p={stats['lesion_bridge_spearman_p']:.4f}")
    print()
    print(f"  H1 (relative improvement >= 0.05): {rep['h1_pass']}")
    print(f"  H2 (p<0.05 & d>=0.3): {rep['h2_pass']}")
    print(f"  H3 (bridge-lesion rho <= -0.3): {rep['h3_pass']}")
    print(f"  verdict: {rep['verdict']}")
    for r in rep["verdict_reasons"]:
        print(f"    {r}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
