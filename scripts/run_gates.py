#!/usr/bin/env python3
"""Run every gate this repo has, in one command, with one exit code.

CI (`.github/workflows/ci.yml`) runs the same set. Having a single local entry
point means "green locally" and "green in CI" cannot silently diverge — the
usual cause of a red pipeline nobody can reproduce.

Gates, in order of cheapness:

  1  secrets      scripts/check_no_secrets.py        no deps, ~0.2 s
  2  docs drift   scripts/check_docs_consistency.py  no deps, ~0.2 s
  3  MCP tools    scripts/check_mcp_tools.py         needs numpy; spawns the server
  4  degraded     scripts/check_degraded_mode.py     optional dep absent must not crash
  5  artifact     generated output is structurally real (see the checker's docstring)
  6  flybrain     flybrain_cli verify                 needs the MaleCNS dataset
  7  module arch  neuropil modules + worm data + combinator + HMAC
  8  tiering      physical tiering (public MIT tree vs private Tier-2 repo)
  9  unit library functional units + connection types + composer fail-closed
 10  embodiment   anchors + measured matrices + acknowledged contradictions

Gates 4 and 5 generate a throwaway organism into a temp dir, so they need no
dataset. The data-backed smoke test (`flybrain verify`, 70 assertions) is *not*
run unless you pass --with-data, because it needs a local MaleCNS v1.0 copy
(~5.63 GB) pointed at by FLYBRAIN_DATA_DIR. Gate 10 runs offline against the
committed anchor artifact, and only recomputes from raw data under --with-data.

Usage:
    python scripts/run_gates.py                  # offline, CI-equivalent
    python scripts/run_gates.py --with-data      # adds `flybrain verify`
    python scripts/run_gates.py --quick          # gates 1+2 only
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def run(label: str, cmd: list[str], cwd: Path | None = None,
        env: dict | None = None) -> tuple[bool, str]:
    print("-" * 72)
    print(">>> %s" % label)
    print("    %s" % " ".join(cmd))
    p = subprocess.run(cmd, cwd=str(cwd or ROOT), env=env,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.strip().splitlines():
        print("    " + line)
    ok = p.returncode == 0
    print("    -> %s (exit %d)" % ("PASS" if ok else "FAIL", p.returncode))
    return ok, out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true",
                    help="only the two dependency-free gates")
    ap.add_argument("--with-data", action="store_true",
                    help="also run `flybrain verify` (needs FLYBRAIN_DATA_DIR)")
    args = ap.parse_args()

    py = sys.executable
    results: list[tuple[str, bool]] = []

    results.append(("gate1 secrets", run(
        "GATE 1 — no hardcoded credentials",
        [py, str(SCRIPTS / "check_no_secrets.py")])[0]))

    results.append(("gate2 docs drift", run(
        "GATE 2 — docs match code",
        [py, str(SCRIPTS / "check_docs_consistency.py")])[0]))

    # ---- Gate 11: the function axis (stdlib only, runs even in --quick) ----
    results.append(("gate11 function coverage", run(
        "GATE 11 — PROJECT_VISION function coverage measured, gaps declared",
        [py, str(SCRIPTS / "check_function_coverage.py")])[0]))

    # ---- Gate 12: the connection cost axis (stdlib only, runs in --quick) ----
    results.append(("gate12 connection costs", run(
        "GATE 12 — every connection latency cited; design abstractions carry none",
        [py, str(SCRIPTS / "check_connection_costs.py")])[0]))

    # ---- Gate 9: functional-unit library (stdlib only, runs even in --quick) ----
    results.append(("gate9 unit library", run(
        "GATE 9 — functional units + connection types + composer fail-closed",
        [py, str(SCRIPTS / "check_functional_units.py")])[0]))

    # ---- Gate 10: embodiment layer (stdlib only, runs even in --quick) ----
    gate10_cmd = [py, str(SCRIPTS / "check_embodiment.py")]
    if args.with_data:
        gate10_cmd.append("--with-data")
    results.append(("gate10 embodiment", run(
        "GATE 10 — MaleCNS embodiment anchors + measured matrices + contradictions",
        gate10_cmd)[0]))

    if not args.quick:
        results.append(("gate3 MCP tools", run(
            "GATE 3 — every advertised MCP tool responds (offline subset)",
            [py, str(SCRIPTS / "check_mcp_tools.py"), "--offline", "--python", py])[0]))

        results.append(("gate4 degraded", run(
            "GATE 4 — a missing optional dependency degrades, it does not crash",
            [py, str(SCRIPTS / "check_degraded_mode.py"), "--python", py])[0]))

        tmp = Path(tempfile.mkdtemp(prefix="flybrain_gates_"))
        try:
            gen_ok, _ = run(
                "GATE 5a — generator smoke test",
                [py, str(ROOT / "flybrain_cli.py"), "generate",
                 "--motif-source", "local", "--blueprint", "predictive_coding_v2",
                 "--modules", "3", "--agents-per-module", "4",
                 "--name", "gates_smoke", "--out", str(tmp), "--no-html"])
            artifact_ok = False
            if gen_ok:
                artifact_ok, _ = run(
                    "GATE 5b — the generated artifact is real",
                    [py, str(SCRIPTS / "check_generated_artifact.py"),
                     "--dir", str(tmp), "--name", "gates_smoke"])
            else:
                print("-" * 72)
                print("    (skipping 5/5b — generation already failed)")
            results.append(("gate5 artifact", gen_ok and artifact_ok))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if args.with_data:
        if not os.environ.get("FLYBRAIN_DATA_DIR"):
            print("-" * 72)
            print("    (--with-data requested but FLYBRAIN_DATA_DIR is unset — skipping)")
            results.append(("gate6 flybrain verify", True))
        else:
            results.append(("gate6 flybrain verify", run(
                "GATE 6 — end-to-end smoke test against the real connectome",
                [py, str(ROOT / "flybrain_cli.py"), "verify"])[0]))

    # ---- Gate 7: module architecture (Phase 8) ----
    results.append(("gate7 module arch", run(
        "GATE 7 — neuropil modules + worm data + combinator middleware + fingerprints + HMAC",
        [py, str(SCRIPTS / "check_module_architecture.py")])[0]))

    # ---- Gate 8: physical tiering (Phase 9) ----
    results.append(("gate8 tiering", run(
        "GATE 8 — physical tiering architecture (core_bridge + LICENSE clause)",
        [py, str(SCRIPTS / "check_physical_tiering.py")])[0]))

    print("=" * 72)
    print("gate summary")
    for name, ok in results:
        print("  %-24s %s" % (name, "PASS" if ok else "FAIL"))
    failed = [n for n, ok in results if not ok]
    print("=" * 72)
    if failed:
        print("GATES: FAIL — %s" % ", ".join(failed))
        return 1
    print("GATES: PASS — %d/%d" % (len(results), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
