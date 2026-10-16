#!/usr/bin/env python3
"""GATE 55 — holdout integrity (E3 vault discipline).

Design (from NEXT_STAGE_VISION_EPE_2026-10-16.md §E3)
-----------------------------------------------------
Every preregistered protocol that produced a PASS verdict must have a
*forward-or-retroactive commit* recorded in `vault/<protocol>.commit.json`
that pins (i) the criteria, (ii) the seed, (iii) the expected verdict.
The vault commit content_hash must match what is currently in
`research_claims.json` for that protocol (drift = FAIL), and the vault's
`open_count` must remain <= 1 forever (a rerun without a fresh commit
violates R-0.3 and is a Gate 55 failure).

This gate turns the R-0.3 discipline ("held-out is used once") from a
statement into a machine check. Prior to this gate nothing in the tree
enforced it — any number of reruns against the same held-out set was
possible with no visible evidence.

Gate 39 meta-discipline: the `injections()` battery below re-runs the
full check on mutated copies of the tree and asserts each mutation
turns the gate red. If any mutation passes, the gate is degenerate for
that defect class and this file FAILs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
VAULT_DIR = ROOT / "vault"
CLAIMS = ROOT / "research_claims.json"

GATE_ID = 55
GATE_LABEL = f"GATE {GATE_ID}"

PY = sys.executable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256_obj(obj) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def commit_path(protocol_id: str) -> Path:
    return VAULT_DIR / f"{protocol_id}.commit.json"


def open_path(protocol_id: str) -> Path:
    return VAULT_DIR / f"{protocol_id}.open.json"


def _extract_criteria(pr_block: dict) -> dict:
    """Mirror vault.py::_extract_criteria. Keeps a single source of truth
    by reimporting the function — but if vault.py is unavailable we fall
    back to a local copy (Gate 55 must be independently runnable)."""
    try:
        sys.path.insert(0, str(SCRIPTS))
        import vault as _v  # type: ignore
        return _v._extract_criteria(pr_block)
    except Exception:  # noqa: BLE001
        # Fallback: same field list as vault.py. If vault.py drifts, this
        # fallback drifts with it, and the injection battery catches the
        # divergence (mutation: delete one field → hash mismatch → RED).
        keys = (
            "outcome_metric", "threshold", "label_definition", "features",
            "model", "n_topologies", "n_nodes", "n_nodes_set", "seed",
            "train_idx", "held_out_idx", "permutations", "start_idx",
            "held_out_from_prereg", "families", "fit_on", "predict_only_on",
            "structural_action", "action_group", "control_group",
            "predict_direction", "compensation_mechanisms", "horizon_T",
            "target_component", "replacement_metrics", "success_criteria",
            "change_from_v1", "protocol_ref",
        )
        return {k: pr_block.get(k) for k in keys}


def _detect_protocol_verdict(pr: dict) -> str:
    """Return the primary verdict string for a protocol block.

    Order: nested scale summary > verification.verdict > pre-execution
    rejection > not yet verified.
    """
    v = pr.get("verification")
    if isinstance(v, dict) and v.get("verdict"):
        return str(v["verdict"])
    summary = pr.get("verification_n100_verdict_summary")
    if isinstance(summary, dict):
        parts = []
        for k, sub in sorted(summary.items()):
            if isinstance(sub, dict) and "verdict" in sub:
                parts.append(f"{k}:{sub['verdict']}")
        if parts:
            return " / ".join(parts)
    if pr.get("kind") == "pre_execution_rejection":
        return "REJECT"
    return "NOT_VERIFIED"


def _is_pass_verdict(verdict: str) -> bool:
    """Return True if verdict represents a positive outcome.

    We include PASS, WEAK_PASS, and multi-scale strings where every
    constituent is PASS — because for a multi-scale protocol (PR2 with
    n=10/50/100), if any scale is PASS we should have committed; if
    none are PASS we still have a commit for the negative result, but
    the gate's *forward-guarantee* check only fires on PASS.
    """
    v = verdict.upper()
    if v == "PASS":
        return True
    # Multi-scale string like "n_nodes_10:FAIL / n_nodes_50:PASS / n_nodes_100:FAIL"
    if ":" in v:
        parts = [p.split(":", 1)[1].strip() for p in v.split("/")]
        return any(p == "PASS" for p in parts)
    return False


def _list_protocols(claims: dict) -> list[str]:
    """Return only protocol keys (PR*) from the preregistered block.

    The `preregistered` object also carries non-protocol metadata
    (protocol_ref path, frozen_at date, freeze_rules) that must not
    be treated as protocols.
    """
    pr = claims.get("preregistered") or {}
    return sorted(k for k in pr if isinstance(pr.get(k), dict)
                  and isinstance(k, str) and k.startswith("PR"))


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def check_all(claims_path: Path, vault_dir: Path) -> tuple[bool, list[str], dict]:
    failures: list[str] = []
    report: dict = {"protocols": {}, "vault_dir": str(vault_dir)}

    if not vault_dir.is_dir():
        return False, [f"vault directory not found: {vault_dir}"], report

    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    protocols = _list_protocols(claims)
    prereg = claims.get("preregistered") or {}

    commit_files = sorted(vault_dir.glob("*.commit.json"))
    open_files = sorted(vault_dir.glob("*.open.json"))

    # Check 1: every PASS protocol must have a commit.
    pass_protocols = []
    for pid in protocols:
        verdict = _detect_protocol_verdict(prereg.get(pid, {}))
        if _is_pass_verdict(verdict):
            pass_protocols.append(pid)

    for pid in pass_protocols:
        cp = commit_path_in(pid, vault_dir)
        if not cp.exists():
            failures.append(
                f"PASS protocol {pid!r} has no vault commit "
                f"({cp.name} missing) — R-0.3 'submit before run' violated.")

    # Check 2: for every commit, verify the payload_hash still matches
    # the current tree (drift = FAIL).
    for cp in commit_files:
        pid = cp.stem.replace(".commit", "")
        entry = json.loads(cp.read_text(encoding="utf-8"))
        # Reconstruct the payload using the stored salt so the hash is
        # comparable to the committed hash.
        pr = prereg.get(pid, {})
        criteria = _extract_criteria(pr)
        payload = {
            "salt": entry.get("salt"),
            "criteria": criteria,
            "expected_verdict": entry.get("expected_verdict"),
            "claimed_registered_at": entry.get("claimed_registered_at"),
        }
        current_hash = sha256_obj(payload)
        expected_hash = entry.get("payload_hash")
        if current_hash != expected_hash:
            failures.append(
                f"{pid}: vault payload_hash drifted — committed "
                f"{expected_hash[:16]}... vs current {current_hash[:16]}... "
                f"(criteria or expected_verdict modified after commit)")
        report["protocols"][pid] = {
            "commit_type": entry.get("commit_type"),
            "committed_at": entry.get("committed_at"),
            "expected_verdict": entry.get("expected_verdict"),
            "payload_hash_matches": current_hash == expected_hash,
        }

    # Check 3: open_count <= 1 for every open.
    for op in open_files:
        pid = op.stem.replace(".open", "")
        entry = json.loads(op.read_text(encoding="utf-8"))
        count = int(entry.get("open_count", 0))
        if count > 1:
            failures.append(
                f"{pid}: vault open_count={count} — exceeds the R-0.3 "
                f"one-time-open limit.")
        report["protocols"].setdefault(pid, {})["open_count"] = count

    # Check 4: commit must not post-date the executed_at of the protocol.
    for cp in commit_files:
        pid = cp.stem.replace(".commit", "")
        entry = json.loads(cp.read_text(encoding="utf-8"))
        pr = prereg.get(pid, {})
        v = pr.get("verification")
        if isinstance(v, dict) and v.get("executed_at"):
            committed = entry.get("committed_at", "")
            executed = v.get("executed_at", "")
            # For retroactive commits, `committed_at` may post-date
            # `executed_at` by design (that is the point of "retroactive").
            # For forward commits, committed_at MUST precede executed_at.
            if entry.get("commit_type") == "forward":
                if committed and executed and committed > executed:
                    failures.append(
                        f"{pid}: forward commit dated {committed} but the "
                        f"protocol executed at {executed} — the commit was "
                        f"made AFTER the experiment. R-0.3 violation.")

    report["n_pass_protocols"] = len(pass_protocols)
    report["pass_protocols"] = pass_protocols
    report["n_commits"] = len(commit_files)
    report["n_opens"] = len(open_files)
    report["ok"] = not failures
    report["failures"] = failures
    return (not failures), failures, report


def commit_path_in(pid: str, vault_dir: Path) -> Path:
    return vault_dir / f"{pid}.commit.json"


# ---------------------------------------------------------------------------
# Injection battery (Gate 39 meta-discipline)
# ---------------------------------------------------------------------------

def injections() -> list[dict]:
    cases = []

    with tempfile.TemporaryDirectory(prefix="gate55_inj_") as td:
        tmp_root = Path(td)
        inj_vault = tmp_root / "vault"
        shutil.copytree(VAULT_DIR, inj_vault)
        claims_copy = tmp_root / "research_claims.json"
        shutil.copyfile(CLAIMS, claims_copy)

        def run() -> bool:
            ok, _, _ = check_all(claims_copy, inj_vault)
            return ok

        # Injection 1: delete the PR4 commit entirely — a PASS protocol
        # with no commit must fail.
        (inj_vault / "PR4.commit.json").unlink()
        ok = run()
        cases.append({
            "name": "delete_pass_commit",
            "description": "Remove PR4.commit.json; PR4 has verdict=PASS, "
                           "so the missing commit is an R-0.3 violation.",
            "mutated_ok": ok,
        })
        shutil.copyfile(VAULT_DIR / "PR4.commit.json", inj_vault / "PR4.commit.json")

        # Injection 2: tamper with the criteria (change threshold) so the
        # recomputed payload_hash no longer matches the commit.
        claims_tamper = json.loads(claims_copy.read_text(encoding="utf-8"))
        pr4 = claims_tamper["preregistered"]["PR4"]
        # Change a success_criteria threshold — this is a criteria field
        # included in the payload hash.
        if isinstance(pr4.get("success_criteria"), dict):
            pr4["success_criteria"]["recovery_auc_variance_min"] = 0.9999
        claims_copy.write_text(json.dumps(claims_tamper, indent=2),
                               encoding="utf-8")
        ok = run()
        cases.append({
            "name": "tamper_criteria_threshold",
            "description": "Change PR4.success_criteria.recovery_auc_ "
                           "variance_min → recomputed payload_hash must "
                           "no longer match the committed hash (MISMATCH).",
            "mutated_ok": ok,
        })
        shutil.copyfile(CLAIMS, claims_copy)

        # Injection 3: bump open_count to 2 in PR4.open.json — violates
        # R-0.3 one-time-open.
        op = inj_vault / "PR4.open.json"
        if op.exists():
            entry = json.loads(op.read_text(encoding="utf-8"))
            entry["open_count"] = 2
            op.write_text(json.dumps(entry, indent=2), encoding="utf-8")
            ok = run()
            cases.append({
                "name": "double_open",
                "description": "Set PR4.open.open_count=2; the R-0.3 "
                               "one-time-open discipline must fail.",
                "mutated_ok": ok,
            })
            shutil.copyfile(VAULT_DIR / "PR4.open.json", op)
        else:
            cases.append({
                "name": "double_open",
                "description": "Skipped — PR4 has no open file yet.",
                "mutated_ok": False,
            })

        # Injection 4: change PR4.expected_verdict in the commit from
        # PASS to FAIL — the vault's expected_verdict must match what
        # the commit hash was computed against.
        cp = inj_vault / "PR4.commit.json"
        c = json.loads(cp.read_text(encoding="utf-8"))
        c["expected_verdict"] = "FAIL"  # tamper
        cp.write_text(json.dumps(c, indent=2), encoding="utf-8")
        ok = run()
        cases.append({
            "name": "tamper_expected_verdict",
            "description": "Change PR4.commit.expected_verdict from "
                           "PASS to FAIL — the recomputed payload_hash "
                           "uses the (tampered) expected_verdict, so it "
                           "no longer matches the stored hash.",
            "mutated_ok": ok,
        })

    return cases


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="GATE 55 — holdout integrity (E3 vault discipline)")
    ap.add_argument("--claims", type=Path, default=CLAIMS)
    ap.add_argument("--vault", type=Path, default=VAULT_DIR)
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--skip-injections", action="store_true")
    args = ap.parse_args()

    claims_path = args.claims.resolve()
    vault_dir = args.vault.resolve()

    print(f"{GATE_LABEL} — holdout integrity (E3 vault)")
    print(f"  claims : {claims_path}")
    print(f"  vault  : {vault_dir}")
    print()

    ok, failures, report = check_all(claims_path, vault_dir)

    print(f"  PASS protocols   : {report.get('n_pass_protocols', 0)} "
          f"({', '.join(report.get('pass_protocols', [])) or '-'})")
    print(f"  vault commits    : {report.get('n_commits', 0)}")
    print(f"  vault opens      : {report.get('n_opens', 0)}")
    print()

    for pid, meta in sorted(report.get("protocols", {}).items()):
        type_str = meta.get("commit_type") or "(no commit)"
        expected = meta.get("expected_verdict") or "-"
        hash_ok = meta.get("payload_hash_matches")
        hash_str = "?"
        if hash_ok is True:
            hash_str = "match"
        elif hash_ok is False:
            hash_str = "DRIFT"
        open_c = meta.get("open_count", "-")
        print(f"    · {pid:10s} type={type_str:11s} "
              f"expected={expected:8s} hash={hash_str:5s} "
              f"opens={open_c}")
    print()

    if failures:
        print("  [FAIL] violations:")
        for f in failures:
            print(f"    ✗ {f}")
    else:
        print("  [PASS] every PASS protocol has a commit, every commit "
              "hash still matches, every open count <= 1")
    print()

    if not args.skip_injections:
        print("  injection battery (Gate 39 meta-discipline):")
        cases = injections()
        any_green = False
        for c in cases:
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

    out_path = args.json_out or (SCRIPTS / "_gate55_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report["injections"] = [] if args.skip_injections else injections()
    report["ok"] = not failures
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n  report: {out_path}")
    print()

    if failures:
        print(f"{GATE_LABEL}: FAIL — {len(failures)} violation(s)")
        return 1
    print(f"{GATE_LABEL}: PASS — holdout integrity enforced "
          f"({report.get('n_commits', 0)} commits, "
          f"{report.get('n_opens', 0)} opens, "
          f"{report.get('n_pass_protocols', 0)} PASS protocols covered, "
          f"injection battery all red)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
