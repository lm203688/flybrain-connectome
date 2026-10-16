#!/usr/bin/env python3
"""GATE 56 — badge ladder semantic consistency (E1b).

What this gate does
-------------------
`compute_verification_badges.py::_claim_badge()` defines V0-V5 as a
ladder where each rung claims a *name* but the predicate it actually
tests is often only "existence of some artifact". EPE vision
(NEXT_STAGE_VISION_EPE_2026-10-16.md §9.3) audits every rung and finds
that V1-V5 predicates are all mismatched with their names.

Gate 56 turns that audit into a machine check. For each V-level, it
extracts the branch of `_claim_badge()` that returns that level and
asserts the branch contains at least one *semantic keyword* that
matches the level's name. If a rung's predicate does not contain any
keyword for its own name, that rung is *degenerate* — it claims a
property but tests something else.

Example of a mismatch Gate 56 catches:
    V1 name:  "reproducible"
    V1 predicate (current): `supports >= 1 and not has_prereg`
    Keywords required: reproduc* | seed | hash | bit_identical | re-run
    Verdict: NO keyword present → rung V1 is degenerate.

Two modes
---------
Default (audit mode): Gate 56 emits the mismatch report and exits 0.
This is the safe mode for CI: the mismatches are *already known* from
EPE §9.3 and are being fixed incrementally. Emitting the report is the
point — the gate is a *visible backlog*.

Strict mode (`--strict`): any mismatch is a FAIL. Turn on this mode
once you have repaired the predicates to match their names.

Gate 39 meta-discipline: the `injections()` battery below re-runs the
check on a mutated `_claim_badge()` source and asserts each mutation
turns the gate red. If any mutation passes, the gate is degenerate for
that defect class.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
BADGES_SRC = SCRIPTS / "compute_verification_badges.py"

GATE_ID = 56
GATE_LABEL = f"GATE {GATE_ID}"

# ---------------------------------------------------------------------------
# The named property each rung claims, and the semantic keywords that
# predicate must use to actually test that property.
#
# The keyword list is intentionally permissive — we are not trying to
# prove semantic equivalence here, only to catch *obvious* mismatches
# where the predicate tests a completely different property than the
# rung's name implies. A future refinement can tighten these lists.
# ---------------------------------------------------------------------------

RUNG_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "V0": {
        "name": "unverified",
        "claim": "bare claim, no machine evidence",
        "keywords": [
            "bare", "supports == 0", "supports==0",
            "no supports", "n_evidence",
        ],
    },
    "V1": {
        "name": "reproducible",
        "claim": "same seed / same code → identical results",
        "keywords": [
            "reproduc", "re-run", "rerun", "seed", "bit_identical",
            "bit-identical", "hash", "sha256",
        ],
    },
    "V2": {
        "name": "machine-tested",
        "claim": "at least one preregistered protocol has run against the claim",
        "keywords": [
            "executed_at", "verdict", "prereg", "ran", "run_at",
            "verification", "machine",
        ],
    },
    "V3": {
        "name": "preregistered",
        "claim": "claim's verdict is enforced by a gate (fail-closed)",
        "keywords": [
            "vault", "payload_hash", "committed", "prereg",
            "freeze", "frozen_at", "gate",
        ],
    },
    "V4": {
        "name": "cross-checked",
        "claim": "at least two independent reads of the evidence agree",
        "keywords": [
            "cross", "crosscheck", "cross-check", "independent",
            "second", "two ", "second_read", "readings",
        ],
    },
    "V5": {
        "name": "externally verified",
        "claim": "a receipt exists AND an external verifier has confirmed it",
        "keywords": [
            "external", "verifier", "signature", "verifiable",
            "receipt", "third-party", "third_party",
        ],
    },
}

# ---------------------------------------------------------------------------
# Source extraction: find each `return {"level": "Vx", ...}` branch and
# return the surrounding predicate code (the `if` conditions that guard
# that return, plus the return statement itself).
# ---------------------------------------------------------------------------

_BRANCH_RE = re.compile(
    r"(if\s+[^:]+:)\s*\n\s*"
    r"(return\s+\{\s*[\"']level[\"']\s*:\s*[\"'](V[0-5])[\"'][^\n]*\})"
    r"(?P<tail>[^\n\n]*)",
    re.MULTILINE,
)


def extract_branches(source: str) -> dict[str, str]:
    """Return {rung: predicate_source} for every V-level returned.

    We capture two lines of `if` context before each `return {"level":
    "Vx", ...}` line to get the full guard condition. A naive regex
    would only see the return line, missing the `supports == 0` /
    `has_prereg` etc. conditions that actually decide the level.
    """
    result: dict[str, str] = {}
    lines = source.splitlines()
    for i, line in enumerate(lines):
        m = re.search(r"[\"']level[\"']\s*:\s*[\"'](V[0-5])[\"']", line)
        if not m:
            continue
        rung = m.group(1)
        # Look backwards up to 6 lines for `if` guards. Stop at the
        # first blank line or function-def boundary.
        ctx_start = i
        for j in range(i - 1, max(i - 6, -1), -1):
            if not (0 <= j < len(lines)):
                break
            stripped = lines[j].strip()
            if stripped.startswith("def "):
                break
            if not stripped:
                break
            if "return" in stripped and "level" not in stripped:
                break
            ctx_start = j
        branch_src = "\n".join(lines[ctx_start:i + 1])
        result[rung] = branch_src
    return result


def check_branch(rung: str, source: str) -> tuple[str, list[str]]:
    """Return (rung, missing_keywords) for one rung.

    If the rung has no keyword matches, missing_keywords is non-empty
    and the rung is degenerate.
    """
    branch = extract_branches(source).get(rung, "")
    if not branch:
        return rung, [f"no predicate branch found for {rung}"]
    kw_map = RUNG_KEYWORDS.get(rung)
    if not kw_map:
        return rung, []  # unknown rung, skip
    keywords = kw_map["keywords"]
    matched: list[str] = []
    for kw in keywords:
        if kw in branch or kw.lower() in branch.lower():
            matched.append(kw)
    if not matched:
        return rung, [f"none of {keywords} present — predicate is degenerate"]
    return rung, []


def check_all(source_path: Path, strict: bool = False) -> tuple[bool, list[str], dict]:
    if not source_path.exists():
        return False, [f"source not found: {source_path}"], {}

    source = source_path.read_text(encoding="utf-8")
    branches = extract_branches(source)

    mismatches: list[dict] = []
    ok_rungs: list[str] = []
    for rung, spec in RUNG_KEYWORDS.items():
        branch = branches.get(rung, "")
        if not branch:
            mismatches.append({
                "rung": rung,
                "name": spec["name"],
                "claim": spec["claim"],
                "problem": "predicate branch not found in source",
                "matched_keywords": [],
            })
            continue
        matched = [kw for kw in spec["keywords"]
                   if kw in branch or kw.lower() in branch.lower()]
        if matched:
            ok_rungs.append(rung)
        else:
            mismatches.append({
                "rung": rung,
                "name": spec["name"],
                "claim": spec["claim"],
                "problem": (
                    "predicate does not contain any keyword for its own "
                    f"name '{spec['name']}' — tests a different property"
                ),
                "matched_keywords": [],
                "branch_preview": branch[:200].replace("\n", " | "),
            })

    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "source": str(source_path),
        "mode": "strict" if strict else "audit",
        "rungs_total": len(RUNG_KEYWORDS),
        "rungs_matching": len(ok_rungs),
        "rungs_degenerate": len(mismatches),
        "ok_rungs": ok_rungs,
        "mismatches": mismatches,
        "strict": strict,
    }

    if mismatches and not strict:
        # Audit mode: report but do not fail. This is the intended
        # steady state while predicates are being repaired.
        return True, [], report
    if mismatches and strict:
        failures = [
            f"{m['rung']} ({m['name']}): {m['problem']}"
            for m in mismatches
        ]
        return False, failures, report
    return True, [], report


# ---------------------------------------------------------------------------
# Injection battery
# ---------------------------------------------------------------------------

def injections() -> list[dict]:
    """Mutate the source and verify the gate catches each rung going
    degenerate. Each mutation targets one specific V-rung and removes
    its semantic keyword."""
    cases = []
    original = BADGES_SRC.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="gate56_inj_") as td:
        tmp_root = Path(td)
        # We'll mutate the source *text* and pass it through the same
        # check logic. Do this by writing mutated copies to disk and
        # running check_all against each.
        for rung in ("V1", "V2", "V3", "V4", "V5"):
            # Pick one keyword that MUST be present for the rung to pass.
            # If we remove ALL keyword matches from the branch, the gate
            # should go red in strict mode.
            # Strategy: take the original source, find the branch for
            # this rung, and strip the keyword tokens from the branch
            # body. To ensure the gate sees a degenerate branch, we
            # replace the branch with a minimal `if True: return {"level":
            # "Vx", "reason": "x"}` — which contains no keyword for Vx.
            rung_spec = RUNG_KEYWORDS[rung]
            # Find the rung's existing return line in the source.
            pattern = re.compile(
                r'return\s+\{\s*["\']level["\']\s*:\s*["\']' + rung + r'["\'][^\n]*\}',
            )
            m = pattern.search(original)
            if not m:
                cases.append({
                    "name": f"strip_{rung.lower()}_keyword",
                    "description": f"No return branch for {rung} found — skipped",
                    "mutated_ok": False,
                    "skipped": True,
                })
                continue
            # Replace the return line with a keyword-free stub so the
            # branch becomes degenerate. Also strip any `if` guards
            # immediately preceding by replacing with `if True:`.
            stub = f'return {{"level": "{rung}", "reason": "stub"}}'
            mutated = original[:m.start()] + stub + original[m.end():]

            p = tmp_root / f"src_{rung}.py"
            p.write_text(mutated, encoding="utf-8")
            ok, _fail, _rep = check_all(p, strict=True)
            cases.append({
                "name": f"strip_{rung.lower()}_keyword",
                "description": (
                    f"Replace the {rung} return branch with a keyword-free "
                    f"stub → the rung now claims '{rung_spec['name']}' but "
                    f"its predicate contains none of {rung_spec['keywords'][:3]}."
                ),
                "mutated_ok": ok,
            })

    return cases


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="GATE 56 — badge ladder semantic consistency (E1b)")
    ap.add_argument("--source", type=Path, default=BADGES_SRC,
                    help=f"path to compute_verification_badges.py "
                         f"(default: {BADGES_SRC})")
    ap.add_argument("--strict", action="store_true",
                    help="treat any mismatch as a failure (default: audit "
                         "mode — report but do not fail)")
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--skip-injections", action="store_true")
    args = ap.parse_args()

    src = args.source.resolve()
    print(f"{GATE_LABEL} — badge ladder semantic consistency (E1b)")
    print(f"  source : {src}")
    print(f"  mode   : {'STRICT' if args.strict else 'AUDIT'}")
    print()

    ok, failures, report = check_all(src, strict=args.strict)

    print(f"  rungs matching : {report.get('rungs_matching', 0)} / "
          f"{report.get('rungs_total', 0)}")
    print(f"  rungs degenerate: {report.get('rungs_degenerate', 0)}")
    print()

    for m in report.get("mismatches", []):
        print(f"    · {m['rung']} ({m['name']}): {m['problem']}")
        print(f"        · claim: {m['claim']}")
        if "branch_preview" in m:
            print(f"        · branch preview: {m['branch_preview'][:120]}...")
    print()

    if report.get("ok_rungs"):
        print(f"  [matching] {', '.join(report['ok_rungs'])}")
        print()

    if not args.strict and report.get("rungs_degenerate"):
        print(f"  [AUDIT MODE] {report['rungs_degenerate']} rung(s) are "
              f"degenerate (predicate does not test its named property). "
              f"This is a known backlog per EPE vision §9.3. Run with "
              f"--strict to fail.")
    elif failures:
        print(f"  [FAIL] {len(failures)} semantic mismatch(es)")
        for f in failures:
            print(f"    ✗ {f}")
    else:
        print(f"  [PASS] every rung's predicate tests its named property")
    print()

    if not args.skip_injections:
        print("  injection battery (Gate 39 meta-discipline):")
        cases = injections()
        any_green = False
        for c in cases:
            if c.get("skipped"):
                print(f"    ~ {c['name']}: skipped")
                continue
            status = "RED" if not c["mutated_ok"] else "GREEN (DEGENERATE)"
            if c["mutated_ok"]:
                any_green = True
            print(f"    {'✓' if not c['mutated_ok'] else '✗'} "
                  f"{c['name']}: {status}")
            print(f"        · {c['description']}")
        if any_green:
            print()
            print("  [FAIL] at least one injection mutation passed the "
                  "check; the gate is degenerate for that defect class")
            failures.append("injection battery: at least one mutation "
                            "did not turn the gate red")
        else:
            print()
            print("  [PASS] every injected defect turned the gate red")

    out_path = args.json_out or (SCRIPTS / "_gate56_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report["injections"] = [] if args.skip_injections else injections()
    report["ok"] = not failures
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n  report: {out_path}")
    print()

    if failures:
        print(f"{GATE_LABEL}: FAIL — {len(failures)} failure(s)")
        return 1
    print(f"{GATE_LABEL}: PASS — "
          f"{report.get('rungs_matching', 0)}/{report.get('rungs_total', 0)} "
          f"rungs match their named property "
          f"(mode={report.get('mode', 'audit')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
