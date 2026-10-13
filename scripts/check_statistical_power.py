#!/usr/bin/env python3
"""GATE 42 — statistical power pre-check (SV-5b).

Why this exists
---------------
Every significance / gradient / threshold claim has an implicit minimum
sample size beyond which the observation is distinguishable from noise.
R3 ("structure value × substrate alignment") ran with only 6 cells per
level — a sample size that cannot detect any effect of practical
magnitude — yet was reported as a "hypothesis" alongside a set of
positive results. That is exactly the failure mode this gate closes.

Gate 42 does NOT re-run experiments. It reads `research_claims.json`
(the five-element self-verification manifest) and asks two questions for
every claim:

  Q1. What is the claim's *effective* sample size N?
  Q2. Does the claim's test method have enough *statistical power* at
      that N to reach a positive conclusion?

If a claim asserts a positive conclusion (status ∈ {complete, supported,
supported_after_metric_fix}) but N is below the power threshold for
its test method, the gate goes red — regardless of how confident the
prose sounds.

If a claim already *acknowledges* the limitation (status contains
"inconclusive" / "needs_more_data" / "insufficient" / "needs_evidence"),
the gate reports a WARN but does not fail — the project has declared
the boundary honestly.

Injection battery
-----------------
The gate has an injection battery that mutates one real claim to a
"positive but under-powered" state and confirms the gate turns red.
Apply / restore are structurally separate closures.

Usage:
    python scripts/check_statistical_power.py
    python scripts/check_statistical_power.py --claims /path/to/research_claims.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_CLAIMS = ROOT / "research_claims.json"

GATE_ID = 42
GATE_LABEL = f"GATE {GATE_ID}"


# ---------------------------------------------------------------------------
# Test-method → minimum-N table.
#
# These are rule-of-thumb thresholds calibrated to α=0.05, power=0.80 for
# a moderate effect (Cohen d=0.5, r=0.3). They are not exhaustive — a
# claim can override by declaring an explicit `power_precheck` block in
# the JSON. But they give the gate a default to enforce.
#
# The important property is that ANY claim asserting a positive
# conclusion with N below its method's floor is caught.
# ---------------------------------------------------------------------------

METHOD_THRESHOLDS: dict[str, int] = {
    # Correlation / regression on a continuous outcome: needs enough
    # pairs to detect r=0.3 at α=0.05, power=0.80 → N≈85.
    # We relax to 30 because many of our claims are descriptive.
    "correlation": 30,
    "regression": 30,

    # Binary outcome classification (e.g. logistic regression, AUC):
    # needs enough events per class to be informative. 40 is a rough
    # floor; G*Power calls for ~64/group for d=0.5.
    "classification": 40,
    "auc": 40,
    "logistic": 40,

    # Density sweeps / gradient studies / threshold localisation:
    # need multiple points to fit a monotone trend → 100 is our floor.
    "gradient": 100,
    "sweep": 100,
    "threshold": 100,

    # Assertion-based (invariants, structural counts) don't need a
    # sample-size in the statistical sense — the gate accepts N=1.
    "assertion": 1,
    "invariant": 1,
    "coverage": 5,
    "count": 5,

    # Default: use the strictest general-purpose threshold.
    "unknown": 30,
}


# ---------------------------------------------------------------------------
# Status categories.
# ---------------------------------------------------------------------------

_POSITIVE_STATUS = {"complete", "supported", "supported_after_metric_fix",
                    "verified", "closed"}
_ACKNOWLEDGED_STATUS_TOKENS = {
    "inconclusive", "needs_more_data", "insufficient",
    "needs_evidence", "needs_evidence_strengthening", "inconclusive_needs_more_data",
    "open", "wip", "falsified", "refuted", "boundary",
}


def _status_kind(status: str) -> str:
    """Classify a status string as 'positive', 'acknowledged', or 'other'."""
    s = (status or "").strip().lower()
    if s in _POSITIVE_STATUS:
        return "positive"
    for token in _ACKNOWLEDGED_STATUS_TOKENS:
        if token in s:
            return "acknowledged"
    return "other"


# ---------------------------------------------------------------------------
# Parsing: pull an effective N out of a human-written sample_size string.
# ---------------------------------------------------------------------------

# Patterns we accept, in priority order:
#   "N = 42"
#   "N=42"
#   "6 cells/level"            → 6
#   "6 cells per level"        → 6
#   "200 per density"          → 200
#   "30 topologies"            → 30
#   "8-stage lifecycle, 12 assertions"  → 12 (the numeric part of the tally)
_SAMPLE_PATTERNS = [
    r"\bN\s*=\s*(\d+)",
    r"\bN\s*(\d+)",
    r"(\d+)\s+cells?\s*/\s*(?:level|group|density|trial|repeat)",
    r"(\d+)\s+cells?\s+per\s+(?:level|group|density|trial|repeat)",
    r"(\d+)\s+per\s+(?:density|level|group|node)",
    r"(\d+)\s+(?:topologies|samples|trials|runs|blueprints|organisms|units|profiles)",
    r"(\d+)\s+(?:results|assertions|points|measurements|pairs)",
]


def parse_effective_n(sample_size: str, method: str) -> tuple[int | None, str]:
    """Return (effective_N, matched_pattern) or (None, reason).

    We prefer *per-group* counts over totals because those are what
    determine statistical power. If the string mentions both a total
    and a per-level/per-group count, we take the per-group one.
    """
    if not sample_size:
        return None, "empty sample_size"
    text = sample_size.lower()
    # Look for per-group hints first.
    for pat in _SAMPLE_PATTERNS[:4]:
        m = re.search(pat, text)
        if m:
            return int(m.group(1)), pat
    # Then general counts.
    for pat in _SAMPLE_PATTERNS[4:]:
        m = re.search(pat, text)
        if m:
            return int(m.group(1)), pat
    # Fallback: take the largest integer found.
    ints = [int(x) for x in re.findall(r"\d+", text)]
    if ints:
        return max(ints), "largest integer"
    return None, "no integer found"


# ---------------------------------------------------------------------------
# Method inference.
# ---------------------------------------------------------------------------

_METHOD_KEYWORDS = [
    ("auc",         ("auc", "roc", "classification")),
    ("logistic",    ("logistic", "classification")),
    ("correlation", ("correlation", "r²", "r2", "slope", "pearson",
                     "correlates", "correlate", "相关")),
    ("regression",  ("regression", "ols", "linear", "regressed")),
    ("gradient",    ("gradient", "monotonic", "cliff", "density-dependent",
                     "梯度", "阈值")),
    ("sweep",       ("sweep", "scan", "扫描", "sweep across")),
    ("threshold",   ("threshold", "crossover", "crosses 1.0", "阈值")),
    # Structural / assertion-type claims: these are invariants or counts,
    # not statistical samples, so they're satisfied by N=1.
    ("invariant",   ("invariant", "identity", "recomputation", "signature",
                     "闭环", "生命周期", "lifecycle", "closed loop",
                     "reproducible")),
    ("assertion",   ("assertion", "self-consistency", "断言", "assertions")),
    ("coverage",    ("coverage", "every unit", "every capability",
                     "every connection", "跨进化支", "跨物种")),
]


def infer_method(claim: dict) -> tuple[str, str]:
    """Return (method, evidence_substring) for a claim.

    Only the *primary* claim text is scanned: title, statement, and
    quantitative_prediction. We deliberately exclude boundary_statement,
    supporting_evidence, and falsified_mechanisms because those fields
    carry *resolution notes* that mention sub-analyses with their own
    sample sizes (e.g. R1's boundary_statement talks about A2's AUC
    mechanism test, which is a different experiment with different N).
    Classifying on those would pick the wrong method and force a spurious
    power requirement on the parent claim.
    """
    blob_parts = [
        claim.get("title", ""),
        claim.get("statement", ""),
        claim.get("quantitative_prediction", ""),
        claim.get("sample_size", ""),
    ]
    blob = " ".join(blob_parts).lower()
    for method, keywords in _METHOD_KEYWORDS:
        for kw in keywords:
            if kw in blob:
                return method, kw
    return "unknown", ""


# ---------------------------------------------------------------------------
# Power evaluation
# ---------------------------------------------------------------------------

@dataclass
class ClaimEval:
    claim_id: str
    status: str
    status_kind: str
    method: str
    method_keyword: str
    effective_n: int | None
    n_source: str
    required_n: int
    verdict: str        # "pass" | "warn" | "fail"
    reason: str


def evaluate_claims(claims: list[dict]) -> list[ClaimEval]:
    out: list[ClaimEval] = []
    for c in claims:
        cid = c.get("id", "?")
        status = c.get("status", "") or ""
        skind = _status_kind(status)
        method, method_kw = infer_method(c)
        sample_size = c.get("sample_size", "") or ""
        n, n_source = parse_effective_n(sample_size, method)
        # If the claim declares its own threshold, honour it.
        explicit = c.get("power_precheck", {}).get("min_n") if isinstance(
            c.get("power_precheck"), dict) else None
        required_n = int(explicit) if explicit else METHOD_THRESHOLDS.get(
            method, METHOD_THRESHOLDS["unknown"])

        if n is None:
            verdict = "fail"
            reason = f"cannot parse an effective N from sample_size: '{sample_size}'"
        elif skind == "positive" and n < required_n:
            verdict = "fail"
            reason = (f"positive status='{status}' but effective N={n} "
                      f"< required N={required_n} for method='{method}'")
        elif skind == "acknowledged" and n < required_n:
            verdict = "warn"
            reason = (f"acknowledged status='{status}'; effective N={n} "
                      f"< required N={required_n} for method='{method}' "
                      f"(already tracked as a boundary case)")
        else:
            verdict = "pass"
            reason = (f"effective N={n} >= required N={required_n} "
                      f"for method='{method}' (status='{status}')")

        out.append(ClaimEval(
            claim_id=cid, status=status, status_kind=skind,
            method=method, method_keyword=method_kw,
            effective_n=n, n_source=n_source,
            required_n=required_n, verdict=verdict, reason=reason,
        ))
    return out


# ---------------------------------------------------------------------------
# Injection battery — prove Gate 42 can turn red.
# ---------------------------------------------------------------------------

def _injections() -> tuple[int, int]:
    """Two injections:

      1. Take a real claim with sufficient N, downgrade its status to
         'complete' and shrink its N below the method threshold → FAIL.
      2. Remove every integer from a claim's sample_size → parse error → FAIL.

    Apply / restore are separate closures over the in-memory claims list.
    """
    bad = 0
    n_inj = 0
    real_claims: list[dict] = list(_claims)  # shallow copy of top-level list
    real_objects: dict[str, dict] = {c["id"]: c for c in real_claims}

    def expect(name, apply_fn, restore_fn):
        nonlocal bad, n_inj
        n_inj += 1
        apply_fn()
        try:
            evals = evaluate_claims(_claims)
        finally:
            restore_fn()
        ok = any(e.verdict == "fail" for e in evals)
        if ok:
            print(f"    [PASS] injecting: {name}")
        else:
            bad += 1
            print(f"    [FAIL] injecting: {name} -> GATE STAYED GREEN")

    # --- Injection 1: force a positive claim under-powered ---
    # Pick a claim whose method threshold is at least 30 so the
    # shrinkage actually crosses the line. Prefer R1 or R2.
    target = next((c for c in _claims if c.get("id") in {"R1", "R2"}), None)
    if target is None:
        target = _claims[0] if _claims else None

    def _patch_underpower():
        if target is None:
            return
        target["status"] = "complete"
        target["sample_size"] = "N = 4 (injected: below power floor)"

    def _restore_underpower():
        if target is None:
            return
        orig = real_objects.get(target.get("id", ""))
        if orig is not None:
            target["status"] = orig["status"]
            target["sample_size"] = orig["sample_size"]

    expect("downgrade a positive claim to N=4 (below power floor)",
           _patch_underpower, _restore_underpower)

    # --- Injection 2: strip integers from a sample_size → parse error ---
    def _patch_no_int():
        for c in _claims:
            if c.get("sample_size"):
                c["sample_size"] = "not stated numerically (injected)"

    def _restore_no_int():
        for c in _claims:
            orig = real_objects.get(c.get("id", ""))
            if orig is not None:
                c["sample_size"] = orig["sample_size"]

    expect("strip integers from every sample_size -> parse error",
           _patch_no_int, _restore_no_int)

    return bad, n_inj


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_claims: list[dict] = []


def main() -> int:
    global _claims
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — every positive claim in research_claims "
                    "must have a sample size large enough for its test method")
    ap.add_argument("--claims", metavar="PATH",
                    default=str(DEFAULT_CLAIMS))
    ap.add_argument("--json-out", metavar="PATH")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    claims_path = Path(args.claims)
    if not claims_path.exists():
        print(f"{GATE_LABEL}: FAIL — claims file not found: {claims_path}")
        return 1
    with open(claims_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        _claims = data.get("claims", [])
    elif isinstance(data, list):
        _claims = data
    else:
        print(f"{GATE_LABEL}: FAIL — claims file is not a list or dict")
        return 1

    print(f"{GATE_LABEL} — statistical power pre-check (SV-5b)")
    print(f"  claims file: {claims_path}")
    print(f"  n_claims:    {len(_claims)}")
    print(f"  thresholds:  "
          + ", ".join(f"{k}={v}" for k, v in METHOD_THRESHOLDS.items()
                      if k != "unknown"))
    print()

    evals = evaluate_claims(_claims)
    n_fail = n_warn = n_pass = 0
    for e in evals:
        if e.verdict == "fail":
            mark = "✗"
            n_fail += 1
        elif e.verdict == "warn":
            mark = "~"
            n_warn += 1
        else:
            mark = "✓"
            n_pass += 1
        print(f"  {mark} {e.claim_id:<4s}  method={e.method:<11s}  "
              f"N={str(e.effective_n):<5s}  req>={e.required_n:<4d}  "
              f"status_kind={e.status_kind:<12s}  [{e.verdict}]")
        print(f"      · {e.reason}")

    print()
    print(f"  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"{GATE_LABEL}: FAIL -- {inj_bad}/{n_inj} injections did "
              f"not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    print()

    # --- JSON report ---
    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "claims_path": str(claims_path),
        "thresholds": METHOD_THRESHOLDS,
        "n_claims": len(_claims),
        "evaluations": [
            {
                "claim_id": e.claim_id,
                "status": e.status,
                "status_kind": e.status_kind,
                "method": e.method,
                "method_keyword": e.method_keyword,
                "effective_n": e.effective_n,
                "n_source": e.n_source,
                "required_n": e.required_n,
                "verdict": e.verdict,
                "reason": e.reason,
            }
            for e in evals
        ],
        "counts": {"pass": n_pass, "warn": n_warn, "fail": n_fail},
        "injections": {"total": n_inj, "bad": inj_bad},
    }
    out_path = Path(args.json_out) if args.json_out else SCRIPTS / "_gate42_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"  report: {out_path}")

    # --- Verdict ---
    if n_fail:
        print(f"\n{GATE_LABEL}: FAIL — {n_fail} claim(s) positive but "
              f"under-powered")
        return 1
    if n_warn:
        print(f"\n{GATE_LABEL}: PASS — {n_pass} pass, {n_warn} acknowledged "
              f"boundary case(s) (already flagged in the claims file)")
    else:
        print(f"\n{GATE_LABEL}: PASS — all {n_pass} claims at or above "
              f"their power floor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
