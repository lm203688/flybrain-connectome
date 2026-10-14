#!/usr/bin/env python3
"""GATE 43 — preregistered claims: manifest ↔ execution integrity (R-0.2).

Why this exists
---------------
PREREGISTRATION_PROTOCOL_v1.md freezes PR-1's threshold, split, features,
and success criteria before any test run. R-0.2 says these frozen values
must live in `research_claims.json.preregistered.PR1.*` AND be echoed by
the execution script, so a future editor cannot silently swap
`--threshold 0.25` for `--threshold 0.30` (or re-introduce a median split)
without tripping a machine check.

Gate 43 is a **mechanism-layer** gate: it checks that preregistration
was performed honestly (JSON present, values frozen, script params
consistent with the JSON, label definition is an absolute threshold).
It does NOT judge whether the L3 prediction succeeded — that outcome
goes to `claims[R1].preregistered.PR1.verified_against` and is reported
as a WARN here so CI stays green for the mechanism while the L3 verdict
is transparent. The project already records 4 measurement-level
defects the same way; this is the same discipline for L3.

Injection battery
-----------------
Two injections prove Gate 43 can turn red:
  1. Tamper the preregistered threshold in the in-memory JSON → FAIL.
  2. Revert the label_definition to a median-split form → FAIL.

Usage:
    python scripts/check_preregistered_claims.py
    python scripts/check_preregistered_claims.py --quiet
    python scripts/check_preregistered_claims.py --json-out report.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_CLAIMS = ROOT / "research_claims.json"
DEFAULT_PR1_RESULT = ROOT / "_r1_mechanism_prereg" / "f1_preregistered.json"

GATE_ID = 43
GATE_LABEL = f"GATE {GATE_ID}"

# PR-1 label definition must NOT contain any of these substrings — they are
# the data-dependent forms we are explicitly replacing.
_FORBIDDEN_IN_LABEL = ("median", "quantile", "percentile", "<=", ">=", "= 0.")


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_pr1(claims: dict, pr1_result: dict) -> tuple[list[str], list[str], list[str]]:
    """Return (failures, warnings, notes) for the PR-1 preregistration block.

    All checks are mechanism-layer: manifest ↔ execution integrity. The
    L3 success/fail verdict is reported as a WARN so that Gate 43 stays
    honest about the outcome without failing the pipeline when PR-1 has
    not yet reached L3 (per R-0.4: preregistration failure is a real
    scientific result and must NOT block progress).
    """
    failures: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    # --- 1. Manifest presence ---
    prereg = claims.get("preregistered", {})
    if not prereg:
        failures.append("research_claims.json has no top-level 'preregistered' block")
        return failures, warnings, notes
    pr1 = prereg.get("PR1")
    if not isinstance(pr1, dict):
        failures.append("preregistered.PR1 missing or not an object")
        return failures, warnings, notes
    notes.append(f"preregistered.PR1 present: threshold={pr1.get('threshold')} "
                 f"features={len(pr1.get('features', []))}")

    # --- 2. Execution JSON presence + shape ---
    summary = pr1_result.get("summary", {})
    params = summary.get("params", {})
    if not params:
        failures.append("execution JSON has no summary.params block")
        return failures, warnings, notes
    notes.append(f"execution JSON summary.params.threshold={params.get('threshold')}")

    # --- 3. Threshold match (float, tight tolerance) ---
    pr_threshold = pr1.get("threshold")
    ex_threshold = params.get("threshold")
    if pr_threshold is None or ex_threshold is None:
        failures.append(f"threshold missing: prereg={pr_threshold!r} exec={ex_threshold!r}")
    else:
        if abs(float(pr_threshold) - float(ex_threshold)) > 1e-9:
            failures.append(
                f"threshold mismatch: preregistered={pr_threshold} "
                f"execution={ex_threshold} (R-0.2 violation)"
            )
        else:
            notes.append(f"threshold consistent: {pr_threshold}")

    # --- 4. Feature set exact match ---
    pr_features = list(pr1.get("features", []))
    ex_features = list(summary.get("features", []))
    if pr_features != ex_features:
        failures.append(
            f"feature-set mismatch: prereg={pr_features} execution={ex_features}"
        )
    else:
        notes.append(f"features frozen: {len(pr_features)} features matched")

    # --- 5. Train / held-out slice match ---
    for key in ("train_idx", "held_out_idx"):
        pr_v = pr1.get(key)
        ex_v = params.get(key)
        if pr_v != ex_v:
            failures.append(
                f"{key} mismatch: prereg={pr_v!r} execution={ex_v!r}"
            )
        else:
            notes.append(f"{key} consistent: {pr_v}")

    # --- 6. Permutation count match ---
    pr_perm = pr1.get("permutations")
    ex_perm = params.get("permutations")
    if pr_perm is not None and ex_perm is not None and int(pr_perm) != int(ex_perm):
        failures.append(
            f"permutations mismatch: prereg={pr_perm} execution={ex_perm}"
        )
    else:
        notes.append(f"permutations consistent: {ex_perm}")

    # --- 7. Label definition is absolute (not median-split) ---
    label_def = summary.get("label_definition", "")
    for token in _FORBIDDEN_IN_LABEL:
        if token in label_def.lower():
            failures.append(
                f"label_definition uses a data-dependent form "
                f"(contains {token!r}): {label_def!r}"
            )
    # Also verify the label definition echoes the exact threshold.
    if pr_threshold is not None and f"{float(pr_threshold):g}" not in label_def:
        failures.append(
            f"label_definition does not echo threshold {pr_threshold}: {label_def!r}"
        )
    else:
        notes.append(f"label_definition is absolute: {label_def!r}")

    # --- 8. Report (WARN) the L3 success criteria vs actual outcome ---
    crit = pr1.get("success_criteria", {})
    auc_min = crit.get("held_out_auc_min")
    z_min = crit.get("z_min")
    auc = summary.get("auc_held_out")
    z = summary.get("z_score")
    if all(v is not None for v in (auc_min, z_min, auc, z)):
        if float(auc) >= float(auc_min) and float(z) >= float(z_min):
            notes.append(
                f"L3 PREREGISTERED TARGET MET: AUC={auc} >= {auc_min}, "
                f"z={z} >= {z_min}"
            )
        elif float(auc) >= float(auc_min):
            warnings.append(
                f"L3 not yet reached: AUC={auc} >= {auc_min} but z={z} < {z_min}. "
                f"Result is honest and preregistered — PR-1 remains weak-pass. "
                f"Do NOT alter thresholds to force a pass (R-0.4)."
            )
        else:
            warnings.append(
                f"L3 PREREGISTERED TARGET NOT MET: AUC={auc} < {auc_min}. "
                f"Record as negative result per R-0.4; do NOT adjust criteria."
            )

    return failures, warnings, notes


def _run_injections(claims: dict, pr1_result: dict) -> tuple[int, int]:
    """Two injections: tamper the threshold, and re-introduce a median split.

    Both must turn Gate 43 red; if either stays green, the gate itself
    is a no-op and this gate fails.
    """
    bad = 0
    n_inj = 0

    def expect(name, apply_fn, restore_fn, checker):
        nonlocal bad, n_inj
        n_inj += 1
        original = (copy.deepcopy(claims), copy.deepcopy(pr1_result))
        try:
            apply_fn()
            failures, _w, _n = checker(claims, pr1_result)
        finally:
            claims.clear()
            claims.update(original[0])
            pr1_result.clear()
            pr1_result.update(original[1])
        ok = len(failures) > 0
        if ok:
            print(f"    [PASS] injecting: {name}")
        else:
            bad += 1
            print(f"    [FAIL] injecting: {name} -> GATE STAYED GREEN")

    def _checker(c, p):
        f, w, n = _check_pr1(c, p)
        return f, w, n

    # --- Injection 1: tamper the preregistered threshold ---
    def _patch_threshold():
        c = claims.get("preregistered", {}).get("PR1")
        if isinstance(c, dict):
            c["threshold"] = 0.99

    def _restore_threshold():
        pass  # handled by the deepcopy swap above

    expect("tamper preregistered threshold to 0.99 -> mismatch -> FAIL",
           _patch_threshold, _restore_threshold, _checker)

    # --- Injection 2: revert label_definition to median split ---
    def _patch_median_split():
        p = pr1_result.get("summary", {})
        if isinstance(p, dict):
            p["label_definition"] = "drop_magnitude < median(0.2133)"

    def _restore_median_split():
        pass

    expect("revert label_definition to median split -> FAIL",
           _patch_median_split, _restore_median_split, _checker)

    return bad, n_inj


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — preregistered claims: manifest ↔ execution integrity")
    ap.add_argument("--claims", metavar="PATH", default=str(DEFAULT_CLAIMS))
    ap.add_argument("--pr1-result", metavar="PATH", default=str(DEFAULT_PR1_RESULT))
    ap.add_argument("--json-out", metavar="PATH")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    claims_path = Path(args.claims)
    pr1_path = Path(args.pr1_result)

    if not claims_path.exists():
        print(f"{GATE_LABEL}: FAIL — claims file not found: {claims_path}")
        return 1
    if not pr1_path.exists():
        print(f"{GATE_LABEL}: FAIL — PR-1 execution result not found: {pr1_path}\n"
              f"  Run: python scripts/f1_mechanism_preregistered.py "
              f"--threshold 0.25 --train-idx 0:60 --held-out-idx 60:100 "
              f"--permutations 200 --seed 42")
        return 1

    claims = _load_json(claims_path)
    pr1_result = _load_json(pr1_path)

    if not args.quiet:
        print(f"{GATE_LABEL} — preregistered claims integrity (R-0.2)")
        print(f"  claims   : {claims_path}")
        print(f"  PR-1 out : {pr1_path}")
        print()

    failures, warnings, notes = _check_pr1(claims, pr1_result)

    if not args.quiet:
        for note in notes:
            print(f"  ✓ {note}")
        for warn in warnings:
            print(f"  ~ WARN {warn}")
        for fail in failures:
            print(f"  ✗ {fail}")
        print()

        print(f"  -- fail-closed injections --")
        inj_bad, n_inj = _run_injections(claims, pr1_result)
        if inj_bad:
            print(f"{GATE_LABEL}: FAIL -- {inj_bad}/{n_inj} injections did "
                  f"not turn red")
            return 1
        print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
        print()

    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "claims_path": str(claims_path),
        "pr1_result_path": str(pr1_path),
        "counts": {
            "fail": len(failures),
            "warn": len(warnings),
            "note": len(notes),
        },
        "notes": notes,
        "warnings": warnings,
        "failures": failures,
        "injections": {"total": n_inj if not args.quiet else 0,
                       "bad": inj_bad if not args.quiet else 0},
    }
    out_path = Path(args.json_out) if args.json_out else SCRIPTS / "_gate43_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    if not args.quiet:
        print(f"  report: {out_path}")

    if failures:
        print(f"\n{GATE_LABEL}: FAIL — {len(failures)} preregistration "
              f"integrity violation(s)")
        return 1
    if warnings:
        print(f"\n{GATE_LABEL}: PASS — mechanism integrity OK "
              f"({len(warnings)} L3 outcome warning(s) — see research_claims for "
              f"the honest status record)")
    else:
        print(f"\n{GATE_LABEL}: PASS — PR-1 preregistration consistent AND "
              f"L3 prediction target met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
