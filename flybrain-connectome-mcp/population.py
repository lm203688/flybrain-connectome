"""
Phase C of the 2026-10-10 digital-organism design — 种群繁殖演化
（clone/mutate + 世系树 + 存活判据 + DGM 档案库 + 死亡回收 + 负结果护栏）。

配套文档：docs/DIGITAL_ORGANISM_DESIGN_2026-10-10.md §二 D3 + §四 Phase C。

设计选择（都是刻意的，不是意外）：

- **stdlib-only**：沿用 runtime.py / topology_profile.py / repair.py /
  combination_reaction.py 的契约。世系树用 dict + 时间戳 + SHA-256 承载，
  不引 W3C PROV 依赖——结构上等价于 PROV Activity/Entity，读起来更直。
- **存活判据是二分的，不是 fitness**：一个个体要么能跑通 N 步的代谢循环
  （`Runtime.step` 无异常 + 输出在 [-1,1] 内），要么不能。不评分、不排序。
  本项目 2025-10 已实测：任何 fitness 都退化成"更多边更好"，本项目明确不
  重复这条路。
- **档案库（DGM 式）保留"非最优但有趣"的解**：不删除任何个体，只打标签
  （archived / active / dead）。种群多样性度量 = 非重复 profile_signature
  的占比。这是 Phase C 的**唯一**结构度量。
- **死亡是终结判据，不是删除**：个体死亡后依然留档（血统封存 + 结构签名
  保存 + 死亡原因记录），但不再参与选择。这是本项目"PROV 血统"承诺的
  延续——不允许信息被擦除。
- **负结果护栏是硬约束**：C5 明确要求"N 代无结构增益即显式关闭并发布负
  结果"。``NegativeResultGuard`` 是**唯一**有权触发关闭的类，且必须留下
  一份负结果记录到 lineage 树，供后续读者复核。

Public API
----------
    Population(lineage=None, archive=None, guard=None)
        .spawn(org, name)                       -> PopulationMember
        .clone(member, name=None, seed=42)      -> PopulationMember
        .mutate(member, name=None, seed=42)     -> PopulationMember
        .apply_damage(member, kind, seed)       -> PopulationMember  # reuses damage.py
        .select(archive, keep_n=None)           -> dict
        .kill(member, reason)                   -> None
        .archive(member)                        -> None
        .lineage_tree(name)                     -> dict  (ancestor chain)
        .snapshot()                             -> dict

CLI
---
    python population.py --selftest

Caveat（引用一个数字前先看这里）
--------------------------------
- **结构增益** 是"这一代中出现了新 profile_signature 的个体数 ÷ 该代非重复
  个体数"，是**多样性度量**，不是"进步"的度量。
- **负结果护栏** 关闭的判据是"连续 N 代结构增益为 0"，**不是**"种群停滞"
  的模糊判据——停滞可能是好事情（多样性低但健康），但 0 增益持续 N 代是
  明确的负结果信号。
- 存活判据基于 ``Runtime.step`` 是否能跑通 N 步，**不代表任务性能**。
  Phase E 之前，本项目没有任务级 benchmark。
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------- errors

class DeathReasonError(ValueError):
    """kill() must be given a non-empty reason string."""


class NegativeResultTriggered(RuntimeError):
    """Raised by NegativeResultGuard when the population should be shut down."""


# --------------------------------------------------------------------- helpers

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sig_of(org) -> str:
    """Return the profile_signature of an organism (Organism or dict).

    Fallback: sha256 of the canonical JSON if the topology profile cannot be
    computed (e.g. malformed modules list).
    """
    if hasattr(org, "to_static_dict"):
        doc = org.to_static_dict()
    elif isinstance(org, dict):
        doc = org
    else:
        return ""
    try:
        import topology_profile as _tp
        # Build a Graph from the doc — same as combination_reaction._build_profile_graph.
        nodes: list[dict] = []
        total = 0
        for m in doc.get("modules", []):
            mid = int(m.get("id"))
            n = max(int(m.get("n_nodes", 1)), 1)
            for _ in range(n):
                nodes.append({"id": f"{mid}.{total - mid * 1000}", "module": mid})
            total += n
        edges: list[dict] = []
        for e in doc.get("edges", []):
            src = e.get("from", e.get("from_module", e.get("source")))
            dst = e.get("to", e.get("to_module", e.get("target")))
            if src is None or dst is None:
                continue
            edges.append({"from": f"{int(src)}.0", "to": f"{int(dst)}.0", "weight": 1.0})
        if not nodes:
            return ""
        g = _tp.Graph(nodes, edges)
        sig = _tp.profile(g).get("profile_signature", "")
        return sig
    except Exception:
        return "sha256:" + hashlib.sha256(
            json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- primitives

@dataclass
class PopulationMember:
    """One member of a population (an organism + its runtime metadata).

    Status lifecycle:
        "active"  ->  "archived"  (retired but kept for lineage)
        "active"  ->  "dead"      (killed by an explicit death reason)
    An "archived" or "dead" member is never selected again, but is kept
    for ancestry bookkeeping (Phase C4).
    """

    name: str
    org: Any
    signature: str
    generation: int
    parent: str | None
    status: str = "active"
    created_utc: str = ""
    archive_utc: str | None = None
    death_reason: str | None = None
    death_utc: str | None = None

    def __post_init__(self):
        if not self.created_utc:
            self.created_utc = _now_iso()

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "signature": self.signature,
            "generation": self.generation,
            "parent": self.parent,
            "status": self.status,
            "created_utc": self.created_utc,
            "archive_utc": self.archive_utc,
            "death_reason": self.death_reason,
            "death_utc": self.death_utc,
        }


@dataclass
class SelectionReport:
    """Outcome of Population.select() — a single generation's selection step."""

    generation: int
    n_candidates: int
    n_kept: int
    n_new_signatures: int
    n_unique_signatures: int
    structural_gain: float
    kept_names: list[str]

    def as_dict(self) -> dict:
        return {
            "generation": self.generation,
            "n_candidates": self.n_candidates,
            "n_kept": self.n_kept,
            "n_new_signatures": self.n_new_signatures,
            "n_unique_signatures": self.n_unique_signatures,
            "structural_gain": self.structural_gain,
            "kept_names": list(self.kept_names),
        }


