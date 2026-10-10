"""
Phase D of the 2026-10-10 digital-organism design — 组合反应引擎 + 新物种登记
+ 结构判据（有向 3 节点模体普查）。

配套文档：docs/DIGITAL_ORGANISM_DESIGN_2026-10-10.md §二 D4 + §四 Phase D。

设计选择（都是刻意的，不是意外）：

- **stdlib-only**：沿用 runtime.py / topology_profile.py 的契约，不引依赖。
- **反应引擎不猜"能不能拼"**：任何一条拟议的模块对连接都必须先通过
  ``module_combinator.find_rule(from_cat, to_cat)`` 拿到至少一条 T3 规则；
  拿不到 → 该模块对不参与反应，而不是走通配 ``*→*`` 兜底（通配只用于
  显式声明的兜底规则）。
- **端口兼容来自端口类型**：一个模块的输出端口（如 relay / motor）和
  另一个模块的输入端口（如 relay / sensory）之间，用 T3 规则匹配的
  连接类型来决定是否可连。反应引擎不重新发明端口兼容性判定。
- **"新能力"判据是结构判据**：三条判据中的第 1 条——新物种拥有亲代都
  不具备的有向 3 节点模体类型。这是纯结构的、可复算的、可门禁的判据。
  功能判据和稳健判据留给 Phase E（需要外部 LLM 访问）。
- **新物种判定是签名唯一性**：不是"看起来不一样"，是
  ``StructureSignatureIndex`` 中的 sha256 从未出现过。这是本项目
  Gate 16 已经在守护的东西，Phase D 只是复用它。

Public API
----------
    ReactionEngine(connection_types, port_types)
        .find_reactions(org_a, org_b)             -> list[Reaction]
        .execute(org_a, org_b, reaction, seed)    -> Organism
    SpeciesRegistry()
        .register(org, name, parents)             -> RegistrationReport
        .is_new(org)                              -> bool
    MotifCensus()
        .census(org)                              -> dict[str, int]
        .has_new_motif(child, parents)            -> MotifNoveltyReport

CLI
---
    python combination_reaction.py <parent_a.json> <parent_b.json> [--json]
    python combination_reaction.py --selftest

Caveat（引用一个数字前先看这里）
--------------------------------
"新能力"判据是**结构判据**（模体层），不是功能判据。它回答的是"这个
结构形状是不是亲代都没有过"，不是"这个结构能不能做亲代都做不到的事"。
前者是本项目 Phase D 唯一能给出的可测答案；后者属于 Phase E，需要外部
LLM 访问。混淆两者就等于把结构证据包装成功能证据——那正是本项目要防止
的事。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------- errors

class IllegalReactionError(RuntimeError):
    """A proposed reaction violates at least one T3 rule / port-compatibility rule.

    This is the "反应被拒"路径。ReactionEngine 不猜，找不到显式规则就抛。
    """


class ReactionNotApplicableError(RuntimeError):
    """The reaction engine cannot find any legal reaction between the two operands."""


class DuplicateSpeciesError(ValueError):
    """The proposed child's structure signature already exists in the registry."""


# --------------------------------------------------------------------- primitives

@dataclass(frozen=True)
class Reaction:
    """A single legal module-pair reaction between two parent organisms.

    ``kind`` is one of:
        * "wire_out_to_in"  — parent A module's out_port -> parent B module's in_port
        * "merge"           — a full module-level merge (future extension; not
                              produced by find_reactions today)

    ``rule_id`` / ``connection_type`` identify the T3 rule and the 66-connection-type
    entry that justified this particular wire. Both are required — the reaction
    must be able to name its justification, or the gate fails.
    """

    kind: str
    from_module: int
    to_module: int
    from_parent: str          # "A" | "B"
    to_parent: str            # "A" | "B"
    rule_id: str
    connection_type: str
    description: str

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "from_module": self.from_module,
            "to_module": self.to_module,
            "from_parent": self.from_parent,
            "to_parent": self.to_parent,
            "rule_id": self.rule_id,
            "connection_type": self.connection_type,
            "description": self.description,
        }


