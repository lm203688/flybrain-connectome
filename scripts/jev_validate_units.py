#!/usr/bin/env python3
"""JEV-powered functional unit validation for flybrain-connectome.

Uses TypeSafe Jev (System One decision model) to assess literature evidence
strength for all 103 functional units in the library.

For each functional unit, queries three dimensions:
  1. literature_support (noul)  — P(documented in peer-reviewed neuroscience)
  2. evidence_strength (score)  — 0-10 rubric of published evidence
  3. model_validation (noul)    — P(computationally modeled & tested)

Cost: ~$0.000024 per call (103 calls × 3 questions ≈ $0.0075 total).
Output: scripts/jev_results/unit_validation.json + stdout summary.

Usage:
  python scripts/jev_validate_units.py                  # run all 103
  python scripts/jev_validate_units.py --limit 10       # first 10 only
  python scripts/jev_validate_units.py --dry-run        # print queries, no API
  python scripts/jev_validate_units.py --skip-embodied  # skip MaleCNS-anchored
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# JEV client path
JEV_CLIENT_DIR = Path(__file__).parent.parent.parent / "aishield" / "scripts" / "typesafe"
sys.path.insert(0, str(JEV_CLIENT_DIR))
from jev_client import call as jev_call, load_key

# Functional units JSON
UNITS_FILE = Path(__file__).parent.parent / "flybrain-connectome-mcp" / "functional_units" / "functional_units.json"


def load_units(path=UNITS_FILE):
    """Load functional units from JSON."""
    with open(path) as f:
        data = json.load(f)
    return data["units"]


def build_query(unit):
    """Build JEV query state and questions for one functional unit."""
    name = unit["name"]
    system = unit.get("system", "unknown")
    species = unit.get("species_source", ["unknown"])
    if isinstance(species, list):
        species_str = ", ".join(species[:5])
    else:
        species_str = str(species)
    bio_ref = unit.get("biological_reference", "")
    description = unit.get("description", "")

    # Build a concise unit description for the model
    members = unit.get("members", [])
    member_roles = [m.get("role", "?") for m in members[:5]]
    member_str = ", ".join(member_roles) if member_roles else "various"

    state = (
        f"Functional unit: {name}\n"
        f"System: {system}\n"
        f"Species source: {species_str}\n"
        f"Member roles: {member_str}\n"
        f"Description: {description[:200]}\n"
        f"Biological reference: {bio_ref[:200]}\n\n"
        f"This is a curated functional neural circuit module (not a single neuron type). "
        f"It groups specific neuron populations into a functional unit with defined "
        f"internal wiring and external interfaces (ports). "
        f"The question is whether this specific circuit module is documented and "
        f"validated in peer-reviewed neuroscience literature."
    )

    questions = {
        "literature_support": {
            "type": "noul",
            "instructions": (
                "Is this specific neural circuit module documented and characterized "
                "in peer-reviewed neuroscience literature? Consider published papers "
                "in journals like Nature Neuroscience, Neuron, PNAS, J. Neuroscience, "
                "Current Biology, Cell. Return probability that at least 2 published "
                "papers describe this functional module in vivo or in vitro."
            ),
        },
        "evidence_strength": {
            "type": "score",
            "instructions": (
                "Rate the strength of published evidence for this functional neural "
                "circuit module on a 0-10 scale. 0 = speculative/no papers; "
                "2 = 1 preliminary paper; 4 = 2-3 papers, preliminary; "
                "6 = 4-6 papers, consensus forming; 8 = 7-10 papers, "
                "well-characterized in one species; 10 = textbook entry, "
                "cross-species consensus."
            ),
            "criteria": [
                "No published evidence",
                "Speculative hypothesis only",
                "1 preliminary paper",
                "2-3 papers, preliminary",
                "4-6 papers, consensus forming",
                "7-10 papers, well-characterized",
                "Textbook entry, cross-species",
            ],
        },
        "model_validation": {
            "type": "noul",
            "instructions": (
                "Has this circuit module been computationally modeled and validated "
                "in neural network simulations? Consider published computational models "
                "(e.g., in J. Comput. Neurosci., Neural Comput. Appl., PLOS Comp. Biol.). "
                "Return probability that at least 1 published computational model exists."
            ),
        },
    }
    return state, questions


def validate_one(unit, key, dry_run=False):
    """Validate one functional unit via JEV. Returns result dict."""
    state, questions = build_query(unit)
    if dry_run:
        return {
            "name": unit["name"],
            "system": unit.get("system"),
            "dry_run": True,
            "state_preview": state[:120],
        }

    status, data, elapsed = jev_call(state, questions, key=key, timeout=90)
    result = {
        "name": unit["name"],
        "system": unit.get("system"),
        "species_source": unit.get("species_source"),
        "embodied": unit.get("provenance", {}).get("embodied_in_malecns", False),
        "evidence_weight_before": unit.get("provenance", {}).get("evidence_weight"),
        "jev_status": status,
        "jev_elapsed_s": round(elapsed, 3),
        "answers": {},
        "evidence_score": None,
        "evidence_label": None,
        "literature_p": None,
        "model_p": None,
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
    mod = answers.get("model_validation", {})
    result["literature_p"] = lit.get("noul")
    result["model_p"] = mod.get("noul")

    # Parse score answer
    score_data = answers.get("evidence_strength", {})
    score_val = score_data.get("score")
    result["evidence_legend"] = score_data.get("legend")
    result["evidence_confidence"] = score_data.get("confidence")
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
            elif result["evidence_score"] >= 6:
                result["evidence_label"] = "well_supported"
            elif result["evidence_score"] >= 4:
                result["evidence_label"] = "preliminary"
            else:
                result["evidence_label"] = "speculative"

    # Overall verdict
    lit_p = result["literature_p"] or 0
    mod_p = result["model_p"] or 0
    ev_score = result["evidence_score"] or 0
    if lit_p >= 0.7 and ev_score >= 6:
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
    parser.add_argument("--skip-embodied", action="store_true",
                        help="Skip units already embodied in MaleCNS")
    parser.add_argument("--out", default=None, help="Output JSON path")
    args = parser.parse_args()

    units = load_units()
    if args.skip_embodied:
        units = [u for u in units if not u.get("provenance", {}).get("embodied_in_malecns")]
    if args.limit > 0:
        units = units[:args.limit]

    print(f"=== JEV Functional Unit Validation ===")
    print(f"Total: {len(units)} units")
    embodied_count = sum(1 for u in units if u.get("provenance", {}).get("embodied_in_malecns"))
    print(f"Embodied in MaleCNS: {embodied_count}")
    print(f"Cross-species: {len(units) - embodied_count}")
    print()

    key = None
    if not args.dry_run:
        key = load_key()
        print(f"JEV key loaded from {key[:8]}...")
        print()

    results = []
    if args.dry_run:
        for u in units:
            r = validate_one(u, key=key, dry_run=True)
            results.append(r)
            print(f"  [DRY] {r['name']:45s} | {r['state_preview'][:50]}")
    else:
        # Concurrent validation (JEV is stateless, safe to parallelize)
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(validate_one, u, key): u for u in units}
            for fut in as_completed(futures):
                r = fut.result()
                results.append(r)
                verdict_sym = {"SUPPORTED": "✓", "PARTIAL": "~", "WEAK": "✗", "unknown": "?"}
                v = r.get("verdict", "unknown")
                sym = verdict_sym.get(v, "?")
                lit_p = r.get("literature_p", 0)
                mod_p = r.get("model_p", 0)
                ev_s = r.get("evidence_score", "?")
                lit_s = f"{lit_p:.2f}" if lit_p is not None else "  ? "
                mod_s = f"{mod_p:.2f}" if mod_p is not None else "  ? "
                emb = "E" if r.get("embodied") else " "
                print(f"  [{sym}]{emb} {r['name']:42s} | lit={lit_s} mod={mod_s} score={ev_s} | {v}")

    # Sort results by name for deterministic output
    results.sort(key=lambda r: r["name"])

    # Summary
    print()
    print("=== Summary ===")
    supported = sum(1 for r in results if r.get("verdict") == "SUPPORTED")
    partial = sum(1 for r in results if r.get("verdict") == "PARTIAL")
    weak = sum(1 for r in results if r.get("verdict") == "WEAK")
    unknown = sum(1 for r in results if r.get("verdict") == "unknown")
    print(f"SUPPORTED: {supported}/{len(results)}")
    print(f"PARTIAL:   {partial}/{len(results)}")
    print(f"WEAK:      {weak}/{len(results)}")
    if unknown:
        print(f"UNKNOWN:   {unknown}/{len(results)}")
    # By embodiment
    embodied_supported = sum(1 for r in results if r.get("embodied") and r.get("verdict") == "SUPPORTED")
    embodied_total = sum(1 for r in results if r.get("embodied"))
    print(f"\nEmbodied: {embodied_supported}/{embodied_total} SUPPORTED")
    cross_supported = sum(1 for r in results if not r.get("embodied") and r.get("verdict") == "SUPPORTED")
    cross_total = sum(1 for r in results if not r.get("embodied"))
    print(f"Cross-species: {cross_supported}/{cross_total} SUPPORTED")

    # Save results
    if args.out:
        out_path = Path(args.out)
    else:
        out_dir = Path(__file__).parent / "jev_results"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "unit_validation.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
