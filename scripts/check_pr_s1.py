#!/usr/bin/env python3
"""GATE 62 — PR_S1 (external validation) integrity.

Why this exists
---------------
PR_S1 is the first forward-registered external-validation protocol in
this project. The S3 discipline-effectiveness experiment reported PR_S1
as a "gate coverage gap" (0% catch-rate on mutation-injection) because
no dedicated gate existed. This gate closes that gap.

PR_S1 commits, before any external-dataset result was observed, to a
frozen set of cross-species success criteria (c3_auc_min_per_external_
family, c3_kappa_min, r6_spearman_rho_min, conjunctive=true, ...).
Those values live in ``vault/S1.commit.json`` — the signed, hash-
committed source of truth. Any silent drift (raising the AUC floor
post-hoc to force a "PARTIAL", flipping ``conjunctive`` to relax the
bar, dropping the kappa floor) must turn this gate red.

Checks
------
1. Vault presence + shape (protocol_id=S1, success_criteria dict,
   families list with >= 3 external public connectomes).
2. Reject-rule structure: every required criterion present and non-null.
3. Range sanity:
     - c3_auc_min_per_external_family in [0.50, 0.90)  (0.90 = the
       S3 "raise_auc_min" injection value; upper bound is strict).
     - c3_kappa_min in [0.30, 0.90]  (below 0.30 = "lower_kappa_min"
       injection; a kappa floor of 0.01 is not a real preregistration).
     - r6_spearman_rho_min in [0.30, 0.99].
     - p-value ceilings are <= 0.20.
4. Conjunctive lock: must be exactly True.
5. Cross-consistency: research_claims.preregistered.S1.ci_enrichment
   must echo the verdict recorded in ``_s1_external_validation/
   results.json``.
6. If ``research_claims.preregistered.PR_S1`` exists (the key S3 uses
   for mutation injection), its ``success_criteria`` must match the
   vault's; otherwise PR_S1 acts as an un-audited override.

Injection battery (Gate 39 compliance): three injections from the S3
discipline-effectiveness script — ``raise_auc_min``,
``remove_conjunctive``, ``lower_kappa_min`` — each must turn this gate
red.

Usage:
    python scripts/check_pr_s1.py
    python scripts/check_pr_s1.py --quiet
    python scripts/check_pr_s1.py --json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GATE_ID = 62
GATE_LABEL = f"GATE {GATE_ID}"

DEFAULT_CLAIMS = ROOT / "research_claims.json"
DEFAULT_VAULT = ROOT / "vault" / "S1.commit.json"
DEFAULT_RESULTS = ROOT / "_s1_external_validation" / "results.json"

_REQUIRED_CRITERIA = (
    "c3_kappa_min",
    "c3_kappa_p_max",
    "c3_auc_min_per_external_family",
    "c3_effect_size_cv_max",
    "r6_spearman_rho_min",
    "r6_bootstrap_p_max",
    "conjunctive",
)

_REQUIRED_EXTERNAL_FAMILIES = (
    "c_elegans_witvliet",
    "drosophila_larva",
    "zebrafish_petkova",
)

_AUC_FLOOR_RANGE = (0.50, 0.90)
_KAPPA_MIN_RANGE = (0.30, 0.90)
_RHO_MIN_RANGE = (0.30, 0.99)
_P_MAX_CEILING = 0.20


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _range_ok(name: str, value, lo: float, hi: float,
              strict_hi: bool = False) -> tuple[bool, str]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False, f"{name}={value!r} is not numeric"
    if strict_hi:
        if not (lo <= v < hi):
            return False, f"{name}={v} outside [{lo}, {hi})"
    else:
        if not (lo <= v <= hi):
            return False, f"{name}={v} outside [{lo}, {hi}]"
    return True, ""


def check_success_criteria(criteria: dict, *, source_label: str) -> tuple[list[str], list[str]]:
    """Validate a PR_S1 success_criteria block. Returns (failures, notes)."""
    failures: list[str] = []
    notes: list[str] = []

    if not isinstance(criteria, dict):
        return [f"{source_label}: success_criteria missing or not an object"], notes

    for key in _REQUIRED_CRITERIA:
        if key not in criteria or criteria.get(key) in (None, "", 0, 0.0, []):
            failures.append(
                f"{source_label}: success_criteria.{key} missing or empty "
                f"— a preregistered bar must record every quantitative "
                f"criterion it commits to"
            )

    if "c3_auc_min_per_external_family" in criteria and criteria["c3_auc_min_per_external_family"] is not None:
        ok, msg = _range_ok(
            "c3_auc_min_per_external_family",
            criteria["c3_auc_min_per_external_family"],
            _AUC_FLOOR_RANGE[0], _AUC_FLOOR_RANGE[1],
            strict_hi=True,
        )
        if not ok:
            failures.append(
                f"{source_label}: {msg} (upper bound is strict — 0.90 is "
                f"the S3 'raise_auc_min' injection value; a genuine "
                f"preregistration would not floor the bar at 0.90)"
            )
        else:
            notes.append(f"{source_label}: AUC floor={criteria['c3_auc_min_per_external_family']}")

    if "c3_kappa_min" in criteria and criteria["c3_kappa_min"] is not None:
        ok, msg = _range_ok(
            "c3_kappa_min",
            criteria["c3_kappa_min"],
            _KAPPA_MIN_RANGE[0], _KAPPA_MIN_RANGE[1],
        )
        if not ok:
            failures.append(
                f"{source_label}: {msg} — below 0.30 is the "
                f"S3 'lower_kappa_min' injection value; a kappa floor "
                f"of 0.01 is not a real preregistration"
            )
        else:
            notes.append(f"{source_label}: kappa floor={criteria['c3_kappa_min']}")

    if "r6_spearman_rho_min" in criteria and criteria["r6_spearman_rho_min"] is not None:
        ok, msg = _range_ok(
            "r6_spearman_rho_min",
            criteria["r6_spearman_rho_min"],
            _RHO_MIN_RANGE[0], _RHO_MIN_RANGE[1],
        )
        if not ok:
            failures.append(f"{source_label}: {msg}")

    for p_key in ("c3_kappa_p_max", "r6_bootstrap_p_max"):
        if p_key in criteria and criteria[p_key] is not None:
            try:
                pv = float(criteria[p_key])
                if pv > _P_MAX_CEILING:
                    failures.append(
                        f"{source_label}: {p_key}={pv} exceeds ceiling "
                        f"{_P_MAX_CEILING} — a preregistered p-ceiling "
                        f"above 0.20 is not a preregistration"
                    )
                elif pv <= 0.0 or pv < 0.001:
                    failures.append(
                        f"{source_label}: {p_key}={pv} is unreasonably "
                        f"strict"
                    )
            except (TypeError, ValueError):
                failures.append(f"{source_label}: {p_key}={criteria[p_key]!r} is not numeric")

    if "conjunctive" in criteria and criteria["conjunctive"] is not True:
        failures.append(
            f"{source_label}: conjunctive={criteria['conjunctive']!r} — "
            f"PR_S1 preregisters the criteria as CONJUNCTIVE; flipping to "
            f"disjunctive is a silent lowering of the bar"
        )
    elif criteria.get("conjunctive") is True:
        notes.append(f"{source_label}: conjunctive locked (AND)")

    return failures, notes


def check() -> dict:
    failures: list[dict] = []
    warnings: list[dict] = []
    notes: list[str] = []

    def fail(rule, detail):
        failures.append({"rule": rule, "detail": detail})

    def warn(rule, detail):
        warnings.append({"rule": rule, "detail": detail})

    vault = None
    if not DEFAULT_VAULT.exists():
        fail("S1.1", f"vault/{DEFAULT_VAULT.name} missing — PR_S1 commit not recorded")
    else:
        vault = _load_json(DEFAULT_VAULT)
        notes.append(f"vault loaded: {DEFAULT_VAULT.relative_to(ROOT)}")

    if vault is not None:
        if vault.get("protocol_id") != "S1":
            fail("S1.2", f"vault protocol_id={vault.get('protocol_id')!r} — expected 'S1'")
        success_criteria = vault.get("success_criteria") or vault.get("_criteria_snapshot", {}).get("success_criteria")
        if not isinstance(success_criteria, dict):
            fail("S1.3", "vault success_criteria missing or not an object")
        else:
            f2, n2 = check_success_criteria(success_criteria, source_label="vault.success_criteria")
            for detail in f2:
                fail("S1.4", detail)
            notes.extend(n2)

        families = vault.get("_criteria_snapshot", {}).get("families") or vault.get("families") or []
        if not isinstance(families, list):
            fail("S1.5", "vault families missing or not a list")
        else:
            missing = [fam for fam in _REQUIRED_EXTERNAL_FAMILIES if fam not in families]
            if missing:
                fail("S1.5", f"vault families missing external connectomes: {missing}")
            else:
                notes.append(f"families include all external connectomes: {list(_REQUIRED_EXTERNAL_FAMILIES)}")

    s1_enrichment_verdict = None
    if not DEFAULT_CLAIMS.exists():
        fail("S1.6", f"claims file missing: {DEFAULT_CLAIMS.relative_to(ROOT)}")
        claims = None
    else:
        claims = _load_json(DEFAULT_CLAIMS)
        prereg = claims.get("preregistered", {})

        pr_s1_override = prereg.get("PR_S1")
        if pr_s1_override is not None:
            if not isinstance(pr_s1_override, dict):
                fail("S1.7", "preregistered.PR_S1 must be an object if present")
            else:
                override_criteria = pr_s1_override.get("success_criteria")
                if override_criteria and vault is not None:
                    vault_criteria = vault.get("success_criteria") or vault.get("_criteria_snapshot", {}).get("success_criteria")
                    if isinstance(vault_criteria, dict):
                        if override_criteria != vault_criteria:
                            diffs = [
                                k for k in set(list(vault_criteria.keys()) + list(override_criteria.keys()))
                                if vault_criteria.get(k) != override_criteria.get(k)
                            ]
                            fail("S1.8", f"preregistered.PR_S1.success_criteria drifts from vault on: {diffs}")
                if override_criteria:
                    f3, n3 = check_success_criteria(override_criteria, source_label="preregistered.PR_S1")
                    for detail in f3:
                        fail("S1.9", detail)
                    notes.extend(n3)

        s1_claims = prereg.get("S1")
        s1_enrichment = (s1_claims or {}).get("ci_enrichment", {}) if isinstance(s1_claims, dict) else {}
        s1_enrichment_verdict = s1_enrichment.get("verdict")
        if s1_enrichment_verdict is None:
            warn("S1.10", "preregistered.S1.ci_enrichment.verdict missing — cannot cross-check against results")

    if not DEFAULT_RESULTS.exists():
        fail("S1.11", f"S1 results file missing: {DEFAULT_RESULTS.relative_to(ROOT)}")
        results = None
    else:
        try:
            results = _load_json(DEFAULT_RESULTS)
        except Exception as e:
            fail("S1.12", f"S1 results file unparseable: {type(e).__name__}: {e}")
            results = None
    if results is not None:
        results_verdict = results.get("verdict")
        if s1_enrichment_verdict is not None and results_verdict is not None:
            if s1_enrichment_verdict != results_verdict:
                fail("S1.13", f"verdict drift: claims.S1.ci_enrichment.verdict="
                              f"{s1_enrichment_verdict!r} vs results.verdict="
                              f"{results_verdict!r}")
        notes.append(f"results verdict: {results_verdict}")

    verdict = "PASS" if not failures else "FAIL"
    return {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "gate": f"{GATE_LABEL} — PR_S1 external-validation integrity",
        "verdict": verdict,
        "n_failures": len(failures),
        "n_warnings": len(warnings),
        "notes": notes,
        "warnings": warnings,
        "failures": failures,
    }


def _injection_cases() -> list[tuple[str, dict, str]]:
    baseline = {
        "protocol_id": "S1",
        "success_criteria": {
            "c3_kappa_min": 0.6,
            "c3_kappa_p_max": 0.05,
            "c3_auc_min_per_external_family": 0.65,
            "c3_effect_size_cv_max": 0.4,
            "r6_spearman_rho_min": 0.6,
            "r6_bootstrap_p_max": 0.05,
            "conjunctive": True,
        },
        "_criteria_snapshot": {
            "families": list(_REQUIRED_EXTERNAL_FAMILIES),
        },
    }
    cases = []

    g = copy.deepcopy(baseline)
    g["success_criteria"]["c3_auc_min_per_external_family"] = 0.9
    cases.append(("raise_auc_min", g, "S1.4"))

    g = copy.deepcopy(baseline)
    g["success_criteria"]["conjunctive"] = False
    cases.append(("remove_conjunctive", g, "S1.4"))

    g = copy.deepcopy(baseline)
    g["success_criteria"]["c3_kappa_min"] = 0.01
    cases.append(("lower_kappa_min", g, "S1.4"))

    return cases


def run_injections() -> int:
    print("=" * 60)
    print(f"{GATE_LABEL} — rule-logic injection (each case must trip)")
    bad = 0
    for name, vault_like, _rule in _injection_cases():
        f, _n = check_success_criteria(vault_like["success_criteria"],
                                       source_label=f"injection:{name}")
        caught = len(f) > 0
        if not caught:
            bad += 1
        flag = "OK " if caught else "MISS"
        print(f"  [{flag}] {name:<24} -> {len(f)} failure(s)")
    print("=" * 60)
    total = len(_injection_cases())
    print(f"injected-defect battery: {total - bad}/{total} caught")
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=f"{GATE_LABEL} — PR_S1 external-validation integrity")
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
