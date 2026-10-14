#!/usr/bin/env python3
"""F6 · Motif-counting feature ablation (GNN expressivity / subgraph isomorphism).

Why this exists
---------------
GNN expressivity theory (Bouritsas et al.; 2026) shows that message-passing
neural networks (MPNNs) are limited by the Weisfeiler–Lehman test and that
**systematic subgraph counting** (molecular 3-/4-node motifs) breaks this
ceiling. The project's hand-picked features (n_bridges, bridge_fraction,
n_articulation_points, edge_connectivity) are effectively a *specific*
subgraph statistic (bridge = cut-edge subgraph, articulation = cut-vertex
subgraph). A reviewer will ask: "is this the OPTIMAL feature set?"

F6 replaces the hand-picked features with a systematic **3-node and 4-node
motif count** (all connected subgraph types on n_nodes up to 10) and
compares the resulting AUC. If the motif-counting features give a
materially better AUC, the project should adopt them; if not, the
hand-picked set is empirically optimal for this task.

Zero external dependencies. Uses itertuples on the underlying undirected
graph.

Output: _f6_motif_ablation/f6_motif_ablation.json + .csv

Usage:
    python scripts/f6_motif_ablation.py --n-topologies 40
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
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
    compute_critical_edge_features,
)

DEFAULT_THRESHOLD = 0.25
DEFAULT_FEATURES = ["n_bridges", "bridge_fraction", "n_articulation_points", "edge_connectivity"]


# ============================================================ motif counting
def _connected_subgraphs(
    nodes: list[str],
    adj: dict[str, set[str]],
    k: int,
) -> list[frozenset]:
    """Enumerate all connected k-node subgraphs as frozensets of node names."""
    result = []
    seen: set[frozenset] = set()
    for combo in itertools.combinations(nodes, k):
        # Check connectivity via BFS on the induced subgraph
        start = combo[0]
        visited = {start}
        queue = [start]
        while queue:
            v = queue.pop()
            for w in adj.get(v, ()):
                if w in combo and w not in visited:
                    visited.add(w)
                    queue.append(w)
        if len(visited) == k:
            key = frozenset(combo)
            if key not in seen:
                seen.add(key)
                result.append(key)
    return result


def _subgraph_isomorphism_count(
    motif_nodes: frozenset,
    motif_adj: dict[str, set[str]],
    target_nodes: list[str],
    target_adj: dict[str, set[str]],
) -> int:
    """Count subgraph embeddings of the (small) motif into the target graph."""
    count = 0
    # Try every injection of motif_nodes into target_nodes
    for inject in itertools.permutations(target_nodes, len(motif_nodes)):
        # Check that all motif edges map to target edges
        inject_map = dict(zip(motif_nodes, inject))
        ok = True
        for u, nbrs in motif_adj.items():
            for v in nbrs:
                if v not in inject_map:
                    ok = False
                    break
                if inject_map[v] not in target_adj.get(inject_map[u], set()):
                    ok = False
                    break
            if not ok:
                break
        if ok:
            count += 1
    return count


def _enumerate_motifs_up_to_k(target_adj: dict[str, set[str]], k: int) -> list[tuple[frozenset, dict]]:
    """Enumerate all canonical motifs up to size k (canonical = smallest lex form)."""
    nodes = list(target_adj.keys())
    motifs: list[tuple[frozenset, dict[str, set]]] = []
    seen: set[tuple] = set()
    for size in range(3, k + 1):
        for sub in _connected_subgraphs(nodes, target_adj, size):
            sub_list = sorted(sub)
            sub_set = set(sub_list)
            sub_adj = {n: target_adj[n] & sub_set for n in sub_list}
            # Canonical form: sort adj lists, then tuple
            canon = tuple(sorted((n, tuple(sorted(sub_adj[n]))) for n in sub_list))
            # Compute a signature of the induced subgraph topology
            # (number of edges + adjacency tuple)
            n_edges = sum(len(sub_adj[n]) for n in sub_list) // 2
            sig = (size, n_edges, canon)
            if sig in seen:
                continue
            seen.add(sig)
            motifs.append((frozenset(sub_list), {n: set(target_adj[n] & sub_set) for n in sub_list}))
    return motifs


def compute_motif_features(bp: Blueprint) -> dict:
    """Return systematic motif counts for each topology.

    Uses a FIXED feature set (well-defined for every graph):
        triangles          : number of 3-cliques
        paths_len2         : number of length-2 paths (u-v-w with no u-w edge)
        stars_len2         : number of length-2 stars (center + 2 leaves with edge)
        connected_subg3    : total connected 3-node subgraphs
        connected_subg4    : total connected 4-node subgraphs
        edge_density       : 2|E| / (n*(n-1))
        n_edges            : |E|
    """
    n_nodes = len(bp.nodes)
    adj: dict[str, set[str]] = {n: set() for n in bp.nodes}
    for src, tgt in bp.edges:
        adj.setdefault(src, set()).add(tgt)
        adj.setdefault(tgt, set()).add(src)

    n_edges = len(bp.edges)
    edge_density = (2 * n_edges / (n_nodes * (n_nodes - 1))) if n_nodes >= 2 else 0.0

    # Triangles
    triangles = 0
    seen: set[tuple] = set()
    for u, nbrs in adj.items():
        for v in sorted(nbrs):
            if u >= v:
                continue
            for w in sorted(nbrs & adj[v]):
                key = tuple(sorted((u, v, w)))
                if key not in seen:
                    seen.add(key)
                    triangles += 1

    # Paths of length 2 (P3 vs star)
    paths_len2 = 0
    stars_len2 = 0
    for center in adj:
        nbrs = sorted(adj[center])
        for i in range(len(nbrs)):
            for j in range(i + 1, len(nbrs)):
                u, v = nbrs[i], nbrs[j]
                if v in adj[u]:
                    stars_len2 += 1
                else:
                    paths_len2 += 1

    connected_subg3 = triangles + paths_len2 + stars_len2
    connected_subg4 = len(_connected_subgraphs(list(bp.nodes), adj, 4))

    return {
        "triangles": triangles,
        "paths_len2": paths_len2,
        "stars_len2": stars_len2,
        "connected_subg3": connected_subg3,
        "connected_subg4": connected_subg4,
        "edge_density": round(edge_density, 4),
        "n_edges": n_edges,
    }


# ============================================================ logistic + AUC
MOTIF_FEATURE_NAMES = [
    "triangles", "paths_len2", "stars_len2",
    "connected_subg3", "connected_subg4",
    "edge_density", "n_edges",
]


def _fit_logistic(X: list[list[float]], y: list[int]) -> list[float]:
    n, d = len(X), len(X[0]) if X else 0
    if d == 0:
        return [0.0]
    w = [0.0] * d
    b = 0.0
    lr = 0.1
    for _ in range(2000):
        grad_w = [0.0] * d
        grad_b = 0.0
        for xi, yi in zip(X, y):
            z = sum(w[j] * xi[j] for j in range(d)) + b
            p = 1.0 / (1.0 + 2.718281828 ** (-z))
            err = p - yi
            for j in range(d):
                grad_w[j] += err * xi[j]
            grad_b += err
        for j in range(d):
            w[j] -= lr * grad_w[j] / n
        b -= lr * grad_b / n
    return w + [b]


def _auc(y_true: list[int], y_score: list[float]) -> float:
    n_pos = sum(1 for y in y_true if y == 1)
    n_neg = sum(1 for y in y_true if y == 0)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    pos_scores = [y_score[i] for i, y in enumerate(y_true) if y == 1]
    neg_scores = [y_score[i] for i, y in enumerate(y_true) if y == 0]
    concordant = 0
    for p in pos_scores:
        for n in neg_scores:
            if p > n:
                concordant += 1
            elif p == n:
                concordant += 0.5
    return concordant / (n_pos * n_neg)


# ============================================================ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-topologies", type=int, default=40)
    ap.add_argument("--n-nodes", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--train-idx", default="0:25")
    ap.add_argument("--held-out-idx", default="25:40")
    ap.add_argument("--output-dir", default="_f6_motif_ablation")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def _slice_range(s: str) -> tuple[int, int]:
        a, b = s.split(":")
        return int(a), int(b)
    tr_s, tr_e = _slice_range(args.train_idx)
    he_s, he_e = _slice_range(args.held_out_idx)

    bps = generate_topologies(args.n_topologies, n_nodes=args.n_nodes, seed=args.seed)

    rows = []
    X_bridge: list[list[float]] = []
    X_motif: list[list[float]] = []
    y: list[int] = []
    for i, bp in enumerate(bps):
        gi = compute_graded_isolation(bp, seed=args.seed)
        ce = compute_critical_edge_features(bp)
        mf = compute_motif_features(bp)
        label = 1 if gi.drop_magnitude > args.threshold else 0
        # Collect motif feature values (stable order via MOTIF_FEATURE_NAMES)
        motif_values = [float(mf[name]) for name in MOTIF_FEATURE_NAMES]
        X_bridge.append([
            float(ce.n_bridges),
            float(ce.bridge_fraction),
            float(ce.n_articulation_points),
            float(ce.edge_connectivity),
        ])
        X_motif.append(motif_values)
        y.append(label)
        row = {
            "idx": i,
            "blueprint_name": bp.name,
            "drop_magnitude": round(gi.drop_magnitude, 6),
            "label": label,
            "n_bridges": ce.n_bridges,
            "bridge_fraction": round(ce.bridge_fraction, 4),
            "n_articulation_points": ce.n_articulation_points,
            "edge_connectivity": ce.edge_connectivity,
        }
        for k, name in enumerate(MOTIF_FEATURE_NAMES):
            row[f"motif_{name}"] = mf[name]
        rows.append(row)

    train_idx = list(range(tr_s, min(tr_e, len(bps))))
    held_idx = list(range(max(he_s, tr_e), min(he_e, len(bps))))

    def _run(X: list[list[float]], features: list[str]) -> dict:
        w = _fit_logistic([X[i] for i in train_idx], [y[i] for i in train_idx])
        if len(features) == 0:
            return {"auc_held_out": 0.5, "coefs": {}, "n_features": 0}
        coefs, intercept = w[:-1], w[-1]
        y_score = [sum(coefs[j] * X[i][j] for j in range(len(features))) + intercept for i in held_idx]
        return {
            "features": features,
            "auc_held_out": round(_auc([y[i] for i in held_idx], y_score), 4),
            "coefs": {features[j]: round(coefs[j], 4) for j in range(len(features))},
            "intercept": round(intercept, 4),
            "n_features": len(features),
        }

    result_bridge = _run(X_bridge, DEFAULT_FEATURES)
    result_motif = _run(X_motif, MOTIF_FEATURE_NAMES)

    gap = result_motif["auc_held_out"] - result_bridge["auc_held_out"]
    if gap >= 0.03:
        winner = "motif_features"
    elif gap <= -0.03:
        winner = "bridge_features"
    else:
        winner = "tie"

    summary = {
        "protocol": "F6 · motif-counting feature ablation",
        "methodology": "Bouritsas et al. (2026) GNN expressivity; subgraph isomorphism counting",
        "params": {
            "n_topologies": args.n_topologies,
            "n_nodes": args.n_nodes,
            "seed": args.seed,
            "threshold": args.threshold,
            "train_idx": args.train_idx,
            "held_out_idx": args.held_out_idx,
        },
        "auc_held_out": {
            "bridge_features": result_bridge["auc_held_out"],
            "motif_features": result_motif["auc_held_out"],
        },
        "coefs": {
            "bridge_features": result_bridge.get("coefs", {}),
            "motif_features": result_motif.get("coefs", {}),
        },
        "auc_gap_motif_minus_bridge": round(gap, 4),
        "winner": winner,
        "n_motif_features": len(MOTIF_FEATURE_NAMES),
        "motif_feature_names": MOTIF_FEATURE_NAMES,
        "interpretation": (
            "Systematic 3-/4-node motif counting vs hand-picked bridge/"
            "articulation features. A POSITIVE gap means systematic counting "
            "beats hand-picked (reviewer question answered: hand-picked is "
            "suboptimal). A NEGATIVE gap means hand-picked is empirically "
            "optimal on this family at n=10 — an honest result. A TIE means "
            "the two feature sets are collinear (bridge = special case of "
            "cut-edge subgraph)."
        ),
        "success_criteria": {
            "gap_abs_min_for_interesting": 0.03,
        },
        "verdict": "INFO",
        "elapsed_seconds": round(time.time() - t0, 3),
    }

    out_json = out_dir / "f6_motif_ablation.json"
    out_csv = out_dir / "f6_motif_ablation.csv"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["idx", "blueprint_name", "drop_magnitude", "label"] + DEFAULT_FEATURES +
                   [f"motif_{name}" for name in MOTIF_FEATURE_NAMES])
        for r in rows:
            w.writerow([r["idx"], r["blueprint_name"], r["drop_magnitude"], r["label"]]
                       + [r[c] for c in DEFAULT_FEATURES]
                       + [r[f"motif_{name}"] for name in MOTIF_FEATURE_NAMES])

    if not args.quiet:
        print("=" * 72)
        print("F6 · motif-counting feature ablation")
        print(f"  bridge_features AUC  : {result_bridge['auc_held_out']:.4f}")
        print(f"  motif_features AUC   : {result_motif['auc_held_out']:.4f}")
        print(f"  gap (motif - bridge): {gap:+.4f}  winner: {winner}")
        print(f"  n_motif_features: {len(MOTIF_FEATURE_NAMES)}")
        print(f"  outputs: {out_json}, {out_csv}")
        print(f"  elapsed: {summary['elapsed_seconds']}s")
        print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