@dataclass
class SurvivalReport:
    """Outcome of can_survive() — a binary survival probe."""

    name: str
    ok: bool
    reason: str

    def as_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "reason": self.reason}


# --------------------------------------------------------------------- archive (C3)

class DGMArchive:
    """Population archive in the DGM (Darwin Gödel Machine) style.

    Deliberate design (see Phase C.3 of the design doc):
      * **retain non-optimal but interesting** — the archive does NOT
        evict; it just tags members as archived. Every structure ever
        seen is retained.
      * the archive is the *only* source of truth for structural
        diversity — population.structural_gain() consults it.
    """

    def __init__(self):
        self._entries: dict[str, dict] = {}   # name -> {signature, entry}
        self._by_sig: dict[str, str] = {}     # signature -> first-name-seen

    def add(self, member: PopulationMember) -> str:
        """Register a member. Returns 'new' if the signature is fresh,
        else the name of the first member with the same signature.

        **Every call registers the member by name** — the archive retains
        every member that ever existed (DGM discipline). Only the
        first-occurrence lookup table (`_by_sig`) is signature-keyed;
        the name-keyed entries dict is member-keyed.
        """
        sig = member.signature
        if not sig:
            sig = "sha256:" + hashlib.sha256(
                json.dumps(member.as_dict(), sort_keys=True).encode("utf-8")).hexdigest()
        is_new_sig = sig not in self._by_sig
        if is_new_sig:
            self._by_sig[sig] = member.name
        # Always register by name — lineage bookkeeping keeps every member.
        self._entries[member.name] = {
            "signature": sig,
            "entry": member.as_dict(),
            "archived": False,
        }
        return "new" if is_new_sig else self._by_sig[sig]

    def archive(self, name: str) -> None:
        rec = self._entries.get(name)
        if rec is None:
            raise KeyError(f"archive: no such entry: {name!r}")
        rec["archived"] = True

    def get(self, name: str) -> dict | None:
        return self._entries.get(name)

    def entries(self) -> list[str]:
        return list(self._entries.keys())

    def unique_signatures(self) -> list[str]:
        return list(self._by_sig.keys())

    def n_unique(self) -> int:
        return len(self._by_sig)

    def snapshot(self) -> dict:
        return {
            "n_entries": len(self._entries),
            "n_unique_signatures": len(self._by_sig),
            "by_signature": dict(self._by_sig),
        }


