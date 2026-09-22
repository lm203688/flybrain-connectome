"""expand_v3_module_registry.py

向 module_registry.py 的 MODULE_REGISTRY 追加 60 个 ModuleSpec（与 MODULE_PROFILES 同步）。
每个 ModuleSpec 有：function/inputs/outputs/size_range/motif_source。
"""
from __future__ import annotations
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "flybrain-connectome-mcp" / "module_registry.py"

# 60 个神经元的 ModuleSpec 参数（不含 description/capabilities/task_hints 等——
# 这些从 MODULE_PROFILES 派生，脚本读取后再组装）
NEURON_SPEC = {
    # ---- 皮层锥体补充 (8) ----
    "pyramidal_l23_cx1":  {"function":"executive", "inputs":["thalamic_relay","pyramidal_l23","interneuron_sst"], "outputs":["pyramidal_l23","pyramidal_l5bt","thalamic_relay"], "motif":"feedforward_excitatory", "size":(5000,50000)},
    "pyramidal_l23_cx5":  {"function":"move", "inputs":["thalamic_relay","pyramidal_l5bt","interneuron_sst"], "outputs":["spinal_motor_alpha","pyramidal_l5bt","pyramidal_l6rt"], "motif":"feedforward_excitatory", "size":(5000,50000)},
    "pyramidal_l4b":      {"function":"perceive", "inputs":["lateral_geniculate_ventral","retina_parvalbumin_gc"], "outputs":["pyramidal_l23_cx1","pyramidal_l5bt","interneuron_sst"], "motif":"topographic_mapping", "size":(3000,30000)},
    "pyramidal_l4c":      {"function":"perceive", "inputs":["lateral_geniculate_ventral","retina_parvalbumin_gc"], "outputs":["pyramidal_l23_cx1","pyramidal_l5bt"], "motif":"topographic_mapping", "size":(3000,30000)},
    "pyramidal_l5bt":     {"function":"integrate", "inputs":["pyramidal_l4b","thalamic_relay","interneuron_vip"], "outputs":["thalamic_relay","pyramidal_l23_cx1","pyramidal_l6rt"], "motif":"recurrent_feedback", "size":(3000,30000)},
    "pyramidal_l6rt":     {"function":"integrate", "inputs":["pyramidal_l23_cx1","pyramidal_l5bt","interneuron_vip"], "outputs":["thalamic_relay"], "motif":"feedback_excitatory", "size":(3000,30000)},
    "pyramidal_l7":       {"function":"integrate", "inputs":["pyramidal_l4c","thalamic_relay","interneuron_vip"], "outputs":["pyramidal_l23_cx1","pyramidal_l5bt"], "motif":"recurrent_feedback", "size":(3000,30000)},
    "pyramidal_mayeret":  {"function":"move", "inputs":["vestibular_hair","cerebellar_purkinje"], "outputs":["vestibular_hair","cerebellar_granule"], "motif":"recurrent_feedback", "size":(500,5000)},
    # ---- 中间神经元补充 (8) ----
    "interneuron_calbindin": {"function":"inhibit", "inputs":["cerebellar_granule","thalamic_relay"], "outputs":["cerebellar_purkinje","cerebellar_granule"], "motif":"feedforward_inhibitory", "size":(5000,50000)},
    "interneuron_lamp":      {"function":"inhibit", "inputs":["cerebellar_granule","cerebellar_purkinje"], "outputs":["cerebellar_purkinje"], "motif":"lateral_inhibitory", "size":(1000,10000)},
    "interneuron_nph":       {"function":"inhibit", "inputs":["pyramidal_l23_cx1","interneuron_pv"], "outputs":["interneuron_pv","interneuron_sst"], "motif":"disinhibition", "size":(2000,20000)},
    "interneuron_npf":       {"function":"inhibit", "inputs":["pyramidal_l23_cx1","hippocampal_ca1"], "outputs":["pyramidal_l23_cx1","hippocampal_ca1"], "motif":"recurrent_inhibitory", "size":(2000,20000)},
    "interneuron_vlac":      {"function":"inhibit", "inputs":["pyramidal_l23_cx1","pyramidal_l5bt"], "outputs":["pyramidal_l23_cx1","pyramidal_l5bt","thalamic_relay"], "motif":"lateral_feedback", "size":(1000,10000)},
    "interneuron_sst_dendritic": {"function":"inhibit", "inputs":["pyramidal_l5bt","thalamic_relay","interneuron_vip"], "outputs":["pyramidal_l23_cx1","pyramidal_l5bt"], "motif":"dendritic_inhibitory_synapse", "size":(3000,30000)},
    "interneuron_sst_somatic":   {"function":"inhibit", "inputs":["pyramidal_l23_cx1","pyramidal_l5bt"], "outputs":["pyramidal_l23_cx1","pyramidal_l5bt"], "motif":"shunting_inhibition", "size":(3000,30000)},
    "interneuron_kcn":       {"function":"inhibit", "inputs":["pyramidal_l5bt","interneuron_vip"], "outputs":["pyramidal_l5bt","pyramidal_l23_cx1"], "motif":"recurrent_inhibitory", "size":(1000,10000)},
    # ---- 调制系统补充 (8) ----
    "dopaminergic_a9_snr":   {"function":"reward", "inputs":["striatum_d1_msn","subthalamic_nucleus"], "outputs":["striatum_d1_msn","striatum_d2_msn","thalamic_relay"], "motif":"modulatory_diffuse", "size":(20000,100000)},
    "dopaminergic_a11":      {"function":"reward", "inputs":["striatum_d1_msn"], "outputs":["pyramidal_l23_cx1","thalamic_relay"], "motif":"modulatory_diffuse", "size":(10000,50000)},
    "dopaminergic_vmc":      {"function":"reward", "inputs":["striatum_d1_msn","amygdala_bla"], "outputs":["striatum_d1_msn","amygdala_bla"], "motif":"volume_transmission", "size":(10000,50000)},
    "serotonergic_dorsal":   {"function":"modulate", "inputs":["pyramidal_l23_cx1","amygdala_bla"], "outputs":["pyramidal_l23_cx1","amygdala_bla","hippocampal_ca1"], "motif":"modulatory_diffuse", "size":(10000,50000)},
    "serotonergic_ventral":  {"function":"modulate", "inputs":["amygdala_bla","striatum_d1_msn"], "outputs":["amygdala_bla","striatum_d1_msn"], "motif":"modulatory_diffuse", "size":(5000,20000)},
    "serotonergic_median":   {"function":"modulate", "inputs":["hippocampal_ca3"], "outputs":["hippocampal_ca1","hippocampal_ca3"], "motif":"modulatory_diffuse", "size":(3000,10000)},
    "cholinergic_horizontal":{"function":"modulate", "inputs":["brainstem_vpm"], "outputs":["thalamic_relay","thalamic_lgn","thalamic_vl"], "motif":"neuromodulatory_axon", "size":(5000,20000)},
    "histaminergic_tm":      {"function":"modulate", "inputs":["pineal","brainstem_vpm"], "outputs":["pyramidal_l23_cx1","thalamic_relay","noradrenergic_lc"], "motif":"modulatory_diffuse", "size":(3000,10000)},
    # ---- 视觉补充 (8) ----
    "retinal_bipolar_cone":  {"function":"perceive", "inputs":["retina_parvalbumin_gc","retinal_horizontal"], "outputs":["retina_parvalbumin_gc","retinal_amacrine_acl1"], "motif":"axo_dendritic", "size":(50000,200000)},
    "retinal_bipolar_rod":   {"function":"perceive", "inputs":["retina_parvalbumin_gc","retinal_horizontal"], "outputs":["retina_parvalbumin_gc"], "motif":"axo_dendritic", "size":(100000,500000)},
    "retinal_amacrine_acl1": {"function":"inhibit", "inputs":["retina_parvalbumin_gc","retinal_bipolar_cone"], "outputs":["retina_parvalbumin_gc","retinal_bipolar_cone"], "motif":"contrast_inhibition", "size":(1000,5000)},
    "retinal_amacrine_acl2": {"function":"inhibit", "inputs":["retina_parvalbumin_gc","retinal_bipolar_cone"], "outputs":["retina_parvalbumin_gc"], "motif":"feedforward_inhibitory", "size":(1000,5000)},
    "retina_midget_gc":      {"function":"perceive", "inputs":["retinal_bipolar_cone","retinal_amacrine_acl1"], "outputs":["thalamic_lgn","thalamic_relay"], "motif":"topographic_mapping", "size":(10000,50000)},
    "retina_parvalbumin_gc": {"function":"perceive", "inputs":["retinal_bipolar_cone","retinal_amacrine_acl1"], "outputs":["thalamic_lgn","brainstem_vpm"], "motif":"feedforward_excitatory", "size":(5000,20000)},
    "lateral_geniculate_ventral": {"function":"integrate", "inputs":["spinal_nociceptor","brainstem_vpm","spinal_interneuron_ih"], "outputs":["pyramidal_l23_cx5","spinal_motor_alpha"], "motif":"topographic_mapping", "size":(50000,300000)},
    "lateral_geniculate_dorsal":  {"function":"integrate", "inputs":["spinal_nociceptor","brainstem_vpm"], "outputs":["pyramidal_l23_cx5","amygdala_bla"], "motif":"topographic_mapping", "size":(10000,50000)},
    # ---- 脊髓/脑干 (8) ----
    "spinal_interneuron_ih": {"function":"inhibit", "inputs":["spinal_motor_alpha","spinal_glycinergic"], "outputs":["spinal_motor_alpha","spinal_interneuron_icc"], "motif":"recurrent_feedback", "size":(5000,20000)},
    "spinal_interneuron_icc":{"function":"inhibit", "inputs":["spinal_motor_alpha","spinal_interneuron_ih"], "outputs":["spinal_motor_alpha","spinal_interneuron_ihp"], "motif":"lateral_inhibitory", "size":(5000,20000)},
    "spinal_interneuron_ihp":{"function":"inhibit", "inputs":["spinal_motor_alpha","spinal_interneuron_ih"], "outputs":["spinal_motor_alpha"], "motif":"recurrent_inhibitory", "size":(5000,20000)},
    "spinal_glycinergic":    {"function":"inhibit", "inputs":["spinal_motor_alpha","spinal_interneuron_ih"], "outputs":["spinal_motor_alpha","spinal_interneuron_icc"], "motif":"gap_junction_inhibitory", "size":(5000,20000)},
    "spinal_nociceptor":     {"function":"pain", "inputs":["external","spinal_interneuron_ih"], "outputs":["lateral_geniculate_ventral","lateral_geniculate_dorsal","brainstem_vpm"], "motif":"feedforward_excitatory", "size":(5000,20000)},
    "brainstem_vpm":         {"function":"integrate", "inputs":["spinal_nociceptor","spinal_interneuron_ih"], "outputs":["pyramidal_l23_cx5","lateral_geniculate_dorsal"], "motif":"topographic_mapping", "size":(5000,20000)},
    "red_nucleus":           {"function":"move", "inputs":["pyramidal_l23_cx5","spinal_motor_alpha"], "outputs":["spinal_motor_alpha","cerebellar_purkinje"], "motif":"feedforward_excitatory", "size":(2000,10000)},
    "inferior_olive":        {"function":"learn", "inputs":["cerebellar_purkinje","pyramidal_l23_cx1"], "outputs":["cerebellar_purkinje"], "motif":"retrograde_messenger", "size":(5000,50000)},
    # ---- 皮层下/边缘 (8) ----
    "striatum_d1_msn":       {"function":"reward", "inputs":["dopaminergic_a9_snr","pyramidal_l23_cx5"], "outputs":["subthalamic_nucleus","thalamic_va","inferior_olive"], "motif":"feedforward_excitatory", "size":(100000,500000)},
    "striatum_d2_msn":       {"function":"punish", "inputs":["dopaminergic_a9_snr","pyramidal_l23_cx1"], "outputs":["inferior_olive","red_nucleus","reticular_thalamic"], "motif":"feedforward_inhibitory", "size":(100000,500000)},
    "hippocampal_ca2":       {"function":"memory", "inputs":["hippocampal_ca3","amygdala_lateral"], "outputs":["hippocampal_ca1","septum"], "motif":"recurrent_feedback", "size":(10000,50000)},
    "hippocampal_ca4":       {"function":"memory", "inputs":["hippocampal_granule","pyramidal_l7"], "outputs":["hippocampal_ca3","hippocampal_ca2"], "motif":"feedforward_excitatory", "size":(5000,30000)},
    "hippocampal_subiculum": {"function":"memory", "inputs":["hippocampal_ca1","hippocampal_ca2"], "outputs":["pyramidal_l7","thalamic_relay"], "motif":"recurrent_feedback", "size":(30000,100000)},
    "amygdala_bla":          {"function":"emotion", "inputs":["amygdala_lateral","striatum_d1_msn"], "outputs":["brainstem_vpm","histaminergic_tm","septum"], "motif":"feedforward_excitatory", "size":(10000,50000)},
    "amygdala_lateral":      {"function":"emotion", "inputs":["retina_parvalbumin_gc","lateral_geniculate_ventral","lateral_geniculate_dorsal"], "outputs":["amygdala_bla","hippocampal_ca2"], "motif":"feedforward_excitatory", "size":(30000,100000)},
    "septum":                {"function":"arousal", "inputs":["amygdala_bla","hippocampal_ca1"], "outputs":["hippocampal_ca1","hippocampal_ca3"], "motif":"modulatory_diffuse", "size":(5000,20000)},
    # ---- 丘脑补充 (6) ----
    "thalamic_lgn":          {"function":"integrate", "inputs":["retina_parvalbumin_gc","retina_midget_gc","retinal_amacrine_acl1"], "outputs":["pyramidal_l4b","pyramidal_l4c","pyramidal_l23_cx1"], "motif":"topographic_mapping", "size":(50000,300000)},
    "thalamic_md":           {"function":"integrate", "inputs":["cochlear_outer_hair","inferior_olive"], "outputs":["pyramidal_l23_cx1","pyramidal_l4c"], "motif":"topographic_mapping", "size":(10000,50000)},
    "thalamic_va":           {"function":"integrate", "inputs":["red_nucleus","subthalamic_nucleus"], "outputs":["pyramidal_l23_cx5","pyramidal_l5bt"], "motif":"topographic_mapping", "size":(50000,200000)},
    "thalamic_vl":           {"function":"integrate", "inputs":["lateral_geniculate_ventral","red_nucleus"], "outputs":["pyramidal_l23_cx5","pyramidal_l5bt"], "motif":"topographic_mapping", "size":(50000,200000)},
    "reticular_thalamic":    {"function":"inhibit", "inputs":["thalamic_relay","pyramidal_l6rt"], "outputs":["thalamic_relay","thalamic_lgn","thalamic_vl"], "motif":"mutual_inhibitory", "size":(50000,200000)},
    "subthalamic_nucleus":   {"function":"integrate", "inputs":["striatum_d2_msn","pyramidal_l5bt","dopaminergic_a9_snr"], "outputs":["inferior_olive","red_nucleus","reticular_thalamic"], "motif":"recurrent_feedback", "size":(5000,20000)},
    # ---- 特殊感觉 + 胶质 (6) ----
    "pineal":                {"function":"circadian", "inputs":["retina_parvalbumin_gc","brainstem_vpm"], "outputs":["histaminergic_tm","orexin_neuron","serotonergic_dorsal"], "motif":"volume_transmission", "size":(500,5000)},
    "melanopsin_ganglion":   {"function":"perceive", "inputs":["retinal_horizontal"], "outputs":["pineal","brainstem_vpm"], "motif":"feedforward_excitatory", "size":(5000,50000)},
    "olfactory_receptor":    {"function":"perceive", "inputs":["external"], "outputs":["hippocampal_ca3","amygdala_lateral","septum"], "motif":"topographic_mapping", "size":(20000,100000)},
    "vestibular_hair":       {"function":"perceive", "inputs":["external"], "outputs":["pyramidal_mayeret","brainstem_vpm","cerebellar_purkinje"], "motif":"feedforward_excitatory", "size":(10000,50000)},
    "cochlear_outer_hair":   {"function":"perceive", "inputs":["external"], "outputs":["inferior_olive","thalamic_md","pyramidal_l23_cx1"], "motif":"feedforward_excitatory", "size":(10000,50000)},
    "astrocyte_reactive":    {"function":"modulate", "inputs":["pyramidal_l23_cx1","interneuron_pv","dopaminergic_a9_snr"], "outputs":["pyramidal_l23_cx1","interneuron_pv","pyramidal_l5bt"], "motif":"astrocyte_neuron_tripartite", "size":(100000,500000)},
}

