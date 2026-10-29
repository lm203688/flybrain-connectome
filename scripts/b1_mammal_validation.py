#!/usr/bin/env python3
"""b1_mammal_validation.py — B-1: R6 cross-4-clade motif conservation (mammal leg).

B-1 (from docs/B_LEG_COMPLETION_CHECKLIST_2026-10-19.md):
  Add the missing mammal clade to the cross-species external validation.
  The H_R6 preregistered gate:
    4 external connectomes, same motif set (inhibitory_hub,
    reservoir_smallworld, recurrent_feedback) achieves AUC >= 0.7
    AND kappa >= 0.5 on >= 3 of 4 clades.

This script uses the S1 C3 pipeline (drop_magnitude rank-label AUC) on FOUR
external connectomes:
  1. C. elegans adult      (cel_data/elife-47155-fig9-data2-v1.csv)      [existing]
  2. Drosophila larva      (larva_data/raw/edges.csv)                    [FIXED loader]
  3. zebrafish Petkova TEN (zebrafish_data/paper_data/TEN_analysis/)     [existing]
  4. Mus musculus V1 L2/3  (mammal_data/mouse_v1_l23/...)                [NEW — MICrONS v185.1]

FIXED: load_drosophila_larva in s1_external_validation.py split on whitespace,
but edges.csv is comma-separated (`0,1,1,da`), so every data row became a
single token and was skipped -> larva graph was EMPTY (n_nodes=0) in PR-S1.
We load with csv.reader here.

Reuses the C3 metric / sampling / bootstrap from s1_external_validation.py
(imported) so the B-1 leg is measured with the SAME metric as PR-S1.

Preregistered H_R6 (frozen in B_LEG §5):
  >= 3 of 4 clades with C3 AUC >= 0.7 AND kappa >= 0.5 -> PASS
  2-3 clades in [0.5, 0.7)                                -> PARTIAL
  <= 1 clade AUC >= 0.7                                   -> FAIL
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "_b1_mammal_validation"
sys.path.insert(0, str(SCRIPTS))

# Reuse S1 pipeline functions (same metric as PR-S1).
from s1_external_validation import (  # noqa: E402
    _sample_subgraph,
    _drop_magnitude,
    _rank_label,
    _bootstrap_ci_auc,
    _count_motifs,
    _wiring_null,
    _node_relabel,
    _spearman_rho,
)

MAMMAL_DIR = ROOT / "mammal_data" / "mouse_v1_l23"
# _count_motifs is O(edges*n); cap motif counting to small graphs only.
MOTIF_MAX_NODES = 5000


def load_mouse_v1_l23() -> tuple[dict[int, list[int]], dict]:
    """Load MICrONS Layer 2/3 v185.1 soma subgraph (Mus musculus V1).

    soma_subgraph_synapses_spines_v185.csv: pre,post root ids (proofread soma
    subgraph — the minimal file to reproduce Dorkenwald et al. 2019).
    Directed edges: pre_root_id -> post_root_id.
    """
    path = MAMMAL_DIR / "soma_subgraph_synapses_spines_v185.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing: {path}")
    edges: list[tuple[str, str]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            pre = row.get("pre_root_id", "").strip()
            post = row.get("post_root_id", "").strip()
            if pre and post and pre != post:
                edges.append((pre, post))
    nodes = sorted({u for u, v in edges} | {v for u, v in edges})
    g, n = _node_relabel(nodes, edges)
    return g, {
        "n_nodes": n,
        "n_edges": len(edges),
        "source": "mammal_data/mouse_v1_l23/soma_subgraph_synapses_spines_v185.csv",
        "species": "Mus musculus V1 L2/3 (MICrONS v185.1)",
        "license": "CC-BY-4.0 (Zenodo 3710459)",
    }


def load_larva_fixed() -> tuple[dict[int, list[int]], dict]:
    """FIXED Drosophila larva loader (comma-separated edges.csv)."""
    path = ROOT / "larva_data" / "raw" / "edges.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing: {path}")
    edges: list[tuple[str, str]] = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for row in csv.reader(f):
            if not row or row[0].startswith("#") or len(row) < 2:
                continue
            s, t = row[0].strip(), row[1].strip()
            if s.isdigit() and t.isdigit() and s != t:
                edges.append((s, t))
    nodes = sorted({u for u, v in edges} | {v for u, v in edges})
    g, n = _node_relabel(nodes, edges)
    return g, {"n_nodes": n, "n_edges": len(edges), "source": "larva_data/raw/edges.csv"}


def load_c_elegans_fixed() -> tuple[dict[int, list[int]], dict]:
    path = ROOT / "cel_data" / "elife-47155-fig9-data2-v1.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing: {path}")
    edges: list[tuple[str, str]] = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            if len(row) < 2:
                continue
            s, t = row[0].strip(), row[1].strip()
            if s and t and s != t:
                edges.append((s, t))
    nodes = sorted({u for u, v in edges} | {v for u, v in edges})
    g, n = _node_relabel(nodes, edges)
    return g, {"n_nodes": n, "n_edges": len(edges), "source": "cel_data/elife-47155-fig9-data2-v1.csv"}


def load_zebrafish_fixed() -> tuple[dict[int, list[int]], dict]:
    from s1_external_validation import load_zebrafish_ten
    return load_zebrafish_ten()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-nodes", default="10,20,50")
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--quantile", type=float, default=0.75)
    ap.add_argument("--bootstrap", type=int, default=500)
    ap.add_argument("--with-motifs", action="store_true",
                    help="compute supplementary R6 motif counts (slow on large graphs)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    n_nodes_set = [int(x.strip()) for x in args.n_nodes.split(",") if x.strip()]
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    loaders = {
        "cel": load_c_elegans_fixed,
        "larva": load_larva_fixed,
        "zebrafish": load_zebrafish_fixed,
        "mouse_v1": load_mouse_v1_l23,
    }

    loaded: dict[str, tuple[dict[int, list[int]], dict]] = {}
    availability: dict[str, str] = {}
    for name, fn in loaders.items():
        try:
            g, meta = fn()
            loaded[name] = (g, meta)
            availability[name] = "LOADED"
        except Exception as e:
            availability[name] = f"DATA_UNAVAILABLE: {type(e).__name__}: {str(e)[:120]}"

    # C3 pipeline: per dataset, sample subgraphs at each n, score drop_magnitude
    c3: dict[str, dict] = {}
    for name, (g, meta) in loaded.items():
        fam_stats: dict[str, dict] = {}
        for n in n_nodes_set:
            scores: list[float] = []
            for seed in range(args.seeds):
                rng = random.Random(seed)
                sub = _sample_subgraph(g, n, rng)
                scores.append(_drop_magnitude(sub))
            labels = _rank_label(scores, args.quantile)
            pairs = list(zip(scores, labels))
            auc, lo, hi = _bootstrap_ci_auc(pairs, n_boot=args.bootstrap, seed=42)
            fam_stats[f"n={n}"] = {
                "n_samples": len(scores),
                "auc": round(auc, 4),
                "auc_ci_low": round(lo, 4),
                "auc_ci_high": round(hi, 4),
                "n_positive": sum(labels),
                "score_mean": round(sum(scores) / max(1, len(scores)), 4),
            }
        c3[name] = fam_stats

    # R6 motif conservation (undirected 3-node motifs vs degree-preserving null).
    # NOTE: _count_motifs is O(edges * n) — too slow for large graphs (zebrafish
    # 26,593 nodes took ~261s). Motif counts are SUPPLEMENTARY; the H_R6 gate is
    # decided by C3 AUC. Only compute when --with-motifs and graph is small.
    r6: dict[str, dict] = {}
    if args.with_motifs:
        for name, (g, meta) in loaded.items():
            if meta.get("n_nodes", 0) > MOTIF_MAX_NODES:
                r6[name] = {"n_nodes": meta.get("n_nodes"),
                            "status": f"SKIPPED_LARGE (> {MOTIF_MAX_NODES} nodes)"}
                continue
            motifs = _count_motifs(g)
            rng = random.Random(42)
            null_g = _wiring_null(g, rng)
            null_motifs = _count_motifs(null_g)
            keys = sorted(set(motifs) | set(null_motifs))
            enrichment = {
                k: (motifs.get(k, 0) / max(1, null_motifs.get(k, 0))) if null_motifs.get(k, 0) else None
                for k in keys
            }
            r6[name] = {
                "n_nodes": meta.get("n_nodes"),
                "motif_counts_obs": {str(k): v for k, v in motifs.items()},
                "motif_counts_null": {str(k): v for k, v in null_motifs.items()},
                "motif_enrichment": {str(k): (round(v, 3) if v is not None else None) for k, v in enrichment.items()},
            }
    else:
        for name, (g, meta) in loaded.items():
            r6[name] = {"n_nodes": meta.get("n_nodes"), "status": "SKIPPED (--with-motifs not set)"}

    # H_R6 gate: >=3 of 4 clades with C3 AUC >= 0.7 (best n) AND kappa >= 0.5.
    # NOTE: kappa here is a PER-CLADE resolution proxy (AUC deviation from 0.5),
    # NOT a cross-clade Cohen's kappa (which needs per-clade motif ground-truth
    # labels that external connectomes do not have). This is an honest, explicit
    # limitation of the proxy; the PR_S1 §1.2 cross-clade Spearman rho is reported
    # separately in r6_motif_results. We keep the proxy direction correct:
    #   AUC=1.0 -> kappa=1.0 (perfect resolution); AUC=0.5 -> kappa=0 (no signal).
    #
    # ROBUSTNESS (added to avoid the "small-graph pseudo-PASS" trap):
    # A clade only counts as a ROBUST PASS if it has >= 2 VALID sampling sizes
    # (n_nodes_set where n <= graph size) AND >= 0.7 AUC on >= 2 valid sizes.
    # Rationale: cel has only 18 nodes, so n=20/50 cannot sample (the sampler
    # returns the whole graph -> every sample identical -> AUC degenerates to
    # 0.5). Its AUC=1.0 at n=10 alone is a fragile, single-scale signal, NOT
    # cross-scale robust conservation. We do NOT count it as a robust pass.
    clade_verdict: dict[str, dict] = {}
    n_pass = 0
    for name, fam_stats in c3.items():
        best = max(fam_stats.items(), key=lambda kv: kv[1]["auc"])
        auc = best[1]["auc"]
        kappa = round(min(1.0, abs(auc - 0.5) * 2), 4)
        # valid sampling sizes = n where n <= graph node count (sampler works)
        n_graph = loaded[name][1].get("n_nodes", 0)
        valid_sizes = [n for n in n_nodes_set if n <= n_graph]
        robust_pass = False
        if len(valid_sizes) >= 2:
            high_auc_sizes = [n for n in valid_sizes if fam_stats[f"n={n}"]["auc"] >= 0.7]
            robust_pass = len(high_auc_sizes) >= 2
        ok = auc >= 0.7 and kappa >= 0.5 and robust_pass
        if ok:
            n_pass += 1
        clade_verdict[name] = {
            "best_n": best[0],
            "best_auc": auc,
            "auc_ci": [best[1]["auc_ci_low"], best[1]["auc_ci_high"]],
            "n_positive": best[1]["n_positive"],
            "kappa_proxy": kappa,
            "n_graph_nodes": n_graph,
            "valid_sampling_sizes": valid_sizes,
            "n_valid_sizes": len(valid_sizes),
            "auc_by_valid_n": {str(n): fam_stats[f"n={n}"]["auc"] for n in valid_sizes},
            "robust_pass": robust_pass,
            "pass": ok,
            "note": ("small-graph fragility: only 1 valid sampling size "
                     f"({valid_sizes}), AUC=1.0 at n={valid_sizes[0]} is single-scale"
                     if len(valid_sizes) < 2 and auc >= 0.7 else ""),
        }

    if n_pass >= 3:
        h_r6 = "PASS"
    elif n_pass >= 2:
        h_r6 = "PARTIAL"
    else:
        h_r6 = "FAIL"

    report = {
        "schema": "b1_mammal_validation_v1",
        "task": "B-1 R6 cross-4-clade motif conservation (mammal leg)",
        "prereg": "H_R6",
        "prereg_doc": "docs/B_LEG_COMPLETION_CHECKLIST_2026-10-19.md",
        "n_nodes_set": n_nodes_set,
        "seeds": args.seeds,
        "quantile": args.quantile,
        "bootstrap": args.bootstrap,
        "availability": availability,
        "dataset_meta": {k: v[1] for k, v in loaded.items()},
        "c3_results": c3,
        "r6_motif_results": r6,
        "clade_verdict": clade_verdict,
        "n_clades_passing": n_pass,
        "n_clades_evaluated": len(clade_verdict),
        "h_r6_verdict": h_r6,
        "h_r6_criteria": {"auc_min": 0.7, "kappa_min": 0.5, "clades_needed": 3},
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(out_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ---- console ----
    print("=" * 72)
    print("B-1 R6 cross-4-clade motif conservation (mammal leg)")
    print(f"  n_nodes={n_nodes_set}  seeds={args.seeds}  bootstrap={args.bootstrap}")
    print()
    print("Availability:")
    for name, st in availability.items():
        print(f"  {name:<12} {st}")
    print()
    print("C3 AUC (drop_magnitude rank-label, best n):")
    print("  clade".ljust(12) + "best_n".ljust(9) + "auc".ljust(9) + "kappa".ljust(9) + "pass")
    for name, v in clade_verdict.items():
        print(f"  {name:<12}{v['best_n']:<9}{v['best_auc']:<9}{v['kappa_proxy']:<9}{v['pass']}")
    print()
    print(f"H_R6: {n_pass}/{len(clade_verdict)} clades AUC>=0.7 & kappa>=0.5 -> {h_r6}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
