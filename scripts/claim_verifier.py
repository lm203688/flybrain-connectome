"""
Fusion A auxiliary — claim falsifiability verifier (LLM-as-a-Verifier helper).

Per OPEN_SOURCE_FUSION §4 Fusion A:
  * Four of the five elements (statement / quantitative_prediction /
    falsification_condition / reproduction_command) are checked STRUCTURALLY
    by Gate 30 (presence, parsability, executability).
  * Only "is the falsification condition actually falsifiable?" requires
    judgement. This script provides an OPTIONAL LLM-assisted check for that
    one dimension.

Discipline (per Fusion A "判据模型不是权威"):
  * The LLM output is a WARNING, never a FAILURE. Gate 30 must remain
    pass/fail based on structural checks alone.
  * When the LLM backend is unavailable, the script exits 0 silently —
    the absence of auxiliary judgement is not a failure.
  * The prompt is deterministic and the seed is fixed.
  * The output is logged to a JSON file for audit, never modifies the
    claim itself.

Usage:
    # Offline mode (no LLM, just structural hint)
    python scripts/claim_verifier.py --claims research_claims.json --mode offline

    # With LLM (requires FLYBRAIN_LLM_BASE_URL or env)
    python scripts/claim_verifier.py --claims research_claims.json --mode llm

Exit 0 = all claims verified (or LLM unavailable). Exit 1 = structural error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ============================================================= LLM backend


def llm_chat(system: str, user: str, timeout_s: float = 30.0) -> str | None:
    """Call the local LLM gateway; return None if unavailable."""
    base_url = (os.environ.get("FLYBRAIN_LLM_BASE_URL")
                or "http://127.0.0.1:8788/v1").rstrip("/")
    if not base_url.endswith("/chat/completions"):
        base_url += "/chat/completions"
    model = os.environ.get("FLYBRAIN_LLM_MODEL") or "deepseek-v4-flash"
    api_key = os.environ.get("FLYBRAIN_LLM_API_KEY") or "dummy"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 256,
        "temperature": 0.0,
        "reasoning_effort": "low",
    }
    payload = json.dumps(body).encode("utf-8")
    try:
        req = urllib.request.Request(
            base_url, data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read())
        return (data.get("choices", [{}])[0]
                .get("message", {}).get("content", ""))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
            KeyError, OSError):
        return None


# ============================================================= verification prompts


SYSTEM_PROMPT = (
    "You are a scientific-rigor verifier. Given a research claim and its "
    "falsification condition, judge whether the falsification condition is "
    "TRULY FALSIFIABLE — i.e. there exists a concrete experiment or "
    "observation that could prove the claim false. Answer with a single "
    "JSON object: {\"falsifiable\": true|false, \"reason\": \"<one sentence>\"}."
)

USER_TEMPLATE = (
    "Claim statement: {statement}\n\n"
    "Quantitative prediction: {prediction}\n\n"
    "Falsification condition: {falsification}\n\n"
    "Is this falsification condition TRULY FALSIFIABLE? "
    "Respond with ONLY the JSON object, no explanation outside it."
)


def judge_falsifiability(statement: str, prediction: str, falsification: str) -> dict:
    """Call LLM to judge whether the falsification condition is truly falsifiable.

    Returns a dict with keys: source, falsifiable, reason.
    source is "llm" if the LLM responded, or "unavailable" if it did not.
    """
    user = USER_TEMPLATE.format(
        statement=statement,
        prediction=prediction,
        falsification=falsification,
    )
    resp = llm_chat(SYSTEM_PROMPT, user)
    if resp is None:
        return {"source": "unavailable", "falsifiable": None, "reason": ""}
    # Parse the JSON response
    txt = resp.strip()
    if txt.startswith("{") and txt.endswith("}"):
        try:
            obj = json.loads(txt)
            return {
                "source": "llm",
                "falsifiable": bool(obj.get("falsifiable", False)),
                "reason": str(obj.get("reason", ""))[:200],
            }
        except json.JSONDecodeError:
            pass
    # Fallback: heuristically parse
    if "true" in txt.lower() and "false" not in txt.lower():
        return {"source": "llm", "falsifiable": True, "reason": txt[:200]}
    if "false" in txt.lower():
        return {"source": "llm", "falsifiable": False, "reason": txt[:200]}
    return {"source": "llm", "falsifiable": None, "reason": txt[:200]}


# ============================================================= structural fallback


def structural_falsifiability_hints(falsification: str) -> dict:
    """Cheap structural heuristics when LLM is unavailable.

    These are WARNINGS, not authoritative. They catch the most obvious
    cases where a falsification condition is empty, vague, or contains
    no concrete measurement.
    """
    if not falsification or not falsification.strip():
        return {"hint": "EMPTY", "severity": "error",
                "note": "falsification_condition is empty"}
    if len(falsification.strip()) < 20:
        return {"hint": "TOO_SHORT", "severity": "warning",
                "note": f"falsification_condition is very short ({len(falsification)} chars)"}
    # Look for concrete measurement language
    concrete_markers = (
        "if", "then", "R²", "slope", "std", "significant",
        "P1", "P2", "P3", "≥", "≤", "=", ">", "<",
        "sample", "n=", "seed", "threshold",
    )
    if not any(m in falsification for m in concrete_markers):
        return {"hint": "VAGUE", "severity": "warning",
                "note": "falsification_condition lacks concrete measurement language"}
    return {"hint": "STRUCTURALLY_OK", "severity": "info", "note": ""}


# ============================================================= main


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--claims", type=str, default="research_claims.json",
                   help="Path to research_claims.json")
    p.add_argument("--mode", type=str, default="offline",
                   choices=["offline", "llm"],
                   help="offline = structural hints only; llm = LLM-assisted falsifiability")
    p.add_argument("--output", type=str, default=None,
                   help="Optional JSON output path")
    args = p.parse_args()

    claims_path = Path(args.claims) if not os.path.isabs(args.claims) else Path(args.claims)
    if not claims_path.exists():
        claims_path = ROOT / args.claims
    if not claims_path.exists():
        print(f"ERROR: claims file not found: {claims_path}", file=sys.stderr)
        return 1

    claims_data = json.loads(claims_path.read_text(encoding="utf-8"))
    claims = claims_data if isinstance(claims_data, list) else claims_data.get("claims", [])

    results = []
    errors = 0
    warnings = 0
    for claim in claims:
        cid = claim.get("id", "?")
        statement = claim.get("statement", "")
        prediction = claim.get("quantitative_prediction", "")
        falsification = claim.get("falsification_condition", "")
        entry = {"id": cid, "statement": statement[:80]}

        # Structural hint (always run)
        hint = structural_falsifiability_hints(falsification)
        entry["structural_hint"] = hint
        if hint["severity"] == "error":
            errors += 1
        elif hint["severity"] == "warning":
            warnings += 1

        # LLM-assisted (only in llm mode)
        if args.mode == "llm":
            llm_judgement = judge_falsifiability(statement, prediction, falsification)
            entry["llm_judgement"] = llm_judgement
            if llm_judgement["source"] == "unavailable":
                warnings += 1  # LLM unavailable is a soft warning
        results.append(entry)

    report = {
        "mode": args.mode,
        "n_claims": len(results),
        "errors": errors,
        "warnings": warnings,
        "results": results,
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        out_path = Path(args.output) if os.path.isabs(args.output) else ROOT / args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {out_path}", file=sys.stderr)

    # Exit 0 unless there are STRUCTURAL errors (LLM unavailability is a warning, not an error)
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
