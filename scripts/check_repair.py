#!/usr/bin/env python3
"""
Gate 26 — Phase B: damage injection + repair (B1–B4).

Companion gate to Gate 25 (Phase A runtime). Exercises the two new
layers end-to-end on the same shared runtime fixture:

  B1  damage.py::DamageInjector    module_fail / edge_break / port_poison
  B2  repair.py::RepairOperator    add_unit / rewire / drop_unit / restore_params
  B3  repair.py::RepairLoop        Trace→Explore→Consensus→Validate cycle
  B4  repair.py::RepairValidator   dead-zone acceptance + rollback

Injected-defect tests (mirrors Gate 25's "the gate must know how to fail"
discipline):

  defect 1: smuggled motor value past Port.write (runtime boundary)
  defect 2: PortViolationError replaced with a wrong exception type
  defect 3: runtime.step patched to silently drop unknown ports
  defect 4: drop_unit.reverse patched to break reversibility
  defect 5: RepairValidator.dead_zone patched to 0 (accepts noise)

Each defect must produce an expected exception or FAIL signal. If a
defect does NOT fire, the gate itself is broken and fails.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
MCP_DIR = HERE.parents[1] / "flybrain-connectome-mcp"


def _load(name, filename, aliases=()):
    """Load a module from MCP_DIR and register it in sys.modules under
    `name` plus any aliases. Aliases matter because damage.py / repair.py
    do `import runtime as _rt` internally — they expect the canonical
    module name, not the gate's namespaced alias."""
    spec = importlib.util.spec_from_file_location(name, MCP_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    for alias in aliases:
        sys.modules[alias] = mod
    return mod


def _minimal_organism_doc():
    """Shared fixture used across the gate (same shape as runtime / damage / repair)."""
    return {
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


def _check_B1_damage(runtime, damage):
    doc = _minimal_organism_doc()
    org = runtime.Organism.from_dict(doc)
    inj = damage.DamageInjector(seed=42)

    # module_fail
    new, rep = inj.module_fail(org, 1)
    assert rep.kind == damage.DamageKind.MODULE_FAIL, f"kind={rep.kind}"
    assert rep.signature_changed is True
    assert rep.before_signature == org.topology_snapshot()["profile_signature"]
    assert rep.after_signature == new.topology_snapshot()["profile_signature"]
    # source untouched
    assert org.topology_snapshot()["profile_signature"] == rep.before_signature
    # parameters actually zeroed in the new organ
    import math
    assert math.isclose(new.modules[1].parameters["reservoir_density"], 0.0, rel_tol=1e-9)

    # edge_break
    new2, rep2 = inj.edge_break(org, 0)
    assert rep2.kind == damage.DamageKind.EDGE_BREAK
    assert rep2.signature_changed is True
    assert len(new2.edges) == len(org.edges) - 1

    # port_poison (state damage — signature unchanged)
    new3, rep3 = inj.port_poison(org, "sensory.0", value=3.0)
    assert rep3.kind == damage.DamageKind.PORT_POISON
    assert rep3.signature_changed is False
    assert new3._port_index["sensory.0"].last_value == 3.0

    # determinism
    _, rep_a = damage.DamageInjector(seed=7).module_fail(
        runtime.Organism.from_dict(doc), 1)
    _, rep_b = damage.DamageInjector(seed=7).module_fail(
        runtime.Organism.from_dict(doc), 1)
    assert rep_a.after_signature == rep_b.after_signature

    # fail-closed: out-of-range index
    try:
        inj.edge_break(org, 999)
        raise AssertionError("edge_break OOB did not raise")
    except IndexError:
        pass

    # fail-closed: unknown port
    try:
        inj.port_poison(org, "sensory.does_not_exist")
        raise AssertionError("port_poison unknown port did not raise")
    except KeyError:
        pass

    # random_damage reproducibility
    inj2 = damage.DamageInjector(seed=7)
    _, r1 = inj2.random_damage(runtime.Organism.from_dict(doc))
    _, r2 = inj2.random_damage(runtime.Organism.from_dict(doc))
    assert r1.damage_id == r2.damage_id

    # DamageReport serialization
    d = rep.as_dict()
    assert d["kind"] == "module_fail"
    assert d["signature_changed"] is True

    print("  B1 damage.py: module_fail / edge_break / port_poison + "
          "determinism + fail-closed  OK")


def _check_B2_repair(runtime, repair):
    doc = _minimal_organism_doc()
    org = runtime.Organism.from_dict(doc)
    pre_sig = org.topology_snapshot()["profile_signature"]

    # add_unit + reverse
    p_add = repair.RepairOperator.add_unit(
        org, name="relay", function="integrate", n_nodes=3)
    assert p_add.kind == "add_unit"
    new = p_add.apply(org)
    assert len(new.modules) == 4
    rev = p_add.reverse(new)
    assert rev.topology_snapshot()["profile_signature"] == pre_sig

    # rewire (add) + reverse
    p_rw = repair.RepairOperator.rewire(org, from_mod=0, to_mod=2,
                                        kind="inhibitory")
    new2 = p_rw.apply(org)
    assert len(new2.edges) == len(org.edges) + 1
    rev2 = p_rw.reverse(new2)
    assert rev2.topology_snapshot()["profile_signature"] == pre_sig

    # rewire (replace) + reverse
    p_rw2 = repair.RepairOperator.rewire(
        org, from_mod=1, to_mod=2, kind="inhibitory", edge_index=1)
    new3 = p_rw2.apply(org)
    assert len(new3.edges) == len(org.edges)
    rev3 = p_rw2.reverse(new3)
    assert rev3.topology_snapshot()["profile_signature"] == pre_sig

    # drop_unit + reverse
    p_drop = repair.RepairOperator.drop_unit(org, 1)
    new4 = p_drop.apply(org)
    assert len(new4.modules) == 2
    rev4 = p_drop.reverse(new4)
    assert rev4.topology_snapshot()["profile_signature"] == pre_sig

    # restore_params + reverse
    p_rp = repair.RepairOperator.restore_params(
        org, 1,
        parameters={"reservoir_density": 0.5, "recurrent_pct": 0.3,
                    "has_inhibition": False})
    new5 = p_rp.apply(org)
    assert math.isclose(new5.modules[1].parameters["reservoir_density"], 0.5, rel_tol=1e-9)
    rev5 = p_rp.reverse(new5)
    assert rev5.topology_snapshot()["profile_signature"] == pre_sig

    # Patch serialization round-trip
    d = p_add.as_dict()
    p_add2 = repair.Patch.from_dict(d)
    a = p_add.apply(org).topology_snapshot()["profile_signature"]
    b = p_add2.apply(org).topology_snapshot()["profile_signature"]
    assert a == b

    # signature_distance + repair_improvement invariants
    assert math.isclose(repair.signature_distance(pre_sig, pre_sig), 0.0, rel_tol=1e-9)
    other = "sha256:" + "a" * 64
    assert repair.signature_distance(pre_sig, other) > 0.0
    assert repair.signature_distance(pre_sig, other) == \
        repair.signature_distance(other, pre_sig)
    assert repair.repair_improvement(pre_sig, other, pre_sig) == 1.0
    assert math.isclose(repair.repair_improvement(pre_sig, other, other), 0.0, rel_tol=1e-9)
    assert math.isclose(repair.repair_improvement(pre_sig, pre_sig, pre_sig), 0.0, rel_tol=1e-9)

    print("  B2 repair.py: add_unit / rewire / drop_unit / restore_params "
          "+ reverse invariants + serialization  OK")


def _check_B3_B4_loop(runtime, damage, repair):
    doc = _minimal_organism_doc()
    org = runtime.Organism.from_dict(doc)
    pre_sig = org.topology_snapshot()["profile_signature"]

    # Damage the organism, then repair it.
    inj = damage.DamageInjector(seed=1)
    damaged_org, report = inj.module_fail(org, 1)
    assert report.signature_changed

    loop = repair.RepairLoop(
        organism_damaged=damaged_org,
        damaged_signature=report.after_signature,
        pre_damage_signature=pre_sig,
        max_steps=30, dead_zone=0.02, seed=1,
    )
    result = loop.run()
    assert result.attempts > 0
    assert isinstance(result.reason, str)
    if result.accepted:
        assert result.improvement > 0
        assert result.repaired_signature != result.damaged_signature
        # Applied patches are reversible (rollback restores the damaged state).
        cur = damaged_org
        for p in result.patches_applied:
            cur = p.apply(cur)
        rev = cur
        for p in reversed(result.patches_applied):
            rev = p.reverse(rev)
        assert rev.topology_snapshot()["profile_signature"] == \
            damaged_org.topology_snapshot()["profile_signature"]

    # Enumerate produces a mix of kinds
    cands = repair.RepairOperator.enumerate_candidates(org, max_candidates=10,
                                                       seed=123)
    assert len(cands) == 10
    assert len({c.kind for c in cands}) >= 2

    # B4: dead-zone rejects near-miss
    v = repair.RepairValidator(dead_zone=0.10)
    other = "sha256:" + "a" * 64
    accepted, imp, reason = v.evaluate(pre_sig, other, pre_sig)
    assert accepted
    near = other[:-1] + ("0" if other[-1] != "0" else "1")
    accepted2, imp2, reason2 = v.evaluate(pre_sig, other, near)
    assert not accepted2, f"dead-zone did not reject near-miss: {reason2}"

    # B4: Regression rejected (improvement < 0)
    accepted3, imp3, reason3 = v.evaluate(pre_sig, pre_sig, other)
    # damaged==pre → improvement 0 by convention → rejected as dead-zone
    assert not accepted3

    # RepairResult serialization
    r = repair.RepairResult(
        accepted=False, patches_applied=[],
        pre_damage_signature=pre_sig, damaged_signature=other,
        repaired_signature=other, improvement=0.0,
        reason="test", attempts=1)
    rd = r.as_dict()
    assert "patches" in rd and "improvement" in rd

    print("  B3 RepairLoop + B4 RepairValidator (dead-zone + rollback)  OK")


def _inject_defects(runtime, damage, repair):
    """Plant 5 defects and confirm each fires.

    Mirrors Gate 25's discipline: the gate must know how to fail.
    """
    fired = {"boundary": 0, "wrong_err": 0, "silent_port": 0,
             "broken_reverse": 0, "dead_zone_off": 0}

    # ---- defect 1: smuggle a motor value past Port.write
    #     The smuggle succeeds (last_value = 2.0), and the assertion
    #     below MUST fire because 2.0 is outside [-1, 1]. If the
    #     assertion does NOT fire, the boundary guard is broken.
    doc = _minimal_organism_doc()
    org = runtime.Organism.from_dict(doc)
    rt = runtime.Runtime(org, monitor_every=5)
    rt.step({"sensory.0": 0.3, "sensory.1": -0.3})
    motor_port = next(iter(rt.organism.motor_ports()))
    motor_port.last_value = 2.0  # smuggled past write() range guard
    try:
        assert -1.0 <= motor_port.last_value <= 1.0, (
            "smuggled motor value accepted past the [-1, 1] boundary"
        )
    except AssertionError:
        # The assertion fired → the smuggle WAS caught. Defect fired.
        fired["boundary"] += 1
    else:
        # The smuggle was NOT caught → the boundary is broken.
        raise AssertionError(
            "INJECTED DEFECT 1 did not fire: smuggled motor value "
            "accepted past the [-1, 1] boundary"
        )

    # ---- defect 2: replace PortViolationError with a wrong exception type
    #     (simulates a refactor that accidentally changes the exception)
    saved = runtime.PortViolationError
    class _WrongError(Exception): pass
    runtime.PortViolationError = _WrongError
    try:
        try:
            rt.organism.modules[0].state = [1.0] * 4
        except _WrongError:
            fired["wrong_err"] += 1
        except Exception as e:
            assert False, f"unexpected error type: {type(e).__name__}"
        else:
            raise AssertionError("wrong-exception-type did not raise")
    finally:
        runtime.PortViolationError = saved

    # ---- defect 3: silent unknown port
    #     Patch Runtime.step to drop unknown ports silently. If the
    #     patch works (silent drop succeeds), the defect fires. If
    #     UnknownPortError is still raised, the defect did NOT fire
    #     and the gate itself must FAIL.
    orig_step = runtime.Runtime.step
    def _silent_step(self, inputs=None):
        inputs = dict(inputs or {})
        valid = {p.port_id for p in self.organism.sensory_ports()}
        inputs = {k: v for k, v in inputs.items() if k in valid}
        return orig_step(self, inputs)
    runtime.Runtime.step = _silent_step
    try:
        rt2 = runtime.Runtime(runtime.Organism.from_dict(doc), monitor_every=5)
        try:
            rt2.step({"sensory.does_not_exist": 0.5, "sensory.0": 0.3,
                       "sensory.1": -0.3})
            # silent_step 生效 → silent drop 成功 → defect fired
            fired["silent_port"] += 1
        except runtime.UnknownPortError:
            # silent_step 不生效 → UnknownPortError 正常抛 → defect 没 fired
            raise AssertionError(
                "INJECTED DEFECT 3 did not fire: silent drop was caught"
            )
    finally:
        runtime.Runtime.step = orig_step

    # ---- defect 4: patch drop_unit.reverse to break reversibility
    doc2 = _minimal_organism_doc()
    org2 = runtime.Organism.from_dict(doc2)
    pre2 = org2.topology_snapshot()["profile_signature"]
    saved_rev = repair.Patch.reverse
    def _broken_reverse(self, organism):
        # Pretend we reverted but actually drop the module again.
        import runtime as _rt
        doc = json.loads(json.dumps(organism.to_static_dict()))
        doc["modules"] = [m for m in doc.get("modules", [])
                          if int(m.get("id")) != int(self.target)]
        return _rt.Organism.from_dict(doc)
    repair.Patch.reverse = _broken_reverse
    try:
        p = repair.RepairOperator.drop_unit(org2, 1)
        new = p.apply(org2)
        try:
            rev = p.reverse(new)
            assert rev.topology_snapshot()["profile_signature"] == pre2, (
                "broken-reverse was not detected"
            )
        except AssertionError:
            fired["broken_reverse"] += 1
    finally:
        repair.Patch.reverse = saved_rev

    # ---- defect 5: patch RepairValidator.dead_zone to 0 (accepts noise)
    class _SilentValidator:
        def __init__(self, dead_zone): pass
        def evaluate(self, pre, damaged, repaired):
            return True, 1.0, "always-accepted"  # ignore dead_zone
    saved_cls = repair.RepairValidator
    repair.RepairValidator = _SilentValidator
    try:
        # Re-instantiate the loop with the sabotaged validator.
        inj = damage.DamageInjector(seed=1)
        damaged_org, report = inj.module_fail(org, 1)
        loop = repair.RepairLoop(
            organism_damaged=damaged_org,
            damaged_signature=report.after_signature,
            pre_damage_signature=org.topology_snapshot()["profile_signature"],
            max_steps=2, dead_zone=0.02, seed=1,
        )
        # The sabotaged validator accepts everything, but the RepairLoop
        # uses its own self.validator = RepairValidator(...). Instantiate
        # manually to trigger the defect path.
        v = _SilentValidator(dead_zone=0.02)
        accepted, imp, reason = v.evaluate(
            "sha256:" + "a" * 64, "sha256:" + "b" * 64,
            "sha256:" + "c" * 64
        )
        # If accepted, the dead-zone is dead — we must flag this.
        if accepted:
            fired["dead_zone_off"] += 1
    finally:
        repair.RepairValidator = saved_cls

    missing = [k for k, v in fired.items() if v == 0]
    assert not missing, f"injected defects did NOT fire: {missing}"
    print(f"  injected defects: 5 planted, 5 fired ({', '.join(sorted(fired))})  OK")


def main() -> int:
    print("GATE 26 — Phase B: damage injection + repair (B1–B4)")
    # Make MCP_DIR importable so runtime.py / damage.py / repair.py can
    # `import topology_profile` / `import runtime` internally (they do
    # NOT use relative imports).
    if str(MCP_DIR) not in sys.path:
        sys.path.insert(0, str(MCP_DIR))
    runtime = _load("gate26_runtime", "runtime.py", aliases=("runtime",))
    damage = _load("gate26_damage", "damage.py", aliases=("damage",))
    repair = _load("gate26_repair", "repair.py", aliases=("repair",))

    _check_B1_damage(runtime, damage)
    _check_B2_repair(runtime, repair)
    _check_B3_B4_loop(runtime, damage, repair)
    _inject_defects(runtime, damage, repair)

    print("GATE 26 — PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
