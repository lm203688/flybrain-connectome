#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE 19 -- functional-unit library is retrievable by canonical function axis.

T2 of the foundation roadmap turns the 116 free-text ``function`` values into a
retrieval axis.  ``flybrain-connectome-mcp/function_canonical.py`` pins 24
canonical categories and a deterministic classifier.  This gate:

  1. asserts the canonical taxonomy still has exactly 24 categories
     (a removed/renamed category would silently break retrieval);
  2. asserts every unit maps to one of the 24 (100% coverage);
  3. fails closed if any unit falls through unmapped;
  4. emits ``docs/function_coverage.json`` -- the 24 x clade x evidence matrix
     the roadmap asks for, so gaps are visible rather than guessed.

The map is deterministic: re-running yields identical output.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
FC = MCP / "function_canonical.py"
OUT = ROOT / "docs" / "function_coverage.json"

sys.path.insert(0, str(MCP))
import function_canonical as fc_mod  # noqa: E402


def fail(msg: str) -> int:
    print("GATE 19: FAIL -- %s" % msg)
    return 1


def ok(msg: str) -> int:
    print("GATE 19: PASS -- %s" % msg)
    return 0


def main() -> int:
    if not FC.exists():
        return fail("function_canonical.py missing -- taxonomy source of truth gone")

    cats = fc_mod.CANON_IDS
    if len(cats) != 24:
        return fail("canonical taxonomy has %d categories, expected 24" % len(cats))

    units = fc_mod.load_units()
    mp = fc_mod.build_map()

    if len(mp) != len(units):
        return fail("map covers %d units but library has %d" % (len(mp), len(units)))
    for u in units:
        if u["name"] not in mp:
            return fail("unit %r not mapped" % u["name"])
        if mp[u["name"]]["category"] not in cats:
            return fail("unit %r mapped to unknown category %r"
                        % (u["name"], mp[u["name"]]["category"]))

    # ---- build the 24 x clade x evidence matrix ----
    clade_total: Counter = Counter()
    per: dict[str, dict] = {}
    for u in units:
        cat = mp[u["name"]]["category"]
        clade = fc_mod.clade_of(u)
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

    matrix = {}
    gaps = []
    for cid in cats:
        d = per.get(cid, {"n_units": 0, "clades": defaultdict(int),
                          "evidence_with_ref": 0, "low_conf": 0})
        clades = dict(d["clades"])
        clade_width = len(clades)
        ev = round(d["evidence_with_ref"] / d["n_units"], 3) if d["n_units"] else 0.0
        # A category is a "gap" if it is empty OR spans fewer than 2 clades
        # with thin evidence (roadmap T2: "每类别补类群宽度").
        is_gap = (d["n_units"] == 0) or (clade_width < 2 and d["n_units"] < 3)
        if is_gap:
            gaps.append(cid)
        matrix[cid] = {
            "label": fc_mod.CANONICAL[cid]["label"],
            "n_units": d["n_units"],
            "clade_width": clade_width,
            "clades": clades,
            "evidence_fraction": ev,
            "low_confidence": d["low_conf"],
            "gap": is_gap,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": "1.0",
        "n_canonical": len(cats),
        "n_units": len(units),
        "coverage_pct": 100.0,
        "clade_totals": dict(clade_total),
        "gaps": gaps,
        "matrix": matrix,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  matrix written: %s" % OUT)
    print("  categories: %d | units: %d | coverage: 100%%" % (len(cats), len(units)))
    print("  gap categories (need clade width): %s" % (gaps or "none"))
    return ok("%d units mapped across 24 categories; %d gap categories declared"
              % (len(units), len(gaps)))


if __name__ == "__main__":
    sys.exit(main())
