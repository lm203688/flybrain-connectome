#!/usr/bin/env python3
"""Generate project_status.json — single source of truth for public docs.

P0-4 fix (2026-10-26 upgrade report):
Prior to this script, version numbers, gate counts, tool counts and
feature counts lived in separate hand-maintained strings across
README, docs/demo, Pages, CITATION.cff, papers and mcp server code.
They drifted: Pages said 58/58, actual was 60/62; docs said 36 tools,
actual was 47 MCP tools + 12 HTTP dispatch.

This script computes the values from the actual source of truth and
writes them to project_status.json. All docs should read from that
JSON instead of hard-coding numbers.

Usage:
    python scripts/gen_project_status.py              # write JSON
    python scripts/gen_project_status.py --check      # exit 1 if stale
    python scripts/gen_project_status.py --check --ci # stricter CI mode

Exit codes:
    0 — status file up-to-date (or written)
    1 --check detected drift (a doc claims X but truth is Y)
    2 — internal error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = ROOT / "project_status.json"


def _read_pyproject_version() -> str:
    """Read version from pyproject.toml (single source)."""
    p = ROOT / "pyproject.toml"
    if not p.exists():
        return "unknown"
    txt = p.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.MULTILINE)
    return m.group(1) if m else "unknown"


def _count_mcp_tools() -> int:
    """Count MCP TOOLS entries."""
    p = ROOT / "flybrain-connectome-mcp" / "mcp_connectome" / "server.py"
    if not p.exists():
        return 0
    txt = p.read_text(encoding="utf-8")
    return len(re.findall(r'^\s+"name"\s*:\s*"', txt, re.MULTILINE))


def _count_http_dispatch() -> int:
    """Count HTTP DISPATCH entries."""
    p = ROOT / "flybrain-connectome-mcp" / "mcp_connectome" / "api_server.py"
    if not p.exists():
        return 0
    txt = p.read_text(encoding="utf-8")
    # Match "tool_name": lambda patterns
    return len(re.findall(r'^\s+"[a-z_]+"[:=]\s*lambda', txt, re.MULTILINE))


def _count_cli_subcommands() -> int:
    """Count flybrain_cli.py subcommands via add_parser calls.

    The CLI uses `s = sub.add_parser("name", ...)` — `sub` is the local
    variable created by `ap.add_subparsers(...)` on line 1069. Match
    `.add_parser(` on any local name (typically `s`) to catch every one.
    """
    p = ROOT / "flybrain_cli.py"
    if not p.exists():
        return 0
    txt = p.read_text(encoding="utf-8")
    return len(re.findall(r'\bsub\.add_parser\s*\(', txt))


def _count_gates() -> int:
    """Count gate entries in run_gates.py."""
    p = ROOT / "scripts" / "run_gates.py"
    if not p.exists():
        return 0
    txt = p.read_text(encoding="utf-8")
    return len(re.findall(r'results\.append\(\("gate', txt))


def _run_quick_gates() -> tuple[int, int, list[str]]:
    """Run gates --quick and return (total, passed, failing_labels)."""
    py = sys.executable
    r = subprocess.run(
        [py, str(ROOT / "scripts" / "run_gates.py"), "--quick"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=900,
    )
    out = (r.stdout or "") + (r.stderr or "")
    total = 0
    passed = 0
    failing: list[str] = []
    for line in out.splitlines():
        m = re.match(r"^\s*gate(\d+)", line)
        if m and "PASS" in line:
            passed += 1
            total += 1
        elif m and "FAIL" in line:
            total += 1
            failing.append(line.strip())
    # Fallback: parse the summary line
    sm = re.search(r"GATES: (PASS|FAIL)\s+—\s+(\d+)/(\d+)", out)
    if sm:
        passed = int(sm.group(2))
        total = int(sm.group(3))
    return total, passed, failing


def _count_examples() -> int:
    p = ROOT / "examples"
    return len(list(p.glob("*.ipynb"))) if p.exists() else 0


def _collect(skip_gates: bool = False) -> dict:
    """Compute status dict from source of truth."""
    if skip_gates:
        total = passed = 0
        failing: list[str] = []
    else:
        total, passed, failing = _run_quick_gates()
    return {
        "schema_version": 1,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "project": {
            "name": "flybrain-connectome",
            "version": _read_pyproject_version(),
            "github": "https://github.com/lm203688/flybrain-connectome",
            "pypi": "https://pypi.org/project/flybrain-connectome/",
        },
        "capabilities": {
            "mcp_tools": _count_mcp_tools(),
            "http_dispatch": _count_http_dispatch(),
            "cli_subcommands": _count_cli_subcommands(),
            "gate_count": _count_gates(),
            "example_notebooks": _count_examples(),
        },
        "gates_quick": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "failing": failing,
            "healthy": total == passed and total > 0,
        },
        "transport_gap": {
            "mcp_only_tools": _count_mcp_tools() - _count_http_dispatch(),
            "note": "Tools declared in MCP but not reachable via HTTP /query.",
        },
    }


def _write(status: dict) -> None:
    STATUS_FILE.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote %s" % STATUS_FILE)


def _check(status: dict) -> int:
    """Compare against on-disk project_status.json and print drift."""
    if not STATUS_FILE.exists():
        print("FAIL  project_status.json does not exist")
        return 1
    try:
        disk = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print("FAIL  project_status.json not parseable: %s" % e)
        return 1

    problems: list[str] = []
    for key in ("version",):
        expected = status["project"].get(key)
        actual = disk.get("project", {}).get(key)
        if expected != actual:
            problems.append(f"project.{key}: disk={actual!r} truth={expected!r}")
    for k in ("mcp_tools", "http_dispatch", "cli_subcommands", "gate_count"):
        e = status["capabilities"][k]
        a = disk.get("capabilities", {}).get(k)
        if e != a:
            problems.append(f"capabilities.{k}: disk={a!r} truth={e!r}")

    if problems:
        print("FAIL  project_status.json drift:")
        for p in problems:
            print("  - %s" % p)
        return 1
    print("PASS  project_status.json matches truth")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="diff computed status against on-disk JSON; exit 1 on drift")
    ap.add_argument("--ci", action="store_true",
                    help="CI mode: also fail if quick gates are not green")
    ap.add_argument("--skip-gates", action="store_true",
                    help="don't invoke run_gates.py --quick; record gate totals as 0/0. "
                         "Used by scripts/check_project_status.py injection battery, "
                         "which needs a fast recompute path.")
    args = ap.parse_args()

    status = _collect(skip_gates=args.skip_gates)

    if args.check:
        rc = _check(status)
        if args.ci and not status["gates_quick"]["healthy"]:
            print("FAIL  --ci requested but quick gates not green: "
                  "%d/%d" % (status["gates_quick"]["passed"],
                             status["gates_quick"]["total"]))
            return 1
        return rc

    _write(status)
    if not status["gates_quick"]["healthy"] and not args.skip_gates:
        print("WARN  quick gates not green: %d/%d"
              % (status["gates_quick"]["passed"], status["gates_quick"]["total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
