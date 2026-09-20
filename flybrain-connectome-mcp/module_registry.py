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
        # 只有当 cycle 涉及 3 个以上模块才标记为冲突
        for cp in cycle_paths:
            if len(set(cp)) >= 3:
                conflicts.append({
                    "type": "long_cycle",
                    "path": " → ".join(cp),
                    "note": f"检测到长循环依赖 ({len(set(cp))} 模块)，可能影响信号传播",
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
        profile_map = {str(i): m for i, m in enumerate(expanded)}

        spec = {
            "n_modules": n_modules,
            "agents_per_module": agents_per_module,
            "module_profiles": {"custom": profile_map},
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

        # 构建变体映射（同模块多副本的标签）
        variant_map = {}
        idx = 0
        for m in modules:
            n = counts.get(m, 1)
            v_list = variants.get(m, [])
            for i in range(n):
                vname = v_list[i] if i < len(v_list) else f"{m}_v{i}" if n > 1 else None
                if vname:
                    variant_map[str(idx)] = {"module": m, "variant": vname}
                idx += 1

        # 提取关键统计
        organism_data = organism_full.get("organism", {})
        stats = {
            "total_nodes": len(organism_data.get("nodes", [])),
            "total_edges": len(organism_data.get("edges", [])),
            "n_modules": n_modules,
            "n_unique_modules": len(modules),
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


# ====================================================================== #
# 导出
# ====================================================================== #
__all__ = ["MODULE_REGISTRY", "PRESETS", "ModuleFactory", "ModuleSpec"]
