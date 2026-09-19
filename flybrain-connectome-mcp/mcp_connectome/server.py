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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

PROTOCOL_VERSION = "2024-11-05"

# ---- path to the SwarmLabs derived motif artifact (NOT the raw neuron data) ----
_MOTIFS_DIR = os.path.dirname(os.path.abspath(__file__))      # .../mcp_connectome
MOTIF_FILE = os.path.abspath(os.path.join(_MOTIFS_DIR, "..", "motifs",
                                           "swarm_agent_topology_motifs.json"))
EXTRACT_SCRIPT = os.path.abspath(os.path.join(_MOTIFS_DIR, "..", "extract_motifs.py"))


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
        "description": "列出 flybrain 当前全部模块 (10 个) 的名称、能力 profile、生物学依据与描述。",
        "inputSchema": {"type": "object", "properties": {}},
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
    if name == "list_bio_motifs":
        return json.dumps(_list_bio_motifs(), ensure_ascii=False)
    if name == "batch_generate_topologies":
        return json.dumps(_batch_generate(args), ensure_ascii=False)
    if name == "get_provenance_bundle":
        return json.dumps(_get_prov_bundle(str(args["blueprint"])), ensure_ascii=False)
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
                "serverInfo": {"name": "drosophila-connectome", "version": "1.0.0"},
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
