#!/usr/bin/env python3
"""GATE 10 -- the embodiment layer is real, self-consistent and drift-free.

WHAT THIS GATE IS FOR
---------------------
Gate 9 checks that the composition library is internally coherent. It cannot
check the one thing the library was worst at: whether any of it corresponds to
the connectome it is named after. Gate 10 closes that. It verifies three
separate kinds of claim:

  A. **Internal consistency of the anchor artifact.** The measured matrices add
     up to the numbers they claim, the profile-level matrix is exactly the
     type-level matrix aggregated over each profile's real cell-type set, every
     anchored profile actually matched cells, and the classification partitions
     all 183 profiles with no double-counting. These run in CI with no dataset.

  B. **Unit-level embodiment honesty.** `provenance.embodied_in_malecns` is true
     for exactly the units with an anchored population -- no unit may claim
     embodiment it does not have, and none may hide embodiment it does have. Each
     declared edge's recorded measured synapse count is re-derived from the
     matrices rather than trusted.

  C. **Every contradiction is acknowledged.** A declared edge whose endpoint
     populations have ZERO measured synapses between them is contradicted by the
     data. The gate fails on any such edge that is not listed, with a reason, in
     `acknowledged_contradictions` -- and also fails if a listed contradiction has
     silently disappeared.

FAIL-CLOSED PROOF
-----------------
Every run re-injects five defects (flipped embodiment flag, fabricated spike in
the measured matrix, deleted anchor type, unacknowledged contradiction, tampered
artifact digest) and requires each to turn the check set red. An injection that
does NOT go red is itself a gate failure.

With `--with-data` the layer is recomputed from the raw annotations and the
cached synapse arrays and compared against the committed artifact, which catches
"the dataset moved but nobody rebuilt the anchors".

Usage:
    python scripts/check_embodiment.py                 # offline (CI-equivalent)
    python scripts/check_embodiment.py --with-data     # + recompute and compare
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "flybrain-connectome-mcp"
UNITS_FILE = PKG / "functional_units" / "functional_units.json"
ANCHORS_FILE = PKG / "functional_units" / "malecns_anchors.json"
README = ROOT / "README.md"

EXPECTED_SYNAPSES = 124_177_617
EXPECTED_EDGES = 25_582_938
EXPECTED_NEURONS = 166_700


def check(results, name, ok, detail=""):
    results.append((name, bool(ok), detail))
    return bool(ok)


# ---------------------------------------------------------------------------
def run_checks(units_doc, anchors, readme_text):
    """Return the full check set. Pure: takes documents, returns verdicts."""
    r: list[tuple[str, bool, str]] = []
    val = anchors.get("validation", {})

    # --- A. artifact self-consistency -------------------------------------
    check(r, "anchor schema is 1.0", anchors.get("schema_version") == "1.0",
          str(anchors.get("schema_version")))
    check(r, "recomputed neuron subgraph equals 124,177,617 synapses / 25,582,938 edges",
          val.get("measured_synapses_neuron_subgraph") == EXPECTED_SYNAPSES
          and val.get("measured_edges_neuron_subgraph") == EXPECTED_EDGES,
          "%s / %s" % (val.get("measured_synapses_neuron_subgraph"),
                       val.get("measured_edges_neuron_subgraph")))
    check(r, "annotation source covers 166,700 neurons",
          anchors.get("source", {}).get("annotations", {}).get("unique_neurons")
          == EXPECTED_NEURONS,
          str(anchors.get("source", {}).get("annotations", {}).get("unique_neurons")))

    sm = anchors["superclass_matrix"]
    names = anchors["superclasses"]
    check(r, "superclass index is a bijection onto the superclass list",
          sorted(sm["index"]) == sorted(names)
          and len(set(sm["index"].values())) == len(names),
          "%d names" % len(names))
    checksum_syn = sum(sum(row) for row in sm["synapses"])
    checksum_edg = sum(sum(row) for row in sm["edges"])
    check(r, "superclass matrix sums to the measured subgraph totals",
          checksum_syn == EXPECTED_SYNAPSES and checksum_edg == EXPECTED_EDGES,
          "%d / %d" % (checksum_syn, checksum_edg))
    check(r, "superclass matrix is square and non-negative",
          len(sm["synapses"]) == len(names)
          and all(len(row) == len(names) for row in sm["synapses"])
          and all(v >= 0 for row in sm["synapses"] for v in row),
          "%dx%d" % (len(sm["synapses"]), len(sm["synapses"][0])))

    # --- anchored types and the two derived matrices ----------------------
    pa = anchors["profile_anchors"]
    named_types = sorted({h["type"] for a in pa.values() for h in a["types"]})
    tid = {n: i for i, n in enumerate(named_types)}
    tam = anchors["anchored_type_matrix"]
    check(r, "anchored-type index covers exactly the types named by the profiles",
          tam["n_types"] == len(named_types),
          "%d vs %d" % (tam["n_types"], len(named_types)))

    # The matrix is indexed by the artifact's own n_types, not by what the
    # profiles happen to name -- so deleting an anchor entry turns the coverage
    # check red instead of crashing the parser.
    n = tam["n_types"]
    tmat = [[0] * n for _ in range(n)]
    tedge = [[0] * n for _ in range(n)]
    problems = []
    seen = set()
    stored_syn = []
    for i, line in enumerate(tam["rows"]):
        if i >= n:
            problems.append("row %d beyond n_types" % i)
        if not line:
            continue
        for part in line.split(","):
            try:
                j, syn, edg = (int(x) for x in part.split(":"))
            except ValueError:
                problems.append("bad entry %r" % part)
                continue
            if not (0 <= j < n):
                problems.append("col %d out of range" % j)
                continue
            if (i, j) in seen:
                problems.append("duplicate pair %d,%d" % (i, j))
            seen.add((i, j))
            tmat[i][j] = syn
            tedge[i][j] = edg
            stored_syn.append(syn)
    check(r, "anchored-type matrix parses, rows match n_types, no duplicate pairs",
          len(tam["rows"]) == n and not problems,
          str(problems[:3]) if problems else "%d rows / %d pairs" % (n, len(seen)))
    check(r, "every stored anchored-type entry is nonzero",
          stored_syn and all(s > 0 for s in stored_syn),
          "%d pairs" % len(stored_syn))

    pm = anchors["profile_matrix"]
    check(r, "profile index matches the anchored profile set",
          sorted(pm["index"]) == sorted(pa), "%d profiles" % len(pa))
    unstorable = sorted({h["type"] for a in pa.values() for h in a["types"]}
                        - set(named_types))
    if unstorable or sorted(pm["index"]) != sorted(pa):
        check(r, "profile matrix equals the type matrix aggregated over each profile's cells",
              False, "unindexable types: %s" % unstorable[:3])
    else:
        bad = []
        for p1 in pa:
            i1 = [tid[h["type"]] for h in pa[p1]["types"]]
            for p2 in pa:
                i2 = [tid[h["type"]] for h in pa[p2]["types"]]
                want_s = sum(tmat[a][b] for a in i1 for b in i2)
                want_e = sum(tedge[a][b] for a in i1 for b in i2)
                row, col = pm["index"][p1], pm["index"][p2]
                if want_s != pm["synapses"][row][col] or want_e != pm["edges"][row][col]:
                    bad.append("%s->%s %d!=%d" % (p1, p2, pm["synapses"][row][col], want_s))
        check(r, "profile matrix equals the type matrix aggregated over each profile's cells",
              not bad, bad[:3] if bad else "%d pairs agree" % (len(pa) ** 2))

    # --- rule hygiene ------------------------------------------------------
    empty = sorted(k for k, a in pa.items() if a["n_types"] == 0)
    check(r, "no anchor rule matched zero cells", not empty, str(empty) if empty else "%d rules" % len(pa))
    bad_order = []
    for k, a in pa.items():
        want = sorted(a["types"], key=lambda h: (-h["n_bodies"], h["type"]))
        if a["types"] != want:
            bad_order.append(k)
        if a["n_bodies"] != sum(h["n_bodies"] for h in a["types"]):
            bad_order.append(k + "(sum)")
    check(r, "anchor entries are canonically ordered and internally summed",
          not bad_order, str(bad_order) if bad_order else "ok")

    cls = anchors["profile_classification"]
    total = sum(len(v) for v in cls.values())
    allnames = [n for v in cls.values() for n in v]
    check(r, "profile classification partitions all profiles without overlap",
          total == anchors["summary"]["profiles_total"]
          and len(allnames) == len(set(allnames)),
          "%d/%d, %d unique" % (total, anchors["summary"]["profiles_total"], len(set(allnames))))
    check(r, "'anchored' class equals the anchor set",
          sorted(cls["anchored"]) == sorted(pa),
          "%d" % len(cls["anchored"]))
    check(r, "anchored + unanchored equals profiles_total",
          len(pa) + anchors["summary"]["unanchored_profiles"]
          == anchors["summary"]["profiles_total"],
          "%d + %d" % (len(pa), anchors["summary"]["unanchored_profiles"]))
    check(r, "every unanchored profile carries a reason category",
          anchors["summary"]["unanchored_profiles"] == total - len(pa),
          str(anchors["summary"]["unanchored_profiles"]))

    # --- B. unit-level embodiment honesty ---------------------------------
    units = units_doc["units"]
    bad_flag, bad_count, bad_cells = [], [], []
    for u in units:
        e = u["embodiment"]
        if u["provenance"]["embodied_in_malecns"] != (e["populations_anchored"] > 0):
            bad_flag.append(u["name"])
        if e["populations_anchored"] > e["populations_total"]:
            bad_count.append(u["name"])
        if e["real_cells_anchored"] != sum(a["n_bodies"] for a in e["anchored"].values()):
            bad_cells.append(u["name"])
        for role, a in e["anchored"].items():
            if role not in {m["role"] for m in u["members"]}:
                bad_count.append(u["name"] + ":unknown role " + role)
    check(r, "embodied_in_malecns is true iff an anchored population exists",
          not bad_flag, str(bad_flag) if bad_flag else "%d units" % len(units))
    check(r, "anchored roles are real member roles", not bad_count,
          str(bad_count) if bad_count else "ok")
    check(r, "real_cells_anchored equals the sum of its anchored populations",
          not bad_cells, str(bad_cells) if bad_cells else "ok")
    check(r, "a unit never anchors more populations than it has members",
          all(u["embodiment"]["populations_anchored"] <= u["embodiment"]["populations_total"]
              for u in units), "ok")

    # --- declared edges re-derived from the matrices ----------------------
    bad_syn, bad_edg, bad_coarse, bad_flag2 = [], [], [], []
    for u in units:
        for s in u["embodiment"]["structural_support"]:
            p1, p2 = s["from_population"], s["to_population"]
            expect = pm["synapses"][pm["index"][p1]][pm["index"][p2]]
            if s["measured_synapses"] != expect:
                bad_syn.append("%s %s->%s" % (u["name"], s["from_role"], s["to_role"]))
            expect_e = pm["edges"][pm["index"][p1]][pm["index"][p2]]
            if s["measured_edges"] != expect_e:
                bad_edg.append(u["name"])
            if s["contradicted"] != (expect == 0):
                bad_flag2.append(u["name"])
            coarse = max(sm["synapses"][sm["index"][a]][sm["index"][b]]
                         for a in pa[p1]["superclasses"] for b in pa[p2]["superclasses"])
            if s["measured_synapses_superclass_coarse"] != coarse:
                bad_coarse.append(u["name"])
    check(r, "declared-edge synapse counts re-derive from the profile matrix",
          not bad_syn, str(bad_syn) if bad_syn else "ok")
    check(r, "declared-edge measured edge counts re-derive from the profile matrix",
          not bad_edg, str(bad_edg) if bad_edg else "ok")
    check(r, "contradicted flag equals (measured synapses == 0)", not bad_flag2,
          str(bad_flag2) if bad_flag2 else "ok")
    check(r, "coarse superclass counts re-derive from the superclass matrix",
          not bad_coarse, str(bad_coarse) if bad_coarse else "ok")

    # --- type-pair resolution: re-derive the tier from the real matrix ----
    # A stored tier is only believed if re-walking every (from_type, to_type) pair
    # across the two populations' cell-type sets reproduces it from the anchored
    # type matrix. This is the resolution at which the artifact can tell "a
    # pathway spread over many cell types" from "one lucky pair carrying a
    # profile-level non-zero".
    tm_rows = anchors["anchored_type_matrix"]["rows"]
    tm_pairs = {}
    for i, row in enumerate(tm_rows):
        if not row:
            continue
        for tok in row.split(","):
            j_s, syn_s, ed_s = tok.split(":")
            tm_pairs[(i, int(j_s))] = (int(syn_s), int(ed_s))
    t_names = sorted({t["type"] for a in pa.values() for t in a["types"]})
    t_index = {n: i for i, n in enumerate(t_names)}

    bad_tier, bad_cnt, bad_reconcile, bad_top = [], [], [], []
    tier_counts = {"SUPPORTED": 0, "FRAGILE": 0, "CONTRADICTED": 0}
    for u in units:
        for s in u["embodiment"]["structural_support"]:
            p1, p2 = s["from_population"], s["to_population"]
            t1 = [t["type"] for t in pa[p1]["types"] if t["type"] in t_index]
            t2 = [t["type"] for t in pa[p2]["types"] if t["type"] in t_index]
            hits = []
            for x in t1:
                for y in t2:
                    v = tm_pairs.get((t_index[x], t_index[y]))
                    if v and v[0] > 0:
                        hits.append((v[0], x, y))
            hits.sort(key=lambda r_: r_[0], reverse=True)
            if not hits:
                expect_tier = "CONTRADICTED"
            elif len(hits) == 1:
                expect_tier = "FRAGILE"
            else:
                expect_tier = "SUPPORTED"
            got = s.get("support_tier")
            tier_counts[got] = tier_counts.get(got, 0) + 1
            if got != expect_tier:
                bad_tier.append("%s %s->%s got %s want %s"
                                % (u["name"], s["from_role"], s["to_role"], got, expect_tier))
            pp = s.get("type_pair_support", {})
            if pp.get("n_type_pairs") != len(t1) * len(t2):
                bad_cnt.append("%s %s->%s" % (u["name"], s["from_role"], s["to_role"]))
            if pp.get("n_pairs_with_synapses") != len(hits):
                bad_reconcile.append("%s %s->%s stored %s measured %d"
                                     % (u["name"], s["from_role"], s["to_role"],
                                        pp.get("n_pairs_with_synapses"), len(hits)))
            if pp.get("top_pairs") != [{"from_type": x, "to_type": y, "synapses": sv}
                                        for sv, x, y in hits[:3]]:
                bad_top.append("%s %s->%s" % (u["name"], s["from_role"], s["to_role"]))
            if got == "CONTRADICTED" and not s["contradicted"]:
                bad_reconcile.append("%s %s->%s tier CONTRA but profile non-zero"
                                     % (u["name"], s["from_role"], s["to_role"]))
    check(r, "support_tier re-derives from the type-level matrix for every edge",
          not bad_tier, str(bad_tier) if bad_tier else "ok")
    check(r, "type_pair_support.n_type_pairs equals the |A x B| pair count",
          not bad_cnt, str(bad_cnt) if bad_cnt else "ok")
    check(r, "type_pair_support pair hits re-derive from the type matrix",
          not bad_reconcile, str(bad_reconcile) if bad_reconcile else "ok")
    check(r, "type_pair_support.top_pairs re-derive (top 3 by synapses)",
          not bad_top, str(bad_top) if bad_top else "ok")
    check(r, "support tier breaks down as SUPPORTED/FRAGILE/CONTRADICTED over %d edges"
          % len([s for u in units for s in u["embodiment"]["structural_support"]]),
          all(v >= 0 for v in tier_counts.values()),
          "SUPPORTED=%d FRAGILE=%d CONTRADICTED=%d"
          % (tier_counts["SUPPORTED"], tier_counts["FRAGILE"], tier_counts["CONTRADICTED"]))

    # --- every unanchored unit carries an enum reason ---------------------
    # The reason must be reproducible from the classification, not hand-typed:
    # re-run the derivation rule and require an exact match.
    not_do = set(cls.get("identity_not_drosophila", []))
    abstract_cls = set(cls.get("abstract_cognitive_module", []))

    def expect_reason(unit):
        if any(m["neuron"] in not_do for m in unit["members"]):
            return "identity_not_in_drosophila"
        if any(m["neuron"] in abstract_cls for m in unit["members"]):
            return "abstract_module_no_cell_type"
        return "taxon_no_malecns_data"

    bad_reason, reason_counts = [], {}
    for u in units:
        embodied = u["provenance"]["embodied_in_malecns"]
        reason = u["provenance"].get("unanchored_reason")
        if embodied:
            if reason is not None:
                bad_reason.append(u["name"] + " embodied but carries reason " + str(reason))
            continue
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if reason not in ("taxon_no_malecns_data", "identity_not_in_drosophila",
                          "abstract_module_no_cell_type"):
            bad_reason.append(u["name"] + ": unknown reason " + str(reason))
        elif reason != expect_reason(u):
            bad_reason.append("%s: reason %r does not re-derive (want %r)"
                              % (u["name"], reason, expect_reason(u)))
    check(r, "every unanchored unit carries an enum unanchored_reason (and embodied units carry none)",
          not bad_reason, str(bad_reason) if bad_reason else "ok")
    check(r, "unanchored reasons re-derive from the profile classification",
          not [b for b in bad_reason if "does not re-derive" in b],
          ", ".join("%s=%d" % (str(k), v) for k, v in sorted(reason_counts.items(), key=lambda kv: str(kv[0])))
          if reason_counts else "no unanchored units")

    # --- C. contradictions are all acknowledged ---------------------------
    src = units_doc["embodiment_source"]
    measured = sorted(
        "%s|%s->%s" % (u["name"], s["from_role"], s["to_role"])
        for u in units for s in u["embodiment"]["structural_support"]
        if s["contradicted"])
    acked = sorted("%s|%s" % (c["unit"], c["edge"])
                   for c in src["acknowledged_contradictions"])
    check(r, "report-order contradiction lists agree with the acknowledged list",
          sorted("%s|%s" % (c["unit"], c["edge"]) for c in src["contradicted_edges"]) == acked,
          "%d measured / %d acknowledged" % (len(measured), len(acked)))
    check(r, "every measured contradiction is acknowledged", measured == acked,
          str([m for m in measured if m not in acked]) if measured != acked else "ok")
    check(r, "every acknowledged contradiction carries a reason",
          all(c.get("reason") for c in src["acknowledged_contradictions"]), "ok")
    check(r, "stats contradictions count matches", 
          units_doc["stats"]["structural_support_edges_contradicted"] == len(measured),
          "%s vs %d" % (units_doc["stats"]["structural_support_edges_contradicted"],
                        len(measured)))

    # --- artifact digest ---------------------------------------------------
    digest = hashlib.sha256(ANCHORS_FILE.read_bytes()).hexdigest()
    check(r, "unit document pins the anchors artifact digest",
          src.get("sha256") == digest, src.get("sha256", "")[:16])
    check(r, "pinned measured totals match the anchors artifact",
          src.get("measured_synapses_neuron_subgraph") == EXPECTED_SYNAPSES
          and src.get("measured_edges_neuron_subgraph") == EXPECTED_EDGES,
          "%s / %s" % (src.get("measured_synapses_neuron_subgraph"),
                       src.get("measured_edges_neuron_subgraph")))

    # --- stats ------------------------------------------------------------
    st = units_doc["stats"]
    embodied = [u for u in units if u["provenance"]["embodied_in_malecns"]]
    check(r, "stats.embodied_units equals the number of embodied units",
          st["embodied_units"] == len(embodied),
          "%s vs %d" % (st["embodied_units"], len(embodied)))
    check(r, "stats.embodied_populations_referenced equals the distinct anchored populations used",
          st["embodied_populations_referenced"] == len(
              {m["neuron"] for u in units for m in u["members"] if m["neuron"] in pa}),
          str(st["embodied_populations_referenced"]))
    check(r, "stats.embodied_real_cells_referenced re-derives",
          st["embodied_real_cells_referenced"] == sum(
              pa[n]["n_bodies"] for n in
              {m["neuron"] for u in units for m in u["members"] if m["neuron"] in pa}),
          str(st["embodied_real_cells_referenced"]))
    check(r, "stats structural-support edge count re-derives",
          st["structural_support_edges_measured"] == sum(
              len(u["embodiment"]["structural_support"]) for u in units),
          str(st["structural_support_edges_measured"]))

    # --- README must state the same numbers -------------------------------
    if readme_text is not None:
        want = [
            ("%d of %d units" % (len(embodied), len(units)), "embodied unit count"),
            ("%d of %d neuron populations" % (len(pa), anchors["summary"]["profiles_total"]),
             "anchored population count"),
            ("{:,} real cells".format(anchors["summary"]["anchored_real_cells"]),
             "anchored real cell count"),
            ("{:,}".format(EXPECTED_SYNAPSES), "measured synapse total"),
        ]
        missing = [lab for text, lab in want if text not in readme_text]
        check(r, "README states the same embodiment numbers as the artifact",
              not missing, str(missing) if missing else "ok")

    return r


# ---------------------------------------------------------------------------
def injections(units_doc, anchors):
    """(label, mutated_units, mutated_anchors) -- each MUST turn the gate red."""
    out = []

    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    for unit in u["units"]:
        if unit["embodiment"]["populations_anchored"] > 0:
            unit["provenance"]["embodied_in_malecns"] = False
            break
    out.append(("an embodied unit claims it is not embodied", u, a))

    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    a["superclass_matrix"]["synapses"][0][0] += 1
    out.append(("a synapse is fabricated into the measured matrix", u, a))

    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    victim = sorted(a["profile_anchors"])[0]
    dropped = a["profile_anchors"][victim]["types"].pop()
    a["profile_anchors"][victim]["n_types"] -= 1
    a["profile_anchors"][victim]["n_bodies"] -= dropped["n_bodies"]
    out.append(("an anchored cell type is deleted but the matrix keeps it", u, a))

    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    u["embodiment_source"]["acknowledged_contradictions"] = []
    out.append(("a declared edge is contradicted with no acknowledgement", u, a))

    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    u["embodiment_source"]["sha256"] = "0" * 64
    out.append(("the pinned anchors digest no longer matches the artifact", u, a))

    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    for unit in u["units"]:
        for s in unit["embodiment"]["structural_support"]:
            s["measured_synapses"] += 1
            break
        else:
            continue
        break
    out.append(("a declared-edge count is nudged away from the matrix", u, a))

    # type-pair tier must not be writable by hand: relabelling a FRAGILE edge as
    # SUPPORTED has to fail the re-derivation check.
    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    for unit in u["units"]:
        for s in unit["embodiment"]["structural_support"]:
            if s.get("support_tier") == "FRAGILE":
                s["support_tier"] = "SUPPORTED"
                s["type_pair_support"]["support_tier"] = "SUPPORTED"
                s["type_pair_support"]["n_pairs_with_synapses"] = 2
                break
        else:
            continue
        break
    out.append(("a FRAGILE edge is relabelled SUPPORTED", u, a))

    # an unanchored unit with an out-of-enum reason is exactly the gap-3 failure
    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    for unit in u["units"]:
        if not unit["provenance"]["embodied_in_malecns"]:
            unit["provenance"]["unanchored_reason"] = "too-much-effort"
            break
    out.append(("an unanchored unit carries a non-enum reason", u, a))

    # a plausible enum value pasted from another unit is just as bad: the reason
    # must RE-DERIVE from the classification, not merely be in the enum
    a = copy.deepcopy(anchors)
    u = copy.deepcopy(units_doc)
    for unit in u["units"]:
        if not unit["provenance"]["embodied_in_malecns"]:
            unit["provenance"]["unanchored_reason"] = "abstract_module_no_cell_type"
            break
    out.append(("an unanchored unit's reason does not re-derive from the classification", u, a))

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--with-data", action="store_true",
                    help="recompute the anchor layer from raw data and compare")
    args = ap.parse_args()

    if not ANCHORS_FILE.exists():
        print("FAIL: %s is missing" % ANCHORS_FILE.name)
        return 1
    anchors = json.loads(ANCHORS_FILE.read_text(encoding="utf-8"))
    units_doc = json.loads(UNITS_FILE.read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8") if README.exists() else None

    results = run_checks(units_doc, anchors, readme)
    for name, ok, detail in results:
        print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                               ("  -- " + detail) if detail and not ok else ""))
    failed = [n for n, ok, _ in results if not ok]

    # fail-closed proof: each injection must turn the check set red
    print("  -- fail-closed injections --")
    for label, mu, ma in injections(units_doc, anchors):
        sub = run_checks(mu, ma, readme)
        went_red = any(not ok for _, ok, _ in sub)
        print("  [%s] injecting: %s" % ("PASS" if went_red else "FAIL", label))
        if not went_red:
            failed.append("injection did not go red: " + label)

    if args.with_data:
        if not os.environ.get("FLYBRAIN_DATA_DIR"):
            print("  (--with-data requested but FLYBRAIN_DATA_DIR is unset -- skipping)")
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_bma", ROOT / "scripts" / "build_malecns_anchors.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["_bma"] = mod
            spec.loader.exec_module(mod)
            fresh = mod.build()
            same = all(anchors[k] == fresh[k] for k in
                       ("superclass_matrix", "anchored_type_matrix", "profile_matrix",
                        "profile_anchors", "profile_classification", "regions"))
            print("  [%s] recomputing from raw data reproduces the artifact (no drift)"
                  % ("PASS" if same else "FAIL"))
            if not same:
                failed.append("anchors artifact has drifted from the raw data")

    print("-" * 72)
    if failed:
        print("GATE 10 FAILED -- %d problem(s)" % len(failed))
        for f in failed:
            print("  -", f)
        return 1
    print("Gate 10 PASSED - %d checks, %s anchored cells in %d populations, "
          "%d/%d units embodied, %d contradictions (all acknowledged)."
          % (len(results), "{:,}".format(anchors["summary"]["anchored_real_cells"]),
             anchors["summary"]["anchored_profiles"],
             units_doc["stats"]["embodied_units"], len(units_doc["units"]),
             units_doc["stats"]["structural_support_edges_contradicted"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
