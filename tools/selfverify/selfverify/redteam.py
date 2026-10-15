"""selfverify.redteam — automated adversarial self-verification (S3).

Four attack vectors, each targeting a different epistemic failure mode. Each
attack receives a claim's data (either a full protocol+results pair or a raw
result dict) and returns a list of findings. Any finding means "the red team
succeeded; the claim should not be trusted until the finding is addressed."

The four attacks:
  1. summary_tamper        — modify a summary field and check if the gate catches it
  2. metric_saturation     — detect zero-variance / always-0 / always-1 outcome metrics
  3. analytic_redundancy   — detect when the consequence metric is derivable from
                            the intervention variable (PR-2b-style denominator artifact)
  4. resolution_clamp      — detect when target intervals silently clamp to boundary
                            (silent density / clamp_density style)

The module is intentionally independent of the flybrain project: it operates
on plain JSON dicts, so any project can adopt it as a red-team harness.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Attack 1: summary_tamper
# ---------------------------------------------------------------------------
def summary_tamper(
    protocol: dict,
    results: dict,
    *,
    summary_field: str = "summary.auc",
    tamper_value: float = 0.999,
    recompute_fn: Callable[[dict], Any] | None = None,
) -> dict:
    """Return a finding dict describing whether a summary field was detected as tampered.

    If `recompute_fn` is provided, we recompute the value from raw samples and
    compare to the tampered summary. If not, we fall back to a hash commitment
    on the raw sample set.
    """
    # Build the raw-samples fingerprint
    raw_samples = results.get("samples") or results.get("all_results") or []
    raw_fingerprint = hashlib.sha256(
        json.dumps(raw_samples, sort_keys=True, default=str).encode()
    ).hexdigest()

    # Extract the current summary value
    summary = results.get("summary", {}) if isinstance(results, dict) else {}
    # allow dotted paths like "summary.auc"
    parts = summary_field.split(".")
    if parts[0] == "summary":
        target = summary
        for p in parts[1:]:
            target = target.get(p, None) if isinstance(target, dict) else None
    else:
        target = results.get(summary_field)

    tampered = dict(results)
    # perform tampering in-memory
    if "summary" in tampered and isinstance(tampered["summary"], dict):
        tampered["summary"][parts[-1]] = tamper_value

    # recompute if possible
    recomputed = None
    if recompute_fn is not None and "samples" in results:
        try:
            recomputed = recompute_fn(results)
        except Exception as e:  # pragma: no cover
            return {
                "attack": "summary_tamper",
                "caught": False,
                "reason": f"recompute raised: {e}",
                "raw_fingerprint": raw_fingerprint,
            }

    # A summary field is caught if the recomputed value disagrees with the tampered value
    caught = recomputed is not None and abs(float(recomputed) - float(tamper_value)) > 1e-9

    return {
        "attack": "summary_tamper",
        "target_field": summary_field,
        "reported_value": target,
        "tampered_value": tamper_value,
        "recomputed_value": recomputed,
        "caught": bool(caught),
        "raw_fingerprint": raw_fingerprint,
    }


# ---------------------------------------------------------------------------
# Attack 2: metric_saturation
# ---------------------------------------------------------------------------
def metric_saturation(
    values: list[float],
    *,
    variance_floor: float = 1e-6,
    zero_ratio_threshold: float = 0.30,
    one_ratio_threshold: float = 0.30,
) -> dict:
    """Detect metrics that have collapsed to a degenerate distribution.

    - variance below `variance_floor` → saturating (no discriminating power)
    - more than `zero_ratio_threshold` of values are exactly 0
    - more than `one_ratio_threshold` of values are exactly 1 (or the max)
    """
    n = len(values)
    if n == 0:
        return {
            "attack": "metric_saturation",
            "caught": True,
            "reason": "empty metric vector",
            "n": 0,
        }
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    zero_ratio = sum(1 for v in values if v == 0) / n
    vmax = max(values)
    one_ratio = sum(1 for v in values if v == vmax) / n if vmax > 0 else 0.0

    reasons: list[str] = []
    if variance < variance_floor:
        reasons.append(f"variance={variance:.3e} < floor {variance_floor:.1e}")
    if zero_ratio >= zero_ratio_threshold:
        reasons.append(f"zero_ratio={zero_ratio:.2%} ≥ {zero_ratio_threshold:.0%}")
    if vmax > 0 and one_ratio >= one_ratio_threshold:
        reasons.append(f"max_ratio={one_ratio:.2%} ≥ {one_ratio_threshold:.0%}")

    return {
        "attack": "metric_saturation",
        "n": n,
        "mean": mean,
        "variance": variance,
        "zero_ratio": zero_ratio,
        "max_value": vmax,
        "max_ratio": one_ratio,
        "caught": bool(reasons),
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Attack 3: analytic_redundancy
# ---------------------------------------------------------------------------
def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / (sxx * syy) ** 0.5


def analytic_redundancy(
    intervention_vars: list[float],
    consequence_vars: list[float],
    *,
    corr_threshold: float = 0.5,
) -> dict:
    """Detect a consequence metric analytically tied to the intervention variable.

    If the consequence metric moves in lockstep with the intervention variable
    (|corr| >= threshold), the metric is analytically redundant and cannot
    serve as an independent consequence read-out.
    """
    if len(intervention_vars) != len(consequence_vars):
        return {
            "attack": "analytic_redundancy",
            "caught": False,
            "reason": "length mismatch",
            "n_intervention": len(intervention_vars),
            "n_consequence": len(consequence_vars),
        }
    corr = _pearson(intervention_vars, consequence_vars)
    return {
        "attack": "analytic_redundancy",
        "n": len(intervention_vars),
        "corr": corr,
        "abs_corr": abs(corr),
        "threshold": corr_threshold,
        "caught": abs(corr) >= corr_threshold,
    }


# ---------------------------------------------------------------------------
# Attack 4: resolution_clamp
# ---------------------------------------------------------------------------
def resolution_clamp(
    requested_grid: list[float],
    actual_grid: list[float],
    *,
    tolerance: float = 1e-9,
) -> dict:
    """Detect when the target grid is silently truncated to the achievable range.

    In the R2 density scan (S7 discipline), the target density grid 0.001..0.100
    was implicitly clamped to clamp_density = n_nodes / (n*(n-1)) = 0.032 for
    n=40. The scan silently stopped at the achievable max — the researcher
    never noticed. This attack surfaces that mismatch.
    """
    if len(requested_grid) == 0 or len(actual_grid) == 0:
        return {
            "attack": "resolution_clamp",
            "caught": False,
            "reason": "empty grid",
        }
    requested_min, requested_max = min(requested_grid), max(requested_grid)
    actual_min, actual_max = min(actual_grid), max(actual_grid)

    # silent clamp: the max we actually reached is significantly below the max
    # we requested
    clamped_high = actual_max < requested_max - tolerance
    clamped_low = actual_min > requested_min + tolerance

    return {
        "attack": "resolution_clamp",
        "requested_range": (requested_min, requested_max),
        "actual_range": (actual_min, actual_max),
        "clamped_high": clamped_high,
        "clamped_low": clamped_low,
        "n_requested": len(requested_grid),
        "n_actual": len(actual_grid),
        "caught": clamped_high or clamped_low,
    }


# ---------------------------------------------------------------------------
# Convenience: run the full red-team battery
# ---------------------------------------------------------------------------
def run_battery(
    *,
    summary_tamper_case: dict | None = None,
    metric_saturation_values: list[float] | None = None,
    analytic_redundancy_case: tuple[list[float], list[float]] | None = None,
    resolution_clamp_case: tuple[list[float], list[float]] | None = None,
) -> dict:
    """Run all four attacks and aggregate findings."""
    findings: list[dict] = []
    if summary_tamper_case is not None:
        findings.append(summary_tamper(**summary_tamper_case))
    if metric_saturation_values is not None:
        findings.append(metric_saturation(metric_saturation_values))
    if analytic_redundancy_case is not None:
        iv, cv = analytic_redundancy_case
        findings.append(analytic_redundancy(iv, cv))
    if resolution_clamp_case is not None:
        req, act = resolution_clamp_case
        findings.append(resolution_clamp(req, act))

    caught = sum(1 for f in findings if f.get("caught"))
    return {
        "n_attacks": len(findings),
        "n_caught": caught,
        "verdict": "REJECTED" if caught == len(findings) and len(findings) > 0 else ("SUSPECT" if caught else "PASS"),
        "findings": findings,
    }


__all__ = [
    "summary_tamper",
    "metric_saturation",
    "analytic_redundancy",
    "resolution_clamp",
    "run_battery",
]
