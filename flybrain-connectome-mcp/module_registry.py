"""
module_registry.py  --  虚拟生物模块化工厂注册表

设计哲学：
    不是生物学物种，而是功能模块。每个模块是一个独立的功能单元，有：
    - name: 模块标识
    - function: 核心功能（感知、决策、记忆、执行...）
    - connection_pattern: 输入输出连接模式
    - size_range: 节点数量范围（可扩展）
    - motif_source: 追溯到 MaleCNS v1.0 的哪个 motif
    - parameters: 拓扑参数（reservoir_density, recurrent_pct, has_inhibition）

    虚拟生物 = 模块的不同组合 + 不同数量
    - 新模块 → 增加种类
    - 同模块多副本 → 增加数量（如 3 个 sensory 模块并行处理不同模态）
"""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


# ====================================================================== #
# 模块注册表（扩展版）
# ====================================================================== #
@dataclass
class ModuleSpec:
    """模块规格定义"""
    name: str
    function: str                    # 核心功能类别
    description: str
    connection_pattern: dict         # 输入/输出连接模式
    size_range: tuple[int, int]      # (min_nodes, max_nodes)
    motif_source: str                # 追溯到哪个 Motif（或 "none"）
    parameters: dict                 # 拓扑参数
    capabilities: list[str]          # SwarmLabs 消费语义
    task_hints: list[str]            # 任务提示池
    lead_task_hint: str              # 主导任务提示
    category: str                    # basic | biological | synthetic


