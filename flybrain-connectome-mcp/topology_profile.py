"""
Topology-aware structural profiling layer (Tier-1, standard library only).

WHY THIS MODULE EXISTS
----------------------
The project can already *generate* a topology and *prove where it came from*
(W3C PROV-JSON). What it could not do is answer the structural question a
downstream consumer actually asks: **"what shape is this thing, and what does
that shape imply?"** Every structural claim in the repo so far — fault
isolation 25/27, spectral radius held at 0.00-0.30%, GA -84% wire cost — was
computed by a one-off experiment script, never by a reusable, callable layer.

This module turns those one-off measurements into a first-class, reproducible
capability:

    graph  ->  structural profile  ->  comparable, hashable, honest numbers

It is deliberately **stdlib-only** (the same promise the rest of the toolkit
makes): spectral radius is computed by power iteration, not by numpy's
``eigvals``. It is also deliberately **honest**: every field that is *not*
measured (dynamics, energy, task performance) is named in ``not_measured`` so
no reader can mistake a structural number for a functional one.

This is step 1 of the topology-aware track. Wiring it into the CLI / MCP tool
registry is a separate change (it would move the advertised tool count, which
Gate 2 guards), so this file ships as a self-contained, testable layer first.

Public API
----------
    load_organism(src)              path | dict  ->  normalised organism
    build_graph(organism)           -> Graph (nodes, edges, adjacency)
    profile(src_or_graph)           -> structural profile dict
    compare(profile_a, profile_b)   -> numeric deltas
    profile_signature(profile)      -> deterministic sha256 of the structure

CLI
---
    python topology_profile.py <organism.json> [--json] [--compare <other.json>]
    python topology_profile.py --selftest

Caveat (read this before quoting a number)
------------------------------------------
Every metric here is a property of the **wiring diagram**, not of any running
system. ``spectral_radius`` is the spectral radius of the *absolute-weight*
adjacency matrix — it is an upper bound on linearised dynamics, not a
simulated activity level. ``feedback_edge_fraction`` depends on a DFS order
and is therefore an estimate, not an invariant. ``modularity_q`` uses the
module labels carried by the organism; it measures how well those labels
explain the wiring, not whether the modules are functionally distinct.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

# Metrics that a *structural* profile cannot speak to. Named explicitly so a
# downstream reader never promotes a structural number into a functional claim.
NOT_MEASURED = [
    "dynamics",            # no simulation is run
    "energy",              # no spiking model is run
    "task_performance",    # no readout / benchmark is run
    "biological_validity", # structure is not evidence of function
]

# Power iteration is capped: organisms in this library are small (<200 nodes),
# but the cap keeps the call O(1)-bounded for any accidental large input.
_SPECTRAL_MAX_ITERS = 500
_SPECTRAL_TOL = 1e-10
_SPECTRAL_NODE_CAP = 2000


class Graph:
    """Minimal directed graph with weighted edges and node metadata."""

    __slots__ = ("nodes", "edges", "out", "inc", "module_of")

    def __init__(self, nodes: list[dict], edges: list[dict]):
        self.nodes = nodes
        self.edges = edges
        self.out: dict[str, list[tuple[str, float]]] = {n["id"]: [] for n in nodes}
        self.inc: dict[str, list[tuple[str, float]]] = {n["id"]: [] for n in nodes}
        self.module_of: dict[str, Any] = {n["id"]: n.get("module") for n in nodes}
        for e in edges:
            u, v = e["from"], e["to"]
            w = float(e.get("weight", 1.0) or 0.0)
            if u not in self.out:
                self.out[u] = []
                self.inc[u] = []
                self.module_of[u] = None
            if v not in self.out:
                self.out[v] = []
                self.inc[v] = []
                self.module_of[v] = None
            self.out[u].append((v, w))
            self.inc[v].append((u, w))

    @property
    def n(self) -> int:
        return len(self.nodes)

    @property
    def m(self) -> int:
        return len(self.edges)

    def is_self_loop(self, e: dict) -> bool:
        return e["from"] == e["to"]


# --------------------------------------------------------------------------- IO

def load_organism(src: Any) -> dict:
    """Accept a path, a parsed organism doc, or a raw {nodes, edges} dict."""
    if isinstance(src, (str, Path)):
        doc = json.loads(Path(src).read_text(encoding="utf-8"))
    elif isinstance(src, dict):
        doc = src
    else:
        raise TypeError("load_organism expects a path or a dict, got %r" % type(src))
    if "organism" in doc and isinstance(doc["organism"], dict):
        org = dict(doc["organism"])
        org.setdefault("_meta", {})
        org["_meta"].setdefault("blueprint", doc.get("blueprint"))
        org["_meta"].setdefault("schema_version", doc.get("schema_version"))
        return org
    return doc


def build_graph(organism: dict) -> Graph:
    nodes = list(organism.get("nodes") or [])
    edges = list(organism.get("edges") or [])
    return Graph(nodes, edges)


# ------------------------------------------------------------------- metrics

def _degree_stats(g: Graph) -> dict:
    tot = [len(g.out[n["id"]]) + len(g.inc[n["id"]]) for n in g.nodes]
    outd = [len(g.out[n["id"]]) for n in g.nodes]
    ind = [len(g.inc[n["id"]]) for n in g.nodes]

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    def median(xs):
        if not xs:
            return 0.0
        s = sorted(xs)
        k = len(s)
        return float(s[k // 2]) if k % 2 else round((s[k // 2 - 1] + s[k // 2]) / 2, 2)

    return {
        "in_mean": mean(ind),
        "out_mean": mean(outd),
        "total_mean": mean(tot),
        "total_median": median(tot),
        "total_max": max(tot) if tot else 0,
    }


def _reciprocity(g: Graph) -> float:
    es = [(e["from"], e["to"]) for e in g.edges if not g.is_self_loop(e)]
    if not es:
        return 0.0
    present = set(es)
    mutual = sum(1 for (u, v) in es if (v, u) in present)
    return round(mutual / len(es), 4)


def _weak_components(g: Graph) -> tuple[int, int]:
    parent: dict[str, str] = {n["id"]: n["id"] for n in g.nodes}
    for e in g.edges:
        u, v = e["from"], e["to"]
        parent.setdefault(u, u)
        parent.setdefault(v, v)
        ru, rv = _find(parent, u), _find(parent, v)
        if ru != rv:
            parent[ru] = rv
    sizes: dict[str, int] = {}
    for k in parent:
        sizes[_find(parent, k)] = sizes.get(_find(parent, k), 0) + 1
    return len(sizes), (max(sizes.values()) if sizes else 0)


def _find(parent: dict, x: str) -> str:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _is_strongly_connected(g: Graph) -> bool:
    ids = [n["id"] for n in g.nodes]
    if not ids:
        return False
    if not _reachable(g, ids[0], ids, reverse=False):
        return False
    return _reachable(g, ids[0], ids, reverse=True)


def _reachable(g: Graph, start: str, ids: list[str], reverse: bool) -> bool:
    adj = g.inc if reverse else g.out
    seen, stack = {start}, [start]
    while stack:
        u = stack.pop()
        for v, _ in adj.get(u, []):
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return len(seen) >= len(ids)


def _modularity_q(g: Graph) -> float | None:
    """Newman modularity on the undirected projection, using node['module']."""
    labels = {n["id"]: n.get("module") for n in g.nodes}
    if len({v for v in labels.values() if v is not None}) < 2:
        return None
    w: dict[tuple[str, str], float] = {}
    for e in g.edges:
        if g.is_self_loop(e):
            continue
        u, v = e["from"], e["to"]
        w[(u, v)] = w.get((u, v), 0.0) + abs(float(e.get("weight", 1.0) or 0.0))
    m2 = sum(w.values()) * 2.0  # 2m on the undirected projection
    if m2 <= 0:
        return None
    deg: dict[str, float] = {n["id"]: 0.0 for n in g.nodes}
    for (u, v), val in w.items():
        deg[u] += val
        deg[v] += val
    comm: dict[Any, float] = {}
    comm_deg: dict[Any, float] = {}
    for (u, v), val in w.items():
        cu, cv = labels.get(u), labels.get(v)
        if cu == cv:
            comm[cu] = comm.get(cu, 0.0) + val
    for nid, d in deg.items():
        c = labels.get(nid)
        comm_deg[c] = comm_deg.get(c, 0.0) + d
    q = 0.0
    for c in set(comm) | set(comm_deg):
        q += (2.0 * comm.get(c, 0.0)) / m2 - (comm_deg.get(c, 0.0) / m2) ** 2
    return round(q, 4)


def _transitivity(g: Graph) -> float:
    """Global clustering coefficient on the undirected simple projection."""
    nb: dict[str, set[str]] = {n["id"]: set() for n in g.nodes}
    for e in g.edges:
        if g.is_self_loop(e):
            continue
        nb[e["from"]].add(e["to"])
        nb[e["to"]].add(e["from"])
    triads = 0
    triangles = 0
    for u, ns in nb.items():
        ns = [v for v in ns if v != u]
        k = len(ns)
        if k < 2:
            continue
        triads += k * (k - 1) / 2
        ns_set = set(ns)
        for i in range(k):
            for j in range(i + 1, k):
                if ns[j] in nb.get(ns[i], ()):
                    triangles += 1
    if triads == 0:
        return 0.0
    return round(triangles / triads, 4)


def _spectral_radius(g: Graph) -> float | None:
    """Spectral radius of the |weight| adjacency, by power iteration.

    Non-negative matrices satisfy Perron-Frobenius, so power iteration
    converges to the dominant (real, non-negative) eigenvalue. Returns None
    when the graph is too large for the cap or has no edges.
    """
    ids = [n["id"] for n in g.nodes]
    n = len(ids)
    if n == 0 or g.m == 0:
        return 0.0
    if n > _SPECTRAL_NODE_CAP:
        return None
    idx = {nid: i for i, nid in enumerate(ids)}
    rows: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for e in g.edges:
        i, j = idx.get(e["from"]), idx.get(e["to"])
        if i is None or j is None:
            continue
        rows[i].append((j, abs(float(e.get("weight", 1.0) or 0.0))))
    x = [1.0 / math.sqrt(n)] * n
    lam = 0.0
    for _ in range(_SPECTRAL_MAX_ITERS):
        y = [0.0] * n
        for i in range(n):
            acc = 0.0
            for j, w in rows[i]:
                acc += w * x[j]
            y[i] = acc
        norm = math.sqrt(sum(t * t for t in y))
        if norm == 0.0:
            return 0.0
        x = [t / norm for t in y]
        new = norm
        if abs(new - lam) < _SPECTRAL_TOL:
            lam = new
            break
        lam = new
    return round(lam, 4)


def _feedback_edge_fraction(g: Graph) -> float:
    """Fraction of edges that are DFS back-edges (feedback arcs).

    Approximate by construction: it depends on the DFS order, so it is an
    estimate of how far the wiring is from a pure feedforward DAG, not an
    invariant. A DAG returns exactly 0.0.
    """
    if g.m == 0:
        return 0.0
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n["id"]: WHITE for n in g.nodes}
    back = 0
    for root in list(color):
        if color[root] != WHITE:
            continue
        stack = [(root, iter(g.out.get(root, [])))]
        color[root] = GRAY
        while stack:
            node, it = stack[-1]
            advanced = False
            for v, _ in it:
                if color.get(v, WHITE) == GRAY:
                    back += 1
                    advanced = True
                elif color.get(v, WHITE) == WHITE:
                    color[v] = GRAY
                    stack.append((v, iter(g.out.get(v, []))))
                    advanced = True
                else:
                    advanced = True
                if advanced:
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()
    return round(back / g.m, 4)


def _motif_census(g: Graph) -> dict:
    """Directed 3-node motif census, capped for tractability."""
    ids = [n["id"] for n in g.nodes]
    if len(ids) > 200:
        return {"capped": True, "reason": "n>200"}
    out = {nid: {v for v, _ in g.out.get(nid, [])} for nid in ids}
    mutual = 0
    for u in ids:
        for v in out[u]:
            if v != u and u in out.get(v, ()):
                mutual += 1
    mutual //= 2
    ffl = 0
    cyc3 = 0
    for u in ids:
        for v in out[u]:
            if v == u:
                continue
            for w in out.get(v, ()):
                if w in (u, v):
                    continue
                if w in out[u]:
                    ffl += 1
                if u in out.get(w, ()):
                    cyc3 += 1
    return {
        "mutual_dyad": mutual,
        "feedforward_loop": ffl,
        "three_cycle": cyc3 // 3,
    }


# ------------------------------------------------------------------ profiling

def profile(src_or_graph: Any) -> dict:
    """Compute a structural profile for an organism (path, dict, or Graph)."""
    if isinstance(src_or_graph, Graph):
        g = src_or_graph
        source = "<graph>"
    else:
        organism = load_organism(src_or_graph)
        g = build_graph(organism)
        source = organism.get("_meta", {}).get("blueprint") or "<organism>"

    n, m = g.n, g.m
    density = round(m / (n * (n - 1)), 6) if n > 1 else 0.0
    self_loops = sum(1 for e in g.edges if g.is_self_loop(e))
    kinds: dict[str, int] = {}
    for e in g.edges:
        k = e.get("kind", "unknown")
        kinds[k] = kinds.get(k, 0) + 1
    inhib = sum(v for k, v in kinds.items() if "inhib" in str(k).lower())
    weak, largest = _weak_components(g)

    prof = {
        "schema_version": SCHEMA_VERSION,
        "kind": "topology_profile",
        "source": source,
        "size": {
            "n_nodes": n,
            "n_edges": m,
            "density": density,
            "self_loops": self_loops,
            "n_modules": len({v for v in g.module_of.values() if v is not None}),
        },
        "degree": _degree_stats(g),
        "reciprocity": _reciprocity(g),
        "components": {
            "weak": weak,
            "largest": largest,
            "is_strongly_connected": _is_strongly_connected(g),
        },
        "modularity_q": _modularity_q(g),
        "clustering_transitivity": _transitivity(g),
        "spectral_radius": _spectral_radius(g),
        "feedback_edge_fraction": _feedback_edge_fraction(g),
        "motifs": _motif_census(g),
        "inhibition_ratio": round(inhib / m, 4) if m else 0.0,
        "edge_kinds": kinds,
        "not_measured": NOT_MEASURED,
        "caveat": (
            "Structural profile only. spectral_radius is over the |weight| "
            "adjacency (an upper bound, not a simulated activity). "
            "feedback_edge_fraction depends on DFS order. modularity_q scores "
            "the declared module labels against the wiring, not functional "
            "distinctness."
        ),
    }
    prof["profile_signature"] = profile_signature(prof)
    return prof


_SIG_FIELDS = ("size", "degree", "reciprocity", "components",
               "modularity_q", "clustering_transitivity", "spectral_radius",
               "feedback_edge_fraction", "motifs", "inhibition_ratio")


def profile_signature(prof: dict) -> str:
    """Deterministic sha256 over the structural core of a profile."""
    core = {k: prof.get(k) for k in _SIG_FIELDS}
    blob = json.dumps(core, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def compare(a: dict, b: dict) -> dict:
    """Numeric delta of two profiles (b - a), field by field."""
    flat_a, flat_b = _flatten(a), _flatten(b)
    delta = {}
    for k in sorted(set(flat_a) & set(flat_b)):
        va, vb = flat_a[k], flat_b[k]
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            delta[k] = round(vb - va, 4)
    same = profile_signature(a) == profile_signature(b)
    return {"identical_structure": same, "delta_b_minus_a": delta}


class StructureSignatureIndex:
    """Persistent index of structural signatures for dedup and version diff.

    T4 of the foundation roadmap asks that every generated organism record a
    ``profile_signature`` and that identical structures be de-duplicated while
    structurally-different versions are diff-able.  This class is the store:

        idx = StructureSignatureIndex.load(path)   # or .new()
        status, existing = idx.add("run_7", profile)   # "new" | "duplicate"
        idx.diff("run_7", "run_8")                  # numeric delta of two entries
        idx.save(path)

    Signatures are content-addressed (sha256 of the structural core), so the
    index is stable across renames and reproducible across machines.
    """

    def __init__(self, records: dict | None = None):
        # records[name] = {"signature": ..., "source": ..., "size": ...}
        self.records: dict[str, dict] = records or {}
        self._by_sig: dict[str, str] = {}
        for name, rec in self.records.items():
            self._by_sig.setdefault(rec["signature"], name)

    @classmethod
    def new(cls) -> "StructureSignatureIndex":
        return cls({})

    @classmethod
    def load(cls, path) -> "StructureSignatureIndex":
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            return cls.new()
        doc = json.loads(p.read_text(encoding="utf-8"))
        return cls(doc.get("records", {}))

    def add(self, name: str, prof: dict) -> tuple[str, str | None]:
        """Register ``name`` -> ``prof``.

        Returns ("new", None) or ("duplicate", <existing name sharing the sig>).
        A name that already exists is overwritten (its old signature freed).
        """
        sig = prof.get("profile_signature") or profile_signature(prof)
        if name in self.records:
            old = self.records.pop(name)
            if self._by_sig.get(old["signature"]) == name:
                del self._by_sig[old["signature"]]
        if sig in self._by_sig:
            existing = self._by_sig[sig]
            # keep the new name pointing at the same signature
            self.records[name] = {
                "signature": sig,
                "source": prof.get("source", ""),
                "size": prof.get("size", {}),
            }
            return "duplicate", existing
        self._by_sig[sig] = name
        self.records[name] = {
            "signature": sig,
            "source": prof.get("source", ""),
            "size": prof.get("size", {}),
        }
        return "new", None

    def diff(self, name_a: str, name_b: str) -> dict:
        """Numeric delta between two registered entries (b - a)."""
        ra, rb = self.records.get(name_a), self.records.get(name_b)
        if ra is None or rb is None:
            missing = name_a if ra is None else name_b
            return {"error": "no such entry: %s" % missing}
        same = ra["signature"] == rb["signature"]
        delta = {}
        for k in ("n_nodes", "n_edges", "density"):
            va = ra.get("size", {}).get(k)
            vb = rb.get("size", {}).get(k)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                delta[k] = round(vb - va, 6)
        return {"identical_structure": same, "size_delta_b_minus_a": delta}

    def duplicates(self) -> list[tuple[str, str]]:
        """All (name, canonical_name) pairs that share a signature."""
        out = []
        seen: dict[str, str] = {}
        for name, rec in self.records.items():
            sig = rec["signature"]
            if sig in seen:
                out.append((name, seen[sig]))
            else:
                seen[sig] = name
        return out

    def save(self, path) -> None:
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"schema_version": SCHEMA_VERSION,
                                  "records": self.records}, indent=2,
                                 ensure_ascii=False), encoding="utf-8")


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flatten(v, prefix + k + "."))
        elif isinstance(v, (int, float, bool)):
            out[prefix + k] = v
    return out


# ------------------------------------------------------------------ self-test

def _self_test() -> int:
    """Assertions that pin the layer's semantics, run by CI/manually."""
    fails: list[str] = []

    def check(name, cond, detail=""):
        print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name,
                                ("- " + detail) if detail else ""))
        if not cond:
            fails.append(name)

    # 1. empty graph
    p0 = profile({"nodes": [], "edges": []})
    check("empty graph: zero edges", p0["size"]["n_edges"] == 0)
    check("empty graph: rho 0", p0["spectral_radius"] == 0.0)

    # 2. a pure 3-node chain 1->2->3 is a DAG: zero feedback, zero cycles
    chain = {"nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
             "edges": [{"from": "1", "to": "2"}, {"from": "2", "to": "3"}]}
    pc = profile(chain)
    check("chain is a DAG (0 feedback)", pc["feedback_edge_fraction"] == 0.0)
    check("chain: 3-cycles 0", pc["motifs"]["three_cycle"] == 0)
    check("chain: weakly connected", pc["components"]["weak"] == 1)

    # 3. a 3-cycle is fully feedback
    cyc = {"nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
           "edges": [{"from": "1", "to": "2"}, {"from": "2", "to": "3"},
                     {"from": "3", "to": "1"}]}
    pcy = profile(cyc)
    check("3-cycle detected", pcy["motifs"]["three_cycle"] == 1, str(pcy["motifs"]))
    check("3-cycle: strongly connected", pcy["components"]["is_strongly_connected"])
    check("3-cycle: feedback > 0", pcy["feedback_edge_fraction"] > 0.0)

    # 4. mutual dyad
    mut = {"nodes": [{"id": "1"}, {"id": "2"}],
           "edges": [{"from": "1", "to": "2"}, {"from": "2", "to": "1"}]}
    pm = profile(mut)
    check("mutual dyad detected", pm["motifs"]["mutual_dyad"] == 1)
    check("reciprocity == 1.0", pm["reciprocity"] == 1.0, str(pm["reciprocity"]))

    # 5. spectral radius of a 2-cycle with weight w is w
    w2 = {"nodes": [{"id": "1"}, {"id": "2"}],
          "edges": [{"from": "1", "to": "2", "weight": 2.0},
                    {"from": "2", "to": "1", "weight": 2.0}]}
    check("rho of 2-cycle(2.0) == 2.0",
          abs(profile(w2)["spectral_radius"] - 2.0) < 1e-6,
          str(profile(w2)["spectral_radius"]))

    # 6. modularity: two clean modules beat one blob
    two = {"nodes": [{"id": "a1", "module": 0}, {"id": "a2", "module": 0},
                     {"id": "b1", "module": 1}, {"id": "b2", "module": 1}],
           "edges": [{"from": "a1", "to": "a2"}, {"from": "b1", "to": "b2"}]}
    check("modularity_q present for 2 modules", profile(two)["modularity_q"] is not None)

    # 7. determinism: same structure -> same signature
    s1 = profile(chain)["profile_signature"]
    s2 = profile({"nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
                  "edges": [{"from": "1", "to": "2"}, {"from": "2", "to": "3"}]})["profile_signature"]
    check("signature deterministic", s1 == s2, s1[:24])
    check("signature change-sensitive",
          s1 != profile(cyc)["profile_signature"])

    # 8. StructureSignatureIndex: dedup + diff (T4 signature store)
    idx = StructureSignatureIndex.new()
    st_a, _ = idx.add("run_a", profile(chain))
    st_b, existing = idx.add("run_b", profile(chain))
    check("index dedup: identical structure flagged duplicate",
          st_b == "duplicate" and existing == "run_a", str((st_b, existing)))
    st_c, _ = idx.add("run_c", profile(cyc))
    check("index: distinct structure is new", st_c == "new")
    d = idx.diff("run_a", "run_c")
    check("index diff reports non-identical", d["identical_structure"] is False)
    check("index diff detects edge-count change",
          d["size_delta_b_minus_a"].get("n_edges") == 1, str(d))

    print("=" * 60)
    if fails:
        print("TOPOLOGY PROFILE SELF-TEST: FAIL (%d)" % len(fails))
        return 1
    print("TOPOLOGY PROFILE SELF-TEST: PASS")
    return 0


