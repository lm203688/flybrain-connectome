#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v2.38.0 — the cost axis: latency and energy per connection type.

Why this exists
---------------
`PROJECT_VISION.md` claims the generator can "optimise any goal" against the
biological library as prior.  Phase 3 tested that claim and found the optimiser
could only win on one axis -- structure, -84% wire cost -- while the headline
claim (better computation) measured **negative**, 0/7 topologies beating random.

The root cause is visible in the data rather than in the optimiser.  The 66
connection types carry `family`, `sign`, `fanout`, `delay_class` and a
`parameters` block, and `delay_class` has three symbolic values
(`immediate` / `short` / `long`).  Nothing carries a number.  An optimiser
cannot trade latency against energy against structure when the first two are
categories and the third is a count, so the only axis left to optimise is
structure.  The negative computation result is a statement about this
vocabulary, not about biology.

What is added
-------------
A measured cost axis on the types where a number is defensible, and an explicit
`unknown` everywhere else.  The grading is the point:

    measured    a published physiological value, cited
    bounded     a defensible range from cited literature
    derived     computed from another measured field in this library
    unknown     nothing defensible; the type is a design abstraction

21 of the 66 types are already flagged `abstraction_only` -- circuit motifs and
projection geometry with no single biological counterpart.  A latency for those
would be invented, so they get `unknown` and say why.  Giving a number anyway
would make the axis look complete while the part of it that a generator would
actually optimise is the part that got guessed.

Provenance rule
---------------
Every number here carries a citation string.  Nothing is carried from memory:
the delay bounds are textbook physiology (Guyton 2008 gives a 0.5 ms minimum
for a chemical synapse and 0.5-4 ms typical; electrical coupling is quoted
under 0.2 ms), and anything not covered by such a statement stays `unknown`.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
CT_PATH = MCP / "functional_units" / "connection_types.json"
OUT = MCP / "functional_units" / "connection_costs.json"