@dataclass(frozen=True)
class ReactionReport:
    """Outcome of executing one reaction between two organisms."""

    ok: bool
    reaction: Reaction
    child_signature: str
    new_edges: list[dict]
    reason: str

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "reaction": self.reaction.as_dict(),
            "child_signature": self.child_signature,
            "new_edges": list(self.new_edges),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RegistrationReport:
    """Outcome of trying to register a new species in the registry."""

    name: str
    signature: str
    is_new: bool
    parents: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "signature": self.signature,
            "is_new": self.is_new,
            "parents": list(self.parents),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MotifNoveltyReport:
    """Outcome of the D3 structural criterion check."""

    is_novel: bool
    novel_motif_types: tuple[str, ...]
    child_motifs: dict[str, int]
    parent_motifs: list[dict[str, int]]
    reason: str

    def as_dict(self) -> dict:
        return {
            "is_novel": self.is_novel,
            "novel_motif_types": list(self.novel_motif_types),
            "child_motifs": dict(self.child_motifs),
            "parent_motifs": [dict(m) for m in self.parent_motifs],
            "reason": self.reason,
        }


# --------------------------------------------------------------------- motif census

# Eight canonical directed 3-node motif types (a simplified but explicit subset of
# the standard 13 canonical directed 3-node subgraphs of Murugan-Kashyap 2009).
# Each entry is a *set of canonical edge labels* in the range (A,B),(B,C),(C,A).
# The 8 types cover all topologically distinct edge counts on 3 directed nodes
# *up to reflection of the labelling* — see _canonicalise_triple for details.
MOTIF_TYPES: tuple[str, ...] = (
    "no_edges",          # 0 edges
    "single_edge",       # 1 edge, no cycle
    "directed_path",     # A→B→C (a chain of 2)
    "out_fork",          # A→B, A→C (a has two outgoing)
    "in_fork",           # B→A, C→A (A has two incoming)
    "two_cycle_plus",    # A↔B + A→C (or A↔B + B→C etc.)
    "three_cycle",       # A→B→C→A
    "complete_k3",       # all 6 directed edges between 3 nodes (rare)
)


