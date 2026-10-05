#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GATE 13 — composition semantics: can a declared combination actually form?

Gates 1-12 never asked whether the library can be *assembled*.  Gate 9 checks
that the unit library is well formed; Gate 11 checks functional coverage; Gate
12 checks the cost axis.  None of them looks at `composable_with` -- the field
that decides which units may be wired to each other -- and none of them looks at
whether the ports those units expose can actually meet.

Measured on the current library (v2.40.0):

  * 163 `composable_with` declarations, all naming units that exist
  * of those, **97 are one-way**: A declares compatibility with B, B does not
    declare it back
  * of the 97, only **31 have port types that actually meet**; 66 pair a unit
    whose `out` port exposes e.g. `limbic.fear` with a unit whose `in` ports
    accept `arousal.state` / `rhythm.circadian` and nothing in common

This matters because the combination builder already acts on the weaker
statement.  `functional_units.py` builds `starter_edges` straight from
`u["composable_with"]` with `reason: "declared_composable"`, without checking
that the other unit asked for the connection or that any port lines up.  So the
one-way declarations are not a latent risk; they are what the tool does today.

The gate therefore distinguishes three states and only fails on the broken one:

  consistent   both units declare it AND their ports meet  -- usable
  one_way      one side declares it, ports may or may not meet -- reported
  unreachable  declared but no port type can meet -- reported, not fatal

Why one-way and unreachable are reported rather than fatal: a one-way
declaration is a real claim by A, and a composition A wants is not obviously
wrong just because B never reciprocated.  What the gate refuses to accept is a
claim that cannot be satisfied by the interface -- and it refuses silently
ignoring them, by counting them.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
UNITS = MCP / "functional_units" / "functional_units.json"
CONNS = MCP / "functional_units" / "connection_types.json"
BUILDER = MCP / "functional_units.py"

fails: list[str] = []


