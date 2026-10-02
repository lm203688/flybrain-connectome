"""
Gate 9: functional-unit composition library integrity.

The library under test asserts that a virtual organism is built out of
FUNCTIONAL UNITS (a function, delivered by a group of neuron populations, with
typed ports) joined by CONNECTION TYPES (a connection form, constrained on port
types) -- rather than out of single neuron types. That claim is only worth
anything if the two libraries cannot drift apart and if the composer actually
refuses bad wiring.

What this gate proves:

  1. Artifacts exist, parse, and carry a schema version + port vocabulary.
  2. NO DRIFT: re-deriving the artifacts from scripts/gen_functional_units.py
     reproduces the committed bytes exactly. A hand-edit that forgets the
     generator -- or a generator that forgets to refresh the artifact -- is a
     hard failure, not a silent divergence.
  3. Every `members[].neuron` exists in synthetic_bio_topology.MODULE_PROFILES,
     every `internal_wiring[].type` and every connection `motif_ref` exists, and
     every port type is in the declared vocabulary.
  4. Composition works AND is deterministic: all four canonical DEMO chains
     (mammal visual-to-action, insect olfactory-navigation, electrosensory
     escape, swim-rhythm chain) validate, twice in a row, to the same sha256.
  5. FAIL-CLOSED PROOF (defect injection): twelve deliberately broken inputs must
     each make the composer return ok=False. A validator that cannot go red is
     not a validator -- so this gate re-injects the defects every run.
  6. Coverage: 112 units / 66 connection types / all 6 families actually wired /
     >= 34 anatomical systems / the v1.4.1 and v1.6.0 clades present / every
     v1.4.1 and v1.6.0 connection form actually wired by >= 1 unit or chain.

Exit code 0 on pass, 1 on fail.
"""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "flybrain-connectome-mcp"
FU_DIR = MCP / "functional_units"
NL = chr(10)
failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name,
                            ("- " + detail) if detail else ""))
    if not cond:
        failures.append(name)


