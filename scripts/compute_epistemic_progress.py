#!/usr/bin/env python3
"""compute_epistemic_progress.py — EPE 双轴进度信号（dense epistemic progress signal）.

Why this exists
---------------
The current V0–V5 badge ladder (`compute_verification_badges.py`) is computed
from the *structure* of the claim graph (how many supports/tests edges point at
a claim, whether a receipt file exists, and one global `redteam_passed` flag).
That measures **apparatus** — what verification machinery is attached — and it
is *not* the same thing as **evidence** — what the claim actually demonstrated.

The two can diverge: a claim can carry the full apparatus (graph edges +
receipt + red-team flag) while its own preregistered protocols returned
WEAK / FAIL.  Collapsing both into one "V5" hides that divergence.

This script separates the two axes:

  A (apparatus)  A0–A5   what machinery is attached        (from badges.json)
  E (evidence)   E0–E5   what was demonstrated             (from receipt verdicts + tiers)

It also runs a **semantic audit** of the ladder: for each rung it compares the
rung's *claimed meaning* (its docstring) with the *predicate actually computed*
in `compute_verification_badges.py`.  A rung whose predicate does not test the
property it names is a metric that does not measure what it claims — the exact
failure mode this project has caught in its own metrics three times before
(S6 control-scoreability, S7 resolution clamp, PR-2b analytic redundancy).

Finally it exports `boundary_atlas.json`: every documented non-confirmation
(FAIL / WEAK / ACCEPT / BOUNDARY) as a durable, citable negative-knowledge
record.

Outputs
-------
  progress.json         per-claim {apparatus, evidence, gap} + ladder audit + vector
  boundary_atlas.json   durable negative-knowledge export

Usage
-----
  python scripts/compute_epistemic_progress.py
  python scripts/compute_epistemic_progress.py --json-out progress.json --atlas-out boundary_atlas.json
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Evidence ladder (E0–E5), aligned with docs/AUDIT_DISCLOSURE.md L1–L5
# ---------------------------------------------------------------------------
E_LADDER = {
    0: "E0 none        — no protocol tested the claim",
    1: "E1 reported    — a protocol ran; verdict WEAK / ACCEPT / BOUNDARY (documented, not confirmed)",
    2: "E2 supported   — >=1 protocol PASS at L2 (measurement layer)",
    3: "E3 generalizes — >=1 protocol PASS at L3 (cross-family, held-out)",
    4: "E4 causal      — >=1 protocol PASS at L4 (intervention)",
    5: "E5 external    — third-party reproduction",
}

# Verdicts that raise evidence to the protocol's own tier, and verdicts that
# only ever raise it to E1 (a documented non-confirmation is knowledge, but it
# is not confirmation of the claim).
_CONFIRMING = {"PASS"}
_REPORTED = {"WEAK", "WEAK_PASS", "ACCEPT", "BOUNDARY", "BOUNDARY_PARTIAL_FALSIFICATION"}

# Semantic audit table: rung -> (claimed meaning, predicate actually computed).
# The predicate strings mirror compute_verification_badges.py `_claim_badge`.
_LADDER_SEMANTICS = {
    "V0": ("unverified — claim is bare, no machine evidence",
           "supports==0 (no supports/tests edge)"),
    "V1": ("reproducible — same seed / same code -> identical results",
           "supports>=1 (at least one evidence edge)"),
    "V2": ("machine-tested — at least one preregistered protocol ran",
           "a prereg/protocol-named edge exists (does not check it RAN)"),
    "V3": ("preregistered — verdict is enforced by a Gate (fail-closed)",
           "supports>=2 (two edges, no gate-enforcement check)"),
    "V4": ("cross-checked — two independent reads of the evidence agree",
           "a receipt file exists (a receipt is a hash commitment, not a 2nd read)"),
    "V5": ("externally verified — a receipt exists AND red-team passed",
           "receipt + global redteam flag (not per-claim, no external party)"),
}


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _tier(evidence_tier: str | None) -> int:
    """Map a free-text evidence_tier string to an integer L-tier (default 2)."""
    if not evidence_tier:
        return 2
    m = re.search(r"L([0-9])", str(evidence_tier))
    return int(m.group(1)) if m else 2


def _protocol_verdicts() -> dict[str, str]:
    """protocol_ref -> verdict, gathered from receipts + result files.

    Provenance is explicit: every verdict comes from a file on disk.
    """
    v: dict[str, str] = {}
    for f in sorted(glob.glob(str(ROOT / "receipts" / "*.json"))):
        try:
            r = _load(Path(f))
        except Exception:
            continue
        pid = r.get("protocol_ref") or r.get("claim_id")
        verdict = r.get("expected_verdict")
        if pid and verdict:
            v[str(pid)] = str(verdict)
    # Result files whose verdicts are not mirrored in a receipt.
    extra = {
        "PR5": ROOT / "_c1_cell_densification" / "c1_results.json",
        "PR3_v2": ROOT / "_c3_rank_label_pr3v2" / "c3_results.json",
    }
    for pid, path in extra.items():
        if path.exists():
            try:
                d = _load(path)
                if d.get("verdict"):
                    v[pid] = str(d["verdict"])
            except Exception:
                pass
    return v


def _apparatus_level(badges: dict) -> dict[str, str]:
    return {k.split(":", 1)[1]: b["level"] for k, b in badges.get("badges", {}).items()}


def compute() -> dict:
    graph = _load(ROOT / "claim_graph.json")
    badges = _load(ROOT / "badges.json")
    claims = _load(ROOT / "research_claims.json")
    verdicts = _protocol_verdicts()

    apparatus = _apparatus_level(badges)
    prereg = {k: v for k, v in claims.get("preregistered", {}).items()
              if isinstance(v, dict) and "claim_id" in v}

    claim_ids = [n["id"].split(":", 1)[1] for n in graph["nodes"] if n.get("type") == "claim"]

    per_claim: dict[str, dict] = {}
    for cid in claim_ids:
        protos = []
        best_e = 0
        for pid, proto in prereg.items():
            if proto.get("claim_id") != cid:
                continue
            tier = _tier(proto.get("evidence_tier"))
            verdict = verdicts.get(pid, "UNKNOWN")
            if verdict in _CONFIRMING:
                e = tier
            elif verdict in _REPORTED:
                e = 1
            else:
                e = 0
            best_e = max(best_e, e)
            protos.append({
                "protocol": pid,
                "tier": f"L{tier}",
                "kind": proto.get("kind") or "protocol",
                "verdict": verdict,
                "raises_to": f"E{e}",
            })
        a = apparatus.get(cid, "V0")
        per_claim[cid] = {
            "apparatus": a,
            "evidence": f"E{best_e}",
            "gap": int(a[1:]) - best_e,
            "protocols": protos,
        }

    # ---- semantic audit of the ladder -------------------------------------
    ladder_audit = {}
    for rung, (claimed, predicate) in _LADDER_SEMANTICS.items():
        # A rung is "aligned" only if its predicate actually tests its claim.
        # We hard-code the judgement with a stated reason — this is an audit,
        # not a computed predicate, and it is meant to be argued with.
        aligned = rung in ("V0",)  # only V0's predicate matches its name
        ladder_audit[rung] = {
            "claimed": claimed,
            "computed_predicate": predicate,
            "predicate_tests_claim": aligned,
            "note": ("predicate matches the named property" if aligned else
                     "predicate measures apparatus presence, not the named property"),
        }

    # ---- dense progress vector (NOT collapsed to one scalar) --------------
    n = len(claim_ids) or 1
    a_ge3 = sum(1 for c in per_claim.values() if int(c["apparatus"][1:]) >= 3)
    e_ge2 = sum(1 for c in per_claim.values() if int(c["evidence"][1:]) >= 2)
    e_ge3 = sum(1 for c in per_claim.values() if int(c["evidence"][1:]) >= 3)
    divergent = [c for c, v in per_claim.items() if v["gap"] >= 2]

    vector = {
        "apparatus_coverage_A>=3": round(a_ge3 / n, 4),
        "evidence_coverage_E>=2": round(e_ge2 / n, 4),
        "evidence_coverage_E>=3": round(e_ge3 / n, 4),
        "divergent_claims": divergent,
        "n_claims": len(claim_ids),
        "note": ("Reported as a VECTOR on purpose: collapsing to a single scalar "
                 "before the scalar itself is validated would repeat the "
                 "unvalidated-metric failure the project has caught 3x."),
    }

    # ---- boundary atlas ----------------------------------------------------
    atlas = []
    for pid, proto in prereg.items():
        verdict = verdicts.get(pid, "UNKNOWN")
        if verdict in _CONFIRMING:
            continue
        atlas.append({
            "protocol": pid,
            "claim": proto.get("claim_id"),
            "tier": proto.get("evidence_tier"),
            "kind": proto.get("kind") or "protocol",
            "verdict": verdict,
            "category": ("pre_execution_rejection" if proto.get("kind") == "pre_execution_rejection"
                         else ("weak" if verdict in ("WEAK", "WEAK_PASS")
                               else ("boundary" if verdict in ("BOUNDARY", "BOUNDARY_PARTIAL_FALSIFICATION")
                                     else "falsified"))),
        })
    # Claim-level boundary statuses (e.g. R3 boundary_partial_falsification,
    # R6 boundary_anchor_gap) are durable knowledge too, but they carry no
    # preregistered protocol — the atlas must not silently drop them.
    for c in claims.get("claims", []):
        st = str(c.get("status", ""))
        if "boundary" in st or "falsif" in st:
            atlas.append({
                "protocol": None,
                "claim": c.get("id"),
                "tier": "claim_status",
                "kind": "claim_boundary",
                "verdict": st,
                "category": "boundary",
            })

    return {
        "schema": "epistemic_progress_v1",
        "generated_from": ["claim_graph.json", "badges.json", "research_claims.json", "receipts/*.json"],
        "evidence_ladder": {f"E{k}": v for k, v in E_LADDER.items()},
        "claims": per_claim,
        "ladder_semantics_audit": ladder_audit,
        "progress_vector": vector,
        "boundary_atlas": atlas,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", default="progress.json")
    ap.add_argument("--atlas-out", default="boundary_atlas.json")
    args = ap.parse_args()

    result = compute()

    out = ROOT / args.json_out
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    atlas_path = ROOT / args.atlas_out
    with open(atlas_path, "w", encoding="utf-8") as f:
        json.dump({"schema": "boundary_atlas_v1",
                   "entries": result["boundary_atlas"]}, f, ensure_ascii=False, indent=2)

    print("=" * 68)
    print("EPE dual-axis progress")
    print("=" * 68)
    print(f"{'claim':6s} {'apparatus':10s} {'evidence':9s} gap  protocols")
    for cid, v in result["claims"].items():
        ps = ", ".join(f"{p['protocol']}={p['verdict']}" for p in v["protocols"]) or "-"
        print(f"{cid:6s} {v['apparatus']:10s} {v['evidence']:9s} {v['gap']:>3d}  {ps}")
    print("-" * 68)
    v = result["progress_vector"]
    print(f"apparatus A>=3 : {v['apparatus_coverage_A>=3']:.2%}")
    print(f"evidence  E>=2 : {v['evidence_coverage_E>=2']:.2%}")
    print(f"evidence  E>=3 : {v['evidence_coverage_E>=3']:.2%}")
    print(f"divergent      : {v['divergent_claims']}")
    print("-" * 68)
    print("ladder semantic audit (rungs whose predicate != their name):")
    for rung, a in result["ladder_semantics_audit"].items():
        flag = "OK " if a["predicate_tests_claim"] else "MISMATCH"
        print(f"  {rung}: [{flag}] claimed={a['claimed'][:52]}")
    print("-" * 68)
    print(f"boundary atlas : {len(result['boundary_atlas'])} entries -> {atlas_path.name}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
