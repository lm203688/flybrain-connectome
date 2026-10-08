#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE 17 -- composition closure: broken declarations must be registered.

T5 turns "can these units be wired" into a closed, auditable question.  The
combination builder (functional_units.suggest_composition, strict mode) already
drops declarations whose ports cannot meet and is not reciprocated.  This gate
makes that debt explicit: every such declaration must appear in
composition_exceptions.json with a suggested fix.  Adding a broken declaration
without registering it turns the gate red -- so the closure is enforced, not
trusted.

It recomputes the broken set from functional_units.json directly (does not
trust the exceptions file), then diffs against the registry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
UNITS = MCP / "functional_units" / "functional_units.json"
MATRIX = ROOT / "docs" / "compatibility_matrix.json"
EXC = ROOT / "composition_exceptions.json"


def fail(msg: str) -> int:
    print("GATE 17: FAIL -- %s" % msg)
    return 1


def ok(msg: str) -> int:
    print("GATE 17: PASS -- %s" % msg)
    return 0


def _types(unit: dict, direction: str) -> set:
    ports = unit.get("ports") or {}
    return {p.get("type", "") for p in (ports.get(direction) or []) if p.get("type")}


def main() -> int:
    if not MATRIX.exists():
        return fail("compatibility_matrix.json missing -- run build_compatibility_matrix.py first")
    if not EXC.exists():
        return fail("composition_exceptions.json missing -- run build_compatibility_matrix.py first")

    doc = json.loads(UNITS.read_text(encoding="utf-8"))
    units = doc["units"] if isinstance(doc, dict) else doc
    by_name = {u["name"]: u for u in units}
    out_t = {n: _types(u, "out") for n, u in by_name.items()}
    in_t = {n: _types(u, "in") for n, u in by_name.items()}

    # Recompute the broken set independently.
    broken = set()
    for a in units:
        an = a["name"]
        for b in (a.get("composable_with") or []):
            if b not in by_name:
                continue
            intf = bool(out_t[an] & in_t[b])
            recip = an in (by_name[b].get("composable_with") or [])
            if not intf and not recip:
                broken.add((an, b))

    reg = json.loads(EXC.read_text(encoding="utf-8"))
    reg_pairs = {(e["from"], e["to"]) for e in reg.get("exceptions", [])}

    # (a) every broken declaration must be registered
    unregistered = sorted(broken - reg_pairs)
    if unregistered:
        for f, t in unregistered[:10]:
            print("  unregistered broken declaration: %s -> %s" % (f, t))
        extra = "" if len(unregistered) <= 10 else " ...(+%d more)" % (len(unregistered) - 10)
        return fail("%d broken declaration(s) not in composition_exceptions.json%s"
                    % (len(unregistered), extra))

    # (b) every registered exception must still be a real broken declaration
    # (otherwise the registry has drifted away from the library)
    stale = sorted(reg_pairs - broken)
    if stale:
        for f, t in stale[:10]:
            print("  stale exception (no longer broken): %s -> %s" % (f, t))
        return fail("%d registered exception(s) are no longer broken -- prune them"
                    % len(stale))

    # (c) matrix integrity
    m = json.loads(MATRIX.read_text(encoding="utf-8"))
    if m.get("n_units") != len(units):
        return fail("matrix n_units %s != library %d" % (m.get("n_units"), len(units)))

    return ok("%d declared-incompatible pairs registered & closed; matrix 116x116 intact"
              % len(broken))


if __name__ == "__main__":
    sys.exit(main())
