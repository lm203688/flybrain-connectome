import importlib.util
import json
import sys
from pathlib import Path

NL = chr(10)
ROOT = Path("C:/Users/xing/Desktop/flybrain-connectome")
MCP = ROOT / "flybrain-connectome-mcp"

spec = importlib.util.spec_from_file_location("sbt_v4", str(MCP / "synthetic_bio_topology.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["sbt_v4"] = mod
spec.loader.exec_module(mod)
PROFILES = mod.MODULE_PROFILES

# name -> (function, inputs, outputs, motif_source, size_range)
META = {
    # ---- insect ----------------------------------------------------------
    "kenyon_cell": ("sparse_encode", ["antennal_lobe_pn"], ["mushroom_body_output"],
                    "sparse_expansion_projection", (1500, 2500)),
    "mushroom_body_output": ("readout", ["kenyon_cell"], ["descending_neuron", "central_complex_fb"],
                             "feedforward_excitatory", (20, 40)),
    "mushroom_body_dan": ("reward_punish", ["mushroom_body_output"], ["kenyon_cell"],
                          "neuromodulatory_axon", (30, 60)),
    "mushroom_body_apl": ("global_inhibition", ["kenyon_cell"], ["kenyon_cell"],
                          "inhibitory_hub", (1, 3)),
    "antennal_lobe_pn": ("odour_encode", ["olfactory_receptor"], ["kenyon_cell", "mushroom_body_output"],
                         "feedforward_excitatory", (50, 150)),
    "antennal_lobe_ln": ("normalize", ["antennal_lobe_pn"], ["antennal_lobe_pn"],
                         "lateral_inhibitory", (30, 100)),
    "central_complex_pb": ("heading_track", ["central_complex_eb", "central_complex_ring"], ["central_complex_eb"],
                           "recurrent_excitatory", (16, 18)),
    "central_complex_eb": ("attractor_hold", ["central_complex_pb", "central_complex_ring"],
                           ["central_complex_pb", "central_complex_fb"], "recurrent_inhibitory", (50, 120)),
    "central_complex_fb": ("steering", ["central_complex_noduli", "central_complex_eb"], ["descending_neuron"],
                           "topographic_mapping", (60, 150)),
    "central_complex_noduli": ("speed_estimate", ["descending_neuron"], ["central_complex_fb"],
                               "feedforward_excitatory", (10, 40)),
    "central_complex_ring": ("bump_sharpen", ["central_complex_pb"], ["central_complex_eb"],
                             "lateral_inhibitory", (20, 60)),
    "clock_neuron_slnv": ("circadian_pace", ["clock_neuron_ln"], ["clock_neuron_ln", "pineal"],
                          "gap_junction_sync", (8, 16)),
    "clock_neuron_ln": ("clock_couple", ["clock_neuron_slnv", "melanopsin_ganglion"], ["clock_neuron_slnv"],
                        "gap_junction_sync", (60, 120)),
    "descending_neuron": ("descending_command", ["central_complex_fb"], ["spinal_motor_alpha"],
                          "corollary_discharge", (200, 400)),
    # ---- bird ------------------------------------------------------------
    "hvc_neuron": ("sequence_generate", ["nif_neuron", "auditory_input"], ["ra_neuron", "area_x_neuron"],
                   "neural_chain_sequence", (20000, 40000)),
    "ra_neuron": ("vocal_motor", ["hvc_neuron", "lman_neuron"], ["syringeal_motor", "respiratory_motor"],
                  "command_neuron_recruitment", (10000, 20000)),
    "lman_neuron": ("explore_variation", ["dlm_neuron"], ["ra_neuron"],
                    "feedforward_excitatory", (5000, 20000)),
    "area_x_neuron": ("action_value", ["hvc_neuron", "auditory_input"], ["dlm_neuron"],
                      "feedforward_inhibitory", (50000, 200000)),
    "dlm_neuron": ("thalamic_relay", ["area_x_neuron"], ["lman_neuron"], "disinhibition", (1000, 5000)),
    "nif_neuron": ("premotor_input", ["auditory_input"], ["hvc_neuron"], "feedforward_excitatory", (2000, 10000)),
    # ---- fish ------------------------------------------------------------
    "mauthner_cell": ("escape_trigger", ["lateral_line_hair_cell", "auditory_input"],
                      ["reticulospinal_neuron"], "command_neuron_recruitment", (1, 2)),
    "reticulospinal_neuron": ("descending_command", ["mauthner_cell"],
                              ["spinal_motor_alpha", "spinal_glycinergic"],
                              "command_neuron_recruitment", (100, 300)),
    "lateral_line_hair_cell": ("flow_detect", ["external"], ["mauthner_cell"],
                               "mixed_electrical_chemical_synapse", (500, 5000)),
    "electroreceptor_ampullary": ("passive_electrolocate", ["external"], ["ells_pyramidal"],
                                  "feedforward_excitatory", (500, 5000)),
    "electroreceptor_tuberous": ("active_electrolocate", ["external"], ["ells_pyramidal"],
                                 "feedforward_excitatory", (1000, 10000)),
    "ells_pyramidal": ("reafferent_cancel", ["electroreceptor_tuberous", "electroreceptor_ampullary"],
                       ["thalamic_relay"], "efference_copy_cancellation", (2000, 10000)),
    "electrosensory_inhibitory_interneuron": ("contrast_enhance", ["ells_pyramidal"], ["ells_pyramidal"],
                                              "contrast_inhibition", (500, 3000)),
    "pacemaker_nucleus_neuron": ("pacemaking", ["arousal_input"],
                                 ["spinal_motor_alpha", "ells_pyramidal"],
                                 "recurrent_excitatory", (50, 200)),
    # ---- cephalopod ------------------------------------------------------
    "vertical_lobe_large_cell": ("associative_learn", ["vertical_lobe_amacrine_cell"],
                                 ["superior_frontal_lobe_cell"], "repetitive_activation_lts",
                                 (50000, 500000)),
    "vertical_lobe_amacrine_cell": ("lts_express", ["vertical_lobe_small_cell"],
                                    ["vertical_lobe_large_cell"], "repetitive_activation_lts",
                                    (100000, 500000)),
    "vertical_lobe_small_cell": ("multimodal_converge", ["visual_input", "tactile_input"],
                                 ["vertical_lobe_amacrine_cell"], "feedforward_excitatory",
                                 (100000, 500000)),
    "superior_frontal_lobe_cell": ("higher_associate", ["vertical_lobe_large_cell"],
                                   ["chromatophore_motor_neuron", "arm_motor_neuron"],
                                   "feedforward_excitatory", (50000, 200000)),
    "chromatophore_motor_neuron": ("camouflage", ["superior_frontal_lobe_cell"],
                                   ["chromatophore_effector"], "feedforward_excitatory", (500, 5000)),
    "arm_motor_neuron": ("arm_control", ["superior_frontal_lobe_cell", "arm_sensory_afferent"],
                         ["arm_muscle_effector"], "recurrent_excitatory", (10000, 100000)),
    "arm_sensory_afferent": ("proprioceptive_loop", ["external"],
                             ["arm_motor_neuron", "superior_frontal_lobe_cell"],
                             "feedforward_excitatory", (50000, 500000)),
}

missing = [k for k in META if k not in PROFILES]
assert not missing, "metadata for unknown profiles: %s" % missing

lines = []
lines.append("# ====================================================================== #")
lines.append("# v1.4.1 跨进化支扩展：35 个非脊椎皮层特有神经元模块")
lines.append("# ---------------------------------------------------------------------- #")
lines.append("# 与 synthetic_bio_topology.MODULE_PROFILES 的 35 个 v1.4.1 档案一一对应：")
lines.append("# 昆虫 14（蘑菇体/触角叶/中央复合体/生物钟/下行）+ 鸟类 6（发声回路）")
lines.append("# + 鱼类 8（Mauthner 逃逸/电感受/电器官起搏）+ 头足类 7（垂直叶/色素细胞/腕）。")
lines.append("# motif_source 取名自 functional_units/connection_types.json 的连接形式；")
lines.append("# size_range 是 swarm 生成用的节点区间（保守），真实细胞量见 description。")
lines.append("# ====================================================================== #")
lines.append("MODULE_REGISTRY.update({")
for name, (fn, ins, outs, motif, size) in META.items():
    p = PROFILES[name]
    lines.append("    %r: ModuleSpec(" % name)
    lines.append("        name=%r," % name)
    lines.append("        function=%r," % fn)
    lines.append("        description=%r," % (p["description"],))
    lines.append("        connection_pattern={\"inputs\": %r, \"outputs\": %r},"
                 % (ins, outs))
    lines.append("        size_range=(%d, %d)," % size)
    lines.append("        motif_source=%r," % motif)
    lines.append("        parameters={\"reservoir_density\": %r, \"recurrent_pct\": %r, "
                 "\"has_inhibition\": %r}," % (p["reservoir_density"], p["recurrent_pct"],
                                               p["has_inhibition"]))
    lines.append("        capabilities=%r," % (p["capability"],))
    lines.append("        task_hints=%r," % (p["task_hint_pool"],))
    lines.append("        lead_task_hint=%r," % p["lead_task_hint"])
    lines.append("        category=\"biological\",")
    lines.append("    ),")
lines.append("})")
block = NL.join(lines)

p = MCP / "module_registry.py"
s = p.read_text(encoding="utf-8")
anchor = "# ====================================================================== #" + NL + "# 导出"
assert s.count(anchor) == 1, "anchor count=%d" % s.count(anchor)
s = s.replace(anchor, block + NL + NL + NL + anchor, 1)
p.write_text(s, encoding="utf-8")

# reload to verify
spec2 = importlib.util.spec_from_file_location("mr_v4", str(p))
m2 = importlib.util.module_from_spec(spec2)
sys.modules["mr_v4"] = m2
spec2.loader.exec_module(m2)
print("MODULE_REGISTRY total:", len(m2.MODULE_REGISTRY))
print("new present:", sum(1 for k in META if k in m2.MODULE_REGISTRY))
