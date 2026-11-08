"""Functional unit CRUD tests (P1-5).

Tests the CRUD API in functional_unit_crud.py and MCP integration.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CRUD = ROOT / "flybrain-connectome-mcp" / "functional_unit_crud.py"
SERVER = ROOT / "flybrain-connectome-mcp" / "mcp_connectome" / "server.py"
PY = sys.executable
ENV = dict(os.environ)
ENV["PYTHONIOENCODING"] = "utf-8"


def _run_cli(args):
    """Run CRUD CLI with UTF-8 IO (Windows GBK otherwise corrupts Chinese)."""
    return subprocess.run([PY, str(CRUD)] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=ENV)


def test_crud_cli():
    """Test CRUD CLI interface."""
    # list (should be 116 units)
    r = _run_cli(["list"])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert len(data) == 116
    assert "retinal_phototransduction_unit" in data

    # get existing unit
    r = _run_cli(["get", "retinal_phototransduction_unit"])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["name"] == "retinal_phototransduction_unit"

    # get non-existing unit
    r = _run_cli(["get", "nonexistent_unit"])
    assert r.returncode == 0
    data = r.stdout
    assert "NOT FOUND" in data


def test_crud_api():
    """Test CRUD API functions directly."""
    sys.path.insert(0, str(ROOT / "flybrain-connectome-mcp"))
    from functional_unit_crud import list_units, get_unit, add_unit, update_unit, delete_unit

    # list
    units = list_units()
    assert len(units) == 116
    assert "retinal_phototransduction_unit" in [u["name"] for u in units]

    # get existing
    unit = get_unit("retinal_phototransduction_unit")
    assert unit is not None
    assert unit["name"] == "retinal_phototransduction_unit"

    # get non-existing
    unit = get_unit("nonexistent_unit")
    assert unit is None


def test_crud_mcp_integration():
    """Test MCP integration via server.py."""
    sys.path.insert(0, str(SERVER.parent))
    import server

    # list_crud_units
    r = server.handle_call("list_crud_units", {})
    data = json.loads(r) if isinstance(r, str) else r
    assert "unit_count" in data
    assert data["unit_count"] == 116

    # get_crud_unit (existing)
    r = server.handle_call("get_crud_unit", {"name": "retinal_phototransduction_unit"})
    data = json.loads(r) if isinstance(r, str) else r
    assert data["name"] == "retinal_phototransduction_unit"

    # get_crud_unit (non-existing)
    r = server.handle_call("get_crud_unit", {"name": "nonexistent_unit"})
    data = json.loads(r) if isinstance(r, str) else r
    assert data["status"] == "error"
    assert "no such functional unit" in data["error"]


def test_crud_validation():
    """Test CRUD validation (fail-closed)."""
    sys.path.insert(0, str(ROOT / "flybrain-connectome-mcp"))
    from functional_unit_crud import add_unit

    # Missing required fields
    invalid_unit = {"name": "test"}  # missing most required fields
    r = add_unit(invalid_unit)
    assert r["ok"] is False
    assert len(r["errors"]) > 0

    # Duplicate name
    valid_unit = {
        "name": "retinal_phototransduction_unit",  # already exists
        "display": "Test",
        "function": "test",
        "system": "test",
        "description": "test",
        "members": [],
        "internal_wiring": [],
        "ports": {"in": [], "out": []},
        "size_range": [1, 10],
        "motif_source": "test",
        "capability": "test",
        "task_hint_pool": []
    }
    r = add_unit(valid_unit)
    assert r["ok"] is False
    assert "存在" in r["errors"][0] or "already exists" in r["errors"][0]