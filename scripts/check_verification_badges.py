#!/usr/bin/env python3
"""check_verification_badges.py — Gate 50: verification badge integrity.

Asserts the claim-graph badge sidecar (badges.json) is consistent with the
claim graph: every claim node has a verification_level that matches its
badge entry, every badge is on the ladder V0..V5, and every claim with
V5 must have a receipt file on disk.

Usage:
    python scripts/check_verification_badges.py --graph claim_graph.json --badges badges.json
    python scripts/check_verification_badges.py --inject
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LADDER = {"V0", "V1", "V2", "V3", "V4", "V5"}


def check(graph: dict, badges: dict, root: Path) -> dict:
    failures: list[dict] = []
    warnings: list[dict] = []
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    badge_map = badges.get("badges", {})

    # V-A: every claim in graph has a badge entry
    for nid, node in nodes.items():
        if node.get("type") != "claim":
            continue
        if nid not in badge_map:
            failures.append({"rule": "B1", "detail": f"claim {nid} missing from badges", "node": nid})

    # V-B: every badge is on the ladder
    for nid, b in badge_map.items():
        lvl = b.get("level")
        if lvl not in LADDER:
            failures.append({"rule": "B2", "detail": f"badge level {lvl!r} not on ladder", "node": nid})

    # V-C: node's verification_level matches badge entry
    for nid, b in badge_map.items():
        node = nodes.get(nid)
        if not node:
            continue
        node_lvl = node.get("verification_level")
        if node_lvl != b.get("level"):
            failures.append({
                "rule": "B3",
                "detail": f"claim_graph.verification_level={node_lvl!r} != badges.level={b.get('level')!r}",
                "node": nid,
            })

    # V-D: V5 claims must have receipt on disk
    for nid, b in badge_map.items():
        if b.get("level") == "V5":
            claim_id = nid.split(":", 1)[1]
            receipt_path = root / "receipts" / f"{claim_id}.json"
            if not receipt_path.exists():
                failures.append({
                    "rule": "B4",
                    "detail": f"V5 claim {nid} has no receipt file at {receipt_path}",
                    "node": nid,
                })

    # V-E: bare claims must be V0
    for nid, b in badge_map.items():
        node = nodes.get(nid)
        if not node or node.get("type") != "claim":
            continue
        supports = sum(
            1 for e in graph.get("edges", [])
            if e.get("to") == nid and e.get("type") in ("supports", "tests")
        )
        if supports == 0 and b.get("level") != "V0":
            failures.append({
                "rule": "B5",
                "detail": f"bare claim (0 supports) but badge level is {b.get('level')}",
                "node": nid,
            })

    verdict = "PASS" if not failures else "FAIL"
    return {
        "gate": "Gate 50 — verification badge integrity",
        "verdict": verdict,
        "n_claims": sum(1 for n in nodes.values() if n.get("type") == "claim"),
        "n_badges": len(badge_map),
        "n_failures": len(failures),
        "n_warnings": len(warnings),
        "failures": failures,
        "warnings": warnings,
    }


def _injections() -> list[tuple[str, dict, dict, str]]:
    """Injection battery: each case must trip its expected rule."""
    base_graph = {
        "nodes": [
            {"id": "claim:X", "type": "claim", "status": "supported", "verification_level": "V2"},
            {"id": "evidence:X:a", "type": "evidence", "artifact": "x.json"},
        ],
        "edges": [
            {"from": "evidence:X:a", "type": "supports", "to": "claim:X"},
        ],
    }
    base_badges = {"badges": {"claim:X": {"level": "V2", "reason": "test"}}}

    cases: list[tuple[str, dict, dict, str]] = []

    # B1: claim missing from badges
    g = copy.deepcopy(base_graph)
    b = copy.deepcopy(base_badges)
    b["badges"] = {}
    cases.append(("claim_missing_from_badges", g, b, "B1"))

    # B2: badge level off ladder
    g = copy.deepcopy(base_graph)
    b = copy.deepcopy(base_badges)
    b["badges"]["claim:X"]["level"] = "V99"
    cases.append(("badge_level_off_ladder", g, b, "B2"))

    # B3: mismatch between node and badge
    g = copy.deepcopy(base_graph)
    b = copy.deepcopy(base_badges)
    b["badges"]["claim:X"]["level"] = "V3"
    cases.append(("node_badge_mismatch", g, b, "B3"))

    # B5: bare claim but V>0
    g = copy.deepcopy(base_graph)
    g["edges"] = []  # strip supports → bare
    b = copy.deepcopy(base_badges)
    b["badges"]["claim:X"]["level"] = "V1"
    cases.append(("bare_claim_with_badge", g, b, "B5"))

    return cases


def run_injections() -> int:
    print("=" * 60)
    print("Gate 50 — injection battery (each injected defect must trip its rule)")
    bad = 0
    for name, g, b, expected in _injections():
        rep = check(g, b, ROOT)
        rules = {f["rule"] for f in rep["failures"]}
        ok = rep["verdict"] == "FAIL" and expected in rules
        if not ok:
            bad += 1
        flag = "OK " if ok else "MISS"
        print(f"  [{flag}] {name:<32} expected={expected} got={sorted(rules) or 'none'}")
    print("=" * 60)
    print(f"injected-defect battery: {len(_injections()) - bad}/{len(_injections())} caught")
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="claim_graph.json")
    ap.add_argument("--badges", default="badges.json")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--inject", action="store_true")
    args = ap.parse_args()

    if args.inject:
        return run_injections()

    with open(args.graph, encoding="utf-8") as f:
        graph = json.load(f)
    with open(args.badges, encoding="utf-8") as f:
        badges = json.load(f)

    rep = check(graph, badges, ROOT)

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print(rep["gate"])
        print(f"  claims={rep['n_claims']} badges={rep['n_badges']}")
        print(f"  failures={rep['n_failures']} warnings={rep['n_warnings']}")
        for f in rep["failures"]:
            print(f"  FAIL [{f['rule']}] {f['detail']}  <- {f['node']}")
        print("=" * 60)
        print(f"GATE 50: {rep['verdict']}")

    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
