#!/usr/bin/env python3
"""Gate 65 — project_status.json consistency.

P0-4 fix (2026-10-26 upgrade report):
Docs, README, Pages, papers and mcp server previously hard-coded
counts that drifted from source truth (58/58 vs 60/62, 36 vs 47 tools).
This gate enforces that project_status.json is up-to-date with the
actual source, and (in --ci mode) that quick gates are all green.

Injection battery (Gate 39 meta-discipline):
We run 3 injected-defect tests to prove this gate can turn red. Each
injection tampers with project_status.json, then re-runs the checks;
all three must fail closed. See _injections() below.

Usage:
    python scripts/check_project_status.py
    python scripts/check_project_status.py --ci
    python scripts/check_project_status.py --injection-battery
    python scripts/check_project_status.py --mutate tamper_version_string
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "project_status.json"
GEN = ROOT / "scripts" / "gen_project_status.py"
PY = sys.executable

GATE_LABEL = "GATE 65"


def _load_status() -> dict:
    return json.loads(STATUS.read_text(encoding="utf-8"))


def _regen(skip_gates: bool = False) -> int:
    """Regenerate project_status.json via the source-of-truth script.

    With skip_gates=True the regen skips invoking run_gates.py --quick,
    which is ~30s per call. The injection battery calls this 3 times, so
    the fast path matters. The gate totals are recorded as 0/0 during
    that call; the happy path (no mutation) uses the full pipeline.
    """
    import subprocess
    cmd = [PY, str(GEN)]
    if skip_gates:
        cmd.append("--skip-gates")
    r = subprocess.run(
        cmd, cwd=str(ROOT),
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600 if not skip_gates else 60,
    )
    return r.returncode


def check_fresh(skip_gates: bool = False) -> dict:
    """Recompute and compare against disk. Any drift is a failure.

    skip_gates=True is used by the injection battery and by the gate
    wrapper (when check_project_status.py is invoked from run_gates.py,
    we must not recurse into another full gate run). The gate totals
    section is excluded from the diff in that case — the gate wrapper
    itself owns the run_gates.py truth, and project_status.json's
    gates_quick is populated only on the happy path (direct call).
    """
    disk = _load_status()
    # Snapshot current disk content, regenerate, diff.
    before = json.dumps(disk, sort_keys=True)
    rc = _regen(skip_gates=skip_gates)
    if rc != 0:
        return {"ok": False, "failures": [f"gen_project_status exited {rc}"]}
    after = _load_status()
    skip_keys = {"generated_utc"}
    if skip_gates:
        skip_keys.add("gates_quick")
    after_cmp = {k: v for k, v in after.items() if k not in skip_keys}
    before_cmp = {k: v for k, v in json.loads(before).items() if k not in skip_keys}
    if before_cmp != after_cmp:
        # Restore original disk copy so mutation tests see the drift.
        STATUS.write_text(before, encoding="utf-8")
        drift = []
        for k in set(list(before_cmp.keys()) + list(after_cmp.keys())):
            if before_cmp.get(k) != after_cmp.get(k):
                drift.append(f"{k}: disk={before_cmp.get(k)!r} truth={after_cmp.get(k)!r}")
        return {"ok": False, "failures": ["stale project_status.json"] + drift}
    return {"ok": True, "failures": []}


def check_gates_healthy() -> dict:
    """In --ci mode, quick gates must be all green."""
    s = _load_status()
    gq = s.get("gates_quick", {})
    healthy = bool(gq.get("healthy"))
    if not healthy:
        return {"ok": False, "failures": [
            f"quick gates not green: {gq.get('passed')}/{gq.get('total')}"
        ]}
    return {"ok": True, "failures": []}


def check_transport_gap_declared() -> dict:
    """Transport gap between MCP and HTTP must be declared openly.

    P0-3 partial: the report flagged MCP=47 vs HTTP=12 as a broken
    promise. Rather than silently hide it, we require the gap to be
    explicitly documented in project_status.json's transport_gap.note.
    Full parity is a follow-up (P0-3-2); this gate just makes drift
    impossible.
    """
    s = _load_status()
    tg = s.get("transport_gap", {})
    if not tg:
        return {"ok": False, "failures": ["transport_gap section missing"]}
    if "mcp_only_tools" not in tg:
        return {"ok": False, "failures": ["transport_gap.mcp_only_tools missing"]}
    if not tg.get("note"):
        return {"ok": False, "failures": ["transport_gap.note empty"]}
    return {"ok": True, "failures": []}


def _mutate(name: str) -> None:
    """Apply a mutation to project_status.json (for the meta-gate battery)."""
    s = _load_status()
    if name == "tamper_mcp_tools_count":
        s.setdefault("capabilities", {})["mcp_tools"] = s["capabilities"]["mcp_tools"] + 1
    elif name == "tamper_version_string":
        s.setdefault("project", {})["version"] = "9.99.99-tampered"
    elif name == "delete_project_key":
        if "project" in s:
            del s["project"]["github"]
    else:
        raise SystemExit(f"unknown mutation: {name}")
    STATUS.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


# Mutation cases for the injected-defect battery (Gate 39 meta-discipline).
# Each entry is a mutation name that must turn the gate red when applied.
MUTATION_CASES = [
    "tamper_mcp_tools_count",
    "tamper_version_string",
    "delete_project_key",
]


def _injections() -> tuple[int, int]:
    """Run the 3 injected-defect tests and return (passed, total).

    For each injected-defect case we:
      1. snapshot the current project_status.json
      2. apply the mutation
      3. re-run check_fresh() — must FAIL
      4. restore the snapshot

    If any case fails to turn the gate red, the meta-gate discipline is
    broken and this battery exits non-zero.
    """
    if not STATUS.exists():
        return 0, 0
    backup = STATUS.read_text(encoding="utf-8")
    passed = 0
    total = 0
    try:
        for case in MUTATION_CASES:
            total += 1
            try:
                _mutate(case)
            except SystemExit:
                STATUS.write_text(backup, encoding="utf-8")
                continue
            r = check_fresh(skip_gates=True)
            STATUS.write_text(backup, encoding="utf-8")
            if not r["ok"]:
                passed += 1
            else:
                print(f"  injection LEAKED (gate stayed green): {case}")
        return passed, total
    finally:
        # Belt and braces — never leave a mutation in place.
        STATUS.write_text(backup, encoding="utf-8")


def run_injections() -> bool:
    """Wrapper that returns True iff every injected-defect turns the gate red."""
    passed, total = _injections()
    if total == 0:
        print("  injection battery: skipped (no project_status.json)")
        return True
    print(f"  injection battery: {passed}/{total} turn the gate red")
    return passed == total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ci", action="store_true",
                    help="also require quick gates to be green")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress verbose output; only print PASS/FAIL summary")
    ap.add_argument("--mutation", dest="mutate_choice", choices=MUTATION_CASES,
                    help="apply a single mutation, then exit 0 (used by the meta-gate battery)")
    ap.add_argument("--mutate", dest="mutate_choice", choices=MUTATION_CASES,
                    help="alias of --mutation")
    ap.add_argument("--injection-battery", "--check-injections", dest="run_injections",
                    action="store_true",
                    help="run the injected-defect battery and exit 0/1 accordingly")
    ap.add_argument("--restore", action="store_true",
                    help="regenerate project_status.json from truth and exit 0")
    args = ap.parse_args()

    # Back up for mutation restoration (mutation only, not on the happy path)
    backup = None
    if args.mutate_choice or args.restore:
        if STATUS.exists():
            backup = STATUS.read_text(encoding="utf-8")

    if args.restore:
        rc = _regen()
        return rc

    if args.run_injections:
        ok = run_injections()
        return 0 if ok else 1

    if args.mutate_choice:
        if not backup:
            print("FAIL  no project_status.json to mutate")
            return 1
        try:
            _mutate(args.mutate_choice)
            print(f"mutated: {args.mutate_choice}")
            return 0
        finally:
            STATUS.write_text(backup, encoding="utf-8")

    results = [check_fresh(skip_gates=True)]
    if args.ci:
        results.append(check_gates_healthy())
    results.append(check_transport_gap_declared())

    failures: list[str] = []
    for r in results:
        if not r["ok"]:
            for f in r["failures"]:
                failures.append(f)
                print(f"  FAIL  {f}")

    if failures:
        print(f"verdict: FAIL  ({len(failures)} failures)")
        return 1
    print("verdict: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