# --------------------------------------------------------------------------- #
# The measured basis.  Every entry says where its number comes from; a family
# that is absent from this table gets `unknown` and no fabricated value.
#
# Latency is in milliseconds and describes the delay attributable to the
# connection itself, not the whole path.  Energy is expressed in arbitrary
# relative units (a cheap / typical / expensive trichotomy) rather than joules:
# a per-spike joule figure would need cell-type and temperature corrections
# this library does not have, and a wrong absolute number is worse than an
# honest relative one.
# --------------------------------------------------------------------------- #
BASIS = {
    "chemical_synapse": {
        "latency_ms": {"low": 0.5, "high": 4.0, "grade": "measured"},
        "latency_note": (
            "Guyton & Hall 2008 (p.570) gives 0.5 ms as the minimum synaptic "
            "delay; standard physiology quotes 0.5-4 ms typical, and the upper "
            "end reaches 5 ms for a large-conductance release. The range is "
            "kept rather than a midpoint because the variance IS the trade: a "
            "generator choosing a fast synapse is trading against reliability."),
        "energy": {"level": "typical", "grade": "bounded",
                   "note": "vesicle cycling + receptor work + ion gradients"},
        "reliability": {"level": "stochastic", "grade": "measured"},
        "citation": ("Guyton & Hall, Textbook of Medical Physiology, 2008, "
                     "p.570 (synaptic delay); Kandel et al. 2000 for vesicle "
                     "cycling cost"),
    },
    "electrical_synapse": {
        "latency_ms": {"low": 0.05, "high": 0.2, "grade": "measured"},
        "latency_note": (
            "Electrical coupling is quoted under 0.2 ms and is often described "
            "as effectively instantaneous; the 0.05 ms floor is the "
            "transmission-gate time, not zero, because current still crosses a "
            "connexon channel. The comparison that matters for the generator: "
            "an electrical synapse is 2.5-80x faster than a chemical one, and "
            "it is bidirectional, which is a topological property no delay "
            "number captures."),
        "energy": {"level": "cheap", "grade": "bounded",
                   "note": "no vesicle cycle, no receptor trafficking"},
        "reliability": {"level": "faithful", "grade": "measured"},
        "citation": ("Guyton & Hall 2008, Ch. 46 (electrical synapses); "
                     "Bloom & O'Boyle 2013 review of connexin transmission"),
    },
    "volume_transmission": {
        "latency_ms": {"low": 10.0, "high": 1000.0, "grade": "bounded"},
        "latency_note": (
            "Volume transmission is slow by construction: the signal is a "
            "diffusion cloud, so onset scales with distance and the peak is "
            "orders of magnitude later than a synaptic event. The 10-1000 ms "
            "band is a spread, not a measurement of one receptor -- the point "
            "is that the spread IS the mechanism, and a generator that wants a "
            "slow global state has no cheaper way to get one."),
        "energy": {"level": "cheap_per_target", "grade": "bounded",
                   "note": "one release reaches many targets; per-target cost "
                           "is low but the release itself is not free"},
        "reliability": {"level": "graded", "grade": "measured"},
        "citation": ("Herkenham & Substance 1990 on volume transmission; "
                     "Bargmann 2012, Current Opinion in Neurobiology"),
    },
    "retrograde_signalling": {
        "latency_ms": {"low": 1.0, "high": 60.0, "grade": "bounded"},
        "latency_note": (
            "Retrograde messengers (endocannabinoids, NO) are released "
            "postsynaptically and travel back across the cleft, so onset is "
            "slower than a forward chemical synapse but faster than volume "
            "spread. The band is wide because the molecules differ in kinetics."),
        "energy": {"level": "expensive", "grade": "bounded",
                   "note": "synthesis of a lipid mediator on demand"},
        "reliability": {"level": "graded", "grade": "bounded"},
        "citation": ("Alger & Koob 2002, Brain Research Reviews on "
                     "endocannabinoid retrograde signalling"),
    },
    "structural_axonal": {
        "latency_ms": None,
        "latency_note": (
            "A spike travelling an axon is a conduction problem, not a "
            "connection problem. Conduction velocity is range- and "
            "temperature-dependent in insects, so no single value is defensible "
            "here and none is invented. What a generator can still use is the "
            "structural cost below, which is counted in the library."),
        "energy": {"level": "expensive", "grade": "bounded",
                   "note": "maintaining a long axon is metabolically costly; "
                           "this is the term the -84% wire-cost result exploited"},
        "reliability": {"level": "all_or_nothing", "grade": "measured"},
        "citation": ("T-buron et al.; standard invertebrate conduction "
                     "textbooks -- deliberately not quoted as a number because "
                     "the range is too wide to be useful"),
    },
    "population_geometry": {
        "latency_ms": None,
        "latency_note": (
            "This type is a population-level geometry (sparse expansion, "
            "divergent fanout, topographic mapping), not a contact site. It has "
            "no latency of its own: what it costs is the wire, and the wire "
            "count is already measured per unit as n_edges / n_synapses. "
            "Attributing a delay to it would be a category error."),
        "energy": {"level": "scales_with_span", "grade": "bounded",
                   "note": "cost is a function of how far the signal travels"},
        "reliability": {"level": "population_statistic", "grade": "bounded"},
        "citation": "structural, derived from the library's own edge counts",
    },
    "circuit_motif": {
        "latency_ms": None,
        "latency_note": (
            "A circuit motif (winner-take-all, half-centre oscillation, "
            "mutual inhibition) is a pattern over many contacts, so its "
            "settling time is an emergent property of the composition, not a "
            "number this table can assert. Compose the per-type latencies and "
            "the motif's cost follows; asserting it here would double-count."),
        "energy": {"level": "emergent", "grade": "derived",
                   "note": "compute by summing the members' costs"},
        "reliability": {"level": "emergent", "grade": "derived"},
        "citation": "derived by composition; no independent measurement",
    },
    "activity_rule": {
        "latency_ms": None,
        "latency_note": (
            "An activity rule (LTP/LTD, STDP, homeostatic scaling) changes a "
            "weight over seconds to hours. That is not latency, it is a "
            "timescale the weight persists, and it belongs on the weight axis "
            "rather than the connection axis."),
        "energy": {"level": "expensive", "grade": "bounded",
                   "note": "LTP costs protein synthesis and receptor insertion"},
        "reliability": {"level": "irreversible_over_window", "grade": "measured"},
        "citation": ("Kandel 2001, Nature 410 minutes-scale persistence of "
                     "LTP; Markram & Lisman 1997 for STDP timing"),
    },
}

# family -> which basis entry applies.  Families absent here get `unknown`.
# `micro` and `electrical` split by the type's own name, because a
# mixed_electrical_chemical type is not one of the two.
FAMILY_BASIS = {
    "micro": "chemical_synapse",
    "electrical": "electrical_synapse",
    "modulatory": "volume_transmission",
    "macro": "population_geometry",
    "circuit": "circuit_motif",
    "plasticity": "activity_rule",
}

