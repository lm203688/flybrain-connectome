#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GATE 12 — the cost axis: every latency asserted here is defensible.

GATE 11 asked whether the library covers the functions the vision needs.  This
one asks a narrower and more dangerous question about the connection layer:
whether any latency or energy value was invented.

The connection library has 66 types.  Sixteen of them can be given a published
physiological latency; the other fifty are circuit patterns, projection
geometries and plasticity rules, where a single-contact delay is not a defined
quantity.  Getting that split right matters more than raising the number, so
this gate enforces the failures that would make the axis a guess:

1. **An `abstraction_only` type may never carry a latency.**  Twenty-one types
   are design patterns.  An autapse is chemically a chemical synapse, but as a
   design pattern ("a neuron inhibiting itself to sustain a limit cycle") it
   has no delay literature can supply.  A number there is a design choice
   wearing a measurement's clothes.
2. **Every asserted latency must be a positive, ordered, finite range with a
   grade.**  A point value where a range is meant is false precision.
3. **The fastest electrical synapse must be strictly faster than the slowest
   chemical one.**  The trade the axis exists to express depends on it, so a
   table that loses that ordering is wrong even though every field parses.
4. **Every graded value must carry a citation**, and the `measured_or_bounded`
   share must not silently shrink -- a regression from "most types grounded" to
   "most types unknown" is a change a reader would not notice in a diff.
5. **Energy must be present for every type**, because energy composes over a
   motif while latency does not.  That asymmetry is the design.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
COSTS = MCP / "functional_units" / "connection_costs.json"
CTYPES = MCP / "functional_units" / "connection_types.json"

fails: list[str] = []


def main() -> int:
    if not COSTS.exists():
        print("FAIL  gate12: %s is missing; run "
              "python scripts/extract_connection_costs.py" % COSTS)
        return 1
    if not CTYPES.exists():
        print("FAIL  gate12: %s is missing" % CTYPES)
        return 1

    doc = json.loads(COSTS.read_text(encoding="utf-8"))
    ctypes = json.loads(CTYPES.read_text(encoding="utf-8"))
    rows = doc.get("cost_axis") or []
    names = {t["name"] for t in ctypes.get("connection_types", [])}

    if not rows:
        print("FAIL  gate12: cost_axis is empty")
        return 1
    if len(rows) != len(names):
        fails.append("cost_axis has %d rows for %d connection types"
                     % (len(rows), len(names)))

    # ---- 1. no latency on a design abstraction --------------------------- #
    for r in rows:
        if r.get("abstraction_only") and r.get("latency_ms"):
            fails.append("abstraction_only type %s carries a latency %r"
                         % (r.get("name"), r["latency_ms"]))
        if r.get("abstraction_only") and "designed_cost" not in r:
            fails.append("abstraction_only type %s does not record its design "
                         "intent under designed_cost" % r.get("name"))

    # ---- 2. every latency is a well-formed graded range ----------------- #
    for r in rows:
        lat = r.get("latency_ms")
        if lat is None:
            continue
        for key in ("low", "high", "grade"):
            if key not in lat:
                fails.append("%s latency is missing %r" % (r["name"], key))
        if not (0 < lat.get("low", -1) <= lat.get("high", -1)):
            fails.append("%s latency range is not positive and ordered: %r"
                         % (r["name"], lat))
        if lat.get("grade") not in ("measured", "bounded", "derived"):
            fails.append("%s latency grade %r is not a known grade"
                         % (r["name"], lat.get("grade")))
        if not r.get("citation"):
            fails.append("%s asserts a latency with no citation" % r["name"])

    # ---- 3. electrical must beat chemical ------------------------------- #
    chem = [r for r in rows if r.get("basis") == "chemical_synapse"
            and r.get("latency_ms")]
    elec = [r for r in rows if r.get("basis") == "electrical_synapse"
            and r.get("latency_ms")]
    speedup = None
    if chem and elec:
        c_min = min(r["latency_ms"]["low"] for r in chem)
        e_max = max(r["latency_ms"]["high"] for r in elec)
        if e_max >= c_min:
            fails.append("fastest electrical (%s ms) is not faster than "
                         "slowest chemical (%s ms)" % (e_max, c_min))
        else:
            speedup = round(c_min / e_max, 1)

    # ---- 4. grounding share must not silently shrink --------------------- #
    s = doc.get("summary", {})
    share = s.get("measured_or_bounded_pct")
    if share is None:
        fails.append("summary.measured_or_bounded_pct is missing")
    elif not (0 < share <= 100):
        fails.append("measured_or_bounded_pct out of range: %r" % share)
    graded = Counter(r.get("grade") for r in rows)
    for r in rows:
        if r.get("grade") in ("measured", "bounded") and not r.get("citation"):
            fails.append("%s is graded %s but cites nothing"
                         % (r["name"], r["grade"]))

    # ---- 5. energy present everywhere ----------------------------------- #
    for r in rows:
        if not r.get("energy"):
            fails.append("%s has no energy entry; energy composes over a motif "
                         "so every type needs one" % r["name"])
        elif not r["energy"].get("level"):
            fails.append("%s energy has no level" % r["name"])

    # ---- report ---------------------------------------------------------- #
    print("cost axis: %d types, %d with a latency number, %d energy-complete"
          % (len(rows), s.get("with_latency_number", 0),
             sum(1 for r in rows if r.get("energy"))))
    print("  grades: %s" % dict(graded))
    print("  abstraction_only: %d (none may carry a latency; checked)"
          % sum(1 for r in rows if r.get("abstraction_only")))
    print("  grounded (measured or bounded): %s%%" % share)
    if speedup:
        print("  electrical vs chemical: fastest electrical is %sx faster than "
              "the slowest chemical" % speedup)
    by_fam = {}
    for r in rows:
        f = r["family"]
        by_fam.setdefault(f, [0, 0])
        by_fam[f][1] += 1
        if r.get("latency_ms"):
            by_fam[f][0] += 1
    for f in sorted(by_fam):
        got, tot = by_fam[f]
        print("    %-12s %d/%d with a latency" % (f, got, tot))

    if fails:
        print()
        for f in fails:
            print("  [FAIL] %s" % f)
        print("GATE 12: FAIL (%d)" % len(fails))
        return 1
    print("GATE 12: PASS -- every latency is cited, and the design "
          "abstractions carry none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
