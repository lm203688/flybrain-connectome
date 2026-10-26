"""Unit tests for scripts/gen_project_status.py + check_project_status.py.

P0-4 fix coverage: the JSON status file must be a stable single source
of truth for the counts README, Pages, papers and the MCP server all
reference. These tests cover the compute function, the JSON shape, and
the gate-65 injection battery that proves the gate can turn red.

The tests are deliberately fast: they use the --skip-gates fast path so
a single test-suite run stays under a few seconds.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "scripts" / "gen_project_status.py"
CHECK = ROOT / "scripts" / "check_project_status.py"
STATUS = ROOT / "project_status.json"
PY = sys.executable


@pytest.fixture(scope="module")
def status_json() -> dict:
    """Regenerate project_status.json once per module and return it."""
    r = subprocess.run(
        [PY, str(GEN), "--skip-gates"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(STATUS.read_text(encoding="utf-8"))


def test_status_json_schema_version() -> None:
    with STATUS.open(encoding="utf-8") as fh:
        s = json.load(fh)
    assert s["schema_version"] == 1


def test_status_json_project_version_matches_pyproject(status_json: dict) -> None:
    """The status file must echo pyproject.toml's version string."""
    pyp = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in pyp.splitlines():
        if line.startswith("version = "):
            py_ver = line.split("=")[1].strip().strip('"')
            break
    else:
        pytest.fail("no version = in pyproject.toml")
    assert status_json["project"]["version"] == py_ver


def test_status_json_capabilities_present(status_json: dict) -> None:
    caps = status_json["capabilities"]
    for k in ("mcp_tools", "http_dispatch", "cli_subcommands",
              "gate_count", "example_notebooks"):
        assert k in caps, f"missing capabilities.{k}"
        assert isinstance(caps[k], int), f"capabilities.{k} not int"


def test_status_json_mcp_tools_at_least_40(status_json: dict) -> None:
    """Sanity: 47 MCP tools expected as of v3.01.2."""
    assert status_json["capabilities"]["mcp_tools"] >= 40


def test_status_json_transport_gap_declared(status_json: dict) -> None:
    """P0-3 partial: transport gap must be openly declared."""
    tg = status_json["transport_gap"]
    assert "mcp_only_tools" in tg
    assert tg["mcp_only_tools"] > 0, "MCP tools should exceed HTTP dispatch"
    assert tg.get("note"), "transport_gap.note must not be empty"


def test_check_project_status_happy_path() -> None:
    """check_project_status.py must PASS on the current on-disk file."""
    r = subprocess.run(
        [PY, str(CHECK)],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_project_status_injection_battery() -> None:
    """Gate 65's 3-injection battery must turn the gate red."""
    r = subprocess.run(
        [PY, str(CHECK), "--injection-battery"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "3/3" in r.stdout, r.stdout