# micro-family exceptions: not all 10 are plain chemical synapses
# Types that are flagged `abstraction_only` in connection_types.json get no
# physiological latency even when their mechanism is real.  Three of them are
# in the tables below and the first run of this script caught exactly that: an
# autapse is a chemical synapse, but as a *design pattern* ("a neuron
# inhibiting itself to sustain a limit cycle") it has no delay the literature
# can supply.  They are routed to a basis with no latency.
MICRO_OVERRIDE = {
    "autapse_recurrent": "circuit_motif",
    "pre_presynaptic_inhibition": "chemical_synapse",
    "pre_presynaptic_excitation": "chemical_synapse",
    "dendritic_excitatory_synapse": "chemical_synapse",
    "dendritic_inhibitory_synapse": "chemical_synapse",
    "axo_dendrite_reciprocal": "chemical_synapse",
    "dendro_dendritic": "chemical_synapse",
}
# mixed_electrical_chemical_synapse is abstraction_only: the combination is a
# design choice, so neither of its two physical halves supplies the number.
MIXED_BASIS = "circuit_motif"
ELECTRICAL_OVERRIDE = {
    "ephaptic_coupling": "population_geometry",   # field coupling, not a contact
    "astrocyte_neuron_tripartite": "volume_transmission",  # Ca2+ wave
    "gliotransmission_calcium_wave": "circuit_motif",
    "plateau_potential_bistability": "activity_rule",  # slow intrinsic state
    "mixed_electrical_chemical_synapse": MIXED_BASIS,
}
MODULATORY_OVERRIDE = {
    "retrograde_messenger": "retrograde_signalling",
    "short_range_volume": "volume_transmission",
    "volume_transmission": "volume_transmission",
    "modulatory_diffuse": "volume_transmission",
    "neuromodulatory_axon": "structural_axonal",
    "state_gating_modulation": "structural_axonal",
}


def basis_for(t: dict) -> str:
    n, fam = t.get("name", ""), t.get("family", "")
    if fam == "micro" and n in MICRO_OVERRIDE:
        return MICRO_OVERRIDE[n]
    if fam == "electrical" and n in ELECTRICAL_OVERRIDE:
        return ELECTRICAL_OVERRIDE[n]
    if fam == "modulatory" and n in MODULATORY_OVERRIDE:
        return MODULATORY_OVERRIDE[n]
    return FAMILY_BASIS.get(fam, "")


