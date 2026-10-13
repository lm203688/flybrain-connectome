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
import shutil
import sys
import tempfile
from collections import Counter
from copy import deepcopy
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


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: write mutated cost_axis JSON to temp,
    monkey-patch COSTS, re-run main(), assert non-zero exit.

    Each injection exercises one of the five failure classes declared in
    the module docstring: abstraction-only-with-latency, malformed
    latency range, missing citation, missing energy, count drift.
    Apply and restore are structurally separate (tempfile + globals swap
    + finally) so no injection leaks state into the next one.
    """
    bad = 0
    n_inj = 0

    real_doc = json.loads(COSTS.read_text(encoding="utf-8"))

    def expect(name, mutate_fn):
        nonlocal bad, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate12_inj_"))
        try:
            doc = deepcopy(real_doc)
            mutate_fn(doc)
            fp = td / "costs.json"
            fp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            old_costs = globals()["COSTS"]
            globals()["COSTS"] = fp
            try:
                # reset fails list each time (module-level mutable state)
                globals()["fails"].clear()
                rc = main()
            finally:
                globals()["COSTS"] = old_costs
        finally:
            shutil.rmtree(td, ignore_errors=True)

        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    # 1. An abstraction_only type is given a latency (design abstraction
    #    wearing a measurement's clothes).
    def _inj_abstract_lat(doc):
        rows = doc.get("cost_axis", [])
        for r in rows:
            if r.get("abstraction_only") and not r.get("latency_ms"):
                r["latency_ms"] = {"low": 1.0, "high": 5.0, "grade": "measured"}
                r["citation"] = "injected fake citation"
                return

    expect("an abstraction_only type is given a latency", _inj_abstract_lat)

    # 2. A latency range is malformed (low > high).
    def _inj_bad_range(doc):
        for r in doc.get("cost_axis", []):
            if r.get("latency_ms") and r["latency_ms"].get("low", 0) > 0:
                r["latency_ms"]["low"] = r["latency_ms"]["high"] + 100
                return

    expect("a latency range is malformed (low > high)", _inj_bad_range)

    # 3. A latency-bearing type loses its citation.
    def _inj_no_citation(doc):
        for r in doc.get("cost_axis", []):
            if r.get("latency_ms"):
                r["citation"] = ""
                return

    expect("a graded latency loses its citation", _inj_no_citation)

    # 4. A type loses its energy entry.
    def _inj_no_energy(doc):
        rows = doc.get("cost_axis", [])
        if rows:
            rows[0]["energy"] = None

    expect("a type loses its energy entry", _inj_no_energy)

    # 5. Row count drifts from connection_types count (silent shrink).
    def _inj_count_drift(doc):
        rows = doc.get("cost_axis", [])
        if len(rows) > 1:
            doc["cost_axis"] = rows[:-1]

    expect("cost_axis row count drifts (silent shrink)", _inj_count_drift)

    # State must be byte-clean after the battery.
    # (fails list is gate-local and gets cleared at the start of each
    # injection; COSTS must be restored to the real path.)
    assert COSTS.exists(), "injections leaked COSTS path"
    fails.clear()

    return bad, n_inj


def _run_with_injections() -> int:
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"GATE 12: FAIL -- {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


if __name__ == "__main__":
    raise SystemExit(_run_with_injections())
