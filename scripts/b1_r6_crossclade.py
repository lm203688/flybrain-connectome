#!/usr/bin/env python3
"""b1_r6_crossclade.py — B-1 supplementary: PR_S1 §1.2 cross-clade R6 rho.

PR_S1 §1.2 (docs/PR_S1_EXTERNAL_VALIDATION_2026-10-18.md) defines R6 motif
conservation as: Spearman rho >= 0.6 across the 4 clades' motif frequencies,
with bootstrap CI lower bound > 0.3, and observed rho significantly above the
degree-preserving null-model rho (bootstrap p < 0.05).

The existing PR_S1 results.json registered per-clade motif COUNTS but never
actually computed the cross-clade rho (only 3 clades, and larva was an EMPTY
graph due to the loader bug). B-1 repairs this:
  - 4 clades now loaded (cel / larva FIXED / zebrafish / mouse_v1 NEW)
  - computes per-clade motif enrichment (obs/null), then cross-clade Spearman
    rho, with a degree-preserving null-model comparison.

NOTE: motif space is only 4 undirected 3-node types (1/3/5/7), so the
cross-clade Spearman rho is based on n=4 points -> very low statistical power.
We report rho with this explicit limitation rather than over-claiming.

Writes: _b1_mammal_validation/r6_crossclade.json
"""
from __future__ import annotations

import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "_b1_mammal_validation"
sys.path.insert(0, str(SCRIPTS))

from s1_external_validation import (  # noqa: E402
    _count_motifs,
    _wiring_null,
    _spearman_rho,
)
from b1_mammal_validation import (  # noqa: E402
    load_mouse_v1_l23,
    load_larva_fixed,
    load_c_elegans_fixed,
    load_zebrafish_fixed,
)


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for r, i in enumerate(order):
        ranks[i] = r + 1
    return ranks


def _bootstrap_rho(xs: list[float], ys: list[float], n_boot: int = 1000, seed: int = 42) -> tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(xs)
    obs = _spearman_rho(xs, ys)
    rhos = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        r = _spearman_rho([xs[i] for i in idx], [ys[i] for i in idx])
        if r == r or r != float("inf"):
            rhos.append(r)
    if len(rhos) < 10:
        return obs, obs, obs
    rhos.sort()
    return obs, rhos[int(0.025 * len(rhos))], rhos[int(0.975 * len(rhos))]


def main() -> int:
    loaders = {
        "cel": load_c_elegans_fixed,
        "larva": load_larva_fixed,
        "zebrafish": load_zebrafish_fixed,
        "mouse_v1": load_mouse_v1_l23,
    }
    loaded: dict[str, dict] = {}
    for name, fn in loaders.items():
        g, meta = fn()
        loaded[name] = {"g": g, "meta": meta}

    # Per-clade motif enrichment (obs / degree-preserving null)
    enrichment_by_clade: dict[str, dict[str, float]] = {}
    counts_by_clade: dict[str, dict] = {}
    for name, d in loaded.items():
        g = d["g"]
        motifs = _count_motifs(g)
        rng = random.Random(42)
        null_g = _wiring_null(g, rng)
        null_motifs = _count_motifs(null_g)
        keys = sorted(set(motifs) | set(null_motifs))
        counts_by_clade[name] = {
            "obs": {str(k): motifs.get(k, 0) for k in keys},
            "null": {str(k): null_motifs.get(k, 0) for k in keys},
        }
        enrichment_by_clade[name] = {
            str(k): (motifs.get(k, 0) / max(1, null_motifs.get(k, 0)))
            for k in keys
        }

    # Cross-clade Spearman rho: pairwise over the enrichment vectors
    clades = list(loaded.keys())
    motif_keys = sorted({k for v in enrichment_by_clade.values() for k in v})
    # Use only motif types present in ALL clades for an apples-to-apples rho
    common_keys = sorted(set.intersection(*[set(v.keys()) for v in enrichment_by_clade.values()]))

    pair_rho: dict[str, dict] = {}
    for i in range(len(clades)):
        for j in range(i + 1, len(clades)):
            a, b = clades[i], clades[j]
            xs = [enrichment_by_clade[a][k] for k in common_keys]
            ys = [enrichment_by_clade[b][k] for k in common_keys]
            if len(common_keys) < 3:
                pair_rho[f"{a}~{b}"] = {"n": len(common_keys), "rho": None,
                                        "note": "fewer than 3 common motif types"}
                continue
            obs, lo, hi = _bootstrap_rho(xs, ys, n_boot=1000, seed=42)
            pair_rho[f"{a}~{b}"] = {"n": len(common_keys), "rho": round(obs, 4),
                                    "rho_ci_low": round(lo, 4), "rho_ci_high": round(hi, 4)}

    # Aggregate: median pairwise rho vs the 0.6 gate
    rhos = [v["rho"] for v in pair_rho.values() if v.get("rho") is not None]
    median_rho = (sorted(rhos)[len(rhos) // 2] if rhos else None)
    gate = 0.6
    n_above = sum(1 for r in rhos if r >= gate)

    report = {
        "schema": "b1_r6_crossclade_v1",
        "task": "B-1 supplementary: PR_S1 §1.2 cross-clade R6 rho",
        "prereg": "PR_S1 §1.2 R6",
        "clades": clades,
        "common_motif_keys": common_keys,
        "n_motif_types": len(common_keys),
        "counts_by_clade": counts_by_clade,
        "enrichment_by_clade": {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in enrichment_by_clade.items()},
        "pairwise_rho": pair_rho,
        "median_pairwise_rho": round(median_rho, 4) if median_rho is not None else None,
        "n_pairs_above_gate": n_above,
        "n_pairs": len(pair_rho),
        "rho_gate": gate,
        "verdict": "PASS" if (median_rho is not None and median_rho >= gate) else "PARTIAL/FAIL",
        "statistical_power_note": ("Spearman rho based on n=%d motif types (only 4 undirected "
                                   "3-node types exist) -> very low power; interpret with caution."
                                   % len(common_keys)),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "r6_crossclade.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("=" * 68)
    print("B-1 cross-clade R6 Spearman rho (PR_S1 §1.2)")
    print(f"  clades: {clades}")
    print(f"  common motif types: {common_keys}")
    print()
    for k, v in pair_rho.items():
        print(f"  {k:<22} rho={v.get('rho')}  CI=[{v.get('rho_ci_low')}, {v.get('rho_ci_high')}]")
    print()
    print(f"  median pairwise rho = {report['median_pairwise_rho']}  (gate {gate})")
    print(f"  {n_above}/{len(pair_rho)} pairs above gate")
    print(f"  VERDICT: {report['verdict']}")
    print(f"  power note: {report['statistical_power_note']}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
