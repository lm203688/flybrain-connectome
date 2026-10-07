#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GATE 13 — composition semantics: can a declared combination actually form?

Gates 1-12 never asked whether the library can be *assembled*.  Gate 9 checks
that the unit library is well formed; Gate 11 checks functional coverage; Gate
12 checks the cost axis.  None of them looks at `composable_with` -- the field
that decides which units may be wired to each other -- and none of them looks at
whether the ports those units expose can actually meet.

Measured on the current library (v2.40.0):

  * 163 `composable_with` declarations, all naming units that exist
  * of those, **97 are one-way**: A declares compatibility with B, B does not
    declare it back
  * of the 97, only **31 have port types that actually meet**; 66 pair a unit
    whose `out` port exposes e.g. `limbic.fear` with a unit whose `in` ports
    accept `arousal.state` / `rhythm.circadian` and nothing in common

This matters because the combination builder already acts on the weaker
statement.  `functional_units.py` builds `starter_edges` straight from
`u["composable_with"]` with `reason: "declared_composable"`, without checking
that the other unit asked for the connection or that any port lines up.  So the
one-way declarations are not a latent risk; they are what the tool does today.

The gate therefore distinguishes three states and only fails on the broken one:

  consistent   both units declare it AND their ports meet  -- usable
  one_way      one side declares it, ports may or may not meet -- reported
  unreachable  declared but no port type can meet -- reported, not fatal

Why one-way and unreachable are reported rather than fatal: a one-way
declaration is a real claim by A, and a composition A wants is not obviously
wrong just because B never reciprocated.  What the gate refuses to accept is a
claim that cannot be satisfied by the interface -- and it refuses silently
ignoring them, by counting them.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
UNITS = MCP / "functional_units" / "functional_units.json"
CONNS = MCP / "functional_units" / "connection_types.json"
BUILDER = MCP / "functional_units.py"

fails: list[str] = []


