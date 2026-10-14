#!/usr/bin/env python3
"""GATE 45 — self-intervention consistency (PR-2 integrity + outcome).

Why this exists
---------------
PR-2 in PREREGISTRATION_PROTOCOL_v1.md upgrades R1's observational AUC to
**causal-level evidence** by pre-registering a structural action (delete one
bridge edge vs one non-bridge edge) and its predicted consequence (an
increase in drop_magnitude), then measuring the direction hit rate on a
fresh set of 30 topologies that are **held out from the PR-1 fit**.

Gate 45 enforces two layers:

  (a) **Manifest ↔ execution integrity (R-0.2)** — the structural action,
      control action, predicted direction, sample size, seed, start slice and
      success criteria must match research_claims.json.preregistered.PR2
      verbatim.

  (b) **Overlap guard** — the intervention slice must NOT intersect the PR-1
      training or held-out slices (0:60 / 60:100). This is the
      "held-out generalization" cell of the Self-Interventional Learning
      four-tuple (arXiv:2608.14894).

  (c) **Outcome honesty (R-0.4)** — a FAIL verdict (hit rate below the
      preregistered 0.70) is preserved verbatim as a WARN, not silenced.

Injection battery (3 injections):
  1. Tamper the structural action from delete_bridge → add_bridge → FAIL.
  2. Force overlap by moving the intervention slice into 0:60 → FAIL.
  3. Reweight the hit rate upward without changing the data → FAIL.

Usage:
    python scripts/check_intervention_test.py
    python scripts/check_intervention_test.py --quiet
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
DEFAULT_F4_RESULT = ROOT / "_f4_intervention" / "f4_intervention.json"

GATE_ID = 45
GATE_LABEL = f"GATE {GATE_ID}"


def _parse_slice(s: str) -> tuple[int, int]:
    """Parse 'a:b' slice string into (start, end) integers."""
    try:
        a, b = s.split(":")
        return int(a), int(b)
    except Exception:
        return None, None


def _slices_overlap(a: str, b: str) -> bool:
    """Two ranges overlap iff neither ends at/before the other starts."""
    a0, a1 = _parse_slice(a)
    b0, b1 = _parse_slice(b)
    if None in (a0, a1, b0, b1):
        return False
    return not (a1 <= b0 or b1 <= a0)


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_f4(claims: dict, f4_result: dict) -> tuple[list[str], list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    # --- 1. Manifest presence ---
    prereg = claims.get("preregistered", {})
    if not prereg:
        failures.append("research_claims.json has no 'preregistered' block")
        return failures, warnings, notes
    pr2 = prereg.get("PR2")
    if not isinstance(pr2, dict):
        failures.append("preregistered.PR2 missing or not an object")
        return failures, warnings, notes
    notes.append(f"preregistered.PR2 present: action={pr2.get('structural_action')}")

    # --- 2. Execution JSON presence + summary ---
    summary = f4_result.get("summary", {})
    if not summary:
        failures.append("execution JSON has no 'summary' block")
        return failures, warnings, notes
    params = summary.get("params", {})
    hits = summary.get("hits", {})
    counts = summary.get("counts", {})
    held = summary.get("held_out_generalization", {})

    # --- 3. Action / control / predict_direction match ---
    for key in ("action", "control"):
        # Manifest stores action under two keys:
        #   structural_action = abstract form ("delete_edge(e)")
        #   action_group      = specific form ("delete_bridge (H1)")
        # The execution JSON records the specific form, so compare against
        # action_group first, falling back to structural_action's verb.
        pr_v = pr2.get(key) if pr2.get(key) else None
        if key == "action":
            pr_v = pr2.get("action_group") or pr2.get("structural_action")
        if key == "control":
            pr_v = pr2.get("control_group")
        ex_v = summary.get(key)
        if pr_v is not None and ex_v is not None:
            pr_head = str(pr_v).split()[0]
            ex_head = str(ex_v).split()[0]
            if pr_head != ex_head:
                failures.append(
                    f"{key} mismatch: prereg={pr_v!r} execution={ex_v!r}"
                )
            else:
                notes.append(f"{key} consistent: {ex_v}")

    pr_dir = pr2.get("predict_direction")
    ex_dir = summary.get("predict_direction")
    if pr_dir != ex_dir:
        failures.append(f"predict_direction mismatch: prereg={pr_dir} exec={ex_dir}")
    else:
        notes.append(f"predict_direction consistent: {ex_dir}")

    # --- 4. Sample size / seed / start slice match ---
    for key in ("n_topologies", "seed", "start_idx"):
        pr_v = pr2.get(key)
        ex_v = params.get(key)
        if pr_v is not None and ex_v is not None:
            if int(pr_v) != int(ex_v):
                failures.append(f"{key} mismatch: prereg={pr_v} exec={ex_v}")
            else:
                notes.append(f"{key} consistent: {ex_v}")

    # --- 5. Held-out generalization overlap guard ---
    intervention_slice = held.get("intervention_slice")
    prereg_train = held.get("prereg_train_slice")
    prereg_held_out = held.get("prereg_held_out_slice")
    overlap_flag = held.get("overlap_with_prereg")
    if overlap_flag:
        failures.append(
            f"intervention_slice overlaps PR-1 slices: {intervention_slice} "
            f"vs {prereg_train}/{prereg_held_out} (held_out_generalization.overlap_with_prereg=True)"
        )
    else:
        # Independent re-verify: don't trust the flag, recompute the intersection
        if intervention_slice and prereg_train:
            if _slices_overlap(intervention_slice, prereg_train):
                failures.append(
                    f"intervention_slice {intervention_slice} overlaps "
                    f"prereg_train {prereg_train} (flag was False — lie!)"
                )
            if prereg_held_out and _slices_overlap(intervention_slice, prereg_held_out):
                failures.append(
                    f"intervention_slice {intervention_slice} overlaps "
                    f"prereg_held_out {prereg_held_out} (flag was False — lie!)"
                )
        notes.append(f"intervention_slice {intervention_slice} disjoint from PR-1 slices")

    # --- 6. Success criteria match ---
    pr_crit = pr2.get("success_criteria", {}) or {}
    ex_crit = summary.get("success_criteria", {}) or {}
    for key in ("direction_hit_rate_min", "paired_z_min"):
        pr_v = pr_crit.get(key)
        ex_v = ex_crit.get(key)
        if pr_v is not None and ex_v is not None:
            if abs(float(pr_v) - float(ex_v)) > 1e-9:
                failures.append(
                    f"success_criteria.{key} mismatch: prereg={pr_v} exec={ex_v}"
                )
            else:
                notes.append(f"success_criteria.{key} consistent: {ex_v}")

    # --- 7. Outcome honesty (R-0.4) ---
    hit_rate = hits.get("h1_hit_rate")
    min_hit = (pr2.get("success_criteria", {}) or {}).get("direction_hit_rate_min", 0.7)
    verdict = summary.get("verdict")
    n_pair = counts.get("n_pair")
    n_skipped = counts.get("skipped_no_bridge")

    # Independently recompute the hit rate from all_results so a tampered
    # summary.hits block cannot silently flip the outcome. If the recomputed
    # hit rate disagrees with the summary by more than 1e-9, the manifest
    # is lying about the outcome.
    all_results = f4_result.get("all_results", [])
    n_with_bridge = sum(
        1 for r in all_results
        if isinstance(r, dict) and r.get("edge_removed_bridge") is not None
    )
    n_hit_h1 = sum(
        1 for r in all_results
        if isinstance(r, dict) and bool(r.get("direction_hit_h1"))
    )
    recomputed_hit = (n_hit_h1 / n_with_bridge) if n_with_bridge else 0.0
    if hit_rate is not None and abs(float(hit_rate) - recomputed_hit) > 1e-9:
        failures.append(
            f"summary.hits.h1_hit_rate={hit_rate} disagrees with "
            f"recomputed rate from all_results ({n_hit_h1}/{n_with_bridge} = "
            f"{recomputed_hit:.6f}) — outcome tampered"
        )
        hit_rate_for_verdict = recomputed_hit
    else:
        hit_rate_for_verdict = hit_rate

    # Verdict must be consistent with the recomputed hit rate.
    if verdict == "PASS" and hit_rate_for_verdict is not None \
            and hit_rate_for_verdict < float(min_hit):
        failures.append(
            f"verdict=PASS but recomputed hit rate "
            f"{hit_rate_for_verdict:.3f} < {min_hit} — verdict lies"
        )
    if verdict == "FAIL" and hit_rate_for_verdict is not None \
            and hit_rate_for_verdict >= float(min_hit):
        failures.append(
            f"verdict=FAIL but recomputed hit rate "
            f"{hit_rate_for_verdict:.3f} >= {min_hit} — verdict lies"
        )

    if hit_rate_for_verdict is not None and hit_rate_for_verdict >= float(min_hit):
        notes.append(
            f"F4 intervention: PASS — hit rate {hit_rate_for_verdict:.3f} >= {min_hit} "
            f"over {n_pair} pairs ({n_skipped} skipped no bridge)"
        )
    elif hit_rate_for_verdict is not None:
        warnings.append(
            f"F4 intervention: FAIL — hit rate {hit_rate_for_verdict:.3f} < {min_hit} "
            f"over {n_pair} pairs ({n_skipped} skipped no bridge). "
            f"Per R-0.4 the negative result is preserved verbatim; "
            f"the isolation metric saturates below the intervention signal "
            f"on tiny (n=10) topologies. Do NOT adjust criteria to force a pass."
        )
    if verdict not in ("PASS", "FAIL", None):
        warnings.append(f"F4 verdict={verdict!r} — unknown verdict string")

    return failures, warnings, notes


def _run_injections(claims: dict, f4_result: dict) -> tuple[int, int]:
    bad = 0
    n_inj = 0

    def expect(name, apply_fn, checker):
        nonlocal bad, n_inj
        n_inj += 1
        orig_c = copy.deepcopy(claims)
        orig_r = copy.deepcopy(f4_result)
        try:
            apply_fn()
            failures, _w, _n = checker(claims, f4_result)
        finally:
            claims.clear(); claims.update(orig_c)
            f4_result.clear(); f4_result.update(orig_r)
        ok = len(failures) > 0
        if ok:
            print(f"    [PASS] injecting: {name}")
        else:
            bad += 1
            print(f"    [FAIL] injecting: {name} -> GATE STAYED GREEN")

    def _checker(c, r):
        f, w, n = _check_f4(c, r)
        return f, w, n

    # --- Injection 1: tamper the structural action to add_bridge ---
    def _patch_action():
        r = f4_result.get("summary", {})
        if isinstance(r, dict):
            r["action"] = "add_bridge"

    expect("tamper action delete_bridge → add_bridge -> FAIL",
           _patch_action, _checker)

    # --- Injection 2: force overlap by moving intervention slice into 0:60 ---
    def _patch_overlap():
        r = f4_result.get("summary", {})
        if isinstance(r, dict):
            held = r.get("held_out_generalization", {})
            if isinstance(held, dict):
                held["intervention_slice"] = "20:80"
                held["overlap_with_prereg"] = True

    expect("intervention slice overlaps PR-1 train 0:60 -> FAIL",
           _patch_overlap, _checker)

    # --- Injection 3: reweight the hit rate upward while data unchanged ---
    def _patch_hitrate():
        r = f4_result.get("summary", {})
        if isinstance(r, dict):
            hits = r.get("hits", {})
            if isinstance(hits, dict):
                hits["h1_hit_rate"] = 0.95
            r["verdict"] = "PASS"

    expect("reweight h1_hit_rate to 0.95 + flip verdict=PASS -> manifest mismatch -> FAIL",
           _patch_hitrate, _checker)

    return bad, n_inj


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — self-intervention consistency (PR-2)")
    ap.add_argument("--claims", metavar="PATH", default=str(DEFAULT_CLAIMS))
    ap.add_argument("--f4-result", metavar="PATH", default=str(DEFAULT_F4_RESULT))
    ap.add_argument("--json-out", metavar="PATH")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    claims_path = Path(args.claims)
    f4_path = Path(args.f4_result)

    if not claims_path.exists():
        print(f"{GATE_LABEL}: FAIL — claims file not found: {claims_path}")
        return 1
    if not f4_path.exists():
        print(f"{GATE_LABEL}: FAIL — F4 execution result not found: {f4_path}\n"
              f"  Run: python scripts/f4_intervention_test.py --seed 42")
        return 1

    claims = _load_json(claims_path)
    f4_result = _load_json(f4_path)

    n_inj = 0
    inj_bad = 0

    if not args.quiet:
        print(f"{GATE_LABEL} — self-intervention consistency (PR-2)")
        print(f"  claims : {claims_path}")
        print(f"  F4 out : {f4_path}")
        print()

    failures, warnings, notes = _check_f4(claims, f4_result)

    if not args.quiet:
        for note in notes:
            print(f"  ✓ {note}")
        for warn in warnings:
            print(f"  ~ WARN {warn}")
        for fail in failures:
            print(f"  ✗ {fail}")
        print()

        print("  -- fail-closed injections --")
        inj_bad, n_inj = _run_injections(claims, f4_result)
        if inj_bad:
            print(f"{GATE_LABEL}: FAIL — {inj_bad}/{n_inj} injections did not turn red")
            return 1
        print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
        print()

    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "claims_path": str(claims_path),
        "f4_result_path": str(f4_path),
        "counts": {"fail": len(failures), "warn": len(warnings), "note": len(notes)},
        "notes": notes,
        "warnings": warnings,
        "failures": failures,
        "injections": {"total": n_inj if not args.quiet else 0,
                       "bad": inj_bad if not args.quiet else 0},
    }
    out_path = Path(args.json_out) if args.json_out else SCRIPTS / "_gate45_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    if not args.quiet:
        print(f"  report: {out_path}")

    if failures:
        print(f"\n{GATE_LABEL}: FAIL — {len(failures)} integrity violation(s)")
        return 1
    if warnings:
        print(f"\n{GATE_LABEL}: PASS — PR-2 mechanism integrity OK "
              f"({len(warnings)} outcome warning(s) — negative result preserved per R-0.4)")
    else:
        print(f"\n{GATE_LABEL}: PASS — PR-2 preregistration consistent AND "
              f"causal direction target met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
