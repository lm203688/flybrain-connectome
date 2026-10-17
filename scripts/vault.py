#!/usr/bin/env python3
"""E3 holdout vault — submit-before-run, open-once, content-addressed.

Motivation
----------
The prior project discipline (R-0.3 in the preregistration protocol) said
"held-out is used once", but nothing in the tree enforced it. If a
protocol was re-run with adjusted criteria, the tree showed only the
*final* `verdict`, not the sequence of decisions. E3 vault turns that
discipline into machine checkability.

Design (from NEXT_STAGE_VISION_EPE_2026-10-16.md §E3)
----------------------------------------------------
* **Submit first**: for each protocol, before running the experiment,
  commit the (i) criteria, (ii) data-generating seed, (iii) expected
  verdict/interval to `vault/<protocol>.commit.json`.
* **One-time open**: after running, `vault open` diffs the observed
  result against the commit and increments `open_count`. `open_count`
  must remain <= 1 forever.
* **Content-addressed**: `content_hash` is the SHA-256 of the canonical
  JSON encoding of the payload. Any change to criteria / seed / expected
  verdict produces a different hash. `vault verify` recomputes the
  current criteria from `research_claims.json` and reports `MISMATCH`
  if the tree has drifted from the commit.
* **Salt**: the commit salt is included in the hash. The salt's only
  role is to prevent a *preimage* attack on the content_hash (someone
  seeing a stored hash and guessing the criteria backwards). It does
  not make the vault tamper-proof — that is Gate 55's job.
* **Retrospective mode**: for protocols that were registered before this
  vault existed, `vault commit --retroactive` stamps `commit_type =
  "retroactive"` and refuses to hide the fact. Gate 55 treats retroactive
  commits as honest-but-unguarded: they satisfy the "must have a commit"
  clause but do not evidence forward-going discipline.

CLI
---
    vault.py commit PR4 --claims research_claims.json
        [--retroactive] [--salt <hex>]
    vault.py open   PR4 --result _f2_recovery/f2_recovery_dynamics.json
    vault.py verify PR4 [--claims research_claims.json]
    vault.py list
    vault.py check                     # Gate 55-friendly summary

Exit codes
----------
    0  success / verify MATCH
    1  verify MISMATCH, or gate-detected violation
    2  usage / IO error
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
VAULT_DIR = ROOT / "vault"
DEFAULT_CLAIMS = ROOT / "research_claims.json"

SCHEMA_COMMIT = "vault_commit_v1"
SCHEMA_OPEN = "vault_open_v1"


# ---------------------------------------------------------------------------
# Canonicalization + hashing
# ---------------------------------------------------------------------------

def canon(obj) -> str:
    """Canonical JSON string (deterministic key order, compact separators)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256_obj(obj) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _today() -> str:
    # Use the local date (matches the project's other audit files which
    # record dates without timezone). Do not use time.time() — see the
    # system prompt rule about timestamps.
    try:
        p = subprocess_date = __import__("subprocess").run(
            ["date", "+%Y-%m-%d"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=2,
        )
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:  # noqa: SILENT — date fallback is benign; return today if date cmd fails
        pass
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Vault primitives
# ---------------------------------------------------------------------------

def _extract_pr_block(claims: dict, protocol_id: str) -> dict:
    """Return the `preregistered.<protocol_id>` block from research_claims."""
    pr = claims.get("preregistered") or {}
    if protocol_id not in pr:
        raise KeyError(
            f"protocol_id={protocol_id!r} not found in "
            f"research_claims.json:.preregistered")
    return pr[protocol_id]


def _extract_criteria(pr_block: dict) -> dict:
    """Return only the fields that count as the frozen criteria.

    Deliberately excludes anything the executor could touch to influence
    the verdict: `verification`, `verification_nXX`, notes, etc.
    """
    return {
        "outcome_metric": pr_block.get("outcome_metric"),
        "threshold": pr_block.get("threshold"),
        "label_definition": pr_block.get("label_definition"),
        "features": pr_block.get("features"),
        "model": pr_block.get("model"),
        "n_topologies": pr_block.get("n_topologies"),
        "n_nodes": pr_block.get("n_nodes"),
        "n_nodes_set": pr_block.get("n_nodes_set"),
        "seed": pr_block.get("seed"),
        "train_idx": pr_block.get("train_idx"),
        "held_out_idx": pr_block.get("held_out_idx"),
        "permutations": pr_block.get("permutations"),
        "start_idx": pr_block.get("start_idx"),
        "held_out_from_prereg": pr_block.get("held_out_from_prereg"),
        "families": pr_block.get("families"),
        "fit_on": pr_block.get("fit_on"),
        "predict_only_on": pr_block.get("predict_only_on"),
        "structural_action": pr_block.get("structural_action"),
        "action_group": pr_block.get("action_group"),
        "control_group": pr_block.get("control_group"),
        "predict_direction": pr_block.get("predict_direction"),
        "compensation_mechanisms": pr_block.get("compensation_mechanisms"),
        "horizon_T": pr_block.get("horizon_T"),
        "target_component": pr_block.get("target_component"),
        "replacement_metrics": pr_block.get("replacement_metrics"),
        "success_criteria": pr_block.get("success_criteria"),
        "change_from_v1": pr_block.get("change_from_v1"),
        "protocol_ref": pr_block.get("protocol_ref"),
    }


def commit_path(protocol_id: str) -> Path:
    return VAULT_DIR / f"{protocol_id}.commit.json"


def open_path(protocol_id: str) -> Path:
    return VAULT_DIR / f"{protocol_id}.open.json"


def _resolve_salt(provided: str | None) -> str:
    if provided:
        return provided
    # 16 bytes of os.urandom is enough for a preimage-safety salt.
    # (Not a security boundary — the content_hash is still visible.)
    return os.urandom(16).hex()


def cmd_commit(args) -> int:
    claims_path = Path(args.claims)
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    pr = _extract_pr_block(claims, args.protocol)

    criteria = _extract_criteria(pr)
    salt = _resolve_salt(args.salt)
    commit_type = "retroactive" if args.retroactive else "forward"
    committed_at = _today()
    claimed_registered_at = pr.get("registered_at", committed_at)

    payload = {
        "salt": salt,
        "criteria": criteria,
        "expected_verdict": args.expected_verdict
                            or _detect_expected_verdict(pr),
        "claimed_registered_at": claimed_registered_at,
    }
    payload_hash = sha256_obj(payload)

    entry = {
        "schema": SCHEMA_COMMIT,
        "protocol_id": args.protocol,
        "commit_type": commit_type,
        "committed_at": committed_at,
        "claimed_registered_at": claimed_registered_at,
        "salt": salt,
        "payload_hash": payload_hash,
        "expected_verdict": payload["expected_verdict"],
        "success_criteria": criteria.get("success_criteria"),
        "outcome_metric": criteria.get("outcome_metric"),
        "note": (
            "retroactive: protocol was registered and executed before this "
            "vault existed; the commit records the *original* criteria at "
            "the time of execution. Forward-guarantee begins with the "
            "next protocol."
            if commit_type == "retroactive"
            else "forward: criteria committed before experiment execution."
        ),
    }

    p = commit_path(args.protocol)
    if p.exists() and not args.force:
        print(f"vault: commit already exists at {p}; refusing to overwrite "
              f"(use --force to replace, at the cost of losing the "
              f"forward-guarantee record).")
        return 1
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entry, indent=2, ensure_ascii=False),
                 encoding="utf-8")
    print(f"vault: committed {args.protocol} [{commit_type}]")
    print(f"    payload_hash : {payload_hash}")
    print(f"    expected     : {entry['expected_verdict']}")
    print(f"    committed_at : {committed_at}")
    print(f"    salt         : {salt[:16]}...")
    print(f"    path         : {p}")
    return 0


