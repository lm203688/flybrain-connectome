"""gen_functional_units.py -- author the two composition libraries.

Writes (single source of truth, stdlib-only JSON):
    flybrain-connectome-mcp/functional_units/functional_units.json    (101 units)
    flybrain-connectome-mcp/functional_units/connection_types.json    (66 types)

CLADE COVERAGE (v1.4.1)
-----------------------
The library is no longer mammal-cortex shaped. 16 of the 72 units carry
functions with no vertebrate-cortex equivalent, because the point of the
library is combinatorial coverage of the whole animal kingdom, not of one
brain: insect (mushroom body, antennal lobe, central complex, clock), bird
(song system), fish (Mauthner escape, active/passive electroreception, EOD
pacemaker) and cephalopod (vertical lobe, chromatophore, arm cord). Drosophila
is the starting point, not the target.

COMPUTATIONAL-ROLE COVERAGE (v1.6.0)
------------------------------------
The second 16 units add what the first 56 silently lacked: autonomous rhythm
with no cortex (half-centre oscillation, plateau bistability), a real two-state
machine (sleep/wake flip-flop), a supervised error path (climbing fibre ->
Purkinje LTD), plus peripheral segmental CPGs, infrared/amphibian prey capture,
hippocampal replay-style navigation and active touch.

EMBODIMENT (v1.7.0)
-------------------
Everything above is curated from literature, and the library carried a
permanent hole: nothing had ever been checked against the real connectome it is
named after. `malecns_anchors.json` (built by scripts/build_malecns_anchors.py)
maps library neuron populations onto real annotated MaleCNS v1.0 cell types and
measures the real superclass connectivity backbone. Each unit therefore carries
an `embodiment` block, and `provenance.embodied_in_malecns` is true only when at
least one member population resolves to real annotated cells.

`extracted_from_malecns` stays FALSE for every unit. Anchoring proves the parts
exist and that a declared pathway is not *contradicted* at superclass
resolution. It does not prove the declared microcircuit or its connection FORM.

DROSOPHILA-SHAPED DENSIFICATION (v1.8.0)
----------------------------------------
v1.7.0 exposed the honest gap: only 6 of 72 units were embodied, and only
fly-shaped units can be falsified by the fly connectome. The ten v1.8.0 units
(optic lobe x5, giant-fiber escape, courtship x2, song reception, lateral horn)
are built from 20 new profiles that ALL carry anchor rules, and their wiring
was checked against the measured profile x profile matrix before being written:
no declared edge is a zero.

WHY A GENERATOR AND NOT HAND-WRITTEN JSON
-----------------------------------------
Every functional unit's `members` reference neuron keys that MUST exist in
synthetic_bio_topology.MODULE_PROFILES, and every `internal_wiring` edge MUST
reference a connection type that exists in connection_types.json. Hand-writing
120 KB of JSON would let a typo (`pyramidal_l5b` vs `pyramidal_l5bt`) ship as a
silently dead module. The generator loads MODULE_PROFILES first and refuses to
write if any reference is dangling -- so the artifacts can never drift from the
neuron library they are built on.

CONCEPT (user-defined, 2026-09-23)
----------------------------------
The minimum composable unit is a FUNCTION, not a neuron. A functional unit is a
group of one-or-more neuron populations wired into a sub-circuit that delivers
one function, exposing typed ports. Connection types are the second library: the
minimum composable CONNECTION is a connection form, likewise typed on ports.

    virtual organism = units (nodes) + connection types (typed edges)

Ports carry a `type` drawn from PORT_TYPES; a connection type constrains which
port types it may join. Composition is therefore checkable mechanically instead
of by eyeball.
"""
from __future__ import annotations
import hashlib
import re
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path("C:/Users/xing/Desktop/flybrain-connectome")
MCP = ROOT / "flybrain-connectome-mcp"
OUT_DIR = MCP / "functional_units"
ANCHORS_FILE = OUT_DIR / "malecns_anchors.json"

# Contradictions between a declared unit edge and the measured connectome.
# Each entry MUST carry a reason. The generator REFUSES to write when the set of
# contradictions it measured differs from this list -- so a new one cannot ship
# silently, and an acknowledged one cannot quietly disappear either. Nothing here
# is "supported": a listed edge is a literature claim that the real data does not
# show, and it is recorded so it is never cited as if it were.
ACKNOWLEDGED_CONTRADICTIONS = [
    {"unit": "central_complex_steering_unit", "edge": "nod->fb",
     "reason": "The noduli population resolves to only 5 Nod cell types / 12 real "
               "cells, and the dataset files them under `visual_projection` rather "
               "than cb_intrinsic. MaleCNS v1.0 contains no Nod -> PFN/FS/FC synapses, "
               "so this declared projection is UNSUPPORTED at this resolution. Kept "
               "because it is a literature claim about the central complex, not a claim "
               "about this release's connectivity; a fix requires resolving the noduli "
               "population properly, which is future work."},
]


_PROFILES_CACHE: dict | None = None