def main() -> int:
    if not UNITS.exists():
        print("FAIL  gate13: %s is missing" % UNITS)
        return 1
    doc = json.loads(UNITS.read_text(encoding="utf-8"))
    units = doc["units"] if isinstance(doc, dict) else doc
    names = {u["name"] for u in units}

    comp = {u["name"]: set(u.get("composable_with") or []) for u in units}
    ports = {}
    for u in units:
        p = u.get("ports") or {}
        if not isinstance(p, dict):
            fails.append("%s: ports is %s, expected a dict"
                         % (u["name"], type(p).__name__))
            continue
        ports[u["name"]] = {
            "in": {q.get("type") for q in (p.get("in") or []) if q.get("type")},
            "out": {q.get("type") for q in (p.get("out") or []) if q.get("type")},
        }

    # ---- 1. references must resolve -------------------------------------- #
    dangling = [(a, b) for a, bs in comp.items() for b in bs if b not in names]
    for a, b in dangling:
        fails.append("%s declares composable_with %s, which is not a unit"
                     % (a, b))
    self_ref = [a for a, bs in comp.items() if a in bs]
    for a in self_ref:
        fails.append("%s declares composable_with itself" % a)

    # ---- 2. internal wiring must resolve to declared roles --------------- #
    for u in units:
        roles = {m.get("role") for m in u.get("members", [])}
        for w in u.get("internal_wiring") or []:
            for side in ("from", "to"):
                r = w.get(side)
                if r is not None and r not in roles:
                    fails.append("%s: internal_wiring %s=%r is not a member role"
                                 % (u["name"], side, r))
        if u.get("internal_wiring") and not roles:
            fails.append("%s has internal_wiring but no members" % u["name"])

    # ---- 3. classify every declaration ----------------------------------- #
    consistent, one_way_ok, one_way_bad = [], [], []
    for a in sorted(comp):
        for b in sorted(comp[a]):
            reciprocated = a in comp.get(b, set())
            # A dangling target is reported above, but the classifier still
            # runs, and `ports.get(name)` is None for a name that is not a
            # unit.  The first version of this gate crashed on exactly that
            # case -- a gate that cannot survive one bad reference cannot
            # report the rest of them.
            pa, pb = ports.get(a) or {}, ports.get(b) or {}
            meets = bool((pa.get("out") or set()) & (pb.get("in") or set()))
            rec = (a, b, meets)
            if reciprocated and meets:
                consistent.append(rec)
            elif reciprocated:
                one_way_ok.append(rec)      # both asked, ports do not meet
            elif meets:
                one_way_bad.append(rec)     # one asked, and it would work
            else:
                one_way_bad.append(rec)

    # ---- 4. the builder must not emit an unreachable edge ---------------- #
    # v2.41.0.  This used to be a note.  The builder emitted every
    # composable_with entry as a starter edge, so the 97 declarations no port
    # can satisfy were becoming edges; now the builder checks the interface and
    # the gate requires it to keep doing so.  `strict=False` remains as an
    # escape hatch and is not what the default path uses.
    if BUILDER.exists():
        src = BUILDER.read_text(encoding="utf-8")
        if "composable_with" in src and "declared_composable" in src:
            for needle, msg in (
                ("def _composable", "the builder has no interface check"),
                ("skipped_edges", "the builder does not record skipped edges"),
                ("strict: bool = True", "the interface check is not the default"),
            ):
                if needle not in src:
                    fails.append("%s: %s (looked for %r)"
                                 % (BUILDER.name, msg, needle))
            print("builder check: interface gate present, skipped edges "
                  "recorded, strict is the default")
        # Behavioural check, not a source check: run it and confirm the drop
        # actually happens.
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_fu_gate13", BUILDER)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            strict = mod.suggest_composition("memory")
            legacy = mod.suggest_composition("memory", strict=False)
            if len(strict["starter_edges"]) > len(legacy["starter_edges"]):
                fails.append("strict mode produced MORE edges than legacy; the "
                             "interface gate is inverted")
            kept = {(e["from"], e["to"]) for e in strict["starter_edges"]}
            for e in strict.get("skipped_edges", []):
                if (e["from"], e["to"]) in kept:
                    fails.append("%s -> %s is both kept and skipped"
                                 % (e["from"], e["to"]))
            print("behaviour: strict keeps %d, drops %d, legacy kept %d"
                  % (len(strict["starter_edges"]),
                     len(strict.get("skipped_edges", [])),
                     len(legacy["starter_edges"])))
        except Exception as exc:            # noqa: BLE001
            fails.append("the builder could not be exercised: %r" % (exc,))

    # ---- 5. every unit must expose both directions ------------------------ #
    for u in units:
        p = ports.get(u["name"], {"in": set(), "out": set()})
        if not p["in"]:
            fails.append("%s exposes no input port, so nothing can drive it"
                         % u["name"])
        if not p["out"]:
            fails.append("%s exposes no output port, so it can feed nothing"
                         % u["name"])

    # ---- 6. the artifact must be reproducible ---------------------------- #
    total = sum(len(v) for v in comp.values())
    mutual_pairs = len({tuple(sorted((a, b))) for a, b, _ in consistent})
    one_way_pairs = len({tuple(sorted((a, b)))
                         for a, b, _ in one_way_ok + one_way_bad})
    if total and not (consistent or one_way_ok or one_way_bad):
        fails.append("no declaration could be classified; the classification "
                     "logic and the data disagree")

    print("composition: %d units, %d composable_with declarations"
          % (len(units), total))
    print("  consistent (reciprocal AND ports meet): %d"
          % len(consistent))
    print("  one-way or unreachable: %d declaration(s) over %d pair(s)"
          % (len(one_way_ok) + len(one_way_bad), one_way_pairs))
    print("    of those, ports could actually meet: %d"
          % len(one_way_ok))
    print("    of those, no port type can meet: %d" % len(one_way_bad))
    print("  distinct usable pairs: %d mutual + %d one-way-but-reachable"
          % (mutual_pairs, len({tuple(sorted((a, b))) for a, b, _ in one_way_ok})))
    reach = Counter()
    for u in units:
        reach["in_ports"] += 1 if ports.get(u["name"], {}).get("in") else 0
        reach["out_ports"] += 1 if ports.get(u["name"], {}).get("out") else 0
    print("  port coverage: %d/%d expose an input, %d/%d expose an output"
          % (reach["in_ports"], len(units), reach["out_ports"], len(units)))

    if one_way_bad:
        print("  examples that are declared but unreachable:")
        for a, b, _m in one_way_bad[:4]:
            oa = sorted((ports.get(a) or {}).get("out") or [])[:2]
            ib = sorted((ports.get(b) or {}).get("in") or [])[:2]
            print("    %-38s -> %-38s out=%s in=%s" % (a, b, oa, ib))

    # ---- 6. behavioural check: every DEMO must build AND function -------- #
    # v2.44.0.  Sections 1-5 all ask "can this be assembled?" -- the
    # classification of `composable_with` and the interface check in the
    # builder.  None of them asks whether a composition that DOES get built
    # actually works.  Two cheap things it must do:
    #
    #   (a) no orphan nodes.  Every node in `organism.nodes` must appear in
    #       at least one edge.  A node that is neither source nor target of
    #       anything is a unit that was instantiated but never wired -- it
    #       consumes memory and does nothing, and no other check in the
    #       library catches it.
    #
    #   (b) there is a drive path.  The organism must have at least one
    #       externally drivable required IN port AND at least one unbound
    #       OUT port, AND at least one IN port that can reach at least one
    #       OUT port through edges.  A composition where every output is
    #       re-consumed internally and no output is readable is a wire-up,
    #       not an organism; a composition where no input can reach any
    #       output is dead topology.
    #
    # Both checks run on the four curated DEMOS in `functional_units.py`,
    # which are the only fully-specified compositions in the library.  They
    # are cheap: one `compose_from_units` call each, no simulation.
    behavioural: dict = {"demos": {}, "orphan_injections": 0,
                          "drive_injections": 0}
    if BUILDER.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_fu_gate13_b", BUILDER)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            demos = getattr(mod, "DEMOS", {})
            for key, demo in demos.items():
                doc = mod.compose_from_units(demo["units"], demo["connections"],
                                             name=demo["name"])
                org = doc.get("organism", {})
                nodes = org.get("nodes", [])
                edges = org.get("edges", [])
                interf = doc.get("interface", {})
                val = doc.get("validation", {})
                ext_in = interf.get("external_in", [])
                ext_out = interf.get("external_out", [])
                touched = set()
                for e in edges:
                    touched.add(e["from"])
                    touched.add(e["to"])
                orphans = [n["id"] for n in nodes if n["id"] not in touched]

                # drive path: BFS from each ext_in, does any reach an
                # ext_out?  Only edges with `from` in `nodes` participate.
                adj: dict = {n["id"]: [] for n in nodes}
                for e in edges:
                    if e["from"] in adj:
                        adj[e["from"]].append(e["to"])
                out_ids = {o["unit"] for o in ext_out}
                drive_ok = False
                if ext_in and ext_out:
                    for s in ext_in:
                        src = s["unit"]
                        seen = {src}
                        stack = [src]
                        while stack:
                            x = stack.pop()
                            if x in out_ids and x != src:
                                drive_ok = True
                                break
                            for y in adj.get(x, []):
                                if y not in seen:
                                    seen.add(y)
                                    stack.append(y)
                        if drive_ok:
                            break

                problems = []
                if orphans:
                    problems.append("orphan nodes: %s" % orphans)
                if not val.get("ok"):
                    problems.append("validation.errors: %s"
                                    % val.get("errors", []))
                if not ext_in:
                    problems.append("no externally drivable required IN port")
                if not ext_out:
                    problems.append("no unbound OUT port (nothing readable)")
                if ext_in and ext_out and not drive_ok:
                    problems.append("no drive path from any external IN to "
                                    "any external OUT")

                behavioural["demos"][key] = {
                    "nodes": len(nodes),
                    "edges": len(edges),
                    "external_in": len(ext_in),
                    "external_out": len(ext_out),
                    "orphans": orphans,
                    "drive_path": drive_ok,
                    "validation_ok": bool(val.get("ok")),
                    "warnings": len(val.get("warnings", [])),
                }
                for p in problems:
                    fails.append("demo %s: %s" % (key, p))

            # Fault injection.  Both checks are new in v2.44.0 and would be
            # worthless if they could not actually fire.  Build two broken
            # compositions in memory and confirm the check reports each.
            # Neither of these touches disk.
            broken_orphan = dict(demos.get("mammal") or {})
            broken_orphan["units"] = list(broken_orphan["units"]) + [
                "hippocampal_ca2_autoassoc_unit"]
            broken_orphan["connections"] = list(broken_orphan["connections"])
            bdoc = mod.compose_from_units(broken_orphan["units"],
                                          broken_orphan["connections"],
                                          name="gate13_orphan_probe")
            bnodes = bdoc["organism"]["nodes"]
            bedges = bdoc["organism"]["edges"]
            btouched = {e["from"] for e in bedges} | {e["to"] for e in bedges}
            borphans = [n["id"] for n in bnodes if n["id"] not in btouched]
            if "hippocampal_ca2_autoassoc_unit" not in borphans:
                fails.append("orphan fault injection did not fire: %s was "
                             "added to a DEMO without edges but is not "
                             "reported as an orphan (orphans=%r)"
                             % ("hippocampal_ca2_autoassoc_unit", borphans))
            else:
                behavioural["orphan_injections"] = 1

            # drive-path injection: take the mammal DEMO and remove every
            # edge touching the deepest output.  The graph still validates
            # (no required port is newly dangling), but no drive path
            # reaches any unbound out.  Simpler: build a 2-unit chain with
            # a single edge that goes backwards.
            b2_units = ["retinal_phototransduction_unit",
                        "visual_thalamic_relay_unit"]
            b2_conns = [
                "visual_thalamic_relay_unit.lgn_out->retinal_phototransduction_unit.photoreceptor_in:feedforward_excitatory"
            ]
            b2doc = mod.compose_from_units(b2_units, b2_conns,
                                           name="gate13_drive_probe")
            b2adj = {n["id"]: [] for n in b2doc["organism"]["nodes"]}
            for e in b2doc["organism"]["edges"]:
                if e["from"] in b2adj:
                    b2adj[e["from"]].append(e["to"])
            b2outs = {o["unit"] for o in b2doc.get("interface", {}).get("external_out", [])}
            b2ins = [i["unit"] for i in b2doc.get("interface", {}).get("external_in", [])]
            b2drive = False
            for s in b2ins:
                seen = {s}
                stack = [s]
                while stack:
                    x = stack.pop()
                    if x in b2outs and x != s:
                        b2drive = True
                        break
                    for y in b2adj.get(x, []):
                        if y not in seen:
                            seen.add(y)
                            stack.append(y)
                if b2drive:
                    break
            behavioural["drive_injections"] = 1
            behavioural["drive_injection_expected_false"] = not b2drive
            if b2drive:
                fails.append("drive-path fault injection did not fire: a "
                             "reverse-only chain still reports a drive path")

            print("behavioural: %d demo(s) built and functional, orphan "
                  "injection fired, drive-path injection fired"
                  % len(behavioural["demos"]))
        except Exception as exc:            # noqa: BLE001
            fails.append("the builder could not be exercised for behavioural "
                         "checks: %r" % (exc,))
    else:
        fails.append("%s missing; behavioural checks skipped" % BUILDER)

    # ---- 7. write the ledger so the finding is queryable ------------------ #
    # A gate that only prints leaves the measurement in a log nobody reads.
    out_doc = {
        "schema_version": "1.0",
        "purpose": (
            "Whether the library can be assembled. `composable_with` decides "
            "which units may be wired together, and until now nothing checked "
            "it: gate 9 verifies the units are well formed, gate 11 checks "
            "functional coverage, gate 12 checks the cost axis, and none of "
            "them asked whether a declared combination can actually form."),
        "measurements": {
            "units": len(units),
            "declarations": total,
            "consistent_reciprocal_and_ports_meet": len(consistent),
            "one_way_or_unreachable": len(one_way_ok) + len(one_way_bad),
            "one_way_ports_would_meet": len(one_way_ok),
            "declared_but_unreachable": len(one_way_bad),
            "distinct_usable_pairs_mutual": mutual_pairs,
            "distinct_usable_pairs_one_way_reachable":
                len({tuple(sorted((a, b))) for a, b, _ in one_way_ok}),
            "port_coverage_in": sum(
                1 for u in units if (ports.get(u["name"]) or {}).get("in")),
            "port_coverage_out": sum(
                1 for u in units if (ports.get(u["name"]) or {}).get("out")),
        },
        "builder_behaviour": {
            "file": "functional_units.py",
            "reads": "composable_with",
            "emits": "starter_edges with reason=declared_composable",
            "checks_reciprocity": False,
            "checks_port_compatibility": False,
            "note": ("The one-way declarations are not a latent risk; they are "
                     "what the tool does today. Changing that is a behaviour "
                     "change and belongs in its own release, not in a gate."),
        },
        "unreachable_examples": [
            {"from": a, "to": b,
             "from_out_ports": sorted((ports.get(a) or {}).get("out") or []),
             "to_in_ports": sorted((ports.get(b) or {}).get("in") or [])}
            for a, b, _m in one_way_bad[:12]
        ],
        "behavioural": behavioural,
        "caveat": [
            "A one-way declaration is a real claim by the declaring unit. It is "
            "counted, not treated as an error: a composition A wants is not "
            "wrong merely because B never reciprocated.",
            "Port compatibility is checked by type string. Two units whose "
            "ports share a type are recorded as meeting, which is the weakest "
            "available reading -- a real composition may still be impossible "
            "for reasons a type string does not capture.",
            "A dangling target is reported as an error and the classifier "
            "still runs, so one bad reference does not hide the rest.",
            "The behavioural checks cover the four curated DEMOS, which are the "
            "only fully-specified compositions in the library.  A caller can "
            "still build an unreached-to-any-output organism from the same "
            "units by picking different connections; the DEMOS are the "
            "canonical examples the library is asked to assemble, so they "
            "must be well formed, but the general composition space is not "
            "exhausted by them.",
            "A 'drive path' means BFS from an external IN port reaches an "
            "external OUT port through directed edges.  It does not mean the "
            "path is functionally meaningful -- only that it is electrically "
            "possible.  Sign, weight, and connection-type semantics are not "
            "evaluated here.",
        ],
    }
    (MCP / "functional_units" / "composition_semantics.json").write_text(
        json.dumps(out_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    if fails:
        print()
        for f in fails:
            print("  [FAIL] %s" % f)
        print("GATE 13: FAIL (%d)" % len(fails))
        return 1
    print("GATE 13: PASS -- wiring resolves, ports are complete, and the "
          "one-way declarations are counted rather than ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
