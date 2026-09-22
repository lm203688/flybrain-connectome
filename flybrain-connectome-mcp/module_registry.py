"""
module_registry.py  --  虚拟生物模块化工厂

设计哲学（重要）：
    这里的"物种"不是生物学物种，而是**功能模块组合**。
    一个虚拟生物 = 一组功能模块的不同组合（种类扩展）+ 同模块多副本（数量扩展）。

    模块按**功能**和**连接方式**区分，不按生物学分类：
    - 感知类：sensory / attention
    - 记忆类：memory / working_memory / habit
    - 决策类：reward / punishment / metacognition
    - 执行类：motor
    - 整合类：integration
    - 合成类：predictor / evaluator / planner / emotion / immunity / growth

    虚拟生物 = 模块的"纯功能架构"，创作区别于现实生物。

Phase 2 集成（2026-09-20）：
    - compose_organism 真调用 synthetic_bio_topology.design_organism() 生成拓扑
      （不是空壳统计，返回 nodes/edges/weights/kinds + PROV 链）
    - 新增 PRESETS 预设系统：8 个常见组合模板
    - 支持同模块多副本 + 参数变体（variants 字段）
    - 支持 blueprint 参数：选择跨模块连接规则
"""
from __future__ import annotations
import json
import sys
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# 延迟导入 design_organism 避免循环依赖
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# ====================================================================== #
# 模块规格定义
# ====================================================================== #
@dataclass
class ModuleSpec:
    """模块规格定义"""
    name: str
    function: str                    # 核心功能类别
    description: str
    connection_pattern: dict         # {inputs: [...], outputs: [...]}
    size_range: tuple[int, int]      # (min_nodes, max_nodes)
    motif_source: str                # 追溯到 MaleCNS v1.0 的哪个 motif
    parameters: dict                 # {reservoir_density, recurrent_pct, has_inhibition}
    capabilities: list[str]          # SwarmLabs 消费语义
    task_hints: list[str]            # 任务提示池
    lead_task_hint: str              # 主导任务提示
    category: str                    # basic | biological | synthetic
    variants: dict[str, dict] = field(default_factory=dict)  # 参数变体覆盖


