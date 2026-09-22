"""expand_v3_motifs.py

向 swarm_agent_topology_motifs.json 追加 20 个概念性 motif（anatomical 5 + functional 8 +
plasticity 2 + specialized 5），并更新 motif_categories 与 schema_version 1.1 → 1.2。

所有 20 个 motif 的 hub_body=0（概念性、非从 MaleCNS 真实连接组提取）。
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

TARGET = Path(__file__).resolve().parent.parent / "flybrain-connectome-mcp" / "motifs" / "swarm_agent_topology_motifs.json"

NEW_MOTIFS = [
    # ==================== anatomical (+5) ====================
    {
        "pattern": "pre_presynaptic_inhibition",
        "biological_role": "Axo-axonic presynaptic inhibition: one neuron modulates the synaptic release of another (e.g. interneuron_lamp → purkinje). Reduces neurotransmitter release at target terminal.",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "presynaptic gate agent", "rule": "One agent reduces the pre-synaptic release weight of K target agents by gating factor in [0.2,0.8].", "edge_weight_hint": "multiplicative pre-factor on each gated edge"},
    },
    {
        "pattern": "pre_presynaptic_excitation",
        "biological_role": "Presynaptic facilitation: enhances neurotransmitter release (e.g. serotonergic facilitation on retinal bipolar). Increases release probability.",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "serotonin_dopamine",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "presynaptic booster agent", "rule": "One agent boosts release of K target agents by gain in [1.2,2.0].", "edge_weight_hint": "multiplicative post-factor"},
    },
    {
        "pattern": "dendritic_excitatory_synapse",
        "biological_role": "Excitatory synapse located on dendrites (not somatic): enables compartmental computation and NMDA-dependent spatial sums.",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "glutamate",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "dendritic excitatory agent", "rule": "Edges land on dendritic compartment of target (weight in [0.3,0.6]).", "edge_weight_hint": "dendritic-only activation"},
    },
    {
        "pattern": "dendritic_inhibitory_synapse",
        "biological_role": "GABAergic synapse on dendrites: dendritic shunting / feedback inhibition (e.g. SOM+ dendritic interneurons).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "dendritic inhibitor agent", "rule": "Applies negative-edge gain in [-0.5,-0.2] specifically to dendritic compartment.", "edge_weight_hint": "dendritic shunting weight"},
    },
    {
        "pattern": "axo_dendrite_reciprocal",
        "biological_role": "Reciprocal (bidirectional) synapse between axon of one neuron and dendrite of another (e.g. retinal bipolar↔horizontal).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "glutamate_gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "reciprocal pair", "rule": "Create mutual edges with opposite signs (source→target excitatory, target→source inhibitory).", "edge_weight_hint": "±0.35 with sign flip"},
    },
    # ==================== functional (+8) ====================
    {
        "pattern": "lateral_feedback",
        "biological_role": "Same-layer feedback: neurons at layer L inhibit or excite their lateral peers (e.g. VLAC+ long-range GABA).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "lateral feedback agent", "rule": "Agents in same role cluster form inhibitory feedback loop (weight in [-0.4,-0.15]).", "edge_weight_hint": "lateral negative edge"},
    },
    {
        "pattern": "recurrent_inhibitory",
        "biological_role": "Recurrent GABAergic loop within a module: fast local inhibition, sharpens winner-take-all.",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "recurrent inhibitory agent", "rule": "Each agent connects to random 30% same-module peers with weight in [-0.4,-0.15].", "edge_weight_hint": "intra-cluster inhibitory"},
    },
    {
        "pattern": "recurrent_excitatory",
        "biological_role": "Recurrent excitatory loop: builds attractor states, supports working memory (e.g. CA3 recurrent).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "glutamate",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "recurrent excitatory agent", "rule": "Each agent connects to random 25-40% same-module peers with weight in [0.2,0.5].", "edge_weight_hint": "intra-cluster excitatory"},
    },
    {
        "pattern": "disinhibition",
        "biological_role": "Inhibition of an inhibitor (inhibiting-inhibition): effectively excites the target. Classic NPV→PV/SST.",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "disinhibition gate", "rule": "One agent's inhibition of another inhibitor results in net excitation of that inhibitor's target.", "edge_weight_hint": "two-hop sign flip"},
    },
    {
        "pattern": "shunting_inhibition",
        "biological_role": "GABAergic somatic shunting: reduces membrane resistance, decreases gain without shifting threshold.",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "gain modulator (shunt)", "rule": "One agent applies multiplicative gain reduction in [0.3,0.7] to K peers.", "edge_weight_hint": "multiplicative gain, not additive"},
    },
    {
        "pattern": "contrast_inhibition",
        "biological_role": "Surround suppression: center excitatory, surround inhibitory (retinal ACL amacrine / V1 lateral).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "contrast enhancer", "rule": "Center agent excites, 3-5 surround agents inhibit (weight ±0.3).", "edge_weight_hint": "center-excitatory + surround-inhibitory"},
    },
    {
        "pattern": "feedforward_gating",
        "biological_role": "Feed-forward gating via fast inhibition: incoming signal gated by an inhibitor receiving the same signal (e.g. thalamic RTN gating).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "signal gate", "rule": "External input splits to gate agent (fast negative) and target agent (excitatory); net gain depends on gate strength.", "edge_weight_hint": "two-pathway with fast negative"},
    },
    {
        "pattern": "temporal_coherence",
        "biological_role": "Temporal synchrony via STDP-like coupling: neurons that fire together wire together.",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "glutamate",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "temporal binder", "rule": "Agents synchronize through time-delayed mutual excitation (τ_delay ∈ [20,100ms]).", "edge_weight_hint": "time-locked edge with delay"},
    },
    # ==================== plasticity (+2) ====================
    {
        "pattern": "retrograde_messenger",
        "biological_role": "Retrograde signaling: postsynaptic messenger travels backward to presynaptic terminal (e.g. NO, endocannabinoids, climbing fibers).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "no_endocannabinoid",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "retrograde modifier", "rule": "Postsynaptic agent broadcasts a slow modulatory signal backward to all pre-synaptic partners.", "edge_weight_hint": "slow bidirectional modifier"},
    },
    {
        "pattern": "dendritic_computation",
        "biological_role": "Dendritic spike-driven nonlinear integration: each dendritic branch is a mini-compute unit (NMDA spikes, calcium spikes).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "glutamate_gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "branch computer", "rule": "Each agent's dendritic branches are modeled as sub-units that perform local threshold nonlinearity before axonal spike.", "edge_weight_hint": "local nonlinear gates"},
    },
    # ==================== specialized (+5) ====================
    {
        "pattern": "ephaptic_coupling",
        "biological_role": "Ephaptic coupling: direct electrical influence through extracellular field, no chemical synapse (e.g. hippocampal mossy fiber → CA3).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "field-coupled agent", "rule": "Agents couple via a shared extracellular field (field amplitude in [0.05,0.15] of spike strength).", "edge_weight_hint": "field-coupling factor"},
    },
    {
        "pattern": "astrocyte_neuron_tripartite",
        "biological_role": "Tripartite synapse: astrocyte modulates between pre- and post-synaptic neurons (gliotransmitter release, glutamate recycling).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "glutamate_serotonin_dopamine",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "triangulation glia", "rule": "A glial agent interposes between pre and post agents, adding a slow positive or negative bias.", "edge_weight_hint": "glia-bias weight in [-0.1,0.1]"},
    },
    {
        "pattern": "gap_junction_inhibitory",
        "biological_role": "Gap-junction-mediated inhibitory coupling between GABAergic interneurons (e.g. glycinergic spinal inhibition).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "gaba",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "electrical-sync inhibitor", "rule": "Agents coupled by bidirectional undirected weight (no sign) in [0.2,0.5].", "edge_weight_hint": "electrical bidirectional edge"},
    },
    {
        "pattern": "neuromodulatory_axon",
        "biological_role": "Long-range neuromodulatory axon projecting from brainstem to specific target region (e.g. horizontal band → thalamus).",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "dopamine_serotonin_acetylcholine_noradrenaline",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "long-range modulator", "rule": "One modulator sends weak positive edges (weight in [0.05,0.2]) to all neurons in a target region.", "edge_weight_hint": "weak broad positive edge"},
    },
    {
        "pattern": "short_range_volume",
        "biological_role": "Short-range volume transmission: modulator releases transmitter into local extracellular space, affecting nearby but not synaptically-connected neurons.",
        "hub_body": 0, "hub_type": "", "hub_superclass": "", "neurotransmitter": "dopamine_serotonin",
        "fan_out_synapses": 0, "fan_in_synapses": 0, "broadcast_targets": [], "canonical_target": None,
        "agent_mapping": {"role": "local volume modulator", "rule": "Modulator affects agents within a spatial radius (weight decayed by distance, [0.02,0.1]).", "edge_weight_hint": "distance-decayed weak edge"},
    },
]

# 按类别聚合
CATEGORY_ADDITIONS = {
    "anatomical": [m["pattern"] for m in NEW_MOTIFS if m["pattern"] in {"pre_presynaptic_inhibition","pre_presynaptic_excitation","dendritic_excitatory_synapse","dendritic_inhibitory_synapse","axo_dendrite_reciprocal"}],
    "functional": [m["pattern"] for m in NEW_MOTIFS if m["pattern"] in {"lateral_feedback","recurrent_inhibitory","recurrent_excitatory","disinhibition","shunting_inhibition","contrast_inhibition","feedforward_gating","temporal_coherence"}],
    "plasticity": [m["pattern"] for m in NEW_MOTIFS if m["pattern"] in {"retrograde_messenger","dendritic_computation"}],
    "specialized": [m["pattern"] for m in NEW_MOTIFS if m["pattern"] in {"ephaptic_coupling","astrocyte_neuron_tripartite","gap_junction_inhibitory","neuromodulatory_axon","short_range_volume"}],
}

# 断言
assert len(NEW_MOTIFS) == 20, f"expected 20, got {len(NEW_MOTIFS)}"
assert all(m["hub_body"] == 0 for m in NEW_MOTIFS), "all new motifs must be conceptual (hub_body=0)"

# 读原文件
data = json.loads(TARGET.read_text(encoding="utf-8"))
existing_patterns = set(data["motifs"].keys())
new_patterns = set(m["pattern"] for m in NEW_MOTIFS)
overlap = existing_patterns & new_patterns
if overlap:
    print(f"WARN overlap with existing: {overlap}")

# 合并 motif
data["motifs"].update({m["pattern"]: m for m in NEW_MOTIFS})

# 合并 motif_categories
for cat, patterns in CATEGORY_ADDITIONS.items():
    existing = set(data["motif_categories"].get(cat, []))
    data["motif_categories"][cat] = sorted(existing | set(patterns))

# 更新 schema_version 和 generated_utc
data["schema_version"] = "1.2"
data["generated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# 更新 caveat 描述
old_caveat = data.get("caveat", "")
data["caveat"] = (
    "Motifs are TOPOLOGY PATTERNS derived from real wiring (3 original extract from MaleCNS v1.0: "
    "inhibitory_hub, reservoir_smallworld, recurrent_feedback) AND from cross-species neuroscience "
    "literature (37 additional conceptual patterns, hub_body=0). They are descriptions, not raw "
    "neuron data. Authoritative 166,700 neurons live in flybrain-connectome-male_cns/ (separate "
    "repo). This file only encodes wiring patterns usable by synthetic_bio_topology."
)

# 更新 dataset_stats
data["dataset_stats"] = {
    "total_motifs": len(data["motifs"]),
    "original_extracted_from_male_cns": 3,
    "conceptual_patterns": len(NEW_MOTIFS) + 17,  # 17 from schema 1.0 -> 1.1, +20 new
    "original_extract": ["inhibitory_hub", "reservoir_smallworld", "recurrent_feedback"],
    "conceptual_hub_body_zero": sum(1 for v in data["motifs"].values() if v.get("hub_body") == 0),
}

TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[expand_v3_motifs] +{len(NEW_MOTIFS)} motifs -> total {len(data['motifs'])}")
print(f"categories updated: {json.dumps(data['motif_categories'], ensure_ascii=False)}")
print("done.")
