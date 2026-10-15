#!/usr/bin/env python3
"""verify_receipt.py — S2 third-party receipt verifier.

Given a receipt, independently recompute the hash commitments and report
VERIFIED / MISMATCH. This is the whole point of the receipt: a third party
who does NOT trust the author's summary can still verify that:

  * the raw artifacts haven't been tampered with (raw_sample_sha256)
  * the recompute scripts haven't been tampered with (recompute_script_sha256)
  * the environment fingerprint is what was declared (env_hash)

If any of those drift, the receipt is MISMATCH and the expected_verdict
should be considered untrusted until re-issued.

Usage:
    python scripts/verify_receipt.py --receipt receipts/R1.json
    python scripts/verify_receipt.py --receipt receipts/R1.json --tamper-field expected_verdict --tamper-value TROLL
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _recompute_env_hash(receipt_env_hash: str) -> tuple[bool, str]:
    """Recompute env_hash. Returns (match, detail).

    We accept either an exact match OR a match after ignoring which optional
    modules were present at issue vs. verify time — this lets a third party
    verify on a machine that lacks numpy.
    """
    def _build(include_absent: bool) -> str:
        parts = [
            "python=" + platform.python_version(),
            "os=" + platform.system(),
            "arch=" + platform.machine(),
        ]
        for mod in ("numpy", "pandas", "networkx"):
            try:
                m = __import__(mod)
                parts.append(f"{mod}=" + getattr(m, "__version__", "n/a"))
            except ImportError:
                if include_absent:
                    parts.append(f"{mod}=absent")
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    exact = _build(include_absent=True)
    exact_without_absent = _build(include_absent=False)
    if exact == receipt_env_hash:
        return True, "exact"
    if exact_without_absent == receipt_env_hash:
        return True, "match_ignoring_absent_modules"
    return False, f"expected={receipt_env_hash[:12]}… actual_exact={exact[:12]}… actual_no_absent={exact_without_absent[:12]}…"


def verify(receipt: dict, root: Path, tamper: str | None = None, tamper_value=None) -> dict:
    r = receipt
    # Tamper simulation: overwrite a top-level receipt field before verifying.
    if tamper:
        r = copy.deepcopy(r)
        r[tamper] = tamper_value

    failures: list[str] = []
    warnings: list[str] = []

    # 1. artifact hashes
    recomputed_raw = []
    for a in r.get("artifacts", []):
        if a.get("status") == "missing" or not a.get("sha256"):
            warnings.append(f"artifact {a['path']} missing at issue time")
            recomputed_raw.append("")
            continue
        p = root / a["path"]
        if not p.exists():
            failures.append(f"artifact {a['path']} no longer on disk")
            recomputed_raw.append("")
            continue
        live_hash = _sha256_file(p)
        if live_hash != a["sha256"]:
            failures.append(f"artifact {a['path']} hash mismatch: receipt={a['sha256'][:12]}… live={live_hash[:12]}…")
        else:
            recomputed_raw.append(live_hash)

    # 2. script hashes
    recomputed_scripts = []
    for s in r.get("scripts", []):
        if s.get("status") == "missing" or not s.get("sha256"):
            warnings.append(f"script {s['path']} missing at issue time")
            recomputed_scripts.append("")
            continue
        p = root / s["path"]
        if not p.exists():
            failures.append(f"script {s['path']} no longer on disk")
            recomputed_scripts.append("")
            continue
        live_hash = _sha256_file(p)
        if live_hash != s["sha256"]:
            failures.append(f"script {s['path']} hash mismatch: receipt={s['sha256'][:12]}… live={live_hash[:12]}…")
        else:
            recomputed_scripts.append(live_hash)

    # 3. aggregated commitments
    recomputed_raw_commit = hashlib.sha256("|".join(recomputed_raw).encode()).hexdigest()
    recomputed_scripts_commit = hashlib.sha256("|".join(recomputed_scripts).encode()).hexdigest()
    if r.get("raw_sample_sha256") and recomputed_raw_commit != r["raw_sample_sha256"]:
        failures.append("raw_sample_sha256 aggregate mismatch")
    if r.get("recompute_script_sha256") and recomputed_scripts_commit != r["recompute_script_sha256"]:
        failures.append("recompute_script_sha256 aggregate mismatch")

    # 4. env_hash
    env_ok, env_detail = _recompute_env_hash(r["env_hash"])
    if not env_ok:
        warnings.append(f"env_hash drift: {env_detail}")

    verdict = "MISMATCH" if failures else "VERIFIED"
    return {
        "verdict": verdict,
        "claim_id": r.get("claim_id"),
        "expected_verdict": r.get("expected_verdict"),
        "n_artifacts_checked": sum(1 for a in r.get("artifacts", []) if a.get("sha256")),
        "n_scripts_checked": sum(1 for s in r.get("scripts", []) if s.get("sha256")),
        "failures": failures,
        "warnings": warnings,
        "env_hash": env_detail,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True, help="path to a receipt JSON")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--tamper-field", help="for demo: overwrite a top-level receipt field before verifying")
    ap.add_argument("--tamper-value", help="value to overwrite with (JSON-parseable)")
    args = ap.parse_args()

    with open(args.receipt, encoding="utf-8") as f:
        receipt = json.load(f)

    tv = args.tamper_value
    if tv:
        try:
            tv = json.loads(tv)
        except json.JSONDecodeError:
            pass  # keep as string

    rep = verify(receipt, ROOT, tamper=args.tamper_field, tamper_value=tv)

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print(f"claim_id={rep['claim_id']} expected_verdict={rep['expected_verdict']}")
        print(f"artifacts={rep['n_artifacts_checked']} scripts={rep['n_scripts_checked']}")
        print(f"env_hash: {rep['env_hash']}")
        for w in rep["warnings"]:
            print(f"  WARN {w}")
        for f_ in rep["failures"]:
            print(f"  FAIL {f_}")
        print("=" * 60)
        print(f"VERDICT: {rep['verdict']}")

    return 0 if rep["verdict"] == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
