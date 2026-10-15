#!/usr/bin/env python3
"""Dry-run pre-flight checker for opening the repository (Release Gate D3).

ZERO SIDE EFFECTS: this script only *scans and reports*. It never deletes,
modifies, moves, or rewrites anything — including git history. It is safe to
run at any time; all mutations are left to an explicit, human-reviewed step.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Patterns that may need cleanup before a public release (Tier-2 IP / private data).
SENSITIVE_DIR_PATTERNS = [
    r"flybrain-tier2-backup",
    r"\.workbuddy-ai",
    r"archive",
    r"generated_organisms",
    r"__pycache__",
]
SENSITIVE_FILE_PATTERNS = [
    r"LICENSE-CLAUSE",
    r"TIER-?2",
    r"private",
    r"secret",
    r"\.env$",
    r"credentials",
]
# README / docs claims that must be reconciled with the actual release state.
PRIVATE_CLAIM_PATTERNS = [
    r"currently private",
    r"private repository",
    r"not.*open.?source",
    r"私有",
]


def scan_sensitive_dirs() -> list[str]:
    hits = []
    for p in ROOT.iterdir():
        if not p.is_dir():
            continue
        for pat in SENSITIVE_DIR_PATTERNS:
            if re.search(pat, p.name, re.IGNORECASE):
                # count contained files (cheap, shallow)
                n = sum(1 for _ in p.glob("**/*") if _.is_file())
                hits.append(f"{p.name}/  ({n} files)")
                break
    return hits


def scan_sensitive_files() -> list[str]:
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        for pat in SENSITIVE_FILE_PATTERNS:
            if re.search(pat, p.name, re.IGNORECASE):
                try:
                    rel = p.relative_to(ROOT)
                except ValueError:
                    rel = p
                hits.append(str(rel))
                break
    return hits


def scan_private_claims() -> list[tuple[str, str, int]]:
    hits = []
    candidates = ["README.md", "docs/arxiv_paper.md"]
    for c in candidates:
        fp = ROOT / c
        if not fp.exists():
            continue
        for i, line in enumerate(fp.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for pat in PRIVATE_CLAIM_PATTERNS:
                if re.search(pat, line, re.IGNORECASE):
                    hits.append((c, line.strip()[:120], i))
                    break
    return hits


def git_history_signal() -> dict:
    """Lightweight, read-only git state report (no rewrite)."""
    import subprocess

    out = {"available": False, "recent_commits": []}
    try:
        r = subprocess.run(
            ["git", "log", "-8", "--format=%h %ad %s", "--date=short"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            out["available"] = True
            out["recent_commits"] = [l for l in r.stdout.splitlines() if l.strip()]
    except Exception as e:  # pragma: no cover
        out["error"] = str(e)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Dry-run pre-flight checker for public release (D3).")
    ap.add_argument("--dry-run", action="store_true", help="Explicit no-op flag (default behavior; no mutations ever).")
    ap.add_argument("--report-path", default="", help="Optional path to write the JSON report.")
    args = ap.parse_args()

    report = {
        "mode": "DRY-RUN (read-only, zero side effects)",
        "root": str(ROOT),
        "sensitive_dirs": scan_sensitive_dirs(),
        "sensitive_files": scan_sensitive_files()[:50],
        "private_claims_in_docs": scan_private_claims(),
        "git": git_history_signal(),
        "recommendation": (
            "REVIEW the lists above. A real release requires: (1) human review of each "
            "sensitive dir/file; (2) rewriting git history ONLY via an explicit, reviewed "
            "command after backup; (3) reconciling private_claims_in_docs with the new state. "
            "This script performed NO changes."
        ),
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report_path:
        Path(args.report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[written] {args.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
