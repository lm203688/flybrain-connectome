"""capability_quantification.py -- honest capability quantification & amplification.

P0-1 of the 2026-11-02 task brief (FlyBrain): prove "compose 2 modules > 1 module
at some function".  This module provides a *quantifiable, non-trivial* framework
so the claim is measurable rather than asserted.

WHAT "FUNCTION" MEANS HERE (deliberately narrow and honest)
-----------------------------------------------------------
We do NOT claim biological fidelity.  We quantify a *structural functional
capacity* on the composed organism graph:

  F(organism) = the set of (external-input-capability, external-output-capability)
                pairs that are *reachable* through the wiring.

A pair (in_cap, out_cap) is reachable iff there is a directed path from a unit
that exposes an unbound (external) IN port carrying `in_cap`, to a unit that
exposes an unbound (external) OUT port carrying `out_cap`.  This is the
"signal can flow from a sensory interface to a motor interface" property —
the minimal definition of a *usable* organism, and the minimal definition of
"one module does something useful".

WHY THIS IS NON-TRIVIAL (the honest part)
-----------------------------------------
A single unit cannot form a sensory→motor closed loop unless it BOTH exposes an
external sensory IN port AND an external motor OUT port AND is internally
wired.  For the canonical units we use, a sensory unit (retinal phototransduction)
has an external IN but NO motor OUT; a motor unit (efferent command bus) has a
motor OUT but NO sensory IN.  Neither alone forms the loop.  The composed
pair DOES.  So "compose 2 modules > 1 module" is demonstrated by an *emergent*
capacity (the loop), not by the trivial "more nodes => more capabilities".

Honest limits (stated, not hidden):
- This quantifies *reachability of capability pairs*, NOT dynamic computation.
  We do not claim the loop actually computes anything — that is Phase E (needs
  a runtime and a task).  Here we only prove the *wiring supports* the pair.
- The "capability" of a port is read from the unit's port TYPE, not from free
  text.  Port types are the library's own typed interface (sensory.visual,
  motor.command, ...).  This keeps the quantification structural and stable.
- No threshold is invented; the metric is the reachable-pair set itself.

Public API
----------
    load_library()                          -> (units, connection_types)
    unit_port_capabilities(unit)            -> {'in': [...], 'out': [...]}
    reachable_pairs(composed_doc)           -> set of (in_cap, out_cap)
    functional_capacity(composed_doc)       -> int (len of reachable_pairs)
    amplification_report(composed_doc, baselines) -> dict (vs each baseline)
    minimal_amplification_example()         -> dict (the canonical P0-1 demo)

CLI
---
    python capability_quantification.py --demo
    python capability_quantification.py --amplify
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


# --------------------------------------------------------------------- #
# Library loading (stdlib only)
# --------------------------------------------------------------------- #
def load_library() -> tuple[dict, dict]:
    """Return (units_doc, connection_types_doc)."""
    from functional_units import load_units, load_connection_types  # local import
    return load_units(), load_connection_types()


def unit_port_capabilities(unit: dict) -> dict:
    """Extract the typed port capabilities of one unit.

    Returns {'in': [port_type,...], 'out': [port_type,...]} using the unit's
    declared port types (the library's own typed interface).
    """
    ports = unit.get("ports", {})
    return {
        "in": sorted({p.get("type", "?") for p in ports.get("in", [])}),
        "out": sorted({p.get("type", "?") for p in ports.get("out", [])}),
    }


def _graph(composed_doc: dict) -> tuple[dict, dict, list, list, dict]:
    """Return (nodes_by_id, adj, external_in, external_out, unit_index).

    Port types are NOT stored on the composed node (nodes carry `unit` refs
    only); they live in the unit library.  We resolve each node's unit to its
    port types here so reachable_pairs can use the typed interface.
    """
    organism = composed_doc.get("organism", {})
    nodes = {n["id"]: n for n in organism.get("nodes", [])}
    # Resolve unit port types from the library.
    units_doc, _ = load_library()
    unit_index = {u["name"]: u for u in units_doc.get("units", [])}
    for nid, n in nodes.items():
        u = unit_index.get(n.get("unit"))
        n["_port_types_in"] = sorted({p.get("type", "?") for p in u.get("ports", {}).get("in", [])}) if u else []
        n["_port_types_out"] = sorted({p.get("type", "?") for p in u.get("ports", {}).get("out", [])}) if u else []
    adj: dict[str, set[str]] = {}
    for e in organism.get("edges", []):
        adj.setdefault(e["from"], set()).add(e["to"])
    ext_in = composed_doc.get("interface", {}).get("external_in", [])
    ext_out = composed_doc.get("interface", {}).get("external_out", [])
    return nodes, adj, ext_in, ext_out, unit_index


def reachable_pairs(composed_doc: dict) -> set[tuple[str, str]]:
    """Set of (in_port_type, out_port_type) pairs reachable through wiring.

    A pair is reachable iff a unit with an unbound (external) IN port of type
    `in_cap` can reach a unit with an unbound (external) OUT port of type
    `out_cap` via directed edges.
    """
    nodes, adj, ext_in, ext_out, unit_index = _graph(composed_doc)

    def _port_type(uid: str, port_name: str, direction: str) -> str:
        """Resolve a port's TYPE from the unit library (ports are named on the
        interface, but the cross-domain semantic axis is the port TYPE)."""
        node = nodes.get(uid, {})
        unit_name = node.get("unit")
        u = unit_index.get(unit_name) if unit_name else None
        if not u:
            return port_name
        for p in u.get("ports", {}).get(direction, []):
            if p.get("name") == port_name:
                return p.get("type", port_name)
        return port_name

    # Map each external IN port to its unit's port TYPE.
    in_pairs: list[tuple[str, str]] = []  # (unit_id, port_type)
    for ep in ext_in:
        uid = ep["unit"]
        if uid in nodes:
            in_pairs.append((uid, _port_type(uid, ep["port"], "in")))

    out_pairs: list[tuple[str, str]] = []  # (unit_id, port_type)
    for ep in ext_out:
        uid = ep["unit"]
        if uid in nodes:
            out_pairs.append((uid, _port_type(uid, ep["port"], "out")))

    # Forward reachability from each external IN unit.
    result: set[tuple[str, str]] = set()
    for src_uid, in_cap in in_pairs:
        seen = {src_uid}
        q = deque([src_uid])
        while q:
            n = q.popleft()
            for m in adj.get(n, set()):
                if m not in seen:
                    seen.add(m)
                    q.append(m)
        for dst_uid, out_cap in out_pairs:
            if dst_uid in seen:
                result.add((in_cap, out_cap))
    return result


def functional_capacity(composed_doc: dict) -> int:
    """Number of reachable (in, out) capability pairs — the quantified metric."""
    return len(reachable_pairs(composed_doc))


# --------------------------------------------------------------------- #
# Amplification analysis
# --------------------------------------------------------------------- #
def amplification_report(composed_doc: dict, baselines: list[dict]) -> dict:
    """Compare a composed organism against each single-module baseline.

    A baseline is a composed_doc built from ONE unit (or any reference).  The
    report states, for each baseline, whether the composition *adds* a
    reachable capability pair the baseline does not have (emergent capacity),
    and whether it *loses* one (regression).

    AMPLIFICATION = emergent CROSS-DOMAIN closed loop.  A cross-domain loop is a
    reachable (in_cap, out_cap) pair where in_cap is a SENSORY input and out_cap
    is a MOTOR output.  This is the semantically meaningful "perceive -> act"
    capability the project's organism abstraction is about.  A single sensory
    unit cannot reach a motor output (it has none); a single motor unit cannot
    reach a sensory input (it has none).  Only the composition wires them.
    """
    combo_pairs = reachable_pairs(composed_doc)

    def cross_domain(pairs: set[tuple[str, str]]) -> set[tuple[str, str]]:
        return {(a, b) for (a, b) in pairs
                if a.startswith("sensory") and b.startswith("motor")}

    combo_cross = cross_domain(combo_pairs)
    report = {
        "composed": {
            "name": composed_doc.get("name"),
            "n_nodes": composed_doc.get("organism", {}).get("n_nodes", 0),
            "n_edges": composed_doc.get("organism", {}).get("n_edges", 0),
            "functional_capacity": len(combo_pairs),
            "cross_domain_pairs": len(combo_cross),
            "pairs": sorted(combo_pairs),
        },
        "baselines": [],
        "amplified": False,
        "regressed": False,
        "amplification_basis": "emergent sensory->motor closed loop",
        "notes": [],
    }
    for base in baselines:
        base_pairs = reachable_pairs(base)
        base_cross = cross_domain(base_pairs)
        added = combo_pairs - base_pairs
        lost = base_pairs - combo_pairs
        # Cross-domain pairs added by composition that the baseline lacks.
        added_cross = combo_cross - base_cross
        entry = {
            "name": base.get("name"),
            "n_nodes": base.get("organism", {}).get("n_nodes", 0),
            "n_edges": base.get("organism", {}).get("n_edges", 0),
            "functional_capacity": len(base_pairs),
            "cross_domain_pairs": len(base_cross),
            "pairs": sorted(base_pairs),
            "added_pairs": sorted(added),
            "lost_pairs": sorted(lost),
            "added_cross_domain": sorted(added_cross),
            "n_added": len(added),
            "n_lost": len(lost),
            "n_added_cross_domain": len(added_cross),
        }
        report["baselines"].append(entry)
        if added_cross:
            report["amplified"] = True
            report["notes"].append(
                "Composition adds sensory->motor capability pair(s) absent from "
                "baseline %s: %s (emergent closed loop, not merely more nodes)"
                % (base.get("name"),
                   ", ".join("%s->%s" % (a, b) for a, b in sorted(added_cross)))
            )
        if lost:
            report["regressed"] = True
            report["notes"].append(
                "Composition loses capability pair(s) present in baseline "
                "%s: %s (port-consumption: an internal port stops being an "
                "external interface once wired)"
                % (base.get("name"),
                   ", ".join("%s->%s" % (a, b) for a, b in sorted(lost)))
            )
    return report


# --------------------------------------------------------------------- #
# Canonical P0-1 example (sensory -> motor closed loop)
# --------------------------------------------------------------------- #
def minimal_amplification_example() -> dict:
    """The canonical P0-1 demo: sensory unit alone vs motor unit alone vs both.

    Returns a self-contained report showing the composed pair exceeds both
    single-module baselines on the sensory->motor capability dimension.
    """
    from functional_units import compose_from_units

    # 1. Baseline A: sensory only (no motor OUT => no closed loop)
    sensory = compose_from_units(
        [{"unit": "retinal_phototransduction_unit", "instances": 1}],
        [], name="baseline_sensory")
    # 2. Baseline B: motor only (no sensory IN => no closed loop)
    motor = compose_from_units(
        [{"unit": "efferent_command_bus_unit", "instances": 1}],
        [], name="baseline_motor")
    # 3. Composition: sensory -> motor (closed loop)
    combo = compose_from_units(
        [{"unit": "retinal_phototransduction_unit", "instances": 1},
         {"unit": "efferent_command_bus_unit", "instances": 1}],
        [{"from": "retinal_phototransduction_unit.high_res",
          "to": "efferent_command_bus_unit.cmd",
          "type": "feedforward_excitatory"}],
        name="composed_sensory_motor")

    report = amplification_report(combo, [sensory, motor])
    report["example"] = {
        "description": ("Sensory->motor closed loop: a single sensory unit has no "
                        "motor OUT; a single motor unit has no sensory IN; the "
                        "composition wires light->motor command, adding a reachable "
                        "sensory->motor capability pair neither baseline has."),
        "input": "light (sensory.visual)",
        "output": "motor command (motor.leg / motor.wing / motor.escape)",
        "wiring": "retinal_phototransduction_unit.high_res "
                  "--feedforward_excitatory--> efferent_command_bus_unit.cmd",
    }
    return report


# --------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------- #
def _cli() -> int:
    import json
    ap = argparse.ArgumentParser(description="Capability quantification (P0-1)")
    ap.add_argument("--demo", action="store_true", help="run the canonical demo")
    ap.add_argument("--amplify", action="store_true", help="amplification report")
    args = ap.parse_args()
    if args.demo or args.amplify:
        report = minimal_amplification_example()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        # Exit code reflects whether amplification was demonstrated.
        return 0 if report.get("amplified") else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
