#!/usr/bin/env python3
"""s3_discipline_effectiveness.py — S3: quantified discipline effectiveness.

For each historical PR/claim, inject a class of preregistration violation
and check whether the corresponding gate catches it. Produces the S3
statistical strengthening: the fraction of injected violations that each
gate catches ("gate catch-rate").

Each protocol is paired with the gate that owns it:
  - PR1   -> check_preregistered_claims.py   (manifest ↔ execution integrity)
  - PR2b  -> check_metric_substitution.py    (metric-family independence)
  - PR3_v2/C3 -> check_c1_c3.py              (label + C3 AUC)
  - PR_S1 -> no dedicated gate yet (this is a new preregistration);
             reported honestly as "gate coverage gap"

Writes:
  _s3_discipline_effectiveness/results.json
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "_s3_discipline_effectiveness"


# ---------- violation injection battery ----------

def _inject_pr1_violation(json_path: Path, mutation: str, rng: random.Random) -> None:
    d = json.loads(json_path.read_text(encoding="utf-8"))
    pr = d.get("preregistered", {}).get("PR1", {})
    if not pr:
        return
    if mutation == "threshold_drift":
        pr["threshold"] = rng.choice([0.1, 0.2, 0.3, 0.4, 0.5])
    elif mutation == "feature_set_shrink":
        if "features" in pr and len(pr["features"]) > 1:
            pr["features"].pop(rng.randrange(len(pr["features"])))
    elif mutation == "slice_overlap":
        pr["train_idx"] = "0:80"
        pr["held_out_idx"] = "60:100"
    elif mutation == "seed_mismatch":
        # Gate checks params.seed vs preregistered seed if both exist; inject
        # a value that will diverge from execution JSON.
        pr["seed"] = rng.randrange(0, 10000)
    elif mutation == "n_permutations_low":
        pr["permutations"] = rng.randrange(1, 50)
    d["preregistered"]["PR1"] = pr
    json_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _inject_pr2b_violation(json_path: Path, mutation: str, rng: random.Random) -> None:
    d = json.loads(json_path.read_text(encoding="utf-8"))
    pr = d.get("preregistered", {}).get("PR2b", {})
    if not pr:
        return
    if mutation == "remove_reject_rule":
        # PR2b records its reject rule INSIDE success_criteria (there is no
        # top-level `reject_rules` block). Silently dropping one of the
        # quantitative reject thresholds is what "remove_reject_rule"
        # should mean. Prior version popped a non-existent top-level key
        # and was therefore a no-op — W2 hardening exposed this.
        sc = pr.get("success_criteria")
        if isinstance(sc, dict):
            sc.pop("reject_if_coupling_corr_abs_min", None)
            sc.pop("reject_if_artifact_rate_min", None)
            pr["success_criteria"] = sc
    elif mutation == "lower_reject_threshold":
        pr["success_criteria"] = {
            "reject_if_coupling_corr_abs_min": 0.01,
            "reject_if_artifact_rate_min": 0.01,
            "conjunctive": False,
            "declared_direction_for_recovery_auc": "increase",
        }
    elif mutation == "wrong_direction":
        pr["success_criteria"] = {
            **pr.get("success_criteria", {}),
            "declared_direction_for_recovery_auc": "increase",
        }
    d["preregistered"]["PR2b"] = pr
    json_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _inject_pr3v2_violation(json_path: Path, mutation: str, rng: random.Random) -> None:
    d = json.loads(json_path.read_text(encoding="utf-8"))
    pr = d.get("preregistered", {}).get("PR3_v2", {})
    if not pr:
        return
    if mutation == "absolute_threshold":
        pr["label_definition"] = "drop_magnitude>0.25"
    elif mutation == "remove_change_from_v1":
        pr.pop("change_from_v1", None)
    elif mutation == "no_real_family":
        if "families" in pr:
            pr["families"] = [f for f in pr["families"] if f != "malecns_subgraph"]
    d["preregistered"]["PR3_v2"] = pr
    json_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _inject_c3_violation(json_path: Path, mutation: str, rng: random.Random) -> None:
    d = json.loads(json_path.read_text(encoding="utf-8"))
    pr = d.get("preregistered", {}).get("PR3_v2", {})
    if not pr:
        return
    v = pr.get("verification", {})
    if mutation == "lower_auc":
        for fam in list(v.get("auc_matrix_summary", {}).keys()):
            for cell in v.get("auc_matrix_summary", {}).get(fam, {}):
                v["auc_matrix_summary"][fam][cell] = round(
                    max(0.0, v["auc_matrix_summary"][fam][cell] - 0.2), 4
                )
    elif mutation == "remove_real_family_passing":
        v["real_family_passing"] = False
        v["n_families_passing"] = 2
    elif mutation == "flip_verdict":
        v["verdict"] = "PASS" if v.get("verdict") == "FAIL" else "FAIL"
    pr["verification"] = v
    d["preregistered"]["PR3_v2"] = pr
    json_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _inject_pr_s1_violation(json_path: Path, mutation: str, rng: random.Random) -> None:
    """Inject a PR_S1 mutation into research_claims.preregistered.PR_S1.

    PR_S1 lives canonically in vault/S1.commit.json; the gate reads that
    as the source of truth. research_claims.preregistered.PR_S1 acts as
    an *override* the gate cross-checks against the vault. Silently
    planting an override with a drifted threshold (raise_auc_min), a
    flipped conjunctive (remove_conjunctive), or a dropped kappa floor
    (lower_kappa_min) must turn Gate 62 red.

    Prior version early-returned when PR_S1 was absent from claims,
    so the injection never actually wrote anything — S3 caught 0/9.
    Fixed in v2.98.1 to plant the override unconditionally.
    """
    d = json.loads(json_path.read_text(encoding="utf-8"))
    prereg = d.setdefault("preregistered", {})
    pr_s1 = prereg.get("PR_S1") or {}
    sc = pr_s1.setdefault("success_criteria", {})
    if mutation == "raise_auc_min":
        # 0.9 is the S3-injected value. Gate 62 upper-bounds the AUC
        # floor strictly below 0.90 — a genuine preregistration would
        # not commit to a 0.90 floor (PR_S1 actually commits to 0.65).
        sc["c3_auc_min_per_external_family"] = 0.9
    elif mutation == "remove_conjunctive":
        sc["conjunctive"] = False
    elif mutation == "lower_kappa_min":
        sc["c3_kappa_min"] = 0.01
    prereg["PR_S1"] = pr_s1
    json_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


MUTATION_SETS = {
    "PR1": ["threshold_drift", "feature_set_shrink", "slice_overlap",
            "seed_mismatch", "n_permutations_low"],
    "PR2b": ["remove_reject_rule", "lower_reject_threshold", "wrong_direction"],
    "PR3_v2": ["absolute_threshold", "remove_change_from_v1", "no_real_family"],
    "C3": ["lower_auc", "remove_real_family_passing", "flip_verdict"],
    "PR_S1": ["raise_auc_min", "remove_conjunctive", "lower_kappa_min"],
}

INJECTORS = {
    "PR1": _inject_pr1_violation,
    "PR2b": _inject_pr2b_violation,
    "PR3_v2": _inject_pr3v2_violation,
    "C3": _inject_c3_violation,
    "PR_S1": _inject_pr_s1_violation,
}

# Which gate script checks each protocol family, and how to invoke it with
# an injected claims file.  `gate_script` = None means "no dedicated gate".
GATE_INVOKER = {
    "PR1": ("check_preregistered_claims.py", ["--claims"]),
    "PR2b": ("check_metric_substitution.py", ["--claims"]),
    "PR3_v2": ("check_c1_c3.py", []),           # reads ROOT/research_claims.json directly
    "C3": ("check_c1_c3.py", []),
    # W7 fix (v2.98.1): PR_S1 now has a dedicated gate. The gate reads
    # vault/S1.commit.json as the source of truth; the injected PR_S1
    # block in research_claims.json is treated as an override and
    # compared against the vault. A drift triggers a fail.
    "PR_S1": ("check_pr_s1.py", []),
}


def _run_gate(protocol: str, claims_path: Path) -> tuple[bool, str]:
    """Run the gate that owns `protocol` against the injected claims file.

    Returns (passed, diagnostic).
    For check_c1_c3.py, we temporarily move the injected file into place,
    run the gate, and restore the original.
    """
    script_name, extra = GATE_INVOKER.get(protocol, (None, []))
    if script_name is None:
        return True, "no gate"  # counted as missed, not caught
    gate_script = SCRIPTS / script_name
    claims_target = ROOT / "research_claims.json"

    if "--claims" in extra:
        cmd = [sys.executable, str(gate_script), *extra, str(claims_path)]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=45, cwd=str(ROOT)
            )
            return (result.returncode == 0,
                    (result.stderr or result.stdout)[-300:])
        except Exception as e:
            return (True, f"gate invocation error: {e}")
    else:
        # Script reads ROOT/research_claims.json; swap in injected file.
        backup = claims_target.read_bytes()
        claims_target.write_bytes(claims_path.read_bytes())
        try:
            result = subprocess.run(
                [sys.executable, str(gate_script)],
                capture_output=True, text=True, timeout=60, cwd=str(ROOT)
            )
            return (result.returncode == 0,
                    (result.stderr or result.stdout)[-300:])
        except Exception as e:
            return (True, f"gate invocation error: {e}")
        finally:
            claims_target.write_bytes(backup)


def run_effectiveness(n_repeats: int = 3, seed: int = 42) -> dict:
    rng = random.Random(seed)
    original = ROOT / "research_claims.json"
    if not original.exists():
        return {"error": "research_claims.json not found"}
    original_content = original.read_text(encoding="utf-8")

    results: dict[str, dict] = {}
    for protocol, mutations in MUTATION_SETS.items():
        protocol_stats = {
            "n_mutations": len(mutations),
            "n_repeats": n_repeats,
            "total_injections": len(mutations) * n_repeats,
            "total_caught": 0,
            "total_missed": 0,
            "per_mutation": {},
        }
        for mutation in mutations:
            caught = 0
            missed = 0
            for _repeat in range(n_repeats):
                with tempfile.TemporaryDirectory() as td:
                    td_path = Path(td)
                    (td_path / "research_claims.json").write_text(
                        original_content, encoding="utf-8"
                    )
                    try:
                        INJECTORS[protocol](td_path / "research_claims.json",
                                            mutation, rng)
                    except Exception:
                        continue
                    passed, _diag = _run_gate(protocol, td_path / "research_claims.json")
                    if not passed:
                        caught += 1
                    else:
                        missed += 1
            total = caught + missed
            catch_rate = caught / total if total > 0 else 0.0
            protocol_stats["per_mutation"][mutation] = {
                "n_injections": total,
                "n_caught": caught,
                "n_missed": missed,
                "catch_rate": round(catch_rate, 4),
            }
            protocol_stats["total_caught"] += caught
            protocol_stats["total_missed"] += missed
        protocol_stats["overall_catch_rate"] = (
            round(protocol_stats["total_caught"] / protocol_stats["total_injections"], 4)
            if protocol_stats["total_injections"] else 0.0
        )
        results[protocol] = protocol_stats

    total_inj = sum(s["total_injections"] for s in results.values())
    total_caught = sum(s["total_caught"] for s in results.values())
    overall_catch_rate = total_caught / total_inj if total_inj else 0.0

    # Which protocols have no gate at all (contribution to "miss" is 100%)
    uncovered = [p for p in MUTATION_SETS if GATE_INVOKER.get(p, (None, []))[0] is None]

    return {
        "schema": "s3_discipline_effectiveness_v1",
        "n_repeats_per_mutation": n_repeats,
        "seed": seed,
        "total_injections": total_inj,
        "total_caught": total_caught,
        "total_missed": total_inj - total_caught,
        "overall_catch_rate": round(overall_catch_rate, 4),
        "counterfactual_miss_rate_without_gate": 1.0,
        "miss_rate_reduction": round(1 - overall_catch_rate, 4),
        "gates_tested": {p: GATE_INVOKER.get(p, (None, []))[0]
                         for p in MUTATION_SETS},
        "gate_coverage_gaps": uncovered,
        "per_protocol": results,
        "interpretation": (
            f"Across {total_inj} injected preregistration violations, "
            f"the gates caught {total_caught} ({overall_catch_rate:.1%}). "
            f"Protocols with no dedicated gate: {uncovered or 'none'}. "
            f"Miss rate drops from 100% (no gates) to "
            f"{1 - overall_catch_rate:.1%}."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rep = run_effectiveness(n_repeats=args.repeats, seed=args.seed)
    with open(out_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print("S3 Discipline Effectiveness — Gate violation catch-rate")
    print(f"  repeats per mutation: {args.repeats}  seed: {args.seed}")
    print(f"  total injected: {rep['total_injections']}, caught: {rep['total_caught']}")
    print(f"  overall catch-rate: {rep['overall_catch_rate']:.1%}")
    print(f"  gate coverage gaps: {rep['gate_coverage_gaps'] or 'none'}")
    print()
    for protocol, stats in rep["per_protocol"].items():
        print(f"  {protocol}: {stats['overall_catch_rate']:.1%} "
              f"({stats['total_caught']}/{stats['total_injections']})")
        for mut, ms in stats["per_mutation"].items():
            marker = "✅" if ms["catch_rate"] >= 0.5 else ("⚠️" if ms["catch_rate"] > 0 else "❌")
            print(f"    {marker} {mut}: {ms['catch_rate']:.1%} "
                  f"({ms['n_caught']}/{ms['n_injections']})")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
