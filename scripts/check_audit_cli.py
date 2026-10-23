#!/usr/bin/env python3
"""GATE 64 — flybrain audit CLI subcommand integrity.

Why this exists
---------------
v3.00.1 added the ``flybrain audit`` CLI subcommand (P2-4 from the
FIVE_DIMENSION_UPGRADE report). It packages the project's most valuable
capability — PROV-JSON + structural integrity checking — as a standalone
command any user can run on any organism or swarmlabs JSON artifact.

This gate asserts:

  1. The ``audit`` subcommand is registered in ``flybrain_cli.py``
     (parser + handler + dispatch).
  2. ``flybrain audit <valid_organism>`` exits 0 (may have WARNs).
  3. ``flybrain audit <broken_organism>`` exits 1 (catches referential
     integrity violations, module mismatches, topology_profile drift).
  4. ``flybrain audit <nonexistent_file>`` exits 1.
  5. The audit handler actually inspects JSON structure (not a stub):
     feeding it a JSON with a broken edge.target must produce an ERROR.

Gate 39 meta-discipline honored: 3-mutation injection battery
(drop_edge_target, corrupt_module_id, drift_topology_profile) must all
turn the gate red.

Exit codes
----------
  0 — all checks pass
  1 — at least one check fails
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GATE_LABEL = "GATE 64"
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "flybrain_cli.py"
PY = sys.executable


def _run(args, timeout=30):
    """Run a command, return (exit_code, stdout, stderr)."""
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            cwd=str(ROOT),
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 99, "", "TIMEOUT"
    except Exception as e:
        return 99, "", str(e)


def check_cli_registered():
    """Check that 'audit' subcommand is in flybrain_cli.py."""
    txt = CLI.read_text(encoding="utf-8")
    checks = {
        "cmd_audit def": "def cmd_audit" in txt,
        "subparser audit": '"audit"' in txt and "cmd_audit" in txt,
        "set_defaults": "s.set_defaults(func=cmd_audit)" in txt,
    }
    failures = [k for k, v in checks.items() if not v]
    return {"ok": not failures, "failures": failures}


def check_valid_organism():
    """Run audit on the demo organism — should exit 0."""
    demo = ROOT / "flybrain-connectome-mcp" / "generated_organisms" / \
        "demo_predictive_coding_v2_m5_a8.json"
    if not demo.exists():
        return {"ok": False, "failures": ["demo organism not found"]}
    code, out, err = _run([PY, str(CLI), "audit", str(demo)])
    return {
        "ok": code == 0,
        "exit_code": code,
        "stdout_tail": out[-300:] if out else "",
        "failures": [] if code == 0 else ["expected exit 0, got %d" % code],
    }


def _make_broken_organism():
    """Write a temporary organism JSON with known defects."""
    bad = {
        "schema_version": "1.2.1",
        "kind": "virtual_organism",
        "organism": {
            "nodes": [
                {"id": "m0_a0", "role": "cell", "module": 0},
                {"id": "m0_a1", "role": "cell", "module": 0},
                {"id": "m1_a0", "role": "cell", "module": 1},
            ],
            "edges": [
                {"source": "m0_a0", "target": "m0_a1"},           # OK
                {"source": "m0_a0", "target": "nonexistent_node"}, # BROKEN
                {"from": "m0_rep", "to": "m0_rep",
                 "module": 0, "kind": "recurrent"},               # OK
                {"from": "m1_rep", "to": "m1_rep",
                 "module": 99, "kind": "recurrent"},              # BROKEN module
            ],
        },
        "module_profiles": {"0": {}, "1": {}},
        "metrics": {"n_nodes": 3, "n_edges": 4, "module_count": 2},
        "topology_profile": {"n_nodes": 999, "n_edges": 4},       # DRIFTED
    }
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="gate64_broken_",
        delete=False, dir=str(ROOT),
    )
    json.dump(bad, f)
    f.close()
    return f.name


def check_broken_organism():
    """Run audit on a broken organism — should exit 1 and catch 3 errors."""
    path = _make_broken_organism()
    try:
        code, out, err = _run([PY, str(CLI), "audit", path])
        failures = []
        if code != 1:
            failures.append("expected exit 1, got %d" % code)
        # Must catch at least 3 specific errors
        expected_patterns = [
            "target='nonexistent_node' not in nodes",
            "module=99 not in module_profiles",
            "topology_profile.n_nodes=999 != actual 3",
        ]
        for pat in expected_patterns:
            if pat not in out:
                failures.append("missing error: %s" % pat)
        return {
            "ok": not failures,
            "exit_code": code,
            "failures": failures,
            "stdout_tail": out[-500:] if out else "",
        }
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def check_nonexistent_file():
    """Run audit on a nonexistent file — should exit 1."""
    code, out, err = _run([PY, str(CLI), "audit", "/nonexistent/path.json"])
    return {
        "ok": code == 1,
        "exit_code": code,
        "failures": [] if code == 1 else ["expected exit 1, got %d" % code],
    }


def check_handler_not_stub():
    """Verify cmd_audit actually parses JSON and inspects structure.

    A stub handler that just prints "ok" and exits 0 would pass the
    valid-organism test but fail here: feeding it a broken JSON should
    produce at least one ERROR line.
    """
    path = _make_broken_organism()
    try:
        code, out, err = _run([PY, str(CLI), "audit", path])
        has_error_section = "[audit] ERRORS" in out
        has_x_prefix = " x " in out  # 'x' prefix on error lines
        return {
            "ok": has_error_section and has_x_prefix,
            "failures": [] if (has_error_section and has_x_prefix)
                else ["handler does not produce ERROR section or ' x ' lines"],
        }
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_injections():
    """3-mutation injection battery — all must turn gate red."""
    cases = [
        ("drop_edge_target",
         {"organism": {"nodes": [{"id": "m0_a0", "role": "cell"}],
                       "edges": [{"source": "m0_a0", "target": "gone"}]}}),
        ("corrupt_module_id",
         {"organism": {"nodes": [{"id": "m0_a0", "role": "cell", "module": 77}],
                       "edges": []},
          "module_profiles": {"0": {}}}),
        ("drift_topology_profile",
         {"organism": {"nodes": [{"id": "m0_a0", "role": "cell"}],
                       "edges": []},
          "topology_profile": {"n_nodes": 999}}),
    ]
    print("=" * 60)
    print("GATE 64 — injection battery")
    print("=" * 60)
    bad = 0
    for name, extra in cases:
        base = {
            "schema_version": "1.2.1",
            "kind": "virtual_organism",
            "organism": {"nodes": [], "edges": []},
            "module_profiles": {},
        }
        base.update(extra)
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix="gate64_inject_",
            delete=False, dir=str(ROOT),
        )
        json.dump(base, f)
        f.close()
        try:
            code, out, err = _run([PY, str(CLI), "audit", f.name])
            caught = code == 1
        finally:
            try:
                os.unlink(f.name)
            except OSError:
                pass
        if not caught:
            bad += 1
        flag = "OK " if caught else "MISS"
        print(f"  [{flag}] {name:<28} -> exit {code}")
    print("=" * 60)
    total = len(cases)
    print(f"injected-defect battery: {total - bad}/{total} caught")
    return 0 if bad == 0 else 1


def check():
    """Run all gate checks, return a report dict."""
    results = {
        "cli_registered": check_cli_registered(),
        "valid_organism": check_valid_organism(),
        "broken_organism": check_broken_organism(),
        "nonexistent_file": check_nonexistent_file(),
        "handler_not_stub": check_handler_not_stub(),
    }
    n_failures = sum(1 for r in results.values() if not r["ok"])
    return {
        "gate": GATE_LABEL,
        "verdict": "PASS" if n_failures == 0 else "FAIL",
        "n_failures": n_failures,
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{GATE_LABEL} — flybrain audit CLI integrity"
    )
    ap.add_argument("--inject", action="store_true",
                    help="run the mutation injection battery")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.inject:
        return run_injections()

    rep = check()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["verdict"] == "PASS" else 1
    if args.quiet:
        print(f"{GATE_LABEL}: {rep['verdict']}  (failures={rep['n_failures']})")
        return 0 if rep["verdict"] == "PASS" else 1

    print("=" * 60)
    print(f"{GATE_LABEL} — flybrain audit CLI integrity")
    print("=" * 60)
    for name, r in rep["results"].items():
        status = "PASS" if r["ok"] else "FAIL"
        print(f"  [{status}] {name}")
        for f in r.get("failures", []):
            print(f"         {f}")
        if "exit_code" in r:
            print(f"         (exit_code={r['exit_code']})")
    print("=" * 60)
    print(f"verdict: {rep['verdict']}  (failures={rep['n_failures']})")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())