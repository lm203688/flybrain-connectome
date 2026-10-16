#!/usr/bin/env python3
"""check_claim_graph.py — Gate 48: validate the Claim Graph (Blueprint IR).

Machine-enforces the structural integrity of the claim graph, independently of any
analyst summary. This is the L1/L2 boundary of the Verifiable Research Object (VRO)
protocol: it makes "which claim is bare" a machine-checkable predicate.

Rules (any FAIL -> exit 1):
  V1  every claim node is either supported (>=1 incoming supports/tests edge)
      or explicitly terminal (status in {boundary, rejected, refuted})
  V2  every evidence node carries an artifact or script pointer
  V3  every node status is on the status ladder
  V4  claims with status in {supported, verified} have >=1 incoming supports/tests edge
  V5  claims with status in {refuted, rejected, boundary} carry documentation
      (a risk node or >=1 falsified mechanism)
  V6  every edge endpoint references an existing node
  V7  all node/edge types are in the allowed vocabulary
  V8  no claim is left in status "draft" (WARNING only, not FAIL)
  V9  a claim whose status is supported/verified must not be contradicted by a
      preregistered tests edge with verdict in {FAIL, WEAK_PASS, ACCEPT}
      (WARNING only: surfaces "claim status outruns its machine evidence")

Usage:
    python scripts/check_claim_graph.py --graph claim_graph.json
    python scripts/check_claim_graph.py --inject   # run the injection battery (Gate 39)
"""
from __future__ import annotations

import argparse
import copy
import json
import sys

ALLOWED_NODE_TYPES = {"claim", "evidence", "assumption", "definition", "risk"}
ALLOWED_EDGE_TYPES = {"supports", "contradicts", "depends_on", "tests"}
ALLOWED_STATUS = {
    "draft", "stated", "supported", "verified",
    "refuted", "rejected", "boundary",
}
SUPPORTED_STATUS = {"supported", "verified"}
TERMINAL_STATUS = {"boundary", "rejected", "refuted"}


def check(g: dict) -> dict:
    nodes = {n["id"]: n for n in g.get("nodes", [])}
    edges = g.get("edges", [])
    failures: list[dict] = []
    warnings: list[dict] = []

    def fail(rule: str, detail: str, node: str | None = None) -> None:
        failures.append({"rule": rule, "detail": detail, "node": node})

    def warn(rule: str, detail: str, node: str | None = None) -> None:
        warnings.append({"rule": rule, "detail": detail, "node": node})

    # V7 node types
    for nid, n in nodes.items():
        if n.get("type") not in ALLOWED_NODE_TYPES:
            fail("V7", f"unknown node type {n.get('type')!r}", nid)
        if "status" in n and n["status"] not in ALLOWED_STATUS:
            fail("V3", f"status {n['status']!r} not on ladder", nid)

    # V6 edge endpoints + V7 edge types
    for e in edges:
        if e.get("type") not in ALLOWED_EDGE_TYPES:
            fail("V7", f"unknown edge type {e.get('type')!r}", e.get("from"))
        if e.get("from") not in nodes:
            fail("V6", f"edge.from {e.get('from')!r} not a node", e.get("from"))
        if e.get("to") not in nodes:
            fail("V6", f"edge.to {e.get('to')!r} not a node", e.get("to"))

    # index incoming supports/tests per claim
    incoming_support: dict[str, int] = {}
    for e in edges:
        if e.get("type") in ("supports", "tests") and e.get("to") in nodes:
            incoming_support[e["to"]] = incoming_support.get(e["to"], 0) + 1

    # per-claim rules
    for nid, n in nodes.items():
        if n.get("type") != "claim":
            continue
        status = n.get("status", "stated")
        sup = incoming_support.get(nid, 0)

        # V4
        if status in SUPPORTED_STATUS and sup == 0:
            fail("V4", f"claim status={status} but has 0 supports/tests edges", nid)

        # V1
        if sup == 0 and status not in TERMINAL_STATUS:
            fail("V1", f"claim is bare (0 supports/tests) and not terminal (status={status})", nid)

        # V5
        if status in TERMINAL_STATUS:
            has_risk = any(
                e.get("from") == nid and e.get("type") == "depends_on"
                and nodes.get(e.get("to"), {}).get("type") == "risk"
                for e in edges
            )
            has_mech = n.get("n_falsified_mechanisms", 0) > 0
            if not (has_risk or has_mech):
                fail("V5", f"terminal claim status={status} lacks documentation (risk node / falsified mechanism)", nid)

        # V8
        if status == "draft":
            warn("V8", "claim still in draft", nid)

    # V9 — claim status must not outrun a preregistered tests edge
    bad_protocol_verdicts = {"FAIL", "WEAK_PASS", "ACCEPT"}
    for e in edges:
        if e.get("type") != "tests":
            continue
        dst = e.get("to")
        dn = nodes.get(dst, {})
        if dn.get("type") != "claim":
            continue
        if dn.get("status") in SUPPORTED_STATUS and e.get("verdict") in bad_protocol_verdicts:
            warn(
                "V9",
                f"claim status={dn.get('status')} outruns preregistered evidence "
                f"({e.get('from')} verdict={e.get('verdict')})",
                dst,
            )

    # V2 evidence pointers
    for nid, n in nodes.items():
        if n.get("type") != "evidence":
            continue
        if n.get("subtype") == "preregistered_protocol":
            if not n.get("protocol_ref"):
                fail("V2", "preregistered protocol evidence lacks protocol_ref", nid)
            continue
        if not (n.get("artifact") or n.get("script")):
            fail("V2", "evidence node lacks artifact/script pointer", nid)

    verdict = "PASS" if not failures else "FAIL"
    return {
        "gate": "Gate 48 — claim graph integrity",
        "verdict": verdict,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "n_failures": len(failures),
        "n_warnings": len(warnings),
        "failures": failures,
        "warnings": warnings,
    }


