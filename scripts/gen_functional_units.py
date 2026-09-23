"""gen_functional_units.py -- author the two composition libraries.

Writes (single source of truth, stdlib-only JSON):
    flybrain-connectome-mcp/functional_units/functional_units.json    (40 units)
    flybrain-connectome-mcp/functional_units/connection_types.json    (50 types)

WHY A GENERATOR AND NOT HAND-WRITTEN JSON
-----------------------------------------
Every functional unit's `members` reference neuron keys that MUST exist in
synthetic_bio_topology.MODULE_PROFILES, and every `internal_wiring` edge MUST
reference a connection type that exists in connection_types.json. Hand-writing
80 KB of JSON would let a typo (`pyramidal_l5b` vs `pyramidal_l5bt`) ship as a
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
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path("C:/Users/xing/Desktop/flybrain-connectome")
MCP = ROOT / "flybrain-connectome-mcp"
OUT_DIR = MCP / "functional_units"


def _load_profiles() -> dict:
    spec = importlib.util.spec_from_file_location(
        "sbt_for_units", str(MCP / "synthetic_bio_topology.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sbt_for_units"] = mod
    spec.loader.exec_module(mod)
    return mod.MODULE_PROFILES


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
    "*":                     "Wildcard: any port type (used by generic forms).",
}

# Port types that are `in`-only / `out`-only semantics are NOT enforced here;
# the composer checks direction, the unit declares which side a port lives on.


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
      "Non-synaptic field coupling; activity in one fibre changes the excitability of a neighbour.",
      "*", "*", "+/-", "many_to_many", "intra_unit", "immediate", False,
      "ephaptic_coupling", {"field_gain": 0.05}, "ephatic/ephaptic coupling (Anastassiou 2011)"),
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
# 2. FUNCTIONAL UNITS -- 40 units, each = one function, N neuron populations
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
      [("arousal_out", "arousal.state", True)],
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
def main() -> int:
    profiles = _load_profiles()
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
    }

    units_doc = {
        "schema_version": "1.0",
        "source": "Curated cross-species comparative neuroscience; NOT extracted "
                  "from MaleCNS v1.0 (see per-unit provenance.extracted_from_malecns).",
        "caveat": "A functional unit is a curated sub-circuit pattern, not a "
                  "measured cell assembly. Members name neuron populations from "
                  "synthetic_bio_topology.MODULE_PROFILES; ratios are composition "
                  "weights, not measured cell counts. Treat as a compositional "
                  "scaffold with literature provenance, not as ground truth.",
        "port_types": PORT_TYPES,
        "stats": stats,
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
        "source": "40 forms map 1:1 onto the curated motif document "
                  "(motifs/swarm_agent_topology_motifs.json); 10 additional "
                  "macro-projection forms are new here.",
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


if __name__ == "__main__":
    raise SystemExit(main())
