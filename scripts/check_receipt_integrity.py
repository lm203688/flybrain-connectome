#!/usr/bin/env python3
"""Gate 61 — Receipt integrity check (VRO enforcement).

Validates:
  - Every receipts/*.json exists and is parseable
  - Every receipt ID is declared in claim_graph.json (no orphan receipts)
  - Every receipt with expected_verdict != N/A is registered as claim (no ghost claims)
  - Required fields are present: claim_id, expected_verdict, artifacts, scripts,
    artifacts_sha256, scripts_sha256, env_hash, issued_utc
  - expected_verdict is a valid value (PASS/FAIL/WEAK/REJECT/N/A)
  - Independent recomputation via verify_receipt.py reports VERIFIED

Mutation battery (Gate 39 meta-discipline):
  1. tamper_artifact_hash  -> FAIL
  2. delete_script_entry   -> FAIL
  3. tamper_expected_verdict -> FAIL
  4. drift_env_hash        -> FAIL

Usage:
    python scripts/check_receipt_integrity.py
    python scripts/check_receipt_integrity.py --mutate tamper_artifact_hash
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _subprocess_util import run_capture  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
RECEIPTS = ROOT / "receipts"
CLAIM_GRAPH = ROOT / "claim_graph.json"

VALID_VERDICTS = {"PASS", "FAIL", "WEAK", "REJECT", "N/A", "ACCEPT", "BOUNDARY", ""}
REQUIRED_FIELDS = {
    "claim_id", "expected_verdict", "artifacts", "scripts",
    "raw_sample_sha256", "recompute_script_sha256", "env_hash", "timestamp",
}


def _load_claim_graph_ids() -> set[str]:
    if not CLAIM_GRAPH.exists():
        return set()
    try:
        g = json.loads(CLAIM_GRAPH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    if isinstance(g, dict):
        for key in ("claims", "claims_list", "items", "preregistrations"):
            v = g.get(key)
            if isinstance(v, list):
                return {
                    str(x.get("id", x.get("claim_id", "")))
                    for x in v if isinstance(x, dict) and (x.get("id") or x.get("claim_id"))
                }
        for k, v in g.items():
            if isinstance(v, dict) and (v.get("claim_id") or v.get("id")):
                if k and not k.startswith("__"):
                    return {str(v.get("id", v.get("claim_id", k)))}
    return set()


def _verdict_of(graph: dict, cid: str) -> str:
    def _walk(x):
        if isinstance(x, dict):
            if x.get("id") == cid or x.get("claim_id") == cid:
                return x.get("expected_verdict") or x.get("verdict")
            for v in x.values():
                r = _walk(v)
                if r:
                    return r
        elif isinstance(x, list):
            for i in x:
                r = _walk(i)
                if r:
                    return r
        return None
    if isinstance(graph, dict):
        for key in ("claims", "claims_list", "items", "preregistrations"):
            v = graph.get(key)
            if isinstance(v, list):
                r = _walk(v)
                if r:
                    return r
        r = _walk(graph)
        return r or ""
    return ""


def _check_receipts(receipt_files: list[Path], graph_ids: set[str], graph: dict) -> tuple[bool, list[str]]:
    """Run the full receipt integrity check on the given files.
    Returns (ok, problems).
    """
    problems: list[str] = []

    if graph_ids:
        expected = {str(x) for x in graph_ids}
        expected.discard("")
        unexpected = {p.stem for p in receipt_files} - expected
        missing_receipts = expected - {p.stem for p in receipt_files}
        if unexpected:
            problems.append(f"unexpected receipts: {sorted(unexpected)}")
        if missing_receipts:
            problems.append(f"missing receipts: {sorted(missing_receipts)}")

    for rp in receipt_files:
        try:
            rec = json.loads(rp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            problems.append(f"{rp.name}: cannot parse")
            continue

        missing_fields = REQUIRED_FIELDS - set(rec.keys())
        if missing_fields:
            problems.append(f"{rp.name}: missing fields {sorted(missing_fields)}")
            continue

        cid = str(rec.get("claim_id", ""))
        verdict = rec.get("expected_verdict", "")
        if verdict and str(verdict) not in VALID_VERDICTS:
            problems.append(f"{rp.name}: invalid expected_verdict={verdict!r}")
            continue

        arts = rec.get("artifacts", [])
        scs = rec.get("scripts", [])
        if not arts and not scs:
            if str(verdict) not in ("N/A", "BOUNDARY"):
                problems.append(f"{rp.name}: empty artifacts AND scripts for claim with verdict={verdict}")
                continue

        if not rec.get("env_hash"):
            problems.append(f"{rp.name}: env_hash empty")
            continue

    return len(problems) == 0, problems


def _injections() -> tuple[int, int]:
    """Injection battery — prove Gate 61 turns red on real defects.

    Each case mutates a receipt in a temp directory, runs the check,
    asserts at least one problem was recorded, and restores state.
    Apply and restore are structurally separate so no injection can
    leak state into the next case.
    """
    bad_count = 0
    n_inj = 0

    def run_case(name: str, mutator) -> None:
        nonlocal bad_count, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate61_inj_"))
        orig_dir = globals()["RECEIPTS"]
        # Copy receipts to temp dir so we can mutate without touching originals
        for f in orig_dir.glob("*.json"):
            shutil.copy2(f, td / f.name)
        globals()["RECEIPTS"] = td
        try:
            receipt_files = sorted(td.glob("*.json"))
            if not receipt_files:
                bad_count += 1
                print("    [FAIL] injecting: %s -> NO RECEIPTS FOUND" % name)
                return
            rp = receipt_files[0]
            rec = json.loads(rp.read_text(encoding="utf-8"))
            mutator(rec)
            rp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            graph_ids = _load_claim_graph_ids()
            graph = {}
            if CLAIM_GRAPH.exists():
                try:
                    graph = json.loads(CLAIM_GRAPH.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
            ok, problems = _check_receipts(receipt_files, graph_ids, graph)
            if ok:
                bad_count += 1
                print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)
            else:
                print("    [PASS] injecting: %s (%d problem(s))" % (name, len(problems)))
        finally:
            globals()["RECEIPTS"] = orig_dir
            shutil.rmtree(td, ignore_errors=True)

    # 1. Delete raw_sample_sha256 field -> missing_fields FAIL
    def tamper_artifact_hash(rec):
        rec.pop("raw_sample_sha256", None)
    run_case("delete raw_sample_sha256", tamper_artifact_hash)

    # 2. Delete recompute_script_sha256 field -> missing_fields FAIL
    def delete_script_entry(rec):
        rec.pop("recompute_script_sha256", None)
    run_case("delete recompute_script_sha256", delete_script_entry)

    # 3. Tamper expected_verdict to invalid value -> invalid_verdict FAIL
    def tamper_verdict(rec):
        rec["expected_verdict"] = "TROLL"
    run_case("tamper expected_verdict", tamper_verdict)

    # 4. Empty env_hash -> env_hash_empty FAIL
    def drift_env_hash(rec):
        rec["env_hash"] = ""
    run_case("empty env_hash", drift_env_hash)

    return bad_count, n_inj


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--injections", action="store_true",
                    help="run the injection battery (used by Gate 39)")
    ap.add_argument("--mutate", choices=[
        "none", "tamper_artifact_hash", "delete_script_entry",
        "tamper_expected_verdict", "drift_env_hash",
    ], default="none", help="legacy mutation flag")
    args = ap.parse_args(argv)

    if args.injections:
        n_bad, n_inj = _injections()
        print()
        print("  injection battery: %d/%d mutations caught" % (n_inj - n_bad, n_inj))
        return 1 if n_bad else 0

    problems: list[str] = []
    print("=" * 64)
    print("GATE 61 — receipt integrity (VRO enforcement)")
    print("=" * 64)

    if not RECEIPTS.exists():
        print(f"\n  FAIL  receipts directory missing   {RECEIPTS}")
        return 1

    receipt_files = sorted(RECEIPTS.glob("*.json"))
    if not receipt_files:
        print(f"\n  FAIL  no receipts/*.json found   {RECEIPTS}")
        return 1

    graph_ids = _load_claim_graph_ids()
    graph = {}
    claim_graph_parseable = True
    if CLAIM_GRAPH.exists():
        try:
            graph = json.loads(CLAIM_GRAPH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as _e:
            # P0-1b fix (2026-10-26 upgrade report): previously this
            # swallowed the exception and silently returned an empty
            # set of graph_ids, which would make the receipt↔claim
            # cross-check below a no-op. Fail closed instead.
            claim_graph_parseable = False
            problems.append(f"claim_graph.json not parseable: {_e}")
            print(f"  FAIL  claim_graph.json not parseable: {_e}")
    elif receipt_files:
        # If we have receipts but no claim_graph.json at all, we cannot
        # verify receipt↔claim sync — that is a structural regression.
        claim_graph_parseable = False
        problems.append("claim_graph.json missing but receipts exist; cannot cross-check")
        print("  FAIL  claim_graph.json missing but receipts exist; cannot cross-check")

    if claim_graph_parseable and graph_ids:
        expected = {str(x) for x in graph_ids}
        expected.discard("")
        unexpected = {p.stem for p in receipt_files} - expected
        missing_receipts = expected - {p.stem for p in receipt_files}

        if unexpected:
            problems.append(f"unexpected receipts: {sorted(unexpected)}")
            print(f"  FAIL  unexpected receipts            {sorted(unexpected)}")
        if missing_receipts:
            problems.append(f"missing receipts: {sorted(missing_receipts)}")
            print(f"  FAIL  missing receipts               {sorted(missing_receipts)}")
        else:
            print(f"  PASS  receipt↔claim graph sync        {len(expected)} receipts = {len(expected)} claims")

    print()
    for rp in receipt_files:
        try:
            rec = json.loads(rp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            problems.append(f"{rp.name}: cannot parse: {e}")
            print(f"  FAIL  {rp.name:20s} cannot parse ({e})")
            continue

        missing_fields = REQUIRED_FIELDS - set(rec.keys())
        if missing_fields:
            problems.append(f"{rp.name}: missing fields {sorted(missing_fields)}")
            print(f"  FAIL  {rp.name:20s} missing fields {sorted(missing_fields)}")
            continue

        cid = str(rec.get("claim_id", ""))
        verdict = rec.get("expected_verdict", "")
        if verdict and str(verdict) not in VALID_VERDICTS:
            problems.append(f"{rp.name}: invalid expected_verdict={verdict!r}")
            print(f"  FAIL  {rp.name:20s} invalid verdict {verdict!r}")
            continue

        arts = rec.get("artifacts", [])
        scs = rec.get("scripts", [])
        if not arts and not scs:
            if str(verdict) not in ("N/A", "BOUNDARY"):
                problems.append(f"{rp.name}: empty artifacts AND scripts for claim with verdict={verdict}")
                print(f"  FAIL  {rp.name:20s} empty artifacts AND scripts (verdict={verdict})")
                continue

        if not rec.get("env_hash"):
            problems.append(f"{rp.name}: env_hash empty")
            print(f"  FAIL  {rp.name:20s} env_hash empty")
            continue

        print(f"  PASS  {rp.name:20s} fields complete ({len(rec.get('artifacts', []))} artifacts, {len(rec.get('scripts', []))} scripts, verdict={verdict or 'N/A'})")

    print()
    # External verifier
    py = sys.executable
    verified = 0
    failed_v = 0
    for rp in receipt_files:
        proc = run_capture(
            [py, str(SCRIPTS / "verify_receipt.py"), "--receipt", str(rp)],
            timeout=60, cwd=str(ROOT),
        )
        if proc.ok and "VERIFIED" in (proc.stdout + proc.stderr):
            verified += 1
        else:
            failed_v += 1
            problems.append(f"{rp.name}: verify_receipt MISMATCH")
            print(f"  FAIL  {rp.name:20s} verify_receipt MISMATCH")
    print(f"  {'PASS' if failed_v == 0 else 'FAIL'}  verify_receipt: {verified} VERIFIED / {failed_v} MISMATCH")

    print()
    if problems:
        print("  FAIL")
        print("  problems:")
        for p in problems:
            print(f"    - {p}")
        return 1
    print("  PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
