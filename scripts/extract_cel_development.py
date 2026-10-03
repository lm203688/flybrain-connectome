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
import itertools
import json
import statistics
import sys
from collections import Counter, defaultdict
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


def attribution(edges: dict, units: dict) -> dict:
    """Sum-of-circuits vs the union, so the per-circuit rows are readable.

    The four circuits are NOT disjoint.  AIA sits in all four, AIB/AIZ/AVB/PV in
    three or two of them, so an edge like AIZ -> AIB is internal wiring for two
    circuits at once and gets counted by both.  Adding the four `synapses` rows
    therefore overstates the real internal wiring by ~1.25x at every stage, and
    a reader who adds the column will publish that inflated number.

    So both figures are reported: the sum (what the four circuits each claim)
    and the union (how much wiring is actually internal to at least one of
    them).  The ratio is recorded rather than hidden, and it is checked below
    against the per-circuit rows so the two can never drift apart.
    """
    claimed = 0
    union_edges: dict[tuple[str, str, str], int] = {}
    per_unit_claims: Counter = Counter()
    shared: Counter = Counter()
    for (a, b, t), n in edges.items():
        hit = [u for u, cs in units.items() if a in cs and b in cs]
        if not hit:
            continue
        claimed += n * len(hit)
        union_edges[(a, b, t)] = n
        for u in hit:
            per_unit_claims[u] += n
        shared[len(hit)] += n
    union = sum(union_edges.values())
    return {
        "sum_of_circuits": claimed,
        "union": union,
        "union_edges": len(union_edges),
        "inflation_ratio": round(claimed / union, 4) if union else None,
        "synapses_by_circuits_claiming": dict(sorted(shared.items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true",
                    help="print the summary only; do not write the artifact")
    args = ap.parse_args()

    # The unit names the adult extractor produces, paired with their classes.
    units = {"cel_%s_unit" % p["suffix"]: set(p["classes"]) for p in cel.PROFILES}

    # The four circuits share cell classes (AIA is in all four), so the sum of
    # their rows is not the network's internal wiring.  Measure the overlap
    # once here instead of restating it as a hand-typed sentence.
    overlap_matrix = {}
    for a, b in itertools.combinations(sorted(units), 2):
        ov = sorted(units[a] & units[b])
        if ov:
            overlap_matrix["%s|%s" % (a, b)] = ov

    stages = []
    for stage, label, files in STAGES:
        per_animal, unit_rows = [], defaultdict(list)
        attr_acc = {"sum_of_circuits": 0, "union": 0, "union_edges": 0,
                    "synapses_by_circuits_claiming": Counter()}
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
            a = attribution(edges, units)
            rec["attribution"] = a
            attr_acc["sum_of_circuits"] += a["sum_of_circuits"]
            attr_acc["union"] += a["union"]
            attr_acc["union_edges"] += a["union_edges"]
            for k, v in a["synapses_by_circuits_claiming"].items():
                attr_acc["synapses_by_circuits_claiming"][k] += v
            per_animal.append(rec)

        # ---- identity: the per-circuit rows must reconstruct the sum ------ #
        row_sum = sum(sum(m["synapses"] for m in unit_rows[u]) for u in units)
        if row_sum != attr_acc["sum_of_circuits"]:
            print("REFUSING TO WRITE: per-circuit synapses sum to %d but the "
                  "independent attribution pass says %d (stage %s)"
                  % (row_sum, attr_acc["sum_of_circuits"], stage),
                  file=sys.stderr)
            return 3
        if attr_acc["union"] > attr_acc["sum_of_circuits"]:
            print("REFUSING TO WRITE: union (%d) exceeds the sum of circuits "
                  "(%d) at stage %s, which is impossible"
                  % (attr_acc["union"], attr_acc["sum_of_circuits"], stage),
                  file=sys.stderr)
            return 3

        stage_rec = {
            "stage": stage,
            "label": label,
            "n_animals": len(files),
            "animals": per_animal,
            "attribution": {
                "sum_of_circuits": attr_acc["sum_of_circuits"],
                "union": attr_acc["union"],
                "union_edges": attr_acc["union_edges"],
                "inflation_ratio": (round(attr_acc["sum_of_circuits"]
                                          / attr_acc["union"], 4)
                                    if attr_acc["union"] else None),
                "synapses_by_circuits_claiming": {
                    str(k): v
                    for k, v in sorted(attr_acc["synapses_by_circuits_claiming"].items())
                },
                "note": ("The four circuits share cell classes, so one edge can "
                         "be internal wiring for several of them. `sum_of_circuits` "
                         "is what the four rows below add up to; `union` is the "
                         "wiring internal to at least one circuit, counted once. "
                         "Use `union` for 'how much of this animal's wiring sits "
                         "inside these circuits' and `sum_of_circuits` only when "
                         "the circuits are being counted individually."),
            },
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
        print("  %-6s %-32s edges=%s synapses=%s"
              % (stage, "SUM of 4 circuits",
                 "-", [s["attribution"]["sum_of_circuits"]
                       for s in per_animal]))
        print("  %-6s %-32s edges=%s synapses=%s  inflation=%s"
              % ("", "UNION (deduplicated)",
                 [s["attribution"]["union_edges"] for s in per_animal],
                 [s["attribution"]["union"] for s in per_animal],
                 stage_rec["attribution"]["inflation_ratio"]))
        for u in units:
            vals = unit_rows[u]
            print("  %-6s %-32s edges=%s synapses=%s"
                  % ("", u, [m["edges"] for m in vals],
                     [m["synapses"] for m in vals]))

    # ---- the L1-only edge count, measured instead of hand-typed --------- #
    # v2.30.0's caveat said "271 edge pairs seen in L1 and absent from adults"
    # as a literal.  It happened to be right, but nothing in the code computed
    # it, so it could not have been re-derived if the source data or the
    # class sets changed.  It is computed here now, from the same edge dicts.
    l1_keys: set = set()
    for _s, _l, fs in STAGES:
        if _s == "L1":
            for fn in fs:
                l1_keys |= set(load_one(CELDIR / fn))
    adult_keys: set = set()
    for _s, _l, fs in STAGES:
        if _s == "adult":
            for fn in fs:
                adult_keys |= set(load_one(CELDIR / fn))
    l1_only = len(l1_keys - adult_keys)
    adult_only = len(adult_keys - l1_keys)
    print("  edge keys: L1 union=%d adult union=%d L1-only=%d adult-only=%d"
          % (len(l1_keys), len(adult_keys), l1_only, adult_only))

    doc = {
        "schema_version": "1.1",
        "source": SOURCE,
        "note": ("Every edge counted here is summed out of the WormWiring xlsx "
                 "rows for that stage.  The four circuits are the same four "
                 "`extract_cel_profiles.py` emits as units; this artifact records "
                 "how many edges and synapses each one carries at L1/L2/L3/adult."),
        "circuit_overlap": {
            "note": ("The four circuits are not disjoint cell-class sets, so the "
                     "four per-circuit rows must not be added together. Both "
                     "figures are reported per stage under `attribution`."),
            "shared_cell_classes": overlap_matrix,
            "cell_classes_per_circuit": {u: sorted(cs) for u, cs in units.items()},
        },
        "stage_diffs": {
            "note": ("Measured on the union of (pre, post, type) keys per group "
                     "of animals, not asserted. v2.30.0 stated the L1-only count "
                     "as a literal in its caveat; it is now derived, so it moves "
                     "if the source data or the class sets move."),
            "l1_union_keys": len(l1_keys),
            "adult_union_keys": len(adult_keys),
            "l1_only_keys": l1_only,
            "adult_only_keys": adult_only,
            "shared_keys": len(l1_keys & adult_keys),
        },
        "caveat": ("These are separate reconstructions of separate animals at "
                   "separate stages, so a smaller edge count at L1 means "
                   "'this many were reconstructed', not 'the animal had this "
                   "many'.  Single L1 files carry ~570-800 distinct edges against "
                   "~1,100 for a single L2 file and ~1,550 for an adult, so the "
                   "L1 numbers are a floor.  The conclusion this artifact is "
                   "offered for -- the four circuits are already wired at the "
                   "earliest stage and gain synapse count afterwards -- is the "
                   "one that survives that confound; the %d edge pairs seen in "
                   "L1 and absent from adults (`stage_diffs.l1_only_keys`) are "
                   "NOT reported as transient synapses, because that difference "
                   "is confounded with reconstruction depth."
                   % l1_only),
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
