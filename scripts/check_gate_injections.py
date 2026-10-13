#!/usr/bin/env python3
"""GATE 39 — meta-gate: every check_*.py must have an injected-defect test.

Why this exists
---------------
A gate that has never proven it can go red is a gate that was never going to
catch anything. This has bit this project twice:

* 92.6% isolation_effect_size passed every gate (V1 ✅, V2 partial ✅) but
  turned out to be a *saturated binary* — no gate asked "does this metric
  still have discrimination?"
* P1's "+33.4pp" claim passed the checker but the control group was structurally
  unable to score on one task class — no gate asked "is the control
  comparable?"

Both failures were *gate-level* failures (V2), not *gate-execution* failures
(V1). Gate 39 is the discipline that escalates V2 to V3: every gate must
evidence its own failure mode by turning red when a defect is injected into
the system it guards.

How a gate satisfies this gate
------------------------------
Any of the following recognisable patterns inside the source counts as an
injection test present:

* a function named ``_injections``, ``inject_defects``, ``test_injection``,
  ``run_injections``, ``inject_*``, or ``_injected_defects``
* a call site that mutates state and re-runs the assertion battery
  (``expect("...injecting..."``), ``_expect_defect``, ``inject_and_expect_red``)
* a ``--inject`` / ``--mutation`` CLI flag
* the string ``injected-defect`` / ``injected defect`` / ``mutation test``

The pattern list is deliberately generous: this gate only asks "does the
authorship record an injection attempt?", not "is the injection battery
comprehensive?" — that quality question is a review concern, not a
machine-checkable one.

Two modes
---------
Default (``--progressive``):  gates listed in KNOWN_MISSING_INJECTIONS are
treated as tracked work-in-progress and produce a WARNING. Everything else
must pass, or the gate exits 1.

Strict (``--v3``):             no exemptions; every gate must have an
injection test. This is the release-mode for phase A → B transition.

Running
-------
    python scripts/check_gate_injections.py
    python scripts/check_gate_injections.py --v3
    python scripts/check_gate_injections.py --json-out /path/report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

GATE_ID = 39
GATE_LABEL = f"GATE {GATE_ID}"

# ---------------------------------------------------------------------------
# Detection patterns — deliberately broad, deliberately conservative.
# ---------------------------------------------------------------------------

# Function definitions that are unambiguously injection batteries.
_INJECT_FN_DEF = re.compile(
    r"^def\s+("
    r"_?injections?[_a-z0-9]*"
    r"|inject[a-z_]*defect[a-z_]*"
    r"|test_injection[a-z_]*"
    r"|run_injections?"
    r"|inject_and_expect[a-z_]*"
    r"|_inject_defect"
    r")\s*\(",
    re.MULTILINE,
)

# Variable/attribute assignments of injection test cases (e.g.
# ``injections = [...]``, ``FAULT_INJECTIONS = {...}``, ``FAULT_CASES = ...``).
_INJECT_LIST_ASSIGN = re.compile(
    r"\b(INJECT(?:ION|ED|_)?(?:S|_DEFECTS?|_CASES?|_TESTS?)?|"
    r"FAULT_INJECTIONS?|"
    r"DEFECT_CASES?|"
    r"MUTATION_CASES?)\s*=\s*[\[\({]",
    re.IGNORECASE,
)

# Call-site patterns: functions that signal an injection attempt.
_INJECT_CALL = re.compile(
    r"\b(expect\s*\([\"'][^\"']*injecting"
    r"|_expect_defect"
    r"|inject_and_expect_red"
    r"|_run_injection\b"
    r"|injection_test\b"
    r"|check\s*\([\"']fail[- ]closed\s*:)"
    r"\b"
)

# CLI flag for injection mode.
_INJECT_FLAG = re.compile(r"\-\-inject(?:ed[- ]defect)?\b|\-\-mutation\b")

# Prose markers used in docstrings/comments. Matched case-insensitively;
# we require at least 2 hits to avoid false positives on a passing mention.
_INJECT_PROSE = re.compile(
    r"injected[- ]defect"
    r"|injected[- ]defects"
    r"|injection test"
    r"|injection tests"
    r"|mutation[- ]test"
    r"|fault injection"
    r"|fault injections"
    r"|defect injection"
    r"|defect injection"
    r"|defect injections"
    r"|fail[- ]closed injection"
    r"|fail[- ]closed proof"
    r"|fail[- ]closed tests"
    r"|inject one defect"
    r"|re-injects the defects"
    r"|must produce ok=false"
    r"|gate stays green"
    r"|gate stayed green"
    r"|goes red"
    r"|turn the gate red"
    r"|turn.*red when.*injected",
    re.IGNORECASE,
)


def has_injection(text: str) -> tuple[bool, list[str]]:
    """Return (has_injection, matched_pattern_kinds)."""
    matched: list[str] = []
    if _INJECT_FN_DEF.search(text):
        matched.append("fn_def")
    if _INJECT_LIST_ASSIGN.search(text):
        matched.append("list_assign")
    if _INJECT_CALL.search(text):
        matched.append("call")
    if _INJECT_FLAG.search(text):
        matched.append("cli_flag")
    prose_hits = _INJECT_PROSE.findall(text)
    if len(prose_hits) >= 2:
        matched.append("prose")
    return bool(matched), matched


# ---------------------------------------------------------------------------
# Tracked work-in-progress (WIP) exemptions.
#
# Each exemption carries (a) a one-line reason, and (b) the M1 subtask that
# will close it. This is not a permanent whitelist — it is a *visible backlog*.
# Gate 39 in default mode warns about these; in --v3 mode it fails on them.
#
# When an exemption's subtask lands, DELETE its line from this dict. The gate
# will then enforce the injection going forward. This is how the backlog
# drains to zero without anyone having to remember.
# ---------------------------------------------------------------------------

KNOWN_MISSING_INJECTIONS: dict[str, str] = {
    # All 6 remaining SV-1a backlog entries CLOSED 2026-10-13:
    #   check_degraded_mode.py, check_docs_consistency.py,
    #   check_mcp_tools.py, check_module_architecture.py,
    #   check_physical_tiering.py, check_topology_signature.py
    # Each now has a _injections() battery; delete lines below when new ones
    # are tracked. Gate 39 in --v3 mode fails if anything lands here.
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def scan() -> tuple[list[dict], list[dict], list[dict]]:
    """Return (with_injection, exempted, missing)."""
    files = sorted(SCRIPTS.glob("check_*.py"))
    with_inj: list[dict] = []
    exempted: list[dict] = []
    missing: list[dict] = []

    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            missing.append({"file": p.name, "error": f"unreadable: {e}"})
            continue
        has, kinds = has_injection(text)
        entry = {"file": p.name, "patterns": kinds, "size": len(text)}
        if has:
            with_inj.append(entry)
        elif p.name in KNOWN_MISSING_INJECTIONS:
            exempted.append({**entry, "reason": KNOWN_MISSING_INJECTIONS[p.name]})
        else:
            missing.append(entry)

    return with_inj, exempted, missing


def main() -> int:
    ap = argparse.ArgumentParser(
        description="GATE 39 — meta-gate: every check_*.py must have an "
                    "injected-defect test (V2 → V3 discipline)")
    ap.add_argument("--v3", action="store_true",
                    help="strict mode: no exemptions; every gate must have an "
                         "injection test (release mode)")
    ap.add_argument("--json-out", metavar="PATH",
                    help="write structured report to PATH")
    args = ap.parse_args()

    with_inj, exempted, missing = scan()

    total = len(with_inj) + len(exempted) + len(missing)
    inj_pct = 100.0 * len(with_inj) / max(total, 1)

    print(f"{GATE_LABEL} — meta-gate: every check_*.py must carry an "
          f"injected-defect test")
    print(f"  mode: {'V3 STRICT' if args.v3 else 'PROGRESSIVE'}")
    print(f"  total gates scanned: {total}")
    print(f"  with injections:     {len(with_inj)} "
          f"({inj_pct:.0f}%)")
    print(f"  exempted (WIP):      {len(exempted)}")
    print(f"  missing (UNTRACKED): {len(missing)}")
    print()

    if with_inj:
        print("  [PASS] gates with injection tests:")
        for e in with_inj:
            print(f"    ✓ {e['file']}  ({','.join(e['patterns'])})")
        print()

    if exempted:
        print("  [WARN] exempted — tracked WIP backlog (each line must be "
              "deleted when its subtask lands):")
        for e in exempted:
            print(f"    ~ {e['file']}")
            print(f"      · {e['reason']}")
        print()

    if missing:
        print("  [FAIL] gates missing injection test AND not exempted:")
        for e in missing:
            print(f"    ✗ {e['file']}")
        print()

    # Write JSON report for cross-gate aggregation.
    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "mode": "v3" if args.v3 else "progressive",
        "total": total,
        "with_injection": len(with_inj),
        "exempted": len(exempted),
        "missing": len(missing),
        "coverage_pct": round(inj_pct, 2),
        "with_injection_files": [e["file"] for e in with_inj],
        "exempted_files": [e["file"] for e in exempted],
        "missing_files": [e["file"] for e in missing],
        "known_missing": KNOWN_MISSING_INJECTIONS,
    }
    out_path = SCRIPTS / "_gate39_report.json"
    if args.json_out:
        out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"  report: {out_path}")
    print()

    # Verdict
    if missing:
        return 1

    if args.v3:
        if exempted:
            print(f"{GATE_LABEL}: FAIL — V3 strict mode; {len(exempted)} "
                  f"exempted gates still in the backlog")
            return 1
        print(f"{GATE_LABEL}: PASS — 100% injection coverage "
              f"({total}/{total}); V3 self-verification threshold met")
        return 0

    if exempted:
        pct_str = f"{inj_pct:.0f}%"
        print(f"{GATE_LABEL}: WARN — {len(with_inj)}/{total} gates have "
              f"injection tests ({pct_str}); "
              f"{len(exempted)} tracked in KNOWN_MISSING_INJECTIONS backlog")
        print(f"  → to reach V3: close each backlog entry and re-run "
              f"with --v3")
        return 0

    print(f"{GATE_LABEL}: PASS — {len(with_inj)}/{total} gates have "
          f"injection tests (100%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
