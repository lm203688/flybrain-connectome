#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE 21 -- functional-unit library is retrievable by canonical capability axis.

T2 of the foundation roadmap turns the 331 free-text ``capability`` values
(300 used exactly once) into a retrieval axis.  ``flybrain-connectome-mcp/
capability_canonical.py`` pins 22 canonical categories (20 functional +
``provenance_marker`` + ``other_unspecified``) and a deterministic
token-based classifier.  This gate:

  1. asserts the canonical taxonomy still has exactly 22 categories
     (a removed/renamed category would silently break retrieval);
  2. asserts every unit maps to one of the 21 non-provenance categories
     (100% coverage);
  3. asserts every one of the 331 capability *strings* classifies with
     confidence ``high`` -- a free-text value that fell through to
     ``other_unspecified`` is a vocabulary drift signal and fails closed;
  4. asserts the two known provenance markers (``traced_connectome``,
     ``measure_synapses``) route to ``provenance_marker`` and are NOT counted
     as functional capabilities (they describe how a unit was derived, not
     what it does);
  5. asserts no unit has ``provenance_marker`` as its PRIMARY category
     (provenance is metadata, not function);
  6. emits ``docs/capability_coverage.json`` -- the 22 x clade readiness
     matrix the roadmap asks for, so gaps are visible rather than guessed;
  7. runs fail-closed injections: a gate that stays green against a removed
     category, a silenced marker, and a hollowed classifier is a gate that
     was never going to catch anything.

The map is deterministic: re-running yields identical output.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
CC = MCP / "capability_canonical.py"
OUT = ROOT / "docs" / "capability_coverage.json"

sys.path.insert(0, str(MCP))
import capability_canonical as cc_mod  # noqa: E402

EXPECTED_CATEGORIES = 22
PROVENANCE_MARKERS = ("traced_connectome", "measure_synapses")


def fail(msg: str) -> int:
    print("GATE 21: FAIL -- %s" % msg)
    return 1


def ok(msg: str) -> int:
    print("GATE 21: PASS -- %s" % msg)
    return 0


def evaluate() -> list[tuple[str, bool, str]]:
    """Run every assertion and return [(label, passed, detail)].

    Reading module globals dynamically (``cc_mod.X``) rather than closing
    over values is deliberate: the fail-closed injections below patch those
    globals to prove each assertion actually bites.
    """
    rows: list[tuple[str, bool, str]] = []

    def rec(label: str, cond: bool, detail: str = "") -> None:
        rows.append((label, bool(cond), detail))

    if not CC.exists():
        rec("taxonomy module present", False, "capability_canonical.py missing")
        return rows

    cats = cc_mod.CANON_IDS
    rec("taxonomy has 22 categories", len(cats) == EXPECTED_CATEGORIES,
        "canonical taxonomy has %d categories, expected %d"
        % (len(cats), EXPECTED_CATEGORIES))

    units = cc_mod.load_units()
    mp = cc_mod.build_map()

    # ---- 1. every unit maps, to a known category ----
    rec("map covers every unit", len(mp) == len(units),
        "map covers %d units but library has %d" % (len(mp), len(units)))
    miss = [u["name"] for u in units if u["name"] not in mp]
    rec("no unit unmapped", not miss, "unmapped: %s" % ", ".join(miss[:4]))
    catset = set(cats)
    unk = ["%s -> %r" % (n, mp[n]["primary_category"])
           for n, v in mp.items() if v["primary_category"] not in catset]
    rec("every category is known", not unk,
        "unknown category: %s" % ", ".join(unk[:4]))

    # ---- 2. every capability STRING classifies high-confidence ----
    cap_mp = cc_mod.build_capability_map()
    low = {cap: v["category"] for cap, v in cap_mp.items()
           if v["confidence"] != "high"}
    rec("every capability string high-confidence", not low,
        "%d/%d low-confidence: %s%s"
        % (len(low), len(cap_mp), sorted(low)[:5],
           " ..." if len(low) > 5 else ""))

    # ---- 3. provenance markers route to provenance_marker, not function ----
    for marker in PROVENANCE_MARKERS:
        rec("marker %r in vocabulary" % marker, marker in cap_mp,
            "marker absent from capability vocabulary")
        routed = cap_mp.get(marker, {}).get("category")
        rec("marker %r routes to provenance_marker" % marker,
            routed == "provenance_marker",
            "routed to %r instead" % routed)
    contam = cc_mod.provenance_contamination()
    rec("contamination reported", bool(contam),
        "provenance_contamination() returned empty -- the known markers were "
        "silently dropped")

    # ---- 4. no unit's PRIMARY category is provenance_marker ----
    prov_primary = [n for n, v in mp.items() if v["primary_category"] == "provenance_marker"]
    rec("no unit has provenance as primary", not prov_primary,
        "provenance is metadata, not function: %s" % ", ".join(prov_primary[:4]))

    return rows


