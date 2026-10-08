#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T5 -- build the 116x116 port-compatibility matrix and repair suggestions.

Reads functional_units.json directly (stdlib only, no model import) and, for
every ordered pair (A -> B), decides whether A's *output* port types can meet
B's *input* port types.  This is the interface-level question that the
combination builder asks before turning a `composable_with` declaration into an
edge (see functional_units.py:_composable).

Outputs
-------
  docs/compatibility_matrix.json   full matrix + per-edge shared types
  composition_exceptions.json      every declared-but-incompatible pair,
                                    registered with a concrete fix suggestion
                                    (so the debt is explicit, not silent)

The companion gate (scripts/check_composition_closure.py = GATE 17) fails
closed if any declared-incompatible, unreciprocated pair is NOT in
composition_exceptions.json -- i.e. you may not add a broken declaration
without registering it.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
UNITS = MCP / "functional_units" / "functional_units.json"
MATRIX = ROOT / "docs" / "compatibility_matrix.json"
EXC = ROOT / "composition_exceptions.json"


def _types(unit: dict, direction: str) -> set[str]:
    ports = unit.get("ports") or {}
    return {p.get("type", "") for p in (ports.get(direction) or []) if p.get("type")}


def main() -> int:
    doc = json.loads(UNITS.read_text(encoding="utf-8"))
    units = doc["units"] if isinstance(doc, dict) else doc
    by_name = {u["name"]: u for u in units}
    names = [u["name"] for u in units]

    out_t = {n: _types(u, "out") for n, u in by_name.items()}
    in_t = {n: _types(u, "in") for n, u in by_name.items()}

    matrix: dict[str, dict] = {}
    total_compat = 0
    for a in names:
        matrix[a] = {}
        for b in names:
            if a == b:
                matrix[a][b] = {"intf": False, "shared": []}
                continue
            shared = sorted(out_t[a] & in_t[b])
            matrix[a][b] = {"intf": bool(shared), "shared": shared}
            if shared:
                total_compat += 1

    # ---- declared-but-incompatible pairs ----
    exceptions: list[dict] = []
    declared_total = 0
    broken = 0
    for a in units:
        an = a["name"]
        for b in (a.get("composable_with") or []):
            if b not in by_name:
                continue
            declared_total += 1
            intf = matrix[an][b]["intf"]
            recip = an in (by_name[b].get("composable_with") or [])
            if intf or recip:
                continue  # consistent or meets ports -> no debt
            broken += 1
            cand = sorted(out_t[an] - in_t[b])  # types A offers that B lacks
            suggestions = []
            if cand:
                suggestions.append(
                    "add an `in` port of type %s to %s (A already exposes it)"
                    % (cand[0], b))
            bt = sorted(out_t[b] - in_t[an])
            if bt:
                suggestions.append(
                    "or add an `out` port of type %s to %s" % (bt[0], an))
            if not suggestions:
                suggestions.append("neither side exposes a meetable port type; "
                                   "redesign the interface")
            exceptions.append({
                "from": an, "to": b,
                "from_out": sorted(out_t[an]), "to_in": sorted(in_t[b]),
                "reciprocated": recip,
                "shared_types": [],
                "suggested_fix": suggestions[0],
            })

    MATRIX.parent.mkdir(parents=True, exist_ok=True)
    MATRIX.write_text(json.dumps({
        "schema_version": "1.0",
        "n_units": len(names),
        "interface_compatible_pairs": total_compat,
        "declared_total": declared_total,
        "declared_incompatible": broken,
        "matrix": matrix,
    }, indent=1, ensure_ascii=False), encoding="utf-8")

    EXC.write_text(json.dumps({
        "schema_version": "1.0",
        "policy": ("Every declared composable_with pair that is interface-"
                   "incompatible AND not reciprocated MUST be listed here with a "
                   "suggested fix, or the build fails (GATE 17). Remove an entry "
                   "only after the declaration is fixed in functional_units.json."),
        "count": len(exceptions),
        "exceptions": exceptions,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print("compatibility matrix: %d units, %d interface-compatible ordered pairs"
          % (len(names), total_compat))
    print("declared composable_with: %d | interface-incompatible & unreciprocated: %d"
          % (declared_total, broken))
    print("  -> registered in composition_exceptions.json (GATE 17 will enforce)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
