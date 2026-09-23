"""Splice v1.6.0 ModuleSpec entries into module_registry.MODULE_REGISTRY.

One spec per neuron population added to MODULE_PROFILES in this batch (24), so the
registry keeps covering the whole vocabulary: profiles = vocabulary, registry =
factory-facing spec (function, connection pattern, size range, motif, capability).
"""
from pathlib import Path
import importlib.util
import sys

NL = chr(10)
ROOT = Path("C:/Users/xing/Desktop/flybrain-connectome")
MCP = ROOT / "flybrain-connectome-mcp"

spec = importlib.util.spec_from_file_location("sbt_v5", str(MCP / "synthetic_bio_topology.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["sbt_v5"] = mod
spec.loader.exec_module(mod)
PROFILES = mod.MODULE_PROFILES

# name -> (function, inputs, outputs, motif_source, size_range)
META = {
    # ---- segmental / peripheral oscillators ------------------------------
    "leech_cpg_interneuron": ("rhythm_generate", ["leech_mechanosensory_neuron", "external"],
                              ["leech_motor_neuron", "leech_cpg_interneuron"],
                              "half_center_oscillation", (100, 300)),
    "leech_motor_neuron": ("swim_control", ["leech_cpg_interneuron"], ["swim_muscle_effector"],
                           "feedforward_excitatory", (200, 600)),
    "leech_mechanosensory_neuron": ("touch_sense", ["external"], ["leech_cpg_interneuron"],
                                    "feedforward_excitatory", (100, 400)),
    "ascidian_larval_motor_neuron": ("escape_swim", ["ascidian_photoreceptor", "spinal_glycinergic"],
                                     ["tail_muscle_effector"], "half_center_oscillation", (10, 40)),
    "ascidian_photoreceptor": ("photoreception", ["external"], ["ascidian_larval_motor_neuron"],
                               "feedforward_excitatory", (4, 20)),
    "aplysia_sensory_neuron": ("touch_sense", ["external", "aplysia_facilitating_interneuron"],
                               ["aplysia_motor_neuron"],
                               "serotonergic_presynaptic_facilitation", (50, 200)),
    "aplysia_motor_neuron": ("gill_retract", ["aplysia_sensory_neuron", "buccal_cpg_neuron"],
                             ["gill_effector", "feeding_effector"],
                             "command_neuron_recruitment", (20, 80)),
    "aplysia_facilitating_interneuron": ("sensitization", ["external"],
                                         ["aplysia_sensory_neuron", "aplysia_motor_neuron"],
                                         "modulatory_diffuse", (10, 60)),
    "buccal_cpg_neuron": ("feeding_rhythm", ["external", "cholinergic_mt"],
                          ["aplysia_motor_neuron", "buccal_cpg_neuron"],
                          "half_center_oscillation", (30, 120)),
    # ---- infrared / amphibian -------------------------------------------
    "trigeminal_infrared_afferent": ("infrared_localize", ["external"], ["infrared_tectal_neuron"],
                                     "topographic_mapping", (200, 2000)),
    "infrared_tectal_neuron": ("thermal_imaging", ["trigeminal_infrared_afferent"],
                               ["optic_tectum_multimodal"], "topographic_mapping", (200, 2000)),
    "optic_tectum_multimodal": ("cross_modal_bind", ["infrared_tectal_neuron", "retinal_gc"],
                                ["spinal_motor_alpha", "tongue_motor_neuron"],
                                "thermal_cross_modal_convergence", (200, 1500)),
    "tectal_prey_detector": ("prey_capture", ["retinal_gc"], ["tongue_motor_neuron"],
                             "command_neuron_recruitment", (500, 5000)),
    "tongue_motor_neuron": ("tongue_strike", ["tectal_prey_detector", "optic_tectum_multimodal"],
                            ["tongue_effector"], "command_neuron_recruitment", (100, 500)),
    # ---- error teaching / state -----------------------------------------
    "climbing_fibre": ("error_teaching", ["inferior_olive"], ["cerebellar_purkinje"],
                       "coincidence_detection", (10, 50)),
    "cerebellar_go_cell": ("gain_control", ["cerebellar_granule"], ["cerebellar_granule"],
                           "feedback_inhibitory", (1000, 10000)),
    "vestibular_nucleus_neuron": ("gaze_stabilize", ["vestibular_hair"], ["spinal_motor_alpha"],
                                  "topographic_mapping", (500, 3000)),
    "pre_botzinger_neuron": ("breathing_rhythm", ["external", "interneuron_pv"],
                             ["phrenic_motor_neuron", "pre_botzinger_neuron"],
                             "plateau_potential_bistability", (200, 800)),
    "phrenic_motor_neuron": ("respiration_drive", ["pre_botzinger_neuron"], ["diaphragm_effector"],
                             "command_neuron_recruitment", (100, 500)),
    "vlpo_neuron": ("sleep_wake", ["noradrenergic_lc"], ["noradrenergic_lc"],
                    "mutual_inhibitory", (500, 3000)),
    # ---- navigation / active sensing ------------------------------------
    "head_direction_cell": ("heading_track", ["external"], ["place_cell"],
                            "topographic_mapping", (200, 2000)),
    "place_cell": ("place_code", ["grid_cell", "head_direction_cell"],
                   ["hippocampal_subiculum"], "grid_phase_precession", (5000, 50000)),
    "barrel_cortex_neuron": ("active_touch", ["thalamic_relay"], ["whisker_motor_neuron"],
                             "topographic_mapping", (2000, 15000)),
    "whisker_motor_neuron": ("active_touch", ["barrel_cortex_neuron"], ["vibrissa_effector"],
                             "feedforward_excitatory", (100, 500)),
}

missing = [k for k in META if k not in PROFILES]
assert not missing, "metadata for unknown profiles: %s" % missing

lines = []
lines.append("# ====================================================================== #")
lines.append("# v1.6.0 节律/状态/误差扩展：24 个神经元模块规格")
lines.append("# ---------------------------------------------------------------------- #")
lines.append("# 与 synthetic_bio_topology.MODULE_PROFILES 的 24 个 v1.6.0 档案一一对应：")
lines.append("# 外周/节段振荡器 9（水蛭游泳 CPG、海鞘幼虫逃逸、海兔缩鳃与口球 CPG）")
lines.append("# + 红外与两栖 5（颊窝热图、顶盖跨模态、蛙捕食释放、舌肌弹射）")
lines.append("# + 误差教学与状态 6（攀爬纤维、高尔基细胞、前庭核、前包钦格、VLPO）")
lines.append("# + 导航与主动感知 4（头方向、位置细胞、桶状皮层、胡须运动）")
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
    lines.append("        connection_pattern={\"inputs\": %r, \"outputs\": %r}," % (ins, outs))
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

spec2 = importlib.util.spec_from_file_location("mr_v5", str(p))
m2 = importlib.util.module_from_spec(spec2)
sys.modules["mr_v5"] = m2
spec2.loader.exec_module(m2)
print("MODULE_REGISTRY total:", len(m2.MODULE_REGISTRY))
print("new present:", sum(1 for k in META if k in m2.MODULE_REGISTRY))
print("profiles covered:",
      sum(1 for k in PROFILES if k in m2.MODULE_REGISTRY), "/", len(PROFILES))
