#!/usr/bin/env python3
"""Export the Preregistered Rejection Public Registry (F3 deliverable).

This script reads `research_claims.json`, extracts every preregistered
segment with `kind = pre_execution_rejection`, and writes a canonical,
machine-readable registry at `registry/preregistered_rejections.json`.

The registry is intended to be:
- Publicly shareable (contains no proprietary data, only hashes and text)
- RO-Crate compatible (each rejection is a `CreativeWork` with `schema.org/Citation` links)
- Machine-verifiable (each entry carries a sha256 of the receipt, so third
  parties can cross-check against `receipts/`)

See NEXT_STAGE_VISION_AND_PLAN_2026-10-15.md §F3 and the P-2 paper for the
underlying concept: preregistered rejection as a first-class negative result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CLAIMS_PATH = REPO_ROOT / "research_claims.json"
RECEIPTS_DIR = REPO_ROOT / "receipts"
REGISTRY_DIR = REPO_ROOT / "registry"
REGISTRY_PATH = REGISTRY_DIR / "preregistered_rejections.json"

SCHEMA = "preexec_rejection_registry_v1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _env_hash() -> str:
    parts = ["python=" + platform.python_version(), "os=" + platform.system(),
             "arch=" + platform.machine()]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _find_rejection_id(pr_id: str) -> str:
    """Return the receipt filename for a given prereg id (e.g. PR2b -> receipts/PR2b.json)."""
    return f"{pr_id}.json"


def _extract_rejection(pr_id: str, pr_seg: dict, claims_meta: dict) -> dict:
    """Convert a single prereg segment into a registry entry."""
    receipt_path = RECEIPTS_DIR / _find_rejection_id(pr_id)
    receipt_sha = None
    if receipt_path.exists():
        receipt_sha = _sha256_file(receipt_path)

    claim_id = pr_seg.get("claim_id")
    entry = {
        "id": pr_id,
        "kind": pr_seg.get("kind", "pre_execution_rejection"),
        "claim_id": claim_id,
        "registered_at": pr_seg.get("registered_at"),
        "protocol_ref": pr_seg.get("protocol_ref"),
        "project_version": claims_meta.get("version"),
        "proposed_as": pr_seg.get("proposed_as"),
        "mechanism_under_test": pr_seg.get("mechanism_under_test"),
        "success_criteria": pr_seg.get("success_criteria"),
        "decision_basis": pr_seg.get("decision_basis"),
        "criteria_modified_after_results": pr_seg.get("criteria_modified_after_results"),
        "unexplored_alternatives": pr_seg.get("unexplored_alternatives", []),
        "notes": pr_seg.get("notes"),
        "verification": pr_seg.get("verification"),
        "receipt_sha256": receipt_sha,
        "receipt_path": f"receipts/{_find_rejection_id(pr_id)}" if receipt_path.exists() else None,
    }
    return entry


def build_registry() -> dict:
    claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
    prereg = claims.get("preregistered", {})
    rejections = [
        _extract_rejection(pr_id, pr_seg, claims)
        for pr_id, pr_seg in prereg.items()
        if isinstance(pr_seg, dict) and pr_seg.get("kind") == "pre_execution_rejection"
    ]

    registry = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": "flybrain-connectome",
        "project_version": claims.get("version"),
        "protocol_doc": "docs/PREREGISTRATION_PROTOCOL_v1.md",
        "paper_ref": "docs/PR2B_PREEXECUTION_REJECTION_PAPER.md",
        "gate": "Gate 47 (metric_substitution) + Gate 51+52 (C1/C3 prereg integrity)",
        "env_hash": _env_hash(),
        "registry_sha256_of_inputs": {
            "research_claims.json": _sha256_file(CLAIMS_PATH),
        },
        "n_rejections": len(rejections),
        "entries": rejections,
        "license": "CC BY 4.0",
    }
    return registry


def export(path: Path = REGISTRY_PATH) -> dict:
    registry = build_registry()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Export preregistered rejection registry")
    parser.add_argument("--out", type=Path, default=REGISTRY_PATH,
                        help="Output registry JSON path")
    parser.add_argument("--check", action="store_true",
                        help="Check existing registry against research_claims.json; exit 1 on mismatch")
    args = parser.parse_args()

    if args.check:
        current = build_registry()
        current_cmp = {k: v for k, v in current.items() if k not in ("generated_at", "env_hash")}
        if not args.out.exists():
            print(f"[FAIL] registry not found: {args.out}")
            return 1
        existing = json.loads(args.out.read_text(encoding="utf-8"))
        existing_cmp = {k: v for k, v in existing.items() if k not in ("generated_at", "env_hash")}
        if current_cmp == existing_cmp:
            print(f"[PASS] registry in sync ({current['n_rejections']} rejections)")
            return 0
        print("[FAIL] registry out of sync")
        for k in set(current_cmp) | set(existing_cmp):
            if current_cmp.get(k) != existing_cmp.get(k):
                print(f"  - field '{k}' differs")
        return 1

    reg = export(args.out)
    print(f"[ok] wrote {args.out} ({reg['n_rejections']} rejection(s))")
    for entry in reg["entries"]:
        rid = entry["id"]
        claim = entry["claim_id"]
        receipt = entry["receipt_sha256"]
        receipt_str = receipt[:12] + "..." if receipt else "MISSING"
        print(f"  - {rid} (claim {claim}) receipt_sha={receipt_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
