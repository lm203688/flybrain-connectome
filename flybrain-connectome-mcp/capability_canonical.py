"""Canonical capability taxonomy for the 116 functional units (T2).

The raw ``capability`` field accumulated **331 distinct free-text values (300
used exactly once)** — a catalogue, not a retrieval axis.  This module pins
**22 canonical capability categories** (20 functional + ``provenance_marker``
+ ``other_unspecified``) and provides a deterministic
``classify()`` that maps any capability string to exactly one category.
Every capability maps to *some* category (including ``other_unspecified``), so
coverage is 100% by construction; the ``confidence`` flag tells a reader how
much to trust the auto-assignment.

This is the single source of truth consumed by Gate 21
(``scripts/check_capability_canonical.py``) and used to build
``docs/capability_coverage.json`` (the 21 x clade readiness matrix from the
foundation roadmap T2).

Design notes
------------
- The classifier is **token-based**: a capability string is split on ``_`` and
  each token is looked up in a priority-ordered token table.  This fixes the
  substring-direction bug that made keyword rules like ``"associative_learn"
  in "associate"`` miss (the keyword is *longer* than the string).
- Two values (``traced_connectome``, ``measure_synapses``) are **provenance
  markers that leaked into the capability field** — they describe how a unit
  was *derived* (from a traced connectome / with measured synapse counts), not
  what the unit *does*.  They are routed to a dedicated ``provenance_marker``
  category so the contamination is visible and can be cleaned at source rather
  than silently miscategorised.
- Borderline calls land in ``other_unspecified`` with ``confidence: low`` so
  the gap is visible rather than silently miscategorised.

Honest limit: with 300 singletons the vocabulary is genuinely free-text.  This
classifier buys a *retrieval axis*, not a *replacement* for curation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

MCP = Path(__file__).resolve().parent
UNITS = MCP / "functional_units" / "functional_units.json"

# ---------------------------------------------------------------------------
# The 22 canonical capability categories (20 functional + provenance_marker
# + other_unspecified).
# ---------------------------------------------------------------------------
CANONICAL: dict[str, dict] = {
    "provenance_marker":     {"label": "Provenance marker (NOT a capability)", "definition": "Evidence/method annotation that leaked into the capability field (e.g. traced_connectome, measure_synapses). Describes how a unit was derived, not what it does. Flagged for source-side cleanup."},
    "sensory_transduce":     {"label": "Sensory transduction",     "definition": "Convert an external physical stimulus into a neural signal (phototransduction, olfaction, mechanosensation, audition, electroreception, thermosensation, taste)."},
    "sensory_feature":       {"label": "Sensory feature extraction","definition": "Extract behaviourally-relevant features from sensory input (direction selectivity, motion, looming, target detection, optic flow, colour, temporal filtering)."},
    "relay_route":           {"label": "Relay / routing",          "definition": "Pass, route, or re-format signals between regions without heavy transformation (relay, projection, gateway, converge/diverge)."},
    "motor_rhythm_gen":      {"label": "Motor rhythm generation",  "definition": "Generate rhythmic or sequential motor patterns centrally (pacemakers, pattern generators, sequence generators, phase locking, entrainment)."},
    "motor_command":         {"label": "Motor command",            "definition": "Issue final actuation commands to effectors (escape, strike, steering, locomotion, posture, gaze, reflex arc)."},
    "associative_learning":  {"label": "Associative learning",     "definition": "Acquire or update stimulus-stimulus / action-outcome associations (Hebbian, reinforcement, prediction, error teaching, credit assignment)."},
    "memory_storage":        {"label": "Memory storage / readout", "definition": "Store and read out experienced facts, maps, or episodes (episodic, spatial, declarative, place/topographic codes)."},
    "working_memory":        {"label": "Working memory",           "definition": "Maintain a transient state online for the current task (buffering, rehearsal, conflict holding, reinstatement)."},
    "attention_gain":        {"label": "Attention / gain control", "definition": "Select or scale signal routes (inhibitory gain, visual gain, centrifugal feedback, multimodal binding, cross-modal arbitration)."},
    "valuation":             {"label": "Valuation",                "definition": "Compute reward, value, or affective broadcast that biases other systems (value/valence broadcast, mood, salience)."},
    "action_selection":      {"label": "Action selection",         "definition": "Choose among competing actions (facilitation, suppression, arbitration, gating, bistable switching)."},
    "cognitive_control":     {"label": "Cognitive control",        "definition": "Metacognitive / executive oversight (confidence evaluation, state switching, uncertainty, effort, self-monitoring)."},
    "inhibitory_control":    {"label": "Inhibitory control",       "definition": "Active gating / suppression that shapes dynamics (lateral inhibition, feedforward inhibition, shunting)."},
    "arousal_state":         {"label": "Arousal / state regulation","definition": "Set global brain state (arousal, cholinergic tone, circadian, sleep-wake)."},
    "emotional_state":       {"label": "Emotional state",          "definition": "Affective / defensive / social-affective states (mood, threat, fear, social stress, pain)."},
    "homeostatic_reg":       {"label": "Homeostatic regulation",   "definition": "Regulate internal physiology to a set point (feeding, respiration, temperature, energy, metabolic)."},
    "navigation":            {"label": "Navigation",               "definition": "Build and use a spatial representation to move through the world (spatial map, heading, optic flow, path integration, proprioception)."},
    "communication":         {"label": "Communication",            "definition": "Produce or receive social / conspecific signals (vocal, song, courtship, camouflage, pheromone, social signalling)."},
    "interoception":         {"label": "Interoception",            "definition": "Represent internal body state via neuromodulators / glia (peptide, neurohormone, gliotransmission, calcium wave)."},
    "plasticity":            {"label": "Structural / synaptic plasticity", "definition": "Develop or rewire connectivity (reflex plasticity, developmental, adaptation, sensitisation, LTD)."},
    "other_unspecified":     {"label": "Other / unspecified",      "definition": "Capability present but not cleanly mapped to the 20 above; flagged for later curation."},
}

CANON_IDS = list(CANONICAL.keys())

# ---------------------------------------------------------------------------
# Exact-string overrides (checked before token matching).
# ---------------------------------------------------------------------------
EXACT_OVERRIDE: dict[str, str] = {
    "traced_connectome": "provenance_marker",
    "measure_synapses": "provenance_marker",
}

# ---------------------------------------------------------------------------
# Priority-ordered token table.  First category whose token set intersects the
# capability's tokens wins.  Order encodes specificity: feature extraction and
# rhythm generation are more specific than the generic "relay"/"sensory".
# ---------------------------------------------------------------------------
_PRIORITY_RULES: list[tuple[str, frozenset[str]]] = [
    ("sensory_feature", frozenset({
        "direction", "selectivity", "select", "motion", "looming", "loom",
        "collision", "target", "object", "onset", "detect", "feature",
        "extract", "classify", "separate", "background", "bump", "sharpen",
        "contrast", "sparsify", "temporal", "filter", "tonotopy",
        "amplify", "normalize", "split", "gather", "wide_field", "sum",
        "optic_flow", "expansion", "visual", "weak_field", "infrared",
        "tuning", "haltere", "saccade", "refine", "shunt", "all", "none",
    })),
    ("motor_rhythm_gen", frozenset({
        "rhythm", "oscillate", "circadian", "pace", "pacemaking", "sequence",
        "clock", "chain", "phase", "synchronise", "sync", "entrain",
        "timing", "burst", "pulse", "pattern", "generate", "modulate",
        "drive", "loop", "loop", "reciprocal", "fast_loop",
    })),
    ("motor_command", frozenset({
        "command", "motor", "leg", "wing", "muscle", "arm", "steering",
        "heading", "gaze", "posture", "strike", "escape", "startle", "reach",
        "swim", "flight", "balance", "flex", "reflex", "control", "locomotion",
        "coordinate", "segment", "joint", "tendon", "effector", "actuat",
        "distributed", "divergent", "reciprocal", "release", "issue",
        "descending", "ballistic", "fixed_action", "segmental", "syringeal",
        "prey", "capture", "turn", "contralateral",
    })),
    ("memory_storage", frozenset({
        "memory", "episodic", "spatial", "place", "topographic", "tactile",
        "map", "metric", "navigate", "navigation", "write", "readout",
        "dispatch", "encode", "reinstate", "context", "hold", "conflict",
        "patience", "tagging", "tag", "state", "tag", "ring", "attractor",
    })),
    ("working_memory", frozenset({
        "buffer", "rehearse", "manipulate", "working", "online",
    })),
    ("cognitive_control", frozenset({
        "confidence", "metacog", "executive", "switch", "effort",
        "self_monitor", "self_locate", "self", "uncertainty", "internal",
        "model", "high_order", "high_dim", "expand", "monitor", "evaluate",
        "assessment", "oversight", "metacognition", "represent", "top", "down",
        "explore", "variation", "order",
    })),
    ("valuation", frozenset({
        "value", "valence", "reward", "mood", "affective", "salience",
        "broadcast", "hardwired", "novelty", "effort", "preference",
        "appraise", "evaluate",
    })),
    ("action_selection", frozenset({
        "action", "select", "choose", "arbitrate", "competition",
        "courtship", "decision", "gate", "flip_flop", "bistable", "hysteresis",
        "facilitation", "suppress", "resolve", "conflict", "drive", "facilitate",
        "suppress", "switch",
    })),
    ("arousal_state", frozenset({
        "arousal", "cholinergic", "sleep", "wake", "diffuse", "global",
        "circadian", "state", "tonic",
    })),
    ("emotional_state", frozenset({
        "fear", "threat", "stress", "pain", "affect", "defense", "defensive",
        "protective", "social", "anxiety",
    })),
    ("plasticity", frozenset({
        "plasticity", "plastic", "adapt", "adaptation", "habituation",
        "sensitization", "ltd", "learn", "learning", "develop", "rewire",
        "long_term", "stabilise", "metaplastic", "shaping",
    })),
    ("interoception", frozenset({
        "peptide", "neurohormone", "hormone", "gliotransmission", "glia",
        "calcium", "wave", "interocept", "dopamine", "modulation", "neuromodulatory",
        "diffuse", "release", "burst", "amplitude", "eod",
    })),
    ("homeostatic_reg", frozenset({
        "feeding", "feed", "respiration", "respiratory", "thermoreg",
        "thermorecept", "homeostat", "energy", "satiety", "hunger", "metabolic",
        "body", "metabolic",
    })),
    ("navigation", frozenset({
        "heading", "optic_flow", "path", "integrate", "goal", "bearing",
        "course", "angular",         "proprioception", "gravity", "self_locate",
        "reafference", "reafferent", "cancel", "localize", "localise",
        "phototaxis", "looming", "escape", "efference", "copy", "compensatory",
    })),
    ("communication", frozenset({
        "vocal", "song", "courtship", "camouflage", "communication",
        "pheromone", "social", "signal", "signalling", "innate_odour",
        "odour", "broadcast",
    })),
    ("attention_gain", frozenset({
        "gain", "attention", "centrifugal", "feedback", "multimodal",
        "cross_modal", "bind", "arbitrate", "top_down", "lateral", "inhibit",
        "inhibitory", "disinhibit", "shunt", "gate", "normalise", "calibrate",
        "set", "modulate",
    })),
    ("inhibitory_control", frozenset({
        "inhibit", "inhibitory", "lateral", "feedforward", "suppress", "shunt",
        "disinhibit", "gating", "block",
    })),
    ("sensory_transduce", frozenset({
        "transduce", "phototransduction", "irradiance", "olfactory",
        "odorant", "odour", "chemosens", "chemo", "cochlear", "vestibular",
        "somatosens", "nociception", "thermal", "electrolocate", "wind",
        "taste", "touch", "acceleration", "appetitive", "innate", "encode",
        "sense", "sensing", "recept", "detect", "transduce", "transduction",
        "ingest", "high_res", "sparse", "dc", "luminance", "weak_field",
        "chemosensation", "thermoreception",
    })),
    ("relay_route", frozenset({
        "relay", "route", "projection", "gateway", "merge", "converge",
        "diverge", "expand", "channel", "parallel", "somatotopic", "touch",
        "respiratory", "auditory", "mechano", "motor", "visual", "photorelay",
        "bimanual", "route", "output", "multi_target", "descend", "conduction",
        "mixed", "fast",
    })),
    ("associative_learning", frozenset({
        "associate", "associative", "auto", "supervised", "predictive",
        "fear", "condition", "credit", "error", "teach", "teaching",
        "learning_rate", "reinforce",         "learn", "hebbian", "motor_learning", "rpe", "compute",
    })),
]

# Tokens that should be ignored entirely (too generic to be informative).
_STOP = frozenset({"the", "a", "of", "to", "and", "is", "in", "for", "with", "or"})


def _tokens(cap: str) -> list[str]:
    return [t for t in cap.lower().split("_") if t and t not in _STOP]


def classify(capability: str) -> tuple[str, str]:
    """Return (canonical_id, confidence) for a capability string.

    confidence is ``high`` when an exact override or token hit matched,
    ``low`` when it fell through to ``other_unspecified``.
    """
    cap = (capability or "").strip().lower()
    if not cap:
        return "other_unspecified", "low"
    if cap in EXACT_OVERRIDE:
        return EXACT_OVERRIDE[cap], "high"
    toks = set(_tokens(cap))
    for cat, cat_tokens in _PRIORITY_RULES:
        if toks & cat_tokens:
            return cat, "high"
    return "other_unspecified", "low"


def classify_unit(unit: dict) -> tuple[str, str, list[str]]:
    """Return (primary_category, confidence, all_categories) for a unit dict.

    A unit may have multiple capabilities; the primary is the first
    non-provenance category (provenance markers are metadata, not function).
    """
    caps = unit.get("capability", [])
    if isinstance(caps, str):
        caps = [caps]
    if not caps:
        return "other_unspecified", "low", []

    all_cats: list[str] = []
    confidences: list[str] = []
    for cap in caps:
        cat, conf = classify(cap)
        all_cats.append(cat)
        confidences.append(conf)

    # Primary = first non-provenance category (provenance is metadata)
    primary = "other_unspecified"
    for c in all_cats:
        if c != "provenance_marker":
            primary = c
            break

    # Confidence is the min across functional capabilities only
    func_confs = [confidences[i] for i, c in enumerate(all_cats) if c != "provenance_marker"]
    conf = min(func_confs, key=lambda c: ["low", "medium", "high"].index(c)) if func_confs else "low"
    return primary, conf, all_cats


def load_units() -> list[dict]:
    doc = json.loads(UNITS.read_text(encoding="utf-8"))
    return doc["units"] if isinstance(doc, dict) else doc


def build_map() -> dict[str, dict]:
    """Map every unit name -> {primary_category, confidence, all_categories}."""
    out: dict[str, dict] = {}
    for u in load_units():
        primary, conf, all_cats = classify_unit(u)
        out[u["name"]] = {
            "primary_category": primary,
            "confidence": conf,
            "all_categories": all_cats,
        }
    return out


def build_capability_map() -> dict[str, dict]:
    """Map every capability string -> {category, confidence}."""
    units = load_units()
    cap_map: dict[str, dict] = {}
    for u in units:
        caps = u.get("capability", [])
        if isinstance(caps, str):
            caps = [caps]
        for cap in caps:
            if cap not in cap_map:
                cat, conf = classify(cap)
                cap_map[cap] = {"category": cat, "confidence": conf}
    return cap_map


def provenance_contamination() -> dict:
    """Report provenance markers that leaked into the capability field.

    Returns {marker: [unit_names...]} so the source-side data can be cleaned
    without silently discarding the signal.
    """
    out: dict[str, list[str]] = {}
    for u in load_units():
        caps = u.get("capability", [])
        if isinstance(caps, str):
            caps = [caps]
        for cap in caps:
            cat, _ = classify(cap)
            if cat == "provenance_marker":
                out.setdefault(cap, []).append(u["name"])
    return out


def clade_of(unit: dict) -> str:
    """Coarse clade for the readiness matrix (species_source or system)."""
    src = unit.get("species_source") or unit.get("system") or "unknown"
    s = str(src).lower()
    if "fly" in s or "drosophil" in s or "male_cns" in s:
        return "insect"
    if "worm" in s or "c. elegans" in s or "c_elegans" in s:
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
    cap_mp = build_capability_map()
    from collections import Counter

    # Category distribution
    c = Counter(v["primary_category"] for v in mp.values())
    print("Primary category coverage: %d/%d units across %d categories"
          % (len(mp), len(mp), len(c)))
    for cid in CANON_IDS:
        print("  %-24s %3d" % (cid, c.get(cid, 0)))

    # Confidence distribution
    conf = Counter(v["confidence"] for v in mp.values())
    print("\nConfidence distribution:")
    for level in ["high", "medium", "low"]:
        print("  %-8s %3d" % (level, conf.get(level, 0)))

    # Capability-level classification
    cap_conf = Counter(v["confidence"] for v in cap_mp.values())
    print("\nCapability string classification (%d unique):" % len(cap_mp))
    for level in ["high", "low"]:
        print("  %-8s %3d" % (level, cap_conf.get(level, 0)))

    # Low-confidence capabilities
    low_caps = [cap for cap, v in cap_mp.items() if v["confidence"] == "low"]
    print("\nLow-confidence capabilities (other_unspecified):", len(low_caps))
    for cap in sorted(low_caps)[:25]:
        print("   ", cap)
    if len(low_caps) > 25:
        print("   ... and %d more" % (len(low_caps) - 25))

    # Provenance contamination
    contam = provenance_contamination()
    print("\nProvenance markers leaked into capability field:")
    for marker, units in sorted(contam.items()):
        print("  %-22s %3d units: %s" % (marker, len(units), ", ".join(units[:3]) + ("..." if len(units) > 3 else "")))