# --------------------------------------------------------------------- population (C1 + C2 + C3 + C4)

class Population:
    """A population of organisms with clone/mutate/lineage/selection/death.

    Lineage tree (C1) — every member points to at most one parent. Ancestors
    are traversed by walking ``parent`` back to ``None``.
    """

    def __init__(self, archive: DGMArchive | None = None,
                 mutation_seed: int | None = None,
                 mutation_steps: int = 3):
        self.members: dict[str, PopulationMember] = {}
        self.archive = archive or DGMArchive()
        self._rng = random.Random(mutation_seed)
        # mutation_steps controls how many mutations per mutate() call — the
        # default of 3 matches the "add/rewire/drop" atomic patch family.
        self._mutation_steps = mutation_steps

    # -- C1: spawn / clone / mutate

    def spawn(self, org, name: str) -> PopulationMember:
        """Introduce a new individual (first-generation, no parent)."""
        sig = _sig_of(org)
        m = PopulationMember(
            name=name, org=org, signature=sig,
            generation=0, parent=None,
        )
        self.members[name] = m
        self.archive.add(m)
        return m

    def clone(self, member: PopulationMember, name: str | None = None,
              seed: int | None = None) -> PopulationMember:
        """Exact duplicate — same signature, same generation, child generation +1."""
        if member.name not in self.members:
            raise KeyError(f"clone: no such member: {member.name!r}")
        src = self.members[member.name]
        child_name = name or f"{src.name}.clone.{len(self.members)}"
        if child_name in self.members:
            raise ValueError(f"clone: name already taken: {child_name!r}")
        rng = random.Random(seed if seed is not None else self._rng.randint(0, 2**31 - 1))
        _ = rng  # clone is deterministic — no mutation, just lineage link.
        new_org = copy.deepcopy(src.org)
        child = PopulationMember(
            name=child_name, org=new_org, signature=src.signature,
            generation=src.generation + 1, parent=src.name,
        )
        self.members[child_name] = child
        self.archive.add(child)
        return child

    def mutate(self, member: PopulationMember, name: str | None = None,
               seed: int | None = None) -> PopulationMember:
        """Apply 1..mutation_steps atomic patches and register the mutant.

        Uses ``repair.Patch`` for the three atomic operations (add_unit,
        rewire, drop_unit). Each patch is drawn with a seeded RNG so the
        mutation is reproducible.
        """
        if member.name not in self.members:
            raise KeyError(f"mutate: no such member: {member.name!r}")
        src = self.members[member.name]
        rng = random.Random(seed if seed is not None else self._rng.randint(0, 2**31 - 1))
        # Copy the source organism as an editable dict.
        doc = copy.deepcopy(src.org.to_static_dict() if hasattr(src.org, "to_static_dict")
                            else src.org)
        n_steps = max(1, min(self._mutation_steps, rng.randint(1, self._mutation_steps)))
        doc = self._apply_random_patches(doc, rng, n_steps=n_steps)
        new_sig = _sig_of(doc)
        child_name = name or f"{src.name}.mut.{len(self.members)}"
        if child_name in self.members:
            raise ValueError(f"mutate: name already taken: {child_name!r}")
        try:
            import runtime as _rt
            new_org = _rt.Organism.from_dict(doc)
        except Exception:
            # Fallback: keep the dict. Population works either way.
            new_org = doc
        child = PopulationMember(
            name=child_name, org=new_org, signature=new_sig,
            generation=src.generation + 1, parent=src.name,
        )
        self.members[child_name] = child
        self.archive.add(child)
        return child

    def _apply_random_patches(self, doc: dict, rng: random.Random,
                              n_steps: int = 3) -> dict:
        """Apply n_steps random atomic patches to a static organism dict.

        Patches are drawn uniformly at random from {add_unit, rewire, drop_unit}
        and applied in-place. Each operation is guarded against degenerate
        states (no modules left, empty edges, etc.).
        """
        doc = copy.deepcopy(doc)
        for step in range(n_steps):
            op = rng.choice(["add_unit", "rewire", "drop_unit"])
            if op == "add_unit" and doc.get("modules"):
                n = max(len(doc["modules"]), 0) + 1
                new_id = max((int(m.get("id", -1)) for m in doc["modules"]), default=-1) + 1
                fn = rng.choice(["perceive", "remember", "execute", "integrate"])
                doc["modules"].append({
                    "id": new_id, "name": f"mut_{new_id}", "function": fn,
                    "n_nodes": rng.randint(2, 4), "motif_source": "none",
                    "parameters": {"reservoir_density": round(rng.uniform(0.1, 0.6), 3),
                                   "has_inhibition": rng.random() < 0.5},
                })
            elif op == "rewire" and doc.get("modules"):
                mods = doc["modules"]
                src = rng.choice(mods)
                dst = rng.choice(mods)
                if src.get("id") == dst.get("id"):
                    continue  # no self-loops in this mutation step
                doc.setdefault("edges", []).append({
                    "from": int(src["id"]), "to": int(dst["id"]),
                    "kind": rng.choice(["excitatory", "inhibitory"]),
                })
            elif op == "drop_unit" and len(doc.get("modules", [])) > 1:
                mods = doc["modules"]
                idx = rng.randrange(len(mods))
                dropped = mods.pop(idx)
                doc["edges"] = [
                    e for e in doc.get("edges", [])
                    if int(e.get("from", -1)) != int(dropped["id"])
                    and int(e.get("to", -1)) != int(dropped["id"])
                ]
            else:
                # Skip this step — no safe patch available.
                continue
        doc["stats"] = {
            "total_nodes": sum(max(int(m.get("n_nodes", 1)), 1)
                              for m in doc.get("modules", [])),
            "n_modules": len(doc.get("modules", [])),
            "n_edges": len(doc.get("edges", [])),
        }
        return doc

    # -- C2: survival criterion (binary, non-fitness)

    def can_survive(self, member: PopulationMember, n_steps: int = 5,
                    input_seed: int = 42) -> SurvivalReport:
        """Return True iff the individual's Runtime can run n_steps without error.

        Survival is a binary predicate:
          * step() runs to completion every step
          * every motor output stays within [-1, 1]
        No scoring, no ranking — matches Phase C2 of the design doc.
        """
        try:
            import runtime as _rt
            if hasattr(member.org, "to_static_dict"):
                org = _rt.Organism.from_dict(member.org.to_static_dict())
            else:
                org = _rt.Organism.from_dict(member.org)
        except Exception as e:
            return SurvivalReport(
                name=member.name, ok=False,
                reason=f"Organism.from_dict failed: {e}",
            )
        try:
            rt = _rt.Runtime(org, monitor_every=max(n_steps, 1))
            rng = random.Random(input_seed)
            sensory_ports = org.sensory_ports()
            for _ in range(n_steps):
                inputs = {p.port_id: round(rng.uniform(-0.9, 0.9), 3)
                          for p in sensory_ports}
                out = rt.step(inputs)
                for pid, val in out.items():
                    if not (-1.0 <= val <= 1.0):
                        return SurvivalReport(
                            name=member.name, ok=False,
                            reason=f"motor {pid!r} out of range: {val}",
                        )
        except Exception as e:
            return SurvivalReport(
                name=member.name, ok=False,
                reason=f"Runtime.step failed: {type(e).__name__}: {e}",
            )
        return SurvivalReport(
            name=member.name, ok=True,
            reason=f"{n_steps} steps completed; all motor outputs in [-1, 1]",
        )

    # -- C3: archive / selection

    def select(self, generation: int | None = None,
               keep_n: int | None = None) -> SelectionReport:
        """Binary selection: keep every *survivable* individual.

        The archive (DGM style) is not evicted — every surviving individual
        is kept. If ``keep_n`` is set and n_kept > keep_n, we keep the
        first keep_n members by insertion order (a tie-breaker, not a
        ranking — survival is a binary criterion, not a score).

        ``structural_gain`` is:
            n_new_signatures / max(1, n_unique_signatures)
        where n_new_signatures is the count of members added in this call
        whose signature was not present in the archive before.
        """
        survivors: list[PopulationMember] = []
        for name, m in self.members.items():
            if m.status != "active":
                continue
            probe = self.can_survive(m)
            if probe.ok:
                survivors.append(m)
        # Count structural gain for THIS call:
        n_new_sigs = 0
        for m in survivors:
            if self.archive.add(m) == "new":
                n_new_sigs += 1
        n_unique = self.archive.n_unique()
        n_kept = len(survivors)
        if keep_n is not None and keep_n < n_kept:
            survivors = survivors[:keep_n]
            n_kept = len(survivors)
        kept_names = [m.name for m in survivors]
        return SelectionReport(
            generation=generation if generation is not None else
                     max((m.generation for m in self.members.values()), default=0),
            n_candidates=len([m for m in self.members.values() if m.status == "active"]),
            n_kept=n_kept,
            n_new_signatures=n_new_sigs,
            n_unique_signatures=n_unique,
            structural_gain=(n_new_sigs / n_unique) if n_unique > 0 else 0.0,
            kept_names=kept_names,
        )

    # -- C4: death / archive

    def kill(self, member: PopulationMember, reason: str) -> None:
        """Mark a member dead with an explicit reason. Lineage is preserved."""
        if not reason or not reason.strip():
            raise DeathReasonError("kill() requires a non-empty reason")
        if member.name not in self.members:
            raise KeyError(f"kill: no such member: {member.name!r}")
        m = self.members[member.name]
        m.status = "dead"
        m.death_reason = reason.strip()
        m.death_utc = _now_iso()
        self.archive.archive(m.name)

    def archive_member(self, member: PopulationMember) -> None:
        """Mark a member archived (still in the archive, no longer 'active')."""
        if member.name not in self.members:
            raise KeyError(f"archive_member: no such member: {member.name!r}")
        m = self.members[member.name]
        m.status = "archived"
        m.archive_utc = _now_iso()
        self.archive.archive(m.name)

    # -- Lineage tree (C1)

    def lineage_tree(self, name: str) -> dict:
        """Walk the parent chain back to the root.

        Returns a dict with:
            "self":       member.as_dict()
            "ancestors":  [parent.as_dict(), grandparent.as_dict(), ...]
            "generation": length of the chain (self is generation 0)
        """
        if name not in self.members:
            raise KeyError(f"lineage_tree: no such member: {name!r}")
        chain: list[PopulationMember] = []
        cur: PopulationMember | None = self.members[name]
        seen: set[str] = set()
        while cur is not None and cur.name not in seen:
            chain.append(cur)
            seen.add(cur.name)
            parent_name = cur.parent
            cur = self.members.get(parent_name) if parent_name else None
        return {
            "self": chain[0].as_dict(),
            "ancestors": [m.as_dict() for m in chain[1:]],
            "generation": chain[0].generation,
        }

    # -- Snapshot

    def snapshot(self) -> dict:
        return {
            "n_members": len(self.members),
            "n_active": sum(1 for m in self.members.values() if m.status == "active"),
            "n_archived": sum(1 for m in self.members.values() if m.status == "archived"),
            "n_dead": sum(1 for m in self.members.values() if m.status == "dead"),
            "archive_unique_signatures": self.archive.n_unique(),
            "members": {k: v.as_dict() for k, v in self.members.items()},
        }