# ------------------------------------------------------------------------ CLI

def _cli(argv: list[str]) -> int:
    if "--selftest" in argv:
        return _self_test()
    if "--list-dups" in argv:
        idx_path = None
        if "--index" in argv:
            idx_path = argv[argv.index("--index") + 1]
        idx = StructureSignatureIndex.load(idx_path) if idx_path else \
            StructureSignatureIndex.new()
        dups = idx.duplicates()
        if not dups:
            print("no duplicate structures in the index")
            return 0
        for name, canonical in dups:
            print("  DUPLICATE  %s  ==  %s" % (name, canonical))
        return 0
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    pa = profile(args[0])
    if "--index" in argv:
        ip = argv[argv.index("--index") + 1]
        idx = StructureSignatureIndex.load(ip)
        name = Path(args[0]).stem
        status, existing = idx.add(name, pa)
        idx.save(ip)
        if status == "duplicate":
            print("INDEX  %s is a DUPLICATE of %s (same signature)" % (name, existing))
        else:
            print("INDEX  %s registered (new signature)" % name)
    if "--compare" in argv:
        idx = argv.index("--compare")
        pb = profile(argv[idx + 1])
        print(json.dumps(compare(pa, pb), ensure_ascii=False, indent=2))
        return 0
    if "--json" in argv:
        print(json.dumps(pa, ensure_ascii=False, indent=2))
        return 0
    print("topology profile  %s" % pa["source"])
    print("-" * 56)
    print("  nodes %-5d edges %-5d density %s  modules %s"
          % (pa["size"]["n_nodes"], pa["size"]["n_edges"],
             pa["size"]["density"], pa["size"]["n_modules"]))
    print("  spectral_radius      %s" % pa["spectral_radius"])
    print("  modularity_q         %s" % pa["modularity_q"])
    print("  reciprocity          %s" % pa["reciprocity"])
    print("  transitivity         %s" % pa["clustering_transitivity"])
    print("  feedback_edge_frac   %s" % pa["feedback_edge_fraction"])
    print("  inhibition_ratio     %s" % pa["inhibition_ratio"])
    print("  motifs               %s" % pa["motifs"])
    print("  strongly_connected   %s" % pa["components"]["is_strongly_connected"])
    print("  signature            %s" % pa["profile_signature"][:34] + "...")
    print("  not_measured         %s" % ", ".join(pa["not_measured"]))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