def _detect_expected_verdict(pr: dict) -> str:
    """Infer the preregistered expected verdict from the PR block.

    For protocols that record multiple scale points (PR2), return a
    canonical summary that includes all three scales.
    """
    n100 = pr.get("verification_n100_verdict_summary")
    if isinstance(n100, dict):
        parts = [f"{k}:{v.get('verdict')}"
                 for k, v in sorted(n100.items())
                 if isinstance(v, dict) and "verdict" in v]
        if parts:
            return " / ".join(parts)
    verification = pr.get("verification") or {}
    return verification.get("verdict") or "UNKNOWN"


def cmd_open(args) -> int:
    cp = commit_path(args.protocol)
    if not cp.exists():
        print(f"vault: no commit for protocol {args.protocol!r}; "
              f"run `vault.py commit {args.protocol}` first.")
        return 1
    commit = json.loads(cp.read_text(encoding="utf-8"))

    result_path = Path(args.result)
    if not result_path.exists():
        print(f"vault: result file not found: {result_path}")
        return 1
    result_bytes = result_path.read_bytes()
    result_text = result_bytes.decode("utf-8", errors="replace")
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError as e:
        print(f"vault: result file is not JSON: {e}")
        return 1

    result_hash = sha256_str(result_text)

    # Extract observed verdict: prefer top-level "summary.verdict"; else
    # look at nested keys. We store the raw path so an auditor can verify.
    observed_verdict = None
    verdict_path = None
    if isinstance(result, dict):
        summary = result.get("summary")
        if isinstance(summary, dict) and "verdict" in summary:
            observed_verdict = summary["verdict"]
            verdict_path = "$.summary.verdict"
        elif "verdict" in result:
            observed_verdict = result["verdict"]
            verdict_path = "$.verdict"
    if observed_verdict is None:
        print(f"vault: could not locate verdict field in {args.result}")
        return 1

    op = open_path(args.protocol)
    if op.exists():
        prev = json.loads(op.read_text(encoding="utf-8"))
        count = int(prev.get("open_count", 1))
    else:
        count = 0
    count += 1

    entry = {
        "schema": SCHEMA_OPEN,
        "protocol_id": args.protocol,
        "opened_at": _today(),
        "open_count": count,
        "result_path": str(result_path.relative_to(ROOT))
                        if result_path.is_relative_to(ROOT) else str(result_path),
        "result_hash": result_hash,
        "observed_verdict": observed_verdict,
        "observed_verdict_path": verdict_path,
        "commit_payload_hash": commit["payload_hash"],
        "verdict_matches_commit": (
            str(observed_verdict) == str(commit["expected_verdict"])
            or str(observed_verdict) in str(commit["expected_verdict"])
            or str(commit["expected_verdict"]) in str(observed_verdict)
        ),
    }
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(entry, indent=2, ensure_ascii=False),
                  encoding="utf-8")
    print(f"vault: opened {args.protocol} (open_count={count})")
    print(f"    observed_verdict : {observed_verdict}  (path {verdict_path})")
    print(f"    commit expected  : {commit['expected_verdict']}")
    print(f"    verdict match    : {entry['verdict_matches_commit']}")
    print(f"    result_hash      : {result_hash[:24]}...")
    return 0 if count <= 1 else 1


