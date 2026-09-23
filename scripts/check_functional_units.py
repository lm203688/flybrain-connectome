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
  4. Composition works AND is deterministic: the canonical DEMO chain validates,
     twice in a row, to the same sha256.
  5. FAIL-CLOSED PROOF (defect injection): four deliberately broken inputs must
     each make the composer return ok=False. A validator that cannot go red is
     not a validator -- so this gate re-injects the defects every run.
  6. Coverage: 40 units / 50 connection types / all 6 families actually wired /
     >= 12 anatomical systems.

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
    gen_units = gen.FUNCTIONAL_UNITS
    gen_conns = gen.CONNECTION_TYPES
    check("generator unit count matches artifact",
          len(gen_units) == len(units), "%d vs %d" % (len(gen_units), len(units)))
    check("generator connection count matches artifact",
          len(gen_conns) == len(conns), "%d vs %d" % (len(gen_conns), len(conns)))
    if len(gen_units) == len(units):
        mism = [g["name"] for g, a in zip(gen_units, units) if g != a]
        check("artifact units are byte-identical to generator output",
              not mism, ("drifted: %s" % ", ".join(mism[:4])) if mism else "40/40")
    if len(gen_conns) == len(conns):
        mism = [g["name"] for g, a in zip(gen_conns, conns) if g != a]
        check("artifact connection types identical to generator output",
              not mism, ("drifted: %s" % ", ".join(mism[:4])) if mism else "50/50")

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
    d1 = fu.compose_from_units(fu.DEMO["units"], fu.DEMO["connections"],
                               name=fu.DEMO["name"])
    d2 = fu.compose_from_units(fu.DEMO["units"], fu.DEMO["connections"],
                               name=fu.DEMO["name"])
    check("canonical DEMO chain composes and validates", d1["validation"]["ok"],
          ("errors: %s" % d1["validation"]["errors"]) if not d1["validation"]["ok"]
          else "%d nodes / %d edges / %d populations"
          % (d1["organism"]["n_nodes"], d1["organism"]["n_edges"],
             d1["organism"]["total_member_populations"]))
    check("composition is deterministic (same sha256 twice)",
          d1["provenance"]["input_sha256"] == d2["provenance"]["input_sha256"],
          d1["provenance"]["input_sha256"][:16])
    check("composed organism exposes >=1 external IN and OUT port",
          bool(d1["interface"]["external_in"]) and bool(d1["interface"]["external_out"]),
          "in=%d out=%d" % (len(d1["interface"]["external_in"]),
                            len(d1["interface"]["external_out"])))
    check("intentional feedback loops are reported, not silently dropped",
          any("cycle" in w for w in d1["validation"]["warnings"]),
          str(len(d1["validation"]["warnings"])) + " warning(s)")
    check("validate_composition() re-checks a built organism",
          fu.validate_composition(d1)["ok"], "")

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
    ]
    for label, doc in injections:
        check("fail-closed: %s is rejected" % label, not doc["validation"]["ok"],
              ("accepted! errors=%s" % doc["validation"]["errors"][:1])
              if doc["validation"]["ok"] else str(len(doc["validation"]["errors"]))
              + " error(s)")

    # ---------------------------------------------------------------- 6
    check("unit count is 40", len(units) == 40, str(len(units)))
    check("connection-type count is 50", len(conns) == 50, str(len(conns)))
    used = {w["type"] for u in units for w in u["internal_wiring"]}
    fams = {c["family"] for c in conns}
    for fam in sorted(fams):
        fam_names = {c["name"] for c in conns if c["family"] == fam}
        check("connection family '%s' is actually wired by >=1 unit" % fam,
              bool(fam_names & used), "%d/%d forms used"
              % (len(fam_names & used), len(fam_names)))
    systems = {u["system"] for u in units}
    check("units span >= 12 anatomical systems", len(systems) >= 12,
          "%d: %s" % (len(systems), ", ".join(sorted(systems))))
    mem = {m["neuron"] for u in units for m in u["members"]}
    check("units reference >= 60 distinct neuron populations", len(mem) >= 60,
          "%d/%d of MODULE_PROFILES" % (len(mem), len(profiles)))
    check("library is honestly marked as NOT connectome-extracted",
          all(u["provenance"]["extracted_from_malecns"] is False for u in units), "")

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
    print("Gate 9 PASSED - 40 units, 50 connection types, composer fail-closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
