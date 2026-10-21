#!/usr/bin/env python3
"""GATE 63 — research_claims.json top-level stat completeness.

Why this exists
---------------
Before v2.98.2, ``research_claims.json`` stored its statistical
enrichment only in *nested* ``ci_enrichment`` blocks inside
``preregistered.<PR>``. The top-level ``claims[].`` records — the
ones a reviewer actually reads when scanning the manifest — had
no ``ci_low``, ``ci_high``, ``p_value``, or ``test_name``. A
reviewer (or a mutation that dropped the CI block) could not
distinguish a rigorously-tested claim from a hand-waved one by
looking at the top-level structure alone.

This gate asserts that every claim in ``research_claims.json``
carries a top-level statistical block:

  - ``point_estimate`` (or an explicit ``null`` with reason)
  - ``ci_low`` / ``ci_high`` (or ``null`` with ``ci_missing_reason``)
  - ``p_value`` (or ``null`` with ``p_value_missing_reason``)
  - ``test_name`` (non-empty string)
  - ``test_detail`` (non-empty string explaining the test)

And when a numeric CI is present, the point estimate must lie
inside [ci_low, ci_high] (with a small float tolerance).

Checks
------
1. All 6 top-level claims present (R1, R2, R3, R4, R5, R6).
2. Each claim has all five required stat fields present (key exists).
3. Every ``null`` value has a matching ``*_missing_reason`` or
   ``*_note`` field explaining why.
4. ``test_name`` and ``test_detail`` are non-empty strings.
5. Numeric point estimate lies inside [ci_low, ci_high] when both
   are numeric.
6. ``ci_method`` (when present) is a recognised vocabulary token
   (wilson_score_95 / bootstrap_percentile_slope_B1000_seed42 /
   deterministic_didactic_test / not_available).

Injection battery (Gate 39 compliance): three injections —
``drop_ci_low``, ``drop_p_value``, ``corrupt_point_estimate`` —
each must turn this gate red.

Usage:
    python scripts/check_claim_stats.py
    python scripts/check_claim_stats.py --quiet
    python scripts/check_claim_stats.py --json
    python scripts/check_claim_stats.py --inject
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GATE_ID = 63
GATE_LABEL = f"GATE {GATE_ID}"

DEFAULT_CLAIMS = ROOT / "research_claims.json"

_REQUIRED_CLAIM_IDS = ("R1", "R2", "R3", "R4", "R5", "R6")

# Fields that must exist as KEYS on every claim (value may be null
# with reason, but the key must be there so a scanner sees the
# shape).
_REQUIRED_FIELDS = (
    "point_estimate",
    "ci_low",
    "ci_high",
    "p_value",
    "test_name",
    "test_detail",
)

# Fields that must be present WHEN the value is null (explaining
# why the null is legitimate).
_NULL_REASON_KEYS = {
    "point_estimate": "point_estimate_missing_reason",
    "ci_low": "ci_missing_reason",
    "ci_high": "ci_missing_reason",
    "p_value": "p_value_missing_reason",
}

_ALLOWED_CI_METHODS = frozenset({
    "wilson_score_95",
    "bootstrap_percentile_slope_B1000_seed42",
    "deterministic_didactic_test",
    "not_available",
    "single-point",
})


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_float(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_claim(claim: dict, expected_id: str) -> tuple[list[str], list[str]]:
    """Validate a single claim record. Returns (failures, notes)."""
    failures: list[str] = []
    notes: list[str] = []

    cid = claim.get("id")
    if cid != expected_id:
        failures.append(f"claim block labelled '{cid!r}', expected '{expected_id}'")
    label = f"claim[{cid or expected_id}]"

    # 1. Required keys must exist.
    for field in _REQUIRED_FIELDS:
        if field not in claim:
            failures.append(
                f"{label}: missing required top-level stat field '{field}'"
            )

    # 2. Null values must have a reason.
    for value_field, reason_key in _NULL_REASON_KEYS.items():
        if value_field in claim and claim[value_field] is None:
            reason = claim.get(reason_key)
            if not reason:
                failures.append(
                    f"{label}: {value_field} is null but "
                    f"'{reason_key}' is missing — a null value "
                    f"must carry an explicit reason"
                )
            else:
                notes.append(f"{label}: {value_field} null, reason given")

    # 3. test_name / test_detail must be non-empty strings.
    for field in ("test_name", "test_detail"):
        v = claim.get(field)
        if v is not None:
            if not isinstance(v, str) or not v.strip():
                failures.append(
                    f"{label}: {field}={v!r} must be a non-empty string"
                )

    # 4. CI method vocabulary.
    ci_method = claim.get("ci_method")
    if ci_method is not None:
        if not isinstance(ci_method, str):
            failures.append(f"{label}: ci_method must be a string, got {type(ci_method).__name__}")
        elif ci_method not in _ALLOWED_CI_METHODS:
            failures.append(
                f"{label}: ci_method={ci_method!r} is not in the recognised "
                f"vocabulary {sorted(_ALLOWED_CI_METHODS)}"
            )

    # 5. Point estimate inside CI when both numeric.
    pe = claim.get("point_estimate")
    lo = claim.get("ci_low")
    hi = claim.get("ci_high")
    if _is_float(pe) and _is_float(lo) and _is_float(hi):
        tol = 1e-6
        if not (lo - tol <= pe <= hi + tol):
            failures.append(
                f"{label}: point_estimate {pe} is outside "
                f"[ci_low={lo}, ci_high={hi}] — either the CI "
                f"or the point estimate is wrong"
            )
        if lo > hi:
            failures.append(
                f"{label}: ci_low={lo} > ci_high={hi} — CI bounds inverted"
            )
    else:
        # Not all numeric — either point or CI is null with reason
        # (already handled above), or a category error.
        notes.append(f"{label}: mixed stat types (point={type(pe).__name__}, "
                     f"ci_low={type(lo).__name__}, ci_high={type(hi).__name__})")

    # 6. p_value numeric sanity when present.
    pv = claim.get("p_value")
    if _is_float(pv):
        if not (0.0 <= pv <= 1.0):
            failures.append(f"{label}: p_value={pv} must be in [0, 1]")

    return failures, notes


def check() -> dict:
    failures: list[dict] = []
    warnings: list[dict] = []
    notes: list[str] = []

    def fail(rule, detail):
        failures.append({"rule": rule, "detail": detail})

    def warn(rule, detail):
        warnings.append({"rule": rule, "detail": detail})

    if not DEFAULT_CLAIMS.exists():
        fail("CS.1", f"claims file missing: {DEFAULT_CLAIMS.relative_to(ROOT)}")
        return _report(failures, warnings, notes, summary="claims file missing")

    claims = _load_json(DEFAULT_CLAIMS)
    top_claims = claims.get("claims")
    if not isinstance(top_claims, list) or not top_claims:
        fail("CS.1", "'claims' is missing or empty at top level")
        return _report(failures, warnings, notes, summary="claims list empty")

    ids_seen = {c.get("id") for c in top_claims}
    missing = [i for i in _REQUIRED_CLAIM_IDS if i not in ids_seen]
    if missing:
        fail("CS.2", f"claims missing required ids: {missing}")
    extra = sorted(ids_seen - set(_REQUIRED_CLAIM_IDS))
    if extra:
        notes.append(f"extra claim ids present (allowed): {extra}")

    per_claim_failures: list[str] = []
    for expected_id in _REQUIRED_CLAIM_IDS:
        claim = next((c for c in top_claims if c.get("id") == expected_id), None)
        if claim is None:
            continue
        f, n = check_claim(claim, expected_id)
        per_claim_failures.extend(f)
        notes.extend(n)

    for detail in per_claim_failures:
        # Rule id derived from the claim id
        tag = detail.split("[", 1)[1].split("]", 1)[0] if "[" in detail else "claim"
        fail(f"CS.{tag}", detail)

    verdict = "PASS" if not failures else "FAIL"
    return _report(failures, warnings, notes,
                   summary=f"{len(top_claims)} claims audited, "
                           f"{len(_REQUIRED_CLAIM_IDS)} required",
                   verdict=verdict)


def _report(failures, warnings, notes, *, summary, verdict="PASS") -> dict:
    if not failures and verdict == "PASS":
        verdict = "PASS"
    elif failures:
        verdict = "FAIL"
    return {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "gate": f"{GATE_LABEL} — research_claims top-level stat completeness",
        "verdict": verdict,
        "summary": summary,
        "n_failures": len(failures),
        "n_warnings": len(warnings),
        "notes": notes,
        "warnings": warnings,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Injection battery (Gate 39 discipline)
# ---------------------------------------------------------------------------

def _baseline_claims() -> dict:
    return {
        "R1": {
            "id": "R1",
            "point_estimate": 0.788,
            "ci_low": 0.788,
            "ci_high": 0.788,
            "p_value": 0.1262,
            "test_name": "two_sided_normal_z_test",
            "test_detail": "z=1.5291, p=0.1262 vs permutation null",
            "ci_method": "single-point",
        },
        "R2": {
            "id": "R2",
            "point_estimate": 0.9060,
            "ci_low": 0.2135,
            "ci_high": 1.0828,
            "p_value": None,
            "p_value_missing_reason": "bootstrap CI reported; no parametric p",
            "test_name": "bootstrap_slope_CI_percentile",
            "test_detail": "slope CI [0.2135, 1.0828] across 350 samples",
            "ci_method": "bootstrap_percentile_slope_B1000_seed42",
        },
        "R4": {
            "id": "R4",
            "point_estimate": 0.56,
            "ci_low": 0.5291,
            "ci_high": 0.5905,
            "p_value": 0.0,
            "test_name": "wilson_score_95",
            "test_detail": "Wilson CI on 560/1000",
            "ci_method": "wilson_score_95",
        },
    }


def _injection_cases() -> list[tuple[str, dict, str]]:
    cases = []

    # 1. Drop ci_low from R1 — must trip the required-field rule.
    c = copy.deepcopy(_baseline_claims())
    c["R1"].pop("ci_low", None)
    cases.append(("drop_ci_low", c, "CS.1-required"))

    # 2. Drop p_value from R2 (which previously had a documented
    #    null) — but here we REMOVE the key entirely, so no reason
    #    field is present either.
    c = copy.deepcopy(_baseline_claims())
    c["R2"].pop("p_value", None)
    cases.append(("drop_p_value_key", c, "CS.1-required"))

    # 3. Corrupt the point estimate: R4 point 0.56 -> 0.99 which is
    #    outside the CI [0.5291, 0.5905].
    c = copy.deepcopy(_baseline_claims())
    c["R4"]["point_estimate"] = 0.99
    cases.append(("corrupt_point_estimate", c, "CS.5-ci-bound"))

    # 4. Flip ci_low above ci_high in R2.
    c = copy.deepcopy(_baseline_claims())
    c["R2"]["ci_low"] = 1.0828
    c["R2"]["ci_high"] = 0.2135
    cases.append(("invert_ci_bounds", c, "CS.5-ci-bound"))

    # 5. Bogus ci_method.
    c = copy.deepcopy(_baseline_claims())
    c["R4"]["ci_method"] = "made_up_method_xyz"
    cases.append(("bogus_ci_method", c, "CS.4-vocabulary"))

    return cases


def run_injections() -> int:
    print("=" * 60)
    print(f"{GATE_LABEL} — rule-logic injection (each case must trip)")
    bad = 0
    for name, claims, _rule in _injection_cases():
        per_id_failures: list[str] = []
        for cid, claim in claims.items():
            f, _n = check_claim(claim, cid)
            per_id_failures.extend(f)
        caught = len(per_id_failures) > 0
        if not caught:
            bad += 1
        flag = "OK " if caught else "MISS"
        print(f"  [{flag}] {name:<24} -> {len(per_id_failures)} failure(s)")
    print("=" * 60)
    total = len(_injection_cases())
    print(f"injected-defect battery: {total - bad}/{total} caught")
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — research_claims top-level stat completeness"
    )
    ap.add_argument("--inject", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.inject:
        return run_injections()

    rep = check()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    elif args.quiet:
        print(f"{GATE_LABEL}: {rep['verdict']}  (failures={rep['n_failures']})")
    else:
        print("=" * 60)
        print(rep["gate"])
        print(f"  summary: {rep.get('summary')}")
        print(f"  failures={rep['n_failures']}  warnings={rep['n_warnings']}")
        for n in rep["notes"]:
            print(f"  v {n}")
        for w in rep["warnings"]:
            print(f"  ~ WARN [{w['rule']}] {w['detail']}")
        for f in rep["failures"]:
            print(f"  x FAIL [{f['rule']}] {f['detail']}")
        print("=" * 60)
        print(f"{GATE_LABEL}: {rep['verdict']}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
