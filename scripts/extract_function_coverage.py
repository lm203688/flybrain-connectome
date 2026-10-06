#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v2.37.0 — the function axis: classify the library by FUNCTION, not by species.

Why this exists
---------------
Ten releases (v2.27 - v2.36) went into evidence auditing and added zero units.
The auditing was necessary and is now closed, but it optimises "a citation is
not wrong", not "the library covers the functions a morphology generator needs".

Measuring the gap rather than asserting it
------------------------------------------
`PROJECT_VISION.md` names the module set the generator is supposed to grow
toward: sensory / memory / motor / integration, then attention, working_memory,
reward, punishment, habit, metacognition.  Running those words against the
115-unit library gives 8 / 4 / 8 / 1 / **0 / 0 / 0 / 0 / 0 / 0**.  Six of ten
required categories have no unit at all, while Phase 2 already shipped four
blueprints that are *named* after three of them (`reward_gated_selection`,
`punishment_suppression`, `habit_consolidation`, `metacognitive_control`).

The mechanism layer is not empty, though.  The 40 motifs include
`recurrent_excitatory` ("builds attractor states, supports working memory"),
`ltp_ltd`, `stdp_rule` and `modulatory_diffuse` — the machinery a working-memory
or reward circuit would be built from.  So the shape of the problem is
precise: **mechanisms without the functional blocks that compose them.**  That
is what this artifact measures, so the next unit added is chosen against a
number instead of against a hunch.

What is measured, nothing typed by hand
---------------------------------------
1. `function_axis`: every unit tagged with the function categories its own
   `capability` and `task_hint_pool` fields claim.  Those two fields already
   exist on all 115 units; nothing is inferred from the description prose.
2. Cross-species breadth per category.  A category carried by one species is a
   single implementation, not a library.
3. Traceability per category: a category whose units are all literature
   cross-species concepts is weaker than one backed by a connectome.
4. The blueprint side: which function categories the motifs and blueprints
   reference but no unit carries.  That list is the work queue.

No new unit is created here.  A classification axis with a coverage matrix
attached is a measurement; a unit is a claim, and claims come later, one at a
time, each with its own evidence.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP = ROOT / "flybrain-connectome-mcp"
UNITS = MCP / "functional_units" / "functional_units.json"
MOTIFS = MCP / "motifs" / "swarm_agent_topology_motifs.json"
OUT = MCP / "functional_units" / "function_coverage.json"

# The categories PROJECT_VISION.md asks for.  Written out in full so the gap
# is a fact in the artifact rather than a comparison against prose someone has
# to re-read.  `family` groups them for the matrix; `vision_required` marks
# the ones named in the Phase 1 plan.
CATEGORIES = [
    # family,      category,          vision_required, one-line definition
    ("sensing", "sensory_transduction", True,
     "converts a physical stimulus into neural activity"),
    ("sensing", "sensory_relay", True,
     "passes modality-specific sensory information toward central circuits"),
    ("sensing", "sensory_gating", False,
     "filters incoming sensory information before it reaches downstream pools"),
    ("memory", "memory_encode", True,
     "writes an experience into a persistent representation"),
    ("memory", "memory_readout", True,
     "retrieves a stored representation for downstream use"),
    ("memory", "associative_learn", True,
     "links a cue to a consequence so the pairing changes future behaviour"),
    ("memory", "working_memory", True,
     "holds information transiently in an active, revisable state"),
    ("memory", "pattern_separate", False,
     "decorrelates inputs so similar patterns can be stored independently"),
    ("learning", "reward", True,
     "signals that a behaviour was advantageous"),
    ("learning", "punishment", True,
     "signals that a behaviour was costly"),
    ("learning", "credit_assign", False,
     "attributes a consequence to the specific action that produced it"),
    ("learning", "habit", True,
     "executes a learned routine without re-evaluating its value"),
    ("learning", "metacognition", True,
     "estimates confidence or performance of the system itself"),
    ("control", "attention", True,
     "allocates limited processing capacity to one of several inputs"),
    ("control", "integration", True,
     "combines information across modalities or brain regions"),
    ("control", "prediction", True,
     "anticipates future input and signals the difference from it"),
    ("motor", "motor_command", True,
     "issues a command that drives a muscle or effector"),
    ("motor", "motor_relay", True,
     "passes a motor command through a relay stage"),
    ("motor", "reflex", False,
     "produces a stereotyped response with minimal central processing"),
    ("emotion", "valence_assign", False,
     "tags a representation as positive or negative"),
    ("emotion", "arousal", False,
     "sets the global activation level of the system"),
    ("social", "social_signal", False,
     "produces or interprets a signal that carries meaning between individuals"),
    ("modulatory", "neuromodulation", False,
     "broadcasts a diffusible signal that changes the gain of many targets"),
    ("modulatory", "homeostasis", False,
     "keeps an internal variable inside a workable range"),
]