def _injections() -> list[tuple[str, dict, str]]:
    """Injection battery: each case mutates a valid graph and names the rule it must trip.

    This is what makes the gate a V3 gate (a gate that has proven it can go red).
    """
    base = {
        "nodes": [
            {"id": "claim:X", "type": "claim", "status": "verified", "n_falsified_mechanisms": 0},
            {"id": "evidence:X:a", "type": "evidence", "artifact": "x.json"},
            {"id": "risk:X:b", "type": "risk", "text": "boundary"},
        ],
        "edges": [
            {"from": "evidence:X:a", "type": "supports", "to": "claim:X"},
        ],
    }
    cases: list[tuple[str, dict, str]] = []

    # 1. bare claim — strip its supporting edge (V1/V4)
    g = copy.deepcopy(base)
    g["edges"] = []
    cases.append(("bare_claim_no_supports", g, "V1"))

    # 2. evidence node with no artifact/script pointer (V2)
    g = copy.deepcopy(base)
    g["nodes"][1] = {"id": "evidence:X:a", "type": "evidence"}
    cases.append(("evidence_without_pointer", g, "V2"))

    # 3. unknown node type (V7)
    g = copy.deepcopy(base)
    g["nodes"].append({"id": "widget:X", "type": "widget"})
    cases.append(("unknown_node_type", g, "V7"))

    # 4. dangling edge endpoint (V6)
    g = copy.deepcopy(base)
    g["edges"].append({"from": "evidence:X:ghost", "type": "supports", "to": "claim:X"})
    cases.append(("dangling_edge", g, "V6"))

    # 5. terminal claim without documentation (V5)
    g = copy.deepcopy(base)
    g["nodes"][0] = {"id": "claim:X", "type": "claim", "status": "boundary", "n_falsified_mechanisms": 0}
    g["nodes"] = [n for n in g["nodes"] if n["type"] != "risk"]
    g["edges"] = [e for e in g["edges"] if e.get("to") != "risk:X:b"]
    cases.append(("terminal_claim_undocumented", g, "V5"))

    # 6. status off the ladder (V3)
    g = copy.deepcopy(base)
    g["nodes"][0]["status"] = "totally_fine"
    cases.append(("status_off_ladder", g, "V3"))

    return cases


def run_injections() -> int:
    """Run every injected defect and assert the checker reports the expected rule."""
    print("=" * 60)
    print("Gate 48 — injection battery (each injected defect must turn the gate red)")
    bad = 0
    for name, g, expect_rule in _injections():
        rep = check(g)
        rules = {f["rule"] for f in rep["failures"]}
        ok = rep["verdict"] == "FAIL" and expect_rule in rules
        flag = "OK " if ok else "MISS"
        if not ok:
            bad += 1
        print(f"  [{flag}] {name:<32} expected={expect_rule} got={sorted(rules) or 'none'}")
    print("=" * 60)
    print(f"injected-defect battery: {len(_injections()) - bad}/{len(_injections())} caught")
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="claim_graph.json")
    ap.add_argument("--json", action="store_true", help="emit JSON report only")
    ap.add_argument("--inject", action="store_true", help="run the injected-defect battery (Gate 39)")
    args = ap.parse_args()

    if args.inject:
        return run_injections()

    with open(args.graph, encoding="utf-8") as f:
        g = json.load(f)

    rep = check(g)

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print(f"{rep['gate']}")
        print(f"  nodes={rep['n_nodes']} edges={rep['n_edges']}")
        print(f"  failures={rep['n_failures']} warnings={rep['n_warnings']}")
        for f in rep["failures"]:
            print(f"  FAIL [{f['rule']}] {f['detail']}  <- {f['node']}")
        for w in rep["warnings"]:
            print(f"  WARN [{w['rule']}] {w['detail']}  <- {w['node']}")
        print("=" * 60)
        print(f"GATE 48: {rep['verdict']}")

    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
