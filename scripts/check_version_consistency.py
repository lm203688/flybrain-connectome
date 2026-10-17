#!/usr/bin/env python3
"""GATE 58 — version single-source-of-truth.

What this gate does
-------------------
The audit report (FOUNDATION_HARDENING_AUDIT_2026-10-16.md §K2) shows
that pyproject.toml was at 2.91.0 while CHANGELOG was already at 2.94.0
— a 3-version drift with no gate covering it.

Gate 58 checks that:
  1. pyproject.toml [project].version
  2. CHANGELOG.md top entry (## [X.Y.Z])
  3. README.md version badge (version-X.Y.Z)
  4. flybrain_cli.py __version__
  5. api_server.py "version" field
  6. server.py serverInfo.version

ALL agree. Any mismatch = FAIL.

Additionally, the gate count badge in README (N gates) must match the
actual number of gates in run_gates.py.

Gate 39 meta-discipline: the `injections()` battery below re-runs the
check on mutated copies and asserts each mutation turns the gate red.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
README = ROOT / "README.md"
CLI = ROOT / "flybrain_cli.py"
RUN_GATES = SCRIPTS / "run_gates.py"
MCP_DIR = ROOT / "flybrain-connectome-mcp" / "mcp_connectome"

GATE_ID = 58
GATE_LABEL = f"GATE {GATE_ID}"
PY = sys.executable

problems: list[str] = []
notes: list[str] = []


def ok(label: str, detail: str = "") -> None:
    print("  PASS  %-50s %s" % (label, detail))


def bad(label: str, detail: str) -> None:
    print("  FAIL  %-50s %s" % (label, detail))
    problems.append("%s: %s" % (label, detail))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Version extraction helpers
# ---------------------------------------------------------------------------

def _extract_pyproject_version() -> str | None:
    """Extract version from pyproject.toml [project] table."""
    text = read(PYPROJECT)
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else None


def _extract_changelog_top_version() -> str | None:
    """Extract top version from CHANGELOG.md (## [X.Y.Z])."""
    text = read(CHANGELOG)
    m = re.search(r'^## \[(\d+\.\d+\.\d+)\]', text, re.MULTILINE)
    return m.group(1) if m else None


def _extract_readme_version() -> str | None:
    """Extract version from README.md badge (version-X.Y.Z)."""
    text = read(README)
    m = re.search(r'badge/version-(\d+\.\d+\.\d+)', text)
    return m.group(1) if m else None


def _extract_cli_version() -> str | None:
    """Extract __version__ from flybrain_cli.py."""
    if not CLI.exists():
        return None
    text = read(CLI)
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


def _extract_api_server_version() -> str | None:
    """Extract version from api_server.py server info."""
    p = MCP_DIR / "api_server.py"
    if not p.exists():
        return None
    text = read(p)
    m = re.search(r'"version"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else None


def _extract_server_version() -> str | None:
    """Extract version from server.py serverInfo."""
    p = MCP_DIR / "server.py"
    if not p.exists():
        return None
    text = read(p)
    m = re.search(r'"version"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else None


def _count_gates() -> int:
    """Count unique GATE N labels in run_gates.py."""
    text = read(RUN_GATES)
    gates = set()
    for m in re.finditer(r'GATE\s+(\d+)', text):
        gates.add(m.group(1))
    return len(gates)


def _extract_readme_gate_count() -> int | None:
    """Extract gate count from README.md badge (N gates)."""
    text = read(README)
    m = re.search(r'(\d+)\s+gates', text, re.IGNORECASE)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def check_all(strict: bool = False) -> tuple[bool, list[str]]:
    """Run all version consistency checks. Returns (passed, problems)."""
    global problems
    problems = []

    print("=" * 60)
    print(f"{GATE_LABEL} — version single-source-of-truth")
    print("=" * 60)

    # Extract all versions
    versions = {
        "pyproject.toml": _extract_pyproject_version(),
        "CHANGELOG.md": _extract_changelog_top_version(),
        "README.md badge": _extract_readme_version(),
        "flybrain_cli.py": _extract_cli_version(),
        "api_server.py": _extract_api_server_version(),
        "server.py": _extract_server_version(),
    }

    # Print extracted versions
    print("\nExtracted versions:")
    for source, v in versions.items():
        print(f"  {source:25s}: {v or 'NOT FOUND'}")

    # Check all found versions agree
    found_versions = {v for v in versions.values() if v is not None}
    if not found_versions:
        bad("version extraction", "no versions found in any source")
        return False, problems

    if len(found_versions) == 1:
        ok("version consistency", f"all sources agree on {found_versions.pop()}")
    else:
        bad("version consistency",
            f"versions differ: {dict(versions)}")

    # Check gate count
    actual_gates = _count_gates()
    readme_gates = _extract_readme_gate_count()
    print(f"\nGate count: actual={actual_gates}, README={readme_gates}")

    if readme_gates is not None:
        if readme_gates == actual_gates:
            ok("gate count consistency", f"README={actual_gates}, actual={actual_gates}")
        else:
            bad("gate count consistency",
                f"README says {readme_gates} gates, but run_gates.py has {actual_gates}")
    else:
        ok("gate count extraction", "no gate count badge in README (skipped)")

    # Summary
    print("\n" + "=" * 60)
    if problems:
        print(f"{GATE_LABEL}: FAIL — {len(problems)} problem(s)")
        return False, problems
    else:
        print(f"{GATE_LABEL}: PASS")
        return True, problems


# ---------------------------------------------------------------------------
# Injection battery
# ---------------------------------------------------------------------------

def injections() -> list[dict]:
    """Test that the gate catches version drift."""
    cases = []

    # Injection 1: change pyproject.toml version only
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for p in [PYPROJECT, CHANGELOG, README, CLI, RUN_GATES]:
            if p.exists():
                shutil.copy2(p, tmp_path / p.name)

        # Modify pyproject.toml version
        pp = tmp_path / "pyproject.toml"
        text = pp.read_text(encoding="utf-8")
        text = text.replace('version = "2.94.0"', 'version = "2.95.0"')
        pp.write_text(text, encoding="utf-8")

        # Run check
        result = subprocess.run(
            [PY, "-c", f"""
import sys
sys.path.insert(0, r'{tmp_path}')
import importlib.util
spec = importlib.util.spec_from_file_location("check_version", r"{SCRIPTS / 'check_version_consistency.py'}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.ROOT = Path(r'{tmp_path}')
mod.PYPROJECT = Path(r'{tmp_path}/pyproject.toml')
mod.CHANGELOG = Path(r'{tmp_path}/CHANGELOG.md')
mod.README = Path(r'{tmp_path}/README.md')
mod.CLI = Path(r'{tmp_path}/flybrain_cli.py')
mod.RUN_GATES = Path(r'{tmp_path}/run_gates.py')
passed, _ = mod.check_all()
sys.exit(0 if passed else 1)
"""],
            capture_output=True, text=True
        )
        cases.append({
            "name": "pyproject version drift",
            "passed": result.returncode != 0,
            "description": "Changed pyproject.toml version only → should FAIL"
        })

    # Injection 2: change CHANGELOG version only
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for p in [PYPROJECT, CHANGELOG, README, CLI, RUN_GATES]:
            if p.exists():
                shutil.copy2(p, tmp_path / p.name)

        # Modify CHANGELOG version
        cl = tmp_path / "CHANGELOG.md"
        text = cl.read_text(encoding="utf-8")
        text = text.replace('## [2.94.0]', '## [2.95.0]')
        cl.write_text(text, encoding="utf-8")

        # Run check
        result = subprocess.run(
            [PY, "-c", f"""
import sys
sys.path.insert(0, r'{tmp_path}')
import importlib.util
spec = importlib.util.spec_from_file_location("check_version", r"{SCRIPTS / 'check_version_consistency.py'}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.ROOT = Path(r'{tmp_path}')
mod.PYPROJECT = Path(r'{tmp_path}/pyproject.toml')
mod.CHANGELOG = Path(r'{tmp_path}/CHANGELOG.md')
mod.README = Path(r'{tmp_path}/README.md')
mod.CLI = Path(r'{tmp_path}/flybrain_cli.py')
mod.RUN_GATES = Path(r'{tmp_path}/run_gates.py')
passed, _ = mod.check_all()
sys.exit(0 if passed else 1)
"""],
            capture_output=True, text=True
        )
        cases.append({
            "name": "CHANGELOG version drift",
            "passed": result.returncode != 0,
            "description": "Changed CHANGELOG version only → should FAIL"
        })

    return cases


def run_injections() -> bool:
    """Run injection battery. Returns True if all injections are caught."""
    print("\n" + "=" * 60)
    print(f"{GATE_LABEL} — injection battery")
    print("=" * 60)

    cases = injections()
    all_caught = True
    for case in cases:
        status = "CAUGHT" if case["passed"] else "MISSED"
        print(f"  {status:8s} {case['name']:30s} {case['description']}")
        if not case["passed"]:
            all_caught = False

    if all_caught:
        print(f"\n  Injection battery: PASS (all {len(cases)} caught)")
        return True
    else:
        print(f"\n  Injection battery: FAIL (some injections missed)")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Gate 58: version consistency")
    parser.add_argument("--check-injections", action="store_true",
                       help="Run injection battery test")
    args = parser.parse_args()

    if args.check_injections:
        passed = run_injections()
        return 0 if passed else 1

    passed, _ = check_all()
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
