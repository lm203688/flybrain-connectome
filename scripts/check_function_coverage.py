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
import shutil
import sys
import tempfile
from collections import Counter
from copy import deepcopy
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

    # ---- 3b. the taxon split must be stated, and must match the matrix ---- #
    # `covered` counts units, so a category carried by one taxon reads as
    # covered even though it is a single implementation.  The cross-taxon
    # split is the honest measure of whether the library generalises, and at
    # v2.41.0 only ONE of fifteen required categories is carried by three or
    # more taxa.  Recording that is the point; the gate requires it to be
    # derived rather than asserted, and it must not silently improve.
    s_ = cov.get("summary", {})
    single = s_.get("vision_required_single_taxon")
    multi = s_.get("vision_required_three_plus_taxa")
    if single is None or multi is None:
        fails.append("summary does not report the taxon split; a category with "
                     "one taxon must not read as covered without saying so")
    else:
        derived_single = {r["category"] for r in required
                          if (r.get("species") or 0) < 3}
        derived_multi = {r["category"] for r in required
                         if (r.get("species") or 0) >= 3}
        check(set(single) == derived_single,
              "vision_required_single_taxon (%d) disagrees with the matrix (%d)"
              % (len(single), len(derived_single)))
        check(set(multi) == derived_multi,
              "vision_required_three_plus_taxa (%d) disagrees with the matrix "
              "(%d)" % (len(multi), len(derived_multi)))
        check(not (set(single) & set(multi)),
              "a category is reported as both single-taxon and 3+-taxon")
        print("  taxon breadth: %d of %d required categories span 3+ taxa; "
              "%d are single-taxon implementations"
              % (len(multi), len(required), len(single)))
        if single:
            print("    single-taxon: %s" % ", ".join(sorted(single)))

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

    # ---- 6. every tag must be traceable to a firing token --------------- #
    # v2.42.0.  This is the difference between a coverage matrix and a
    # coincidence report.  Three releases ago a keyword match manufactured a
    # fully "covered" matrix twice -- `encode` inside `high_res_encode`, then
    # `meta` inside `metabolic_support` -- and both looked correct to anyone
    # reading the summary numbers.  The matrix carries the exact
    # `cap <- token` pair that earned each tag, so the gate can re-derive the
    # match from the unit's own fields instead of trusting it.
    caps_by_unit: dict[str, set] = {}
    for u in units:
        n = u.get("name", "?")
        caps = set()
        for f in ("capability", "task_hint_pool"):
            v = u.get(f)
            if isinstance(v, list):
                caps |= {str(x) for x in v}
            elif isinstance(v, str):
                caps.add(v)
        caps_by_unit[n] = caps

    def token_hits(cap: str, tok: str) -> bool:
        return (cap == tok or cap.startswith(tok + "_")
                or cap.endswith("_" + tok) or ("_" + tok + "_") in cap)

    total_pairs = 0
    no_evidence = 0
    for row in matrix:
        cat = row.get("category")
        listed = row.get("units_listed")
        # units_listed is the full list; example_units is a truncated preview.
        check(isinstance(listed, list),
              "category %s has no units_listed" % cat)
        if isinstance(listed, list):
            check(len(listed) == (row.get("units") or 0),
                  "category %s: units_listed has %d entries against a unit "
                  "count of %s" % (cat, len(listed), row.get("units")))
            for name in listed:
                check(name in unit_names,
                      "category %s lists an unknown unit: %s" % (cat, name))
        ev = row.get("match_evidence")
        check(isinstance(ev, dict),
              "category %s has no match_evidence; a tag nobody can trace is "
              "not a tag" % cat)
        if not isinstance(ev, dict):
            continue
        claimed = row.get("evidence_units")
        if claimed is None:
            fails.append("category %s has no evidence_units count" % cat)
            continue
        if row.get("units") and claimed != row["units"]:
            fails.append("category %s lists %d units but only %d carry a "
                         "recorded firing token"
                         % (cat, row["units"], claimed))
        if (row.get("units") or 0) != len(ev):
            fails.append("category %s: %d units but %d evidence entries"
                         % (cat, row.get("units") or 0, len(ev)))
        for name, pairs in ev.items():
            if not isinstance(pairs, list) or not pairs:
                no_evidence += 1
                fails.append("category %s / unit %s has no firing token; "
                             "its tag cannot be reproduced" % (cat, name))
                continue
            for pair in pairs:
                total_pairs += 1
                if not isinstance(pair, str) or " <- " not in pair:
                    fails.append("category %s / unit %s has a malformed "
                                 "evidence entry %r" % (cat, name, pair))
                    continue
                cap, tok = pair.split(" <- ", 1)
                if cap not in caps_by_unit.get(name, set()):
                    fails.append("category %s / unit %s claims it fired on "
                                 "%r, which that unit does not declare"
                                 % (cat, name, cap))
                elif not token_hits(cap, tok):
                    fails.append("category %s / unit %s evidence %r does not "
                                 "match under the whole-token rule; the tag "
                                 "was not earned" % (cat, name, pair))
    if total_pairs == 0 and not no_evidence:
        fails.append("match_evidence is empty for every category; the trace "
                     "is absent")

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
    if total_pairs:
        print("  match evidence: %d 'cap <- token' pairs re-derived from the "
              "units' own capability fields and verified" % total_pairs)
        if no_evidence:
            print("    %d tagged unit/category cells carry no traceable token"
                  % no_evidence)
    kr = cov.get("keyword_repairs") or {}
    if kr:
        rej = kr.get("rejected") or []
        print("  keyword repairs: %s added"
              % ", ".join("%s+%d" % (k, len(v))
                          for k, v in sorted((kr.get("added") or {}).items())))
        if rej:
            print("    rejected as false-positive sources: %s"
                  % ", ".join("%s(%s)" % (r.get("token"), r.get("target"))
                              for r in rej))
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


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: mutate the coverage artifact and assert
    the gate goes red. Each injection exercises one of the failure
    classes declared in the module docstring.

    Apply and restore are structurally separate (tempfile + globals swap
    + finally), so no injection leaks state into the next one.
    """
    bad = 0
    n_inj = 0

    real_cov = json.loads(COVERAGE.read_text(encoding="utf-8"))

    def expect(name, mutate_fn):
        nonlocal bad, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate11_inj_"))
        try:
            cov = deepcopy(real_cov)
            mutate_fn(cov)
            fp = td / "coverage.json"
            fp.write_text(json.dumps(cov, ensure_ascii=False), encoding="utf-8")
            old_cov_path = globals()["COVERAGE"]
            globals()["COVERAGE"] = fp
            globals()["fails"].clear()
            globals()["warns"].clear()
            try:
                rc = main()
            finally:
                globals()["COVERAGE"] = old_cov_path
        finally:
            shutil.rmtree(td, ignore_errors=True)

        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    # 1. coverage_matrix is emptied (silent loss of the whole artifact).
    def _inj_empty_matrix(cov):
        cov["coverage_matrix"] = []

    expect("coverage_matrix is emptied", _inj_empty_matrix)

    # 2. A vision_required category silently loses its flag (target set
    #    dropped from the artifact).
    def _inj_no_required(cov):
        for r in cov.get("coverage_matrix", []):
            r["vision_required"] = False

    expect("every vision_required flag is cleared", _inj_no_required)

    # 3. A category claims units but lists none (count vs. evidence drift).
    def _inj_count_vs_listed(cov):
        for r in cov.get("coverage_matrix", []):
            if r.get("units") and r.get("units_listed"):
                r["units_listed"] = []
                return

    expect("a category claims units but lists none", _inj_count_vs_listed)

    # 4. A category names a unit the library does not have.
    def _inj_unknown_unit(cov):
        matrix = cov.get("coverage_matrix", [])
        for r in matrix:
            if r.get("units_listed"):
                r["units_listed"] = ["nonexistent_unit_zzz"]
                r["units"] = 1
                r.pop("match_evidence", None)
                return

    expect("a category names an unknown unit", _inj_unknown_unit)

    # 5. The summary's taxon split disagrees with the matrix.
    def _inj_taxon_drift(cov):
        s = cov.get("summary", {})
        if s:
            s["vision_required_single_taxon"] = ["__fake_single__"]
            s["vision_required_three_plus_taxa"] = ["__fake_multi__"]

    expect("the summary's taxon split disagrees with the matrix", _inj_taxon_drift)

    # State must be byte-clean after the battery.
    assert COVERAGE.exists(), "injections leaked COVERAGE path"
    fails.clear()
    warns.clear()

    return bad, n_inj


def _run_with_injections() -> int:
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"GATE 11: FAIL -- {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


if __name__ == "__main__":
    raise SystemExit(_run_with_injections())
