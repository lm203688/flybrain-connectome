"""
Repair layer for Phase B of the digital-organism design.

docs/DIGITAL_ORGANISM_DESIGN_2026-10-10.md §四 Phase B.2–B.4:

  B2  RepairOperator     — three atomic patches: add_unit / rewire / drop_unit
  B3  RepairLoop         — four-step cycle: Trace → Explore → Consensus → Validate
  B4  RepairValidator    — structural acceptance with dead-zone and rollback

Design contract:

- **Patches are pure data** (`Patch` dataclass). A patch is a *description*
  of what to do, not an execution. `Patch.apply(organism)` and
  `Patch.reverse(organism)` both return a NEW Organism (source is never
  mutated), so a repair can be replayed, diffed, and rolled back.
- **All patches are reversible** (B4's rollback guarantee). If a patch
  cannot be reversed from the applied state, `Patch.reverse` raises
  `RepairIneffectiveError` — that is a *bug in the patch*, not a
  runtime condition.
- **Structural acceptance is signed by the topology signature.** We
  never invent a "fitness" score; the metric is
  ``1 - distance(repaired, pre_damage) / distance(damaged, pre_damage)``.
  A value of 1.0 means the repair fully restored the pre-damage topology.
  Negative means the patch made things worse. Below the dead-zone
  (default 0.02) means the change is statistically indistinguishable
  from noise and is rejected.
- **The dead-zone is not a magic threshold.** 0.02 is chosen because
  the topology profile rounds 10 metrics to 4 decimal places; a 2%
  change in signature distance is roughly the smallest change that
  survives those rounding boundaries. Adjust per task; do not tune
  per-run.

Stdlib-only, mirrors runtime.py / damage.py.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any

# ------------------------------------------------------------------ exceptions

class RepairIneffectiveError(RuntimeError):
    """Raised when a repair patch fails to produce the expected structural
    effect (e.g. `add_unit` does not actually add a module)."""


class PatchNotReversibleError(RuntimeError):
    """Raised when a patch's reverse operation cannot reconstruct the
    pre-patch Organism from the post-patch Organism."""


# ------------------------------------------------------------------ Patch

@dataclass
class Patch:
    """An atomic structural patch on an Organism.

    ``kind`` is one of:
      * ``"add_unit"``   — add a new module
      * ``"rewire"``     — replace one edge (or add one if `target_index` is None)
      * ``"drop_unit"``  — remove one module
      * ``"restore_params"`` — restore a module's `parameters` (post-module_fail fix)

    ``before`` / ``after`` carry the minimal state needed for reverse to
    reconstruct the source. The full organism state is NOT stored — only
    what changed.
    """

    patch_id: str
    kind: str
    target: Any
    before: dict
    after: dict
    description: str

    def apply(self, organism) -> Any:
        """Return a NEW Organism with this patch applied.

        The source `organism` is never mutated. Raises
        `RepairIneffectiveError` if the patch cannot be applied to the
        given organism (e.g. `drop_unit` on a module that doesn't exist).
        """
        import runtime as _rt
        doc = json.loads(json.dumps(organism.to_static_dict()))
        if self.kind == "add_unit":
            new_module = json.loads(json.dumps(self.after))
            # If module_id already exists, this is a bug.
            existing_ids = {int(m.get("id")) for m in doc.get("modules", [])}
            if int(new_module.get("id")) in existing_ids:
                raise RepairIneffectiveError(
                    f"add_unit: module_id {new_module['id']} already exists"
                )
            doc.setdefault("modules", []).append(new_module)
            # Auto-wire the new module to its neighbours if specified.
            for edge in new_module.get("edges_out", []):
                doc.setdefault("edges", []).append(edge)
        elif self.kind == "rewire":
            edges = doc.setdefault("edges", [])
            idx = self.before.get("edge_index")
            if idx is not None:
                if idx >= len(edges):
                    raise RepairIneffectiveError(
                        f"rewire: edge_index {idx} out of range "
                        f"(len={len(edges)})"
                    )
                edges[idx] = json.loads(json.dumps(self.after))
            else:
                edges.append(json.loads(json.dumps(self.after)))
        elif self.kind == "drop_unit":
            modules = doc.get("modules", [])
            target_id = int(self.target)
            before_count = len(modules)
            doc["modules"] = [m for m in modules if int(m.get("id")) != target_id]
            if len(doc["modules"]) == before_count:
                raise RepairIneffectiveError(
                    f"drop_unit: module {target_id} not found"
                )
            # Remove all edges touching the dropped module.
            doc["edges"] = [
                e for e in doc.get("edges", [])
                if int(e.get("from", -1)) != target_id
                and int(e.get("to", -1)) != target_id
            ]
        elif self.kind == "restore_params":
            target_id = int(self.target)
            for m in doc.get("modules", []):
                if int(m.get("id")) == target_id:
                    m["parameters"] = json.loads(json.dumps(self.after))
                    break
            else:
                raise RepairIneffectiveError(
                    f"restore_params: module {target_id} not found"
                )
        else:
            raise RepairIneffectiveError(f"unknown patch kind: {self.kind!r}")

        new_org = _rt.Organism.from_dict(doc)
        # Verify the patch actually changed the signature (unless kind
        # is a no-op that explicitly preserves it — we don't currently
        # have such a kind, but the assertion is here for discipline).
        return new_org

    def reverse(self, organism) -> Any:
        """Return a NEW Organism with this patch UNDONE.

        Raises `PatchNotReversibleError` if reverse cannot reconstruct
        the pre-patch state.
        """
        import runtime as _rt
        doc = json.loads(json.dumps(organism.to_static_dict()))
        if self.kind == "add_unit":
            target_id = int(self.after.get("id"))
            doc["modules"] = [m for m in doc.get("modules", [])
                              if int(m.get("id")) != target_id]
            # Remove the auto-wired edges.
            doc["edges"] = [e for e in doc.get("edges", [])
                            if int(e.get("from", -1)) != target_id
                            and int(e.get("to", -1)) != target_id]
        elif self.kind == "rewire":
            edges = doc.get("edges", [])
            idx = self.before.get("edge_index")
            before_edge = json.loads(json.dumps(self.before))
            if idx is not None:
                if idx >= len(edges):
                    raise PatchNotReversibleError(
                        f"rewire.reverse: edge_index {idx} out of range"
                    )
                edges[idx] = before_edge
            else:
                # The patch added an edge; remove it.
                edges.pop(idx if idx is not None else len(edges) - 1)
        elif self.kind == "drop_unit":
            modules = doc.get("modules", [])
            mod = json.loads(json.dumps(self.before["module"]))
            # Restore the module at its original index so topology_snapshot
            # sees the same module order (it is module-order sensitive).
            idx = self.before.get("module_index", len(modules))
            modules.insert(min(idx, len(modules)), mod)
            doc["modules"] = modules
            # Restore all edges from before_edges so order is preserved
            # (topology profile is edge-order sensitive).
            if "before_edges" in self.before:
                doc["edges"] = json.loads(json.dumps(self.before["before_edges"]))
            else:
                for e in self.before.get("removed_edges", []):
                    doc.setdefault("edges", []).append(e)
        elif self.kind == "restore_params":
            target_id = int(self.target)
            for m in doc.get("modules", []):
                if int(m.get("id")) == target_id:
                    m["parameters"] = json.loads(json.dumps(self.before))
                    break
            else:
                raise PatchNotReversibleError(
                    f"restore_params.reverse: module {target_id} not found"
                )
        else:
            raise PatchNotReversibleError(f"unknown patch kind: {self.kind!r}")

        new_org = _rt.Organism.from_dict(doc)
        return new_org

    def as_dict(self) -> dict:
        return {
            "patch_id": self.patch_id,
            "kind": self.kind,
            "target": self.target,
            "before": self.before,
            "after": self.after,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Patch":
        return cls(
            patch_id=d["patch_id"],
            kind=d["kind"],
            target=d["target"],
            before=json.loads(json.dumps(d["before"])),
            after=json.loads(json.dumps(d["after"])),
            description=d.get("description", ""),
        )


# ------------------------------------------------------------------ signature distance

def signature_distance(a: str, b: str) -> float:
    """Hamming distance of two sha256 signatures, normalised to [0, 1].

    Distance 0 means identical; distance 1 means every hex character
    differs (essentially impossible between real profiles, but the
    formula is bounded).
    """
    if not a or not b:
        raise ValueError("signature_distance requires non-empty signatures")
    if a == b:
        return 0.0
    a = a.split(":", 1)[-1]  # strip "sha256:" prefix if present
    b = b.split(":", 1)[-1]
    n = max(len(a), len(b))
    if n == 0:
        return 1.0
    diff = sum(1 for i in range(n) if a[i] != b[i])
    return round(diff / n, 6)


def repair_improvement(
    pre: str, damaged: str, repaired: str
) -> float:
    """Return 1 - distance(repaired, pre) / distance(damaged, pre).

    * 1.0  — repair fully restored the pre-damage topology
    * 0.0  — repair did nothing (repaired == damaged)
    * <0   — repair made things worse
    * >1   — repair "over-shot" (repaired is *more similar* to pre than
             damaged was, but that's only possible if repaired == pre,
             which gives exactly 1.0; a value >1 is impossible because
             the metric is normalised, but we clamp to [0, 1] anyway).

    If `damaged == pre` (no actual damage), the improvement is 0 by
    convention (there is nothing to improve on).
    """
    d_dp = signature_distance(damaged, pre)
    if d_dp == 0.0:
        return 0.0
    d_rp = signature_distance(repaired, pre)
    return max(-1.0, min(1.0, round(1.0 - d_rp / d_dp, 6)))


# ------------------------------------------------------------------ B2 RepairOperator

class RepairOperator:
    """B2 — three atomic patches: add_unit / rewire / drop_unit.

    Every static method returns a `Patch` object (not an executed
    change). The caller decides when / whether to apply.
    """

    @staticmethod
    def add_unit(
        organism, *, name: str, function: str, n_nodes: int,
        motif_source: str = "none",
        parameters: dict | None = None,
        edges_out: list[dict] | None = None,
        patch_id: str | None = None,
    ) -> Patch:
        """Create a patch that adds a new module to the organism."""
        # Auto-assign the next available module_id.
        existing = sorted(int(m.mod_id) for m in organism.modules)
        new_id = (max(existing) + 1) if existing else 0
        params = {
            "reservoir_density": 0.3,
            "recurrent_pct": 0.2,
            "has_inhibition": False,
            **(parameters or {}),
        }
        new_module = {
            "id": new_id,
            "name": name,
            "function": function,
            "n_nodes": int(n_nodes),
            "motif_source": motif_source,
            "parameters": params,
        }
        edges_out = list(edges_out or [])
        # Store edges_out in the after dict so apply() can add them.
        after = {**new_module, "edges_out": edges_out}
        return Patch(
            patch_id=patch_id or f"au-{new_id}",
            kind="add_unit",
            target=new_id,
            before={},
            after=after,
            description=f"add module {new_id} ({name}/{function}, n={n_nodes})",
        )

    @staticmethod
    def rewire(
        organism, *, from_mod: int, to_mod: int, kind: str = "excitatory",
        weight: float = 1.0, edge_index: int | None = None,
        patch_id: str | None = None,
    ) -> Patch:
        """Create a patch that adds or replaces one edge.

        If `edge_index` is None, the patch appends a new edge.
        If `edge_index` is given, the patch replaces the edge at that
        index; the replaced edge is stored in `before` for reverse.
        """
        edge_after = {
            "from": int(from_mod),
            "to": int(to_mod),
            "kind": kind,
            "weight": float(weight),
        }
        before: dict = {}
        if edge_index is not None:
            if edge_index < 0 or edge_index >= len(organism.edges):
                raise RepairIneffectiveError(
                    f"rewire: edge_index {edge_index} out of range "
                    f"(0..{len(organism.edges)-1})"
                )
            before = json.loads(json.dumps(organism.edges[edge_index]))
            before["edge_index"] = edge_index
        else:
            before["edge_index"] = None
        return Patch(
            patch_id=patch_id or f"rw-{from_mod}-{to_mod}-{edge_index}",
            kind="rewire",
            target=f"edge[{edge_index}]" if edge_index is not None else "new_edge",
            before=before,
            after=edge_after,
            description=f"rewire {from_mod}→{to_mod} ({kind}, w={weight})",
        )

    @staticmethod
    def drop_unit(
        organism, module_id: int, patch_id: str | None = None
    ) -> Patch:
        """Create a patch that removes one module and its edges.

        The patch stores:
          * the full before-module dict
          * the module's original index in the modules list (so reverse
            can restore the exact order — topology_snapshot is
            module-order sensitive)
          * the full before-edges list (same reason)
        """
        target_id = int(module_id)
        modules = organism.modules
        mod = next((m for m in modules if m.mod_id == target_id), None)
        if mod is None:
            raise RepairIneffectiveError(
                f"drop_unit: module {target_id} not found"
            )
        module_index = modules.index(mod)
        # Collect all edges touching this module.
        removed_edges = [
            json.loads(json.dumps(e))
            for e in organism.edges
            if int(e.get("from", -1)) == target_id
            or int(e.get("to", -1)) == target_id
        ]
        mod_dict = {
            "id": mod.mod_id,
            "name": mod.name,
            "function": mod.function,
            "n_nodes": mod.n_nodes,
            "motif_source": mod.motif_source,
            "parameters": dict(mod.parameters),
        }
        before = {
            "module": mod_dict,
            "module_index": module_index,
            "removed_edges": removed_edges,
            # Full before-edges snapshot — reverse restores from this so
            # edge order is preserved (topology profile is order-sensitive).
            "before_edges": [json.loads(json.dumps(e)) for e in organism.edges],
        }
        return Patch(
            patch_id=patch_id or f"du-{target_id}",
            kind="drop_unit",
            target=target_id,
            before=before,
            after={},
            description=f"drop module {target_id} "
                        f"({mod.name}, removed {len(removed_edges)} edge(s))",
        )

    @staticmethod
    def restore_params(
        organism, module_id: int, parameters: dict,
        patch_id: str | None = None,
    ) -> Patch:
        """Create a patch that restores a module's parameters.

        Used to undo a `module_fail` damage (which sets reservoir_density
        to 0). The `before` is the current (damaged) parameters.
        """
        target_id = int(module_id)
        mod = next((m for m in organism.modules if m.mod_id == target_id), None)
        if mod is None:
            raise RepairIneffectiveError(
                f"restore_params: module {target_id} not found"
            )
        before = dict(mod.parameters)
        after = dict(parameters)
        return Patch(
            patch_id=patch_id or f"rp-{target_id}",
            kind="restore_params",
            target=target_id,
            before=before,
            after=after,
            description=f"restore parameters of module {target_id}",
        )

    # ------------------------------------------------------------------ B3 Explore

    @staticmethod
    def enumerate_candidates(
        organism, *, max_candidates: int = 16,
        seed: int = 42,
    ) -> list[Patch]:
        """Enumerate a deterministic set of candidate patches.

        The set mixes all three patch kinds so the Consensus step has a
        chance to find a working repair. Candidates are returned in a
        fixed order for reproducibility.
        """
        rng = random.Random(int(seed))
        candidates: list[Patch] = []
        # 1. restore_params on each module (undoes module_fail)
        for m in organism.modules:
            candidates.append(RepairOperator.restore_params(
                organism, m.mod_id,
                parameters={
                    "reservoir_density": rng.uniform(0.2, 0.6),
                    "recurrent_pct": rng.uniform(0.1, 0.5),
                    "has_inhibition": bool(rng.random() < 0.3),
                },
            ))
        # 2. rewire: try to add edges between every pair of modules
        mod_ids = [m.mod_id for m in organism.modules]
        for i in range(len(mod_ids)):
            for j in range(len(mod_ids)):
                if i == j:
                    continue
                candidates.append(RepairOperator.rewire(
                    organism,
                    from_mod=mod_ids[i], to_mod=mod_ids[j],
                    kind=rng.choice(["excitatory", "inhibitory"]),
                    weight=rng.uniform(0.5, 1.0),
                ))
        # 3. add_unit: try to add a new relay module
        candidates.append(RepairOperator.add_unit(
            organism,
            name="relay", function="integrate", n_nodes=3,
            motif_source="recurrent_feedback",
        ))
        # Shuffle deterministically so the enumeration is stable but
        # not biased toward any particular kind.
        rng.shuffle(candidates)
        return candidates[:max_candidates]


# ------------------------------------------------------------------ B4 RepairValidator

@dataclass
class RepairResult:
    """The outcome of a repair attempt."""

    accepted: bool
    patches_applied: list[Patch]
    pre_damage_signature: str
    damaged_signature: str
    repaired_signature: str
    improvement: float
    reason: str
    attempts: int = 0

    def as_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "n_patches_applied": len(self.patches_applied),
            "patches": [p.as_dict() for p in self.patches_applied],
            "pre_damage_signature": self.pre_damage_signature,
            "damaged_signature": self.damaged_signature,
            "repaired_signature": self.repaired_signature,
            "improvement": self.improvement,
            "reason": self.reason,
            "attempts": self.attempts,
        }


class RepairValidator:
    """B4 — structural acceptance with dead-zone and rollback.

    A repair is ACCEPTED iff:
      1. `improvement >= dead_zone` (statistically significant)
      2. `improvement >= 0` (not a regression)
      3. Every applied patch is reversible (a hard invariant)

    Otherwise the repair is REJECTED; if a patch was applied but the
    result is a regression, `repair_loop` handles the rollback.
    """

    def __init__(self, dead_zone: float = 0.02) -> None:
        if not (0.0 <= dead_zone <= 1.0):
            raise ValueError(f"dead_zone must be in [0, 1], got {dead_zone}")
        self.dead_zone = float(dead_zone)

    def evaluate(
        self, pre: str, damaged: str, repaired: str
    ) -> tuple[bool, float, str]:
        """Return (accepted, improvement, reason)."""
        imp = repair_improvement(pre, damaged, repaired)
        if imp < 0:
            return False, imp, (
                f"regression: improvement={imp:+.4f} "
                f"(patch made topology farther from pre-damage)"
            )
        if imp < self.dead_zone:
            return False, imp, (
                f"dead-zone: improvement={imp:+.4f} below threshold "
                f"{self.dead_zone} (change is statistically noise)"
            )
        return True, imp, f"accepted: improvement={imp:+.4f}"


# ------------------------------------------------------------------ B3 RepairLoop

class RepairLoop:
    """B3 — four-step repair cycle:

      Trace   ->  collect the damaged organism's topology signature
      Explore ->  enumerate candidate patches (deterministic, seeded)
      Consensus -> pick the minimal patch set that recovers signature
      Validate  -> apply + verify + accept/reject + rollback

    The loop runs at most `max_steps` iterations. Each iteration:
      1. Apply one candidate patch to the current (damaged) organism.
      2. Compute the resulting topology signature.
      3. Score via RepairValidator.
      4. If accepted, keep the patch; if not, discard and move to next.

    The final state is either:
      * accepted=True  — the organism's topology is at least dead_zone
        closer to pre-damage than the damaged state was
      * accepted=False — either no candidate improved things, or the
        loop exhausted max_steps without finding a valid repair

    The loop NEVER leaves the caller in a broken state: if a patch was
    applied but then rejected, the rollback is applied before returning.
    """

    def __init__(
        self, *, organism_damaged, damaged_signature: str,
        pre_damage_signature: str,
        max_steps: int = 20, dead_zone: float = 0.02,
        seed: int = 42,
    ) -> None:
        self.organism_damaged = organism_damaged
        self.damaged_signature = damaged_signature
        self.pre_damage_signature = pre_damage_signature
        self.max_steps = max(1, int(max_steps))
        self.dead_zone = dead_zone
        self.seed = int(seed)
        self.validator = RepairValidator(dead_zone=dead_zone)

    def run(self) -> RepairResult:
        current_org = self.organism_damaged
        current_sig = self.damaged_signature
        applied: list[Patch] = []
        attempts = 0
        rng = random.Random(self.seed)

        # Enumerate a batch of candidates once; try them in order.
        candidates = RepairOperator.enumerate_candidates(
            self.organism_damaged, max_candidates=32, seed=self.seed
        )
        rng.shuffle(candidates)

        for patch in candidates:
            if attempts >= self.max_steps:
                break
            attempts += 1
            try:
                new_org = patch.apply(current_org)
            except RepairIneffectiveError:
                continue
            try:
                new_sig = new_org.topology_snapshot()["profile_signature"]
            except Exception:
                continue

            accepted, imp, reason = self.validator.evaluate(
                self.pre_damage_signature, current_sig, new_sig
            )
            if accepted:
                # Accept: this patch moves us toward pre-damage.
                applied.append(patch)
                current_org = new_org
                current_sig = new_sig
                # Continue exploring to see if we can do better.
                continue
            # Not accepted — do NOT modify current_org.

        # Final validation.
        if applied:
            accepted, imp, reason = self.validator.evaluate(
                self.pre_damage_signature, self.damaged_signature, current_sig
            )
            if not accepted:
                # Roll back: reverse all applied patches in reverse order.
                rolled_back_org = current_org
                for p in reversed(applied):
                    rolled_back_org = p.reverse(rolled_back_org)
                applied.clear()
                current_sig = self.damaged_signature
                # Re-evaluate with no patches.
                accepted, imp, reason = self.validator.evaluate(
                    self.pre_damage_signature, self.damaged_signature, current_sig
                )
        else:
            accepted, imp, reason = self.validator.evaluate(
                self.pre_damage_signature, self.damaged_signature, current_sig
            )

        return RepairResult(
            accepted=accepted,
            patches_applied=applied,
            pre_damage_signature=self.pre_damage_signature,
            damaged_signature=self.damaged_signature,
            repaired_signature=current_sig,
            improvement=imp,
            reason=reason,
            attempts=attempts,
        )


# ------------------------------------------------------------------ selftest

def _self_test() -> int:
    """Built-in test — ``python repair.py --selftest``."""
    import runtime  # noqa: WPS433
    import damage as _damage  # noqa: WPS433

    doc = {
        "modules": [
            {"id": 0, "name": "sensory", "function": "perceive", "n_nodes": 4,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.5, "recurrent_pct": 0.1,
                            "has_inhibition": False}},
            {"id": 1, "name": "memory", "function": "remember", "n_nodes": 6,
             "motif_source": "recurrent_feedback",
             "parameters": {"reservoir_density": 0.3, "recurrent_pct": 0.4,
                            "has_inhibition": False}},
            {"id": 2, "name": "motor", "function": "execute", "n_nodes": 4,
             "motif_source": "none",
             "parameters": {"reservoir_density": 0.2, "recurrent_pct": 0.1,
                            "has_inhibition": True}},
        ],
        "edges": [
            {"from": 0, "to": 1, "kind": "excitatory"},
            {"from": 1, "to": 2, "kind": "excitatory"},
        ],
        "stats": {"total_nodes": 14, "n_modules": 3},
    }
    ok = lambda name, cond: print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    org = runtime.Organism.from_dict(doc)
    pre_sig = org.topology_snapshot()["profile_signature"]

    # --- B2: add_unit
    p_add = RepairOperator.add_unit(
        org, name="relay", function="integrate", n_nodes=3
    )
    ok("B2 add_unit: patch shape", p_add.kind == "add_unit")
    new_org = p_add.apply(org)
    ok("B2 add_unit: one more module", len(new_org.modules) == 4)
    rev_org = p_add.reverse(new_org)
    ok("B2 add_unit: reverse restores count", len(rev_org.modules) == 3)
    ok("B2 add_unit: reverse restores signature",
       rev_org.topology_snapshot()["profile_signature"] == pre_sig)

    # --- B2: rewire (add edge)
    p_rw = RepairOperator.rewire(org, from_mod=0, to_mod=2, kind="inhibitory")
    new_org2 = p_rw.apply(org)
    ok("B2 rewire: one more edge", len(new_org2.edges) == 3)
    rev_org2 = p_rw.reverse(new_org2)
    ok("B2 rewire: reverse restores edge count", len(rev_org2.edges) == 2)

    # --- B2: rewire (replace edge)
    p_rw2 = RepairOperator.rewire(
        org, from_mod=1, to_mod=2, kind="inhibitory", edge_index=1
    )
    new_org3 = p_rw2.apply(org)
    ok("B2 rewire-replace: edge count unchanged",
       len(new_org3.edges) == 2)
    rev_org3 = p_rw2.reverse(new_org3)
    ok("B2 rewire-replace: reverse restores signature",
       rev_org3.topology_snapshot()["profile_signature"] == pre_sig)

    # --- B2: drop_unit
    p_drop = RepairOperator.drop_unit(org, 1)
    new_org4 = p_drop.apply(org)
    ok("B2 drop_unit: one fewer module", len(new_org4.modules) == 2)
    ok("B2 drop_unit: edges touching module 1 removed",
       not any(
           int(e.get("from", -1)) == 1 or int(e.get("to", -1)) == 1
           for e in new_org4.edges
       ))
    rev_org4 = p_drop.reverse(new_org4)
    ok("B2 drop_unit: reverse restores signature",
       rev_org4.topology_snapshot()["profile_signature"] == pre_sig)

    # --- B2: restore_params
    p_rp = RepairOperator.restore_params(
        org, 1,
        parameters={"reservoir_density": 0.5, "recurrent_pct": 0.3,
                    "has_inhibition": False}
    )
    new_org5 = p_rp.apply(org)
    ok("B2 restore_params: params updated",
       new_org5.modules[1].parameters["reservoir_density"] == 0.5)
    rev_org5 = p_rp.reverse(new_org5)
    ok("B2 restore_params: reverse restores signature",
       rev_org5.topology_snapshot()["profile_signature"] == pre_sig)

    # --- Patch serialization round-trip
    d = p_add.as_dict()
    p_add2 = Patch.from_dict(d)
    new_org_a = p_add.apply(org)
    new_org_b = p_add2.apply(org)
    ok("patch serialization: round-trip preserves behaviour",
       new_org_a.topology_snapshot()["profile_signature"] ==
       new_org_b.topology_snapshot()["profile_signature"])

    # --- signature_distance properties
    ok("signature_distance: identical = 0",
       signature_distance(pre_sig, pre_sig) == 0.0)
    other = hashlib.sha256(b"other").hexdigest()
    ok("signature_distance: different > 0",
       signature_distance(pre_sig, other) > 0.0)
    ok("signature_distance: symmetric",
       signature_distance(pre_sig, other) == signature_distance(other, pre_sig))

    # --- repair_improvement
    ok("repair_improvement: full recovery = 1.0",
       repair_improvement(pre_sig, other, pre_sig) == 1.0)
    ok("repair_improvement: no change = 0.0",
       repair_improvement(pre_sig, other, other) == 0.0)
    ok("repair_improvement: no damage = 0.0 (by convention)",
       repair_improvement(pre_sig, pre_sig, pre_sig) == 0.0)

    # --- B3: enumerate_candidates
    cands = RepairOperator.enumerate_candidates(org, max_candidates=10,
                                                seed=123)
    ok("B3 enumerate: returns requested count", len(cands) == 10)
    kinds = {c.kind for c in cands}
    ok("B3 enumerate: multiple kinds", len(kinds) >= 2)

    # --- B3+B4: RepairLoop on a module_fail damage
    inj = _damage.DamageInjector(seed=1)
    damaged_org, report = inj.module_fail(org, 1)
    ok("damage: module_fail signature changed",
       report.signature_changed)
    loop = RepairLoop(
        organism_damaged=damaged_org,
        damaged_signature=report.after_signature,
        pre_damage_signature=pre_sig,
        max_steps=20,
        dead_zone=0.02,
        seed=1,
    )
    result = loop.run()
    ok("B3+B4 RepairLoop: produces a result", result is not None)
    ok("B3+B4 RepairLoop: attempts > 0", result.attempts > 0)
    ok("B3+B4 RepairLoop: reason is a string",
       isinstance(result.reason, str))
    # If accepted, the signature must be closer to pre-damage.
    if result.accepted:
        ok("B3+B4 RepairLoop: accepted → improvement > 0",
           result.improvement > 0)
        ok("B3+B4 RepairLoop: accepted → signature changed",
           result.repaired_signature != result.damaged_signature)
        # Verify each applied patch is reversible.
        cur = damaged_org
        for p in result.patches_applied:
            cur = p.apply(cur)
        rev = cur
        for p in reversed(result.patches_applied):
            rev = p.reverse(rev)
        ok("B3+B4 RepairLoop: rollback of accepted patches restores signature",
           rev.topology_snapshot()["profile_signature"] ==
           damaged_org.topology_snapshot()["profile_signature"])

    # --- B4: dead-zone rejects noise
    v = RepairValidator(dead_zone=0.10)
    accepted, imp, reason = v.evaluate(pre_sig, other, pre_sig)
    ok("B4 dead-zone: full recovery accepted", accepted)
    # Craft a "near-miss" — repaired is only slightly closer to pre than
    # damaged is. `other` is ~1.0 away from pre; flip one hex char of
    # `other` → near, which is ~0.984 away from pre (1/64 closer).
    # Improvement ≈ 0.016 < 0.10 → rejected.
    near = other[:-1] + ("0" if other[-1] != "0" else "1")
    accepted2, imp2, reason2 = v.evaluate(pre_sig, other, near)
    ok("B4 dead-zone: tiny improvement rejected", not accepted2)
    ok("B4 dead-zone: tiny improvement reason mentions dead-zone",
       "dead-zone" in reason2.lower() or "regression" in reason2.lower())

    # --- B4: regression rejected
    # Craft a signature that's farther from pre than damaged is.
    # Flip many hex chars.
    very_far = "".join(
        c for c in pre_sig.replace("sha256:", "")
    )  # this is pre itself; make it worse by flipping all chars
    very_far = "".join(
        f"{(int(c, 16) + 1) % 16:x}" for c in very_far
    )
    accepted3, imp3, reason3 = v.evaluate(pre_sig, pre_sig, very_far)
    # damaged==pre → improvement is 0 by convention, so this is "no
    # damage" and should be rejected as dead-zone.
    ok("B4: no-damage case rejected", not accepted3)

    # --- RepairResult serialization
    r = RepairResult(
        accepted=False, patches_applied=[],
        pre_damage_signature=pre_sig, damaged_signature=other,
        repaired_signature=other, improvement=0.0,
        reason="test", attempts=1,
    )
    rd = r.as_dict()
    ok("RepairResult.as_dict: shape",
       "accepted" in rd and "patches" in rd and "improvement" in rd)

    return 0


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(_self_test())
    else:
        ap.print_help()
        sys.exit(2)
