#!/usr/bin/env python3
"""v2.26.0 — connectome-aware re-scoring of low-scoring functional units.

WHY THIS EXISTS
---------------
The v2.24 pass scored every unit with the SAME rubric: "published literature
evidence, 0-10, where 2 = 1-2 papers". That rubric is correct for the
cross-species half of the library. It is systematically wrong for the
connectome-derived half.

A unit such as `leg_motor_pool_unit` is not a hypothesis awaiting literature;
it was traced directly out of MaleCNS v1.0 -- every number in its description
(1,205,967 synapses onto 403 real cells / 84 types) is a measured edge from a
published connectome reconstruction (Dorkenwald et al. 2024, 166,700 neurons,
124,177,617 synapses). Asking "how many papers describe this module" and
answering "1-2 papers => score 2" measures the wrong quantity.

Measured consequence (v2.26.0 diagnostic):
    embodied / connectome-derived : n=37  mean evidence_score 2.95
    cross-species                 : n=66  mean evidence_score 4.32
    15 of the 19 units scoring <=2 are connectome-derived.

So this pass splits the axis instead of faking citations. Connectome-derived
units get scored on BOTH axes:
    literature_evidence_score -- the stale v2.24 number, kept for comparability
    connectome_evidence_score -- NEW: strength of the extraction evidence
Only the axis that applies is used to set the shipped verdict, and `rescore`
is marked with `rescore_basis` so downstream consumers can tell which axis
produced the number.

Cross-species units are deliberately NOT re-scored here: for those, "how many
papers" IS the right question, and raising their score without new literature
would be fabrication.

Usage:
  python scripts/jev_rescore_units.py                 # re-score all connectome-derived units <= 2
  python scripts/jev_rescore_units.py --limit 5       # smoke test
  python scripts/jev_rescore_units.py --dry-run       # print queries, no API
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

JEV_CLIENT_DIR = Path(__file__).parent.parent.parent / "aishield" / "scripts" / "typesafe"
sys.path.insert(0, str(JEV_CLIENT_DIR))
from jev_client import call as jev_call, load_key  # noqa: E402

ROOT = Path(__file__).parent.parent
UNITS_FILE = ROOT / "flybrain-connectome-mcp" / "functional_units" / "functional_units.json"
VALIDATION_FILE = ROOT / "scripts" / "jev_results" / "unit_validation.json"
OUT_FILE = ROOT / "scripts" / "jev_results" / "unit_rescore.json"

CONNECTOME_REFERENCE = (
    "Dorkenwald et al. 2024, A connectome of the adult male Drosophila brain "
    "(MaleCNS v1.0; 166,700 neurons, 124,177,617 synapses)"
)

# v2.27.0: a second, independent reconstruction. The rescore now has to know
# which organism it is looking at, otherwise the prompt tells the model the
# module came out of a Drosophila reconstruction when it came out of a worm.
CEL_REFERENCE = (
    "Witvliet et al. 2020, connectome of the adult C. elegans hermaphrodite "
    "nervous system reconstructed by serial-section EM (bioRxiv "
    "10.1101/2020.04.30.066209; adult datasets 7 & 8)"
)


def _reference(unit: dict) -> tuple[str, str]:
    """(connectome reference, species phrase) for one unit."""
    if unit.get("provenance", {}).get("source_connectome"):
        return CEL_REFERENCE, "the C. elegans hermaphrodite nervous system"
    return CONNECTOME_REFERENCE, "the Drosophila male brain"


def load_units():
    with open(UNITS_FILE, encoding="utf-8") as f:
        return json.load(f)["units"]


def build_query(unit):
    """Connectome-aware questions for one unit."""
    name = unit["name"]
    description = unit.get("description", "")
    members = unit.get("members", [])
    member_roles = [m.get("role", "?") for m in members[:5]]
    member_str = ", ".join(member_roles) if member_roles else "various"
    reference, organism = _reference(unit)

    state = (
        f"Functional unit: {name}\n"
        f"Member roles: {member_str}\n"
        f"Measured description: {description[:400]}\n\n"
        f"This module is NOT a literature hypothesis. It was traced directly "
        f"out of a published electron-microscopy connectome reconstruction of "
        f"{organism} ({reference}). Every edge "
        f"cited in the description (synapse counts, cell-type groupings) is a "
        f"directly measured anatomical connection from that reconstruction, "
        f"not an inference from research papers.\n\n"
        f"Score the evidence on the axis that actually applies: the strength "
        f"of the connectome-extraction evidence, and separately the "
        f"independent literature evidence."
    )

    questions = {
        "connectome_evidence": {
            "type": "score",
            "instructions": (
                "Rate the strength of the connectome-extraction evidence for "
                "this circuit module, 0-10. Boundaries are explicit -- pick "
                "by the strongest statement that is TRUE below:\n"
                "  9-10 = individual neurons of the module were traced and "
                "identified as named cell types, AND synapse counts between "
                "its members were measured directly.\n"
                "  7-8  = neurons traced to named cell types, but synapse "
                "counts reported only at group level or approximate.\n"
                "  5-6  = module traced as a group, individual neurons only "
                "partially resolved.\n"
                "  3-4  = module NOT individually traced; wiring inferred "
                "from aggregate connection statistics only.\n"
                "  0-2  = module absent, or only its existence can be "
                "inferred.\n"
                "The description gives measured synapse counts and cell-type "
                "resolutions -- use them to place 9-10 vs 7-8 vs 5-6, do not "
                "default to the middle."
            ),
            "criteria": [
                "Absent from the connectome",
                "Existence only inferred",
                "Wiring inferred, not traced",
                "Traced coarsely",
                "Traced cleanly",
                "Traced with cell-type resolution",
                "Traced and independently verified",
            ],
        },
        "literature_evidence": {
            "type": "score",
            "instructions": (
                "Rate the strength of published peer-reviewed LITERATURE "
                "evidence specifically for this module as an identified "
                "circuit, 0-10 (same rubric as the v2.24 pass: 2 = 1 "
                "preliminary paper, 4 = 2-3 papers, 6 = 4-6 papers, "
                "8 = 7-10 papers well characterised, 10 = textbook). "
                "This number is recorded for comparability with the earlier "
                "pass even though the connectome axis governs the verdict."
            ),
            "criteria": [
                "No published evidence",
                "Speculative only",
                "1 preliminary paper",
                "2-3 papers",
                "4-6 papers",
                "7-10 papers",
                "Textbook entry",
            ],
        },
        "cell_type_resolved": {
            "type": "noul",
            "instructions": (
                "In this connectome reconstruction, were the neurons of this "
                "module resolved into named cell types with counted instances, "
                "rather than being only a functionally defined grouping? "
                "Return probability they are type-resolved."
            ),
        },
    }
    return state, questions


def rescore_one(unit, key, dry_run=False):
    state, questions = build_query(unit)
    if dry_run:
        return {"name": unit["name"], "dry_run": True}

    status, data, elapsed = jev_call(state, questions, key=key, timeout=120)
    reference, _organ = _reference(unit)
    out = {
        "name": unit["name"],
        "jev_status": status,
        "jev_elapsed_s": round(elapsed, 3),
        "jev_fallback": False,
        "connectome_evidence_score": 0,
        "connectome_evidence_label": "unvalidated_fallback",
        "literature_evidence_score": 0,
        "literature_evidence_label": "unvalidated_fallback",
        "cell_type_resolved_p": None,
        "connectome_reference": reference,
        "rescore_basis": "connectome_axis",
        "error": None,
    }
    if status != 200 or not data:
        # Fail-closed, same contract as jev_validate_units.py.
        out["jev_fallback"] = True
        out["error"] = f"HTTP {status}"
        return out

    answers = data.get("answers", {})
    for qn, q in questions.items():
        out.setdefault("answers", {})[qn] = answers.get(qn, {})

    def _score(qn, key_="score"):
        d = answers.get(qn, {})
        v = d.get(key_)
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return None

    c = _score("connectome_evidence")
    l = _score("literature_evidence")
    if c is None:
        out["jev_fallback"] = True
    out["connectome_evidence_score"] = c if c is not None else 0
    out["connectome_evidence_label"] = _label(c)
    out["literature_evidence_score"] = l if l is not None else 0
    out["literature_evidence_label"] = _label(l)
    out["cell_type_resolved_p"] = answers.get("cell_type_resolved", {}).get("noul")
    return out


def _label(score):
    if score is None:
        return "unvalidated_fallback"
    if score >= 8:
        return "traced_verified"
    if score >= 6:
        return "traced_cleanly"
    if score >= 4:
        return "traced_coarse"
    if score >= 2:
        return "wiring_inferred"
    return "absent_or_inferred"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--score-threshold", type=int, default=3,
                    help="re-score connectome-derived units at or below this "
                         "v2.24 evidence_score (default 3)")
    args = ap.parse_args()

    units = load_units()
    by_name = {u["name"]: u for u in units}
    with open(VALIDATION_FILE, encoding="utf-8") as f:
        validation = {r["name"]: r for r in json.load(f)}

    targets = []
    for r in validation.values():
        u = by_name.get(r["name"])
        if u is None:
            continue
        prov = u.get("provenance", {})
        # v2.27.0: C. elegans units are connectome-derived too. They arrive
        # without a v2.24 evidence_score (they are new), so they are taken
        # in unconditionally instead of by threshold.
        if prov.get("source_connectome"):
            targets.append(u)
            continue
        if not prov.get("embodied_in_malecns"):
            continue
        if (r.get("evidence_score") or 0) <= args.score_threshold:
            targets.append(u)
    if args.limit:
        targets = targets[: args.limit]

    print(f"=== v2.27.0 connectome-aware re-scoring ===")
    print(f"connectome-derived units scoring <= {args.score_threshold}: "
          f"{len(targets)}")
    print("(cross-species units are excluded by design: for those, the "
          "literature axis is the correct one and re-scoring without new "
          "papers would be fabrication)")
    print()

    key = None
    if not args.dry_run:
        key = load_key()
        print(f"JEV key loaded from {key[:8]}...\n")

    results = []
    if args.dry_run:
        for u in targets:
            r = rescore_one(u, key, dry_run=True)
            print(f"  [DRY] {r['name']}")
        return

    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(rescore_one, u, key): u for u in targets}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            flag = "!" if r.get("jev_fallback") else " "
            print(f"  [{flag}] {r['name']:44s} "
                  f"connectome={r['connectome_evidence_score']:>2} "
                  f"({r['connectome_evidence_label']:18s}) "
                  f"lit={r['literature_evidence_score']:>2} "
                  f"typed={r['cell_type_resolved_p']}")

    results.sort(key=lambda r: r["name"])
    fb = [r for r in results if r.get("jev_fallback")]
    print(f"\nfallback: {len(fb)}/{len(results)}")
    if args.dry_run or args.limit:
        return

    OUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Results saved: {OUT_FILE}")


if __name__ == "__main__":
    main()