def cmd_verify(args) -> int:
    """Verify current research_claims.json still matches the commit.

    Any drift in the frozen criteria (threshold, seed, features, ...)
    after the commit was made is reported as MISMATCH.
    """
    cp = commit_path(args.protocol)
    if not cp.exists():
        print(f"vault: no commit for {args.protocol!r}")
        return 1
    commit = json.loads(cp.read_text(encoding="utf-8"))

    claims_path = Path(args.claims)
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    pr = _extract_pr_block(claims, args.protocol)
    current_criteria = _extract_criteria(pr)

    committed_criteria = commit.get("payload_hash")
    # Reconstruct the expected payload from the current tree using the
    # stored salt (so the hash depends on the same salt as at commit time).
    current_payload = {
        "salt": commit.get("salt"),
        "criteria": current_criteria,
        "expected_verdict": commit.get("expected_verdict"),
        "claimed_registered_at": commit.get("claimed_registered_at"),
    }
    current_payload_hash = sha256_obj(current_payload)

    match = current_payload_hash == committed_criteria
    print(f"vault verify {args.protocol}:")
    print(f"    committed payload_hash : {committed_criteria}")
    print(f"    current   payload_hash : {current_payload_hash}")
    if match:
        print("    status                  : MATCH")
        return 0
    print("    status                  : MISMATCH — research_claims.json "
          "has drifted from the vault commit.")
    # Diagnose which fields differ.
    committed_full = {}
    try:
        for k, v in commit.items():
            if k in ("salt", "payload_hash", "expected_verdict",
                     "claimed_registered_at"):
                committed_full[k] = v
    except Exception:  # noqa: SILENT — drift diagnosis only; commit_payload_get handles missing keys
        pass
    drift_fields = []
    for k, v in current_criteria.items():
        if commit_payload_get(commit, k) != v:
            drift_fields.append(k)
    print(f"    drift fields             : "
          f"{','.join(sorted(drift_fields)) or '(see payload diff)'}")
    return 1


