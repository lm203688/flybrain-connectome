#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v2.31.0 — ledger the *unannotated half* of the Drosophila larva connectome.

Context
-------
v2.28.0 pulled the larva network into the library as eight sensory-channel
units.  They were built by aggregating nodes on
``(cell_type, annotations)`` -- the two columns the original authors
published.  What the aggregation silently *dropped* is the other half of the
network: the nodes whose ``annotations`` read ``no official annotation``.
The library never said how big that half is, so nothing in it could answer
"how much of the larva connectome do the eight units actually cover?".

This script answers that, and only that.  It is a ledger, not a proposal:

* every number is accumulated out of ``nodes.csv`` / ``edges.csv``;
* no cluster is given a function, a name, or a unit.  The source's own
  ``cluster`` column (the authors' inferred clusters) is used as-is;
* a synapse is marked *covered* when BOTH endpoints' ``(cell_type,
  modality bucket)`` resolve to a ``larv.*`` profile that at least one larva
  unit declares as a member.  Coverage here means "traceable into the
  library", not "functionally characterised" -- a unit may legitimately
  declare an ``_unannotated`` member population as a filler role.

Honest limits, kept rather than papered over
--------------------------------------------
* ``cluster`` is the source's own inferred cluster index.  Two nodes in one
  cluster are *suggested* to share a cell type by the reconstruction, not
  asserted to: no lineage or morphology is checked here.
* ``homologue`` pairs are counted as the source declares them (i -> j and
  j -> i), which is a claim about left/right duality, not a test of it.
* cluster 0 in the source holds 364 nodes; it is the authors' unassigned
  bucket, and it turns out to be the single largest holder of synapses in
  the network.  That is a measured fact about the reconstruction, not a
  statement about biology.
* nothing here is added to FUNCTIONAL_UNITS or MODULE_PROFILES.  A cluster
  with no function is structure, and the library does not file structure as
  function.

Usage
-----
    python scripts/extract_larva_clusters.py            # writes the artifact
    python scripts/extract_larva_clusters.py --report   # stdout summary only
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LARVA_DIR = ROOT / "larva_data"
RAW = LARVA_DIR / "raw"

OUT = (ROOT / "flybrain-connectome-mcp" / "functional_units"
       / "larva_clusters.json")
PROFILES = (ROOT / "flybrain-connectome-mcp" / "functional_units"
            / "larva_profiles.json")

NODES_CSV = RAW / "nodes.csv"
EDGES_CSV = RAW / "edges.csv"

SOURCE = ("WormWiring / Winding et al. 2023, Science 379:eadd9330 "
          "(doi:10.1126/science.add9330), larva network `fly_larva`")

# read the modality bucketder out of the v2.28.0 extractor rather than
# re-implementing it: the two must agree or the coverage numbers below are
# counting a different partition than the units were built from.
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "extract_larva_profiles", Path(__file__).resolve().parent
    / "extract_larva_profiles.py")
_LP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_LP)
bucket = _LP.bucket
_slug = _LP._slug


def _read_nodes() -> list[dict]:
    with NODES_CSV.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _read_edges() -> list[dict]:
    with EDGES_CSV.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _annotated(annotations: str) -> bool:
    a = (annotations or "").strip()
    return bool(a) and "no official annotation" not in a


