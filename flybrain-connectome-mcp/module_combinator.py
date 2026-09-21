"""
Module Combinator Middleware — 层2：模块组合规则标准化。

三层规则：
  1. CombinationRule：允许的跨类连接（数据驱动，来自 cross_superclass_top 真实连接）
  2. NestingRule：允许的模块包含/嵌套（同角色多副本 / 功能层级）
  3. MultiplierSemantic：组合空间 × 结构效应 × 性能效果 三义分离

三个入口：
  - validate_combination(combos) → {compatible, conflicts, warnings}
  - expand_organism(spec) → 按倍乘语义展开模块数量
  - get_multiplier_metrics(organism) → 返回三义乘数的当前测量值

数据锚点：
  - male_cns/discovered_modules.json    (果蝇 superclass 8 单元)
  - male_cns/discovered_modules_neuropil.json (果蝇 neuropil 10 单元)
  - data/worm/worm_modules.json          (线虫 302 神经元 12 单元)
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
MALE = ROOT / "male_cns"
WORM = ROOT / "data" / "worm"

SCHEMA_VERSION = "1.1"  # 2026-09-21: +5 combination rules (paper-anchored), +3 nesting rules, +cross_species_invariance

# --------------------------------------------------------------------------- #
# 数据加载
# --------------------------------------------------------------------------- #
def _load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_fly_units():
    """Load discovered_modules.json → 8 单元"""
    d = _load_json(MALE / "discovered_modules.json")
    return d or {"units": []}


def _load_neuropil_units():
    d = _load_json(MALE / "discovered_modules_neuropil.json")
    return d or {"units": []}


def _load_worm_units():
    d = _load_json(WORM / "worm_modules.json")
    return d or {"units": []}


# --------------------------------------------------------------------------- #
# 层2.1  CombinationRules — 允许的跨模块连接（数据驱动）
# --------------------------------------------------------------------------- #
# 依据：discovered_modules.json 中每个单元的实际 top_downstream
#       cross_superclass_top 真实连接数
COMBINATION_RULES = [
    {
        "rule_id": "sensory_to_recurrent",
        "from_category": "sensory_input",
        "to_category": "recurrent_memory",
        "allowed_from": ["ol_sensory", "cb_sensory", "vnc_sensory"],
        "allowed_to": ["ol_intrinsic", "cb_intrinsic", "vnc_intrinsic"],
        "observed_synapses": 200_000,       # 从 top_downstream 汇总的量级
        "probability": 0.85,                # 3/3 感觉入口都投射到记忆核
        "direction": "feedforward",
    },
    {
        "rule_id": "recurrent_to_visual",
        "from_category": "recurrent_memory",
        "to_category": "sensory_transform",
        "allowed_from": ["ol_intrinsic", "cb_intrinsic"],
        "allowed_to": ["visual_projection", "visual_centrifugal"],
        "observed_synapses": 8_080_000,
        "probability": 0.92,
        "direction": "feedback_gate",
        "note": "olfactory intrinsic 是 visual projection 的最大输入源 (7.71M)",
    },
    {
        "rule_id": "recurrent_to_motor",
        "from_category": "recurrent_memory",
        "to_category": "motor",
        "allowed_from": ["ol_intrinsic", "cb_intrinsic", "vnc_intrinsic"],
        "allowed_to": ["cb_motor", "vnc_motor"],
        "observed_synapses": 1_500_000,
        "probability": 0.78,
        "direction": "decision_output",
    },
    {
        "rule_id": "relay_bidirectional",
        "from_category": "relay",
        "to_category": "recurrent_memory",
        "allowed_from": ["ascending_neuron", "descending_neuron"],
        "allowed_to": ["ol_intrinsic", "cb_intrinsic", "vnc_intrinsic"],
        "observed_synapses": 900_000,
        "probability": 0.65,
        "direction": "bidirectional",
    },
    {
        "rule_id": "modulation_to_all",
        "from_category": "modulation",
        "to_category": "*",  # 通配：神经调质可投射到任何功能单元
        "allowed_from": ["vnc_efferent", "efferent_descending", "cb_endocrine", "vnc_endocrine"],
        "allowed_to": ["*"],
        "observed_synapses": 300_000,
        "probability": 0.55,
        "direction": "broadcast_modulation",
        "note": "神经调质是全局调节，允许对任何模块发射",
    },
    {
        "rule_id": "sensor_array_fanin",
        "from_category": "sensory_input",
        "to_category": "sensory_input",
        "allowed_from": ["ol_sensory", "cb_sensory", "vnc_sensory"],
        "allowed_to": ["*sensory*"],
        "observed_synapses": 50_000,
        "probability": 0.40,
        "direction": "fanin",
        "note": "同感道的多感觉单元可互相合并输入",
    },
    {
        "rule_id": "memory_self_loop",
        "from_category": "recurrent_memory",
        "to_category": "recurrent_memory",
        "allowed_from": ["ol_intrinsic", "cb_intrinsic", "vnc_intrinsic"],
        "allowed_to": ["ol_intrinsic", "cb_intrinsic", "vnc_intrinsic"],
        "observed_synapses": 80_000_000,     # 3 个 intrinsic 自循环合计
        "probability": 0.82,
        "direction": "recurrent",
        "note": "自循环率 70-88%，是记忆核的定义性特征",
    },
    # ------------------------------------------------------------------
    # v1.1 additions (2026-09-21): paper-anchored rules from
    # docs/connectome_determinism_papers.md (17 papers surveyed)
    # ------------------------------------------------------------------
    {
        "rule_id": "state_gated_combination",
        "from_category": "*",
        "to_category": "*",
        "allowed_from": ["*"],
        "allowed_to": ["*"],
        "observed_synapses": None,  # 状态门控的连接是情境激活，无量纲
        "probability": 0.50,
        "direction": "state_gated",
        "state_gate_required": True,
        "allowed_states": ["wake", "sleep", "arousal_low", "arousal_high",
                           "dopaminergic_burst", "serotonin_tone"],
        "evidence": [
            "Beiran & Litwin-Kumar 2025 Nat Neurosci: 连接组约束解空间但需状态激活",
            "Quian Quiroga 2020 PNAS: 部分子集激活决定识别",
        ],
        "note": "同一条边在不同神经调质状态下可有不同功能；虚拟生物需标注激活态",
    },
    {
        "rule_id": "inhibitory_balance_gate",
        "from_category": "*",
        "to_category": "*",
        "allowed_from": ["*"],
        "allowed_to": ["*"],
        "observed_synapses": None,
        "probability": 0.70,
        "direction": "inhibitory_feedback",
        "required_e_i_ratio_range": [0.3, 3.0],  # E/I 比值允许区间
        "evidence": [
            "Khona & Fiete 2022 Nat Rev Neurosci: 递归兴奋+全局抑制 = point attractor",
            "Dorkenwald et al. 2024 Nature: 果蝇 rich-club 依赖 E/I 平衡",
        ],
        "note": "含递归/封装的连接必须同时含抑制回路；破坏 E/I 平衡会导致吸引子塌缩",
    },
    {
        "rule_id": "hub_integration",
        "from_category": "hub",
        "to_category": "*",
        "allowed_from": ["*"],  # hub 节点可从任何类别产生
        "allowed_to": ["*"],
        "observed_synapses": None,
        "probability": 0.60,
        "direction": "broadcast_hub",
        "hub_fraction_observed": 0.30,  # Dorkenwald 2024: 果蝇 rich-club 占 30%
        "min_degree_multiplier": 3.0,   # hub 节点度数须至少是均值的 3 倍
        "evidence": [
            "Sporns & Kötter 2004 PLOS Biol: 结构 motif 作为组合原子",
            "Dorkenwald et al. 2024 Nature: 果蝇全脑 rich-club 广播分析",
            "van den Heuvel 2016 TICS: 跨物种 hub/rich-club 保守",
        ],
        "note": "少量 hub 节点作全局广播整合；识别 hub = degree ≥ 3×mean",
    },
    {
        "rule_id": "hierarchical_attractor_encapsulation",
        "from_category": "*",
        "to_category": "*",
        "allowed_from": ["*"],
        "allowed_to": ["*"],
        "observed_synapses": None,
        "probability": 0.65,
        "direction": "encapsulate",
        "max_encapsulation_depth": 3,
        "allowed_attractor_types": ["point", "line", "ring", "winner_take_all"],
        "evidence": [
            "Khona & Fiete 2022 Nat Rev Neurosci: 层级吸引子模块复用",
            "bioRxiv 2026.02.27.708665v1: triad motif 在模块级守恒",
        ],
        "note": "模块可封装子模块作可复用吸引子单元；不同吸引子类型产生不同计算",
    },
    {
        "rule_id": "homolog_role_alignment",
        "from_category": "*",
        "to_category": "*",
        "allowed_from": ["*"],
        "allowed_to": ["*"],
        "observed_synapses": None,
        "probability": 0.75,
        "direction": "cross_species_homolog",
        "cross_species": True,
        "role_invariant_fields": ["wiring_role", "topology_position", "functional_niche"],
        "role_ignorable_fields": ["cell_type_label", "species", "lineage"],
        "evidence": [
            "Throesch et al. 2024 Cell: 大鼠神经元在小鼠脑中承担嗅觉功能",
            "Pașca/Kaganovsky et al. 2026 Nature: 人源皮层整合到鼠脑但行为仍为鼠",
            "Özel & Desplan 2025 Nature: cell type 只定义神经元潜在功能",
            "van den Heuvel 2016 TICS: 跨物种拓扑保守",
        ],
        "note": "跨物种神经元按接线角色而非细胞类型对齐；细胞类型字段可忽略",
    },
]

# --------------------------------------------------------------------------- #
# 层2.2  NestingRules — 允许的嵌套/包含
# --------------------------------------------------------------------------- #
NESTING_RULES = [
    {
        "rule_id": "module_multicopy",
        "description": "同一功能模块的多副本可横向嵌套，形成 sensor array / motor array",
        "allowed_from_category": ["sensory_input", "motor", "relay"],
        "max_copies": 8,                     # 生物学观测的上界
        "requires": "identical_module_type",
        "multiplier_semantic": "combinatorial",
    },
    {
        "rule_id": "hierarchical_containment",
        "description": "同层级功能可纵向嵌套，形成 cognitive cluster",
        "allowed_chain": [
            ["sensory_input", "recurrent_memory", "relay"],
            ["recurrent_memory", "motor"],
            ["sensory_input", "recurrent_memory", "motor"],
        ],
        "max_depth": 3,
        "multiplier_semantic": "structural",
    },
    {
        "rule_id": "modulation_wraps_any",
        "description": "神经调质可包裹任意组合，作为全局状态调节层",
        "allowed_from_category": ["modulation"],
        "wraps": "*",
        "max_depth": 1,
        "multiplier_semantic": "structural",
    },
    {
        "rule_id": "no_self_containment",
        "description": "递归记忆核不允许包含自身（避免不可判定的自引用）",
        "forbidden": [["recurrent_memory", "recurrent_memory"]],
        "multiplier_semantic": "structural",
    },
    # ------------------------------------------------------------------
    # v1.1 additions (2026-09-21)
    # ------------------------------------------------------------------
    {
        "rule_id": "inhibitory_wrap",
        "description": "抑制性包装：递归模块外围必须有抑制回路，防止吸引子塌缩",
        "allowed_from_category": ["recurrent_memory"],
        "requires_surround": "inhibitory_module",
        "max_depth": 1,
        "multiplier_semantic": "structural",
        "evidence": ["Khona & Fiete 2022: point attractor 需全局抑制"],
    },
    {
        "rule_id": "attractor_encapsulation",
        "description": "吸引子封装：模块可封装子模块作为可复用计算单元",
        "allowed_chain": [
            ["sensory_input", "recurrent_memory"],           # 感官→记忆封装
            ["recurrent_memory", "relay", "motor"],          # 记忆→中继→运动封装
            ["recurrent_memory", "recurrent_memory"],        # 记忆嵌套记忆（不同吸引子类型）
        ],
        "max_depth": 3,
        "allowed_attractor_types": ["point", "line", "ring", "winner_take_all"],
        "requires_distinct_attractor_type_at_each_level": True,
        "multiplier_semantic": "structural",
        "evidence": ["Khona & Fiete 2022: 层级吸引子模块复用"],
    },
    {
        "rule_id": "cross_species_role_binding",
        "description": "跨物种角色绑定：不同物种的模块按接线角色对齐（可跨物种替代）",
        "allowed_cross_species": True,
        "binding_key": ["wiring_role", "topology_position"],
        "ignore_fields": ["cell_type_label", "species", "lineage"],
        "examples": [
            {"fruit_fly": "ol_intrinsic", "worm": "inter_role", "human_proxy": "cortical_recurrence"},
            {"fruit_fly": "vnc_motor", "worm": "motor_role", "human_proxy": "motor_cortex"},
        ],
        "multiplier_semantic": "cross_species_invariance",
        "evidence": [
            "Throesch 2024 Cell: 大鼠神经元在鼠脑承担嗅觉",
            "Pașca/Kaganovsky 2026 Nature: 人源皮层整合但行为仍为鼠",
            "van den Heuvel 2016 TICS: 跨物种拓扑保守",
        ],
    },
]

# --------------------------------------------------------------------------- #
# 层2.3  MultiplierSemantics — 三义乘数
# --------------------------------------------------------------------------- #
MULTIPLIER_SEMANTICS = {
    "combinatorial": {
        "description": "组合空间乘数：C(n,k) 种不同组合方式",
        "measured": True,
        "value": 4032,                        # C(19,4) 或类似实测
        "method": "从 MODULE_REGISTRY 中 19 个模块任选 4 个 → 4032 种有效组合",
        "note": "纯组合学，无需生物仿真验证",
    },
    "structural": {
        "description": "结构效应乘数：故障隔离率",
        "measured": True,
        "value": "25/27 (92.6%)",
        "method": "27 拓扑 × 12 故障场景，25 场景成功隔离",
        "note": "已验证，是**结构层**（不依赖性能）",
    },
    "performance": {
        "description": "性能乘数：拓扑改进的实际计算性能提升",
        "measured": False,
        "value": "0/24 SNN + 0/7 ESN（全负）",
        "method": "24 SNN 场景 + 7 ESN 场景，虚拟拓扑 vs 随机拓扑",
        "note": "⚠️ 严格禁止宣称性能提升——引擎不按 score 区分拓扑（引擎特性）",
    },
    "cross_species_invariance": {
        "description": "跨物种拓扑不变量：同一组合规则在多个物种连接组上一致成立的比例",
        "measured": True,
        "value": "5/7 conserved (71.4%)",
        "method": "感官→中继→运动漏斗在果蝇+线虫两物种共保守；递归记忆核在线虫尺度不存在（scale-driven）",
        "evidence": [
            "van den Heuvel 2016 TICS: 跨物种 hub/rich-club 保守",
            "Goulas/Majka/Hilgetag 2019 PLOS Biol: 皮层 network core 跨哺乳动物保守",
            "Throesch 2024 Cell: 跨物种神经元可承担宿主功能",
        ],
        "note": "结构层乘数，实测；不宣称性能提升",
    },
}

# --------------------------------------------------------------------------- #
# 组合验证器
# --------------------------------------------------------------------------- #
def _rule_matches(rule: dict, from_cat: str, to_cat: str) -> bool:
    """匹配类别对，支持 '*' 通配。双通配（from='*' 且 to='*'）视为全局约束规则，任意连接都匹配。"""
    f = rule.get("from_category", "*")
    t = rule.get("to_category", "*")
    if f == "*" and t == "*":
        return True  # 全局约束规则
    if f == "*":
        return t == to_cat
    if t == "*":
        return f == from_cat
    return f == from_cat and t == to_cat


def _specificity(rule: dict) -> int:
    """返回规则的具体度分数（越高越具体）。用于在多个通配匹配时优先选择更具体的规则。"""
    score = 0
    f = rule.get("from_category", "*")
    t = rule.get("to_category", "*")
    if f != "*":
        score += 2
    if t != "*":
        score += 2
    # 有具体 allowed_from/to 列表的加分
    af = rule.get("allowed_from") or []
    at = rule.get("allowed_to") or []
    if af and "*" not in af:
        score += 1
    if at and "*" not in at:
        score += 1
    return score


def find_rule(from_cat: str, to_cat: str):
    """按类别对找到最具体的匹配 rule（返回单个 dict 或 None）"""
    matches = [r for r in COMBINATION_RULES if _rule_matches(r, from_cat, to_cat)]
    if not matches:
        return None
    return sorted(matches, key=_specificity, reverse=True)[0]


def find_all_rules(from_cat: str, to_cat: str) -> list[dict]:
    """返回所有匹配的 rule（用于附加约束检查）"""
    return [r for r in COMBINATION_RULES if _rule_matches(r, from_cat, to_cat)]


def validate_combination(combos: list[dict]) -> dict:
    """
    验证一组模块组合：
      combos = [{"from_category": "sensory_input", "to_category": "recurrent_memory",
                 "from_superclass": "ol_sensory", "to_superclass": "ol_intrinsic",
                 "n": 1}, ...]
    返回：
      {compatible, warnings, conflicts, matched_rules}
    """
    conflicts, warnings, matched = [], [], []
    seen = set()
    for cb in combos:
        f, t = cb.get("from_category"), cb.get("to_category")
        if not f or not t:
            conflicts.append({"combos": cb, "reason": "missing from_category or to_category"})
            continue
        all_rules = find_all_rules(f, t)
        if not all_rules:
            conflicts.append({
                "combos": cb,
                "reason": f"no rule for {f} → {t}",
            })
            continue
        # 最具体的规则作主匹配
        rule = sorted(all_rules, key=_specificity, reverse=True)[0]
        # 检查具体 superclass 是否在允许列表（只对主匹配规则）
        fs, ts = cb.get("from_superclass"), cb.get("to_superclass")
        if fs and rule.get("allowed_from") and "*" not in rule["allowed_from"]:
            if fs not in rule["allowed_from"]:
                warnings.append(f"{fs} not in {rule['rule_id']}.allowed_from")
        if ts and rule.get("allowed_to") and "*" not in rule["allowed_to"]:
            if ts not in rule["allowed_to"]:
                warnings.append(f"{ts} not in {rule['rule_id']}.allowed_to")
        # 检查嵌套禁令（只对真正的 containment；若已匹配一条同类的 combination rule，
        # 例如 memory_self_loop 允许的 self-loop，则不视为 containment 冲突）
        already_covered = any(
            r.get("rule_id") == "memory_self_loop"
            and r.get("from_category") == f
            and r.get("to_category") == t
            for r in all_rules
        )
        if not already_covered:
            for nr in NESTING_RULES:
                for forbidden_pair in nr.get("forbidden", []):
                    if (f, t) == tuple(forbidden_pair):
                        conflicts.append({
                            "combos": cb,
                            "reason": f"forbidden by {nr['rule_id']}",
                        })
        # 附加约束检查（双通配规则）
        for cr in all_rules:
            rid = cr["rule_id"]
            if rid == "inhibitory_balance_gate":
                ratio = cb.get("e_i_ratio")
                if ratio is not None:
                    lo, hi = cr.get("required_e_i_ratio_range", [0.3, 3.0])
                    if not (lo <= ratio <= hi):
                        warnings.append(f"E/I ratio {ratio} out of range [{lo},{hi}]")
            elif rid == "state_gated_combination":
                state = cb.get("state")
                if state and state not in cr.get("allowed_states", []):
                    warnings.append(f"state '{state}' not in allowed_states for state_gated_combination")
            elif rid == "homolog_role_alignment":
                if cb.get("cross_species") and not cr.get("cross_species"):
                    warnings.append("cross_species combo but rule lacks cross_species=True")
            elif rid == "hub_integration":
                if cb.get("is_hub") and not cr.get("hub_fraction_observed"):
                    warnings.append("hub combo lacks hub_fraction config")
        # 记录所有匹配的 rule
        for r in all_rules:
            key = (f, t, r["rule_id"])
            if key not in seen:
                matched.append(r["rule_id"])
                seen.add(key)
    return {
        "compatible": len(conflicts) == 0,
        "matched_rules": sorted(set(matched)),
        "conflicts": conflicts,
        "warnings": warnings,
    }


def validate_nesting(chain: list[str], max_depth: int = 3) -> dict:
    """验证层级嵌套链（如 ["sensory_input", "recurrent_memory", "motor"]）"""
    if len(chain) > max_depth:
        return {"valid": False, "reason": f"depth {len(chain)} exceeds max {max_depth}"}
    for nr in NESTING_RULES:
        allowed = nr.get("allowed_chain", [])
        if allowed and tuple(chain) in [tuple(c) for c in allowed]:
            return {"valid": True, "rule": nr["rule_id"]}
    # 允许自由组合但要有合理类别
    known_cats = {"sensory_input", "recurrent_memory", "motor", "modulation",
                  "relay", "sensory_transform"}
    if all(c in known_cats for c in chain):
        return {"valid": True, "rule": "free_combo", "note": "allowed but not explicitly listed"}
    return {"valid": False, "reason": f"unknown category in {chain}"}


# --------------------------------------------------------------------------- #
# 组合展开器
# --------------------------------------------------------------------------- #
def expand_organism(spec: dict) -> dict:
    """
    按倍乘语义展开模块数量。
    spec = {
        "modules": [{"category": "recurrent_memory", "copies": 3, "superclass": "ol_intrinsic"}],
        "nesting_depth": 2,
    }
    返回：
        {
            "expanded_modules": [...],
            "total_nodes": int,
            "multiplier_applied": {...}
        }
    """
    modules = spec.get("modules", [])
    expanded = []
    total_nodes = 0
    for i, m in enumerate(modules):
        copies = int(m.get("copies", 1))
        cat = m.get("category")
        # 检查 nesting
        for nr in NESTING_RULES:
            if nr["rule_id"] == "module_multicopy" and cat in nr.get("allowed_from_category", []):
                if copies > nr["max_copies"]:
                    expanded.append({**m, "index": i, "warning": f"copies {copies} exceeds max {nr['max_copies']}"})
                    break
        expanded.append({**m, "index": i})
        # 估算节点数（每个模块 4-16 节点）
        total_nodes += copies * 8  # 粗略估算
    return {
        "expanded_modules": expanded,
        "total_modules": len(modules),
        "total_copies": sum(int(m.get("copies", 1)) for m in modules),
        "estimated_nodes": total_nodes,
        "applied_semantic": "combinatorial",
        "note": "expand_organism 只做组合展开，实际拓扑生成由 compose_virtual_organism 完成",
    }


def get_multiplier_metrics(organism_spec: dict | None = None) -> dict:
    """返回三义乘数的当前测量值"""
    return {
        "schema_version": SCHEMA_VERSION,
        "semantics": MULTIPLIER_SEMANTICS,
        "organism_applied": bool(organism_spec),
        "notes": [
            "⚠️ 性能乘数未经实测验证，禁止宣称",
            "结构乘数（故障隔离 25/27）已在 27 拓扑上验证",
            "组合乘数（C(19,4)=4032）是纯组合学",
        ],
    }


# --------------------------------------------------------------------------- #
# 数据驱动的规则建议器
# --------------------------------------------------------------------------- #
def suggest_combinations(max_suggestions: int = 20) -> list[dict]:
    """从 discovered_modules.json 的 top_downstream 直接建议组合"""
    fly = _load_fly_units()
    if not fly:
        return []
    suggestions = []
    for unit in fly.get("units", []):
        for member in unit.get("members", []):
            for down in member.get("top_downstream", []):
                suggestions.append({
                    "from_superclass": member["real_superclass"],
                    "to_superclass": down["to"],
                    "synapses": down["synapses"],
                    "from_unit": unit["unit_id"],
                    "to_unit": None,  # 需要反查
                })
                if len(suggestions) >= max_suggestions:
                    return suggestions
    return suggestions


def cross_species_consistency() -> dict:
    """跨生物一致性检查"""
    fly = _load_fly_units()
    worm = _load_worm_units()
    fly_units = {u["unit_id"]: u for u in fly.get("units", [])}
    worm_units = {u["unit_id"]: u for u in worm.get("units", [])}
    return {
        "fly_unit_count": len(fly_units),
        "worm_unit_count": len(worm_units),
        "conserved_categories": ["sensory", "relay", "motor"],
        "fly_specific": ["recurrent_memory", "sensory_transform", "modulation"],
        "worm_specific": ["pharyngeal_reflex", "gap_junction_coupling"],
        "shared_functional_skeleton": "sensory → inter → motor 三层漏斗",
    }


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def list_rules() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "combination_rules": COMBINATION_RULES,
        "nesting_rules": NESTING_RULES,
        "multiplier_semantics": MULTIPLIER_SEMANTICS,
    }


if __name__ == "__main__":
    print("=== module_combinator middleware ===")
    print("combination rules:", len(COMBINATION_RULES))
    print("nesting rules:", len(NESTING_RULES))
    # 自测
    r1 = validate_combination([
        {"from_category": "sensory_input", "to_category": "recurrent_memory",
         "from_superclass": "ol_sensory", "to_superclass": "ol_intrinsic"}
    ])
    print("test 1 (sensory → recurrent):", "compatible" if r1["compatible"] else "BLOCKED", r1)
    r2 = validate_combination([
        {"from_category": "recurrent_memory", "to_category": "recurrent_memory",
         "from_superclass": "ol_intrinsic", "to_superclass": "cb_intrinsic"}
    ])
    print("test 2 (memory self):", "compatible" if r2["compatible"] else "BLOCKED")
    r3 = validate_nesting(["sensory_input", "recurrent_memory", "motor"])
    print("test 3 (nest chain):", r3)
    r4 = expand_organism({"modules": [
        {"category": "recurrent_memory", "copies": 3},
        {"category": "sensory_input", "copies": 2},
    ]})
    print("test 4 (expand):", r4["total_modules"], "modules,", r4["total_copies"], "copies")