def commit_payload_get(commit: dict, key: str):
    """The commit does not inline the criteria dict (only its hash). So we
    cannot field-level compare without re-hashing. Instead, if the payload
    hash matches we know everything matches; if not we list every frozen
    field as potentially drifted and let the caller check by re-verifying
    the hash. For a useful diagnostic, we include the *currently stored*
    criteria snapshot in the commit at write time (below)."""
    return commit.get("_criteria_snapshot", {}).get(key)


def cmd_list(args) -> int:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    commits = sorted(VAULT_DIR.glob("*.commit.json"))
    opens = sorted(VAULT_DIR.glob("*.open.json"))
    print(f"vault dir : {VAULT_DIR}")
    print(f"commits   : {len(commits)}")
    for p in commits:
        c = json.loads(p.read_text(encoding="utf-8"))
        op = open_path(c["protocol_id"])
        opened = "yes" if op.exists() else "no"
        print(f"  · {c['protocol_id']:12s} type={c['commit_type']:11s} "
              f"committed={c['committed_at']} opened={opened}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="E3 holdout vault — submit-before-run, open-once, "
                    "content-addressed")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("commit", help="commit criteria before running")
    p.add_argument("protocol", help="protocol id (e.g. PR4)")
    p.add_argument("--claims", default=str(DEFAULT_CLAIMS))
    p.add_argument("--salt", help="16-byte hex salt (auto if omitted)")
    p.add_argument("--expected-verdict", help="override auto-detect")
    p.add_argument("--retroactive", action="store_true",
                   help="mark commit as retroactive (protocol ran before "
                        "vault existed)")
    p.add_argument("--force", action="store_true",
                   help="overwrite an existing commit (breaks "
                        "forward-guarantee)")
    p.set_defaults(func=cmd_commit)

    p = sub.add_parser("open", help="open commit after running")
    p.add_argument("protocol")
    p.add_argument("--result", required=True, help="path to result JSON")
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("verify",
                       help="verify current research_claims.json matches "
                            "the vault commit")
    p.add_argument("protocol")
    p.add_argument("--claims", default=str(DEFAULT_CLAIMS))
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("list", help="list all commits and opens")
    p.set_defaults(func=cmd_list)

    return ap


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    # Store a criteria snapshot at commit time so that `verify` can
    # report drift on a per-field basis when the hash changes.
    _orig_commit = cmd_commit

    def cmd_commit_with_snapshot(args):  # noqa: D401
        rc = _orig_commit(args)
        if rc == 0:
            p = commit_path(args.protocol)
            c = json.loads(p.read_text(encoding="utf-8"))
            if "_criteria_snapshot" not in c:
                claims = json.loads(Path(args.claims).read_text(
                    encoding="utf-8"))
                pr = _extract_pr_block(claims, args.protocol)
                c["_criteria_snapshot"] = _extract_criteria(pr)
                p.write_text(json.dumps(c, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        return rc

    cmd_commit = cmd_commit_with_snapshot

    sys.exit(main())