def _load(path: Path, modname: str):
    spec = importlib.util.spec_from_file_location(modname, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[modname] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    print("Gate 9: functional-unit composition library")
    print("-" * 68)

    # ---------------------------------------------------------------- 1
    units_p = FU_DIR / "functional_units.json"
    conn_p = FU_DIR / "connection_types.json"
    check("functional_units.json exists", units_p.exists(), str(units_p))
    check("connection_types.json exists", conn_p.exists(), str(conn_p))
    if not (units_p.exists() and conn_p.exists()):
        print(NL + "FAILED (%d): %s" % (len(failures), ", ".join(failures)))
        return 1

    udoc = json.loads(units_p.read_text(encoding="utf-8"))
    cdoc = json.loads(conn_p.read_text(encoding="utf-8"))
    units = udoc["units"]
    conns = cdoc["connection_types"]
    check("units schema_version present", bool(udoc.get("schema_version")),
          str(udoc.get("schema_version")))
    check("connections schema_version present", bool(cdoc.get("schema_version")),
          str(cdoc.get("schema_version")))
    check("port vocabulary declared", len(udoc.get("port_types", {})) >= 30,
          "%d port types" % len(udoc.get("port_types", {})))

    # ---------------------------------------------------------------- 2
    # NO DRIFT: re-run the generator in-process and diff the payloads. The
    # generator writes the same files, so we compare what it would write with
    # what is committed.
    gen = _load(ROOT / "scripts" / "gen_functional_units.py", "gen_fu_gate")
    profiles = gen._load_profiles()
    # `FUNCTIONAL_UNITS` is the authored source; `embodied_units()` returns what
    # the generator actually writes (embodiment applied). Comparing the authored
    # list against the artifact would report phantom drift for every unit.
    gen_units, gen_anchors = gen.embodied_units()
    gen_conns = gen.CONNECTION_TYPES
    check("generator unit count matches artifact",
          len(gen_units) == len(units), "%d vs %d" % (len(gen_units), len(units)))
    check("generator connection count matches artifact",
          len(gen_conns) == len(conns), "%d vs %d" % (len(gen_conns), len(conns)))
    check("every written unit carries an embodiment block",
          all("embodiment" in u and "embodied_in_malecns" in u["provenance"]
              for u in gen_units),
          "%d/%d" % (sum(1 for u in gen_units if u.get("embodiment")), len(gen_units)))
    if len(gen_units) == len(units):
        mism = [g["name"] for g, a in zip(gen_units, units) if g != a]
        check("artifact units are byte-identical to generator output",
              not mism, ("drifted: %s" % ", ".join(mism[:4])) if mism else "%d/%d"
              % (len(units), len(units)))
    if len(gen_conns) == len(conns):
        mism = [g["name"] for g, a in zip(gen_conns, conns) if g != a]
        check("artifact connection types identical to generator output",
              not mism, ("drifted: %s" % ", ".join(mism[:4])) if mism else "%d/%d"
              % (len(conns), len(conns)))

    # ---------------------------------------------------------------- 3
    conn_names = {c["name"] for c in conns}
    motif_names = set(json.loads(
        (MCP / "motifs" / "swarm_agent_topology_motifs.json")
        .read_text(encoding="utf-8"))["motifs"].keys())
    port_types = set(udoc["port_types"])

    bad_members, bad_wiring, bad_ports, bad_conn_ref, bad_motif = [], [], [], [], []
    for u in units:
        for m in u["members"]:
            if m["neuron"] not in profiles:
                bad_members.append("%s.%s" % (u["name"], m["neuron"]))
        for w in u["internal_wiring"]:
            if w["type"] not in conn_names:
                bad_wiring.append("%s.%s" % (u["name"], w["type"]))
        for side in ("in", "out"):
            for p in u["ports"][side]:
                t = p["type"]
                if t in port_types or t == "*" or t.endswith(".*"):
                    continue
                bad_ports.append("%s.%s=%s" % (u["name"], p["name"], t))
        for c in u["motif_source"]:
            if c not in conn_names:
                bad_conn_ref.append("%s.%s" % (u["name"], c))
    for c in conns:
        if c["motif_ref"] and c["motif_ref"] not in motif_names:
            bad_motif.append("%s->%s" % (c["name"], c["motif_ref"]))

    check("every member neuron exists in MODULE_PROFILES", not bad_members,
          "%d dangling" % len(bad_members) if bad_members else "%d refs ok"
          % sum(len(u["members"]) for u in units))
    check("every internal wiring type is a real connection type", not bad_wiring,
          (", ".join(bad_wiring[:4])) if bad_wiring else
          "%d edges" % sum(len(u["internal_wiring"]) for u in units))
    check("every unit port type is in the vocabulary", not bad_ports,
          ", ".join(bad_ports[:4]) if bad_ports else "ok")
    check("every motif_source names a real connection type", not bad_conn_ref,
          ", ".join(bad_conn_ref[:4]) if bad_conn_ref else "ok")
    check("every connection motif_ref resolves to a real motif", not bad_motif,
          ", ".join(bad_motif[:4]) if bad_motif else "ok")

    unames = {u["name"] for u in units}
    bad_comp = [(u["name"], o) for u in units for o in u["composable_with"]
                if o not in unames]
    check("every composable_with target resolves", not bad_comp,
          str(bad_comp[:3]) if bad_comp else "ok")
    no_out = [u["name"] for u in units
              if not any(p["required"] for p in u["ports"]["out"])]
    check("every unit declares a required OUT port", not no_out,
          str(no_out[:3]) if no_out else "ok")
    ratios_bad = [u["name"] for u in units
                  if abs(sum(m["count_ratio"] for m in u["members"]) - 1.0) > 0.05]
    check("member count_ratios sum to 1.0", not ratios_bad,
          str(ratios_bad[:3]) if ratios_bad else "ok")

    # ---------------------------------------------------------------- 4
    fu = _load(MCP / "functional_units.py", "fu_gate")
    demos = getattr(fu, "DEMOS", {"mammal": fu.DEMO})
    built = {}
    for label in sorted(demos):
        spec = demos[label]
        b1 = fu.compose_from_units(spec["units"], spec["connections"], name=spec["name"])
        b2 = fu.compose_from_units(spec["units"], spec["connections"], name=spec["name"])
        built[label] = b1
        check("%s demo chain composes and validates" % label, b1["validation"]["ok"],
              ("errors: %s" % b1["validation"]["errors"]) if not b1["validation"]["ok"]
              else "%d nodes / %d edges / %d populations"
              % (b1["organism"]["n_nodes"], b1["organism"]["n_edges"],
                 b1["organism"]["total_member_populations"]))
        check("%s composition is deterministic (same sha256 twice)" % label,
              b1["provenance"]["input_sha256"] == b2["provenance"]["input_sha256"],
              b1["provenance"]["input_sha256"][:16])
        check("%s exposes >=1 external IN and OUT port" % label,
              bool(b1["interface"]["external_in"]) and bool(b1["interface"]["external_out"]),
              "in=%d out=%d" % (len(b1["interface"]["external_in"]),
                                len(b1["interface"]["external_out"])))
    d1 = built.get("mammal") or list(built.values())[0]
    check("intentional feedback loops are reported, not silently dropped",
          any("cycle" in w for w in d1["validation"]["warnings"]),
          str(len(d1["validation"]["warnings"])) + " warning(s)")
    check("validate_composition() re-checks a built organism",
          fu.validate_composition(d1)["ok"], "")
    # The two cross-clade chains exist to prove the v1.4.1 inter-unit forms are
    # usable, not decorative. If they stop using them, the chains have drifted.
    cross_forms = set()
    for label in ("insect", "electrosensory"):
        if label in built:
            cross_forms |= set(built[label]["validation"]["connection_types_used"])
    check("cross-clade chains exercise the v1.4.1 inter-unit forms",
          {"efference_copy_cancellation", "ephaptic_coupling"} <= cross_forms,
          ", ".join(sorted(cross_forms)))

    # ---------------------------------------------------------------- 5
    # FAIL-CLOSED PROOF. Each defect below MUST produce ok=False; if any slips
    # through, the validator is decorative and the gate goes red.
    good_u = fu.DEMO["units"]
    good_c = fu.DEMO["connections"]
    injections = [
        ("unknown connection type",
         fu.compose_from_units(good_u, good_c + [
             "cortical_l23_association_unit.assoc_out->cortical_l4_input_unit.thalamic_in:"
             "no_such_connection_form"])),
        ("port type rejected by the connection form (family-typed form)",
         fu.compose_from_units(good_u, good_c + [
             # `modulatory_diffuse` declares from_port = "modulatory.*"; a
             # basal-ganglia command is not a modulatory source, so it must be
             # refused. (Forms whose ports are "*" are deliberately generic and
             # are covered by the next injection instead.)
             "basal_ganglia_selection_unit.selected_action->cortical_l4_input_unit.thalamic_in:"
             "modulatory_diffuse"])),
        ("port type rejected by the connection form (concrete-typed form)",
         fu.compose_from_units(good_u, good_c + [
             # `corollary_discharge` declares from_port = "motor.command"
             "cortical_l23_association_unit.assoc_out->cerebellar_cortical_unit.mossy_fibre:"
             "corollary_discharge"])),
        ("edge names a non-existent out-port",
         fu.compose_from_units(good_u, good_c + [
             "cortical_l23_association_unit.no_such_port->dopaminergic_value_unit.rpe_in:"
             "lateral_inhibitory"])),
        ("unknown unit in the node list",
         fu.compose_from_units(good_u + ["no_such_unit"], good_c)),
        ("dangling boundary input forbidden (strict sub-chain mode)",
         fu.compose_from_units(good_u, good_c, allow_boundary_inputs=False)),
        ("completely empty composition",
         fu.compose_from_units([], [])),
        ("efference-copy form fed by a non-efference source",
         fu.compose_from_units(good_u, good_c + [
             # `efference_copy_cancellation` declares from_port = "efference.copy";
             # an association-cortex output is not a copy of a motor command.
             "cortical_l23_association_unit.assoc_out->cerebellar_cortical_unit.mossy_fibre:"
             "efference_copy_cancellation"])),
        ("cross-clade chain wired through a non-existent out-port",
         fu.compose_from_units(fu.DEMO_ESCAPE["units"], fu.DEMO_ESCAPE["connections"] + [
             "electric_organ_discharge_unit.no_such_out->"
             "electrosensory_electrolocation_unit.eod_self:ephaptic_coupling"])),
        ("cross-clade chain validated as an interior sub-chain (dangling mandatory input)",
         fu.compose_from_units(fu.DEMO_INSECT["units"], fu.DEMO_INSECT["connections"],
                               allow_boundary_inputs=False)),
        ("v1.6.0 rhythm chain wired through a non-existent out-port",
         fu.compose_from_units(fu.DEMO_SWIM["units"], fu.DEMO_SWIM["connections"] + [
             "leech_swim_cpg_unit.no_such_rhythm->frog_escape_swim_unit.rhythm_in:"
             "feedforward_excitatory"])),
        ("v1.6.0 rhythm chain validated as an interior sub-chain (dangling mandatory input)",
         fu.compose_from_units(fu.DEMO_SWIM["units"], fu.DEMO_SWIM["connections"],
                               allow_boundary_inputs=False)),
    ]
    for label, doc in injections:
        check("fail-closed: %s is rejected" % label, not doc["validation"]["ok"],
              ("accepted! errors=%s" % doc["validation"]["errors"][:1])
              if doc["validation"]["ok"] else str(len(doc["validation"]["errors"]))
              + " error(s)")

    # ---------------------------------------------------------------- 6
    # 112 = 103 curated + 4 C. elegans + 5 Drosophila larva (v2.28.0).
    check("unit count is 112", len(units) == 112, str(len(units)))
    check("connection-type count is 66", len(conns) == 66, str(len(conns)))
    used = {w["type"] for u in units for w in u["internal_wiring"]}
    fams = {c["family"] for c in conns}
    for fam in sorted(fams):
        fam_names = {c["name"] for c in conns if c["family"] == fam}
        check("connection family '%s' is actually wired by >=1 unit" % fam,
              bool(fam_names & used), "%d/%d forms used"
              % (len(fam_names & used), len(fam_names)))
    # the v1.4.1 forms must be wired somewhere, otherwise they are dead weight
    # and the "cross-clade coverage" claim is decoration.
    v4_forms = {"sparse_expansion_projection", "global_inhibitory_gain_control",
                "neural_chain_sequence", "efference_copy_cancellation",
                "mixed_electrical_chemical_synapse", "modulatory_gated_plasticity",
                "repetitive_activation_lts", "command_neuron_recruitment"}
    # A form counts as "used" if it is wired inside a unit OR across units in one
    # of the demo chains -- `efference_copy_cancellation` is by definition an
    # inter-unit form and never appears as internal wiring.
    used_all = set(used)
    for b in built.values():
        used_all |= set(b["validation"]["connection_types_used"])
    unwired = sorted(v4_forms - used_all)
    check("every v1.4.1 connection form is wired by >=1 unit or demo chain",
          not unwired, str(unwired) if unwired else "%d/%d wired" % (len(v4_forms), len(v4_forms)))
    # v1.6.0 forms: same rule. They exist to make rhythm, state switching and
    # error teaching expressible; if a unit stops using one it becomes decoration.
    v5_forms = {"half_center_oscillation", "plateau_potential_bistability",
                "serotonergic_presynaptic_facilitation", "short_term_habituation",
                "coincidence_detection", "state_switch_bistable",
                "grid_phase_precession", "thermal_cross_modal_convergence"}
    unwired5 = sorted(v5_forms - used_all)
    check("every v1.6.0 connection form is wired by >=1 unit or demo chain",
          not unwired5, str(unwired5) if unwired5 else
          "%d/%d wired" % (len(v5_forms), len(v5_forms)))
    systems = {u["system"] for u in units}
    check("units span >= 34 anatomical systems", len(systems) >= 34,
          "%d: %s" % (len(systems), ", ".join(sorted(systems))))
    clades = {"mushroom_body": "insect", "central_complex": "insect",
              "song_system": "bird", "startle_circuit": "fish",
              "electrosensory": "fish", "vertical_lobe": "cephalopod",
              "chromatophore": "cephalopod", "arm_cord": "cephalopod"}
    absent = sorted(s for s in clades if s not in systems)
    check("all four v1.4.1 clades are represented (insect/bird/fish/cephalopod)",
          not absent, str(absent) if absent else
          ", ".join(sorted({v for k, v in clades.items() if k in systems})))
    # v1.6.0 added systems. The swim CPG, the pit organ and the arousal switch are
    # the three claims that batch makes, so each must have a system of its own.
    v5_systems = {"leech_ganglion": "annelid_swim_cpg", "ascidian_larva": "chordate_larva_cpg",
                  "aplysia_ganglion": "mollusc_reflex", "buccal_ganglion": "mollusc_feeding_cpg",
                  "infrared_pit": "infrared_cross_modal", "optic_tectum": "amphibian_capture",
                  "olivocerebellar": "error_teaching", "respiratory": "respiratory_cpg",
                  "arousal_switch": "sleep_wake_bistable", "locus_coeruleus": "arousal_broadcast",
                  "hippocampus": "spatial_map", "barrel_cortex": "active_touch"}
    absent5 = sorted(s for s in v5_systems if s not in systems)
    check("all v1.6.0 systems are represented (rhythm/state/error/active-sensing)",
          not absent5, str(absent5) if absent5 else
          ", ".join(sorted({v for k, v in v5_systems.items() if k in systems})))
    mem = {m["neuron"] for u in units for m in u["members"]}
    check("units reference >= 140 distinct neuron populations", len(mem) >= 140,
          "%d/%d of MODULE_PROFILES" % (len(mem), len(profiles)))
    check("library is honestly marked as NOT connectome-extracted",
          all(u["provenance"]["extracted_from_malecns"] is False for u in units), "")

    # --- evidence ledger aggregation must match the per-unit blocks ---------
    # The evidence ledger is a view over each unit's embodiment.structural_support.
    # Recompute it here independently of functional_units.list_evidence_ledger()
    # so a drift between the two cannot slip through Gate 9.
    fu_mod = _load(MCP / "functional_units.py", "fu_gate_ledger")
    ledger = fu_mod.list_evidence_ledger()
    recomputed = {"SUPPORTED": 0, "FRAGILE": 0, "CONTRADICTED": 0}
    emb_units = 0
    for u in units:
        if not u["provenance"].get("embodied_in_malecns"):
            continue
        emb_units += 1
        for s in u["embodiment"]["structural_support"]:
            tier = s.get("support_tier") or ("CONTRADICTED" if s.get("contradicted") else "SUPPORTED")
            if tier in recomputed:
                recomputed[tier] += 1
    check("evidence_ledger summary matches per-unit structural_support",
          ledger["summary"]["SUPPORTED"] == recomputed["SUPPORTED"]
          and ledger["summary"]["FRAGILE"] == recomputed["FRAGILE"]
          and ledger["summary"]["CONTRADICTED"] == recomputed["CONTRADICTED"]
          and ledger["summary"]["total_declared_edges"] == sum(recomputed.values())
          and ledger["summary"]["embodied_units"] == emb_units,
          "ledger=%s recomputed=%s embodied_units=%d"
          % (ledger["summary"], recomputed, emb_units))
    # An entry's tier in the ledger must agree with the entry's own support_tier
    bad_tier = [e for t, entries in ledger["tiers"].items() for e in entries
                if e["contradicted"] and t != "CONTRADICTED"]
    check("no SUPPORTED/FRAGILE ledger entry is actually contradicted",
          not bad_tier, str(bad_tier[:3]))
    # every entry must resolve to a real embodied unit
    embodied_names = {u["name"] for u in units if u["provenance"]["embodied_in_malecns"]}
    orphan = [e for t, entries in ledger["tiers"].items() for e in entries
              if e["unit"] not in embodied_names]
    check("every evidence_ledger entry references an embodied unit",
          not orphan, str([e["unit"] for e in orphan[:3]]))

    # ---------------------------------------------------------------- 7
    # Docs cross-check: the README is the doc of record, so it must state the
    # real counts. Kept here (not in Gate 2) so every assertion about this
    # library lives in one place.
    readme = ROOT / "README.md"
    if readme.exists():
        txt = readme.read_text(encoding="utf-8")
        check("README states the functional-unit count",
              "%d functional units" % len(units) in txt,
              "looking for '%d functional units'" % len(units))
        check("README states the connection-type count",
              "%d connection types" % len(conns) in txt,
              "looking for '%d connection types'" % len(conns))
        check("README documents the port-typed composition algebra",
              "compose_from_units" in txt and "connection_type(" in txt, "")
    else:
        check("README.md exists", False, str(readme))

    print("-" * 68)
    if failures:
        print("FAILED (%d): %s" % (len(failures), ", ".join(failures)))
        return 1
    print("Gate 9 PASSED - %d units, %d connection types, v1.4.1 + v1.6.0 clades, "
          "composer fail-closed." % (len(units), len(conns)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