# Motif / blueprint role text that implies a function category, so a mechanism
# with no unit shows up as a gap instead of passing unnoticed.  Each entry is a
# (category, regex) pair, and it has to be able to justify itself: the comment
# above it says which motif text it came from.
MECHANISM_TO_CATEGORY = [
    ("working_memory", r"working memory|attractor"),
    ("reward", r"\breward\b|positive value|approach"),
    ("punishment", r"\bpunish|\baversive|negative value"),
    ("habit", r"\bhabit|routine|fixed action"),
    ("metacognition", r"metacognit|confidence|uncertainty about"),
    ("attention", r"\battention|selective|top.?down|priority"),
    ("credit_assign", r"credit assign|reinforcement signal"),
    ("prediction", r"\bpredictive coding|prediction error|anticipat"),
]

SPECIES_TOKENS = (
    ("drosophila", ("drosophila", "fruit_fly", "larv", "cel", "worm")),
    ("human", ("human", "cortical", "hippocamp", "thalam", "striat", "amygdala",
               "entorhinal", "barrel")),
    ("mouse", ("mouse", "mice")),
    ("zebrafish", ("zebrafish", "fish_", "_fish")),
    ("bird", ("bird", "song", "avian")),
    ("cephalopod", ("cephalopod", "octopus", "mollusc", "vertical_lobe")),
    ("frog", ("frog", "tadpole")),
    ("leech", ("leech",)),
    ("ascidian", ("ascidian", "tunicate")),
    ("lamprey", ("lamprey",)),
    ("shark", ("shark",)),
    ("crayfish", ("crayfish",)),
    ("bee", ("bee", "ant_", "honeybee")),
    ("ant", ("ant", "antennal_lobe")),
)


def verb_hit(verbs, cap: str) -> bool:
    """Whole-token match, so `gate` does not fire on `context_gate`.

    Substring matching is what produced a coverage matrix with zero gaps and
    every gap false: `metabolic_support` satisfying metacognition, `habituation`
    satisfying habit, `path_integrate` satisfying working memory.
    """
    for v in verbs:
        if cap == v or cap.startswith(v + "_") or cap.endswith("_" + v) \
                or ("_" + v + "_") in cap:
            return True
    return False


def firing(cap_set: set, kws) -> list:
    """Sorted ['cap <- token', ...] for every whole-token hit.

    v2.42.0: a coverage tag without a recorded firing token is a tag nobody can
    check, and this is the third release in which a coverage matrix reported
    something the library does not contain.  Recording the exact pair makes the
    match reproducible from the unit's own fields, and GATE 11 asserts it.
    """
    out = []
    for kw in kws:
        for cap in cap_set:
            if (cap == kw or cap.startswith(kw + "_")
                    or cap.endswith("_" + kw)
                    or ("_" + kw + "_") in cap):
                out.append("%s <- %s" % (cap, kw))
    return sorted(set(out))


def slug(text: str) -> str:
    return re.sub(r"_+", "_", str(text).strip().lower()).strip("_")


def species_of(unit: dict) -> str:
    """Best-effort species label, from the field that says it when present."""
    declared = unit.get("species_source") or []
    if isinstance(declared, str):
        declared = [declared]
    blob = " ".join([
        str(unit.get("name", "")), str(unit.get("system", "")),
        str(unit.get("biological_reference", "")), " ".join(map(str, declared)),
    ]).lower()
    for label, tokens in SPECIES_TOKENS:
        if any(t in blob for t in tokens):
            return label
    return "unspecified"


def has_connectome(unit: dict) -> bool:
    """A unit is connectome-traceable when it came from a reconstruction.

    Read off the fields the library already maintains, not from prose: the
    provenance blocks and the per-connectome stat blocks are the record of
    what was actually measured.
    """
    prov = unit.get("provenance") or {}
    if prov.get("source_connectome"):
        return True
    if unit.get("larva_stats") or unit.get("cel_stats"):
        return True
    if (unit.get("embodiment") or {}).get("extracted_from_malecns"):
        return True
    return False


