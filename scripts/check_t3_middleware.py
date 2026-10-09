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

    print("GATE 24 — PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