def build() -> dict:
    nodes = _read_nodes()
    edges = _read_edges()

    # index -> {cluster, cell_type, annotations, hemisphere, homologue}
    info: dict[int, dict] = {}
    for i, r in enumerate(nodes):
        info[i] = {
            "cluster": (r.get(" cluster") or "").strip(),
            "cell_type": (r.get(" cell_type") or "").strip(),
            "annotations": (r.get(" annotations") or "").strip(),
            "hemisphere": (r.get(" hemisphere") or "").strip(),
            "homologue": (r.get(" homologue") or "").strip(),
            "vids": (r.get(" vids") or "").strip(),
        }

    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    unit_members: list[tuple[str, set[str]]] = []
    for u in profiles["units"]:
        unit_members.append((u["name"],
                             {m["neuron"] for m in u.get("members", [])}))

    # node -> (profile id, covered-by-unit-or-not)
    node_profile: dict[int, str] = {}
    node_covered: dict[int, bool] = {}
    for i, d in info.items():
        pid = "larv." + _slug(d["cell_type"],
                              bucket(d["annotations"], d["cell_type"]))
        node_profile[i] = pid
        node_covered[i] = any(pid in mem for _n, mem in unit_members)

    # per-unit reach, so a unit's share of the network is a measured number
    # rather than an inference from its member list
    unit_syn: dict[str, int] = {n: 0 for n, _m in unit_members}
    unit_nodes: dict[str, set] = {n: set() for n, _m in unit_members}

    # accumulate
    total_syn = 0
    both_cov = 0
    either_cov = 0
    frontier_syn = 0
    covered_pairs: Counter[tuple[str, str]] = Counter()
    cell_covered_syn: Counter[str] = Counter()
    cell_syn: Counter[str] = Counter()
    cell_nodes: Counter[str] = Counter()
    cl_internal = Counter()
    cl_out = Counter()
    cl_in = Counter()
    cl_out_pairs: dict[str, Counter] = defaultdict(Counter)
    cl_in_pairs: dict[str, Counter] = defaultdict(Counter)
    cl_nodes: Counter[str] = Counter()
    cl_ann: Counter[str] = Counter()
    cl_ctypes: dict[str, set] = defaultdict(set)
    cl_self_syn = 0
    node_syn: Counter[int] = Counter()
    unannot_syn = 0
    unannot_nodes: set[int] = set()

    for r in edges:
        try:
            s = int(r["# source"])
            t = int(r[" target"])
            c = int(r[" count"])
        except (KeyError, TypeError, ValueError):
            continue
        src = info.get(s)
        tgt = info.get(t)
        if src is None or tgt is None:
            continue
        total_syn += c
        node_syn[s] += c
        node_syn[t] += c
        # an edge counts once against the unannotated population whenever
        # either of its endpoints lacks an official annotation
        if not _annotated(src["annotations"]) or not _annotated(tgt["annotations"]):
            unannot_syn += c
        if not _annotated(src["annotations"]):
            unannot_nodes.add(s)
        if not _annotated(tgt["annotations"]):
            unannot_nodes.add(t)
        cs, ct = src["cluster"], tgt["cluster"]
        if cs == ct:
            cl_internal[cs] += c
            if cs == ct and s == t:
                cl_self_syn += c
        else:
            cl_out[cs] += c
            cl_in[ct] += c
            cl_out_pairs[cs][ct] += c
            cl_in_pairs[ct][cs] += c

        ps, pt = node_profile[s], node_profile[t]
        for name, mem in unit_members:
            if ps in mem and pt in mem:
                unit_syn[name] += c
                unit_nodes[name].update((s, t))

        cov_s, cov_t = node_covered[s], node_covered[t]
        if cov_s and cov_t:
            both_cov += c
            covered_pairs[(node_profile[s], node_profile[t])] += c
            cell_covered_syn[src["cell_type"]] += c
            cell_covered_syn[tgt["cell_type"]] += c
        if cov_s or cov_t:
            either_cov += c
        else:
            frontier_syn += c

        for(nd, ct_) in ((s, src["cell_type"]), (t, tgt["cell_type"])):
            cell_syn[ct_] += c

    for i, d in info.items():
        cl = d["cluster"]
        cl_nodes[cl] += 1
        if _annotated(d["annotations"]):
            cl_ann[cl] += 1
        cl_ctypes[cl].add(d["cell_type"] or "(none)")

    # left/right homologue pairs, as the source declares them
    homo_pairs = 0
    by_vid = {}
    for i, d in info.items():
        if d["vids"]:
            try:
                by_vid[int(d["vids"])] = i
            except ValueError:
                pass
    for i, d in info.items():
        h = d["homologue"]
        vid = d["vids"]
        if not h or not vid or h == vid:
            continue
        j = by_vid.get(int(h)) if h.isdigit() else None
        if j is None or j <= i:
            continue
        if info[j]["homologue"] == vid and info[i]["cluster"] == info[j]["cluster"]:
            homo_pairs += 1

    clusters = []
    for cl in sorted(cl_nodes, key=lambda x: (x == "0", -cl_nodes[x])):
        n = cl_nodes[cl]
        ann = cl_ann[cl]
        status = "all_annotated" if ann == n else (
            "none_annotated" if ann == 0 else "mixed")
        clusters.append({
            "cluster": cl,
            "n_nodes": n,
            "n_annotated": ann,
            "n_unannotated": n - ann,
            "annotation_status": status,
            "cell_types": sorted(cl_ctypes[cl])[:8],
            "internal_synapses": cl_internal[cl],
            "out_synapses": cl_out[cl],
            "in_synapses": cl_in[cl],
            "top_out": [{"to": k, "synapses": v}
                        for k, v in cl_out_pairs[cl].most_common(5)],
            "top_in": [{"from": k, "synapses": v}
                       for k, v in cl_in_pairs[cl].most_common(5)],
        })

    cell_types = sorted({c for cs in cl_ctypes.values() for c in cs})
    covered_ctypes = sorted({c for c, v in cell_covered_syn.items() if v})
    frontier_ctypes = sorted({c for c in cell_types
                              if cell_covered_syn.get(c, 0) == 0})

    # ------------------------------------------------------------------ #
    # v2.34.0 -- make the per-unit rows addable, or say why they cannot.
    #
    # Auditing this ledger after the v2.33.0 attribution bug: the coverage
    # arithmetic itself is sound (either + frontier == total, asserted below),
    # but the eight `unit_coverage` rows sum to 319,064 against a covered
    # total of 271,956 -- 1.17x.  That is not a double count, it is the eight
    # units sharing profiles: `larv.lhn_unannotated` and friends are declared
    # by more than one unit, so one synapse legitimately serves two units.
    #
    # The v2.31.0 artifact printed those eight rows and never said so, so the
    # obvious move -- add the column, get the total -- silently overstates
    # coverage by 17%.  Both figures are now emitted, plus the profile-level
    # overlap that explains the gap, and the arithmetic is asserted.
    # ------------------------------------------------------------------ #
    prof_units: dict[str, list[str]] = defaultdict(list)
    for name, mem in unit_members:
        for pid in sorted(mem):
            prof_units[pid].append(name)
    shared_profiles = {p: u for p, u in sorted(prof_units.items()) if len(u) > 1}
    per_unit_sum = sum(unit_syn[n] for n, _m in unit_members)
    attribution = {
        "per_unit_sum": per_unit_sum,
        "covered_total": both_cov,
        "ratio": round(per_unit_sum / both_cov, 4) if both_cov else None,
        "shared_profiles": len(shared_profiles),
        "shared_profiles_detail": shared_profiles,
        "note": ("The eight unit rows are NOT additive. A profile declared by "
                 "more than one unit (larv.lhn_unannotated and the other "
                 "shared ones) makes a single synapse count toward each of "
                 "them, which is correct but means the column sums above the "
                 "covered total. Use `covered_total` for network coverage and "
                 "the per-unit rows only to compare units with each other."),
    }

    doc = {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "purpose": ("ledger of the larva connectome at the source's own "
                    "cluster resolution, plus the coverage of the eight "
                    "v2.28.0/v2.29.0 larva units over it"),
        "caveat": ("cluster is the SOURCE's inferred cluster index and is "
                   "reproduced, not asserted; no cluster is given a "
                   "function or a unit, and none was added to the library. "
                   "Coverage means the endpoint's (cell_type, modality "
                   "bucket) resolves to a larva profile at least one unit "
                   "declares -- it does NOT mean the circuit's function is "
                   "known. Left/right homology is counted as the source "
                   "declares it, not verified. The eight unit_coverage rows "
                   "are not additive: profiles are shared between units, so "
                   "their sum exceeds `coverage.synapses_both_ends_covered` "
                   "by the ratio recorded in `unit_attribution`."),
        "network": {
            "nodes": len(nodes),
            "edges": len(edges),
            "synapses": total_syn,
            "n_clusters": len(cl_nodes),
            "homologue_pairs": homo_pairs,
            "unannotated_nodes": len(unannot_nodes),
            "unannotated_nodes_pct": round(100 * len(unannot_nodes) / len(nodes), 2) if nodes else 0.0,
            "unannotated_incident_synapses": unannot_syn,
            "unannotated_synapse_pct": round(100 * unannot_syn / total_syn, 2) if total_syn else 0.0,
            "unannotated_note": ("an edge touches the unannotated population "
                                 "whenever EITHER endpoint lacks an official "
                                 "annotation, so the synapse share exceeds the "
                                 "node share"),
        },
        "coverage": {
            "synapses_total": total_syn,
            "synapses_both_ends_covered": both_cov,
            "synapses_both_ends_covered_pct": round(100 * both_cov / total_syn, 2) if total_syn else 0.0,
            "synapses_either_end_covered": either_cov,
            "synapses_frontier": frontier_syn,
            "synapses_frontier_pct": round(100 * frontier_syn / total_syn, 2) if total_syn else 0.0,
            "defined": ("an endpoint is covered when its "
                        "(cell_type, modality bucket) resolves to a larv.* "
                        "profile that at least one larva unit declares as a "
                        "member; a synapse is counted as covered only when "
                        "BOTH endpoints are"),
        },
        "cell_type_coverage": {
            "cell_types_seen": cell_types,
            "covered": covered_ctypes,
            "frontier": frontier_ctypes,
            "frontier_note": ("cell classes with no synapse on either side "
                              "reaching a covered endpoint"),
        },
        "unit_coverage": {
            name: {
                "synapses_both_ends": unit_syn[name],
                "synapse_share_pct": (round(100 * unit_syn[name] / total_syn, 2)
                                      if total_syn else 0.0),
                "nodes_reached": len(unit_nodes[name]),
                "n_member_profiles": len(unit_members[i][1]),
            }
            for i, (name, _mem) in enumerate(unit_members)
        },
        "unit_attribution": attribution,
        "covered_profile_pairs": [
            {"from": a, "to": b, "synapses": v}
            for (a, b), v in covered_pairs.most_common(30)
        ],
        "clusters": clusters,
    }
    return doc


