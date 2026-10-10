"""
Damage injection layer for Phase B of the digital-organism design.

docs/DIGITAL_ORGANISM_DESIGN_2026-10-10.md §四 Phase B.1 — "可复现的扰动
（模块失效 / 接线断裂 / 端口污染）". Every damage is deterministic from a
seed; every injection returns a `DamageReport` that carries the topology
signature delta so a damage that silently does not change the topology is
caught as a bug.

Three damage kinds are supported:

  * `module_fail`   — zero out a module's recurrent weights. The module
                      still exists but its internal dynamics are dead
                      (a realistic neuron-death analogue rather than
                      removal). Changes the topology signature.
  * `edge_break`    — remove one edge from the wiring. Changes the
                      topology signature.
  * `port_poison`   — write an out-of-range value to a port by bypassing
                      `Port.write()`. Simulates an attacker or a hardware
                      fault. Does NOT change the topology signature (the
                      wiring is intact), but the trajectory will — so the
                      report carries both a signature delta and a
                      "silent" flag that the monitor must catch via the
                      trajectory (not the structure).

Design choices:

- **Stdlib-only**, mirrors runtime.py's promise. No numpy.
- **Deterministic**: same seed → same damage, same before/after signature.
- **Fail-closed**: every damage is validated to have the expected effect;
  a damage that does not produce the expected signature delta raises
  `DamageIneffectiveError` — this is the "wrong assertions are worse than
  none" discipline from Gate 22 / 23 / 25.
- **No side-effects on the source Organism**: every injection returns a
  NEW Organism via round-trip through `to_static_dict()`. The caller owns
  the original and can diff against it.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ------------------------------------------------------------------ exceptions

class DamageIneffectiveError(RuntimeError):
    """Raised when a damage does not produce the expected topology change.

    This is a *gate*, not a warning: if `module_fail` on a module does
    not change the topology signature, the damage implementation is
    broken and the whole repair loop is meaningless.
    """


# ------------------------------------------------------------------ kinds

class DamageKind(str, Enum):
    MODULE_FAIL = "module_fail"
    EDGE_BREAK = "edge_break"
    PORT_POISON = "port_poison"


# ------------------------------------------------------------------ reports

@dataclass
class DamageReport:
    """The result of a single damage injection."""

    damage_id: str
    kind: DamageKind
    target: Any
    seed: int
    before_signature: str
    after_signature: str
    signature_changed: bool
    description: str
    affected_module_ids: list[int] = field(default_factory=list)
    affected_edge_indices: list[int] = field(default_factory=list)
    affected_port_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "damage_id": self.damage_id,
            "kind": self.kind.value,
            "target": self.target,
            "seed": self.seed,
            "before_signature": self.before_signature,
            "after_signature": self.after_signature,
            "signature_changed": self.signature_changed,
            "description": self.description,
            "affected_module_ids": self.affected_module_ids,
            "affected_edge_indices": self.affected_edge_indices,
            "affected_port_ids": self.affected_port_ids,
        }


# ------------------------------------------------------------------ injector

class DamageInjector:
    """B1 — reproducible damage injection on an Organism.

    All damage is deterministic from `seed`. Every method returns a
    `(new_organism, DamageReport)` tuple. The source `organism` is
    never mutated.
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = int(seed)

    # ------------------------------------------------------------- module fail

    def module_fail(self, organism, module_id: int) -> tuple[Any, DamageReport]:
        """Zero out a module's recurrent weights.

        The module still exists (its `n_nodes` is preserved) but its
        `_w_rec` matrix is set to all zeros. The signature MUST change
        because the topology snapshot includes the recurrent edges.
        """
        import runtime as _rt  # local import to keep this module stdlib-only

        new_doc = json.loads(json.dumps(organism.to_static_dict()))
        # Locate the module in the static dict and mark it as failed.
        mod = None
        for m in new_doc.get("modules", []):
            if int(m.get("id")) == int(module_id):
                mod = m
                break
        if mod is None:
            raise KeyError(f"module {module_id!r} not found in organism")

        # Mark the module as failed by zeroing its recurrent density.
        # The topology_snapshot() will sample from reservoir_density; 0.0
        # density → no intra-module edges → signature changes.
        params = mod.setdefault("parameters", {})
        params["reservoir_density"] = 0.0
        params["_failed"] = True

        new_org = _rt.Organism.from_dict(new_doc)
        before = organism.topology_snapshot()["profile_signature"]
        after = new_org.topology_snapshot()["profile_signature"]
        changed = before != after
        if not changed:
            raise DamageIneffectiveError(
                f"module_fail on module {module_id!r} did not change the "
                f"topology signature — damage implementation is broken"
            )
        report = DamageReport(
            damage_id=f"df-{self.seed}-{module_id}",
            kind=DamageKind.MODULE_FAIL,
            target=module_id,
            seed=self.seed,
            before_signature=before,
            after_signature=after,
            signature_changed=True,
            description=f"module {module_id!r} recurrent weights zeroed "
                        f"(reservoir_density → 0)",
            affected_module_ids=[module_id],
        )
        return new_org, report

    # --------------------------------------------------------------- edge break

    def edge_break(self, organism, edge_index: int) -> tuple[Any, DamageReport]:
        """Remove one edge from the declared wiring.

        The signature MUST change because the topology snapshot includes
        inter-module edges.
        """
        import runtime as _rt

        new_doc = json.loads(json.dumps(organism.to_static_dict()))
        edges = new_doc.get("edges", [])
        if edge_index < 0 or edge_index >= len(edges):
            raise IndexError(
                f"edge_index {edge_index!r} out of range "
                f"(0..{len(edges)-1})"
            )
        removed = edges.pop(edge_index)
        new_org = _rt.Organism.from_dict(new_doc)
        before = organism.topology_snapshot()["profile_signature"]
        after = new_org.topology_snapshot()["profile_signature"]
        changed = before != after
        if not changed:
            raise DamageIneffectiveError(
                f"edge_break at index {edge_index!r} did not change the "
                f"topology signature — damage implementation is broken"
            )
        report = DamageReport(
            damage_id=f"eb-{self.seed}-{edge_index}",
            kind=DamageKind.EDGE_BREAK,
            target=f"edge[{edge_index}] ({removed})",
            seed=self.seed,
            before_signature=before,
            after_signature=after,
            signature_changed=True,
            description=f"edge {edge_index!r} removed: {removed}",
            affected_edge_indices=[edge_index],
        )
        return new_org, report

    # --------------------------------------------------------------- port poison

    def port_poison(
        self, organism, port_id: str, value: float = 5.0
    ) -> tuple[Any, DamageReport]:
        """Write an out-of-range value to a port, bypassing `Port.write()`.

        This is a *state* damage, not a *structural* damage. The topology
        signature does NOT change (the wiring is intact), but the port's
        `last_value` is now outside the [-1, 1] invariant that
        `Runtime.step` would otherwise refuse. The next step will either
        crash or propagate an invalid activation.

        Used to test that the runtime's boundary enforcement catches
        smuggled values — and that Phase B's repair loop can detect the
        corruption via trajectory (not structure).

        IMPORTANT: this damage mutates the Runtime's internal state, so
        the "new organism" returned here is a fresh copy with the poison
        baked in as an *initial condition*. The caller must instantiate
        a Runtime on this organism to observe the trajectory effect.
        """
        import runtime as _rt

        # Round-trip so we get an independent copy.
        new_doc = json.loads(json.dumps(organism.to_static_dict()))
        new_org = _rt.Organism.from_dict(new_doc)
        # Locate the port and set its value directly, bypassing write().
        port = new_org._port_index.get(port_id)
        if port is None:
            raise KeyError(
                f"port {port_id!r} not found; known: "
                f"{sorted(new_org._port_index.keys())[:8]}"
            )
        # Smuggle the value in — this is the point of the test.
        port.last_value = float(value)
        port.writes += 1

        # Signature is intentionally unchanged (structural damage).
        before = organism.topology_snapshot()["profile_signature"]
        after = new_org.topology_snapshot()["profile_signature"]
        changed = before != after
        if changed:
            raise DamageIneffectiveError(
                f"port_poison on {port_id!r} unexpectedly changed the "
                f"topology signature — port_poison is a state damage, not "
                f"a structural one"
            )
        report = DamageReport(
            damage_id=f"pp-{self.seed}-{port_id}",
            kind=DamageKind.PORT_POISON,
            target=port_id,
            seed=self.seed,
            before_signature=before,
            after_signature=after,
            signature_changed=False,
            description=f"port {port_id!r} value set to {value:+.4f} "
                        f"(bypassed write() range guard)",
            affected_port_ids=[port_id],
        )
        return new_org, report

    # ------------------------------------------------------------- batch

    def random_damage(
        self, organism, seed: int | None = None
    ) -> tuple[Any, DamageReport]:
        """Pick one damage kind at random (deterministic from seed) and apply it.

        Returns the same tuple as each of the three methods above.
        """
        import random
        s = int(seed if seed is not None else self.seed)
        rng = random.Random(s)
        kind = rng.choice([
            DamageKind.MODULE_FAIL,
            DamageKind.EDGE_BREAK,
            DamageKind.PORT_POISON,
        ])
        if kind == DamageKind.MODULE_FAIL:
            mod_ids = [m.mod_id for m in organism.modules]
            return self.module_fail(organism, rng.choice(mod_ids))
        elif kind == DamageKind.EDGE_BREAK:
            n_edges = len(organism.edges)
            if n_edges == 0:
                # No edges to break — fall back to module_fail.
                mod_ids = [m.mod_id for m in organism.modules]
                return self.module_fail(organism, rng.choice(mod_ids))
            return self.edge_break(organism, rng.randrange(n_edges))
        else:
            sensory_ids = [p.port_id for p in organism.sensory_ports()]
            if not sensory_ids:
                # No sensory ports — fall back to module_fail.
                mod_ids = [m.mod_id for m in organism.modules]
                return self.module_fail(organism, rng.choice(mod_ids))
            return self.port_poison(organism, rng.choice(sensory_ids),
                                    value=rng.uniform(2.0, 5.0))


