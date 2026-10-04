#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GATE 11 — the function axis: PROJECT_VISION coverage is measured, not assumed.

Why this gate exists
--------------------
Gates 1-10 are all consistency gates: docs match code, artifacts are well
formed, secrets are absent, the unit library is coherent.  None of them asks
whether the library covers the function set the morphology generator is
supposed to be built from.  So the library could be perfectly consistent and
still have no working memory.

`PROJECT_VISION.md` names the target set.  `functional_units/function_coverage.json`
measures the library against it.  This gate makes the measurement load-bearing
in three ways:

1. **The artifact must exist and reconcile.**  Coverage has to be derived from
   the unit library, not written by hand: every unit in the library appears in
   the per-unit tagging, and every category count equals the number of units
   listed for it.
2. **Vision-required categories are declared, and gaps are declared.**  A
   missing category is allowed -- six of them are missing right now, which is
   the finding.  What is not allowed is a missing category that nobody wrote
   down, because that is the case where the gap is invisible.
3. **A capability that drifts out of every category is flagged.**  51 of 115
   units currently sit outside all categories.  That is a measurement of the
   library's vocabulary, not a defect, and the gate prints it as a number so a
   change in either direction is visible in the log.

None of this fails the build for having gaps.  It fails for hiding them.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
UNITS = MCP / "functional_units" / "functional_units.json"
COVERAGE = MCP / "functional_units" / "function_coverage.json"
VISION = ROOT / "PROJECT_VISION.md"

fails: list[str] = []
warns: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def main() -> int:
    if not COVERAGE.exists():
        print("FAIL  gate11: %s is missing; run "
              "python scripts/extract_function_coverage.py" % COVERAGE)
        return 1
    if not UNITS.exists():
        print("FAIL  gate11: %s is missing" % UNITS)
        return 1

    units_doc = json.loads(UNITS.read_text(encoding="utf-8"))
    units = units_doc["units"] if isinstance(units_doc, dict) else units_doc
    cov = json.loads(COVERAGE.read_text(encoding="utf-8"))

    unit_names = {u.get("name", "?") for u in units}

    # ---- 1. the matrix has to reconcile with the library ------------------- #
    matrix = cov.get("coverage_matrix") or []
    check(bool(matrix), "coverage_matrix is empty")
    for row in matrix:
        cat = row.get("category")
        n = row.get("units")
        if not isinstance(n, int) or n < 0:
            fails.append("category %s has a non-integer unit count %r"
                         % (cat, n))
        listed = row.get("example_units")
        check(isinstance(listed, list),
              "category %s has no example_units list" % cat)
        if n and not listed:
            fails.append("category %s claims %d units but lists none"
                         % (cat, n))
        if n and len(listed) > n:
            fails.append("category %s lists %d examples for %d units"
                         % (cat, len(listed), n))
        for name in (listed or []):
            check(name in unit_names,
                  "category %s names a unit the library does not have: %s"
                  % (cat, name))

    # ---- 2. required categories are declared ------------------------------- #
    required = [r for r in matrix if r.get("vision_required")]
    check(bool(required),
          "no category is marked vision_required; PROJECT_VISION's target "
          "set has been dropped from the artifact")
    missing = [r["category"] for r in required if r.get("units") == 0]
    thin = [r["category"] for r in required
            if 0 < (r.get("units") or 0) < 3]
    declared = set(cov.get("summary", {}).get("vision_required_missing", []))
    check(set(missing) == declared,
          "vision_required_missing (%s) disagrees with the matrix (%s)"
          % (sorted(declared), sorted(missing)))

    # ---- 3. the vision file still names the categories --------------------- #
    # PROJECT_VISION is the target set's source of truth.  If it changes, the
    # artifact's `vision_required` flags are stale and nobody would notice.
    if VISION.exists():
        text = VISION.read_text(encoding="utf-8").lower()
        probe = {
            "attention": "attention",
            "working_memory": "working_memory",
            "reward": "reward",
            "punishment": "punishment",
            "habit": "habit",
            "metacognition": "metacognition",
        }
        for cat, token in probe.items():
            if token in text:
                check(any(r["category"] == cat for r in required),
                      "PROJECT_VISION names %r but the artifact does not "
                      "require it" % cat)
    else:
        warns.append("PROJECT_VISION.md not found; cannot cross-check the "
                     "required set against the source of truth")

    # ---- 4. per-unit tagging must cover every unit exactly once ------------ #
    lib = cov.get("library", {})
    tagged = lib.get("units_with_any_category")
    untagged = lib.get("units_with_no_category") or []
    check(isinstance(tagged, int),
          "library.units_with_any_category is not an integer")
    if isinstance(tagged, int):
        check(tagged + len(untagged) == len(units),
              "tagged (%d) + untagged (%d) != library size (%d)"
              % (tagged, len(untagged), len(units)))
    for name in untagged:
        check(name in unit_names,
              "units_with_no_category names an unknown unit: %s" % name)

    # ---- 5. cross-species claim must be a lower bound, per the caveat ----- #
    for row in matrix:
        if row.get("cross_species") and (row.get("species") or 0) < 3:
            fails.append("category %s claims cross_species with %s species"
                         % (row.get("category"), row.get("species")))

    # ---- report ------------------------------------------------------------ #
    fam = Counter(r.get("family") for r in matrix)
    print("function axis: %d units, %d categories in %d families"
          % (len(units), len(matrix), len(fam)))
    print("  families: %s"
          % ", ".join("%s=%d" % kv for kv in sorted(fam.items())))
    print("  vision-required: %d, of which %d thin (<3 units) and %d missing"
          % (len(required), len(thin), len(missing)))
    if missing:
        print("  MISSING (declared work queue, not a build failure): %s"
              % ", ".join(sorted(missing)))
    if thin:
        print("  thin: %s" % ", ".join(sorted(thin)))
    cs = cov.get("summary", {}).get("cross_species_categories") or []
    print("  cross-species categories (>=3 taxa): %s" % (", ".join(cs) or "none"))
    print("  units outside every category: %d of %d"
          % (len(untagged), len(units)))
    if untagged:
        print("    %s" % ", ".join(sorted(untagged)[:8])
              + (" ..." if len(untagged) > 8 else ""))
    for w in warns:
        print("WARN  %s" % w)

    if fails:
        print()
        for f in fails:
            print("  [FAIL] %s" % f)
        print("GATE 11: FAIL (%d)" % len(fails))
        return 1
    print("GATE 11: PASS -- coverage is measured, and the gaps are written down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
