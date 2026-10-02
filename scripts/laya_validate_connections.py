#!/usr/bin/env python3
"""Laya-powered connection type validation (free local alternative to JEV).

Uses Laya 421M decision model to assess literature evidence strength for
the 21 abstraction-level connection types.

Prerequisites:
  - Laya HTTP server running on port 8188 (default)
  - `laya_mcp_server.py` or `laya_infer.py serve --port 8188`

Usage:
  python laya_validate_connections.py               # validate all 21
  python laya_validate_connections.py --limit 5     # first 5 only
  python laya_validate_connections.py --dry-run     # print queries, no API
  python laya_validate_connections.py --port 8188   # custom port
"""
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Reuse the same 21 abstraction types from JEV validation
JEV_RESULTS = Path(__file__).parent / "jev_results" / "connection_validation.json"
LAYA_PORT = 8188
LAYA_BASE = f"http://127.0.0.1:{LAYA_PORT}/decide"

def load_types():
    """Load the 21 abstraction connection types from JEV results."""
    if not JEV_RESULTS.exists():
        print(f"[ERROR] JEV results not found: {JEV_RESULTS}")
        print("Run jev_validate_connections.py first.")
        sys.exit(1)
    with open(JEV_RESULTS, "r", encoding="utf-8") as f:
        return json.load(f)


def query_laya(text, questions, checkpoint="en", port=LAYA_PORT, timeout=30):
    """Send a decision query to Laya HTTP server."""
    payload = {
        "text": text,
        "checkpoint": checkpoint,
        "questions": questions,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/decide",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if not result.get("ok"):
                return None, result
            item = result["items"][0]
            answers = item["result"]["answers"]
            return answers, item["result"]
    except Exception as e:
        return None, {"error": str(e)}


def validate_one(ct, port=LAYA_PORT, dry_run=False):
    """Validate one connection type via Laya."""
    text = (
        f"Neural circuit pattern: {ct['name']} ({ct['family']}). "
        f"Description: {ct['description']}. "
        f"Family: {ct['family']}. "
        f"JEV verdict: {ct.get('verdict', 'unknown')}. "
        f"JEV evidence_score: {ct.get('evidence_score', 'unknown')}. "
        f"Is this pattern documented in peer-reviewed neuroscience literature?"
    )
    questions = {
        "literature_supported": {
            "type": "noul",
            "instructions": (
                "Is this neural circuit pattern documented and characterized "
                "in peer-reviewed neuroscience literature? Consider published "
                "papers in Nature Neuroscience, Neuron, PNAS, J. Neuroscience. "
                "Return probability that at least 2 published papers describe "
                "this pattern."
            ),
        },
        "evidence_strength": {
            "type": "score",
            "instructions": (
                "Rate the strength of published evidence for this pattern on "
                "a 0-10 scale. 0=speculative, 3=preliminary, 5=consensus forming, "
                "7=well-characterized, 9=cross-species consensus, 10=textbook."
            ),
            "criteria": [
                "No evidence", "Speculative", "Preliminary",
                "Consensus forming", "Well-characterized",
                "Cross-species", "Textbook",
            ],
        },
    }

    if dry_run:
        return {
            "name": ct["name"],
            "family": ct["family"],
            "dry_run": True,
            "text_preview": text[:100],
        }

    t0 = time.time()
    answers, meta = query_laya(text, questions, port=port)
    elapsed = time.time() - t0

    result = {
        "name": ct["name"],
        "family": ct["family"],
        "description": ct.get("description", ""),
        "laya_status": "ok" if answers else "error",
        "laya_elapsed_s": round(elapsed, 3),
        "answers": answers or {},
        "literature_p": None,
        "evidence_score": None,
        "evidence_label": None,
        "verdict": "unknown",
        "error": None if answers else str(meta),
    }

    if answers:
        lit = answers.get("literature_supported", {})
        result["literature_p"] = lit.get("p")

        score_data = answers.get("evidence_strength", {})
        # Laya score might return as int or dict
        if isinstance(score_data, dict):
            result["evidence_score"] = score_data.get("score") or score_data.get("p")
        else:
            result["evidence_score"] = score_data

        ev = result["evidence_score"]
        if ev is not None:
            try:
                ev_float = float(ev)
                if ev_float >= 8:
                    result["evidence_label"] = "textbook"
                elif ev_float >= 5:
                    result["evidence_label"] = "well_supported"
                elif ev_float >= 2:
                    result["evidence_label"] = "preliminary"
                else:
                    result["evidence_label"] = "speculative"
            except (ValueError, TypeError):
                pass

        # Cross-reference with JEV
        jev_verdict = ct.get("verdict", "unknown")
        jev_score = ct.get("evidence_score")
        result["jev_verdict"] = jev_verdict
        result["jev_evidence_score"] = jev_score

        # Agreement check
        lit_p = result["literature_p"] or 0
        if jev_verdict == "SUPPORTED" and lit_p >= 0.5:
            result["agreement"] = "agree"
        elif jev_verdict == "WEAK" and lit_p < 0.3:
            result["agreement"] = "agree"
        elif jev_verdict in ("PARTIAL", "SUPPORTED") and lit_p >= 0.3:
            result["agreement"] = "partial_agree"
        else:
            result["agreement"] = "disagree"

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--port", type=int, default=LAYA_PORT)
    parser.add_argument("--out", default=None)
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()

    types = load_types()
    ct_list = types if args.limit == 0 else types[:args.limit]

    print(f"=== Laya Connection Type Validation ===")
    print(f"Total: {len(ct_list)} abstraction types")
    print(f"Port: {args.port}")
    print()

    results = []
    if args.dry_run:
        for ct in ct_list:
            r = validate_one(ct, dry_run=True)
            results.append(r)
            print(f"  [DRY] {r['name']:40s} | {r['text_preview'][:50]}")
    else:
        # Sequential to avoid overwhelming CPU-only Laya
        for ct in ct_list:
            r = validate_one(ct, port=args.port)
            results.append(r)
            lit_p = r.get("literature_p")
            ev_s = r.get("evidence_score")
            agree = r.get("agreement", "?")
            agree_sym = {"agree": "✓", "partial_agree": "~", "disagree": "✗"}.get(agree, "?")
            print(f"  [{agree_sym}] {r['name']:40s} | p={lit_p:.2f} score={ev_s} "
                  f"| JEV={r.get('jev_verdict','?')} {agree} ({r.get('laya_elapsed_s',0):.1f}s)")

    # Summary
    print()
    print("=== Summary ===")
    n_agree = sum(1 for r in results if r.get("agreement") == "agree")
    n_partial = sum(1 for r in results if r.get("agreement") == "partial_agree")
    n_disagree = sum(1 for r in results if r.get("agreement") == "disagree")
    n_total = len(results)
    print(f"Agree with JEV:      {n_agree}/{n_total}")
    print(f"Partial agree:       {n_partial}/{n_total}")
    print(f"Disagree:            {n_disagree}/{n_total}")

    # Save
    if args.out:
        out_path = Path(args.out)
    else:
        out_dir = Path(__file__).parent / "laya_results"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "connection_validation.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