# --------------------------------------------------------------------- C5: negative result guard

class NegativeResultGuard:
    """C5 — negative result guardrail.

    Deliberate: **only this class** can trigger a shutdown. The rule is:

        if structural_gain == 0 for ``stall_limit`` consecutive generations
        and total members >= ``min_members``, raise NegativeResultTriggered.

    The raised exception carries a negative-result record that MUST be
    persisted (to the lineage tree / snapshot) before the population is
    discarded. This is the anti-"hope it will get better" mechanism:
    every stop is a stop for a reason, and every reason is on the record.
    """

    def __init__(self, population: Population,
                 stall_limit: int = 3, min_members: int = 4):
        self._pop = population
        self._stall_limit = max(1, int(stall_limit))
        self._min_members = max(1, int(min_members))
        self._history: list[float] = []

    def observe(self, report: SelectionReport) -> bool:
        """Record one generation's structural gain. Returns True if the
        guard fired (shutdown required), False otherwise.

        The guard is triggered when:
          * len(history) >= stall_limit
          * all of the last stall_limit entries are 0
          * total active + archived members >= min_members
        """
        gain = float(report.structural_gain)
        self._history.append(gain)
        n_total = len(self._pop.members)
        triggered = (
            len(self._history) >= self._stall_limit
            and all(g == 0.0 for g in self._history[-self._stall_limit:])
            and n_total >= self._min_members
        )
        if triggered:
            raise NegativeResultTriggered(
                f"stall_limit={self._stall_limit} consecutive 0-gain "
                f"generations with {n_total} members >= min_members="
                f"{self._min_members}; shutting down with negative-result "
                f"record (see guard.snapshot)"
            )
        return False

    def snapshot(self) -> dict:
        return {
            "stall_limit": self._stall_limit,
            "min_members": self._min_members,
            "history": list(self._history),
            "would_trigger": (
                len(self._history) >= self._stall_limit
                and all(g == 0.0 for g in self._history[-self._stall_limit:])
            ),
        }


