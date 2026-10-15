#!/usr/bin/env python3
"""Claim Graph (Blueprint IR) — build a typed directed graph from research_claims.json.

This is the L1 layer of the Verifiable Research Object (VRO) protocol. It replaces a
flat list of claims with a typed directed graph, so that "which claim is bare, which
has evidence, which was refuted" is machine-readable at a glance.

Inspired by (and an instance of) two 2026 frontier lines:
  - "Toward an Engineering of Science" (UIUC, 2026): Blueprints as typed graph
    components (Claim / Evidence / Assumption / Definition / Risk) with status tracking.
  - "F(AI)2R: Verifiable AI Provenance as an Executable Skill" (arXiv:2607.25637):
    the claim ladder separating machine-checkable / machine-judged / human-checked.

Node types : claim | evidence | assumption | definition | risk
Edge types : supports | contradicts | depends_on | tests
Status     : draft -> stated -> supported -> verified | refuted | rejected | boundary

Usage:
    python scripts/claim_graph.py build --out claim_graph.json
    python scripts/claim_graph.py stats --graph claim_graph.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

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

# verification level (V0..V5) heuristic, aligned with INNER_STRENGTH_ROADMAP_V2
def _verification_level(status: str, n_evidence: int, has_repro: bool) -> str:
    if status == "verified" and n_evidence >= 1 and has_repro:
        return "V3"  # adversarial-grade: machine-enforced + reproducible
    if status == "supported" and n_evidence >= 1:
        return "V2"
    if status == "boundary":
        return "V1"
    if status in ("refuted", "rejected"):
        return "V1"
    return "V0"


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build(src: str) -> dict:
    rc = _load(src)
    nodes: list[dict] = []
    edges: list[dict] = []
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
            verification_level=_verification_level(status, len(ev), has_repro),
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
        # definition node from quantitative prediction target (lightweight)
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Claim Graph (Blueprint IR).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--src", default="research_claims.json")
    b.add_argument("--out", default="claim_graph.json")

    s = sub.add_parser("stats")
    s.add_argument("--graph", default="claim_graph.json")

    args = ap.parse_args()

    if args.cmd == "build":
        g = build(args.src)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(g, f, ensure_ascii=False, indent=2)
        st = g["stats"]
        print(f"claim_graph -> {args.out}")
        print(f"  nodes={st['n_nodes']} edges={st['n_edges']} "
              f"claims={st['n_claims']} evidence={st['n_evidence']} "
              f"assumptions={st['n_assumptions']} definitions={st['n_definitions']} risks={st['n_risks']}")
        return 0

    if args.cmd == "stats":
        g = _load(args.graph)
        print(json.dumps(g["stats"], ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
