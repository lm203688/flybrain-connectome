"""
drosophila_connectome / server.py
-------------------------------
Minimal MCP (Model Context Protocol) server over stdio, implemented with the
Python standard library only — no third-party MCP SDK required, so it runs
anywhere the data + numpy + pyarrow are available.

It exposes the connectome query layer (core.py) as MCP `tools`. Compatible with
any MCP client that speaks JSON-RPC 2.0 over stdio (Claude Desktop, WorkBuddy,
Cursor, etc.).

Run:
    python -m mcp_connectome.server
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import core
from module_registry import ModuleFactory

PROTOCOL_VERSION = "2024-11-05"

# ---- path to the SwarmLabs derived motif artifact (NOT the raw neuron data) ----
_MOTIFS_DIR = os.path.dirname(os.path.abspath(__file__))      # .../mcp_connectome
MOTIF_FILE = os.path.abspath(os.path.join(_MOTIFS_DIR, "..", "motifs",
                                           "swarm_agent_topology_motifs.json"))
EXTRACT_SCRIPT = os.path.abspath(os.path.join(_MOTIFS_DIR, "..", "extract_motifs.py"))
_STACKED_REPORT = os.path.abspath(os.path.join(_MOTIFS_DIR, "..", "..",
                                               "male_cns", "stacked_blueprints.json"))
_NEUROFIL_STATS = os.path.abspath(os.path.join(_MOTIFS_DIR, "..", "..",
                                               "male_cns", "neuropil_stats.json"))


def export_swarm_motifs(refresh: bool = False):
    """Return the latest SwarmLabs agent-topology motifs (real, derived from
    MaleCNS v1.0). If refresh=True, re-run extract_motifs.py first so the caller
    always gets the freshest derived artifact (real-time pull)."""
    if refresh:
        import subprocess
        env = dict(os.environ)
        env.setdefault("FLYBRAIN_DATA_DIR",
                       os.environ.get("FLYBRAIN_DATA_DIR", ""))
        try:
            subprocess.run([sys.executable, EXTRACT_SCRIPT], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=900, check=False)
        except Exception:
            pass
    if not os.path.exists(MOTIF_FILE):
        raise FileNotFoundError(
            "motif file not found: %s (run extract_motifs.py first)" % MOTIF_FILE)
    with open(MOTIF_FILE, encoding="utf-8") as fh:
        return json.load(fh)

TOOLS = [
    {
        "name": "connectome_overview",
        "description": "返回雄性果蝇脑连接组 (MaleCNS v1.0) 的高层真实统计：总突触数、平均输入输出度、注释神经元数、Top 枢纽神经元。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "neuron_info",
        "description": "查询某个神经元 (body id 整数) 的完整元数据：细胞类型、超类、神经递质预测、胞体神经节、以及输入/输出突触总数。",
        "inputSchema": {
            "type": "object",
            "properties": {"body": {"type": "integer",
                                    "description": "神经元 bodyId，如 58130"}},
            "required": ["body"],
        },
    },
    {
        "name": "pair_synapses",
        "description": "神经元 A (body_pre) 到神经元 B (body_post) 之间有多少突触？返回整数。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pre": {"type": "integer", "description": "上游神经元 bodyId"},
                "post": {"type": "integer", "description": "下游神经元 bodyId"},
            },
            "required": ["pre", "post"],
        },
    },
    {
        "name": "neuron_outputs",
        "description": "列出某神经元最强的下游靶点 (Top-N)，返回 (靶神经元body, 突触数) 列表，并附靶点的类型/超类。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {"type": "integer", "description": "神经元 bodyId"},
                "top": {"type": "integer", "description": "返回前 N 个靶点，默认 20"},
            },
            "required": ["body"],
        },
    },
    {
        "name": "neuron_inputs",
        "description": "列出某神经元最强的上游输入源 (Top-N)，返回 (源神经元body, 突触数) 列表，并附源的类型/超类。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {"type": "integer", "description": "神经元 bodyId"},
                "top": {"type": "integer", "description": "返回前 N 个输入源，默认 20"},
            },
            "required": ["body"],
        },
    },
    {
        "name": "degree",
        "description": "返回某神经元的连接度：发出 (fan-out) 与接收 (fan-in) 的突触总数。",
        "inputSchema": {
            "type": "object",
            "properties": {"body": {"type": "integer", "description": "神经元 bodyId"}},
            "required": ["body"],
        },
    },
    {
        "name": "search_neurons",
        "description": "按字段 (type / superclass / instance / somaNeuromere) 模糊搜索神经元，返回匹配的 bodyId 与元数据。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索词，如 'APL' / 'mushroom' / 'olfactory'"},
                "field": {"type": "string", "description": "字段名，默认 type",
                          "enum": ["type", "superclass", "supertype", "subclass",
                                   "instance", "somaNeuromere", "statusLabel"]},
                "limit": {"type": "integer", "description": "最多返回条数，默认 20"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "superclass_projection",
        "description": "查询某个脑区/超类 (superclass) 的主要上游输入来自哪些脑区、下游投射到哪些脑区（基于预计算的跨脑区投射矩阵）。支持直观别名：olfactory→ol_intrinsic、central_complex→cb_intrinsic、visual→visual_projection、descending/ascending、ventral(vnc) 等；也支持子串模糊匹配。",
        "inputSchema": {
            "type": "object",
            "properties": {"superclass": {"type": "string",
                                        "description": "超类名或别名，如 'olfactory' / 'central_complex' / 'visual' / 'descending'"}},
            "required": ["superclass"],
        },
    },
    {
        "name": "hub_targets",
        "description": "查询命名枢纽神经元 (如 CT1、APL) 的最强下游靶点，数据来自预计算事实库。",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string",
                                    "description": "枢纽名或 bodyId，如 'CT1' / 'APL' / '58130'"}},
            "required": ["name"],
        },
    },
    {
        "name": "list_superclasses",
        "description": "列出所有可用的脑区/超类 (superclass) token，供 superclass_projection 与 search_neurons 使用。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "pathway",
        "description": "神经元 source 与 target 之间是否连通？返回跳数与一条示例通路（1 跳直连或 2 跳经中间神经元）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "integer", "description": "起点神经元 bodyId"},
                "target": {"type": "integer", "description": "终点神经元 bodyId"},
                "max_via": {"type": "integer", "description": "允许的最大中转跳数，默认 1"},
            },
            "required": ["source", "target"],
        },
    },
    {
        "name": "export_swarm_motifs",
        "description": "实时拉取蜂群科研(SwarmLabs)用的 Agent 拓扑 motif —— 派生自 MaleCNS v1.0 真实连接模式（抑制枢纽 / 储备池 / 递归反馈）。返回完整 JSON 对象（SwarmLabs 用 json.loads 解析）。设 refresh=true 可先重跑 extract_motifs.py 拿到最新派生结果。注意：本工具只返回派生的轻量描述，绝不返回 16 万神经元的原始数据，保持项目独立性。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "refresh": {"type": "boolean",
                            "description": "是否先重跑抽取脚本刷新 motif，默认 false"},
            },
        },
    },
    # ---- Phase 6 开发者工具 (2026-09-19) ----
    {
        "name": "list_blueprints",
        "description": "列出 flybrain 当前全部蓝图 (25 个) 的名称、motif 来源、stability_target、is_bio_prior 与描述。用于发现可用拓扑与审计动机溯源。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_modules",
        "description": "列出 flybrain 当前全部模块（10 个认知功能模块 + 150 个跨生物保守神经元类型，含昆虫 / 鸟类 / 鱼类 / 头足类四个非脊椎皮层进化支），返回名称、能力 profile、生物学依据与描述。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_functional_units",
        "description": "列出 72 个功能单元（最小可组合单位 = 一个功能，由一组神经元群 + 内部微回路构成，带类型化输入/输出端口；其中 16 个为 v1.4.1 跨进化支：昆虫 / 鸟类 / 鱼类 / 头足类，另 16 个为 v1.6.0 节律/状态/误差与主动感知批次：环节动物 / 海鞘 / 软体动物 / 颊窝蛇 / 蛙 / 小脑 / 脑干 / 海马 / 桶状皮层；其中 6 个单元成员已锚定到真实 MaleCNS 细胞类型，14 个神经元群对应 8,798 个真实细胞，见 embodiment 字段）。可按 system（如 cortex / hippocampus）或 capability（如 action_select）过滤。这是组合虚拟生物时真正当节点用的那一层，不是单神经元类型。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "system": {"type": "string",
                           "description": "解剖系统过滤，如 sensory / thalamus / cortex / cerebellum / hippocampus / basal_ganglia / limbic / spinal_cord / neuromodulatory"},
                "capability": {"type": "string",
                               "description": "能力子串过滤，如 gate / select / relay / rhythm"},
            },
        },
    },
    {
        "name": "get_functional_unit",
        "description": "返回单个功能单元的完整定义：成员神经元群（role + neuron + 组成比例）、内部微回路（含连接件类型）、类型化输入/输出端口、能力、任务提示、生物学文献依据与组合约束。",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string",
                                    "description": "单元名，如 thalamocortical_relay_unit"}},
            "required": ["name"],
        },
    },
    {
        "name": "list_evidence_ledger",
        "description": "把整个功能单元库的声明边汇总成「证据账本」，按 support_tier 分组：SUPPORTED(≥2 类型对支持) / FRAGILE(恰 1 类型对) / CONTRADICTED(0 突触，已登记的矛盾)。这是回答「全库哪些边脆弱」的一等公民查询面——不用手动遍历 97 个单元。可选 only 参数只返回某一档。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "only": {"type": "string",
                         "description": "仅返回该档，如 FRAGILE",
                         "enum": ["SUPPORTED", "FRAGILE", "CONTRADICTED"]},
            },
        },
    },
    {
        "name": "list_connection_types",
        "description": "列出 66 种连接件（最小可组合连接单位 = 一种连接形式，带端口类型约束、符号、扇出、时延与可塑性标记）。分 6 族：micro（点对点突触位点）/ circuit（多神经元回路）/ modulatory（弥散·容积·逆行）/ electrical（电突触·电场·胶质）/ plasticity（可塑性规则）/ macro（群体投射几何）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "family": {"type": "string",
                           "description": "仅返回该族，如 circuit / macro"},
            },
        },
    },
    {
        "name": "compose_from_units",
        "description": "用「功能单元 + 连接件」组装一个虚拟生物，并做机械校验：端口类型兼容性、必需端口满足、是否可被外部驱动/读出、回路闭环报告。返回 nodes/edges/interface/validation/provenance（sha256 可复现）。边界上未绑定的必需输入端口即生物体的外部输入，不算错误。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "units": {
                    "type": "array",
                    "description": "节点列表，元素为单元名或 {\"unit\":name,\"instances\":n}",
                    "items": {},
                },
                "connections": {
                    "type": "array",
                    "description": "边列表，元素为 \"unitA.out_port->unitB.in_port:connection_type\" 字符串或 {\"from\",\"to\",\"type\"} 对象",
                    "items": {},
                },
                "name": {"type": "string", "description": "生物体名，默认 composed_organism"},
                "seed": {"type": "integer", "description": "确定性种子，默认 42"},
                "strict_cycles": {"type": "boolean",
                                  "description": "true 时任何回路都报错（默认 false：回路作为警告报告，因为反馈回路是本库的一等公民）"},
                "allow_boundary_inputs": {"type": "boolean",
                                          "description": "默认 true（生物体边界允许外部输入）；校验内部子链时设 false，悬空必需输入即为错误"},
            },
            "required": ["units", "connections"],
        },
    },
    {
        "name": "list_bio_motifs",
        "description": "列出从 MaleCNS v1.0 抽取的 3 个真实生物学 motif（inhibitory_hub / reservoir_smallworld / recurrent_feedback）及其神经元锚点、突触统计、可运行查询。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "batch_generate_topologies",
        "description": "批量生成多个 SwarmLabs 兼容拓扑（一次性多个蓝图/模块组合），返回 JSON 列表。适合做对照实验或批量部署。max 10。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec_list": {
                    "type": "array",
                    "maxItems": 10,
                    "items": {
                        "type": "object",
                        "properties": {
                            "blueprint": {"type": "string",
                                          "description": "蓝图名，如 predictive_coding_v2"},
                            "n_modules": {"type": "integer", "default": 6,
                                          "description": "模块数（与 modules 二选一）"},
                            "modules": {
                                "type": "array", "items": {"type": "string"},
                                "description": "模块 profile 列表；给定则用其长度作为 n_modules",
                            },
                            "agents_per_module": {"type": "integer", "default": 6},
                        },
                    },
                    "description": "多个拓扑的生成规格，最多 10 个",
                },
                "seed": {"type": "integer", "default": 42,
                         "description": "随机种子基线，每个 spec 用 seed+i"},
                "max_nodes": {"type": "integer", "default": 32,
                              "description": "节点数上限；超出会在结果里标 exceeds_max_nodes=true"},
            },
            "required": ["spec_list"],
        },
    },
    {
        "name": "get_provenance_bundle",
        "description": "为指定蓝图导出 W3C PROV-JSON provenance bundle（含 motif_synapse_stats / motif_query / dataset_anchor）。可用于 EU AI Act 合规、yProv4ML 摄入、MIT Sloan 分析。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "blueprint": {"type": "string", "description": "蓝图名，如 'predictive_coding'"},
            },
            "required": ["blueprint"],
        },
    },
    {
        "name": "list_stacked_blueprints",
        "description": "列出 5 个「某方面特别强」的堆叠方案（stack_visual_cognition / stack_reinforcement_decision / stack_active_inference / stack_habit_automation / stack_meta_cognition）。每个方案由 3 个基础 blueprint 组合而成，追溯到 1-2 个真实 MaleCNS motif。含可行性判断：nodes/edges/fanout 爆炸/权重冲突/stability_target/metrics。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_stacked_feasibility",
        "description": "获取某个堆叠方案的详细可行性报告：组合标签、追溯 motif 链、organism 边数、规则冲突详情（哪些 blueprint 对同一 (from_profile, to_profile, kind, semantic) 组合产生规则）、stability_target 是否落在合理范围、metrics 快照、生成耗时。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "堆叠方案名，如 'stack_visual_cognition'"},
            },
            "required": ["name"],
        },
    },    {
        "name": "list_neuropils",
        "description": "列出 MaleCNS v1.0 的 146 个 primary neuropil（脑区）及其突触数量、涉及 pre/post 神经元数、mean_synapses_per_pre。空间维度的顶层聚合（不加载 6.78 GB 大文件）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "top": {"type": "integer", "default": 30,
                        "description": "按突触数排序后返回前 N 个"},
            },
        },
    },
    {
        "name": "get_neuropil_detail",
        "description": "获取单个 neuropil 的详细突触统计（含 pre/post 神经元数、突触均值、脑区左右对比信息）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "neuropil 名，如 'ME(L)' / 'LO(R)' / 'GNG' / 'AVLP(L)'"},
            },
            "required": ["name"],
        },
    },
    # ---- Phase 7 模块化工厂工具 (2026-09-20) ----
    {
        "name": "get_module",
        "description": "获取单个模块的完整规格定义，包括连接模式、拓扑参数、capabilities 等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "模块名，如 'sensory' / 'memory' / 'attention'"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "check_module_compatibility",
        "description": "检查多个模块组合的兼容性。检测循环依赖、motif 资源竞争、总节点数范围。返回 compatible=true/false + 冲突详情。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "modules": {"type": "array",
                            "items": {"type": "string"},
                            "description": "模块名列表，如 ['sensory', 'memory', 'motor']"},
            },
            "required": ["modules"],
        },
    },
    {
        "name": "compose_virtual_organism",
        "description": "根据模块规格组合生成虚拟生物拓扑。支持同模块多副本（counts 参数）。产出 organism 结构含 modules 列表、stats 统计、兼容性报告。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "modules": {"type": "array",
                            "items": {"type": "string"},
                            "description": "模块名列表"},
                "counts": {"type": "object",
                           "additionalProperties": {"type": "integer"},
                           "description": "每个模块的副本数，如 {'sensory': 2}"},
                "seed": {"type": "integer",
                         "description": "随机种子，控制节点数分布，默认 42"},
            },
            "required": ["modules"],
        },
    },
    {
        "name": "list_virtual_organisms",
        "description": "列出已生成的虚拟生物标本（保存在 male_cns/virtual_organisms/）。每个标本对应一次 compose_virtual_organism 调用。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # ---- Phase 2 预设组合工具 (2026-09-20) ----
    {
        "name": "list_presets",
        "description": "列出所有虚拟生物预设组合（10 个），包括 minimal_reflex / cognitive_animal / multi_sensory_perceptor / deep_thinker / reward_learner / planning_agent / fast_reflexor / swarm_controller / self_adaptive_organism / conscious_being。每个预设定义了一组模块、副本数、跨模块连接蓝图。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_preset",
        "description": "获取单个预设组合的完整定义，包括模块列表、副本数、跨模块连接蓝图、每模块节点数、seed。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "预设名，如 'cognitive_animal' / 'deep_thinker' / 'conscious_being'"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "apply_preset",
        "description": "应用预设组合并生成虚拟生物拓扑（真调用 design_organism 生成 nodes/edges/weights）。支持通过 overrides 覆盖任意参数（modules/counts/variants/blueprint/agents_per_module/seed）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "预设名"},
                "overrides": {"type": "object",
                              "additionalProperties": True,
                              "description": "覆盖参数，如 {\"seed\": 100, \"agents_per_module\": 8}"},
            },
            "required": ["name"],
        },
    },
    # ---- Phase 5: SwarmLabs 集成工具 ----
    {
        "name": "organism_to_swarmlabs",
        "description": "把虚拟生物拓扑转换为 SwarmLabs 多 Agent 团队 spec（含 agents/modules/edges/guardrails/validation/motif_provenance/prov_json）。让每个模块的 profile / task_hint / capability 直接映射到 SwarmLabs agent 角色。返回 module_role_summary 便于查看每个模块的 Agent 角色分配。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "SwarmLabs 团队名称（可选，默认从预设名推导）"},
                "organism_result": {"type": "object",
                                    "description": "compose_virtual_organism 或 apply_preset 的完整返回结果（含 organism/stats 字段）"},
            },
            "required": ["organism_result"],
        },
    },
    {
        "name": "get_module_agent_roles",
        "description": "列出所有模块到 SwarmLabs Agent 角色的映射表（每个模块的 swarm_role / lead_task_hint / task_hints / capability / category / motif_source）。让 SwarmLabs 用户一眼看到选了哪些模块会得到哪些 Agent 角色。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # ---- Phase 6: 虚拟生物市场工具 ----
    {
        "name": "save_market_organism",
        "description": "保存自定义模块组合到市场（JSON 持久化 + 自动 compose 拿 stats）。同名会覆盖。市场目录：male_cns/virtual_organisms/market/。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "组合名称（唯一）"},
                "module_spec": {"type": "object",
                                "description": "模块规格（modules/counts/variants/blueprint/agents_per_module/seed）"},
                "description": {"type": "string", "description": "组合说明"},
                "tags": {"type": "array", "items": {"type": "string"},
                         "description": "标签列表，便于检索"},
                "author": {"type": "string", "description": "作者"},
            },
            "required": ["name", "module_spec"],
        },
    },
    {
        "name": "load_market_organism",
        "description": "从市场加载指定组合（返回 module_spec + 已 compose 的完整拓扑 JSON）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "组合名称"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_market_organisms",
        "description": "列出市场所有组合，支持按 tag 过滤、按 rating/name/nodes/created 排序。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {"type": "string", "description": "按标签过滤（可选）"},
                "sort_by": {"type": "string",
                            "enum": ["name", "rating", "nodes", "created"],
                            "description": "排序字段，默认 name"},
                "limit": {"type": "integer", "description": "返回数量上限，默认 50"},
            },
        },
    },
    {
        "name": "rate_market_organism",
        "description": "给市场组合评分（1.0-5.0 分）。重复评分会追加到 comments 并重新计算平均分。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "组合名称"},
                "score": {"type": "number", "description": "评分 1.0-5.0"},
                "comment": {"type": "string", "description": "评语"},
                "rater": {"type": "string", "description": "评分者"},
            },
            "required": ["name", "score"],
        },
    },
    {
        "name": "search_market_organisms",
        "description": "按关键词搜索市场组合（匹配 name/description/tags/modules/blueprint）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回数量上限，默认 20"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "delete_market_organism",
        "description": "从市场删除组合（含 JSON 文件）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "组合名称"},
            },
            "required": ["name"],
        },
    },
    # ---- Phase 8: 组合规则 middleware (2026-09-21) ----
    {
        "name": "list_combination_rules",
        "description": "列出所有组合规则 (CombinationRule)、嵌套规则 (NestingRule) 与乘数语义 (MultiplierSemantic)。规则源自 discovered_modules.json 与 cross_superclass_top 真实数据。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "validate_combination",
        "description": "验证一组模块组合的合法性。输入 [{from_category, to_category, from_superclass?, to_superclass?}]，返回 compatible/warnings/conflicts/matched_rules。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "combos": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "模块组合列表，每项含 from_category, to_category 及可选的 from_superclass/to_superclass",
                },
            },
            "required": ["combos"],
        },
    },
    {
        "name": "expand_organism",
        "description": "按倍乘语义 (combinatorial/structural/performance) 展开模块副本数。返回 expanded_modules / total_copies / estimated_nodes。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "properties": {
                        "modules": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "每个模块的 category/copies/superclass",
                        },
                    },
                },
            },
            "required": ["spec"],
        },
    },
    {
        "name": "get_multiplier_metrics",
        "description": "返回三义乘数的当前实测值：combinatorial (C(19,4)=4032)、structural (故障隔离 25/27)、performance (⚠️ 未经证实)。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def _fmt_targets(pairs):
    out = []
    ann = core._STATE["ann"]
    for bid, syns in pairs:
        rec = ann.get(bid, {})
        typ = rec.get("type") or rec.get("superclass") or "未注释"
        sc = rec.get("superclass") or ""
        out.append("  - %s (body %d) | %d 突触%s" % (
            typ, bid, syns, (" | " + sc) if sc else ""))
    return "\n".join(out) if out else "  (无)"


def _format(name, result):
    if name == "connectome_overview":
        o = result
        hubs = "\n".join("  - %s (body %d): %d 突触" % (
            h["hub_type"], h["hub_body"], h["total_synapses"]) for h in o["top_hubs"])
        return (
            "数据集: %s (%s)\n"
            "注释神经元数: %d\n总突触数: %d\n"
            "平均每个神经元发出: %.1f 突触 / 接收: %.1f 突触\n"
            "Top 枢纽:\n%s" % (
                o["dataset"], o["license"], o["annotated_neurons"],
                o["total_synapses"], o["mean_fanout"], o["mean_fanin"], hubs)
        )
    if name == "neuron_info":
        if not result:
            return "未找到该 bodyId 的注释信息。"
        lines = ["神经元 body %d:" % result["bodyId"]]
        for k in ["type", "superclass", "supertype", "subclass", "statusLabel",
                  "somaSide", "somaNeuromere", "neurotransmitter", "instance", "vfbId"]:
            v = result.get(k)
            if v:
                lines.append("  %s: %s" % (k, v))
        lines.append("  连接度: 发出 %d 突触 / 接收 %d 突触" % (
            result["fan_out"], result["fan_in"]))
        return "\n".join(lines)
    if name == "pair_synapses":
        return "突触数: %d" % result
    if name == "neuron_outputs":
        return "下游靶点 (Top):\n" + _fmt_targets(result)
    if name == "neuron_inputs":
        return "上游输入源 (Top):\n" + _fmt_targets(result)
    if name == "degree":
        return "连接度: 发出(fan-out) %d 突触 / 接收(fan-in) %d 突触" % result
    if name == "search_neurons":
        if not result:
            return "未匹配到神经元。"
        lines = ["匹配 %d 条 (展示前 %d):" % (len(result), len(result))]
        for bid, rec in result:
            lines.append("  - body %d | %s | %s" % (
                bid, rec.get("type") or "?", rec.get("superclass") or ""))
        return "\n".join(lines)
    if name == "superclass_projection":
        if result["candidates"] is not None:
            return "未匹配到脑区。可用 superclass token:\n  " + "\n  ".join(result["candidates"])
        if not result["io"] and not result["top_downstream"] and not result["top_upstream"]:
            return "未找到该 superclass 的投射数据。"
        lines = ["超类 %s:" % result["superclass"]]
        io = result["io"]
        if io:
            lines.append("  含 %d 神经元；累计发出 %d 突触、接收 %d 突触" % (
                io["n_neurons"], io["out_synapses"], io["in_synapses"]))
        if result["top_downstream"]:
            lines.append("  主要下游脑区:")
            for c in result["top_downstream"]:
                lines.append("    -> %s : %d 突触 (占 %.2f%%)" % (
                    c["to"], c["synapses"], c["pct_of_total"]))
        if result["top_upstream"]:
            lines.append("  主要上游脑区:")
            for c in result["top_upstream"]:
                lines.append("    <- %s : %d 突触 (占 %.2f%%)" % (
                    c["from"], c["synapses"], c["pct_of_total"]))
        return "\n".join(lines)
    if name == "hub_targets":
        if not result:
            return "未找到该枢纽神经元。"
        lines = ["枢纽 %s (body %d, %s):" % (
            result["hub_type"], result["hub_body"], result["hub_superclass"])]
        lines.append("  总突触约 %d (发出 %d / 接收 %d)" % (
            result["hub_total_synapses"], result["hub_fanout"], result["hub_fanin"]))
        lines.append("  最强下游靶点:")
        for tg in result["top_targets"][:8]:
            lines.append("    -> %s (body %d, %s): %d 突触" % (
                tg["target_type"], tg["target_body"],
                tg["target_superclass"], tg["synapses"]))
        return "\n".join(lines)
    if name == "pathway":
        if result["connected"]:
            if result["hops"] == 1:
                return "连通：body %d --[%d 突触]--> body %d (直连)" % (
                    result["route"][0], result["synapses"], result["route"][1])
            return "连通：body %d 经中间神经元 %s 到达 body %d (2 跳)" % (
                result["route"][0], result["via"][:3], result["route"][-1])
        return "在 1~2 跳范围内未找到连接通路。"
    return json.dumps(result, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Phase 6 developer helpers (2026-09-19)
# --------------------------------------------------------------------------- #
def _load_topology_module():
    """Load synthetic_bio_topology.py (path may vary by layout).

    NOTE: this used to reference an undefined ``HERE``, which made every
    generator-surface tool raise NameError. The module-level constant is
    ``_MOTIFS_DIR`` (== the directory holding this file).
    """
    import os as _os
    here = _os.path.dirname(_os.path.abspath(__file__))
    candidates = [
        _os.path.normpath(_os.path.join(here, "..", "synthetic_bio_topology.py")),
        _os.path.normpath(_os.path.join(here, "..", "..", "synthetic_bio_topology.py")),
    ]
    for p in candidates:
        if _os.path.exists(p):
            import importlib.util
            spec = importlib.util.spec_from_file_location("sbt", p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m
    raise RuntimeError("synthetic_bio_topology.py not found in %s" % candidates)


def _motif_name(entry) -> str:
    """Normalize a BLUEPRINT_SOURCE_MOTIF value to a plain motif name.

    Values are dicts of the shape {"motif": ..., "note": ..., "stability_target": ...}
    (older/other entries may be bare strings). Treating them as hashable strings
    silently made every blueprint look bio-prior, so normalize in one place.
    """
    if isinstance(entry, dict):
        return str(entry.get("motif") or "none")
    return str(entry or "none")


def _motif_note(entry) -> str:
    return entry.get("note", "") if isinstance(entry, dict) else ""


def _motif_stability(entry):
    return entry.get("stability_target") if isinstance(entry, dict) else None


def _list_blueprints():
    mod = _load_topology_module()
    motif_map = getattr(mod, "BLUEPRINT_SOURCE_MOTIF", {})
    out = []
    for name, entry in mod.BLUEPRINTS.items():
        raw = motif_map.get(name, "none")
        motif = _motif_name(raw)
        out.append({
            "name": name,
            "category": entry.get("category", ""),
            "description": entry.get("description", ""),
            "use_cases": entry.get("use_cases", []),
            "source_motif": motif,
            "source_motif_note": _motif_note(raw),
            "stability_target": _motif_stability(raw),
            "is_bio_prior": motif != "none",
        })
    return {"blueprint_count": len(out), "blueprints": out}


def _list_modules():
    mod = _load_topology_module()
    profiles = getattr(mod, "MODULE_PROFILES", {})
    out = []
    for name, entry in profiles.items():
        out.append({
            "name": name,
            "description": entry.get("description", ""),
            "capability": entry.get("capability", []),
            "task_hint_pool": entry.get("task_hint_pool", []),
            "lead_task_hint": entry.get("lead_task_hint", ""),
            "reservoir_density": entry.get("reservoir_density"),
            "recurrent_pct": entry.get("recurrent_pct"),
            "has_inhibition": entry.get("has_inhibition"),
        })
    return {"module_count": len(out), "modules": out}


def _list_bio_motifs():
    mod = _load_topology_module()
    motif_map = getattr(mod, "BLUEPRINT_SOURCE_MOTIF", {})
    # Deduplicate by normalized motif name (skip "none" == no bio-prior)
    motif_names = sorted({_motif_name(v) for v in motif_map.values()} - {"none"})
    out = []
    for mname in motif_names:
        rep_bp = next((b for b, m in motif_map.items()
                       if _motif_name(m) == mname), None)
        entry = {"motif": mname, "representative_blueprint": rep_bp,
                 "note": _motif_note(motif_map.get(rep_bp)),
                 "stability_target": _motif_stability(motif_map.get(rep_bp))}
        if rep_bp:
            try:
                entry["stats"] = mod._motif_synapse_stats(mname) if hasattr(mod, "_motif_synapse_stats") else None
                entry["query"] = mod._motif_query(mname) if hasattr(mod, "_motif_query") else None
            except Exception as e:  # noqa: BLE001
                entry["query_error"] = str(e)[:150]
        out.append(entry)
    return {"motif_count": len(out), "motifs": out,
            "dataset": "MaleCNS v1.0 / 124,177,617 synapses / 166,700 neurons / CC-BY"}


def _batch_generate(args, seed=42, max_nodes=32):
    """Batch-generate topologies from a spec_list.

    Accepts the documented shape ``{"spec_list": [{"blueprint": ..., "n_modules":
    ...}, ...]}`` (max 10). A single spec dict is also accepted for convenience.
    """
    if isinstance(args, dict) and "spec_list" in args:
        spec_list = args.get("spec_list") or []
        seed = int(args.get("seed", seed) or seed)
        max_nodes = int(args.get("max_nodes", max_nodes) or max_nodes)
    elif isinstance(args, list):
        spec_list = args
    elif isinstance(args, dict) and args:
        spec_list = [args]          # single spec passed directly
        seed = int(spec_list[0].get("seed", seed) or seed)
    else:
        spec_list = []

    mod = _load_topology_module()
    results = []
    for i, spec in enumerate(list(spec_list)[:10]):
        spec = spec if isinstance(spec, dict) else {}
        bp = spec.get("blueprint", "sequential")
        n_mod = spec.get("n_modules")
        if n_mod is None:
            mods = spec.get("modules")
            n_mod = len(mods) if isinstance(mods, list) else 6
        n_mod = int(n_mod)
        agents_per = int(spec.get("agents_per_module", 6))
        try:
            design_spec = {
                "blueprint": bp,
                "n_modules": n_mod,
                "agents_per_module": agents_per,
            }
            org = mod.design_organism(design_spec, seed=seed + i)
            cfg = mod.build_swarmlabs_config(
                org, name="batch_%d_%s" % (i, bp),
                provenance=org.get("motif_provenance"))
            swarm = cfg.get("swarm", {})
            val = swarm.get("validation", {})
            agents = swarm.get("agents", [])
            metrics = org.get("metrics", {})
            # Same None-vs-missing trap as in _get_prov_bundle: `prov_json` is
            # an explicit None when the optional dataprov package is absent.
            prov = cfg.get("prov_json")
            bundle = prov if isinstance(prov, dict) else {}
            results.append({
                "index": i,
                "blueprint": bp,
                "n_modules": n_mod,
                "agents": len(agents) if isinstance(agents, list) else agents,
                "n_edges": val.get("n_edges"),
                "ok": val.get("ok"),
                "schema_version": cfg.get("schema_version"),
                "prov_available": bool(bundle),
                "prov_bundle_keys": sorted(bundle.keys())[:5],
                "exceeds_max_nodes": bool(metrics.get("n_nodes", 0) > max_nodes),
            })
        except Exception as e:  # noqa: BLE001
            results.append({"index": i, "blueprint": bp, "error": str(e)[:200]})
    # Report successes and failures separately. A bare `generated` count of
    # attempts is a lie by omission: a batch where every spec raised still
    # returned generated=1 with isError=false, and a caller checking only that
    # field would treat a total failure as a success.
    succeeded = sum(1 for r in results if "error" not in r)
    return {"total": len(spec_list),
            "attempted": len(results),
            "succeeded": succeeded,
            "failed": len(results) - succeeded,
            "max_nodes": max_nodes,
            "results": results}


def _get_prov_bundle(blueprint):
    mod = _load_topology_module()
    try:
        org = mod.design_organism({"blueprint": blueprint, "n_modules": 6,
                                   "agents_per_module": 6}, seed=42)
    except Exception as e:  # noqa: BLE001
        return {"error": "design failed: %s" % str(e)[:200]}
    cfg = mod.build_swarmlabs_config(org, name=blueprint,
                                     provenance=org.get("motif_provenance"))
    # `prov_json` is None -- not absent -- when the optional `dataprov` package
    # is not importable, because `_prov_json()` degrades gracefully by design.
    # `cfg.get("prov_json", {})` does NOT cover that case: a default only
    # applies to a missing key, not to a key whose value is None. Reading it
    # as a dict unconditionally crashed this tool on any interpreter without
    # dataprov (found by CI, which installs no optional extras).
    prov = cfg.get("prov_json")
    bundle = prov if isinstance(prov, dict) else {}
    out = {
        "blueprint": blueprint,
        "schema_version": cfg.get("schema_version"),
        "prov_available": bool(bundle),
        "prov_bundle_keys": sorted(bundle.keys()),
        "prov_json": prov if bundle else None,
        # Structural provenance must survive even without the W3C serializer.
        "motif_provenance": (cfg.get("motif_provenance")
                             or org.get("motif_provenance")),
    }
    if not bundle:
        out["prov_unavailable"] = (
            "W3C PROV-JSON bundle not produced: the optional 'dataprov' package "
            "is not importable in this interpreter. Structural provenance is "
            "still present under 'motif_provenance'. Enable the standardized "
            "bundle with: pip install dataprov  (or pip install \"flybrain-connectome[prov]\")"
        )
    return out


def _load_stacked_report():
    """Load male_cns/stacked_blueprints.json lazily."""
    if not os.path.exists(_STACKED_REPORT):
        raise FileNotFoundError(
            "stacked_blueprints.json not found at %s (run "
            "drosophila_connectome/scripts/stacked_blueprints.py first)"
            % _STACKED_REPORT)
    with open(_STACKED_REPORT, encoding="utf-8") as f:
        return json.load(f)


def _list_stacked_blueprints():
    """Return a compact view of all stacked schemes + feasibility summary."""
    report = _load_stacked_report()
    items = []
    for s in report.get("stacks", []):
        f = s.get("feasibility", {}) or {}
        items.append({
            "name": s.get("name"),
            "label": s.get("label"),
            "combination": s.get("combination"),
            "strength": s.get("strength"),
            "use_cases": s.get("use_cases"),
            "expected_motifs": s.get("expected_motifs"),
            "feasible": f.get("feasible"),
            "n_motifs_traced": f.get("n_distinct_motifs"),
            "stability_target": f.get("stability_target"),
            "stability_in_range": f.get("stability_in_range"),
            "n_blueprint_edges": (f.get("organism_stats") or {}).get("n_blueprint_edges"),
            "rule_conflicts": (f.get("organism_stats") or {}).get("rule_conflicts"),
        })
    return {
        "schema_version": report.get("schema_version"),
        "generated_at": report.get("generated_at"),
        "n_stacks": report.get("n_stacks"),
        "motif_library": report.get("motif_library"),
        "summary": report.get("summary"),
        "stacks": items,
    }


def _get_stacked_feasibility(name):
    """Return the full feasibility record for a single stacked scheme."""
    report = _load_stacked_report()
    for s in report.get("stacks", []):
        if s.get("name") == name:
            return {
                "name": s.get("name"),
                "label": s.get("label"),
                "combination": s.get("combination"),
                "strength": s.get("strength"),
                "rational": s.get("rational"),
                "use_cases": s.get("use_cases"),
                "expected_motifs": s.get("expected_motifs"),
                "feasibility": s.get("feasibility"),
            }
    available = [s.get("name") for s in report.get("stacks", [])]
    raise ValueError("unknown stacked blueprint '%s'. Available: %s"
                     % (name, ", ".join(available)))


def _load_neuropil_stats():
    """Load male_cns/neuropil_stats.json lazily."""
    if not os.path.exists(_NEUROFIL_STATS):
        raise FileNotFoundError(
            "neuropil_stats.json not found at %s (run "
            "drosophila_connectome/scripts/analyze_neuropil.py first)"
            % _NEUROFIL_STATS)
    with open(_NEUROFIL_STATS, encoding="utf-8") as f:
        return json.load(f)


def _list_neuropils(top=30):
    """Return the top-N neuropils by synapse count."""
    d = _load_neuropil_stats()
    items = sorted(d.get("neuropils", {}).items(),
                   key=lambda x: -x[1]["synapses"])[:top]
    return {
        "schema_version": d.get("generated_at"),
        "source_file": d.get("source_file_syn_partners"),
        "source_file_tbar_nt": d.get("source_file_tbar_nt"),
        "total_synapse_pairs": d.get("total_synapse_pairs"),
        "total_tbar_synapses": d.get("total_tbar_synapses"),
        "n_neuropil_categories": d.get("n_neuropil_categories"),
        "top": top,
        "neuropils": [
            {"name": name, **vals} for name, vals in items
        ],
    }


def _get_neuropil_detail(name):
    """Return full stats for a single neuropil."""
    d = _load_neuropil_stats()
    neu = d.get("neuropils", {})
    if name not in neu:
        # Fuzzy: list candidates
        cands = [k for k in neu.keys() if name.lower() in k.lower()][:20]
        raise ValueError(
            "unknown neuropil '%s'. Similar: %s"
            % (name, ", ".join(cands) if cands else "(none)"))
    v = neu[name]
    total = d.get("total_synapse_pairs", 0)
    return {
        "name": name,
        "synapses": v["synapses"],
        "pct_of_total": round(v["synapses"] * 100 / total, 3) if total else None,
        "distinct_pre_neurons": v["distinct_pre_neurons"],
        "distinct_post_neurons": v["distinct_post_neurons"],
        "mean_synapses_per_pre": v["mean_synapses_per_pre"],
        "tbar_synapses": v.get("tbar_synapses"),
        "distinct_bodies_tbar": v.get("distinct_bodies_tbar"),
        "neurotransmitters": v.get("neurotransmitters"),
        "source_file": d.get("source_file_syn_partners"),
        "source_file_tbar_nt": d.get("source_file_tbar_nt"),
    }


# --------------------------------------------------------------------------- #
# Phase 7: Module Factory tools
# --------------------------------------------------------------------------- #
_MODULE_DIR = os.path.normpath(os.path.join(_MOTIFS_DIR, "..", "..", "male_cns", "virtual_organisms"))


def _list_modules(category=None):
    modules = ModuleFactory.list_modules(category=category)
    return {"module_count": len(modules), "modules": modules}


def _get_module(name):
    return ModuleFactory.get_module(name)


def _check_compatibility(modules):
    return ModuleFactory.check_compatibility(modules)


def _compose_organism(args):
    spec = {
        "modules": args.get("modules", []),
        "counts": args.get("counts", {}),
        "seed": int(args.get("seed", 42)),
    }
    result = ModuleFactory.compose_organism(spec)
    # Save artifact
    if result.get("status") == "success":
        os.makedirs(_MODULE_DIR, exist_ok=True)
        org_name = args.get("name", "organism_%d" % int(time.time()))
        path = os.path.join(_MODULE_DIR, f"{org_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["saved_path"] = path
    return result


def _list_presets():
    presets = ModuleFactory.list_presets()
    return {"preset_count": len(presets), "presets": presets}


def _get_preset(name):
    return ModuleFactory.get_preset(name)


def _apply_preset(args):
    """Apply a preset combination and generate virtual organism topology.

    Preset args:
      name: preset name (required)
      overrides: optional dict to override any preset field (modules/counts/variants/blueprint/agents_per_module/seed)
    """
    result = ModuleFactory.apply_preset(str(args["name"]), args.get("overrides"))
    # Save artifact
    if result.get("status") == "success":
        os.makedirs(_MODULE_DIR, exist_ok=True)
        preset_name = args.get("name", "preset_%d" % int(time.time()))
        path = os.path.join(_MODULE_DIR, f"preset_{preset_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["saved_path"] = path
    return result


# --------------------------------------------------------------------------- #
# Functional-unit composition library (Tier-1, stdlib only)
#
# Two libraries live in ../functional_units/*.json: 40 FUNCTIONAL UNITS (a
# function delivered by a group of neuron populations, with typed ports) and 50
# CONNECTION TYPES (a connection form, constrained on port types). A virtual
# organism is composed as units (nodes) + connection types (typed edges) -- the
# layer above the neuron-type registry, which is what actually composes.
# --------------------------------------------------------------------------- #
def _fu_module():
    """Lazy import so a deployment missing the JSON artifacts still serves the
    other tools instead of dying at import time."""
    import importlib
    return importlib.import_module("functional_units")


def _list_functional_units(args):
    try:
        fu = _fu_module()
    except Exception as exc:
        return {"status": "unit_library_unavailable", "error": str(exc),
                "hint": "functional_units.py + functional_units/*.json are Tier-1; "
                        "reinstall or regenerate with scripts/gen_functional_units.py"}
    units = fu.list_units(system=args.get("system"), capability=args.get("capability"))
    return {"unit_count": len(units), "stats": fu.stats(), "units": units}


def _get_functional_unit(args):
    try:
        fu = _fu_module()
    except Exception as exc:
        return {"status": "unit_library_unavailable", "error": str(exc)}
    u = fu.get_unit(str(args["name"]))
    if u is None:
        return {"status": "error", "error": "no such functional unit",
                "name": args["name"],
                "known": [x["name"] for x in fu.list_units()]}
    return u


def _list_evidence_ledger(args):
    try:
        fu = _fu_module()
    except Exception as exc:
        return {"status": "unit_library_unavailable", "error": str(exc)}
    return fu.list_evidence_ledger(only=args.get("only"))


def _list_connection_types(args):
    try:
        fu = _fu_module()
    except Exception as exc:
        return {"status": "unit_library_unavailable", "error": str(exc)}
    doc = fu.load_connection_types()
    fam = args.get("family")
    items = [c for c in doc["connection_types"] if not fam or c["family"] == fam]
    return {"connection_type_count": len(items), "families": doc["families"],
            "connection_types": items}


def _compose_from_units(args):
    try:
        fu = _fu_module()
    except Exception as exc:
        return {"status": "unit_library_unavailable", "error": str(exc)}
    return fu.compose_from_units(
        args.get("units") or [],
        args.get("connections") or [],
        name=args.get("name", "composed_organism"),
        seed=int(args.get("seed", 42)),
        strict_cycles=bool(args.get("strict_cycles", False)),
        allow_boundary_inputs=bool(args.get("allow_boundary_inputs", True)),
    )


def _list_virtual_organisms():
    if not os.path.exists(_MODULE_DIR):
        return {"organisms": [], "count": 0}
    files = [f for f in os.listdir(_MODULE_DIR) if f.endswith(".json")]
    items = []
    for f in files:
        path = os.path.join(_MODULE_DIR, f)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        items.append({
            "filename": f,
            "path": path,
            "status": data.get("status"),
            "stats": data.get("organism", {}).get("stats", {}),
            "generated_at": os.path.getmtime(path),
        })
    return {"organism_count": len(items), "organisms": items}


# ---- Phase 5: SwarmLabs 集成 ----
def _organism_to_swarmlabs(args):
    organism_result = args.get("organism_result")
    if not organism_result or not isinstance(organism_result, dict):
        return {"status": "error", "error": "organism_result is required (must be dict from compose_virtual_organism or apply_preset)"}
    name = args.get("name")
    return ModuleFactory.to_swarmlabs(organism_result, name=name)


def _get_module_agent_roles():
    roles = ModuleFactory.get_module_agent_roles()
    return {"role_count": len(roles), "roles": roles}


# ---- Phase 6: 虚拟生物市场 ----
def _save_market_organism(args):
    name = args.get("name")
    module_spec = args.get("module_spec")
    if not name or not module_spec:
        return {"status": "error", "error": "name and module_spec are required"}
    return ModuleFactory.save_market_organism(
        name=name,
        module_spec=module_spec,
        description=args.get("description", ""),
        tags=args.get("tags"),
        author=args.get("author", "anonymous"),
    )


def _load_market_organism(args):
    return ModuleFactory.load_market_organism(str(args["name"]))


def _list_market_organisms(args):
    return ModuleFactory.list_market_organisms(
        tag=args.get("tag"),
        sort_by=args.get("sort_by", "name"),
        limit=int(args.get("limit", 50)),
    )


def _rate_market_organism(args):
    return ModuleFactory.rate_market_organism(
        name=str(args["name"]),
        score=float(args["score"]),
        comment=args.get("comment", ""),
        rater=args.get("rater", "anonymous"),
    )


def _search_market_organisms(args):
    return ModuleFactory.search_market_organisms(
        query=str(args["query"]),
        limit=int(args.get("limit", 20)),
    )


def _delete_market_organism(args):
    return ModuleFactory.delete_market_organism(str(args["name"]))


# --------------------------------------------------------------------------- #
# Phase 8: 组合规则 middleware (module_combinator)
# --------------------------------------------------------------------------- #
def _load_combinator():
    import importlib
    return importlib.import_module("module_combinator")


def _list_combination_rules():
    return _load_combinator().list_rules()


def _validate_combination(args):
    return _load_combinator().validate_combination(args.get("combos", []))


def _expand_organism(args):
    return _load_combinator().expand_organism(args.get("spec", {}))


def _get_multiplier_metrics(args):
    return _load_combinator().get_multiplier_metrics()


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def handle_call(name, args):
    args = args or {}
    if name == "connectome_overview":
        return _format(name, core.connectome_overview())
    if name == "neuron_info":
        return _format(name, core.neuron_info(int(args["body"])))
    if name == "pair_synapses":
        return _format(name, core.pair_synapses(int(args["pre"]), int(args["post"])))
    if name == "neuron_outputs":
        top = int(args.get("top", 20))
        return _format(name, core.neuron_outputs(int(args["body"]), top))
    if name == "neuron_inputs":
        top = int(args.get("top", 20))
        return _format(name, core.neuron_inputs(int(args["body"]), top))
    if name == "degree":
        return _format(name, core.degree(int(args["body"])))
    if name == "search_neurons":
        return _format(name, core.search_neurons(
            args["query"], args.get("field", "type"), int(args.get("limit", 20))))
    if name == "superclass_projection":
        return _format(name, core.superclass_projection(args["superclass"]))
    if name == "hub_targets":
        return _format(name, core.hub_targets(str(args["name"])))
    if name == "list_superclasses":
        scs = core.list_superclasses()
        return "可用 superclass token (%d):\n  " % len(scs) + "\n  ".join(scs)
    if name == "pathway":
        return _format(name, core.pathway(
            int(args["source"]), int(args["target"]), int(args.get("max_via", 1))))
    if name == "export_swarm_motifs":
        # return the raw motif object as JSON text (SwarmLabs json.loads it)
        return json.dumps(export_swarm_motifs(bool(args.get("refresh", False))),
                          ensure_ascii=False)
    # ---- Phase 6 developer tools ----
    if name == "list_blueprints":
        return json.dumps(_list_blueprints(), ensure_ascii=False)
    if name == "list_modules":
        return json.dumps(_list_modules(), ensure_ascii=False)
    # ---- functional-unit composition library (Tier-1) ----
    if name == "list_functional_units":
        return json.dumps(_list_functional_units(args), ensure_ascii=False)
    if name == "get_functional_unit":
        return json.dumps(_get_functional_unit(args), ensure_ascii=False)
    if name == "list_evidence_ledger":
        return json.dumps(_list_evidence_ledger(args), ensure_ascii=False)
    if name == "list_connection_types":
        return json.dumps(_list_connection_types(args), ensure_ascii=False)
    if name == "compose_from_units":
        return json.dumps(_compose_from_units(args), ensure_ascii=False)
    if name == "list_bio_motifs":
        return json.dumps(_list_bio_motifs(), ensure_ascii=False)
    if name == "batch_generate_topologies":
        return json.dumps(_batch_generate(args), ensure_ascii=False)
    if name == "get_provenance_bundle":
        return json.dumps(_get_prov_bundle(str(args["blueprint"])), ensure_ascii=False)
    if name == "list_stacked_blueprints":
        return json.dumps(_list_stacked_blueprints(), ensure_ascii=False)
    if name == "get_stacked_feasibility":
        return json.dumps(_get_stacked_feasibility(str(args["name"])), ensure_ascii=False)
    if name == "list_neuropils":
        top = int(args.get("top", 30))
        return json.dumps(_list_neuropils(top), ensure_ascii=False)
    if name == "get_neuropil_detail":
        return json.dumps(_get_neuropil_detail(str(args["name"])), ensure_ascii=False)
    # ---- Phase 7: Module factory tools ----
    if name == "get_module":
        return json.dumps(_get_module(str(args["name"])), ensure_ascii=False)
    if name == "check_module_compatibility":
        return json.dumps(_check_compatibility(args.get("modules", [])), ensure_ascii=False)
    if name == "compose_virtual_organism":
        return json.dumps(_compose_organism(args), ensure_ascii=False)
    if name == "list_virtual_organisms":
        return json.dumps(_list_virtual_organisms(), ensure_ascii=False)
    if name == "list_presets":
        return json.dumps(_list_presets(), ensure_ascii=False)
    if name == "get_preset":
        return json.dumps(_get_preset(str(args["name"])), ensure_ascii=False)
    if name == "apply_preset":
        return json.dumps(_apply_preset(args), ensure_ascii=False)
    # ---- Phase 5: SwarmLabs 集成 ----
    if name == "organism_to_swarmlabs":
        return json.dumps(_organism_to_swarmlabs(args), ensure_ascii=False)
    if name == "get_module_agent_roles":
        return json.dumps(_get_module_agent_roles(), ensure_ascii=False)
    # ---- Phase 6: 虚拟生物市场 ----
    if name == "save_market_organism":
        return json.dumps(_save_market_organism(args), ensure_ascii=False)
    if name == "load_market_organism":
        return json.dumps(_load_market_organism(args), ensure_ascii=False)
    if name == "list_market_organisms":
        return json.dumps(_list_market_organisms(args), ensure_ascii=False)
    if name == "rate_market_organism":
        return json.dumps(_rate_market_organism(args), ensure_ascii=False)
    if name == "search_market_organisms":
        return json.dumps(_search_market_organisms(args), ensure_ascii=False)
    if name == "delete_market_organism":
        return json.dumps(_delete_market_organism(args), ensure_ascii=False)
    # ---- Phase 8: 组合规则 middleware ----
    if name == "list_combination_rules":
        return json.dumps(_list_combination_rules(), ensure_ascii=False)
    if name == "validate_combination":
        return json.dumps(_validate_combination(args), ensure_ascii=False)
    if name == "expand_organism":
        return json.dumps(_expand_organism(args), ensure_ascii=False)
    if name == "get_multiplier_metrics":
        return json.dumps(_get_multiplier_metrics(args), ensure_ascii=False)
    raise ValueError("unknown tool: %s" % name)


# --------------------------------------------------------------------------- #
# JSON-RPC loop
# --------------------------------------------------------------------------- #
def main():
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            continue
        method = req.get("method")
        rid = req.get("id")

        if method == "initialize":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "drosophila-connectome", "version": "2.18.0"},
            }}
        elif method == "notifications/initialized":
            continue
        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {}}
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            try:
                text = handle_call(name, params.get("arguments", {}))
                resp = {"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                }}
            except Exception as e:  # noqa: BLE001
                resp = {"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": "ERROR: %s" % e}],
                    "isError": True,
                }}
        else:
            resp = {"jsonrpc": "2.0", "id": rid, "error": {
                "code": -32601, "message": "method not found: %s" % method}}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
