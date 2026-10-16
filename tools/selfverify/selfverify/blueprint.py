"""selfverify.blueprint — S1 命题图（Blueprint IR）核心逻辑。

将扁平的 research_claims.json 升级为类型化有向命题图，使"哪些主张裸奔、
哪些有证据、哪些被证伪"一眼可见。

节点类型：claim | evidence | assumption | definition | risk
边类型：supports | contradicts | depends_on | tests
状态阶梯：draft → stated → supported → verified | refuted | rejected | boundary

参考：
  - "Toward an Engineering of Science" (UIUC, 2026): Blueprints as typed graph
  - "F(AI)2R: Verifiable AI Provenance as an Executable Skill" (arXiv:2607.25637)
"""
from __future__ import annotations

import json
import os
from typing import Any

ALLOWED_NODE_TYPES = {"claim", "evidence", "assumption", "definition", "risk"}
ALLOWED_EDGE_TYPES = {"supports", "contradicts", "depends_on", "tests"}
ALLOWED_STATUS = {
    "draft", "stated", "supported", "verified",
    "refuted", "rejected", "boundary",
}

# raw research_claims.json status -> claim-graph status ladder
STATUS_MAP = {
    "complete": "verified",
    "supported_after_metric_fix": "supported",
    "boundary_partial_falsification": "boundary",
    "boundary_anchor_gap": "boundary",
    "negative_result": "refuted",
}

# preregistered verdict -> status ladder (for the protocol-as-evidence node)
PROTOCOL_VERDICT_MAP = {
    "PASS": "verified",
    "WEAK_PASS": "boundary",
    "FAIL": "refuted",
    "ACCEPT": "rejected",  # pre-execution rejection
}


def verification_level(status: str, n_evidence: int, has_repro: bool) -> str:
    """计算验证等级 V0..V5（对齐 INNER_STRENGTH_ROADMAP_V2）。"""
    if status == "verified" and n_evidence >= 1 and has_repro:
        return "V3"  # adversarial-grade: machine-enforced + reproducible
    if status == "supported" and n_evidence >= 1:
        return "V2"
    if status == "boundary":
        return "V1"
    if status in ("refuted", "rejected"):
        return "V1"
    return "V0"


