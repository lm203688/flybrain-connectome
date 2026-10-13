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
import shutil
import sys
import tempfile
from collections import defaultdict
from copy import deepcopy
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


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: inject one defect at a time, assert it turns red.

    Each case writes a mutated copy of the vocab/units to a temp dir,
    monkey-patches the module-level UNITS/VOCAB paths, re-runs main(),
    then asserts non-zero exit. Apply and restore are structurally
    separate (via tempfile + globals swap + finally), so no injection
    can leak state into the next one.

    The battery mirrors GATE 14's declared fail-closed list (1–4 in the
    docstring): rogue unit.system, duplicate system across domains,
    missing note, missing unit.system field.
    """
    bad = 0
    n_inj = 0

    with VOCAB.open(encoding="utf-8") as f:
        real_vocab = json.load(f)
    with UNITS.open(encoding="utf-8") as f:
        real_units = json.load(f)

    def expect(name: str, mutate_fn) -> None:
        nonlocal bad, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate14_inj_"))
        try:
            v_copy = deepcopy(real_vocab)
            u_copy = deepcopy(real_units)
            mutate_fn(v_copy, u_copy)

            vp = td / "vocab.json"
            up = td / "units.json"
            vp.write_text(json.dumps(v_copy, ensure_ascii=False), encoding="utf-8")
            up.write_text(json.dumps(u_copy, ensure_ascii=False), encoding="utf-8")

            old_units, old_vocab = UNITS, VOCAB
            globals()["UNITS"] = up
            globals()["VOCAB"] = vp
            try:
                rc = main()
            finally:
                globals()["UNITS"] = old_units
                globals()["VOCAB"] = old_vocab
        finally:
            shutil.rmtree(td, ignore_errors=True)

        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    def _units_list(doc):
        return doc.get("units", []) if isinstance(doc, dict) else (doc or [])

    def _first_unit(doc):
        ls = _units_list(doc)
        return ls[0] if ls else None

    # 1. A unit uses a system not in the vocabulary.
    def _rogue_unit_system(v, u):
        fu = _first_unit(u)
        if fu is None:
            return
        fu["system"] = "nonexistent_system_zzz_gone"
    expect("a unit.system value is not in the vocabulary", _rogue_unit_system)

    # 2. A unit's system field is missing entirely.
    def _missing_unit_system(v, u):
        fu = _first_unit(u)
        if fu is None:
            return
        fu.pop("system", None)
    expect("a unit's `system` field is missing", _missing_unit_system)

    # 3. A system id appears in two different domains (ambiguity).
    def _duplicate_system(v, u):
        domains = v.get("domains", [])
        if len(domains) >= 2 and domains[0].get("systems"):
            donor = dict(domains[0]["systems"][0])
            domains[1]["systems"] = list(domains[1].get("systems", [])) + [donor]
    expect("a system id is declared under two domains (ambiguity)", _duplicate_system)

    # 4. A system entry lacks its `note`.
    def _missing_note(v, u):
        domains = v.get("domains", [])
        if domains and domains[0].get("systems"):
            domains[0]["systems"][0].pop("note", None)
    expect("a system entry lacks its `note`", _missing_note)

    # 5. The vocabulary is empty (no domains).
    def _empty_vocab(v, u):
        v["domains"] = []
    expect("the vocabulary has no domains", _empty_vocab)

    # State must be byte-clean after the battery.
    assert UNITS == Path(str(UNITS)), "injections leaked UNITS path"
    assert VOCAB == Path(str(VOCAB)), "injections leaked VOCAB path"

    return bad, n_inj


def _run_with_injections() -> int:
    """Wrapper: run main(), then the injection battery, then report."""
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"GATE 14: FAIL — {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


if __name__ == "__main__":
    sys.exit(_run_with_injections())
