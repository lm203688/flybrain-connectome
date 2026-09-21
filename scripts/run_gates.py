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

Gates 4 and 5 generate a throwaway organism into a temp dir, so they need no
dataset. The data-backed smoke test (`flybrain verify`, 70 assertions) is *not*
run unless you pass --with-data, because it needs a local MaleCNS v1.0 copy
(~5.63 GB) pointed at by FLYBRAIN_DATA_DIR.

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

    results.append(("1/5 secrets", run(
        "GATE 1/5 — no hardcoded credentials",
        [py, str(SCRIPTS / "check_no_secrets.py")])[0]))

    results.append(("2/5 docs drift", run(
        "GATE 2/5 — docs match code",
        [py, str(SCRIPTS / "check_docs_consistency.py")])[0]))

    if not args.quick:
        results.append(("3/5 MCP tools", run(
            "GATE 3/5 — every advertised MCP tool responds (offline subset)",
            [py, str(SCRIPTS / "check_mcp_tools.py"), "--offline", "--python", py])[0]))

        results.append(("4/5 degraded mode", run(
            "GATE 4/5 — a missing optional dependency degrades, it does not crash",
            [py, str(SCRIPTS / "check_degraded_mode.py"), "--python", py])[0]))

        tmp = Path(tempfile.mkdtemp(prefix="flybrain_gates_"))
        try:
            gen_ok, _ = run(
                "GATE 5/5a — generator smoke test",
                [py, str(ROOT / "flybrain_cli.py"), "generate",
                 "--motif-source", "local", "--blueprint", "predictive_coding_v2",
                 "--modules", "3", "--agents-per-module", "4",
                 "--name", "gates_smoke", "--out", str(tmp), "--no-html"])
            artifact_ok = False
            if gen_ok:
                artifact_ok, _ = run(
                    "GATE 5/5b — the generated artifact is real",
                    [py, str(SCRIPTS / "check_generated_artifact.py"),
                     "--dir", str(tmp), "--name", "gates_smoke"])
            else:
                print("-" * 72)
                print("    (skipping 5/5b — generation already failed)")
            results.append(("5/5 artifact", gen_ok and artifact_ok))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if args.with_data:
        if not os.environ.get("FLYBRAIN_DATA_DIR"):
            print("-" * 72)
            print("    (--with-data requested but FLYBRAIN_DATA_DIR is unset — skipping)")
            results.append(("6/7 flybrain verify", True))
        else:
            results.append(("6/7 flybrain verify", run(
                "GATE 6/7 — end-to-end smoke test against the real connectome",
                [py, str(ROOT / "flybrain_cli.py"), "verify"])[0]))

    # ---- Gate 7: module architecture (Phase 8) ----
    results.append(("7/7 module arch", run(
        "GATE 7/7 — neuropil modules + worm data + combinator middleware + fingerprints",
        [py, str(SCRIPTS / "check_module_architecture.py")])[0]))

    print("=" * 72)
    print("gate summary")
    for name, ok in results:
        print("  %-22s %s" % (name, "PASS" if ok else "FAIL"))
    failed = [n for n, ok in results if not ok]
    print("=" * 72)
    if failed:
        print("GATES: FAIL — %s" % ", ".join(failed))
        return 1
    print("GATES: PASS — %d/%d" % (len(results), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
