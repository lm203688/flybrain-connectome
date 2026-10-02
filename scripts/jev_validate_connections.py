#!/usr/bin/env python3
"""JEV-powered connection type validation for flybrain-connectome.

Uses TypeSafe Jev (System One decision model) to assess literature evidence
strength for the 21 abstraction-level connection types that lack a motif_ref.

For each connection type, queries three dimensions:
  1. literature_support (noul)  — P(documented in peer-reviewed neuroscience)
  2. evidence_strength (score)  — 0-10 rubric of published evidence
  3. computational_validation (noul) — P(computationally modeled & tested)

Cost: ~$0.000024 per call (61 calls ≈ $0.0015 total).
Output: scripts/jev_results/connection_validation.json + stdout summary.

Usage:
  python scripts/jev_validate_connections.py              # run all 21
  python scripts/jev_validate_connections.py --limit 5    # first 5 only
  python scripts/jev_validate_connections.py --dry-run    # print queries, no API
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# JEV client path
JEV_CLIENT_DIR = Path(__file__).parent.parent.parent / "aishield" / "scripts" / "typesafe"
sys.path.insert(0, str(JEV_CLIENT_DIR))
from jev_client import call as jev_call, load_key

# Connection types without motif_ref (system-level abstractions)
ABSTRACTION_TYPES = [
    {
        "name": "autapse_recurrent",
        "family": "micro",
        "description": "A population connects to itself with gain < 1; local persistence with decay.",
    },
    {
        "name": "winner_take_all",
        "family": "circuit",
        "description": "Global inhibitory pool lets the strongest unit suppress the rest; competitive selection.",
    },
    {
        "name": "loop_relay_chain",
        "family": "circuit",
        "description": "Strictly ordered series of relays; each stage passes a transformed copy to the next.",
    },
    {
        "name": "state_gating_modulation",
        "family": "modulatory",
        "description": "A global state variable (arousal, phase) multiplies whole-pathway throughput.",
    },
    {
        "name": "gliotransmission_calcium_wave",
        "family": "electrical",
        "description": "Calcium wave propagates through the astrocytic syncytium, carrying a slow modulatory signal.",
    },
    {
        "name": "homeostatic_scaling",
        "family": "plasticity",
        "description": "Slow multiplicative rescaling of all weights to hold a firing-rate set-point constant.",
    },
    {
        "name": "divergent_fanout",
        "family": "macro",
        "description": "One source drives many independent downstream populations; broadcast without convergence.",
    },
    {
        "name": "convergent_fanin",
        "family": "macro",
        "description": "Many sources converge onto one target; the target sees an integrated summary.",
    },
    {
        "name": "corollary_discharge",
        "family": "macro",
        "description": "A copy of a motor command is routed to a sensory/predictor unit alongside the sensory input.",
    },
    {
        "name": "global_broadcast",
        "family": "macro",
        "description": "A command reaches every unit in the organism; used for reset, halt, or mode-switch.",
    },
    {
        "name": "sparse_expansion_projection",
        "family": "macro",
        "description": "A few input channels fan out onto a very large population of which only a sparse subset fires.",
    },
    {
        "name": "neural_chain_sequence",
        "family": "circuit",
        "description": "A synfire-like chain in which each element activates the next after a fixed delay.",
    },
    {
        "name": "efference_copy_cancellation",
        "family": "circuit",
        "description": "A copy of the motor command is sent ahead to sensory areas and subtracted from incoming signals.",
    },
    {
        "name": "mixed_electrical_chemical_synapse",
        "family": "electrical",
        "description": "A contact carrying both a gap-junction conductance and a chemical component.",
    },
    {
        "name": "modulatory_gated_plasticity",
        "family": "plasticity",
        "description": "A synapse whose weight changes only when a third, modulatory neuron is also active.",
    },
    {
        "name": "command_neuron_recruitment",
        "family": "macro",
        "description": "One identified command neuron, once past threshold, recruits an entire downstream population.",
    },
    {
        "name": "half_center_oscillation",
        "family": "circuit",
        "description": "Two reciprocally inhibitory pools plus adaptation: whichever is released from inhibition fires.",
    },
    {
        "name": "plateau_potential_bistability",
        "family": "electrical",
        "description": "A brief input pushes the cell onto a sustained depolarised plateau that persists until inhibited.",
    },
    {
        "name": "coincidence_detection",
        "family": "plasticity",
        "description": "The synapse only changes when two inputs arrive together; a single click does nothing.",
    },
    {
        "name": "state_switch_bistable",
        "family": "macro",
        "description": "Two mutually inhibitory populations with a slow external bias: the circuit flips state.",
    },
    {
        "name": "grid_phase_precession",
        "family": "circuit",
        "description": "A theta-rhythm reference makes a spatial cell's firing phase advance linearly with position.",
    },
]

def build_query(ct):
    """Build JEV query state and questions for one connection type."""
    state = (
        f"Connection type: {ct['name']}\n"
        f"Family: {ct['family']}\n"
        f"Description: {ct['description']}\n\n"
        f"This is a system-level neural circuit pattern (not a single synapse type). "
        f"It lacks a motif reference because it describes an abstract circuit architecture "
        f"rather than a specific synapse anatomy."
    )
    questions = {
        "literature_support": {
            "type": "noul",
            "instructions": (
                "Is this neural circuit pattern documented and characterized in "
                "peer-reviewed neuroscience literature? Consider published papers "
                "in journals like Nature Neuroscience, Neuron, PNAS, J. Neuroscience, "
                "Current Biology. Return probability that at least 2 published papers "
                "describe this pattern in vivo or in vitro."
            ),
        },
        "evidence_strength": {
            "type": "score",
            "instructions": (
                "Rate the strength of published evidence for this neural circuit pattern "
                "on a 0-10 scale. 0 = speculative/no papers; 3 = 1-2 papers, preliminary; "
                "5 = 3-5 papers, consensus forming; 7 = 5-10 papers, well-characterized "
                "in one species; 9 = 10+ papers, cross-species consensus; 10 = textbook entry."
            ),
            "criteria": [
                "No published evidence",
                "Speculative hypothesis only",
                "1-2 preliminary papers",
                "3-5 papers, consensus forming",
                "5-10 papers, well-characterized",
                "10+ papers, cross-species consensus",
                "Textbook entry",
            ],
        },
        "computational_validation": {
            "type": "noul",
            "instructions": (
                "Has this circuit pattern been computationally modeled and validated "
                "in neural network simulations? Consider published computational models "
                "(e.g., in J. Comput. Neurosci., Neural Comput. Appl., PLOS Comp. Biol.). "
                "Return probability that at least 1 published computational model exists."
            ),
        },
    }
    return state, questions


def validate_one(ct, key, dry_run=False):
    """Validate one connection type via JEV. Returns result dict."""
    state, questions = build_query(ct)
    if dry_run:
        return {
            "name": ct["name"],
            "family": ct["family"],
            "dry_run": True,
            "state_preview": state[:120],
        }
    status, data, elapsed = jev_call(state, questions, key=key, timeout=90)
    result = {
        "name": ct["name"],
        "family": ct["family"],
        "description": ct["description"],
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
        qdata = answers.get(qname, {})
        result["answers"][qname] = qdata
    # Parse noul answers
    lit = answers.get("literature_support", {})
    comp = answers.get("computational_validation", {})
    result["literature_p"] = lit.get("noul")
    result["computational_p"] = comp.get("noul")
    # Parse score answer (score type returns {"score": int, "confidence": float, "legend": [...]})
    score_data = answers.get("evidence_strength", {})
    score_val = score_data.get("score")
    # Also capture legend if available
    result["evidence_legend"] = score_data.get("legend")
    result["evidence_confidence"] = score_data.get("confidence")
    if score_val is not None:
        try:
            result["evidence_score"] = int(score_val)
        except (ValueError, TypeError):
            # score might be a float or string representation
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
    # Overall verdict
    lit_p = result["literature_p"] or 0
    comp_p = result["computational_p"] or 0
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

    ct_list = ABSTRACTION_TYPES if args.limit == 0 else ABSTRACTION_TYPES[:args.limit]
    print(f"=== JEV Connection Type Validation ===")
    print(f"Total: {len(ct_list)} abstraction types")
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
            print(f"  [DRY] {r['name']:40s} | {r['state_preview'][:60]}")
    else:
        # Concurrent validation (JEV is stateless, safe to parallelize)
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(validate_one, ct, key): ct for ct in ct_list}
            for fut in as_completed(futures):
                r = fut.result()
                results.append(r)
                verdict_sym = {"SUPPORTED": "✓", "PARTIAL": "~", "WEAK": "✗", "unknown": "?"}
                v = r.get("verdict", "unknown")
                sym = verdict_sym.get(v, "?")
                lit_p = r.get("literature_p", 0)
                comp_p = r.get("computational_p", 0)
                ev_s = r.get("evidence_score", "?")
                lit_s = f"{lit_p:.2f}" if lit_p is not None else "  ? "
                comp_s = f"{comp_p:.2f}" if comp_p is not None else "  ? "
                print(f"  [{sym}] {r['name']:40s} | lit={lit_s} comp={comp_s} score={ev_s} | {v}")

    # Sort results by name for deterministic output
    results.sort(key=lambda r: r["name"])

    # Summary
    print()
    print("=== Summary ===")
    supported = sum(1 for r in results if r.get("verdict") == "SUPPORTED")
    partial = sum(1 for r in results if r.get("verdict") == "PARTIAL")
    weak = sum(1 for r in results if r.get("verdict") == "WEAK")
    print(f"SUPPORTED: {supported}/{len(results)}")
    print(f"PARTIAL:   {partial}/{len(results)}")
    print(f"WEAK:      {weak}/{len(results)}")

    # Save results
    if args.out:
        out_path = Path(args.out)
    else:
        out_dir = Path(__file__).parent / "jev_results"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "connection_validation.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