def _diagnostics():
    """Build the 22 x clade x evidence readiness matrix (side effect only)."""
    units = cc_mod.load_units()
    mp = cc_mod.build_map()
    clade_total: Counter = Counter()
    per: dict[str, dict] = {}
    for u in units:
        cat = mp[u["name"]]["primary_category"]
        clade = cc_mod.clade_of(u)
        clade_total[clade] += 1
        d = per.setdefault(cat, {
            "n_units": 0, "clades": defaultdict(int),
            "evidence_with_ref": 0, "low_conf": 0,
        })
        d["n_units"] += 1
        d["clades"][clade] += 1
        prov = u.get("provenance") or {}
        if prov.get("biological_reference") or u.get("biological_reference"):
            d["evidence_with_ref"] += 1
        if mp[u["name"]]["confidence"] == "low":
            d["low_conf"] += 1

    matrix, gaps = {}, []
    for cid in cc_mod.CANON_IDS:
        d = per.get(cid, {"n_units": 0, "clades": defaultdict(int),
                          "evidence_with_ref": 0, "low_conf": 0})
        clades = dict(d["clades"])
        clade_width = len(clades)
        ev = round(d["evidence_with_ref"] / d["n_units"], 3) if d["n_units"] else 0.0
        # A category is a "gap" if it is empty OR spans fewer than 2 clades
        # with thin coverage (roadmap T2: "每类别补类群宽度").
        is_gap = (d["n_units"] == 0) or (clade_width < 2 and d["n_units"] < 3)
        if is_gap:
            gaps.append(cid)
        matrix[cid] = {
            "label": cc_mod.CANONICAL[cid]["label"],
            "n_units": d["n_units"],
            "clade_width": clade_width,
            "clades": clades,
            "evidence_fraction": ev,
            "low_confidence": d["low_conf"],
            "gap": is_gap,
        }
    return units, mp, matrix, gaps, clade_total


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: inject one defect at a time.

    Each case has an explicit ``apply`` and ``restore`` pair, re-runs every
    assertion, and asserts the gate goes red.  Applying and restoring MUST be
    separate operations: for mutation-style patches (``pop``, ``append``,
    ``clear``) calling the same callable twice compounds the defect instead of
    undoing it, which silently poisons every later injection with state it did
    not create.

    A gate that stays green against all of these is a gate that was never
    going to catch anything -- the same discipline Gate 10 applies to its 17
    embodiment injections.
    """
    bad = 0
    n_inj = 0

    real_classify = cc_mod.classify
    real_classify_unit = cc_mod.classify_unit
    real_contam = cc_mod.provenance_contamination
    real_override = dict(cc_mod.EXACT_OVERRIDE)
    real_ids = list(cc_mod.CANON_IDS)
    real_map = cc_mod.build_map
    first_unit = cc_mod.load_units()[0]["name"]

    def expect(name: str, apply_fn, restore_fn) -> None:
        nonlocal bad, n_inj
        n_inj += 1
        apply_fn()
        try:
            rows = evaluate()
        finally:
            restore_fn()
        hits = [d for _l, passed, d in rows if not passed]
        if hits:
            print("    [PASS] injecting: %s -> %s" % (name, hits[0][:110]))
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    expect("a category is removed from the taxonomy",
           lambda: setattr(cc_mod, "CANON_IDS", real_ids[:-1]),
           lambda: setattr(cc_mod, "CANON_IDS", real_ids))

    expect("a category is silently added (taxonomy grows)",
           lambda: setattr(cc_mod, "CANON_IDS", real_ids + ["synthetic_extra"]),
           lambda: setattr(cc_mod, "CANON_IDS", real_ids))

    expect("one capability string falls through to other_unspecified",
           lambda: setattr(
               cc_mod, "classify",
               lambda c, _r=real_classify: ("other_unspecified", "low")
               if c == "relay" else _r(c)),
           lambda: setattr(cc_mod, "classify", real_classify))

    expect("a provenance marker is routed to a functional category",
           lambda: setattr(
               cc_mod, "classify",
               lambda c, _r=real_classify: ("relay_route", "high")
               if c == "traced_connectome" else _r(c)),
           lambda: setattr(cc_mod, "classify", real_classify))

    expect("provenance_contamination() is hollowed out",
           lambda: setattr(cc_mod, "provenance_contamination", lambda: {}),
           lambda: setattr(cc_mod, "provenance_contamination", real_contam))

    expect("a unit's PRIMARY category becomes provenance_marker",
           lambda: setattr(
               cc_mod, "classify_unit",
               lambda u, _r=real_classify_unit:
               ("provenance_marker", "high", ["provenance_marker"])
               if u["name"] == first_unit else _r(u)),
           lambda: setattr(cc_mod, "classify_unit", real_classify_unit))

    expect("the unit map is empty (coverage silently lost)",
           lambda: setattr(cc_mod, "build_map", lambda: {}),
           lambda: setattr(cc_mod, "build_map", real_map))

    expect("the exact-string override table is emptied",
           lambda: cc_mod.EXACT_OVERRIDE.clear(),
           lambda: cc_mod.EXACT_OVERRIDE.update(real_override))

    # Regression witness (not an injection): the classifier is token-based
    # precisely because keyword rules like "associative_learn" in "associate"
    # miss when the keyword is *longer* than the string.  Confirm the short
    # form still resolves, so a future refactor back to substring matching is
    # caught here rather than in production.
    got = real_classify("associate")
    witness_ok = got[0] == "associative_learning"
    print("    [%s] witness: token matching resolves short form %r -> %r"
          % ("PASS" if witness_ok else "FAIL", "associate", got[0]))
    if not witness_ok:
        bad += 1

    # State must be byte-clean after the battery, otherwise the matrix that
    # follows is built from a contaminated taxonomy.
    assert cc_mod.CANON_IDS == real_ids, "injections leaked taxonomy state"
    assert cc_mod.EXACT_OVERRIDE == real_override, "injections leaked overrides"

    return bad, n_inj


def main() -> int:
    rows = evaluate()
    bad = [(l, d) for l, passed, d in rows if not passed]
    if bad:
        first = bad[0]
        return fail("%s: %s" % (first[0], first[1]))

    units, mp, matrix, gaps, clade_total = _diagnostics()
    cap_mp = cc_mod.build_capability_map()
    contam = cc_mod.provenance_contamination()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": "1.0",
        "n_canonical": len(cc_mod.CANON_IDS),
        "n_units": len(units),
        "n_capability_strings": len(cap_mp),
        "coverage_pct": 100.0,
        "clade_totals": dict(clade_total),
        "gaps": gaps,
        "provenance_contamination": {k: len(v) for k, v in contam.items()},
        "matrix": matrix,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  matrix written: %s" % OUT)
    print("  categories: %d | units: %d | capability strings: %d | coverage: 100%%"
          % (len(cc_mod.CANON_IDS), len(units), len(cap_mp)))
    print("  gap categories (empty or thin clade width): %s" % (gaps or "none"))
    print("  provenance markers routed away from function: %s"
          % ", ".join("%s(%d)" % (k, len(v)) for k, v in sorted(contam.items())))

    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        return fail("%d/%d fail-closed injections did not turn the gate red"
                    % (inj_bad, n_inj))

    return ok("%d units mapped across %d categories; %d/%d capability strings "
              "high-confidence; %d gap categories declared; %d fail-closed "
              "injections confirmed red"
              % (len(units), len(cc_mod.CANON_IDS),
                 len(cap_mp), len(cap_mp), len(gaps), n_inj))


if __name__ == "__main__":
    sys.exit(main())
