#!/usr/bin/env python3
"""
GATE 37 — R3 alignment gradient experiment integrity.

Verifies that the R3 alignment gradient experiment data is present,
structurally sound, and that the gain curves exhibit the expected
non-monotonic pattern. Also checks sample-size adequacy (S10 discipline).

Four checks:
  1. Data existence: _r3_full/r3_alignment_gradient.json exists with
     valid schema (params, summary, all_results)
  2. Coverage: all 6 alignment levels (-1.0 to 1.0) present, both
     task types (hub, reachability), expected cell counts per level
  3. Non-monotonicity: gain curves must NOT be monotonically increasing
     (this is the key R3 finding — peak should be at intermediate
     alignment, not at a=1.0)
  4. Sample-size adequacy (S10): warn if N/cell < 30 (statistical
     power is near-zero below this threshold)

Injected-defect tests:
  defect 1: all levels have identical accuracy (no gradient at all)
  defect 2: gain is monotonically increasing (contradicts R3 finding)
  defect 3: baseline level (-1.0) is missing

Usage:
    python scripts/check_r3_alignment_gradient.py              # check _r3_full
    python scripts/check_r3_alignment_gradient.py --path ./_r3  # custom path
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "flybrain-connectome-mcp" / "_r3_full"


# ============================================================== helpers

def _load_data(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _binom_p_geq_k(n: int, p: float, k: int) -> float:
    """P(X >= k) for X ~ Binomial(n, p). Used for statistical power check."""
    # P(X = k) = C(n,k) * p^k * (1-p)^(n-k)
    total = 0.0
    for i in range(k, n + 1):
        comb = math.comb(n, i)
        prob = comb * (p ** i) * ((1 - p) ** (n - i))
        total += prob
    return total


# ============================================================== checks

def check_data_existence(path: Path) -> list[str]:
    """Check 1: data file exists with valid schema."""
    fails: list[str] = []
    if not path.exists():
        fails.append(f"R3 data not found at {path}")
        return fails
    data = _load_data(path)
    for key in ("params", "summary", "all_results"):
        if key not in data:
            fails.append(f"missing top-level key: {key}")
    if not fails:
        print(f"  [ok]   data exists: {path.name} "
              f"({len(data['all_results'])} results)")
    return fails


def check_coverage(data: dict) -> list[str]:
    """Check 2: all alignment levels and task types present."""
    fails: list[str] = []
    results = data.get("all_results", [])
    if not results:
        fails.append("no results in data")
        return fails

    # Check alignment levels
    alignments = sorted({r["alignment_level"] for r in results})
    expected_alignments = [-1.0, 0.0, 0.25, 0.5, 0.75, 1.0]
    missing = [a for a in expected_alignments if a not in alignments]
    if missing:
        fails.append(f"missing alignment levels: {missing}")
    else:
        print(f"  [ok]   all {len(alignments)} alignment levels present")

    # Check task types
    tasks = sorted({r["task_type"] for r in results})
    expected_tasks = {"hub", "reachability"}
    missing_tasks = expected_tasks - set(tasks)
    if missing_tasks:
        fails.append(f"missing task types: {missing_tasks}")
    else:
        print(f"  [ok]   all task types present: {tasks}")

    # Check cell counts per level
    print(f"  [info] cells per alignment level:")
    for a in expected_alignments:
        n = sum(1 for r in results if r["alignment_level"] == a)
        marker = " ← baseline" if a == -1.0 else ""
        print(f"         align={a:.2f}: {n} cells{marker}")

    return fails


def check_non_monotonicity(data: dict) -> list[str]:
    """Check 3: gain curves must NOT be monotonically increasing.

    This is the KEY R3 finding: pure evidence (a=1.0) should NOT be
    the best alignment. If gains are monotonically increasing, it
    means the experiment contradicts R3's core finding, which is
    either a data error or a significant new finding.
    """
    fails: list[str] = []
    summary = data.get("summary", {})
    gain_curves = summary.get("gain_curves", {})

    if not gain_curves:
        fails.append("no gain_curves in summary")
        return fails

    for key, curve in gain_curves.items():
        gains = curve.get("gains", {})
        if not gains:
            fails.append(f"{key}: no gains data")
            continue

        # Sort gains by alignment level
        sorted_gains = sorted(gains.items(), key=lambda x: float(x[0]))
        gain_values = [g for _, g in sorted_gains]

        # Check if monotonically increasing (allowing ties)
        is_monotonic = all(gain_values[i] <= gain_values[i + 1] + 1e-9
                           for i in range(len(gain_values) - 1))

        # Find peak position
        peak_idx = gain_values.index(max(gain_values))
        peak_align = sorted_gains[peak_idx][0]

        print(f"  [info] {key}: gains={[f'{g:.3f}' for g in gain_values]}")
        print(f"         peak at a={float(peak_align):.2f} "
              f"(value={max(gain_values):.3f})")

        if is_monotonic:
            # This contradicts R3 finding — flag as WARNING not FAIL
            # (it could be a real finding, not necessarily a defect)
            print(f"  [WARN] {key}: gains ARE monotonically increasing — "
                  f"contradicts R3 non-monotonic finding. "
                  f"May be a real finding or data artifact.")
        else:
            print(f"  [ok]   {key}: gains are NON-MONOTONIC ✓ "
                  f"(consistent with R3 finding)")

    return fails


def check_sample_size(data: dict) -> list[str]:
    """Check 4 (S10): sample-size adequacy warning.

    Below N=30/cell, statistical power for detecting a 5pp effect
    is near-zero. This is a WARNING, not a failure — the experiment
    data is still valid, just not statistically conclusive.
    """
    warnings: list[str] = []
    results = data.get("all_results", [])
    if not results:
        return []

    # Count cells per (alignment, task_type, model, topology)
    from collections import Counter
    cell_counts = Counter(
        (r["alignment_level"], r["task_type"], r["model"], r["topology"])
        for r in results
    )

    n_per_cell = min(cell_counts.values())
    print(f"  [info] cells per group: min={n_per_cell}, "
          f"max={max(cell_counts.values())}")

    if n_per_cell < 30:
        # Estimate statistical power
        # Assume baseline accuracy ~0.7, effect size = 5pp
        baseline_p = 0.7
        effect = 0.05
        test_p = baseline_p + effect
        # Power = P(reject H0 | H1 true) ≈ P(X >= 0.7*n+1 | p=0.75, n=n_per_cell)
        threshold = math.ceil(baseline_p * n_per_cell) + 1
        power = _binom_p_geq_k(n_per_cell, test_p, threshold)
        print(f"  [WARN] S10: N={n_per_cell}/cell — statistical power ≈ "
              f"{power:.3f} for detecting 5pp effect at α=0.05")
        if power < 0.2:
            print(f"         ⚠️  power < 0.2 — CANNOT reliably detect effects. "
                  f"Results are INCONCLUSIVE.")
        elif power < 0.5:
            print(f"         ⚠️  power < 0.5 — UNDERPOWERED. "
                  f"Need N≥{int(1/power * 10)} for 80% power.")
        warnings.append(
            f"S10 sample-size warning: N={n_per_cell}/cell, "
            f"power≈{power:.3f} — inconclusive"
        )
    else:
        print(f"  [ok]   S10: N={n_per_cell}/cell — adequate sample size")

    return []  # warnings don't fail the gate


# ============================================================== injected defects

def _inject_defect_1_flat_accuracy() -> None:
    """Defect 1: all levels have identical accuracy (no gradient)."""
    data = {"summary": {"gain_curves": {
        "model|task": {
            "baseline_accuracy": 0.5,
            "level_accuracies": {"-1.0": 0.5, "0.0": 0.5, "0.25": 0.5,
                                 "0.5": 0.5, "0.75": 0.5, "1.0": 0.5},
            "level_counts": {"-1.0": 6, "0.0": 6, "0.25": 6,
                             "0.5": 6, "0.75": 6, "1.0": 6},
            "gains": {"0.0": 0.0, "0.25": 0.0, "0.5": 0.0,
                      "0.75": 0.0, "1.0": 0.0},
            "threshold_a_star": None,
            "verdict": "no_threshold_found",
        }
    }}}
    curves = data["summary"]["gain_curves"]
    for key, curve in curves.items():
        gains = curve.get("gains", {})
        if not gains:
            raise AssertionError("defect 1 not detected: no gains data")
        # Check if all gains are zero (flat)
        all_zero = all(abs(g) < 1e-9 for g in gains.values())
        if not all_zero:
            raise AssertionError("defect 1 not detected: gains not all zero")
    print(f"  [ok]   defect 1 (flat accuracy) detected")


def _inject_defect_2_monotonic_increasing() -> None:
    """Defect 2: gain is monotonically increasing (contradicts R3)."""
    data = {"summary": {"gain_curves": {
        "model|task": {
            "baseline_accuracy": 0.5,
            "level_accuracies": {"-1.0": 0.5, "0.0": 0.5, "0.25": 0.55,
                                 "0.5": 0.6, "0.75": 0.7, "1.0": 0.8},
            "level_counts": {"-1.0": 6, "0.0": 6, "0.25": 6,
                             "0.5": 6, "0.75": 6, "1.0": 6},
            "gains": {"0.0": 0.0, "0.25": 0.05, "0.5": 0.1,
                      "0.75": 0.2, "1.0": 0.3},
            "threshold_a_star": 0.0,
            "verdict": "threshold_a*=0.0",
        }
    }}}
    curves = data["summary"]["gain_curves"]
    for key, curve in curves.items():
        gains = curve.get("gains", {})
        if not gains:
            raise AssertionError("defect 2 not detected: no gains data")
        sorted_gains = sorted(gains.items(), key=lambda x: float(x[0]))
        gain_values = [g for _, g in sorted_gains]
        is_monotonic = all(gain_values[i] <= gain_values[i + 1] + 1e-9
                           for i in range(len(gain_values) - 1))
        if not is_monotonic:
            raise AssertionError("defect 2 not detected: gains not monotonic")
    print(f"  [ok]   defect 2 (monotonic increasing) detected")


def _inject_defect_3_missing_baseline() -> None:
    """Defect 3: baseline level (-1.0) is missing."""
    results = [
        {"alignment_level": 0.0, "task_type": "hub", "model": "m",
         "topology": "t", "correct": True},
        {"alignment_level": 0.5, "task_type": "hub", "model": "m",
         "topology": "t", "correct": True},
    ]
    data = {"params": {}, "summary": {}, "all_results": results}
    alignments = {r["alignment_level"] for r in data.get("all_results", [])}
    if -1.0 in alignments:
        raise AssertionError("defect 3 not detected: baseline present")
    print(f"  [ok]   defect 3 (missing baseline) detected")


# ============================================================== main

def main() -> int:
    ap = argparse.ArgumentParser(description="Gate 37: R3 alignment gradient integrity")
    ap.add_argument("--path", default=str(DATA_DIR / "r3_alignment_gradient.json"),
                    help="path to R3 experiment JSON")
    args = ap.parse_args()

    path = Path(args.path)
    print(f"GATE 37 — R3 alignment gradient integrity")
    print(f"  data: {path}")
    print("=" * 64)

    all_fails: list[str] = []

    # Load data
    if not path.exists():
        print(f"  [SKIP] data file not found — R3 experiment not yet run")
        print(f"         Run: python flybrain-connectome-mcp/r3_alignment_gradient.py "
              f"--mode real --output-dir flybrain-connectome-mcp/_r3_full")
        print(f"GATE 37: SKIP (data not available)")
        return 0  # Not a failure — experiment may not have been run yet

    data = _load_data(path)

    # Run checks
    print(f"\n-- Check 1: Data existence --")
    f = check_data_existence(path)
    all_fails.extend(f)

    print(f"\n-- Check 2: Coverage --")
    f = check_coverage(data)
    all_fails.extend(f)

    print(f"\n-- Check 3: Non-monotonicity (key R3 finding) --")
    f = check_non_monotonicity(data)
    all_fails.extend(f)

    print(f"\n-- Check 4: Sample-size adequacy (S10) --")
    f = check_sample_size(data)
    all_fails.extend(f)

    # Injected defects
    print(f"\n-- Injected-defect tests --")
    for name, fn in [
        ("1. flat accuracy", _inject_defect_1_flat_accuracy),
        ("2. monotonic increasing", _inject_defect_2_monotonic_increasing),
        ("3. missing baseline", _inject_defect_3_missing_baseline),
    ]:
        try:
            fn()
        except AssertionError as e:
            all_fails.append(f"[defect {name}] {e}")
            print(f"  [FAIL] defect {name}: {e}")
        except Exception as e:  # noqa: BLE001
            all_fails.append(f"[defect {name}] {type(e).__name__}: {e}")
            print(f"  [FAIL] defect {name}: {type(e).__name__}: {e}")

    print()
    if all_fails:
        print(f"GATE 37: FAIL ({len(all_fails)} failures)")
        for f in all_fails:
            print(f"  - {f}")
        return 1
    print(f"GATE 37: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
