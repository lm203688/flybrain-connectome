#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v2.39.0 — does the cost axis actually give the optimiser a second axis?

The question
------------
v2.38.0 gave every connection type a graded latency and energy.  That is data
sitting in a file.  Phase 3 already measured the consequence of its absence:
with latency a three-valued category and energy missing, the optimiser could
only trade structure, so it won on wire cost (-84%) and measured **negative** on
computation (0/7 topologies beating random).

This script asks whether the axis is actually usable, which is a stronger claim
than "the numbers are cited".  An axis nobody optimises over is decoration.

The test
--------
Run a GA twice on the same search space with the same budget and the same seed,
changing one thing: the objective.

    struct_only    fitness = wire cost + capability coverage   (the Phase 3 shape)
    cost_aware     fitness = wire cost + capability coverage
                           + latency penalty + energy penalty

Then check the thing that would make the axis worth having:

    Does cost_aware produce a DIFFERENT optimum, and is the difference
    the one the axis predicts?

If GA is indifferent, the axis did nothing.  If GA trades wire cost for latency
(or the reverse) when told to, the axis is a real second dimension and the
trade-off is now measurable.  If the cost_aware run just collapses to "use
electrical synapses everywhere", that is also a finding -- it would say the axis
degrades to a one-switch choice, and the caveat must say so.

Honest boundaries
-----------------
* This measures whether the OPTIMISER RESPONDS, not whether the result is
  better than biology.  Phase 3's negative computation result is not revisited
  here and nothing in this script revises it.
