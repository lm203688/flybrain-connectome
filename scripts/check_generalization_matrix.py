#!/usr/bin/env python3
"""GATE 44 — cross-family generalization boundary (PR-3 integrity + outcome).

Why this exists
---------------
PR-3 in PREREGISTRATION_PROTOCOL_v1.md requires that the R1 mechanism
(n_bridges / bridge_fraction / n_articulation_points / edge_connectivity →
drop_magnitude) generalise across graph families and scales, not just the
project-synthetic family at n_nodes=10. Two things must hold:

  (a) Manifest ↔ execution integrity (R-0.2): the five families, the n_nodes
      set, the threshold, the features, the AUC floor and the min-families
      rule in research_claims.json.preregistered.PR3 must match the execution
      JSON verbatim. Gate 44 fails on any drift.

  (b) Outcome honesty (R-0.4): the verdict — which families pass, which
      fail, where the boundary is — is recorded and NOT rescued by moving
      the criteria. Failure is a real scientific result (the claim narrows
      to "within project-synthetic at n=10").

Gate 44 is a **pragmatic** gate: it stays GREEN when the preregistration is
mechanically honest AND the negative outcome is preserved verbatim; it goes
RED when someone tampers with the criteria, drops the real-connectome
family from the test, or re-labels a FAIL as a PASS.

Injection battery (3 injections prove it can turn red):
  1. Remove `malecns_subgraph` from the matrix → FAIL (must include real).
  2. Reweight the `success_criteria.auc_min` upward to force a pass → FAIL.
  3. Flip verdict from FAIL to PASS without changing the data → FAIL.

Usage:
    python scripts/check_generalization_matrix.py
    python scripts/check_generalization_matrix.py --quiet
    python scripts/check_generalization_matrix.py --json-out report.json
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
DEFAULT_F3_RESULT = ROOT / "_f3_generalization" / "f3_generalization.json"

GATE_ID = 44
GATE_LABEL = f"GATE {GATE_ID}"

# The five families PR-3 preregisters. MaleCNS is the real-data anchor.
_REQUIRED_FAMILIES = (
    "project_synthetic", "erdos_renyi", "barabasi_albert",
    "watts_strogatz", "malecns_subgraph",
)
_REQUIRED_REAL = "malecns_subgraph"


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_f3(claims: dict, f3_result: dict) -> tuple[list[str], list[str], list[str]]:
    """Return (failures, warnings, notes) for the F3 / PR-3 preregistration block."""
    failures: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    # --- 1. Manifest presence ---
    prereg = claims.get("preregistered", {})
    if not prereg:
        failures.append("research_claims.json has no top-level 'preregistered' block")
        return failures, warnings, notes
    pr3 = prereg.get("PR3")
    if not isinstance(pr3, dict):
        failures.append("preregistered.PR3 missing or not an object")
        return failures, warnings, notes
    notes.append(f"preregistered.PR3 present: {len(pr3.get('families', []))} families, "
                 f"{len(pr3.get('n_nodes_set', []))} n_nodes")

    # --- 2. Execution JSON presence + shape ---
    params = f3_result.get("params", {})
    matrix = f3_result.get("matrix", {})
    if not params:
        failures.append("execution JSON has no params block")
        return failures, warnings, notes
    if not matrix:
        failures.append("execution JSON has no matrix block")
        return failures, warnings, notes

    # --- 3. Family set exact match (as a set; order in the manifest can vary) ---
    pr_families = set(pr3.get("families", []))
    ex_families = set(matrix.keys())
    if pr_families != ex_families:
        failures.append(
            f"family set mismatch: prereg={sorted(pr_families)} "
            f"execution={sorted(ex_families)}"
        )
    else:
        notes.append(f"families frozen: {len(pr_families)} matched")

    # --- 4. Real-connectome family MUST be present in both manifest and matrix ---
    if _REQUIRED_REAL not in pr_families:
        failures.append(
            f"PR-3 manifest must include {_REQUIRED_REAL} (real connectome anchor)"
        )
    if _REQUIRED_REAL not in matrix:
        failures.append(
            f"execution matrix must include {_REQUIRED_REAL} (real connectome anchor)"
        )
    else:
        notes.append(f"real family {_REQUIRED_REAL} present in matrix")

    # --- 5. n_nodes set: execution must be a subset of preregistered ---
    pr_n = set(pr3.get("n_nodes_set", []))
    # Collect n_nodes from every cell of the matrix
    ex_n: set[int] = set()
    for fam_cells in matrix.values():
        if isinstance(fam_cells, dict):
            for k in fam_cells.keys():
                try:
                    ex_n.add(int(k))
                except (ValueError, TypeError):
                    pass
    if ex_n and ex_n <= pr_n:
        notes.append(f"n_nodes set consistent: {sorted(ex_n)} ⊆ prereg {sorted(pr_n)}")
    else:
        failures.append(
            f"n_nodes set drift: prereg={sorted(pr_n)} execution={sorted(ex_n)}"
        )

    # --- 6. Feature set exact match ---
    pr_feats = list(pr3.get("families", []))  # placeholder to avoid confusing with features
    pr_feats = list(pr3.get("features", [])) if "features" in pr3 else []
    ex_feats = list(params.get("features", []))
    if pr_feats:
        if pr_feats != ex_feats:
            failures.append(
                f"feature set mismatch: prereg={pr_feats} execution={ex_feats}"
            )
        else:
            notes.append(f"features frozen: {len(pr_feats)} matched")

    # --- 7. Threshold and AUC floor match ---
    pr_thr = pr3.get("threshold")
    ex_thr = params.get("threshold")
    if pr_thr is not None and ex_thr is not None:
        if abs(float(pr_thr) - float(ex_thr)) > 1e-9:
            failures.append(
                f"threshold mismatch: prereg={pr_thr} exec={ex_thr}"
            )
        else:
            notes.append(f"threshold consistent: {ex_thr}")

    pr_auc = (pr3.get("success_criteria", {}) or {}).get("auc_min")
    ex_auc = params.get("auc_min")
    if pr_auc is not None and ex_auc is not None:
        if abs(float(pr_auc) - float(ex_auc)) > 1e-9:
            failures.append(
                f"auc_min mismatch: prereg={pr_auc} exec={ex_auc}"
            )
        else:
            notes.append(f"auc_min consistent: {ex_auc}")

    # --- 8. Outcome honesty (R-0.4): report verdict as a WARN when not PASS ---
    n_passing = f3_result.get("n_families_passing")
    real_pass = f3_result.get("real_family_passing")
    verdict = f3_result.get("verdict")
    crit = f3_result.get("success_criteria", {}) or {}

    # Independently recompute the pass condition from the underlying counts.
    # A "PASS" verdict is only honest when the two preregistered conditions
    # are actually met; otherwise the verdict string is lying and we FAIL.
    min_fams = int(crit.get("min_families_auc_consistent",
                            (pr3.get("success_criteria", {}) or {}).get(
                                "min_families_auc_direction_consistent", 3)))
    must_real = bool(crit.get("must_include_real",
                              (pr3.get("success_criteria", {}) or {}).get(
                                  "must_include_real", True)))
    data_passes = (
        n_passing is not None and int(n_passing) >= min_fams
        and (not must_real or real_pass is True)
    )
    if verdict == "PASS" and not data_passes:
        failures.append(
            f"verdict says PASS but data contradicts: "
            f"n_families_passing={n_passing} < {min_fams} or "
            f"real_family_passing={real_pass} (must_include_real={must_real})"
        )
    elif verdict in ("FAIL", "NARROW", "INCONCLUSIVE") and data_passes:
        failures.append(
            f"verdict says {verdict} but data meets criteria: "
            f"n_families_passing={n_passing} >= {min_fams} and "
            f"real_family_passing={real_pass}"
        )

    if verdict == "PASS":
        notes.append(f"F3 generalization: PASS "
                     f"({n_passing} families, real={real_pass})")
    elif verdict in ("FAIL", "NARROW", "INCONCLUSIVE"):
        warnings.append(
            f"F3 generalization: {verdict} — {n_passing} families pass, "
            f"real family pass={real_pass}. Per R-0.4 the negative outcome is "
            f"preserved verbatim and the claim is NARROWED to the fitted family; "
            f"do NOT move the criteria to force a pass."
        )
    else:
        warnings.append(f"F3 verdict={verdict!r} — unknown verdict string")

    return failures, warnings, notes


def _run_injections(claims: dict, f3_result: dict) -> tuple[int, int]:
    """Three injections: tamper families, reweight criteria, flip verdict."""
    bad = 0
    n_inj = 0

    def expect(name, apply_fn, checker):
        nonlocal bad, n_inj
        n_inj += 1
        orig_c = copy.deepcopy(claims)
        orig_r = copy.deepcopy(f3_result)
        try:
            apply_fn()
            failures, _w, _n = checker(claims, f3_result)
        finally:
            claims.clear(); claims.update(orig_c)
            f3_result.clear(); f3_result.update(orig_r)
        ok = len(failures) > 0
        if ok:
            print(f"    [PASS] injecting: {name}")
        else:
            bad += 1
            print(f"    [FAIL] injecting: {name} -> GATE STAYED GREEN")

    def _checker(c, r):
        f, w, n = _check_f3(c, r)
        return f, w, n

    # --- Injection 1: drop the real-connectome family from the matrix ---
    def _patch_drop_real():
        r = f3_result
        if "malecns_subgraph" in r.get("matrix", {}):
            r["matrix"].pop("malecns_subgraph", None)

    expect("drop malecns_subgraph from matrix -> real family missing -> FAIL",
           _patch_drop_real, _checker)

    # --- Injection 2: reweight auc_min upward to force a pass ---
    def _patch_auc_floor():
        r = f3_result
        r["params"]["auc_min"] = 0.99  # absurdly high — nothing will pass
        r["success_criteria"]["auc_min"] = 0.99
        r["verdict"] = "PASS"  # try to sneak it through as PASS
        r["n_families_passing"] = 5
        r["real_family_passing"] = True

    expect("reweight auc_min=0.99 + flip verdict=PASS -> mismatch vs manifest -> FAIL",
           _patch_auc_floor, _checker)

    # --- Injection 3: silently flip FAIL → PASS while keeping the real data ---
    def _patch_flip_verdict():
        r = f3_result
        r["verdict"] = "PASS"

    expect("flip verdict FAIL→PASS with data unchanged -> criterion check fires -> FAIL",
           _patch_flip_verdict, _checker)

    return bad, n_inj


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — cross-family generalization boundary (PR-3)")
    ap.add_argument("--claims", metavar="PATH", default=str(DEFAULT_CLAIMS))
    ap.add_argument("--f3-result", metavar="PATH", default=str(DEFAULT_F3_RESULT))
    ap.add_argument("--json-out", metavar="PATH")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    claims_path = Path(args.claims)
    f3_path = Path(args.f3_result)

    if not claims_path.exists():
        print(f"{GATE_LABEL}: FAIL — claims file not found: {claims_path}")
        return 1
    if not f3_path.exists():
        print(f"{GATE_LABEL}: FAIL — F3 execution result not found: {f3_path}\n"
              f"  Run: python scripts/f3_generalization_matrix.py --seed 42")
        return 1

    claims = _load_json(claims_path)
    f3_result = _load_json(f3_path)

    n_inj = 0
    inj_bad = 0

    if not args.quiet:
        print(f"{GATE_LABEL} — cross-family generalization boundary (PR-3)")
        print(f"  claims : {claims_path}")
        print(f"  F3 out : {f3_path}")
        print()

    failures, warnings, notes = _check_f3(claims, f3_result)

    if not args.quiet:
        for note in notes:
            print(f"  ✓ {note}")
        for warn in warnings:
            print(f"  ~ WARN {warn}")
        for fail in failures:
            print(f"  ✗ {fail}")
        print()

        print("  -- fail-closed injections --")
        inj_bad, n_inj = _run_injections(claims, f3_result)
        if inj_bad:
            print(f"{GATE_LABEL}: FAIL — {inj_bad}/{n_inj} injections did not turn red")
            return 1
        print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
        print()

    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "claims_path": str(claims_path),
        "f3_result_path": str(f3_path),
        "counts": {"fail": len(failures), "warn": len(warnings), "note": len(notes)},
        "notes": notes,
        "warnings": warnings,
        "failures": failures,
        "injections": {"total": n_inj if not args.quiet else 0,
                       "bad": inj_bad if not args.quiet else 0},
    }
    out_path = Path(args.json_out) if args.json_out else SCRIPTS / "_gate44_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    if not args.quiet:
        print(f"  report: {out_path}")

    if failures:
        print(f"\n{GATE_LABEL}: FAIL — {len(failures)} integrity violation(s)")
        return 1
    if warnings:
        print(f"\n{GATE_LABEL}: PASS — PR-3 mechanism integrity OK "
              f"({len(warnings)} outcome warning(s) — negative result preserved per R-0.4)")
    else:
        print(f"\n{GATE_LABEL}: PASS — PR-3 preregistration consistent AND "
              f"generalization target met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