# 从 MODULE_PROFILES 派生 description / capabilities / task_hints / neurotransmitter / brain_region
# 通过 exec 加载 synthetic_bio_topology.py 以拿到 MODULE_PROFILES
import sys
from pathlib import Path
sbt_path = TARGET.parent / "synthetic_bio_topology.py"
sys.path.insert(0, str(sbt_path.parent))
import importlib.util
spec = importlib.util.spec_from_file_location("sbt", str(sbt_path))
sbt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sbt)
PROFILES = sbt.MODULE_PROFILES

# 生成 ModuleSpec 字典字面量
def fmt_spec(name, ns):
    p = PROFILES.get(name, {})
    desc = p.get("description", "")
    caps = p.get("capability", [])
    task_pool = p.get("task_hint_pool", [])
    lead = p.get("lead_task_hint", "")
    nt = p.get("neurotransmitter", "")
    return (
        f'    "{name}": ModuleSpec(\n'
        f'        name="{name}",\n'
        f'        function="{ns["function"]}",\n'
        f'        description="{desc}",\n'
        f'        connection_pattern={{"inputs": {ns["inputs"]!r}, "outputs": {ns["outputs"]!r}}},\n'
        f'        size_range={ns["size"]},\n'
        f'        motif_source="{ns["motif"]}",\n'
        f'        parameters={{"reservoir_density": {p.get("reservoir_density", 0.3)}, '
        f'"recurrent_pct": {p.get("recurrent_pct", 0.15)}, '
        f'"has_inhibition": {p.get("has_inhibition", False)}, '
        f'"neurotransmitter": "{nt}"}},\n'
        f'        capabilities={caps!r},\n'
        f'        task_hints={task_pool!r},\n'
        f'        lead_task_hint="{lead}",\n'
        f'        category="biological",\n'
        f'    ),\n'
    )

BLOCK = "".join(fmt_spec(k, v) for k, v in NEURON_SPEC.items())

# 读取原文件，在 orexin_neuron 之后（第 756 行 `),` 之后）插入
text = TARGET.read_text(encoding="utf-8")
ANCHOR = '''        lead_task_hint="arousal_stability",
        category="biological",
    ),
}
'''
NEW_ANCHOR = '''        lead_task_hint="arousal_stability",
        category="biological",
    ),

    # ------------------------------------------------------------------ #
    # Phase 5 大规模扩展 (2026-09-22)：+60 ModuleSpec
    # 与 MODULE_PROFILES 同步，覆盖跨物种神经元类型（皮层锥体/中间神经元/
    #   调制/视觉/脊髓脑干/边缘/丘脑/特殊感觉胶质）
    # ------------------------------------------------------------------ #
''' + BLOCK + '}'
if ANCHOR not in text:
    raise RuntimeError("ANCHOR not found in module_registry.py")
TARGET.write_text(text.replace(ANCHOR, NEW_ANCHOR, 1), encoding="utf-8")

print(f"[expand_v3_module_registry] +{len(NEURON_SPEC)} ModuleSpec -> {TARGET}")
print("done.")
