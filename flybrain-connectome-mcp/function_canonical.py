"""Canonical function taxonomy for the 116 functional units (T2).

The raw ``function`` field accumulated 110 distinct free-text values (104 used
exactly once) — a catalogue, not a retrieval axis.  This module pins **24
canonical function categories** and provides a deterministic ``classify()`` that
maps any unit to exactly one category.  Every unit maps to *some* category
(including ``other_unspecified``), so coverage is 100% by construction; the
``confidence`` flag tells a reader how much to trust the auto-assignment.

This is the single source of truth consumed by Gate 19
(``scripts/check_function_canonical.py``) and used to build
``docs/function_coverage.json`` (the 24 x clade x evidence-level readiness
matrix from the foundation roadmap T2).

Design note: the classifier is keyword-priority based and deliberately
deterministic.  It is NOT a machine-learning model and makes no claim of
neuroscience correctness for borderline units — borderline calls are flagged
``confidence: low`` and land in ``other_unspecified`` so the gap is visible
rather than silently miscategorised.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

MCP = Path(__file__).resolve().parent
UNITS = MCP / "functional_units" / "functional_units.json"

# ---------------------------------------------------------------------------
# The 24 canonical categories.
# ---------------------------------------------------------------------------
CANONICAL: dict[str, dict] = {
    "sensory_encoding":        {"label": "Sensory encoding",        "definition": "Transduce an external physical stimulus into an internal neural signal (photoreception, olfaction, mechanosensation, audition, electroreception, thermosensation)."},
    "sensory_motor_transform": {"label": "Sensory-motor transform", "definition": "Convert a sensory feature into a behaviourally-relevant signal (direction selectivity, motion onset, looming, target detection, optic flow)."},
    "relay_gateway":           {"label": "Relay / gateway",         "definition": "Pass, route or re-format signals between regions without heavy transformation (thalamic/cortical relays, association, projection hubs)."},
    "motor_pattern_gen":       {"label": "Motor pattern generation","definition": "Generate rhythmic or sequential motor patterns centrally (rhythm/pattern generators, pacemakers, sequence generators, servo loops)."},
    "motor_command":           {"label": "Motor command",           "definition": "Issue the final actuation command to effectors (escape, strike, steering, locomotion, posture, gaze)."},
    "associative_learning":    {"label": "Associative learning",    "definition": "Acquire or update stimulus-stimulus / action-outcome associations (Hebbian, reinforcement, predictive learning)."},
    "declarative_memory":      {"label": "Declarative memory",      "definition": "Store and read out experienced facts / maps / episodes (episodic, spatial, social)."},
    "working_memory":          {"label": "Working memory",          "definition": "Maintain a transient state online for the current task."},
    "attention_gain":          {"label": "Attention / gain",        "definition": "Select or scale signal routes (inhibitory gain control, visual gain, centrifugal feedback, multimodal gating)."},
    "valuation":               {"label": "Valuation",               "definition": "Compute reward / value / affective broadcast that biases other systems."},
    "action_selection":        {"label": "Action selection",        "definition": "Choose among competing actions (facilitation, suppression, decision)."},
    "cognitive_control":       {"label": "Cognitive control",       "definition": "Metacognitive / executive oversight (confidence evaluation, global state switching)."},
    "inhibitory_control":      {"label": "Inhibitory control",      "definition": "Active gating / suppression that shapes dynamics (dedicated inhibitory control circuits)."},
    "arousal_regulation":      {"label": "Arousal regulation",      "definition": "Set global brain state (arousal stability, cholinergic tone, circadian pacemaking)."},
    "emotional_state":         {"label": "Emotional state",         "definition": "Affective / defensive / social-affective states (mood, threat, social stress)."},
    "homeostatic_regulation":  {"label": "Homeostatic regulation",  "definition": "Regulate internal physiology to a set point (feeding, respiration, temperature, energy)."},
    "navigation":              {"label": "Navigation",              "definition": "Build and use a spatial representation to move through the world (spatial map, heading, flow)."},
    "communication":           {"label": "Communication",            "definition": "Produce or receive social / conspecific signals (vocal, song, courtship, camouflage)."},
    "interoception":           {"label": "Interoception",           "definition": "Represent internal body state via neuromodulators / glia (peptide, neurohormone, gliotransmission)."},
    "prediction":              {"label": "Prediction",              "definition": "Form forward expectations about sensory input."},
    "error_computation":       {"label": "Error computation",       "definition": "Compute teaching / prediction-error signals that drive learning (cerebellar, error teaching)."},
    "timing":                  {"label": "Timing",                  "definition": "Represent interval / phase / rhythm used as a timing reference (theta, spindle)."},
    "structural_plasticity":   {"label": "Structural plasticity",   "definition": "Develop or rewire connectivity (reflex plasticity, developmental learning)."},
    "other_unspecified":       {"label": "Other / unspecified",     "definition": "Function present but not cleanly mapped to the 23 above; flagged for later curation."},
}

CANON_IDS = list(CANONICAL.keys())

# ---------------------------------------------------------------------------
# Keyword priority rules.  First matching category wins (top to bottom).
# Each entry: category -> list of lower-cased substrings to test against the
# unit's function / lead_task_hint / capability text.
# ---------------------------------------------------------------------------
_RULES: list[tuple[str, list[str]]] = [
    ("error_computation", ["error_teach", "cerebellar", "teaching"]),
    ("structural_plasticity", ["reflex_plasticity", "structural_plast", "developmental"]),
    ("motor_pattern_gen", ["rhythmic_pattern", "rhythm_generate", "rhythm ", "spindle", "breathing_rhythm", "feeding_rhythm", "pacemak", "sequence_generate", "song_pattern", "motor_coordination"]),
    ("motor_command", ["motor_command", "arm_control", "leg_drive", "flight_steer", "flight_power", "steering", "heading_track", "strike", "prey_capture", "escape_trigger", "escape_swim", "escape_reflex", "locomotion_command", "command_issue", "distributed_command", "reflex_arc", "local_reflex", "touch_reflex", "posture_set", "gaze_stabilize"]),
    ("associative_learning", ["associative_learn", "associative_learning", "threat_learning", "motor_learning", "predictive_learn", "reflex_plasticity"]),
    ("declarative_memory", ["episodic_memory", "social_stress_memory", "memory_readout", "spatial_map"]),
    ("working_memory", ["working_memory", "buffer"]),
    ("prediction", ["predictive_learn", "predict", "expectation"]),
    ("attention_gain", ["gain_control", "visual_gain", "centrifugal_feedback", "ingestive_feedback", "visual_gain_feedback", "multimodal_integration", "cross_modal", "inhibitory_gain"]),
    ("valuation", ["value_broadcast", "mood_modulation", "valuation"]),
    ("emotional_state", ["mood_modulation", "affective", "fear", "threat", "social_stress"]),
    ("action_selection", ["action_selection", "action_facilitation", "action_suppression", "courtship_decision"]),
    ("cognitive_control", ["confidence_evaluation", "metacog", "executive", "global_arousal", "state_switch"]),
    ("inhibitory_control", ["inhibitory_control", "active_inhibit"]),
    ("arousal_regulation", ["arousal_stability", "cholinergic_arousal", "circadian", "arousal_modulate", "arousal_regulation"]),
    ("homeostatic_regulation", ["feeding", "respiratory", "thermorecept", "homeostat", "energy"]),
    ("navigation", ["spatial_map", "heading_track", "optic_flow", "navigation"]),
    ("communication", ["vocal_motor", "song_", "courtship", "camouflage", "communication"]),
    ("interoception", ["gliotransmission", "neurohormone", "peptide_release", "neuromodulatory", "modulation", "interocept"]),
    ("sensory_motor_transform", ["direction_selectivity", "motion_onset", "motion_detect", "target_detect", "looming", "optic_flow", "visual_gain", "visual_gain_control", "visual_gain_feedback"]),
    ("relay_gateway", ["relay", "cortical_input", "cortical_output", "cortical_feedback", "cortical_association", "projection", "aa_l", "aal_cc"]),
    ("sensory_encoding", ["phototransduction", "irradiance", "photorecept", "olfaction", "odour_encode", "chemosensation", "cochlear", "vestibular", "somatosensation", "somatosensory", "taste_encode", "nociception", "thermorecept", "thermal_imaging", "electrolocate", "active_touch", "wind_detect", "song_reception", "colour_encode", "colour", "sensory"]),
]

# Categories that, if reached only via hint/capability (not the function field
# itself), are considered lower-confidence.
_HIGH_CONF_VIA_FUNCTION = True


def _unit_text(u: dict) -> str:
    parts = [u.get("function", "") or "", u.get("lead_task_hint", "") or ""]
    caps = u.get("capability")
    if isinstance(caps, list):
        parts.extend(caps)
    elif caps:
        parts.append(str(caps))
    return " \n ".join(parts).lower()


def classify(unit: dict) -> tuple[str, str]:
    """Return (canonical_id, confidence) for a functional-unit dict.

    confidence is ``high`` when the unit's ``function`` field itself matches a
    rule, ``medium`` when only hint/capability matched, ``low`` when it fell
    through to ``other_unspecified``.
    """
    fn = (unit.get("function", "") or "").lower()
    text = _unit_text(unit)
    for cat, kws in _RULES:
        for kw in kws:
            if kw in fn:
                return cat, "high"
    for cat, kws in _RULES:
        for kw in kws:
            if kw in text:
                return cat, "medium"
    return "other_unspecified", "low"


def load_units() -> list[dict]:
    doc = json.loads(UNITS.read_text(encoding="utf-8"))
    return doc["units"] if isinstance(doc, dict) else doc


def build_map() -> dict[str, dict]:
    """Map every unit name -> {category, confidence}."""
    out: dict[str, dict] = {}
    for u in load_units():
        cat, conf = classify(u)
        out[u["name"]] = {"category": cat, "confidence": conf}
    return out


def clade_of(unit: dict) -> str:
    """Coarse clade for the readiness matrix (species_source or system)."""
    src = unit.get("species_source") or unit.get("system") or "unknown"
    s = str(src).lower()
    if "fly" in s or "drosophil" in s or "male_cns" in s:
        return "insect"
    if "worm" in s or "c. elegans" in s:
        return "worm"
    if "larva" in s or "winding" in s:
        return "insect_larva"
    if "zebra" in s or "petkova" in s:
        return "vertebrate_fish"
    if "h01" in s or "human" in s:
        return "human"
    if "microns" in s or "mouse" in s:
        return "vertebrate_mouse"
    return "unknown"


if __name__ == "__main__":
    mp = build_map()
    from collections import Counter
    c = Counter(v["category"] for v in mp.values())
    print("canonical coverage: %d/%d units across %d categories" % (len(mp), len(mp), len(c)))
    for cid in CANON_IDS:
        print("  %-22s %3d" % (cid, c.get(cid, 0)))
    low = [n for n, v in mp.items() if v["confidence"] == "low"]
    print("low-confidence (other_unspecified):", len(low))
    for n in low:
        print("   ", n)