# 模块注册表
MODULE_REGISTRY: dict[str, ModuleSpec] = {
    # --------------------------------------------------------------- #
    # 基础感知模块（输入层）
    # --------------------------------------------------------------- #
    "sensory": ModuleSpec(
        name="sensory",
        function="perceive",
        description="高密度输入缓冲，模拟 ol_intrinsic 层特征",
        connection_pattern={"inputs": ["external"], "outputs": ["memory", "attention"]},
        size_range=(8, 32),
        motif_source="none",
        parameters={
            "reservoir_density": 0.50,
            "recurrent_pct": 0.10,
            "has_inhibition": False,
        },
        capabilities=["perceive", "ingest", "buffer"],
        task_hints=["data_ingest", "signal_preprocess", "stream_buffer", "sensor_noise_filter"],
        lead_task_hint="input_triage",
        category="basic",
    ),

    "attention": ModuleSpec(
        name="attention",
        function="focus",
        description="选择性注意门控，模拟视网膜/皮层侧抑制",
        connection_pattern={"inputs": ["sensory"], "outputs": ["memory", "motor", "integration"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={
            "reservoir_density": 0.15,
            "recurrent_pct": 0.20,
            "has_inhibition": True,
        },
        capabilities=["focus", "filter", "prioritize", "salience_detection"],
        task_hints=["attention_focus", "salience_detection", "filter_irrelevant", "prioritize_signal"],
        lead_task_hint="attention_allocation",
        category="biological",
    ),

    # --------------------------------------------------------------- #
    # 记忆模块（状态层）
    # --------------------------------------------------------------- #
    "memory": ModuleSpec(
        name="memory",
        function="remember",
        description="递归工作记忆，模拟 cb_intrinsic 层",
        connection_pattern={"inputs": ["sensory", "attention"], "outputs": ["integration", "working_memory"]},
        size_range=(8, 48),
        motif_source="recurrent_feedback",
        parameters={
            "reservoir_density": 0.20,
            "recurrent_pct": 0.40,
            "has_inhibition": False,
        },
        capabilities=["gp_surrogate", "remember", "replay", "state_carry"],
        task_hints=["gp_surrogate_fit", "prior_recall", "state_carry", "history_replay"],
        lead_task_hint="memory_synthesis",
        category="biological",
    ),

    "working_memory": ModuleSpec(
        name="working_memory",
        function="manipulate",
        description="短期活跃记忆，用于操作和更新",
        connection_pattern={"inputs": ["memory", "attention"], "outputs": ["integration", "metacognition"]},
        size_range=(4, 24),
        motif_source="recurrent_feedback",
        parameters={
            "reservoir_density": 0.35,
            "recurrent_pct": 0.45,
            "has_inhibition": False,
        },
        capabilities=["hold", "manipulate", "update", "active_recall"],
        task_hints=["working_hold", "active_manipulation", "state_update", "short_term_recall"],
        lead_task_hint="working_memory_update",
        category="biological",
    ),

    # --------------------------------------------------------------- #
    # 决策模块（评估层）
    # --------------------------------------------------------------- #
    "reward": ModuleSpec(
        name="reward",
        function="value_estimate",
        description="多巴胺能奖赏调制，模拟 PPL/PAM",
        connection_pattern={"inputs": ["motor", "integration"], "outputs": ["motor"]},
        size_range=(4, 16),
        motif_source="inhibitory_hub",
        parameters={
            "reservoir_density": 0.25,
            "recurrent_pct": 0.30,
            "has_inhibition": False,
        },
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
        parameters={
            "reservoir_density": 0.25,
            "recurrent_pct": 0.30,
            "has_inhibition": True,
        },
        capabilities=["punish_signal", "penalty_estimate", "avoidance_gate", "negative_reinforce"],
        task_hints=["penalty_estimate", "avoidance_gate", "negative_reinforce", "risk_downweight"],
        lead_task_hint="punishment_allocation",
        category="biological",
    ),

    # --------------------------------------------------------------- #
    # 执行模块（输出层）
    # --------------------------------------------------------------- #
    "motor": ModuleSpec(
        name="motor",
        function="execute",
        description="运动输出，带局部抑制，模拟 vnc_intrinsic",
        connection_pattern={"inputs": ["integration", "attention"], "outputs": ["external"]},
        size_range=(4, 16),
        motif_source="none",
        parameters={
            "reservoir_density": 0.10,
            "recurrent_pct": 0.10,
            "has_inhibition": True,
        },
        capabilities=["execute", "actuate", "numeric_integration", "verify_output"],
        task_hints=["experiment_run", "numeric_integration", "output_check", "actuation_dispatch"],
        lead_task_hint="output_coordination",
        category="basic",
    ),

    # --------------------------------------------------------------- #
    # 整合模块（协调层）
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
        parameters={
            "reservoir_density": 0.30,
            "recurrent_pct": 0.25,
            "has_inhibition": True,
        },
        capabilities=["rank", "synthesize", "arbitrate", "elo_score"],
        task_hints=["candidate_rank", "cross_domain_bridge", "elo_scoring", "arbitrate_conflict"],
        lead_task_hint="cross_module_arbitration",
        category="basic",
    ),

    # --------------------------------------------------------------- #
    # 高级认知模块
    # --------------------------------------------------------------- #
    "habit": ModuleSpec(
        name="habit",
        function="automatize",
        description="程序性习惯固化，模拟 MBON",
        connection_pattern={"inputs": ["motor", "reward"], "outputs": ["motor"]},
        size_range=(4, 20),
        motif_source="recurrent_feedback",
        parameters={
            "reservoir_density": 0.30,
            "recurrent_pct": 0.50,
            "has_inhibition": False,
        },
        capabilities=["automatize", "chunk", "procedural_consolidate", "skill_encode"],
        task_hints=["skill_chunk", "procedural_consolidate", "automatize_step", "habit_encode"],
        lead_task_hint="habit_consolidation",
        category="biological",
    ),

    "metacognition": ModuleSpec(
        name="metacognition",
        function="monitor",
        description="元认知监控，模拟 CRE/DCHB",
        connection_pattern={"inputs": ["integration", "working_memory"], "outputs": ["integration", "motor"]},
        size_range=(2, 12),
        motif_source="inhibitory_hub",
        parameters={
            "reservoir_density": 0.20,
            "recurrent_pct": 0.35,
            "has_inhibition": True,
        },
        capabilities=["confidence_estimate", "uncertainty_detect", "meta_monitor", "calibration"],
        task_hints=["confidence_estimate", "uncertainty_flag", "meta_monitor", "calibration_check"],
        lead_task_hint="metacognitive_monitor",
        category="biological",
    ),

    # --------------------------------------------------------------- #
    # 合成模块（无生物学先验，纯功能定义）
    # --------------------------------------------------------------- #
    "predictor": ModuleSpec(
        name="predictor",
        function="forecast",
        description="预测编码模块，生成自上而下预测",
        connection_pattern={"inputs": ["integration"], "outputs": ["memory", "working_memory"]},
        size_range=(4, 16),
        motif_source="recurrent_feedback",
        parameters={
            "reservoir_density": 0.30,
            "recurrent_pct": 0.40,
            "has_inhibition": False,
        },
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
        parameters={
            "reservoir_density": 0.25,
            "recurrent_pct": 0.30,
            "has_inhibition": True,
        },
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
        parameters={
            "reservoir_density": 0.20,
            "recurrent_pct": 0.35,
            "has_inhibition": False,
        },
        capabilities=["plan", "sequence", "schedule", "delegate"],
        task_hints=["task_planning", "sequence_generation", "resource_allocation"],
        lead_task_hint="task_planning",
        category="synthetic",
    ),
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
        1. 没有循环依赖（A→B→A 形成闭环）
        2. 没有重复的 motif 来源导致资源竞争
        3. 总节点数在合理范围内
        """
        specs = [MODULE_REGISTRY[m] for m in modules if m in MODULE_REGISTRY]
        missing = [m for m in modules if m not in MODULE_REGISTRY]

        if missing:
            return {"compatible": False, "error": f"unknown modules: {missing}"}

        conflicts = []

        # 检查循环依赖：使用拓扑排序检测
        # 构建有向图：module → outputs → downstream modules
        graph: dict[str, set[str]] = {}
        module_outputs: dict[str, set[str]] = {}
        module_inputs: dict[str, set[str]] = {}

        for spec in specs:
            graph[spec.name] = set()
            module_outputs[spec.name] = set(spec.connection_pattern.get("outputs", []))
            module_inputs[spec.name] = set(spec.connection_pattern.get("inputs", []))

        # 构建邻接表
        for spec in specs:
            for out_mod in module_outputs[spec.name]:
                if out_mod in module_inputs:
                    graph[spec.name].add(out_mod)

        # 拓扑排序检测循环
        visited = set()
        rec_stack = set()
        has_cycle = False

        def dfs(node: str) -> None:
            nonlocal has_cycle
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    has_cycle = True
                    conflicts.append({
                        "type": "cycle",
                        "path": f"{node} → {neighbor}",
                        "note": f"检测到循环依赖: {node} → {neighbor}",
                    })
            rec_stack.discard(node)

        for spec in specs:
            if spec.name not in visited:
                dfs(spec.name)

        # 检查 motif 冲突：多个模块使用同一 motif 但功能相反
        motif_map: dict[str, list[str]] = {}
        for spec in specs:
            if spec.motif_source != "none":
                motif_map.setdefault(spec.motif_source, []).append(spec.name)

        for motif, mods in motif_map.items():
            if len(mods) > 2:
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
            "motif_sources": motif_sources,
            "total_size_range": total_size,
        }

    @classmethod
    def compose_organism(cls, module_spec: dict) -> dict:
        """
        根据模块规格组合虚拟生物

        module_spec: {
            "modules": ["sensory", "memory", "motor"],
            "counts": {"sensory": 2, "memory": 1, "motor": 1},  # 可选，同模块多副本
            "seed": 42,
        }
        """
        modules = module_spec.get("modules", [])
        counts = module_spec.get("counts", {})
        seed = module_spec.get("seed", 42)

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

        # 构建 organism
        import random
        rng = random.Random(seed)

        organism = {
            "modules": [],
            "edges": [],
            "stats": {},
        }

        node_id = 0
        for i, mname in enumerate(expanded):
            spec = MODULE_REGISTRY[mname]
            # 在 size_range 内随机选取节点数
            n_nodes = rng.randint(spec.size_range[0], spec.size_range[1])
            organism["modules"].append({
                "id": i,
                "name": mname,
                "function": spec.function,
                "n_nodes": n_nodes,
                "motif_source": spec.motif_source,
                "parameters": spec.parameters,
            })
            node_id += n_nodes

        organism["stats"] = {
            "total_nodes": node_id,
            "n_modules": len(expanded),
            "motif_sources": compat["motif_sources"],
            "size_range": compat["total_size_range"],
        }

        return {
            "status": "success",
            "organism": organism,
            "compatibility": compat,
        }


# ====================================================================== #
# 导出
# ====================================================================== #
__all__ = ["MODULE_REGISTRY", "ModuleFactory", "ModuleSpec"]