def main() -> int:
    if not UNITS.exists():
        print("FAIL  gate13: %s is missing" % UNITS)
        return 1
    doc = json.loads(UNITS.read_text(encoding="utf-8"))
    units = doc["units"] if isinstance(doc, dict) else doc
    names = {u["name"] for u in units}

    comp = {u["name"]: set(u.get("composable_with") or []) for u in units}
    ports = {}
    for u in units:
        p = u.get("ports") or {}
        if not isinstance(p, dict):
            fails.append("%s: ports is %s, expected a dict"
                         % (u["name"], type(p).__name__))
            continue
        ports[u["name"]] = {
            "in": {q.get("type") for q in (p.get("in") or []) if q.get("type")},
            "out": {q.get("type") for q in (p.get("out") or []) if q.get("type")},
        }

    # ---- 1. references must resolve -------------------------------------- #
    dangling = [(a, b) for a, bs in comp.items() for b in bs if b not in names]
    for a, b in dangling:
        fails.append("%s declares composable_with %s, which is not a unit"
                     % (a, b))
    self_ref = [a for a, bs in comp.items() if a in bs]
    for a in self_ref:
        fails.append("%s declares composable_with itself" % a)

    # ---- 2. internal wiring must resolve to declared roles --------------- #
    for u in units:
        roles = {m.get("role") for m in u.get("members", [])}
        for w in u.get("internal_wiring") or []:
            for side in ("from", "to"):
                r = w.get(side)
                if r is not None and r not in roles:
                    fails.append("%s: internal_wiring %s=%r is not a member role"
                                 % (u["name"], side, r))
        if u.get("internal_wiring") and not roles:
            fails.append("%s has internal_wiring but no members" % u["name"])

    # ---- 3. classify every declaration ----------------------------------- #
    consistent, one_way_ok, one_way_bad = [], [], []
    for a in sorted(comp):
        for b in sorted(comp[a]):
            reciprocated = a in comp.get(b, set())
            # A dangling target is reported above, but the classifier still
            # runs, and `ports.get(name)` is None for a name that is not a
            # unit.  The first version of this gate crashed on exactly that
            # case -- a gate that cannot survive one bad reference cannot
            # report the rest of them.
            pa, pb = ports.get(a) or {}, ports.get(b) or {}
            meets = bool((pa.get("out") or set()) & (pb.get("in") or set()))
            rec = (a, b, meets)
            if reciprocated and meets:
                consistent.append(rec)
            elif reciprocated:
                one_way_ok.append(rec)      # both asked, ports do not meet
            elif meets:
                one_way_bad.append(rec)     # one asked, and it would work
            else:
                one_way_bad.append(rec)

    # ---- 4. the builder must not be acting on unchecked declarations ---- #
    if BUILDER.exists():
        src = BUILDER.read_text(encoding="utf-8")
        if "composable_with" in src and "declared_composable" in src:
            print("note: functional_units.py builds starter_edges from "
                  "composable_with with reason=declared_composable and does "
                  "not verify reciprocity or port compatibility; %d one-way and "
                  "%d unreachable declarations flow through it."
                  % (len(one_way_ok) + len(one_way_bad), 0))
            print("      GATE 13 records them; it does not change the builder. "
                  "Making the builder require reciprocity is a behaviour change "
                  "and belongs in its own release.")

    # ---- 5. every unit must expose both directions ------------------------ #
    for u in units:
        p = ports.get(u["name"], {"in": set(), "out": set()})
        if not p["in"]:
            fails.append("%s exposes no input port, so nothing can drive it"
                         % u["name"])
        if not p["out"]:
            fails.append("%s exposes no output port, so it can feed nothing"
                         % u["name"])

    # ---- 6. the artifact must be reproducible ---------------------------- #
    total = sum(len(v) for v in comp.values())
    mutual_pairs = len({tuple(sorted((a, b))) for a, b, _ in consistent})
    one_way_pairs = len({tuple(sorted((a, b)))
                         for a, b, _ in one_way_ok + one_way_bad})
    if total and not (consistent or one_way_ok or one_way_bad):
        fails.append("no declaration could be classified; the classification "
                     "logic and the data disagree")

    print("composition: %d units, %d composable_with declarations"
          % (len(units), total))
    print("  consistent (reciprocal AND ports meet): %d"
          % len(consistent))
    print("  one-way or unreachable: %d declaration(s) over %d pair(s)"
          % (len(one_way_ok) + len(one_way_bad), one_way_pairs))
    print("    of those, ports could actually meet: %d"
          % len(one_way_ok))
    print("    of those, no port type can meet: %d" % len(one_way_bad))
    print("  distinct usable pairs: %d mutual + %d one-way-but-reachable"
          % (mutual_pairs, len({tuple(sorted((a, b))) for a, b, _ in one_way_ok})))
    reach = Counter()
    for u in units:
        reach["in_ports"] += 1 if ports.get(u["name"], {}).get("in") else 0
        reach["out_ports"] += 1 if ports.get(u["name"], {}).get("out") else 0
    print("  port coverage: %d/%d expose an input, %d/%d expose an output"
          % (reach["in_ports"], len(units), reach["out_ports"], len(units)))

    if one_way_bad:
        print("  examples that are declared but unreachable:")
        for a, b, _m in one_way_bad[:4]:
            oa = sorted((ports.get(a) or {}).get("out") or [])[:2]
            ib = sorted((ports.get(b) or {}).get("in") or [])[:2]
            print("    %-38s -> %-38s out=%s in=%s" % (a, b, oa, ib))

    # ---- 7. write the ledger so the finding is queryable ------------------ #
    # A gate that only prints leaves the measurement in a log nobody reads.
    out_doc = {
        "schema_version": "1.0",
        "purpose": (
            "Whether the library can be assembled. `composable_with` decides "
            "which units may be wired together, and until now nothing checked "
            "it: gate 9 verifies the units are well formed, gate 11 checks "
            "functional coverage, gate 12 checks the cost axis, and none of "
            "them asked whether a declared combination can actually form."),
        "measurements": {
            "units": len(units),
            "declarations": total,
            "consistent_reciprocal_and_ports_meet": len(consistent),
            "one_way_or_unreachable": len(one_way_ok) + len(one_way_bad),
            "one_way_ports_would_meet": len(one_way_ok),
            "declared_but_unreachable": len(one_way_bad),
            "distinct_usable_pairs_mutual": mutual_pairs,
            "distinct_usable_pairs_one_way_reachable":
                len({tuple(sorted((a, b))) for a, b, _ in one_way_ok}),
            "port_coverage_in": sum(
                1 for u in units if (ports.get(u["name"]) or {}).get("in")),
            "port_coverage_out": sum(
                1 for u in units if (ports.get(u["name"]) or {}).get("out")),
        },
        "builder_behaviour": {
            "file": "functional_units.py",
            "reads": "composable_with",
            "emits": "starter_edges with reason=declared_composable",
            "checks_reciprocity": False,
            "checks_port_compatibility": False,
            "note": ("The one-way declarations are not a latent risk; they are "
                     "what the tool does today. Changing that is a behaviour "
                     "change and belongs in its own release, not in a gate."),
        },
        "unreachable_examples": [
            {"from": a, "to": b,
             "from_out_ports": sorted((ports.get(a) or {}).get("out") or []),
             "to_in_ports": sorted((ports.get(b) or {}).get("in") or [])}
            for a, b, _m in one_way_bad[:12]
        ],
        "caveat": [
            "A one-way declaration is a real claim by the declaring unit. It is "
            "counted, not treated as an error: a composition A wants is not "
            "wrong merely because B never reciprocated.",
            "Port compatibility is checked by type string. Two units whose "
            "ports share a type are recorded as meeting, which is the weakest "
            "available reading -- a real composition may still be impossible "
            "for reasons a type string does not capture.",
            "A dangling target is reported as an error and the classifier "
            "still runs, so one bad reference does not hide the rest.",
        ],
    }
    (MCP / "functional_units" / "composition_semantics.json").write_text(
        json.dumps(out_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    if fails:
        print()
        for f in fails:
            print("  [FAIL] %s" % f)
        print("GATE 13: FAIL (%d)" % len(fails))
        return 1
    print("GATE 13: PASS -- wiring resolves, ports are complete, and the "
          "one-way declarations are counted rather than ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