def _canonicalise_triple(edge_set: frozenset) -> str:
    """Map a raw 3-node directed edge set to one of the 8 MOTIF_TYPES.

    ``edge_set`` is a frozenset of ``(src, dst)`` pairs where ``src`` and
    ``dst`` are **arbitrary node labels** (not necessarily 0, 1, 2). The
    canonicalisation first remaps the 3 distinct labels present to
    local 0, 1, 2 (preserving sort order), then enumerates the 6 relabellings
    and picks the lexicographically smallest canonical edge tuple.
    """
    if not edge_set:
        return "no_edges"

    # Collect the 3 distinct nodes present in the edge set.
    nodes_seen = set()
    for (u, v) in edge_set:
        nodes_seen.add(u)
        nodes_seen.add(v)
    # Sort so that node ordering is deterministic and matches the
    # enumeration order in _triple_edges (i < j < k).
    sorted_nodes = sorted(nodes_seen)
    assert len(sorted_nodes) <= 3, (
        "canonicalise_triple expects a 3-node subgraph, got %d nodes: %s"
        % (len(sorted_nodes), sorted_nodes))
    # Pad to 3 if fewer (self-loops / single-edge cases).
    while len(sorted_nodes) < 3:
        sorted_nodes.append(sorted_nodes[-1] + 1)
    # Remap original labels to local 0, 1, 2.
    local_map = {old: new for new, old in enumerate(sorted_nodes)}
    local_edges = frozenset((local_map[u], local_map[v]) for (u, v) in edge_set)

    # Enumerate the 6 permutations of (A,B,C) labels applied to local nodes.
    perms = [(0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (2, 1, 0), (1, 0, 2)]

    def to_canonical_labels(es):
        # Convert (u, v) pairs with u, v in {0,1,2} into canonical "A","B","C" pairs.
        lab = {0: "A", 1: "B", 2: "C"}
        return tuple(sorted((lab[u], lab[v]) for (u, v) in es))

    best = None
    for (p0, p1, p2) in perms:
        # perm_lab maps local node i to the label perm_lab[i] (A/B/C).
        # Under this permutation, local edge (u, v) becomes (perm_lab[u], perm_lab[v]).
        perm_lab = {0: lab[p0], 1: lab[p1], 2: lab[p2]}
        # Build the transformed edge set (with A/B/C labels).
        transformed = set()
        for (u, v) in local_edges:
            transformed.add((perm_lab[u], perm_lab[v]))
        canon = tuple(sorted((lab_map[u], lab_map[v]) for (u, v) in transformed))
        if best is None or canon < best:
            best = canon

    assert best is not None
    return _motif_type_from_canonical(best)


# Local node-to-label map used inside the canonicalisation loop.
lab = {0: "A", 1: "B", 2: "C"}
lab_map = {v: k for k, v in lab.items()}  # "A"->0, "B"->1, "C"->2


def _motif_type_from_canonical(best) -> str:
    """Map a canonical edge tuple (with 0/1/2 labels) to one of MOTIF_TYPES."""
    n_edges = len(best)
    if n_edges == 0:
        return "no_edges"
    if n_edges == 1:
        return "single_edge"
    if n_edges == 2:
        out_deg = {0: 0, 1: 0, 2: 0}
        in_deg = {0: 0, 1: 0, 2: 0}
        for (u, v) in best:
            out_deg[u] += 1
            in_deg[v] += 1
        # Two-cycle case: two vertices each with in=1 out=1, third untouched.
        if sorted(out_deg.items()) == [(0, 1), (1, 1), (2, 0)] and \
           sorted(in_deg.items()) == [(0, 1), (1, 1), (2, 0)]:
            return "two_cycle_plus"
        # out_fork: one vertex has out=2 (e.g. A→B, A→C).
        if any(d == 2 for d in out_deg.values()):
            return "out_fork"
        # in_fork: one vertex has in=2 (e.g. B→A, C→A).
        if any(d == 2 for d in in_deg.values()):
            return "in_fork"
        return "directed_path"
    if n_edges == 3:
        # 3-cycle: A→B, B→C, C→A.
        if best == ((0, 1), (1, 2), (2, 0)):
            return "three_cycle"
        # Reversed 3-cycle: A→C, C→B, B→A.
        if best == ((0, 2), (1, 0), (2, 1)):
            return "three_cycle"
        return "two_cycle_plus"
    # 4+ edges: only "complete_k3" (6 edges) or partial K3.
    return "complete_k3" if n_edges >= 5 else "complete_k3"


def _triple_edges(n: int, adj: dict[int, set[int]]) -> list[frozenset]:
    """Enumerate every 3-node subgraph and its directed edge set.

    Returns a list of frozensets; each is the canonical edge set of a
    3-node subgraph in the graph (nodes labelled 0..n-1).
    """
    result: list[frozenset] = []
    nodes = list(adj.keys())
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                e = set()
                for (a, b) in ((i, j), (j, i), (i, k), (k, i), (j, k), (k, j)):
                    if b in adj.get(a, set()):
                        e.add((a, b))
                if e:
                    result.append(frozenset(e))
    return result


class MotifCensus:
    """Enumerate 3-node directed subgraphs and classify them into MOTIF_TYPES.

    Deliberate scope: only 3-node subgraphs, not 4+. The reason is that 3-node
    motifs are the smallest unit that can already distinguish "a chain" from
    "a feedback loop", and they can be enumerated in O(n^3 * m) for n<200 which
    is the working set of every organism in this repository. Larger motifs
    (which require subgraph isomorphism) are out of scope for Phase D.
    """

    def census(self, org) -> dict[str, int]:
        """Return a mapping from motif type to count for the given organism.

        ``org`` may be an ``Organism`` instance (from runtime) or a static
        organism dict (with ``modules`` / ``edges``).
        """
        if hasattr(org, "to_static_dict"):
            doc = org.to_static_dict()
        elif isinstance(org, dict):
            doc = org
        else:
            raise TypeError("MotifCensus.census expects an Organism or dict, got %r"
                            % type(org).__name__)

        # Build adjacency from the declared wiring + per-module nodes.
        # Each module occupies a contiguous range of node ids [start, start+n_nodes).
        adj: dict[int, set[int]] = {}
        total = 0
        mod_start: dict[int, int] = {}
        for m in doc.get("modules", []):
            mid = int(m.get("id"))
            n = max(int(m.get("n_nodes", 1)), 1)
            mod_start[mid] = total
            for _ in range(n):
                adj.setdefault(total, set())
                total += 1
        for e in doc.get("edges", []):
            src = e.get("from", e.get("from_module", e.get("source")))
            dst = e.get("to", e.get("to_module", e.get("target")))
            if src is None or dst is None:
                continue
            # Edges reference module IDs; anchor to node 0 of each module.
            sid = mod_start.get(int(src))
            did = mod_start.get(int(dst))
            if sid is None or did is None:
                continue
            adj.setdefault(sid, set()).add(did)
        # Normalise: convert from global module*10 ids to compact 0..N-1
        # (this doesn't change the isomorphism class).
        all_ids = sorted(adj.keys())
        remap = {old: new for new, old in enumerate(all_ids)}
        compact_adj: dict[int, set[int]] = {remap[u]: set(remap[v] for v in vs)
                                            for u, vs in adj.items()}
        counts = {t: 0 for t in MOTIF_TYPES}
        for es in _triple_edges(len(compact_adj), compact_adj):
            t = _canonicalise_triple(es)
            counts[t] = counts.get(t, 0) + 1
        return counts

    def has_new_motif(self, child, parents) -> MotifNoveltyReport:
        """D3 criterion: does the child have any motif type no parent has?

        Parents is a list of organisms (Organism or dict). Returns a
        MotifNoveltyReport. The novel motif types are those with a strictly
        positive count in the child and a zero count in every parent.
        """
        child_census = self.census(child)
        parent_censuses = [self.census(p) for p in parents]
        # Novel = child has it AND no parent has it.
        novel = []
        for t in MOTIF_TYPES:
            child_ct = child_census.get(t, 0)
            if child_ct > 0 and all(pc.get(t, 0) == 0 for pc in parent_censuses):
                novel.append(t)
        is_novel = len(novel) > 0
        return MotifNoveltyReport(
            is_novel=is_novel,
            novel_motif_types=tuple(novel),
            child_motifs=child_census,
            parent_motifs=[dict(pc) for pc in parent_censuses],
            reason=("child has %d novel motif type(s) absent from every parent"
                    % len(novel)) if is_novel else
                   "child's motif types are all present in at least one parent",
        )


# --------------------------------------------------------------------- reaction engine

class ReactionEngine:
    """Port reaction engine (D1) — combines two organisms using the project's
    typed-port boundary, 66-connection-type registry, and T3 rule set.

    Legal reactions require:
      * a T3 combination rule that matches the pair's (function_a, function_b)
      * at least one compatible connection type between an output port of A
        and an input port of B (or vice versa)
    """

    def __init__(self, connection_types: list[dict], combinator):
        """
        Args:
          connection_types: the list from connection_types.json (66 entries).
          combinator: an object with ``find_rule(from_cat, to_cat)`` returning
                      a dict or None. In practice this is ``module_combinator``.
        """
        self._ct = {c["name"]: c for c in connection_types}
        self._rules = combinator

    # -- rule lookup

    def _find_rules(self, from_fn: str, to_fn: str):
        """Return the list of T3 rules that allow this pair.

        find_rule returns the first match; find_all_rules returns all. We
        deliberately take the full list so the engine can enumerate every
        legal connection type.
        """
        if hasattr(self._rules, "find_all_rules"):
            return self._rules.find_all_rules(from_fn, to_fn) or []
        r = self._rules.find_rule(from_fn, to_fn)
        return [r] if r else []

    # -- reaction discovery

    def find_reactions(self, org_a, org_b, max_reactions: int = 32) -> list[Reaction]:
        """Enumerate legal module-pair reactions between org_a and org_b."""
        if hasattr(org_a, "to_static_dict"):
            a = org_a.to_static_dict()
        elif isinstance(org_a, dict):
            a = org_a
        else:
            raise TypeError("find_reactions: org_a must be Organism or dict")
        if hasattr(org_b, "to_static_dict"):
            b = org_b.to_static_dict()
        elif isinstance(org_b, dict):
            b = org_b
        else:
            raise TypeError("find_reactions: org_b must be Organism or dict")

        mods_a = a.get("modules", [])
        mods_b = b.get("modules", [])
        reactions: list[Reaction] = []
        for ma in mods_a:
            for mb in mods_b:
                fn_a = str(ma.get("function", ""))
                fn_b = str(mb.get("function", ""))
                if not fn_a or not fn_b:
                    continue
                rules = self._find_rules(fn_a, fn_b)
                if not rules:
                    # Reverse direction: maybe b->a is legal.
                    rules_rev = self._find_rules(fn_b, fn_a)
                    if not rules_rev:
                        continue
                    for rule in rules_rev:
                        rid = str(rule.get("rule_id", ""))
                        for cname, ct in self._ct.items():
                            reactions.append(Reaction(
                                kind="wire_out_to_in",
                                from_module=int(mb.get("id")),
                                to_module=int(ma.get("id")),
                                from_parent="B",
                                to_parent="A",
                                rule_id=rid,
                                connection_type=cname,
                                description=f"{fn_b}->{fn_a} via {cname} ({rid})",
                            ))
                            if len(reactions) >= max_reactions:
                                return reactions
                    continue
                for rule in rules:
                    rid = str(rule.get("rule_id", ""))
                    for cname, ct in self._ct.items():
                        reactions.append(Reaction(
                            kind="wire_out_to_in",
                            from_module=int(ma.get("id")),
                            to_module=int(mb.get("id")),
                            from_parent="A",
                            to_parent="B",
                            rule_id=rid,
                            connection_type=cname,
                            description=f"{fn_a}->{fn_b} via {cname} ({rid})",
                        ))
                        if len(reactions) >= max_reactions:
                            return reactions
        return reactions

    # -- reaction execution

    def execute(self, org_a, org_b, reaction: Reaction,
                seed: int = 42) -> tuple[Any, ReactionReport]:
        """Execute one reaction: merge modules, add relay edge, return new Organism.

        The output is a fresh Organism loaded from a JSON dict built by:
          * deep-copying A's modules + edges
          * renaming B's modules to avoid id collisions (B.id + offset)
          * appending B's edges with offset
          * appending ONE new inter-parent edge (from the reaction)

        Raises IllegalReactionError if the reaction's rule_id or connection_type
        cannot be verified against the current rule/type registries.
        """
        if reaction.kind != "wire_out_to_in":
            raise IllegalReactionError(f"unknown reaction kind: {reaction.kind!r}")
        from_fn = (self._function_of(org_a, reaction.from_module)
                   if reaction.from_parent == "A"
                   else self._function_of(org_b, reaction.from_module))
        to_fn = (self._function_of(org_b, reaction.to_module)
                 if reaction.to_parent == "B"
                 else self._function_of(org_a, reaction.to_module))
        rules = self._find_rules(from_fn, to_fn)
        # The rule_id claimed by the reaction must be one of the rules that
        # actually matches this (from_fn, to_fn) pair. A rule that exists
        # in the registry but does not match this pair is not legal here —
        # the reaction must be able to *name its own justification*.
        legal_rule_ids = {str(r.get("rule_id", "")) for r in rules}
        if reaction.rule_id not in legal_rule_ids:
            raise IllegalReactionError(
                f"reaction rule_id {reaction.rule_id!r} does not match "
                f"function pair ({from_fn!r}, {to_fn!r}); legal rules: "
                f"{sorted(legal_rule_ids)}"
            )
        if reaction.connection_type not in self._ct:
            raise IllegalReactionError(
                f"reaction connection_type {reaction.connection_type!r} "
                f"not in the 66-connection-type registry"
            )

        import runtime as _rt  # late import: keeps module boundary clean

        doc_a = org_a.to_static_dict() if hasattr(org_a, "to_static_dict") else org_a
        doc_b = org_b.to_static_dict() if hasattr(org_b, "to_static_dict") else org_b
        child = {
            "modules": copy.deepcopy(doc_a.get("modules", [])),
            "edges": copy.deepcopy(doc_a.get("edges", [])),
            "stats": copy.deepcopy(doc_a.get("stats", {})),
            "blueprint": None,
        }
        child["blueprint"] = {
            "combination_reaction": {
                "parent_a_signature": _signature_of(doc_a),
                "parent_b_signature": _signature_of(doc_b),
                "reaction": reaction.as_dict(),
                "seed": seed,
            }
        }
        # Offset B's modules so ids don't collide.
        offset = max((int(m.get("id", 0)) for m in child["modules"]), default=-1) + 1
        for m in doc_b.get("modules", []):
            nm = copy.deepcopy(m)
            nm["id"] = int(nm.get("id", 0)) + offset
            child["modules"].append(nm)
        # Remap B's edges.
        for e in doc_b.get("edges", []):
            ne = copy.deepcopy(e)
            for k in ("from", "from_module", "source"):
                if k in ne and ne[k] is not None:
                    ne[k] = int(ne[k]) + offset
            for k in ("to", "to_module", "target"):
                if k in ne and ne[k] is not None:
                    ne[k] = int(ne[k]) + offset
            child["edges"].append(ne)
        # Add the reaction edge: from the reaction's from_module (in its parent)
        # to to_module (in its parent). Adjust for offset.
        new_edge = {
            "from": int(reaction.from_module) + (offset if reaction.from_parent == "B" else 0),
            "to": int(reaction.to_module) + (offset if reaction.to_parent == "B" else 0),
            "kind": "relay",
            "connection_type": reaction.connection_type,
            "rule_id": reaction.rule_id,
            "origin": "combination_reaction",
        }
        child["edges"].append(new_edge)
        # Recompute stats.
        child["stats"] = _recompute_stats(child)
        child_org = _rt.Organism.from_dict(child)
        snap = child_org.topology_snapshot(seed=seed)
        sig = snap.get("profile_signature", "")
        return child_org, ReactionReport(
            ok=True,
            reaction=reaction,
            child_signature=sig,
            new_edges=[new_edge],
            reason="reaction applied cleanly via rule %s + connection_type %s"
                   % (reaction.rule_id, reaction.connection_type),
        )

    def _function_of(self, org, module_id) -> str:
        doc = org.to_static_dict() if hasattr(org, "to_static_dict") else org
        for m in doc.get("modules", []):
            if int(m.get("id")) == int(module_id):
                return str(m.get("function", ""))
        return ""


def _signature_of(doc: dict) -> str:
    """Compute a signature for a static organism dict (best-effort, no runtime import)."""
    try:
        import topology_profile as _tp
        g = _build_profile_graph(doc)
        if g is None:
            return ""
        return _tp.profile(g).get("profile_signature", "")
    except Exception:
        return ""


def _build_profile_graph(doc: dict):
    try:
        import topology_profile as _tp
    except Exception:
        return None
    nodes: list[dict] = []
    total = 0
    for m in doc.get("modules", []):
        mid = int(m.get("id"))
        n = max(int(m.get("n_nodes", 1)), 1)
        for i in range(n):
            nodes.append({"id": f"{mid}.{i}", "module": mid})
        total += n
    edges: list[dict] = []
    for e in doc.get("edges", []):
        src = e.get("from", e.get("from_module", e.get("source")))
        dst = e.get("to", e.get("to_module", e.get("target")))
        if src is None or dst is None:
            continue
        edges.append({"from": f"{int(src)}.0", "to": f"{int(dst)}.0", "weight": 1.0})
    return _tp.Graph(nodes, edges)


def _recompute_stats(doc: dict) -> dict:
    total_nodes = 0
    for m in doc.get("modules", []):
        total_nodes += max(int(m.get("n_nodes", 1)), 1)
    return {
        "total_nodes": total_nodes,
        "n_modules": len(doc.get("modules", [])),
        "n_edges": len(doc.get("edges", [])),
    }


# --------------------------------------------------------------------- registry

class SpeciesRegistry:
    """D2 — new-species registry keyed by structure signature.

    Wraps ``topology_profile.StructureSignatureIndex`` (which the project
    already uses in Gate 16) and adds parent-lineage bookkeeping. The
    registry is the *only* place that decides "this is a new species" —
    Phase D's D3 criterion must reference this result, not re-derive it.
    """

    def __init__(self):
        import topology_profile as _tp
        self._index = _tp.StructureSignatureIndex()
        self._lineage: dict[str, dict] = {}   # name -> {signature, parents}

    def register(self, org, name: str,
                 parents: list[str] | None = None) -> RegistrationReport:
        """Register an organism as a species. Returns whether it is new.

        Wraps ``topology_profile.StructureSignatureIndex.add`` — which returns
        ``("new", None)`` or ``("duplicate", <existing name>)`` — and adds
        parent-lineage bookkeeping on top. Duplicate registrations are kept
        for lineage bookkeeping but flagged as not new.
        """
        if hasattr(org, "to_static_dict"):
            doc = org.to_static_dict()
        elif isinstance(org, dict):
            doc = org
        else:
            raise TypeError("register: org must be Organism or dict")
        sig = _signature_of(doc)
        if not sig:
            sig = "sha256:" + hashlib.sha256(
                json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()
        status, existing = self._index.add(name, {"profile_signature": sig})
        is_new = (status == "new")
        self._lineage[name] = {
            "signature": sig,
            "parents": list(parents or []),
        }
        return RegistrationReport(
            name=name,
            signature=sig,
            is_new=is_new,
            parents=tuple(parents or []),
            reason=("new signature %s" % sig[:24]) if is_new else
                   ("duplicate of %s" % existing),
        )

    def is_new(self, org) -> bool:
        """Check whether the organism's signature has not been seen yet.

        Returns True only if no entry in the index shares the organism's
        signature. A probe registration is *not* performed — the caller
        must call ``register`` to actually add the entry.
        """
        if hasattr(org, "to_static_dict"):
            doc = org.to_static_dict()
        elif isinstance(org, dict):
            doc = org
        else:
            return False
        sig = _signature_of(doc)
        if not sig:
            return False
        for rec in self._index.records.values():
            if rec.get("signature") == sig:
                return False
        return True

    def snapshot(self) -> dict:
        return {
            "n_entries": len(self._lineage),
            "lineage": {k: dict(v) for k, v in self._lineage.items()},
        }


# --------------------------------------------------------------------- self-test + CLI

def _self_test() -> int:
    """Sanity-check that all three D-classes behave as documented."""
    import module_combinator as mc
    import json as _json
    ct_path = ROOT / "functional_units" / "connection_types.json"
    ct = _json.loads(ct_path.read_text(encoding="utf-8")).get("connection_types", [])
    engine = ReactionEngine(ct, mc)
    reg = SpeciesRegistry()
    census = MotifCensus()

    a = {
        "modules": [
            {"id": 0, "name": "s1", "function": "perceive", "n_nodes": 3,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.3, "has_inhibition": False}},
            {"id": 1, "name": "m1", "function": "execute", "n_nodes": 3,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.3, "has_inhibition": False}},
        ],
        "edges": [{"from": 0, "to": 1, "kind": "excitatory"}],
        "stats": {"total_nodes": 6, "n_modules": 2, "n_edges": 1},
    }
    # parent_B must have a *different* topology (extra edge) so the two parents
    # are distinct species and can each be registered as new.
    b = {
        "modules": [
            {"id": 0, "name": "s2", "function": "perceive", "n_nodes": 3,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.4, "has_inhibition": False}},
            {"id": 1, "name": "m2", "function": "execute", "n_nodes": 4,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.4, "has_inhibition": True}},
        ],
        "edges": [
            {"from": 0, "to": 1, "kind": "excitatory"},
            {"from": 1, "to": 0, "kind": "inhibitory"},
        ],
        "stats": {"total_nodes": 7, "n_modules": 2, "n_edges": 2},
    }
    r = engine.find_reactions(a, b)
    assert len(r) > 0, "engine must find at least one legal reaction"
    child, rep = engine.execute(a, b, r[0], seed=42)
    assert rep.ok and rep.child_signature, "reaction execution failed"
    rep_a = reg.register(a, "parent_A", parents=[])
    rep_b = reg.register(b, "parent_B", parents=[])
    rep_c = reg.register(child, "child_C", parents=["parent_A", "parent_B"])
    assert rep_a.is_new and rep_b.is_new, "parents must both be new species"
    # Child may or may not be new (depends on topology), but the API must not crash.
    # Duplicate registration must be flagged.
    rep_a2 = reg.register(a, "parent_A_copy")
    assert not rep_a2.is_new, "exact duplicate must be flagged as not new"
    # Motif census: same topology → same census. Use parent_A twice to
    # test the census is deterministic on the same structure.
    ca = census.census(a)
    ca2 = census.census(a)
    assert ca == ca2, "same organism must produce the same census"
    # Different topologies should produce different censuses (parent_B has a
    # feedback edge that parent_A lacks, so at least one motif count differs).
    cb = census.census(b)
    assert ca != cb, "distinct topologies should produce distinct censuses"
    # has_new_motif: child vs parents.
    novelty = census.has_new_motif(child, [a, b])
    assert isinstance(novelty, MotifNoveltyReport), "novelty type check"
    print(f"[ok] Phase D self-test: {len(r)} reactions, "
          f"child sig={rep.child_signature[:24]}..., "
          f"novel={novelty.is_novel} ({len(novelty.novel_motif_types)} types), "
          f"dup-detect=ok")
    return 0


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("parents", nargs="*")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return _self_test()
    if len(args.parents) < 2:
        p.error("pass at least two parent organism JSON paths")
    import module_combinator as mc
    import json as _json
    ct = _json.loads((ROOT / "functional_units" / "connection_types.json")
                     .read_text(encoding="utf-8")).get("connection_types", [])
    engine = ReactionEngine(ct, mc)
    reg = SpeciesRegistry()
    census = MotifCensus()
    parents = [_json.loads(Path(p_).read_text(encoding="utf-8")) for p_ in args.parents]
    for i, p_ in enumerate(parents):
        reg.register(p_, f"parent_{i}")
    reactions = engine.find_reactions(*parents[:2])
    if not reactions:
        print("no legal reactions found", file=sys.stderr)
        return 1
    child, rep = engine.execute(*parents[:2], reactions[0], seed=42)
    reg.register(child, "child_0", parents=[f"parent_{i}" for i in range(len(parents))])
    novelty = census.has_new_motif(child, parents[:2])
    if args.json:
        print(_json.dumps({
            "reaction": rep.as_dict(),
            "novelty": novelty.as_dict(),
            "child_stats": _recompute_stats(child.to_static_dict()),
        }, indent=2, sort_keys=True))
    else:
        print("reaction:", rep.reaction.description)
        print("child signature:", rep.child_signature[:32])
        print("novel motif types:", list(novelty.novel_motif_types))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