def report(doc: dict) -> None:
    net = doc["network"]
    cov = doc["coverage"]
    print("larva network: %d nodes / %d edges / %d synapses / %d clusters"
          % (net["nodes"], net["edges"], net["synapses"], net["n_clusters"]))
    print("  left/right homologue pairs (as declared): %d" % net["homologue_pairs"])
    print("  unannotated nodes: %d (%.2f%% of cells) touching %d synapses "
          "(%.2f%%)"
          % (net["unannotated_nodes"], net["unannotated_nodes_pct"],
             net["unannotated_incident_synapses"], net["unannotated_synapse_pct"]))
    print("coverage of the eight larva units:")
    print("  both ends covered : %d synapses (%.2f%%)"
          % (cov["synapses_both_ends_covered"], cov["synapses_both_ends_covered_pct"]))
    print("  either end covered: %d synapses" % cov["synapses_either_end_covered"])
    print("  frontier          : %d synapses (%.2f%%)"
          % (cov["synapses_frontier"], cov["synapses_frontier_pct"]))
    ct = doc["cell_type_coverage"]
    print("cell classes: %d seen, %d touched by covered synapses, %d frontier"
          % (len(ct["cell_types_seen"]), len(ct["covered"]), len(ct["frontier"])))
    print("  frontier cell classes: %s" % ", ".join(ct["frontier"]))
    print("top 10 clusters by synapse volume:")
    for c in sorted(doc["clusters"], key=lambda x: -(x["internal_synapses"]
                                                     + x["out_synapses"]
                                                     + x["in_synapses"]))[:10]:
        tot = c["internal_synapses"] + c["out_synapses"] + c["in_synapses"]
        print("  cluster %-4s nodes=%-4d syn=%-7d %-16s %s"
              % (c["cluster"], c["n_nodes"], tot, c["annotation_status"],
                 " ".join(c["cell_types"][:4])))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT), help="artifact path")
    ap.add_argument("--report", action="store_true",
                    help="print the summary instead of writing")
    args = ap.parse_args()

    doc = build()

    # ------------------------------------------------------------------ #
    # Assertions, before anything is written.
    #
    # The coverage partition has to close: every synapse is either reached by
    # a covered endpoint or it is frontier, and the two must add to the whole.
    # The v2.33.0 pass found a four-times-inflated per-type column in the
    # MaleCNS ledger, so the habit here is to check the arithmetic rather
    # than trust that the loop above added the right things up.  It did --
    # these pass on the real data and are kept because they would catch the
    # next version that does not.
    # ------------------------------------------------------------------ #
    import sys as _sys

    net, cov = doc["network"], doc["coverage"]
    total = net["synapses"]
    if total <= 0:
        print("REFUSING TO WRITE: network synapse total is %d" % total,
              file=_sys.stderr)
        return 3
    if cov["synapses_either_end_covered"] + cov["synapses_frontier"] != total:
        print("REFUSING TO WRITE: covered + frontier = %d but the network holds "
              "%d synapses; the coverage partition does not close"
              % (cov["synapses_either_end_covered"] + cov["synapses_frontier"],
                 total), file=_sys.stderr)
        return 3
    if cov["synapses_both_ends_covered"] > cov["synapses_either_end_covered"]:
        print("REFUSING TO WRITE: both-ends covered (%d) exceeds either-end "
              "covered (%d), which is impossible"
              % (cov["synapses_both_ends_covered"],
                 cov["synapses_either_end_covered"]), file=_sys.stderr)
        return 3
    attr = doc["unit_attribution"]
    if attr["per_unit_sum"] < attr["covered_total"]:
        print("REFUSING TO WRITE: the per-unit rows sum to %d, below the "
              "covered total %d; shared profiles can only push the sum up"
              % (attr["per_unit_sum"], attr["covered_total"]), file=_sys.stderr)
        return 3
    # Every cluster's internal + out must reconstruct the network.  A
    # cross-cluster edge is charged once to the source cluster's `out` and
    # once to the target's `in`, so `in` is NOT added here: internal + out
    # already covers each synapse exactly once, and adding `in` too would
    # double the 305,482 cross-cluster synapses.  (Asserted the other way
    # first, which reported 658,093 against a 352,611 network -- the
    # assertion was wrong, not the ledger.  out == in holds because every
    # cross-cluster edge contributes to both.)
    recon = sum(c["internal_synapses"] + c["out_synapses"] for c in doc["clusters"])
    if recon != total:
        print("REFUSING TO WRITE: per-cluster internal+out sums to %d against "
              "a network total of %d" % (recon, total), file=_sys.stderr)
        return 3
    if sum(c["out_synapses"] for c in doc["clusters"]) != sum(
            c["in_synapses"] for c in doc["clusters"]):
        print("REFUSING TO WRITE: cluster out and in totals disagree, so some "
              "edge is not landing on both of its clusters", file=_sys.stderr)
        return 3
    print("assertions: coverage closes (%d + %d = %d); per-unit sum %d >= "
          "covered %d via %d shared profiles; per-cluster sum %d"
          % (cov["synapses_either_end_covered"], cov["synapses_frontier"],
             total, attr["per_unit_sum"], attr["covered_total"],
             attr["shared_profiles"], recon))

    if args.report:
        report(doc)
        return 0
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    report(doc)
    print("wrote %s (%d bytes)" % (args.out, Path(args.out).stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
