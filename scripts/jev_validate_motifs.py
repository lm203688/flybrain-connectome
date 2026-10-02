#!/usr/bin/env python3
"""JEV-powered validation for the 45 motif_ref connection types.

Companion to `jev_validate_connections.py`, which validates the 21
abstraction-only types.  This script validates the 45 connection types
that DO carry a `motif_ref` field — i.e. they map to a named neuroanatomy
motif (axo_dendritic, feedforward_excitatory, dendro_dendritic, etc.).

Even though these already have a motif reference, we still want an
independent literature-evidence score from JEV so that:
  * users can distinguish "textbook" motifs from "preliminary" ones
    at a glance, without cross-referencing the original paper;
  * the 66-connection-type catalogue is uniformly annotated with a
    machine-readable evidence tier.

Queries three dimensions per motif (same rubric as the abstraction
script for cross-consistency):
  1. literature_support (noul)  — P(≥2 peer-reviewed papers describe this motif)
  2. evidence_strength (score)  — 0-10 published-evidence rubric
  3. computational_validation (noul) — P(≥1 published computational model)

Cost: 45 calls × 3 questions ≈ $0.002.

Usage:
  python scripts/jev_validate_motifs.py                # run all 45
  python scripts/jev_validate_motifs.py --limit 3      # first 3 only
  python scripts/jev_validate_motifs.py --dry-run      # print, no API
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# JEV client (shared with the abstraction script)
JEV_CLIENT_DIR = Path(__file__).parent.parent.parent / "aishield" / "scripts" / "typesafe"
sys.path.insert(0, str(JEV_CLIENT_DIR))
from jev_client import call as jev_call, load_key  # type: ignore  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
CONNECTION_TYPES_JSON = REPO_ROOT / "flybrain-connectome-mcp" / "functional_units" / "connection_types.json"


def load_motif_types():
    """Return only the motif_ref connection types (45 of them)."""
    with open(CONNECTION_TYPES_JSON, "r", encoding="utf-8") as f:
        doc = json.load(f)
    return [
        ct for ct in doc["connection_types"] if ct.get("motif_ref")
    ]


def build_query(ct):
    """Build JEV query state + questions for one motif_ref connection type."""
    state = (
        f"Connection type: {ct['name']}\n"
        f"Family: {ct.get('family', 'unknown')}\n"
        f"Motif reference: {ct.get('motif_ref', 'n/a')}\n"
        f"Description: {ct.get('description', '')}\n\n"
        f"This connection type maps to a named neuroanatomical motif "
        f"(a concrete synapse or circuit arrangement).  Rate the strength "
        f"of published evidence that this motif is documented and "
        f"characterised in the peer-reviewed neuroscience literature."
    )
    questions = {
        "literature_support": {
            "type": "noul",
            "instructions": (
                "Is this neuroanatomical motif documented and characterised "
                "in peer-reviewed neuroscience literature (Nature "
                "Neuroscience, Neuron, PNAS, J. Neuroscience, Current Biology)? "
                "Return the probability that at least two published papers "
                "describe this motif in vivo or in vitro."
            ),
        },
        "evidence_strength": {
            "type": "score",
            "instructions": (
                "Rate the strength of published evidence for this "
                "neuroanatomical motif on a 0-10 scale.  "
                "0 = speculative/no papers;  3 = 1-2 papers, preliminary;  "
                "5 = 3-5 papers, consensus forming;  "
                "7 = 5-10 papers, well-characterised in one species;  "
                "9 = 10+ papers, cross-species consensus;  "
                "10 = textbook entry."
            ),
            "criteria": [
                "No published evidence",
                "Speculative hypothesis only",
                "1-2 preliminary papers",
                "3-5 papers, consensus forming",
                "5-10 papers, well-characterised",
                "10+ papers, cross-species consensus",
                "Textbook entry",
            ],
        },
        "computational_validation": {
            "type": "noul",
            "instructions": (
                "Has this motif been computationally modelled and validated "
                "in neural-network simulations (J. Comput. Neurosci., "
                "Neural Comput. Appl., PLOS Comp. Biol., Neural Networks)?  "
                "Return the probability that at least one published "
                "computational model exists for this motif."
            ),
        },
    }
    return state, questions


def validate_one(ct, key, dry_run=False):
    state, questions = build_query(ct)
    if dry_run:
        return {
            "name": ct["name"],
            "family": ct.get("family"),
            "motif_ref": ct.get("motif_ref"),
            "dry_run": True,
            "state_preview": state[:120],
        }
    status, data, elapsed = jev_call(state, questions, key=key, timeout=90)
    result = {
        "name": ct["name"],
        "family": ct.get("family"),
        "motif_ref": ct.get("motif_ref"),
        "description": ct.get("description"),
        "jev_status": status,
        "jev_elapsed_s": round(elapsed, 3),
        "answers": {},
        "evidence_score": None,
        "evidence_label": None,
        "literature_p": None,
        "computational_p": None,
        "verdict": "unknown",
    }
    if status != 200 or not data:
        result["error"] = f"HTTP {status}"
        return result
    answers = data.get("answers", {})
    for qname in questions:
        result["answers"][qname] = answers.get(qname, {})
    lit = answers.get("literature_support", {})
    comp = answers.get("computational_validation", {})
    result["literature_p"] = lit.get("noul")
    result["computational_p"] = comp.get("noul")
    score_data = answers.get("evidence_strength", {})
    result["evidence_legend"] = score_data.get("legend")
    result["evidence_confidence"] = score_data.get("confidence")
    score_val = score_data.get("score")
    if score_val is not None:
        try:
            result["evidence_score"] = int(score_val)
        except (ValueError, TypeError):
            try:
                result["evidence_score"] = int(float(score_val))
            except (ValueError, TypeError):
                result["evidence_score"] = None
        if result["evidence_score"] is not None:
            if result["evidence_score"] >= 8:
                result["evidence_label"] = "textbook"
            elif result["evidence_score"] >= 5:
                result["evidence_label"] = "well_supported"
            elif result["evidence_score"] >= 2:
                result["evidence_label"] = "preliminary"
            else:
                result["evidence_label"] = "speculative"
    lit_p = result["literature_p"] or 0
    ev_score = result["evidence_score"] or 0
    if lit_p >= 0.7 and ev_score >= 5:
        result["verdict"] = "SUPPORTED"
    elif lit_p >= 0.4 or ev_score >= 3:
        result["verdict"] = "PARTIAL"
    else:
        result["verdict"] = "WEAK"
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Validate first N only")
    parser.add_argument("--dry-run", action="store_true", help="Print queries, no API calls")
    parser.add_argument("--out", default=None, help="Output JSON path")
    args = parser.parse_args()

    all_motifs = load_motif_types()
    ct_list = all_motifs if args.limit == 0 else all_motifs[:args.limit]
    print("=== JEV Motif-Ref Connection Type Validation ===")
    print(f"Total: {len(ct_list)} motif_ref types")
    print()

    key = None
    if not args.dry_run:
        key = load_key()
        print(f"JEV key loaded from {key[:8]}...")
        print()

    results = []
    if args.dry_run:
        for ct in ct_list:
            r = validate_one(ct, key=key, dry_run=True)
            results.append(r)
            print(f"  [DRY] {r['name']:40s} | motif={r['motif_ref'][:20]}")
    else:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(validate_one, ct, key): ct for ct in ct_list}
            for fut in as_completed(futures):
                r = fut.result()
                results.append(r)
                v = r.get("verdict", "unknown")
                sym = {"SUPPORTED": "OK", "PARTIAL": "~", "WEAK": "X", "unknown": "?"}.get(v, "?")
                lit_p = r.get("literature_p")
                comp_p = r.get("computational_p")
                ev_s = r.get("evidence_score", "?")
                lit_s = f"{lit_p:.2f}" if lit_p is not None else "  ? "
                comp_s = f"{comp_p:.2f}" if comp_p is not None else "  ? "
                print(
                    f"  [{sym}] {r['name']:40s} "
                    f"| fam={str(r.get('family','?')):12s} "
                    f"| lit={lit_s} comp={comp_s} score={ev_s} | {v}"
                )

    results.sort(key=lambda r: r["name"])

    print()
    print("=== Summary ===")
    for tier in ("SUPPORTED", "PARTIAL", "WEAK"):
        n = sum(1 for r in results if r.get("verdict") == tier)
        print(f"  {tier:10s}: {n}/{len(results)}")
    print()
    print("By family:")
    by_fam = {}
    for r in results:
        by_fam.setdefault(r.get("family", "unknown"), []).append(r)
    for fam, rs in sorted(by_fam.items()):
        sup = sum(1 for r in rs if r.get("verdict") == "SUPPORTED")
        par = sum(1 for r in rs if r.get("verdict") == "PARTIAL")
        weak = sum(1 for r in rs if r.get("verdict") == "WEAK")
        print(f"  {fam:12s}: SUPPORTED={sup} PARTIAL={par} WEAK={weak}  (total={len(rs)})")

    out_path = Path(args.out) if args.out else (
        Path(__file__).parent / "jev_results" / "motif_validation.json"
    )
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