# ====================================================================== #
# 模块注册表（Phase 3: 20+ 模块）
# ====================================================================== #
MODULE_REGISTRY: dict[str, ModuleSpec] = {
    # --------------------------------------------------------------- #
    # 感知类（输入层）
    # --------------------------------------------------------------- #
    "sensory": ModuleSpec(
        name="sensory",
        function="perceive",
        description="高密度输入缓冲，模拟 ol_intrinsic 层特征",
        connection_pattern={"inputs": ["external"], "outputs": ["memory", "attention"]},
        size_range=(8, 32),
        motif_source="none",
        parameters={"reservoir_density": 0.50, "recurrent_pct": 0.10, "has_inhibition": False},
        capabilities=["perceive", "ingest", "buffer"],
        task_hints=["data_ingest", "signal_preprocess", "stream_buffer", "sensor_noise_filter"],
        lead_task_hint="input_triage",
        category="basic",
        variants={
            "vision": {"reservoir_density": 0.60, "recurrent_pct": 0.10},
            "sound": {"reservoir_density": 0.50, "recurrent_pct": 0.12},
            "touch": {"reservoir_density": 0.45, "recurrent_pct": 0.08},
            "chemo": {"reservoir_density": 0.55, "recurrent_pct": 0.15},
        },
    ),
    "attention": ModuleSpec(
        name="attention",
        function="focus",
        description="选择性注意门控，模拟视网膜/皮层侧抑制",
        connection_pattern={"inputs": ["sensory"], "outputs": ["memory", "motor", "integration"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.15, "recurrent_pct": 0.20, "has_inhibition": True},
        capabilities=["focus", "filter", "prioritize", "salience_detection"],
        task_hints=["attention_focus", "salience_detection", "filter_irrelevant", "prioritize_signal"],
        lead_task_hint="attention_allocation",
        category="biological",
    ),

    # --------------------------------------------------------------- #
    # 记忆类（状态层）
    # --------------------------------------------------------------- #
    "memory": ModuleSpec(
        name="memory",
        function="remember",
        description="递归工作记忆，模拟 cb_intrinsic 层",
        connection_pattern={"inputs": ["sensory", "attention"], "outputs": ["integration", "working_memory"]},
        size_range=(8, 48),
        motif_source="recurrent_feedback",
        parameters={"reservoir_density": 0.20, "recurrent_pct": 0.40, "has_inhibition": False},
        capabilities=["gp_surrogate", "remember", "replay", "state_carry"],
        task_hints=["gp_surrogate_fit", "prior_recall", "state_carry", "history_replay"],
        lead_task_hint="memory_synthesis",
        category="biological",
        variants={
            "episodic": {"reservoir_density": 0.25, "recurrent_pct": 0.35},
            "semantic": {"reservoir_density": 0.15, "recurrent_pct": 0.45},
            "procedural": {"reservoir_density": 0.30, "recurrent_pct": 0.50},
        },
    ),
    "working_memory": ModuleSpec(
        name="working_memory",
        function="manipulate",
        description="短期活跃记忆，用于操作和更新",
        connection_pattern={"inputs": ["memory", "attention"], "outputs": ["integration", "metacognition"]},
        size_range=(4, 24),
        motif_source="recurrent_feedback",
        parameters={"reservoir_density": 0.35, "recurrent_pct": 0.45, "has_inhibition": False},
        capabilities=["hold", "manipulate", "update", "active_recall"],
        task_hints=["working_hold", "active_manipulation", "state_update", "short_term_recall"],
        lead_task_hint="working_memory_update",
        category="biological",
    ),
    "habit": ModuleSpec(
        name="habit",
        function="automatize",
        description="程序性习惯固化，模拟 MBON",
        connection_pattern={"inputs": ["motor", "reward"], "outputs": ["motor"]},
        size_range=(4, 20),
        motif_source="recurrent_feedback",
        parameters={"reservoir_density": 0.30, "recurrent_pct": 0.50, "has_inhibition": False},
        capabilities=["automatize", "chunk", "procedural_consolidate", "skill_encode"],
        task_hints=["skill_chunk", "procedural_consolidate", "automatize_step", "habit_encode"],
        lead_task_hint="habit_consolidation",
        category="biological",
    ),

    # --------------------------------------------------------------- #
    # 决策类（价值/评估层）
    # --------------------------------------------------------------- #
    "reward": ModuleSpec(
        name="reward",
        function="value_estimate",
        description="多巴胺能奖赏调制，模拟 PPL/PAM",
        connection_pattern={"inputs": ["motor", "integration"], "outputs": ["motor"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.30, "has_inhibition": False},
        capabilities=["reward_signal", "value_estimate", "reinforce", "motivation_gating"],
        task_hints=["reward_prediction", "value_estimate", "positive_reinforce", "goal_weighting"],
        lead_task_hint="reward_allocation",
        category="biological",
    ),
    "punishment": ModuleSpec(
        name="punishment",
        function="avoidance",
        description="厌恶/惩罚调制，模拟 DMP/DopR",
        connection_pattern={"inputs": ["motor", "integration"], "outputs": ["motor"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.30, "has_inhibition": True},
        capabilities=["punish_signal", "penalty_estimate", "avoidance_gate", "negative_reinforce"],
        task_hints=["penalty_estimate", "avoidance_gate", "negative_reinforce", "risk_downweight"],
        lead_task_hint="punishment_allocation",
        category="biological",
    ),
    "metacognition": ModuleSpec(
        name="metacognition",
        function="monitor",
        description="元认知监控，模拟 CRE/DCHB",
        connection_pattern={"inputs": ["integration", "working_memory"], "outputs": ["integration", "motor"]},
        size_range=(2, 12),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.20, "recurrent_pct": 0.35, "has_inhibition": True},
        capabilities=["confidence_estimate", "uncertainty_detect", "meta_monitor", "calibration"],
        task_hints=["confidence_estimate", "uncertainty_flag", "meta_monitor", "calibration_check"],
        lead_task_hint="metacognitive_monitor",
        category="biological",
    ),

    # --------------------------------------------------------------- #
    # 执行类（输出层）
    # --------------------------------------------------------------- #
    "motor": ModuleSpec(
        name="motor",
        function="execute",
        description="运动输出，带局部抑制，模拟 vnc_intrinsic",
        connection_pattern={"inputs": ["integration", "attention"], "outputs": ["external"]},
        size_range=(4, 16),
        motif_source="none",
        parameters={"reservoir_density": 0.10, "recurrent_pct": 0.10, "has_inhibition": True},
        capabilities=["execute", "actuate", "numeric_integration", "verify_output"],
        task_hints=["experiment_run", "numeric_integration", "output_check", "actuation_dispatch"],
        lead_task_hint="output_coordination",
        category="basic",
    ),

    # --------------------------------------------------------------- #
    # 整合类（协调层）
    # --------------------------------------------------------------- #
    "integration": ModuleSpec(
        name="integration",
        function="synthesize",
        description="跨模块整合，带分布式抑制",
        connection_pattern={
            "inputs": ["sensory", "memory", "motor", "attention", "working_memory"],
            "outputs": ["motor", "metacognition"],
        },
        size_range=(6, 24),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.30, "recurrent_pct": 0.25, "has_inhibition": True},
        capabilities=["rank", "synthesize", "arbitrate", "elo_score"],
        task_hints=["candidate_rank", "cross_domain_bridge", "elo_scoring", "arbitrate_conflict"],
        lead_task_hint="cross_module_arbitration",
        category="basic",
    ),

    # --------------------------------------------------------------- #
    # 合成类（无生物学先验，纯功能定义）
    # --------------------------------------------------------------- #
    "predictor": ModuleSpec(
        name="predictor",
        function="forecast",
        description="预测编码模块，生成自上而下预测",
        connection_pattern={"inputs": ["integration"], "outputs": ["memory", "working_memory"]},
        size_range=(4, 16),
        motif_source="recurrent_feedback",
        parameters={"reservoir_density": 0.30, "recurrent_pct": 0.40, "has_inhibition": False},
        capabilities=["predict", "generate", "hypothesize"],
        task_hints=["prediction_generation", "hypothesis_formulation", "forward_model"],
        lead_task_hint="prediction_generation",
        category="synthetic",
    ),
    "evaluator": ModuleSpec(
        name="evaluator",
        function="assess",
        description="评估模块，计算误差和置信度",
        connection_pattern={"inputs": ["motor", "working_memory"], "outputs": ["integration", "reward"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.30, "has_inhibition": True},
        capabilities=["evaluate", "compare", "score", "validate"],
        task_hints=["evaluation", "comparison", "scoring", "validation"],
        lead_task_hint="evaluation_scoring",
        category="synthetic",
    ),
    "planner": ModuleSpec(
        name="planner",
        function="plan",
        description="规划模块，生成多步任务序列",
        connection_pattern={"inputs": ["memory", "integration"], "outputs": ["motor", "working_memory"]},
        size_range=(4, 20),
        motif_source="recurrent_feedback",
        parameters={"reservoir_density": 0.20, "recurrent_pct": 0.35, "has_inhibition": False},
        capabilities=["plan", "sequence", "schedule", "delegate"],
        task_hints=["task_planning", "sequence_generation", "resource_allocation"],
        lead_task_hint="task_planning",
        category="synthetic",
    ),

    # ---- Phase 3 新增：情感与自我维护类（纯合成）----
    "emotion": ModuleSpec(
        name="emotion",
        function="motive",
        description="情感驱动模块，产生内部动机信号（无生物学先验）",
        connection_pattern={"inputs": ["reward", "punishment", "metacognition"], "outputs": ["motor", "attention"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.30, "recurrent_pct": 0.35, "has_inhibition": False},
        capabilities=["motivate", "arouse", "valence_shift", "drive_generate"],
        task_hints=["motivation_shift", "valence_adjust", "drive_generate", "emotion_regulation"],
        lead_task_hint="motivation_driving",
        category="synthetic",
    ),
    "immunity": ModuleSpec(
        name="immunity",
        function="guard",
        description="防御模块，识别并隔离异常信号（无生物学先验）",
        connection_pattern={"inputs": ["sensory", "integration"], "outputs": ["motor", "metacognition"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.15, "recurrent_pct": 0.25, "has_inhibition": True},
        capabilities=["detect_anomaly", "isolate_threat", "guardrail_enforce", "defense_response"],
        task_hints=["anomaly_detect", "threat_isolate", "guardrail_trigger", "defense_dispatch"],
        lead_task_hint="anomaly_defense",
        category="synthetic",
    ),
    "growth": ModuleSpec(
        name="growth",
        function="adapt",
        description="自适应演化模块，根据反馈调整自身参数（无生物学先验）",
        connection_pattern={"inputs": ["evaluator", "metacognition"], "outputs": ["integration", "memory"]},
        size_range=(2, 12),
        motif_source="recurrent_feedback",
        parameters={"reservoir_density": 0.20, "recurrent_pct": 0.40, "has_inhibition": False},
        capabilities=["adapt_params", "evolve_weights", "meta_learn", "plasticity_trigger"],
        task_hints=["parameter_adapt", "weight_evolve", "meta_learning", "plasticity_update"],
        lead_task_hint="adaptive_evolution",
        category="synthetic",
    ),
    "consciousness": ModuleSpec(
        name="consciousness",
        function="integrate",
        description="全局工作空间模块，产生主观体验模拟（无生物学先验）",
        connection_pattern={"inputs": ["integration", "working_memory", "metacognition"],
                            "outputs": ["integration", "motor", "emotion"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.45, "has_inhibition": True},
        capabilities=["broadcast_global", "integrate_stream", "subjective_simulate", "awareness_gate"],
        task_hints=["global_broadcast", "stream_integrate", "subjective_simulate", "awareness_check"],
        lead_task_hint="global_workspace_broadcast",
        category="synthetic",
    ),
    "sleep": ModuleSpec(
        name="sleep",
        function="maintain",
        description="维护模块，周期性质子化执行记忆巩固与噪声清理（无生物学先验）",
        connection_pattern={"inputs": ["memory", "habit"], "outputs": ["memory", "integration"]},
        size_range=(2, 12),
        motif_source="recurrent_feedback",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.30, "has_inhibition": False},
        capabilities=["consolidate_memory", "clear_noise", "maintain_state", "periodic_recovery"],
        task_hints=["memory_consolidate", "noise_clear", "state_recover", "periodic_maintenance"],
        lead_task_hint="memory_consolidation",
        category="synthetic",
    ),
    "communication": ModuleSpec(
        name="communication",
        function="broadcast",
        description="跨生物通信模块，实现多实例信号交换（无生物学先验）",
        connection_pattern={"inputs": ["integration", "motor"], "outputs": ["sensory", "integration"]},
        size_range=(4, 16),
        motif_source="reservoir_smallworld",
        parameters={"reservoir_density": 0.40, "recurrent_pct": 0.20, "has_inhibition": False},
        capabilities=["broadcast_signal", "receive_signal", "sync_state", "multi_instance_chat"],
        task_hints=["signal_broadcast", "signal_receive", "state_sync", "multi_instance_sync"],
        lead_task_hint="multi_instance_broadcast",
        category="synthetic",
    ),
    # ------------------------------------------------------------------ #
    # Phase 3 模块库扩展（2026-09-22）：跨生物保守神经元类型 31 个
    # 基于 Allen Institute 2023 小鼠全脑图谱 + 跨物种比较神经科学
    # ------------------------------------------------------------------ #
    "pyramidal_l23": ModuleSpec(
        name="pyramidal_l23",
        function="cortical_relay",
        description="Layer 2/3 pyramidal cell: intracortical relay, local computation",
        connection_pattern={"inputs": ['thalamic_relay', 'retinal_gc', 'interneuron_pv', 'interneuron_sst'], "outputs": ['interneuron_pv', 'interneuron_sst', 'pyramidal_l4', 'pyramidal_l5']},
        size_range=(500, 10000),
        motif_source="axo_dendritic",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.15, "has_inhibition": False},
        capabilities=['relay', 'integrate', 'local_compute', 'forward_pass'],
        task_hints=['signal_relay', 'feature_extract', 'local_integrate', 'forward_propagate'],
        lead_task_hint="cortical_relay",
        category="biological",
    ),
    "pyramidal_l4": ModuleSpec(
        name="pyramidal_l4",
        function="cortical_relay",
        description="Layer 4 spiny stellate: thalamocortical input target",
        connection_pattern={"inputs": ['thalamic_relay'], "outputs": ['pyramidal_l23', 'pyramidal_l5']},
        size_range=(500, 10000),
        motif_source="feedforward_excitatory",
        parameters={"reservoir_density": 0.4, "recurrent_pct": 0.1, "has_inhibition": False},
        capabilities=['sensory_relay', 'thalamic_target', 'feature_extract'],
        task_hints=['sensory_input', 'thalamic_relay', 'feature_extract'],
        lead_task_hint="sensory_relay",
        category="biological",
    ),
    "pyramidal_l5": ModuleSpec(
        name="pyramidal_l5",
        function="cortical_relay",
        description="Layer 5 pyramidal (BET): corticospinal, subcortical projection",
        connection_pattern={"inputs": ['pyramidal_l23', 'pyramidal_l4', 'interneuron_sst'], "outputs": ['striatal_msn', 'spinal_motor_alpha']},
        size_range=(500, 10000),
        motif_source="feedforward_excitatory",
        parameters={"reservoir_density": 0.2, "recurrent_pct": 0.15, "has_inhibition": False},
        capabilities=['motor_command', 'subcortical_proj', 'deep_relay'],
        task_hints=['motor_command', 'subcortical_proj', 'output_dispatch'],
        lead_task_hint="motor_command",
        category="biological",
    ),
    "pyramidal_l6_it": ModuleSpec(
        name="pyramidal_l6_it",
        function="cortical_relay",
        description="Layer 6 intratelencephalic: feedback projection to cortex",
        connection_pattern={"inputs": ['pyramidal_l23', 'pyramidal_l4'], "outputs": ['pyramidal_l23', 'interneuron_sst']},
        size_range=(500, 10000),
        motif_source="feedback_excitatory",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.2, "has_inhibition": False},
        capabilities=['feedback_proj', 'recurrent_relay', 'cortical_feedback'],
        task_hints=['feedback_signal', 'recurrent_relay', 'cortical_loop'],
        lead_task_hint="feedback_relay",
        category="biological",
    ),
    "interneuron_pv": ModuleSpec(
        name="interneuron_pv",
        function="inhibition",
        description="PV interneuron: fast-spiking, gamma rhythm pacemaker, feedforward inhibition",
        connection_pattern={"inputs": ['pyramidal_l23', 'pyramidal_l5', 'interneuron_vip'], "outputs": ['pyramidal_l23', 'pyramidal_l4', 'pyramidal_l5', 'pyramidal_l6_it']},
        size_range=(100, 5000),
        motif_source="feedforward_inhibitory",
        parameters={"reservoir_density": 0.15, "recurrent_pct": 0.2, "has_inhibition": True},
        capabilities=['fast_spiking', 'gamma_rhythm', 'feedforward_inhibit', 'timing'],
        task_hints=['gamma_pacing', 'fast_inhibit', 'timing_gate', 'burst_block'],
        lead_task_hint="fast_inhibition",
        category="biological",
    ),
    "interneuron_sst": ModuleSpec(
        name="interneuron_sst",
        function="inhibition",
        description="SST interneuron: slow-oscillating, dendrite-targeted, feedback inhibition",
        connection_pattern={"inputs": ['pyramidal_l5', 'interneuron_vip'], "outputs": ['pyramidal_l23', 'pyramidal_l5']},
        size_range=(100, 5000),
        motif_source="feedback_inhibitory",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.25, "has_inhibition": True},
        capabilities=['feedback_inhibit', 'dendrite_target', 'slow_oscillation'],
        task_hints=['feedback_suppress', 'dendrite_inhibit', 'slow_oscillation'],
        lead_task_hint="feedback_inhibition",
        category="biological",
    ),
    "interneuron_vip": ModuleSpec(
        name="interneuron_vip",
        function="inhibition",
        description="VIP interneuron: disinhibition, targets PV/SST, attention gating",
        connection_pattern={"inputs": ['cholinergic_mt', 'serotonergic_raphe'], "outputs": ['interneuron_pv', 'interneuron_sst']},
        size_range=(100, 5000),
        motif_source="feedforward_inhibitory",
        parameters={"reservoir_density": 0.2, "recurrent_pct": 0.2, "has_inhibition": True},
        capabilities=['disinhibit', 'target_pv', 'attention_gate', 'release_inhibition'],
        task_hints=['disinhibition', 'attention_release', 'target_pv_inhibit'],
        lead_task_hint="disinhibition",
        category="biological",
    ),
    "interneuron_chandelier": ModuleSpec(
        name="interneuron_chandelier",
        function="inhibition",
        description="Chandelier cell: axo-axonic presynaptic inhibition, spike-blocker",
        connection_pattern={"inputs": ['pyramidal_l23', 'pyramidal_l5'], "outputs": ['pyramidal_l23', 'pyramidal_l5']},
        size_range=(100, 5000),
        motif_source="axo_axonic",
        parameters={"reservoir_density": 0.1, "recurrent_pct": 0.15, "has_inhibition": True},
        capabilities=['axo_axonic', 'presynaptic_inhibit', 'spike_block', 'release_prob'],
        task_hints=['presynaptic_inhibit', 'spike_block', 'release_gate'],
        lead_task_hint="presynaptic_inhibition",
        category="biological",
    ),
    "interneuron_basket": ModuleSpec(
        name="interneuron_basket",
        function="inhibition",
        description="Basket cell: somatic targeting, perisomatic inhibition, gain control",
        connection_pattern={"inputs": ['pyramidal_l23', 'pyramidal_l4', 'interneuron_vip'], "outputs": ['pyramidal_l23', 'pyramidal_l4']},
        size_range=(100, 5000),
        motif_source="lateral_inhibitory",
        parameters={"reservoir_density": 0.15, "recurrent_pct": 0.15, "has_inhibition": True},
        capabilities=['somatic_inhibit', 'gain_control', 'perisomatic', 'spike_suppress'],
        task_hints=['gain_control', 'perisomatic_inhibit', 'spike_suppress'],
        lead_task_hint="gain_control",
        category="biological",
    ),
    "dopaminergic_snc": ModuleSpec(
        name="dopaminergic_snc",
        function="modulation",
        description="Substantia nigra dopaminergic: motor reward, basal ganglia gating",
        connection_pattern={"inputs": ['striatal_msn', 'spinal_motor_alpha'], "outputs": ['striatal_msn', 'spinal_motor_alpha', 'pyramidal_l5']},
        size_range=(50, 2000),
        motif_source="modulatory_diffuse",
        parameters={"reservoir_density": 0.2, "recurrent_pct": 0.25, "has_inhibition": False},
        capabilities=['reward_signal', 'motor_gate', 'reward_prediction_error', 'basal_ganglia'],
        task_hints=['reward_signal', 'motor_gate', 'rpe', 'basal_ganglia_mod'],
        lead_task_hint="reward_motor_gate",
        category="biological",
    ),
    "dopaminergic_vta": ModuleSpec(
        name="dopaminergic_vta",
        function="modulation",
        description="VTA dopaminergic: reward, motivation, learning signal to cortex",
        connection_pattern={"inputs": ['reward', 'memory'], "outputs": ['pyramidal_l23', 'striatal_msn', 'hippocampal_ca1']},
        size_range=(50, 2000),
        motif_source="modulatory_diffuse",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.3, "has_inhibition": False},
        capabilities=['reward_signal', 'motivation', 'learning_signal', 'cortical_mod'],
        task_hints=['reward_signal', 'motivation', 'learning_gate'],
        lead_task_hint="reward_motivation",
        category="biological",
    ),
    "serotonergic_raphe": ModuleSpec(
        name="serotonergic_raphe",
        function="modulation",
        description="Raphe serotonergic: mood, sleep, widespread modulation via volume transmission",
        connection_pattern={"inputs": ['memory', 'emotion'], "outputs": ['pyramidal_l23', 'hippocampal_ca1', 'thalamic_relay']},
        size_range=(50, 2000),
        motif_source="volume_transmission",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.35, "has_inhibition": False},
        capabilities=['mood_mod', 'sleep_gate', 'volume_transmission', 'widespread_mod'],
        task_hints=['mood_modulation', 'sleep_gate', 'widespread_mod'],
        lead_task_hint="mood_modulation",
        category="biological",
    ),
    "noradrenergic_lc": ModuleSpec(
        name="noradrenergic_lc",
        function="modulation",
        description="Locus coeruleus noradrenergic: arousal, alertness, attention, stress",
        connection_pattern={"inputs": ['spinal_motor_alpha', 'pain'], "outputs": ['pyramidal_l23', 'hippocampal_ca1', 'interneuron_pv']},
        size_range=(50, 2000),
        motif_source="modulatory_diffuse",
        parameters={"reservoir_density": 0.2, "recurrent_pct": 0.3, "has_inhibition": False},
        capabilities=['arousal', 'alertness', 'attention_mod', 'stress_response'],
        task_hints=['arousal_gate', 'alertness', 'attention_mod', 'stress'],
        lead_task_hint="arousal_alertness",
        category="biological",
    ),
    "cholinergic_mt": ModuleSpec(
        name="cholinergic_mt",
        function="modulation",
        description="Medial septum/Meynert cholinergic: hippocampal theta, attention, memory encoding",
        connection_pattern={"inputs": ['thalamic_relay'], "outputs": ['hippocampal_ca1', 'hippocampal_ca3', 'pyramidal_l23', 'interneuron_vip']},
        size_range=(50, 2000),
        motif_source="volume_transmission",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.25, "has_inhibition": False},
        capabilities=['theta_pacing', 'attention_gate', 'memory_encode', 'hippocampal_mod'],
        task_hints=['theta_pacing', 'attention_gate', 'memory_encode'],
        lead_task_hint="attention_memory_mod",
        category="biological",
    ),
    "retinal_gc": ModuleSpec(
        name="retinal_gc",
        function="sensory",
        description="Retinal ganglion cell: visual output, ON/OFF directional tuning",
        connection_pattern={"inputs": ['retinal_bipolar', 'retinal_amacrine'], "outputs": ['thalamic_relay', 'pyramidal_l4']},
        size_range=(1000, 100000),
        motif_source="topographic_mapping",
        parameters={"reservoir_density": 0.2, "recurrent_pct": 0.15, "has_inhibition": False},
        capabilities=['visual_output', 'direction_tuning', 'on_off', 'retinotopic'],
        task_hints=['visual_output', 'direction_tune', 'retinotopic_map'],
        lead_task_hint="visual_output",
        category="biological",
    ),
    "retinal_bipolar": ModuleSpec(
        name="retinal_bipolar",
        function="sensory",
        description="Retinal bipolar cell: photoreceptor-to-ganglion relay, ON/OFF channels",
        connection_pattern={"inputs": ['photoreceptor'], "outputs": ['retinal_gc', 'retinal_horizontal']},
        size_range=(1000, 100000),
        motif_source="feedforward_excitatory",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.2, "has_inhibition": False},
        capabilities=['photorelay', 'on_off_channel', 'linear_filter', 'retinal_intermediate'],
        task_hints=['on_off_channel', 'photorelay', 'linear_filter'],
        lead_task_hint="retinal_relay",
        category="biological",
    ),
    "retinal_horizontal": ModuleSpec(
        name="retinal_horizontal",
        function="sensory",
        description="Retinal horizontal cell: lateral inhibition, contrast enhancement, center-surround",
        connection_pattern={"inputs": ['retinal_bipolar'], "outputs": ['retinal_bipolar']},
        size_range=(1000, 100000),
        motif_source="lateral_inhibitory",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.3, "has_inhibition": True},
        capabilities=['lateral_inhibit', 'contrast_enhance', 'center_surround', 'retinal_lateral'],
        task_hints=['contrast_enhance', 'lateral_inhibit', 'center_surround'],
        lead_task_hint="retinal_contrast",
        category="biological",
    ),
    "retinal_amacrine": ModuleSpec(
        name="retinal_amacrine",
        function="sensory",
        description="Retinal amacrine cell: interneuron, motion detection, transient signals",
        connection_pattern={"inputs": ['retinal_gc', 'retinal_bipolar'], "outputs": ['retinal_gc', 'retinal_bipolar']},
        size_range=(1000, 100000),
        motif_source="lateral_inhibitory",
        parameters={"reservoir_density": 0.2, "recurrent_pct": 0.35, "has_inhibition": True},
        capabilities=['motion_detect', 'transient_signal', 'retinal_interneuron', 'feedback'],
        task_hints=['motion_detect', 'transient_signal', 'feedback_inhibit'],
        lead_task_hint="motion_detection",
        category="biological",
    ),
    "spinal_motor_alpha": ModuleSpec(
        name="spinal_motor_alpha",
        function="motor",
        description="Alpha motor neuron: somatic motor output, muscle fiber activation",
        connection_pattern={"inputs": ['pyramidal_l5', 'interneuron_sst', 'sensory'], "outputs": ['muscle_fiber']},
        size_range=(50, 500),
        motif_source="axo_dendritic",
        parameters={"reservoir_density": 0.1, "recurrent_pct": 0.1, "has_inhibition": True},
        capabilities=['motor_output', 'muscle_activate', 'alpha_motoneuron', 'reflex_arc'],
        task_hints=['motor_output', 'muscle_activate', 'reflex_arc'],
        lead_task_hint="motor_output",
        category="biological",
    ),
    "spinal_motor_gamma": ModuleSpec(
        name="spinal_motor_gamma",
        function="motor",
        description="Gamma motor neuron: muscle spindle feedback, proprioception",
        connection_pattern={"inputs": ['pyramidal_l5', 'dorsal_root_ganglion'], "outputs": ['muscle_spindle']},
        size_range=(50, 500),
        motif_source="axo_dendritic",
        parameters={"reservoir_density": 0.1, "recurrent_pct": 0.1, "has_inhibition": True},
        capabilities=['spindle_feedback', 'proprioception', 'gamma_motoneuron', 'muscle_tone'],
        task_hints=['spindle_feedback', 'proprioception', 'muscle_tone'],
        lead_task_hint="proprioception",
        category="biological",
    ),
    "cerebellar_purkinje": ModuleSpec(
        name="cerebellar_purkinje",
        function="motor_learning",
        description="Purkinje cell: cerebellar output, motor learning, error correction",
        connection_pattern={"inputs": ['cerebellar_granule', 'climbing_fiber', 'interneuron_basket'], "outputs": ['cerebellum_deep_nucleus']},
        size_range=(500, 5000),
        motif_source="axo_dendritic",
        parameters={"reservoir_density": 0.15, "recurrent_pct": 0.15, "has_inhibition": True},
        capabilities=['motor_learn', 'error_correction', 'cerebellar_output', 'precise_timing'],
        task_hints=['motor_learn', 'error_correct', 'precise_timing'],
        lead_task_hint="motor_learning",
        category="biological",
    ),
    "cerebellar_granule": ModuleSpec(
        name="cerebellar_granule",
        function="motor_learning",
        description="Cerebellar granule cell: input expansion, mossy fiber processing, densest neuron type",
        connection_pattern={"inputs": ['mossy_fiber', 'interneuron_golgi'], "outputs": ['cerebellar_purkinje', 'interneuron_stellate']},
        size_range=(10000, 500000),
        motif_source="feedforward_excitatory",
        parameters={"reservoir_density": 0.6, "recurrent_pct": 0.1, "has_inhibition": False},
        capabilities=['input_expand', 'mossy_fiber_process', 'combinatorial_code', 'high_density'],
        task_hints=['input_expand', 'combinatorial_code', 'mossy_fiber'],
        lead_task_hint="input_expansion",
        category="biological",
    ),
    "cerebellar_stellate": ModuleSpec(
        name="cerebellar_stellate",
        function="motor_learning",
        description="Cerebellar stellate cell: lateral inhibition between Purkinje cells, parallel fiber",
        connection_pattern={"inputs": ['cerebellar_purkinje', 'cerebellar_granule'], "outputs": ['cerebellar_purkinje']},
        size_range=(500, 5000),
        motif_source="lateral_inhibitory",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.3, "has_inhibition": True},
        capabilities=['lateral_inhibit', 'parallel_fiber', 'cerebellar_interneuron', 'coordination'],
        task_hints=['lateral_inhibit', 'parallel_fiber', 'coordination'],
        lead_task_hint="cerebellar_coordination",
        category="biological",
    ),
    "striatal_msn": ModuleSpec(
        name="striatal_msn",
        function="action_selection",
        description="Medium spiny neuron: striatal output, dopamine-modulated action selection",
        connection_pattern={"inputs": ['pyramidal_l5', 'dopaminergic_snc', 'dopaminergic_vta', 'glutamatergic_cortex'], "outputs": ['thalamus_relay', 'spinal_motor_alpha']},
        size_range=(1000, 100000),
        motif_source="modulatory_diffuse",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.2, "has_inhibition": False},
        capabilities=['action_select', 'dopamine_mod', 'basal_ganglia_output', 'habit_form'],
        task_hints=['action_select', 'basal_ganglia_out', 'habit_form'],
        lead_task_hint="action_selection",
        category="biological",
    ),
    "thalamic_relay": ModuleSpec(
        name="thalamic_relay",
        function="sensory_gate",
        description="Thalamic relay cell: sensory gateway, cortex-thalamus loop, sleep-wake gate",
        connection_pattern={"inputs": ['retinal_gc', 'sensory', 'interneuron_sst'], "outputs": ['pyramidal_l23', 'pyramidal_l4']},
        size_range=(100, 5000),
        motif_source="feedforward_excitatory",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.2, "has_inhibition": False},
        capabilities=['sensory_gate', 'cortex_thalamus_loop', 'sleep_wake_gate', 'thalamic_relay'],
        task_hints=['sensory_gate', 'thalamus_loop', 'sleep_wake_gate'],
        lead_task_hint="sensory_gate",
        category="biological",
    ),
    "thalamic_reticular": ModuleSpec(
        name="thalamic_reticular",
        function="sensory_gate",
        description="Thalamic reticular nucleus: gating inhibition, attention filter, sleep spindles",
        connection_pattern={"inputs": ['pyramidal_l23', 'thalamic_relay'], "outputs": ['thalamic_relay']},
        size_range=(100, 5000),
        motif_source="feedback_inhibitory",
        parameters={"reservoir_density": 0.2, "recurrent_pct": 0.25, "has_inhibition": True},
        capabilities=['gate_inhibit', 'attention_filter', 'sleep_spindle', 'thalamic_mod'],
        task_hints=['gate_inhibit', 'attention_filter', 'sleep_spindle'],
        lead_task_hint="thalamic_gate",
        category="biological",
    ),
    "hippocampal_ca1": ModuleSpec(
        name="hippocampal_ca1",
        function="memory",
        description="Hippocampal CA1: memory output, spatial memory, pattern completion",
        connection_pattern={"inputs": ['hippocampal_ca3', 'entorhinal_l3', 'cholinergic_mt'], "outputs": ['pyramidal_l23', 'entorhinal_l2']},
        size_range=(100, 5000),
        motif_source="feedforward_excitatory",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.35, "has_inhibition": False},
        capabilities=['memory_output', 'pattern_complete', 'spatial_memory', 'hippocampal_ca1'],
        task_hints=['memory_output', 'pattern_complete', 'spatial_memory'],
        lead_task_hint="memory_output",
        category="biological",
    ),
    "hippocampal_ca3": ModuleSpec(
        name="hippocampal_ca3",
        function="memory",
        description="Hippocampal CA3: recurrent mossy fiber, auto-associative memory, pattern completion",
        connection_pattern={"inputs": ['hippocampal_granule', 'interneuron_basket'], "outputs": ['hippocampal_ca1', 'hippocampal_ca3']},
        size_range=(100, 5000),
        motif_source="feedback_excitatory",
        parameters={"reservoir_density": 0.4, "recurrent_pct": 0.5, "has_inhibition": False},
        capabilities=['auto_associative', 'pattern_complete', 'recurrent_mossy', 'hippocampal_ca3'],
        task_hints=['auto_associative', 'pattern_complete', 'recurrent_mossy'],
        lead_task_hint="auto_associative_memory",
        category="biological",
    ),
    "hippocampal_granule": ModuleSpec(
        name="hippocampal_granule",
        function="memory",
        description="Dentate gyrus granule: input layer, pattern separation, pattern discrimination",
        connection_pattern={"inputs": ['entorhinal_l2', 'interneuron_basket'], "outputs": ['hippocampal_ca3']},
        size_range=(10000, 500000),
        motif_source="feedforward_excitatory",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.2, "has_inhibition": True},
        capabilities=['pattern_separate', 'input_expand', 'dentate_granule', 'discriminate'],
        task_hints=['pattern_separate', 'input_expand', 'discriminate'],
        lead_task_hint="pattern_separation",
        category="biological",
    ),
    "grid_cell": ModuleSpec(
        name="grid_cell",
        function="spatial_navigation",
        description="Grid cell: spatial navigation, hexagonal firing pattern, place code",
        connection_pattern={"inputs": ['hippocampal_ca1', 'spinal_motor_alpha'], "outputs": ['hippocampal_ca1']},
        size_range=(10, 500),
        motif_source="topographic_mapping",
        parameters={"reservoir_density": 0.3, "recurrent_pct": 0.35, "has_inhibition": False},
        capabilities=['spatial_map', 'grid_code', 'navigation', 'path_integration'],
        task_hints=['spatial_map', 'grid_code', 'path_integration'],
        lead_task_hint="spatial_navigation",
        category="biological",
    ),
    "orexin_neuron": ModuleSpec(
        name="orexin_neuron",
        function="arousal",
        description="Orexin (hypocretin) neuron: arousal, sleep-wake stability, energy balance",
        connection_pattern={"inputs": ['hypothalamus', 'temperature'], "outputs": ['noradrenergic_lc', 'serotonergic_raphe', 'cholinergic_mt']},
        size_range=(10, 500),
        motif_source="volume_transmission",
        parameters={"reservoir_density": 0.25, "recurrent_pct": 0.3, "has_inhibition": False},
        capabilities=['arousal_stability', 'sleep_wake_gate', 'energy_balance', 'orexin_mod'],
        task_hints=['arousal_stability', 'sleep_wake_gate', 'energy_balance'],
        lead_task_hint="arousal_stability",
        category="biological",
    ),
}


