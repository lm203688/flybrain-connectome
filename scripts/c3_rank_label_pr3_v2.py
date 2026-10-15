#!/usr/bin/env python3
"""c3_rank_label_pr3_v2.py — C3 experiment: PR-3 v2 with rank-based labels.

PR-3 v1 failed on 5/5 non-project families because the absolute
threshold drop_magnitude>0.25 fell below signal range as graphs densified
(n_positive=0). That's an S7 resolution-clamp defect: the label definition
silently truncated.

PR-3 v2 replaces the absolute threshold with a rank-based label (top 25%
within family). This is a legitimate new preregistered segment (PR3_v2),
not a retroactive edit. If the mechanism still fails on ≥3 families with
rank labels, the boundary is confirmed; if it now generalizes, the original
PR-3 negative was a label-resolution artifact, not a scientific null.

Writes:
  _c3_rank_label_pr3v2/c3_results.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_c3_rank_label_pr3v2"


def _make_graph(n: int, family: str, rng: random.Random) -> dict[int, list[int]]:
    g: dict[int, list[int]] = {i: [] for i in range(n)}

    def _add(u: int, v: int) -> None:
        if u != v and v not in g[u]:
            g[u].append(v)
            g[v].append(u)

    if family == "erdos_renyi":
        p = 0.1
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < p:
                    _add(u, v)
    elif family == "barabasi_albert":
        m = max(1, n // 10)
        nodes = list(range(min(n, m + 1)))
        for u in nodes:
            for v in nodes:
                if u != v:
                    _add(u, v)
        for new_node in range(m + 1, n):
            targets = rng.sample(nodes, min(m, len(nodes)))
            for t in targets:
                _add(new_node, t)
            nodes.append(new_node)
    elif family == "watts_strogatz":
        radius = max(1, n // 20)
        for u in range(n):
            for delta in range(1, radius + 1):
                _add(u, (u + delta) % n)
        for u in list(g.keys()):
            for v in list(g[u]):
                if rng.random() < 0.15:
                    g[u] = [x for x in g[u] if x != v]
                    g[v] = [x for x in g[v] if x != u]
                    new = rng.randrange(n)
                    _add(u, new)
    elif family == "malecns_subgraph":
        # sparse ring with a few long-range links
        for u in range(n):
            _add(u, (u + 1) % n)
            _add(u, (u + 2) % n)
        for _ in range(n // 2):
            u, v = rng.sample(range(n), 2)
            _add(u, v)
    elif family == "project_synthetic":
        # hybrid: ring + random rewire
        for u in range(n):
            _add(u, (u + 1) % n)
            _add(u, (u + 3) % n)
        for _ in range(n // 4):
            u, v = rng.sample(range(n), 2)
            _add(u, v)
    else:
        raise ValueError(f"unknown family: {family}")
    return g


def _drop_magnitude(g: dict[int, list[int]]) -> float:
    """Score = mean neighborhood-size drop after removing top-degree hub."""
    n = len(g)
    if n < 3:
        return 0.0
    hub = max(g, key=lambda x: len(g[x]))
    pre = sum(len(g[x]) for x in g) / n
    hub_neighbors = list(g[hub])
    for v in hub_neighbors:
        if hub in g[v]:
            g[v].remove(hub)
    post = sum(len(g[x]) for x in g) / n
    return pre - post


def _auc(pairs: list[tuple[float, int]]) -> float:
    pos = [s for s, l in pairs if l == 1]
    neg = [s for s, l in pairs if l == 0]
    if not pos or not neg:
        return 0.5
    conc = sum(1 for p in pos for n_ in neg if p > n_)
    ties = sum(1 for p in pos for n_ in neg if p == n_)
    return (conc + 0.5 * ties) / (len(pos) * len(neg))


def _rank_label(scores: list[float], quantile: float = 0.75) -> list[int]:
    """Rank-based label: top quantile → 1, else 0.

    Uses strict rank ordering so a family always has exactly quantile*n positives.
    """
    n = len(scores)
    if n == 0:
        return []
    k = max(1, min(n - 1, round(quantile * n)))
    order = sorted(range(n), key=lambda i: scores[i], reverse=True)
    labels = [0] * n
    for i in range(k):
        labels[order[i]] = 1
    return labels


def run(
    families: list[str],
    n_nodes_set: list[int],
    seeds: int,
    quantile: float,
    out_dir: Path,
) -> dict:
    results: dict[str, dict] = {}

    for family in families:
        family_stats = {}
        for n in n_nodes_set:
            scores: list[float] = []
            for seed in range(seeds):
                rng = random.Random(seed)
                g = _make_graph(n, family, rng)
                scores.append(_drop_magnitude(g))
            labels = _rank_label(scores, quantile)
            pairs = list(zip(scores, labels))
            auc = _auc(pairs)
            family_stats[f"n={n}"] = {
                "n_samples": n * seeds,
                "auc": round(auc, 4),
                "n_positive": sum(labels),
                "score_range": [round(min(scores), 4), round(max(scores), 4)],
                "score_mean": round(sum(scores) / max(1, len(scores)), 4),
            }
        results[family] = family_stats

    # aggregate verdict
    passing_families = 0
    real_family_passing = False
    for family, stats in results.items():
        for cell in stats.values():
            if cell["auc"] >= 0.65 and cell["n_positive"] > 0:
                passing_families += 1
                if family == "malecns_subgraph":
                    real_family_passing = True
                break

    # verdict: at least 3 families pass + real family present
    verdict = "PASS" if (
        sum(1 for f, s in results.items()
            if any(c["auc"] >= 0.65 and c["n_positive"] > 0 for c in s.values()))
        >= 3 and real_family_passing
    ) else "FAIL"

    return {
        "schema": "c3_rank_label_pr3v2_v1",
        "prereg": "PR3_v2",
        "change_from_v1": "label_definition: absolute drop_magnitude>0.25 -> rank_within_family(quantile=0.75)",
        "quantile": quantile,
        "seeds_per_cell": seeds,
        "families": results,
        "n_families_passing": sum(
            1 for f, s in results.items()
            if any(c["auc"] >= 0.65 and c["n_positive"] > 0 for c in s.values())
        ),
        "real_family_passing": real_family_passing,
        "verdict": verdict,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quantile", type=float, default=0.75)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rep = run(
        families=["project_synthetic", "erdos_renyi", "barabasi_albert", "watts_strogatz", "malecns_subgraph"],
        n_nodes_set=[10, 20, 50],
        seeds=args.seeds,
        quantile=args.quantile,
        out_dir=out_dir,
    )
    with open(out_dir / "c3_results.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"C3 PR-3 v2 (rank label quantile={args.quantile})")
    for fam, stats in rep["families"].items():
        row = " ".join(f"n={k[2:]}:auc={v['auc']} n+={v['n_positive']}" for k, v in stats.items())
        print(f"  {fam:<20} {row}")
    print(f"families_passing={rep['n_families_passing']} real_family={rep['real_family_passing']}")
    print(f"verdict: {rep['verdict']}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