def build(src: str) -> dict[str, Any]:
    """从 research_claims.json 构建命题图。"""
    with open(src, encoding="utf-8") as f:
        rc = json.load(f)
    
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()

    def add_node(nid: str, ntype: str, **attrs) -> None:
        assert ntype in ALLOWED_NODE_TYPES, f"bad node type {ntype}"
        if nid in seen_nodes:
            return
        seen_nodes.add(nid)
        nodes.append({"id": nid, "type": ntype, **attrs})

    def add_edge(src_id: str, etype: str, dst_id: str, **attrs) -> None:
        assert etype in ALLOWED_EDGE_TYPES, f"bad edge type {etype}"
        edges.append({"from": src_id, "type": etype, "to": dst_id, **attrs})

    # ---- claim nodes from claims[] ----
    claim_ids: set[str] = set()
    for c in rc.get("claims", []):
        cid = c["id"]
        claim_ids.add(cid)
        raw_status = c.get("status", "stated")
        status = STATUS_MAP.get(raw_status, raw_status if raw_status in ALLOWED_STATUS else "stated")
        ev = c.get("supporting_evidence", []) or []
        has_repro = bool(c.get("reproduction_command"))
        add_node(
            f"claim:{cid}",
            "claim",
            title=c.get("title", ""),
            statement=c.get("statement", ""),
            raw_status=raw_status,
            status=status,
            external_dependency=c.get("external_dependency", "unknown"),
            verification_level=verification_level(status, len(ev), has_repro),
            n_evidence=len(ev),
            n_falsified_mechanisms=len(c.get("falsified_mechanisms", []) or []),
        )
        # evidence nodes
        for i, e in enumerate(ev):
            if isinstance(e, dict):
                art = e.get("artifact", f"evidence_{i}")
                eid = f"evidence:{cid}:{art}"
                add_node(
                    eid, "evidence",
                    artifact=art,
                    claim=e.get("claim", ""),
                    script=e.get("script", ""),
                )
            else:
                eid = f"evidence:{cid}:{i}"
                add_node(eid, "evidence", artifact=str(e))
            add_edge(eid, "supports", f"claim:{cid}")
        # assumption nodes from falsified mechanisms
        for m in c.get("falsified_mechanisms", []) or []:
            mech = m.get("mechanism", "unknown")
            aid = f"assumption:{cid}:{mech}"
            add_node(
                aid, "assumption",
                hypothesis=m.get("hypothesis", ""),
                verdict=m.get("verdict", ""),
            )
            add_edge(f"claim:{cid}", "depends_on", aid)
            if m.get("verdict", "").startswith("falsified"):
                add_edge(aid, "contradicts", f"claim:{cid}")
        # risk node from boundary statement
        bs = c.get("boundary_statement")
        if bs:
            rid = f"risk:{cid}:boundary"
            add_node(rid, "risk", text=bs)
            add_edge(f"claim:{cid}", "depends_on", rid)
        # definition node from quantitative prediction target
        if c.get("quantitative_prediction"):
            did = f"definition:{cid}:prediction"
            add_node(did, "definition", text=c["quantitative_prediction"])
            add_edge(f"claim:{cid}", "depends_on", did)

    # ---- preregistered protocol nodes (type=evidence, subtype=protocol) ----
    prereg = rc.get("preregistered", {}) or {}
    for key, block in prereg.items():
        if key in ("protocol", "frozen_at", "freeze_rules"):
            continue
        if not isinstance(block, dict):
            continue
        target = block.get("claim_id")
        if not target or target not in claim_ids:
            continue
        # pick the strongest verdict available in the block
        verdicts = []
        for k, v in block.items():
            if isinstance(v, dict) and "verdict" in v:
                verdicts.append(v["verdict"])
            if k == "verification" and isinstance(v, dict) and "verdict" in v:
                verdicts.append(v["verdict"])
        if block.get("kind") == "pre_execution_rejection":
            verdict = "ACCEPT"
        else:
            # strongest = worst outcome wins for honesty (FAIL > WEAK > PASS)
            order = {"FAIL": 3, "WEAK_PASS": 2, "PASS": 1, "ACCEPT": 3}
            verdict = max(verdicts, key=lambda x: order.get(x, 0)) if verdicts else "WEAK_PASS"
        nid = f"protocol:{key}"
        add_node(
            nid, "evidence",
            subtype="preregistered_protocol",
            protocol_ref=block.get("protocol_ref", ""),
            verdict=verdict,
            status=PROTOCOL_VERDICT_MAP.get(verdict, "stated"),
        )
        add_edge(nid, "tests", f"claim:{target}", verdict=verdict)

    graph = {
        "schema": "claim_graph_v1",
        "generated_from": os.path.basename(src),
        "node_types": sorted(ALLOWED_NODE_TYPES),
        "edge_types": sorted(ALLOWED_EDGE_TYPES),
        "status_ladder": ["draft", "stated", "supported", "verified", "refuted", "rejected", "boundary"],
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "n_claims": sum(1 for n in nodes if n["type"] == "claim"),
            "n_evidence": sum(1 for n in nodes if n["type"] == "evidence"),
            "n_assumptions": sum(1 for n in nodes if n["type"] == "assumption"),
            "n_definitions": sum(1 for n in nodes if n["type"] == "definition"),
            "n_risks": sum(1 for n in nodes if n["type"] == "risk"),
        },
    }
    return graph


def validate(graph: dict[str, Any]) -> list[str]:
    """验证命题图的完整性。返回错误列表。"""
    errors = []
    
    # 检查节点类型
    for node in graph.get("nodes", []):
        if node["type"] not in ALLOWED_NODE_TYPES:
            errors.append(f"节点 {node['id']} 类型无效: {node['type']}")
    
    # 检查边类型
    for edge in graph.get("edges", []):
        if edge["type"] not in ALLOWED_EDGE_TYPES:
            errors.append(f"边 {edge['from']}->{edge['to']} 类型无效: {edge['type']}")
    
    # 检查 claim 至少有证据或 boundary 状态
    claim_ids = [n["id"] for n in graph.get("nodes", []) if n["type"] == "claim"]
    evidence_targets = set()
    for edge in graph.get("edges", []):
        if edge["type"] == "supports":
            evidence_targets.add(edge["to"])
    
    for claim_id in claim_ids:
        if claim_id not in evidence_targets:
            # 检查是否有 boundary 状态
            claim_node = next((n for n in graph["nodes"] if n["id"] == claim_id), None)
            if claim_node and claim_node.get("status") != "boundary":
                errors.append(f"claim {claim_id} 无证据且无 boundary 状态")
    
    return errors
