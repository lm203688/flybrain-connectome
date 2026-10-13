#!/usr/bin/env python3
"""
GATE 24 — T3 middleware rule engine (conditional, fail-closed).

The combination-rule middleware (module_combinator) is Tier-2: it lives in the
private `flybrain-connectome-core` package and is only importable when that
package is installed or a local checkout is discoverable (env FLYBRAIN_CORE or a
sibling `flybrain-connectome-core` directory next to this repo).

On a bare public install this gate SKIPS so the battery stays green. When the
core IS available it asserts the engine actually works and that its curated rules
are backed by the shipped connectome data — the ROADMAP T3 deliverable
("中间件规则必须能复现它引用的数据") expressed as a real, fail-closed check.
"""
from __future__ import annotations

import builtins as _builtins
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _category_support(combo_rules) -> int:
    """Count directional combination rules whose (from_category, to_category)
    direction is enriched (>=1.5x) in the shipped connectome candidate data.

    Uses the real engine's loaded candidate table, so it fails closed if the
    data file is missing or the rules are gutted.
    """
    import flybrain_core.module_combinator as mc  # noqa: WPS433 (core optional)

    cand = mc._load_candidate_rules().get("candidates", [])
    catlut: dict[tuple, list] = {}
    for c in cand:
        catlut.setdefault((c.get("from_category"), c.get("to_category")), []).append(c)
    n = 0
    for r in combo_rules:
        f, t = r.get("from_category"), r.get("to_category")
        if f in ("*", None) or t in ("*", None):
            continue  # wildcard rules are global constraints, not pairwise-testable
        if any(c.get("enrichment", 0) >= 1.5 for c in catlut.get((f, t), [])):
            n += 1
    return n


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT / "flybrain-connectome-mcp"))
    import core_bridge  # noqa: WPS433

    if not core_bridge.core_available():
        print("GATE 24 — T3 middleware: SKIP (Tier-2 core not configured)")
        print("  set FLYBRAIN_CORE or place a sibling flybrain-connectome-core "
              "checkout to enable this gate.")
        return 0

    print("GATE 24 — T3 middleware: core AVAILABLE, running assertions")
    import module_combinator as stub  # public stub delegates to the real engine

    lr = stub.list_rules()
    combo = lr["combination_rules"]
    nest = lr["nesting_rules"]
    mult = lr["multiplier_semantics"]
    assert len(combo) == 12, f"expected 12 combination rules, got {len(combo)}"
    assert len(nest) == 7, f"expected 7 nesting rules, got {len(nest)}"
    assert len(mult) == 4, f"expected 4 multiplier semantics, got {len(mult)}"
    print(f"  rule counts: 12 + 7 + 4 = {len(combo) + len(nest) + len(mult)} OK")
    assert lr.get("schema_version") == "1.1", "SCHEMA_VERSION must stay 1.1"

    # Engine self-tests must pass against the real rule logic.
    r1 = stub.validate_combination([
        {"from_category": "sensory_input", "to_category": "recurrent_memory",
         "from_superclass": "ol_sensory", "to_superclass": "ol_intrinsic"}])
    assert r1["compatible"], "sensory->recurrent must be compatible"
    r2 = stub.validate_combination([
        {"from_category": "recurrent_memory", "to_category": "recurrent_memory",
         "from_superclass": "ol_intrinsic", "to_superclass": "cb_intrinsic"}])
    assert r2["compatible"], "memory self-loop must be compatible"
    r3 = stub.validate_nesting(["sensory_input", "recurrent_memory", "motor"])
    assert r3.get("valid"), f"nesting chain must validate: {r3}"
    r4 = stub.expand_organism({"modules": [
        {"category": "recurrent_memory", "copies": 3},
        {"category": "sensory_input", "copies": 2}]})
    assert r4["total_copies"] == 5, f"expand expected 5 copies, got {r4['total_copies']}"
    print("  engine self-tests (validate / nesting / expand) OK")

    # MCP dispatch layer: server.py -> stub -> core must return REAL engine
    # output, not a degraded tier2_required envelope. This is the layer where
    # the silent-degradation bug actually lived (the stub imported flybrain_core
    # before core_bridge ran its path discovery), so asserting it here is what
    # closes the hole — every other gate only exercised the module directly.
    sys.path.insert(0, str(REPO_ROOT / "flybrain-connectome-mcp" / "mcp_connectome"))
    import server  # noqa: WPS433

    dl = server._list_combination_rules()
    assert dl.get("combination_rules") == combo, \
        "dispatch returns different rules than the engine (silent degradation?)"
    assert "combination_rules" in dl, \
        f"dispatch envelope not the real rule list: {sorted(dl)[:6]}"
    d3 = server._get_multiplier_metrics({})
    assert d3 == stub.get_multiplier_metrics(), \
        "server dispatch must return the stub's multiplier envelope verbatim"
    assert list(d3.get("semantics", {}).keys()) == list(mult.keys()), \
        f"dispatch semantics payload mismatch: {sorted(d3.get('semantics', {}))}"
    print("  MCP dispatch layer returns real engine output (no silent degradation)")

    # Audit runs and covers all 12 combination rules with a structured report.
    audit = stub.audit_rules_against_data()
    assert "audit" in audit and len(audit["audit"]) == 12, \
        f"audit must cover 12 rules, got {len(audit.get('audit', []))}"
    print("  audit_rules_against_data() ran, 12-rule report OK")

    # Data reproduction: the shipped connectome candidate data must back the
    # directional rules. 4 is the verified minimum (sensory->recurrent,
    # recurrent->visual, recurrent->motor, relay->recurrent).
    supported = _category_support(combo)
    assert supported >= 4, \
        f"category-level data support too low: {supported} (expected >= 4)"
    print(f"  data reproduction: {supported} directional rules backed by "
          f"shipped connectome data OK")

    # ---- T5 #4: cross-species role binding annotation ----------------- #
    # The public synthesis path must bind modules by the engine rule's
    # binding_key (wiring_role + topology_position), derived from the
    # profiles' real capability / species_source fields — never a hardcoded
    # taxonomy. The binding key is read from the rule, so a drift between what
    # the middleware claims and what the artifact reports is caught here.
    import synthetic_bio_topology as sbot

    rule = next(r for r in nest if r.get("rule_id") == "cross_species_role_binding")
    rb = sbot.cross_species_role_binding(
        {i: dict(sbot.MODULE_PROFILES[n], name=n) for i, n in enumerate(
            ("pyramidal_l23", "mauthner_cell", "lateral_line_hair_cell",
             "spinal_motor_alpha", "retinal_gc", "dopaminergic_vta"))})
    assert rb.get("status") == "ok", f"role binding must resolve when core is live: {rb}"
    assert rb["binding_key"] == rule["binding_key"], \
        f"binding_key drifted from the engine rule: {rb['binding_key']} != {rule['binding_key']}"
    assert rb["ignore_fields"] == rule["ignore_fields"], "ignore_fields drifted from the rule"
    assert rb["multiplier_semantic"] == rule["multiplier_semantic"], "multiplier_semantic drifted"
    assert rb["n_groups"] >= 6, f"expected >= 6 binding groups, got {rb['n_groups']}"
    assert rb["n_cross_species_groups"] >= 4, \
        f"cross-species binding too thin: {rb['n_cross_species_groups']}"
    for g in rb["groups"]:
        assert g["topology_position"] in {"sensory", "relay", "motor"}, \
            f"unknown funnel tier: {g['topology_position']}"
        assert g["n_profiles"] >= 1 and len(g["modules"]) >= 1, f"empty binding group: {g}"
    print(f"  T5 #4 role binding: {rb['n_cross_species_groups']}/"
          f"{rb['n_groups']} groups cross-species substitutable OK")

    # The annotation must actually be carried by generated organisms, and it
    # must degrade honestly (not raise) when the Tier-2 rule is unreachable.
    org = sbot.design_organism({"n_modules": 3, "agents_per_module": 3, "seed": 7})
    assert "role_binding" in org, "design_organism must carry the role_binding annotation"
    fake = _builtins.__import__

    def _blocked(name, *a, **k):
        if name == "module_combinator":
            raise ImportError("injection: Tier-2 core unreachable")
        return fake(name, *a, **k)

    _builtins.__import__ = _blocked
    try:
        deg = sbot.cross_species_role_binding(
            {0: dict(sbot.MODULE_PROFILES["pyramidal_l23"], name="pyramidal_l23")})
    finally:
        _builtins.__import__ = fake
    assert deg.get("status") == "unavailable" and "reason" in deg, \
        f"missing core must degrade to a reason, not raise or claim ok: {deg}"
    print("  role binding degrades to a reason (no raise, no false 'ok') OK")

    print("GATE 24 — PASS")
    return 0


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: inject defects into the T3 middleware
    module and assert the gate goes red. Each injection exercises one of
    the failure classes the gate's assertions declare.

    The gate uses bare `assert` statements, so AssertionError is caught
    and treated as rc=1. Apply and restore are structurally separate
    (monkey-patch + finally), so no injection leaks state into the next one.
    """
    import sys as _sys
    bad = 0
    n_inj = 0

    # Ensure core is available for the injection tests
    _sys.path.insert(0, str(REPO_ROOT / "flybrain-connectome-mcp"))
    import core_bridge

    if not core_bridge.core_available():
        print("    [SKIP] core not available; cannot run injection tests")
        return 0, 0

    import module_combinator as stub

    real_list_rules = stub.list_rules
    real_validate = stub.validate_combination
    real_expand = stub.expand_organism
    real_audit = stub.audit_rules_against_data

    def expect(name, apply_fn, restore_fn):
        nonlocal bad, n_inj
        n_inj += 1
        apply_fn()
        try:
            try:
                rc = main()
            except AssertionError as e:
                rc = 1
        finally:
            restore_fn()
        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    # 1. Rule count drifts (wrong number of combination rules).
    def _inj_bad_rule_count():
        def _patched():
            result = real_list_rules()
            result["combination_rules"] = result["combination_rules"][:-3]
            return result
        stub.list_rules = _patched

    expect("rule count drifts (wrong number of combination rules)",
           _inj_bad_rule_count,
           lambda: setattr(stub, "list_rules", real_list_rules))

    # 2. Validation returns incompatible (engine rejects valid combos).
    def _inj_bad_validation():
        def _patched(combos):
            return {"compatible": False, "reason": "injected failure"}
        stub.validate_combination = _patched

    expect("validation returns incompatible (engine rejects valid combos)",
           _inj_bad_validation,
           lambda: setattr(stub, "validate_combination", real_validate))

    # 3. Expand returns wrong copy count.
    def _inj_bad_expand():
        def _patched(modules):
            return {"total_copies": 99, "modules": []}
        stub.expand_organism = _patched

    expect("expand returns wrong copy count",
           _inj_bad_expand,
           lambda: setattr(stub, "expand_organism", real_expand))

    # 4. Audit fails (wrong rule coverage).
    def _inj_bad_audit():
        def _patched():
            return {"audit": []}
        stub.audit_rules_against_data = _patched

    expect("audit fails (wrong rule coverage)",
           _inj_bad_audit,
           lambda: setattr(stub, "audit_rules_against_data", real_audit))

    # State must be byte-clean after the battery.
    assert stub.list_rules is real_list_rules, "injections leaked list_rules"
    assert stub.validate_combination is real_validate, "injections leaked validate_combination"

    return bad, n_inj


def _run_with_injections() -> int:
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if n_inj == 0:
        print("    (skipped: core not available)")
        return rc
    if inj_bad:
        print(f"GATE 24: FAIL -- {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


if __name__ == "__main__":
    sys.exit(_run_with_injections())
