#!/usr/bin/env python3
"""GATE 47 — PR-2b metric-substitution pre-check integrity.

Why this exists
---------------
PR-2 (delete_bridge vs delete_nonbridge -> drop_magnitude) returned FAIL at
three scales. The remediation proposed in the previous round was to *substitute*
the consequence metric with ``recovery_AUC``. That substitution was NOT run:
``scripts/f4b_metric_substitution_check.py`` found that ``recovery_AUC`` is
definitionally coupled to the intervention (its R-a modulator contains
``bridge_fraction`` and the whole trajectory is normalised by ``drop_magnitude``,
the quantity PR-2 measures).

Gate 47 locks that decision in so it cannot be quietly reversed:

  (a) **Manifest presence + typing** — ``research_claims.json.preregistered.PR2b``
      must exist, be typed ``pre_execution_rejection``, and carry a recorded
      decision.

  (b) **Criterion immutability (R-0.1 / R-0.4)** — the reject thresholds in the
      manifest must match the executed JSON verbatim, and
      ``criteria_modified_after_results`` must be false. If the thresholds drift,
      the recorded rejection can no longer be trusted as a pre-execution call.

  (c) **Decision integrity** — the recorded decision must be REJECT, and if the
      decision overrides the rule's own verdict the manifest MUST flag
      ``rule_underpowered`` so the override is explicit rather than silent.

  (d) **Independent recomputation** — the artifact rate and the pooled-sample
      coupling correlation are recomputed from ``all_results``. A summary block
      that claims a rejection the underlying rows do not support fails the gate.

Injection battery (4 injections):
  1. Tamper the manifest artifact threshold upward (0.90 -> 0.99) -> FAIL.
  2. Flip ``decision`` to ACCEPT while the artifact gate still fires -> FAIL.
  3. Set ``criteria_modified_after_results`` true -> FAIL.
  4. Reweight the artifact rate downward in ``all_results`` so the recomputed
     rate no longer supports the rejection -> FAIL.

Usage:
    python scripts/check_metric_substitution.py
    python scripts/check_metric_substitution.py --quiet
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_CLAIMS = ROOT / "research_claims.json"
DEFAULT_F4B_RESULT = ROOT / "_f4b_metric_substitution" / "f4b_metric_substitution.json"

GATE_ID = 47
GATE_LABEL = f"GATE {GATE_ID}"


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _pearson(a: list, b: list):
    """Pearson correlation. Delegates to metrics_kernel (K5)."""
    from _metrics_compat import pearson
    n = len(a)
    if n < 3 or len(b) != n:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a) / n)
    sb = math.sqrt(sum((y - mb) ** 2 for y in b) / n)
    if sa <= 1e-12 or sb <= 1e-12:
        return None
    return pearson(a, b)


def _check_pr2b(claims: dict, f4b: dict) -> tuple[list[str], list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    # --- 1. Manifest presence + typing ---
    prereg = claims.get("preregistered", {})
    if not prereg:
        failures.append("research_claims.json has no 'preregistered' block")
        return failures, warnings, notes
    pr2b = prereg.get("PR2b")
    if not isinstance(pr2b, dict):
        failures.append("preregistered.PR2b missing or not an object")
        return failures, warnings, notes
    kind = pr2b.get("kind")
    if kind != "pre_execution_rejection":
        failures.append(
            f"preregistered.PR2b.kind={kind!r} — expected 'pre_execution_rejection'"
        )
    else:
        notes.append(f"PR2b typed as {kind}")

    ver = pr2b.get("verification", {}) or {}
    if not ver:
        failures.append("preregistered.PR2b.verification missing or empty")
        return failures, warnings, notes
    criteria = pr2b.get("success_criteria", {}) or {}

    # --- 1b. Reject-rule structure (W2 hardening — S3 gate-effectiveness) ---
    # S3 showed `remove_reject_rule` injection was not caught. A preregistered
    # rejection MUST carry both quantitative thresholds — an empty or zero
    # reject rule cannot be trusted as a pre-execution call.
    _R2B_REQUIRED_CRITERIA = (
        "reject_if_coupling_corr_abs_min",
        "reject_if_artifact_rate_min",
        "declared_direction_for_recovery_auc",
    )
    for _field in _R2B_REQUIRED_CRITERIA:
        if _field not in criteria or criteria.get(_field) in (None, "", 0, 0.0, []):
            failures.append(
                f"preregistered.PR2b.success_criteria.{_field} missing or empty "
                f"— a pre-execution rejection must record every quantitative "
                f"threshold it commits to (W2 fix)"
            )

    # --- 1c. Direction lock (W3 hardening — S3 gate-effectiveness) ---
    # PR-2b's whole point is that `recovery_AUC` SHOULD decrease under the
    # proposed substitution (which is why it was rejected as definitionally
    # coupled). Flipping the direction to "increase" reinterprets the
    # substitution as a positive-intervention test — a silent semantic
    # reversal of the preregistration. Lock the value.
    _direction = criteria.get("declared_direction_for_recovery_auc")
    if _direction is not None and str(_direction).lower() != "decrease":
        failures.append(
            f"preregistered.PR2b.success_criteria.declared_direction_for_recovery_auc="
            f"{_direction!r} — PR-2b rejection rule requires 'decrease'; a "
            f"different direction is a semantic reversal of the preregistration "
            f"(W3 fix)"
        )
    elif _direction == "decrease":
        notes.append("direction locked: recovery_AUC declared 'decrease'")

    notes.append(
        f"PR2b thresholds: coupling_corr>={criteria.get('reject_if_coupling_corr_abs_min')} "
        f"artifact_rate>={criteria.get('reject_if_artifact_rate_min')} "
        f"(conjunctive={criteria.get('conjunctive')})"
    )

    # --- 2. Criterion immutability (R-0.1 / R-0.4) ---
    summary = f4b.get("summary", {})
    if not summary:
        failures.append("execution JSON has no 'summary' block")
        return failures, warnings, notes
    ex_rule = summary.get("reject_rule", {}) or {}
    pairs = (
        ("reject_if_coupling_corr_abs_min", "coupling_corr_min"),
        ("reject_if_artifact_rate_min", "artifact_rate_min"),
    )
    for mk, ek in pairs:
        pr_v = criteria.get(mk)
        ex_v = ex_rule.get(ek)
        if pr_v is None or ex_v is None:
            failures.append(f"{mk} missing (manifest={pr_v!r} exec={ex_v!r})")
        elif abs(float(pr_v) - float(ex_v)) > 1e-9:
            failures.append(
                f"{mk} mismatch: prereg={pr_v} exec={ex_v} "
                f"— criteria drifted after registration (R-0.1 violation)"
            )
        else:
            notes.append(f"{mk} consistent: {ex_v}")

    modified = pr2b.get("criteria_modified_after_results")
    if modified is True:
        failures.append(
            "preregistered.PR2b.criteria_modified_after_results=true — "
            "a pre-execution rejection must not modify its criteria post-hoc (R-0.4)"
        )
    elif modified is False:
        notes.append("criteria_modified_after_results=false (frozen)")
    else:
        warnings.append(
            f"preregistered.PR2b.criteria_modified_after_results="
            f"{modified!r} — expected an explicit boolean"
        )

    # --- 3. Independent recomputation from all_results ---
    rows = f4b.get("all_results", [])
    if not rows:
        failures.append("execution JSON has no all_results block")
        return failures, warnings, notes

    d_ra_b = [r.get("d_recovery_auc_bridge") for r in rows if r.get("d_recovery_auc_bridge") is not None]
    d_bf_b = [r.get("d_bridge_fraction_bridge") for r in rows if r.get("d_bridge_fraction_bridge") is not None]
    d_ra_n = [r.get("d_recovery_auc_nonbridge") for r in rows if r.get("d_recovery_auc_nonbridge") is not None]
    d_bf_n = [r.get("d_bridge_fraction_nonbridge") for r in rows if r.get("d_bridge_fraction_nonbridge") is not None]
    rise = [r.get("recovery_auc_rises_on_bridge_deletion") for r in rows]

    if not d_ra_b or not d_bf_b:
        failures.append("all_results carries no d_recovery_auc / d_bridge_fraction values")
        return failures, warnings, notes

    n = len(rise)
    recomputed_artifact = (sum(1 for v in rise if v) / n) if n else 0.0
    # Pooled sample: both arms, so var(d_bridge_fraction) is not compressed.
    corr_pooled = _pearson(d_bf_b + d_bf_n, d_ra_b + d_ra_n)
    corr_bridge = _pearson(d_bf_b, d_ra_b)

    measures = summary.get("measurements", {}) or {}
    rec = ver.get("power_diagnostic", {}) or {}

    ex_artifact = ver.get("artifact_rate")
    if ex_artifact is not None and abs(float(ex_artifact) - recomputed_artifact) > 1e-4:
        failures.append(
            f"summary artifact_rate={ex_artifact} disagrees with recomputed rate "
            f"from all_results ({recomputed_artifact:.6f}) — outcome tampered"
        )
    else:
        notes.append(
            f"artifact_rate {recomputed_artifact:.4f} reproduced from all_results "
            f"({sum(1 for v in rise if v)}/{n})"
        )

    ex_pooled = rec.get("corr_pooled_both_arms")
    if ex_pooled is not None and corr_pooled is not None \
            and abs(float(ex_pooled) - corr_pooled) > 1e-3:
        failures.append(
            f"recorded pooled corr={ex_pooled} disagrees with recomputed "
            f"{corr_pooled:+.6f} — coupling statistic tampered"
        )
    else:
        notes.append(f"pooled coupling corr {corr_pooled:+.4f} reproduced from all_results"
                     if corr_pooled is not None
                     else "pooled coupling corr unavailable (insufficient variance)")

    # --- 4. Decision integrity ---
    decision = ver.get("decision", "")
    rule_verdict = ver.get("rule_verdict")
    underpowered = ver.get("rule_underpowered")
    artifact_min = float(criteria.get("reject_if_artifact_rate_min", 0.90))

    if not decision.startswith("REJECT"):
        failures.append(
            f"preregistered.PR2b.verification.decision={decision!r} — "
            f"expected a REJECT decision (the substitution was declined)"
        )
    else:
        notes.append(f"decision recorded: {decision}")

    # If the decision overrides the rule, the override must be flagged.
    if rule_verdict and str(rule_verdict).upper() != "REJECT":
        if not underpowered:
            failures.append(
                f"decision=REJECT overrides rule_verdict={rule_verdict!r} but "
                f"rule_underpowered is not true — a silent override of the gate's "
                f"own verdict must be declared, not implied"
            )
        else:
            notes.append(
                f"decision overrides rule_verdict={rule_verdict} with "
                f"rule_underpowered=true declared"
            )

    # The rejection must be supported by at least the artifact gate.
    artifact_hit = recomputed_artifact >= artifact_min
    coupling_min = float(criteria.get("reject_if_coupling_corr_abs_min", 0.50))
    coupling_hit = (corr_bridge is not None and abs(corr_bridge) >= coupling_min)
    if not (artifact_hit or coupling_hit):
        failures.append(
            f"recorded REJECT is unsupported: recomputed artifact rate "
            f"{recomputed_artifact:.3f} < {artifact_min} and |bridge-arm corr| "
            f"{abs(corr_bridge) if corr_bridge else 0:.3f} < {coupling_min}"
        )
    elif measures:
        warnings.append(
            f"PR-2b pre-execution REJECTION preserved per R-0.4: artifact rate "
            f"{recomputed_artifact:.1%} >= {artifact_min:.0%}, pooled coupling "
            f"{corr_pooled:+.4f} (rule sample underpowered at "
            f"{corr_bridge:+.4f}). recovery_AUC is definitionally coupled to "
            f"delete_bridge via modulator_Ra and must NOT be substituted in as a "
            f"PR-2 consequence metric. The rejection is a substrate boundary, not a "
            f"failure to try harder."
        )

    return failures, warnings, notes


def _run_injections(claims: dict, f4b: dict) -> tuple[int, int]:
    bad = 0
    n_inj = 0

    def expect(name, apply_fn):
        nonlocal bad, n_inj
        n_inj += 1
        orig_c = copy.deepcopy(claims)
        orig_r = copy.deepcopy(f4b)
        try:
            apply_fn()
            failures, _w, _n = _check_pr2b(claims, f4b)
        finally:
            claims.clear(); claims.update(orig_c)
            f4b.clear(); f4b.update(orig_r)
        ok = len(failures) > 0
        if ok:
            print(f"    [PASS] injecting: {name}")
        else:
            bad += 1
            print(f"    [FAIL] injecting: {name} -> GATE STAYED GREEN")

    def _patch_threshold():
        pr = claims.get("preregistered", {}).get("PR2b", {})
        crit = pr.get("success_criteria", {})
        if isinstance(crit, dict):
            crit["reject_if_artifact_rate_min"] = 0.99

    expect("raise artifact threshold 0.90 -> 0.99 in manifest -> criteria drift -> FAIL",
           _patch_threshold)

    def _patch_decision():
        v = claims.get("preregistered", {}).get("PR2b", {}).get("verification", {})
        if isinstance(v, dict):
            v["decision"] = "ACCEPT"
            v["rule_underpowered"] = False

    expect("flip decision to ACCEPT + drop rule_underpowered -> FAIL", _patch_decision)

    def _patch_modified():
        pr = claims.get("preregistered", {}).get("PR2b", {})
        pr["criteria_modified_after_results"] = True

    expect("set criteria_modified_after_results=true -> R-0.4 violation -> FAIL",
           _patch_modified)

    def _patch_rows():
        # Force every bridge arm to NOT rise so the recomputed artifact rate collapses.
        for r in f4b.get("all_results", []):
            r["recovery_auc_rises_on_bridge_deletion"] = False
            d = r.get("d_recovery_auc_bridge")
            if isinstance(d, (int, float)):
                r["d_recovery_auc_bridge"] = -abs(d) - 1e-6

    expect("kill all bridge-arm rises in all_results -> recomputed rate no longer "
           "supports REJECT -> FAIL", _patch_rows)

    return bad, n_inj


def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — PR-2b metric-substitution pre-check integrity")
    ap.add_argument("--claims", metavar="PATH", default=str(DEFAULT_CLAIMS))
    ap.add_argument("--f4b-result", metavar="PATH", default=str(DEFAULT_F4B_RESULT))
    ap.add_argument("--json-out", metavar="PATH")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    claims_path = Path(args.claims)
    f4b_path = Path(args.f4b_result)

    if not claims_path.exists():
        print(f"{GATE_LABEL}: FAIL — claims file not found: {claims_path}")
        return 1
    if not f4b_path.exists():
        print(f"{GATE_LABEL}: FAIL — F4b result not found: {f4b_path}\n"
              f"  Run: python scripts/f4b_metric_substitution_check.py --seed 42")
        return 1

    claims = _load_json(claims_path)
    f4b = _load_json(f4b_path)

    n_inj = 0
    inj_bad = 0

    if not args.quiet:
        print(f"{GATE_LABEL} — PR-2b metric-substitution pre-check integrity")
        print(f"  claims : {claims_path}")
        print(f"  F4b out: {f4b_path}")
        print()

    failures, warnings, notes = _check_pr2b(claims, f4b)

    if not args.quiet:
        for note in notes:
            print(f"  ✓ {note}")
        for warn in warnings:
            print(f"  ~ WARN {warn}")
        for fail in failures:
            print(f"  ✗ {fail}")
        print()

        print("  -- fail-closed injections --")
        inj_bad, n_inj = _run_injections(claims, f4b)
        if inj_bad:
            print(f"{GATE_LABEL}: FAIL — {inj_bad}/{n_inj} injections did not turn red")
            return 1
        print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
        print()

    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "claims_path": str(claims_path),
        "f4b_result_path": str(f4b_path),
        "counts": {"fail": len(failures), "warn": len(warnings), "note": len(notes)},
        "notes": notes,
        "warnings": warnings,
        "failures": failures,
        "injections": {"total": n_inj if not args.quiet else 0,
                       "bad": inj_bad if not args.quiet else 0},
    }
    out_path = Path(args.json_out) if args.json_out else SCRIPTS / "_gate47_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    if not args.quiet:
        print(f"  report: {out_path}")

    if failures:
        print(f"\n{GATE_LABEL}: FAIL — {len(failures)} integrity violation(s)")
        return 1
    if warnings:
        print(f"\n{GATE_LABEL}: PASS — PR-2b pre-execution REJECTION consistent and locked "
              f"({len(warnings)} warning(s))")
    else:
        print(f"\n{GATE_LABEL}: PASS — PR-2b manifest consistent with execution")
    return 0


if __name__ == "__main__":
    sys.exit(main())