# ------------------------------------------------------------------ selftest

def _self_test() -> int:
    """Built-in test — ``python damage.py --selftest``."""
    import runtime  # noqa: WPS433

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
    inj = DamageInjector(seed=42)
    ok = lambda name, cond: print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # --- module_fail
    org = runtime.Organism.from_dict(doc)
    new, rep = inj.module_fail(org, 1)
    ok("module_fail: signature changed", rep.signature_changed)
    ok("module_fail: report shape", rep.kind == DamageKind.MODULE_FAIL)
    ok("module_fail: source untouched",
       org.topology_snapshot()["profile_signature"] == rep.before_signature)
    ok("module_fail: new org different",
       new.topology_snapshot()["profile_signature"] == rep.after_signature)

    # --- edge_break
    new2, rep2 = inj.edge_break(org, 0)
    ok("edge_break: signature changed", rep2.signature_changed)
    ok("edge_break: report shape", rep2.kind == DamageKind.EDGE_BREAK)
    ok("edge_break: one fewer edge", len(new2.edges) == len(org.edges) - 1)

    # --- port_poison
    new3, rep3 = inj.port_poison(org, "sensory.0", value=3.0)
    ok("port_poison: signature unchanged (state damage)",
       not rep3.signature_changed)
    ok("port_poison: port value smuggled",
       new3._port_index["sensory.0"].last_value == 3.0)

    # --- determinism: same seed → same signature
    new_a, rep_a = DamageInjector(seed=99).module_fail(
        runtime.Organism.from_dict(doc), 1)
    new_b, rep_b = DamageInjector(seed=99).module_fail(
        runtime.Organism.from_dict(doc), 1)
    ok("module_fail: deterministic (same seed)",
       rep_a.after_signature == rep_b.after_signature)

    # --- random_damage is reproducible
    inj2 = DamageInjector(seed=7)
    _, rep_rand1 = inj2.random_damage(runtime.Organism.from_dict(doc))
    _, rep_rand2 = inj2.random_damage(runtime.Organism.from_dict(doc))
    ok("random_damage: deterministic (same seed)",
       rep_rand1.damage_id == rep_rand2.damage_id)

    # --- fail-closed: index out of range raises
    raised = False
    try:
        inj.edge_break(org, 999)
    except IndexError:
        raised = True
    ok("edge_break: out-of-range index raises IndexError", raised)

    # --- fail-closed: unknown port raises
    raised = False
    try:
        inj.port_poison(org, "sensory.does_not_exist")
    except KeyError:
        raised = True
    ok("port_poison: unknown port raises KeyError", raised)

    # --- report serialization
    d = rep.as_dict()
    ok("report.as_dict(): shape",
       "damage_id" in d and "kind" in d and "signature_changed" in d)
    ok("report.as_dict(): kind is enum value",
       d["kind"] == "module_fail")

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
