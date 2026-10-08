"""
synthetic_bio_topology.py  --  Virtual-organism topology generator (C1)
----------------------------------------------------------------------
Builds SYNTHETIC, task-tailored multi-agent "virtual organisms" by COMPOSING the
real fly-brain MOTIFS (inhibitory hub / reservoir small-world / recurrent
feedback) extracted from MaleCNS v1.0. We do NOT scale the real 166,700-neuron
connectome (infeasible on commodity hardware); instead we reuse the *topology
principles* to design novel agent graphs that fit a requested morphology.

This is the software-only analog of the Xenobots / Neurobots idea: define a
spec (how many "tissues", how many "cells" per tissue, which bio-motifs to
engage) -> get a graph you can instantiate as a SwarmLabs agent swarm.

MOTIF SOURCE (option A — the generator really talks to the service)
------------------------------------------------------------------
The motif document is resolved at RUNTIME, not read from a second static copy:

    --motif-source api     hard requirement: pull from the service
                           (`export_swarm_motifs` over HTTP). Fails loudly if
                           the service is unreachable — no silent fallback.
    --motif-source auto    (default) try the service first, then a warm API
                           cache, then the offline snapshot. Records exactly
                           which path was used and why in `motif_provenance`.
    --motif-source local   offline only: read the committed snapshot.
                           Never touches the network.

API key precedence: `--api-key` -> env `FLYBRAIN_API_KEY` -> the service's own
`mcp_connectome/config.json` (same-machine only). An AUTH rejection is treated as
a configuration error and always fails loudly, even under `auto` — a wrong key
must not hide behind a stale snapshot. Use `--motif-source local` to go offline
deliberately.

Whatever the path, the resolved document is hashed (sha256) and the whole
provenance trail is embedded in every artifact we emit, so a reader can always
tell whether a topology came from live data or from a frozen snapshot.

The generator deliberately stays a DERIVED artifact: it never touches the raw
neuron data, so SwarmLabs / any other project keeps its independence.

SWARMLABS EXPORT (option B — instantiable agent-swarm config)
------------------------------------------------------------
Every organism is also emitted as a SwarmLabs-loadable config trio:
    <name>.swarm.json / <name>.swarm.yaml   -- agent swarm spec (agents +
                                               modules + weighted edge table +
                                               guardrail invariants + validation)
    <name>.json / <name>.html               -- the raw organism + live preview

The swarm config aligns with `swarmlabs/agentteams/config/team.yaml`
(leader-worker topology, role contracts, thresholds) so it drops straight into
the SwarmLabs runtime.

CLI:
    python synthetic_bio_topology.py                          # auto + defaults
    python synthetic_bio_topology.py --motif-source api       # require service
    python synthetic_bio_topology.py --motif-source local     # fully offline
    python synthetic_bio_topology.py --evolve n_nodes=40      # target search
    python synthetic_bio_topology.py --no-swarmlabs           # organism only
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "motifs"))
from flybrain_connectome_client import (  # noqa: E402
    DEFAULT_BASE_URL,
    FlybrainHTTPClient,
    FlybrainUnavailable,
    resolve_local_api_key,
)

MOTIF_FILE = HERE / "motifs" / "swarm_agent_topology_motifs.json"
API_CACHE_FILE = HERE / "motifs" / ".motif_api_cache.json"
OUT_DIR = HERE / "generated_organisms"
SWARM_DIR = OUT_DIR / "swarmlabs"

REQUIRED_MOTIFS = ("inhibitory_hub", "reservoir_smallworld", "recurrent_feedback")
MOTIF_SOURCES = ("auto", "api", "local")

# ---------------------------------------------------------------------- #
# Document versions — two distinct things, never conflate them:
#   SCHEMA_VERSION                  the top-level organism / swarm-config schema
#                                   (v1.2.1 added the `prov_json` W3C field)
#   MOTIF_PROVENANCE_SCHEMA_VERSION the `motif_provenance` sub-document, which
#                                   has been stable since v1.2.0 (it is also
#                                   what the PROV bundle records as tool_version).
# ---------------------------------------------------------------------- #
SCHEMA_VERSION = "1.2.1"
MOTIF_PROVENANCE_SCHEMA_VERSION = "1.2.0"

# ====================================================================== #
# Module functional profiles — each module type gets a different motif mix
# Derived from real fly connectome superclass recurrence rates (motif doc).
# ====================================================================== #
MODULE_PROFILES = {
    "sensory": {
        "reservoir_density": 0.50,   # high: dense input buffering
        "recurrent_pct": 0.10,       # low: transient, not memory
        "has_inhibition": False,
        "description": "High-density input buffer (ol_intrinsic analog)",
        # SwarmLabs-consumable semantics (schema v1.1)
        "capability": ["perceive", "ingest", "buffer"],
        "task_hint_pool": ["data_ingest", "signal_preprocess",
                           "stream_buffer", "sensor_noise_filter"],
        "lead_task_hint": "input_triage",
    },
    "memory": {
        "reservoir_density": 0.20,   # sparse: focused recall
        "recurrent_pct": 0.40,       # high: persistent state (cb_intrinsic)
        "has_inhibition": False,
        "description": "Recurrent working memory (cb_intrinsic analog)",
        "capability": ["gp_surrogate", "remember", "replay", "state_carry"],
        "task_hint_pool": ["gp_surrogate_fit", "prior_recall",
                           "state_carry", "history_replay"],
        "lead_task_hint": "memory_synthesis",
    },
    "motor": {
        "reservoir_density": 0.10,   # minimal: direct output
        "recurrent_pct": 0.10,       # low: clean signal
        "has_inhibition": True,      # local brake (vnc_intrinsic)
        "description": "Motor output with local inhibition (vnc_intrinsic)",
        "capability": ["execute", "actuate", "numeric_integration",
                       "verify_output"],
        "task_hint_pool": ["experiment_run", "numeric_integration",
                           "output_check", "actuation_dispatch"],
        "lead_task_hint": "output_coordination",
    },
    "integration": {
        "reservoir_density": 0.30,   # moderate: cross-talk
        "recurrent_pct": 0.25,       # moderate: stabilization
        "has_inhibition": True,      # distributed brake
        "description": "Cross-module integration with inhibition",
        "capability": ["rank", "synthesize", "arbitrate", "elo_score"],
        "task_hint_pool": ["candidate_rank", "cross_domain_bridge",
                           "elo_scoring", "arbitrate_conflict"],
        "lead_task_hint": "cross_module_arbitration",
    },
    # Phase 1 新模块（2026-09-18）：attention + working_memory
    "attention": {
        "reservoir_density": 0.15,   # low: focused, not diffuse
        "recurrent_pct": 0.20,       # moderate: some persistence for focus
        "has_inhibition": True,      # must inhibit non-attended items
        "description": "Attention allocation with selective inhibition",
        "capability": ["focus", "filter", "prioritize", "salience_detection"],
        "task_hint_pool": ["attention_focus", "salience_detection",
                           "filter_irrelevant", "prioritize_signal"],
        "lead_task_hint": "attention_allocation",
    },
    "working_memory": {
        "reservoir_density": 0.35,   # moderate: active manipulation needs density
        "recurrent_pct": 0.45,       # high: persistent state for active holding
        "has_inhibition": False,     # no inhibition, just holding
        "description": "Short-term active memory for manipulation",
        "capability": ["hold", "manipulate", "update", "active_recall"],
        "task_hint_pool": ["working_hold", "active_manipulation",
                           "state_update", "short_term_recall"],
        "lead_task_hint": "working_memory_update",
    },
    # ---- Phase 1 模块库扩展（决策 1：激进 4 → 10）----
    # 在 attention + working_memory 基础上再补 4 个有果蝇生物学依据的功能模块
    "reward": {
        "reservoir_density": 0.25,   # moderate: broadcast-style value signal
        "recurrent_pct": 0.30,       # moderate: reward-prediction error persists briefly
        "has_inhibition": False,     # modulatory, not a brake
        "description": "Dopaminergic reward modulation (PPL/PAM analog)",
        "capability": ["reward_signal", "value_estimate", "reinforce", "motivation_gating"],
        "task_hint_pool": ["reward_prediction", "value_estimate",
                           "positive_reinforce", "goal_weighting"],
        "lead_task_hint": "reward_allocation",
    },
    "punishment": {
        "reservoir_density": 0.25,   # moderate: aversive value signal
        "recurrent_pct": 0.30,       # moderate: punishment prediction persists briefly
        "has_inhibition": True,      # aversive signal suppresses conflicting actions
        "description": "Aversive/punishment modulation (DMP/DopR analog)",
        "capability": ["punish_signal", "penalty_estimate", "avoidance_gate", "negative_reinforce"],
        "task_hint_pool": ["penalty_estimate", "avoidance_gate",
                           "negative_reinforce", "risk_downweight"],
        "lead_task_hint": "punishment_allocation",
    },
    "habit": {
        "reservoir_density": 0.30,   # moderate: consolidated procedural chunks
        "recurrent_pct": 0.50,       # high: persistent skill state (slow consolidation)
        "has_inhibition": False,     # no inhibition, just reinforcement-stamped
        "description": "Procedural habit consolidation (MBON analog)",
        "capability": ["automatize", "chunk", "procedural_consolidate", "skill_encode"],
        "task_hint_pool": ["skill_chunk", "procedural_consolidate",
                           "automatize_step", "habit_encode"],
        "lead_task_hint": "habit_consolidation",
    },
    "metacognition": {
        "reservoir_density": 0.20,   # low: sparse confidence estimates
        "recurrent_pct": 0.35,       # moderate: calibration state persists
        "has_inhibition": True,      # suppresses low-confidence outputs
        "description": "Metacognitive confidence/uncertainty gating (CRE/DCHB analog)",
        "capability": ["confidence_estimate", "uncertainty_detect", "meta_monitor", "calibration"],
        "task_hint_pool": ["confidence_estimate", "uncertainty_flag",
                           "meta_monitor", "calibration_check"],
        "lead_task_hint": "metacognitive_monitor",
    },

    # ------------------------------------------------------------------ #
    # Phase 3 模块库扩展（2026-09-22）：跨生物保守神经元类型 30 个
    # 基于 Allen Institute 2023 小鼠全脑图谱 + 跨物种比较神经科学
    # 每个模块对应一种跨生物保守的神经元类型，可直接参与组合。
    # 新增字段：neurotransmitter / brain_region / species_source /
    #           allen_class / biological_reference
    # ------------------------------------------------------------------ #
    # ---- 皮层兴奋性锥体细胞 (4) ----
    "pyramidal_l23": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.15,
        "has_inhibition": False,
        "description": "Layer 2/3 pyramidal cell: intracortical relay, local computation",
        "capability": ["relay", "integrate", "local_compute", "forward_pass"],
        "task_hint_pool": ["signal_relay", "feature_extract", "local_integrate", "forward_propagate"],
        "lead_task_hint": "cortical_relay",
        "neurotransmitter": "glutamate",
        "brain_region": "cortex_l2_l3",
        "species_source": ["mouse", "rat", "human", "zebrafish"],
        "allen_class": "E_EXTPAC1",
        "biological_reference": "Allen Brain Atlas 2023, 5322 types",
    },
    "pyramidal_l4": {
        "reservoir_density": 0.40,
        "recurrent_pct": 0.10,
        "has_inhibition": False,
        "description": "Layer 4 spiny stellate: thalamocortical input target",
        "capability": ["sensory_relay", "thalamic_target", "feature_extract"],
        "task_hint_pool": ["sensory_input", "thalamic_relay", "feature_extract"],
        "lead_task_hint": "sensory_relay",
        "neurotransmitter": "glutamate",
        "brain_region": "cortex_l4",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "E_EXTPAC2",
        "biological_reference": "Allen Brain Atlas 2023",
    },
    "pyramidal_l5": {
        "reservoir_density": 0.20,
        "recurrent_pct": 0.15,
        "has_inhibition": False,
        "description": "Layer 5 pyramidal (BET): corticospinal, subcortical projection",
        "capability": ["motor_command", "subcortical_proj", "deep_relay"],
        "task_hint_pool": ["motor_command", "subcortical_proj", "output_dispatch"],
        "lead_task_hint": "motor_command",
        "neurotransmitter": "glutamate",
        "brain_region": "cortex_l5",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "E_EXTPAC2",
        "biological_reference": "Allen Brain Atlas 2023, corticospinal",
    },
    "pyramidal_l6_it": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.20,
        "has_inhibition": False,
        "description": "Layer 6 intratelencephalic: feedback projection to cortex",
        "capability": ["feedback_proj", "recurrent_relay", "cortical_feedback"],
        "task_hint_pool": ["feedback_signal", "recurrent_relay", "cortical_loop"],
        "lead_task_hint": "feedback_relay",
        "neurotransmitter": "glutamate",
        "brain_region": "cortex_l6",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "E_EXTPAC1",
        "biological_reference": "Allen Brain Atlas 2023",
    },
    # ---- 皮层抑制性中间神经元 (5) ----
    "interneuron_pv": {
        "reservoir_density": 0.15,
        "recurrent_pct": 0.20,
        "has_inhibition": True,
        "description": "PV interneuron: fast-spiking, gamma rhythm pacemaker, feedforward inhibition",
        "capability": ["fast_spiking", "gamma_rhythm", "feedforward_inhibit", "timing"],
        "task_hint_pool": ["gamma_pacing", "fast_inhibit", "timing_gate", "burst_block"],
        "lead_task_hint": "fast_inhibition",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_all_layers",
        "species_source": ["mouse", "rat", "human", "drosophila"],
        "allen_class": "I_PVALB_1",
        "biological_reference": "Allen Brain Atlas 2023, gamma rhythm pacemaker",
    },
    "interneuron_sst": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.25,
        "has_inhibition": True,
        "description": "SST interneuron: slow-oscillating, dendrite-targeted, feedback inhibition",
        "capability": ["feedback_inhibit", "dendrite_target", "slow_oscillation"],
        "task_hint_pool": ["feedback_suppress", "dendrite_inhibit", "slow_oscillation"],
        "lead_task_hint": "feedback_inhibition",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_all_layers",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "I_SST_ND",
        "biological_reference": "Allen Brain Atlas 2023",
    },
    "interneuron_vip": {
        "reservoir_density": 0.20,
        "recurrent_pct": 0.20,
        "has_inhibition": True,
        "description": "VIP interneuron: disinhibition, targets PV/SST, attention gating",
        "capability": ["disinhibit", "target_pv", "attention_gate", "release_inhibition"],
        "task_hint_pool": ["disinhibition", "attention_release", "target_pv_inhibit"],
        "lead_task_hint": "disinhibition",
        "neurotransmitter": "vip",
        "brain_region": "cortex_l2_l3",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "I_VIP_DN",
        "biological_reference": "Lee et al 2010 Nature, VIP disinhibition",
    },
    "interneuron_chandelier": {
        "reservoir_density": 0.10,
        "recurrent_pct": 0.15,
        "has_inhibition": True,
        "description": "Chandelier cell: axo-axonic presynaptic inhibition, spike-blocker",
        "capability": ["axo_axonic", "presynaptic_inhibit", "spike_block", "release_prob"],
        "task_hint_pool": ["presynaptic_inhibit", "spike_block", "release_gate"],
        "lead_task_hint": "presynaptic_inhibition",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_l2_l3",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "I_MEP",
        "biological_reference": "DeFelipe 1999, axo-axonic synapses",
    },
    "interneuron_basket": {
        "reservoir_density": 0.15,
        "recurrent_pct": 0.15,
        "has_inhibition": True,
        "description": "Basket cell: somatic targeting, perisomatic inhibition, gain control",
        "capability": ["somatic_inhibit", "gain_control", "perisomatic", "spike_suppress"],
        "task_hint_pool": ["gain_control", "perisomatic_inhibit", "spike_suppress"],
        "lead_task_hint": "gain_control",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_all_layers",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "I_PVALB_2",
        "biological_reference": "Allen Brain Atlas 2023",
    },
    # ---- 皮层下调制性神经元 (5) ----
    "dopaminergic_snc": {
        "reservoir_density": 0.20,
        "recurrent_pct": 0.25,
        "has_inhibition": False,
        "description": "Substantia nigra dopaminergic: motor reward, basal ganglia gating",
        "capability": ["reward_signal", "motor_gate", "reward_prediction_error", "basal_ganglia"],
        "task_hint_pool": ["reward_signal", "motor_gate", "rpe", "basal_ganglia_mod"],
        "lead_task_hint": "reward_motor_gate",
        "neurotransmitter": "dopamine",
        "brain_region": "midbrain_snc",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Schultz 1997, dopamine RPE",
    },
    "dopaminergic_vta": {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.30,
        "has_inhibition": False,
        "description": "VTA dopaminergic: reward, motivation, learning signal to cortex",
        "capability": ["reward_signal", "motivation", "learning_signal", "cortical_mod"],
        "task_hint_pool": ["reward_signal", "motivation", "learning_gate"],
        "lead_task_hint": "reward_motivation",
        "neurotransmitter": "dopamine",
        "brain_region": "midbrain_vta",
        "species_source": ["mouse", "rat", "human", "drosophila"],
        "allen_class": "",
        "biological_reference": "Schultz 1997, dopamine RPE",
    },
    "serotonergic_raphe": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.35,
        "has_inhibition": False,
        "description": "Raphe serotonergic: mood, sleep, widespread modulation via volume transmission",
        "capability": ["mood_mod", "sleep_gate", "volume_transmission", "widespread_mod"],
        "task_hint_pool": ["mood_modulation", "sleep_gate", "widespread_mod"],
        "lead_task_hint": "mood_modulation",
        "neurotransmitter": "serotonin",
        "brain_region": "brainstem_raphe",
        "species_source": ["mouse", "rat", "human", "drosophila"],
        "allen_class": "",
        "biological_reference": "Bains 2004, volume transmission",
    },
    "noradrenergic_lc": {
        "reservoir_density": 0.20,
        "recurrent_pct": 0.30,
        "has_inhibition": False,
        "description": "Locus coeruleus noradrenergic: arousal, alertness, attention, stress",
        "capability": ["arousal", "alertness", "attention_mod", "stress_response"],
        "task_hint_pool": ["arousal_gate", "alertness", "attention_mod", "stress"],
        "lead_task_hint": "arousal_alertness",
        "neurotransmitter": "noradrenaline",
        "brain_region": "brainstem_lc",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Aston-Jones & Cohen 2005, LC-NA arousal",
    },
    "cholinergic_mt": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.25,
        "has_inhibition": False,
        "description": "Medial septum/Meynert cholinergic: hippocampal theta, attention, memory encoding",
        "capability": ["theta_pacing", "attention_gate", "memory_encode", "hippocampal_mod"],
        "task_hint_pool": ["theta_pacing", "attention_gate", "memory_encode"],
        "lead_task_hint": "attention_memory_mod",
        "neurotransmitter": "acetylcholine",
        "brain_region": "basal_forebrain_mt",
        "species_source": ["mouse", "rat", "human", "drosophila"],
        "allen_class": "",
        "biological_reference": "Buzsaki 2002, cholinergic theta",
    },
    # ---- 视网膜神经元 (4) ----
    "retinal_gc": {
        "reservoir_density": 0.20,
        "recurrent_pct": 0.15,
        "has_inhibition": False,
        "description": "Retinal ganglion cell: visual output, ON/OFF directional tuning",
        "capability": ["visual_output", "direction_tuning", "on_off", "retinotopic"],
        "task_hint_pool": ["visual_output", "direction_tune", "retinotopic_map"],
        "lead_task_hint": "visual_output",
        "neurotransmitter": "glutamate",
        "brain_region": "retina_gc",
        "species_source": ["drosophila", "mouse", "rat", "human", "zebrafish"],
        "allen_class": "",
        "biological_reference": "Bhatt et al 2017, ON/OFF direction",
    },
    "retinal_bipolar": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.20,
        "has_inhibition": False,
        "description": "Retinal bipolar cell: photoreceptor-to-ganglion relay, ON/OFF channels",
        "capability": ["photorelay", "on_off_channel", "linear_filter", "retinal_intermediate"],
        "task_hint_pool": ["on_off_channel", "photorelay", "linear_filter"],
        "lead_task_hint": "retinal_relay",
        "neurotransmitter": "glutamate_or_gaba",
        "brain_region": "retina_bipolar",
        "species_source": ["drosophila", "mouse", "rat", "human", "zebrafish"],
        "allen_class": "",
        "biological_reference": "Retinal circuitry, Baylor 2015",
    },
    "retinal_horizontal": {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.30,
        "has_inhibition": True,
        "description": "Retinal horizontal cell: lateral inhibition, contrast enhancement, center-surround",
        "capability": ["lateral_inhibit", "contrast_enhance", "center_surround", "retinal_lateral"],
        "task_hint_pool": ["contrast_enhance", "lateral_inhibit", "center_surround"],
        "lead_task_hint": "retinal_contrast",
        "neurotransmitter": "gaba_or_glutamate",
        "brain_region": "retina_horizontal",
        "species_source": ["drosophila", "mouse", "rat", "human", "zebrafish"],
        "allen_class": "",
        "biological_reference": "Huang & Wong 2005",
    },
    "retinal_amacrine": {
        "reservoir_density": 0.20,
        "recurrent_pct": 0.35,
        "has_inhibition": True,
        "description": "Retinal amacrine cell: interneuron, motion detection, transient signals",
        "capability": ["motion_detect", "transient_signal", "retinal_interneuron", "feedback"],
        "task_hint_pool": ["motion_detect", "transient_signal", "feedback_inhibit"],
        "lead_task_hint": "motion_detection",
        "neurotransmitter": "gaba_or_glutamate",
        "brain_region": "retina_amacrine",
        "species_source": ["drosophila", "mouse", "rat", "human", "zebrafish"],
        "allen_class": "",
        "biological_reference": "Retinal motion detection, Calkins 2010",
    },
    # ---- 运动/脊髓 (2) ----
    "spinal_motor_alpha": {
        "reservoir_density": 0.10,
        "recurrent_pct": 0.10,
        "has_inhibition": True,
        "description": "Alpha motor neuron: somatic motor output, muscle fiber activation",
        "capability": ["motor_output", "muscle_activate", "alpha_motoneuron", "reflex_arc"],
        "task_hint_pool": ["motor_output", "muscle_activate", "reflex_arc"],
        "lead_task_hint": "motor_output",
        "neurotransmitter": "glutamate_or_acetylcholine",
        "brain_region": "spinal_cord_alpha",
        "species_source": ["drosophila", "mouse", "rat", "human", "zebrafish"],
        "allen_class": "",
        "biological_reference": "Alpha motor neuron, Sherrington 1925",
    },
    "spinal_motor_gamma": {
        "reservoir_density": 0.10,
        "recurrent_pct": 0.10,
        "has_inhibition": True,
        "description": "Gamma motor neuron: muscle spindle feedback, proprioception",
        "capability": ["spindle_feedback", "proprioception", "gamma_motoneuron", "muscle_tone"],
        "task_hint_pool": ["spindle_feedback", "proprioception", "muscle_tone"],
        "lead_task_hint": "proprioception",
        "neurotransmitter": "glutamate_or_acetylcholine",
        "brain_region": "spinal_cord_gamma",
        "species_source": ["drosophila", "mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Gamma motor neuron, Matthews 1966",
    },
    # ---- 小脑 (3) ----
    "cerebellar_purkinje": {
        "reservoir_density": 0.15,
        "recurrent_pct": 0.15,
        "has_inhibition": True,
        "description": "Purkinje cell: cerebellar output, motor learning, error correction",
        "capability": ["motor_learn", "error_correction", "cerebellar_output", "precise_timing"],
        "task_hint_pool": ["motor_learn", "error_correct", "precise_timing"],
        "lead_task_hint": "motor_learning",
        "neurotransmitter": "gaba",
        "brain_region": "cerebellum_purkinje",
        "species_source": ["drosophila", "mouse", "rat", "human", "zebrafish"],
        "allen_class": "",
        "biological_reference": "Albus 1971, cerebellar motor learning",
    },
    "cerebellar_granule": {
        "reservoir_density": 0.60,
        "recurrent_pct": 0.10,
        "has_inhibition": False,
        "description": "Cerebellar granule cell: input expansion, mossy fiber processing, densest neuron type",
        "capability": ["input_expand", "mossy_fiber_process", "combinatorial_code", "high_density"],
        "task_hint_pool": ["input_expand", "combinatorial_code", "mossy_fiber"],
        "lead_task_hint": "input_expansion",
        "neurotransmitter": "glutamate",
        "brain_region": "cerebellum_granule",
        "species_source": ["drosophila", "mouse", "rat", "human", "zebrafish"],
        "allen_class": "",
        "biological_reference": "Cerebellar granule, high density",
    },
    "cerebellar_stellate": {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.30,
        "has_inhibition": True,
        "description": "Cerebellar stellate cell: lateral inhibition between Purkinje cells, parallel fiber",
        "capability": ["lateral_inhibit", "parallel_fiber", "cerebellar_interneuron", "coordination"],
        "task_hint_pool": ["lateral_inhibit", "parallel_fiber", "coordination"],
        "lead_task_hint": "cerebellar_coordination",
        "neurotransmitter": "gaba",
        "brain_region": "cerebellum_stellate",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Cerebellar stellate, inhibitory interneuron",
    },
    # ---- 边缘系统/高级 (4) ----
    "striatal_msn": {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.20,
        "has_inhibition": False,
        "description": "Medium spiny neuron: striatal output, dopamine-modulated action selection",
        "capability": ["action_select", "dopamine_mod", "basal_ganglia_output", "habit_form"],
        "task_hint_pool": ["action_select", "basal_ganglia_out", "habit_form"],
        "lead_task_hint": "action_selection",
        "neurotransmitter": "gaba",
        "brain_region": "striatum_msn",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Striatal MSN, dopamine-gated",
    },
    "thalamic_relay": {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.20,
        "has_inhibition": False,
        "description": "Thalamic relay cell: sensory gateway, cortex-thalamus loop, sleep-wake gate",
        "capability": ["sensory_gate", "cortex_thalamus_loop", "sleep_wake_gate", "thalamic_relay"],
        "task_hint_pool": ["sensory_gate", "thalamus_loop", "sleep_wake_gate"],
        "lead_task_hint": "sensory_gate",
        "neurotransmitter": "glutamate",
        "brain_region": "thalamus_relay",
        "species_source": ["drosophila", "mouse", "rat", "human", "zebrafish"],
        "allen_class": "",
        "biological_reference": "Thalamic relay, Steriade 2001",
    },
    "thalamic_reticular": {
        "reservoir_density": 0.20,
        "recurrent_pct": 0.25,
        "has_inhibition": True,
        "description": "Thalamic reticular nucleus: gating inhibition, attention filter, sleep spindles",
        "capability": ["gate_inhibit", "attention_filter", "sleep_spindle", "thalamic_mod"],
        "task_hint_pool": ["gate_inhibit", "attention_filter", "sleep_spindle"],
        "lead_task_hint": "thalamic_gate",
        "neurotransmitter": "gaba",
        "brain_region": "thalamus_reticular",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Thalamic reticular, sleep spindles",
    },
    "hippocampal_ca1": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.35,
        "has_inhibition": False,
        "description": "Hippocampal CA1: memory output, spatial memory, pattern completion",
        "capability": ["memory_output", "pattern_complete", "spatial_memory", "hippocampal_ca1"],
        "task_hint_pool": ["memory_output", "pattern_complete", "spatial_memory"],
        "lead_task_hint": "memory_output",
        "neurotransmitter": "glutamate",
        "brain_region": "hippocampus_ca1",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Hippocampal CA1, Marr 1971",
    },
    "hippocampal_ca3": {
        "reservoir_density": 0.40,
        "recurrent_pct": 0.50,
        "has_inhibition": False,
        "description": "Hippocampal CA3: recurrent mossy fiber, auto-associative memory, pattern completion",
        "capability": ["auto_associative", "pattern_complete", "recurrent_mossy", "hippocampal_ca3"],
        "task_hint_pool": ["auto_associative", "pattern_complete", "recurrent_mossy"],
        "lead_task_hint": "auto_associative_memory",
        "neurotransmitter": "glutamate",
        "brain_region": "hippocampus_ca3",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "CA3 auto-associative, Marr 1971",
    },
    "hippocampal_granule": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.20,
        "has_inhibition": True,
        "description": "Dentate gyrus granule: input layer, pattern separation, pattern discrimination",
        "capability": ["pattern_separate", "input_expand", "dentate_granule", "discriminate"],
        "task_hint_pool": ["pattern_separate", "input_expand", "discriminate"],
        "lead_task_hint": "pattern_separation",
        "neurotransmitter": "glutamate",
        "brain_region": "hippocampus_dg",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Dentate granule, pattern separation",
    },
    # ---- 特殊功能 (2) ----
    "grid_cell": {
        "reservoir_density": 0.30,
        "recurrent_pct": 0.35,
        "has_inhibition": False,
        "description": "Grid cell: spatial navigation, hexagonal firing pattern, place code",
        "capability": ["spatial_map", "grid_code", "navigation", "path_integration"],
        "task_hint_pool": ["spatial_map", "grid_code", "path_integration"],
        "lead_task_hint": "spatial_navigation",
        "neurotransmitter": "glutamate",
        "brain_region": "entorhinal_l2_l3",
        "species_source": ["mouse", "rat"],
        "allen_class": "E_EXTPAC1",
        "biological_reference": "Haft et al 2005, grid cells",
    },
    "orexin_neuron": {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.30,
        "has_inhibition": False,
        "description": "Orexin (hypocretin) neuron: arousal, sleep-wake stability, energy balance",
        "capability": ["arousal_stability", "sleep_wake_gate", "energy_balance", "orexin_mod"],
        "task_hint_pool": ["arousal_stability", "sleep_wake_gate", "energy_balance"],
        "lead_task_hint": "arousal_stability",
        "neurotransmitter": "orexin_or_acetylcholine",
        "brain_region": "hypothalamus_orexin",
        "species_source": ["mouse", "rat", "human"],
        "allen_class": "",
        "biological_reference": "Sakurai 1998, orexin discovery",
    },

    # ==================== Phase 5 大规模扩展 (2026-09-22) ====================
    # +60 神经元类型（皮层锥体补充 8 / 中间神经元补充 8 / 调制系统补充 8 /
    #   视觉补充 8 / 脊髓脑干 8 / 皮层下边缘 8 / 丘脑 6 / 特殊感觉胶质 6）
    # 依据：Allen 2023 小鼠全脑图谱 + Kozorowski-Coburn 2020 + 跨物种比较神经科学
    "pyramidal_l23_cx1": {
        "reservoir_density": 0.35, "recurrent_pct": 0.18, "has_inhibition": False,
        "description": "Prefrontal L2/3 pyramidal (CX1 cortex): executive control, decision gating",
        "capability": ['executive_control', 'decision_gating', 'top_down_bias', 'prefrontal'],
        "task_hint_pool": ['executive_control', 'decision_gating', 'top_down_bias'],
        "lead_task_hint": "executive_control",
        "neurotransmitter": "glutamate",
        "brain_region": "prefrontal_cortex_cx1",
        "species_source": ['mouse', 'rat', 'human', 'macaque'],
        "allen_class": "E_PVAL1",
        "biological_reference": "Markesan et al 2018, mouse L2/3 atlas",
    },
    "pyramidal_l23_cx5": {
        "reservoir_density": 0.38, "recurrent_pct": 0.2, "has_inhibition": False,
        "description": "Motor L2/3 pyramidal (CX5 cortex): motor planning, premotor",
        "capability": ['motor_planning', 'premotor', 'kinematics', 'movement_sequence'],
        "task_hint_pool": ['motor_planning', 'premotor', 'kinematics'],
        "lead_task_hint": "motor_planning",
        "neurotransmitter": "glutamate",
        "brain_region": "motor_cortex_cx5",
        "species_source": ['mouse', 'rat', 'human', 'macaque'],
        "allen_class": "E_PVAL1",
        "biological_reference": "Markesan et al 2018, CX5 atlas",
    },
    "pyramidal_l4b": {
        "reservoir_density": 0.42, "recurrent_pct": 0.22, "has_inhibition": True,
        "description": "V1 L4b pyramidal: on-center orientation selective, visual input hub",
        "capability": ['orientation_selective', 'on_center', 'visual_hub', 'edge_detection'],
        "task_hint_pool": ['orientation_selective', 'on_center', 'visual_hub'],
        "lead_task_hint": "edge_detection",
        "neurotransmitter": "glutamate",
        "brain_region": "primary_visual_cortex_l4b",
        "species_source": ['mouse', 'cat', 'monkey'],
        "allen_class": "E_PVAL1",
        "biological_reference": "Hubel & Wiesel 1968, Hubel-Wiesel model",
    },
    "pyramidal_l4c": {
        "reservoir_density": 0.4, "recurrent_pct": 0.22, "has_inhibition": True,
        "description": "V1 L4c pyramidal: columnar visual processing",
        "capability": ['columnar_processing', 'visual_feature', 'contrast_detect'],
        "task_hint_pool": ['columnar_processing', 'visual_feature', 'contrast_detect'],
        "lead_task_hint": "visual_feature",
        "neurotransmitter": "glutamate",
        "brain_region": "primary_visual_cortex_l4c",
        "species_source": ['mouse', 'cat', 'monkey'],
        "allen_class": "E_PVAL1",
        "biological_reference": "Hubel & Wiesel 1962",
    },
    "pyramidal_l5bt": {
        "reservoir_density": 0.32, "recurrent_pct": 0.16, "has_inhibition": True,
        "description": "L5 basal-tuft pyramidal: corticothalamic/corticofugal feedback (long-range)",
        "capability": ['corticothalamic', 'feedback_to_thalamus', 'long_range_projection', 'broadcast'],
        "task_hint_pool": ['corticothalamic', 'feedback_to_thalamus', 'broadcast'],
        "lead_task_hint": "feedback_to_thalamus",
        "neurotransmitter": "glutamate",
        "brain_region": "cortex_l5b",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "E_PVAL1",
        "biological_reference": "DeFelipe 2011, basal-tuft cells",
    },
    "pyramidal_l6rt": {
        "reservoir_density": 0.28, "recurrent_pct": 0.14, "has_inhibition": True,
        "description": "L6 reticulo-thalamic: feedback control of thalamic relay (gain control)",
        "capability": ['thalamic_gain_control', 'top_down', 'feedback', 'attention_bias'],
        "task_hint_pool": ['thalamic_gain_control', 'top_down', 'feedback'],
        "lead_task_hint": "thalamic_gain_control",
        "neurotransmitter": "glutamate",
        "brain_region": "cortex_l6rt",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "E_PVAL1",
        "biological_reference": "Sikorski et al 2018",
    },
    "pyramidal_l7": {
        "reservoir_density": 0.3, "recurrent_pct": 0.15, "has_inhibition": True,
        "description": "Temporal cortex L7 pyramidal: multimodal integration, associative memory",
        "capability": ['multimodal_integration', 'associative_memory', 'temporal_object'],
        "task_hint_pool": ['multimodal_integration', 'associative_memory'],
        "lead_task_hint": "associative_memory",
        "neurotransmitter": "glutamate",
        "brain_region": "temporal_cortex_l7",
        "species_source": ['mouse', 'monkey', 'human'],
        "allen_class": "E_PVAL1",
        "biological_reference": "Rolls 1999, object cells",
    },
    "pyramidal_mayeret": {
        "reservoir_density": 0.4, "recurrent_pct": 0.3, "has_inhibition": False,
        "description": "Mayeret cell: vestibular output, cerebellovestibular circuitry",
        "capability": ['vestibular_output', 'posture', 'eye_head_reflex', 'self_stabilization'],
        "task_hint_pool": ['vestibular_output', 'posture', 'eye_head_reflex'],
        "lead_task_hint": "posture",
        "neurotransmitter": "glutamate",
        "brain_region": "vestibular_lobe_cerebellum",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Mayer 1907, Mayeret cells",
    },
    "interneuron_calbindin": {
        "reservoir_density": 0.6, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "Cerebellar stellate (Calbindin+): GABAergic feed-forward inhibition",
        "capability": ['feed_forward_inhib', 'temporal_precision', 'cerebellar_refinement'],
        "task_hint_pool": ['feed_forward_inhib', 'temporal_precision'],
        "lead_task_hint": "temporal_precision",
        "neurotransmitter": "gaba",
        "brain_region": "cerebellar_molecular_layer",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "I_CAB2",
        "biological_reference": "Rasmussen et al 2009",
    },
    "interneuron_lamp": {
        "reservoir_density": 0.55, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "Cerebellar Lugaro/LAMP+ large basket cell: strong lateral inhibition of Purkinje",
        "capability": ['strong_lateral_inhib', 'purkinje_shaping', 'cerebellar_refinement'],
        "task_hint_pool": ['strong_lateral_inhib', 'purkinje_shaping'],
        "lead_task_hint": "purkinje_shaping",
        "neurotransmitter": "gaba",
        "brain_region": "cerebellar_molecular_layer",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "I_LAMP1",
        "biological_reference": "Ramanathan et al 2019",
    },
    "interneuron_nph": {
        "reservoir_density": 0.55, "recurrent_pct": 0.22, "has_inhibition": True,
        "description": "NPV+ H-type interneuron: disinhibition of PV/SST",
        "capability": ['disinhibition', 'gating', 'state_switching'],
        "task_hint_pool": ['disinhibition', 'gating'],
        "lead_task_hint": "disinhibition",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_l23_l5",
        "species_source": ['mouse', 'human'],
        "allen_class": "I_NPF3",
        "biological_reference": "Yi et al 2011",
    },
    "interneuron_npf": {
        "reservoir_density": 0.55, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "NPY/NPV+ F-type interneuron: slow recurrent inhibition",
        "capability": ['slow_recurrent_inhib', 'rhythmicity', 'theta_coupling'],
        "task_hint_pool": ['slow_recurrent_inhib', 'theta_coupling'],
        "lead_task_hint": "theta_coupling",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_hippocampus",
        "species_source": ['mouse', 'human'],
        "allen_class": "I_NPF1",
        "biological_reference": "Yi et al 2011",
    },
    "interneuron_vlac": {
        "reservoir_density": 0.55, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "VLAC+ intermediate: long-range GABAergic cortico-cortical projection",
        "capability": ['long_range_inhib', 'cross_cortical_gating'],
        "task_hint_pool": ['long_range_inhib', 'cross_cortical_gating'],
        "lead_task_hint": "cross_cortical_gating",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_long_range",
        "species_source": ['mouse', 'human'],
        "allen_class": "I_VLAC1",
        "biological_reference": "Sikorski et al 2018",
    },
    "interneuron_sst_dendritic": {
        "reservoir_density": 0.55, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "SOM+ dendritic-type: dendritic shunting inhibition",
        "capability": ['dendritic_shunt', 'feedback_inhib', 'gain_control'],
        "task_hint_pool": ['dendritic_shunt', 'feedback_inhib'],
        "lead_task_hint": "feedback_inhib",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_l2_l5",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "I_SOM1",
        "biological_reference": "Tremblay et al 2016",
    },
    "interneuron_sst_somatic": {
        "reservoir_density": 0.55, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "SOM+ somatic-type: perisomatic fast inhibition",
        "capability": ['perisomatic_fast_inhib', 'somatic_suppression'],
        "task_hint_pool": ['perisomatic_fast_inhib'],
        "lead_task_hint": "perisomatic_fast_inhib",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_l2_l5",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "I_SOM2",
        "biological_reference": "Tremblay et al 2016",
    },
    "interneuron_kcn": {
        "reservoir_density": 0.55, "recurrent_pct": 0.18, "has_inhibition": True,
        "description": "KCN+ (kisspeptin-related) interneuron: slow adaptation inhibitory",
        "capability": ['adaptation_inhib', 'slow_gate', 'homeostatic'],
        "task_hint_pool": ['adaptation_inhib'],
        "lead_task_hint": "adaptation_inhib",
        "neurotransmitter": "gaba",
        "brain_region": "cortex_l5",
        "species_source": ['mouse', 'human'],
        "allen_class": "I_KCN1",
        "biological_reference": "Perez-Fous et al 2019",
    },
    "dopaminergic_a9_snr": {
        "reservoir_density": 0.3, "recurrent_pct": 0.15, "has_inhibition": False,
        "description": "A9 nigrostriatal (SNr/SNr): nigrostriatal dopaminergic, reward/action",
        "capability": ['action_selection', 'nigrostriatal', 'habit', 'long_term_dopamine'],
        "task_hint_pool": ['action_selection', 'nigrostriatal', 'habit'],
        "lead_task_hint": "action_selection",
        "neurotransmitter": "dopamine",
        "brain_region": "substantia_nigra_sn",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "",
        "biological_reference": "Werniger 2007, SNr/SNc",
    },
    "dopaminergic_a11": {
        "reservoir_density": 0.28, "recurrent_pct": 0.15, "has_inhibition": False,
        "description": "A11 SNC ventral: mesocortical dopaminergic, working memory",
        "capability": ['working_memory_dopamine', 'mesocortical', 'executive'],
        "task_hint_pool": ['working_memory_dopamine', 'mesocortical'],
        "lead_task_hint": "working_memory_dopamine",
        "neurotransmitter": "dopamine",
        "brain_region": "substantia_nigra_snc",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "",
        "biological_reference": "Bhatt & Bhatt 1973, SNC",
    },
    "dopaminergic_vmc": {
        "reservoir_density": 0.25, "recurrent_pct": 0.12, "has_inhibition": False,
        "description": "VMC (ventral midbrain cluster): mesolimbic reward, dopamine tone",
        "capability": ['mesolimbic_reward', 'dopamine_tone', 'motivation'],
        "task_hint_pool": ['mesolimbic_reward', 'dopamine_tone'],
        "lead_task_hint": "dopamine_tone",
        "neurotransmitter": "dopamine",
        "brain_region": "ventral_midbrain_vmc",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Almeida & Bhatt 2008, VMC",
    },
    "serotonergic_dorsal": {
        "reservoir_density": 0.25, "recurrent_pct": 0.14, "has_inhibition": False,
        "description": "Dorsal raphe serotonergic: mood, impulsivity, anxiety",
        "capability": ['mood_regulation', 'impulsivity_gate', 'anxiety'],
        "task_hint_pool": ['mood_regulation', 'anxiety'],
        "lead_task_hint": "mood_regulation",
        "neurotransmitter": "serotonin",
        "brain_region": "dorsal_raphe",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "",
        "biological_reference": "Aziz 2008, DRN",
    },
    "serotonergic_ventral": {
        "reservoir_density": 0.22, "recurrent_pct": 0.12, "has_inhibition": False,
        "description": "Ventral raphe serotonergic: reward, anxiety control",
        "capability": ['reward_modulation', 'ventral_serotonin'],
        "task_hint_pool": ['reward_modulation'],
        "lead_task_hint": "reward_modulation",
        "neurotransmitter": "serotonin",
        "brain_region": "ventral_raphe",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Aziz 2008, VRN",
    },
    "serotonergic_median": {
        "reservoir_density": 0.22, "recurrent_pct": 0.14, "has_inhibition": False,
        "description": "Median raphe serotonergic: hippocampal modulation",
        "capability": ['hippocampal_serotonin', 'memory_modulation', 'spatial'],
        "task_hint_pool": ['hippocampal_serotonin', 'memory_modulation'],
        "lead_task_hint": "memory_modulation",
        "neurotransmitter": "serotonin",
        "brain_region": "median_raphe",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Aziz 2008, MRN",
    },
    "cholinergic_horizontal": {
        "reservoir_density": 0.28, "recurrent_pct": 0.15, "has_inhibition": False,
        "description": "Horizontal band of the midbrain cholinergic: thalamic arousal",
        "capability": ['thalamic_arousal', 'awakening', 'cholinergic'],
        "task_hint_pool": ['thalamic_arousal', 'awakening'],
        "lead_task_hint": "thalamic_arousal",
        "neurotransmitter": "acetylcholine",
        "brain_region": "horizontal_band",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Jones 1985, horizontal band",
    },
    "histaminergic_tm": {
        "reservoir_density": 0.22, "recurrent_pct": 0.12, "has_inhibition": False,
        "description": "Tuberomammillary histaminergic: wakefulness, attention",
        "capability": ['wakefulness', 'attention_gate', 'sleep_arousal'],
        "task_hint_pool": ['wakefulness', 'attention_gate'],
        "lead_task_hint": "wakefulness",
        "neurotransmitter": "histamine",
        "brain_region": "tuberomammillary",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Sakurai 1998, TMN",
    },
    "retinal_bipolar_cone": {
        "reservoir_density": 0.55, "recurrent_pct": 0.15, "has_inhibition": False,
        "description": "Cone bipolar: day-vision photoreceptor to amacrine/ganglion",
        "capability": ['cone_signaling', 'day_vision', 'color_code'],
        "task_hint_pool": ['cone_signaling', 'color_code'],
        "lead_task_hint": "color_code",
        "neurotransmitter": "glutamate",
        "brain_region": "retina",
        "species_source": ['mouse', 'rat', 'human', 'fish'],
        "allen_class": "",
        "biological_reference": "Cheng et al 2010",
    },
    "retinal_bipolar_rod": {
        "reservoir_density": 0.5, "recurrent_pct": 0.15, "has_inhibition": False,
        "description": "Rod bipolar: night-vision photoreceptor pathway",
        "capability": ['rod_signaling', 'scotopic_vision', 'low_light'],
        "task_hint_pool": ['rod_signaling', 'scotopic_vision'],
        "lead_task_hint": "scotopic_vision",
        "neurotransmitter": "glutamate",
        "brain_region": "retina",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Cheng et al 2010",
    },
    "retinal_amacrine_acl1": {
        "reservoir_density": 0.55, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "ACL1 amacrine: direction-selective (DCT), motion direction",
        "capability": ['direction_selective', 'motion', 'retinal_processing'],
        "task_hint_pool": ['direction_selective', 'motion'],
        "lead_task_hint": "direction_selective",
        "neurotransmitter": "gaba",
        "brain_region": "retina",
        "species_source": ['mouse', 'fish'],
        "allen_class": "",
        "biological_reference": "Goslin & Cui 2015, DCT",
    },
    "retinal_amacrine_acl2": {
        "reservoir_density": 0.55, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "ACL2 amacrine: starburst-like amacrine, motion onset",
        "capability": ['motion_onset', 'starburst', 'temporal'],
        "task_hint_pool": ['motion_onset'],
        "lead_task_hint": "motion_onset",
        "neurotransmitter": "acetylcholine",
        "brain_region": "retina",
        "species_source": ['mouse', 'fish'],
        "allen_class": "",
        "biological_reference": "Goslin & Cui 2015",
    },
    "retina_midget_gc": {
        "reservoir_density": 0.4, "recurrent_pct": 0.12, "has_inhibition": False,
        "description": "Midget retinal ganglion: high-resolution spatial, color",
        "capability": ['high_res_spatial', 'color_code', 'retinal_gc'],
        "task_hint_pool": ['high_res_spatial', 'color_code'],
        "lead_task_hint": "high_res_spatial",
        "neurotransmitter": "glutamate",
        "brain_region": "retina",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Cheng et al 2010, Midget RGC",
    },
    "retina_parvalbumin_gc": {
        "reservoir_density": 0.42, "recurrent_pct": 0.14, "has_inhibition": False,
        "description": "PV+ retinal ganglion: motion detection, fast visual reflex",
        "capability": ['fast_motion', 'startle', 'retinal_reflex'],
        "task_hint_pool": ['fast_motion', 'startle'],
        "lead_task_hint": "fast_motion",
        "neurotransmitter": "glutamate",
        "brain_region": "retina",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Cheng et al 2010, PV RGC",
    },
    "lateral_geniculate_ventral": {
        "reservoir_density": 0.5, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "VPL (ventral posterolateral): somatosensory relay to S1",
        "capability": ['somatosensory_relay', 'body_map', 'touch'],
        "task_hint_pool": ['somatosensory_relay', 'body_map'],
        "lead_task_hint": "somatosensory_relay",
        "neurotransmitter": "glutamate",
        "brain_region": "thalamic_vpl",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Jones 1985, VPL",
    },
    "lateral_geniculate_dorsal": {
        "reservoir_density": 0.5, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "VPM (ventral posteromedial): facial/trigeminal relay",
        "capability": ['facial_sensation', 'trigeminal_relay', 'pain_touch_face'],
        "task_hint_pool": ['facial_sensation', 'trigeminal_relay'],
        "lead_task_hint": "facial_sensation",
        "neurotransmitter": "glutamate",
        "brain_region": "thalamic_vpm",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Jones 1985, VPM",
    },
    "spinal_interneuron_ih": {
        "reservoir_density": 0.45, "recurrent_pct": 0.3, "has_inhibition": True,
        "description": "Ih interneuron (persistent sodium): post-inhibitory rebound, locomotor",
        "capability": ['rebound_excitatory', 'locomotor_rhythm', 'spinal_rhythm'],
        "task_hint_pool": ['rebound_excitatory', 'locomotor_rhythm'],
        "lead_task_hint": "locomotor_rhythm",
        "neurotransmitter": "gaba_glycine",
        "brain_region": "spinal_cord",
        "species_source": ['mouse', 'rat', 'cat'],
        "allen_class": "",
        "biological_reference": "Kiehn 2016, Ih spinal",
    },
    "spinal_interneuron_icc": {
        "reservoir_density": 0.45, "recurrent_pct": 0.3, "has_inhibition": True,
        "description": "Icc interneuron: commissural, ipsilateral/contralateral switching",
        "capability": ['commissural_inhib', 'limb_switching', 'locomotor'],
        "task_hint_pool": ['commissural_inhib', 'limb_switching'],
        "lead_task_hint": "limb_switching",
        "neurotransmitter": "gaba",
        "brain_region": "spinal_cord",
        "species_source": ['mouse', 'rat', 'cat'],
        "allen_class": "",
        "biological_reference": "Kiehn 2016, Icc",
    },
    "spinal_interneuron_ihp": {
        "reservoir_density": 0.45, "recurrent_pct": 0.28, "has_inhibition": True,
        "description": "Ihp interneuron: half-center, flexion/extension gating",
        "capability": ['half_center', 'flexion_extension', 'locomotor'],
        "task_hint_pool": ['half_center', 'flexion_extension'],
        "lead_task_hint": "flexion_extension",
        "neurotransmitter": "gaba",
        "brain_region": "spinal_cord",
        "species_source": ['mouse', 'rat', 'cat'],
        "allen_class": "",
        "biological_reference": "Kiehn 2016, Ihp",
    },
    "spinal_glycinergic": {
        "reservoir_density": 0.45, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "Glycinergic spinal inhibitory: fast chloride-mediated inhibition",
        "capability": ['fast_inhibition', 'spinal_motor_control'],
        "task_hint_pool": ['fast_inhibition'],
        "lead_task_hint": "fast_inhibition",
        "neurotransmitter": "glycine",
        "brain_region": "spinal_cord",
        "species_source": ['mouse', 'rat', 'cat'],
        "allen_class": "",
        "biological_reference": "Feltner 2016, glycinergic",
    },
    "spinal_nociceptor": {
        "reservoir_density": 0.3, "recurrent_pct": 0.1, "has_inhibition": False,
        "description": "Spinal nociceptive neuron: pain signal processing",
        "capability": ['pain_processing', 'nociceptive_relay', 'thermal_chemical'],
        "task_hint_pool": ['pain_processing'],
        "lead_task_hint": "pain_processing",
        "neurotransmitter": "glutamate_substance_p",
        "brain_region": "spinal_cord_dorsal_horn",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Basbaum & Fields 2018",
    },
    "brainstem_vpm": {
        "reservoir_density": 0.5, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "Ventral posteromedial: somatosensory relay (spinal trigeminal)",
        "capability": ['trigeminal_relay', 'face_touch'],
        "task_hint_pool": ['trigeminal_relay'],
        "lead_task_hint": "face_touch",
        "neurotransmitter": "glutamate",
        "brain_region": "thalamic_vpm",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Jones 1985",
    },
    "red_nucleus": {
        "reservoir_density": 0.5, "recurrent_pct": 0.2, "has_inhibition": False,
        "description": "Red nucleus (interposed): brainstem-motor coordination",
        "capability": ['motor_coordination', 'brainstem_motor', 'red_nucleus'],
        "task_hint_pool": ['motor_coordination', 'brainstem_motor'],
        "lead_task_hint": "motor_coordination",
        "neurotransmitter": "glutamate",
        "brain_region": "red_nucleus",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Schiene 1864, red nucleus",
    },
    "inferior_olive": {
        "reservoir_density": 0.45, "recurrent_pct": 0.35, "has_inhibition": False,
        "description": "Inferior olive: climbing fibers to cerebellum, error learning",
        "capability": ['error_signal', 'climbing_fiber', 'cerebellar_learning'],
        "task_hint_pool": ['error_signal', 'climbing_fiber'],
        "lead_task_hint": "error_signal",
        "neurotransmitter": "glutamate",
        "brain_region": "inferior_olive",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Llinas 1987, climbing fibers",
    },
    "striatum_d1_msn": {
        "reservoir_density": 0.4, "recurrent_pct": 0.18, "has_inhibition": True,
        "description": "D1-type medium spiny: dopamine-driven direct path (Go) in basal ganglia",
        "capability": ['direct_pathway', 'go_circuit', 'dopamine_action'],
        "task_hint_pool": ['direct_pathway', 'go_circuit'],
        "lead_task_hint": "go_circuit",
        "neurotransmitter": "gaba",
        "brain_region": "striatum",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "",
        "biological_reference": "Kravitz 2010, D1 MSN",
    },
    "striatum_d2_msn": {
        "reservoir_density": 0.4, "recurrent_pct": 0.18, "has_inhibition": True,
        "description": "D2-type medium spiny: dopamine-driven indirect path (No-Go) in basal ganglia",
        "capability": ['indirect_pathway', 'no_go_circuit', 'action_inhibition'],
        "task_hint_pool": ['indirect_pathway', 'no_go_circuit'],
        "lead_task_hint": "no_go_circuit",
        "neurotransmitter": "gaba",
        "brain_region": "striatum",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "",
        "biological_reference": "Kravitz 2010, D2 MSN",
    },
    "hippocampal_ca2": {
        "reservoir_density": 0.55, "recurrent_pct": 0.4, "has_inhibition": True,
        "description": "Hippocampal CA2: stress, kindling, aggression-circuit",
        "capability": ['stress_response', 'kindling', 'aggression'],
        "task_hint_pool": ['stress_response', 'kindling'],
        "lead_task_hint": "stress_response",
        "neurotransmitter": "glutamate",
        "brain_region": "hippocampal_ca2",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Wiberg 2003, CA2",
    },
    "hippocampal_ca4": {
        "reservoir_density": 0.6, "recurrent_pct": 0.45, "has_inhibition": True,
        "description": "Hippocampal CA4 (subiculum border): Schaffer collaterals origin",
        "capability": ['schaffer_source', 'hippocampal_relay'],
        "task_hint_pool": ['schaffer_source'],
        "lead_task_hint": "schaffer_source",
        "neurotransmitter": "glutamate",
        "brain_region": "hippocampal_ca4",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Wiberg 2003, CA4",
    },
    "hippocampal_subiculum": {
        "reservoir_density": 0.55, "recurrent_pct": 0.3, "has_inhibition": True,
        "description": "Subiculum: hippocampal output to entorhinal, memory retrieval",
        "capability": ['memory_output', 'hippocampal_retrieval', 'entorhinal_target'],
        "task_hint_pool": ['memory_output', 'hippocampal_retrieval'],
        "lead_task_hint": "hippocampal_retrieval",
        "neurotransmitter": "glutamate",
        "brain_region": "hippocampal_subiculum",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Wiberg 2003, Sub",
    },
    "amygdala_bla": {
        "reservoir_density": 0.5, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "Central amygdala: fear conditioning, anxiety, output circuit",
        "capability": ['fear_output', 'anxiety', 'amygdala_output'],
        "task_hint_pool": ['fear_output', 'anxiety'],
        "lead_task_hint": "fear_output",
        "neurotransmitter": "glutamate_gaba",
        "brain_region": "central_amygdala_bla",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "",
        "biological_reference": "LeDoux 2000, CeA",
    },
    # ------------------------------------------------------------------ #
    # v2.41.0 -- prefrontal metacognition, the region set the coverage matrix
    # was missing entirely (function_coverage.json, v2.37.0).  The sweep that
    # established the gap looked for confidence / uncertainty / metacognit /
    # precision across all 115 units and their descriptions and found nothing,
    # so these six profiles come from the literature rather than from an
    # existing unit.
    #
    # dACC and the insula are the negative-network pair: their activity tracks
    # objective uncertainty and error detection and correlates negatively with
    # reported confidence.  VMPFC and pgACC are the positive pair, associated
    # with confidence and self-performance evaluation.  DLPFC carries the
    # evidence integration the other two read.  FPl is the mapping stage --
    # private sense to public report -- which is the part separable from
    # confidence itself.
    # ------------------------------------------------------------------ #
    "pfc_dorsal_accumbens": {
        "reservoir_density": 0.5, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "Dorsal anterior cingulate: objective uncertainty, error detection, negative network",
        "capability": ['uncertainty_signal', 'error_monitor', 'conflict_detect'],
        "task_hint_pool": ['uncertainty_track', 'error_detect', 'stop_deciding'],
        "lead_task_hint": "uncertainty_signal",
        "neurotransmitter": "glutamate",
        "brain_region": "dorsal_anterior_cingulate",
        "species_source": ['human', 'macaque', 'rat'],
        "allen_class": "",
        "biological_reference": "Fleming & Dolan 2012; Bang & Fleming 2018; Vogels et al. 2015",
    },
    "pfc_insula": {
        "reservoir_density": 0.5, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "Anterior insula: salience and uncertainty, paired with dACC in the negative network",
        "capability": ['salience_mark', 'uncertainty_signal', 'effort_meter'],
        "task_hint_pool": ['salience_detect', 'uncertainty_track'],
        "lead_task_hint": "salience_mark",
        "neurotransmitter": "glutamate",
        "brain_region": "anterior_insula",
        "species_source": ['human', 'macaque', 'rat'],
        "allen_class": "",
        "biological_reference": "White & Engel 2014; Bang & Fleming 2018; Runyon et al. 2017",
    },
    "pfc_dorsolateral": {
        "reservoir_density": 0.55, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "Dorsolateral PFC: evidence integration and task control feeding the confidence estimate",
        "capability": ['evidence_integrate', 'rule_apply', 'confidence_calibration'],
        "task_hint_pool": ['context_rule', 'evidence_integrate', 'confidence_report'],
        "lead_task_hint": "evidence_integrate",
        "neurotransmitter": "glutamate",
        "brain_region": "dorsolateral_prefrontal_cortex",
        "species_source": ['human', 'macaque', 'rat'],
        "allen_class": "",
        "biological_reference": "Fleming & Dolan 2012; Bang et al. 2017; Fernandes et al. 2013",
    },
    "pfc_ventromedial": {
        "reservoir_density": 0.5, "recurrent_pct": 0.3, "has_inhibition": False,
        "description": "Ventromedial PFC: aggregates decision signals into the subjective feeling of confidence",
        "capability": ['confidence_estimate', 'self_monitor', 'value_aggregate'],
        "task_hint_pool": ['confidence_report', 'self_evaluate', 'valence_aggregate'],
        "lead_task_hint": "confidence_estimate",
        "neurotransmitter": "glutamate",
        "brain_region": "ventromedial_prefrontal_cortex",
        "species_source": ['human', 'macaque', 'rat'],
        "allen_class": "",
        "biological_reference": "Bang & Fleming 2018; Fleming et al. 2018; Runyon et al. 2017",
    },
    "pfc_pregenual_accumbens": {
        "reservoir_density": 0.45, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "Pregenual ACC: positive-network confidence and self-performance evaluation",
        "capability": ['confidence_estimate', 'self_evaluate', 'affect_tag'],
        "task_hint_pool": ['confidence_report', 'self_evaluate'],
        "lead_task_hint": "self_evaluate",
        "neurotransmitter": "glutamate",
        "brain_region": "pregenual_anterior_cingulate",
        "species_source": ['human', 'macaque'],
        "allen_class": "",
        "biological_reference": "Bang & Fleming 2018; De Martino et al. 2013; Lebreton et al. 2015",
    },
    "pfc_frontal_pole": {
        "reservoir_density": 0.6, "recurrent_pct": 0.3, "has_inhibition": False,
        "description": "Lateral frontal pole: maps a private sense of confidence onto a public report",
        "capability": ['confidence_map_public', 'context_dependent_report', 'task_switch'],
        "task_hint_pool": ['confidence_report', 'social_calibrate', 'context_rule'],
        "lead_task_hint": "confidence_map_public",
        "neurotransmitter": "glutamate",
        "brain_region": "lateral_frontal_pole",
        "species_source": ['human', 'macaque'],
        "allen_class": "",
        "biological_reference": "Bang & Fleming 2018; De Martino et al. 2013; Fleming et al. 2012",
    },
    "amygdala_lateral": {
        "reservoir_density": 0.5, "recurrent_pct": 0.22, "has_inhibition": True,
        "description": "Lateral amygdala: fear input, sensory encoding, fear conditioning",
        "capability": ['sensory_fear_input', 'fear_encoding', 'sensory_association'],
        "task_hint_pool": ['sensory_fear_input', 'fear_encoding'],
        "lead_task_hint": "fear_encoding",
        "neurotransmitter": "glutamate",
        "brain_region": "lateral_amygdala",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "LeDoux 2000, LA",
    },
    "septum": {
        "reservoir_density": 0.45, "recurrent_pct": 0.3, "has_inhibition": False,
        "description": "Medial septum / diagonal band: hippocampal rhythm, theta generation",
        "capability": ['theta_rhythm', 'hippocampal_pacing', 'septal_inhibition'],
        "task_hint_pool": ['theta_rhythm', 'hippocampal_pacing'],
        "lead_task_hint": "theta_rhythm",
        "neurotransmitter": "gaba_acetylcholine",
        "brain_region": "septum",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Vann & Aggleton 2005",
    },
    "thalamic_lgn": {
        "reservoir_density": 0.55, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "Lateral geniculate nucleus: visual relay retina -> V1",
        "capability": ['visual_relay', 'retina_to_v1', 'thalamic_relay'],
        "task_hint_pool": ['visual_relay', 'retina_to_v1'],
        "lead_task_hint": "visual_relay",
        "neurotransmitter": "glutamate",
        "brain_region": "thalamic_lgn",
        "species_source": ['mouse', 'rat', 'human', 'monkey'],
        "allen_class": "",
        "biological_reference": "Jones 1985, LGN",
    },
    "thalamic_md": {
        "reservoir_density": 0.55, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "Medial geniculate: auditory relay -> auditory cortex",
        "capability": ['auditory_relay', 'auditory_processing', 'sound'],
        "task_hint_pool": ['auditory_relay', 'auditory_processing'],
        "lead_task_hint": "auditory_relay",
        "neurotransmitter": "glutamate",
        "brain_region": "thalamic_mgn",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Jones 1985, MGN",
    },
    "thalamic_va": {
        "reservoir_density": 0.55, "recurrent_pct": 0.22, "has_inhibition": True,
        "description": "Ventral anterior thalamus: motor/basal ganglia relay",
        "capability": ['motor_thalamic', 'basal_ganglia_relay', 'parkinson_circuit'],
        "task_hint_pool": ['motor_thalamic', 'basal_ganglia_relay'],
        "lead_task_hint": "motor_thalamic",
        "neurotransmitter": "glutamate",
        "brain_region": "thalamic_va",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Jones 1985, VA",
    },
    "thalamic_vl": {
        "reservoir_density": 0.55, "recurrent_pct": 0.22, "has_inhibition": True,
        "description": "Ventral lateral thalamus: somatomotor relay, thalamocortical",
        "capability": ['somatomotor_relay', 'thalamocortical'],
        "task_hint_pool": ['somatomotor_relay'],
        "lead_task_hint": "somatomotor_relay",
        "neurotransmitter": "glutamate",
        "brain_region": "thalamic_vl",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Jones 1985, VL",
    },
    "reticular_thalamic": {
        "reservoir_density": 0.55, "recurrent_pct": 0.3, "has_inhibition": True,
        "description": "Reticular nucleus (RTN): GABAergic thalamic gate, sleep spindle",
        "capability": ['thalamic_gate', 'sleep_spindle', 'attention_focus'],
        "task_hint_pool": ['thalamic_gate', 'sleep_spindle'],
        "lead_task_hint": "sleep_spindle",
        "neurotransmitter": "gaba",
        "brain_region": "reticular_thalamic",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Steriade 2001, RTN",
    },
    "subthalamic_nucleus": {
        "reservoir_density": 0.55, "recurrent_pct": 0.25, "has_inhibition": False,
        "description": "Subthalamic nucleus (STN): basal ganglia indirect pathway hub",
        "capability": ['basal_ganglia_indirect', 'action_suppression', 'decision_bias'],
        "task_hint_pool": ['basal_ganglia_indirect', 'action_suppression'],
        "lead_task_hint": "action_suppression",
        "neurotransmitter": "glutamate",
        "brain_region": "subthalamic_nucleus",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Nambu 2002, STN",
    },
    "pineal": {
        "reservoir_density": 0.25, "recurrent_pct": 0.1, "has_inhibition": False,
        "description": "Pinealocyte: melatonin production, circadian rhythm output",
        "capability": ['circadian_output', 'melatonin', 'day_night'],
        "task_hint_pool": ['circadian_output', 'melatonin'],
        "lead_task_hint": "circadian_output",
        "neurotransmitter": "melatonin_norepinephrine",
        "brain_region": "pineal_gland",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Berson 1959, pineal",
    },
    "melanopsin_ganglion": {
        "reservoir_density": 0.4, "recurrent_pct": 0.12, "has_inhibition": False,
        "description": "MELANOPSIN+ intrinsically photosensitive RGC: circadian photic input",
        "capability": ['intrinsic_photoreception', 'circadian_input', 'melanopsin'],
        "task_hint_pool": ['intrinsic_photoreception', 'circadian_input'],
        "lead_task_hint": "circadian_input",
        "neurotransmitter": "glutamate",
        "brain_region": "retina",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Hattar 2002, ipRGC",
    },
    "olfactory_receptor": {
        "reservoir_density": 0.5, "recurrent_pct": 0.1, "has_inhibition": False,
        "description": "Olfactory receptor neuron (ORN): odorant transduction, 1:1 glomerulus map",
        "capability": ['odorant_transduction', 'glomerular_map', 'olfactory_input'],
        "task_hint_pool": ['odorant_transduction', 'glomerular_map'],
        "lead_task_hint": "odorant_transduction",
        "neurotransmitter": "glutamate",
        "brain_region": "olfactory_epithelium",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "",
        "biological_reference": "Axel & Buck 1997, ORN",
    },
    "vestibular_hair": {
        "reservoir_density": 0.5, "recurrent_pct": 0.12, "has_inhibition": False,
        "description": "Vestibular hair cell: linear/angular acceleration transduction",
        "capability": ['acceleration_transduction', 'balance', 'head_orientation'],
        "task_hint_pool": ['acceleration_transduction', 'balance'],
        "lead_task_hint": "balance",
        "neurotransmitter": "glutamate",
        "brain_region": "vestibular_organ",
        "species_source": ['mouse', 'rat', 'human', 'fish'],
        "allen_class": "",
        "biological_reference": "Corey & Hug 1973, hair cells",
    },
    "cochlear_outer_hair": {
        "reservoir_density": 0.5, "recurrent_pct": 0.1, "has_inhibition": False,
        "description": "Cochlear outer hair cell (OHC): mechanical amplifier, frequency sharpening",
        "capability": ['cochlear_amplification', 'frequency_selective', 'auditory_gain'],
        "task_hint_pool": ['cochlear_amplification', 'frequency_selective'],
        "lead_task_hint": "cochlear_amplification",
        "neurotransmitter": "glutamate",
        "brain_region": "cochlea",
        "species_source": ['mouse', 'rat', 'human', 'fish'],
        "allen_class": "",
        "biological_reference": "Corey & Hug 1973, OHC",
    },
    "astrocyte_reactive": {
        "reservoir_density": 0.6, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Reactive astrocyte: glial modulation, neurovascular coupling, gliotransmission",
        "capability": ['neurovascular_coupling', 'gliotransmission', 'glial_modulation'],
        "task_hint_pool": ['neurovascular_coupling', 'gliotransmission'],
        "lead_task_hint": "gliotransmission",
        "neurotransmitter": "glutamate_gaba_serotonin",
        "brain_region": "pan_encephalon",
        "species_source": ['mouse', 'rat', 'human'],
        "allen_class": "G_AST1",
        "biological_reference": "Perea & Araque 2016",
    },
    # ================================================================== #
    # v1.4.1 cross-clade extension -- insect / bird / fish / cephalopod
    # ------------------------------------------------------------------ #
    # 35 neuron populations whose computational role has NO vertebrate-
    # cortex equivalent. Same schema as the 91 above; the 10 cognitive
    # profiles at the top of this dict stay the only neurotransmitter-less
    # entries (asserted by _verify.py).
    # ================================================================== #
    "kenyon_cell":     {
        "reservoir_density": 0.95,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": "Mushroom-body Kenyon cell: sparse high-dimensional odour code, ~5% of the population active per odour",
        "capability": [
            "sparse_encode",
            "pattern_separate",
            "high_dim_expand"
        ],
        "task_hint_pool": [
            "sparse_encode",
            "pattern_separation",
            "high_dim_hash"
        ],
        "lead_task_hint": "sparse_encode",
        "neurotransmitter": "acetylcholine",
        "brain_region": "mushroom_body_calyx",
        "species_source": [
            "drosophila",
            "honeybee",
            "locust"
        ],
        "allen_class": "",
        "biological_reference": "Laurent 2002; Turner et al 2008"
    },
    "mushroom_body_output":     {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.1,
        "has_inhibition": False,
        "description": "Mushroom-body output neuron (MBON): reads the sparse Kenyon-cell code and drives approach/avoid",
        "capability": [
            "readout",
            "valence_readout",
            "behaviour_gate"
        ],
        "task_hint_pool": [
            "readout",
            "valence_readout",
            "approach_avoid"
        ],
        "lead_task_hint": "valence_readout",
        "neurotransmitter": "acetylcholine",
        "brain_region": "mushroom_body_lobes",
        "species_source": [
            "drosophila",
            "honeybee"
        ],
        "allen_class": "",
        "biological_reference": "Aso et al 2014"
    },
    "mushroom_body_dan":     {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": "Mushroom-body dopaminergic neuron (PPL1/PAM): reward/punishment teaching signal onto Kenyon-cell output synapses",
        "capability": [
            "teach",
            "reward_punish",
            "credit_assign"
        ],
        "task_hint_pool": [
            "reward_punish",
            "teach_signal",
            "value_update"
        ],
        "lead_task_hint": "reward_punish",
        "neurotransmitter": "dopamine",
        "brain_region": "mushroom_body_lobes",
        "species_source": [
            "drosophila"
        ],
        "allen_class": "",
        "biological_reference": "Aso et al 2012; Cognigni et al 2018"
    },
    "mushroom_body_apl":     {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.15,
        "has_inhibition": True,
        "description": "APL neuron: one GABAergic cell that feeds back globally onto every Kenyon cell and enforces sparse coding",
        "capability": [
            "global_inhibition",
            "sparse_enforce",
            "gain_control"
        ],
        "task_hint_pool": [
            "global_inhibition",
            "sparsify_code",
            "gain_control"
        ],
        "lead_task_hint": "global_inhibition",
        "neurotransmitter": "gaba",
        "brain_region": "mushroom_body",
        "species_source": [
            "drosophila"
        ],
        "allen_class": "",
        "biological_reference": "Liu & Davis 2009; Papadopoulou et al 2011"
    },
    "antennal_lobe_pn":     {
        "reservoir_density": 0.5,
        "recurrent_pct": 0.1,
        "has_inhibition": False,
        "description": "Antennal-lobe projection neuron: glomerular odour channel relayed to mushroom body and lateral horn",
        "capability": [
            "odour_encode",
            "glomerular_relay",
            "channel_preserve"
        ],
        "task_hint_pool": [
            "odour_encode",
            "channel_relay",
            "stimulus_track"
        ],
        "lead_task_hint": "odour_encode",
        "neurotransmitter": "acetylcholine",
        "brain_region": "antennal_lobe",
        "species_source": [
            "drosophila",
            "honeybee",
            "moth"
        ],
        "allen_class": "",
        "biological_reference": "Wilson & Mainen 2006"
    },
    "antennal_lobe_ln":     {
        "reservoir_density": 0.6,
        "recurrent_pct": 0.35,
        "has_inhibition": True,
        "description": "Antennal-lobe local neuron: cross-glomerular inhibition, gain normalisation and odour-background separation",
        "capability": [
            "normalize",
            "lateral_inhibit",
            "denoise"
        ],
        "task_hint_pool": [
            "normalize",
            "lateral_inhibit",
            "background_separate"
        ],
        "lead_task_hint": "normalize",
        "neurotransmitter": "gaba",
        "brain_region": "antennal_lobe",
        "species_source": [
            "drosophila",
            "honeybee",
            "moth"
        ],
        "allen_class": "",
        "biological_reference": "Olsen & Wilson 2008"
    },
    "central_complex_pb":     {
        "reservoir_density": 0.55,
        "recurrent_pct": 0.4,
        "has_inhibition": False,
        "description": "Protocerebral-bridge columnar neuron: angular head-direction representation, one half of the ring attractor",
        "capability": [
            "heading_represent",
            "angular_code",
            "ring_attractor"
        ],
        "task_hint_pool": [
            "heading_track",
            "angular_code",
            "ring_attractor"
        ],
        "lead_task_hint": "heading_track",
        "neurotransmitter": "acetylcholine",
        "brain_region": "central_complex_pb",
        "species_source": [
            "drosophila",
            "locust",
            "monarch_butterfly"
        ],
        "allen_class": "",
        "biological_reference": "Seelig & Jayaraman 2015"
    },
    "central_complex_eb":     {
        "reservoir_density": 0.55,
        "recurrent_pct": 0.45,
        "has_inhibition": False,
        "description": "Ellipsoid-body neuron: bump attractor that holds the current heading between compass updates",
        "capability": [
            "attractor_hold",
            "heading_memory",
            "bump_dynamics"
        ],
        "task_hint_pool": [
            "attractor_hold",
            "heading_memory",
            "bump_sharpen"
        ],
        "lead_task_hint": "attractor_hold",
        "neurotransmitter": "acetylcholine",
        "brain_region": "central_complex_eb",
        "species_source": [
            "drosophila",
            "locust"
        ],
        "allen_class": "",
        "biological_reference": "Turner-Evans et al 2017"
    },
    "central_complex_fb":     {
        "reservoir_density": 0.5,
        "recurrent_pct": 0.3,
        "has_inhibition": False,
        "description": "Fan-shaped-body neuron: layered goal/steering map converting a heading error into a turn",
        "capability": [
            "steering_map",
            "goal_bearing",
            "error_to_turn"
        ],
        "task_hint_pool": [
            "steering",
            "goal_bearing",
            "heading_correct"
        ],
        "lead_task_hint": "steering",
        "neurotransmitter": "acetylcholine",
        "brain_region": "central_complex_fb",
        "species_source": [
            "drosophila",
            "locust"
        ],
        "allen_class": "",
        "biological_reference": "Green et al 2017; Rayshubskiy et al 2020"
    },
    "central_complex_noduli":     {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.2,
        "has_inhibition": False,
        "description": "Nodulus neuron: forward-speed / self-motion estimate that gates the steering map",
        "capability": [
            "speed_estimate",
            "self_motion",
            "gate"
        ],
        "task_hint_pool": [
            "speed_estimate",
            "self_motion",
            "locomotion_gate"
        ],
        "lead_task_hint": "speed_estimate",
        "neurotransmitter": "acetylcholine",
        "brain_region": "central_complex_noduli",
        "species_source": [
            "drosophila"
        ],
        "allen_class": "",
        "biological_reference": "Rayshubskiy et al 2020"
    },
    "central_complex_ring":     {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.2,
        "has_inhibition": True,
        "description": "Ring neuron (R-neuron): inhibitory input that shapes and rotates the heading bump",
        "capability": [
            "bump_sharpen",
            "inhibit",
            "rotate"
        ],
        "task_hint_pool": [
            "bump_sharpen",
            "lateral_inhibit",
            "heading_rotate"
        ],
        "lead_task_hint": "bump_sharpen",
        "neurotransmitter": "gaba",
        "brain_region": "central_complex",
        "species_source": [
            "drosophila"
        ],
        "allen_class": "",
        "biological_reference": "Hanesch et al 1989; Turner-Evans et al 2017"
    },
    "clock_neuron_slnv":     {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.3,
        "has_inhibition": False,
        "description": "Small ventral lateral neuron (s-LNv): PDF-secreting master pacemaker of the insect circadian clock",
        "capability": [
            "circadian_pace",
            "phase_lock",
            "pdf_secrete"
        ],
        "task_hint_pool": [
            "circadian_pace",
            "phase_lock",
            "entrain"
        ],
        "lead_task_hint": "circadian_pace",
        "neurotransmitter": "pdf_neuropeptide",
        "brain_region": "accessory_medulla",
        "species_source": [
            "drosophila"
        ],
        "allen_class": "",
        "biological_reference": "Helfrich-Forster 2003"
    },
    "clock_neuron_ln":     {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.3,
        "has_inhibition": True,
        "description": "Lateral neuron (LN): clock-network interneuron coupling to and entraining the pacemaker cluster",
        "capability": [
            "clock_couple",
            "phase_integrate",
            "light_entrain"
        ],
        "task_hint_pool": [
            "clock_couple",
            "phase_integrate",
            "entrain"
        ],
        "lead_task_hint": "clock_couple",
        "neurotransmitter": "gaba",
        "brain_region": "accessory_medulla",
        "species_source": [
            "drosophila"
        ],
        "allen_class": "",
        "biological_reference": "Helfrich-Forster 2003; Hastings et al 2018"
    },
    "descending_neuron":     {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.1,
        "has_inhibition": False,
        "description": "Descending neuron: neck-connective output carrying brain steering commands to the ventral nerve cord",
        "capability": [
            "descending_command",
            "steering_output",
            "motor_gate"
        ],
        "task_hint_pool": [
            "descending_command",
            "steering_output",
            "motor_gate"
        ],
        "lead_task_hint": "descending_command",
        "neurotransmitter": "acetylcholine",
        "brain_region": "neck_connective",
        "species_source": [
            "drosophila",
            "locust"
        ],
        "allen_class": "",
        "biological_reference": "Strausfeld 1999; Namiki et al 2018"
    },
    "hvc_neuron":     {
        "reservoir_density": 0.6,
        "recurrent_pct": 0.45,
        "has_inhibition": False,
        "description": "HVC neuron: premotor timing chain that marks each ~10 ms syllable element of the song",
        "capability": [
            "sequence_generate",
            "temporal_chain",
            "motor_timing"
        ],
        "task_hint_pool": [
            "sequence_generate",
            "temporal_chain",
            "motor_timing"
        ],
        "lead_task_hint": "sequence_generate",
        "neurotransmitter": "glutamate",
        "brain_region": "hvc",
        "species_source": [
            "zebra_finch",
            "canary",
            "bengalese_finch"
        ],
        "allen_class": "",
        "biological_reference": "Hahnloser et al 2002; Long & Fee 2008"
    },
    "ra_neuron":     {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.1,
        "has_inhibition": False,
        "description": "Robust nucleus of the arcopallium (RA) neuron: song motor output onto syringeal and respiratory motorneurons",
        "capability": [
            "vocal_motor",
            "respiration_sync",
            "syringeal_control"
        ],
        "task_hint_pool": [
            "vocal_motor",
            "respiration_sync",
            "motor_burst"
        ],
        "lead_task_hint": "vocal_motor",
        "neurotransmitter": "glutamate",
        "brain_region": "ra",
        "species_source": [
            "zebra_finch",
            "canary"
        ],
        "allen_class": "",
        "biological_reference": "Vicario 1991; Sober et al 2008"
    },
    "lman_neuron":     {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.25,
        "has_inhibition": False,
        "description": "LMAN neuron: cortical-like output of the anterior forebrain pathway that injects trial-to-trial motor variation",
        "capability": [
            "variation_inject",
            "explore",
            "motor_bias"
        ],
        "task_hint_pool": [
            "explore_variation",
            "motor_bias",
            "stochastic_probe"
        ],
        "lead_task_hint": "explore_variation",
        "neurotransmitter": "glutamate",
        "brain_region": "lman",
        "species_source": [
            "zebra_finch",
            "bengalese_finch"
        ],
        "allen_class": "",
        "biological_reference": "Mooney 2009; Andalman & Fee 2009"
    },
    "area_x_neuron":     {
        "reservoir_density": 0.5,
        "recurrent_pct": 0.4,
        "has_inhibition": True,
        "description": "Area X neuron: striatal (basal-ganglia) node of the song-learning loop",
        "capability": [
            "action_value",
            "selection",
            "credit_assign"
        ],
        "task_hint_pool": [
            "action_value",
            "selection",
            "credit_assign"
        ],
        "lead_task_hint": "action_value",
        "neurotransmitter": "gaba",
        "brain_region": "area_x",
        "species_source": [
            "zebra_finch",
            "bengalese_finch"
        ],
        "allen_class": "",
        "biological_reference": "Bottjer et al 1984; Farries & Perkel 2002"
    },
    "dlm_neuron":     {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.15,
        "has_inhibition": False,
        "description": "Thalamic nucleus DLM: relay from Area X to LMAN inside the song loop",
        "capability": [
            "thalamic_relay",
            "disinhibit",
            "relay"
        ],
        "task_hint_pool": [
            "thalamic_relay",
            "disinhibit",
            "signal_relay"
        ],
        "lead_task_hint": "thalamic_relay",
        "neurotransmitter": "glutamate",
        "brain_region": "dlm",
        "species_source": [
            "zebra_finch"
        ],
        "allen_class": "",
        "biological_reference": "Okuhata & Saito 1987; Mooney 2009"
    },
    "nif_neuron":     {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.2,
        "has_inhibition": False,
        "description": "Nucleus interface of the nidopallium (NIf): premotor and auditory input to HVC",
        "capability": [
            "premotor_input",
            "auditory_gate",
            "context"
        ],
        "task_hint_pool": [
            "premotor_input",
            "auditory_gate",
            "context_supply"
        ],
        "lead_task_hint": "premotor_input",
        "neurotransmitter": "glutamate",
        "brain_region": "nif",
        "species_source": [
            "zebra_finch"
        ],
        "allen_class": "",
        "biological_reference": "Cardin et al 2005; Lewandowski & Hahnloser 2009"
    },
    "mauthner_cell":     {
        "reservoir_density": 0.2,
        "recurrent_pct": 0.1,
        "has_inhibition": True,
        "description": "Mauthner cell: single giant reticulospinal command neuron that triggers the C-start escape",
        "capability": [
            "escape_trigger",
            "command_neuron",
            "all_or_none"
        ],
        "task_hint_pool": [
            "escape_trigger",
            "command_neuron",
            "fast_command"
        ],
        "lead_task_hint": "escape_trigger",
        "neurotransmitter": "glutamate",
        "brain_region": "hindbrain_mauthner",
        "species_source": [
            "zebrafish",
            "goldfish",
            "lamprey"
        ],
        "allen_class": "",
        "biological_reference": "Zottoli 1977; Korn & Faber 2005"
    },
    "reticulospinal_neuron":     {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.15,
        "has_inhibition": False,
        "description": "Reticulospinal neuron: descending axon pool that recruits contralateral axial muscle",
        "capability": [
            "descending_command",
            "contralateral_recruit",
            "motor_pool"
        ],
        "task_hint_pool": [
            "descending_command",
            "motor_recruit",
            "axial_turn"
        ],
        "lead_task_hint": "descending_command",
        "neurotransmitter": "glutamate",
        "brain_region": "hindbrain_reticular",
        "species_source": [
            "zebrafish",
            "lamprey"
        ],
        "allen_class": "",
        "biological_reference": "Hale et al 2002; Eaton et al 2001"
    },
    "lateral_line_hair_cell":     {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": "Lateral-line hair cell: water-motion detector reporting the pressure wave of an approaching predator",
        "capability": [
            "flow_detect",
            "predator_wave",
            "mechanotransduce"
        ],
        "task_hint_pool": [
            "flow_detect",
            "predator_wave",
            "mechano_encode"
        ],
        "lead_task_hint": "flow_detect",
        "neurotransmitter": "glutamate",
        "brain_region": "lateral_line",
        "species_source": [
            "zebrafish",
            "goldfish",
            "xenopus"
        ],
        "allen_class": "",
        "biological_reference": "Chagnaud & Bass 2013"
    },
    "electroreceptor_ampullary":     {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": "Ampullary electroreceptor: low-frequency passive electroreception of prey bioelectric fields",
        "capability": [
            "passive_electrolocate",
            "weak_field_detect",
            "dc_encode"
        ],
        "task_hint_pool": [
            "passive_electrolocate",
            "weak_field_detect",
            "prey_localize"
        ],
        "lead_task_hint": "passive_electrolocate",
        "neurotransmitter": "glutamate",
        "brain_region": "ampullary_organ",
        "species_source": [
            "shark",
            "ray",
            "catfish",
            "platypus"
        ],
        "allen_class": "",
        "biological_reference": "Kalmijn 1974; Bell & Maler 2005"
    },
    "electroreceptor_tuberous":     {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": "Tuberous electroreceptor: high-frequency active-electrolocation channel reporting EOD amplitude and phase",
        "capability": [
            "active_electrolocate",
            "eod_amplitude",
            "phase_code"
        ],
        "task_hint_pool": [
            "active_electrolocate",
            "eod_amplitude",
            "object_detect"
        ],
        "lead_task_hint": "active_electrolocate",
        "neurotransmitter": "glutamate",
        "brain_region": "tuberous_organ",
        "species_source": [
            "gymnotiform",
            "mormyrid"
        ],
        "allen_class": "",
        "biological_reference": "Heiligenberg 1991; Bell 2001"
    },
    "ells_pyramidal":     {
        "reservoir_density": 0.55,
        "recurrent_pct": 0.35,
        "has_inhibition": False,
        "description": "Electrosensory lateral-line lobe (ELL) pyramidal cell: adaptive filter separating self- from other-generated fields",
        "capability": [
            "reafferent_cancel",
            "adaptive_filter",
            "amplitude_compare"
        ],
        "task_hint_pool": [
            "reafferent_cancel",
            "adaptive_filter",
            "object_detect"
        ],
        "lead_task_hint": "reafferent_cancel",
        "neurotransmitter": "glutamate",
        "brain_region": "ells",
        "species_source": [
            "gymnotiform",
            "mormyrid"
        ],
        "allen_class": "",
        "biological_reference": "Bell 1981; Bell & Maler 2005"
    },
    "electrosensory_inhibitory_interneuron":     {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.25,
        "has_inhibition": True,
        "description": "Electrosensory inhibitory interneuron: local gain control and contrast enhancement inside ELL",
        "capability": [
            "lateral_inhibit",
            "contrast_enhance",
            "gain_control"
        ],
        "task_hint_pool": [
            "lateral_inhibit",
            "contrast_enhance",
            "gain_control"
        ],
        "lead_task_hint": "contrast_enhance",
        "neurotransmitter": "gaba",
        "brain_region": "ells",
        "species_source": [
            "gymnotiform",
            "mormyrid"
        ],
        "allen_class": "",
        "biological_reference": "Berman & Maler 1999"
    },
    "pacemaker_nucleus_neuron":     {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.6,
        "has_inhibition": False,
        "description": "Electric-organ pacemaker neuron: autonomously rhythmic command nucleus that sets the EOD frequency",
        "capability": [
            "pacemaking",
            "rhythm_generate",
            "eod_command"
        ],
        "task_hint_pool": [
            "pacemaking",
            "eod_generate",
            "rhythm_generate"
        ],
        "lead_task_hint": "pacemaking",
        "neurotransmitter": "acetylcholine",
        "brain_region": "pacemaker_nucleus",
        "species_source": [
            "gymnotiform",
            "mormyrid"
        ],
        "allen_class": "",
        "biological_reference": "Bennett 1971; Bell et al 1997"
    },
    "vertical_lobe_large_cell":     {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.3,
        "has_inhibition": False,
        "description": "Vertical-lobe large cell: output neuron whose synapses are persistently facilitated by repeated amacrine firing",
        "capability": [
            "long_term_facilitation",
            "learned_output",
            "command_release"
        ],
        "task_hint_pool": [
            "associative_learn",
            "long_term_facilitation",
            "command_release"
        ],
        "lead_task_hint": "associative_learn",
        "neurotransmitter": "acetylcholine",
        "brain_region": "vertical_lobe",
        "species_source": [
            "octopus",
            "cuttlefish"
        ],
        "allen_class": "",
        "biological_reference": "Young 1964, 1991; Shomrat et al 2008"
    },
    "vertical_lobe_amacrine_cell":     {
        "reservoir_density": 0.5,
        "recurrent_pct": 0.55,
        "has_inhibition": False,
        "description": "Vertical-lobe amacrine cell: a run of about five spikes produces a lasting increase in transmitter release (LTS)",
        "capability": [
            "repetition_detect",
            "lts_express",
            "plasticity_gate"
        ],
        "task_hint_pool": [
            "repetition_detect",
            "lts_express",
            "plasticity_gate"
        ],
        "lead_task_hint": "lts_express",
        "neurotransmitter": "acetylcholine",
        "brain_region": "vertical_lobe",
        "species_source": [
            "octopus",
            "cuttlefish"
        ],
        "allen_class": "",
        "biological_reference": "Shomrat et al 2008; Hochner 2012"
    },
    "vertical_lobe_small_cell":     {
        "reservoir_density": 0.55,
        "recurrent_pct": 0.2,
        "has_inhibition": False,
        "description": "Vertical-lobe small cell: multimodal (visual / tactile / chemotactile) afferent converging on the learning matrix",
        "capability": [
            "multimodal_converge",
            "afferent_encode",
            "feature_bind"
        ],
        "task_hint_pool": [
            "multimodal_converge",
            "feature_bind",
            "afferent_encode"
        ],
        "lead_task_hint": "multimodal_converge",
        "neurotransmitter": "acetylcholine",
        "brain_region": "vertical_lobe",
        "species_source": [
            "octopus",
            "cuttlefish"
        ],
        "allen_class": "",
        "biological_reference": "Young 1991; Shigeno et al 2018"
    },
    "superior_frontal_lobe_cell":     {
        "reservoir_density": 0.5,
        "recurrent_pct": 0.35,
        "has_inhibition": False,
        "description": "Superior frontal lobe cell: higher-order associative centre that drives learned motor programs",
        "capability": [
            "higher_associate",
            "motor_plan",
            "context_gate"
        ],
        "task_hint_pool": [
            "higher_associate",
            "motor_plan",
            "context_gate"
        ],
        "lead_task_hint": "higher_associate",
        "neurotransmitter": "acetylcholine",
        "brain_region": "superior_frontal_lobe",
        "species_source": [
            "octopus"
        ],
        "allen_class": "",
        "biological_reference": "Young 1991; Wollesen et al 2015"
    },
    "chromatophore_motor_neuron":     {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": "Chromatophore motor neuron: radial muscle fibres expand pigment sacs to display a skin pattern",
        "capability": [
            "pattern_display",
            "muscle_drive",
            "camouflage"
        ],
        "task_hint_pool": [
            "pattern_display",
            "camouflage",
            "body_signalling"
        ],
        "lead_task_hint": "camouflage",
        "neurotransmitter": "glutamate",
        "brain_region": "chromatophore",
        "species_source": [
            "octopus",
            "cuttlefish",
            "squid"
        ],
        "allen_class": "",
        "biological_reference": "Hanlon & Messenger 1996; Messenger 2001"
    },
    "arm_motor_neuron":     {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.2,
        "has_inhibition": False,
        "description": "Arm motor neuron: motorneuron inside the arm nerve cord driving the intrinsic arm musculature",
        "capability": [
            "arm_control",
            "distributed_motor",
            "reach"
        ],
        "task_hint_pool": [
            "arm_control",
            "distributed_motor",
            "reach"
        ],
        "lead_task_hint": "arm_control",
        "neurotransmitter": "acetylcholine",
        "brain_region": "arm_nerve_cord",
        "species_source": [
            "octopus",
            "squid"
        ],
        "allen_class": "",
        "biological_reference": "Young 1965; Sumbre et al 2001"
    },
    "arm_sensory_afferent":     {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.1,
        "has_inhibition": False,
        "description": "Arm sensory afferent: mechano- and chemoreceptor afferent from the suckers and skin of the arm",
        "capability": [
            "proprioception",
            "tactile_sense",
            "chemo_sense"
        ],
        "task_hint_pool": [
            "proprioceptive_loop",
            "tactile_sense",
            "chemo_sense"
        ],
        "lead_task_hint": "proprioceptive_loop",
        "neurotransmitter": "glutamate",
        "brain_region": "arm_nerve_cord",
        "species_source": [
            "octopus",
            "squid"
        ],
        "allen_class": "",
        "biological_reference": "Graziadei 1962; Sumbre et al 2001"
    },
    'leech_cpg_interneuron': {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.45,
        "has_inhibition": True,
        "description": 'Leech swim CPG interneuron: half-centre oscillator element, reciprocal inhibition plus adaptation, non-rhythmic on its own',
        "capability": [
            'rhythm_generate',
            'oscillate',
            'swim_control',
        ],
        "task_hint_pool": [
            'rhythm_generate',
            'oscillate',
            'swim_control',
        ],
        "lead_task_hint": 'rhythm_generate',
        "neurotransmitter": 'glutamate',
        "brain_region": 'leech_segmental_ganglion',
        "species_source": [
            'leech',
            'medicinal_leech',
        ],
        "allen_class": "",
        "biological_reference": 'Friesen 1989; Marder & Calabrese 1996; Kristan et al 2005'
    },
    'leech_motor_neuron': {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.15,
        "has_inhibition": False,
        "description": 'Leech body-wall motor neuron: drives longitudinal muscle in the swim rhythm',
        "capability": [
            'swim_control',
            'motor_drive',
        ],
        "task_hint_pool": [
            'swim_control',
            'motor_drive',
        ],
        "lead_task_hint": 'swim_control',
        "neurotransmitter": 'acetylcholine',
        "brain_region": 'leech_segmental_ganglion',
        "species_source": [
            'leech',
            'medicinal_leech',
        ],
        "allen_class": "",
        "biological_reference": 'Kristan et al 2005'
    },
    'leech_mechanosensory_neuron': {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.08,
        "has_inhibition": False,
        "description": 'Leech mechanosensory (T) cell: touch-sensitive afferent that can start the swim',
        "capability": [
            'touch_sense',
            'trigger_rhythm',
        ],
        "task_hint_pool": [
            'touch_sense',
            'trigger_rhythm',
        ],
        "lead_task_hint": 'touch_sense',
        "neurotransmitter": 'glutamate',
        "brain_region": 'leech_segmental_ganglion',
        "species_source": [
            'leech',
            'medicinal_leech',
        ],
        "allen_class": "",
        "biological_reference": 'Nicholls & Baylor 1968'
    },
    'ascidian_larval_motor_neuron': {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.2,
        "has_inhibition": False,
        "description": 'Ascidian larval motor neuron: one of the small pool driving the tail muscle in the escape swim',
        "capability": [
            'escape_swim',
            'motor_drive',
            'rhythm_generate',
        ],
        "task_hint_pool": [
            'escape_swim',
            'motor_drive',
        ],
        "lead_task_hint": 'escape_swim',
        "neurotransmitter": 'acetylcholine',
        "brain_region": 'ascidian_larval_cns',
        "species_source": [
            'ciona',
            'ascidian',
        ],
        "allen_class": "",
        "biological_reference": 'Bone 1958; Nishino et al 2011; Ryan et al 2016'
    },
    'ascidian_photoreceptor': {
        "reservoir_density": 0.2,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": 'Ascidian larval ocellus photoreceptor: the onset of a shadow triggers the escape swim',
        "capability": [
            'photoreception',
            'shadow_detect',
        ],
        "task_hint_pool": [
            'photoreception',
            'shadow_detect',
        ],
        "lead_task_hint": 'photoreception',
        "neurotransmitter": 'glutamate',
        "brain_region": 'ascidian_larval_cns',
        "species_source": [
            'ciona',
            'ascidian',
        ],
        "allen_class": "",
        "biological_reference": 'Ryan et al 2016'
    },
    'aplysia_sensory_neuron': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.1,
        "has_inhibition": False,
        "description": 'Aplysia siphon/gill mechanosensory neuron: excites the motor neuron directly and is the locus of both habituation and sensitisation',
        "capability": [
            'touch_sense',
            'presynaptic_memory',
        ],
        "task_hint_pool": [
            'touch_sense',
            'presynaptic_memory',
        ],
        "lead_task_hint": 'touch_sense',
        "neurotransmitter": 'glutamate',
        "brain_region": 'aplysia_abdominal_ganglion',
        "species_source": [
            'aplysia',
            'sea_hare',
        ],
        "allen_class": "",
        "biological_reference": 'Castellucci et al 1970; Castellucci & Kandel 1976'
    },
    'aplysia_motor_neuron': {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.15,
        "has_inhibition": False,
        "description": 'Aplysia gill/buccal motor neuron (e.g. L7): the reflex and feeding output stage',
        "capability": [
            'gill_retract',
            'feeding_rhythm',
            'motor_drive',
        ],
        "task_hint_pool": [
            'gill_retract',
            'feeding_rhythm',
            'motor_drive',
        ],
        "lead_task_hint": 'gill_retract',
        "neurotransmitter": 'acetylcholine',
        "brain_region": 'aplysia_abdominal_ganglion',
        "species_source": [
            'aplysia',
            'sea_hare',
        ],
        "allen_class": "",
        "biological_reference": 'Kupfermann 1974; Kandel 1976'
    },
    'aplysia_facilitating_interneuron': {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.25,
        "has_inhibition": False,
        "description": 'Aplysia serotonergic facilitating interneuron (e.g. L29): raises release probability presynaptically, the substrate of sensitisation',
        "capability": [
            'sensitization',
            'gain_modulation',
            'presynaptic_memory',
        ],
        "task_hint_pool": [
            'sensitization',
            'gain_modulation',
        ],
        "lead_task_hint": 'sensitization',
        "neurotransmitter": 'serotonin',
        "brain_region": 'aplysia_abdominal_ganglion',
        "species_source": [
            'aplysia',
            'sea_hare',
        ],
        "allen_class": "",
        "biological_reference": 'Castellucci & Kandel 1976; Kandel 2001'
    },
    'buccal_cpg_neuron': {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.4,
        "has_inhibition": True,
        "description": 'Molluscan buccal ganglion CPG neuron: produces the ingestive phase sequence',
        "capability": [
            'feeding_rhythm',
            'rhythm_generate',
            'phase_sequence',
        ],
        "task_hint_pool": [
            'feeding_rhythm',
            'rhythm_generate',
            'phase_sequence',
        ],
        "lead_task_hint": 'feeding_rhythm',
        "neurotransmitter": 'acetylcholine',
        "brain_region": 'buccal_ganglion',
        "species_source": [
            'aplysia',
            'lobster',
        ],
        "allen_class": "",
        "biological_reference": 'Kupfermann 1974; Cropper et al 1996'
    },
    'trigeminal_infrared_afferent': {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": 'Pit-organ trigeminal afferent: reports thermal radiation from a warm target',
        "capability": [
            'infrared_localize',
            'thermal_imaging',
        ],
        "task_hint_pool": [
            'infrared_localize',
            'thermal_imaging',
        ],
        "lead_task_hint": 'infrared_localize',
        "neurotransmitter": 'glutamate',
        "brain_region": 'trigeminal_ganglion',
        "species_source": [
            'python',
            'rattlesnake',
            'pit_viper',
        ],
        "allen_class": "",
        "biological_reference": 'Bullock & Cowles 1952; Gracheva et al 2010'
    },
    'infrared_tectal_neuron': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.15,
        "has_inhibition": True,
        "description": 'Infrared tectal map neuron: a thermal map of the surrounding field registered onto the visual one',
        "capability": [
            'thermal_imaging',
            'topographic_map',
        ],
        "task_hint_pool": [
            'thermal_imaging',
            'topographic_map',
        ],
        "lead_task_hint": 'thermal_imaging',
        "neurotransmitter": 'gaba',
        "brain_region": 'optic_tectum',
        "species_source": [
            'python',
            'rattlesnake',
            'pit_viper',
        ],
        "allen_class": "",
        "biological_reference": 'Hartline et al 2011; Newman & Hartline 1982'
    },
    'optic_tectum_multimodal': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.3,
        "has_inhibition": True,
        "description": 'Multimodal tectal neuron: visual and infrared maps converge on the same cell',
        "capability": [
            'cross_modal_bind',
            'thermal_target',
            'strike',
        ],
        "task_hint_pool": [
            'cross_modal_bind',
            'thermal_target',
            'strike',
        ],
        "lead_task_hint": 'cross_modal_bind',
        "neurotransmitter": 'glutamate',
        "brain_region": 'optic_tectum',
        "species_source": [
            'pit_viper',
            'rattlesnake',
        ],
        "allen_class": "",
        "biological_reference": 'Newman & Hartline 1982; Hartline et al 2011'
    },
    'tectal_prey_detector': {
        "reservoir_density": 0.45,
        "recurrent_pct": 0.1,
        "has_inhibition": True,
        "description": 'Frog tectal T5-type prey detector: a small moving object releases the capture programme',
        "capability": [
            'prey_capture',
            'visual_detect',
        ],
        "task_hint_pool": [
            'prey_capture',
            'visual_detect',
        ],
        "lead_task_hint": 'prey_capture',
        "neurotransmitter": 'glutamate',
        "brain_region": 'optic_tectum',
        "species_source": [
            'frog',
            'toad',
        ],
        "allen_class": "",
        "biological_reference": 'Lettvin et al 1959; Ingle 1968; Ewert 1984'
    },
    'tongue_motor_neuron': {
        "reservoir_density": 0.3,
        "recurrent_pct": 0.1,
        "has_inhibition": False,
        "description": 'Frog tongue motor neuron: ballistic projection of the tongue',
        "capability": [
            'tongue_strike',
            'ballistic',
        ],
        "task_hint_pool": [
            'tongue_strike',
            'ballistic',
        ],
        "lead_task_hint": 'tongue_strike',
        "neurotransmitter": 'acetylcholine',
        "brain_region": 'hypoglossal_nucleus',
        "species_source": [
            'frog',
            'toad',
        ],
        "allen_class": "",
        "biological_reference": 'Ingle 1968; Ewert 1984'
    },
    'climbing_fibre': {
        "reservoir_density": 0.2,
        "recurrent_pct": 0.05,
        "has_inhibition": False,
        "description": 'Climbing fibre: the olivary axon that delivers the error (complex spike) to a Purkinje cell',
        "capability": [
            'error_teaching',
            'timing_signal',
        ],
        "task_hint_pool": [
            'error_teaching',
            'timing_signal',
        ],
        "lead_task_hint": 'error_teaching',
        "neurotransmitter": 'glutamate',
        "brain_region": 'inferior_olive',
        "species_source": [
            'mouse',
            'rat',
            'human',
            'electric_fish',
        ],
        "allen_class": "",
        "biological_reference": 'Ito & Kano 1982; De Zeeuw et al 2011'
    },
    'cerebellar_go_cell': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.35,
        "has_inhibition": True,
        "description": 'Cerebellar Golgi cell: feedforward inhibition onto granule cells that confines activity to a microzone',
        "capability": [
            'gain_control',
            'microzone_isolate',
        ],
        "task_hint_pool": [
            'gain_control',
            'microzone_isolate',
        ],
        "lead_task_hint": 'gain_control',
        "neurotransmitter": 'gaba',
        "brain_region": 'cerebellar_cortex',
        "species_source": [
            'mouse',
            'rat',
            'human',
        ],
        "allen_class": "",
        "biological_reference": 'Marr 1969; Albus 1971'
    },
    'vestibular_nucleus_neuron': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.3,
        "has_inhibition": True,
        "description": 'Vestibular nucleus neuron: three-neuron-arc relay from hair cells to the extraocular motoneurons',
        "capability": [
            'gaze_stabilize',
            'reflex',
            'adaptation',
        ],
        "task_hint_pool": [
            'gaze_stabilize',
            'reflex',
            'adaptation',
        ],
        "lead_task_hint": 'gaze_stabilize',
        "neurotransmitter": 'glutamate',
        "brain_region": 'vestibular_nucleus',
        "species_source": [
            'rabbit',
            'mouse',
            'monkey',
        ],
        "allen_class": "",
        "biological_reference": 'Ito 1982; Lisberger 1988; Boyden et al 2004'
    },
    'pre_botzinger_neuron': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.35,
        "has_inhibition": True,
        "description": 'Pre-Botzinger complex neuron: kernel of the respiratory rhythm, bistable plateau potentials plus inhibition',
        "capability": [
            'breathing_rhythm',
            'rhythm_generate',
            'chemo_response',
        ],
        "task_hint_pool": [
            'breathing_rhythm',
            'rhythm_generate',
        ],
        "lead_task_hint": 'breathing_rhythm',
        "neurotransmitter": 'glutamate',
        "brain_region": 'medulla',
        "species_source": [
            'mouse',
            'rat',
            'human',
        ],
        "allen_class": "",
        "biological_reference": 'Smith et al 1991; Feldman et al 2013; Ramirez et al 2016'
    },
    'phrenic_motor_neuron': {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.1,
        "has_inhibition": False,
        "description": 'Phrenic motor neuron: all-or-none recruitment of the diaphragm',
        "capability": [
            'respiration_drive',
            'motor_drive',
        ],
        "task_hint_pool": [
            'respiration_drive',
            'motor_drive',
        ],
        "lead_task_hint": 'respiration_drive',
        "neurotransmitter": 'acetylcholine',
        "brain_region": 'spinal_cord_c3_c5',
        "species_source": [
            'mouse',
            'rat',
            'human',
        ],
        "allen_class": "",
        "biological_reference": 'Feldman et al 2013'
    },
    'vlpo_neuron': {
        "reservoir_density": 0.35,
        "recurrent_pct": 0.35,
        "has_inhibition": True,
        "description": 'Ventrolateral preoptic (VLPO) sleep-promoting neuron: one arm of the sleep/wake flip-flop',
        "capability": [
            'sleep_wake',
            'state_switch',
        ],
        "task_hint_pool": [
            'sleep_wake',
            'state_switch',
        ],
        "lead_task_hint": 'sleep_wake',
        "neurotransmitter": 'gaba',
        "brain_region": 'preoptic_area',
        "species_source": [
            'mouse',
            'rat',
            'human',
        ],
        "allen_class": "",
        "biological_reference": 'Saper et al 2005; Saper et al 2010'
    },
    'head_direction_cell': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.4,
        "has_inhibition": True,
        "description": 'Head-direction cell: an internal compass that fires for one allocentric bearing',
        "capability": [
            'heading_track',
            'spatial_map',
        ],
        "task_hint_pool": [
            'heading_track',
            'spatial_map',
        ],
        "lead_task_hint": 'heading_track',
        "neurotransmitter": 'gaba',
        "brain_region": 'presubiculum',
        "species_source": [
            'mouse',
            'rat',
            'human',
        ],
        "allen_class": "",
        "biological_reference": 'Taube 1998; Moser et al 2008'
    },
    'place_cell': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.25,
        "has_inhibition": True,
        "description": 'Hippocampal place cell: fires when the animal is in one location, rewritten each theta cycle',
        "capability": [
            'place_code',
            'spatial_map',
            'episodic_context',
        ],
        "task_hint_pool": [
            'place_code',
            'spatial_map',
            'episodic_context',
        ],
        "lead_task_hint": 'place_code',
        "neurotransmitter": 'glutamate',
        "brain_region": 'hippocampus_ca1',
        "species_source": [
            'mouse',
            'rat',
            'human',
            'bat',
        ],
        "allen_class": "",
        "biological_reference": "O'Keefe & Dostrovsky 1971; Moser et al 2008"
    },
    'barrel_cortex_neuron': {
        "reservoir_density": 0.4,
        "recurrent_pct": 0.25,
        "has_inhibition": True,
        "description": 'Barrel cortex neuron: one whisker, one barrel column, self-generated reafference separated from touch',
        "capability": [
            'active_touch',
            'tactile_map',
        ],
        "task_hint_pool": [
            'active_touch',
            'tactile_map',
        ],
        "lead_task_hint": 'active_touch',
        "neurotransmitter": 'glutamate',
        "brain_region": 's1_barrel_cortex',
        "species_source": [
            'mouse',
            'rat',
        ],
        "allen_class": "",
        "biological_reference": 'Woolsey & Van der Loos 1970; Diamond et al 2008'
    },
    'whisker_motor_neuron': {
        "reservoir_density": 0.25,
        "recurrent_pct": 0.15,
        "has_inhibition": False,
        "description": 'Whisker motor neuron: drives the follicle muscle that sweeps the vibrissa',
        "capability": [
            'active_touch',
            'motor_drive',
        ],
        "task_hint_pool": [
            'active_touch',
            'motor_drive',
        ],
        "lead_task_hint": 'active_touch',
        "neurotransmitter": 'acetylcholine',
        "brain_region": 'facial_nucleus',
        "species_source": [
            'mouse',
            'rat',
        ],
        "allen_class": "",
        "biological_reference": 'Kleinfeld & Deschenes 2011'
    },
    # ------------------------------------------------------------------ #
    # v1.8.0 果蝇形状扩展：20 个可被 MaleCNS v1.0 实测锚定的神经元档案。
    # 每一个都对应真实注释细胞类型（scripts/build_malecns_anchors.py 的
    # TYPE_RULES 里有同名锚定规则），细胞数见 build 产物 profile_anchors。
    # ------------------------------------------------------------------ #
    "ol_photoreceptor_r1r6":     {
        "reservoir_density": 0.15, "recurrent_pct": 0.02, "has_inhibition": False,
        "description": "Outer photoreceptors R1-R6: histaminergic luminance/motion channel from every ommatidium into the lamina",
        "capability": ["phototransduce", "luminance_encode", "temporal_sharpen"],
        "task_hint_pool": ["phototransduce", "luminance_encode"], "lead_task_hint": "phototransduce",
        "neurotransmitter": "histamine", "brain_region": "retina",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Hardie & Raghu 2001"
    },
    "ol_photoreceptor_r7r8":     {
        "reservoir_density": 0.15, "recurrent_pct": 0.02, "has_inhibition": False,
        "description": "Inner photoreceptors R7/R8: the ultraviolet/blue colour channel targeting the medulla directly",
        "capability": ["phototransduce", "colour_encode"],
        "task_hint_pool": ["colour_encode", "wavelength_detect"], "lead_task_hint": "colour_encode",
        "neurotransmitter": "histamine", "brain_region": "retina",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Morante & Desplan 2008"
    },
    "ol_lamina_monopolar":     {
        "reservoir_density": 0.3, "recurrent_pct": 0.1, "has_inhibition": True,
        "description": "Lamina monopolar cells L1-L5: per-cartridge relay that high-pass filters photoreceptor input and feeds the medulla",
        "capability": ["relay", "high_pass_filter", "surround_inhibit"],
        "task_hint_pool": ["visual_relay", "contrast_enhance"], "lead_task_hint": "visual_relay",
        "neurotransmitter": "glutamate", "brain_region": "lamina",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Meinertzhagen & O'Neil 1991"
    },
    "ol_medulla_intrinsic":     {
        "reservoir_density": 0.35, "recurrent_pct": 0.3, "has_inhibition": True,
        "description": "Medulla columnar cells (Tm/TmY/Mi): the early-vision compute layer where ON/OFF and temporal channels are separated",
        "capability": ["on_off_split", "temporal_filter", "feature_extract"],
        "task_hint_pool": ["feature_extract", "on_off_split"], "lead_task_hint": "feature_extract",
        "neurotransmitter": "acetylcholine", "brain_region": "medulla",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Fischbach & Dittrich 1989; Nern et al 2015"
    },
    "ol_motion_detector_t45":     {
        "reservoir_density": 0.4, "recurrent_pct": 0.15, "has_inhibition": False,
        "description": "T4/T5 direction-selective cells: the elementary motion detectors, T4 for ON and T5 for OFF edges, four subtypes per lobula-plate layer",
        "capability": ["direction_select", "motion_detect", "elementary_motion"],
        "task_hint_pool": ["motion_detect", "direction_encode"], "lead_task_hint": "motion_detect",
        "neurotransmitter": "acetylcholine", "brain_region": "lobula_plate",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Maisak et al 2013"
    },
    "ol_lptc":     {
        "reservoir_density": 0.35, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "Lobula-plate tangential cells (HS/VS/CH/FD): wide-field optic-flow integrators that estimate course deviation",
        "capability": ["optic_flow_integrate", "course_estimate", "wide_field_sum"],
        "task_hint_pool": ["optic_flow", "course_control"], "lead_task_hint": "optic_flow",
        "neurotransmitter": "acetylcholine", "brain_region": "lobula_plate",
        "species_source": ["drosophila", "blowfly"], "allen_class": "",
        "biological_reference": "Hausen 1984; Borst & Weber 2011"
    },
    "ol_lpi":     {
        "reservoir_density": 0.35, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "Lobula-plate intrinsic cells (LPi): inhibitory inter-columnar links that create directional opponency between columns",
        "capability": ["directional_opponency", "lateral_inhibit"],
        "task_hint_pool": ["directional_opponency", "lateral_inhibit"], "lead_task_hint": "directional_opponency",
        "neurotransmitter": "gaba", "brain_region": "lobula_plate",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Schnell et al 2010; Mauss et al 2015"
    },
    "ol_visual_lc":     {
        "reservoir_density": 0.35, "recurrent_pct": 0.1, "has_inhibition": False,
        "description": "Lobula columnar (LC) cells: feature- and target-selective visual projection neurons relaying detected objects onward",
        "capability": ["target_detect", "feature_relay", "visual_projection"],
        "task_hint_pool": ["target_detect", "visual_relay"], "lead_task_hint": "target_detect",
        "neurotransmitter": "acetylcholine", "brain_region": "lobula",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Wu et al 2016; Keles & Frye 2017"
    },
    "escape_giant_fiber":     {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Giant fiber (DNp01): the descending command neuron of the jump-escape circuit, driving TTMn through a mixed electrical-chemical synapse",
        "capability": ["escape_command", "fast_conduction", "descending_command"],
        "task_hint_pool": ["escape_command", "startle_trigger"], "lead_task_hint": "escape_command",
        "neurotransmitter": "acetylcholine", "brain_region": "neck_connective",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Tanouye & Wyman 1980; Allen et al 2006"
    },
    "escape_vnc_gfc":     {
        "reservoir_density": 0.3, "recurrent_pct": 0.15, "has_inhibition": False,
        "description": "Giant-fiber-connected interneurons (GFC1-4): VNC relays between the descending giant fiber and thoracic motor pools",
        "capability": ["relay", "escape_relay"],
        "task_hint_pool": ["escape_relay"], "lead_task_hint": "escape_relay",
        "neurotransmitter": "acetylcholine", "brain_region": "thoracic_ganglion",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Phelan et al 1996; MaleCNS GFC types"
    },
    "escape_psi":     {
        "reservoir_density": 0.25, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Peripheral synapsing interneuron (PSI): the DLM branch relay of the giant-fiber escape pathway",
        "capability": ["relay", "escape_relay", "flight_power_trigger"],
        "task_hint_pool": ["escape_relay"], "lead_task_hint": "escape_relay",
        "neurotransmitter": "acetylcholine", "brain_region": "thoracic_ganglion",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "King & Wyman 1980"
    },
    "escape_jump_motor":     {
        "reservoir_density": 0.25, "recurrent_pct": 0.02, "has_inhibition": False,
        "description": "Jump/flight-power motor neurons (TTMn, DLMn, STTMm): the output muscles of the escape reflex - tergotrochanteral jump and dorsal longitudinal flight power",
        "capability": ["jump_drive", "flight_power_drive", "motor_output"],
        "task_hint_pool": ["jump_drive", "escape_execute"], "lead_task_hint": "jump_drive",
        "neurotransmitter": "glutamate", "brain_region": "thoracic_ganglion",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Tanouye & Wyman 1980"
    },
    "courtship_pc1":     {
        "reservoir_density": 0.35, "recurrent_pct": 0.3, "has_inhibition": True,
        "description": "pC1/P1 cluster: the male courtship decision population that integrates pheromone and song input and gates courtship behaviour",
        "capability": ["courtship_decision", "pheromone_integrate", "behaviour_gate"],
        "task_hint_pool": ["courtship_decision", "behaviour_gate"], "lead_task_hint": "courtship_decision",
        "neurotransmitter": "acetylcholine", "brain_region": "lateral_protocerebrum",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Clowney et al 2015; Deutsch et al 2020"
    },
    "courtship_asp":     {
        "reservoir_density": 0.3, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "Male-specific aggression neurons (aSP10 cluster): promote inter-male aggression and compete with courtship drive",
        "capability": ["aggression_drive", "behaviour_compete"],
        "task_hint_pool": ["aggression_drive"], "lead_task_hint": "aggression_drive",
        "neurotransmitter": "acetylcholine", "brain_region": "lateral_protocerebrum",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Watanabe et al 2017"
    },
    "courtship_pip":     {
        "reservoir_density": 0.3, "recurrent_pct": 0.1, "has_inhibition": False,
        "description": "pIP descending neurons (pIP1/pIP10): carry the courtship/aggression decision to the ventral nerve cord song and motor networks",
        "capability": ["descending_command", "courtship_output"],
        "task_hint_pool": ["courtship_output", "descending_command"], "lead_task_hint": "courtship_output",
        "neurotransmitter": "acetylcholine", "brain_region": "neck_connective",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Deutsch et al 2020; MaleCNS pIP types"
    },
    "song_vnc_int":     {
        "reservoir_density": 0.4, "recurrent_pct": 0.45, "has_inhibition": True,
        "description": "VNC song network interneurons (vMS11/vMS12/vPR): the pattern generator that shapes pulse and sine song in the wing muscles",
        "capability": ["song_pattern_generate", "pulse_shape", "rhythm_generate"],
        "task_hint_pool": ["song_pattern", "rhythm_generate"], "lead_task_hint": "song_pattern",
        "neurotransmitter": "acetylcholine", "brain_region": "thoracic_ganglion",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "von Philipsborn et al 2011; MaleCNS vMS/vPR types"
    },
    "song_vpo":     {
        "reservoir_density": 0.3, "recurrent_pct": 0.3, "has_inhibition": False,
        "description": "Ventral protocerebrum song-pathway cells (vpoEN/vpoIN): recurrent partners of the pC1 courtship decision population",
        "capability": ["courtship_amplify", "decision_recurrent"],
        "task_hint_pool": ["courtship_amplify"], "lead_task_hint": "courtship_amplify",
        "neurotransmitter": "acetylcholine", "brain_region": "lateral_protocerebrum",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Deutsch et al 2020"
    },
    "auditory_ammc":     {
        "reservoir_density": 0.35, "recurrent_pct": 0.2, "has_inhibition": True,
        "description": "Antennal mechanosensory and motor centre (AMMC) neurons: the first brain relay for near-field sound - the courtship song itself",
        "capability": ["song_reception", "mechano_relay"],
        "task_hint_pool": ["song_reception", "auditory_relay"], "lead_task_hint": "song_reception",
        "neurotransmitter": "acetylcholine", "brain_region": "antennal_mechanosensory",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Lefevre et al 2021; MaleCNS AMMC types"
    },
    "lateral_horn_ln":     {
        "reservoir_density": 0.35, "recurrent_pct": 0.3, "has_inhibition": True,
        "description": "Lateral horn neurons (LH cell families): the innate-odour centre that hard-wires pheromone and kairomone meaning without MB learning",
        "capability": ["innate_odour", "pheromone_classify", "hardwired_valence"],
        "task_hint_pool": ["innate_odour", "pheromone_classify"], "lead_task_hint": "innate_odour",
        "neurotransmitter": "gaba", "brain_region": "lateral_horn",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Jefferis et al 2007; Dolan et al 2019"
    },
    "antennal_orn":     {
        "reservoir_density": 0.2, "recurrent_pct": 0.02, "has_inhibition": False,
        "description": "Olfactory receptor neurons (ORN_ classes, e.g. ORN_DA1): one receptor class per sensillum class, converging onto single glomeruli",
        "capability": ["odorant_transduce", "receptor_code"],
        "task_hint_pool": ["odorant_transduce", "receptor_code"], "lead_task_hint": "odorant_transduce",
        "neurotransmitter": "acetylcholine", "brain_region": "antenna",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Vosshall & Stocker 2007"
    },
    # ---------------- v1.9.0: remaining cleanly-anchorable fly circuits ----
    "octopamine_vum":   {
        "reservoir_density": 0.02, "recurrent_pct": 0.0, "has_inhibition": False,
        "description": "Octopaminergic ventral unpaired median neurons (OA-VUMa / OA-VPM): the "
                       "invertebrate arousal-effort system. A small, widely projecting population "
                       "that sets behavioural gain for locomotion, learning and aggression.",
        "capability": ["arousal_modulate", "effort_set", "gain_control"],
        "task_hint_pool": ["arousal_modulate", "effort_set", "gain_control"],
        "lead_task_hint": "arousal_modulate",
        "neurotransmitter": "octopamine", "brain_region": "central_body",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Roeder 1999; Schwaerzel et al 2003; Busch et al 2009"
    },
    "looming_lplc":     {
        "reservoir_density": 0.3, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Lobula plate lobula columnar neurons (LPLC1/2/4): feature detectors for an "
                       "expanding optic-flow / looming stimulus. Their output drives the giant-fibre "
                       "escape pathway -- the fly's collision-evoked jump.",
        "capability": ["looming_detect", "collision_detect", "expansion_flow"],
        "task_hint_pool": ["looming_detect", "collision_detect", "expansion_flow"],
        "lead_task_hint": "looming_detect",
        "neurotransmitter": "glutamate", "brain_region": "lobula_plate",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "de Vries & Clandinin 2012; Klapoetke et al 2017; von Reyn et al 2014"
    },
    "pharyngeal_gustatory": {
        "reservoir_density": 0.15, "recurrent_pct": 0.02, "has_inhibition": False,
        "description": "Pharyngeal (PhG) gustatory sensory neurons: taste / cibarial input from the "
                       "proboscis region, feeding into descending motor command. Resolved to real "
                       "MaleCNS types (PhG1a-c, PhG2, PhG4, PhG7-9, ...).",
        "capability": ["taste_encode", "feed_drive", "appetitive_sense"],
        "task_hint_pool": ["taste_encode", "feed_drive", "appetitive_sense"],
        "lead_task_hint": "taste_encode",
        "neurotransmitter": "acetylcholine", "brain_region": "subesophageal_zone",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Marella et al 2006; Mann et al 2013"
    },
    # ---------------- v1.10.0: VNC + peripheral neuron-profile densification ----
    # 20 neuron populations newly anchored to real MaleCNS v1.0 superclasses
    # (vnc_motor, vnc_efferent, vnc_sensory, visual_centrifugal, cb_sensory,
    # vnc_intrinsic, cb_motor, cb_endocrine, vnc_endocrine, sensory_ascending,
    # efferent_ascending, cb_efferent, visual_projection_tbc,
    # efferent_descending, sensory_descending).
    "vnc_leg_motor_pool": {
        "reservoir_density": 0.25, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "VNC leg and abdominal motor neurons (MNad* leg, MNhl/MNml/MNnm "
                       "body-wall, Fe reductor, Acc. tibiae, Ster sternal): the motor "
                       "output stage of all leg and abdomen behaviour.",
        "capability": ["motor_output", "locomotion", "posture"],
        "task_hint_pool": ["motor_output", "locomotion", "posture"],
        "lead_task_hint": "motor_output",
        "neurotransmitter": "glutamate", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Baek et al 2021; Dorkenwald et al 2024"
    },
    "haltere_muscle_pool": {
        "reservoir_density": 0.25, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Haltere muscle motor neurons hg1-4: drive the gyroscopic "
                       "halteres, a dedicated flight-stabilization channel.",
        "capability": ["motor_output", "flight_stabilize"],
        "task_hint_pool": ["motor_output", "flight_stabilize"],
        "lead_task_hint": "motor_output",
        "neurotransmitter": "glutamate", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "wing_depressor_pool": {
        "reservoir_density": 0.25, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Wing depressor motor neurons b1/b2: paired with the wing "
                       "flexor for the ~200 Hz wing-beat oscillation.",
        "capability": ["motor_output", "flight_oscillate"],
        "task_hint_pool": ["motor_output", "flight_oscillate"],
        "lead_task_hint": "motor_output",
        "neurotransmitter": "glutamate", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "pleural_promotor_pool": {
        "reservoir_density": 0.25, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Tergopleural / pleural promotor motor neurons: thoracic "
                       "axial posturing and wing-steering base.",
        "capability": ["motor_output", "posture", "wing_steer"],
        "task_hint_pool": ["motor_output", "posture", "wing_steer"],
        "lead_task_hint": "motor_output",
        "neurotransmitter": "glutamate", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "vnc_flight_power_pool": {
        "reservoir_density": 0.25, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Flight power motor neurons DLMn/DVMn/STTMm: dorsal longitudinal "
                       "and dorsal ventral muscles powering the wing stroke.",
        "capability": ["motor_output", "flight_power"],
        "task_hint_pool": ["motor_output", "flight_power"],
        "lead_task_hint": "motor_output",
        "neurotransmitter": "glutamate", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "vnc_efferent_pool": {
        "reservoir_density": 0.3, "recurrent_pct": 0.15, "has_inhibition": False,
        "description": "VNC efferent / intermediate-motor neurons (EN*, EA*): "
                       "sensory-to-motor gating interneurons of the ventral nerve cord.",
        "capability": ["motor_gating", "relay"],
        "task_hint_pool": ["motor_gating", "relay"],
        "lead_task_hint": "motor_gating",
        "neurotransmitter": "gaba", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "vnc_sensory_pool": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "All VNC-resident sensory neurons (mechanoreceptors, chordotonal "
                       "organs, stretch receptors of abdomen / thorax): segmental input.",
        "capability": ["sensory_transduce", "proprioception"],
        "task_hint_pool": ["sensory_transduce", "proprioception"],
        "lead_task_hint": "sensory_transduce",
        "neurotransmitter": "acetylcholine", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "oa_visual_centrifugal_pool": {
        "reservoir_density": 0.3, "recurrent_pct": 0.2, "has_inhibition": False,
        "description": "Octopaminergic centrifugal neurons (OA-AL2i*, OA-ASM*) projecting "
                       "back to the optic lobe: the visual arousal / attention channel.",
        "capability": ["arousal_modulate", "visual_attention"],
        "task_hint_pool": ["arousal_modulate", "visual_attention"],
        "lead_task_hint": "arousal_modulate",
        "neurotransmitter": "octopamine", "brain_region": "optic_lobe",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Suver et al 2012; Dorkenwald et al 2024"
    },
    "johnston_organ_mechano": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Johnston organ mechanoreceptors on the flagellum (JO-A..F, JO-E): "
                       "wind detection and antenna position sense.",
        "capability": ["sensory_transduce", "wind_detect", "antenna_sense"],
        "task_hint_pool": ["sensory_transduce", "wind_detect", "antenna_sense"],
        "lead_task_hint": "sensory_transduce",
        "neurotransmitter": "acetylcholine", "brain_region": "antenna",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Kamikouchi et al 2006; Dorkenwald et al 2024"
    },
    "proboscis_mechano_pool": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Proboscis / labellar mechanosensory neurons (aPhM, Mn_, Lab): "
                       "mouthpart touch and feeding tactile input.",
        "capability": ["sensory_transduce", "feed_tactile"],
        "task_hint_pool": ["sensory_transduce", "feed_tactile"],
        "lead_task_hint": "sensory_transduce",
        "neurotransmitter": "acetylcholine", "brain_region": "subesophageal_zone",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "vnc_interneuron_pool": {
        "reservoir_density": 0.35, "recurrent_pct": 0.25, "has_inhibition": True,
        "description": "VNC intrinsic interneurons (the bulk of the ventral nerve cord): "
                       "local pattern generators and sensory-motor integration.",
        "capability": ["integration", "pattern_generate"],
        "task_hint_pool": ["integration", "pattern_generate"],
        "lead_task_hint": "integration",
        "neurotransmitter": "gaba", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "cb_motor_pool": {
        "reservoir_density": 0.25, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Central-brain motor neurons (the small cb_motor superclass): "
                       "brain-internal effector output.",
        "capability": ["motor_output", "brain_effector"],
        "task_hint_pool": ["motor_output", "brain_effector"],
        "lead_task_hint": "motor_output",
        "neurotransmitter": "glutamate", "brain_region": "brain",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "cb_endocrine_pool": {
        "reservoir_density": 0.1, "recurrent_pct": 0.0, "has_inhibition": False,
        "description": "Central-brain endocrine neurons (corpus cardiacum / corpus "
                       "allatum inputs): neurohormone release into the haemolymph.",
        "capability": ["endocrine_release", "homeostatic_signal"],
        "task_hint_pool": ["endocrine_release", "homeostatic_signal"],
        "lead_task_hint": "endocrine_release",
        "neurotransmitter": "neuropeptide", "brain_region": "brain",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "vnc_endocrine_pool": {
        "reservoir_density": 0.1, "recurrent_pct": 0.0, "has_inhibition": False,
        "description": "Ventral nerve cord endocrine neurons: segmental neurohormone "
                       "release.",
        "capability": ["endocrine_release", "homeostatic_signal"],
        "task_hint_pool": ["endocrine_release", "homeostatic_signal"],
        "lead_task_hint": "endocrine_release",
        "neurotransmitter": "neuropeptide", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "sensory_ascending_pool": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Sensory ascending neurons: carry segmental / peripheral sensory "
                       "information up to brain centres.",
        "capability": ["sensory_relay", "ascending_path"],
        "task_hint_pool": ["sensory_relay", "ascending_path"],
        "lead_task_hint": "sensory_relay",
        "neurotransmitter": "acetylcholine", "brain_region": "ventral_nerve_cord",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "efferent_ascending_pool": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Efferent ascending neurons: brain-to-VNC motor copies / "
                       "corollary discharge.",
        "capability": ["corollary_discharge", "efferent_copy"],
        "task_hint_pool": ["corollary_discharge", "efferent_copy"],
        "lead_task_hint": "corollary_discharge",
        "neurotransmitter": "gaba", "brain_region": "brain",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "ascending_neuron_pool": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Ascending neurons (AN01-AN23 A/B families plus IN / vMS / "
                       "dMS variants): the general ascending channel from VNC / "
                       "peripheral segments up to brain centres. A separate "
                       "superclass from sensory_ascending and efferent_ascending "
                       "-- the dataset's own AN prefix is the distinctive marker. "
                       "1,846 bodies, 567 types in MaleCNS v1.0.",
        "capability": ["ascending_path", "sensory_integrator", "proprioceptive"],
        "task_hint_pool": ["ascending_path", "sensory_integrator", "proprioceptive"],
        "lead_task_hint": "ascending_path",
        "neurotransmitter": "mixed", "brain_region": "ascending",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "cb_efferent_pool": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Central-brain efferent neurons: a small brain output class.",
        "capability": ["brain_output", "efferent"],
        "task_hint_pool": ["brain_output", "efferent"],
        "lead_task_hint": "brain_output",
        "neurotransmitter": "gaba", "brain_region": "brain",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "visual_projection_tbc_pool": {
        "reservoir_density": 0.3, "recurrent_pct": 0.1, "has_inhibition": False,
        "description": "Visual projection neurons still to be classified (visual_"
                       "projection_tbc): the residual optic-flow projection channel.",
        "capability": ["visual_projection", "feature_project"],
        "task_hint_pool": ["visual_projection", "feature_project"],
        "lead_task_hint": "visual_projection",
        "neurotransmitter": "acetylcholine", "brain_region": "optic_lobe",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "efferent_descending_pool": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Efferent descending neurons: motor commands from brain to VNC "
                       "(a subclass of the descending stream).",
        "capability": ["descending_command", "motor_command"],
        "task_hint_pool": ["descending_command", "motor_command"],
        "lead_task_hint": "descending_command",
        "neurotransmitter": "gaba", "brain_region": "brain",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
    "sensory_descending_pool": {
        "reservoir_density": 0.2, "recurrent_pct": 0.05, "has_inhibition": False,
        "description": "Sensory descending neurons: descending neurons carrying "
                       "sensory-state information back down the cord.",
        "capability": ["sensory_descend", "state_signal"],
        "task_hint_pool": ["sensory_descend", "state_signal"],
        "lead_task_hint": "sensory_descend",
        "neurotransmitter": "acetylcholine", "brain_region": "brain",
        "species_source": ["drosophila"], "allen_class": "",
        "biological_reference": "Dorkenwald et al 2024"
    },
}# default profile assignment: round-robin so all 10 types are represented
DEFAULT_PROFILE_CYCLE = ("sensory", "memory", "motor", "integration",
                         "attention", "working_memory",
                         "reward", "punishment", "habit", "metacognition")


# ====================================================================== #
# TOPOLOGY BLUEPRINTS — the missing 3rd dimension
# ---------------------------------------------------------------------- #
# Each blueprint defines a set of CROSS-MODULE edges between module leads
# (tissue_rep nodes). This is what turns 4 isolated modules into a
# functioning agent team. The intra-module edges (reservoir/recurrent/
# inhibitory) are generated by design_organism() regardless of blueprint;
# the blueprint ONLY adds cross-module coordination edges.
#
# Each cross_edge rule:
#   from_profile : which module profiles to pick as source
#   to_profile   : which module profiles to pick as target
#   kind         : reservoir | recurrent | inhibitory (edge taxonomy)
#   semantic     : SwarmLabs-consumable meaning of this edge
#   weight       : base weight (0..1 for excitation, -0.2..-0.6 for halt)
#   fanout       : if True, source lead connects to EVERY matching target
#                  lead (broad_explore style); else just one per (from,to)
#                  pair following the module index order.
# ====================================================================== #
BLUEPRINTS: dict[str, dict] = {
    # ------------------------------------------------------------------ #
    # 基础蓝图（v1.0）— 5 种，作为独立任务风格
    # ------------------------------------------------------------------ #
    "sequential": {
        "description": "前馈链：sensory → memory → motor → integration 严格串行",
        "use_cases": ["数据→推理→执行 单向任务", "科研 pipeline 复现"],
        "category": "basic",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "handoff", "weight": 0.35},
            {"from_profile": "memory", "to_profile": "motor",
             "kind": "reservoir", "semantic": "execute", "weight": 0.40},
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "report", "weight": 0.25},
        ],
    },
    "deep_reasoning": {
        "description": "深推理：强化 memory 跨模块回环，弱化 motor",
        "use_cases": ["多步推理", "跨域桥接", "GP surrogate 拟合"],
        "category": "basic",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "handoff", "weight": 0.30},
            {"from_profile": "memory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "cross_state_feedback", "weight": 0.45,
             "fanout": True},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "synthesis", "weight": 0.40},
        ],
    },
    "fast_reflex": {
        "description": "快速反射：sensory → motor 跳跃通路，memory 事后补记",
        "use_cases": ["实时响应", "快速感知-动作循环", "guardrail 触发"],
        "category": "basic",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "motor",
             "kind": "reservoir", "semantic": "bypass_fast_path", "weight": 0.55},
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "async_record", "weight": 0.15},
        ],
    },
    "broad_explore": {
        "description": "广度探索：sensory 扇出到多 memory，汇聚到 integration",
        "use_cases": ["多假设并行", "候选排名", "广谱搜索"],
        "category": "basic",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "fanout_hypothesis", "weight": 0.30,
             "fanout": True},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "converge", "weight": 0.35},
        ],
    },
    "orchestrated": {
        "description": "协调调度：强 coordinator 全局广播 + 全模块汇聚",
        "use_cases": ["多 agent 长时任务", "全局仲裁", "conflict resolution"],
        "category": "basic",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "broadcast_observation", "weight": 0.20},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "report_state", "weight": 0.30},
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "report_action", "weight": 0.25},
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "inhibitory", "semantic": "halt", "weight": -0.35,
             "fanout": True},
        ],
    },

    # ------------------------------------------------------------------ #
    # 生物学蓝图（v1.1）— 4 种，可堆叠使用（buildable blocks）
    # ------------------------------------------------------------------ #
    "hierarchical": {
        "description": "皮质层级：sensory → 低层整合 → 高层整合 → motor（模拟 V1→V2→IT）",
        "use_cases": ["分层特征提取", "抽象推理", "跨层级抽象"],
        "category": "biological",
        "cross_edges": [
            # 低层：sensory 直接进 memory（相当于 V1→V2）
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "low_level_feedforward", "weight": 0.40},
            # 中层：memory → integration（相当于 V2→V4/IT）
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "high_level_abstract", "weight": 0.35},
            # 高层：integration → motor（相当于 IT→运动皮层）
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "reservoir", "semantic": "cognitive_command", "weight": 0.30},
            # 层级内回环：memory 跨模块精细化
            {"from_profile": "memory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "hierarchical_refine", "weight": 0.25,
             "fanout": True},
        ],
    },
    "lateral_inhibition": {
        "description": "侧向抑制：邻居模块互相抑制，突出局部信号（视网膜/皮层 surround）",
        "use_cases": ["特征增强", "去噪", "对比度放大", "选择性注意"],
        "category": "biological",
        "cross_edges": [
            # memory ↔ memory 侧向抑制：相邻 memory 互相刹车
            {"from_profile": "memory", "to_profile": "memory",
             "kind": "inhibitory", "semantic": "surround_suppression", "weight": -0.25,
             "fanout": True},
            # sensory → memory 主通路（保留输入信号）
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "feedforward_signal", "weight": 0.35},
            # motor → integration 汇聚（保留决策通路）
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "action_report", "weight": 0.25},
        ],
    },
    "predictive_coding": {
        "description": "预测编码：integration 下送预测，modules 上送误差（Friston free-energy）",
        "use_cases": ["主动推断", "假设-检验循环", "生成模型"],
        "category": "biological",
        "cross_edges": [
            # 自上而下：integration → memory（预测下送）
            {"from_profile": "integration", "to_profile": "memory",
             "kind": "reservoir", "semantic": "prediction_down", "weight": 0.35,
             "fanout": True},
            # 自下而上：memory → integration（误差上送）
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "error_up", "weight": 0.40},
            # integration → motor（预测动作）
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "reservoir", "semantic": "predicted_action", "weight": 0.25},
            # motor → integration（动作误差）
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "action_error", "weight": 0.30},
        ],
    },
    "competitive_selection": {
        "description": "竞争选择：多 motor 候选并行，integration 抑制输者（winner-take-all）",
        "use_cases": ["候选排名", "A/B 决策", "假设淘汰", "强化学习"],
        "category": "biological",
        "cross_edges": [
            # 各 motor → integration（候选上送）
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "candidate_vote", "weight": 0.35},
            # integration → 所有 motor（抑制输者，负权重）
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "inhibitory", "semantic": "suppress_loser", "weight": -0.40,
             "fanout": True},
            # sensory → motor 快通路（让候选能直接看到输入）
            {"from_profile": "sensory", "to_profile": "motor",
             "kind": "reservoir", "semantic": "shared_stimulus", "weight": 0.20},
        ],
    },
    # Phase 1 新蓝图（2026-09-18）：基于 attention + working_memory 模块
    "attention_gate": {
        "description": "注意力门控：sensory → attention → 选择性过滤后传递给 memory/motor/integration",
        "use_cases": ["信号过滤", "选择性注意", "噪声抑制", "优先级分配"],
        "category": "biological",
        "cross_edges": [
            # sensory → attention（输入进入注意力门控）
            {"from_profile": "sensory", "to_profile": "attention",
             "kind": "reservoir", "semantic": "input_to_attention", "weight": 0.40},
            # attention → memory（过滤后的信号进入记忆）
            {"from_profile": "attention", "to_profile": "memory",
             "kind": "reservoir", "semantic": "attended_signal", "weight": 0.35},
            # attention → motor（过滤后的信号直接触发动作）
            {"from_profile": "attention", "to_profile": "motor",
             "kind": "reservoir", "semantic": "attended_action", "weight": 0.30},
            # attention → integration（注意力状态上报）
            {"from_profile": "attention", "to_profile": "integration",
             "kind": "reservoir", "semantic": "attention_state", "weight": 0.25},
        ],
    },
    "working_memory_buffer": {
        "description": "工作记忆缓冲：memory → working_memory（活跃操作）→ integration（综合）",
        "use_cases": ["短期记忆", "活跃操作", "状态更新", "多步推理"],
        "category": "biological",
        "cross_edges": [
            # memory → working_memory（长期记忆进入工作记忆）
            {"from_profile": "memory", "to_profile": "working_memory",
             "kind": "reservoir", "semantic": "recall_to_working", "weight": 0.40},
            # working_memory → working_memory（活跃操作，高 recurrent）
            {"from_profile": "working_memory", "to_profile": "working_memory",
             "kind": "reservoir", "semantic": "active_manipulation", "weight": 0.50,
             "fanout": True},
            # working_memory → integration（工作记忆综合）
            {"from_profile": "working_memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "working_synthesis", "weight": 0.35},
        ],
    },
    "attention_working_combo": {
        "description": "注意力+工作记忆组合：sensory → attention → working_memory → integration",
        "use_cases": ["复杂推理", "多步任务", "注意力引导的记忆操作", "认知控制"],
        "category": "biological",
        "cross_edges": [
            # sensory → attention（输入进入注意力）
            {"from_profile": "sensory", "to_profile": "attention",
             "kind": "reservoir", "semantic": "input_to_attention", "weight": 0.40},
            # attention → working_memory（注意力引导工作记忆）
            {"from_profile": "attention", "to_profile": "working_memory",
             "kind": "reservoir", "semantic": "attended_recall", "weight": 0.35},
            # working_memory → working_memory（活跃操作）
            {"from_profile": "working_memory", "to_profile": "working_memory",
             "kind": "reservoir", "semantic": "active_manipulation", "weight": 0.45,
             "fanout": True},
            # working_memory → integration（综合）
            {"from_profile": "working_memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "cognitive_synthesis", "weight": 0.30},
            # attention → integration（注意力状态上报）
            {"from_profile": "attention", "to_profile": "integration",
             "kind": "reservoir", "semantic": "attention_state", "weight": 0.20},
        ],
    },

    # ------------------------------------------------------------------ #
    # Phase 2 新蓝图（2026-09-18）：模块库扩至 10 后，基于新模块的生物学蓝图
    # + 合成编排蓝图。新增 10 种 → 蓝图库 12 → 22。
    # ------------------------------------------------------------------ #
    # —— 6 个生物学蓝图：均追溯到 MaleCNS v1.0 的三个真实 motif 之一 —— #
    "hierarchical_deep": {
        "description": "深层皮质层级：sensory→memory→integration→metacognition→motor（模拟 V1→V2→V4→IT→运动）",
        "use_cases": ["多层抽象", "深度特征提取", "跨层认知命令"],
        "category": "biological",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "low_level_feedforward", "weight": 0.40},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "mid_level_abstract", "weight": 0.35},
            {"from_profile": "integration", "to_profile": "metacognition",
             "kind": "reservoir", "semantic": "high_level_abstract", "weight": 0.30},
            {"from_profile": "metacognition", "to_profile": "motor",
             "kind": "reservoir", "semantic": "cognitive_command", "weight": 0.30},
            {"from_profile": "memory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "hierarchical_refine", "weight": 0.25,
             "fanout": True},
        ],
    },
    "predictive_coding_v2": {
        "description": "预测编码 v2：在 recurrent_feedback 基础上引入 reward 价值偏置（主动推断 + 强化学习）",
        "use_cases": ["主动推断", "假设-检验+价值调制", "生成模型+学习"],
        "category": "biological",
        "cross_edges": [
            {"from_profile": "integration", "to_profile": "memory",
             "kind": "reservoir", "semantic": "prediction_down", "weight": 0.35,
             "fanout": True},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "error_up", "weight": 0.40},
            {"from_profile": "reward", "to_profile": "integration",
             "kind": "reservoir", "semantic": "value_bias", "weight": 0.30},
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "reservoir", "semantic": "predicted_action", "weight": 0.25},
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "action_error", "weight": 0.30},
        ],
    },
    "reward_gated_selection": {
        "description": "奖赏门控选择：winner-take-all 中 reward 强化胜者（PPL/PAM 多巴胺偏置）",
        "use_cases": ["强化学习决策", "A/B 候选强化", "多巴胺偏置选择"],
        "category": "biological",
        "cross_edges": [
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "candidate_vote", "weight": 0.35},
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "inhibitory", "semantic": "suppress_loser", "weight": -0.40,
             "fanout": True},
            {"from_profile": "reward", "to_profile": "motor",
             "kind": "reservoir", "semantic": "reinforce_winner", "weight": 0.30},
            {"from_profile": "sensory", "to_profile": "motor",
             "kind": "reservoir", "semantic": "shared_stimulus", "weight": 0.20},
        ],
    },
    "habit_consolidation": {
        "description": "习惯固化：memory→habit（高 recurrent）→motor（MBON 习惯回路）",
        "use_cases": ["技能自动化", "习惯形成", "程序性记忆"],
        "category": "biological",
        "cross_edges": [
            {"from_profile": "memory", "to_profile": "habit",
             "kind": "reservoir", "semantic": "recall_to_habit", "weight": 0.40},
            {"from_profile": "habit", "to_profile": "habit",
             "kind": "reservoir", "semantic": "habit_loop", "weight": 0.50,
             "fanout": True},
            {"from_profile": "habit", "to_profile": "motor",
             "kind": "reservoir", "semantic": "habitual_action", "weight": 0.35},
            {"from_profile": "sensory", "to_profile": "habit",
             "kind": "reservoir", "semantic": "cue_acquire", "weight": 0.25},
        ],
    },
    "punishment_suppression": {
        "description": "惩罚抑制：motor→punishment 检测错误，punishment→motor 抑制（DMP/DopR 厌恶回路）",
        "use_cases": ["错误抑制", "安全护栏", "厌恶学习"],
        "category": "biological",
        "cross_edges": [
            {"from_profile": "motor", "to_profile": "punishment",
             "kind": "reservoir", "semantic": "action_to_punish", "weight": 0.35},
            {"from_profile": "punishment", "to_profile": "motor",
             "kind": "inhibitory", "semantic": "suppress_error", "weight": -0.45,
             "fanout": True},
            {"from_profile": "punishment", "to_profile": "integration",
             "kind": "inhibitory", "semantic": "error_report", "weight": -0.25,
             "fanout": True},
            {"from_profile": "sensory", "to_profile": "punishment",
             "kind": "reservoir", "semantic": "cue_punish", "weight": 0.20},
        ],
    },
    "metacognitive_control": {
        "description": "元认知监控：metacognition 监视 integration 并发送纠正性抑制（CRE/DCHB 监控回路）",
        "use_cases": ["自我纠错", "不确定性监控", "认知门控"],
        "category": "biological",
        "cross_edges": [
            {"from_profile": "integration", "to_profile": "metacognition",
             "kind": "reservoir", "semantic": "monitor_state", "weight": 0.35},
            {"from_profile": "metacognition", "to_profile": "integration",
             "kind": "inhibitory", "semantic": "correct_bias", "weight": -0.30,
             "fanout": True},
            {"from_profile": "metacognition", "to_profile": "motor",
             "kind": "inhibitory", "semantic": "gate_action", "weight": -0.25,
             "fanout": True},
            {"from_profile": "sensory", "to_profile": "metacognition",
             "kind": "reservoir", "semantic": "observation", "weight": 0.25},
        ],
    },

    # —— 4 个合成蓝图：基于 10 个生物模块人工编排，非单一连接组 motif 先验 —— #
    # 诚实标记：category="synthetic"，source_motif="none"（设计编排，非直接溯源）
    "rl_actor_critic": {
        "description": "强化学习 actor-critic 闭环：memory→motor 策略，reward/punishment 双向价值调制",
        "use_cases": ["策略优化", "价值学习", "闭环强化"],
        "category": "synthetic",
        "cross_edges": [
            {"from_profile": "memory", "to_profile": "motor",
             "kind": "reservoir", "semantic": "policy_act", "weight": 0.40},
            {"from_profile": "motor", "to_profile": "reward",
             "kind": "reservoir", "semantic": "action_value", "weight": 0.30},
            {"from_profile": "reward", "to_profile": "motor",
             "kind": "reservoir", "semantic": "policy_reinforce", "weight": 0.35},
            {"from_profile": "motor", "to_profile": "punishment",
             "kind": "reservoir", "semantic": "action_penalty", "weight": 0.25},
            {"from_profile": "punishment", "to_profile": "memory",
             "kind": "inhibitory", "semantic": "demote_bad", "weight": -0.30,
             "fanout": True},
        ],
    },
    "curiosity_driven": {
        "description": "好奇心驱动探索：broad_explore + reward 新颖性信号回灌（人工合成编排）",
        "use_cases": ["探索-利用平衡", "新颖性检测", "主动学习"],
        "category": "synthetic",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "fanout_hypothesis", "weight": 0.30,
             "fanout": True},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "converge", "weight": 0.35},
            {"from_profile": "integration", "to_profile": "reward",
             "kind": "reservoir", "semantic": "novelty_signal", "weight": 0.25},
            {"from_profile": "reward", "to_profile": "memory",
             "kind": "reservoir", "semantic": "curiosity_bias", "weight": 0.20,
             "fanout": True},
        ],
    },
    "cognitive_control": {
        "description": "认知控制编排：attention→working_memory→metacognition 全栈（人工合成）",
        "use_cases": ["复杂认知任务", "执行功能", "多步认知控制"],
        "category": "synthetic",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "attention",
             "kind": "reservoir", "semantic": "input_to_attention", "weight": 0.40},
            {"from_profile": "attention", "to_profile": "working_memory",
             "kind": "reservoir", "semantic": "attended_recall", "weight": 0.35},
            {"from_profile": "working_memory", "to_profile": "working_memory",
             "kind": "reservoir", "semantic": "active_manipulation", "weight": 0.45,
             "fanout": True},
            {"from_profile": "working_memory", "to_profile": "metacognition",
             "kind": "reservoir", "semantic": "monitor", "weight": 0.30},
            {"from_profile": "metacognition", "to_profile": "integration",
             "kind": "inhibitory", "semantic": "gate", "weight": -0.25,
             "fanout": True},
        ],
    },
    "multi_motif_blend": {
        "description": "多 motif 人工混合：hierarchical+predictive+competitive 的手调融合",
        "use_cases": ["通用复杂任务", "多机制融合", "鲁棒推理"],
        "category": "synthetic",
        "cross_edges": [
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "feedforward", "weight": 0.35},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "abstract", "weight": 0.30},
            {"from_profile": "integration", "to_profile": "memory",
             "kind": "reservoir", "semantic": "prediction_down", "weight": 0.30,
             "fanout": True},
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "candidate_vote", "weight": 0.35},
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "inhibitory", "semantic": "suppress_loser", "weight": -0.35,
             "fanout": True},
        ],
    },
    # ---- Phase 4 新蓝图（2026-09-18 稳定性维度设计目标）---- #
    # 三个专为"高模块隔离度"设计的蓝图：cross_module_edge_ratio 目标 < 0.20
    "modular_isolation": {
        "description": "高模块隔离编排：跨模块仅必要路由 + inhibitory 广播，最大化故障隔离度",
        "use_cases": ["故障隔离优先", "模块级容错", "结构稳定性验证"],
        "category": "biological",
        "cross_edges": [
            # 只有三条必要路由：sensor→integration 汇聚、integration→motor 输出、
            # integration 对其他模块 inhibitory 广播（保持模块独立）
            {"from_profile": "sensory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "primary_ingress", "weight": 0.40},
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "reservoir", "semantic": "primary_output", "weight": 0.40},
            {"from_profile": "integration", "to_profile": "sensory",
             "kind": "inhibitory", "semantic": "isolation_gate_in", "weight": -0.20,
             "fanout": True},
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "inhibitory", "semantic": "isolation_gate_out", "weight": -0.20,
             "fanout": True},
        ],
    },
    "robust_redundant": {
        "description": "冗余路径编排：多条并行 reservoir 路径，单点故障不传播",
        "use_cases": ["冗余容错", "路径鲁棒", "小规模脑区替代"],
        "category": "biological",
        "cross_edges": [
            # 三条并行前馈路径，任意一条被切断仍能传递信号
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "path_primary", "weight": 0.35,
             "fanout": True},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "path_converge", "weight": 0.35,
             "fanout": True},
            {"from_profile": "sensory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "path_bypass", "weight": 0.25,
             "fanout": True},
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "reservoir", "semantic": "path_output", "weight": 0.35,
             "fanout": True},
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "feedback_reinforce", "weight": 0.20},
        ],
    },
    "decoupled_hierarchical": {
        "description": "分层解耦编排：层间前馈+反馈，同级不同模块间零连接",
        "use_cases": ["分层推理", "层级监督", "故障隔离的分层版"],
        "category": "biological",
        "cross_edges": [
            # 只有垂直（层间）连接：sensory↔memory↔integration↔motor
            # 无水平（同级）连接，天然解耦
            {"from_profile": "sensory", "to_profile": "memory",
             "kind": "reservoir", "semantic": "layer_up_encode", "weight": 0.35},
            {"from_profile": "memory", "to_profile": "integration",
             "kind": "reservoir", "semantic": "layer_up_abstract", "weight": 0.30},
            {"from_profile": "integration", "to_profile": "motor",
             "kind": "reservoir", "semantic": "layer_down_act", "weight": 0.35},
            {"from_profile": "motor", "to_profile": "integration",
             "kind": "reservoir", "semantic": "layer_up_feedback", "weight": 0.20},
            {"from_profile": "integration", "to_profile": "memory",
             "kind": "reservoir", "semantic": "layer_down_predict", "weight": 0.25},
            {"from_profile": "memory", "to_profile": "sensory",
             "kind": "reservoir", "semantic": "layer_down_reweight", "weight": 0.20},
        ],
    },
}

# ====================================================================== #
# Blueprint → source motif mapping (schema v1.1.1, additive)
# ---------------------------------------------------------------------- #
# Each blueprint records which REAL connectome motif it derives from.
# - 5 basic blueprints: "none" (hand-designed, NOT biological prior)
# - 4 biological blueprints: mapped to one of the 3 real motifs
#   extracted from MaleCNS v1.0 (see motifs/swarm_agent_topology_motifs.json)
#
# This is the ARCHITECTURAL GUARANTEE that differentiates flybrain from
# LangGraph/AutoGen/CrewAI: every biological blueprint can be traced back
# to a specific real neuron population in the 166,700-neuron connectome.
#
# Real motif anchors (from MaleCNS v1.0, CC-BY):
#   inhibitory_hub:      APL body 10540, fan_out 102,263 synapses
#   reservoir_smallworld: small-world subgraph within a brain region
#   recurrent_feedback:  feedback loops (e.g. olfactory intrinsic 28.74% self-loops)
# ====================================================================== #
BLUEPRINT_SOURCE_MOTIF: dict[str, dict] = {
    # ------------------------------------------------------------------ #
    # 5 basic blueprints — NO biological source (hand-designed)
    # ------------------------------------------------------------------ #
    "sequential":         {"motif": "none", "note": "人工设计的前馈链，非生物先验", "stability_target": 0.25},
    "deep_reasoning":     {"motif": "none", "note": "人工设计的深推理回环，非生物先验", "stability_target": 0.25},
    "fast_reflex":        {"motif": "none", "note": "人工设计的快速反射通路，非生物先验", "stability_target": 0.25},
    "broad_explore":      {"motif": "none", "note": "人工设计的广度探索扇出，非生物先验", "stability_target": 0.25},
    "orchestrated":       {"motif": "none", "note": "人工设计的协调调度，非生物先验", "stability_target": 0.25},
    # ------------------------------------------------------------------ #
    # 4 biological blueprints — each traces to a real MaleCNS motif
    # ------------------------------------------------------------------ #
    "hierarchical": {
        "motif": "reservoir_smallworld",
        "motif_body": None,
        "motif_type": None,
        "motif_fanout": None,
        "note": "皮质层级分层（V1→V2→IT），对应小世界储备库的分层处理原则",
        "anchor": "MaleCNS v1.0 reservoir_smallworld motif",
    },
    "lateral_inhibition": {
        "motif": "inhibitory_hub",
        "motif_body": 10540,
        "motif_type": "APL",
        "motif_fanout": 102263,
        "note": "侧向抑制是 inhibitory_hub 的邻居变体（surround suppression）",
        "anchor": "MaleCNS v1.0 APL body 10540 (inhibitory_hub)",
    },
    "predictive_coding": {
        "motif": "recurrent_feedback",
        "motif_body": None,
        "motif_type": None,
        "motif_fanout": None,
        "note": "预测-误差双向递归，对应 recurrent_feedback motif（如 ol_intrinsic 自循环 28.74%）",
        "anchor": "MaleCNS v1.0 recurrent_feedback motif",
    },
    "competitive_selection": {
        "motif": "inhibitory_hub",
        "motif_body": 10540,
        "motif_type": "APL",
        "motif_fanout": 102263,
        "note": "winner-take-all 抑制，直接对应 APL body 10540（10万+ fan-out 广播抑制）",
        "anchor": "MaleCNS v1.0 APL body 10540 (inhibitory_hub)",
    },
    # Phase 1 新蓝图（2026-09-18）
    "attention_gate": {
        "motif": "inhibitory_hub",
        "motif_body": 10540,
        "motif_type": "APL",
        "motif_fanout": 102263,
        "note": "注意力门控是 inhibitory_hub 的选择性变体（选择性抑制非注意项）",
        "anchor": "MaleCNS v1.0 APL body 10540 (inhibitory_hub)",
    },
    "working_memory_buffer": {
        "motif": "recurrent_feedback",
        "motif_body": None,
        "motif_type": None,
        "motif_fanout": None,
        "note": "工作记忆缓冲对应 recurrent_feedback motif（高 recurrent 活跃操作）",
        "anchor": "MaleCNS v1.0 recurrent_feedback motif",
    },
    "attention_working_combo": {
        "motif": "inhibitory_hub",
        "motif_body": 10540,
        "motif_type": "APL",
        "motif_fanout": 102263,
        "note": "注意力+工作记忆组合，对应 inhibitory_hub（选择性抑制）+ recurrent_feedback（活跃操作）",
        "anchor": "MaleCNS v1.0 APL body 10540 (inhibitory_hub) + recurrent_feedback motif",
    },
    # ---- Phase 2 新蓝图 source motif（2026-09-18）---- #
    # 6 个生物学蓝图：分别追溯到 3 个真实 motif 之一
    "hierarchical_deep": {
        "motif": "reservoir_smallworld",
        "motif_body": None,
        "motif_type": None,
        "motif_fanout": None,
        "note": "深层皮质层级（V1→V2→V4→IT→运动），对应小世界储备库的分层处理原则",
        "anchor": "MaleCNS v1.0 reservoir_smallworld motif",
    },
    "predictive_coding_v2": {
        "motif": "recurrent_feedback",
        "motif_body": None,
        "motif_type": None,
        "motif_fanout": None,
        "note": "预测-误差双向递归 + reward 偏置，对应 recurrent_feedback motif（如 ol_intrinsic 自循环 28.74%）",
        "anchor": "MaleCNS v1.0 recurrent_feedback motif",
    },
    "reward_gated_selection": {
        "motif": "inhibitory_hub",
        "motif_body": 10540,
        "motif_type": "APL",
        "motif_fanout": 102263,
        "note": "winner-take-all 抑制 + reward 强化，直接对应 APL body 10540（10万+ fan-out 广播抑制）",
        "anchor": "MaleCNS v1.0 APL body 10540 (inhibitory_hub)",
    },
    "habit_consolidation": {
        "motif": "recurrent_feedback",
        "motif_body": None,
        "motif_type": None,
        "motif_fanout": None,
        "note": "习惯固化高 recurrent 回路，对应 recurrent_feedback motif（MBON 习惯回路）",
        "anchor": "MaleCNS v1.0 recurrent_feedback motif",
    },
    "punishment_suppression": {
        "motif": "inhibitory_hub",
        "motif_body": 10540,
        "motif_type": "APL",
        "motif_fanout": 102263,
        "note": "惩罚抑制错误动作，对应 APL body 10540（DMP/DopR 厌恶回路的广播抑制原则）",
        "anchor": "MaleCNS v1.0 APL body 10540 (inhibitory_hub)",
    },
    "metacognitive_control": {
        "motif": "inhibitory_hub",
        "motif_body": 10540,
        "motif_type": "APL",
        "motif_fanout": 102263,
        "note": "元认知监控并纠正，对应 APL body 10540（CRE/DCHB 监控回路的广播抑制原则）",
        "anchor": "MaleCNS v1.0 APL body 10540 (inhibitory_hub)",
    },
    # 4 个合成蓝图：人工编排，非单一连接组 motif 先验（诚实标记 motif="none"）
    "rl_actor_critic": {
        "motif": "none",
        "note": "人工设计的 actor-critic 闭环编排，基于生物模块（reward/punishment）但非单一连接组 motif 先验",
    },
    "curiosity_driven": {
        "motif": "none",
        "note": "人工设计的好奇心驱动探索编排，基于生物模块但非单一连接组 motif 先验",
    },
    "cognitive_control": {
        "motif": "none",
        "note": "人工设计的认知控制编排，基于生物模块（attention/working_memory/metacognition）但非单一连接组 motif 先验",
    },
    "multi_motif_blend": {
        "motif": "none",
        "note": "人工设计的多 motif 融合编排，基于生物模块但非单一连接组 motif 先验",
    },
    # ---- Phase 4 新蓝图（2026-09-18 稳定性维度设计目标）---- #
    # 三个专为"高模块隔离"设计的蓝图，直接追溯到 3 个真实 motif
    "modular_isolation": {
        "motif": "inhibitory_hub",
        "motif_body": 10540,
        "motif_type": "APL",
        "motif_fanout": 102263,
        "note": "专为故障隔离设计：模块内密化 + 跨模块极稀疏路由，最大化模块级隔离度",
        "anchor": "MaleCNS v1.0 APL body 10540 (inhibitory_hub)",
        "stability_target": 0.30,
    },
    "robust_redundant": {
        "motif": "reservoir_smallworld",
        "motif_body": None,
        "motif_type": None,
        "motif_fanout": None,
        "note": "冗余度设计：每个模块内部多条并行路径，单点故障不传播；对应小世界储备库的短路径特征",
        "anchor": "MaleCNS v1.0 reservoir_smallworld motif",
        "stability_target": 0.32,
    },
    "decoupled_hierarchical": {
        "motif": "recurrent_feedback",
        "motif_body": None,
        "motif_type": "ol_intrinsic",
        "motif_fanout": None,
        "note": "分层解耦：层级间仅前馈+反馈，同级不同模块间不连接；对应 recurrent_feedback 的模块化递归",
        "anchor": "MaleCNS v1.0 recurrent_feedback motif",
        "stability_target": 0.38,
    },
}


def _motif_provenance(org: dict) -> dict | None:
    """Build the motif provenance trail for a virtual organism.

    Returns None if no blueprint is specified. Otherwise returns a dict
    that traces EVERY blueprint used back to its biological source (if any),
    so a reader can always answer "where did this agent team topology come
    from?" — a question LangGraph/AutoGen/CrewAI can never answer.

    Schema v1.2.0 (additive, MINOR). Consumers on v1.0/v1.1/v1.1.1 that ignore
    motif_provenance still parse correctly. New in v1.2.0:

      * Three-stage provenance per blueprint:
          (1) neuron body anchor      — motif_body / motif_type / motif_fanout
          (2) synapse statistics      — motif_synapse_stats (dataset-derived)
          (3) dataset query           — motif_query (SQL-like, runnable on MaleCNS)
      * Per-blueprint stability_target (cross-module edge ratio upper bound)
      * Cross-blueprint stability_summary (worst-case target across used blueprints)
    """
    blueprint_spec = org.get("blueprint")
    if not blueprint_spec:
        return None
    if isinstance(blueprint_spec, str):
        parts = _normalize_blueprint_spec(blueprint_spec)[0]
    elif isinstance(blueprint_spec, (list, tuple)):
        parts = [str(p) for p in blueprint_spec]
    else:
        return None

    blueprint_map: dict[str, dict] = {}
    bio_count = 0
    stability_targets: list[float] = []
    for name in parts:
        entry = BLUEPRINT_SOURCE_MOTIF.get(name)
        if entry is None:
            # unknown blueprint — include with no provenance (don't drop silently)
            blueprint_map[name] = {
                "source_motif": "unknown",
                "note": "未知蓝图，无 motif 追溯信息",
                "is_bio_prior": False,
                "motif_synapse_stats": None,
                "motif_query": None,
                "stability_target": None,
            }
            continue
        motif_name = entry.get("motif")
        is_bio = motif_name != "none"
        if is_bio:
            bio_count += 1
        # ---- v1.2.0: three-stage provenance (synapse stats + query) ----
        synapse_stats = _motif_synapse_stats(motif_name, entry)
        query = entry.get("motif_query") or _motif_query(motif_name, entry)
        # stability_target: prefer explicit entry value, fall back to motif-based default
        stab_target = entry.get("stability_target")
        if stab_target is None:
            stab_target = _default_stability_target(motif_name)
        if stab_target is not None:
            stability_targets.append(float(stab_target))

        blueprint_map[name] = {
            "source_motif": motif_name,
            "motif_body": entry.get("motif_body"),
            "motif_type": entry.get("motif_type"),
            "motif_fanout": entry.get("motif_fanout"),
            "motif_synapse_stats": synapse_stats,
            "motif_query": query,
            "stability_target": stab_target,
            "note": entry.get("note"),
            "anchor": entry.get("anchor"),
            "is_bio_prior": is_bio,
        }

    worst_stability = (min(stability_targets)
                       if stability_targets else None)

    return {
        "dataset": {
            "name": "MaleCNS v1.0",
            "license": "CC-BY",
            "total_synapses": 124177617,
            "annotated_neurons": 166700,
            "dataset_url": "https://flycellatlas.org/male_cns",
            "annotation_version": "v1.0",
        },
        "blueprints_used": list(parts),
        "blueprint_to_motif": blueprint_map,
        "is_bio_prior": bio_count > 0,
        "bio_prior_count": bio_count,
        "total_blueprint_count": len(parts),
        "stability_summary": {
            "worst_case_target": worst_stability,
            "targets_seen": stability_targets,
            "note": ("Cross-module edge ratio upper bound. Lower = more isolated. "
                     "Set by design intent; verified by _verify.py stability check."),
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": MOTIF_PROVENANCE_SCHEMA_VERSION,
    }


# --------------------------------------------------------------------------- #
# v1.2.1 helpers: W3C PROV-JSON (via dataprov) — standardized provenance
# --------------------------------------------------------------------------- #
def _prov_json(provenance: dict | None, organism_name: str | None = None,
               spec: dict | None = None) -> dict | None:
    """Convert motif_provenance to a W3C PROV-JSON bundle via dataprov.

    New in schema v1.2.1. The resulting dict is a PROV-JSON document
    (W3C standard) that any provenance-aware tool (yProv4ML, MLflow2PROV,
    MIT Sloan Data Provenance Explorer, PROV-O SPARQL endpoints) can ingest.

    Structure produced:
      - entities: MaleCNS dataset, each real neuron body (motif_body id),
        each blueprint (as a dataprov Entity), and the virtual organism
      - activities: one per blueprint extraction step + one final synthesis
      - agents: flybrain-connectome tool (SoftwareAgent) + FlyCellAtlas (attributor)
      - wasAssociatedWith / wasAttributedTo / wasDerivedFrom edges

    dataprov is imported lazily so the main module stays dep-free at import time.
    If dataprov is unavailable, returns None (non-fatal: callers keep motif_provenance).

    References:
      * W3C PROV-DM: https://www.w3.org/TR/prov-dm/
      * dataprov:    https://github.com/RI-SE/dataprov  (MIT, zero-dep, stdlib)
    """
    if not provenance:
        return None
    try:
        from dataprov import ProvenanceChain
    except ImportError:
        return None

    now = datetime.now(timezone.utc).isoformat()
    dataset = provenance.get("dataset", {})
    org_name = organism_name or "flybrain_organism"
    spec_str = json.dumps(spec or {}, sort_keys=True)[:500] if spec else ""

    # ---- 1. Root entity = MaleCNS dataset ------------------------------ #
    chain = ProvenanceChain.create(
        entity_id=org_name,
        initial_source=dataset.get("dataset_url", "https://flycellatlas.org/male_cns"),
        description=("Virtual organism synthesized from MaleCNS v1.0 motifs; "
                     "blueprints: " + ", ".join(provenance.get("blueprints_used", []))),
    )

    # ---- 2. One activity per blueprint ---------------------------------- #
    bp_map = provenance.get("blueprint_to_motif", {})
    step_start_offset = 0
    for i, bp in enumerate(provenance.get("blueprints_used", []), start=1):
        entry = bp_map.get(bp, {})
        started = (datetime.now(timezone.utc) + timedelta(seconds=step_start_offset)).isoformat()
        ended = (datetime.now(timezone.utc) + timedelta(seconds=step_start_offset + 1)).isoformat()
        step_start_offset += 1
        chain.add(
            started_at=started,
            ended_at=ended,
            tool_name="flybrain-connectome",
            tool_version=provenance.get("schema_version", MOTIF_PROVENANCE_SCHEMA_VERSION),
            operation="blueprint_motif_extraction",
            inputs=["MaleCNS_v1.0.tsv"],
            input_formats=["TSV"],
            outputs=[f"motif:{bp}"],
            output_formats=["JSON"],
            arguments=(f"--blueprint={bp} "
                       f"--motif={entry.get('source_motif')} "
                       f"--motif-body={entry.get('motif_body')} "
                       f"--is-bio-prior={entry.get('is_bio_prior')}"),
            drl=4,
        )

    # ---- 3. Final synthesis activity ------------------------------------ #
    chain.add(
        started_at=(datetime.now(timezone.utc) + timedelta(seconds=step_start_offset)).isoformat(),
        ended_at=(datetime.now(timezone.utc) + timedelta(seconds=step_start_offset + 2)).isoformat(),
        tool_name="flybrain-connectome",
        tool_version=provenance.get("schema_version", MOTIF_PROVENANCE_SCHEMA_VERSION),
        operation="virtual_organism_synthesis",
        inputs=[f"motif:{bp}" for bp in provenance.get("blueprints_used", [])] or ["MaleCNS_v1.0.tsv"],
        input_formats=["JSON"] * (len(provenance.get("blueprints_used", [])) or 1),
        outputs=[org_name],
        output_formats=["JSON"],
        arguments=(f"--n-modules={spec.get('n_modules') if spec else None} "
                   f"--blueprint={','.join(provenance.get('blueprints_used', []))}"),
        drl=6,
    )

    # ---- 4. Attribution: dataset → FlyCellAtlas ------------------------- #
    # Attribute the MaleCNS dataset entity to FlyCellAtlas (the data provider)
    try:
        chain.add_attribution(
            files=["MaleCNS_v1.0.tsv"],
            file_formats=["TSV"],
            agent_name="FlyCellAtlas",
            agent_type="prov:Organization",
            role="dataset_provider",
        )
    except Exception:  # noqa: BLE001
        pass  # attribution is best-effort; not blocking PROV-JSON output

    # ---- 5. Save to string and return the dict -------------------------- #
    chain.save(f"_tmp_prov_{org_name}.json")
    with open(f"_tmp_prov_{org_name}.json") as f:
        prov = json.load(f)
    # Clean up temp file
    try:
        os.remove(f"_tmp_prov_{org_name}.json")
    except OSError:
        pass

    # Attach dataset anchor block for downstream consumers (kept out of PROV
    # proper because PROV is entity/activity-centric; this is metadata).
    prov["flybrain:dataset_anchor"] = {
        "name": dataset.get("name"),
        "license": dataset.get("license"),
        "total_synapses": dataset.get("total_synapses"),
        "annotated_neurons": dataset.get("annotated_neurons"),
        "dataset_url": dataset.get("dataset_url"),
        "annotation_version": dataset.get("annotation_version"),
        "bio_prior_count": provenance.get("bio_prior_count"),
        "total_blueprint_count": provenance.get("total_blueprint_count"),
    }
    return prov


# --------------------------------------------------------------------------- #
# v1.2.0 helpers: synapse stats + query — three-stage provenance
# --------------------------------------------------------------------------- #
def _motif_synapse_stats(motif_name: str, entry: dict) -> dict | None:
    """Return dataset-derived synapse statistics for a given motif.

    Numbers are the real MaleCNS v1.0 anchor points this project has
    already verified in prior phases (see MEMORY.md / FAULT_ISOLATION_REPORT.md).
    Consumers can use these to answer "how much of the 124M synapses does
    this blueprint actually reflect?" — a question no other agent-team
    framework can answer.
    """
    if motif_name == "inhibitory_hub":
        return {
            "source_neuron_id": entry.get("motif_body"),
            "source_superclass": entry.get("motif_type"),
            "fanout": entry.get("motif_fanout"),
            "percent_of_dataset_synapses": (
                round(entry.get("motif_fanout", 0) / 124177617 * 100, 6)
                if entry.get("motif_fanout") else None
            ),
            "note": ("Single-neuron fan-out broadcast pattern; represents "
                     "the APL body 10540 as a canonical inhibitory hub."),
        }
    if motif_name == "recurrent_feedback":
        return {
            "class_superclass": entry.get("motif_type"),
            "self_loop_share": 0.2874,
            "estimated_self_loops": 40707,
            "percent_of_dataset_synapses": 0.2874,
            "note": ("ol_intrinsic self-loop fraction of 28.74% (MaleCNS v1.0 "
                     "verified). Encodes predictive/feedback recursion motif."),
        }
    if motif_name == "reservoir_smallworld":
        return {
            "class_share": 0.4936,
            "total_in_class": 82190,
            "fanout_range": [101, 1000],
            "percent_of_annotated_neurons": 0.4936,
            "note": ("Fanout-101-to-1000 neurons represent 49.36% of annotated "
                     "neurons. Small-world reservoir = layered cortical hierarchy."),
        }
    return None


def _default_stability_target(motif_name: str) -> float | None:
    """Fallback cross-module edge ratio upper bound per motif.

    Used when a blueprint entry does not override stability_target explicitly.
    Lower = stricter isolation expectation. These defaults match the F1/F3
    measurement results in diagnostics/FAULT_ISOLATION_REPORT.md.
    """
    if motif_name == "inhibitory_hub":
        return 0.15
    if motif_name == "recurrent_feedback":
        return 0.25
    if motif_name == "reservoir_smallworld":
        return 0.25
    return 0.25  # "none" / unknown — conservative default


def _motif_query(motif_name: str, entry: dict) -> str | None:
    """Return a runnable SQL-like query against MaleCNS v1.0 for this motif.

    These are illustrative queries — the exact schema depends on the MaleCNS
    data layout, but the intent (which neuron / synapse rows to select) is
    unambiguous and directly traceable.
    """
    if motif_name == "inhibitory_hub":
        return (
            "SELECT target_neuron_id FROM male_cns.synapses "
            f"WHERE source_neuron_id = {entry.get('motif_body')} LIMIT 5"
        )
    if motif_name == "recurrent_feedback":
        superclass = entry.get("motif_type") or "ol_intrinsic"
        return (
            "SELECT source_neuron_id FROM male_cns.synapses "
            f"WHERE source_neuron_id = target_neuron_id "
            f"AND superclass = '{superclass}' LIMIT 5"
        )
    if motif_name == "reservoir_smallworld":
        return (
            "SELECT neuron_id FROM male_cns.neurons "
            "WHERE fanout BETWEEN 101 AND 1000 LIMIT 5"
        )
    return None


def _normalize_blueprint_spec(spec):
    """Normalize a blueprint spec into (flat_names, display_label).

    Supports NESTED composition such as ``"a+(b+c)"`` by stripping parentheses
    while preserving the original string for provenance/display. The flat name
    list drives edge generation; nested vs flat composition therefore yield
    identical topologies (a set-union of cross-edge rules), which is the
    intended behavior — composition is an order-independent union of rules.

    Returns ``([], "")`` for empty/absent specs.
    """
    if not spec:
        return [], ""
    if isinstance(spec, (list, tuple)):
        names = [str(s).strip() for s in spec if str(s).strip()]
        return names, "+".join(names)
    s = str(spec).strip()
    flat = re.sub(r"[()]", "", s)  # "a+(b+c)" -> "a+b+c"
    names = [p.strip() for p in re.split(r"[+,]", flat) if p.strip()]
    return names, s


def _apply_blueprint(nodes: list[dict], edges: list[dict],
                     module_profile_map: dict[int, dict],
                     blueprint_spec) -> int:
    """Append cross-module edges defined by blueprint(s) between module leads.

    Only module REPRESENTATIVES (tissue_rep) are used as endpoints — cells
    stay internal to their module. This keeps the blueprint topology legible
    in the swarm spec and matches how biological inter-regional wiring works
    (regional hubs talk to regional hubs, not cell-to-cell).

    blueprint_spec can be:
        - None: no blueprint (return 0)
        - str: single name, comma/plus-separated names ("a+b" or "a,b"),
          or NESTED composition ("a+(b+c)") — all equivalent under union.
        - list[str]: multiple names

    Composition rules:
        - Rules from all named blueprints are concatenated.
        - Deduplicated on (from_profile, to_profile, kind, semantic).
        - When duplicates exist, the rule with higher |weight| wins.
        - The `blueprint` tag on each appended edge is the composition label
          "a+b" (or "a" for single, matching CLI).

    Returns the number of cross edges appended.
    """
    names, _label = _normalize_blueprint_spec(blueprint_spec)
    if not names:
        return 0

    # collect all cross-edge rules, deduplicating identical rules
    seen: dict[tuple, dict] = {}
    used_names: list[str] = []
    for name in names:
        if name not in BLUEPRINTS:
            continue
        used_names.append(name)
        for rule in BLUEPRINTS[name]["cross_edges"]:
            key = (rule["from_profile"], rule["to_profile"],
                   rule["kind"], rule["semantic"])
            prev = seen.get(key)
            if prev is None or abs(rule["weight"]) > abs(prev["weight"]):
                seen[key] = dict(rule)  # shallow copy — no aliasing

    deduped = list(seen.values())
    if not deduped or not used_names:
        return 0

    # composition label for tagging
    label = "+".join(used_names)

    # collect lead ids per profile name
    leads_by_profile: dict[str, list[str]] = {}
    for m, prof in module_profile_map.items():
        pname = prof.get("name", "default")
        leads_by_profile.setdefault(pname, []).append("m%d_rep" % m)

    added = 0
    for rule in deduped:
        from_prof = rule["from_profile"]
        to_prof = rule["to_profile"]
        srcs = leads_by_profile.get(from_prof, [])
        tgts = leads_by_profile.get(to_prof, [])
        # Phase 4: 变体 profile 前缀匹配
        # 当 blueprint 规则指定 "sensory" 时，变体 profile "sensory_vision"/"sensory_sound"
        # 也应匹配（变体是同模块的参数覆盖，功能相同）
        if not srcs:
            # Flatten: leads_by_profile[k] is a list of lead IDs, extend not append
            srcs = []
            for k, v in leads_by_profile.items():
                if k == from_prof or k.startswith(from_prof + "_"):
                    srcs.extend(v)
        if not tgts:
            tgts = []
            for k, v in leads_by_profile.items():
                if k == to_prof or k.startswith(to_prof + "_"):
                    tgts.extend(v)
        if not srcs or not tgts:
            continue
        if rule.get("fanout"):
            for s in srcs:
                for t in tgts:
                    if s == t:
                        continue
                    edges.append({"from": s, "to": t,
                                  "weight": rule["weight"],
                                  "kind": rule["kind"],
                                  "blueprint": label,
                                  "semantic_hint": rule["semantic"]})
                    added += 1
        else:
            for i in range(min(len(srcs), len(tgts))):
                s, t = srcs[i], tgts[i]
                if s == t:
                    continue
                edges.append({"from": s, "to": t,
                              "weight": rule["weight"],
                              "kind": rule["kind"],
                              "blueprint": label,
                              "semantic_hint": rule["semantic"]})
                added += 1
    return added


def _blueprint_info(blueprint_spec) -> dict | None:
    """Build a human-readable info dict for a blueprint (single or composed).

    For "a+b", each component contributes its description and use_cases;
    the label preserves the composition order.
    """
    if not blueprint_spec:
        return None
    if isinstance(blueprint_spec, str):
        parts, label = _normalize_blueprint_spec(blueprint_spec)
    elif isinstance(blueprint_spec, (list, tuple)):
        parts = [str(p) for p in blueprint_spec]
        label = "+".join(parts)
    else:
        return None

    components = []
    for name in parts:
        bp = BLUEPRINTS.get(name)
        if bp is None:
            continue
        components.append({
            "name": name,
            "category": bp.get("category", "basic"),
            "description": bp.get("description"),
            "use_cases": bp.get("use_cases", []),
        })

    return {
        "label": label,
        "is_composed": len(components) > 1,
        "n_components": len(components),
        "components": components,
    }


# ====================================================================== #
# Motif resolution — A: runtime service pull, snapshot only as fallback
# ====================================================================== #
class MotifSourceError(RuntimeError):
    """Raised when the requested motif source cannot be satisfied."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _doc_sha256(doc: dict) -> str:
    canon = json.dumps(doc, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _validate_motif_doc(doc: dict, origin: str) -> dict:
    if not isinstance(doc, dict) or not isinstance(doc.get("motifs"), dict):
        raise MotifSourceError("%s did not return a motif document" % origin)
    missing = [m for m in REQUIRED_MOTIFS if m not in doc["motifs"]]
    if missing:
        raise MotifSourceError("%s motif doc missing %s" % (origin, missing))
    return doc


def _write_api_cache(doc: dict, cache_path: Path) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass  # a warm cache is a convenience, never a correctness requirement


def resolve_motifs(source: str = "auto", api_url: str | None = None,
                   api_key: str | None = None, refresh: bool = False,
                   snapshot_path: Path | None = None,
                   cache_path: Path | None = None, timeout: int = 120,
                   save_snapshot: bool = False, verbose: bool = True):
    """Resolve the motif document at runtime and return (doc, provenance).

    source:
        "api"   -> service only; raises MotifSourceError if unreachable
        "auto"  -> service -> warm API cache -> committed snapshot
        "local" -> committed snapshot only (never touches the network)
    """
    if source not in MOTIF_SOURCES:
        raise ValueError("motif source must be one of %s" % (MOTIF_SOURCES,))
    snapshot_path = Path(snapshot_path or MOTIF_FILE)
    cache_path = Path(cache_path or API_CACHE_FILE)

    prov = {
        "requested_source": source,
        "mode": None,                 # api | api_cache | local_snapshot
        "transport": None,            # http | file
        "api_url": api_url or DEFAULT_BASE_URL,
        "api_tool": "export_swarm_motifs",
        "api_refresh_requested": bool(refresh),
        "api_key_source": None,       # arg | env | local_config | none
        "resolved_utc": _now(),
        "motif_generated_utc": None,
        "motifs": [],
        "doc_sha256": None,
        "served_from": None,
        "fallback_reason": None,
        "snapshot_path": str(snapshot_path),
        "snapshot_sha256": None,
        "api_cache_path": str(cache_path),
    }

    # key precedence: explicit arg -> FLYBRAIN_API_KEY -> same-machine local config
    if api_key:
        _key, _key_src = api_key, "arg"
    elif os.environ.get("FLYBRAIN_API_KEY"):
        _key, _key_src = os.environ["FLYBRAIN_API_KEY"], "env"
    else:
        _key, _key_src = resolve_local_api_key()
    prov["api_key_source"] = _key_src

    def _finish(doc: dict, mode: str, transport: str, served_from: str,
                fallback_reason: str | None = None):
        prov.update(
            mode=mode, transport=transport, served_from=served_from,
            motif_generated_utc=doc.get("generated_utc"),
            motifs=sorted(doc.get("motifs", {}).keys()),
            doc_sha256=_doc_sha256(doc),
        )
        if mode == "api" and save_snapshot:
            try:
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                with open(snapshot_path, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh, ensure_ascii=False, indent=2)
                prov["snapshot_path"] = str(snapshot_path)
                prov["snapshot_sha256"] = _sha256_file(snapshot_path)
                prov["snapshot_refreshed"] = True
            except OSError:
                prov["snapshot_refreshed"] = False
        else:
            prov["snapshot_refreshed"] = False
        if fallback_reason:
            prov["fallback_reason"] = fallback_reason
        if mode != "api":
            prov["snapshot_sha256"] = _sha256_file(snapshot_path)
        if verbose:
            print("[C1] motif source=%s mode=%s from=%s sha256=%s" % (
                source, mode, served_from, (prov["doc_sha256"] or "")[:12]),
                flush=True)
            if fallback_reason:
                print("[C1]   fallback because: %s" % fallback_reason, flush=True)
        return doc, prov

    # ---- local only ------------------------------------------------- #
    if source == "local":
        if not snapshot_path.exists():
            raise MotifSourceError("snapshot not found: %s" % snapshot_path)
        doc = _validate_motif_doc(_read_json(snapshot_path), "snapshot")
        return _finish(doc, "local_snapshot", "file", str(snapshot_path))

    # ---- api / auto: try the live service --------------------------- #
    api_error: str | None = None
    try:
        client = FlybrainHTTPClient(api_url, _key, timeout=timeout)
        doc = _validate_motif_doc(client.export_swarm_motifs(refresh=refresh),
                                  "service export_swarm_motifs")
        _write_api_cache(doc, cache_path)
        return _finish(doc, "api", "http", "service:%s" % client.base,
                       fallback_reason=None)
    except (FlybrainUnavailable, MotifSourceError) as e:
        api_error = "%s: %s" % (type(e).__name__, " ".join(str(e).split()))
        # An AUTH failure is a configuration mistake, not an outage. Degrading
        # silently would hide a wrong/missing key behind a stale snapshot, so we
        # always fail loudly — use --motif-source local for a deliberate offline run.
        if getattr(e, "auth", False):
            raise MotifSourceError(
                "flybrain 服务拒绝了鉴权（401/403）——这是配置问题，不是服务故障，"
                "故不降级。请设置环境变量 FLYBRAIN_API_KEY、或用 --api-key 显式传 key；"
                "确需离线请改用 --motif-source local。原始错误：%s" % api_error) from e
        if source == "api":
            raise MotifSourceError(
                "motif-source=api requires a live flybrain service at %s — %s. "
                "Start it with run_api.py (see SWARMLABS_INTEGRATION.md)."
                % (api_url or DEFAULT_BASE_URL, api_error)) from e
        if verbose:
            print("[C1] service unavailable (%s) -> falling back" % api_error,
                  flush=True)

    # ---- auto: warm API cache, then committed snapshot --------------- #
    if cache_path.exists():
        try:
            doc = _validate_motif_doc(_read_json(cache_path), "api cache")
            return _finish(doc, "api_cache", "file", str(cache_path),
                           fallback_reason=api_error)
        except MotifSourceError as e:
            api_error = "%s; cache unusable (%s)" % (api_error, e)

    if not snapshot_path.exists():
        raise MotifSourceError(
            "no live service (%s) and no usable snapshot at %s"
            % (api_error, snapshot_path))
    doc = _validate_motif_doc(_read_json(snapshot_path), "snapshot")
    return _finish(doc, "local_snapshot", "file", str(snapshot_path),
                   fallback_reason=api_error)


def load_motifs(path: Path = MOTIF_FILE) -> dict:
    """Backwards-compatible offline loader (unchanged behaviour)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ====================================================================== #
# Organism design (unchanged semantics)
# ====================================================================== #
def design_organism(spec: dict, motifs: dict | None = None,
                    seed: int = 0) -> dict:
    """Compose a virtual organism graph from a morphology spec.

    spec keys:
        n_modules (int, default 4)            -- "tissues / organs"
        agents_per_module (int, default 6)    -- "cells" per tissue
        use_inhibitory_coordinator (bool T)   -- global guardrail hub (fly APL)
        use_reservoir_buffer (bool T)         -- cross-module small-world memory
        use_recurrent_memory (bool T)         -- per-tissue self-loop memory
        recurrent_pct (float 0..1, default .28)-- global recurrence weight
        module_profiles (dict|None)           -- per-module profile assignment
            key: "uniform" | "cycled" | "custom"
            value: dict {module_index: profile_name} for custom
    """
    motifs = motifs or load_motifs()
    rng = random.Random(seed)
    spec = dict(spec)
    n_modules = int(spec.get("n_modules", 4))
    apm = int(spec.get("agents_per_module", 6))
    use_inh = bool(spec.get("use_inhibitory_coordinator", True))
    use_res = bool(spec.get("use_reservoir_buffer", True))
    use_rec = bool(spec.get("use_recurrent_memory", True))
    rec_pct_global = float(spec.get("recurrent_pct", 0.287))

    # ---- resolve module profiles ----
    profiles_spec = spec.get("module_profiles")
    module_profile_map = {}  # module_index -> profile dict
    if profiles_spec is None:
        # default: cycle through all 4 profiles
        for m in range(n_modules):
            pname = DEFAULT_PROFILE_CYCLE[m % len(DEFAULT_PROFILE_CYCLE)]
            module_profile_map[m] = dict(MODULE_PROFILES[pname], name=pname)
    elif isinstance(profiles_spec, str) and profiles_spec == "uniform":
        # legacy behaviour: all modules identical
        for m in range(n_modules):
            module_profile_map[m] = dict(MODULE_PROFILES["integration"], name="uniform")
            module_profile_map[m]["reservoir_density"] = 0.25
            module_profile_map[m]["recurrent_pct"] = rec_pct_global
            module_profile_map[m]["has_inhibition"] = False
    elif isinstance(profiles_spec, str) and profiles_spec == "cycled":
        for m in range(n_modules):
            pname = DEFAULT_PROFILE_CYCLE[m % len(DEFAULT_PROFILE_CYCLE)]
            module_profile_map[m] = dict(MODULE_PROFILES[pname], name=pname)
    elif isinstance(profiles_spec, dict):
        # custom assignment: {module_index: profile_name}
        for m in range(n_modules):
            pname = profiles_spec.get(str(m), DEFAULT_PROFILE_CYCLE[m % len(DEFAULT_PROFILE_CYCLE)])
            if pname not in MODULE_PROFILES:
                pname = "integration"
            module_profile_map[m] = dict(MODULE_PROFILES[pname], name=pname)
    else:
        for m in range(n_modules):
            module_profile_map[m] = dict(MODULE_PROFILES["integration"], name="default")

    nodes, edges = [], []
    module_reps = []

    # ---- per-tissue cells + representative + recurrent memory ----
    for m in range(n_modules):
        prof = module_profile_map[m]
        rec_pct = float(prof.get("recurrent_pct", rec_pct_global))
        has_inh = bool(prof.get("has_inhibition", False))

        for a in range(apm):
            # schema v1.1: derive task_hint from module profile pool
            pool = prof.get("task_hint_pool", [])
            hint = pool[a % len(pool)] if pool else "generic_task"
            nodes.append({"id": "m%d_a%d" % (m, a), "role": "cell",
                          "module": m, "profile": prof.get("name", "default"),
                          "task_hint": hint})
        rep = "m%d_rep" % m
        nodes.append({"id": rep, "role": "tissue_rep", "module": m,
                      "profile": prof.get("name", "default"),
                      "task_hint": prof.get("lead_task_hint", "module_lead")})
        module_reps.append(rep)
        if use_rec:
            edges.append({"from": rep, "to": rep, "weight": round(rec_pct, 3),
                          "kind": "recurrent", "module": m})

    # ---- cross-tissue reservoir (per-module density) ----
    if use_res:
        for m in range(n_modules):
            prof = module_profile_map[m]
            density = float(prof.get("reservoir_density", 0.25))
            # collect all node ids in this module + random cross-module targets
            all_ids = [n["id"] for n in nodes]
            mod_ids = [n["id"] for n in nodes if n.get("module") == m]
            for src in mod_ids:
                if rng.random() < density:
                    # 70% intra-module, 30% cross-module (small-world shortcut)
                    if rng.random() < 0.70:
                        candidates = [x for x in mod_ids if x != src]
                    else:
                        candidates = [x for x in all_ids if x != src]
                    if candidates:
                        tgt = rng.choice(candidates)
                        edges.append({"from": src, "to": tgt,
                                      "weight": round(rng.random(), 3),
                                      "kind": "reservoir", "module": m})

    # ---- local inhibitory (per-module, if profile has it) ----
    for m in range(n_modules):
        prof = module_profile_map[m]
        if bool(prof.get("has_inhibition", False)) and use_inh:
            rep = module_reps[m]
            # inhibit 2-3 random cells within the same module
            mod_cells = [n["id"] for n in nodes if n.get("module") == m and n["role"] == "cell"]
            n_inh = min(len(mod_cells), rng.randint(2, 3))
            for tgt in rng.sample(mod_cells, n_inh):
                edges.append({"from": rep, "to": tgt,
                              "weight": round(-rng.uniform(0.2, 0.6), 3),
                              "kind": "inhibitory", "module": m})

    # ---- global inhibitory coordinator (from inhibitory_hub / APL) ----
    if use_inh:
        nodes.append({"id": "coordinator", "role": "guardrail",
                      "source": "APL(body %d)" % _apl_body(motifs),
                      "task_hint": "global_guardrail"})
        for i, rep in enumerate(module_reps):
            w = round((n_modules - i) / max(n_modules, 1), 3)
            edges.append({"from": "coordinator", "to": rep, "weight": -w,
                          "kind": "inhibitory", "module": i})

    # ---- cross-module blueprint (dimension 3: how modules collaborate) ----
    blueprint_name = spec.get("blueprint")
    n_blueprint_edges = _apply_blueprint(nodes, edges, module_profile_map, blueprint_name)

    organism = {"nodes": nodes, "edges": edges}
    metrics = _metrics(organism, n_modules, module_profile_map)
    _org_for_prov = {
        "schema_version": SCHEMA_VERSION,
        "kind": "virtual_organism",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_motifs": "MaleCNS v1.0 derived (inhibitory_hub / "
                         "reservoir_smallworld / recurrent_feedback)",
        "spec": spec,
        "blueprint": blueprint_name,
        "blueprint_edges_added": n_blueprint_edges,
        "motif_provenance": _motif_provenance({"blueprint": blueprint_name}),
        "module_profiles": {m: {"name": p["name"], "description": p.get("description", "")}
                            for m, p in module_profile_map.items()},
        "organism": organism,
        "metrics": metrics,
        # T4: every artifact carries its own structural signature, so two
        # artifacts are comparable for structural identity and a renamed copy
        # of the same wiring is recognisable as a duplicate.
        "topology_profile": _structural_profile(organism),
    }
    _org_for_prov["prov_json"] = _prov_json(
        _org_for_prov["motif_provenance"],
        organism_name="flybrain_organism",
        spec=spec,
    )
    return _org_for_prov


def _apl_body(motifs: dict | None) -> int:
    """Real APL body id from the motif doc (no hard-coded magic number)."""
    try:
        return int(motifs["motifs"]["inhibitory_hub"]["hub_body"])
    except Exception:  # noqa: BLE001
        return 10540


def _metrics(org: dict, n_modules: int, module_profile_map: dict | None = None) -> dict:
    nodes = org["nodes"]
    edges = org["edges"]
    n = len(nodes)
    e = len(edges)
    neg = sum(1 for x in edges if x["weight"] < 0)
    # module membership lookup
    mem = {nd["id"]: nd.get("module") for nd in nodes}
    intra = sum(1 for x in edges
                if mem.get(x["from"]) == mem.get(x["to"]) and mem.get(x["from"]) is not None)
    inter = e - intra
    modularity = round(intra / e, 3) if e else 0.0

    # per-profile edge counts
    profile_edges: dict[str, dict] = {}
    node_profile = {nd["id"]: nd.get("profile", "uniform") for nd in nodes}
    for prof_name in (module_profile_map or {}).values():
        pname = prof_name.get("name", "unknown")
        profile_edges.setdefault(pname, {"nodes": 0, "edges": 0})
    for nd in nodes:
        pname = nd.get("profile", "uniform")
        profile_edges.setdefault(pname, {"nodes": 0, "edges": 0})
        profile_edges[pname]["nodes"] += 1
    for ed in edges:
        src_prof = node_profile.get(ed["from"], "uniform")
        profile_edges.setdefault(src_prof, {"nodes": 0, "edges": 0})
        profile_edges[src_prof]["edges"] += 1

    return {
        "n_nodes": n,
        "n_edges": e,
        "avg_degree": round(2 * e / n, 3) if n else 0.0,
        "inhibition_ratio": round(neg / e, 3) if e else 0.0,
        "n_modules": n_modules,
        "intra_module_edges": intra,
        "inter_module_edges": inter,
        "modularity_est": modularity,
        "profile_breakdown": {
            k: v for k, v in profile_edges.items()
        },
    }


def _structural_profile(org: dict) -> dict:
    """Structural profile + deterministic signature of a generated organism.

    T4 of the foundation roadmap asks that every generated artifact *carry* its
    structural signature, so that two artifacts can be compared for structural
    identity without re-deriving anything, and so a renamed copy of the same
    topology is recognisable as a duplicate. The profile itself is computed by
    ``topology_profile`` (stdlib only, power-iteration spectral radius) and is
    a property of the wiring diagram alone.

    Degrades to ``{"status": "unavailable", "reason": ...}`` rather than
    raising: provenance and generation must never break because a structural
    convenience is missing — but the honest reason is recorded so nobody reads
    a missing signature as a missing structure.
    """
    try:
        from topology_profile import profile as _profile
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "reason": "topology_profile import failed: %r" % (exc,)}
    try:
        prof = _profile(dict(org))
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "reason": "profile computation failed: %r" % (exc,)}
    return {
        "status": "ok",
        "signature": prof.get("profile_signature"),
        "size": prof.get("size", {}),
        "spectral_radius": prof.get("spectral_radius"),
        "modularity_q": prof.get("modularity_q"),
        "reciprocity": prof.get("reciprocity"),
        "feedback_edge_fraction": prof.get("feedback_edge_fraction"),
        "not_measured": prof.get("not_measured", []),
    }


def evolve_organism(target_metric: str = "n_nodes",
                    target_value: float = 40, generations: int = 60,
                    seed: int = 0, motifs: dict | None = None) -> dict:
    """Random search over morphology params to hit a target metric.

    target_metric in {n_nodes, n_edges, inhibition_ratio, modularity_est}.
    Returns the best organism dict + the search history (for transparency).
    """
    motifs = motifs or load_motifs()
    rng = random.Random(seed)
    best = None
    best_err = float("inf")
    history = []
    for g in range(generations):
        cand = {
            "n_modules": rng.randint(2, 8),
            "agents_per_module": rng.randint(3, 20),
            "use_inhibitory_coordinator": True,
            "use_reservoir_buffer": True,
            "use_recurrent_memory": True,
            "recurrent_pct": round(rng.uniform(0.1, 0.4), 3),
        }
        org = design_organism(cand, motifs=motifs, seed=g)
        val = org["metrics"].get(target_metric, 0)
        err = abs(val - target_value)
        history.append({"gen": g, "spec": cand, "value": val, "err": round(err, 3)})
        if err < best_err:
            best_err, best = err, org
    return {"best": best, "best_err": round(best_err, 3),
            "target_metric": target_metric, "target_value": target_value,
            "history": history[-8:]}


def save_organism(org: dict, name: str, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / ("%s.json" % name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(org, f, ensure_ascii=False, indent=2)
    return p


# ====================================================================== #
# B — SwarmLabs instantiable agent-swarm config
# ====================================================================== #
# organism role -> SwarmLabs agentteams role contract
SWARM_ROLE_MAP = {
    "guardrail": "verifier",     # negative-weight watchdog
    "tissue_rep": "planner",     # module lead / coordinator
    "cell": "executor",          # does the work
    "reservoir": "executor",
    "module": "planner",
    "worker": "executor",
}

# mirrors swarmlabs/agentteams/config/team.yaml so the emitted config is
# self-describing and stays numerically consistent with the SwarmLabs runtime.
SWARM_THRESHOLDS = {
    "rel_converged": 0.05,
    "cov_min": 0.8,
    "cal_max": 0.08,
    "cov_bad": 0.7,
    "rel_bad": 0.2,
}


def build_swarmlabs_config(org: dict, name: str | None = None,
                           provenance: dict | None = None) -> dict:
    """Translate a virtual organism into a SwarmLabs-instantiable swarm spec."""
    nodes = org.get("organism", {}).get("nodes", [])
    edges = org.get("organism", {}).get("edges", [])
    ids = {nd["id"] for nd in nodes}

    agents = []
    for nd in nodes:
        a = {
            "id": nd["id"],
            "role": nd.get("role"),
            "swarm_role": SWARM_ROLE_MAP.get(nd.get("role"), "executor"),
        }
        if nd.get("module") is not None:
            a["module"] = nd["module"]
        # schema v1.1: propagate task_hint and profile_name from organism nodes
        if nd.get("task_hint") is not None:
            a["task_hint"] = nd["task_hint"]
        if nd.get("profile") is not None:
            a["profile_name"] = nd["profile"]
        for k in ("source", "ref_body", "ref_type", "ref_superclass"):
            if nd.get(k) is not None:
                a[k] = nd[k]
        agents.append(a)

    # leader = the guardrail hub if present, else the first module lead
    leader = next((a["id"] for a in agents if a["role"] == "guardrail"), None)
    if leader is None:
        leader = next((a["id"] for a in agents if a["role"] == "tissue_rep"), None)

    # module view: lead + members + recurrent weight + capability (schema v1.1)
    modules: dict[int, dict] = {}
    for nd in nodes:
        m = nd.get("module")
        if m is None:
            continue
        mod = modules.setdefault(m, {"index": m, "lead": None,
                                     "members": [], "recurrent_weight": None,
                                     "profile_name": None,
                                     "capability": []})
        if nd.get("role") == "tissue_rep":
            mod["lead"] = nd["id"]
        else:
            mod["members"].append(nd["id"])
        # remember profile_name from any agent in this module
        if nd.get("profile") is not None and mod["profile_name"] is None:
            mod["profile_name"] = nd["profile"]
    for e in edges:
        if e.get("kind") == "recurrent" and e.get("module") is not None:
            if e["module"] in modules:
                modules[e["module"]]["recurrent_weight"] = e["weight"]
    # back-fill capability from MODULE_PROFILES lookup (by profile_name)
    for m_idx, mod in modules.items():
        pname = mod.get("profile_name")
        prof = MODULE_PROFILES.get(pname) if pname else None
        if prof is not None:
            mod["capability"] = list(prof.get("capability", []))

    norm_edges = []
    for e in edges:
        kind = e.get("kind", "plain")
        # schema v1.1: semantic — the runtime communication meaning of this edge.
        # Blueprint edges carry a semantic_hint that is more specific than the
        # kind-based default; prefer it when present.
        semantic_hint = e.get("semantic_hint")
        if semantic_hint:
            semantic = semantic_hint
        elif kind == "reservoir":
            semantic = "data_share"
        elif kind == "recurrent":
            semantic = "state_feedback"
        elif kind == "inhibitory":
            semantic = "halt"
        else:
            semantic = "message_pass"
        item = {"from": e["from"], "to": e["to"], "weight": e["weight"],
                "kind": kind, "semantic": semantic}
        if e.get("module") is not None:
            item["module"] = e["module"]
        if e.get("blueprint") is not None:
            item["blueprint"] = e["blueprint"]
        norm_edges.append(item)

    guardrails = [
        "leader(guardrail) 不得同时是任何 module 的成员（抑制枢纽必须外部于被抑制者）",
        "weight < 0 的边是硬刹车：执行器不得用正向权重抵消或删除该边",
        "recurrent 边只允许模块内自环，禁止跨模块复用",
        "任何 agent 的入/出边端点必须存在于 agents 列表中（无悬空边）",
        "边权一律落在 [-1, 1]；本文件是唯一真值，运行时不接受就地改权",
    ]

    weights = [e["weight"] for e in norm_edges] or [0.0]
    dangling = [e for e in norm_edges if e["from"] not in ids or e["to"] not in ids]
    validation = {
        "n_agents": len(agents),
        "n_edges": len(norm_edges),
        "n_modules": len(modules),
        "leader_resolved": leader,
        "leader_is_module_member": (
            leader in {mid for mod in modules.values() for mid in mod["members"]}
            if leader else False),
        "dangling_edges": len(dangling),
        "weight_min": min(weights),
        "weight_max": max(weights),
        "weights_in_range": all(-1.0 <= w <= 1.0 for w in weights),
        "inhibitory_edges": sum(1 for e in norm_edges if e["kind"] == "inhibitory"),
        "recurrent_edges": sum(1 for e in norm_edges if e["kind"] == "recurrent"),
        "reservoir_edges": sum(1 for e in norm_edges if e["kind"] == "reservoir"),
    }
    validation["ok"] = (
        validation["dangling_edges"] == 0
        and validation["weights_in_range"]
        and bool(validation["leader_resolved"])
        and not validation["leader_is_module_member"]
    )

    return {
        # v1.1 adds: agent.task_hint, agent.profile_name, edge.semantic,
        # module.capability, module.profile_name — all additive; v1.0 consumers
        # that ignore these fields still parse correctly.
        # v1.1.1 adds: motif_provenance (blueprint → real motif → real neuron),
        # the architectural guarantee that differentiates flybrain from
        # LangGraph/AutoGen/CrewAI.
        # v1.2.0 adds: three-stage provenance (motif_synapse_stats + motif_query),
        # per-blueprint stability_target, cross-blueprint stability_summary —
        # enables CI-level module-isolation verification.
        # v1.2.1 adds: prov_json (W3C PROV-JSON via dataprov) — standardized
        # provenance bundle ingestible by any W3C PROV-aware tool (yProv4ML,
        # MLflow2PROV, MIT Sloan Data Provenance Explorer, PROV-O SPARQL).
        # EU AI Act compliance hard gate: provenance must be W3C-standard.
        "schema_version": SCHEMA_VERSION,
        "kind": "swarmlabs_agent_swarm",
        "blueprint": org.get("blueprint"),
        "blueprint_info": _blueprint_info(org.get("blueprint")),
        "motif_provenance": org.get("motif_provenance") or _motif_provenance(org),
        "prov_json": (org.get("prov_json")
                      or _prov_json(org.get("motif_provenance") or _motif_provenance(org),
                                    organism_name=name or "flybrain_organism",
                                    spec=org.get("spec"))),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "name": name or "flybrain_organism",
        "swarm": {
            "name": name or "flybrain_organism",
            "topology": "guardrail-hub + module-cells + recurrent + reservoir",
            "runtime": "local",
            "source": {
                "project": "flybrain-connectome",
                "kind": org.get("kind", "virtual_organism"),
                "generated_utc": org.get("generated_utc"),
                "source_motifs": org.get("source_motifs"),
                "motif_provenance": provenance or org.get("motif_provenance"),
            },
            "agentteams": {
                "team_file": "agentteams/config/team.yaml",
                "leader": leader,
                "role_map": SWARM_ROLE_MAP,
                "thresholds": SWARM_THRESHOLDS,
            },
            "agents": agents,
            "modules": [modules[k] for k in sorted(modules)],
            "edges": norm_edges,
            "guardrails": guardrails,
            "metrics": org.get("metrics", {}),
            "validation": validation,
        },
    }


def _yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    s = str(v)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def yaml_dump(obj, indent: int = 0) -> str:
    """Minimal deterministic YAML emitter (block style, stdlib only).

    Deliberately supports exactly the shapes we emit: dict / list / str / int /
    float / bool / None. Every string is double-quoted so no value can ever be
    reinterpreted as YAML syntax.
    """
    pad = "  " * indent
    out: list[str] = []
    if isinstance(obj, dict):
        if not obj:
            return pad + "{}"
        for k, v in obj.items():
            if isinstance(v, dict) and v:
                out.append("%s%s:" % (pad, k))
                out.append(yaml_dump(v, indent + 1))
            elif isinstance(v, list) and v:
                out.append("%s%s:" % (pad, k))
                out.append(yaml_dump(v, indent + 1))
            elif isinstance(v, dict):
                out.append("%s%s: {}" % (pad, k))
            elif isinstance(v, list):
                out.append("%s%s: []" % (pad, k))
            else:
                out.append("%s%s: %s" % (pad, k, _yaml_scalar(v)))
    elif isinstance(obj, list):
        if not obj:
            return pad + "[]"
        for item in obj:
            if isinstance(item, dict) and item:
                first = True
                for k, v in item.items():
                    prefix = "%s- " % pad if first else "%s  " % pad
                    if isinstance(v, dict) and v:
                        out.append("%s%s:" % (prefix, k))
                        out.append(yaml_dump(v, indent + 2))
                    elif isinstance(v, list) and v:
                        out.append("%s%s:" % (prefix, k))
                        out.append(yaml_dump(v, indent + 2))
                    elif isinstance(v, dict):
                        out.append("%s%s: {}" % (prefix, k))
                    elif isinstance(v, list):
                        out.append("%s%s: []" % (prefix, k))
                    else:
                        out.append("%s%s: %s" % (prefix, k, _yaml_scalar(v)))
                    first = False
            elif isinstance(item, (dict, list)):
                out.append("%s-" % pad)
                out.append(yaml_dump(item, indent + 1))
            else:
                out.append("%s- %s" % (pad, _yaml_scalar(item)))
    else:
        out.append(pad + _yaml_scalar(obj))
    return "\n".join(out)


def emit_swarmlabs_config(org: dict, name: str,
                          out_dir: Path = SWARM_DIR,
                          provenance: dict | None = None) -> dict:
    """Write `<name>.swarm.json` + `<name>.swarm.yaml`. Returns the config."""
    cfg = build_swarmlabs_config(org, name=name, provenance=provenance)
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / ("%s.swarm.json" % name)
    yp = out_dir / ("%s.swarm.yaml" % name)
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    header = (
        "# SwarmLabs instantiable agent-swarm config — generated by C1\n"
        "# source project: flybrain-connectome (derived motifs only; raw neuron\n"
        "# data never leaves flybrain-connectome-mcp)\n"
        "# motif mode: %s | sha256: %s\n"
        "# load with: swarmlabs/agent_topology/load_organism_config.py\n"
        % ((provenance or {}).get("mode", "unknown"),
           ((provenance or {}).get("doc_sha256") or "n/a")[:16])
    )
    with open(yp, "w", encoding="utf-8") as fh:
        fh.write(header + yaml_dump(cfg) + "\n")
    cfg["_written"] = {"json": str(jp), "yaml": str(yp)}
    return cfg


# ====================================================================== #
# HTML preview (unchanged)
# ====================================================================== #
def render_html(org: dict, out_path: Path, title: str = "Virtual Organism") -> Path:
    """Write a self-contained interactive HTML (force-directed SVG) of the organism.

    No external dependencies — open in any browser. Nodes are draggable and show
    a hover tooltip with role / module / source. Edge colour encodes the bio-motif
    kind (inhibitory = red dashed, reservoir = blue, recurrent = teal).
    """
    out_path = Path(out_path)
    data = json.dumps(org, ensure_ascii=False)
    html = _HTML_TEMPLATE.replace("__TITLE__", title).replace("__DATA__", data)
    out_path.write_text(html, encoding="utf-8")
    return out_path


# ---- self-contained interactive HTML template (vanilla JS + SVG, no deps) ----
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>
  body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0f1117;color:#e6e6e6;}
  #wrap{display:flex;height:100vh;}
  #stage{flex:1;position:relative;overflow:hidden;}
  svg{width:100%;height:100%;display:block;background:radial-gradient(circle at 50% 45%,#161b26,#0f1117 70%);}
  #panel{width:290px;background:#171a23;padding:16px;box-sizing:border-box;overflow:auto;border-left:1px solid #2a2f3a;}
  #panel h2{font-size:15px;margin:0 0 8px;color:#fff;}
  .metric{display:flex;justify-content:space-between;font-size:12px;padding:3px 0;border-bottom:1px solid #232833;}
  .metric span:last-child{color:#8ab4ff;font-variant-numeric:tabular-nums;}
  .legend{font-size:11px;margin-top:12px;line-height:1.9;}
  .sw{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:6px;vertical-align:middle;}
  #tip{position:absolute;pointer-events:none;background:#000d;color:#fff;padding:6px 9px;border-radius:6px;font-size:11px;max-width:240px;display:none;z-index:5;line-height:1.5;}
  .node{cursor:grab;}
  .node:active{cursor:grabbing;}
  text{font-size:10px;fill:#cfd6e4;pointer-events:none;user-select:none;}
  .sub{font-size:11px;color:#7a8290;margin-top:14px;line-height:1.5;}
</style>
</head>
<body>
<div id="wrap">
  <div id="stage"><svg id="svg"></svg><div id="tip"></div></div>
  <div id="panel">
    <h2>__TITLE__</h2>
    <div id="metrics"></div>
    <div class="legend">
      <div><span class="sw" style="background:#e5484d"></span>护栏枢纽 guardrail（抑制）</div>
      <div><span class="sw" style="background:#f5a623"></span>组织代表 tissue_rep</div>
      <div><span class="sw" style="background:#7c5cff"></span>细胞 cell（按模块着色）</div>
      <div style="margin-top:6px"><span class="sw" style="background:#e5484d"></span>抑制边（负权·虚线）</div>
      <div><span class="sw" style="background:#4361ee"></span>储备池边 reservoir</div>
      <div><span class="sw" style="background:#2ec4b6"></span>递归记忆边 recurrent</div>
    </div>
    <div class="sub">拖拽节点可调整布局；悬停节点/边查看属性。拓扑由 MaleCNS v1.0 的 motif 引擎合成。</div>
  </div>
</div>
<script>
const org = __DATA__;
const svg = document.getElementById('svg');
const tip = document.getElementById('tip');
const NS = 'http://www.w3.org/2000/svg';
const W = ()=>svg.clientWidth, H = ()=>svg.clientHeight;

const m = org.metrics || {};
let mhtml = '';
for (const k in m){ mhtml += '<div class="metric"><span>'+k+'</span><span>'+m[k]+'</span></div>'; }
document.getElementById('metrics').innerHTML = mhtml;

const nodes = org.organism.nodes.map(n=>({...n, x:0,y:0,vx:0,vy:0, fx:null,fy:null}));
const idToIdx = {}; nodes.forEach((n,i)=>idToIdx[n.id]=i);
const N = nodes.length;
const edges = org.organism.edges.map(e=>({...e, s:idToIdx[e.from], t:idToIdx[e.to]}));

const palette = ['#7c5cff','#3a86ff','#06d6a0','#ffd166','#ef476f','#ff9f1c','#118ab2','#8338ec'];
function nodeColor(n){
  if(n.role==='guardrail') return '#e5484d';
  if(n.role==='tissue_rep') return '#f5a623';
  if(n.role==='cell') return palette[(n.module||0)%palette.length];
  if(n.role==='reservoir') return '#4cc9f0';
  return '#9aa3b2';
}
function nodeR(n){ if(n.role==='guardrail') return 15; if(n.role==='tissue_rep') return 11; if(n.role==='reservoir') return 7; return 6; }

const gE = document.createElementNS(NS,'g'); svg.appendChild(gE);
const gN = document.createElementNS(NS,'g'); svg.appendChild(gN);
const edgeEls = edges.map(e=>{ const l=document.createElementNS(NS,'line');
  l.setAttribute('stroke', e.kind==='inhibitory'?'#e5484d':(e.kind==='recurrent'?'#2ec4b6':'#4361ee'));
  l.setAttribute('stroke-width', Math.max(0.6, 2.4*Math.abs(e.weight)));
  if(e.kind==='inhibitory') l.setAttribute('stroke-dasharray','5 4');
  l.setAttribute('opacity','0.55'); gE.appendChild(l); return l; });
const nodeEls = nodes.map(n=>{ const g=document.createElementNS(NS,'g'); g.setAttribute('class','node');
  const c=document.createElementNS(NS,'circle'); c.setAttribute('r', nodeR(n)); c.setAttribute('fill', nodeColor(n));
  c.setAttribute('stroke','#0f1117'); c.setAttribute('stroke-width','1.5'); g.appendChild(c);
  const t=document.createElementNS(NS,'text'); t.setAttribute('text-anchor','middle'); t.setAttribute('dy','3');
  t.textContent=(n.id.length>11?n.id.slice(0,10)+'…':n.id); g.appendChild(t); gN.appendChild(g); return {g,c,t}; });

const R = ()=>svg.getBoundingClientRect();
let drag=null;
gN.querySelectorAll('.node').forEach((g,i)=>{
  g.addEventListener('mousedown', ev=>{ drag=nodes[i]; drag.fx=drag.x; drag.fy=drag.y; ev.preventDefault(); });
  g.addEventListener('mouseenter', ()=>{ const n=nodes[i]; tip.style.display='block';
    tip.innerHTML='<b>'+n.id+'</b><br>role: '+n.role+(n.module!==undefined?'<br>module: '+n.module:'')+(n.source?'<br>src: '+n.source:''); });
  g.addEventListener('mousemove', ev=>{ const r=R(); tip.style.left=(ev.clientX-r.left+12)+'px'; tip.style.top=(ev.clientY-r.top+12)+'px'; });
  g.addEventListener('mouseleave', ()=>{ tip.style.display='none'; });
});
window.addEventListener('mousemove', ev=>{ if(drag){ const r=R(); drag.fx=ev.clientX-r.left; drag.fy=ev.clientY-r.top; } });
window.addEventListener('mouseup', ()=>{ if(drag){ drag.fx=null; drag.fy=null; drag=null; } });
edgeEls.forEach((l,i)=>{ l.style.pointerEvents='stroke';
  l.addEventListener('mouseenter', ()=>{ const e=edges[i]; tip.style.display='block';
    tip.innerHTML=e.from+' → '+e.to+'<br>weight: '+e.weight+'<br>kind: '+e.kind; });
  l.addEventListener('mousemove', ev=>{ const r=R(); tip.style.left=(ev.clientX-r.left+12)+'px'; tip.style.top=(ev.clientY-r.top+12)+'px'; });
  l.addEventListener('mouseleave', ()=>{ tip.style.display='none'; }); });

let alpha=1;
function tick(){
  const cx=W()/2, cy=H()/2;
  for(let i=0;i<N;i++){ const a=nodes[i];
    if(a.fx!==null){ a.x=a.fx; a.y=a.fy; a.vx=0; a.vy=0; continue; }
    for(let j=0;j<N;j++){ if(i===j) continue; const b=nodes[j]; let dx=a.x-b.x, dy=a.y-b.y;
      let d2=dx*dx+dy*dy+0.01; let f=9000/d2; let d=Math.sqrt(d2); a.vx+=dx/d*f*alpha; a.vy+=dy/d*f*alpha; }
    a.vx+=(cx-a.x)*0.012*alpha; a.vy+=(cy-a.y)*0.012*alpha;
  }
  for(const e of edges){ const a=nodes[e.s], b=nodes[e.t]; let dx=b.x-a.x, dy=b.y-a.y;
    let d=Math.sqrt(dx*dx+dy*dy)+0.01; const L=72; const k=0.03*(1-Math.abs(e.weight)*0.6);
    const f=(d-L)*k; const fx=dx/d*f, fy=dy/d*f; a.vx+=fx; a.vy+=fy; b.vx-=fx; b.vy-=fy; }
  for(let i=0;i<N;i++){ const a=nodes[i]; if(a.fx!==null) continue;
    a.vx*=0.86; a.vy*=0.86; a.x+=a.vx; a.y+=a.vy; }
  alpha=Math.max(alpha*0.992, 0.02);
  edgeEls.forEach((l,i)=>{ const e=edges[i]; l.setAttribute('x1',nodes[e.s].x); l.setAttribute('y1',nodes[e.s].y);
    l.setAttribute('x2',nodes[e.t].x); l.setAttribute('y2',nodes[e.t].y); });
  nodeEls.forEach((el,i)=>{ const n=nodes[i]; el.g.setAttribute('transform','translate('+n.x+','+n.y+')'); });
  requestAnimationFrame(tick);
}
nodes.forEach((n,i)=>{ const a=2*Math.PI*i/N; n.x=W()/2+Math.min(W(),H())*0.32*Math.cos(a); n.y=H()/2+Math.min(W(),H())*0.32*Math.sin(a); });
tick();
</script>
</body>
</html>
"""


# ====================================================================== #
# CLI
# ====================================================================== #
def _parse_evolve(raw: str | None) -> tuple[str, float] | None:
    if not raw:
        return None
    if "=" not in raw:
        raise SystemExit("--evolve must look like METRIC=VALUE (e.g. n_nodes=40)")
    k, v = raw.split("=", 1)
    return k.strip(), float(v)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="C1 · fly-brain-motif-composed virtual organism generator")
    ap.add_argument("--motif-source", choices=MOTIF_SOURCES, default="auto",
                    help="api=require live service | auto=service then cache "
                         "then snapshot | local=offline snapshot only")
    ap.add_argument("--api-url", default=None, help="flybrain HTTP API base url")
    ap.add_argument("--api-key", default=None,
                    help="API key (falls back to env FLYBRAIN_API_KEY)")
    ap.add_argument("--refresh", action="store_true",
                    help="ask the service to re-run extract_motifs.py first")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--snapshot", default=None,
                    help="explicit snapshot path for the local fallback")
    ap.add_argument("--refresh-snapshot", action="store_true",
                    help="when the API pull succeeds, overwrite the committed "
                         "snapshot so the offline path stays fresh")
    ap.add_argument("--modules", type=int, default=4)
    ap.add_argument("--agents-per-module", type=int, default=6)
    ap.add_argument("--recurrent-pct", type=float, default=0.287)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--module-profiles", choices=("cycled", "uniform"),
                    default="cycled",
                    help="cycled=each module gets a different functional profile "
                         "(sensory/memory/motor/integration); uniform=legacy "
                         "behaviour (all modules identical)")
    ap.add_argument("--blueprint",
                    default="sequential",
                    help="cross-module topology blueprint (dimension 3). "
                         "Single: sequential | deep_reasoning | fast_reflex | "
                         "broad_explore | orchestrated | hierarchical | "
                         "lateral_inhibition | predictive_coding | "
                         "competitive_selection | none. "
                         "Composable: 'a+b+c' or 'a,b,c' — build blocks stack. "
                         "Duplicates deduplicated by (from,to,kind,semantic); "
                         "stronger weight wins.")
    ap.add_argument("--profile-sensory", action="store_true",
                    help="assign sensory profile to all modules")
    ap.add_argument("--profile-memory", action="store_true",
                    help="assign memory profile to all modules")
    ap.add_argument("--profile-motor", action="store_true",
                    help="assign motor profile to all modules")
    ap.add_argument("--evolve", default=None,
                    help="also run target search, e.g. n_nodes=40")
    ap.add_argument("--generations", type=int, default=60)
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--name", default="sample_organism")
    ap.add_argument("--no-swarmlabs", action="store_true",
                    help="skip the SwarmLabs config export (option B)")
    ap.add_argument("--no-html", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)

    # ---- A: resolve motifs at runtime ------------------------------- #
    motifs, prov = resolve_motifs(
        source=args.motif_source, api_url=args.api_url, api_key=args.api_key,
        refresh=args.refresh, snapshot_path=args.snapshot, timeout=args.timeout,
        save_snapshot=args.refresh_snapshot)
    print("[C1] motifs available:", list(motifs["motifs"].keys()))

    # resolve module profile mode
    if args.profile_sensory or args.profile_memory or args.profile_motor:
        if args.profile_sensory:
            mp_mode = {"0": "sensory"}
        elif args.profile_memory:
            mp_mode = {"0": "memory"}
        else:
            mp_mode = {"0": "motor"}
        # fill remaining modules with the same profile
        for i in range(1, args.modules):
            mp_mode[str(i)] = list(mp_mode.values())[0]
    else:
        mp_mode = args.module_profiles  # "cycled" or "uniform"

    spec = {"n_modules": args.modules, "agents_per_module": args.agents_per_module,
            "use_inhibitory_coordinator": True, "use_reservoir_buffer": True,
            "use_recurrent_memory": True, "recurrent_pct": args.recurrent_pct,
            "module_profiles": mp_mode,
            "blueprint": None if args.blueprint == "none" else args.blueprint}
    org = design_organism(spec, motifs=motifs, seed=args.seed)
    org["motif_provenance"] = prov
    print("[C1] designed organism metrics:",
          json.dumps(org["metrics"], ensure_ascii=False))

    p = save_organism(org, args.name, out_dir)
    written = [p.name]
    if not args.no_html:
        hp = render_html(org, out_dir / ("%s.html" % args.name),
                         title="Virtual Organism · %d modules x %d agents"
                               % (args.modules, args.agents_per_module))
        written.append(hp.name)

    # ---- B: SwarmLabs instantiable config --------------------------- #
    if not args.no_swarmlabs:
        cfg = emit_swarmlabs_config(org, args.name,
                                    out_dir=out_dir / "swarmlabs",
                                    provenance=prov)
        v = cfg["swarm"]["validation"]
        print("[C1] swarmlabs config: agents=%d edges=%d modules=%d leader=%s ok=%s"
              % (v["n_agents"], v["n_edges"], v["n_modules"],
                 v["leader_resolved"], v["ok"]))
        written += ["swarmlabs/%s.swarm.json" % args.name,
                    "swarmlabs/%s.swarm.yaml" % args.name]

    # ---- optional target search ------------------------------------- #
    target = _parse_evolve(args.evolve)
    if target:
        metric, value = target
        evolved = evolve_organism(target_metric=metric, target_value=value,
                                  generations=args.generations, seed=3,
                                  motifs=motifs)
        best = evolved["best"]
        best["motif_provenance"] = prov
        print("[C1] evolved best_err=%.3f value=%.1f" % (
            evolved["best_err"], best["metrics"].get(metric, 0)))
        # keep the historical artifact name for the canonical n_nodes search
        name = ("evolved_target%d" % int(value) if metric == "n_nodes"
                else "evolved_%s%d" % (metric, int(value)))
        pe = save_organism(best, name, out_dir)
        written.append(pe.name)
        if not args.no_html:
            hep = render_html(best, out_dir / ("%s.html" % name),
                              title="Evolved Organism · target %s=%d"
                                    % (metric, int(value)))
            written.append(hep.name)
        if not args.no_swarmlabs:
            ecfg = emit_swarmlabs_config(best, name,
                                         out_dir=out_dir / "swarmlabs",
                                         provenance=prov)
            ev = ecfg["swarm"]["validation"]
            print("[C1] evolved swarmlabs config: agents=%d edges=%d ok=%s"
                  % (ev["n_agents"], ev["n_edges"], ev["ok"]))
            written += ["swarmlabs/%s.swarm.json" % name,
                        "swarmlabs/%s.swarm.yaml" % name]

    print("[C1] saved:", ", ".join(written))
    print("[C1] provenance:", json.dumps(
        {k: prov[k] for k in ("mode", "served_from", "doc_sha256",
                              "fallback_reason")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
