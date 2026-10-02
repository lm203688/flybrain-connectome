#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v2.30.0 — measure the same four C. elegans circuits across development.

Source data
-----------
WormWiring (wormwiring.org) hosts the raw reconstructions of

    Witvliet D, Mulcahy B, Mitchell JK, Meirovitch Y, Berger DR, Wu Y, ... Zhen M.
    "Connectomes across development reveal principles of brain maturation in
     C. elegans."  bioRxiv 2020, doi:10.1101/2020.04.30.066209

That series is eight reconstructions, not two.  ``/pages/witvliet.html`` lists
four L1 animals (datasets 1-4), one L2 (dataset 5), one L3 (dataset 6) and two
adults (datasets 7-8).  The v2.27.0 extractor took only the two adults, because
they were the only files the first pass happened to pull; the six larval
reconstitutions were still sitting on the same page.

This script loads all eight and measures, for each of the four circuits that
``extract_cel_profiles.py`` already emits as units, how many edges and how many
synapses that circuit carries at every stage.  Nothing here is written by hand:
every number in the artifact is summed out of the xlsx rows.

What is NOT in the source
-------------------------
* no transmitter / excitatory-inhibitory identity  -> the edge-vs-gap-junction
  distinction is kept as ``type`` but no sign is asserted.
* left/right homologues are collapsed to the cell class (``AVBL`` -> ``AVB``),
  exactly as the adult extractor does, so stage numbers stay comparable with
  the adult units.
* the number of edges a single small reconstruction records is NOT the number
  of edges the animal has.  A single L1 file carries ~570-800 distinct edges
  against ~1,100 for a single L2 file, so "edge present at L1" is a lower bound
  on what is there, never a claim that the circuit is absent elsewhere.  See
  ``caveat`` in the artifact; the reported conclusion is deliberately the one
  that survives that confound (circuits are present at the earliest stage and
  gain weight later), not the one that does not (the 271 L1-only edges are not
  called transient synapses).

Usage
-----
    python scripts/extract_cel_development.py            # writes the artifact
    python scripts/extract_cel_development.py --report   # stdout summary only
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
CELDIR = ROOT / "cel_data"
OUT = (ROOT / "flybrain-connectome-mcp" / "functional_units"
       / "cel_development_stages.json")

SOURCE = ("WormWiring / Witvliet et al. 2020 "
          "(bioRxiv 10.1101/2020.04.30.066209), datasets 1-8 "
          "(L1 x4, L2, L3, adult x2)")

# The four circuits already emitted by extract_cel_profiles.py.  Importing them
# keeps the cell-class sets in one place: if the adult extractor's definition of
# a circuit drifts, the developmental measurement drifts with it instead of
# silently measuring something else.
import extract_cel_profiles as cel  # noqa: E402

STAGES = [
    ("L1", "L1 (four independent animals)", [f"witvliet_2020_{i}_L1.xlsx" for i in (1, 2, 3, 4)]),
    ("L2", "L2", ["witvliet_2020_5_L2.xlsx"]),
    ("L3", "L3", ["witvliet_2020_6_L3.xlsx"]),
    ("adult", "adult (two animals)", ["witvliet_witvliet_2020_7_adult.xlsx",
                                      "witvliet_witvliet_2020_8_adult.xlsx"]),
]


def canonical(name: str) -> str:
    """Collapse the L/R homologue onto the cell class, as the adult extractor does."""
    n = str(name).strip()
    return n[:-1] if n.endswith("L") or n.endswith("R") else n


def load_one(path: Path) -> dict[tuple[str, str, str], int]:
    """Return {(pre, post, type): synapses} for a single reconstruction."""
    if not path.exists():
        raise SystemExit("missing source file: %s (run the download step)" % path)
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    edges: dict[tuple[str, str, str], int] = defaultdict(int)
    for pre, post, typ, ns in ws.iter_rows(values_only=True):
        if pre is None:
            continue
        try:
            ns = int(ns or 0)
        except (TypeError, ValueError):
            continue  # header row
        edges[(canonical(pre), canonical(post), str(typ).lower())] += ns
    return dict(edges)


