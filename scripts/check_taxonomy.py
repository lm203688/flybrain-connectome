#!/usr/bin/env python3
"""GATE 14 — taxonomy.system controlled vocabulary.

The unit field `system` accumulated 47 distinct values across 116 units and
14 species with no vocabulary. Anyone adding a new unit could tag it with any
string and the taxonomy would silently fragment. GATE 14 pins the vocabulary
in flybrain-connectome-mcp/functional_units/taxonomy_systems.json and fails
closed if any of:

  1. A unit.system is not in the vocabulary.
  2. The vocabulary has a system listed under more than one domain
     (ambiguity would make downstream grouping meaningless).
  3. Any vocabulary entry lacks a `definition` or a `note`.
  4. Any unit.system is missing (i.e. the field was never filled).

Coverage is reported per-domain so gaps are visible.  Unlike GATE 11 (which
is about *which functions are missing* — a declared work queue), GATE 14 is
about *which labels are legal*: adding a new legal label is fine, but it must
be added to the vocabulary first, in a version-bumped commit.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
UNITS = MCP / "functional_units" / "functional_units.json"
VOCAB = MCP / "functional_units" / "taxonomy_systems.json"


def fail(msg: str) -> int:
    print(f"GATE 14: FAIL — {msg}")
    return 1


def ok(msg: str) -> int:
    print(f"GATE 14: PASS — {msg}")
    return 0


def main() -> int:
    if not UNITS.exists():
        return fail(f"functional_units.json not found at {UNITS}")
    if not VOCAB.exists():
        return fail(f"taxonomy_systems.json not found at {VOCAB} — vocabulary must exist before this gate can run")

    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    units_doc = json.loads(UNITS.read_text(encoding="utf-8"))
    units = units_doc if isinstance(units_doc, list) else units_doc.get("units", [])

    # 1. Vocabulary integrity.
    domains = vocab.get("domains", [])
    if not domains:
        return fail("taxonomy_systems.json has no `domains`")
    if not vocab.get("definition_of_purpose") and not vocab.get("purpose"):
        return fail("taxonomy_systems.json must declare `purpose`")

    domain_ids: set[str] = set()
    legal_systems: dict[str, str] = {}  # system_id -> domain_id
    vocab_errors: list[str] = []
    for d in domains:
        did = d.get("id", "")
        if not did:
            vocab_errors.append("domain with empty id")
            continue
        if did in domain_ids:
            vocab_errors.append(f"duplicate domain id {did!r}")
        domain_ids.add(did)
        if not d.get("definition", "").strip():
            vocab_errors.append(f"domain {did!r} missing `definition`")
        for s in d.get("systems", []):
            sid = s.get("id", "")
            if not sid:
                vocab_errors.append(f"domain {did!r} has a system with empty id")
                continue
            if sid in legal_systems:
                vocab_errors.append(
                    f"system {sid!r} appears in both {legal_systems[sid]!r} and {did!r} — ambiguity"
                )
                continue
            if not s.get("note", "").strip():
                vocab_errors.append(f"system {sid!r} in domain {did!r} missing `note`")
            legal_systems[sid] = did

    if vocab_errors:
        for e in vocab_errors:
            print(f"  vocabulary: {e}")
        return fail(f"{len(vocab_errors)} vocabulary integrity error(s)")

    # 2. Every unit.system must be in the vocabulary.
    unknown: list[tuple[str, str]] = []
    missing: list[str] = []
    for u in units:
        uid = u.get("id", u.get("name", "?"))
        sys_v = u.get("system")
        if not sys_v:
            missing.append(uid)
            continue
        if sys_v not in legal_systems:
            unknown.append((uid, sys_v))

    if missing:
        return fail(f"{len(missing)} unit(s) missing `system` field: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    if unknown:
        for uid, sv in unknown[:10]:
            print(f"  unknown system {sv!r} on unit {uid!r}")
        if len(unknown) > 10:
            print(f"  ... and {len(unknown) - 10} more")
        return fail(f"{len(unknown)} unit(s) use a system not in the vocabulary — add them to taxonomy_systems.json first")

    # 3. Coverage per domain — for the record, never a fail condition.
    counts: dict[str, int] = defaultdict(int)
    for u in units:
        counts[legal_systems[u["system"]]] += 1

    print(f"  vocabulary: {len(domain_ids)} domains / {len(legal_systems)} systems")
    print(f"  units tagged: {len(units)}")
    print("  per-domain coverage:")
    for d in domains:
        did = d["id"]
        n = counts.get(did, 0)
        declared = len(d.get("systems", []))
        marker = "  (empty)" if n == 0 else ""
        print(f"    {did:24s}  {n:3d}/{len(units):3d} units  ({declared} systems declared){marker}")
    empty = [d["id"] for d in domains if counts.get(d["id"], 0) == 0]
    if empty:
        print(f"  empty domain(s): {empty} — this is a coverage fact, not a gate failure")

    return ok(f"{len(units)} units mapped across {len(domain_ids)} domains, vocabulary {len(legal_systems)} systems")


if __name__ == "__main__":
    sys.exit(main())