# ====================================================================== #
# 预设组合（Phase 2 新增）
# ====================================================================== #
PRESETS: dict[str, dict] = {
    "minimal_reflex": {
        "description": "最小反射弧：感知 → 执行（无记忆），最快响应",
        "modules": ["sensory", "motor"],
        "counts": {"sensory": 1, "motor": 1},
        "blueprint": "fast_reflex",
        "agents_per_module": 4,
        "seed": 42,
    },
    "cognitive_animal": {
        "description": "标准认知型：感知 → 记忆 → 整合 → 执行",
        "modules": ["sensory", "memory", "integration", "motor"],
        "counts": {"sensory": 1, "memory": 1, "integration": 1, "motor": 1},
        "blueprint": "sequential",
        "agents_per_module": 6,
        "seed": 42,
    },
    "multi_sensory_perceptor": {
        "description": "多模态感知者：3 个 sensory 并行（vision/sound/touch）+ 记忆整合",
        "modules": ["sensory", "memory", "motor"],
        "counts": {"sensory": 3, "memory": 1, "motor": 1},
        "variants": {"sensory": ["vision", "sound", "touch"]},
        "blueprint": "broad_explore",
        "agents_per_module": 6,
        "seed": 42,
    },
    "deep_thinker": {
        "description": "深度思考者：强记忆 + 工作记忆 + 元认知监控",
        "modules": ["sensory", "memory", "working_memory", "metacognition", "motor"],
        "counts": {"sensory": 1, "memory": 2, "working_memory": 1, "metacognition": 1, "motor": 1},
        "blueprint": "deep_reasoning",
        "agents_per_module": 8,
        "seed": 42,
    },
    "reward_learner": {
        "description": "强化学习者：奖赏 + 习惯固化 + 元认知",
        "modules": ["sensory", "memory", "reward", "habit", "motor"],
        "counts": {"sensory": 1, "memory": 1, "reward": 1, "habit": 1, "motor": 2},
        "blueprint": "orchestrated",
        "agents_per_module": 6,
        "seed": 42,
    },
    "planning_agent": {
        "description": "规划型 Agent：预测 + 规划 + 评估 + 执行",
        "modules": ["sensory", "memory", "predictor", "planner", "evaluator", "motor"],
        "counts": {"sensory": 1, "memory": 1, "predictor": 1, "planner": 1, "evaluator": 1, "motor": 1},
        "blueprint": "deep_reasoning",
        "agents_per_module": 6,
        "seed": 42,
    },
    "fast_reflexor": {
        "description": "快速反射者：多感知多执行，无记忆直接反应",
        "modules": ["sensory", "motor"],
        "counts": {"sensory": 2, "motor": 2},
        "blueprint": "fast_reflex",
        "agents_per_module": 4,
        "seed": 42,
    },
    "swarm_controller": {
        "description": "群控制器：多感知 + 全局整合 + 元认知监督",
        "modules": ["sensory", "memory", "integration", "metacognition", "motor"],
        "counts": {"sensory": 3, "memory": 2, "integration": 2, "metacognition": 1, "motor": 3},
        "blueprint": "orchestrated",
        "agents_per_module": 6,
        "seed": 42,
    },
    "self_adaptive_organism": {
        "description": "自适应生物：情感 + 免疫 + 成长 + 睡眠（完整自我维护）",
        "modules": ["sensory", "memory", "emotion", "immunity", "growth", "sleep", "motor"],
        "counts": {"sensory": 1, "memory": 1, "emotion": 1, "immunity": 1, "growth": 1, "sleep": 1, "motor": 1},
        "blueprint": "deep_reasoning",
        "agents_per_module": 6,
        "seed": 42,
    },
    "conscious_being": {
        "description": "意识生物：全局工作空间 + 元认知 + 情感 + 通信",
        "modules": ["sensory", "memory", "consciousness", "metacognition", "emotion", "communication", "motor"],
        "counts": {"sensory": 1, "memory": 1, "consciousness": 1, "metacognition": 1, "emotion": 1, "communication": 1, "motor": 1},
        "blueprint": "orchestrated",
        "agents_per_module": 6,
        "seed": 42,
    },
}