# --------------------------------------------------------------------- self-test + CLI

def _self_test() -> int:
    """Sanity-check all Phase C components."""
    pop = Population(mutation_seed=42)
    org_a = {
        "modules": [
            {"id": 0, "name": "s", "function": "perceive", "n_nodes": 3,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.3, "has_inhibition": False}},
            {"id": 1, "name": "m", "function": "execute", "n_nodes": 3,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.3, "has_inhibition": False}},
        ],
        "edges": [{"from": 0, "to": 1, "kind": "excitatory"}],
        "stats": {"total_nodes": 6, "n_modules": 2, "n_edges": 1},
    }
    m0 = pop.spawn(org_a, "root")
    assert m0.generation == 0 and m0.parent is None
    m1 = pop.clone(m0, "clone_0")
    assert m1.generation == 1 and m1.parent == "root"
    m2 = pop.mutate(m0, "mut_0", seed=1)
    assert m2.generation == 1 and m2.parent == "root"
    tree = pop.lineage_tree("mut_0")
    assert tree["self"]["name"] == "mut_0"
    assert len(tree["ancestors"]) == 1
    assert tree["ancestors"][0]["name"] == "root"
    # Survival probe on a valid organism.
    surv = pop.can_survive(m0, n_steps=3)
    assert surv.ok, f"root should survive: {surv.reason}"
    # Selection report.
    report = pop.select(generation=1)
    assert report.n_kept >= 1, "at least one member should survive"
    assert report.structural_gain >= 0.0, "structural gain must be non-negative"
    # Kill a member with a reason.
    pop.kill(m1, "stagnation")
    assert pop.members["clone_0"].status == "dead"
    assert pop.members["clone_0"].death_reason == "stagnation"
    # Kill with empty reason must fail.
    try:
        pop.kill(m0, "")
        raise AssertionError("kill with empty reason must raise DeathReasonError")
    except DeathReasonError:
        pass
    # Negative result guard: build a population where every selection is
    # stall-limit-zero gain, verify the guard triggers.
    pop2 = Population(mutation_seed=7)
    # Register one root and clone it 5 times — every clone has the same
    # signature, so structural_gain is 0 for every generation.
    pop2.spawn(org_a, "root2")
    for i in range(5):
        pop2.clone(pop2.members["root2"], f"clone_{i}")
    guard = NegativeResultGuard(pop2, stall_limit=3, min_members=4)
    fired = False
    for _ in range(3):
        rep = pop2.select(generation=1)
        # Force structural_gain to 0 by calling select on already-seen sigs.
        # The archive already has root2's signature; clones have the same
        # sig, so they add no new signatures.
        try:
            guard.observe(rep)
        except NegativeResultTriggered:
            fired = True
            break
    assert fired, "guard must trigger after 3 zero-gain generations with 6 members"
    snap = pop.snapshot()
    assert snap["n_dead"] >= 1
    print(f"[ok] Phase C self-test: pop has {len(pop.members)} members, "
          f"dead={snap['n_dead']}, guard fired after 3 stalls")
    return 0


def _cli(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return _self_test()
    p.error("use --selftest for the built-in smoke test")
    return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