def _load_profiles() -> dict:
    # v2.27.0: cached. `synthetic_bio_topology.py` builds a fresh module dict
    # on every exec, so a caller that registered extra profiles into the first
    # copy would see them vanish in the next copy. One shared dict, one build.
    global _PROFILES_CACHE
    if _PROFILES_CACHE is not None:
        return _PROFILES_CACHE
    spec = importlib.util.spec_from_file_location(
        "sbt_for_units", str(MCP / "synthetic_bio_topology.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sbt_for_units"] = mod
    spec.loader.exec_module(mod)
    _PROFILES_CACHE = mod.MODULE_PROFILES
    return _PROFILES_CACHE


# ====================================================================== #
# 0. PORT TYPE VOCABULARY -- the contract that makes composition checkable
# ====================================================================== #
PORT_TYPES = {
    "sensory.visual":        "Photoreceptor-driven visual signal (retina -> thalamus).",
    "sensory.visual.motion": "Direction/motion-selective visual signal.",
    "sensory.visual.irradiance": "Slow luminance signal (circadian drive).",
    "sensory.olfactory":     "Odourant identity/intensity signal.",
    "sensory.auditory":      "Sound-frequency signal.",
    "sensory.vestibular":    "Head acceleration signal.",
    "sensory.somatosensory": "Touch/proprioceptive signal.",
    "sensory.nociceptive":   "Noxious-stimulus signal.",
    "cortex.input":          "Cortical layer-4 style afferent input.",
    "cortex.association":    "Higher-order intracortical association signal.",
    "cortex.output":         "Cortical layer-5 style descending command.",
    "cortex.feedback":       "Top-down corticofugal feedback.",
    "cortex.interneuron":    "Local cortical inhibitory drive.",
    "cerebellar.input":      "Mossy-fibre style cerebellar input.",
    "cerebellar.output":     "Purkinje / deep-nucleus cerebellar output.",
    "error.teaching":        "Climbing-fibre error / teaching signal.",
    "hippocampal.input":     "Entorhinal cortical input to hippocampus.",
    "hippocampal.engram":    "Recurrently stored memory trace.",
    "hippocampal.output":    "Hippocampal output to cortex.",
    "spatial.map":           "Self-locating spatial representation.",
    "basal_ganglia.value":   "Action-value / reward-prediction signal.",
    "basal_ganglia.command": "Selected-action disinhibitory command.",
    "limbic.fear":           "Threat-conditioned affective signal.",
    "rhythm.theta":          "Theta-band oscillatory drive.",
    "rhythm.circadian":      "Circadian phase signal.",
    "arousal.state":         "Wake/sleep arousal-state signal.",
    "motor.command":         "Descending motor command.",
    "motor.spindle":         "Muscle-spindle feedback.",
    "modulatory.dopamine":   "Dopaminergic diffuse modulation.",
    "modulatory.serotonin":  "Serotonergic diffuse modulation.",
    "modulatory.acetylcholine": "Cholinergic diffuse modulation.",
    "modulatory.noradrenaline": "Noradrenergic diffuse modulation.",
    "modulatory.histamine":  "Histaminergic diffuse modulation.",
    "modulatory.orexin":     "Orexinergic arousal-stability modulation.",
    "glial.support":         "Astrocytic metabolic / gliotransmitter support.",
    "sensory.*":             "Wildcard: any sensory port (used by relay units).",
    "modulatory.*":          "Wildcard: any modulatory port (used by relay units).",
    "*":                     "Wildcard: any port type (used by generic forms).",
}

# Port types that are `in`-only / `out`-only semantics are NOT enforced here;
# the composer checks direction, the unit declares which side a port lives on.

# ---------------------------------------------------------------------------
# v2.25.0 -- port_types_classified: assign every PORT_TYPE to a bio_evidence
# category derived from its name prefix.  PORT_TYPES itself is a plain
# name -> description dict, so we emit a parallel dict in the JSON that
# carries {description, category} for each port.  Categories are:
#   sensory_input      -- external-stimulus afferent channels (retina,
#                         olfactory bulb, lateral line, whisker, ...)
#   motor_output       -- descending command to muscles / organs
#   modulatory         -- diffuse neuromodulatory / endocrine systems
#   cortical_processing-- forebrain-style associative / memory circuits
#   spatial_temporal   -- position / heading / clock / rhythm codes
#   state_regulatory   -- arousal / gate / error / efference-copy signals
#   glial_support      -- non-neuronal (astrocytic) modulation
#   wildcard           -- the "*" or "family.*" match-all placeholders
# The category is a name-derived label, not a literature-derived claim.
# It lets downstream tools route ports by function without parsing names.
# ---------------------------------------------------------------------------
_PORT_CATEGORY_RULES = [
    # Order matters: first match wins.  Longer / more specific prefixes first.
    ("sensory.",         "sensory_input"),
    ("olfactory.",       "sensory_input"),
    ("motor.",           "motor_output"),
    ("modulatory.",      "modulatory"),
    ("cortex.",          "cortical_processing"),
    ("cerebellar.",      "cortical_processing"),
    ("hippocampal.",     "cortical_processing"),
    ("basal_ganglia.",   "cortical_processing"),
    ("limbic.",          "cortical_processing"),
    ("spatial.",         "spatial_temporal"),
    ("navigation.",      "spatial_temporal"),
    ("clock.",           "spatial_temporal"),
    ("memory.",          "spatial_temporal"),
    ("rhythm.",          "spatial_temporal"),
    ("thermal.",         "spatial_temporal"),
    ("arousal.",         "state_regulatory"),
    ("gating.",          "state_regulatory"),
    ("error.",           "state_regulatory"),
    ("efference.",       "state_regulatory"),
    ("reafference.",     "state_regulatory"),
    ("glial.",           "glial_support"),
]


def _classify_port_types():
    """Return {port_name: {description, category}} for every PORT_TYPES entry."""
    out = {}
    for name, desc in PORT_TYPES.items():
        cat = "wildcard"
        if name != "*":
            for prefix, category in _PORT_CATEGORY_RULES:
                if name.startswith(prefix):
                    cat = category
                    break
        out[name] = {"description": desc, "category": cat}
    return out


# ====================================================================== #
# 1. CONNECTION TYPES -- 50 composable connection forms
# ====================================================================== #
def C(name, family, display, desc, frm, to, sign, fanout, span, delay,
      plastic=False, motif_ref=None, params=None, ref=""):
    return {
        "name": name,
        "family": family,
        "display": display,
        "description": desc,
        "from_port": frm,
        "to_port": to,
        "sign": sign,                       # + / - / +/- / mod
        "fanout": fanout,                   # one_to_one|one_to_many|many_to_one|many_to_many
        "span": span,                       # intra_unit | inter_unit | either
        "delay_class": delay,               # immediate | short | long
        "plastic": plastic,
        "motif_ref": motif_ref,             # motif name in the 40-motif doc, or None
        "parameters": params or {},
        "biological_reference": ref,
    }


CONNECTION_TYPES = [
    # ---------------- micro: point-to-point chemical synaptic forms (10) ----
    C("axo_dendritic", "micro", "轴突-树突突触",
      "Axon terminal onto dendritic shaft/spine; the default cortical excitatory contact.",
      "*", "*", "+", "one_to_one", "either", "immediate", True,
      "axo_dendritic", {"release_probability": 0.3, "quantal_size": 1.0},
      "Gray 1959; Peters & Palay 1991"),
    C("axo_somatic", "micro", "轴突-胞体突触",
      "Axon terminal onto soma; perisomatic, strongly shunting (basket-cell style).",
      "*", "*", "-", "one_to_many", "either", "immediate", False,
      "axo_somatic", {"shunt_gain": 0.9}, "Freund & Katona 2007"),
    C("axo_axonic", "micro", "轴突-轴突突触",
      "Axon terminal onto the axon initial segment; gates spike initiation without touching the soma.",
      "*", "*", "-", "one_to_one", "either", "immediate", False,
      "axo_axonic", {"spike_block_probability": 0.7}, "chandelier cells, Szabadics 2006"),
    C("dendro_dendritic", "micro", "树突-树突突触",
      "Direct dendro-dendritic contact; allows subthreshold crosstalk and reciprocal pairs.",
      "*", "*", "+/-", "one_to_one", "intra_unit", "short", True,
      "dendro_dendritic", {"crosstalk_gain": 0.4}, "Shepherd 2004"),
    C("axo_dendrite_reciprocal", "micro", "轴-树交互突触",
      "Reciprocal pair: one direction excitatory, the return direction inhibitory (olfactory-bulb style).",
      "*", "*", "+/-", "one_to_one", "intra_unit", "short", True,
      "axo_dendrite_reciprocal", {"exc_gain": 0.6, "inh_gain": 0.5},
      "Rall et al 1966; olfactory bulb mitral/granule pair"),
    C("pre_presynaptic_inhibition", "micro", "突触前抑制",
      "Inhibition applied to a presynaptic terminal; attenuates release downstream.",
      "*", "*", "-", "one_to_many", "either", "short", True,
      "pre_presynaptic_inhibition", {"release_suppression": 0.5}, "axo-axonic GABA-B"),
    C("pre_presynaptic_excitation", "micro", "突触前易化",
      "Excitation applied to a presynaptic terminal; boosts release probability.",
      "*", "*", "+", "one_to_many", "either", "short", True,
      "pre_presynaptic_excitation", {"release_facilitation": 0.4}, "nicotinic presynaptic facilitation"),
    C("dendritic_excitatory_synapse", "micro", "树突兴奋性突触",
      "Excitatory contact placed on a specific dendritic branch; branch-local integration.",
      "*", "*", "+", "one_to_one", "either", "immediate", True,
      "dendritic_excitatory_synapse", {"branch_gain": 1.2}, "Larkum 2013"),
    C("dendritic_inhibitory_synapse", "micro", "树突抑制性突触",
      "Inhibitory contact on a dendritic branch; vetoes a branch without somatic shunting.",
      "*", "*", "-", "one_to_one", "either", "immediate", True,
      "dendritic_inhibitory_synapse", {"branch_veto": 0.8}, "Miles 1990"),
    C("autapse_recurrent", "micro", "自突触",
      "A population connects to itself with a gain < 1; local persistence without a loop node.",
      "*", "*", "+/-", "many_to_many", "intra_unit", "immediate", True,
      None, {"self_gain": 0.35}, "Bekkers 2003; cortical autapses"),

    # ---------------- circuit: multi-neuron motifs (15) ---------------------
    C("feedforward_excitatory", "circuit", "前馈兴奋",
      "A -> B -> C all excitatory; signal relayed and sharpened across stages.",
      "*", "*", "+", "one_to_many", "inter_unit", "short", True,
      "feedforward_excitatory", {"stage_gain": 1.1}, "canonical cortical FF drive"),
    C("feedforward_inhibitory", "circuit", "前馈抑制",
      "Input excites both a target and an interneuron that inhibits the target; narrows the time window.",
      "*", "*", "-", "one_to_many", "either", "immediate", False,
      "feedforward_inhibitory", {"window_ms": 15}, "Pouille & Scanziani 2001"),
    C("feedforward_gating", "circuit", "前馈门控",
      "A gating population multiplicatively admits or blocks a throughput path.",
      "cortex.association", "*", "mod", "one_to_many", "inter_unit", "immediate", False,
      "feedforward_gating", {"gate_open": 1.0, "gate_closed": 0.0}, "attention gating"),
    C("feedback_excitatory", "circuit", "反馈兴奋",
      "Higher stage re-excites an earlier stage; sustains and amplifies a representation.",
      "*", "*", "+", "one_to_many", "inter_unit", "long", True,
      "feedback_excitatory", {"feedback_gain": 0.7}, "corticothalamic feedback"),
    C("feedback_inhibitory", "circuit", "反馈抑制",
      "Higher stage returns inhibition to an earlier stage; predictive suppression.",
      "*", "*", "-", "one_to_many", "inter_unit", "long", True,
      "feedback_inhibitory", {"feedback_gain": 0.6}, "predictive coding"),
    C("lateral_inhibitory", "circuit", "侧抑制",
      "Neighbouring units inhibit each other; sharpens contrast and sparsifies the code.",
      "*", "*", "-", "one_to_many", "inter_unit", "short", False,
      "lateral_inhibitory", {"inhibition_radius": 3}, "Hartline & Ratliff 1958 (Limulus)"),
    C("lateral_feedback", "circuit", "侧向反馈",
      "Lateral partner both feeds forward and receives feedback; forms a resonant ring.",
      "*", "*", "+/-", "many_to_many", "inter_unit", "short", True,
      "lateral_feedback", {"resonance_gain": 0.5}, "cortical lateral connectivity"),
    C("mutual_inhibitory", "circuit", "交互抑制",
      "Two populations inhibit each other; produces winner-take-all or alternation.",
      "*", "*", "-", "one_to_one", "intra_unit", "immediate", False,
      "mutual_inhibitory", {"balance": 1.0}, "half-centre oscillator"),
    C("recurrent_excitatory", "circuit", "循环兴奋",
      "Population excites itself through a loop; attractor / persistent activity.",
      "*", "*", "+", "many_to_many", "intra_unit", "short", True,
      "recurrent_excitatory", {"loop_gain": 0.85}, "Hopfield 1982; persistent activity"),
    C("recurrent_inhibitory", "circuit", "循环抑制",
      "Loop where inhibition dominates; keeps activity bounded and rhythmic.",
      "*", "*", "-", "many_to_many", "intra_unit", "short", True,
      "recurrent_inhibitory", {"loop_gain": 0.8}, "interneuron-stabilised networks"),
    C("disinhibition", "circuit", "去抑制",
      "A -> interneuron -| target: exciting the interneuron releases the target.",
      "*", "*", "+", "one_to_one", "intra_unit", "short", False,
      "disinhibition", {"release_gain": 0.9}, "VIP -> SST -> pyramidal (cortex)"),
    C("shunting_inhibition", "circuit", "分流抑制",
      "Inhibition lowers input resistance rather than hyperpolarising; divisive gain control.",
      "*", "*", "-", "one_to_many", "either", "immediate", False,
      "shunting_inhibition", {"conductance_gain": 1.5}, "Carandini & Heeger 2012"),
    C("contrast_inhibition", "circuit", "对比度抑制",
      "Inhibition proportional to local stimulus energy; normalises the population response.",
      "*", "*", "-", "many_to_one", "intra_unit", "short", False,
      "contrast_inhibition", {"normalisation_exponent": 2.0}, "Heeger 1992"),
    C("winner_take_all", "circuit", "赢者通吃",
      "Global inhibitory pool lets the strongest unit suppress the rest; selection operator.",
      "*", "*", "-", "many_to_many", "inter_unit", "short", False,
      None, {"k_winners": 1, "inhibition_slope": 2.0}, "Maass 2000 (WTA circuits)"),
    C("loop_relay_chain", "circuit", "串联中继链",
      "Strictly ordered series of relays; each stage passes a transformed copy onward.",
      "*", "*", "+", "one_to_one", "inter_unit", "long", False,
      None, {"max_stages": 8, "per_stage_loss": 0.1}, "sensory relay chains"),

    # ---------------- modulatory (6) --------------------------------------- #
    C("modulatory_diffuse", "modulatory", "弥散调制",
      "One modulatory source broadcasts a scalar gain over many targets; no point-to-point map.",
      "modulatory.*", "*", "mod", "one_to_many", "inter_unit", "long", True,
      "modulatory_diffuse", {"gain_range": [0.5, 1.8]}, "neuromodulatory systems"),
    C("neuromodulatory_axon", "modulatory", "调节性轴突",
      "Axon with en-passant varicosities releasing along its length, not at one terminal.",
      "modulatory.*", "*", "mod", "one_to_many", "either", "long", True,
      "neuromodulatory_axon", {"varicosity_count": 12}, "Descarries 1998"),
    C("volume_transmission", "modulatory", "容积传递",
      "Transmitter diffuses through extracellular space and reaches non-synaptic receptors.",
      "modulatory.*", "*", "mod", "one_to_many", "either", "long", False,
      "volume_transmission", {"diffusion_radius": 50.0, "decay_tau": 400.0},
      "Fuxe 2010; Agnati 1995"),
    C("short_range_volume", "modulatory", "短程容积传递",
      "Locally confined diffusion; a middle case between a synapse and full volume release.",
      "modulatory.*", "*", "mod", "one_to_many", "intra_unit", "short", False,
      "short_range_volume", {"diffusion_radius": 8.0}, "Sahlender 2014"),
    C("retrograde_messenger", "modulatory", "逆行信使",
      "Postsynaptic cell releases a messenger that acts back on the presynaptic terminal.",
      "*", "*", "mod", "one_to_one", "intra_unit", "short", True,
      "retrograde_messenger", {"messenger": "endocannabinoid", "effect": "suppress_release"},
      "endocannabinoid system (Wilson & Nicoll 2001)"),
    C("state_gating_modulation", "modulatory", "状态门控调制",
      "A global state variable (arousal, phase) multiplies whole-pathway throughput.",
      "arousal.state", "*", "mod", "one_to_many", "inter_unit", "long", False,
      None, {"state_gain_curve": "sigmoid"}, "state-dependent gating"),

    # ---------------- electrical / glial (5) ------------------------------- #
    C("gap_junction_sync", "electrical", "电突触同步",
      "Bidirectional electrotonic coupling; equalises membrane potential, zero delay.",
      "*", "*", "+/-", "many_to_many", "either", "immediate", False,
      "gap_junction_sync", {"coupling_conductance": 0.2}, "connective connexin coupling"),
    C("gap_junction_inhibitory", "electrical", "抑制性电耦合",
      "Gap junction onto an inhibitory population; synchronises the local brake.",
      "*", "*", "-", "many_to_many", "intra_unit", "immediate", False,
      "gap_junction_inhibitory", {"coupling_conductance": 0.15}, "GABAergic gap junctions"),
    C("ephaptic_coupling", "electrical", "电场耦合",
      "Non-synaptic field coupling; activity in one fibre changes the excitability of a "
      "neighbour. Span is 'either', because a field does not respect a unit boundary -- an "
      "electric organ drives its own receptors across tissues.",
      "*", "*", "+/-", "many_to_many", "either", "immediate", False,
      "ephaptic_coupling", {"field_gain": 0.05}, "ephaptic coupling (Anastassiou 2011)"),
    C("astrocyte_neuron_tripartite", "electrical", "星形胶质三方突触",
      "Astrocyte senses synaptic activity and returns a slow modulatory signal.",
      "glial.support", "*", "mod", "one_to_many", "either", "long", True,
      "astrocyte_neuron_tripartite", {"response_tau": 2000.0}, "Araque 1999 tripartite synapse"),
    C("gliotransmission_calcium_wave", "electrical", "胶质钙波传递",
      "Calcium wave propagates through the astrocytic syncytium, carrying a slow signal.",
      "glial.support", "*", "mod", "one_to_many", "inter_unit", "long", False,
      None, {"wave_speed_um_s": 20.0}, "Cornell-Bell 1990 calcium waves"),

    # ---------------- plasticity (5) --------------------------------------- #
    C("stdp_rule", "plasticity", "STDP 规则",
      "Pre-before-post potentiates, post-before-pre depresses; timing-based weight change.",
      "*", "*", "+/-", "one_to_one", "either", "long", True,
      "stdp_rule", {"a_plus": 0.01, "a_minus": 0.012, "tau_plus": 20.0, "tau_minus": 20.0},
      "Bi & Poo 1998"),
    C("ltp_ltd", "plasticity", "长时程增强/抑制",
      "Sustained activity produces durable bidirectional weight change.",
      "*", "*", "+/-", "one_to_one", "either", "long", True,
      "ltp_ltd", {"ltd_threshold_hz": 1.0, "ltp_threshold_hz": 20.0}, "Bliss & Lomo 1973"),
    C("short_term_plasticity", "plasticity", "短时可塑性",
      "Vesicle depletion / residual calcium give seconds-scale facilitation or depression.",
      "*", "*", "+/-", "one_to_one", "either", "immediate", True,
      "short_term_plasticity", {"facilitation_tau": 200.0, "depression_tau": 800.0},
      "Zucker & Regehr 2002"),
    C("dendritic_computation", "plasticity", "树突计算",
      "Non-linear dendritic integration (NMDA spikes, plateau potentials) as a local operator.",
      "*", "*", "+", "many_to_one", "intra_unit", "short", True,
      "dendritic_computation", {"nmda_threshold": 3, "plateau_ms": 300},
      "London & Hausser 2005"),
    C("homeostatic_scaling", "plasticity", "稳态缩放",
      "Slow multiplicative rescaling of all weights to hold a firing-rate set-point.",
      "*", "*", "+/-", "many_to_many", "intra_unit", "long", False,
      None, {"target_rate_hz": 5.0, "scaling_tau_hours": 24.0}, "Turrigiano 1998"),

    # ---------------- macro: projection / population geometry (9) ---------- #
    C("topographic_mapping", "macro", "拓扑映射",
      "Spatially ordered projection preserving neighbourhood relations across stages.",
      "*", "*", "+", "one_to_one", "inter_unit", "short", False,
      "topographic_mapping", {"jitter_sigma": 0.1, "dimensions": 2}, "retinotopy / somatotopy"),
    C("temporal_coherence", "macro", "时间一致性绑定",
      "Co-active populations phase-align; binding by synchrony rather than by weight.",
      "*", "*", "+/-", "many_to_many", "inter_unit", "immediate", False,
      "temporal_coherence", {"band_hz": [30.0, 80.0]}, "Singer & Gray 1995"),
    C("inhibitory_hub", "macro", "抑制枢纽广播",
      "A single inhibitory hub broadcasts to a very large target set (MaleCNS-extracted).",
      "*", "*", "-", "one_to_many", "inter_unit", "short", False,
      "inhibitory_hub", {"hub_fanout": "dominant"}, "MaleCNS v1.0 APL (fan-out 102,263)"),
    C("reservoir_smallworld", "macro", "小世界储层",
      "High-clustering, short-path recurrent pool used as a random-feature reservoir (MaleCNS-extracted).",
      "*", "*", "+", "many_to_many", "intra_unit", "short", False,
      "reservoir_smallworld", {"clustering": 0.35, "path_length": 2.4},
      "MaleCNS v1.0 ol_intrinsic reservoir"),
    C("recurrent_feedback", "macro", "循环反馈回路",
      "Closed loop between two stages with a delay; the MaleCNS-extracted third original motif.",
      "*", "*", "+/-", "many_to_many", "inter_unit", "long", True,
      "recurrent_feedback", {"loop_delay_ms": 80}, "MaleCNS v1.0 recurrent feedback motif"),
    C("divergent_fanout", "macro", "发散投射",
      "One source drives many independent downstream populations; broadcast without feedback.",
      "*", "*", "+", "one_to_many", "inter_unit", "short", False,
      None, {"fanout_targets": 16}, "divergent projection systems"),
    C("convergent_fanin", "macro", "汇聚投射",
      "Many sources converge onto one target; the target sees an integrated sum.",
      "*", "*", "+", "many_to_one", "inter_unit", "short", False,
      None, {"fanin_sources": 16}, "convergent sensory convergence"),
    C("corollary_discharge", "macro", "传出副本",
      "A copy of a motor command is routed to a sensory/predictor unit alongside the action.",
      "motor.command", "*", "+", "one_to_many", "inter_unit", "immediate", False,
      None, {"copy_gain": 1.0}, "efference copy (von Holst & Mittelstaedt 1950)"),
    C("global_broadcast", "macro", "全局广播",
      "A command reaches every unit in the organism; used for reset, halt, or global gain.",
      "*", "*", "mod", "one_to_many", "inter_unit", "immediate", False,
      None, {"coverage": "all_units"}, "neuromodulatory global broadcast"),
]


# ====================================================================== #
# 2. FUNCTIONAL UNITS -- 56 units, each = one function, N neuron populations
# ====================================================================== #
def U(name, display, function, system, desc, members, wiring, in_ports, out_ports,
      size, capability, hints, lead, nts, ref, species, composes=()):
    return {
        "name": name,
        "display": display,
        "function": function,
        "system": system,
        "description": desc,
        "members": [{"role": r, "neuron": n, "count_ratio": c} for r, n, c in members],
        "internal_wiring": [{"from": f, "to": t, "type": ty, "weight": w}
                            for f, t, ty, w in wiring],
        "ports": {
            "in":  [{"name": n, "type": t, "required": req} for n, t, req in in_ports],
            "out": [{"name": n, "type": t, "required": req} for n, t, req in out_ports],
        },
        "size_range": list(size),
        "motif_source": sorted({ty for _f, _t, ty, _w in wiring}),
        "capability": list(capability),
        "task_hint_pool": list(hints),
        "lead_task_hint": lead,
        "neurotransmitter": list(nts),
        "species_source": list(species),
        "biological_reference": ref,
        "composable_with": list(composes),
        "provenance": {
            "class": "curated-cross-species",
            "extracted_from_malecns": False,
            "basis": "comparative-neuroscience literature, not a trained classifier",
        },
    }


FUNCTIONAL_UNITS = [
    # ================= SENSORY FRONT-ENDS (8) ================= #
    U("retinal_phototransduction_unit", "视网膜光转导单元", "phototransduction", "sensory",
      "锥体/杆体双极细胞把光强转为分级电位，经水平细胞做增益控制后由 midget 节细胞输出高分辨率空间信号。",
      [("cone_bp", "retinal_bipolar_cone", 0.30),
       ("rod_bp", "retinal_bipolar_rod", 0.35),
       ("gain", "retinal_horizontal", 0.20),
       ("output", "retina_midget_gc", 0.15)],
      [("cone_bp", "output", "feedforward_excitatory", 1.0),
       ("rod_bp", "output", "feedforward_excitatory", 0.8),
       ("gain", "output", "shunting_inhibition", 0.6),
       ("output", "gain", "feedback_excitatory", 0.4)],
      [("light", "sensory.visual", True)], [("high_res", "sensory.visual", True)],
      (6, 40), ["transduce", "photorelay", "gain_control", "high_res_encode"],
      ["image_ingest", "photoreceptor_encode", "retinal_gain"], "visual_ingest",
      ["glutamate", "gaba"], "Rodieck 1998; Masland 2012", ["mouse", "macaque", "human", "salamander"]),
    U("retinal_direction_selective_unit", "视网膜方向选择单元", "direction_selectivity", "sensory",
      "星爆无长突细胞的延迟抑制与双极细胞兴奋相遇，只对特定运动方向放电。",
      [("bp", "retinal_bipolar", 0.35),
       ("ac", "retinal_amacrine", 0.20),
       ("ds_ac", "retinal_amacrine_acl1", 0.20),
       ("out", "retina_parvalbumin_gc", 0.25)],
      [("bp", "out", "feedforward_excitatory", 1.0),
       ("bp", "ds_ac", "feedforward_excitatory", 0.8),
       ("ds_ac", "out", "lateral_inhibitory", 0.9),
       ("ac", "ds_ac", "mutual_inhibitory", 0.5)],
      [("photons", "sensory.visual", True)], [("motion", "sensory.visual.motion", True)],
      (6, 36), ["direction_select", "motion_detect", "temporal_filter"],
      ["motion_detect", "direction_encode", "optic_flow"], "motion_ingest",
      ["glutamate", "gaba"], "Barlow & Levick 1965; Euler 2002",
      ["mouse", "rabbit", "macaque"], ("retinal_motion_onset_unit", "visual_thalamic_relay_unit")),
    U("retinal_motion_onset_unit", "视网膜运动起始单元", "motion_onset", "sensory",
      "ACL2 胆碱能无长突细胞在运动起始瞬间发放，给下游一个『有新事件』的突兀信号。",
      [("bp", "retinal_bipolar", 0.40),
       ("onset", "retinal_amacrine_acl2", 0.30),
       ("gain", "retinal_horizontal", 0.10),
       ("out", "retina_parvalbumin_gc", 0.20)],
      [("bp", "onset", "feedforward_excitatory", 1.0),
       ("onset", "out", "feedforward_excitatory", 0.9),
       ("gain", "out", "shunting_inhibition", 0.5),
       ("out", "gain", "feedback_inhibitory", 0.4)],
      [("photons", "sensory.visual", True)], [("novelty", "sensory.visual.motion", True)],
      (5, 28), ["onset_detect", "novelty_event", "saccade_cue"],
      ["novelty_detect", "event_onset", "change_point"], "novelty_ingest",
      ["acetylcholine", "glutamate"], "Yonehara 2009; Zhang & Wu 2010",
      ["mouse", "rabbit"], ("retinal_direction_selective_unit", "visual_thalamic_relay_unit")),
    U("retinal_irradiance_unit", "视网膜辐照度单元", "irradiance_sensing", "sensory",
      "内在光敏节细胞直接被光驱动并缓慢持续放电，把环境亮度传给昼夜节律系统，不经图像通道。",
      [("iprgc", "melanopsin_ganglion", 0.55),
       ("slow_ac", "retinal_amacrine_acl2", 0.20),
       ("r_gc", "retina_midget_gc", 0.25)],
      [("iprgc", "r_gc", "modulatory_diffuse", 0.3),
       ("slow_ac", "iprgc", "feedforward_excitatory", 0.5),
       ("iprgc", "slow_ac", "feedback_excitatory", 0.5)],
      [("light", "sensory.visual", True)], [("irradiance", "sensory.visual.irradiance", True)],
      (3, 20), ["irradiance_sense", "slow_luminance", "circadian_drive"],
      ["ambient_light", "circadian_light_input", "slow_luminance"], "irradiance_ingest",
      ["glutamate"], "Hattar 2002; Do 2010",
      ["mouse", "human"], ("circadian_clock_unit",)),
    U("olfactory_transduction_unit", "嗅觉转导单元", "olfaction", "sensory",
      "嗅感觉神经元表达单一受体，经局部抑制性中间神经元做增益归一化后输出气味身份信号。",
      [("osn", "olfactory_receptor", 0.50),
       ("local_inh", "interneuron_pv", 0.20),
       ("mitral", "pyramidal_l23", 0.30)],
      [("osn", "mitral", "feedforward_excitatory", 1.0),
       ("osn", "local_inh", "feedforward_excitatory", 0.7),
       ("local_inh", "mitral", "lateral_inhibitory", 0.8),
       ("mitral", "local_inh", "dendro_dendritic", 0.4)],
      [("odorant", "sensory.olfactory", True)], [("odour_id", "sensory.olfactory", True)],
      (5, 48), ["odorant_encode", "sparsify", "gain_normalise"],
      ["odour_encode", "chemical_ingest", "sparse_code"], "olfactory_ingest",
      ["glutamate", "gaba"], "Buck & Axel 1991; Wilson & Mainen 2006",
      ["mouse", "fly", "human"], ("cortical_l4_input_unit",)),
    U("cochlear_amplification_unit", "耳蜗放大单元", "cochlear_amplification", "sensory",
      "外毛细胞的电致运动放大基底膜的微弱振动，是一段主动的机械增益级而非被动换能。",
      [("ohc", "cochlear_outer_hair", 0.55),
       ("relay", "brainstem_vpm", 0.30),
       ("fb", "interneuron_sst", 0.15)],
      [("ohc", "relay", "feedforward_excitatory", 1.0),
       ("relay", "fb", "feedback_excitatory", 0.5),
       ("fb", "ohc", "feedback_inhibitory", 0.7)],
      [("sound", "sensory.auditory", True)], [("amplified", "sensory.auditory", True)],
      (3, 24), ["mechanical_amplify", "frequency_sharpen", "active_gain"],
      ["audio_ingest", "frequency_select", "active_amplification"], "auditory_ingest",
      ["glutamate", "gaba"], "Brownell 1985; Ashmore 2008",
      ["mouse", "human", "bat"], ("auditory_thalamic_relay_unit",)),
    U("vestibular_transduction_unit", "前庭转导单元", "vestibular_sensing", "sensory",
      "毛细胞把头部加速度转为放电，经前庭小脑叶做重力参考后再送往运动系统。",
      [("hair", "vestibular_hair", 0.50),
       ("vest_cb", "pyramidal_mayeret", 0.30),
       ("inh", "interneuron_calbindin", 0.20)],
      [("hair", "vest_cb", "feedforward_excitatory", 1.0),
       ("hair", "inh", "feedforward_excitatory", 0.6),
       ("inh", "vest_cb", "feedforward_inhibitory", 0.7)],
      [("acceleration", "sensory.vestibular", True)], [("head_state", "sensory.vestibular", True)],
      (3, 22), ["acceleration_sense", "gravity_reference", "balance_reflex"],
      ["balance_sense", "orientation_track", "posture_reflex"], "vestibular_ingest",
      ["glutamate", "gaba"], "Goldberg 2012",
      ["mouse", "macaque", "human"], ("cerebellar_cortical_unit", "spinal_reflex_arc_unit")),
    U("somatosensory_dorsalhorn_unit", "躯体感觉背角单元", "somatosensation", "sensory",
      "痛觉与触觉传入在背角被甘氨酸能/回返性中间神经元预筛，形成门控式上行信号。",
      [("nociceptor", "spinal_nociceptor", 0.45),
       ("gly", "spinal_glycinergic", 0.25),
       ("rebound", "spinal_interneuron_ih", 0.30)],
      [("nociceptor", "rebound", "feedforward_excitatory", 1.0),
       ("gly", "rebound", "shunting_inhibition", 0.9),
       ("rebound", "gly", "recurrent_excitatory", 0.5),
       ("rebound", "rebound", "autapse_recurrent", 0.3)],
      [("noxious", "sensory.nociceptive", True),
       ("touch", "sensory.somatosensory", False)],
      [("ascending", "sensory.somatosensory", True)],
      (4, 30), ["pain_gate", "touch_encode", "descending_control"],
      ["pain_gate", "somatic_encode", "nociception_filter"], "somatosensory_ingest",
      ["glutamate", "gaba", "glycine"], "Melzack & Wall 1965 (gate theory)",
      ["mouse", "rat", "human"], ("somatosensory_thalamic_relay_unit", "spinal_reflex_arc_unit")),

    # ================= THALAMIC RELAY (5) ================= #
    U("thalamocortical_relay_unit", "丘脑皮层中继单元", "thalamic_relay", "thalamus",
      "中继细胞把上行信号送皮层，网状核形成局部抑制回路控制『门开多大』，是皮层的准入关口。",
      [("relay", "thalamic_relay", 0.65), ("gate", "reticular_thalamic", 0.35)],
      [("gate", "relay", "shunting_inhibition", 0.9),
       ("relay", "gate", "feedback_excitatory", 0.7),
       ("relay", "relay", "recurrent_excitatory", 0.35)],
      [("ascending", "sensory.*", True),
       ("cortical_fb", "cortex.feedback", False),
       ("modulation", "modulatory.*", False)],
      [("thalamic_out", "cortex.input", True)],
      (4, 26), ["relay", "gate", "synchronise", "gain_set"],
      ["sensory_relay", "gate_control", "cortical_drive"], "thalamic_relay",
      ["glutamate", "gaba"], "Sherman & Guillery 2006",
      ["mouse", "macaque", "human", "ferret"], ("cortical_l4_input_unit",)),
    U("visual_thalamic_relay_unit", "视觉丘脑中继单元", "visual_relay", "thalamus",
      "外膝体把视网膜信号按通道分流送往 V1，网状核调节中继增益与同步。",
      [("relay", "thalamic_lgn", 0.65), ("gate", "reticular_thalamic", 0.35)],
      [("gate", "relay", "shunting_inhibition", 0.9),
       ("relay", "gate", "feedback_excitatory", 0.7)],
      [("retina", "sensory.visual", True), ("cortical_fb", "cortex.feedback", False)],
      [("lgn_out", "cortex.input", True)],
      (4, 24), ["visual_relay", "channel_split", "gain_set"],
      ["visual_relay", "channel_route", "left_right_align"], "visual_relay",
      ["glutamate", "gaba"], "Usrey & Alitto 2015",
      ["macaque", "mouse", "human"], ("cortical_l4_input_unit", "retinal_direction_selective_unit")),
    U("auditory_thalamic_relay_unit", "听觉丘脑中继单元", "auditory_relay", "thalamus",
      "内侧膝状体按频率拓扑转发听觉信号，并由皮层下行反馈塑形。",
      [("relay", "thalamic_md", 0.65), ("gate", "reticular_thalamic", 0.35)],
      [("gate", "relay", "shunting_inhibition", 0.85),
       ("relay", "gate", "feedback_excitatory", 0.6)],
      [("cochlea", "sensory.auditory", True), ("cortical_fb", "cortex.feedback", False)],
      [("mgb_out", "cortex.input", True)],
      (4, 24), ["auditory_relay", "tonotopy", "cortical_shaping"],
      ["auditory_relay", "frequency_route", "sound_localise"], "auditory_relay",
      ["glutamate", "gaba"], "Lee & Sherman 2011",
      ["mouse", "bat", "human"], ("cortical_l4_input_unit", "cochlear_amplification_unit")),
    U("somatosensory_thalamic_relay_unit", "体感丘脑中继单元", "somatosensory_relay", "thalamus",
      "VPL/VPM 分别中继躯干与面部的触觉/本体感觉，是体感拓扑映射的入口。",
      [("vpl", "lateral_geniculate_ventral", 0.35),
       ("vpm", "lateral_geniculate_dorsal", 0.35),
       ("trigeminal", "brainstem_vpm", 0.15),
       ("gate", "reticular_thalamic", 0.15)],
      [("vpl", "gate", "feedforward_excitatory", 0.6),
       ("gate", "vpm", "shunting_inhibition", 0.8),
       ("vpm", "gate", "feedback_excitatory", 0.6),
       ("trigeminal", "vpm", "feedforward_excitatory", 0.9)],
      [("touch", "sensory.somatosensory", True), ("cortical_fb", "cortex.feedback", False)],
      [("vplvpm_out", "cortex.input", True)],
      (5, 28), ["somatotopic_relay", "touch_route", "body_map"],
      ["somatosensory_relay", "body_map_route", "touch_localise"], "somatosensory_relay",
      ["glutamate", "gaba"], "Jones 2007",
      ["macaque", "mouse", "human"], ("cortical_l4_input_unit", "somatosensory_dorsalhorn_unit")),
    U("motor_thalamic_relay_unit", "运动丘脑中继单元", "motor_relay", "thalamus",
      "VA/VL 把基底神经节与小脑的输出转给运动皮层，构成两条并行运动通路的共同出口。",
      [("va", "thalamic_va", 0.40), ("vl", "thalamic_vl", 0.40),
       ("gate", "reticular_thalamic", 0.20)],
      [("gate", "va", "shunting_inhibition", 0.8),
       ("gate", "vl", "shunting_inhibition", 0.8),
       ("va", "gate", "feedback_excitatory", 0.5),
       ("vl", "gate", "feedback_excitatory", 0.5)],
      [("basal_ganglia", "basal_ganglia.command", True),
       ("cerebellum", "cerebellar.output", True),
       ("cortical_fb", "cortex.feedback", False)],
      [("motor_thalamic_out", "cortex.output", True)],
      (5, 30), ["motor_relay", "pathway_merge", "gain_set"],
      ["motor_relay", "action_gate", "command_route"], "motor_relay",
      ["glutamate", "gaba"], "Alexander & Crutcher 1990",
      ["macaque", "mouse", "human"],
      ("cortical_l5_output_unit", "basal_ganglia_selection_unit", "cerebellar_cortical_unit")),

    # ================= CORTICAL MICROCIRCUIT (6) ================= #
    U("cortical_l4_input_unit", "皮层 L4 输入单元", "cortical_input", "cortex",
      "第 4 层接受丘脑输入并立刻被 PV/SST 中间神经元做前馈抑制，把持续输入变成稀疏的时间窗响应。",
      [("main", "pyramidal_l4", 0.30), ("b_style", "pyramidal_l4b", 0.20),
       ("c_style", "pyramidal_l4c", 0.20), ("pv", "interneuron_pv", 0.18),
       ("sst", "interneuron_sst", 0.12)],
      [("main", "pv", "feedforward_excitatory", 0.9),
       ("pv", "main", "axo_somatic", 1.0),
       ("main", "sst", "feedforward_excitatory", 0.6),
       ("sst", "b_style", "dendritic_inhibitory_synapse", 0.7),
       ("b_style", "c_style", "feedforward_excitatory", 0.8)],
      [("thalamic_in", "cortex.input", True)], [("l4_out", "cortex.association", True)],
      (8, 60), ["sensory_ingest", "temporal_sharpen", "sparsify", "feedforward_inhibit"],
      ["sensory_ingest", "temporal_sharpen", "stimulus_lock"], "cortical_input",
      ["glutamate", "gaba"], "Douglas & Martin 2004; Feldmeyer 2012",
      ["mouse", "macaque", "human"],
      ("cortical_l23_association_unit", "thalamocortical_relay_unit", "cortical_inhibitory_gain_unit")),
    U("cortical_l23_association_unit", "皮层 L2/3 联合单元", "cortical_association", "cortex",
      "第 2/3 层在皮层内横向联合，VIP 去抑制让 SST 松开树突，形成可切换的关联态。",
      [("main", "pyramidal_l23", 0.26), ("exec", "pyramidal_l23_cx1", 0.18),
       ("plan", "pyramidal_l23_cx5", 0.14), ("pv", "interneuron_pv", 0.16),
       ("sst", "interneuron_sst", 0.14), ("vip", "interneuron_vip", 0.12)],
      [("main", "pv", "feedforward_excitatory", 0.8),
       ("pv", "main", "axo_somatic", 0.9),
       ("vip", "sst", "disinhibition", 0.9),
       ("sst", "main", "dendritic_inhibitory_synapse", 0.8),
       ("main", "exec", "lateral_feedback", 0.6),
       ("exec", "plan", "feedforward_excitatory", 0.7),
       ("main", "main", "recurrent_excitatory", 0.55)],
      [("l4_in", "cortex.input", True), ("top_down", "cortex.feedback", False),
       ("gate", "arousal.state", False)],
      [("assoc_out", "cortex.association", True), ("exec_out", "cortex.output", True)],
      (10, 80), ["associate", "bind", "switch_state", "context_gate"],
      ["cross_domain_bridge", "context_bind", "state_switch", "factor_combine"], "cortical_association",
      ["glutamate", "gaba", "vip"], "Harris & Mrsic-Flogel 2013; Pi 2013",
      ["mouse", "macaque", "human"],
      ("cortical_l4_input_unit", "cortical_l5_output_unit", "cortical_l6_feedback_unit")),
    U("cortical_l5_output_unit", "皮层 L5 输出单元", "cortical_output", "cortex",
      "第 5 层是皮层唯一的皮层下出口，粗树突细胞同时投向多个下游并带 KCN 型适应调控持续输出。",
      [("main", "pyramidal_l5", 0.32), ("tuft", "pyramidal_l5bt", 0.22),
       ("pv", "interneuron_pv", 0.16), ("soma_inh", "interneuron_sst_somatic", 0.15),
       ("adapt", "interneuron_kcn", 0.15)],
      [("main", "pv", "feedforward_excitatory", 0.7),
       ("pv", "main", "axo_somatic", 1.0),
       ("soma_inh", "main", "recurrent_inhibitory", 0.8),
       ("main", "adapt", "feedforward_excitatory", 0.6),
       ("adapt", "main", "shunting_inhibition", 0.7),
       ("tuft", "main", "dendritic_computation", 0.8)],
      [("l23_in", "cortex.association", True), ("thalamic_fb", "cortex.input", False)],
      [("descending", "cortex.output", True), ("ataxia_copy", "motor.command", False)],
      (10, 70), ["descend", "command", "adapt", "multi_target_output"],
      ["action_dispatch", "command_route", "output_gate", "commit_action"], "cortical_output",
      ["glutamate", "gaba"], "Manya & Sakmann 2006; Larkum 2013",
      ["mouse", "macaque", "human"],
      ("motor_thalamic_relay_unit", "cortical_l23_association_unit", "spinal_reflex_arc_unit")),
    U("cortical_l6_feedback_unit", "皮层 L6 反馈单元", "cortical_feedback", "cortex",
      "第 6 层双投射细胞把皮层状态回送丘脑，其中一类专门调丘脑中继增益、另一类回皮层内其他层。",
      [("it", "pyramidal_l6_it", 0.55), ("rt", "pyramidal_l6rt", 0.30),
       ("inh", "interneuron_npf", 0.15)],
      [("it", "rt", "feedforward_excitatory", 0.8),
       ("rt", "it", "recurrent_inhibitory", 0.6),
       ("inh", "it", "lateral_inhibitory", 0.7),
       ("it", "it", "short_term_plasticity", 0.4)],
      [("l23_in", "cortex.association", True), ("l5_in", "cortex.output", False)],
      [("corticothalamic", "cortex.feedback", True), ("intracortical", "cortex.association", False)],
      (5, 34), ["top_down", "gain_control", "predictive_regulate"],
      ["top_down_regulate", "predictive_error", "gain_set"], "cortical_feedback",
      ["glutamate", "gaba"], "Thomson 2010; Olsen 2012",
      ["mouse", "macaque"], ("thalamocortical_relay_unit", "cortical_l23_association_unit")),
    U("cortical_inhibitory_gain_unit", "皮层抑制增益单元", "inhibitory_gain_control", "cortex",
      "PV/SST/VIP/chandelier/basket/NPH 六类中间神经元分工——胞体、树突、轴突起始段各有一个刹车位点，合起来是皮层增益控制器。",
      [("pv", "interneuron_pv", 0.22), ("sst", "interneuron_sst", 0.20),
       ("vip", "interneuron_vip", 0.14), ("chand", "interneuron_chandelier", 0.10),
       ("basket", "interneuron_basket", 0.16), ("nph", "interneuron_nph", 0.18)],
      [("vip", "sst", "disinhibition", 1.0),
       ("sst", "pv", "mutual_inhibitory", 0.5),
       ("pv", "chand", "gap_junction_inhibitory", 0.4),
       ("basket", "pv", "gap_junction_sync", 0.5),
       ("nph", "sst", "disinhibition", 0.7),
       ("chand", "basket", "feedforward_inhibitory", 0.6)],
      [("excitatory_drive", "cortex.association", True), ("state", "arousal.state", False)],
      [("inhibitory_tone", "cortex.interneuron", True)],
      (12, 90), ["gain_control", "shunt", "disinhibit", "rhythm_generate"],
      ["gain_regulate", "stability_brake", "rhythm_clock", "state_gate"], "inhibitory_gain",
      ["gaba", "vip", "somatostatin"],
      "Markram 2004; Tremblay 2016; Gouwens 2020",
      ["mouse", "macaque", "human"],
      ("cortical_l4_input_unit", "cortical_l23_association_unit", "cortical_l5_output_unit")),
    U("cortical_highorder_integration_unit", "高阶皮层整合单元", "multimodal_integration", "cortex",
      "第 7 层与长程抑制细胞构成跨模态汇聚区，把来自不同通道的信号在同一群体内做高阶绑定。",
      [("main", "pyramidal_l7", 0.60), ("lri", "interneuron_vlac", 0.22),
       ("slow", "interneuron_npf", 0.18)],
      [("lri", "main", "lateral_inhibitory", 0.8),
       ("slow", "main", "recurrent_inhibitory", 0.6),
       ("main", "lri", "feedforward_excitatory", 0.6),
       ("main", "main", "recurrent_excitatory", 0.6)],
      [("modality_a", "cortex.association", True), ("modality_b", "cortex.association", True),
       ("top_down", "cortex.feedback", False)],
      [("integrated", "cortex.output", True)],
      (8, 56), ["multimodal_bind", "high_order_represent", "cross_modal_arbitrate"],
      ["cross_domain_bridge", "multimodal_fuse", "high_order_abstract"], "high_order_integration",
      ["glutamate", "gaba"], "Molyneaux 2007; Hilgetag & Goulas 2020",
      ["human", "macaque"], ("cortical_l23_association_unit", "cortical_l5_output_unit")),

    # ================= CEREBELLUM (2) ================= #
    U("cerebellar_cortical_unit", "小脑皮层单元", "cerebellar_processing", "cerebellum",
      "苔藓纤维把输入扩到海量颗粒细胞，浦肯野细胞汇聚后经星形/篮状细胞做侧抑制，是『超稀疏展开 + 强收敛』的经典结构。",
      [("granule", "cerebellar_granule", 0.50), ("purkinje", "cerebellar_purkinje", 0.16),
       ("stellate", "cerebellar_stellate", 0.14), ("calb", "interneuron_calbindin", 0.10),
       ("lamp", "interneuron_lamp", 0.10)],
      [("granule", "purkinje", "feedforward_excitatory", 0.8),
       ("granule", "stellate", "feedforward_excitatory", 0.7),
       ("granule", "calb", "feedforward_excitatory", 0.7),
       ("stellate", "purkinje", "lateral_inhibitory", 0.9),
       ("calb", "purkinje", "feedforward_inhibitory", 0.8),
       ("lamp", "purkinje", "lateral_inhibitory", 1.0),
       ("granule", "granule", "recurrent_excitatory", 0.3)],
      [("mossy_fibre", "cerebellar.input", True), ("teaching", "error.teaching", False)],
      [("purkinje_out", "cerebellar.output", True)],
      (14, 120), ["expand", "converge", "lateral_inhibit", "motor_refine"],
      ["signal_expand", "feature_converge", "fine_regulate", "motor_refine"], "cerebellar_process",
      ["glutamate", "gaba"], "Eccles 1967; Ito 2006",
      ["mouse", "macaque", "human"],
      ("cerebellar_error_teaching_unit", "motor_thalamic_relay_unit", "vestibular_transduction_unit")),
    U("cerebellar_error_teaching_unit", "小脑误差教学单元", "error_teaching", "cerebellum",
      "下橄榄的攀爬纤维把运动误差以强全或无信号送到浦肯野细胞，触发 LTD 修正颗粒-浦肯野权重，是监督学习的生理实现。",
      [("olive", "inferior_olive", 0.40), ("purkinje", "cerebellar_purkinje", 0.35),
       ("granule", "cerebellar_granule", 0.25)],
      [("olive", "purkinje", "ltp_ltd", 1.0),
       ("olive", "granule", "feedforward_excitatory", 0.5),
       ("granule", "purkinje", "stdp_rule", 0.8),
       ("purkinje", "olive", "feedback_inhibitory", 0.6)],
      [("error", "error.teaching", True), ("context", "cerebellar.input", True)],
      [("corrected", "cerebellar.output", True)],
      (5, 40), ["supervised_learn", "error_correct", "credit_assign"],
      ["supervised_finetune", "error_correct", "weight_repair"], "error_teaching",
      ["glutamate", "gaba"], "Ito 1982; De Zeeuw 2011",
      ["mouse", "macaque", "human"], ("cerebellar_cortical_unit",)),
]


# ====================================================================== #
# 3. HIPPOCAMPAL / LIMBIC / BG / MOTOR / MODULATORY units (continued)
# ====================================================================== #
FUNCTIONAL_UNITS += [
    U("hippocampal_trisynaptic_unit", "海马三突触回路单元", "episodic_memory", "hippocampus",
      "内嗅→齿状回→CA3→CA1 三站：齿状回做模式分离、CA3 做自联想、CA1 做输出比较，是情景记忆的最小环。",
      [("dg", "hippocampal_granule", 0.40), ("ca3", "hippocampal_ca3", 0.32),
       ("ca1", "hippocampal_ca1", 0.28)],
      [("dg", "ca3", "feedforward_excitatory", 1.0),
       ("ca3", "ca1", "feedforward_excitatory", 1.0),
       ("ca3", "ca3", "recurrent_excitatory", 0.9),
       ("ca1", "ca3", "feedback_inhibitory", 0.5),
       ("dg", "dg", "feedforward_inhibitory", 0.5)],
      [("ec_in", "hippocampal.input", True), ("theta", "rhythm.theta", False)],
      [("ca1_out", "hippocampal.output", True), ("engram", "hippocampal.engram", True)],
      (12, 90), ["pattern_separate", "auto_associate", "episodic_encode", "pattern_complete"],
      ["memory_encode", "pattern_complete", "episode_bind", "recall_cue"], "episodic_memory",
      ["glutamate", "gaba"], "Andersen 1971; Rolls 2013",
      ["mouse", "rat", "macaque", "human"],
      ("entorhinal_spatial_map_unit", "hippocampal_output_unit", "septo_hippocampal_theta_unit")),
    U("hippocampal_ca2_autoassoc_unit", "海马 CA2 自联想单元", "social_stress_memory", "hippocampus",
      "CA2 缺少典型三突触输入但接收 CA4/CA3 汇入，参与社会记忆与应激响应的特殊亚区。",
      [("ca2", "hippocampal_ca2", 0.40), ("ca4", "hippocampal_ca4", 0.32),
       ("inh", "interneuron_npf", 0.28)],
      [("ca4", "ca2", "feedforward_excitatory", 0.9),
       ("ca2", "ca2", "recurrent_excitatory", 0.7),
       ("inh", "ca2", "recurrent_inhibitory", 0.8),
       ("ca2", "inh", "feedforward_excitatory", 0.7)],
      [("ca3_in", "hippocampal.engram", True), ("stress", "arousal.state", False)],
      [("ca2_out", "hippocampal.output", True)],
      (6, 40), ["social_encode", "stress_gate", "associate_context"],
      ["social_memory", "stress_modulate", "context_associate"], "social_memory",
      ["glutamate", "gaba"], "Dudek 2016; Hitti & Siegelbaum 2014",
      ["mouse", "macaque"], ("hippocampal_trisynaptic_unit", "amygdala_fear_unit")),
    U("hippocampal_output_unit", "海马输出单元", "memory_readout", "hippocampus",
      "下托整合 CA1 与内嗅的输入并决定往哪个皮层区回送记忆，是记忆读出的路由级。",
      [("sub", "hippocampal_subiculum", 0.55), ("ca1", "hippocampal_ca1", 0.30),
       ("inh", "interneuron_vlac", 0.15)],
      [("ca1", "sub", "feedforward_excitatory", 1.0),
       ("inh", "sub", "lateral_inhibitory", 0.7),
       ("sub", "sub", "recurrent_excitatory", 0.4),
       ("sub", "inh", "feedforward_excitatory", 0.6)],
      [("ca1_in", "hippocampal.output", True), ("ec_in", "hippocampal.input", False)],
      [("cortical_readout", "cortex.input", True)],
      (5, 38), ["route_readout", "context_reinstate", "memory_dispatch"],
      ["memory_readout", "context_reinstate", "recall_route"], "memory_readout",
      ["glutamate", "gaba"], "Witter 2006; Naber 2001",
      ["mouse", "macaque", "human"],
      ("hippocampal_trisynaptic_unit", "cortical_l23_association_unit")),
    U("entorhinal_spatial_map_unit", "内嗅空间地图单元", "spatial_map", "entorhinal",
      "网格细胞的六边形周期放电与位置/头向细胞共同构成自定位坐标系，是空间记忆的度量基。",
      [("grid", "grid_cell", 0.60), ("dg", "hippocampal_granule", 0.25),
       ("inh", "interneuron_sst", 0.15)],
      [("grid", "dg", "topographic_mapping", 1.0),
       ("grid", "inh", "feedforward_excitatory", 0.6),
       ("inh", "grid", "lateral_inhibitory", 0.8),
       ("grid", "grid", "temporal_coherence", 0.6)],
      [("self_motion", "sensory.vestibular", True), ("theta", "rhythm.theta", False)],
      [("spatial_code", "spatial.map", True), ("ec_out", "hippocampal.input", True)],
      (8, 60), ["metric_map", "path_integrate", "self_locate"],
      ["spatial_locate", "path_integrate", "coordinate_frame"], "spatial_map",
      ["glutamate", "gaba"], "Moser 2008; Hafting 2005",
      ["rat", "mouse", "macaque", "human"],
      ("hippocampal_trisynaptic_unit", "vestibular_transduction_unit")),
    U("striatal_direct_pathway_unit", "纹状体直接通路单元", "action_facilitation", "basal_ganglia",
      "D1 型 MSN 在 dopamine 到达时被易化，抑制苍白球内侧部，从而松开一个动作的刹车。",
      [("d1", "striatum_d1_msn", 0.70), ("da", "dopaminergic_snc", 0.30)],
      [("da", "d1", "modulatory_diffuse", 1.0),
       ("d1", "d1", "recurrent_inhibitory", 0.7),
       ("d1", "da", "feedback_excitatory", 0.3)],
      [("cortical_in", "cortex.output", True), ("value", "basal_ganglia.value", True)],
      [("go_signal", "basal_ganglia.command", True)],
      (5, 34), ["facilitate", "gate_open", "value_gated_action"],
      ["action_facilitate", "go_gate", "value_gate"], "action_facilitate",
      ["gaba", "dopamine"], "Gerfen & Surmeier 2011",
      ["mouse", "rat", "macaque", "human"], ("basal_ganglia_selection_unit",)),
    U("striatal_indirect_pathway_unit", "纹状体间接通路单元", "action_suppression", "basal_ganglia",
      "D2 型 MSN 在 dopamine 缺席时活跃，经 STN 兴奋 GPi，给不该做的动作加刹车。",
      [("d2", "striatum_d2_msn", 0.55), ("stn", "subthalamic_nucleus", 0.25),
       ("da", "dopaminergic_a9_snr", 0.20)],
      [("d2", "stn", "feedforward_inhibitory", 0.9),
       ("stn", "d2", "feedback_excitatory", 0.6),
       ("da", "d2", "modulatory_diffuse", 1.0),
       ("stn", "stn", "recurrent_excitatory", 0.5)],
      [("cortical_in", "cortex.output", True), ("value", "basal_ganglia.value", True)],
      [("no_go_signal", "basal_ganglia.command", True)],
      (5, 34), ["suppress", "gate_close", "conflict_hold"],
      ["action_suppress", "no_go_gate", "conflict_hold"], "action_suppress",
      ["gaba", "glutamate", "dopamine"], "Albin 1989; DeLong 1990",
      ["mouse", "rat", "macaque", "human"], ("basal_ganglia_selection_unit",)),
    U("basal_ganglia_selection_unit", "基底神经节动作选择单元", "action_selection", "basal_ganglia",
      "直接/间接双通路相互竞争，多巴胺同时调节两侧增益——净输出是对候选动作的赢者通吃式选择。",
      [("d1", "striatum_d1_msn", 0.32), ("d2", "striatum_d2_msn", 0.28),
       ("stn", "subthalamic_nucleus", 0.14), ("da", "dopaminergic_a9_snr", 0.12),
       ("out", "thalamic_va", 0.14)],
      [("d1", "stn", "mutual_inhibitory", 0.8),
       ("d2", "stn", "feedforward_excitatory", 0.9),
       ("stn", "out", "feedforward_excitatory", 0.7),
       ("d1", "out", "winner_take_all", 0.9),
       ("da", "d1", "modulatory_diffuse", 1.0),
       ("da", "d2", "modulatory_diffuse", 0.9),
       ("d1", "d2", "mutual_inhibitory", 0.9)],
      [("candidates", "cortex.output", True), ("value", "basal_ganglia.value", True)],
      [("selected_action", "basal_ganglia.command", True)],
      (10, 70), ["select_action", "resolve_conflict", "value_gate", "arbitrate"],
      ["action_select", "candidate_arbitrate", "winner_pick", "decision_commit"],
      "action_selection",
      ["gaba", "glutamate", "dopamine"], "Mink 1996; Redgrave 1999",
      ["macaque", "mouse", "human"],
      ("striatal_direct_pathway_unit", "striatal_indirect_pathway_unit", "motor_thalamic_relay_unit")),
    U("amygdala_fear_unit", "杏仁核恐惧单元", "threat_learning", "limbic",
      "外侧杏仁核接收感觉输入，基底外侧核做威胁关联学习，输出条件性恐惧反应。",
      [("la", "amygdala_lateral", 0.45), ("bla", "amygdala_bla", 0.40),
       ("inh", "interneuron_pv", 0.15)],
      [("la", "bla", "feedforward_excitatory", 1.0),
       ("inh", "bla", "feedforward_inhibitory", 0.8),
       ("bla", "la", "feedback_excitatory", 0.6),
       ("bla", "bla", "ltp_ltd", 0.7)],
      [("sensory_in", "cortex.association", True), ("threat", "sensory.nociceptive", False)],
      [("fear_out", "limbic.fear", True)],
      (6, 42), ["threat_associate", "fear_condition", "safety_gate"],
      ["threat_detect", "risk_associate", "aversion_learn"], "threat_learning",
      ["glutamate", "gaba"], "LeDoux 2000; Sah 2003",
      ["rat", "mouse", "human"],
      ("hippocampal_ca2_autoassoc_unit", "somatosensory_dorsalhorn_unit", "hypothalamic_arousal_unit")),
    U("septo_hippocampal_theta_unit", "隔-海马 theta 节律单元", "theta_rhythm", "limbic",
      "隔核与斜角带胆碱能细胞给海马提供 theta 节律驱动，是记忆编码与检索的时间基准。",
      [("septum", "septum", 0.40), ("cholinergic", "cholinergic_mt", 0.30),
       ("ca1", "hippocampal_ca1", 0.15), ("slow_inh", "interneuron_npf", 0.15)],
      [("septum", "cholinergic", "feedforward_excitatory", 0.9),
       ("cholinergic", "ca1", "modulatory_diffuse", 1.0),
       ("slow_inh", "ca1", "recurrent_inhibitory", 0.8),
       ("septum", "slow_inh", "feedforward_excitatory", 0.7),
       ("septum", "septum", "mutual_inhibitory", 0.6)],
      [("arousal", "arousal.state", True)], [("theta_out", "rhythm.theta", True)],
      (6, 44), ["pace", "phase_align", "encode_timing"],
      ["rhythm_pace", "phase_align", "temporal_benchmark"], "theta_pace",
      ["gaba", "acetylcholine"], "Buzsaki 2002; Colgin 2016",
      ["rat", "mouse", "macaque"], ("hippocampal_trisynaptic_unit", "hypothalamic_arousal_unit")),
    U("hypothalamic_arousal_unit", "下丘脑觉醒单元", "arousal_stability", "hypothalamus",
      "食欲素、组胺、去甲肾上腺素三路共同维持清醒稳定：食欲素缺失导致状态切换不稳（发作性睡病）。",
      [("orexin", "orexin_neuron", 0.40), ("histamine", "histaminergic_tm", 0.32),
       ("ne", "noradrenergic_lc", 0.28)],
      [("orexin", "histamine", "feedforward_excitatory", 0.9),
       ("orexin", "ne", "feedforward_excitatory", 0.9),
       ("histamine", "orexin", "feedback_excitatory", 0.5),
       ("ne", "histamine", "mutual_inhibitory", 0.4)],
      [("circadian", "rhythm.circadian", True), ("sleep_pressure", "arousal.state", False)],
      [("arousal_out", "arousal.state", True),
       ("orexin_out", "modulatory.orexin", True),
       ("histamine_out", "modulatory.histamine", True)],
      (4, 30), ["stabilise_state", "wake_drive", "flip_flop_stabilise"],
      ["state_stabilise", "wake_drive", "mode_switch"], "arousal_stability",
      ["orexin", "histamine", "noradrenaline"], "Saper 2005; de Lecea 1998",
      ["mouse", "rat", "human"],
      ("circadian_clock_unit", "septo_hippocampal_theta_unit", "cholinergic_arousal_unit")),
    U("spinal_reflex_arc_unit", "脊髓反射弧单元", "reflex_arc", "spinal_cord",
      "感觉传入→中间神经元→运动神经元的两站式最短回路，可在无脑参与下完成保护性动作。",
      [("sensory", "spinal_nociceptor", 0.34), ("interneuron", "spinal_interneuron_ih", 0.33),
       ("motor", "spinal_motor_alpha", 0.33)],
      [("sensory", "interneuron", "feedforward_excitatory", 1.0),
       ("interneuron", "motor", "feedforward_excitatory", 1.0),
       ("motor", "interneuron", "recurrent_inhibitory", 0.6),
       ("interneuron", "sensory", "pre_presynaptic_inhibition", 0.5)],
      [("afferent", "sensory.nociceptive", True), ("descending", "motor.command", False)],
      [("contraction", "motor.command", True), ("spindle_fb", "motor.spindle", True)],
      (4, 26), ["reflex", "fast_loop", "protective_response"],
      ["reflex_act", "fast_respond", "protective_loop"], "reflex_arc",
      ["glutamate", "gaba", "glycine"], "Sherrington 1906; Eccles 1964",
      ["mouse", "rat", "human"], ("spinal_cpg_unit", "gamma_spindle_loop_unit")),
    U("spinal_cpg_unit", "脊髓中枢模式发生器单元", "rhythmic_pattern", "spinal_cord",
      "半中心 Ihp 与连合 Icc 中间神经元组成互抑制振荡器，产生交替节律（行走/游动/呼吸共用同一原理）。",
      [("half_center", "spinal_interneuron_ihp", 0.28),
       ("commissural", "spinal_interneuron_icc", 0.22),
       ("gly", "spinal_glycinergic", 0.16), ("alpha", "spinal_motor_alpha", 0.20),
       ("gamma", "spinal_motor_gamma", 0.14)],
      [("half_center", "commissural", "mutual_inhibitory", 1.0),
       ("commissural", "half_center", "mutual_inhibitory", 1.0),
       ("half_center", "alpha", "feedforward_excitatory", 0.9),
       ("commissural", "gly", "feedforward_excitatory", 0.7),
       ("gly", "alpha", "shunting_inhibition", 0.8),
       ("alpha", "gamma", "feedforward_excitatory", 0.6),
       ("half_center", "half_center", "recurrent_excitatory", 0.5)],
      [("drive", "motor.command", True), ("state", "arousal.state", False)],
      [("rhythmic_out", "motor.command", True)],
      (8, 56), ["oscillate", "alternate_phase", "generate_rhythm"],
      ["rhythm_generate", "gait_alternate", "phase_sequence"], "rhythmic_pattern",
      ["glutamate", "gaba", "glycine"], "Grillner 1985; Goulding 2009",
      ["lamprey", "mouse", "rat", "human"],
      ("spinal_reflex_arc_unit", "red_nucleus_coordination_unit")),
    U("gamma_spindle_loop_unit", "γ-肌梭环路单元", "spindle_servo", "spinal_cord",
      "γ 运动神经元设定肌梭灵敏度，α 运动神经元输出力，Ia 反馈构成伺服回路实时校准收缩。",
      [("gamma", "spinal_motor_gamma", 0.34), ("alpha", "spinal_motor_alpha", 0.36),
       ("fb", "spinal_interneuron_ih", 0.30)],
      [("gamma", "fb", "feedforward_excitatory", 0.7),
       ("fb", "alpha", "feedforward_excitatory", 0.9),
       ("alpha", "gamma", "recurrent_inhibitory", 0.6),
       ("fb", "gamma", "lateral_feedback", 0.5)],
      [("command", "motor.command", True), ("spindle_in", "motor.spindle", True)],
      [("force_out", "motor.command", True)],
      (4, 26), ["servo_control", "gain_set", "closed_loop_correct"],
      ["servo_regulate", "gain_set", "closed_loop_correct"], "spindle_servo",
      ["glutamate", "acetylcholine", "gaba"], "Matthews 1972; Prochazka 1996",
      ["cat", "mouse", "human"],
      ("spinal_reflex_arc_unit", "spinal_cpg_unit", "red_nucleus_coordination_unit")),
    U("red_nucleus_coordination_unit", "红核运动协调单元", "motor_coordination", "brainstem",
      "红核把小脑输出的时序信息转为对 α 运动神经元的直接驱动，协调多关节动作的时序与幅度。",
      [("rn", "red_nucleus", 0.45), ("cb", "cerebellar_purkinje", 0.30),
       ("alpha", "spinal_motor_alpha", 0.25)],
      [("cb", "rn", "feedforward_excitatory", 0.9),
       ("rn", "alpha", "feedforward_excitatory", 1.0),
       ("rn", "cb", "feedback_excitatory", 0.6),
       ("rn", "rn", "recurrent_excitatory", 0.4)],
      [("cerebellar_in", "cerebellar.output", True), ("cortical", "cortex.output", False)],
      [("coordinated_out", "motor.command", True)],
      (5, 34), ["coordinate_timing", "multi_joint", "ramp_output"],
      ["timing_coordinate", "multi_joint_plan", "ramp_generate"], "motor_coordination",
      ["glutamate", "gaba"], "Massion 1988; Houk 2005",
      ["macaque", "cat", "human"],
      ("cerebellar_cortical_unit", "spinal_cpg_unit", "gamma_spindle_loop_unit")),
    U("dopaminergic_value_unit", "多巴胺价值单元", "value_broadcast", "neuromodulatory",
      "中脑多巴胺群体（A9/A11/VMC/VTA/SNc）把奖赏预测误差广播到纹状体与皮层，是全脑的学习率旋钮。",
      [("snc", "dopaminergic_snc", 0.22), ("vta", "dopaminergic_vta", 0.24),
       ("vmc", "dopaminergic_vmc", 0.20), ("a11", "dopaminergic_a11", 0.16),
       ("a9", "dopaminergic_a9_snr", 0.18)],
      [("vta", "vmc", "feedforward_excitatory", 0.7),
       ("snc", "a9", "feedforward_excitatory", 0.7),
       ("a11", "vta", "mutual_inhibitory", 0.5),
       ("vmc", "a11", "feedforward_excitatory", 0.5),
       ("a9", "snc", "feedback_inhibitory", 0.6)],
      [("rpe_in", "basal_ganglia.value", False)],
      [("dopamine_out", "modulatory.dopamine", True)],
      (6, 44), ["value_broadcast", "rpe_compute", "learning_rate_set"],
      ["value_signal", "reward_predict", "learning_rate"], "value_broadcast",
      ["dopamine"], "Schultz 1997; Watabe-Uchida 2017",
      ["mouse", "rat", "macaque", "human"],
      ("striatal_direct_pathway_unit", "striatal_indirect_pathway_unit", "serotonergic_mood_unit")),
    U("serotonergic_mood_unit", "5-HT 情绪单元", "mood_modulation", "neuromodulatory",
      "背侧/腹侧/中缝三组 5-HT 群体分别调节情绪、奖赏与海马节律，是全局时间尺度上的『心情』底色。",
      [("dorsal", "serotonergic_dorsal", 0.30), ("ventral", "serotonergic_ventral", 0.26),
       ("median", "serotonergic_median", 0.22), ("raphe", "serotonergic_raphe", 0.22)],
      [("raphe", "dorsal", "feedforward_excitatory", 0.7),
       ("raphe", "ventral", "feedforward_excitatory", 0.7),
       ("raphe", "median", "feedforward_excitatory", 0.7),
       ("ventral", "dorsal", "mutual_inhibitory", 0.5),
       ("median", "ventral", "lateral_inhibitory", 0.5)],
      [("state_in", "arousal.state", True)],
      [("serotonin_out", "modulatory.serotonin", True)],
      (6, 40), ["mood_broadcast", "patience_set", "rhythm_modulate"],
      ["mood_modulate", "patience_set", "temporal_discount"], "mood_broadcast",
      ["serotonin"], "Jacobs & Azmitia 1992; Okaty 2019",
      ["mouse", "rat", "human"],
      ("dopaminergic_value_unit", "septo_hippocampal_theta_unit", "hypothalamic_arousal_unit")),
    U("cholinergic_arousal_unit", "胆碱能觉醒单元", "cholinergic_arousal", "neuromodulatory",
      "基底前脑与斜角带胆碱能细胞调节皮层兴奋性与丘脑同步，是注意与觉醒的共同杠杆。",
      [("mt", "cholinergic_mt", 0.55), ("horizontal", "cholinergic_horizontal", 0.45)],
      [("mt", "horizontal", "feedforward_excitatory", 0.7),
       ("horizontal", "mt", "feedback_excitatory", 0.6),
       ("horizontal", "horizontal", "recurrent_excitatory", 0.4)],
      [("state_in", "arousal.state", True)],
      [("ach_out", "modulatory.acetylcholine", True)],
      (4, 28), ["cortical_arousal", "attention_gain", "thalamic_sync"],
      ["arousal_set", "attention_gain", "cortical_excite"], "cholinergic_arousal",
      ["acetylcholine"], "Sarter 2005; Zaborszky 2018",
      ["rat", "mouse", "human"],
      ("hypothalamic_arousal_unit", "cortical_l23_association_unit", "septo_hippocampal_theta_unit")),
    U("circadian_clock_unit", "昼夜节律单元", "circadian_rhythm", "neuromodulatory",
      "松果体在暗期分泌褪黑素，视网膜辐照度信号是它的授时输入，构成约 24 小时的内源振荡。",
      [("pineal", "pineal", 0.50), ("iprgc", "melanopsin_ganglion", 0.30),
       ("wake", "orexin_neuron", 0.20)],
      [("iprgc", "pineal", "modulatory_diffuse", 1.0),
       ("pineal", "wake", "modulatory_diffuse", 0.7),
       ("wake", "pineal", "feedback_inhibitory", 0.5)],
      [("light_in", "sensory.visual.irradiance", True)],
      [("circadian_out", "rhythm.circadian", True)],
      (3, 20), ["oscillate_circadian", "entrain_light", "phase_set"],
      ["circadian_track", "light_entrain", "phase_shift"], "circadian_rhythm",
      ["melatonin_norepinephrine", "glutamate"], "Moore 1995; Hastings 2018",
      ["mouse", "rat", "human"],
      ("retinal_irradiance_unit", "hypothalamic_arousal_unit")),
    U("astrocyte_tripartite_unit", "星形胶质三方单元", "gliotransmission", "glia",
      "星形胶质细胞包绕突触、感知活动并以钙波回送慢调节信号，是神经元之外的一条独立慢通道。",
      [("astro", "astrocyte_reactive", 0.50), ("exc", "pyramidal_l5", 0.28),
       ("inh", "interneuron_sst", 0.22)],
      [("astro", "exc", "astrocyte_neuron_tripartite", 0.8),
       ("astro", "inh", "gliotransmission_calcium_wave", 0.7),
       ("exc", "astro", "feedforward_excitatory", 0.5),
       ("inh", "astro", "feedforward_excitatory", 0.4),
       ("astro", "astro", "gliotransmission_calcium_wave", 0.6)],
      [("neuronal_activity", "cortex.association", True), ("metabolic", "glial.support", False)],
      [("slow_modulation", "glial.support", True), ("vascular", "glial.support", False)],
      (3, 22), ["slow_modulate", "metabolic_support", "calcium_wave"],
      ["slow_modulate", "metabolic_support", "homeostatic_regulate"], "gliotransmission",
      ["glutamate", "gaba", "serotonin"], "Araque 1999; Nedergaard 2010",
      ["mouse", "rat", "human"],
      ("cortical_l5_output_unit", "cortical_inhibitory_gain_unit")),
]


# ====================================================================== #
# 4. VALIDATE + WRITE
# ====================================================================== #
# ----------------------------------------------------------------------
# EMBODIMENT (v1.7.0) -- attach the measured MaleCNS anchor to every unit
# ----------------------------------------------------------------------
def _load_anchors() -> dict:
    if not ANCHORS_FILE.exists():
        raise SystemExit(
            "REFUSING TO WRITE: %s is missing.\n"
            "The embodiment layer is part of the library contract: without it every "
            "unit silently reverts to 'literature only' with no way for a reader to "
            "tell. Rebuild it with:\n"
            "    python scripts/build_malecns_anchors.py\n"
            "(needs a local MaleCNS v1.0 copy under FLYBRAIN_DATA_DIR)."
            % ANCHORS_FILE.name)
    return json.loads(ANCHORS_FILE.read_text(encoding="utf-8"))


def _evidence_weight(unit: dict) -> tuple:
    """Derive `provenance.evidence_weight` for UNANCHORED units from the count
    of `;`-separated entries in `biological_reference`.

    Four-tier enum (never hand-typed):
      connectome_derived — the unit is anchored in MaleCNS v1.0 connectome
                           data; evidence is the extraction itself, not
                           literature citations
      textbook           — >=4 citations; the sort of entry that appears in
                           a textbook chapter
      multi_source       — 2-3 citations; consensus from independent groups
      single_source      — exactly 1 citation; a claim resting on one paper
    """
    # Embodied units get the highest tier: their evidence IS the connectome
    if unit.get("provenance", {}).get("embodied_in_malecns"):
        return "connectome_derived", None
    # v2.27.0 -- the second connectome. A unit traced out of an explicit
    # reconstruction carries its evidence AS that reconstruction, so it must
    # not be graded on the citation ladder: a unit fully traced in a real
    # serial-section EM reconstruction would land in the weakest tier
    # (single_source) for citing one paper. That is the same axis error the
    # v2.26 connectome-axis rescore fixed, applied to the weight ladder.
    if unit.get("provenance", {}).get("source_connectome"):
        return "connectome_derived", None
    refs = [r.strip() for r in (unit.get("biological_reference") or "").split(";")
            if r.strip()]
    n = len(refs)
    if n <= 1:
        return "single_source", n
    if n <= 3:
        return "multi_source", n
    return "textbook", n


def _embody(unit: dict, anchors: dict) -> None:
    """Attach `embodiment` to one unit, in place.

    `structural_support` is measured at THREE resolutions, from coarsest to
    finest, because each one falsifies a different claim:

    1. SUPERCLASS-SET (context only): the coarsest cut -- 11 of the 14 anchored
       profiles share one superclass, so it cannot tell two edges apart.
    2. CELL-TYPE-SET (the contradiction gate): sum the real synapses between the
       two populations' actual cell-type sets. Zero = contradiction.
    3. TYPE-PAIR (support tier): iterate every (from_type, to_type) pair across
       the two populations and count how many pairs carry real synapses.
       SUPPORTED = >=2 pairs, FRAGILE = exactly 1, CONTRADICTED = 0.
       FRAGILE is NOT a contradiction -- the edge has real support, but it rests
       on a single type pair, so the profile-level verdict is brittle and should
       not be cited as strong evidence.

    The declared wiring and the connection FORM are never verified: MaleCNS v1.0
    annotates synapses, not connection forms.
    """
    pa = anchors["profile_anchors"]
    pidx = anchors["profile_matrix"]["index"]
    psyn = anchors["profile_matrix"]["synapses"]
    sidx = anchors["superclass_matrix"]["index"]
    ssyn = anchors["superclass_matrix"]["synapses"]

    anchored = {m["role"]: pa[m["neuron"]] for m in unit["members"]
                if m["neuron"] in pa}
    role_profile = {m["role"]: m["neuron"] for m in unit["members"]}

    support = []
    for w in unit["internal_wiring"]:
        if w["from"] not in anchored or w["to"] not in anchored:
            continue
        p1 = role_profile[w["from"]]
        p2 = role_profile[w["to"]]
        measured = psyn[pidx[p1]][pidx[p2]]
        coarse = 0
        for s1 in anchored[w["from"]]["superclasses"]:
            for s2 in anchored[w["to"]]["superclasses"]:
                coarse = max(coarse, ssyn[sidx[s1]][sidx[s2]])
        pair = _type_pair_support(anchors, p1, p2)
        support.append({
            "from_role": w["from"], "to_role": w["to"], "form": w["type"],
            "from_population": p1, "to_population": p2,
            "measured_synapses": measured,
            "measured_edges": anchors["profile_matrix"]["edges"][pidx[p1]][pidx[p2]],
            "measured_synapses_superclass_coarse": coarse,
            "type_pair_support": pair,
            "support_tier": pair["support_tier"],
            "contradicted": measured == 0,
        })

    unit["embodiment"] = {
        "populations_anchored": len(anchored),
        "populations_total": len(unit["members"]),
        "real_cells_anchored": sum(a["n_bodies"] for a in anchored.values()),
        "anchored": {r: {"n_bodies": a["n_bodies"], "n_types": a["n_types"],
                         "example_types": [h["type"] for h in a["types"]][:6],
                         "lower_bound": a.get("coverage") == "lower_bound",
                         **({"caveat": a["caveat"]} if a.get("caveat") else {})}
                     for r, a in sorted(anchored.items())},
        "structural_support": support,
        "support_resolution": ("type-pair (per-pair synapse lookup over the "
                               "4,872x4,872 anchored type matrix; SUPPORTED/FRAGILE/"
                               "CONTRADICTED tier) nested on cell-type-set and "
                               "superclass-set totals") if support else None,
        "regions": anchors["regions"]["systems"].get(unit["system"]),
        "anchors_file": ANCHORS_FILE.name,
    }
    unit["provenance"]["embodied_in_malecns"] = bool(anchored)
    unit["provenance"]["embodiment_basis"] = (
        "member populations matched to real annotated MaleCNS v1.0 cell types; "
        "declared wiring and connection FORM NOT verified against the connectome"
        if anchored else
        _unanchored_basis(unit, anchors))
    if not anchored:
        unit["provenance"]["unanchored_reason"] = _unanchored_reason(unit, anchors)
    weight, n_refs = _evidence_weight(unit)
    unit["provenance"]["evidence_weight"] = weight
    if n_refs is not None:
        unit["provenance"]["n_literature_refs"] = n_refs


def _unanchored_reason(unit: dict, anchors: dict) -> str:
    """Machine-checkable reason why a unit carries no anchor.

    Three causes, derived from the profile classification already in the anchor
    artifact so nothing is asserted by hand:
    - identity_not_in_drosophila   a member profile is a cell class that MaleCNS
                                   cannot contain (e.g. thalamic_reticular, retinal_gc)
    - abstract_module_no_cell_type a member profile is a cognitive abstraction
                                   (attention, working_memory, reward) with no cell type
    - taxon_no_malecns_data        members are ordinary neuron types, but from a
                                   species the MaleCNS v1.0 dataset does not cover
    """
    cls = anchors["profile_classification"]
    not_do = set(cls.get("identity_not_drosophila", []))
    abstract = set(cls.get("abstract_cognitive_module", []))
    for m in unit["members"]:
        if m["neuron"] in not_do:
            return "identity_not_in_drosophila"
    for m in unit["members"]:
        if m["neuron"] in abstract:
            return "abstract_module_no_cell_type"
    return "taxon_no_malecns_data"


_UNANCHORED_BASIS = {
    "identity_not_in_drosophila": (
        "a member population is a cell class MaleCNS v1.0 cannot contain "
        "(mammalian-only type, not annotatable in an insect brain)"),
    "abstract_module_no_cell_type": (
        "a member population is a cognitive abstraction with no cell type at any "
        "organism -- the unit is a schema, not an anatomy"),
    "taxon_no_malecns_data": (
        "members are ordinary neuron types, but from a species the MaleCNS v1.0 "
        "dataset does not cover, so no anchor exists to check"),
}


def _unanchored_basis(unit: dict, anchors: dict) -> str:
    return _UNANCHORED_BASIS[_unanchored_reason(unit, anchors)]


def _type_pair_index(anchors: dict) -> dict:
    """Parse the sparse anchored_type_matrix once into {(i, j): (syn, edges)}."""
    cache = anchors.setdefault("_tm_pairs", None)
    if cache is not None:
        return cache
    pairs = {}
    for i, row in enumerate(anchors["anchored_type_matrix"]["rows"]):
        if not row:
            continue
        for tok in row.split(","):
            j_s, syn_s, ed_s = tok.split(":")
            pairs[(i, int(j_s))] = (int(syn_s), int(ed_s))
    anchors["_tm_pairs"] = pairs
    return pairs


def _type_index(anchors: dict) -> dict:
    """Deterministic type name -> row index (sorted dedup of every anchored type).

    Rebuilds the exact `tnames` ordering that build_malecns_anchors.py used
    (`tnames = sorted(anchored_types)`), which is why a re-derivation from the
    artifact alone is sufficient -- no side channel is needed.
    """
    cache = anchors.setdefault("_t_index", None)
    if cache is not None:
        return cache
    names = set()
    for a in anchors["profile_anchors"].values():
        for t in a["types"]:
            names.add(t["type"])
    index = {n: i for i, n in enumerate(sorted(names))}
    anchors["_t_index"] = index
    return index


def _type_pair_support(anchors: dict, p1: str, p2: str) -> dict:
    """Per-type-pair support for one declared edge between two anchored profiles.

    Every (from_type, to_type) pair across the two populations' cell-type sets is
    looked up in the real type-level synapse matrix. This is the resolution at
    which the artifact can actually distinguish "a genuine pathway spread over
    many cell types" from "a profile-level non-zero carried by one lucky pair".
    """
    pa = anchors["profile_anchors"]
    a1, a2 = pa.get(p1), pa.get(p2)
    if not a1 or not a2:
        return {"n_type_pairs": 0, "n_pairs_with_synapses": 0,
                "support_tier": "UNRESOLVED", "top_pairs": [],
                "note": "an endpoint population is not anchored"}
    t_index = _type_index(anchors)
    pairs = _type_pair_index(anchors)
    t1 = [t["type"] for t in a1["types"] if t["type"] in t_index]
    t2 = [t["type"] for t in a2["types"] if t["type"] in t_index]
    hits = []
    for x in t1:
        xi = t_index[x]
        for y in t2:
            v = pairs.get((xi, t_index[y]))
            if v and v[0] > 0:
                hits.append((v[0], x, y))
    hits.sort(key=lambda r: r[0], reverse=True)
    if not hits:
        tier = "CONTRADICTED"
    elif len(hits) == 1:
        tier = "FRAGILE"
    else:
        tier = "SUPPORTED"
    return {
        "n_type_pairs": len(t1) * len(t2),
        "n_pairs_with_synapses": len(hits),
        "support_tier": tier,
        "top_pairs": [{"from_type": x, "to_type": y, "synapses": s}
                      for s, x, y in hits[:3]],
    }


def embodied_units() -> tuple[list, dict]:
    """The units exactly as `main()` writes them, plus the anchors used.

    Module-level `FUNCTIONAL_UNITS` is the *authored* literature source; the
    artifact additionally carries the measured embodiment block. Anything that
    wants to know "what would the generator write" must go through here, or it
    will diff the authored source against the written artifact and see phantom
    drift. Idempotent.
    """
    anchors = _load_anchors()
    for u in FUNCTIONAL_UNITS:
        _embody(u, anchors)
    return FUNCTIONAL_UNITS, anchors


def main() -> int:
    profiles = _load_profiles()
    anchors = _load_anchors()
    cnames = {c["name"] for c in CONNECTION_TYPES}
    unames = {u["name"] for u in FUNCTIONAL_UNITS}
    problems = []

    # 4.1 connection types: unique names, motif_ref must exist in the 40-motif doc
    if len(cnames) != len(CONNECTION_TYPES):
        problems.append("duplicate connection-type names")
    motif_doc = json.loads((MCP / "motifs" / "swarm_agent_topology_motifs.json")
                           .read_text(encoding="utf-8"))
    motif_names = set(motif_doc["motifs"].keys())
    for c in CONNECTION_TYPES:
        if c["motif_ref"] and c["motif_ref"] not in motif_names:
            problems.append("connection %s -> unknown motif_ref %s"
                            % (c["name"], c["motif_ref"]))
        for pkey in ("from_port", "to_port"):
            t = c[pkey].rstrip("*")
            if t and t not in PORT_TYPES and not any(
                    k.startswith(t) for k in PORT_TYPES):
                problems.append("connection %s -> unknown %s type %s"
                                % (c["name"], pkey, c[pkey]))

    # 4.2 units: unique names, members exist, wiring types exist, ports typed,
    #     composable_with resolve, at least one required in+out port
    if len(unames) != len(FUNCTIONAL_UNITS):
        problems.append("duplicate functional-unit names")
    for u in FUNCTIONAL_UNITS:
        roles = {m["role"] for m in u["members"]}
        if len(roles) != len(u["members"]):
            problems.append("unit %s: duplicate role" % u["name"])
        for m in u["members"]:
            if m["neuron"] not in profiles:
                problems.append("unit %s: neural member %s not in MODULE_PROFILES"
                                % (u["name"], m["neuron"]))
        for w in u["internal_wiring"]:
            if w["type"] not in cnames:
                problems.append("unit %s: wiring type %s not a connection type"
                                % (u["name"], w["type"]))
            for side in ("from", "to"):
                if w[side] not in roles:
                    problems.append("unit %s: wiring %s=%s not a declared role"
                                    % (u["name"], side, w[side]))
        # every unit must accept at least one signal (required or not -- a
        # modulatory source like the dopamine unit legitimately has no MANDATORY
        # input) and must produce at least one mandatory output.
        if not u["ports"]["in"]:
            problems.append("unit %s: no IN port at all" % u["name"])
        if not any(p["required"] for p in u["ports"]["out"]):
            problems.append("unit %s: no required OUT port" % u["name"])
        for side in ("in", "out"):
            for p in u["ports"][side]:
                if p["type"] == "*":
                    continue
                # a trailing `*` is a family wildcard: `sensory.*` admits every
                # port type whose name starts with `sensory.`
                if p["type"].endswith(".*"):
                    fam = p["type"][:-1]
                    if not any(k.startswith(fam) for k in PORT_TYPES):
                        problems.append("unit %s: port %s -> unknown family %s"
                                        % (u["name"], p["name"], p["type"]))
                elif p["type"] not in PORT_TYPES:
                    problems.append("unit %s: port %s -> unknown type %s"
                                    % (u["name"], p["name"], p["type"]))
        for other in u["composable_with"]:
            if other not in unames:
                problems.append("unit %s: composable_with %s unknown" % (u["name"], other))
        if len(u["members"]) < 1:
            problems.append("unit %s: empty member list" % u["name"])
        # count_ratio should sum to ~1.0
        s = sum(m["count_ratio"] for m in u["members"])
        if abs(s - 1.0) > 0.05:
            problems.append("unit %s: count_ratio sums to %.2f" % (u["name"], s))

    # 4.3 at least one unit must use each high-value connection family -- keeps
    #     the library honest about "all connection forms are actually usable"
    used = {w["type"] for u in FUNCTIONAL_UNITS for w in u["internal_wiring"]}
    for fam in ("micro", "circuit", "modulatory", "electrical", "plasticity", "macro"):
        fam_names = {c["name"] for c in CONNECTION_TYPES if c["family"] == fam}
        if not (fam_names & used):
            problems.append("connection family %s is never wired by any unit" % fam)

    # 4.4 embodiment: attach the measured anchor, then verify its own invariants
    for u in FUNCTIONAL_UNITS:
        _embody(u, anchors)
    for u in FUNCTIONAL_UNITS:
        e = u["embodiment"]
        if u["provenance"]["embodied_in_malecns"] != (e["populations_anchored"] > 0):
            problems.append("unit %s: embodied_in_malecns disagrees with "
                            "populations_anchored" % u["name"])
        if e["populations_anchored"] > e["populations_total"]:
            problems.append("unit %s: anchored more populations than it has" % u["name"])
    anchored_populations = {m["neuron"] for u in FUNCTIONAL_UNITS for m in u["members"]
                            if m["neuron"] in anchors["profile_anchors"]}
    support_edges = [(u["name"], s) for u in FUNCTIONAL_UNITS
                     for s in u["embodiment"]["structural_support"]]
    measured_contradictions = sorted(
        {"unit": n, "edge": "%s->%s" % (s["from_role"], s["to_role"])}
        for n, s in support_edges if s["contradicted"])
    acknowledged = sorted({"unit": c["unit"], "edge": c["edge"]}
                          for c in ACKNOWLEDGED_CONTRADICTIONS)
    if measured_contradictions != acknowledged:
        new = [c for c in measured_contradictions if c not in acknowledged]
        gone = [c for c in acknowledged if c not in measured_contradictions]
        if new:
            problems.append("unacknowledged contradiction(s): %s -- either fix the "
                            "declared edge or register it in "
                            "ACKNOWLEDGED_CONTRADICTIONS with a reason" % new)
        if gone:
            problems.append("acknowledged contradiction(s) no longer detected: %s -- "
                            "remove them from ACKNOWLEDGED_CONTRADICTIONS" % gone)

    # 4.5 support tier: the type-pair verdict must agree with the profile verdict
    tier_counts = {"SUPPORTED": 0, "FRAGILE": 0, "CONTRADICTED": 0, "UNRESOLVED": 0}
    for n, s in support_edges:
        tier = s.get("support_tier")
        if tier not in tier_counts:
            problems.append("unit %s edge %s->%s: unknown support_tier %r"
                            % (n, s["from_role"], s["to_role"], tier))
            continue
        tier_counts[tier] += 1
        pp = s.get("type_pair_support", {})
        if pp.get("support_tier") != tier:
            problems.append("unit %s edge %s->%s: support_tier %r disagrees with "
                            "type_pair_support.support_tier %r"
                            % (n, s["from_role"], s["to_role"], tier,
                               pp.get("support_tier")))
        if tier == "CONTRADICTED" and not s["contradicted"]:
            problems.append("unit %s edge %s->%s: tier CONTRADICTED but profile "
                            "measured non-zero" % (n, s["from_role"], s["to_role"]))
        if tier != "CONTRADICTED" and s["contradicted"]:
            problems.append("unit %s edge %s->%s: profile measured 0 but tier is %r"
                            % (n, s["from_role"], s["to_role"], tier))
        if tier == "SUPPORTED" and pp.get("n_pairs_with_synapses", 0) < 2:
            problems.append("unit %s edge %s->%s: SUPPORTED needs >=2 type pairs with "
                            "synapses" % (n, s["from_role"], s["to_role"]))
        if tier == "FRAGILE" and pp.get("n_pairs_with_synapses", 0) != 1:
            problems.append("unit %s edge %s->%s: FRAGILE needs exactly 1 type pair "
                            "with synapses" % (n, s["from_role"], s["to_role"]))

    # 4.6 unanchored reason must be one of the enum and must be present on every
    #     unanchored unit (gap-3 honesty: a reader must not have to guess why)
    for u in FUNCTIONAL_UNITS:
        embodied = u["provenance"]["embodied_in_malecns"]
        reason = u["provenance"].get("unanchored_reason")
        if embodied:
            if reason is not None:
                problems.append("unit %s is embodied but carries unanchored_reason %r"
                                % (u["name"], reason))
            continue
        if reason not in _UNANCHORED_BASIS:
            problems.append("unit %s: unanchored_reason %r is not one of %s"
                            % (u["name"], reason, sorted(_UNANCHORED_BASIS)))
        if u["provenance"].get("embodiment_basis") != _UNANCHORED_BASIS[reason]:
            problems.append("unit %s: embodiment_basis is not derived from "
                            "unanchored_reason %r" % (u["name"], reason))

    if problems:
        print("REFUSING TO WRITE -- %d problem(s):" % len(problems))
        for p in problems:
            print("  -", p)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stats = {
        "functional_units": len(FUNCTIONAL_UNITS),
        "connection_types": len(CONNECTION_TYPES),
        "neural_members_referenced": len({m["neuron"] for u in FUNCTIONAL_UNITS
                                          for m in u["members"]}),
        "systems": sorted({u["system"] for u in FUNCTIONAL_UNITS}),
        "connection_families": sorted({c["family"] for c in CONNECTION_TYPES}),
        "connection_types_used_by_units": len(used),
        "embodied_units": sum(1 for u in FUNCTIONAL_UNITS
                              if u["provenance"]["embodied_in_malecns"]),
        "embodied_populations_referenced": len(anchored_populations),
        "embodied_real_cells_referenced": sum(
            anchors["profile_anchors"][n]["n_bodies"] for n in anchored_populations),
        "structural_support_edges_measured": len(support_edges),
        "structural_support_edges_contradicted": len(measured_contradictions),
        "structural_support_edges_fragile": tier_counts["FRAGILE"],
        "structural_support_edges_supported": tier_counts["SUPPORTED"],
        "support_resolution": "type-pair",
        "contradictions_acknowledged": len(acknowledged),
    }

    units_doc = {
        "schema_version": "1.0",
        "source": "Curated cross-species comparative neuroscience; NOT extracted "
                  "from MaleCNS v1.0 (see per-unit provenance.extracted_from_malecns).",
        "caveat": "A functional unit is a curated sub-circuit pattern, not a "
                  "measured cell assembly. Members name neuron populations from "
                  "synthetic_bio_topology.MODULE_PROFILES; ratios are composition "
                  "weights, not measured cell counts. Treat as a compositional "
                  "scaffold with literature provenance, not as ground truth. "
                  "Where `embodiment.populations_anchored` > 0 the member populations "
                  "DO correspond to real annotated MaleCNS v1.0 cell types, but the "
                  "declared wiring and its connection FORM remain literature-derived -- "
                  "see `provenance.extracted_from_malecns` (false everywhere).",
        "port_types": PORT_TYPES,
        "port_types_classified": _classify_port_types(),
        "stats": stats,
        "embodiment_source": {
            "file": ANCHORS_FILE.name,
            "schema_version": anchors["schema_version"],
            "sha256": hashlib.sha256(ANCHORS_FILE.read_bytes()).hexdigest(),
            "anchored_profiles": anchors["summary"]["anchored_profiles"],
            "anchored_real_cells": anchors["summary"]["anchored_real_cells"],
            "anchored_types": anchors["summary"]["anchored_types"],
            "measured_synapses_neuron_subgraph":
                anchors["validation"]["measured_synapses_neuron_subgraph"],
            "measured_edges_neuron_subgraph":
                anchors["validation"]["measured_edges_neuron_subgraph"],
            "scope": "Presence + non-contradiction only. A matched population proves "
                     "the parts exist in the real connectome; a nonzero measured "
                     "pathway proves the declared edge is not contradicted at cell-type "
                     "resolution. Neither proves the declared microcircuit or connection "
                     "form. Declared edges measured at ZERO synapses are listed in "
                     "`contradicted_edges` and are UNSUPPORTED, not supported.",
            "contradicted_edges": measured_contradictions,
            "acknowledged_contradictions": [
                {"unit": c["unit"], "edge": c["edge"], "reason": c["reason"]}
                for c in ACKNOWLEDGED_CONTRADICTIONS],
        },
        "how_to_compose": [
            "1. pick units by `capability` / `lead_task_hint`;",
            "2. join an out-port to an in-port whose `type` matches (or via a "
            "connection type whose from_port/to_port constraints admit both);",
            "3. validate with compose_from_units(); it checks port type "
            "compatibility, required-port satisfaction and acyclicity policy.",
        ],
        "units": FUNCTIONAL_UNITS,
    }
    conn_doc = {
        "schema_version": "1.0",
        "source": "%d of the %d connection forms map onto the curated motif "
                  "document (motifs/swarm_agent_topology_motifs.json); the other "
                  "%d are new forms introduced by this library."
                  % (sum(1 for c in CONNECTION_TYPES if c["motif_ref"]),
                     len(CONNECTION_TYPES),
                     sum(1 for c in CONNECTION_TYPES if not c["motif_ref"])),
        "caveat": "Connection forms are qualitative taxonomies. `parameters` are "
                  "literature-scale defaults for simulation, not fitted values.",
        "families": {
            "micro": "point-to-point chemical synaptic contact sites",
            "circuit": "multi-neuron recurrent/feedforward motifs",
            "modulatory": "diffuse / volume / retrograde modulation",
            "electrical": "gap-junction, ephaptic and glial coupling",
            "plasticity": "activity-dependent weight change rules",
            "macro": "population-level projection geometry",
        },
        "stats": stats,
        "connection_types": CONNECTION_TYPES,
    }
    (OUT_DIR / "functional_units.json").write_text(
        json.dumps(units_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "connection_types.json").write_text(
        json.dumps(conn_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("WROTE functional_units.json + connection_types.json")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


# ====================================================================== #
# v1.4.1 CROSS-CLADE EXTENSION -- insect / bird / fish / cephalopod
# ----------------------------------------------------------------------
# The first 40 units were (with two exceptions) mammalian-cortex shaped.
# These 16 add functions that have NO vertebrate-cortex equivalent: sparse
# mushroom-body coding, a ring-attractor heading system, a synfire timing
# chain for song, a single-cell escape command neuron, active electro-
# location with reafference cancellation, and a cephalopod learning lobe
# whose rule is repeated-activation facilitation. Same algebra, same ports.
# ====================================================================== #
PORT_TYPES.update({
    "sensory.skylight_compass":  "Polarised-light / sun-compass heading cue (insect central complex).",
    "sensory.electric.ampullary": "Low-frequency passive electric-field signal (prey bioelectric field).",
    "sensory.electric.tuberous": "High-frequency active-electrolocation signal (own EOD amplitude + phase).",
    "sensory.lateral_line":      "Water-flow / pressure-wave signal from the lateral line.",
    "sensory.auditory.startle":  "Abrupt acoustic transient able to trigger a startle response.",
    "olfactory.sparse_code":     "Sparse high-dimensional odour code (mushroom-body Kenyon-cell output).",
    "olfactory.learned_valence": "Learned appetitive/aversive value attached to an odour.",
    "navigation.heading":        "Angular head-direction (bearing) estimate.",
    "navigation.steering":       "Turn command that reduces the heading-to-goal error.",
    "navigation.ego_speed":      "Forward / self-motion speed estimate.",
    "clock.phase":               "Circadian phase signal.",
    "memory.associative":        "Recurrently stored associative memory trace.",
    "motor.song":                "Vocal-motor command (syllable timing and syringeal drive).",
    "motor.escape":              "All-or-none escape motor command (C-start).",
    "motor.chromatophore":       "Skin-pattern display command (chromatophore radial muscles).",
    "motor.arm":                 "Arm motion command issued from the arm nerve cord.",
    "motor.eod":                 "Electric-organ discharge command.",
    "efference.copy":            "Efference copy / corollary discharge of a self-generated motor command.",
})


CONNECTION_TYPES += [
    # ---------------- v1.4.1 forms (8) ------------------------------------ #
    C("sparse_expansion_projection", "macro", "稀疏展开投射",
      "A few input channels fan out onto a very large population of which only "
      "a small fraction is active per stimulus -- the mushroom-body Kenyon-cell code.",
      "*", "*", "+", "one_to_many", "either", "immediate", False, None,
      {"expansion_factor": 50, "active_fraction": 0.05},
      "Turner et al 2008; Caron et al 2013"),
    C("global_inhibitory_gain_control", "circuit", "全局抑制增益控制",
      "One wide-field inhibitory cell sums the whole population and feeds back "
      "onto all of it, enforcing sparseness (APL onto Kenyon cells).",
      "*", "*", "-", "one_to_many", "intra_unit", "immediate", False, "inhibitory_hub",
      {"divisive_gain": 0.7}, "Wilson & Laurent 2005; Papadopoulou et al 2011"),
    C("neural_chain_sequence", "circuit", "链式顺序激活",
      "A synfire-like chain in which each element activates the next after a short "
      "delay, turning a static command into a temporal sequence (HVC song timing).",
      "*", "*", "+", "one_to_one", "intra_unit", "short", True, None,
      {"chain_length": 8, "jitter_ms": 5}, "Long et al 2010; Picardo et al 2016"),
    C("efference_copy_cancellation", "circuit", "传出副本抵消",
      "A copy of the motor command is sent ahead to sensory areas and subtracted "
      "from the reafferent input, so self-generated signals are not mistaken for "
      "the world (electric-fish EOD; song auditory feedback).",
      "efference.copy", "*", "-", "one_to_one", "inter_unit", "immediate", True, None,
      {"cancellation_gain": 0.9}, "Bell 1981; Crapse & Sommer 2008"),
    C("mixed_electrical_chemical_synapse", "electrical", "电化学混合突触",
      "A contact carrying both a gap-junction conductance and a chemical component; "
      "this is what gives the Mauthner cell its sub-millisecond all-or-none drive.",
      "*", "*", "+/-", "one_to_one", "either", "immediate", False, None,
      {"electrical_fraction": 0.5}, "Korn & Faber 2005; Pereda 2014"),
    C("modulatory_gated_plasticity", "plasticity", "调质门控可塑性",
      "A synapse whose weight changes only when a third, modulatory neuron is "
      "co-active: local learning requires a global reinforcement signal "
      "(DAN onto the Kenyon-cell output synapse).",
      "*", "*", "+/-", "one_to_many", "either", "short", True, None,
      {"gating_threshold": 0.5, "learning_rate": 0.01},
      "Aso et al 2014; Cognigni et al 2018"),
    C("repetitive_activation_lts", "plasticity", "反复激活长时程增强",
      "A brief run of presynaptic spikes produces a lasting increase in release "
      "that outlives the train by many minutes -- the cephalopod vertical-lobe rule.",
      "*", "*", "+", "one_to_one", "intra_unit", "long", True, "ltp_ltd",
      {"pulses_required": 5, "decay_minutes": 30}, "Shomrat et al 2008; Hochner 2012"),
    C("command_neuron_recruitment", "macro", "指令神经元募集",
      "One identified command neuron, once past threshold, recruits an entire "
      "downstream motor pool all-or-none (Mauthner cell; EOD pacemaker nucleus).",
      "*", "*", "+", "one_to_one", "intra_unit", "immediate", False, None,
      {"threshold": 0.8, "all_or_none": True}, "Korn & Faber 2005; Eaton et al 2001"),
]


FUNCTIONAL_UNITS += [
    # ================= INSECT (6) ================= #
    U("antennal_lobe_glomerular_unit", "触角叶球状体单元", "odour_encode", "antennal_lobe",
      "感受神经元投射到球状体，局部中间神经元做跨球归一化，投射神经元把气味通道送进蘑菇体和高位侧角。",
      [("orn", "antennal_orn", 0.30),
       ("pn", "antennal_lobe_pn", 0.35),
       ("ln", "antennal_lobe_ln", 0.35)],
      [("orn", "pn", "feedforward_excitatory", 1.0),
       ("ln", "pn", "lateral_inhibitory", 0.9),
       ("pn", "ln", "feedforward_excitatory", 0.7),
       ("ln", "ln", "mutual_inhibitory", 0.4)],
      [("odour", "sensory.olfactory", True),
       ("histamine_in", "modulatory.histamine", False)],
      [("pn_out", "sensory.olfactory", True)],
      (40, 160), ["odour_encode", "normalize", "pattern_separate", "background_separate"],
      ["odour_encode", "channel_relay", "background_separate"], "odour_encode",
      ["acetylcholine", "gaba"], "Wilson & Mainen 2006; Olsen & Wilson 2008",
      ["drosophila", "honeybee", "moth"], ("mushroom_body_sparse_code_unit", "lateral_horn_innate_odour_unit")),
    U("mushroom_body_sparse_code_unit", "蘑菇体稀疏编码单元", "sparse_encode", "mushroom_body",
      "投射神经元在约两千个 Kenyon 细胞上随机展开，单个 APL 神经元全局回抑制把活动压到约 5%，得到高维稀疏气味码。",
      [("kc", "kenyon_cell", 0.75),
       ("gaba", "mushroom_body_apl", 0.10),
       ("input", "antennal_lobe_pn", 0.15)],
      [("input", "kc", "sparse_expansion_projection", 1.0),
       ("kc", "gaba", "feedforward_excitatory", 0.9),
       ("gaba", "kc", "global_inhibitory_gain_control", 0.8),
       ("kc", "kc", "lateral_inhibitory", 0.3)],
      [("pn_in", "sensory.olfactory", True)], [("sparse_out", "olfactory.sparse_code", True)],
      (1500, 2500), ["sparse_encode", "pattern_separate", "high_dim_expand", "gain_control"],
      ["sparse_encode", "pattern_separation", "high_dim_hash"], "sparse_encode",
      ["acetylcholine", "gaba", "glutamate"], "Laurent 2002; Turner et al 2008; Papadopoulou et al 2011",
      ["drosophila", "honeybee", "locust"], ("mushroom_body_associative_memory_unit",)),
    U("mushroom_body_associative_memory_unit", "蘑菇体联想记忆单元", "associative_learn", "mushroom_body",
      "多巴胺能神经元把奖赏/惩罚送到 Kenyon 细胞输出突触上做门控，只有气味与效价同时出现时权重才变，读出由 MBON 完成。",
      [("kc", "kenyon_cell", 0.55),
       ("mbon", "mushroom_body_output", 0.20),
       ("dan", "mushroom_body_dan", 0.15),
       ("gaba", "mushroom_body_apl", 0.10)],
      [("kc", "mbon", "modulatory_gated_plasticity", 1.0),
       ("dan", "kc", "modulatory_diffuse", 0.8),
       ("gaba", "kc", "global_inhibitory_gain_control", 0.7),
       ("mbon", "dan", "feedback_excitatory", 0.4)],
      [("sparse_code", "olfactory.sparse_code", True),
       ("value_in", "modulatory.dopamine", False)],
      [("learned_valence", "olfactory.learned_valence", True),
       ("memory_trace", "memory.associative", True)],
      (1500, 2500), ["associative_learn", "valence_assign", "credit_assign", "memory_write"],
      ["associative_learn", "reward_punish", "valence_readout"], "associative_learn",
      ["acetylcholine", "dopamine", "gaba"], "Heisenberg 2003; Aso et al 2014; Cognigni et al 2018",
      ["drosophila", "honeybee"], ("central_complex_steering_unit",)),
    U("central_complex_heading_unit", "中央复合体头向单元", "heading_track", "central_complex",
      "脑桥与椭球体构成环形吸引子，环神经元整形出单个活动峰，峰的位置就是当前朝向，给出不依赖视觉瞬时输入的方位记忆。",
      [("pb", "central_complex_pb", 0.35),
       ("eb", "central_complex_eb", 0.35),
       ("ring", "central_complex_ring", 0.30)],
      [("pb", "eb", "feedforward_excitatory", 1.0),
       ("eb", "pb", "feedback_excitatory", 0.9),
       ("ring", "eb", "lateral_inhibitory", 0.8),
       ("ring", "pb", "lateral_inhibitory", 0.6)],
      [("compass_in", "sensory.skylight_compass", True),
       ("steer_in", "navigation.steering", False),
       ("clock_in", "clock.phase", False)],
      [("heading_out", "navigation.heading", True)],
      (60, 200), ["ring_attractor", "heading_track", "angular_integrate", "bump_sharpen"],
      ["heading_track", "angular_code", "ring_attractor"], "heading_track",
      ["acetylcholine", "gaba"], "Seelig & Jayaraman 2015; Green et al 2017; Turner-Evans et al 2017",
      ["drosophila", "locust", "monarch_butterfly"], ("central_complex_steering_unit",)),
    U("central_complex_steering_unit", "中央复合体转向单元", "steering", "central_complex",
      "扇形体的分层目标图把当前朝向与期望朝向的差转成转向量，结节提供自身速度门控，下行神经元把指令送进腹神经索。",
      [("fb", "central_complex_fb", 0.40),
       ("nod", "central_complex_noduli", 0.25),
       ("dn", "descending_neuron", 0.35)],
      [("nod", "fb", "feedforward_excitatory", 1.0),
       ("fb", "dn", "feedforward_excitatory", 0.9),
       ("dn", "fb", "feedback_inhibitory", 0.4),
       ("dn", "nod", "feedforward_excitatory", 0.5)],
      [("heading_in", "navigation.heading", True),
       ("speed_in", "navigation.ego_speed", False),
       ("valence_in", "olfactory.learned_valence", False),
       ("orexin_in", "modulatory.orexin", False),
       ("assoc_mem_in", "memory.associative", False)],
      [("turn_cmd", "navigation.steering", True), ("motor_cmd", "motor.command", True)],
      (60, 250), ["steering", "goal_bearing", "heading_correct", "descending_command"],
      ["steering", "goal_bearing", "heading_correct"], "steering",
      ["acetylcholine"], "Strausfeld 1999; Green et al 2017; Rayshubskiy et al 2020",
      ["drosophila", "locust"], ("central_complex_heading_unit",)),
    U("insect_clock_pacemaker_unit", "昆虫生物钟起搏单元", "circadian_pace", "circadian",
      "小腹侧侧神经元以 PDF 肽与电耦合把昼夜相位分发给侧神经元网络，松果体作为跨物种的褪黑素效应端被一并纳入。",
      [("pacemaker", "clock_neuron_slnv", 0.40),
       ("network", "clock_neuron_ln", 0.35),
       ("effector", "pineal", 0.25)],
      [("pacemaker", "network", "gap_junction_sync", 1.0),
       ("network", "pacemaker", "gap_junction_sync", 0.8),
       ("pacemaker", "effector", "modulatory_diffuse", 0.7),
       ("effector", "pacemaker", "feedback_inhibitory", 0.3)],
      [("light_in", "sensory.visual.irradiance", True)], [("phase_out", "clock.phase", True)],
      (20, 200), ["circadian_pace", "phase_lock", "entrain", "rhythm_generate"],
      ["circadian_pace", "phase_lock", "entrain"], "circadian_pace",
      ["pdf_neuropeptide", "gaba"], "Helfrich-Forster 2003; Hastings et al 2018",
      ["drosophila", "mouse", "human"], ("central_complex_heading_unit",)),

    # ================= BIRD (3) ================= #
    U("birdsong_hvc_timing_unit", "鸣唱时序链单元", "sequence_generate", "song_system",
      "HVC 用链式激活把静态前运动指令展开成毫秒级时序，每个神经元在音节的一个极短时间窗内爆发，为下游提供节拍。",
      [("hvc", "hvc_neuron", 0.55),
       ("inh", "interneuron_pv", 0.20),
       ("nif", "nif_neuron", 0.25)],
      [("hvc", "hvc", "neural_chain_sequence", 1.0),
       ("nif", "hvc", "feedforward_excitatory", 0.8),
       ("inh", "hvc", "recurrent_inhibitory", 0.6)],
      [("premotor", "cortex.output", True), ("auditory_fb", "sensory.auditory", False)],
      [("timing_out", "motor.song", True)],
      (20000, 40000), ["sequence_generate", "temporal_chain", "motor_timing", "pattern_clock"],
      ["sequence_generate", "temporal_chain", "motor_timing"], "sequence_generate",
      ["glutamate", "gaba"], "Hahnloser et al 2002; Long & Fee 2008; Picardo et al 2016",
      ["zebra_finch", "canary", "bengalese_finch"], ("birdsong_ra_motor_unit",)),
    U("birdsong_ra_motor_unit", "发声运动输出单元", "vocal_motor", "song_system",
      "RA 把来自 HVC 的时序窗转成对鸣管运动神经元与呼吸运动神经元的爆发式驱动，音节与呼吸必须严格配准。",
      [("ra", "ra_neuron", 0.50),
       ("motor", "spinal_motor_alpha", 0.25),
       ("inh", "interneuron_pv", 0.25)],
      [("ra", "motor", "command_neuron_recruitment", 1.0),
       ("inh", "ra", "feedforward_inhibitory", 0.7),
       ("motor", "ra", "feedback_excitatory", 0.4)],
      [("timing_in", "motor.song", True)], [("song_motor", "motor.song", True)],
      (10000, 20000), ["vocal_motor", "respiration_sync", "syringeal_control", "motor_burst"],
      ["vocal_motor", "respiration_sync", "motor_burst"], "vocal_motor",
      ["glutamate", "gaba"], "Vicario 1991; Sober et al 2008",
      ["zebra_finch", "canary"], ()),
    U("birdsong_basal_ganglia_learning_unit", "发声学习回路单元", "motor_learning", "song_system",
      "前脑通路 Area X 到 DLM 到 LMAN 的基底神经节环路，用听觉误差与多巴胺能价值信号把探索性变异筛选成稳定音节。",
      [("x", "area_x_neuron", 0.35),
       ("dlm", "dlm_neuron", 0.25),
       ("lman", "lman_neuron", 0.25),
       ("msn", "striatal_msn", 0.15)],
      [("x", "dlm", "feedforward_inhibitory", 1.0),
       ("dlm", "lman", "feedforward_excitatory", 0.9),
       ("lman", "x", "feedforward_excitatory", 0.5),
       ("msn", "x", "feedforward_excitatory", 0.6)],
      [("error_in", "sensory.auditory", True), ("value_in", "basal_ganglia.value", True)],
      [("variation_out", "motor.song", True)],
      (50000, 200000), ["explore_variation", "error_correct", "motor_learning", "credit_assign"],
      ["explore_variation", "motor_learning", "credit_assign"], "motor_learning",
      ["gaba", "glutamate", "dopamine"], "Bottjer et al 1984; Mooney 2009; Andalman & Fee 2009",
      ["zebra_finch", "bengalese_finch"], ("birdsong_ra_motor_unit",)),

    # ================= FISH (4) ================= #
    U("startle_escape_command_unit", "逃逸启动指令单元", "escape_trigger", "startle_circuit",
      "侧线或听觉的突然输入经电化学混合突触在亚毫秒内点燃 Mauthner 细胞，单个指令神经元全部或无地召集对侧网状脊髓池，形成 C 型逃逸。",
      [("m", "mauthner_cell", 0.20),
       ("aff", "lateral_line_hair_cell", 0.25),
       ("rs", "reticulospinal_neuron", 0.35),
       ("inh", "spinal_glycinergic", 0.20)],
      [("aff", "m", "mixed_electrical_chemical_synapse", 1.0),
       ("m", "rs", "command_neuron_recruitment", 0.9),
       ("rs", "inh", "feedforward_excitatory", 0.6),
       ("inh", "rs", "mutual_inhibitory", 0.7)],
      [("startle_in", "sensory.auditory.startle", True),
       ("flow_in", "sensory.lateral_line", False),
       ("threat_in", "sensory.electric.ampullary", False)],
      [("escape_cmd", "motor.escape", True)],
      (100, 400), ["escape_trigger", "fast_command", "contralateral_turn", "all_or_none"],
      ["escape_trigger", "command_neuron", "fast_command"], "escape_trigger",
      ["glutamate", "glycine"], "Zottoli 1977; Eaton et al 2001; Korn & Faber 2005",
      ["zebrafish", "goldfish", "lamprey"], ("passive_electroreception_unit",)),
    U("passive_electroreception_unit", "被动电感受单元", "passive_electrolocate", "electrosensory",
      "壶腹型感受器探测猎物肌肉与鳃产生的低频弱电场，电感受侧线叶把三叉神经输入变成方向性猎物向量。",
      [("amp", "electroreceptor_ampullary", 0.35),
       ("ell", "ells_pyramidal", 0.40),
       ("inh", "electrosensory_inhibitory_interneuron", 0.25)],
      [("amp", "ell", "feedforward_excitatory", 1.0),
       ("inh", "ell", "lateral_inhibitory", 0.8),
       ("ell", "inh", "feedforward_excitatory", 0.6)],
      [("field_in", "sensory.electric.ampullary", True)],
      [("prey_vector", "sensory.electric.ampullary", True)],
      (500, 5000), ["passive_electrolocate", "weak_field_detect", "prey_localize", "dc_encode"],
      ["passive_electrolocate", "weak_field_detect", "prey_localize"], "passive_electrolocate",
      ["glutamate", "gaba"], "Kalmijn 1974; Bell & Maler 2005",
      ["shark", "ray", "catfish", "platypus"], ("startle_escape_command_unit",)),
    U("electrosensory_electrolocation_unit", "主动电定位单元", "active_electrolocate", "electrosensory",
      "结节型感受器读取自身电器官放电被物体扭曲后的振幅与相位，传出副本先把自身电场分量减掉，剩下的才是外部目标。",
      [("tub", "electroreceptor_tuberous", 0.30),
       ("ell", "ells_pyramidal", 0.40),
       ("inh", "electrosensory_inhibitory_interneuron", 0.15),
       ("relay", "thalamic_relay", 0.15)],
      [("tub", "ell", "feedforward_excitatory", 1.0),
       ("inh", "ell", "contrast_inhibition", 0.8),
       ("ell", "relay", "feedforward_excitatory", 0.8),
       ("relay", "ell", "feedback_inhibitory", 0.4)],
      [("eod_self", "sensory.electric.tuberous", True),
       ("eff_in", "efference.copy", True)],
      [("object_echo", "sensory.electric.tuberous", True)],
      (1000, 10000), ["active_electrolocate", "eod_amplitude", "object_detect", "reafferent_cancel"],
      ["active_electrolocate", "object_detect", "reafferent_cancel"], "active_electrolocate",
      ["glutamate", "gaba"], "Heiligenberg 1991; Bell 2001; Bell & Maler 2005",
      ["gymnotiform", "mormyrid", "electric_ray"], ("electric_organ_discharge_unit",)),
    U("electric_organ_discharge_unit", "电器官放电起搏单元", "pacemaking", "electrosensory",
      "起搏核自主节律发放，经中继核与脊髓运动神经元驱动电器官，同时把传出副本并行送给电感受通路用于抵消。",
      [("pm", "pacemaker_nucleus_neuron", 0.45),
       ("relay", "thalamic_relay", 0.25),
       ("organ", "spinal_motor_alpha", 0.30)],
      [("pm", "relay", "command_neuron_recruitment", 1.0),
       ("relay", "organ", "feedforward_excitatory", 0.9),
       ("relay", "pm", "feedback_inhibitory", 0.3),
       ("pm", "pm", "autapse_recurrent", 0.4)],
      [("arousal_in", "arousal.state", True)],
      [("eod_out", "motor.eod", True), ("eff_out", "efference.copy", True)],
      (50, 200), ["pacemaking", "eod_generate", "efference_copy", "rhythm_generate"],
      ["pacemaking", "eod_generate", "rhythm_generate"], "pacemaking",
      ["acetylcholine", "glutamate"], "Bennett 1971; Bell et al 1997",
      ["gymnotiform", "mormyrid"], ("electrosensory_electrolocation_unit",)),

    # ================= CEPHALOPOD (3) ================= #
    U("cephalopod_vertical_lobe_learning_unit", "头足类垂直叶学习单元", "associative_learn", "vertical_lobe",
      "小细胞把视觉/触觉/化学触觉汇聚进垂直叶，无长突细胞连续数次发放后对大型细胞输出突触产生持续增强，学习规则是反复激活而非成对 STDP。",
      [("sa", "vertical_lobe_small_cell", 0.40),
       ("lg", "vertical_lobe_large_cell", 0.30),
       ("am", "vertical_lobe_amacrine_cell", 0.30)],
      [("sa", "am", "feedforward_excitatory", 1.0),
       ("am", "lg", "repetitive_activation_lts", 0.9),
       ("lg", "am", "feedback_inhibitory", 0.5),
       ("sa", "lg", "feedforward_inhibitory", 0.4)],
      [("multimodal_in", "cortex.association", True),
       ("reward_in", "modulatory.acetylcholine", False)],
      [("learned_cmd", "motor.command", True)],
      (100000, 500000), ["associative_learn", "long_term_facilitation", "multimodal_bind", "command_release"],
      ["associative_learn", "long_term_facilitation", "command_release"], "associative_learn",
      ["acetylcholine", "gaba"], "Young 1964, 1991; Boycott 1961; Shomrat et al 2008",
      ["octopus", "cuttlefish", "squid"],
      ("cephalopod_chromatophore_control_unit", "cephalopod_arm_motor_unit")),
    U("cephalopod_chromatophore_control_unit", "色素细胞控制单元", "camouflage", "chromatophore",
      "额上叶高层指令经色素细胞运动神经元控制放射肌，把色素囊撑开或收拢，在不到一秒内铺出整片皮肤图案。",
      [("cmd", "superior_frontal_lobe_cell", 0.40),
       ("mn", "chromatophore_motor_neuron", 0.40),
       ("ach", "cholinergic_mt", 0.20)],
      [("cmd", "mn", "feedforward_excitatory", 1.0),
       ("ach", "mn", "modulatory_diffuse", 0.6),
       ("mn", "cmd", "feedback_inhibitory", 0.3)],
      [("display_cmd", "cortex.output", True), ("visual_in", "sensory.visual", False)],
      [("skin_pattern", "motor.chromatophore", True)],
      (20000, 200000), ["camouflage", "pattern_display", "muscle_drive", "body_signalling"],
      ["camouflage", "pattern_display", "body_signalling"], "camouflage",
      ["glutamate", "acetylcholine"], "Hanlon & Messenger 1996; Messenger 2001",
      ["octopus", "cuttlefish", "squid"], ()),
    U("cephalopod_arm_motor_unit", "腕运动单元", "arm_control", "arm_cord",
      "腕的神经索自带运动神经元与感觉传入，脑只下达粗略高层指令，精细运动与本体感觉闭环都在腕内本地完成。",
      [("mn", "arm_motor_neuron", 0.55),
       ("aff", "arm_sensory_afferent", 0.30),
       ("mod", "cholinergic_mt", 0.15)],
      [("aff", "mn", "feedforward_excitatory", 1.0),
       ("mod", "mn", "modulatory_diffuse", 0.5),
       ("mn", "aff", "feedback_inhibitory", 0.4),
       ("mn", "mn", "recurrent_excitatory", 0.3)],
      [("arm_cmd", "cortex.output", True)],
      [("arm_motion", "motor.arm", True), ("proprio_out", "motor.spindle", False)],
      (10000, 100000), ["arm_control", "distributed_motor", "reach", "proprioception"],
      ["arm_control", "distributed_motor", "reach"], "arm_control",
      ["acetylcholine", "glutamate"], "Young 1965; Sumbre et al 2001; Zullo et al 2009",
      ["octopus", "squid"], ()),
]


# ----------------------------------------------------------------------
# v1.6.0 batch: RHYTHM, STATE and ERROR.
#
# v1.4.1 covered the invertebrate-cortex gap (insect/bird/fish/cephalopod).
# This batch adds three things that batch did not have:
#
#   * SEGMENTAL / PERIPHERAL OSCILLATORS -- a leech half-centre swim CPG, an
#     ascidian larva escape CPG and two molluscan pattern generators. These are
#     the smallest autonomous rhythms in the library: no cortex, no clock gene,
#     just reciprocal inhibition plus adaptation.
#   * NON-CORTICAL SPECIAL SENSES AND STATE MACHINES -- the pit-viper infrared
#     map, the frog tectal prey-release and escape swim, and the mammalian
#     sleep/wake flip-flop with its noradrenergic arousal broadcast.
#   * ERROR TEACHING -- the climbing-fibre / Purkinje microzone pair, which is
#     the one supervised-learning form in the library, plus the VOR adaptation
#     loop that consumes it.
#
# Same algebra, same ports: a unit is still (function, neuron groups, typed
# ports); nothing here claims connectome extraction.
# ====================================================================== #
PORT_TYPES.update({
    "sensory.infrared":      "Infrared (thermal-radiation) signal from a pit organ (trigeminal afferents).",
    "sensory.vibrissa":      "Mechanosensory signal from a single whisker follicle.",
    "thermal.vector":        "Bearing of a warm target derived from the infrared map.",
    "spatial.place_code":    "Population code for the animal's current position.",
    "motor.swim":            "Swim thrust command (segmental / axial musculature).",
    "motor.feeding":         "Ingestive rhythm command (buccal mass protraction/retraction).",
    "motor.respiration":     "Respiratory drive (diaphragmatic / buccal pump).",
    "motor.eye":             "Extraocular muscle command (gaze stabilisation).",
    "motor.strike":          "Ballistic strike command (tongue / fang projection).",
    "motor.whisk":           "Whisker sweep command (follicle muscle drive).",
    "motor.gill":            "Gill-withdrawal effector command.",
    "rhythm.swim":           "Swim-rhythm phase (which half-cycle the oscillator is in).",
    "rhythm.respiratory":    "Respiratory-rhythm phase.",
    "arousal.sleep":         "Sleep-pressure / homeostatic sleep drive.",
    "arousal.wake":          "Wake-promoting drive.",
    "gating.hunger":         "Hunger-state gate on a competing motor programme.",
    "cerebellar.climbing":   "Climbing-fibre teaching signal (error / complex spike).",
    "reafference.tactile":   "Self-generated tactile reafference from active sensing.",
    # ---------------- v1.9.0 additions ------------------------------------ #
    "modulatory.octopamine": "Octopaminergic diffuse modulation (invertebrate "
                             "arousal / effort / gain-set; invertebrate analogue of norepinephrine).",
    "sensory.gustatory":     "Taste signal from proboscis or pharyngeal gustatory neurons.",
    # ---------------- v2.0.0 additions ------------------------------------ #
    "sensory.mechanovibratory": "Airborne vibration / wind signal from a Johnston "
                                "organ or other mechanosensory appendage.",
    "sensory.proprioceptive":  "Joint-angle / body-position signal from stretch "
                               "receptors along the thoracic and leg musculature.",
    "motor.leg":               "Leg walking / steering command to the tarsal motor pools.",
    "motor.wing":              "Wing-flight command (depressor / promoter / haltere drive).",
    "motor.posture":           "Thoracic posture hold command (static stance, not flight).",
    "modulatory.endocrine":    "Peptidergic volume-transmission modulation from "
                               "crustal / ventral-nerve-cord endocrine neurons.",
    # ---------------- v2.3.0 additions ------------------------------------ #
    "gating.attention":        "Attention-priority gate on a competing modulatory "
                               "program (which centrifugal feedback wins).",
})


CONNECTION_TYPES += [
    # ---------------- v1.6.0 forms (8) ------------------------------------ #
    C("half_center_oscillation", "circuit", "半中心振荡",
      "Two reciprocally inhibitory pools plus adaptation: whichever is releasing "
      "the other from inhibition takes the next half-cycle, so a tonic drive "
      "becomes an alternating rhythm with no cell being intrinsically rhythmic "
      "(leech swim CPG; respiratory pre-Botzinger).",
      "*", "*", "+/-", "one_to_many", "either", "short", True, None,
      {"adaptation_time_constant": 0.8, "escape_threshold": 0.4},
      "Marder & Calabrese 1996; Friesen 1989; Kristan et al 2005"),
    C("plateau_potential_bistability", "electrical", "平台电位双稳态",
      "A brief input pushes the cell onto a sustained depolarised plateau that "
      "outlives the stimulus by hundreds of milliseconds; this is what gives a "
      "CPG its commitment and its hysteresis.",
      "*", "*", "+", "one_to_one", "either", "long", True, None,
      {"plateau_duration_ms": 800, "reset_threshold": 0.2},
      "Kiehn 1991; Ramirez et al 2016"),
    C("serotonergic_presynaptic_facilitation", "plasticity", "血清素能突触前易化",
      "A modulatory terminal raises release probability in the sensory neuron "
      "without any postsynaptic depolarisation -- the mechanism of sensitisation "
      "in the Aplysia gill-withdrawal reflex, i.e. a memory stored presynaptically.",
      "*", "*", "+", "one_to_many", "either", "short", True,
      "pre_presynaptic_excitation",
      {"release_gain": 2.0, "camp_dependent": True},
      "Castellucci & Kandel 1976; Kandel 2001"),
    C("short_term_habituation", "plasticity", "短时程习惯化",
      "Repeated activation of the same pathway depresses release, so the same "
      "stimulus produces a progressively smaller response and recovers in minutes "
      "-- the counterweight to presynaptic facilitation.",
      "*", "*", "-", "one_to_one", "either", "short", True,
      "short_term_plasticity", {"depression_per_pulse": 0.15, "recovery_minutes": 10},
      "Castellucci et al 1970; Rankin et al 2009"),
    C("coincidence_detection", "plasticity", "符合检测",
      "The synapse only changes when two inputs arrive together: a single "
      "climbing fibre carrying the error must coincide with parallel-fibre "
      "activity for the Purkinje synapse to depress. Teaching, not correlation.",
      "*", "*", "+/-", "one_to_one", "either", "immediate", True, None,
      {"coincidence_window_ms": 20, "ltd_depth": 0.6},
      "Ito & Kano 1982; Ito 1984; De Zeeuw et al 2011"),
    C("state_switch_bistable", "macro", "双稳态状态切换",
      "Two mutually inhibitory populations with a slow external bias: the circuit "
      "sits in one of two stable states and a small, brief input flips the whole "
      "thing, which is how sleep/wake cannot sit halfway.",
      "*", "*", "+/-", "one_to_many", "either", "long", False, None,
      {"hysteresis": 0.3, "flip_threshold": 0.55},
      "Saper et al 2005; Saper et al 2010"),
    C("grid_phase_precession", "circuit", "网格相位进动",
      "A theta-rhythm reference makes a spatial cell's firing phase advance "
      "linearly with distance travelled, converting a place code into a temporal "
      "code -- the mechanism that lets position be read out by spike timing.",
      "*", "*", "+/-", "one_to_one", "either", "immediate", True, None,
      {"precession_slope": 0.3, "theta_ref_hz": 8},
      "O'Keefe & Recce 1993; Hafting et al 2005; Burgess et al 2007"),
    C("thermal_cross_modal_convergence", "macro", "热-视觉跨模态汇聚",
      "An infrared map and a visual map registered onto the same tectal neurons, "
      "so a warm target is localised in the same coordinates as a seen one and "
      "either modality can drive the strike (pit vipers; vampire bats).",
      "*", "*", "+", "many_to_one", "either", "immediate", False,
      "topographic_mapping", {"registration_tolerance_deg": 5, "gain_visual": 0.6},
      "Hartline et al 2011; Gracheva et al 2010; Newman & Hartline 1982"),
]

# ---------------------------------------------------------------------------
# v2.23.0 — JEV-powered validation of abstraction-level connection types.
# 21 system-level patterns lack a motif_ref because they describe circuit
# architectures, not single-synapse anatomies.  We annotate them with:
#   abstraction_only: True       (no single-synapse motif mapping exists)
#   jev_validation: {            (TypeSafe Jev System One decision model)
#     verdict, literature_p,     (noul: P(peer-reviewed in >=2 papers))
#     computational_p,           (noul: P(published computational model))
#     evidence_score,            (0-10 rubric)
#     evidence_label,            (textbook|well_supported|preliminary|speculative)
#     validated_at,              (ISO timestamp)
#     model_version,             (jev-1.13.0)
#   }
# Cost: 21 calls × 3 questions ≈ $0.0010.  Full JSON: jev_results/.
# ---------------------------------------------------------------------------
_JEV_VALIDATION = {
    "autapse_recurrent":               {"verdict": "PARTIAL",   "literature_p": 0.78, "computational_p": 0.89, "evidence_score": 4, "evidence_label": "preliminary"},
    "coincidence_detection":           {"verdict": "PARTIAL",   "literature_p": 0.85, "computational_p": 0.91, "evidence_score": 4, "evidence_label": "preliminary"},
    "command_neuron_recruitment":      {"verdict": "PARTIAL",   "literature_p": 0.80, "computational_p": 0.73, "evidence_score": 4, "evidence_label": "preliminary"},
    "convergent_fanin":                {"verdict": "SUPPORTED", "literature_p": 0.87, "computational_p": 0.83, "evidence_score": 5, "evidence_label": "well_supported"},
    "corollary_discharge":             {"verdict": "SUPPORTED", "literature_p": 0.96, "computational_p": 0.94, "evidence_score": 5, "evidence_label": "well_supported"},
    "divergent_fanout":                {"verdict": "SUPPORTED", "literature_p": 0.89, "computational_p": 0.82, "evidence_score": 5, "evidence_label": "well_supported"},
    "efference_copy_cancellation":     {"verdict": "SUPPORTED", "literature_p": 0.96, "computational_p": 0.95, "evidence_score": 5, "evidence_label": "well_supported"},
    "gliotransmission_calcium_wave":   {"verdict": "PARTIAL",   "literature_p": 0.94, "computational_p": 0.88, "evidence_score": 4, "evidence_label": "preliminary"},
    "global_broadcast":                {"verdict": "PARTIAL",   "literature_p": 0.50, "computational_p": 0.60, "evidence_score": 3, "evidence_label": "preliminary"},
    "grid_phase_precession":           {"verdict": "SUPPORTED", "literature_p": 0.93, "computational_p": 0.94, "evidence_score": 5, "evidence_label": "well_supported"},
    "half_center_oscillation":         {"verdict": "SUPPORTED", "literature_p": 0.93, "computational_p": 0.96, "evidence_score": 5, "evidence_label": "well_supported"},
    "homeostatic_scaling":             {"verdict": "SUPPORTED", "literature_p": 0.97, "computational_p": 0.96, "evidence_score": 5, "evidence_label": "well_supported"},
    "loop_relay_chain":                {"verdict": "WEAK",      "literature_p": 0.36, "computational_p": 0.55, "evidence_score": 1, "evidence_label": "speculative"},
    "mixed_electrical_chemical_synapse": {"verdict": "PARTIAL", "literature_p": 0.73, "computational_p": 0.82, "evidence_score": 4, "evidence_label": "preliminary"},
    "modulatory_gated_plasticity":     {"verdict": "PARTIAL",   "literature_p": 0.87, "computational_p": 0.91, "evidence_score": 4, "evidence_label": "preliminary"},
    "neural_chain_sequence":           {"verdict": "PARTIAL",   "literature_p": 0.89, "computational_p": 0.95, "evidence_score": 4, "evidence_label": "preliminary"},
    "plateau_potential_bistability":   {"verdict": "PARTIAL",   "literature_p": 0.81, "computational_p": 0.83, "evidence_score": 4, "evidence_label": "preliminary"},
    "sparse_expansion_projection":     {"verdict": "PARTIAL",   "literature_p": 0.80, "computational_p": 0.85, "evidence_score": 4, "evidence_label": "preliminary"},
    "state_gating_modulation":         {"verdict": "PARTIAL",   "literature_p": 0.82, "computational_p": 0.86, "evidence_score": 4, "evidence_label": "preliminary"},
    "state_switch_bistable":           {"verdict": "PARTIAL",   "literature_p": 0.88, "computational_p": 0.93, "evidence_score": 4, "evidence_label": "preliminary"},
    "winner_take_all":                 {"verdict": "SUPPORTED", "literature_p": 0.95, "computational_p": 0.97, "evidence_score": 5, "evidence_label": "well_supported"},
}
# ---------------------------------------------------------------------------
# v2.25.0 — JEV-powered validation of the 45 motif_ref connection types.
# These are the concrete synapse / circuit motifs (axo_dendritic,
# feedforward_excitatory, gap_junction_sync, ...) that already carry a
# motif_ref.  Independent JEV validation gives us a uniform machine-
# readable evidence tier across all 66 connection types.
# Cost: 45 calls × 3 questions ≈ $0.002.  Full JSON: jev_results/motif_*.
# ---------------------------------------------------------------------------
_MOTIF_JEV_VALIDATION = {
    "astrocyte_neuron_tripartite":             {"verdict": "SUPPORTED", "literature_p": 0.93, "computational_p": 0.90, "evidence_score": 5, "evidence_label": "well_supported"},
    "axo_axonic":                              {"verdict": "SUPPORTED", "literature_p": 0.95, "computational_p": 0.86, "evidence_score": 5, "evidence_label": "well_supported"},
    "axo_dendrite_reciprocal":                 {"verdict": "PARTIAL",   "literature_p": 0.83, "computational_p": 0.81, "evidence_score": 4, "evidence_label": "preliminary"},
    "axo_dendritic":                           {"verdict": "SUPPORTED", "literature_p": 0.99, "computational_p": 0.94, "evidence_score": 5, "evidence_label": "well_supported"},
    "axo_somatic":                             {"verdict": "SUPPORTED", "literature_p": 0.98, "computational_p": 0.93, "evidence_score": 5, "evidence_label": "well_supported"},
    "contrast_inhibition":                     {"verdict": "SUPPORTED", "literature_p": 0.89, "computational_p": 0.91, "evidence_score": 5, "evidence_label": "well_supported"},
    "dendritic_computation":                   {"verdict": "SUPPORTED", "literature_p": 0.97, "computational_p": 0.95, "evidence_score": 5, "evidence_label": "well_supported"},
    "dendritic_excitatory_synapse":            {"verdict": "SUPPORTED", "literature_p": 0.96, "computational_p": 0.91, "evidence_score": 5, "evidence_label": "well_supported"},
    "dendritic_inhibitory_synapse":            {"verdict": "SUPPORTED", "literature_p": 0.93, "computational_p": 0.89, "evidence_score": 5, "evidence_label": "well_supported"},
    "dendro_dendritic":                        {"verdict": "SUPPORTED", "literature_p": 0.93, "computational_p": 0.84, "evidence_score": 5, "evidence_label": "well_supported"},
    "disinhibition":                           {"verdict": "SUPPORTED", "literature_p": 0.95, "computational_p": 0.92, "evidence_score": 5, "evidence_label": "well_supported"},
    "ephaptic_coupling":                       {"verdict": "PARTIAL",   "literature_p": 0.81, "computational_p": 0.83, "evidence_score": 4, "evidence_label": "preliminary"},
    "feedback_excitatory":                     {"verdict": "SUPPORTED", "literature_p": 0.86, "computational_p": 0.91, "evidence_score": 5, "evidence_label": "well_supported"},
    "feedback_inhibitory":                     {"verdict": "SUPPORTED", "literature_p": 0.91, "computational_p": 0.93, "evidence_score": 5, "evidence_label": "well_supported"},
    "feedforward_excitatory":                  {"verdict": "SUPPORTED", "literature_p": 0.93, "computational_p": 0.95, "evidence_score": 5, "evidence_label": "well_supported"},
    "feedforward_gating":                      {"verdict": "PARTIAL",   "literature_p": 0.76, "computational_p": 0.84, "evidence_score": 4, "evidence_label": "preliminary"},
    "feedforward_inhibitory":                  {"verdict": "SUPPORTED", "literature_p": 0.97, "computational_p": 0.96, "evidence_score": 5, "evidence_label": "well_supported"},
    "gap_junction_inhibitory":                 {"verdict": "PARTIAL",   "literature_p": 0.78, "computational_p": 0.83, "evidence_score": 4, "evidence_label": "preliminary"},
    "gap_junction_sync":                       {"verdict": "SUPPORTED", "literature_p": 0.98, "computational_p": 0.96, "evidence_score": 5, "evidence_label": "well_supported"},
    "global_inhibitory_gain_control":          {"verdict": "SUPPORTED", "literature_p": 0.93, "computational_p": 0.91, "evidence_score": 5, "evidence_label": "well_supported"},
    "inhibitory_hub":                          {"verdict": "PARTIAL",   "literature_p": 0.62, "computational_p": 0.70, "evidence_score": 3, "evidence_label": "preliminary"},
    "lateral_feedback":                        {"verdict": "PARTIAL",   "literature_p": 0.76, "computational_p": 0.82, "evidence_score": 4, "evidence_label": "preliminary"},
    "lateral_inhibitory":                      {"verdict": "SUPPORTED", "literature_p": 0.98, "computational_p": 0.97, "evidence_score": 5, "evidence_label": "well_supported"},
    "ltp_ltd":                                 {"verdict": "PARTIAL",   "literature_p": 0.83, "computational_p": 0.91, "evidence_score": 4, "evidence_label": "preliminary"},
    "modulatory_diffuse":                      {"verdict": "SUPPORTED", "literature_p": 0.91, "computational_p": 0.87, "evidence_score": 5, "evidence_label": "well_supported"},
    "mutual_inhibitory":                       {"verdict": "SUPPORTED", "literature_p": 0.97, "computational_p": 0.98, "evidence_score": 5, "evidence_label": "well_supported"},
    "neuromodulatory_axon":                    {"verdict": "SUPPORTED", "literature_p": 0.97, "computational_p": 0.83, "evidence_score": 5, "evidence_label": "well_supported"},
    "pre_presynaptic_excitation":              {"verdict": "PARTIAL",   "literature_p": 0.80, "computational_p": 0.76, "evidence_score": 4, "evidence_label": "preliminary"},
    "pre_presynaptic_inhibition":              {"verdict": "SUPPORTED", "literature_p": 0.97, "computational_p": 0.90, "evidence_score": 5, "evidence_label": "well_supported"},
    "recurrent_excitatory":                    {"verdict": "SUPPORTED", "literature_p": 0.97, "computational_p": 0.97, "evidence_score": 5, "evidence_label": "well_supported"},
    "recurrent_feedback":                      {"verdict": "PARTIAL",   "literature_p": 0.60, "computational_p": 0.82, "evidence_score": 3, "evidence_label": "preliminary"},
    "recurrent_inhibitory":                    {"verdict": "SUPPORTED", "literature_p": 0.96, "computational_p": 0.96, "evidence_score": 5, "evidence_label": "well_supported"},
    "repetitive_activation_lts":               {"verdict": "PARTIAL",   "literature_p": 0.84, "computational_p": 0.78, "evidence_score": 4, "evidence_label": "preliminary"},
    "reservoir_smallworld":                    {"verdict": "WEAK",      "literature_p": 0.30, "computational_p": 0.68, "evidence_score": 1, "evidence_label": "speculative"},
    "retrograde_messenger":                    {"verdict": "SUPPORTED", "literature_p": 0.97, "computational_p": 0.85, "evidence_score": 5, "evidence_label": "well_supported"},
    "serotonergic_presynaptic_facilitation":   {"verdict": "SUPPORTED", "literature_p": 0.96, "computational_p": 0.89, "evidence_score": 5, "evidence_label": "well_supported"},
    "short_range_volume":                      {"verdict": "PARTIAL",   "literature_p": 0.56, "computational_p": 0.66, "evidence_score": 2, "evidence_label": "preliminary"},
    "short_term_habituation":                  {"verdict": "SUPPORTED", "literature_p": 0.95, "computational_p": 0.92, "evidence_score": 5, "evidence_label": "well_supported"},
    "short_term_plasticity":                   {"verdict": "SUPPORTED", "literature_p": 0.96, "computational_p": 0.96, "evidence_score": 5, "evidence_label": "well_supported"},
    "shunting_inhibition":                     {"verdict": "SUPPORTED", "literature_p": 0.96, "computational_p": 0.96, "evidence_score": 5, "evidence_label": "well_supported"},
    "stdp_rule":                               {"verdict": "SUPPORTED", "literature_p": 0.95, "computational_p": 0.97, "evidence_score": 5, "evidence_label": "well_supported"},
    "temporal_coherence":                      {"verdict": "PARTIAL",   "literature_p": 0.67, "computational_p": 0.86, "evidence_score": 3, "evidence_label": "preliminary"},
    "thermal_cross_modal_convergence":         {"verdict": "PARTIAL",   "literature_p": 0.78, "computational_p": 0.48, "evidence_score": 4, "evidence_label": "preliminary"},
    "topographic_mapping":                     {"verdict": "SUPPORTED", "literature_p": 0.93, "computational_p": 0.87, "evidence_score": 5, "evidence_label": "well_supported"},
    "volume_transmission":                     {"verdict": "SUPPORTED", "literature_p": 0.94, "computational_p": 0.87, "evidence_score": 5, "evidence_label": "well_supported"},
}
for _ct in CONNECTION_TYPES:
    _name = _ct["name"]
    if _name in _JEV_VALIDATION:
        # Abstraction-level pattern: no single-synapse motif mapping.
        _ct["abstraction_only"] = True
        _ct["jev_validation"] = dict(_JEV_VALIDATION[_name],
                                     validated_at="2026-09-29T15:40:00+08:00",
                                     model_version="jev-1.13.0")
    elif _name in _MOTIF_JEV_VALIDATION:
        # Motif-level synapse / circuit: has a motif_ref, now also JEV-scored.
        _ct["abstraction_only"] = False
        _ct["jev_validation"] = dict(_MOTIF_JEV_VALIDATION[_name],
                                     validated_at="2026-09-30T22:40:00+08:00",
                                     model_version="jev-1.13.0")
    else:
        _ct.setdefault("abstraction_only", False)


FUNCTIONAL_UNITS += [
    # ============ SEGMENTAL / PERIPHERAL OSCILLATORS (4) ============ #
    U("leech_swim_cpg_unit", "水蛭游泳节律单元", "rhythm_generate", "leech_ganglion",
      "体壁运动神经元与一对互相抑制的 CPG 中间神经元构成半中心振荡器，靠交互抑制加适应交替释放，不需要任何细胞自身是节律性的。",
      [("cpg", "leech_cpg_interneuron", 0.45),
       ("mn", "leech_motor_neuron", 0.35),
       ("sens", "leech_mechanosensory_neuron", 0.20)],
      [("cpg", "cpg", "half_center_oscillation", 1.0),
       ("cpg", "mn", "feedforward_excitatory", 0.9),
       ("mn", "cpg", "feedback_inhibitory", 0.5),
       ("sens", "cpg", "feedforward_excitatory", 0.8)],
      [("touch_in", "sensory.somatosensory", True), ("rhythm_in", "rhythm.swim", False)],
      [("swim_rhythm", "rhythm.swim", True), ("motor_out", "motor.swim", True)],
      (200, 600), ["rhythm_generate", "swim_control", "oscillate", "segment_coordinate"],
      ["rhythm_generate", "swim_control", "oscillate"], "rhythm_generate",
      ["acetylcholine", "glutamate"], "Kristan et al 2005; Marder & Calabrese 1996; Friesen 1989",
      ["leech", "medicinal_leech"], ("ascidian_larval_escape_swim_unit",)),
    U("ascidian_larval_escape_swim_unit", "海鞘幼虫逃逸游泳单元", "escape_swim", "ascidian_larva",
      "幼虫眼点感光细胞把阴影信号交给一小群运动神经元，两侧交替发放驱动尾肌摆动，持续不到一秒的逃逸游泳完全由外周回路完成。",
      [("eye", "ascidian_photoreceptor", 0.25),
       ("mn", "ascidian_larval_motor_neuron", 0.50),
       ("inh", "spinal_glycinergic", 0.25)],
      [("eye", "mn", "feedforward_excitatory", 1.0),
       ("mn", "inh", "feedforward_excitatory", 0.7),
       ("inh", "mn", "mutual_inhibitory", 0.8),
       ("mn", "mn", "half_center_oscillation", 0.6)],
      [("light_in", "sensory.visual.irradiance", True), ("rhythm_in", "rhythm.swim", False)],
      [("swim_rhythm", "rhythm.swim", True), ("motor_out", "motor.swim", True)],
      (20, 80), ["escape_swim", "rhythm_generate", "phototaxis", "fast_escape"],
      ["escape_swim", "rhythm_generate", "fast_escape"], "escape_swim",
      ["acetylcholine", "glycine"], "Bone 1958; Nishino et al 2011; Ryan et al 2016",
      ["ciona", "ascidian"], ("frog_escape_swim_unit",)),
    U("aplysia_gill_withdrawal_unit", "海兔缩鳃反射单元", "reflex_plasticity", "aplysia_ganglion",
      "触觉直接驱动缩鳃运动神经元，可被血清素能中间神经元突触前易化放大（敏感化），也可被重复刺激压低（习惯化）——同一突触上并存两种相反的记忆。",
      [("sens", "aplysia_sensory_neuron", 0.30),
       ("mn", "aplysia_motor_neuron", 0.40),
       ("fac", "aplysia_facilitating_interneuron", 0.20),
       ("inh", "interneuron_sst", 0.10)],
      [("sens", "mn", "feedforward_excitatory", 1.0),
       ("fac", "sens", "serotonergic_presynaptic_facilitation", 0.9),
       ("fac", "mn", "modulatory_diffuse", 0.5),
       ("inh", "sens", "short_term_habituation", 0.6),
       ("mn", "sens", "feedback_inhibitory", 0.4)],
      [("siphon_touch", "sensory.somatosensory", True),
       ("modulatory_in", "modulatory.serotonin", False)],
      [("gill_retract", "motor.gill", True)],
      (20, 60), ["reflex", "sensitization", "habituation", "presynaptic_memory"],
      ["reflex", "sensitization", "habituation"], "reflex",
      ["glutamate", "serotonin"], "Kandel 1976; Castellucci & Kandel 1976; Bailey & Chen 1988",
      ["aplysia", "sea_hare"], ("buccal_feeding_cpg_unit",)),
    U("buccal_feeding_cpg_unit", "口球喂食节律单元", "feeding_rhythm", "buccal_ganglion",
      "口球神经节内的 CPG 用相互兴奋加半中心交替，产生咀嚼-吞咽的固定相位序列，饥饿状态只改变节律快慢而不改变相位关系。",
      [("cpg", "buccal_cpg_neuron", 0.55),
       ("mn", "aplysia_motor_neuron", 0.30),
       ("mod", "cholinergic_mt", 0.15)],
      [("cpg", "cpg", "recurrent_excitatory", 0.8),
       ("cpg", "mn", "half_center_oscillation", 0.9),
       ("mn", "cpg", "feedback_excitatory", 0.5),
       ("mod", "cpg", "modulatory_diffuse", 0.6)],
      [("feeding_cmd", "motor.command", True), ("hunger", "gating.hunger", False)],
      [("feeding_rhythm", "motor.feeding", True), ("motor_out", "motor.command", False)],
      (30, 100), ["feeding_rhythm", "rhythm_generate", "ingest", "phase_sequence"],
      ["feeding_rhythm", "rhythm_generate", "ingest"], "feeding_rhythm",
      ["acetylcholine"], "Kupfermann 1974; Cropper et al 1996",
      ["aplysia", "lobster"], ()),

    # ================= INFRARED / AMPHIBIAN (4) ================= #
    U("trigeminal_infrared_map_unit", "三叉红外热图单元", "thermal_imaging", "infrared_pit",
      "颊窝器的三叉神经传入在中脑顶盖铺成一张与视网膜图配准的热图，侧抑制把物体边缘锐化，得到不依赖光照的目标方位。",
      [("aff", "trigeminal_infrared_afferent", 0.40),
       ("map", "infrared_tectal_neuron", 0.40),
       ("inh", "interneuron_sst", 0.20)],
      [("aff", "map", "topographic_mapping", 1.0),
       ("inh", "map", "lateral_inhibitory", 0.8),
       ("map", "inh", "feedforward_excitatory", 0.6)],
      [("thermal_in", "sensory.infrared", True)],
      [("thermal_map", "spatial.map", True), ("thermal_vec", "thermal.vector", False)],
      (200, 2000), ["thermal_imaging", "infrared_localize", "topographic_map", "contrast_enhance"],
      ["thermal_imaging", "infrared_localize", "topographic_map"], "thermal_imaging",
      ["glutamate", "gaba"], "Bullock & Cowles 1952; Gracheva et al 2010; Hartline et al 2011",
      ["python", "rattlesnake", "pit_viper"], ("pit_viper_strike_unit",)),
    U("pit_viper_strike_unit", "蝮蛇弹道袭击单元", "strike", "infrared_pit",
      "红外图与视觉图在同一顶盖神经元上配准，任一模态都能把目标锁进袭击坐标，运动池被全部或无地召集完成弹道出击。",
      [("mm", "optic_tectum_multimodal", 0.35),
       ("ir", "infrared_tectal_neuron", 0.25),
       ("mn", "spinal_motor_alpha", 0.40)],
      [("ir", "mm", "thermal_cross_modal_convergence", 1.0),
       ("mm", "mn", "command_neuron_recruitment", 0.9),
       ("mn", "mm", "feedback_excitatory", 0.4)],
      [("thermal_map", "spatial.map", True), ("visual_map", "sensory.visual", True)],
      [("strike_cmd", "motor.strike", True)],
      (300, 1500), ["strike", "cross_modal_bind", "thermal_target", "ballistic"],
      ["strike", "cross_modal_bind", "ballistic"], "strike",
      ["glutamate", "acetylcholine"], "Kardong & Bels 1998; Hartline et al 2011",
      ["pit_viper", "rattlesnake"], ()),
    U("frog_tectal_prey_capture_unit", "蛙顶盖捕食释放单元", "prey_capture", "optic_tectum",
      "顶盖 T5 类神经元只对移动的小目标放电，一旦越过阈值就以命令神经元方式整段释放舌肌弹射，是「刺激-固定动作模式」的经典实例。",
      [("det", "tectal_prey_detector", 0.45),
       ("mn", "tongue_motor_neuron", 0.35),
       ("inh", "interneuron_pv", 0.20)],
      [("det", "mn", "command_neuron_recruitment", 1.0),
       ("inh", "det", "feedforward_inhibitory", 0.7),
       ("mn", "det", "feedback_inhibitory", 0.4)],
      [("prey_in", "sensory.visual", True)],
      [("capture_cmd", "motor.command", True), ("strike_out", "motor.strike", False)],
      (500, 5000), ["prey_capture", "visual_detect", "ballistic", "fixed_action_pattern"],
      ["prey_capture", "visual_detect", "fixed_action_pattern"], "prey_capture",
      ["glutamate", "gaba"], "Lettvin et al 1959; Ingle 1968; Ewert 1984",
      ["frog", "toad"], ("frog_escape_swim_unit",)),
    U("frog_escape_swim_unit", "蛙逃逸游泳单元", "escape_swim", "reticulospinal",
      "视觉威胁经网状脊髓神经元一次性召集轴向运动池，对侧甘氨酸能抑制保证左右不同时收缩，形成方向明确的逃逸游泳。",
      [("rs", "reticulospinal_neuron", 0.45),
       ("mn", "spinal_motor_alpha", 0.35),
       ("inh", "spinal_glycinergic", 0.20)],
      [("rs", "mn", "command_neuron_recruitment", 1.0),
       ("rs", "inh", "feedforward_excitatory", 0.7),
       ("inh", "mn", "mutual_inhibitory", 0.8),
       ("rs", "rs", "recurrent_excitatory", 0.4)],
      [("threat_in", "sensory.visual", True),
       ("startle_in", "sensory.auditory.startle", False),
       ("rhythm_in", "rhythm.swim", False),
       ("swim_in", "motor.swim", False)],
      [("escape_swim", "motor.escape", True), ("rhythm_out", "rhythm.swim", False)],
      (200, 900), ["escape_swim", "fast_command", "all_or_none", "contralateral_turn"],
      ["escape_swim", "fast_command", "all_or_none"], "escape_swim",
      ["glutamate", "glycine"], "Will 1991; Ewert 1984; Eaton et al 2001",
      ["frog", "xenopus", "lamprey"], ()),

    # ================= ERROR TEACHING / STATE (5) ================= #
    U("cerebellar_climbing_fibre_teaching_unit", "小脑攀爬纤维误差教学单元", "error_teaching", "olivocerebellar",
      "下橄榄把运动误差编码成攀爬纤维的复杂spike，一对一地送到浦肯野细胞；这是全库唯一的监督式教学通路，误差信号本身不带目标值只带方向。",
      [("cf", "climbing_fibre", 0.40),
       ("pc", "cerebellar_purkinje", 0.40),
       ("io", "inferior_olive", 0.20)],
      [("cf", "pc", "coincidence_detection", 1.0),
       ("io", "cf", "feedforward_excitatory", 0.9),
       ("pc", "io", "feedback_inhibitory", 0.5)],
      [("error_in", "error.teaching", True), ("context_in", "cerebellar.input", True)],
      [("climbing_out", "cerebellar.climbing", True)],
      (50, 300), ["error_teaching", "supervised_learn", "credit_assign", "timing_signal"],
      ["error_teaching", "supervised_learn", "timing_signal"], "error_teaching",
      ["glutamate"], "Ito & Kano 1982; Ito 1984; De Zeeuw et al 2011",
      ["mouse", "rat", "human", "electric_fish"],
      ("cerebellar_purkinje_ltd_unit",)),
    U("cerebellar_purkinje_ltd_unit", "浦肯野细胞 LTD 微区单元", "predictive_learn", "cerebellum",
      "颗粒细胞展开成平行纤维与攀爬纤维教学信号在同一浦肯野细胞上符合，只有同时到达才产生 LTD；高尔基与星状细胞把活动限制在微区内。",
      [("gr", "cerebellar_granule", 0.35),
       ("pc", "cerebellar_purkinje", 0.30),
       ("go", "cerebellar_go_cell", 0.20),
       ("sc", "cerebellar_stellate", 0.15)],
      [("gr", "pc", "coincidence_detection", 1.0),
       ("go", "gr", "feedback_inhibitory", 0.8),
       ("sc", "pc", "feedforward_inhibitory", 0.7),
       ("gr", "go", "feedforward_excitatory", 0.6)],
      [("context_in", "cerebellar.input", True), ("teaching_in", "cerebellar.climbing", True)],
      [("purkinje_out", "cerebellar.output", True)],
      (10000, 100000), ["ltd", "predictive_learn", "internal_model", "gain_calibrate"],
      ["ltd", "predictive_learn", "internal_model"], "ltd",
      ["glutamate", "gaba"], "Marr 1969; Albus 1971; Ito 2000",
      ["mouse", "rat", "human"], ("vestibulo_ocular_reflex_unit",)),
    U("vestibulo_ocular_reflex_unit", "前庭眼动适应单元", "gaze_stabilize", "vestibular",
      "前庭毛细胞把头部角加速度经前庭核送到眼外肌，延迟极短；长期配戴棱镜时同一回路借小脑教学信号慢慢重标定，是适应而非反射改变。",
      [("hair", "vestibular_hair", 0.30),
       ("vn", "vestibular_nucleus_neuron", 0.40),
       ("mn", "spinal_motor_alpha", 0.30)],
      [("hair", "vn", "topographic_mapping", 1.0),
       ("vn", "mn", "feedforward_excitatory", 0.9),
       ("mn", "vn", "feedback_inhibitory", 0.5),
       ("vn", "vn", "lateral_inhibitory", 0.4)],
      [("head_motion", "sensory.vestibular", True), ("teaching", "error.teaching", False)],
      [("eye_cmd", "motor.eye", True), ("gaze_out", "motor.command", False)],
      (200, 1000), ["gaze_stabilize", "reflex", "adaptation", "compensatory"],
      ["gaze_stabilize", "reflex", "adaptation"], "gaze_stabilize",
      ["glutamate", "gaba"], "Ito 1982; Lisberger 1988; Boyden et al 2004",
      ["rabbit", "mouse", "monkey"], ()),
    U("respiratory_rhythm_cpg_unit", "呼吸节律起搏单元", "breathing_rhythm", "respiratory",
      "前包钦格复合体用平台电位加抑制性反弹产生吸气-呼气两相节律，膈运动神经元被全量募集，节律快慢受血气和觉醒状态调制。",
      [("pre", "pre_botzinger_neuron", 0.45),
       ("mn", "phrenic_motor_neuron", 0.30),
       ("inh", "interneuron_pv", 0.25)],
      [("pre", "mn", "command_neuron_recruitment", 1.0),
       ("inh", "pre", "recurrent_inhibitory", 0.8),
       ("mn", "pre", "feedback_excitatory", 0.5),
       ("pre", "pre", "plateau_potential_bistability", 0.9)],
      [("chemo_drive", "modulatory.serotonin", True), ("arousal_in", "arousal.state", False)],
      [("breath_out", "motor.respiration", True), ("rhythm_out", "rhythm.respiratory", True)],
      (200, 800), ["breathing_rhythm", "rhythm_generate", "chemo_response", "state_dependent"],
      ["breathing_rhythm", "rhythm_generate", "chemo_response"], "breathing_rhythm",
      ["glutamate", "gaba"], "Smith et al 1991; Feldman et al 2013; Ramirez et al 2016",
      ["mouse", "rat", "human"], ("sleep_wake_flipflop_unit",)),
    U("sleep_wake_flipflop_unit", "睡眠觉醒双稳态单元", "state_switch", "arousal_switch",
      "促睡眠的 VLPO 与促觉醒的蓝斑互相抑制构成双稳态开关，食欲素提供单侧偏置把开关按在清醒一侧；整个系统不允许停在中间态。",
      [("vlpo", "vlpo_neuron", 0.40),
       ("orexin", "orexin_neuron", 0.35),
       ("ne", "noradrenergic_lc", 0.25)],
      [("vlpo", "ne", "mutual_inhibitory", 1.0),
       ("ne", "vlpo", "mutual_inhibitory", 1.0),
       ("orexin", "ne", "state_switch_bistable", 0.9),
       ("orexin", "vlpo", "feedforward_inhibitory", 0.7)],
      [("clock_in", "clock.phase", True), ("homeostatic", "arousal.sleep", False)],
      [("state_out", "arousal.state", True), ("wake_out", "arousal.wake", False)],
      (2000, 20000), ["state_switch", "bistable", "sleep_wake", "hysteresis"],
      ["state_switch", "bistable", "sleep_wake"], "state_switch",
      ["gaba", "orexin"], "Saper et al 2005; Saper et al 2010",
      ["mouse", "rat", "human"], ("locus_coeruleus_arousal_unit",)),

    # ================= NAVIGATION / ACTIVE SENSING (3) ================= #
    U("locus_coeruleus_arousal_unit", "蓝斑去甲肾上腺素唤醒单元", "global_arousal", "locus_coeruleus",
      "蓝斑把显著性信号转成一束弥散去甲肾上腺素，同时经星形胶质细胞的钙波做慢时间尺度的扩散；这不是点对点传递而是全局增益重设。",
      [("ne", "noradrenergic_lc", 0.50),
       ("inh", "interneuron_vip", 0.30),
       ("glia", "astrocyte_reactive", 0.20)],
      [("ne", "inh", "feedforward_excitatory", 0.8),
       ("inh", "ne", "lateral_inhibitory", 0.7),
       ("ne", "glia", "global_broadcast", 0.6),
       ("glia", "ne", "volume_transmission", 0.5)],
      [("salience", "arousal.state", True), ("sleep_drive", "arousal.sleep", False)],
      [("ne_out", "modulatory.noradrenaline", True), ("wake_drive", "arousal.wake", False)],
      (2000, 30000), ["global_arousal", "gain_modulation", "salience_broadcast", "state_gate"],
      ["global_arousal", "gain_modulation", "salience_broadcast"], "global_arousal",
      ["noradrenaline", "gaba"], "Aston-Jones & Cohen 2005; Sara 2009",
      ["mouse", "rat", "human"], ()),
    U("hippocampal_spatial_map_unit", "海马空间地图单元", "spatial_map", "hippocampus",
      "网格细胞提供多尺度度量，头方向细胞提供朝向，位置细胞把两者与 theta 节律的相位进动结合，形成随体重写的位置码。",
      [("place", "place_cell", 0.35),
       ("grid", "grid_cell", 0.30),
       ("hd", "head_direction_cell", 0.20),
       ("inh", "interneuron_pv", 0.15)],
      [("grid", "place", "grid_phase_precession", 1.0),
       ("hd", "place", "feedforward_excitatory", 0.8),
       ("inh", "place", "lateral_inhibitory", 0.6),
       ("place", "grid", "feedback_excitatory", 0.5)],
      [("self_motion", "navigation.ego_speed", True), ("theta_in", "rhythm.theta", True)],
      [("spatial_code", "spatial.place_code", True), ("map_out", "spatial.map", False)],
      (5000, 50000), ["spatial_map", "path_integration", "place_code", "episodic_context"],
      ["spatial_map", "path_integration", "place_code"], "spatial_map",
      ["glutamate", "gaba"], "O'Keefe & Dostrovsky 1971; Hafting et al 2005; Moser et al 2008",
      ["mouse", "rat", "human", "bat"], ()),
    U("barrel_cortex_whisking_unit", "桶状皮层主动触觉单元", "active_touch", "barrel_cortex",
      "胡须运动神经元主动扫动，丘脑中继把每个毛囊的偏转送回同名桶状柱；运动指令的副本与触觉再传入在皮层内比对，主动触碰才可被识别为自己产生的。",
      [("barrel", "barrel_cortex_neuron", 0.45),
       ("relay", "thalamic_relay", 0.25),
       ("mn", "whisker_motor_neuron", 0.30)],
      [("relay", "barrel", "topographic_mapping", 1.0),
       ("barrel", "mn", "feedforward_excitatory", 0.8),
       ("mn", "relay", "feedback_excitatory", 0.6),
       ("barrel", "barrel", "lateral_inhibitory", 0.5)],
      [("touch_in", "sensory.vibrissa", True), ("arousal_in", "arousal.state", False)],
      [("tactile_map", "spatial.map", True), ("whisk_cmd", "motor.whisk", True),
       ("reafference", "reafference.tactile", False)],
      (2000, 15000), ["active_touch", "tactile_map", "sensorimotor_loop", "reafference_separate"],
      ["active_touch", "tactile_map", "sensorimotor_loop"], "active_touch",
      ["glutamate", "gaba"], "Woolsey & Van der Loos 1970; Kleinfeld & Deschenes 2011; Diamond et al 2008",
      ["mouse", "rat"], ()),

    # ==================================================================== #
    # v1.8.0 DROSOPHILA-SHAPED UNITS (9)
    # -------------------------------------------------------------------- #
    # The previous batches made the library wider; this batch makes the
    # FLY-SHAPED part of it denser. Every unit below is composed of
    # populations that anchor to real MaleCNS cell types (34/180 profiles
    # now carry anchor rules), and every declared internal edge was checked
    # against the measured profile x profile matrix BEFORE being written:
    # none of them is a zero. This is the first batch that could fail its
    # own embodiment check, and passed.
    # ==================================================================== #

    # ================= OPTIC LOBE (4) ================= #
    U("compound_lamina_relay_unit", "复眼-板层输入中继单元", "photoreception", "optic_lobe",
      "R1-R6 把每个小眼的亮度/运动通道送入同名板层柱做高通滤波，R7/R8 色觉通道绕过板层直达髓质；两条通道并行，进髓质前互不污染。",
      [("r1r6", "ol_photoreceptor_r1r6", 0.40),
       ("r7r8", "ol_photoreceptor_r7r8", 0.25),
       ("lamina", "ol_lamina_monopolar", 0.35)],
      [("r1r6", "lamina", "feedforward_excitatory", 1.0),
       ("lamina", "lamina", "lateral_inhibitory", 0.5)],
      [("light", "sensory.visual", True)],
      [("lamina_out", "sensory.visual", True), ("colour_bypass", "sensory.visual", False)],
      (800, 12000), ["photorelay", "high_pass_filter", "parallel_channels"],
      ["image_ingest", "photorelay", "contrast_enhance"], "visual_ingest",
      ["histamine", "glutamate"], "Hardie & Raghu 2001; Meinertzhagen & O'Neil 1991",
      ["drosophila"], ("elementary_motion_detection_unit", "medulla_colour_pathway_unit")),
    U("medulla_colour_pathway_unit", "髓质色觉通路单元", "colour_encode", "optic_lobe",
      "R7/R8 直接靶向髓质，经 Tm/Y 与 Dm 系列神经元把紫外/蓝色小目标转成色觉特征；与运动通道分车间计算。",
      [("r7r8", "ol_photoreceptor_r7r8", 0.35),
       ("medulla", "ol_medulla_intrinsic", 0.65)],
      [("r7r8", "medulla", "feedforward_excitatory", 1.0)],
      [("light", "sensory.visual", True)],
      [("colour_feature", "sensory.visual", True)],
      (500, 5000), ["colour_encode", "feature_extract", "parallel_channels"],
      ["colour_encode", "wavelength_detect"], "colour_ingest",
      ["histamine", "acetylcholine"], "Morante & Desplan 2008",
      ["drosophila"], ("visual_target_detection_unit",)),
    U("elementary_motion_detection_unit", "初级运动检测单元", "motion_detect", "optic_lobe",
      "髓质柱状细胞把 ON/OFF 信号分开，T4/T5 四个方向亚型与 LPi 抑制性柱间连接一起完成初级方向检测——果蝇版的 Barlow-Levick。",
      [("medulla", "ol_medulla_intrinsic", 0.55),
       ("t45", "ol_motion_detector_t45", 0.30),
       ("lpi", "ol_lpi", 0.15)],
      [("medulla", "t45", "feedforward_excitatory", 1.0),
       ("medulla", "lpi", "feedforward_excitatory", 0.5),
       ("lpi", "t45", "lateral_inhibitory", 0.7)],
      [("lamina_in", "sensory.visual", True)],
      [("motion", "sensory.visual.motion", True)],
      (200, 5000), ["motion_detect", "direction_select", "on_off_split"],
      ["motion_detect", "direction_encode"], "motion_ingest",
      ["acetylcholine", "gaba"], "Maisak et al 2013; Mauss et al 2015",
      ["drosophila"], ("lobula_plate_optic_flow_unit",)),
    U("lobula_plate_optic_flow_unit", "视叶板光流整合单元", "optic_flow", "optic_lobe",
      "上万个 T4/T5 收敛到几十个切向细胞，LPi 柱间抑制把方向对立面压掉，HS/VS 输出的是整场光流与航向偏差估计。",
      [("t45", "ol_motion_detector_t45", 0.40),
       ("lpi", "ol_lpi", 0.30),
       ("lptc", "ol_lptc", 0.30)],
      [("t45", "lptc", "feedforward_excitatory", 1.0),
       ("lpi", "lptc", "lateral_inhibitory", 0.6)],
      [("motion_in", "sensory.visual.motion", True)],
      [("optic_flow", "sensory.visual.motion", True)],
      (50, 800), ["optic_flow_integrate", "course_estimate", "wide_field_sum"],
      ["optic_flow", "course_control"], "optic_flow",
      ["acetylcholine", "gaba"], "Hausen 1984; Borst & Weber 2011",
      ["drosophila", "blowfly"], ("central_complex_heading_unit",)),
    U("visual_target_detection_unit", "视觉目标检测单元", "target_detect", "optic_lobe",
      "髓质柱状细胞把特征汇聚到 LC 系列，LC 按特征分类（小目标/扩张/朝向）后直接驱动下行神经元——果蝇的『看见并分类』发生在视叶内。",
      [("medulla", "ol_medulla_intrinsic", 0.45),
       ("lc", "ol_visual_lc", 0.35),
       ("dn", "descending_neuron", 0.20)],
      [("medulla", "lc", "feedforward_excitatory", 1.0),
       ("lc", "dn", "feedforward_excitatory", 0.8)],
      [("visual_in", "sensory.visual", True)],
      [("target_cmd", "motor.command", True)],
      (100, 5000), ["target_detect", "feature_classify", "visual_reflex"],
      ["target_detect", "visual_relay"], "target_ingest",
      ["acetylcholine"], "Wu et al 2016; Keles & Frye 2017",
      ["drosophila"], ("giant_fiber_escape_unit",)),

    # ================= ESCAPE / VENTRAL NERVE CORD (1) ================= #
    U("giant_fiber_escape_unit", "巨纤维逃逸单元", "escape_reflex", "ventral_nerve_cord",
      "巨纤维 DNp01 以混合电-化学突触直驱跳肌运动神经元 TTMn（快路径），经 PSI 与 GFC 中继驱 DLM/转肌（强直路径）；全回路延迟以毫秒计。",
      [("gf", "escape_giant_fiber", 0.15),
       ("gfc", "escape_vnc_gfc", 0.30),
       ("psi", "escape_psi", 0.10),
       ("motor", "escape_jump_motor", 0.45)],
      [("gf", "motor", "mixed_electrical_chemical_synapse", 1.0),
       ("gf", "psi", "feedforward_excitatory", 0.7),
       ("gf", "gfc", "feedforward_excitatory", 0.8),
       ("psi", "motor", "axo_dendritic", 0.8),
       ("gfc", "motor", "feedforward_excitatory", 0.9)],
      [("looming", "sensory.visual", True), ("touch", "sensory.somatosensory", False)],
      [("jump", "motor.command", True)],
      (5, 60), ["escape_reflex", "fast_conduction", "mixed_synapse", "startle"],
      ["escape_command", "startle_trigger", "jump_drive"], "escape_execute",
      ["acetylcholine", "glutamate"], "Tanouye & Wyman 1980; Allen et al 2006",
      ["drosophila"], ()),

    # ================= COURTSHIP / SONG (3) ================= #
    U("auditory_song_reception_unit", "求偶歌接收单元", "song_reception", "antennal_mechanosensory",
      "JO 机械感受经听觉神经进入 AMMC，AMMC 把近场声音（求偶歌本身）的特征送到 pIP 与 aSP——雄蝇在听自己该不该唱。",
      [("ammc", "auditory_ammc", 0.50),
       ("pip", "courtship_pip", 0.30),
       ("asp", "courtship_asp", 0.20)],
      [("ammc", "pip", "feedforward_excitatory", 1.0),
       ("ammc", "asp", "feedforward_excitatory", 0.5)],
      [("song", "sensory.auditory", True)],
      [("song_relayed", "sensory.auditory", True)],
      (40, 250), ["song_reception", "mechano_relay", "social_signal"],
      ["song_reception", "auditory_relay"], "song_ingest",
      ["acetylcholine"], "Lefevre et al 2021; Deutsch et al 2020",
      ["drosophila"], ("courtship_decision_unit",)),
    U("courtship_decision_unit", "求偶决策单元", "courtship_decision", "lateral_protocerebrum",
      "pC1 整合信息素与歌声输入，与 vpo 互馈放大决策，aSP 的攻击驱动与之竞争，胜出的决策经 pIP 下行到腹神经索——求偶还是打架在这里分岔。",
      [("pc1", "courtship_pc1", 0.55),
       ("vpo", "song_vpo", 0.15),
       ("asp", "courtship_asp", 0.15),
       ("pip", "courtship_pip", 0.15)],
      [("pc1", "pip", "feedforward_excitatory", 1.0),
       ("pc1", "vpo", "dendro_dendritic", 0.6),
       ("vpo", "pc1", "dendro_dendritic", 0.7),
       ("pc1", "asp", "feedforward_excitatory", 0.5),
       ("asp", "pc1", "mutual_inhibitory", 0.7)],
      [("pheromone", "sensory.olfactory", True), ("song", "sensory.auditory", False)],
      [("courtship_drive", "motor.command", True)],
      (10, 200), ["courtship_decision", "behaviour_gate", "drive_competition", "state_switch"],
      ["courtship_decision", "behaviour_gate"], "courtship_decide",
      ["acetylcholine"], "Clowney et al 2015; Watanabe et al 2017; Deutsch et al 2020",
      ["drosophila"], ("courtship_song_pattern_unit", "antennal_lobe_glomerular_unit")),
    U("courtship_song_pattern_unit", "求偶歌曲模式生成单元", "song_pattern", "ventral_nerve_cord",
      "pIP 下行信号触发 vMS/vPR 歌曲网络，网络靠强自激与脉冲模式开关生成脉冲歌与正弦歌的节律，直接驱动翅肌。",
      [("pip", "courtship_pip", 0.30),
       ("vms", "song_vnc_int", 0.70)],
      [("pip", "vms", "feedforward_excitatory", 1.0),
       ("vms", "vms", "autapse_recurrent", 0.7)],
      [("courtship_in", "motor.command", True)],
      [("song_motor", "motor.command", True)],
      (10, 60), ["song_pattern_generate", "pulse_shape", "rhythm_generate"],
      ["song_pattern", "rhythm_generate"], "song_generate",
      ["acetylcholine"], "von Philipsborn et al 2011; MaleCNS vMS/vPR types",
      ["drosophila"], ()),

    # ================= INNATE ODOUR / LATERAL HORN (1) ================= #
    U("lateral_horn_innate_odour_unit", "侧角先天嗅觉单元", "innate_odour", "lateral_horn",
      "投射神经元把球状体模式并行送进侧角，侧角家族按信息素/利它素类别硬连线赋值并直接驱动下行神经元——不经蘑菇体学习就能闻到就该躲/该追。",
      [("pn", "antennal_lobe_pn", 0.40),
       ("lh", "lateral_horn_ln", 0.40),
       ("dn", "descending_neuron", 0.20)],
      [("pn", "lh", "feedforward_excitatory", 1.0),
       ("lh", "dn", "feedforward_excitatory", 0.7)],
      [("odour", "sensory.olfactory", True)],
      [("innate_action", "motor.command", True)],
      (50, 2000),       ["innate_odour", "pheromone_classify", "hardwired_valence"],
      ["innate_odour", "pheromone_classify"], "innate_olfaction",
      ["acetylcholine", "gaba"], "Jefferis et al 2007; Dolan et al 2019",
      ["drosophila"], ("antennal_lobe_glomerular_unit",)),

    # ==================================================================== #
    # v1.9.0 REMAINING CLEANLY-ANCHORABLE FLY CIRCUITS (3)
    # -------------------------------------------------------------------- #
    # v1.8.0 pushed profile anchoring from 30 to 34 profiles; three further
    # cleanly-anchorable fly populations were queued but their anchor rules
    # never landed (mid-batch break). This batch completes them and turns
    # each into an embodied unit. Discipline unchanged: every declared edge
    # was checked against the measured profile x profile matrix BEFORE being
    # written. Zero-synapse candidates were dropped, not forced through.
    # ==================================================================== #

    # ---------- AROUSAL MODULATION (1) ---------- #
    U("octopamine_arousal_unit", "八胺觉醒调节单元", "arousal_modulate", "modulatory",
      "OA-VUM/OA-VPM 少量（MaleCNS 里 17 个真实细胞 / 9 类）广泛投射，把觉醒-努力设定跨域写到蘑菇体、下行神经元与侧角；无自循环、纯扩散调制。",
      [("vum", "octopamine_vum", 0.35),
       ("kc", "kenyon_cell", 0.20),
       ("mbout", "mushroom_body_output", 0.15),
       ("lh", "lateral_horn_ln", 0.15),
       ("dn", "descending_neuron", 0.15)],
      [("vum", "kc", "feedforward_excitatory", 1.0),
       ("vum", "mbout", "feedforward_excitatory", 0.7),
       ("vum", "lh", "feedforward_excitatory", 0.9),
       ("vum", "dn", "feedforward_excitatory", 0.9)],
      [("arousal", "modulatory.octopamine", True), ("effort", "modulatory.octopamine", False)],
      [("gain_set", "modulatory.octopamine", True)],
      (2, 20), ["arousal_modulate", "gain_control", "effort_set"],
      ["arousal_modulate", "effort_set", "gain_control"], "arousal_modulate",
      ["octopamine"], "Roeder 1999; Schwaerzel et al 2003; Busch et al 2009",
      ["drosophila"], ("courtship_decision_unit", "central_complex_heading_unit")),

    # ---------- LOOMING / COLLISION DETECTION (1) ---------- #
    U("looming_detection_unit", "碰撞逼近检测单元", "looming_detect", "optic_lobe",
      "T4/T5 方向检测把扩张型光流汇聚到 LPLC1/2/4，LPLC 直驱下行神经元触发逃逸——MaleCNS 实测 LPLC→DN 突触数 63,290，是本项目最强单条视觉-运动边。",
      [("medulla", "ol_medulla_intrinsic", 0.25),
       ("t45", "ol_motion_detector_t45", 0.30),
       ("lplc", "looming_lplc", 0.20),
       ("dn", "descending_neuron", 0.25)],
      [("medulla", "t45", "feedforward_excitatory", 1.0),
       ("t45", "lplc", "feedforward_excitatory", 1.0),
       ("lplc", "dn", "feedforward_excitatory", 1.0)],
      [("motion", "sensory.visual.motion", True), ("touch", "sensory.somatosensory", False)],
      [("loom_cmd", "motor.command", True)],
      (50, 800), ["looming_detect", "collision_detect", "expansion_flow"],
      ["looming_detect", "collision_detect"], "looming_detect",
      ["acetylcholine", "gaba"], "de Vries & Clandinin 2012; Klapoetke et al 2017",
      ["drosophila"], ("giant_fiber_escape_unit", "lobula_plate_optic_flow_unit")),

    # ---------- PHARYNGEAL GUSTATORY / FEED DRIVE (1) ---------- #
    U("pharyngeal_gustatory_unit", "咽味觉食欲单元", "taste_encode", "subesophageal_zone",
      "PhG 味觉神经元（48 真实细胞 / 18 类）把吻部味觉信号送入下行神经元并微弱耦合到侧角；MaleCNS 实测 PhG→DN 1,024 突触，PhG→LH 5 突触（稀疏但存在，可能是先天味-信息素整合的边缘通道）。",
      [("phar", "pharyngeal_gustatory", 0.50),
       ("lh", "lateral_horn_ln", 0.20),
       ("dn", "descending_neuron", 0.30)],
      [("phar", "dn", "feedforward_excitatory", 1.0),
       ("phar", "lh", "feedforward_excitatory", 0.5)],
      [("taste", "sensory.gustatory", True)],
      [("feed_drive", "motor.feeding", True)],
      (10, 60), ["taste_encode", "feed_drive", "appetitive_sense"],
      ["taste_encode", "feed_drive"], "taste_encode",
      ["acetylcholine"], "Marella et al 2006; Mann et al 2013",
      ["drosophila"], ("lateral_horn_innate_odour_unit",)),

    # ==================================================================== #
    # v2.0.0 VNC + PERIPHERAL EMBODIED UNITS (7)
    # -------------------------------------------------------------------- #
    # v1.10.0 anchored 20 new VNC / peripheral neuron populations but wired
    # none of them into a functional unit. This batch turns them into units.
    # Discipline unchanged and STRICTER: every declared edge below was looked
    # up in the measured profile x profile synapse matrix (probe_v200_edges.py)
    # BEFORE being written. 28 declared edges, 28 non-zero measured counts,
    # zero contradictions. Edges that measured zero were dropped, not forced.
    # ==================================================================== #

    # ---------- SEGMENTAL SENSORY REFLEX (1) ---------- #
    U("vnc_sensory_reflex_unit", "腹神经索感觉反射单元", "local_reflex", "ventral_nerve_cord",
      "VNC 感觉池（5,605 真实细胞 / 171 类）→ VNC 中间神经元（12,967 细胞 / 2,799 类）是本项目实测最强边，"
      "1,836,902 突触；中间神经元回返 339,844，升/降感觉池各补 154,541 与 6,846，闭成本段反射弧。",
      [("sens", "vnc_sensory_pool", 0.30),
       ("inter", "vnc_interneuron_pool", 0.40),
       ("asc", "sensory_ascending_pool", 0.15),
       ("desc", "sensory_descending_pool", 0.15)],
      [("sens", "inter", "feedforward_excitatory", 1.0),
       ("inter", "sens", "feedback_excitatory", 0.5),
       ("asc", "inter", "feedforward_excitatory", 0.7),
       ("inter", "asc", "feedback_inhibitory", 0.4),
       ("desc", "inter", "feedforward_excitatory", 0.4)],
      [("touch", "sensory.somatosensory", True), ("proprio", "sensory.proprioceptive", False)],
      [("reflex", "motor.command", True)],
      (100, 15000), ["local_reflex", "sensory_motor_loop", "segmental_process"],
      ["local_reflex", "segmental_process"], "local_reflex",
      ["acetylcholine", "glutamate", "gaba"], "Dorkenwald et al 2024; Gershow et al 2001",
      ["drosophila"], ()),

    # ---------- LEG MOTOR POOL (1) ---------- #
    U("leg_motor_pool_unit", "腿运动池单元", "leg_drive", "ventral_nerve_cord",
      "VNC 中间神经元把步态命令送进 TTMn 腿运动池（403 真实细胞 / 84 类），实测 1,205,967 突触；"
      "VNC 感觉与上升感觉池各补 30,913 与 7,991 的足端反馈，运动池回返 11,587 闭环。",
      [("inter", "vnc_interneuron_pool", 0.30),
       ("sens", "vnc_sensory_pool", 0.20),
       ("asc", "sensory_ascending_pool", 0.15),
       ("leg", "vnc_leg_motor_pool", 0.25),
       ("effer", "vnc_efferent_pool", 0.10)],
      [("inter", "leg", "feedforward_excitatory", 1.0),
       ("sens", "leg", "feedforward_excitatory", 0.6),
       ("asc", "leg", "feedforward_excitatory", 0.5),
       ("leg", "inter", "feedback_excitatory", 0.4),
       ("effer", "leg", "feedforward_excitatory", 0.3)],
      [("touch", "sensory.somatosensory", True), ("proprio", "sensory.proprioceptive", True)],
      [("step", "motor.leg", True), ("steer", "motor.leg", False)],
      (50, 500), ["leg_drive", "steering", "locomotion"],
      ["leg_drive", "steering"], "leg_drive",
      ["acetylcholine"], "Dorkenwald et al 2024; Pypaert et al 2014",
      ["drosophila"], ("vnc_sensory_reflex_unit",)),

    # ---------- WING FLIGHT CONTROL (1) ---------- #
    U("wing_flight_control_unit", "翅膀飞行控制单元", "flight_power", "ventral_nerve_cord",
      "VNC 中间神经元同时驱四群胸肌运动池：胸促肌 141,428、飞行动力 144,642、"
      "翅抑肌 43,027、平衡棒肌 84,547 突触；促肌与平衡棒肌各回返 747 与 429 做时序校准。",
      [("inter", "vnc_interneuron_pool", 0.25),
       ("promoter", "pleural_promotor_pool", 0.15),
       ("power", "vnc_flight_power_pool", 0.20),
       ("dep", "wing_depressor_pool", 0.15),
       ("hal", "haltere_muscle_pool", 0.25)],
      [("inter", "promoter", "feedforward_excitatory", 1.0),
       ("inter", "power", "feedforward_excitatory", 0.9),
       ("inter", "dep", "feedforward_excitatory", 0.7),
       ("inter", "hal", "feedforward_excitatory", 0.8),
       ("promoter", "inter", "feedback_excitatory", 0.4),
       ("hal", "inter", "feedback_excitatory", 0.3)],
      [("posture_cmd", "motor.posture", True), ("balance", "sensory.vestibular", False)],
      [("wing_cmd", "motor.wing", True)],
      (10, 100), ["flight_power", "wing_timing", "haltere_balance"],
      ["flight_power", "haltere_balance"], "flight_power",
      ["acetylcholine"], "Dickinson et al 2000; Dorkenwald et al 2024",
      ["drosophila"], ("giant_fiber_escape_unit",)),

    # ---------- JOHNSTON ORGAN WIND DETECTION (1) ---------- #
    U("johnston_organ_wind_unit", "约翰斯顿器风感单元", "wind_detect", "antennal_mechanosensory",
      "触角 JO 机械感受神经元（672 真实细胞 / 34 类）把气流感同时送进听觉中枢（48,207 突触）"
      "与下行神经元（46,595），并稀疏耦合到求偶 pIP（1,655）与巨纤维（709）——风向、风强与求偶声走同一输入。",
      [("jo", "johnston_organ_mechano", 0.35),
       ("ammc", "auditory_ammc", 0.25),
       ("pip", "courtship_pip", 0.15),
       ("dn", "descending_neuron", 0.15),
       ("gf", "escape_giant_fiber", 0.10)],
      [("jo", "ammc", "feedforward_excitatory", 1.0),
       ("jo", "dn", "feedforward_excitatory", 1.0),
       ("jo", "pip", "feedforward_excitatory", 0.5),
       ("jo", "gf", "feedforward_excitatory", 0.4)],
      [("wind", "sensory.mechanovibratory", True), ("song", "sensory.auditory", False)],
      [("wind_alarm", "motor.command", True)],
      (100, 500), ["wind_detect", "escape_trigger", "social_detect"],
      ["wind_detect", "social_detect"], "wind_detect",
      ["acetylcholine"], "Wilson & Dickinson 2010; Dorkenwald et al 2024",
      ["drosophila"], ("auditory_song_reception_unit",)),

    # ---------- OA VISUAL CENTRIFUGAL MODULATION (1) ---------- #
    U("oa_visual_modulation_unit", "八胺视觉离心调节单元", "visual_gain", "optic_lobe",
      "少量八胺离心神经元（16 真实细胞 / 5 类）容积式调制整个视叶：中神经 56,231、"
      "LC 8,729、T4/T5 6,600、LPLC 2,906 突触——觉醒状态把视觉增益一次性拉满。",
      [("oa", "oa_visual_centrifugal_pool", 0.20),
       ("med", "ol_medulla_intrinsic", 0.30),
       ("lc", "ol_visual_lc", 0.15),
       ("t45", "ol_motion_detector_t45", 0.20),
       ("lplc", "looming_lplc", 0.15)],
      [("oa", "med", "modulatory_diffuse", 1.0),
       ("oa", "lc", "modulatory_diffuse", 0.7),
       ("oa", "t45", "modulatory_diffuse", 0.8),
       ("oa", "lplc", "modulatory_diffuse", 0.6)],
      [("arousal", "modulatory.octopamine", True)],
      [("gain_set", "modulatory.octopamine", True)],
      (20, 100), ["visual_gain", "attention_visual", "arousal_link"],
      ["visual_gain", "arousal_link"], "visual_gain",
      ["octopamine"], "Pan & Clandinin 2007; Dorkenwald et al 2024",
      ["drosophila"], ("octopamine_arousal_unit",)),

    # ---------- CRUSTAL SENSORY-MOTOR CONVERGENCE (1) ---------- #
    U("cb_sensory_motor_unit", "脑-胸部感觉运动汇聚单元", "posture_set", "brain",
      "四类感觉（上升感觉 11,609、VNC 感觉 2,711、吻部机械 790、JO 机械 466 突触）"
      "在胸胸部运动核汇聚，是姿态设定的输入侧最完整的实测汇聚点。",
      [("asc", "sensory_ascending_pool", 0.25),
       ("vns", "vnc_sensory_pool", 0.25),
       ("prob", "proboscis_mechano_pool", 0.15),
       ("jo", "johnston_organ_mechano", 0.15),
       ("cbm", "cb_motor_pool", 0.20)],
      [("asc", "cbm", "feedforward_excitatory", 1.0),
       ("vns", "cbm", "feedforward_excitatory", 0.9),
       ("prob", "cbm", "feedforward_excitatory", 0.6),
       ("jo", "cbm", "feedforward_excitatory", 0.5)],
      [("touch", "sensory.somatosensory", True), ("wind", "sensory.mechanovibratory", False),
       ("feed", "sensory.gustatory", False)],
      [("posture_cmd", "motor.posture", True)],
      (50, 300), ["convergent_gather", "posture_set", "sensory_gather"],
      ["posture_set", "convergent_gather"], "posture_set",
      ["acetylcholine", "glutamate"], "Dorkenwald et al 2024; Gershow et al 2001",
      ["drosophila"], ("wing_flight_control_unit",)),

    # ---------- CRUSTAL ENDOCRINE POOL (1) ---------- #
    U("cb_endocrine_modulation_unit", "脑内分泌调节池单元", "peptide_release", "brain",
      "VNC 中间神经元与上升感觉池各自少量地驱动胸部内分泌池（65 真实细胞 / 10 类，"
      "实测 288 与 149 突触）——肽类容积传递的状态调制，非突触点对点。",
      [("vni", "vnc_interneuron_pool", 0.25),
       ("asc", "sensory_ascending_pool", 0.25),
       ("cbe", "cb_endocrine_pool", 0.50)],
      [("vni", "cbe", "modulatory_diffuse", 1.0),
       ("asc", "cbe", "modulatory_diffuse", 0.7)],
      [("state", "arousal.state", False)],
      [("peptide", "modulatory.endocrine", True)],
      (20, 100), ["endocrine_release", "state_modulate", "peptide_burst"],
      ["endocrine_release", "state_modulate"], "peptide_release",
       ["neuropeptide"], "Dorkenwald et al 2024; Bhatt et al 2005",
      ["drosophila"], ()),

    # ------------------------------------------------------------------ #
    # v2.1.0 -- the last five anchored populations that had no unit yet
    # (VNC/crustal endocrine, the two efferent "E" pools, the central
    # complex efferent cell, the TBC centrifugal projection). Same
    # fail-closed discipline as v1.8.0 / v2.0.0: every wiring edge below
    # was looked up in the measured profile x profile synapse matrix
    # BEFORE it was written. One planned edge measured zero and was
    # dropped, not forced: pharyngeal_gustatory -> efferent_descending_
    # pool = 0 synapses, so buccal_efferent_feedback_unit closes its
    # return loop through cb_motor_pool instead (both directions non-
    # zero: 11 out, 12 back).
    # ------------------------------------------------------------------ #

    # ---------- VNC ENDOCRINE POOL (1) ---------- #
    U("vnc_endocrine_modulation_unit", "腹神经索内分泌调节单元", "neurohormone_release",
      "ventral_nerve_cord",
      "VNC 内分泌池仅 22 真实细胞 / 4 类（LK、CAPA_a、CAPA_b、FMRFa_Tv），却是整条索体的"
      "神经激素发射口：VNC 中间神经元（12,967 细胞）实测 13,162 突触下行驱动它，下行神经元"
      "（1,306 细胞）再补 5,263；内分泌池经容积传递回返中间神经元 207、向腿运动池（403 细胞）"
      "外溢 54，腿运动池回测 35 突触闭环。突触量级极小，作用形式是肽类弥漫而非点对点。",
      [("endo", "vnc_endocrine_pool", 0.10),
       ("vni", "vnc_interneuron_pool", 0.50),
       ("dn", "descending_neuron", 0.25),
       ("leg", "vnc_leg_motor_pool", 0.15)],
      [("vni", "endo", "feedforward_excitatory", 1.0),
       ("dn", "endo", "feedforward_excitatory", 0.7),
       ("endo", "vni", "volume_transmission", 0.6),
       ("endo", "leg", "volume_transmission", 0.5),
       ("leg", "endo", "feedback_excitatory", 0.3)],
      [("touch", "sensory.somatosensory", True),
       ("proprio", "sensory.proprioceptive", False),
       ("state", "arousal.state", False)],
      [("peptide", "modulatory.endocrine", True),
       ("leg_mod", "motor.leg", False)],
      (100, 15000), ["peptide_release", "neurohormone_diffuse", "state_modulate",
                     "segmental_gate"],
      ["neurohormone_diffuse", "state_modulate"], "peptide_release",
      ["neuropeptide"], "Dorkenwald et al 2024; Bhatt et al 2005; Roder et al 2006",
      ["drosophila"],
      ("vnc_sensory_reflex_unit", "leg_motor_pool_unit",
       "cb_endocrine_modulation_unit")),

    # ---------- EFFERENT ASCENDING COMMAND BUS (1) ---------- #
    U("efferent_command_bus_unit", "外周上升指挥总线单元", "distributed_command",
      "brainstem",
      "EPP 上升外周池只有 8 真实细胞 / 5 类，却是脑到腹索的指挥总线：下行神经元（1,306 细胞）"
      "实测 4,724 突触注入它，它再扇出到 VNC 中间神经元（12,967 细胞）6,304、腿运动池 1,259、"
      "巨纤维前体 GFC（34 细胞）631；中间神经元回返 7,377、GFC 回返 126，构成一条"
      "「命令—确认」双向闭环，并把逃逸系统挂在同一条总线上。",
      [("bus", "efferent_ascending_pool", 0.08),
       ("dn", "descending_neuron", 0.30),
       ("vni", "vnc_interneuron_pool", 0.42),
       ("leg", "vnc_leg_motor_pool", 0.12),
       ("gfc", "escape_vnc_gfc", 0.08)],
      [("dn", "bus", "feedforward_excitatory", 1.0),
       ("bus", "vni", "feedforward_excitatory", 0.9),
       ("bus", "leg", "feedforward_excitatory", 0.7),
       ("bus", "gfc", "feedforward_excitatory", 0.6),
       ("vni", "bus", "feedback_excitatory", 0.8),
       ("gfc", "bus", "feedback_excitatory", 0.3)],
      [("cmd", "motor.command", True), ("escape", "motor.escape", False)],
      [("leg_cmd", "motor.leg", True),
       ("wing_cmd", "motor.wing", False),
       ("escape_cmd", "motor.escape", False)],
      (100, 15000), ["divergent_command", "command_reciprocal", "escape_coupling",
                     "bimanual_relay"],
      ["divergent_command", "escape_coupling"], "distributed_command",
      ["acetylcholine", "gaba"], "Dorkenwald et al 2024; Gershow et al 2001",
      ["drosophila"],
      ("giant_fiber_escape_unit", "leg_motor_pool_unit",
       "central_complex_steering_unit")),

    # ---------- CENTRAL COMPLEX EFFERENT (1) ---------- #
    U("cb_efferent_command_unit", "中央复合体外周下命令单元", "command_issue",
      "central_complex",
      "中央复合体外周池只有 4 真实细胞 / 1 类，是这块脑区唯一的下行出口：嗅觉投射 PN"
      "（583 细胞）实测 2 突触输入它，它输出到下行政令神经元 26 突触、被回接 73，"
      "并向 CB 内分泌池（65 细胞）溢出 7 突触给状态打标记。规模最小的一档，但处在路径最顶端。",
      [("ef", "cb_efferent_pool", 0.10),
       ("dn", "descending_neuron", 0.45),
       ("alp", "antennal_lobe_pn", 0.25),
       ("cbe", "cb_endocrine_pool", 0.20)],
      [("alp", "ef", "feedforward_excitatory", 0.4),
       ("ef", "dn", "feedforward_excitatory", 1.0),
       ("dn", "ef", "feedback_excitatory", 0.6),
       ("ef", "cbe", "modulatory_diffuse", 0.3)],
      [("odour", "olfactory.sparse_code", True),
       ("heading", "navigation.heading", False)],
      [("command", "motor.command", True),
       ("state_peptide", "modulatory.endocrine", False)],
      (20, 300), ["command_issue", "goal_bearing_transfer", "reciprocal_gate",
                  "state_tagging"],
      ["command_issue", "goal_bearing_transfer"], "command_issue",
      ["acetylcholine", "neuropeptide"], "Dorkenwald et al 2024; Tan et al 2015",
      ["drosophila", "locust"],
      ("central_complex_steering_unit", "lateral_horn_innate_odour_unit",
       "cb_sensory_motor_unit")),

    # ---------- CENTRIFUGAL VISUAL FEEDBACK (1) ---------- #
    U("centrifugal_visual_feedback_unit", "离心视觉反馈单元", "visual_gain_feedback",
      "optic_lobe",
      "TBC 离心池只有 2 真实细胞 / 2 类，却是整条视网膜增益调节的离心通路：它把中枢信号回灌到"
      "视叶内生神经元（37,146 细胞）实测 3,323 突触、LC（4,164 细胞）1,131、八胺离心池"
      "（16 细胞）30、T4/T5（13,580 细胞）9；内生回传 5,222、LC 回传 661、T4/T5 回传 532，"
      "双向边全部实测非零，是典型的双向增益环而非单向广播。",
      [("tbc", "visual_projection_tbc_pool", 0.02),
       ("med", "ol_medulla_intrinsic", 0.55),
       ("lc", "ol_visual_lc", 0.18),
       ("t45", "ol_motion_detector_t45", 0.22),
       ("oa", "oa_visual_centrifugal_pool", 0.03)],
      [("tbc", "med", "feedforward_excitatory", 0.8),
       ("tbc", "lc", "feedforward_excitatory", 0.6),
       ("tbc", "oa", "feedforward_excitatory", 0.3),
       ("med", "tbc", "feedback_excitatory", 1.0),
       ("lc", "tbc", "feedback_excitatory", 0.5),
       ("t45", "tbc", "feedforward_excitatory", 0.4),
       ("tbc", "t45", "feedback_excitatory", 0.2)],
      [("motion", "sensory.visual.motion", True),
       ("irradiance", "sensory.visual.irradiance", False)],
      [("gain", "modulatory.acetylcholine", True),
       ("t45_gain", "modulatory.acetylcholine", False)],
      (200, 40000), ["centrifugal_feedback", "gain_control", "bidirectional_loop",
                     "contrast_set"],
      ["centrifugal_feedback", "gain_control"], "visual_gain_feedback",
      ["acetylcholine", "gaba"], "Dorkenwald et al 2024; Watanabe & Singh 2003",
      ["drosophila"],
      ("oa_visual_modulation_unit", "elementary_motion_detection_unit",
       "looming_detection_unit")),

    # ---------- EFFERENT DESCENDING / BUCCAL (1) ---------- #
    U("buccal_efferent_feedback_unit", "咽下外周反哺单元", "ingestive_feedback",
      "subesophageal_zone",
      "EPP 下降外周池只有 4 真实细胞 / 1 类，是口腔—腹部行为之间的下行反馈枢纽：下行神经元"
      "注入 123 突触并被回接 62，CB 运动池（106 细胞）与它双向互馈 11 与 12，感觉下降池"
      "（12 细胞）再输入 16；输出侧驱动咽味觉神经元（48 细胞）3 突触、八胺 VUM（17 细胞）"
      "5 突触。每条边都在实测矩阵里，但量级都 <=123 突触，属精细调节而非驱动级。",
      [("ed", "efferent_descending_pool", 0.10),
       ("dn", "descending_neuron", 0.30),
       ("cbm", "cb_motor_pool", 0.15),
       ("sdesc", "sensory_descending_pool", 0.15),
       ("pg", "pharyngeal_gustatory", 0.20),
       ("oa", "octopamine_vum", 0.10)],
      [("dn", "ed", "feedforward_excitatory", 1.0),
       ("ed", "dn", "feedback_excitatory", 0.6),
       ("cbm", "ed", "feedback_excitatory", 0.5),
       ("ed", "cbm", "feedforward_excitatory", 0.5),
       ("sdesc", "ed", "feedforward_excitatory", 0.4),
       ("ed", "pg", "feedforward_excitatory", 0.4),
       ("ed", "oa", "modulatory_diffuse", 0.3)],
      [("taste", "sensory.gustatory", True),
       ("touch", "sensory.somatosensory", False),
       ("hunger", "gating.hunger", False)],
      [("feeding", "motor.feeding", True),
       ("octopamine", "modulatory.octopamine", False)],
      (20, 300), ["ingestive_feedback", "reciprocal_gate", "satiety_tag",
                  "diffuse_arousal"],
      ["ingestive_feedback", "satiety_tag"], "ingestive_feedback",
      ["acetylcholine", "octopamine"], "Dorkenwald et al 2024; Gershow et al 2001; "
      "Bhatt et al 2005",
      ["drosophila"],
      ("pharyngeal_gustatory_unit", "octopamine_arousal_unit",
       "cb_sensory_motor_unit")),

    # ---------- WING FLIGHT STEERING (1, v2.3.0) ---------- #
    U("wing_flight_steering_unit", "翅膀转向调节单元", "flight_steering",
      "ventral_nerve_cord",
      "飞行动作选择：下行神经元（1306 真实细胞 / 477 类）注入 VNC 中间池 1,673,751 突触，"
      "VNC 中间池同时驱动飞行功率池 144,642、腿运动池 1,205,967、VNC 外周 85,992；"
      "飞行功率池再输出到翅膀伸张（4 突触 / 2 类）与鼓翅肌（4 突触 / 4 类）——后者是"
      "果蝇飞行的定常振荡器，反馈到 VNC 中间池 162 突触构成闭合的定速回路；VNC 中间池"
      "与 VNC 外周之间的 85,992 突触是姿态反馈通路的实测承载。所有 7 条边在实测矩阵"
      "里都非零，量级从 1 到 1,673,751 跨越六个数量级：功率/腿是驱动级，翅膀伸张与"
      "鼓翅是微调级。",
      [("dn", "descending_neuron", 0.20),
       ("vn", "vnc_interneuron_pool", 0.35),
       ("fp", "vnc_flight_power_pool", 0.10),
       ("wm", "wing_depressor_pool", 0.05),
       ("hd", "haltere_muscle_pool", 0.05),
       ("lm", "vnc_leg_motor_pool", 0.15),
       ("ve", "vnc_efferent_pool", 0.10)],
      [("dn", "vn", "feedforward_excitatory", 1.0),
       ("vn", "fp", "feedforward_excitatory", 1.0),
       ("fp", "wm", "feedforward_excitatory", 0.4),
       ("fp", "hd", "feedforward_excitatory", 0.6),
       ("vn", "lm", "feedforward_excitatory", 0.8),
       ("vn", "ve", "feedback_excitatory", 0.5),
       ("wm", "vn", "feedback_excitatory", 0.3)],
      [("command", "motor.command", True),
       ("proprioception", "sensory.proprioceptive", True)],
      [("wing", "motor.wing", True),
       ("leg", "motor.leg", False),
       ("posture", "motor.posture", False)],
      (40, 400), ["flight_steering", "haltere_tuned", "wing_control",
                  "leg_coordination"],
      ["flight_steering", "haltere_tuned"], "flight_steering",
      ["acetylcholine", "GABA"], "Niven et al 2013; Maimon et al 2005; "
      "Straube et al 2007",
      ["drosophila"],
      ("wing_flight_control_unit", "giant_fiber_escape_unit",
       "vnc_sensory_reflex_unit")),

    # ---------- GUSTATORY CENTRIFUGAL FEEDBACK (1, v2.3.0) ---------- #
    U("gustatory_centrifugal_unit", "味觉离心反馈单元", "centrifugal_feedback",
      "subesophageal_zone",
      "味觉信号的离心放大回路：咽味觉神经元（48 细胞 / 18 类）注入感觉上升池 68 突触，"
      "上升池同时注入 CB 内分泌池 149、CB 运动池 11,609、VNC 中间池 154,541、"
      "EPP 上升池 256；EPP 上升池再向 VNC 中间池注入 6,304 突触形成闭环。这条回路"
      "把咽部味觉输入放大成跨越脑干与 VNC 的全脑反馈——MaleCNS 实测显示上升池到"
      "VNC 的 154,541 突触比到 CB 内分泌的 149 高三个数量级，暗示味觉反馈主要走"
      "运动通路而非内分通路。",
      [("pg", "pharyngeal_gustatory", 0.15),
       ("sa", "sensory_ascending_pool", 0.25),
       ("ce", "cb_endocrine_pool", 0.10),
       ("cbm", "cb_motor_pool", 0.15),
       ("ea", "efferent_ascending_pool", 0.10),
       ("vn", "vnc_interneuron_pool", 0.25)],
      [("pg", "sa", "feedforward_excitatory", 0.6),
       ("sa", "ce", "feedforward_excitatory", 0.3),
       ("sa", "cbm", "feedforward_excitatory", 1.0),
       ("sa", "ea", "feedforward_excitatory", 0.5),
       ("ea", "vn", "feedforward_excitatory", 0.7),
       ("sa", "vn", "feedforward_excitatory", 0.9)],
      [("taste", "sensory.gustatory", True),
       ("attention", "gating.attention", False)],
      [("centrifugal", "modulatory.endocrine", True),
       ("motor_drive", "motor.command", False)],
      (30, 200), ["centrifugal_feedback", "taste_driven", "arousal_broadcast"],
      ["centrifugal_feedback", "arousal_broadcast"], "centrifugal_feedback",
      ["acetylcholine", "neuropeptide"], "Marella et al 2006; Mann et al 2013; "
      "Bhatt et al 2005",
      ["drosophila"],
      ("pharyngeal_gustatory_unit", "vnc_sensory_reflex_unit",
       "cb_sensory_motor_unit")),

    # ==================================================================== #
    # v2.4.0 CROSS-MODAL DROSOPHILA UNITS (2)
    # -------------------------------------------------------------------- #
    # Both units are seeded from unused strong profile-pairs in the
    # measured profile x profile matrix (synapses > 9,000, all SUPPORTED
    # at type-pair resolution, no CONTRADICTED and no FRAGILE). Neither
    # overlaps an existing unit's member set in a way that would make the
    # new wiring redundant.
    # ==================================================================== #

    # ---------- MUSHROOM BODY / LATERAL HORN RECIPROCAL (1, v2.4.0) ---------- #
    U("mushroom_body_lateral_horn_reciprocal_unit", "蘑菇体-侧角往返单元", "cross_modal_integrate",
      "mushroom_body",
      "学得的蘑菇体与先天的侧角之间存在双向投影——MaleCNS 实测 mushroom_body_output→lateral_horn_ln 36,712 突触、"
      "lateral_horn_ln→mushroom_body_output 21,199、mushroom_body_dan→lateral_horn_ln 11,517、"
      "lateral_horn_ln→mushroom_body_dan 19,655、kenyon_cell→lateral_horn_ln 11,265；再叠上加味通路"
      "mushroom_body_dan→mushroom_body_output 39,960。六条边全部在类型对层面 SUPPORTED（最少 270/6330 对、"
      "最多 1555/13504 对）。这个单元填补了此前只有单向 mushroom_body_associative_memory_unit 与"
      "lateral_horn_innate_odour_unit、没有跨模态整合的缺口：气味在蘑菇体被赋效价之后回写到侧角的先天通道，"
      "侧角再把信息素类别信号反哺给多巴胺神经元。",
      [("kc", "kenyon_cell", 0.25),
       ("lh", "lateral_horn_ln", 0.30),
       ("mbon", "mushroom_body_output", 0.20),
       ("dan", "mushroom_body_dan", 0.25)],
      [("dan", "mbon", "feedforward_excitatory", 0.9),
       ("mbon", "lh", "feedforward_excitatory", 1.0),
       ("lh", "mbon", "feedback_excitatory", 0.7),
       ("dan", "lh", "feedforward_excitatory", 0.8),
       ("lh", "dan", "feedback_excitatory", 0.5),
       ("kc", "lh", "feedforward_excitatory", 0.6)],
      [("sparse_code", "olfactory.sparse_code", True),
       ("value_in", "modulatory.dopamine", False)],
      [("learned_valence", "olfactory.learned_valence", True),
       ("innate_valence", "olfactory.learned_valence", False)],
      (1000, 2000), ["cross_modal_integrate", "learned_innate_mix", "valence_transfer"],
      ["cross_modal_integrate", "learned_innate_mix", "valence_transfer",
       "mb_lh_reciprocal"], "cross_modal_integrate",
      ["acetylcholine", "dopamine", "gaba"],
      "Aso et al 2014; Dolan et al 2019; Kaur et al 2021",
      ["drosophila"],
      ("mushroom_body_associative_memory_unit", "lateral_horn_innate_odour_unit")),

    # ---------- ANTENNAL LOBE / CENTRAL COMPLEX FEEDBACK (1, v2.4.0) ---------- #
    U("antennal_lobe_central_complex_feedback_unit", "触角叶-中央复合体反馈单元",
      "aal_cc_projection", "central_complex",
      "触角叶的局部神经元（GLNO/LNO 类，16 个真实细胞 / 5 类）直接向中央复合体脑桥与蘑菇体样脑桥发出双向投影——"
      "MaleCNS 实测 antennal_lobe_ln→central_complex_pb 16,379 突触（GLNO→PEN_a 单类型对 9,806 突触，"
      "占 60%）、antennal_lobe_ln→central_complex_fb 25,402（LNO2→PFNd 单类型对 9,610）、"
      "central_complex_fb→antennal_lobe_ln 9,473（PFNd→LNO2 反行 3,542）——三条边在类型对层面全部 SUPPORTED"
      "（6/355、13/185、11/185），零 FRAGILE、零 CONTRADICTED。这条通路把气味身份写进"
      "中央复合体的头向参考系，同时让中央复合体把当前航向反哺回触角叶的局部环路，是嗅觉驱动导航的"
      "解剖学证据；此前 antennal_lobe_glomerular_unit 与 central_complex_heading_unit 各管一段，"
      "没有单元把两者连起来。",
      [("ln", "antennal_lobe_ln", 0.25),
       ("pb", "central_complex_pb", 0.40),
       ("fb", "central_complex_fb", 0.35)],
      [("ln", "pb", "feedforward_excitatory", 1.0),
       ("ln", "fb", "feedforward_excitatory", 0.9),
       ("fb", "ln", "feedback_excitatory", 0.7)],
      [("odour_in", "sensory.olfactory", True),
       ("heading_in", "navigation.heading", False)],
      [("heading_set", "navigation.heading", True),
       ("steering_out", "navigation.steering", True)],
      (20, 300), ["olfactory_to_navigation", "centrifugal_feedback", "heading_set"],
      ["olfactory_to_navigation", "heading_set", "centrifugal_feedback",
       "aal_cc_projection"], "olfactory_to_navigation",
      ["acetylcholine", "gaba", "glutamate"],
      "Tse et al 2022; Pohl et al 2015; Dorkenwald et al 2022",
      ["drosophila"],
      ("antennal_lobe_glomerular_unit", "central_complex_heading_unit",
       "central_complex_steering_unit")),

    # ==================================================================== #
    # v2.8.0 DROSOPHILA UNITS — MOTION FEEDBACK + DOPAMINE AROUSAL (2)
    # -------------------------------------------------------------------- #
    # Both units are seeded from SUPPORTED profile-pairs in the unused-edge
    # list from tmp/probe_v270_candidates.py. Every internal edge is
    # SUPPORTED at type-pair resolution (0 FRAGILE, 0 CONTRADICTED).
    # ==================================================================== #

    # ---------- MEDULLA CENTRIPETAL GAIN (1, v2.8.0) ---------- #
    U("medulla_centripetal_gain_unit", "髓质离心增益单元", "visual_gain_control",
      "optic_lobe",
      "T4/T5 方向选择性细胞向 Tm 家族与 LPi 抑制柱发出离心反馈，与 Tm→T4/T5 的顺向驱动形成完整的离心回路；"
      "整个回路再汇聚到 LPLC 大场单元做趋近检测——MaleCNS 实测 lamina→medulla 1,883,036 突触（L2→Tm2 单类型对 "
      "221,186）、t45→medulla 480,306（T5a→TmY20 46,394）、t45→lpi 953,115（T5c→LPi34 92,944）、"
      "medulla→looming 324,426（Tm5Y→LPLC2 27,058）、t45→looming 68,768、lpi→looming 37,769，"
      "六条主边在类型对层面全部 SUPPORTED（最少 31/32 对、最多 303/855 对），另加 Tm→T4/T5、Tm→LPi、LPi→Tm "
      "三条已存在于 elementary_motion_detection_unit 的边作为完整回路的支撑。九条边合计 ~4.7M 突触、"
      "零 FRAGILE、零 CONTRADICTED。这个单元填补了 visual 通路的一个结构缺口：compound_lamina_relay_unit 到 "
      "elementary_motion_detection_unit 之间没有 lam→medulla 的直连，"
      "elementary_motion_detection_unit 与 looming_detection_unit 之间也没有 lpi→looming 的直连——"
      "现在把这两段缝起来，且把 T4/T5→Tm 的离心反馈作为独立结构记录下来（此前只在 literature 里，"
      "没有单元把它作为 wiring 建模）。",
      [("lamina", "ol_lamina_monopolar", 0.20),
       ("medulla", "ol_medulla_intrinsic", 0.30),
       ("t45", "ol_motion_detector_t45", 0.25),
       ("lpi", "ol_lpi", 0.15),
       ("looming", "looming_lplc", 0.10)],
      [("lamina", "medulla", "feedforward_excitatory", 1.0),
       ("medulla", "t45", "feedforward_excitatory", 0.9),
       ("t45", "medulla", "feedback_excitatory", 0.7),
       ("t45", "lpi", "feedforward_excitatory", 0.8),
       ("medulla", "lpi", "feedforward_excitatory", 0.6),
       ("lpi", "medulla", "lateral_inhibitory", 0.5),
       ("t45", "looming", "feedforward_excitatory", 0.9),
       ("medulla", "looming", "feedforward_excitatory", 0.7),
       ("lpi", "looming", "feedforward_excitatory", 0.6)],
      [("lamina_in", "sensory.visual", True),
       ("gain_modulation", "modulatory.endocrine", False)],
      [("motion_out", "sensory.visual.motion", True),
       ("looming_cmd", "sensory.visual", True)],
      (200, 5000), ["visual_gain_control", "centrifugal_feedback", "loom_integrate"],
      ["visual_gain_control", "looming_detect", "centrifugal_feedback",
       "medulla_centripetal_gain"], "visual_gain_control",
      ["acetylcholine", "gaba", "glutamate"],
      "Maisak et al 2013; Mauss et al 2015; Borst & Heisenberg 2012; "
      "Pfeiffer et al 2020",
      ["drosophila"],
      ("compound_lamina_relay_unit", "elementary_motion_detection_unit",
       "lobula_plate_optic_flow_unit", "looming_detection_unit")),

    # ---------- MUSHROOM BODY DOPAMINE AROUSAL (1, v2.8.0) ---------- #
    U("mushroom_body_dopamine_arousal_unit", "蘑菇体多巴胺觉醒单元",
      "neuromodulatory_hub", "mushroom_body",
      "多巴胺能觉醒中枢：Kenyon 细胞、DAN 多巴胺能神经元、MBON 输出、APL 多巴胺调控与 OA-VUM 章鱼胺"
      "调节器构成一张全向互馈的觉醒调制网——MaleCNS 实测 kc→dan 281,864 突触（KCg-m→PAM08 单类型对 "
      "29,697）、dan→kc 213 对 216k、kc→mbon 302,591、mbon→dan 637k、apl→dan 567、apl→kc 204,202、"
      "dan→mbon 212k、dan→oa_vum 5,431、oa_vum→mbon 70,538、oa_vum→kc 39,112，十条边在类型对层面"
      "全部 SUPPORTED（最少 15/15 对、最多 443/1184 对），零 FRAGILE、零 CONTRADICTED。这个单元把"
      "mushroom_body_associative_memory_unit（学习）与 octopamine_arousal_broadcast 概念之间"
      "没有连接的那层调制器补齐：DAN 既是记忆的调制器，也是 KC↔MBON 的时钟；APL 是 KC 的强多巴胺"
      "调节器，OA-VUM 再把觉醒信号广播到 MBON 与触角叶 PN 通路。",
      [("kc", "kenyon_cell", 0.30),
       ("dan", "mushroom_body_dan", 0.30),
       ("mbon", "mushroom_body_output", 0.20),
       ("apl", "mushroom_body_apl", 0.10),
       ("oa", "octopamine_vum", 0.10)],
      [("kc", "dan", "feedforward_excitatory", 0.9),
       ("dan", "kc", "feedback_excitatory", 0.7),
       ("kc", "mbon", "feedforward_excitatory", 1.0),
       ("mbon", "dan", "feedback_excitatory", 0.5),
       ("apl", "dan", "modulatory_gated_plasticity", 0.8),
       ("apl", "kc", "modulatory_gated_plasticity", 1.0),
       ("dan", "mbon", "feedforward_excitatory", 0.7),
       ("dan", "oa", "feedforward_excitatory", 0.6),
       ("oa", "mbon", "modulatory_gated_plasticity", 0.8),
       ("oa", "kc", "modulatory_gated_plasticity", 0.6)],
      [("sparse_code", "olfactory.sparse_code", True),
       ("arousal", "modulatory.endocrine", False)],
      [("learned_valence", "olfactory.learned_valence", True),
       ("arousal_state", "modulatory.dopamine", True)],
      (1000, 2000), ["neuromodulatory_hub", "dopamine_modulation", "arousal_state"],
      ["neuromodulatory_hub", "dopamine_modulation", "arousal_state",
       "mb_dopamine_arousal"], "neuromodulatory_hub",
      ["dopamine", "octopamine", "acetylcholine", "gaba"],
      "Aso et al 2014; Tanaka et al 2008; Schulze et al 2018; "
      "Cazalet & Wang 2020",
      ["drosophila"],
      ("mushroom_body_associative_memory_unit", "mushroom_body_lateral_horn_reciprocal_unit",
       "lateral_horn_innate_odour_unit")),
]

# ---------------------------------------------------------------------------
# v2.24.0 — JEV-powered validation of all 103 functional units.
# Each unit is assessed on three dimensions:
#   literature_p:  (noul) P(documented in >=2 peer-reviewed papers)
#   model_p:       (noul) P(published computational model exists)
#   evidence_score:(0-10 rubric of published evidence strength)
#   verdict:       SUPPORTED | PARTIAL | WEAK
# Cost: 103 calls × 3 questions ≈ $0.0075. Full JSON: jev_results/.
# ---------------------------------------------------------------------------
_JEV_UNIT_VALIDATION = {
    "amygdala_fear_unit":                              {"verdict": "PARTIAL", "literature_p": 0.93, "model_p": 0.86, "evidence_score": 5, "evidence_label": "preliminary"},
    "antennal_lobe_central_complex_feedback_unit":     {"verdict": "PARTIAL", "literature_p": 0.59, "model_p": 0.33, "evidence_score": 3, "evidence_label": "speculative"},
    "antennal_lobe_glomerular_unit":                   {"verdict": "PARTIAL", "literature_p": 0.93, "model_p": 0.89, "evidence_score": 5, "evidence_label": "preliminary"},
    "aplysia_gill_withdrawal_unit":                    {"verdict": "PARTIAL", "literature_p": 0.94, "model_p": 0.88, "evidence_score": 5, "evidence_label": "preliminary"},
    "ascidian_larval_escape_swim_unit":                {"verdict": "PARTIAL", "literature_p": 0.84, "model_p": 0.59, "evidence_score": 3, "evidence_label": "speculative"},
    "astrocyte_tripartite_unit":                       {"verdict": "PARTIAL", "literature_p": 0.92, "model_p": 0.78, "evidence_score": 5, "evidence_label": "preliminary"},
    "auditory_song_reception_unit":                    {"verdict": "PARTIAL", "literature_p": 0.62, "model_p": 0.26, "evidence_score": 3, "evidence_label": "speculative"},
    "auditory_thalamic_relay_unit":                    {"verdict": "PARTIAL", "literature_p": 0.89, "model_p": 0.68, "evidence_score": 5, "evidence_label": "preliminary"},
    "barrel_cortex_whisking_unit":                     {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.71, "evidence_score": 5, "evidence_label": "preliminary"},
    "basal_ganglia_selection_unit":                    {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.93, "evidence_score": 5, "evidence_label": "preliminary"},
    "birdsong_basal_ganglia_learning_unit":            {"verdict": "PARTIAL", "literature_p": 0.94, "model_p": 0.81, "evidence_score": 5, "evidence_label": "preliminary"},
    "birdsong_hvc_timing_unit":                        {"verdict": "PARTIAL", "literature_p": 0.85, "model_p": 0.79, "evidence_score": 4, "evidence_label": "preliminary"},
    "birdsong_ra_motor_unit":                          {"verdict": "PARTIAL", "literature_p": 0.84, "model_p": 0.79, "evidence_score": 4, "evidence_label": "preliminary"},
    "buccal_efferent_feedback_unit":                   {"verdict": "WEAK",    "literature_p": 0.28, "model_p": 0.24, "evidence_score": 2, "evidence_label": "speculative"},
    "buccal_feeding_cpg_unit":                         {"verdict": "PARTIAL", "literature_p": 0.75, "model_p": 0.71, "evidence_score": 3, "evidence_label": "speculative"},
    "cb_efferent_command_unit":                        {"verdict": "WEAK",    "literature_p": 0.30, "model_p": 0.31, "evidence_score": 2, "evidence_label": "speculative"},
    "cb_endocrine_modulation_unit":                    {"verdict": "WEAK",    "literature_p": 0.29, "model_p": 0.16, "evidence_score": 2, "evidence_label": "speculative"},
    "cb_sensory_motor_unit":                           {"verdict": "WEAK",    "literature_p": 0.39, "model_p": 0.26, "evidence_score": 2, "evidence_label": "speculative"},
    "central_complex_heading_unit":                    {"verdict": "PARTIAL", "literature_p": 0.93, "model_p": 0.90, "evidence_score": 4, "evidence_label": "preliminary"},
    "central_complex_steering_unit":                   {"verdict": "PARTIAL", "literature_p": 0.71, "model_p": 0.67, "evidence_score": 3, "evidence_label": "speculative"},
    "centrifugal_visual_feedback_unit":                {"verdict": "WEAK",    "literature_p": 0.29, "model_p": 0.19, "evidence_score": 2, "evidence_label": "speculative"},
    "cephalopod_arm_motor_unit":                       {"verdict": "PARTIAL", "literature_p": 0.75, "model_p": 0.65, "evidence_score": 4, "evidence_label": "preliminary"},
    "cephalopod_chromatophore_control_unit":           {"verdict": "PARTIAL", "literature_p": 0.69, "model_p": 0.41, "evidence_score": 4, "evidence_label": "preliminary"},
    "cephalopod_vertical_lobe_learning_unit":          {"verdict": "PARTIAL", "literature_p": 0.67, "model_p": 0.48, "evidence_score": 3, "evidence_label": "speculative"},
    "cerebellar_climbing_fibre_teaching_unit":         {"verdict": "PARTIAL", "literature_p": 0.95, "model_p": 0.92, "evidence_score": 5, "evidence_label": "preliminary"},
    "cerebellar_cortical_unit":                        {"verdict": "PARTIAL", "literature_p": 0.95, "model_p": 0.94, "evidence_score": 5, "evidence_label": "preliminary"},
    "cerebellar_error_teaching_unit":                  {"verdict": "PARTIAL", "literature_p": 0.94, "model_p": 0.93, "evidence_score": 5, "evidence_label": "preliminary"},
    "cerebellar_purkinje_ltd_unit":                    {"verdict": "PARTIAL", "literature_p": 0.91, "model_p": 0.90, "evidence_score": 5, "evidence_label": "preliminary"},
    "cholinergic_arousal_unit":                        {"verdict": "PARTIAL", "literature_p": 0.90, "model_p": 0.70, "evidence_score": 5, "evidence_label": "preliminary"},
    "circadian_clock_unit":                            {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.71, "evidence_score": 5, "evidence_label": "preliminary"},
    "cochlear_amplification_unit":                     {"verdict": "PARTIAL", "literature_p": 0.66, "model_p": 0.58, "evidence_score": 4, "evidence_label": "preliminary"},
    "compound_lamina_relay_unit":                      {"verdict": "PARTIAL", "literature_p": 0.87, "model_p": 0.66, "evidence_score": 5, "evidence_label": "preliminary"},
    "cortical_highorder_integration_unit":             {"verdict": "WEAK",    "literature_p": 0.18, "model_p": 0.23, "evidence_score": 1, "evidence_label": "speculative"},
    "cortical_inhibitory_gain_unit":                   {"verdict": "WEAK",    "literature_p": 0.39, "model_p": 0.63, "evidence_score": 2, "evidence_label": "speculative"},
    "cortical_l23_association_unit":                   {"verdict": "PARTIAL", "literature_p": 0.72, "model_p": 0.61, "evidence_score": 3, "evidence_label": "speculative"},
    "cortical_l4_input_unit":                          {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.81, "evidence_score": 5, "evidence_label": "preliminary"},
    "cortical_l5_output_unit":                         {"verdict": "PARTIAL", "literature_p": 0.59, "model_p": 0.72, "evidence_score": 3, "evidence_label": "speculative"},
    "cortical_l6_feedback_unit":                       {"verdict": "PARTIAL", "literature_p": 0.72, "model_p": 0.66, "evidence_score": 4, "evidence_label": "preliminary"},
    "courtship_decision_unit":                         {"verdict": "PARTIAL", "literature_p": 0.77, "model_p": 0.40, "evidence_score": 3, "evidence_label": "speculative"},
    "courtship_song_pattern_unit":                     {"verdict": "PARTIAL", "literature_p": 0.59, "model_p": 0.43, "evidence_score": 3, "evidence_label": "speculative"},
    "dopaminergic_value_unit":                         {"verdict": "PARTIAL", "literature_p": 0.81, "model_p": 0.82, "evidence_score": 4, "evidence_label": "preliminary"},
    "efferent_command_bus_unit":                       {"verdict": "WEAK",    "literature_p": 0.34, "model_p": 0.21, "evidence_score": 2, "evidence_label": "speculative"},
    "electric_organ_discharge_unit":                   {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.79, "evidence_score": 5, "evidence_label": "preliminary"},
    "electrosensory_electrolocation_unit":             {"verdict": "PARTIAL", "literature_p": 0.79, "model_p": 0.77, "evidence_score": 4, "evidence_label": "preliminary"},
    "elementary_motion_detection_unit":                {"verdict": "PARTIAL", "literature_p": 0.89, "model_p": 0.75, "evidence_score": 4, "evidence_label": "preliminary"},
    "entorhinal_spatial_map_unit":                     {"verdict": "PARTIAL", "literature_p": 0.70, "model_p": 0.87, "evidence_score": 4, "evidence_label": "preliminary"},
    "frog_escape_swim_unit":                           {"verdict": "PARTIAL", "literature_p": 0.82, "model_p": 0.74, "evidence_score": 4, "evidence_label": "preliminary"},
    "frog_tectal_prey_capture_unit":                   {"verdict": "PARTIAL", "literature_p": 0.80, "model_p": 0.68, "evidence_score": 4, "evidence_label": "preliminary"},
    "gamma_spindle_loop_unit":                         {"verdict": "PARTIAL", "literature_p": 0.90, "model_p": 0.88, "evidence_score": 5, "evidence_label": "preliminary"},
    "giant_fiber_escape_unit":                         {"verdict": "PARTIAL", "literature_p": 0.86, "model_p": 0.69, "evidence_score": 4, "evidence_label": "preliminary"},
    "gustatory_centrifugal_unit":                      {"verdict": "WEAK",    "literature_p": 0.20, "model_p": 0.12, "evidence_score": 1, "evidence_label": "speculative"},
    "hippocampal_ca2_autoassoc_unit":                  {"verdict": "PARTIAL", "literature_p": 0.67, "model_p": 0.48, "evidence_score": 4, "evidence_label": "preliminary"},
    "hippocampal_output_unit":                         {"verdict": "PARTIAL", "literature_p": 0.67, "model_p": 0.56, "evidence_score": 4, "evidence_label": "preliminary"},
    "hippocampal_spatial_map_unit":                    {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.94, "evidence_score": 5, "evidence_label": "preliminary"},
    "hippocampal_trisynaptic_unit":                    {"verdict": "PARTIAL", "literature_p": 0.97, "model_p": 0.95, "evidence_score": 5, "evidence_label": "preliminary"},
    "hypothalamic_arousal_unit":                       {"verdict": "PARTIAL", "literature_p": 0.87, "model_p": 0.78, "evidence_score": 5, "evidence_label": "preliminary"},
    "insect_clock_pacemaker_unit":                     {"verdict": "PARTIAL", "literature_p": 0.55, "model_p": 0.67, "evidence_score": 3, "evidence_label": "speculative"},
    "johnston_organ_wind_unit":                        {"verdict": "PARTIAL", "literature_p": 0.44, "model_p": 0.30, "evidence_score": 2, "evidence_label": "speculative"},
    "lateral_horn_innate_odour_unit":                  {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.50, "evidence_score": 4, "evidence_label": "preliminary"},
    "leech_swim_cpg_unit":                             {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.89, "evidence_score": 4, "evidence_label": "preliminary"},
    "leg_motor_pool_unit":                             {"verdict": "WEAK",    "literature_p": 0.34, "model_p": 0.31, "evidence_score": 2, "evidence_label": "speculative"},
    "lobula_plate_optic_flow_unit":                    {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.87, "evidence_score": 5, "evidence_label": "preliminary"},
    "locus_coeruleus_arousal_unit":                    {"verdict": "PARTIAL", "literature_p": 0.60, "model_p": 0.65, "evidence_score": 4, "evidence_label": "preliminary"},
    "looming_detection_unit":                          {"verdict": "PARTIAL", "literature_p": 0.68, "model_p": 0.51, "evidence_score": 3, "evidence_label": "speculative"},
    "medulla_centripetal_gain_unit":                   {"verdict": "PARTIAL", "literature_p": 0.65, "model_p": 0.54, "evidence_score": 3, "evidence_label": "speculative"},
    "medulla_colour_pathway_unit":                     {"verdict": "PARTIAL", "literature_p": 0.56, "model_p": 0.38, "evidence_score": 3, "evidence_label": "speculative"},
    "motor_thalamic_relay_unit":                       {"verdict": "PARTIAL", "literature_p": 0.85, "model_p": 0.59, "evidence_score": 5, "evidence_label": "preliminary"},
    "mushroom_body_associative_memory_unit":           {"verdict": "PARTIAL", "literature_p": 0.92, "model_p": 0.81, "evidence_score": 5, "evidence_label": "preliminary"},
    "mushroom_body_dopamine_arousal_unit":             {"verdict": "PARTIAL", "literature_p": 0.65, "model_p": 0.54, "evidence_score": 3, "evidence_label": "speculative"},
    "mushroom_body_lateral_horn_reciprocal_unit":      {"verdict": "PARTIAL", "literature_p": 0.76, "model_p": 0.41, "evidence_score": 3, "evidence_label": "speculative"},
    "mushroom_body_sparse_code_unit":                  {"verdict": "PARTIAL", "literature_p": 0.91, "model_p": 0.90, "evidence_score": 5, "evidence_label": "preliminary"},
    "oa_visual_modulation_unit":                       {"verdict": "WEAK",    "literature_p": 0.32, "model_p": 0.26, "evidence_score": 2, "evidence_label": "speculative"},
    "octopamine_arousal_unit":                         {"verdict": "PARTIAL", "literature_p": 0.54, "model_p": 0.29, "evidence_score": 3, "evidence_label": "speculative"},
    "olfactory_transduction_unit":                     {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.87, "evidence_score": 5, "evidence_label": "preliminary"},
    "passive_electroreception_unit":                   {"verdict": "PARTIAL", "literature_p": 0.61, "model_p": 0.66, "evidence_score": 4, "evidence_label": "preliminary"},
    "pharyngeal_gustatory_unit":                       {"verdict": "PARTIAL", "literature_p": 0.47, "model_p": 0.18, "evidence_score": 2, "evidence_label": "speculative"},
    "pit_viper_strike_unit":                           {"verdict": "WEAK",    "literature_p": 0.32, "model_p": 0.27, "evidence_score": 2, "evidence_label": "speculative"},
    "red_nucleus_coordination_unit":                   {"verdict": "PARTIAL", "literature_p": 0.68, "model_p": 0.56, "evidence_score": 4, "evidence_label": "preliminary"},
    "respiratory_rhythm_cpg_unit":                     {"verdict": "PARTIAL", "literature_p": 0.88, "model_p": 0.88, "evidence_score": 4, "evidence_label": "preliminary"},
    "retinal_direction_selective_unit":                {"verdict": "PARTIAL", "literature_p": 0.90, "model_p": 0.86, "evidence_score": 5, "evidence_label": "preliminary"},
    "retinal_irradiance_unit":                         {"verdict": "PARTIAL", "literature_p": 0.80, "model_p": 0.56, "evidence_score": 4, "evidence_label": "preliminary"},
    "retinal_motion_onset_unit":                       {"verdict": "PARTIAL", "literature_p": 0.46, "model_p": 0.38, "evidence_score": 2, "evidence_label": "speculative"},
    "retinal_phototransduction_unit":                  {"verdict": "PARTIAL", "literature_p": 0.85, "model_p": 0.80, "evidence_score": 5, "evidence_label": "preliminary"},
    "septo_hippocampal_theta_unit":                    {"verdict": "PARTIAL", "literature_p": 0.92, "model_p": 0.88, "evidence_score": 5, "evidence_label": "preliminary"},
    "serotonergic_mood_unit":                          {"verdict": "PARTIAL", "literature_p": 0.57, "model_p": 0.57, "evidence_score": 4, "evidence_label": "preliminary"},
    "sleep_wake_flipflop_unit":                        {"verdict": "PARTIAL", "literature_p": 0.91, "model_p": 0.89, "evidence_score": 5, "evidence_label": "preliminary"},
    "somatosensory_dorsalhorn_unit":                   {"verdict": "PARTIAL", "literature_p": 0.79, "model_p": 0.80, "evidence_score": 5, "evidence_label": "preliminary"},
    "somatosensory_thalamic_relay_unit":               {"verdict": "PARTIAL", "literature_p": 0.86, "model_p": 0.58, "evidence_score": 5, "evidence_label": "preliminary"},
    "spinal_cpg_unit":                                 {"verdict": "PARTIAL", "literature_p": 0.94, "model_p": 0.94, "evidence_score": 5, "evidence_label": "preliminary"},
    "spinal_reflex_arc_unit":                          {"verdict": "PARTIAL", "literature_p": 0.96, "model_p": 0.91, "evidence_score": 5, "evidence_label": "preliminary"},
    "startle_escape_command_unit":                     {"verdict": "PARTIAL", "literature_p": 0.92, "model_p": 0.84, "evidence_score": 5, "evidence_label": "preliminary"},
    "striatal_direct_pathway_unit":                    {"verdict": "PARTIAL", "literature_p": 0.95, "model_p": 0.89, "evidence_score": 5, "evidence_label": "preliminary"},
    "striatal_indirect_pathway_unit":                  {"verdict": "PARTIAL", "literature_p": 0.92, "model_p": 0.92, "evidence_score": 5, "evidence_label": "preliminary"},
    "thalamocortical_relay_unit":                      {"verdict": "PARTIAL", "literature_p": 0.95, "model_p": 0.87, "evidence_score": 5, "evidence_label": "preliminary"},
    "trigeminal_infrared_map_unit":                    {"verdict": "PARTIAL", "literature_p": 0.80, "model_p": 0.47, "evidence_score": 4, "evidence_label": "preliminary"},
    "vestibular_transduction_unit":                    {"verdict": "PARTIAL", "literature_p": 0.59, "model_p": 0.61, "evidence_score": 4, "evidence_label": "preliminary"},
    "vestibulo_ocular_reflex_unit":                    {"verdict": "PARTIAL", "literature_p": 0.91, "model_p": 0.83, "evidence_score": 5, "evidence_label": "preliminary"},
    "visual_target_detection_unit":                    {"verdict": "PARTIAL", "literature_p": 0.72, "model_p": 0.48, "evidence_score": 3, "evidence_label": "speculative"},
    "visual_thalamic_relay_unit":                      {"verdict": "PARTIAL", "literature_p": 0.91, "model_p": 0.74, "evidence_score": 5, "evidence_label": "preliminary"},
    "vnc_endocrine_modulation_unit":                   {"verdict": "WEAK",    "literature_p": 0.28, "model_p": 0.15, "evidence_score": 2, "evidence_label": "speculative"},
    "vnc_sensory_reflex_unit":                         {"verdict": "WEAK",    "literature_p": 0.21, "model_p": 0.27, "evidence_score": 2, "evidence_label": "speculative"},
    "wing_flight_control_unit":                        {"verdict": "WEAK",    "literature_p": 0.25, "model_p": 0.38, "evidence_score": 2, "evidence_label": "speculative"},
    "wing_flight_steering_unit":                       {"verdict": "PARTIAL", "literature_p": 0.43, "model_p": 0.44, "evidence_score": 2, "evidence_label": "speculative"},
}

def _load_unit_jev():
    """Resolve per-unit JEV verdicts.

    v2.24 shipped these values as a hand-copied literal, and the JEV script's
    own output (scripts/jev_results/unit_validation.json) was never read back
    by anything — so re-running the validation produced no artifact change
    unless someone manually pasted 103 lines into this file.

    From v2.26.0 the JEV result file is the primary source, keyed by unit
    name, and the literal above is kept only as a fallback for units the JEV
    run did not cover. Coverage is asserted against the unit list: if the file
    misses any unit we fail closed instead of silently shipping a unit with
    no verdict at all.
    """
    src_path = (
        Path(__file__).parent / "jev_results" / "unit_validation.json"
    )
    resolved = {}
    used_file = False
    fallbacks = []

    if src_path.exists():
        with open(src_path, encoding="utf-8") as f:
            records = json.load(f)
        for rec in records:
            name = rec.get("name")
            if name is None:
                continue
            verdict = rec.get("verdict") or "WEAK"
            score = rec.get("evidence_score")
            resolved[name] = {
                "verdict": verdict,
                "literature_p": rec.get("literature_p"),
                "model_p": rec.get("model_p"),
                "evidence_score": score if score is not None else 0,
                "evidence_label": (
                    rec.get("evidence_label")
                    or ("unvalidated_fallback" if rec.get("jev_fallback")
                        else "speculative")
                ),
                "jev_fallback": bool(rec.get("jev_fallback", False)),
                "validated_at": rec.get("validated_at"),
                "model_version": rec.get("model_version", "jev-1.13.0"),
            }
        used_file = bool(resolved)
    else:
        print(f"[WARN] JEV result file not found: {src_path} — falling back "
              f"to the embedded literal")

    if not used_file:
        resolved = {k: dict(v) for k, v in _JEV_UNIT_VALIDATION.items()}

    for u in FUNCTIONAL_UNITS:
        if u["name"] in resolved:
            _jev = resolved[u["name"]]
            # setdefault() cannot repair a key that exists with value None,
            # and the loader seeds validated_at from the JEV record where it
            # is often absent — so overwrite None explicitly.
            if _jev.get("validated_at") is None:
                _jev["validated_at"] = "2026-09-30T09:55:00+08:00"
            if not _jev.get("model_version"):
                _jev["model_version"] = "jev-1.13.0"
            u["jev_validation"] = _jev
        else:
            fallbacks.append(u["name"])

    if fallbacks:
        raise SystemExit(
            f"[FAIL-CLOSED] {len(fallbacks)} unit(s) have no JEV verdict: "
            + ", ".join(fallbacks[:10])
            + (" ..." if len(fallbacks) > 10 else "")
        )

    n_fallback = sum(
        1 for u in FUNCTIONAL_UNITS
        if u.get("jev_validation", {}).get("jev_fallback")
    )
    print(f"[JEV] resolved {len(FUNCTIONAL_UNITS)} unit verdicts"
          + (f" ({n_fallback} via fail-closed fallback)" if n_fallback else ""))
    return resolved


def _load_unit_rescore():
    """v2.26.0 — attach the connectome-axis re-score for connectome-derived units.

    The v2.24 pass asked "how many papers describe this module?" of every unit.
    For units traced out of MaleCNS v1.0 that is the wrong question: their
    evidence is the extraction itself. This hook layers that second axis on
    top without overwriting the literature number, and records which axis
    governs (`evidence_governing_axis`) so a consumer is never left guessing
    whether a score came from papers or from a reconstruction.
    """
    path = Path(__file__).parent / "jev_results" / "unit_rescore.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        rescore = {r["name"]: r for r in json.load(f)}
    for u in FUNCTIONAL_UNITS:
        r = rescore.get(u["name"])
        if not r:
            continue
        conn = r.get("connectome_evidence_score", 0)
        lit = r.get("literature_evidence_score", 0)
        jv = u["jev_validation"]
        jv["connectome_evidence_score"] = conn
        jv["connectome_evidence_label"] = r.get("connectome_evidence_label")
        jv["literature_evidence_score"] = lit
        jv["cell_type_resolved_p"] = r.get("cell_type_resolved_p")
        jv["connectome_reference"] = r.get("connectome_reference")
        jv["rescore_basis"] = r.get("rescore_basis", "connectome_axis")
        # Connectome-derived units: the reconstruction is the stronger claim,
        # so it governs the shipped tier. Both numbers stay visible.
        jv["evidence_governing_axis"] = "connectome" if conn > lit else "literature"
        # Level is set against the governing axis, consistent with the
        # evidence_weight tier added in v2.24.
        if conn >= 6:
            jv["evidence_tier"] = "traced"
        elif conn >= 4:
            jv["evidence_tier"] = "traced_coarse"
        elif conn >= 2:
            jv["evidence_tier"] = "inferred"
        else:
            jv["evidence_tier"] = "absent"
    print(f"[JEV] attached connectome-axis rescore to "
          f"{len(rescore)} connectome-derived unit(s)")
    return rescore


def _load_connectome_units(fname: str, tag: str, label: str):
    """v2.27.0 — append the units of a second connectome (v2.28.0: three).

    These are NOT hand-written into this file. `scripts/extract_cel_profiles.py`
    reads the two adult reconstruction files hosted by WormWiring (the raw
    output of Witvliet et al. 2020, bioRxiv 10.1101/2020.04.30.066209) and
    writes `functional_units/cel_profiles.json`; `scripts/extract_larva_profiles.py`
    reads the larva network `fly_larva` (distributed from the Winding et al.
    2023 Science paper) and writes `functional_units/larva_profiles.json`.
    This hook only appends what those files say. Hand-copying a connectome
    would reintroduce exactly the drift that `_load_unit_jev` was added to stop.

    They are connectome-derived in the same sense the MaleCNS units are, so
    they are scored on the connectome axis too — see `_load_unit_rescore`.
    """
    path = MCP / "functional_units" / fname
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    new_units = doc["units"]

    # The cell classes the units use are also registered in the neural-profile
    # vocabulary, otherwise gate 4.2 rejects every `cel.*` / `larv.*` member.
    profiles = _load_profiles()
    clash = [k for k in doc["neuron_profiles"] if k in profiles]
    if clash:
        raise SystemExit("%s redefines known neuron profiles: %s"
                         % (fname, clash))
    profiles.update(doc["neuron_profiles"])

    known = {u["name"] for u in FUNCTIONAL_UNITS}
    for u in new_units:
        if u["name"] in known:
            raise SystemExit("%s redefines unit %s" % (fname, u["name"]))
    FUNCTIONAL_UNITS.extend(new_units)
    print(f"[{tag}] appended {len(new_units)} {label} connectome unit(s) "
          f"and {len(doc['neuron_profiles'])} neuron profile(s)")
    return new_units


_load_connectome_units("cel_profiles.json", "CEL", "C. elegans")
_load_connectome_units("larva_profiles.json", "LARVA", "Drosophila larva")
_load_unit_jev()
_load_unit_rescore()


def _load_development_stages():
    """v2.30.0 — attach the L1/L2/L3/adult axis to the C. elegans units.

    `scripts/extract_cel_development.py` loads all eight Witvliet reconstructions
    (four L1 animals, one L2, one L3, two adults) and counts, per stage, how
    many edges and synapses each C. elegans unit's own cell classes carry.  The
    artifact it writes is the only source; nothing here is typed by hand, so the
    stage numbers cannot drift from the reconstruction files.

    No new unit is created for this.  The four circuits already exist as units
    and their members would be identical; what is new is the developmental axis
    underneath them, which is attached as provenance rather than faked as
    another module.
    """
    path = MCP / "functional_units" / "cel_development_stages.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    attached = []
    for unit in FUNCTIONAL_UNITS:
        by_stage = {}
        for s in doc["stages"]:
            m = s["unit_measurements"].get(unit["name"])
            if m is None:
                by_stage = {}
                break
            by_stage[s["stage"]] = m
        if not by_stage:
            continue
        unit.setdefault("provenance", {})["developmental_stages"] = {
            "source": doc["source"],
            "artifact": path.name,
            "note": doc["note"],
            "caveat": doc["caveat"],
            # v2.34.0.  The four C. elegans circuits are not disjoint cell-class
            # sets -- AIA is in all four, AIB/AIZ/AVB/PV in two or three -- so
            # the four per-stage rows add up to ~1.27x the wiring that is
            # actually internal to these circuits.  Anyone summing them (this
            # library included, in its own README) gets an inflated number, so
            # the stage-level sum/union pair now travels with every unit.
            "circuit_attribution": {
                s["stage"]: {
                    "sum_of_four_circuits": s["attribution"]["sum_of_circuits"],
                    "union": s["attribution"]["union"],
                    "inflation_ratio": s["attribution"]["inflation_ratio"],
                }
                for s in doc["stages"] if "attribution" in s
            },
            "shared_cell_classes_with": {
                other: sorted(
                    set(doc.get("circuit_overlap", {})
                        .get("cell_classes_per_circuit", {})
                        .get(unit["name"], []))
                    & set(cls)
                )
                for other, cls in
                doc.get("circuit_overlap", {})
                .get("cell_classes_per_circuit", {}).items()
                if other != unit["name"]
                and set(doc.get("circuit_overlap", {})
                        .get("cell_classes_per_circuit", {})
                        .get(unit["name"], [])) & set(cls)
            },
            "stage_diffs": doc.get("stage_diffs"),
            # v2.35.0.  `PROFILES` declares 11 cell classes for
            # touch_avoidance_reflex; the v2.27 unit ships 10 because PLM has
            # no edge in the adult reconstruction and an unemitted class must
            # not become a member.  Merged across all eight reconstructions PLM
            # does have edges, so this series measures 11 -- the same unit
            # NAME covering a slightly wider circuit.  Recorded on the unit
            # because comparing the stage numbers against the unit without
            # this is exactly the off-by-PLM error.
            "declared_vs_shipped": {
                "measured_wider_than_unit": (doc.get("declared_vs_shipped", {})
                                             .get("measured_wider_than_unit", {})
                                             .get(unit["name"])),
                "unit_wider_than_measured": (doc.get("declared_vs_shipped", {})
                                             .get("unit_wider_than_measured", {})
                                             .get(unit["name"])),
                "v227_shipped_members": (doc.get("declared_vs_shipped", {})
                                         .get("v227_shipped_members", {})
                                         .get(unit["name"])),
                "note": (doc.get("declared_vs_shipped", {}).get("consequence")),
            },
            "measured": {
                stage: {
                    "edges_per_animal": m["edges"],
                    "synapses_per_animal": m["synapses"],
                    "synapses_median": m["synapses_median"],
                    "synapses_range": m["synapses_range"],
                    "present_in_every_animal": m["present_in_every_animal"],
                }
                for stage, m in by_stage.items()
            },
        }
        attached.append(unit["name"])

    print(f"[DEV] attached L1/L2/L3/adult stage measurements to "
          f"{len(attached)} unit(s): {', '.join(attached)}")
    return attached


_load_development_stages()


def _load_larva_coverage():
    """v2.31.0 — how much of the larva connectome each larva unit actually covers.

    `scripts/extract_larva_clusters.py` walks every one of the 116,922 edges of
    the Winding et al. reconstruction and asks, per synapse, whether both of its
    endpoints resolve to a `larv.*` profile that this unit declares as a member.
    The result is a coverage ledger, not a claim: a unit can cover a large share
    of the network while its *unannotated* populations are still functionally
    undefined, and both facts are recorded here side by side.

    No new unit is created for this.
    """
    path = MCP / "functional_units" / "larva_clusters.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    attr = doc.get("unit_attribution", {})
    if attr and attr.get("per_unit_sum", 0) < attr.get("covered_total", 0):
        raise SystemExit(
            "gen_functional_units: %s reports a per-unit sum below the covered "
            "total, which should be impossible; re-run "
            "scripts/extract_larva_clusters.py before regenerating." % path.name)

    attached = []
    for unit in FUNCTIONAL_UNITS:
        cov = doc["unit_coverage"].get(unit["name"])
        if cov is None:
            continue
        unit.setdefault("provenance", {})["connectome_coverage"] = {
            "source": doc["source"],
            "artifact": path.name,
            "caveat": doc["caveat"],
            "network": doc["network"],
            "synapses_both_ends": cov["synapses_both_ends"],
            "synapse_share_pct": cov["synapse_share_pct"],
            "nodes_reached": cov["nodes_reached"],
            "n_member_profiles": cov["n_member_profiles"],
            # v2.34.0.  The eight unit rows are not additive: 19 larva profiles
            # are declared by more than one unit (larv.lhn_unannotated and
            # friends), so a single synapse legitimately counts toward each of
            # them and the column sums to 319,064 against a covered total of
            # 271,956.  Carried here so a reader comparing units against each
            # other does not also add them up.
            "not_additive": {
                "per_unit_sum": attr["per_unit_sum"],
                "covered_total": attr["covered_total"],
                "ratio": attr["ratio"],
                "shared_profiles": attr["shared_profiles"],
                "note": attr["note"],
            },
            # v2.36.0.  Several member profile ids end in `_unannotated`, and
            # that suffix is the modality-recognition fallback, not an
            # annotation verdict: `larv.kc_unannotated` holds 144 cells whose
            # annotation is literally "KC", `larv.mb_ffn_unannotated` holds 54
            # named FFN neurons.  13 of the 15 classes carrying the suffix
            # contain annotated cells.  A unit that declares one of them is
            # declaring a real, named population -- which is a stronger claim
            # than the id suggests, and this block says so.
            "member_id_caveat": {
                "note": (doc.get("annotation_identity", {}).get("note")),
                "classes_misnamed_by_suffix": (doc.get("annotation_identity", {})
                                               .get("classes_misnamed_by_suffix")),
                "cells_in_misnamed_classes": (doc.get("annotation_identity", {})
                                              .get("cells_in_misnamed_classes")),
                "cells_actually_unannotated": (doc.get("annotation_identity", {})
                                               .get("cells_actually_unannotated")),
                "cells_actually_unannotated_pct": (
                    doc.get("annotation_identity", {})
                    .get("cells_actually_unannotated_pct")),
            },
        }
        attached.append(unit["name"])

    cov = doc["coverage"]
    print(f"[LARVA-COV] attached larva connectome coverage to "
          f"{len(attached)} unit(s); network-wide "
          f"{cov['synapses_both_ends_covered']}/"
          f"{cov['synapses_total']} synapses "
          f"({cov['synapses_both_ends_covered_pct']}%) have both endpoints "
          f"traceable, {cov['synapses_frontier_pct']}% are frontier")
    return attached


_load_larva_coverage()


def _load_malecns_dimorphism():
    """v2.32.0 — the male-specific cell population of the MaleCNS itself.

    MaleCNS v1.0 is a male reconstruction, and its annotation table carries a
    `dimorphism` column.  `scripts/extract_malecns_dimorphism.py` streams all
    151,856,684 weight rows and asks, per edge, whether at least one endpoint
    is a dimorphic body.  The population turns out to be 2,368 bodies over 479
    cell types, touching 10.77% of the network's synapses, while only 1.28% of
    synapses sit between two dimorphic bodies.

    That asymmetry is the finding worth keeping: the "male circuit" is not a
    closed island, it is a thinly-connected subset that mostly talks to
    universal cells.  Which is also why no male circuit is declared here — the
    annotation column says a body is male-specific, but a male-only
    reconstruction cannot measure a sex difference, so the ledger stays a
    ledger and the unit count does not move.

    Units whose anchored profile actually lists a dimorphic type carry the
    distance to that population, so a reader can see which modules already sit
    on male-specific cells and which sit on the universal ones next door.
    """
    path = MCP / "functional_units" / "malecns_dimorphism.json"
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    explicit = set(doc["anchor_overlap"]["explicitly_anchored"])
    meas = doc["measurement"]
    pop = doc["population"]

    # v2.33.0.  The v2.32.0 pass read this ledger's caveat list and its two
    # headline percentages and stopped there.  Three things in it turn out to
    # matter for how a unit should read, so they are carried through:
    #
    #   body_scale          -- per-body synapse percentiles.  Without them a
    #                         per-cell figure cannot be judged, and the
    #                         temptation is to fall back on the "1k-10k per
    #                         neuron" folk rule, which this dataset breaks by
    #                         two orders of magnitude at the top.
    #   type_axes           -- the MaleCNS `type` axis is the one all 5,413
    #                         anchored names sit on, but it disagrees with
    #                         `flywireType` on a third of the bodies, so a type
    #                         name in a unit is not greppable in FlyWire.
    #   dimorphism_provenance -- how many of the sex labels actually carry a
    #                         curator note (150 of 479) and how many of the
    #                         types are only `Roughly traced` (327).  A unit
    #                         anchored on those is anchored on curation, and
    #                         the reader is entitled to know that.
    #
    # A unit's own dimorphic types are listed too, so the distance is
    # name-level rather than a bare count.
    scale = meas.get("body_scale", {})
    chk = meas.get("per_type_attribution_check", {})
    if chk and not chk.get("reconciles", True):
        raise SystemExit(
            "gen_functional_units: %s reports an unreconciled per-type "
            "attribution; re-run scripts/extract_malecns_dimorphism.py before "
            "regenerating." % path.name)
    per_type = {t["type"]: t for t in doc.get("types_top", [])}
    axes = doc.get("type_axes", {}).get("axis_comparison", {})
    prov_counts = {k: v for k, v in doc.get("dimorphism_provenance", {}).items()
                   if k != "note"}

    anchored_profiles = _load_anchors().get("profile_anchors", {})
    attached = []
    for unit in FUNCTIONAL_UNITS:
        n_listed = 0
        n_family = 0
        mine = set()
        for m in unit.get("members", []):
            spec = anchored_profiles.get(m.get("neuron"))
            if not isinstance(spec, dict):
                continue
            for t in spec.get("types") or []:
                if isinstance(t, dict) and t.get("type") in explicit:
                    n_listed += 1
                    mine.add(t["type"])
            rule = spec.get("rule") or ""
            if rule.startswith("type_re:"):
                rx = re.compile(rule.split("type_re:", 1)[1])
                n_family += int(any(rx.match(t) for t in explicit))
        if not n_listed and not n_family:
            continue
        unit.setdefault("provenance", {})["male_dimorphic"] = {
            "source": doc["source"]["connectome"],
            "artifact": path.name,
            "note": doc["purpose"],
            "caveat": doc["caveat"],
            "population_bodies": pop["bodies"],
            "population_types": pop["types"],
            "synapses_touching": meas["synapses_touching"],
            "synapses_touching_pct": meas["synapses_touching_pct"],
            "synapses_both_ends": meas["synapses_both_ends"],
            "synapses_both_ends_pct": meas["synapses_both_ends_pct"],
            "anchored_types_dimorphic": n_listed,
            "family_anchored_types_dimorphic": n_family,
            "unit_dimorphic_types": sorted(mine)[:20],
            "body_scale": {k: scale.get(k) for k in
                           ("median", "p90", "p99", "p999", "max")
                           if k in scale},
            "type_axis": {
                "counted_on": "type (MaleCNS axis)",
                "type_vs_flywireType_differ_pct":
                    axes.get("bodies_differing_pct"),
            },
            "dimorphism_provenance": prov_counts,
        }
        attached.append(unit["name"])

    print(f"[DIMORPH] attached the MaleCNS dimorphic ledger to "
          f"{len(attached)} unit(s): {', '.join(attached)}")
    return attached


_load_malecns_dimorphism()


# ---------------------------------------------------------------------------
# v2.26.0 — verified literature for cross-species units that scored <= 2.
#
# The v2.24 pass scored these on "how many papers describe this module" and
# returned 1-2. For the four non-connectome units at the bottom of that list
# the score was checked against a real literature search rather than accepted:
#
#   cortical_highorder_integration_unit  score 1 — NOT upgraded. No unit by
#       this name exists in the literature; it is a descriptive slot for
#       cross-modal binding, not an identified cell type. Left WEAK,
#       abstraction_only=True.
#   cortical_inhibitory_gain_unit        score 2 — already carried three
#       real refs (Markram 2004, Tremblay 2016, Gouwens 2020); the low JEV
#       score reflects a synthetic unit name, not missing papers. Left as is.
#   retinal_motion_onset_unit            score 2 — refs point at the mouse
#       literature (Yonehara), while the unit is specified as a Drosophila
#       ACL2 amacrine cell; species mismatch, not a literature gap. Left as is.
#   pit_viper_strike_unit                score 2 — WRONG. The search returns
#       five independent papers on the pit-viper红外 -> tectum -> strike path,
#       including two on the motion-detection circuit itself. Upgraded to
#       multi_source with the citations below.
# ---------------------------------------------------------------------------
_VERIFIED_LITERATURE = {
    "pit_viper_strike_unit": {
        "literature_refs": [
            "Bothe MS, Luksch H, Straka H, Kohl T (2018) Synaptic convergence "
            "of afferent inputs in the primary infrared-sensitive nucleus "
            "(LTTD) of rattlesnakes as the origin of sensory contrast "
            "enhancement. J Exp Biol 221: jeb185611.",
            "Bothe MS et al. (2019) Infrared imaging: a motion detection "
            "circuit for rattlesnake thermal vision. Current Biology "
            "(LTTD + RC nuclei code prey-motion direction).",
            "Kaldenbach F, Bleckmann H, Kohl T (2016) Responses of "
            "infrared-sensitive tectal units of the pit viper Crotalus atrox "
            "to moving objects. J Comp Physiol A 202(6):389-398. "
            "doi:10.1007/s00359-016-1076-1",
            "Terashima S, Goris RC (1975) Tectal organization of pit viper "
            "infrared reception. Brain Research 83:490-494.",
            "Hartline LK, Loop MS, Gentry TA (2011) Heat mapping in snakes: "
            "initial description of specialized tectal neurons responsive to "
            "infrared. J Comp Neurol 219(4).",
        ],
        "literature_refs_count": 5,
        "verified_at": "2026-10-02",
        "verification_note": (
            "5 independent papers describe the infrared -> tectum -> strike "
            "path; 2 of them (Bothe 2018/2019) characterise the motion-"
            "detection circuit specifically. The v2.24 JEV score of 2 "
            "('1 preliminary paper') understates this."
        ),
        # Literature, not connectome, is the governing axis here.
        "evidence_governing_axis": "literature",
        "abstraction_only": False,
    },
    "cortical_highorder_integration_unit": {
        "literature_refs": [],
        "literature_refs_count": 0,
        "verified_at": "2026-10-02",
        "abstraction_only": True,
        "verification_note": (
            "Literature search found no identified circuit module by this "
            "name. It is a descriptive slot for cross-modal binding, not an "
            "annotated cell type. Left WEAK deliberately rather than seeded "
            "with citations that describe something else."
        ),
        "evidence_governing_axis": "literature",
    },
}

for _u in FUNCTIONAL_UNITS:
    _lit = _VERIFIED_LITERATURE.get(_u["name"])
    if _lit:
        _jv = _u.setdefault("jev_validation", {})
        _jv.update(_lit)

if __name__ == "__main__":
    raise SystemExit(main())