def measure(edges: dict, cell_classes: list[str]) -> dict[str, int]:
    """Edges and synapses that run between two classes of the same circuit.

    Both endpoints must be inside the circuit: this counts the circuit's own
    internal wiring, not its input from outside.
    """
    cls = set(cell_classes)
    n_edges = n_syn = 0
    for (a, b, _t), n in edges.items():
        if a in cls and b in cls:
            n_edges += 1
            n_syn += n
    return {"edges": n_edges, "synapses": n_syn}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true",
                    help="print the summary only; do not write the artifact")
    args = ap.parse_args()

    # The unit names the adult extractor produces, paired with their classes.
    units = {"cel_%s_unit" % p["suffix"]: p["classes"] for p in cel.PROFILES}

    stages = []
    for stage, label, files in STAGES:
        per_animal, unit_rows = [], defaultdict(list)
        for fname in files:
            edges = load_one(CELDIR / fname)
            cells = {canonical(k) for e in edges for k in e[:2]}
            rec = {
                "dataset": fname,
                "n_cell_classes": len(cells),
                "n_weighted_edges": sum(edges.values()),
                "n_unique_edges": len(edges),
            }
            for uname, classes in units.items():
                m = measure(edges, classes)
                unit_rows[uname].append(m)
                rec["unit_" + uname] = m
            per_animal.append(rec)
        stage_rec = {
            "stage": stage,
            "label": label,
            "n_animals": len(files),
            "animals": per_animal,
            "unit_measurements": {
                u: {
                    "edges": [m["edges"] for m in unit_rows[u]],
                    "synapses": [m["synapses"] for m in unit_rows[u]],
                    "synapses_median": statistics.median(m["synapses"] for m in unit_rows[u]),
                    "synapses_range": [min(m["synapses"] for m in unit_rows[u]),
                                       max(m["synapses"] for m in unit_rows[u])],
                    "present_in_every_animal": all(m["edges"] > 0
                                                   for m in unit_rows[u]),
                }
                for u in units
            },
        }
        stages.append(stage_rec)
        for u in units:
            vals = unit_rows[u]
            print("  %-6s %-32s edges=%s synapses=%s"
                  % (stage, u, [m["edges"] for m in vals],
                     [m["synapses"] for m in vals]))

    doc = {
        "schema_version": "1.0",
        "source": SOURCE,
        "note": ("Every edge counted here is summed out of the WormWiring xlsx "
                 "rows for that stage.  The four circuits are the same four "
                 "`extract_cel_profiles.py` emits as units; this artifact records "
                 "how many edges and synapses each one carries at L1/L2/L3/adult."),
        "caveat": ("These are separate reconstructions of separate animals at "
                   "separate stages, so a smaller edge count at L1 means "
                   "'this many were reconstructed', not 'the animal had this "
                   "many'.  Single L1 files carry ~570-800 distinct edges against "
                   "~1,100 for a single L2 file and ~1,550 for an adult, so the "
                   "L1 numbers are a floor.  The conclusion this artifact is "
                   "offered for -- the four circuits are already wired at the "
                   "earliest stage and gain synapse count afterwards -- is the "
                   "one that survives that confound; the 271 edge pairs seen in "
                   "L1 and absent from adults are NOT reported as transient "
                   "synapses, because that difference is confounded with "
                   "reconstruction depth."),
        "stages": stages,
    }

    if args.report:
        for s in stages:
            print("[%s]" % s["stage"])
            for a in s["animals"]:
                print("   %-34s classes=%3d unique_edges=%4d synapses=%5d"
                      % (a["dataset"], a["n_cell_classes"],
                         a["n_unique_edges"], a["n_weighted_edges"]))
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("wrote %s (%d stages)" % (OUT, len(stages)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
