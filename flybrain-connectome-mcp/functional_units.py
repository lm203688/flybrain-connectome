"""functional_units.py -- composition engine for the functional-unit library.

TWO LIBRARIES, ONE ALGEBRA
--------------------------
`functional_units/functional_units.json` holds 72 FUNCTIONAL UNITS. A unit is
NOT a neuron type: it is a group of one-or-more neuron populations wired into a
sub-circuit that delivers exactly one function (phototransduction, action
selection, theta pacing, ...) and that exposes typed PORTS.

`functional_units/connection_types.json` holds 66 CONNECTION TYPES. A connection
type is NOT a single synapse: it is a connection FORM (axo-somatic, mutual
inhibitory, volume transmission, corollary discharge, ...) that constrains which
port types it may join.

So the composition algebra is:

    virtual organism =  units (nodes)  +  connection types (typed edges)

and every edge is checkable, because both sides declare port types:

    unit A .out_port[type]  --connection_type(from_port,to_port)-->  unit B .in_port[type]

WHY THIS REPLACES "one module = one neuron type"
------------------------------------------------
The earlier library exposed 160 leaf entries (10 cognitive-function profiles plus
150 cross-species neuron types). A single neuron type is
not a composable unit: `pyramidal_l5` on its own does nothing, and joining two of
them means nothing. What composes is a FUNCTION with a known interface. This
module is the layer where a function becomes a node you can wire.

HONESTY CONTRACT
----------------
Units are curated from comparative-neuroscience literature, NOT extracted from
MaleCNS v1.0 — each unit carries `provenance.extracted_from_malecns = false`.
Member `count_ratio` values are composition weights, not measured cell counts.
`validate_composition()` therefore checks STRUCTURE (types, ports, reachability),
never claims biological fidelity.

Usage:
    from functional_units import (load_units, load_connection_types,
                                  list_units, get_unit, compose_from_units,
                                  validate_composition, suggest_composition)

CLI:
    python functional_units.py --list
    python functional_units.py --show thalamocortical_relay_unit
    python functional_units.py --suggest "attention"
    python functional_units.py --demo
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNITS_FILE = HERE / "functional_units" / "functional_units.json"
CONN_FILE = HERE / "functional_units" / "connection_types.json"
SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------- #
# Loading (stdlib json only -- no third-party dependency, matching the
# project-wide zero-dependency contract in pyproject.toml)
# ---------------------------------------------------------------------- #
def load_units() -> dict:
    """Return {'units': [...], 'port_types': {...}, 'stats': {...}}."""
    return json.loads(UNITS_FILE.read_text(encoding="utf-8"))


def load_connection_types() -> dict:
    return json.loads(CONN_FILE.read_text(encoding="utf-8"))


def _index_units() -> dict:
    return {u["name"]: u for u in load_units()["units"]}


def _index_conns() -> dict:
    return {c["name"]: c for c in load_connection_types()["connection_types"]}


# ---------------------------------------------------------------------- #
# Port-type matching
# ---------------------------------------------------------------------- #
def _type_ok(constraint: str, actual: str) -> bool:
    """Does a declared port `actual` satisfy a connection-type `constraint`?

    `*`            admits everything.
    `sensory.*`    admits the whole `sensory.` family.
    exact string   must match exactly.

    A unit may itself declare a family port (`sensory.*`); a concrete constraint
    into that port is accepted, because the unit is saying "I take this family".
    """
    if constraint in ("*", ""):
        return True
    if actual in ("*", ""):
        return True
    if actual.endswith(".*"):
        return constraint.startswith(actual[:-1])
    if constraint.endswith(".*"):
        return actual.startswith(constraint[:-1])
    return constraint == actual


# ---------------------------------------------------------------------- #
# Read-side API
# ---------------------------------------------------------------------- #
def list_units(system: str | None = None, capability: str | None = None) -> list:
    """Filter units by `system` (exact) and/or `capability` (substring)."""
    out = []
    for u in load_units()["units"]:
        if system and u["system"] != system:
            continue
        if capability and not any(capability in c for c in u["capability"]):
            continue
        out.append({
            "name": u["name"],
            "display": u["display"],
            "system": u["system"],
            "function": u["function"],
            "members": len(u["members"]),
            "capability": u["capability"],
            "ports_in": [p["name"] for p in u["ports"]["in"]],
            "ports_out": [p["name"] for p in u["ports"]["out"]],
        })
    return out


def get_unit(name: str) -> dict | None:
    return _index_units().get(name)


def suggest_composition(task_hint: str, limit: int = 6) -> dict:
    """Rank units by how well their task hints match a free-text hint.

    Deterministic: score = 3*lead_task_hint match + 2*hint-pool match +
    1*capability match, ties broken by unit name so repeated calls agree.
    """
    q = (task_hint or "").strip().lower()
    scored = []
    for u in load_units()["units"]:
        s = 0
        if q and q in u["lead_task_hint"].lower():
            s += 3
        if any(q and q in h.lower() for h in u["task_hint_pool"]):
            s += 2
        if any(q and q in c.lower() for c in u["capability"]):
            s += 1
        if s:
            scored.append((s, u["name"], u["system"], u["lead_task_hint"]))
    scored.sort(key=lambda t: (-t[0], t[1]))
    top = scored[:limit]
    # Deterministic starter chain: the highest-scoring unit, then anything it
    # declares itself composable with that also scored.
    picked = [t[1] for t in top]
    edges = []
    for name in picked:
        u = _index_units()[name]
        for other in u["composable_with"]:
            if other in picked:
                edges.append({"from": name, "to": other, "reason": "declared_composable"})
    return {"query": task_hint, "ranked": [
        {"score": s, "unit": n, "system": sy, "lead_task_hint": lh} for s, n, sy, lh in top
    ], "starter_edges": edges}


# ---------------------------------------------------------------------- #
# Composition
# ---------------------------------------------------------------------- #
def _norm_units(spec) -> list:
    """Accept ["a","b"] or [{"unit":"a","instances":2}]. Returns normalised list."""
    out = []
    for item in spec or []:
        if isinstance(item, str):
            out.append({"unit": item, "instances": 1})
        elif isinstance(item, dict) and "unit" in item:
            out.append({"unit": item["unit"], "instances": int(item.get("instances", 1))})
        else:
            raise ValueError("bad unit spec: %r" % (item,))
    return out


def _norm_conns(spec) -> list:
    """Accept {"from":"A.out","to":"B.in","type":"x"} or "A.out->B.in:x"."""
    out = []
    for item in spec or []:
        if isinstance(item, str):
            try:
                lhs, ctype = item.split(":", 1)
                src, dst = lhs.split("->", 1)
            except ValueError:
                raise ValueError("bad edge string %r (want 'A.out->B.in:type')" % item)
            out.append({"from": src.strip(), "to": dst.strip(), "type": ctype.strip()})
        elif isinstance(item, dict):
            out.append({"from": item["from"], "to": item["to"], "type": item["type"]})
        else:
            raise ValueError("bad edge spec: %r" % (item,))
    return out


def _split_port(ref: str) -> tuple:
    if "." not in ref:
        raise ValueError("port ref %r must be 'unit.port'" % ref)
    u, p = ref.rsplit(".", 1)
    return u.strip(), p.strip()


def compose_from_units(units, connections, name: str = "composed_organism",
                       seed: int = 42, strict_cycles: bool = False,
                       allow_boundary_inputs: bool = True) -> dict:
    """Build a virtual-organism graph from functional units + connection types.

    BOUNDARY SEMANTICS (important): an unsatisfied *required* IN port is not an
    error when it sits on the organism boundary — it IS the organism's external
    input, which is exactly what a top-level organism must expose. Pass
    `allow_boundary_inputs=False` when validating an *interior* sub-chain, where
    a dangling required input really is a wiring mistake.

    Returns a dict with: organism (nodes/edges), interface, validation and
    provenance. Never raises on a bad composition -- callers get
    `validation.ok == False` plus an `errors` list, so an agent can self-repair.
    """
    uspec = _norm_units(units)
    cspec = _norm_conns(connections)
    unit_index = _index_units()
    conn_index = _index_conns()
    errors, warnings = [], []

    # -- 1. instantiate nodes ------------------------------------------- #
    nodes, instances = [], {}
    for spec in uspec:
        u = unit_index.get(spec["unit"])
        if u is None:
            errors.append("unknown unit %r" % spec["unit"])
            continue
        for i in range(max(1, spec["instances"])):
            iid = spec["unit"] if spec["instances"] == 1 else "%s#%d" % (spec["unit"], i)
            instances[iid] = u
            lo, hi = u["size_range"]
            nodes.append({
                "id": iid,
                "unit": u["name"],
                "system": u["system"],
                "function": u["function"],
                "size_range": [lo, hi],
                "members": u["members"],
                "capability": u["capability"],
                "lead_task_hint": u["lead_task_hint"],
            })

    # -- 2. wiring, with connection-type port-constraint checking -------- #
    edges = []
    inbound = {iid: set() for iid in instances}   # satisfied required in-ports
    used_conn_types = set()
    for c in cspec:
        ctype = conn_index.get(c["type"])
        if ctype is None:
            errors.append("unknown connection type %r" % c["type"])
            continue
        try:
            su, sp = _split_port(c["from"])
            tu, tp = _split_port(c["to"])
        except ValueError as e:
            errors.append(str(e))
            continue
        if su not in instances:
            errors.append("edge source unit %r not in composition" % su)
            continue
        if tu not in instances:
            errors.append("edge target unit %r not in composition" % tu)
            continue
        sp_def = next((p for p in instances[su]["ports"]["out"] if p["name"] == sp), None)
        tp_def = next((p for p in instances[tu]["ports"]["in"] if p["name"] == tp), None)
        if sp_def is None:
            errors.append("%s has no OUT port %r" % (su, sp))
            continue
        if tp_def is None:
            errors.append("%s has no IN port %r" % (tu, tp))
            continue
        # connection type must admit both endpoint port types
        if not _type_ok(ctype["from_port"], sp_def["type"]):
            errors.append("connection %s from_port=%s rejects %s.%s (type %s)"
                          % (ctype["name"], ctype["from_port"], su, sp, sp_def["type"]))
            continue
        if not _type_ok(ctype["to_port"], tp_def["type"]):
            errors.append("connection %s to_port=%s rejects %s.%s (type %s)"
                          % (ctype["name"], ctype["to_port"], tu, tp, tp_def["type"]))
            continue
        if ctype["span"] == "intra_unit" and su != tu:
            warnings.append("connection %s is intra_unit but joins %s -> %s"
                            % (ctype["name"], su, tu))
        used_conn_types.add(ctype["name"])
        if tp_def["required"]:
            inbound[tu].add(tp)
        edges.append({
            "from": su, "from_port": sp, "to": tu, "to_port": tp,
            "type": ctype["name"], "family": ctype["family"], "sign": ctype["sign"],
            "weight": round(1.0 + 0.05 * len(edges), 4) if ctype["sign"] != "-" else -1.0,
        })

    # -- 3. required-port bookkeeping ----------------------------------- #
    # An unbound required IN port on the boundary is the organism's INPUT, not a
    # defect. We still record it per-unit so a caller validating an interior
    # sub-chain can see exactly what is dangling.
    unbound_required_in = []
    for iid, u in instances.items():
        for p in u["ports"]["in"]:
            if p["required"] and p["name"] not in inbound[iid]:
                unbound_required_in.append({"unit": iid, "port": p["name"],
                                            "type": p["type"]})
                if not allow_boundary_inputs:
                    errors.append("unit %s: required IN port %r unsatisfied "
                                  "(boundary inputs disallowed)" % (iid, p["name"]))

    # -- 4. external interface: the organism must be drivable and readable #
    external_in, external_out = [], []
    for iid, u in instances.items():
        for p in u["ports"]["in"]:
            if p["required"] and p["name"] not in inbound[iid]:
                external_in.append({"unit": iid, "port": p["name"], "type": p["type"]})
        for p in u["ports"]["out"]:
            # an out-port is "readable" if nothing consumes it
            consumed = any(e["from"] == iid and e["from_port"] == p["name"] for e in edges)
            if not consumed:
                external_out.append({"unit": iid, "port": p["name"], "type": p["type"]})
    if not external_in:
        errors.append("organism has no externally drivable required IN port")
    if not external_out:
        warnings.append("organism has no unbound OUT port (every output is consumed)")

    # -- 5. cycle policy -------------------------------------------------- #
    # A cycle is acceptable only if it is intentional (feedback loops are a
    # first-class citizen in this library), so we REPORT cycles, and only turn
    # them into errors when the caller asks for a strictly feedforward graph.
    adj = {iid: [] for iid in instances}
    for e in edges:
        adj[e["from"]].append(e["to"])
    colour, cycles = {iid: 0 for iid in instances}, []

    def _dfs(n, stack):
        colour[n] = 1
        for m in adj[n]:
            if colour.get(m, 0) == 1:
                cycles.append(stack[stack.index(m):] + [m] if m in stack else [n, m])
            elif colour.get(m, 0) == 0:
                _dfs(m, stack + [m])
        colour[n] = 2

    for iid in sorted(instances):
        if colour[iid] == 0:
            _dfs(iid, [iid])
    if cycles:
        if strict_cycles:
            for cyc in cycles:
                errors.append("cycle under strict_cycles: %s" % " -> ".join(cyc))
        else:
            warnings.append("%d feedback cycle(s) present: %s"
                            % (len(cycles), "; ".join(" -> ".join(c) for c in cycles[:3])))

    # -- 6. deterministic provenance ------------------------------------- #
    payload = json.dumps({"units": uspec, "connections": cspec, "seed": seed},
                         sort_keys=True, ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()

    return {
        "name": name,
        "schema_version": SCHEMA_VERSION,
        "organism": {
            "nodes": nodes,
            "edges": edges,
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "total_member_populations": sum(len(n["members"]) for n in nodes),
        },
        "interface": {"external_in": external_in, "external_out": external_out,
                      "unbound_required_in": unbound_required_in},
        "validation": {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "boundary_inputs_allowed": allow_boundary_inputs,
            "connection_types_used": sorted(used_conn_types),
            "families_used": sorted({c["family"] for c in
                                     load_connection_types()["connection_types"]
                                     if c["name"] in used_conn_types}),
        },
        "provenance": {
            "class": "composed-from-curated-units",
            "unit_library_schema": load_units()["schema_version"],
            "connection_library_schema": load_connection_types()["schema_version"],
            "input_sha256": digest,
            "seed": seed,
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "raw_neurons_embedded": False,
        },
    }


def validate_composition(doc: dict) -> dict:
    """Re-check an already-built organism document. Returns {ok, errors}."""
    errors = []
    for i, e in enumerate(doc.get("organism", {}).get("edges", [])):
        if not e.get("type"):
            errors.append("edge %d has no connection type" % i)
        if not e.get("from_port") or not e.get("to_port"):
            errors.append("edge %d is not port-qualified" % i)
    v = doc.get("validation", {})
    errors.extend(v.get("errors", []))
    return {"ok": not errors, "errors": errors,
            "n_nodes": doc.get("organism", {}).get("n_nodes", 0),
            "n_edges": doc.get("organism", {}).get("n_edges", 0)}


# ---------------------------------------------------------------------- #
# A canonical demo chain, used by the gate as a round-trip fixture
# ---------------------------------------------------------------------- #
DEMO = {
    "name": "demo_visual_to_action",
    "units": [
        "retinal_phototransduction_unit",
        "visual_thalamic_relay_unit",
        "cortical_l4_input_unit",
        "cortical_l23_association_unit",
        "cortical_l5_output_unit",
        "basal_ganglia_selection_unit",
        "dopaminergic_value_unit",
        "cerebellar_cortical_unit",
        "motor_thalamic_relay_unit",
    ],
    "connections": [
        # ascending sensory chain
        "retinal_phototransduction_unit.high_res->visual_thalamic_relay_unit.retina:feedforward_excitatory",
        "visual_thalamic_relay_unit.lgn_out->cortical_l4_input_unit.thalamic_in:feedforward_excitatory",
        "cortical_l4_input_unit.l4_out->cortical_l23_association_unit.l4_in:feedforward_excitatory",
        "cortical_l23_association_unit.exec_out->cortical_l5_output_unit.l23_in:feedforward_excitatory",
        # descending action chain
        "cortical_l5_output_unit.descending->basal_ganglia_selection_unit.candidates:feedforward_excitatory",
        "basal_ganglia_selection_unit.selected_action->motor_thalamic_relay_unit.basal_ganglia:feedforward_excitatory",
        # value modulation (fan-out onto the selector)
        "dopaminergic_value_unit.dopamine_out->basal_ganglia_selection_unit.value:modulatory_diffuse",
        # cerebellar coordination limb into the shared motor thalamus
        "cortical_l5_output_unit.descending->cerebellar_cortical_unit.mossy_fibre:divergent_fanout",
        "cerebellar_cortical_unit.purkinje_out->motor_thalamic_relay_unit.cerebellum:feedforward_excitatory",
        # intentional closed loop: motor thalamus returns to L5 (cycle policy test)
        "motor_thalamic_relay_unit.motor_thalamic_out->cortical_l5_output_unit.thalamic_fb:feedback_excitatory",
    ],
}

# ---------------------------------------------------------------------- #
# Two more canonical chains, one per non-mammalian clade group. They exist
# because the claim "the library composes cross-clade" is only worth
# something if the cross-clade chains actually validate end to end.
# ---------------------------------------------------------------------- #
DEMO_INSECT = {
    "name": "demo_insect_olfactory_navigation",
    "units": [
        "antennal_lobe_glomerular_unit",
        "mushroom_body_sparse_code_unit",
        "mushroom_body_associative_memory_unit",
        "central_complex_heading_unit",
        "central_complex_steering_unit",
        "insect_clock_pacemaker_unit",
    ],
    "connections": [
        # odour -> sparse mushroom-body code -> learned valence
        "antennal_lobe_glomerular_unit.pn_out->mushroom_body_sparse_code_unit.pn_in:feedforward_excitatory",
        "mushroom_body_sparse_code_unit.sparse_out->mushroom_body_associative_memory_unit.sparse_code:feedforward_excitatory",
        # learned odour value biases the steering map
        "mushroom_body_associative_memory_unit.learned_valence->central_complex_steering_unit.valence_in:divergent_fanout",
        # heading -> steering, with a feedback turn back onto the heading map
        "central_complex_heading_unit.heading_out->central_complex_steering_unit.heading_in:feedforward_excitatory",
        "central_complex_steering_unit.turn_cmd->central_complex_heading_unit.steer_in:lateral_feedback",
        # the clock biases the heading system (time-of-day dependent navigation)
        "insect_clock_pacemaker_unit.phase_out->central_complex_heading_unit.clock_in:feedforward_excitatory",
    ],
}

DEMO_ESCAPE = {
    "name": "demo_electrosensory_escape",
    "units": [
        "electric_organ_discharge_unit",
        "electrosensory_electrolocation_unit",
        "passive_electroreception_unit",
        "startle_escape_command_unit",
    ],
    "connections": [
        # the pacemaker tells the sensory side what it is about to emit
        "electric_organ_discharge_unit.eff_out->electrosensory_electrolocation_unit.eff_in:efference_copy_cancellation",
        # ...and the emitted field itself reaches the receptors (field coupling)
        "electric_organ_discharge_unit.eod_out->electrosensory_electrolocation_unit.eod_self:ephaptic_coupling",
        # a passive electric cue from prey/danger reaches the escape command
        "passive_electroreception_unit.prey_vector->startle_escape_command_unit.threat_in:feedforward_excitatory",
    ],
}

DEMO_SWIM = {
    "name": "demo_swim_rhythm_chain",
    "units": [
        "leech_swim_cpg_unit",
        "ascidian_larval_escape_swim_unit",
        "frog_escape_swim_unit",
    ],
    "connections": [
        # a leech half-centre oscillator entrains the ascidian larval oscillator
        "leech_swim_cpg_unit.swim_rhythm->ascidian_larval_escape_swim_unit.rhythm_in:feedforward_excitatory",
        # ...and the entrained rhythm gates the vertebrate escape swim
        "ascidian_larval_escape_swim_unit.swim_rhythm->frog_escape_swim_unit.rhythm_in:feedforward_excitatory",
        # the driving segmental motor output reaches the escape pool directly
        "leech_swim_cpg_unit.motor_out->frog_escape_swim_unit.swim_in:feedforward_excitatory",
    ],
}

DEMOS = {
    "mammal": DEMO,
    "insect": DEMO_INSECT,
    "electrosensory": DEMO_ESCAPE,
    "swim": DEMO_SWIM,
}


def stats() -> dict:
    u = load_units()
    c = load_connection_types()
    return {
        "functional_units": len(u["units"]),
        "connection_types": len(c["connection_types"]),
        "systems": sorted({x["system"] for x in u["units"]}),
        "families": sorted({x["family"] for x in c["connection_types"]}),
        "port_types": len(u["port_types"]),
        "schema_version": u["schema_version"],
    }


def _cli() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--system")
    ap.add_argument("--capability")
    ap.add_argument("--show", metavar="UNIT")
    ap.add_argument("--suggest", metavar="HINT")
    ap.add_argument("--connections", action="store_true")
    ap.add_argument("--demo", nargs="?", const="all", metavar="NAME",
                    help="mammal | insect | electrosensory | swim | all (default)")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()

    if a.stats:
        print(json.dumps(stats(), ensure_ascii=False, indent=2)); return 0
    if a.list:
        for u in list_units(system=a.system, capability=a.capability):
            print("%-38s %-16s %-24s %s"
                  % (u["name"], u["system"], u["function"], "/".join(u["capability"][:3])))
        return 0
    if a.connections:
        for c in load_connection_types()["connection_types"]:
            print("%-32s %-12s %-18s -> %s"
                  % (c["name"], c["family"], c["from_port"], c["to_port"]))
        return 0
    if a.show:
        u = get_unit(a.show)
        if not u:
            print("no such unit:", a.show, file=sys.stderr); return 2
        print(json.dumps(u, ensure_ascii=False, indent=2)); return 0
    if a.suggest:
        print(json.dumps(suggest_composition(a.suggest), ensure_ascii=False, indent=2))
        return 0
    if a.demo:
        names = list(DEMOS) if a.demo == "all" else [a.demo]
        built = []
        for n in names:
            if n not in DEMOS:
                print("no such demo:", n, file=sys.stderr); return 2
            spec = DEMOS[n]
            built.append(compose_from_units(spec["units"], spec["connections"],
                                             name=spec["name"]))
        print(json.dumps(built[0] if len(built) == 1 else built,
                         ensure_ascii=False, indent=2)); return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