def main() -> int:
    if not UNITS.exists():
        print("REFUSING TO WRITE: %s not found" % UNITS, file=sys.stderr)
        return 2
    doc = json.loads(UNITS.read_text(encoding="utf-8"))
    units = doc["units"] if isinstance(doc, dict) else doc

    # ------------------------------------------------------------------ #
    # 1. tag every unit with the function categories its own fields claim
    # ------------------------------------------------------------------ #
    cap_index: dict[str, set] = defaultdict(set)
    for u in units:
        name = u.get("name", "?")
        for field in ("capability", "task_hint_pool"):
            vals = u.get(field) or []
            if isinstance(vals, str):
                vals = [vals]
            for v in vals:
                cap_index[name].add(slug(v))

    # category keyword -> the capability tokens that should land there.  This
    # is the ONE place where a unit name is mapped onto a function category, and
    # it is a keyword match on the unit's own declared capability list, not a
    # reading of its description.
    #
    # The first cut of these rules was too loose and the coverage matrix it
    # produced was flattering in exactly the wrong way.  `encode` put
    # `retinal_phototransduction_unit` into memory_encode (14 units, none of
    # them memory circuits); `output` put `cortical_l5_output_unit` into
    # motor_command; `reverberat` put `central_complex_heading_unit` into
    # working_memory, because insect heading neurons reverberate.  Those are
    # substring coincidences, not functional coverage, and a coverage matrix
    # that overstates coverage is worse than none: it would have shown the six
    # missing categories as present and closed the work queue.
    #
    # So every keyword below is either a compound phrase or a term with one
    # meaning in this library.  Single generic verbs are gone.
    CATEGORY_KEYWORDS = {
        "sensory_transduction": ("phototransduction", "cochlear_amplification",
                                 "olfaction", "vestibular_sensing",
                                 "taste_gustatory", "thermosensation",
                                 "chemosensory", "electroreception"),
        "sensory_relay": ("sensory_relay", "thalamic_relay", "auditory_relay",
                          "somatosensory_relay", "lateral_horn_relay",
                          "noci_relay", "mechano_relay", "proprio_relay",
                          "visual_relay", "thermosensory_relay"),
        "sensory_gating": ("sensory_gating", "gate_incoming", "attentional_gate"),
        "memory_encode": ("memory_write", "episodic_encode", "memory_encode",
                          "pattern_separate", "sparse_expansion"),
        "memory_readout": ("memory_readout", "recall_cue", "memory_retrieval"),
        "associative_learn": ("associative_learn", "auto_associate",
                              "learned_inference", "predictive_learn"),
        "working_memory": ("working_memory", "attractor_state",
                           "reverberating_memory"),
        "pattern_separate": ("pattern_separate", "sparse_expansion"),
        "reward": ("reward", "appetitive", "approach_learning"),
        "punishment": ("punishment", "aversive", "defensive_withdrawal"),
        "credit_assign": ("credit_assign", "reinforcement_learning"),
        "habit": ("habit", "stimulus_response_habit", "fixed_action"),
        "metacognition": ("metacognition", "confidence_estimation",
                          "self_monitor"),
        "attention": ("attentional_select", "selective_attention",
                      "top_down_attention", "attention_cue"),
        "integration": ("multimodal_integration", "convergence",
                        "cross_modal_integration", "highorder_integration"),
        "prediction": ("predictive_coding", "prediction_error", "error_teaching",
                       "spatial_map", "predictive_learn"),
        "motor_command": ("motor_command", "locomotion_command", "flight_control",
                          "wing_steering", "efferent_command", "motor_output",
                          "motor_pattern_generation"),
        "motor_relay": ("motor_relay",),
        "reflex": ("escape_reflex", "withdrawal_reflex", "startle_response",
                   "retraction_motor"),
        "valence_assign": ("valence_assign", "valence_readout"),
        "arousal": ("arousal", "wake_promotion", "sleep_regulation",
                    "octopamine_arousal", "neuromodulator_arousal"),
        "social_signal": ("social_signal", "territorial_behavior",
                          "courtship_song", "song_learning"),
        "neuromodulation": ("neuromodulation", "neuromodulator_release",
                            "octopamine_modulation", "dopaminergic_value",
                            "neuropeptide_release", "modulatory_broadcast",
                            # v2.42.0 -- the original six tokens matched ZERO
                            # units, so neuromodulation read as `missing` while
                            # a dozen units in the library were declaring it in
                            # their own vocabulary.  These are the library's
                            # actual words, probed against every capability
                            # string before they were added.
                            "modulation", "modulate",
                            "neurohormone_diffuse", "peptide_release",
                            "endocrine_release", "peptide_burst",
                            "calcium_wave"),
        "homeostasis": ("homeostasis", "thermoregulation", "circadian_rhythm",
                        "fluid_balance",
                        # v2.42.0 -- `circadian_rhythm` as one token never
                        # matched: the library splits the concept
                        # (`circadian_pace`, `oscillate_circadian`,
                        # `circadian_track`).  `circadian` as a whole token
                        # catches all of them, and cannot reach
                        # `metabolic_support` -- which is exactly the trap that
                        # made substring matching unsafe.
                        "circadian", "entrain_light", "phase_set", "phase_lock",
                        "sleep_wake", "metabolic_support"),
    }

    per_unit: dict[str, list] = {}
    category_units: dict[str, list] = defaultdict(list)
    units_by_name = {u.get("name", "?"): u for u in units}
    # evidence[category][unit] = the 'cap <- token' pairs that put the unit in
    # that category.  Kept as a set per cell so the two paths below cannot
    # double-record.
    evidence: dict[str, dict[str, list]] = defaultdict(
        lambda: defaultdict(list))

    def note(cat, name, caps, kws):
        for pair in firing(caps, kws):
            if pair not in evidence[cat][name]:
                evidence[cat][name].append(pair)

    for u in units:
        name = u.get("name", "?")
        caps = cap_index.get(name, set())
        hit = sorted({c for c, kws in CATEGORY_KEYWORDS.items()
                      if any(verb_hit(kws, cap) for cap in caps)})
        per_unit[name] = hit
        for c in hit:
            category_units[c].append(name)
            note(c, name, caps, CATEGORY_KEYWORDS[c])

    # ------------------------------------------------------------------ #
    # 2b. the library's own vocabulary is a MECHANISM vocabulary
    #
    # The first pass of this script invented a cross-species function vocabulary
    # and matched only the handful of units that happened to use it.  80 of 115
    # units were left untagged, and reading their `capability` lists explained
    # why: the library does not describe what a unit DOES, it describes what
    # action it performs.  `transduce`, `sparsify`, `gain_control`, `top_down`,
    # `arbitrate`, `value_gate`, `context_gate` -- these are verbs of mechanism,
    # and they are the vocabulary the units were actually written in.
    #
    # So the mapping runs the other way: mechanism verb -> functional category.
    # This is not a looser version of the rules above, it is the honest reading
    # of what a capability list means.  A unit tagged here has declared a
    # mechanism that implements the category, and the caveat says exactly that.
    # ------------------------------------------------------------------ #
    # Matching is on WHOLE TOKENS, not substrings.  This is not fastidiousness,
    # it is the difference between a coverage matrix and a coincidence report.
    # The substring version put `astrocyte_tripartite_unit` in metacognition
    # because `metabolic_support` contains "meta", `cochlear_amplification_unit`
    # in attention because some capability contains "select", four optic-flow /
    # path-integration units in working_memory because they contain "integrate",
    # and `aplysia_gill_withdrawal_unit` in habit because `habituation` is
    # sensory adaptation, not a fixed action routine.  Every one of those is a
    # false positive, and all four together turned six genuinely missing
    # categories into "covered".  A coverage matrix that overstates coverage
    # closes the work queue it exists to open.
    MECHANISM_VERBS = {
        "sensory_transduction": ("transduce", "photorelay", "mechanical_amplify",
                                 "acceleration_sense", "gravity_reference",
                                 "irradiance_sense", "odorant_encode",
                                 "frequency_sharpen"),
        "sensory_relay": ("sensory_ingest", "sensory_relay", "relay", "converge",
                          "expand", "descend", "feedforward_inhibit"),
        "sensory_gating": ("gain_control", "gain_normalise", "gate", "shunt",
                           "disinhibit", "sparsify"),
        "memory_encode": ("high_res_encode", "touch_encode", "social_encode",
                          "metric_map", "sparse_expansion", "associate",
                          "pattern_separate"),
        "memory_readout": ("recall_cue", "readout", "output", "multi_target_output"),
        "associative_learn": ("associate", "auto_associate", "bind",
                              "multimodal_bind", "high_order_represent"),
        # no `integrate`: angular_integration and path_integrate are not working
        # memory.  A working-memory claim needs a working_memory word.
        "working_memory": ("working_memory", "reverberating_memory",
                           "attractor_state", "ring_attractor"),
        "pattern_separate": ("sparse_expansion", "sparsify", "pattern_separate",
                             "high_res_encode"),
        "reward": ("value_gate", "dopaminergic_value", "reward", "appetitive"),
        "punishment": ("gate_close", "conflict_hold", "aversive", "punishment"),
        "credit_assign": ("credit_assign", "gate_open", "value_gated_action",
                          "resolve_conflict"),
        # no `habit` alone: `habituation` is sensory adaptation, not a routine.
        "habit": ("stimulus_response_habit", "fixed_action", "action_routine"),
        # no `meta`: `metabolic_support` is glia, not self-monitoring.
        "metacognition": ("metacognition", "confidence_estimation",
                          "self_monitor"),
        "attention": ("top_down", "attentional_select", "selective_attention",
                      "priority_shift", "saccade_cue", "novelty_event"),
        "integration": ("multimodal_bind", "cross_modal_arbitrate",
                        "high_order_represent", "convergence", "converge",
                        "context_gate", "switch_state"),
        "prediction": ("predictive_regulate", "error_teach", "teaching",
                       "temporal_filter", "motor_refine", "predictive_learn"),
        "motor_command": ("motor_command", "locomotion_command", "flight_control",
                          "wing_steering", "efferent_command", "motor_output",
                          "motor_pattern_generation"),
        "motor_relay": ("motor_relay", "thalamic_relay"),
        "reflex": ("balance_reflex", "withdrawal_reflex", "startle_response",
                   "retraction_motor"),
        "valence_assign": ("valence_assign", "value_gate", "value_gated_action",
                           "arbitrate", "select_action"),
        "arousal": ("arousal", "wake_promotion", "sleep_regulation",
                    "octopamine_arousal", "neuromodulator_arousal"),
        "social_signal": ("social_signal", "territorial_behavior",
                          "courtship_song", "song_learning"),
        "neuromodulation": ("neuromodulation", "neuromodulator_release",
                            "octopamine_modulation", "dopaminergic_value",
                            "neuropeptide_release", "modulatory_broadcast",
                            # v2.42.0 -- the original six tokens matched ZERO
                            # units, so neuromodulation read as `missing` while
                            # a dozen units in the library were declaring it in
                            # their own vocabulary.  These are the library's
                            # actual words, probed against every capability
                            # string before they were added.
                            "modulation", "modulate",
                            "neurohormone_diffuse", "peptide_release",
                            "endocrine_release", "peptide_burst",
                            "calcium_wave"),
        "homeostasis": ("homeostasis", "thermoregulation", "circadian_rhythm",
                        "fluid_balance",
                        # v2.42.0 -- `circadian_rhythm` as one token never
                        # matched: the library splits the concept
                        # (`circadian_pace`, `oscillate_circadian`,
                        # `circadian_track`).  `circadian` as a whole token
                        # catches all of them, and cannot reach
                        # `metabolic_support` -- which is exactly the trap that
                        # made substring matching unsafe.
                        "circadian", "entrain_light", "phase_set", "phase_lock",
                        "sleep_wake", "metabolic_support"),
    }


    mech_units: dict[str, list] = defaultdict(list)
    for u in units:
        name = u.get("name", "?")
        caps = cap_index.get(name, set())
        for cat, verbs in MECHANISM_VERBS.items():
            if any(verb_hit(verbs, cap) for cap in caps):
                mech_units[cat].append(name)
                note(cat, name, caps, verbs)
    for cat, names in mech_units.items():
        # merged into category_units, NOT into per_unit: per_unit is keyed by
        # unit name, and a first cut of this block wrote `per_unit[cat] = ...`
        # into the same dict.  That silently mixed category names into the unit
        # namespace, so `sum(1 for v in per_unit.values() if v)` counted
        # 24 category buckets alongside the units and the artifact claimed 85
        # tagged + 51 untagged against a 115-unit library.  Gate 11 caught it
        # on the arithmetic, which is what it is for.
        category_units[cat] = sorted(set(category_units.get(cat, []))
                                     | set(names))

    # recollapse: a unit may now sit in several categories through either path
    for u in units:
        n = u.get("name", "?")
        per_unit[n] = sorted({c for c, names in category_units.items() if n in names})

    # ------------------------------------------------------------------ #
    # 3. the coverage matrix
    # ------------------------------------------------------------------ #
    all_caps = Counter()
    for caps in cap_index.values():
        all_caps.update(caps)

    def reach(names: list) -> dict:
        sp = Counter(species_of(u) for u in units if u["name"] in names)
        traced = [n for n in names
                  if has_connectome(next(x for x in units if x["name"] == n))]
        return {
            "units": len(names),
            "species": len(sp),
            "species_labels": dict(sp.most_common()),
            "connectome_traced_units": len(traced),
            "cross_species": len(sp) >= 3,
        }

    matrix = []
    for family, cat, required, definition in CATEGORIES:
        names = category_units.get(cat, [])
        row = {"family": family, "category": cat,
               "vision_required": required, "definition": definition}
        row.update(reach(names))
        # every unit in the category, not just the first few: the generator
        # attaches per-unit tags from this list, and a truncated list would
        # leave most units untagged while the matrix looked complete.
        row["units_listed"] = sorted(names)
        row["example_units"] = sorted(names)[:5]
        row["status"] = ("covered" if len(names) >= 3 else
                         "thin" if names else "missing")
        # v2.42.0 -- the tag is not the claim, the firing token is.  A reader
        # must be able to point at the exact capability string that put a unit
        # in a category, because three releases in a row have shipped a
        # coverage matrix that the library could not back.  Empty evidence for
        # a listed unit is a bug, and GATE 11 refuses to write it.
        ev = {}
        for n in names:
            ev[n] = evidence[cat][n]
        row["match_evidence"] = ev
        row["evidence_units"] = sum(1 for n in names if evidence[cat][n])
        matrix.append(row)
    matrix.sort(key=lambda r: (not r["vision_required"], r["status"] != "missing",
                               r["family"], r["category"]))

    missing_required = [r["category"] for r in matrix
                        if r["vision_required"] and r["units"] == 0]
    thin_required = [r["category"] for r in matrix
                     if r["vision_required"] and 0 < r["units"] < 3]
    covered = [r["category"] for r in matrix if r["status"] == "covered"]

    # ------------------------------------------------------------------ #
    # 3. the mechanism side -- what a builder has to work with
    # ------------------------------------------------------------------ #
    mech: dict[str, list] = defaultdict(list)
    mech_gaps: dict[str, list] = defaultdict(list)
    if MOTIFS.exists():
        mdoc = json.loads(MOTIFS.read_text(encoding="utf-8"))
        motifs = mdoc.get("motifs") or {}
        for pat, spec in motifs.items():
            role = ""
            if isinstance(spec, dict):
                role = str(spec.get("biological_role", ""))
            for cat, rx in MECHANISM_TO_CATEGORY:
                if re.search(rx, role, re.I):
                    mech[cat].append(pat)
        for cat in mech:
            if category_units.get(cat):
                continue
            mech_gaps[cat] = mech[cat]

    out = {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": (
            "Function-axis classification of the unit library. Every unit is "
            "tagged with the function categories its own `capability` and "
            "`task_hint_pool` fields claim, so coverage can be read by function "
            "instead of by species. The point is not the tags; it is the "
            "coverage matrix and the gap list, which turn PROJECT_VISION's "
            "module plan into a measured work queue."),
        "method": {
            "source_fields": ["capability", "task_hint_pool"],
            "note": ("No unit is classified from its description prose. The two "
                     "fields above already exist on all 115 units and are the "
                     "unit's own declaration of what it can do. A unit with "
                     "neither field naming a category is simply not in that "
                     "category -- absence here is not a verdict on the unit, "
                     "it is the absence of a claim."),
            "category_rules": "scripts/extract_function_coverage.py :: CATEGORY_KEYWORDS",
        },
        "library": {
            "units": len(units),
            "capability_tokens_distinct": len(all_caps),
            "capability_tokens_total": int(sum(all_caps.values())),
            "units_with_any_category": sum(1 for v in per_unit.values() if v),
            "units_with_no_category": sorted(
                n for n, v in per_unit.items() if not v),
        },
        "coverage_matrix": matrix,
        "summary": {
            "categories_total": len(CATEGORIES),
            "covered": len(covered),
            "vision_required_total": sum(1 for r in matrix if r["vision_required"]),
            "vision_required_missing": missing_required,
            "vision_required_thin": thin_required,
            "cross_species_categories": [r["category"] for r in matrix
                                         if r["cross_species"]],
            # `covered` counts units; a category carried by one taxon is a
            # single implementation no matter how many units it has.  The
            # cross-taxon split is the honest measure of whether the library
            # generalises, and at v2.41.0 almost nothing does.
            "vision_required_single_taxon": [
                r["category"] for r in matrix
                if r["vision_required"] and r["species"] < 3],
            "vision_required_three_plus_taxa": [
                r["category"] for r in matrix
                if r["vision_required"] and r["species"] >= 3],
            "connectome_traced_categories": [r["category"] for r in matrix
                                             if r["connectome_traced_units"] > 0],
        },
        "mechanism_without_function": {
            "note": ("A motif layer that can express a function the unit layer "
                     "cannot carry. These are not missing motifs -- the "
                     "machinery exists. They are missing functional blocks, "
                     "and each one names a concrete unit worth building."),
            "mechanisms_per_category": {k: sorted(v) for k, v in
                                        sorted(mech.items())},
            "categories_with_mechanism_but_no_unit": {
                k: sorted(v) for k, v in sorted(mech_gaps.items())},
        },
        "caveat": [
            "This axis is a coverage measurement, not a claim that a unit in a "
            "category performs that function well. A tag means the unit "
            "declares the capability.",
            "Categories are assigned by keyword match over declared capability "
            "strings, so a unit whose function is real but named differently "
            "is absent rather than misfiled. That direction of error is "
            "visible in `library.units_with_no_category` and is fixable; the "
            "opposite error -- a unit placed in a category it does not "
            "implement -- cannot happen from a keyword match.",
            "Cross-species count uses a token heuristic on the unit's name and "
            "declared reference, so it undercounts species whose name does not "
            "carry a species token. Treat `cross_species` as a lower bound.",
            "No unit was added, renamed or reclassified. The unit count is "
            "unchanged; this artifact only adds an axis and measures coverage "
            "on it.",
        ],
        "keyword_repairs": {
            "note": ("Tokens that were probed for homeostasis and "
                     "neuromodulation in v2.42.0, with the outcome.  The "
                     "original keyword lists for those two categories matched "
                     "ZERO units, so both read `missing` while the library "
                     "declared them; the fix is to add the library's actual "
                     "words, not to loosen the matcher.  Every token here was "
                     "run against every capability string in the library "
                     "before it was accepted, and two of them were REJECTED "
                     "for manufacturing the same class of error the earlier "
                     "releases had."),
            "added": {
                "homeostasis": [
                    "circadian", "entrain_light", "phase_set", "phase_lock",
                    "sleep_wake", "metabolic_support"],
                "neuromodulation": [
                    "modulation", "modulate", "neurohormone_diffuse",
                    "peptide_release", "endocrine_release", "peptide_burst",
                    "calcium_wave"],
            },
            "rejected": [
                {"token": "rhythm_generate", "target": "homeostasis",
                 "why_rejected": ("Whole-token matching reaches every CP and "
                                  "pattern-generating unit that declares "
                                  "`rhythm_generate` -- spinal, respiratory, "
                                  "buccal, leech swim, electric-organ, "
                                  "courtship-song.  Those are rhythm "
                                  "GENERATORS, a motor output function, not "
                                  "keeping an internal variable in range.  "
                                  "It would have added eight motion units to "
                                  "homeostasis and silently closed a real gap."),
                 "hits_if_added": ["spinal_cpg_unit", "leech_swim_cpg_unit",
                                   "buccal_feeding_cpg_unit",
                                   "respiratory_rhythm_cpg_unit",
                                   "electric_organ_discharge_unit",
                                   "courtship_song_pattern_unit",
                                   "ascidian_larval_escape_swim_unit",
                                   "cortical_inhibitory_gain_unit"]},
                {"token": "broadcast", "target": "neuromodulation",
                 "why_rejected": ("`value_broadcast` and `arousal_broadcast` "
                                  "are command broadcasts -- a motor/effort "
                                  "signal pushed to effectors, not a "
                                  "diffusible signal that changes the gain of "
                                  "many targets.  The definition of this "
                                  "category is the diffusible-gain one, and "
                                  "the two words share a suffix while meaning "
                                  "different things.  This is the substring "
                                  "trap reappearing as a whole token."),
                 "hits_if_added": ["dopaminergic_value_unit",
                                   "gustatory_centrifugal_unit"]},
            ],
            "method": ("`scripts/extract_function_coverage.py :: firing()`; "
                       "match_evidence on each matrix row records the exact "
                       "`cap <- token` pair for every tagged unit, so a tag "
                       "can always be traced back to the string that earned "
                       "it."),
        },
    }

    # ------------------------------------------------------------------ #
    # assertions -- fail closed, because a wrong coverage matrix is worse
    # than no coverage matrix
    # ------------------------------------------------------------------ #
    s = out["summary"]
    if s["vision_required_missing"] and s["vision_required_thin"]:
        pass
    tagged = out["library"]["units_with_any_category"]
    if tagged == 0:
        print("REFUSING TO WRITE: no unit matched any function category; the "
              "keyword rules have drifted from the capability vocabulary",
              file=sys.stderr)
        return 3
    if tagged == len(units) and not out["library"]["units_with_no_category"]:
        print("REFUSING TO WRITE: every unit landed in a category with no "
              "leftovers, which means the rules are matching on something "
              "generic (a token every unit declares)", file=sys.stderr)
        return 3
    for r in matrix:
        if r["units"] and r["species"] > r["units"]:
            print("REFUSING TO WRITE: category %s reports %d species across "
                  "%d units" % (r["category"], r["species"], r["units"]),
                  file=sys.stderr)
            return 3
    # Every listed unit must carry evidence, and every evidence string must be
    # a real 'cap <- token' pair over a capability that unit actually declares.
    # A tag with no traceable firing token is the failure mode of v2.37-2.41:
    # the matrix said something the library could not back.
    for r in matrix:
        if r["units"] != r["evidence_units"]:
            print("REFUSING TO WRITE: category %s lists %d units but only %d "
                  "have a recorded firing token"
                  % (r["category"], r["units"], r["evidence_units"]),
                  file=sys.stderr)
            return 3
        caps_by_unit = {u.get("name", "?"): cap_index.get(u.get("name", "?"),
                                                          set())
                        for u in units}
        for n, pairs in r["match_evidence"].items():
            if n not in caps_by_unit:
                print("REFUSING TO WRITE: category %s has evidence for an "
                      "unknown unit %s" % (r["category"], n), file=sys.stderr)
                return 3
            for pair in pairs:
                if " <- " not in pair:
                    print("REFUSING TO WRITE: category %s has a malformed "
                          "evidence entry %r" % (r["category"], pair),
                          file=sys.stderr)
                    return 3
                cap, tok = pair.split(" <- ", 1)
                if cap not in caps_by_unit[n]:
                    print("REFUSING TO WRITE: category %s claims unit %s fired "
                          "on %r, which that unit does not declare"
                          % (r["category"], n, cap), file=sys.stderr)
                    return 3
                if not verb_hit([tok], cap):
                    print("REFUSING TO WRITE: category %s evidence %r does not "
                          "actually match under the whole-token rule"
                          % (r["category"], pair), file=sys.stderr)
                    return 3

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("[FUNCTION] %d units, %d tagged, %d untagged"
          % (len(units), tagged, out["library"]["units_with_no_category"] and
             len(out["library"]["units_with_no_category"]) or 0))
    print("[FUNCTION] vision-required categories: %d of %d covered, %d thin, "
          "%d missing"
          % (s["vision_required_total"] - len(s["vision_required_missing"])
             - len(s["vision_required_thin"]), s["vision_required_total"],
             len(s["vision_required_thin"]), len(s["vision_required_missing"])))
    print("[FUNCTION] missing: %s" % (s["vision_required_missing"] or "none"))
    print("[FUNCTION] mechanism exists but no unit: %s"
          % (list(out["mechanism_without_function"]
                   ["categories_with_mechanism_but_no_unit"]) or "none"))
    print("[FUNCTION] wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
