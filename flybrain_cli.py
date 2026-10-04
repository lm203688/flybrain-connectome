#!/usr/bin/env python3
"""
flybrain — unified developer CLI for the flybrain-connectome toolkit.
==================================================================

A zero-third-party-dependency command line that wraps the project's three
public surfaces:

  serve      start the local HTTP API server (default :8799)
  query      call one connectome tool over HTTP
  motifs     export / pull the derived SwarmLabs motif document
  generate   compose a synthetic bio-topology (pass-through to the generator)
  verify     run the end-to-end smoke test (_verify.py)
  info       report the resolved toolkit / data / snapshot paths

Design notes
------------
* Standard library only — no pip install required to run in-repo.
* The toolkit is located through `resolve_layout()`: `$FLYBRAIN_HOME` first,
  then this file's directory, then the cwd. That makes all three shapes work:
  clone-and-run, `pip install -e .`, and a launcher installed elsewhere.
* The connectome data (5.63 GB) is NEVER embedded. `serve`/`query` need a
  running service backed by your own local copy of MaleCNS v1.0; `generate`
  and `motifs --out` (offline snapshot) need no data at all.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
__version__ = "2.37.0"
_TOOLKIT_DIRNAME = "flybrain-connectome-mcp"
_TOOLKIT_MARKER = "synthetic_bio_topology.py"


def resolve_layout():
    """Locate the flybrain-connectome checkout that holds the toolkit.

    Returns ``(root, mcp_dir, mcp_pkg, motifs_dir)``.

    Resolution order — first match wins:

    1. ``$FLYBRAIN_HOME`` — explicit override; point it at a checkout.
    2. the directory of this file — clone-and-run, and ``pip install -e .``
       (an editable install maps this module back to the real checkout).
    3. the current working directory — a launcher installed elsewhere that is
       being run from inside a checkout.

    Each candidate is probed both as a repo root (``<c>/flybrain-connectome-mcp``)
    and as the toolkit directory itself.
    """
    cands = []
    env = os.environ.get("FLYBRAIN_HOME")
    if env:
        cands.append(Path(env).expanduser().resolve())
    cands.append(HERE)
    try:
        cands.append(Path.cwd().resolve())
    except OSError:  # pragma: no cover - deleted cwd
        pass

    seen = set()
    for root in cands:
        if root in seen:
            continue
        seen.add(root)
        for mcp in (root / _TOOLKIT_DIRNAME, root):
            if (mcp / _TOOLKIT_MARKER).exists():
                return root, mcp, mcp / "mcp_connectome", mcp / "motifs"
    # Nothing found: return the in-repo guess so error messages can name it.
    mcp = HERE / _TOOLKIT_DIRNAME
    return HERE, mcp, mcp / "mcp_connectome", mcp / "motifs"


ROOT, MCP_DIR, MCP_PKG, MOTIFS_DIR = resolve_layout()


def _add_paths() -> None:
    for p in (str(MCP_DIR), str(MCP_PKG), str(MOTIFS_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _require_toolkit() -> None:
    """Fail loudly with an actionable message instead of an ImportError trace."""
    if not (MCP_DIR / _TOOLKIT_MARKER).exists():
        sys.stderr.write(
            "ERROR: cannot locate the flybrain-connectome toolkit.\n"
            "  looked in : %s\n"
            "  and also  : %s\n"
            "Fix: run the CLI from inside a checkout, or point FLYBRAIN_HOME at one:\n"
            "  export FLYBRAIN_HOME=/path/to/flybrain-connectome\n"
            "Clone: https://github.com/lm203688/flybrain-connectome\n"
            % (MCP_DIR, HERE))
        raise SystemExit(2)


def _default_data_dir() -> str:
    cand = ROOT / "male_cns"
    return str(cand) if cand.exists() else ""


def _resolve_key(explicit: str | None = None) -> str | None:
    """Same-machine key discovery, in precedence order.

    1. ``--api-key`` on the command line
    2. ``$FLYBRAIN_API_KEY``
    3. ``mcp_connectome/config.json`` → ``api_keys[0]`` (via the client's
       ``resolve_local_api_key``), so a local service works without exporting
       anything. A downstream copy of the client has no such file and returns
       nothing, which is why this is a fallback and not the primary path.
    """
    if explicit:
        return explicit
    env = os.environ.get("FLYBRAIN_API_KEY")
    if env:
        return env
    try:
        from flybrain_connectome_client import resolve_local_api_key
        key, _src = resolve_local_api_key()
        return key or None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------- #
# subcommands
# ---------------------------------------------------------------------- #
def cmd_serve(args) -> int:
    _add_paths()
    _require_toolkit()
    if not os.environ.get("FLYBRAIN_DATA_DIR"):
        d = _default_data_dir()
        if d:
            os.environ["FLYBRAIN_DATA_DIR"] = d
    if args.host:
        os.environ["FLYBRAIN_API_HOST"] = args.host
    if args.port:
        os.environ["FLYBRAIN_API_PORT"] = str(args.port)
    if args.api_key:
        os.environ["FLYBRAIN_API_KEY"] = args.api_key
    import api_server  # noqa: WPS433 (late import keeps --help dependency-free)
    api_server.main()
    return 0


def cmd_query(args) -> int:
    _add_paths()
    _require_toolkit()
    from flybrain_connectome_client import FlybrainHTTPClient, FlybrainUnavailable
    c = FlybrainHTTPClient(args.base_url, _resolve_key(args.api_key))
    payload = json.loads(args.args) if args.args else {}
    try:
        result = c.query(args.tool, payload)
    except FlybrainUnavailable as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_motifs(args) -> int:
    _add_paths()
    _require_toolkit()
    from flybrain_connectome_client import FlybrainHTTPClient, FlybrainUnavailable
    c = FlybrainHTTPClient(args.base_url, _resolve_key(args.api_key))
    try:
        doc = c.export_swarm_motifs(refresh=args.refresh)
    except FlybrainUnavailable as e:
        print("ERROR: %s" % e, file=sys.stderr)
        print("hint: the offline snapshot lives at "
              "flybrain-connectome-mcp/motifs/swarm_agent_topology_motifs.json",
              file=sys.stderr)
        return 1
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote %s (%d bytes)" % (args.out, len(text)))
    else:
        print(text)
    return 0


def cmd_generate(args) -> int:
    _add_paths()
    _require_toolkit()
    import synthetic_bio_topology as c1
    return c1.main(args.rest or [])


def cmd_generate_raw(rest: list[str]) -> int:
    """Forward argv verbatim to the C1 generator.

    We deliberately bypass argparse for `generate`: `nargs=REMAINDER` is
    unreliable for leading `--flags` inside a sub-parser (Python >= 3.13 mixes
    values into the leftover list, breaking flag/value pairing). Forwarding the
    raw tail keeps the generator's own CLI authoritative and makes
    `flybrain generate --help` print the real generator options.
    """
    _add_paths()
    _require_toolkit()
    import synthetic_bio_topology as c1
    saved = sys.argv[0]
    sys.argv[0] = "flybrain generate"
    try:
        return c1.main(rest)
    finally:
        sys.argv[0] = saved


def cmd_verify(args) -> int:
    _add_paths()
    _require_toolkit()
    if not os.environ.get("FLYBRAIN_DATA_DIR"):
        d = _default_data_dir()
        if d:
            os.environ["FLYBRAIN_DATA_DIR"] = d
    import _verify
    return _verify.main([])


def cmd_stages(args) -> int:
    """v2.30.0 — print the C. elegans developmental axis.

    All eight Witvliet 2020 reconstructions (L1 x4, L2, L3, adult x2) form one
    series, but the library used to carry only the two adults.  This command
    reports what the other six contribute: for each stage how much of the
    network was reconstructed, and how many edges / synapses each C. elegans
    unit's own cell classes carry there.

    Every number comes from `functional_units/cel_development_stages.json`,
    which `scripts/extract_cel_development.py` sums out of the raw xlsx files.
    `--caveat` prints why the L1 columns are a floor and why the L1-only edges
    are deliberately not called transient synapses.
    """
    path = MCP_DIR / "functional_units" / "cel_development_stages.json"
    if not path.exists():
        print("developmental axis artifact missing: %s" % path)
        print("run: python scripts/extract_cel_development.py")
        return 2
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    if args.caveat:
        print(doc["caveat"], "\n")
    ov = doc.get("circuit_overlap", {})
    if ov.get("shared_cell_classes"):
        print("the four circuits share cell classes, so their rows are NOT "
              "additive:")
        for pair, shared in ov["shared_cell_classes"].items():
            print("    %-64s %s" % (pair, shared))
        print()
    sd = doc.get("stage_diffs", {})
    if sd:
        print("stage key sets (measured, not asserted): L1 union=%d  adult "
              "union=%d  shared=%d  L1-only=%d  adult-only=%d"
              % (sd["l1_union_keys"], sd["adult_union_keys"],
                 sd["shared_keys"], sd["l1_only_keys"], sd["adult_only_keys"]))
        print()
    dvs = doc.get("declared_vs_shipped", {})
    if dvs.get("measured_wider_than_unit"):
        print("v2.35.0 -- this series measures a wider circuit than the unit it "
              "attaches to:")
        for uname, extra in sorted(dvs["measured_wider_than_unit"].items()):
            print("    %-42s +%s" % (uname, extra))
        print("    (declared in PROFILES, no edge in the adult reconstruction, "
              "so not shipped as a v2.27 member)")
        print()
    for s in doc["stages"]:
        print("[%s] %s" % (s["stage"], s["label"]))
        for a in s["animals"]:
            print("    %-34s classes=%3d unique_edges=%4d synapses=%5d"
                  % (a["dataset"], a["n_cell_classes"],
                     a["n_unique_edges"], a["n_weighted_edges"]))
        attr = s.get("attribution")
        if attr:
            print("    %-42s sum=%-14s union=%-14s inflation=%s"
                  % ("ALL FOUR CIRCUITS",
                     attr["sum_of_circuits"], attr["union"],
                     attr["inflation_ratio"]))
        for uname, m in s["unit_measurements"].items():
            if args.unit and uname not in args.unit:
                continue
            print("    %-42s edges=%-14s synapses=%-14s present=%s"
                  % (uname, m["edges"], m["synapses"],
                     "yes" if m["present_in_every_animal"]
                     else "NOT IN EVERY ANIMAL"))
        print()
    return 0


def cmd_larva_clusters(args) -> int:
    """v2.31.0 — ledger the larva connectome at cluster resolution.

    Two questions, both answered by counting every edge of the Winding et al.
    reconstruction rather than by modelling either one:

    1. how much of the network the eight v2.28.0/v2.29.0 larva units actually
       cover -- a synapse counts when BOTH of its endpoints resolve to a
       `larv.*` profile the unit declares as a member;
    2. what the unannotated half is really made of, in synapses rather than
       headcount, and which cell classes sit entirely outside every unit.

    Every number comes from `functional_units/larva_clusters.json`, which
    `scripts/extract_larva_clusters.py` sums out of nodes.csv / edges.csv.
    """
    path = MCP_DIR / "functional_units" / "larva_clusters.json"
    if not path.exists():
        print("larva cluster ledger missing: %s" % path)
        print("run: python scripts/extract_larva_clusters.py")
        return 2
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    if args.caveat:
        print(doc["caveat"], "\n")

    net = doc["network"]
    print("larva network: %d nodes / %d edges / %d synapses / %d clusters"
          % (net["nodes"], net["edges"], net["synapses"], net["n_clusters"]))
    print("  unannotated cells: %d (%.2f%%) touching %d synapses (%.2f%%)"
          % (net["unannotated_nodes"], net["unannotated_nodes_pct"],
             net["unannotated_incident_synapses"], net["unannotated_synapse_pct"]))
    print("  left/right homologue pairs, as declared: %d"
          % net["homologue_pairs"])

    cov = doc["coverage"]
    print("unit coverage (both endpoints traceable):")
    for name, c in sorted(doc["unit_coverage"].items(),
                          key=lambda kv: -kv[1]["synapses_both_ends"]):
        if args.unit and name not in args.unit:
            continue
        print("    %-42s %7d synapses  %5.2f%%  nodes=%-5d (%d profiles)"
              % (name, c["synapses_both_ends"], c["synapse_share_pct"],
                 c["nodes_reached"], c["n_member_profiles"]))
    print("    %-42s %7d synapses  %5.2f%%"
          % ("ALL units (union)", cov["synapses_both_ends_covered"],
             cov["synapses_both_ends_covered_pct"]))
    print("    %-42s %7d synapses  %5.2f%%  <- frontier"
          % ("no unit declares either endpoint",
             cov["synapses_frontier"], cov["synapses_frontier_pct"]))
    attr = doc.get("unit_attribution")
    if attr:
        print("    ^ the per-unit rows above are NOT additive: %d profiles are "
              "declared by more than one unit," % attr["shared_profiles"])
        print("      so they sum to %d against the %d covered above (%.4fx). "
              "Use the union row for coverage."
              % (attr["per_unit_sum"], attr["covered_total"], attr["ratio"]))
        if args.caveat:
            for p, us in sorted(attr["shared_profiles_detail"].items()):
                print("      shared: %-34s %s"
                      % (p, ", ".join(u.replace("larv_", "").replace("_unit", "")
                                      for u in us)))

    ct = doc["cell_type_coverage"]
    print("cell classes: %d seen, %d touched, %d entirely outside every unit"
          % (len(ct["cell_types_seen"]), len(ct["covered"]), len(ct["frontier"])))
    print("    outside every unit: %s" % ", ".join(ct["frontier"]))
    if ct.get("frontier_is_not_an_annotations_verdict"):
        print("    ^ being outside a unit is a coverage fact, not an "
              "annotation verdict -- see annotation identity below")

    ident = doc.get("annotation_identity")
    if ident:
        print("annotation identity: %d classes carry the `_unannotated` "
              "suffix; %d of them hold annotated cells (%d cells)"
              % (ident["classes_with_fallback_suffix"],
                 ident["classes_misnamed_by_suffix"],
                 ident["cells_in_misnamed_classes"]))
        print("    cells genuinely without an official annotation: %d (%.2f%%)"
              % (ident["cells_actually_unannotated"],
                 ident["cells_actually_unannotated_pct"]))
        for pid, e in sorted(ident["misnamed_detail"].items(),
                             key=lambda kv: -kv[1]["cells_with_official_annotation"])[:5]:
            print("    %-32s %d/%d annotated  e.g. %s"
                  % (pid, e["cells_with_official_annotation"], e["cells"],
                     ", ".join(e["example_annotations"][:2])))
        if args.caveat:
            print("    %s" % ident["note"])

    top = sorted(doc["clusters"],
                 key=lambda c: -(c["internal_synapses"] + c["out_synapses"]
                                 + c["in_synapses"]))[:args.top]
    print("top %d clusters by synapse volume:" % len(top))
    for c in top:
        tot = c["internal_synapses"] + c["out_synapses"] + c["in_synapses"]
        if args.unannotated and c["n_unannotated"] == 0:
            continue
        print("    cluster %-4s nodes=%-4d synapses=%-7d %-15s %s"
              % (c["cluster"], c["n_nodes"], tot, c["annotation_status"],
                 " ".join(c["cell_types"][:4])))
    return 0


def cmd_dimorphism(args) -> int:
    """v2.32.0 — ledger the male-specific population sitting inside MaleCNS.

    MaleCNS v1.0 is a male reconstruction and its annotation table carries a
    `dimorphism` column.  `scripts/extract_malecns_dimorphism.py` streams all
    151,856,684 weight rows and counts, per edge, how many synapses touch a
    dimorphic body and how many sit between two of them.

    The interesting number is the gap between those two: the population is
    large and talks to the whole network, but almost none of it talks to
    itself.  And because MaleCNS contains no female reconstruction, none of
    this measures a sex difference -- it only reports what the annotation
    column declares and what the edges actually do.
    """
    path = MCP_DIR / "functional_units" / "malecns_dimorphism.json"
    if not path.exists():
        print("male dimorphic ledger missing: %s" % path)
        print("run: FLYBRAIN_DATA_DIR=... python scripts/extract_malecns_dimorphism.py")
        return 2
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    if args.caveat:
        for c in doc["caveat"]:
            print("! %s" % c)
        print()

    pop, meas = doc["population"], doc["measurement"]
    base = meas["network_baseline"]
    print("MaleCNS dimorphic population: %d bodies over %d cell types"
          % (pop["bodies"], pop["types"]))
    for lb, n in pop["labels"].items():
        print("    %-32s %5d" % (lb, n))
    print("measured over %s raw weight rows of the neuron subgraph:"
          % "{:,}".format(doc["source"]["rows_scanned"]))
    print("    touching the population    %12d pairs  %5.2f%%   "
          "%13d synapses  %5.2f%%"
          % (meas["edges_touching"], meas["edges_touching_pct"],
             meas["synapses_touching"], meas["synapses_touching_pct"]))
    print("    both endpoints dimorphic   %12d pairs  %5.2f%%   "
          "%13d synapses  %5.2f%%   (%.1f%% of the touching synapses)"
          % (meas["edges_both_ends"], meas["edges_both_ends_pct"],
             meas["synapses_both_ends"], meas["synapses_both_ends_pct"],
             100.0 * meas["internal_share_of_touched_synapses"]))
    print("    baseline: %d pairs / %d synapses"
          % (base["edges"], base["synapses"]))

    print("per annotation label:")
    for lb, v in doc["per_label"].items():
        print("    %-32s bodies=%-5d touching=%-9d both-ends=%-7d synapses=%d"
              % (lb, v["bodies"], v["edges_touching"],
                 v["edges_both_ends"], v["synapses_both_ends"]))

    if args.unit:
        print("per-unit distance to the population:")
        for unit in args.unit:
            print("    %-42s see `flybrain dimorphism --unit` on the ledger; "
                  "unit provenance block `male_dimorphic`" % unit)

    print("heaviest dimorphic types:")
    for t in doc["types_top"][:args.top]:
        alias = t.get("provenance", {}).get("flywire_alias") or []
        print("    %-16s bodies=%-4d %10d synapses (%7.0f/cell) %5.3f%%  %-18s anchored=%s%s"
              % (t["type"], t["bodies"], t["synapses"],
                 t.get("synapses_per_body") or 0.0, t["pct_of_network"],
                 t["superclass"], "yes" if t["anchored"] else "no",
                 ("  [FlyWire: %s]" % alias[0]) if alias else ""))
        if args.provenance:
            for note in t.get("provenance", {}).get("matching_notes", []):
                print("        note: %s" % note)
            grades = t.get("provenance", {}).get("status_labels", []) or []
            itolee = t.get("provenance", {}).get("itolee_grade", []) or []
            if grades or itolee:
                print("        trace: %s%s"
                      % ("/".join(grades),
                         ("  itolee:" + "/".join(itolee)) if itolee else ""))
        if t.get("body_synapse_percentile") is not None:
            print("        per-body strength: p%.2f of annotated bodies "
                  "(median body %s synapses)"
                  % (t["body_synapse_percentile"],
                     (t.get("median_body_synapses") or 0)))

    axes = doc.get("type_axes", {})
    if axes:
        cmp_ = axes.get("axis_comparison") or {}
        print("type axes (this ledger counts the `type` axis only):")
        for col, n in (axes.get("class_counts") or {}).items():
            print("    %-16s %6d classes" % (col, n))
        if cmp_.get("compared"):
            print("    %s differ on %d/%d bodies (%.2f%%), across %d classes"
                  % (cmp_["compared"], cmp_["bodies_differing"],
                     cmp_["bodies_compared"], cmp_["bodies_differing_pct"],
                     cmp_["classes_involved"]))
            print("    -> a class name here may be filed under another name in "
                  "FlyWire / hemibrain; see types_top[].provenance.flywire_alias")

    chk = meas.get("per_type_attribution_check")
    if chk:
        print("per-type attribution check: %s (%d charged == touching + both-ends)"
              % ("reconciles" if chk.get("reconciles") else "FAILED",
                 chk.get("charged_to_types", -1)))

    bs = meas.get("body_scale")
    if bs:
        print("per-body scale (annotated bodies with synapses: %d):"
              % bs["bodies_with_synapses"])
        print("    median %d   p90 %d   p99 %d   p99.9 %d   max %d"
              % (bs["median"], bs["p90"], bs["p99"], bs["p999"], bs["max"]))
        print("    -> per-cell means above are read against this, not against a "
              "rule of thumb; the distribution is heavy-tailed")

    prov = doc.get("dimorphism_provenance", {})
    if prov:
        print("dimorphism provenance: %d/%d types carry a curator matchingNote, "
              "%d are `Roughly traced`"
              % (prov.get("types_with_matching_note", 0),
                 prov.get("types_total", 0),
                 prov.get("types_roughly_traced", 0)))

    ov = doc["anchor_overlap"]
    print("anchored profiles: %d dimorphic types listed explicitly, %d inside a "
          "family rule, %d fully dark"
          % (ov["dimorphic_types_explicitly_anchored"],
             ov["dimorphic_types_family_anchored"],
             ov["dimorphic_types_dark"]))
    print("    (family membership is not tracing: it only means the type sits in "
          "a clan somebody anchored)")

    if args.internal:
        print("heaviest both-ends dimorphic type pairs:")
        for p in doc["internal_type_pairs_top"][:args.top]:
            print("    %-18s -> %-18s edges=%-7d synapses=%d"
                  % (p["from"], p["to"], p["edges"], p["synapses"]))
    return 0


def cmd_function(args) -> int:
    """v2.37.0 — the function axis: coverage by FUNCTION, not by species.

    The library is organised by taxon (115 units named for fruit fly, worm,
    mouse, bird, frog...).  PROJECT_VISION says the generator grows toward a
    function set instead.  This command prints the measured distance between
    the two, so the next unit added is chosen against a number.

    A tag means the unit's own `capability` / `task_hint_pool` fields declare
    a mechanism implementing the category. It is a coverage label, not a
    claim that the unit performs the function well.
    """
    path = MCP_DIR / "functional_units" / "function_coverage.json"
    if not path.exists():
        print("function coverage artifact missing: %s" % path)
        print("run: python scripts/extract_function_coverage.py")
        return 2
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    if args.caveat:
        for c in doc["caveat"]:
            print("! %s" % c)
        print()

    lib = doc["library"]
    print("function axis: %d units / %d categories / %d distinct capability "
          "tokens" % (lib["units"], len(doc["coverage_matrix"]),
                      lib["capability_tokens_distinct"]))
    fams = {}
    for r in doc["coverage_matrix"]:
        fams.setdefault(r["family"], []).append(r)
    for fam in sorted(fams):
        print("  %s" % fam)
        for r in fams[fam]:
            if args.vision and not r["vision_required"]:
                continue
            mark = "*" if r["vision_required"] else " "
            print("   %s %-22s units=%-3d taxa=%-2d connectome-traced=%-3d %s"
                  % (mark, r["category"], r["units"], r["species"],
                     r["connectome_traced_units"], r["status"]))
    print("  (* = required by PROJECT_VISION; unit count, how many taxa carry "
          "it, and how many of those come from a reconstruction)")

    s = doc["summary"]
    if s["vision_required_missing"]:
        print()
        print("MISSING, declared work queue: %s"
              % ", ".join(s["vision_required_missing"]))
    if s["vision_required_thin"]:
        print("THIN (<3 units): %s" % ", ".join(s["vision_required_thin"]))
    if s["cross_species_categories"]:
        print("cross-species (>=3 taxa): %s"
              % ", ".join(s["cross_species_categories"]))
    if doc["library"]["units_with_no_category"]:
        print("units outside every category: %d of %d"
              % (len(doc["library"]["units_with_no_category"]), lib["units"]))
    return 0


def cmd_info(args) -> int:
    """Report what this launcher resolved — the one command that diagnoses
    a broken install (wrong toolkit root, missing data dir, missing snapshot)."""
    ok = (MCP_DIR / _TOOLKIT_MARKER).exists()
    snap = MOTIFS_DIR / "swarm_agent_topology_motifs.json"
    data = os.environ.get("FLYBRAIN_DATA_DIR") or _default_data_dir()
    print("flybrain-connectome — launcher report")
    print("  cli version      : %s" % __version__)
    print("  this file        : %s" % Path(__file__).resolve())
    print("  cwd              : %s" % Path.cwd())
    print("  FLYBRAIN_HOME    : %s" % (os.environ.get("FLYBRAIN_HOME") or "(unset)"))
    print("  toolkit root     : %s  %s" % (ROOT, "[ok]" if ok else "[MISSING]"))
    print("  toolkit dir      : %s" % MCP_DIR)
    print("  motif snapshot   : %s  %s"
          % (snap, "[ok, %d bytes]" % snap.stat().st_size if snap.exists() else "[MISSING]"))
    print("  data dir         : %s  %s" % (data or "(unset)", "[ok]" if data and Path(data).exists() else "[missing]"))
    print("  api key          : %s" % ("set" if (os.environ.get("FLYBRAIN_API_KEY")
          or (MCP_PKG / "config.json").exists()) else "not configured"))
    if ok:
        try:
            _add_paths()
            from server import TOOLS  # noqa: WPS433
            print("  tools exposed    : %d" % len(TOOLS))
        except Exception as e:  # noqa: BLE001
            print("  tools exposed    : (could not load: %s)" % e)
    else:
        print("\nToolkit missing — set FLYBRAIN_HOME or run from inside a checkout.")
        return 2
    return 0


# ---------------------------------------------------------------------- #
# argument parser
# ---------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="flybrain",
        description="flybrain-connectome developer CLI "
                    "(connectome service + traceable synthetic bio-topologies).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="start the HTTP API server")
    s.add_argument("--host", default=None, help="bind host (default 127.0.0.1)")
    s.add_argument("--port", type=int, default=None, help="bind port (default 8799)")
    s.add_argument("--api-key", default=None, help="override FLYBRAIN_API_KEY")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("query", help="call a connectome tool over HTTP")
    s.add_argument("tool", help="tool name, e.g. pair_synapses")
    s.add_argument("--args", default=None,
                   help='JSON object of tool args, e.g. \'{"pre":10540,"post":12569}\'')
    s.add_argument("--base-url", default=None, help="service base url")
    s.add_argument("--api-key", default=None, help="override FLYBRAIN_API_KEY")
    s.set_defaults(func=cmd_query)

    s = sub.add_parser("motifs", help="export / pull derived motifs")
    s.add_argument("--out", default=None, help="write motif doc to this file")
    s.add_argument("--refresh", action="store_true",
                   help="ask the service to re-extract motifs first")
    s.add_argument("--base-url", default=None, help="service base url")
    s.add_argument("--api-key", default=None, help="override FLYBRAIN_API_KEY")
    s.set_defaults(func=cmd_motifs)

    s = sub.add_parser("generate", help="compose a synthetic bio-topology")
    s.add_argument("rest", nargs=argparse.REMAINDER,
                   help="arguments passed through to synthetic_bio_topology "
                        "(run `flybrain generate --help` to see them)")
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("stages",
                       help="print the C. elegans L1/L2/L3/adult measurements")
    s.add_argument("--unit", action="append", default=None,
                   help="show only this unit (repeatable)")
    s.add_argument("--caveat", action="store_true",
                   help="print the coverage caveat before the tables")
    s.set_defaults(func=cmd_stages)

    s = sub.add_parser("larva-clusters",
                       help="larva connectome cluster ledger + unit coverage")
    s.add_argument("--unit", action="append", default=None,
                   help="show only this unit (repeatable)")
    s.add_argument("--top", type=int, default=10,
                   help="show this many clusters (default 10)")
    s.add_argument("--unannotated", action="store_true",
                   help="print only clusters that hold unannotated cells")
    s.add_argument("--caveat", action="store_true",
                   help="print the coverage caveat before the tables")
    s.set_defaults(func=cmd_larva_clusters)

    s = sub.add_parser("dimorphism",
                       help="MaleCNS male-specific / dimorphic population ledger")
    s.add_argument("--unit", action="append", default=None,
                   help="name the unit whose provenance block to show")
    s.add_argument("--top", type=int, default=10,
                   help="show this many types (default 10)")
    s.add_argument("--internal", action="store_true",
                   help="also print the both-endpoints-dimorphic type pairs")
    s.add_argument("--provenance", action="store_true",
                   help="print the curator note and trace grade behind each type")
    s.add_argument("--caveat", action="store_true",
                   help="print the ledger caveats first")
    s.set_defaults(func=cmd_dimorphism)

    s = sub.add_parser("function",
                       help="function-axis coverage against PROJECT_VISION")
    s.add_argument("--vision", action="store_true",
                   help="only the categories PROJECT_VISION requires")
    s.add_argument("--caveat", action="store_true",
                   help="print the coverage caveats first")
    s.set_defaults(func=cmd_function)

    s = sub.add_parser("verify", help="run the end-to-end smoke test")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("info", help="report the resolved toolkit/data paths")
    s.set_defaults(func=cmd_info)
    return ap


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # `generate` is a thin pass-through to synthetic_bio_topology's own CLI.
    # Handle it before argparse so flags are forwarded verbatim (see
    # cmd_generate_raw for why REMAINDER is not used here).
    if raw and raw[0] == "generate":
        return int(cmd_generate_raw(raw[1:]))

    ap = build_parser()
    args, unknown = ap.parse_known_args(raw)
    if unknown:
        ap.error("unrecognized arguments: %s" % " ".join(unknown))
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