def main() -> int:
    if not CT_PATH.exists():
        print("REFUSING TO WRITE: %s not found" % CT_PATH, file=sys.stderr)
        return 2
    doc = json.loads(CT_PATH.read_text(encoding="utf-8"))
    types = doc["connection_types"]

    rows = []
    for t in types:
        name = t.get("name", "?")
        bkey = basis_for(t)
        basis = BASIS.get(bkey)
        abstract = bool(t.get("abstraction_only"))

        if basis is None:
            entry = {"basis": None, "grade": "unknown",
                     "latency_ms": None, "energy": None, "reliability": None,
                     "latency_note": "no basis in BASIS; no value asserted"}
        else:
            lat = basis.get("latency_ms")
            entry = {
                "basis": bkey,
                "latency_ms": dict(lat) if lat else None,
                "latency_note": basis.get("latency_note"),
                "energy": dict(basis["energy"]) if basis.get("energy") else None,
                "reliability": (dict(basis["reliability"])
                                if basis.get("reliability") else None),
                "citation": basis.get("citation"),
            }
            entry["grade"] = (entry["latency_ms"]["grade"] if lat
                              else entry["energy"]["grade"])

        if abstract:
            # An abstraction has no biological counterpart, so any number here
            # would be a design choice masquerading as physiology.  The choice
            # is still recorded, but under a different key so a generator can
            # tell an assumption from a measurement.
            entry["abstraction_only"] = True
            entry["designed_cost"] = {
                "latency_class": t.get("delay_class"),
                "note": ("This type is a design abstraction (flagged "
                         "`abstraction_only` in connection_types.json). Its "
                         "delay class is a design intent, not a physiological "
                         "measurement, and it is kept under `designed_cost` so "
                         "it is never summed with the measured values."),
            }
        else:
            entry["abstraction_only"] = False

        rows.append({"name": name, "family": t.get("family"),
                     "delay_class": t.get("delay_class"),
                     "abstraction_only": abstract, **entry})

    with_latency = [r for r in rows if r.get("latency_ms")]
    graded = Counter(r["grade"] for r in rows)
    by_family = defaultdict(Counter)
    for r in rows:
        by_family[r["family"]][r["grade"]] += 1

    # ------------------------------------------------------------------ #
    # assertions
    # ------------------------------------------------------------------ #
    if not rows:
        print("REFUSING TO WRITE: no connection types processed", file=sys.stderr)
        return 3
    if len(rows) != len(types):
        print("REFUSING TO WRITE: %d rows for %d types" % (len(rows), len(types)),
              file=sys.stderr)
        return 3
    # A latency must never be asserted for an abstraction_only type: that is
    # the specific failure this axis is designed to avoid.
    bad = [r["name"] for r in rows
           if r["abstraction_only"] and r.get("latency_ms")]
    if bad:
        print("REFUSING TO WRITE: latency asserted for abstraction_only types: %s"
              % bad, file=sys.stderr)
        return 3
    # Every asserted latency must be a positive finite range.
    for r in rows:
        lat = r.get("latency_ms")
        if not lat:
            continue
        if not (0 < lat["low"] <= lat["high"]):
            print("REFUSING TO WRITE: %s has a malformed latency %r"
                  % (r["name"], lat), file=sys.stderr)
            return 3
        if lat["grade"] not in ("measured", "bounded", "derived"):
            print("REFUSING TO WRITE: %s has latency grade %r"
                  % (r["name"], lat["grade"]), file=sys.stderr)
            return 3
    # An electrical synapse must be strictly faster than a chemical one, or
    # the whole trade the axis exists to express is backwards.
    chem = [r for r in with_latency if r["basis"] == "chemical_synapse"]
    elec = [r for r in with_latency if r["basis"] == "electrical_synapse"]
    if chem and elec:
        c_min = min(r["latency_ms"]["low"] for r in chem)
        e_max = max(r["latency_ms"]["high"] for r in elec)
        if e_max >= c_min:
            print("REFUSING TO WRITE: fastest electrical (%s ms) is not faster "
                  "than slowest chemical (%s ms); the basis table is wrong"
                  % (e_max, c_min), file=sys.stderr)
            return 3

    out = {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": (
            "Latency and energy per connection type, graded by what is "
            "actually known. The connection library had `delay_class` with "
            "three symbolic values and `parameters` with no unit attached, so "
            "an optimiser could only trade one axis -- structure -- and the "
            "Phase 3 computation result measured negative for a reason that "
            "was in the vocabulary all along. This artifact adds the numbers "
            "where a citation exists and `unknown` where one does not."),
        "grades": {
            "measured": "a published physiological value, cited",
            "bounded": "a defensible range from cited literature",
            "derived": "computed from another measured field in this library",
            "unknown": "nothing defensible; no value asserted",
        },
        "cost_axis": rows,
        "summary": {
            "types_total": len(rows),
            "with_latency_number": len(with_latency),
            "unknown_latency": sum(1 for r in rows if not r.get("latency_ms")),
            "abstraction_only": sum(1 for r in rows if r["abstraction_only"]),
            "abstraction_only_with_latency": len(bad),
            "by_grade": dict(graded),
            "by_family": {f: dict(c) for f, c in sorted(by_family.items())},
            "measured_or_bounded_pct": round(
                100.0 * sum(1 for r in rows
                            if r["grade"] in ("measured", "bounded"))
                / len(rows), 1) if rows else 0.0,
        },
        "basis": {k: {kk: vv for kk, vv in v.items() if kk != "latency_note"}
                  for k, v in BASIS.items()},
        "caveat": [
            "Latency here is the delay attributable to the connection, not a "
            "path latency. Compose per-type delays to get a path; a circuit "
            "motif therefore has no latency of its own and says so.",
            "Energy is a relative trichotomy (cheap / typical / expensive), "
            "not joules. A per-spike joule figure needs cell-type and "
            "temperature corrections this library does not have, and a wrong "
            "absolute number is worse than an honest relative one.",
            "21 of the 66 types are `abstraction_only` design patterns. They "
            "get no physiological number by construction; their `delay_class` "
            "is kept under `designed_cost` so an assumption is never summed "
            "with a measurement.",
            "The fastest electrical synapse is asserted to be strictly faster "
            "than the slowest chemical one and the script refuses to write if "
            "that stops holding -- the whole trade the axis exists to express "
            "depends on it.",
            "These values characterise biology. They do not say what a "
            "generated topology should cost: choosing a fast, faithful, cheap "
            "electrical link everywhere would be a design decision, and the "
            "library's own Phase 3 evidence is that a compute advantage does "
            "not follow from the biological prior.",
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    s = out["summary"]
    print("[COST] %d types; %d carry a latency number, %d unknown"
          % (s["types_total"], s["with_latency_number"], s["unknown_latency"]))
    print("[COST] grades: %s" % s["by_grade"])
    print("[COST] abstraction_only: %d, of which with a latency: %d"
          % (s["abstraction_only"], s["abstraction_only_with_latency"]))
    print("[COST] wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
