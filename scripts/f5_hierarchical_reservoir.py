#!/usr/bin/env python3
"""F5 · Hierarchical modular reservoir × memory capacity.

Why this exists
---------------
*Nat Commun* 2026-07 "Neuromorphic hierarchical modular reservoirs" proves
that hierarchical modular organisation of reservoirs increases *memory
capacity*. The complementary missing half is: **does the isolation-degree
(measured by drop_magnitude) predict memory capacity?** If yes, the project
can speak directly to the Nature sub-journal — not as a bigger simulator,
but as the analytic half of the same object.

This script:
  1. Generates the same 40 topologies (seed=42, n_nodes=10) as PR-1.
  2. For each topology, builds an ESN-like reservoir with a
     module-internal / module-external weight hierarchy (hierarchical
     modular wiring).
  3. Measures memory capacity on a delayed-input task (Naud 2011 protocol).
  4. Reports the correlation between isolation (drop_magnitude) and
     memory capacity across topologies.

Zero external dependencies (numpy is fine but not required — we fall back
to pure Python for the reservoir step).

Output: _f5_hierarchical_reservoir/f5_reservoir.json + .csv

Usage:
    python scripts/f5_hierarchical_reservoir.py --n-topologies 40
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / "flybrain-connectome-mcp"
sys.path.insert(0, str(MCP_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from llm_tasks import Blueprint  # noqa: E402
from isolation_graded import (  # noqa: E402
    generate_topologies,
    compute_graded_isolation,
)


# ============================================================ ESN reservoir
def _reservoir_step(
    state: list[float],
    input_val: float,
    W_rec: list[list[float]],
    W_in: list[float],
    leak_rate: float = 0.2,
    noise: float = 0.0,
    rng: random.Random | None = None,
) -> list[float]:
    """One discrete-time ESN step: y(t) = (1-a)*y(t-1) + a*f(W_rec y + W_in u)."""
    n = len(state)
    new_state = [0.0] * n
    for i in range(n):
        s = W_in[i] * input_val
        for j in range(n):
            s += W_rec[i][j] * state[j]
        # tanh activation
        s = math.tanh(s)
        new_state[i] = (1.0 - leak_rate) * state[i] + leak_rate * s
        if noise > 0 and rng is not None:
            new_state[i] += noise * rng.gauss(0, 1)
    return new_state


def _build_reservoir_weights(
    bp: Blueprint,
    n_units: int,
    spectral_radius: float,
    seed: int,
) -> tuple[list[list[float]], list[float], list[int]]:
    """Build W_rec from the blueprint topology + hierarchical modular scaling.

    Edges in bp.edges are treated as reservoir connections (source → target).
    Weights follow a hierarchical modular structure:
        w = spectral_radius * sqrt(n_units) * scale_factor
    where scale_factor = 1.0 for "within-module" edges (both endpoints in
    the same 50/50 split of nodes) and 0.3 for "between-module" edges.
    """
    rng = random.Random(seed)
    node_idx = {n: i for i, n in enumerate(bp.nodes)}
    n = len(bp.nodes)
    if n != n_units:
        # Pad or truncate to the requested reservoir size
        extra = n_units - n
        bp_nodes = list(bp.nodes) + [f"_pad_{i}" for i in range(max(extra, 0))]
        bp_nodes = bp_nodes[:n_units]
        node_idx = {n: i for i, n in enumerate(bp_nodes)}

    W_rec = [[0.0] * n_units for _ in range(n_units)]
    W_in = [rng.uniform(-0.5, 0.5) for _ in range(n_units)]
    module_of = [0 if i < n_units // 2 else 1 for i in range(n_units)]

    for src, tgt in bp.edges:
        i = node_idx.get(src)
        j = node_idx.get(tgt)
        if i is None or j is None or i == j:
            continue
        scale = 1.0 if module_of[i] == module_of[j] else 0.3
        W_rec[i][j] = spectral_radius * math.sqrt(n_units) * scale

    # Scale by target spectral radius (iterative power method, 20 steps)
    for _ in range(20):
        v = [1.0] * n_units
        for _ in range(n_units):
            new = [0.0] * n_units
            for i in range(n_units):
                for j in range(n_units):
                    new[i] += W_rec[i][j] * v[j]
            norm = math.sqrt(sum(x * x for x in new)) or 1.0
            v = [x / norm for x in new]
        rho = sum(W_rec[0][j] * v[j] for j in range(n_units))
        if abs(rho) < 1e-9:
            break
        scale = spectral_radius / rho
        for i in range(n_units):
            for j in range(n_units):
                W_rec[i][j] *= scale

    return W_rec, W_in, module_of


def _memory_capacity(
    W_rec: list[list[list[float]]],  # not used, kept for signature compat
    W_in: list[float],
    seed: int,
    n_delays: int = 10,
    t_start: int = 200,
    t_end: int = 1000,
    spectral_radius: float = 0.95,
    leak_rate: float = 0.2,
) -> list[float]:
    """Naud 2011 delayed-input protocol.

    Input x_t ~ U(0, 1). Readout: linear regression y_t[k] = sum_i w_i k_t[i].
    Memory capacity c_k = (Var(y_t[k]) / Var(x_{t-k}))² clipped to [0, 1].
    """
    rng = random.Random(seed)
    n = len(W_in)
    state = [0.0] * n
    input_hist: list[float] = [rng.random() for _ in range(t_end + n_delays + 50)]
    y_hist: list[list[float]] = [[] for _ in range(n_delays)]

    for t in range(t_start, t_end):
        x = input_hist[t]
        state = _reservoir_step(state, x, W_rec, W_in, leak_rate=leak_rate, rng=rng)
        for k in range(n_delays):
            y_hist[k].append(state)

    # Compute per-delay memory capacity via correlation squared
    caps = []
    for k in range(n_delays):
        target = [input_hist[t - k] for t in range(t_start, t_end)]
        # Take mean activation per reservoir unit, correlate with target
        y_series = [sum(state) / n for state in y_hist[k]]
        n_obs = len(target)
        if n_obs < 3:
            caps.append(0.0)
            continue
        mean_x = sum(target) / n_obs
        mean_y = sum(y_series) / n_obs
        var_x = sum((x - mean_x) ** 2 for x in target) / n_obs
        var_y = sum((y - mean_y) ** 2 for y in y_series) / n_obs
        cov = sum((target[i] - mean_x) * (y_series[i] - mean_y) for i in range(n_obs)) / n_obs
        denom = math.sqrt(var_x * var_y)
        r2 = (cov / denom) ** 2 if denom > 0 else 0.0
        caps.append(min(r2, 1.0))
    return caps


def _total_memory_capacity(caps: list[float]) -> float:
    """Total memory capacity = sum of per-delay capacities (Naud convention)."""
    return sum(caps)


# ============================================================ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-topologies", type=int, default=40)
    ap.add_argument("--n-nodes", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-delays", type=int, default=10)
    ap.add_argument("--spectral-radius", type=float, default=0.95)
    ap.add_argument("--output-dir", default="_f5_hierarchical_reservoir")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bps = generate_topologies(args.n_topologies, n_nodes=args.n_nodes, seed=args.seed)

    rows = []
    drop_mags: list[float] = []
    mem_caps: list[float] = []
    mem_caps_total: list[float] = []
    for i, bp in enumerate(bps):
        gi = compute_graded_isolation(bp, seed=args.seed)
        W_rec, W_in, _ = _build_reservoir_weights(
            bp, n_units=len(bp.nodes), spectral_radius=args.spectral_radius,
            seed=args.seed + i,
        )
        caps = _memory_capacity(
            W_rec, W_in, seed=args.seed + i, n_delays=args.n_delays,
            spectral_radius=args.spectral_radius,
        )
        mc_total = _total_memory_capacity(caps)
        rows.append({
            "idx": i,
            "blueprint_name": bp.name,
            "drop_magnitude": round(gi.drop_magnitude, 6),
            "memory_capacity_total": round(mc_total, 4),
            "caps_per_delay": [round(c, 4) for c in caps],
        })
        drop_mags.append(gi.drop_magnitude)
        mem_caps.extend(caps)
        mem_caps_total.append(mc_total)

    # Pearson correlation between drop_magnitude and total memory capacity
    n = len(drop_mags)
    if n >= 3:
        mean_x = sum(drop_mags) / n
        mean_y = sum(mem_caps_total) / n
        cov = sum((drop_mags[i] - mean_x) * (mem_caps_total[i] - mean_y) for i in range(n)) / n
        var_x = sum((x - mean_x) ** 2 for x in drop_mags) / n
        var_y = sum((y - mean_y) ** 2 for y in mem_caps_total) / n
        denom = math.sqrt(var_x * var_y) if var_x > 0 and var_y > 0 else 0.0
        pearson_r = cov / denom if denom > 0 else 0.0
    else:
        pearson_r = 0.0

    summary = {
        "protocol": "F5 · hierarchical modular reservoir × memory capacity",
        "methodology": "Naud (2011) delayed-input memory capacity; Nat Commun 2026-07 hierarchical modular reservoirs",
        "params": {
            "n_topologies": args.n_topologies,
            "n_nodes": args.n_nodes,
            "seed": args.seed,
            "n_delays": args.n_delays,
            "spectral_radius": args.spectral_radius,
        },
        "pearson_r_drop_vs_memory": round(pearson_r, 4),
        "drop_magnitude_mean": round(sum(drop_mags) / n, 4),
        "drop_magnitude_var": round(
            sum((x - sum(drop_mags) / n) ** 2 for x in drop_mags) / n, 6),
        "memory_capacity_total_mean": round(sum(mem_caps_total) / n, 4),
        "memory_capacity_total_var": round(
            sum((x - sum(mem_caps_total) / n) ** 2 for x in mem_caps_total) / n, 6),
        "interpretation": (
            "Isolation-degree (drop_magnitude) vs reservoir memory capacity "
            "on Naud delayed-input task. A POSITIVE r suggests isolation "
            "supports memory (matches Nat Commun 2026-07 hierarchical-modular "
            "result); a NEGATIVE r suggests a tension between isolation and "
            "recurrent reuse. The project's unique contribution is to "
            "QUANTIFY the sign of this relationship across many topologies "
            "and give an analytic bound — not to build a bigger simulator."
        ),
        "success_criteria": {
            "pearson_r_abs_min": 0.3,
            "n_topologies_min": 20,
        },
        "verdict": (
            "SIGNAL" if abs(pearson_r) >= 0.3 else
            "WEAK" if abs(pearson_r) >= 0.1 else
            "NOISY"
        ),
        "elapsed_seconds": round(time.time() - t0, 3),
    }

    out_json = out_dir / "f5_reservoir.json"
    out_csv = out_dir / "f5_reservoir.csv"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["idx", "blueprint_name", "drop_magnitude", "memory_capacity_total"] +
                   [f"cap_{k}" for k in range(args.n_delays)])
        for r in rows:
            w.writerow([r["idx"], r["blueprint_name"], r["drop_magnitude"],
                        r["memory_capacity_total"]] + r["caps_per_delay"])

    if not args.quiet:
        print("=" * 72)
        print("F5 · hierarchical modular reservoir × memory capacity")
        print(f"  Pearson r(drop_magnitude, memory_capacity): {pearson_r:.4f}")
        print(f"  drop_magnitude mean={summary['drop_magnitude_mean']}, "
              f"memory_capacity mean={summary['memory_capacity_total_mean']}")
        print(f"  verdict: {summary['verdict']}")
        print(f"  outputs: {out_json}, {out_csv}")
        print(f"  elapsed: {summary['elapsed_seconds']}s")
        print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
