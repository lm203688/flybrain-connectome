#!/usr/bin/env python3
"""compute_verification_badges.py — S5 claim verification badges.

Computes V0–V5 verification levels for every claim in claim_graph.json,
aligned with the INNER_STRENGTH_ROADMAP_V2 self-verification ladder:

  V0  unverified     — claim is bare, no machine evidence
  V1  reproducible   — same seed / same code → identical results
  V2  machine-tested — at least one preregistered protocol ran against the claim
  V3  preregistered  — claim's verdict is enforced by a Gate (fail-closed)
  V4  cross-checked  — at least two independent reads of the evidence agree
  V5  externally verified — a receipt exists AND red-team passed adversarial battery

Writes a badges.json sidecar and patches claim_graph.json in place so each
claim node carries its `verification_level` field.

Usage:
    python scripts/compute_verification_badges.py --graph claim_graph.json --out badges.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


LADDER = ["V0", "V1", "V2", "V3", "V4", "V5"]


def _has_receipts(root: Path, claim_id: str) -> bool:
    return (root / "receipts" / f"{claim_id}.json").exists()


def _claim_badge(
    node: dict,
    edges: list[dict],
    *,
    has_receipt: bool,
    redteam_passed: bool,
) -> dict:
    """Compute V-level for one claim node.

    Ladder (each rung requires the previous):
      V0  bare (no supports/tests edges)
      V1  ≥1 supports/tests edge (machine-tested)
      V2  ≥1 preregistered protocol tests edge (preregistered)
      V3  ≥2 supports/tests edges (cross-checked)
      V4  receipt present (third-party verifiable)
      V5  receipt + redteam passed (adversarially verified)
    """
    status = node.get("status", "stated")
    supports = sum(
        1 for e in edges if e.get("to") == node["id"] and e.get("type") in ("supports", "tests")
    )
    # A claim is only eligible for V2+ if it has some machine evidence.
    # Bare claims (supports==0) cannot exceed V0 regardless of status.
    if supports == 0:
        return {"level": "V0", "reason": "bare claim (no supports/tests edges)"}

    has_prereg = any(
        e.get("from") and ("prereg" in str(e.get("from", "")).lower() or "protocol" in str(e.get("from", "")).lower())
        and e.get("to") == node["id"]
        for e in edges
    )

    if not has_prereg:
        return {"level": "V1", "reason": "≥1 evidence edge but no preregistered protocol"}

    if supports < 2:
        return {"level": "V2", "reason": "preregistered, single source"}

    if not has_receipt:
        return {"level": "V3", "reason": "cross-checked, no receipt"}

    if not redteam_passed:
        return {"level": "V4", "reason": "receipt present, redteam not verified"}

    return {"level": "V5", "reason": f"cross-checked + receipt + redteam (status={status})"}


def compute(graph: dict, root: Path, *, redteam_passed: bool) -> dict:
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = graph["edges"]

    badges = {}
    for nid, node in nodes.items():
        if node.get("type") != "claim":
            continue
        claim_id = nid.split(":", 1)[1]
        badge = _claim_badge(
            node,
            edges,
            has_receipt=_has_receipts(root, claim_id),
            redteam_passed=redteam_passed,
        )
        badges[nid] = badge

    # patch graph
    for nid, badge in badges.items():
        if nid in nodes:
            nodes[nid]["verification_level"] = badge["level"]
            nodes[nid]["verification_reason"] = badge["reason"]

    return badges


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default="claim_graph.json")
    ap.add_argument("--out", default="badges.json")
    ap.add_argument("--no-redteam", action="store_true", help="pretend redteam did not pass")
    args = ap.parse_args()

    graph_path = ROOT / args.graph
    with open(graph_path, encoding="utf-8") as f:
        graph = json.load(f)

    badges = compute(graph, ROOT, redteam_passed=not args.no_redteam)

    out_path = ROOT / args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"schema": "vro_badges_v1", "badges": badges}, f, ensure_ascii=False, indent=2)

    # patch graph in place
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"verification badges — {len(badges)} claims")
    for nid, b in badges.items():
        print(f"  {nid}: {b['level']}  ({b['reason']})")
    print("=" * 60)
    print(f"patched {graph_path}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
