#!/usr/bin/env python3
"""GATE 40 — dual-implementation cross-check (SV-2).

Why this exists
---------------
A single implementation of a metric can silently encode a design
assumption that a human reviewer never notices. Two independent
implementations — with different algorithms, different data structures,
even different loops — that *disagree* on the same input are the only
in-tree mechanism that catches this class of bug.

Gate 40 demands that every critical graph-theoretic metric be
implemented twice and that the two implementations agree on a standard
suite within a numerical tolerance of 1e-9. If they drift, the gate
fails — the disagreement is evidence that at least one of them is
wrong.

Metric pairs (independent algorithms)
-------------------------------------
  1. `n_components`
       A: BFS / DFS on the undirected adjacency
       B: Union-Find (weighted) — completely different data structure

  2. `is_connected`
       A: BFS from node 0, count reached
       B: Kruskal-style: sort edges by weight (all=1), union-find, then
          check if root(0) == root(i) for all i.

  3. `spectral_radius` (undirected)
       A: numpy.linalg.eigvalsh on the (symmetrised) adjacency matrix
       B: pure-Python power iteration (no numpy)

The last one deliberately avoids numpy for the second implementation —
if numpy and the pure-Python version disagree, one of them has a
normalisation / ordering bug.

Injection battery
-----------------
Two injections:

  1. add a tiny offset (1e-12) to one `n_components` implementation →
     the two disagree → gate fails.
  2. swap the two `spectral_radius` implementations' internal order of
     operations (transpose / conjugate-transpose mismatch) → the two
     disagree on non-symmetric input → gate fails.

Apply / restore are structurally separate closures over the module
globals dict; no state leaks between injections.

Usage:
    python scripts/check_dual_implementation.py
    python scripts/check_dual_implementation.py --tolerance 1e-9
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

GATE_ID = 40
GATE_LABEL = f"GATE {GATE_ID}"


# ---------------------------------------------------------------------------
# Standard input suite (small, deterministic, structurally varied).
# Same suite as Gate 41 to keep the two gates' inputs comparable.
# ---------------------------------------------------------------------------

def _full(n: int):
    nodes = tuple(f"n{i}" for i in range(n))
    return nodes, tuple((a, b) for a in nodes for b in nodes if a != b)

def _chain(n: int):
    nodes = tuple(f"n{i}" for i in range(n))
    return nodes, tuple((nodes[i], nodes[i + 1]) for i in range(n - 1))

def _star(n: int):
    nodes = tuple(f"n{i}" for i in range(n))
    return nodes, tuple((nodes[0], b) for b in nodes[1:])

def _disconnected_duo():
    # Two separate triangles — tests that components > 1.
    nodes = tuple(f"n{i}" for i in range(6))
    edges = tuple((a, b) for a, b in
                  [("n0", "n1"), ("n1", "n2"), ("n0", "n2"),
                   ("n3", "n4"), ("n4", "n5"), ("n3", "n5")])
    return nodes, edges

def _path_plus_cycle():
    # Path n0→n1→n2 plus cycle n2-n3-n4-n2, plus a bridge n4-n5.
    nodes = tuple(f"n{i}" for i in range(6))
    edges = tuple([("n0", "n1"), ("n1", "n2"),
                   ("n2", "n3"), ("n3", "n4"), ("n4", "n2"),
                   ("n4", "n5")])
    return nodes, edges


STANDARD_SUITE = {
    "chain": _chain(6),
    "star":  _star(6),
    "full":  _full(5),
    "disconnected_duo": _disconnected_duo(),
    "path_plus_cycle":  _path_plus_cycle(),
}


# ---------------------------------------------------------------------------
# Metric A: n_components via BFS
# ---------------------------------------------------------------------------

def n_components_bfs(nodes, edges):
    adj = {n: set() for n in nodes}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b); adj[b].add(a)
    seen = set()
    count = 0
    for start in nodes:
        if start in seen:
            continue
        count += 1
        q = deque([start])
        seen.add(start)
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
    return count


# ---------------------------------------------------------------------------
# Metric B: n_components via Union-Find
# ---------------------------------------------------------------------------

class _UF:
    def __init__(self, members):
        self.parent = {m: m for m in members}
        self.size = {m: 1 for m in members}

    def find(self, x):
        while self.parent[x] != x:
            # Path halving.
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]


def n_components_unionfind(nodes, edges):
    uf = _UF(nodes)
    for a, b in edges:
        if a in uf.parent and b in uf.parent:
            uf.union(a, b)
    roots = set()
    for n in nodes:
        roots.add(uf.find(n))
    return len(roots)


# ---------------------------------------------------------------------------
# Metric A: is_connected via BFS from node 0
# ---------------------------------------------------------------------------

def is_connected_bfs(nodes, edges):
    if not nodes:
        return True
    adj = {n: set() for n in nodes}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b); adj[b].add(a)
    start = nodes[0]
    seen = {start}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in seen:
                seen.add(v); q.append(v)
    return seen == set(nodes)


# ---------------------------------------------------------------------------
# Metric B: is_connected via Kruskal / Union-Find on edge weights
# ---------------------------------------------------------------------------

def is_connected_kruskal(nodes, edges):
    """Union edges in sorted order, then check if root(start) == root(any).

    All edges are weight 1 (i.e. the graph is unweighted); the sort is
    stable but irrelevant here. The Kruskal-style traversal is kept to
    demonstrate that a very different algorithmic path yields the same
    boolean result as BFS.
    """
    if not nodes:
        return True
    uf = _UF(nodes)
    # Sort edges for determinism; order is irrelevant for connectivity.
    for a, b in sorted(edges):
        if a in uf.parent and b in uf.parent:
            uf.union(a, b)
    root0 = uf.find(nodes[0])
    return all(uf.find(n) == root0 for n in nodes)


# ---------------------------------------------------------------------------
# Metric A: spectral radius via numpy eigenvalues
# ---------------------------------------------------------------------------

def spectral_radius_numpy(nodes, edges):
    """Return the largest eigenvalue of the symmetrised adjacency matrix."""
    import numpy as np
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    A = np.zeros((n, n))
    for a, b in edges:
        i, j = idx.get(a), idx.get(b)
        if i is not None and j is not None:
            A[i, j] = 1.0
            A[j, i] = 1.0   # symmetrise: undirected adjacency
    # Since A is symmetric, eigvalsh is exact.
    vals = np.linalg.eigvalsh(A)
    return float(max(vals[0], vals[-1], 0.0))


# ---------------------------------------------------------------------------
# Metric B: spectral radius via pure-Python power iteration
# ---------------------------------------------------------------------------

def spectral_radius_power(nodes, edges, max_iter: int = 500, tol: float = 1e-10):
    """Pure-Python spectral radius via power iteration on A^2.

    Why A^2 instead of A:
    For a symmetric adjacency matrix A, the eigenvalues are real but can
    be negative. For a bipartite graph (star, chain, etc.) the largest
    eigenvalue λ_max has a matching -λ_max with the same absolute
    value, so power iteration on A itself oscillates between two
    eigenvectors and the Rayleigh quotient converges to 0, not λ_max.

    Applying A^2 instead turns every eigenvalue into λ_i^2 (all
    non-negative, and the largest has multiplicity equal to the number
    of ±λ_max pairs). Power iteration on A^2 converges to λ_max^2,
    and sqrt(λ_max^2) = |λ_max| = spectral radius.

    This is a genuinely different algorithmic path from numpy's
    eigvalsh, and it works on bipartite graphs too.
    """
    n = len(nodes)
    if n == 0:
        return 0.0
    idx = {n_: i for i, n_ in enumerate(nodes)}
    A_rows = [set() for _ in range(n)]
    for a, b in edges:
        i, j = idx.get(a), idx.get(b)
        if i is not None and j is not None:
            A_rows[i].add(j)
            A_rows[j].add(i)

    # Deterministic initial vector (avoids zero-start).
    v = [0.0] * n
    v[0] = 1.0

    lam_sq = 0.0
    lam_sq_prev = None
    for _ in range(max_iter):
        # Av = A @ v
        Av = [0.0] * n
        for i in range(n):
            for j in A_rows[i]:
                Av[i] += v[j]
        # AvAv = A @ Av = A^2 @ v
        AvAv = [0.0] * n
        for i in range(n):
            for j in A_rows[i]:
                AvAv[i] += Av[j]
        # Rayleigh quotient for A^2:  v^T (A^2 v) / v^T v
        vv = sum(x * x for x in v)
        vw = sum(v[i] * AvAv[i] for i in range(n))
        lam_sq = vw / vv if vv > 0 else 0.0
        # Renormalise by AvAv so the next iteration stays bounded.
        wn = sum(x * x for x in AvAv)
        if wn > 0:
            inv = 1.0 / (wn ** 0.5)
            v = [x * inv for x in AvAv]
        # Convergence check: only after we've seen two distinct values.
        if lam_sq_prev is not None and abs(lam_sq - lam_sq_prev) < tol:
            return (lam_sq) ** 0.5
        lam_sq_prev = lam_sq
    return (lam_sq) ** 0.5


# ---------------------------------------------------------------------------
# Dual-implementation registry
# ---------------------------------------------------------------------------

PAIRS = [
    {
        "name": "n_components",
        "description": "number of weakly-connected components",
        "impl_a": ("BFS", n_components_bfs),
        "impl_b": ("Union-Find", n_components_unionfind),
    },
    {
        "name": "is_connected",
        "description": "boolean: is the graph connected?",
        "impl_a": ("BFS from node 0", is_connected_bfs),
        "impl_b": ("Kruskal / Union-Find", is_connected_kruskal),
    },
    {
        "name": "spectral_radius",
        "description": "largest eigenvalue of symmetrised adjacency matrix",
        "impl_a": ("numpy eigvalsh", spectral_radius_numpy),
        "impl_b": ("pure-Python power iteration", spectral_radius_power),
    },
]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _normalise(x):
    """Return a comparable float; treat bool/None safely."""
    if isinstance(x, bool):
        return int(x)
    if x is None:
        return 0.0
    return float(x)


def evaluate(pairs: list[dict], suite: dict, tol: float) -> list[dict]:
    rows = []
    for pair in pairs:
        a_name, a_fn = pair["impl_a"]
        b_name, b_fn = pair["impl_b"]
        pair_results = []
        max_delta = 0.0
        for suite_name, (nodes, edges) in suite.items():
            try:
                va = _normalise(a_fn(nodes, edges))
                vb = _normalise(b_fn(nodes, edges))
                delta = abs(va - vb)
                max_delta = max(max_delta, delta)
                pair_results.append({
                    "suite": suite_name,
                    "impl_a": va,
                    "impl_b": vb,
                    "delta": delta,
                    "match": delta <= tol,
                })
            except Exception as e:  # noqa: BLE001
                pair_results.append({
                    "suite": suite_name,
                    "error": f"{type(e).__name__}: {e}",
                    "match": False,
                })
        overall_match = all(r.get("match") for r in pair_results)
        rows.append({
            "name": pair["name"],
            "description": pair["description"],
            "impl_a": a_name,
            "impl_b": b_name,
            "max_delta": max_delta,
            "tolerance": tol,
            "verdict": "pass" if overall_match else "fail",
            "results": pair_results,
        })
    return rows


# ---------------------------------------------------------------------------
# Injection battery
# ---------------------------------------------------------------------------

def _injections() -> tuple[int, int]:
    """Two injections:

      1. monkey-patch `n_components_unionfind` to add 1e-12 to its
         integer result — trivially detectable via `abs(a - b) > tol`.
      2. monkey-patch `spectral_radius_power` to return a constant
         1.0 regardless of input — power iteration must move with the
         graph, so the disagreement is enormous.

    Apply / restore are structurally separate closures.
    """
    bad = 0
    n_inj = 0

    real_unionfind = globals()["n_components_unionfind"]
    real_power = globals()["spectral_radius_power"]
    original_pair_uf = PAIRS[0]["impl_b"]
    original_pair_sp = PAIRS[2]["impl_b"]

    def expect(name, apply_fn, restore_fn):
        nonlocal bad, n_inj
        n_inj += 1
        apply_fn()
        try:
            rows = evaluate(PAIRS, STANDARD_SUITE, 1e-9)
        finally:
            restore_fn()
        ok = any(r["verdict"] == "fail" for r in rows)
        if ok:
            print(f"    [PASS] injecting: {name}")
        else:
            bad += 1
            print(f"    [FAIL] injecting: {name} -> GATE STAYED GREEN")

    # --- Injection 1: perturb the Union-Find implementation ---
    # Perturbation must exceed the tolerance (1e-9) so the gate's
    # disagreement check actually fires. 1e-6 is still numerically
    # tiny in absolute terms but 1000× the tolerance.
    def perturbed_uf(nodes, edges):
        return real_unionfind(nodes, edges) + 1e-6

    def _apply_perturb_uf():
        globals()["n_components_unionfind"] = perturbed_uf
        PAIRS[0]["impl_b"] = ("Union-Find (perturbed)", perturbed_uf)

    def _restore_perturb_uf():
        globals()["n_components_unionfind"] = real_unionfind
        PAIRS[0]["impl_b"] = original_pair_uf

    expect("perturb n_components Union-Find by 1e-6",
           _apply_perturb_uf, _restore_perturb_uf)

    # --- Injection 2: collapse spectral radius power iteration to constant 1.0 ---
    def constant_sp(*_args, **_kw):
        return 1.0

    def _apply_constant_sp():
        globals()["spectral_radius_power"] = constant_sp
        PAIRS[2]["impl_b"] = ("pure-Python power iteration (constant)", constant_sp)

    def _restore_constant_sp():
        globals()["spectral_radius_power"] = real_power
        PAIRS[2]["impl_b"] = original_pair_sp

    expect("collapse spectral_radius power iteration to constant 1.0",
           _apply_constant_sp, _restore_constant_sp)

    # State must be byte-clean after the battery.
    assert globals()["n_components_unionfind"] is real_unionfind
    assert globals()["spectral_radius_power"] is real_power
    assert PAIRS[0]["impl_b"] == original_pair_uf
    assert PAIRS[2]["impl_b"] == original_pair_sp

    return bad, n_inj


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — every critical metric must be "
                    "duplicated by an independent implementation")
    ap.add_argument("--tolerance", type=float, default=1e-9)
    ap.add_argument("--json-out", metavar="PATH")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    print(f"{GATE_LABEL} — dual-implementation cross-check (SV-2)")
    print(f"  suite size: {len(STANDARD_SUITE)} topologies")
    print(f"  metric pairs: {len(PAIRS)}")
    print(f"  tolerance: {args.tolerance}")
    print()

    rows = evaluate(PAIRS, STANDARD_SUITE, args.tolerance)
    for r in rows:
        mark = "✓" if r["verdict"] == "pass" else "✗"
        print(f"  {mark} {r['name']:<22}  A={r['impl_a']:<24s}  "
              f"B={r['impl_b']:<24s}  max_delta={r['max_delta']:.2e}  "
              f"[{r['verdict']}]")

    print()
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
        "tolerance": args.tolerance,
        "suite_size": len(STANDARD_SUITE),
        "suite_inputs": list(STANDARD_SUITE.keys()),
        "metric_pairs": rows,
        "counts": {
            "pass": sum(1 for r in rows if r["verdict"] == "pass"),
            "fail": sum(1 for r in rows if r["verdict"] == "fail"),
        },
        "injections": {"total": n_inj, "bad": inj_bad},
    }
    out_path = Path(args.json_out) if args.json_out else SCRIPTS / "_gate40_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"  report: {out_path}")

    # --- Verdict ---
    if any(r["verdict"] == "fail" for r in rows):
        print(f"\n{GATE_LABEL}: FAIL — dual implementations disagree")
        return 1
    print(f"\n{GATE_LABEL}: PASS — all {len(rows)} metric pairs agree within "
          f"{args.tolerance:.1e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