* Latency is summed from the cited per-type ranges (low bound and high bound
  both, so a topology's latency is reported as a band, not a point).  A
  topology containing an `unknown`-latency type has no latency figure and is
  reported as such rather than assigned a default.
* The GA is the Phase 3 GA -- same operators, same evaluation seed.  The only
  change is the objective, so any difference is attributable to it.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent              # .../swarmlabs/diagnostics
ROOT = HERE.parent.parent.parent                     # flybrain-connectome/
MCP = ROOT / "flybrain-connectome-mcp"
COSTS = MCP / "functional_units" / "connection_costs.json"
OUT_DIR = HERE / "cost_aware"

EVAL_SEED = 7
N_PROFILES = 10


# --------------------------------------------------------------------------- #
# the cost axis, loaded and indexed by connection type
# --------------------------------------------------------------------------- #
def load_costs() -> dict:
    doc = json.loads(COSTS.read_text(encoding="utf-8"))
    by_name = {}
    for r in doc["cost_axis"]:
        by_name[r["name"]] = r
    return {"by_name": by_name, "doc": doc}


COST = load_costs()

# An unknown-latency type is charged the slowest latency the library asserts
# anywhere, so "unmeasured" is expensive rather than free.  See latency_band().
UNKNOWN_LATENCY_MS = 1000.0


ENERGY_RANK = {"cheap": 0.15, "cheap_per_target": 0.2, "typical": 0.5,
               "scales_with_span": 0.7, "expensive": 0.9, "emergent": 0.6,
               "unknown": 0.6}


def latency_band(names) -> tuple:
    """(low_ms, high_ms, unknown_count) for a set of connection type names.

    Sums the cited ranges.  An `unknown` type contributes NEITHER its latency
    NOR a synthetic penalty -- it contributes a count, and a topology with any
    unknown-latency type is reported as **not comparable on latency**.

    Two earlier versions got this wrong in opposite directions, and both were
    caught by the direction check rather than by reading the code:

    1. unknown -> 0 ms.  The cheapest way to lower a latency penalty became
       selecting types the axis cannot measure.  `cost_aware` returned 0.1-0.4
       ms topologies -- all gap junctions -- with 4-7 unknown types riding
       along free.  The reported -99.9% was the optimiser exploiting a hole in
       the measurement.
    2. unknown -> charged the slowest latency in the library (1000 ms).  Now
       GA learned the inverse: reduce the number of *known* synapses and
       increase the number of unmeasured ones.  Over 3 runs (8/16/24 seeds,
       80 generations) latency went UP 16-19% every time -- consistently, so
       it is a real effect of this policy, not noise.

    The honest resolution is that an unmeasured type is not cheap and not
    expensive, it is **incomparable**.  A topology carrying one has no latency
    figure, and the experiment counts it as unranked rather than pretending.
    """
    lo = hi = 0.0
    unk = 0
    for n in names:
        r = COST["by_name"].get(n)
        if not r or not r.get("latency_ms"):
            unk += 1
            continue
        lo += r["latency_ms"]["low"]
        hi += r["latency_ms"]["high"]
    return lo, hi, unk


def energy_mean(names) -> float:
    vals = []
    for n in names:
        r = COST["by_name"].get(n)
        if r and r.get("energy"):
            vals.append(ENERGY_RANK.get(r["energy"]["level"], 0.6))
    if not vals:
        return 1.0   # nothing measured: expensive, not free
    return statistics.fmean(vals)


# --------------------------------------------------------------------------- #
# the search space: which connection types a candidate organism uses
# --------------------------------------------------------------------------- #
# Mirrors ga_evolve_topology.py's phenotype: a candidate is a set of module
# blueprints, and each blueprint contributes connection types.  Reading the
# types from the unit library rather than inventing a parallel list is what
# keeps the two objectives comparable -- wire cost and latency are then
# computed over the same edge objects.
def load_space() -> dict:
    doc = json.loads((MCP / "functional_units" / "functional_units.json")
                     .read_text(encoding="utf-8"))
    units = doc["units"] if isinstance(doc, dict) else doc
    space = []
    for u in units:
        wiring = u.get("internal_wiring") or []
        types = []
        for w in wiring:
            t = w.get("type") if isinstance(w, dict) else w
            if t:
                types.append(t)
        if not types:
            for t in (u.get("motif_source") or []):
                if isinstance(t, str):
                    types.append(t)
        if types:
            space.append({
                "unit": u["name"],
                "types": sorted(set(types)),
                "edges": len(types),
                "profiles": len(u.get("members", [])),
                "dynamic": sum(1 for t in set(types)
                               if "recurrent" in t or "reservoir" in t),
            })
    return {"space": space, "n_units_total": len(units)}


SPACE = load_space()

# ------------------------------------------------------------------ #
# v2.39.0 -- the granularity matters, and the unit level does not work.
#
# Measured before writing any of the conclusions below: of 115 units, only 14
# have every connection type on the latency axis (almost all of them larv/cel,
# whose wiring is chemically simple).  The other 101 carry unknown-latency
# types, with a MEDIAN unknown share of 100%.  A 5-6 unit organism therefore
# contains an unknown type essentially always, which means its latency is not
# a quantity -- there is nothing to optimise and nothing to compare.
#
# That is the finding: **at unit granularity the cost axis is untestable**, so
# the experiment has to move to where the axis actually has authority, which
# is the connection type itself.  The two spaces are reported separately and
# never pooled.
# ------------------------------------------------------------------ #

RANKABLE_UNITS = []
for _s in SPACE["space"]:
    _t = set(_s["types"])
    if _t and _t <= set(r["name"] for r in COST["doc"]["cost_axis"]
                        if r.get("latency_ms")):
        RANKABLE_UNITS.append(_s["unit"])


def load_type_space() -> list:
    """The search space where the cost axis has authority: connection types.

    Each candidate is a set of connection types.  Wire cost is the number of
    types (one edge each), latency is summed from the cited ranges, energy is
    the mean of the relative levels.  Every quantity is measured, so the
    comparison between objectives is meaningful here and is not at unit level.
    """
    out = []
    for r in COST["doc"]["cost_axis"]:
        if not r.get("latency_ms"):
            continue
        out.append({
            "type": r["name"],
            "lat_lo": r["latency_ms"]["low"],
            "lat_hi": r["latency_ms"]["high"],
            "energy": ENERGY_RANK.get((r.get("energy") or {}).get("level"), 0.6),
        })
    return out


# Built here, after both the cost axis and the energy table exist.  At unit
# granularity the axis is untestable -- see RANKABLE_UNITS.
TYPE_SPACE = load_type_space()





def evaluate(cand: list, cost_aware: bool) -> dict:
    """Fitness over a candidate list of unit names.

    struct_only reproduces the Phase 3 shape: wire cost plus coverage.
    cost_aware adds the two penalties.  Both are normalised to 0-1 so the
    weights mean the same thing in both modes.
    """
    idx = {s["unit"]: s for s in SPACE["space"]}
    sel = [idx[n] for n in cand if n in idx]
    if not sel:
        return {"fitness": 0.0, "n_edges": 0, "lat_lo": 0.0, "lat_hi": 0.0,
                "unknown_types": 0, "energy": 0.0, "profiles": 0,
                "types": Counter()}
    n_edges = sum(s["edges"] for s in sel)
    profiles = sum(s["profiles"] for s in sel)
    types = Counter(t for s in sel for t in s["types"])

    cost = min(n_edges / 60.0, 1.0)
    cover = min(profiles / 40.0, 1.0)
    fitness = 1.0 - 0.5 * cost + 0.5 * cover

    lo, hi, unk = latency_band(list(types))
    # A topology carrying an unknown-latency type has NO latency figure.  It is
    # neither fast nor slow, so it is left out of the latency comparison
    # entirely rather than scored -- see latency_band() for the two wrong
    # policies this replaces and what the optimiser did with each.
    comparable = unk == 0
    lat = min((lo + hi) / 2.0 / 50.0, 1.0) if (lo or hi) else 0.0
    en = energy_mean(list(types))
    if cost_aware and comparable:
        fitness -= 0.30 * lat + 0.20 * en
    elif cost_aware:
        # unranked on latency: only the energy term, which every type has
        fitness -= 0.20 * en
    return {
        "fitness": fitness, "n_edges": n_edges, "profiles": profiles,
        "lat_lo": lo, "lat_hi": hi, "unknown_types": unk,
        "latency_comparable": comparable,
        "latency_norm": lat, "energy": en, "types": types,
    }


def ga_run(objective_cost_aware: bool, seed: int, gens: int, pop: int,
           rng: random.Random) -> dict:
    pool = [s["unit"] for s in SPACE["space"]]
    k = random.Random(EVAL_SEED)          # fixed topology: same search space
    population = [k.sample(pool, min(len(pool), 6)) for _ in range(pop)]
    best = None
    history = []
    for _g in range(gens):
        scored = [(evaluate(list(set(ind)), objective_cost_aware), list(set(ind)))
                  for ind in population]
        scored.sort(key=lambda x: -x[0]["fitness"])
        if best is None or scored[0][0]["fitness"] > best["fitness"]:
            best = scored[0][0] | {"chosen": scored[0][1]}
        history.append(scored[0][0]["fitness"])
        elite = [list(ind) for _s, ind in scored[:max(2, pop // 4)]]
        population = list(elite)
        while len(population) < pop:
            a = list(rng.choice(elite))
            b = list(rng.choice(elite))
            child = a[:]
            if b and rng.random() < 0.7:
                child[rng.randrange(len(child))] = rng.choice(b)
            if len(child) > 3 and rng.random() < 0.5:
                child.pop(rng.randrange(len(child)))
            else:
                cand = rng.choice(pool)
                if cand not in child:
                    child.append(cand)
            population.append(list(dict.fromkeys(child))[:10])
    return {"best": best, "history": history}


def fill_to_k(names, pool, k, rng) -> list:
    """Exactly k distinct types.  `dict.fromkeys(... )[:k]` can return fewer
    than k when a mutation re-picks a type already present, which let a
    candidate shrink from 6 edges to 5 and turned a latency comparison into a
    wire-cost comparison.  Restored here so the size is invariant."""
    out = list(dict.fromkeys(names))
    guard = 0
    while len(out) < k and guard < 200:
        out.append(rng.choice(pool))
        out = list(dict.fromkeys(out))
        guard += 1
    return out[:k]


def ga_type_run(cost_aware: bool, seed: int, gens: int, pop: int,
                k: int) -> dict:
    """GA over connection types -- the granularity where the axis has authority.

    A candidate is a set of k connection types.  Everything is measured:
    wire cost is the edge count, latency is summed from the cited bands, energy
    is the mean relative level.  There is no `unknown` here, so nothing has to
    be excluded from the comparison and the two objectives are directly
    comparable.
    """
    rng = random.Random(2000 + seed)
    pool = [t["type"] for t in TYPE_SPACE]
    meta = {t["type"]: t for t in TYPE_SPACE}
    population = []
    for _i in range(pop):
        r2 = random.Random(EVAL_SEED + seed + _i)
        population.append(fill_to_k(r2.sample(pool, min(k, len(pool))),
                                    pool, k, r2))
    best = None
    for _g in range(gens):
        scored = []
        for ind in population:
            s = fill_to_k(sorted(set(ind)), pool, k, rng)
            lo = sum(meta[t]["lat_lo"] for t in s)
            hi = sum(meta[t]["lat_hi"] for t in s)
            en = statistics.fmean([meta[t]["energy"] for t in s])
            # The candidate size is FIXED at k in both objectives.  A first
            # version let it float and scored wire as len(s)/k: GA then
            # shrank every candidate to a single type, because one edge is
            # cheaper than six and the latency term was too small to stop it.
            # It reported 384 ms -> 0.20 ms, a 99.9% "improvement" achieved by
            # removing the topology.  Wire cost is a property of a fixed
            # budget, so it is held constant and the latency term is what
            # actually moves -- which is the question being asked.
            wire = len(s) / k          # == 1.0 always, kept for the report
            lat = ((lo + hi) / 2.0) / 50.0
            fit = 1.0
            if cost_aware:
                fit -= 0.35 * min(lat, 1.0) + 0.15 * en
            scored.append(({"fitness": fit, "n_edges": len(s), "lat_lo": lo,
                            "lat_hi": hi, "energy": en, "types": s}, s))
        scored.sort(key=lambda x: -x[0]["fitness"])
        if best is None or scored[0][0]["fitness"] > best["fitness"]:
            best = scored[0][0]
        elite = [s for _f, s in scored[:max(2, pop // 4)]]
        population = list(elite)
        while len(population) < pop:
            child = list(rng.choice(elite))
            if rng.random() < 0.6 and child:
                child[rng.randrange(len(child))] = rng.choice(pool)
            population.append(fill_to_k(child, pool, k, rng))
    if best["n_edges"] != k:
        print("REFUSING TO REPORT: the type-level best has %d edges, not the "
              "fixed budget k=%d. The comparison would be a wire-cost "
              "comparison wearing a latency label."
              % (best["n_edges"], k), file=sys.stderr)
        return {"best": best, "size_violation": True}
    return {"best": best}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--gens", type=int, default=60)
    ap.add_argument("--pop", type=int, default=40)
    ap.add_argument("--k", type=int, default=6,
                    help="types per candidate in the type-level run")
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if len(COST["by_name"]) < 60:
        print("REFUSING TO RUN: cost axis has only %d types; run "
              "scripts/extract_connection_costs.py first" % len(COST["by_name"]),
              file=sys.stderr)
        return 2
    if not SPACE["space"]:
        print("REFUSING TO RUN: empty search space", file=sys.stderr)
        return 2

    print("cost-aware GA: %d units in the space, %d connection types on the axis"
          % (len(SPACE["space"]), len(COST["by_name"])))
    print("  objective A (struct_only): wire cost + capability coverage")
    print("  objective B (cost_aware) : + latency penalty + energy penalty")
    print("  %d seeds x %d gens x pop %d, evaluation seed fixed at %d"
          % (args.seeds, args.gens, args.pop, EVAL_SEED))

    rows = []
    for seed in range(args.seeds):
        rng = random.Random(1000 + seed)
        a = ga_run(False, seed, args.gens, args.pop, rng)
        b = ga_run(True, seed, args.gens, args.pop, random.Random(1000 + seed))
        for label, r in (("struct_only", a), ("cost_aware", b)):
            best = r["best"]
            rows.append({
                "seed": seed, "objective": label,
                "fitness": round(best["fitness"], 4),
                "n_edges": best["n_edges"],
                "latency_low_ms": round(best["lat_lo"], 2),
                "latency_high_ms": round(best["lat_hi"], 2),
                "unknown_latency_types": best["unknown_types"],
                "latency_ranked": "1" if best["latency_comparable"] else "0",
                "energy": round(best["energy"], 3),
                "units": ";".join(best["chosen"]),
            })
        print("  seed %d: struct_only edges=%-3d lat=%6.1fms | cost_aware "
              "edges=%-3d lat=%6.1fms"
              % (seed, a["best"]["n_edges"], a["best"]["lat_lo"] + a["best"]["lat_hi"],
                 b["best"]["n_edges"], b["best"]["lat_lo"] + b["best"]["lat_hi"]))

    with (out / "cost_aware_runs.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---------------- does the axis actually move the optimum? ------------ #
    def agg(label, key):
        vals = [r[key] for r in rows if r["objective"] == label]
        return (statistics.fmean(vals), statistics.pstdev(vals) if len(vals) > 1 else 0.0)

    a_edges, a_edges_sd = agg("struct_only", "n_edges")
    b_edges, b_edges_sd = agg("cost_aware", "n_edges")
    # Latency is compared only over topologies whose every type is measured.
    # Comparing across unranked ones would compare a number against nothing.
    a_lat = [r["latency_low_ms"] + r["latency_high_ms"] for r in rows
             if r["objective"] == "struct_only" and r["latency_ranked"] == "1"]
    b_lat = [r["latency_low_ms"] + r["latency_high_ms"] for r in rows
             if r["objective"] == "cost_aware" and r["latency_ranked"] == "1"]
    a_unranked = sum(1 for r in rows
                     if r["objective"] == "struct_only" and r["latency_ranked"] != "1")
    b_unranked = sum(1 for r in rows
                     if r["objective"] == "cost_aware" and r["latency_ranked"] != "1")
    if not a_lat or not b_lat:
        print()
        print("  no latency-ranked topologies on one side "
              "(struct_only=%d, cost_aware=%d); the axis cannot be compared."
              % (len(a_lat), len(b_lat)))
        a_lat_m = b_lat_m = 0.0
    else:
        a_lat_m, b_lat_m = statistics.fmean(a_lat), statistics.fmean(b_lat)
    a_fit, b_fit = agg("struct_only", "fitness")[0], agg("cost_aware", "fitness")[0]

    # Do the two objectives pick the same organism?
    same_topology = sum(1 for r in rows
                        if r["objective"] == "struct_only"
                        and any(x["seed"] == r["seed"] and x["objective"] == "cost_aware"
                                and x["units"] == r["units"] for x in rows))
    identical = same_topology / max(1, args.seeds)

    lat_cut = (a_lat_m - b_lat_m) / a_lat_m * 100 if a_lat_m else 0.0
    edge_cut = (a_edges - b_edges) / a_edges * 100 if a_edges else 0.0

    if identical == 1.0:
        verdict = ("the cost axis had NO effect: both objectives converged on the "
                   "same organism in every seed. The axis is data, not a "
                   "dimension -- an optimiser given it does not use it.")
    elif b_lat_m < a_lat_m * 0.95:
        verdict = ("the cost axis works as an axis: told to penalise latency, "
                   "the optimiser moved to topologies %.1f%% lower in latency, "
                   "and it did not buy that with more wire. The axis is a real "
                   "second dimension and the trade is measurable."
                   % (100 * (1 - b_lat_m / a_lat_m)))
    elif a_lat_m < b_lat_m * 0.95:
        verdict = ("SUSPECT: told to penalise latency, the optimiser ended up "
                   "%.1f%% HIGHER in latency. The objectives differ but the "
                   "penalty is not doing what it claims, so \"different "
                   "topology\" is not evidence of a working axis."
                   % (100 * (b_lat_m / a_lat_m - 1)))
    elif identical == 0.0:
        verdict = ("WEAK: the two objectives never picked the same organism, but "
                   "neither is better on latency. The axis reshuffles the "
                   "search without steering it, which is noise dressed as a "
                   "result.")
    else:
        verdict = ("the cost axis changed the optimum in %d of %d seeds at "
                   "essentially unchanged latency. Not evidence of a working "
                   "dimension." % (args.seeds - same_topology, args.seeds))

    # The headline number a reader takes away has to be the direction check, not
    # the difference rate.  The first version of this script reported only
    # "0% identical -> real dimension", which a run where the latency penalty
    # made things WORSE would also have satisfied.
    axis_works = b_lat_m < a_lat_m * 0.95

    # ---------------- type granularity, where the axis has authority ------- #
    trows = []
    for seed in range(args.seeds):
        for label, aware in (("struct_only", False), ("cost_aware", True)):
            r = ga_type_run(aware, seed, args.gens, args.pop, args.k)
            b = r["best"]
            trows.append({
                "seed": seed, "objective": label,
                "fitness": round(b["fitness"], 4), "n_edges": b["n_edges"],
                "latency_low_ms": round(b["lat_lo"], 2),
                "latency_high_ms": round(b["lat_hi"], 2),
                "energy": round(b["energy"], 3),
                "types": ";".join(b["types"]),
            })
    with (out / "cost_aware_type_runs.csv").open("w", encoding="utf-8",
                                                 newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trows[0]))
        w.writeheader()
        w.writerows(trows)

    def tagg(label, key):
        return statistics.fmean([r[key] for r in trows
                                 if r["objective"] == label])
    ta_lat = tagg("struct_only", "latency_high_ms")
    tb_lat = tagg("cost_aware", "latency_high_ms")
    ta_ed = tagg("struct_only", "n_edges")
    tb_ed = tagg("cost_aware", "n_edges")
    ta_en = tagg("struct_only", "energy")
    tb_en = tagg("cost_aware", "energy")
    t_cut = (ta_lat - tb_lat) / ta_lat * 100 if ta_lat else 0.0
    t_same = sum(1 for r in trows if r["objective"] == "struct_only"
                 and any(x["seed"] == r["seed"] and x["objective"] == "cost_aware"
                         and x["types"] == r["types"] for x in trows)) / max(1, args.seeds)
    t_axis_works = tb_lat < ta_lat * 0.95

    print()
    print("type granularity (%d latency-bearing types, k=%d):" % (len(TYPE_SPACE), args.k))
    print("  struct_only : edges %5.2f  latency %7.2f ms  energy %.3f"
          % (ta_ed, ta_lat, ta_en))
    print("  cost_aware  : edges %5.2f  latency %7.2f ms  energy %.3f"
          % (tb_ed, tb_lat, tb_en))
    print("  latency %+.1f%%   energy %+.1f%%   wire %+.1f%%   identical %.0f%%"
          % (-t_cut, (ta_en - tb_en) / ta_en * 100 if ta_en else 0.0,
             (ta_ed - tb_ed) / ta_ed * 100 if ta_ed else 0.0, 100 * t_same))
    print("  VERDICT: %s" % (
        "the cost axis steers the optimiser at type level: %.1f%% lower latency, "
        "bought with %s" % (-t_cut,
                           "more wire" if tb_ed > ta_ed * 1.05 else "less wire")
        if t_axis_works else
        "the axis does NOT steer at type level (%.1f%%)" % (-t_cut)))

    doc = {
        "schema_version": "1.0",
        "purpose": (
            "Test whether the connection cost axis gives the optimiser something "
            "to trade. v2.38.0 added cited latency and energy per connection "
            "type; an axis nobody optimises over is decoration. Two runs, same "
            "space, same budget, same evaluation seed, one objective changed."),
        "method": {
            "objective_a": "wire cost + capability coverage (the Phase 3 shape)",
            "objective_b": "objective A + latency penalty + energy penalty",
            "seeds": args.seeds, "generations": args.gens, "population": args.pop,
            "evaluation_seed": EVAL_SEED,
            "search_space": "unit names whose internal wiring names connection types",
        },
        "results": {
            "identical_topology_rate": round(identical, 4),
            "struct_only": {"edges_mean": round(a_edges, 2),
                            "edges_sd": round(a_edges_sd, 2),
                            "latency_ms_mean": round(a_lat_m, 2),
                            "energy_mean": round(agg("struct_only", "energy")[0], 3),
                            "fitness_mean": round(a_fit, 4)},
            "cost_aware": {"edges_mean": round(b_edges, 2),
                           "edges_sd": round(b_edges_sd, 2),
                           "latency_ms_mean": round(b_lat_m, 2),
                           "energy_mean": round(agg("cost_aware", "energy")[0], 3),
                           "fitness_mean": round(b_fit, 4)},
            "latency_change_pct": round(lat_cut, 2),
            "edge_change_pct": round(edge_cut, 2),
        },
        "type_granularity": {
            "note": ("Unit granularity is where the library's own units live and "
                     "it is NOT testable: only 14 of 115 units have every "
                     "connection type on the latency axis. The type-level run "
                     "is the one with authority, and the two are never pooled."),
            "latency_bearing_types": len(TYPE_SPACE),
            "k": args.k,
            "struct_only": {"edges": round(ta_ed, 2), "latency_ms": round(ta_lat, 2),
                            "energy": round(ta_en, 3)},
            "cost_aware": {"edges": round(tb_ed, 2), "latency_ms": round(tb_lat, 2),
                           "energy": round(tb_en, 3)},
            "latency_change_pct": round(t_cut, 2),
            "identical_topology_rate": round(t_same, 4),
            "axis_works": bool(t_axis_works),
        },
        "verdict": verdict,
        "axis_works": axis_works,
        "direction_check": {
            "note": ("The claim under test is 'the axis steers the optimiser'. "
                     "A run where the latency penalty ends up with HIGHER "
                     "latency has failed regardless of how many seeds picked a "
                     "different topology."),
            "latency_improved": bool(b_lat_m < a_lat_m),
            "latency_change_pct": round(lat_cut, 2),
            "wire_cost_change_pct": round(edge_cut, 2),
            "bought_latency_with_wire": bool(b_edges > a_edges * 1.05),
            "struct_only_unranked": a_unranked,
            "cost_aware_unranked": b_unranked,
            "ranked_struct_only": len(a_lat),
            "ranked_cost_aware": len(b_lat),
        },
        "caveat": [
            "This measures whether the OPTIMISER RESPONDS to the axis, not "
            "whether the outcome beats biology. Phase 3's negative computation "
            "result is untouched by this script and nothing here revises it.",
            "Latency is summed from cited ranges, so every figure is a band. A "
            "topology containing an `unknown`-latency type has no latency "
            "figure and is reported as such, never assigned a default.",
            "The two fitness values are NOT comparable across objectives: each "
            "is normalised inside its own objective, so `cost_aware` scores "
            "lower by construction (it carries two extra penalty terms). Only "
            "the topologies and the axis values are compared.",
            "The search space is unit names, not connection types. A future "
            "version should let the GA pick connection types directly; this "
            "one can only trade at the granularity the unit library offers.",
        ],
    }
    (out / "cost_aware_result.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("  struct_only : edges %6.2f +- %.2f   latency %7.2f ms   fitness %.4f"
          % (a_edges, a_edges_sd, a_lat_m, a_fit))
    print("  cost_aware  : edges %6.2f +- %.2f   latency %7.2f ms   fitness %.4f"
          % (b_edges, b_edges_sd, b_lat_m, b_fit))
    print("  latency %+.1f%%   edges %+.1f%%   identical topology in %.0f%% of seeds"
          % (-lat_cut, edge_cut, 100 * identical))
    print()
    print("VERDICT: %s" % verdict)
    print("wrote %s" % (out / "cost_aware_result.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
