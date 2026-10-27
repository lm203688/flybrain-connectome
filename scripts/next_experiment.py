#!/usr/bin/env python3
"""next_experiment.py — E2 反馈导向实验调度（signal → next experiment）.

Why this exists
---------------
E1 (`compute_epistemic_progress.py`) separates the *apparatus* axis (A0–A5, what
verification machinery is attached) from the *evidence* axis (E0–E5, what the
claim actually demonstrated) and exports `progress.json` + `boundary_atlas.json`.

A dense progress signal is useless unless it *decides what to do next*.  This is
the second capability of 2608.09855: "the signal must determine the next
intervention, so the agent *searches* rather than *re-samples*."  E1 tells us
WHERE the knowledge is thin; this script converts that into a ranked action list.

Design: coverage-guided mutation, fuzzer-style.
  - coverage   = the boundary atlas (which claim × tier regions are explored)
  - mutation   = the next experiment, chosen to open the thinnest region
  - interest   = information gain, ranked by (evidence step × gap priority)

The single most important signal is the **apparatus/evidence gap** (`gap`):
a claim carrying V5 apparatus but only E3 evidence is a *divergent claim* —
the apparatus says "verified" while the evidence says "not confirmed".  Closing
that divergence is worth more than adding a redundant experiment to an
already-supported claim.  This is why the top recommendation for R1 (the only
divergent claim, gap=2, PR3_v2 passed on 5 families) is the *cross-family
absolute-threshold recalibration* — NOT another same-family expansion.

Outputs
-------
  next_experiment.json   ranked candidate experiments + info gain + rationale

Usage
-----
  python scripts/next_experiment.py
  python scripts/next_experiment.py --progress progress.json \\
      --atlas boundary_atlas.json --out next_experiment.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Evidence ladder (mirrors compute_epistemic_progress.py E_LADDER).
# ---------------------------------------------------------------------------
E_LEVEL = {
    "E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4, "E5": 5,
}

# ---------------------------------------------------------------------------
# Candidate experiment table.
# Each entry is the *next* experiment that would raise a claim's evidence, with
# an explicit rationale tied to the claim's current state.  This is deliberately
# explicit rather than auto-inferred: the "next intervention" must be justified
# by the actual boundary the claim sits on, not a generic rule.
# ---------------------------------------------------------------------------
# claim -> (experiment_id, description, target_evidence, rationale, basis)
CANDIDATES = {
    "R1": {
        "experiment_id": "X_R1_cross_family_threshold_recalib",
        "description": "跨族绝对阈值重标定（PR3_v2 已在 5 族通过后）",
        "target_evidence": "E4",
        "rationale": (
            "PR3_v2 PASS on 5 families raised R1 to E3. The next informative "
            "step is a cross-family absolute-threshold recalibration (is the "
            "family-relative effect a stable absolute effect?), NOT another "
            "same-family expansion. This is the E2 acceptance example verbatim."
        ),
        "basis": "PR3_v2 PASS (L3 cross-family) + R1 divergent (gap=2)",
    },
    "R2": {
        "experiment_id": "X_R2_recovery_cross_n_recalib",
        "description": "恢复动力学跨 n 阈值重标定（PR5 FAIL 后）",
        "target_evidence": "E2",
        "rationale": (
            "PR5 FAIL (cell densification) left R2 at E0. The recovery-fraction "
            "metric needs a cross-n threshold recalibration to separate a real "
            "recovery signal from the 64% zero-value floor already documented. "
            "Raising R2 to E2 requires a PASS at the measurement layer."
        ),
        "basis": "PR5 FAIL (L2 recovery) + R2 gap=1",
    },
    "R4": {
        "experiment_id": "X_R4_sensitivity_robustness",
        "description": "敏感性鲁棒性边界补测（R4 已有 sensitivity scan）",
        "target_evidence": "E2",
        "rationale": (
            "R4 sensitivity scan exists but no protocol PASS. A robustness "
            "boundary rerun with a preregistered PASS threshold would raise "
            "R4 from E0 to E2."
        ),
        "basis": "R4 sensitivity scan + R4 gap=1",
    },
    "R5": {
        "experiment_id": "X_R5_reservoir_capacity",
        "description": "层级储备池容量复测（F5 已有数据）",
        "target_evidence": "E2",
        "rationale": (
            "F5 hierarchical reservoir data exists but no protocol PASS. A "
            "capacity rerun with a preregistered PASS threshold would raise "
            "R5 from E0 to E2."
        ),
        "basis": "F5 hierarchical reservoir + R5 gap=1",
    },
    "R3": {
        "experiment_id": "X_R3_cross_species_external",
        "description": "跨物种外部验证（PR-S1 PARTIAL 边界后）",
        "target_evidence": "E1",
        "rationale": (
            "R3 carries a boundary_partial_falsification (cross-species PARTIAL "
            "in PR-S1). The next step is an external validation pass on the "
            "families where the boundary was PARTIAL, raising R3 to E1 as a "
            "documented (non-confirmed) boundary refinement."
        ),
        "basis": "R3 claim_boundary (boundary_partial_falsification)",
    },
    "R6": {
        "experiment_id": "X_R6_cross_species_role",
        "description": "跨物种 role 绑定扩展（T5#4 已 141 组跨 ≥2 物种）",
        "target_evidence": "E1",
        "rationale": (
            "R6 carries a boundary_anchor_gap (cross-species role binding "
            "partial). Extending the T5#4 role-binding across the remaining "
            "families would refine the boundary to E1."
        ),
        "basis": "R6 claim_boundary (boundary_anchor_gap) + T5#4 141 组跨物种",
    },
}


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def _info_gain(
    claim: str,
    gap: int,
    current: str,
    target: str,
    divergent: set[str],
) -> float:
    """Coverage-guided information gain.

    gain = (evidence step) x (1 + gap) + divergent bonus

    - evidence step: how many E-rungs the experiment could climb.
    - (1 + gap): a claim with high apparatus but low evidence is a *thinner*
      region — closing it is worth more (search, not re-sample).
    - divergent bonus: a claim whose apparatus/evidence gap makes it a
      registered divergent claim (progress_vector.divergent_claims) is the
      single highest-value target: the apparatus claims "verified" while the
      evidence says "not confirmed".  Bonus +3.0.
    """
    step = E_LEVEL.get(target, 0) - E_LEVEL.get(current, 0)
    if step <= 0:
        return 0.0
    gap_priority = 1.0 + max(gap, 0)
    divergent_bonus = 3.0 if claim in divergent else 0.0
    return float(step) * gap_priority + divergent_bonus


def main() -> int:
    ap = argparse.ArgumentParser(description="E2 feedback-driven experiment scheduling")
    ap.add_argument("--progress", default=str(ROOT / "progress.json"))
    ap.add_argument("--atlas", default=str(ROOT / "boundary_atlas.json"))
    ap.add_argument("--out", default=str(ROOT / "next_experiment.json"))
    args = ap.parse_args()

    prog_path = Path(args.progress)
    atlas_path = Path(args.atlas)
    out_path = Path(args.out)

    if not prog_path.exists():
        print(f"[FAIL] progress.json not found: {prog_path}", file=sys.stderr)
        return 1
    if not atlas_path.exists():
        print(f"[FAIL] boundary_atlas.json not found: {atlas_path}", file=sys.stderr)
        return 1

    progress = _load(prog_path)
    atlas = _load(atlas_path)

    claims = progress.get("claims", {})
    if not claims:
        print("[FAIL] progress.json has no 'claims'", file=sys.stderr)
        return 1

    vector = progress.get("progress_vector", {})
    divergent = set(vector.get("divergent_claims", []))
    if not isinstance(divergent, set):
        divergent = set(divergent)

    # Atlas coverage: which claim has a registered boundary entry (falsified /
    # weak / pre-execution / boundary).
    atlas_entries = atlas.get("entries", []) if isinstance(atlas, dict) else []
    atlas_covered: dict[str, list[dict]] = {}
    for e in atlas_entries:
        if not isinstance(e, dict):
            continue
        c = e.get("claim")
        if c:
            atlas_covered.setdefault(c, []).append(e)

    # Build ranked experiment list.
    ranked: list[dict] = []
    for claim, cand in CANDIDATES.items():
        state = claims.get(claim)
        if not state:
            continue
        gap = state.get("gap", 0)
        current = state.get("evidence", "E0")
        target = cand["target_evidence"]
        gain = _info_gain(claim, gap, current, target, divergent)
        ranked.append({
            "claim": claim,
            "experiment_id": cand["experiment_id"],
            "description": cand["description"],
            "current_evidence": current,
            "target_evidence": target,
            "apparatus": state.get("apparatus", "?"),
            "gap": gap,
            "divergent": claim in divergent,
            "info_gain": round(gain, 2),
            "rationale": cand["rationale"],
            "basis": cand["basis"],
            "atlas_boundary_entries": atlas_covered.get(claim, []),
        })

    ranked.sort(key=lambda r: (-r["info_gain"], r["claim"]))

    out = {
        "schema": "next_experiment_v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_files": {
            "progress.json": _file_hash(prog_path),
            "boundary_atlas.json": _file_hash(atlas_path),
        },
        "model": "coverage_guided_gain = step x (1+gap) + 3.0 if divergent",
        "divergent_claims": sorted(divergent),
        "n_candidates": len(ranked),
        "experiments": ranked,
        "top_recommendation": ranked[0] if ranked else None,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[ok] wrote {out_path} ({len(ranked)} candidates)")
    if ranked:
        top = ranked[0]
        print(f"[ok] TOP: {top['experiment_id']}  claim={top['claim']}  "
              f"gain={top['info_gain']}  {top['description']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