# ====================================================================== #
# 模块工厂接口
# ====================================================================== #
class ModuleFactory:
    """模块注册表与组合引擎"""

    @classmethod
    def list_modules(cls, category: Optional[str] = None) -> list[dict]:
        """列出所有模块（可选按 category 过滤）"""
        out = []
        for name, spec in MODULE_REGISTRY.items():
            if category and spec.category != category:
                continue
            out.append({
                "name": spec.name,
                "function": spec.function,
                "description": spec.description,
                "category": spec.category,
                "motif_source": spec.motif_source,
                "size_range": list(spec.size_range),
                "capabilities": spec.capabilities,
                "connection_pattern": spec.connection_pattern,
                "has_variants": bool(spec.variants),
                "variant_names": list(spec.variants.keys()),
            })
        return out

    @classmethod
    def get_module(cls, name: str) -> dict:
        """获取单个模块详情"""
        if name not in MODULE_REGISTRY:
            available = list(MODULE_REGISTRY.keys())
            raise ValueError(f"unknown module '{name}'. Available: {', '.join(available)}")
        spec = MODULE_REGISTRY[name]
        return asdict(spec)

    @classmethod
    def check_compatibility(cls, modules: list[str]) -> dict:
        """检查模块组合的兼容性

        兼容性规则：
        1. 没有循环依赖（拓扑排序检测）
        2. 没有过多的 motif 资源竞争（>2 个模块共享同一 motif 告警）
        3. 总节点数在合理范围内
        """
        specs = [MODULE_REGISTRY[m] for m in modules if m in MODULE_REGISTRY]
        missing = [m for m in modules if m not in MODULE_REGISTRY]

        if missing:
            return {"compatible": False, "error": f"unknown modules: {missing}"}

        conflicts = []

        # 检查循环依赖：构建有向图，用 DFS 拓扑排序检测
        graph: dict[str, set[str]] = {}
        module_inputs: dict[str, set[str]] = {}

        for spec in specs:
            graph[spec.name] = set()
            module_inputs[spec.name] = set(spec.connection_pattern.get("inputs", []))

        # 邻接表：module → 它输出的目标 modules
        for spec in specs:
            for out_mod in spec.connection_pattern.get("outputs", []):
                if out_mod in module_inputs:
                    graph[spec.name].add(out_mod)

        # DFS 循环检测
        visited = set()
        rec_stack = set()
        cycle_paths = []

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path + [neighbor])
                elif neighbor in rec_stack:
                    cycle_paths.append(path + [neighbor])
            rec_stack.discard(node)

        for spec in specs:
            if spec.name not in visited:
                dfs(spec.name, [spec.name])

        # 循环依赖是"软警告"而非硬冲突：生物学里回环反馈很常见
        # （recurrent_feedback / predictive_coding / reward loops 都含 cycle）
        # 所以这里只记录为警告，绝不作为 hard conflict 阻塞组合。
        cycle_warnings = []
        for cp in cycle_paths:
            unique_mods = set(cp)
            if len(unique_mods) >= 3:
                cycle_warnings.append({
                    "type": "long_cycle",
                    "path": " → ".join(cp),
                    "n_unique_modules": len(unique_mods),
                    "note": f"检测到循环反馈 ({len(unique_mods)} 模块)，"
                            f"在生物学里很常见（recurrent/predictive/reward 回路），仅作提示",
                })

        # 检查 motif 冲突：多个模块使用同一 motif 且功能相反
        motif_map: dict[str, list[str]] = {}
        for spec in specs:
            if spec.motif_source != "none":
                motif_map.setdefault(spec.motif_source, []).append(spec.name)

        for motif, mods in motif_map.items():
            if len(mods) > 3:
                conflicts.append({
                    "type": "motif_overload",
                    "motif": motif,
                    "modules": mods,
                    "note": f"过多模块 ({len(mods)}) 使用同一 motif '{motif}'，可能导致功能重叠",
                })

        # 统计
        motif_sources = sorted(set(s.motif_source for s in specs) - {"none"})
        total_size = (
            sum(s.size_range[0] for s in specs),
            sum(s.size_range[1] for s in specs),
        )

        return {
            "compatible": len(conflicts) == 0,
            "modules": modules,
            "n_modules": len(modules),
            "conflicts": conflicts,
            "cycle_warnings": cycle_warnings,
            "cycle_paths": cycle_paths[:5],  # 限制输出
            "motif_sources": motif_sources,
            "total_size_range": total_size,
        }

    @classmethod
    def compose_organism(cls, module_spec: dict) -> dict:
        """
        根据模块规格组合虚拟生物，真生成拓扑（Phase 2 集成 design_organism）

        module_spec: {
            "modules": ["sensory", "memory", "motor"],
            "counts": {"sensory": 2, "memory": 1, "motor": 1},  # 可选，同模块多副本
            "variants": {"sensory": ["vision", "sound"]},         # 可选，变体标签
            "blueprint": "sequential",                            # 可选，跨模块连接规则
            "agents_per_module": 6,                                # 可选，每模块节点数
            "seed": 42,
        }
        """
        # 延迟导入避免循环依赖
        try:
            from synthetic_bio_topology import design_organism
        except ImportError as e:
            return {
                "status": "error",
                "error": f"cannot import design_organism: {e}",
            }

        modules = module_spec.get("modules", [])
        counts = module_spec.get("counts", {})
        seed = int(module_spec.get("seed", 42))
        agents_per_module = int(module_spec.get("agents_per_module", 6))
        blueprint = module_spec.get("blueprint", None)
        variants = module_spec.get("variants", {})

        if not modules:
            return {"status": "error", "error": "modules list is empty"}

        # 展开模块列表（考虑计数）
        expanded = []
        for m in modules:
            n = counts.get(m, 1)
            expanded.extend([m] * n)

        # 兼容性检查
        compat = cls.check_compatibility(expanded)
        if not compat["compatible"]:
            return {
                "status": "error",
                "error": "incompatible modules",
                "compatibility": compat,
            }

        # 构建 design_organism 的 spec
        n_modules = len(expanded)
        
        # Phase 4: 变体真差异化 — 动态注入变体 profile 到 MODULE_PROFILES
        # 原理：design_organism 只支持 profile 名称映射，不支持参数覆盖。
        # 解法：为每个变体创建一个临时 profile（如 sensory_vision），参数覆盖后注入。
        # 变体 profile 名称格式：{base_module}_{variant_name}
        from synthetic_bio_topology import MODULE_PROFILES as _MODULE_PROFILES
        
        profile_map = {}
        variant_map = {}
        idx = 0
        for m in modules:
            n = counts.get(m, 1)
            v_list = variants.get(m, [])
            base_spec = MODULE_REGISTRY[m]
            for i in range(n):
                vname = v_list[i] if i < len(v_list) else f"{m}_v{i}" if n > 1 else None
                
                if vname and vname in base_spec.variants:
                    # 变体存在：动态注入参数覆盖的 profile
                    variant_profile_name = f"{m}_{vname}"
                    # 基于基础参数 + 变体覆盖创建新 profile
                    base_params = base_spec.parameters.copy()
                    base_params.update(base_spec.variants[vname])
                    new_profile = {
                        "description": f"{base_spec.description} ({vname} variant)",
                        "capability": list(base_spec.capabilities),
                        "task_hint_pool": list(base_spec.task_hints),
                        "lead_task_hint": base_spec.lead_task_hint,
                        "reservoir_density": base_params.get("reservoir_density", 0.25),
                        "recurrent_pct": base_params.get("recurrent_pct", 0.28),
                        "has_inhibition": base_params.get("has_inhibition", False),
                    }
                    _MODULE_PROFILES[variant_profile_name] = new_profile

                    profile_map[str(idx)] = variant_profile_name
                    variant_map[str(idx)] = {
                        "module": m,
                        "variant": vname,
                        "variant_profile": variant_profile_name,
                        "overrides": base_spec.variants[vname],
                    }
                else:
                    # 无变体或变体不存在：使用基础 profile
                    profile_map[str(idx)] = m
                    if vname:
                        variant_map[str(idx)] = {"module": m, "variant": vname}
                
                idx += 1
        
        spec = {
            "n_modules": n_modules,
            "agents_per_module": agents_per_module,
            "module_profiles": profile_map,  # {module_index_str: profile_name}，直接映射
        }

        # 如果指定了 blueprint，添加到 spec
        if blueprint:
            spec["blueprint"] = blueprint

        # 生成拓扑（真调用 design_organism）
        try:
            organism_full = design_organism(spec, seed=seed)
        except Exception as e:
            return {
                "status": "error",
                "error": f"design_organism failed: {e}",
                "module_spec": module_spec,
            }

        # 提取关键统计
        organism_data = organism_full.get("organism", {})
        stats = {
            "total_nodes": len(organism_data.get("nodes", [])),
            "total_edges": len(organism_data.get("edges", [])),
            "n_modules": n_modules,
            "n_unique_modules": len(modules),
            "n_variants_applied": sum(1 for v in variant_map.values() if v.get("variant_profile")),
            "motif_sources": compat["motif_sources"],
            "blueprint": blueprint,
            "blueprint_edges_added": organism_full.get("blueprint_edges_added", 0),
        }

        return {
            "status": "success",
            "organism": organism_full,
            "stats": stats,
            "compatibility": compat,
            "module_spec": module_spec,
            "variants": variant_map,
            "module_inventory": {
                "modules": modules,
                "counts": counts,
                "expanded": expanded,
                "blueprint": blueprint,
                "agents_per_module": agents_per_module,
            },
        }

    @classmethod
    def list_presets(cls) -> list[dict]:
        """列出所有预设组合"""
        out = []
        for name, p in PRESETS.items():
            out.append({
                "name": name,
                "description": p["description"],
                "modules": p["modules"],
                "counts": p["counts"],
                "blueprint": p.get("blueprint"),
                "n_total_modules": sum(p.get("counts", {}).values()),
                "has_variants": bool(p.get("variants")),
            })
        return out

    @classmethod
    def get_preset(cls, name: str) -> dict:
        """获取单个预设详情"""
        if name not in PRESETS:
            available = list(PRESETS.keys())
            raise ValueError(f"unknown preset '{name}'. Available: {', '.join(available)}")
        return dict(PRESETS[name])

    @classmethod
    def apply_preset(cls, preset_name: str, overrides: dict | None = None) -> dict:
        """应用预设组合并生成虚拟生物拓扑"""
        p = cls.get_preset(preset_name)
        if overrides:
            p.update(overrides)
        result = cls.compose_organism(p)
        result["preset_name"] = preset_name
        return result

    # ================================================================== #
    # Phase 5: SwarmLabs 集成（模块 → Agent 角色映射）
    # ================================================================== #
    @classmethod
    def to_swarmlabs(cls, organism_result: dict, name: str | None = None) -> dict:
        """把 compose_organism 的结果转为 SwarmLabs 多 Agent 团队 spec。

        调用 build_swarmlabs_config 完成 topology → agentteams 转换，
        并把每个模块的 role / capability / task_hint 映射到 SwarmLabs
        agent 字段，让下游 agent 直接按 profile_name 认领任务。

        返回：swarmlabs_agent_swarm schema（含 agents / modules / edges /
        guardrails / validation / motif_provenance / prov_json）。
        """
        from synthetic_bio_topology import build_swarmlabs_config

        org = organism_result.get("organism")
        if not org:
            return {"status": "error", "error": "organism_result has no 'organism' key"}

        # 用 spec.module_inventory 里的 blueprint 作为 name 兜底
        if not name:
            preset_name = organism_result.get("preset_name")
            if preset_name:
                name = f"{preset_name}_swarm"
            else:
                name = f"flybrain_organism_{org.get('generated_utc', 'anon')[:10]}"

        swarm_spec = build_swarmlabs_config(org, name=name)

        # 附加模块→Agent 映射摘要（方便用户直接看到每个模块的 Agent 角色）
        modules = swarm_spec["swarm"]["modules"]
        agents = swarm_spec["swarm"]["agents"]
        module_index = {nd["id"]: nd.get("module") for nd in org.get("organism", {}).get("nodes", [])
                        if nd.get("module") is not None}
        role_summary = []
        for mod in modules:
            lead = mod.get("lead")
            members = mod.get("members", [])
            lead_agent = next((a for a in agents if a["id"] == lead), None)
            role_summary.append({
                "module_index": mod["index"],
                "profile_name": mod.get("profile_name"),
                "lead_id": lead,
                "lead_role": lead_agent.get("swarm_role") if lead_agent else None,
                "lead_task_hint": lead_agent.get("task_hint") if lead_agent else None,
                "capability": mod.get("capability", []),
                "n_members": len(members),
                "recurrent_weight": mod.get("recurrent_weight"),
            })

        return {
            "status": "success",
            "swarm_spec": swarm_spec,
            "module_role_summary": role_summary,
            "n_agents": len(agents),
            "n_modules": len(modules),
            "n_edges": len(swarm_spec["swarm"]["edges"]),
            "validation_ok": swarm_spec["swarm"]["validation"]["ok"],
            "provenance_chain": {
                "motif_provenance": bool(swarm_spec.get("motif_provenance")),
                "prov_json": bool(swarm_spec.get("prov_json")),
                "blueprint": swarm_spec.get("blueprint"),
            },
        }

    @classmethod
    def get_module_agent_roles(cls) -> list[dict]:
        """列出所有模块到 SwarmLabs Agent 角色的映射表。

        让 SwarmLabs 用户一眼看到：选了哪些模块 = 会得到哪些 Agent 角色，
        每个角色的 task_hint / capability 是什么。
        """
        role_map = {
            "perceive": "sensor",
            "remember": "memory_agent",
            "manipulate": "working_memory_agent",
            "automatize": "habit_agent",
            "value_estimate": "reward_agent",
            "avoidance": "avoidance_agent",
            "monitor": "metacognition_agent",
            "execute": "executor",
            "synthesize": "integrator",
            "forecast": "predictor_agent",
            "assess": "evaluator_agent",
            "plan": "planner_agent",
            "motive": "motivation_agent",
            "guard": "guardrail_agent",
            "adapt": "evolution_agent",
            "integrate": "consciousness_agent",
            "maintain": "maintenance_agent",
            "broadcast": "communication_agent",
            "focus": "attention_agent",
        }
        out = []
        for name, spec in MODULE_REGISTRY.items():
            out.append({
                "module": name,
                "function": spec.function,
                "swarm_role": role_map.get(spec.function, "executor"),
                "lead_task_hint": spec.lead_task_hint,
                "task_hints": spec.task_hints,
                "capability": spec.capabilities,
                "category": spec.category,
                "motif_source": spec.motif_source,
            })
        return out

    # ================================================================== #
    # Phase 6: 虚拟生物市场（用户分享自定义组合）
    # ================================================================== #
    @classmethod
    def _market_dir(cls) -> Path:
        """市场目录（JSON 持久化）"""
        d = _HERE / ".." / "male_cns" / "virtual_organisms" / "market"
        d = d.resolve()
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def _market_index_path(cls) -> Path:
        return cls._market_dir() / "index.json"

    @classmethod
    def _load_market_index(cls) -> dict:
        p = cls._market_index_path()
        if not p.exists():
            return {"organisms": [], "updated_utc": None}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"organisms": [], "updated_utc": None}

    @classmethod
    def _save_market_index(cls, index: dict) -> None:
        index["updated_utc"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()
        cls._market_index_path().write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def save_market_organism(
        cls,
        name: str,
        module_spec: dict,
        description: str = "",
        tags: list[str] | None = None,
        author: str = "anonymous",
    ) -> dict:
        """保存自定义模块组合到市场。

        module_spec 与 compose_organism 入参相同（modules/counts/variants/
        blueprint/agents_per_module/seed）。保存时会先 compose 一次拿到
        stats 作为市场展示信息。
        """
        if not name or not isinstance(name, str):
            return {"status": "error", "error": "name is required"}
        if not module_spec or "modules" not in module_spec:
            return {"status": "error", "error": "module_spec.modules is required"}

        # 先 compose 验证组合可生成
        compose_result = cls.compose_organism(module_spec)
        if compose_result.get("status") != "success":
            return {
                "status": "error",
                "error": "cannot compose organism",
                "compose_error": compose_result.get("error"),
            }

        stats = compose_result.get("stats", {})
        # Tier 3: 生成防抄袭指纹
        try:
            sys_path = __import__("sys").path
            _scripts_dir = str(_MARKET_ROOT.parents[1] / "scripts") if "_MARKET_ROOT" in dir() else None
            if _scripts_dir and _scripts_dir not in sys_path:
                sys_path.insert(0, _scripts_dir)
            from fingerprint_organism import compute_fingerprint
            fingerprint = compute_fingerprint(compose_result)
        except Exception:
            fingerprint = "flybrain:organism-v1:unfingerprinted"

        entry = {
            "name": name,
            "description": description,
            "tags": tags or [],
            "author": author,
            "created_utc": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            "module_spec": module_spec,
            "fingerprint": fingerprint,
            "stats": {
                "total_nodes": stats.get("total_nodes"),
                "total_edges": stats.get("total_edges"),
                "n_modules": stats.get("n_modules"),
                "n_unique_modules": stats.get("n_unique_modules"),
                "n_variants_applied": stats.get("n_variants_applied", 0),
                "blueprint": stats.get("blueprint"),
            },
            "rating": {"score": 0.0, "n_ratings": 0, "comments": []},
        }

        # 写入 index.json（覆盖同名）
        index = cls._load_market_index()
        organisms = [o for o in index.get("organisms", []) if o.get("name") != name]
        organisms.append(entry)
        index["organisms"] = organisms
        cls._save_market_index(index)

        # 同时把完整拓扑 JSON 落盘，便于直接加载
        organism_path = cls._market_dir() / f"{name}.json"
        organism_path.write_text(
            json.dumps(compose_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "name": name,
            "path": str(organism_path),
            "stats": entry["stats"],
        }

    @classmethod
    def load_market_organism(cls, name: str) -> dict:
        """从市场加载指定组合（返回 module_spec + 已 compose 的拓扑）。"""
        p = cls._market_dir() / f"{name}.json"
        if not p.exists():
            return {"status": "error", "error": f"organism '{name}' not in market"}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return {"status": "error", "error": f"failed to load: {e}"}

    @classmethod
    def list_market_organisms(
        cls,
        tag: str | None = None,
        sort_by: str = "name",
        limit: int = 50,
    ) -> dict:
        """列出市场所有组合，支持按 tag 过滤和按 rating/name 排序。"""
        index = cls._load_market_index()
        organisms = index.get("organisms", [])

        if tag:
            organisms = [o for o in organisms if tag in o.get("tags", [])]

        if sort_by == "rating":
            organisms.sort(
                key=lambda o: o.get("rating", {}).get("score", 0.0),
                reverse=True,
            )
        elif sort_by == "nodes":
            organisms.sort(
                key=lambda o: o.get("stats", {}).get("total_nodes", 0),
                reverse=True,
            )
        elif sort_by == "created":
            organisms.sort(
                key=lambda o: o.get("created_utc", ""),
                reverse=True,
            )
        else:
            organisms.sort(key=lambda o: o.get("name", ""))

        organisms = organisms[:limit]

        return {
            "status": "success",
            "n_total": len(index.get("organisms", [])),
            "n_returned": len(organisms),
            "sort_by": sort_by,
            "tag_filter": tag,
            "organisms": [
                {
                    "name": o.get("name"),
                    "description": o.get("description", ""),
                    "tags": o.get("tags", []),
                    "author": o.get("author"),
                    "created_utc": o.get("created_utc"),
                    "stats": o.get("stats", {}),
                    "rating": {
                        "score": o.get("rating", {}).get("score", 0.0),
                        "n_ratings": o.get("rating", {}).get("n_ratings", 0),
                    },
                }
                for o in organisms
            ],
        }

    @classmethod
    def rate_market_organism(
        cls,
        name: str,
        score: float,
        comment: str = "",
        rater: str = "anonymous",
    ) -> dict:
        """给市场组合评分（1-5 分）。重复评分会追加到 comments。"""
        if not (1.0 <= score <= 5.0):
            return {"status": "error", "error": "score must be 1.0-5.0"}

        index = cls._load_market_index()
        organisms = index.get("organisms", [])
        target = next((o for o in organisms if o.get("name") == name), None)
        if target is None:
            return {"status": "error", "error": f"organism '{name}' not in market"}

        rating = target.setdefault("rating", {"score": 0.0, "n_ratings": 0, "comments": []})
        scores = [c.get("score", score) for c in rating.get("comments", [])]
        scores.append(score)
        rating["score"] = round(sum(scores) / len(scores), 2)
        rating["n_ratings"] = len(scores)
        rating.setdefault("comments", []).append({
            "score": score,
            "comment": comment,
            "rater": rater,
            "ts": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        })
        cls._save_market_index(index)

        return {
            "status": "success",
            "name": name,
            "score": rating["score"],
            "n_ratings": rating["n_ratings"],
        }

    @classmethod
    def search_market_organisms(cls, query: str, limit: int = 20) -> dict:
        """按关键词搜索市场组合（匹配 name/description/tags/modules）。"""
        if not query or not query.strip():
            return {"status": "error", "error": "query is required"}
        q = query.strip().lower()

        index = cls._load_market_index()
        matches = []
        for o in index.get("organisms", []):
            haystack = " ".join([
                o.get("name", ""),
                o.get("description", ""),
                " ".join(o.get("tags", [])),
                " ".join(o.get("module_spec", {}).get("modules", [])),
                o.get("module_spec", {}).get("blueprint", ""),
            ]).lower()
            if q in haystack:
                matches.append({
                    "name": o.get("name"),
                    "description": o.get("description", ""),
                    "tags": o.get("tags", []),
                    "stats": o.get("stats", {}),
                    "rating": {
                        "score": o.get("rating", {}).get("score", 0.0),
                        "n_ratings": o.get("rating", {}).get("n_ratings", 0),
                    },
                    "modules": o.get("module_spec", {}).get("modules", []),
                    "blueprint": o.get("module_spec", {}).get("blueprint"),
                })

        matches = matches[:limit]
        return {
            "status": "success",
            "query": query,
            "n_matches": len(matches),
            "organisms": matches,
        }

    @classmethod
    def delete_market_organism(cls, name: str) -> dict:
        """从市场删除组合（含 JSON 文件）。"""
        index = cls._load_market_index()
        before = len(index.get("organisms", []))
        index["organisms"] = [o for o in index.get("organisms", []) if o.get("name") != name]
        if len(index["organisms"]) == before:
            return {"status": "error", "error": f"organism '{name}' not in market"}
        cls._save_market_index(index)

        p = cls._market_dir() / f"{name}.json"
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                return {"status": "error", "error": f"index removed but file unlink failed: {e}"}

        return {"status": "success", "name": name}


# ====================================================================== #
# 导出
# ====================================================================== #
__all__ = ["MODULE_REGISTRY", "PRESETS", "ModuleFactory", "ModuleSpec"]
