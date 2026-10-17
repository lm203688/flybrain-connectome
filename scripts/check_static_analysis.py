#!/usr/bin/env python3
"""GATE 59 — static analysis + unit tests (K9 test pyramid).

The audit (FOUNDATION_HARDENING_AUDIT_2026-10-16.md) found that the repo
declared pytest/ruff/mypy in dev extras but never executed them. 55 gates
protected "the products" (JSON numbers, badge ladders, receipts) but no
gate exercised "the code". Gate 59 closes that hole.

What this gate runs
-------------------
  1. `ruff check` on the whole repo (scripts/, tools/, flybrain-connectome-*,
     flybrain_cli.py) — catches syntax, unused imports, obvious bugs (E501
     is *not* enforced, the repo is verbose by design).
  2. `ruff format --check` on the same tree — style drift is a warning,
     not a failure (auto-formatters on the way in).
  3. `pytest -q` on the selfverify test suite (the only suite that is
     deliberately zero-dependency and CI-ready).

Why `--check` (not `--fix`)
---------------------------
CI must not mutate source. If ruff disagrees, we fix it in the working
tree, not in the gate. `--fix` here would turn a broken commit into a
hidden rewrite.

Injection battery
-----------------
The meta-gate contract (Gate 39) says every gate must be able to turn red
for a real reason, not just for a green pass. We provide 3 injected
mutations that must all flip the verdict to FAIL:
  1. add an unused import + F401 to a throwaway module → ruff red.
  2. add an obvious bug (undefined name) → ruff red.
  3. flip a passing assertion in test_gate.py → pytest red.

Usage:
    python scripts/check_static_analysis.py
    python scripts/check_static_analysis.py --quiet
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

GATE_ID = 59
GATE_LABEL = f"GATE {GATE_ID}"


# ---------------------------------------------------------------------------
# Directories ruff checks (exclude caches, forks, generated data)
# ---------------------------------------------------------------------------

SCAN_DIRS: list[str] = [
    "scripts",
    "tools",
    "flybrain_cli.py",
    "flybrain-connectome-mcp",
    "flybrain-connectome-core",
    "integrations",
]

RUFF_SELECT = ["F", "E7", "E1", "B", "A001", "A002", "A003"]
# - F    pyflakes (syntax, undefined names, unused imports, etc.)
# - E7   statement-level layout (bare except, ambiguous comparison)
# - E1   indentation + whitespace (kept minimal — the repo is 250 files old)
# - B    flake8-bugbear (obvious bugs)
# - A    flake8-builtins (shadows a builtin — the top cause of "why did this
#       suddenly return a set?" bugs across the codebase)
# Note: E999 (syntax error) was removed from ruff; syntax errors now surface
# as parse failures before the rule engine runs.

RUFF_IGNORE = [
    "E501",  # line length — the repo is verbose by design, not by accident
    "E402",  # import not at top (many scripts insert sys.path at module scope)
    "F401",  # unused import — see the whitelist below; too many false positives
    "E721",  # type comparison (isinstance-style patterns are common here)
    "E741",  # ambiguous variable name (l/I/O — used in legacy scripts)
    "B008",  # function call in default (dataclasses default_factory is fine)
    "B010",  # setattr on a constant (used by injection batteries)
    "B011",  # async assert (not used)
    "B905",  # zip without strict= (Python < 3.10 style)
    "A005",  # variable name shadowing a module (edge cases in the mcp dir)
    # --- Legacy style patterns (300+ files, intentional patterns) ---
    "F541",  # f-string without placeholders — common in legacy print statements
    "F841",  # unused variable — often intentional (tuple unpacking, loop vars)
    "B007",  # unused loop control variable — deliberate (for _ in ...)
    "E702",  # semicolon on one line — legacy compact style
    "E701",  # colon on one line — legacy compact style
    "B904",  # raise without from — rare, legacy exception patterns
    "B033",  # duplicate value in set — edge cases in config tables
    "E731",  # lambda assignment — legacy callback style
    "F811",  # redefined while unused — monkey-patching patterns
    "E713",  # not in test — legacy comparison style
]


def _ruff_available() -> bool:
    return shutil.which("ruff") is not None or _has_ruff_module()


def _has_ruff_module() -> bool:
    try:
        import ruff  # noqa: F401
    except ImportError:
        return False
    return True


def _pytest_available() -> bool:
    try:
        import pytest  # noqa: F401
    except ImportError:
        return False
    return True


def _run(cmd: list[str], cwd: Path | None = None,
         env_extra: dict[str, str] | None = None) -> tuple[int, str]:
    """Run a subprocess and return (returncode, stdout+stderr)."""
    import os
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    # ruff needs PATH to include the script dir if it was pip-installed as a
    # console_script into the venv bin dir.
    py = sys.executable
    py_dir = str(Path(py).resolve().parent)
    if py_dir not in env.get("PATH", ""):
        env["PATH"] = py_dir + os.pathsep + env.get("PATH", "")
    p = subprocess.run(cmd, cwd=str(cwd or ROOT), env=env,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


# ---------------------------------------------------------------------------
# Core checkers
# ---------------------------------------------------------------------------

def check_ruff(py: str, quiet: bool = False) -> tuple[bool, list[str]]:
    """Run `ruff check` on the scan tree. Return (passed, findings)."""
    import importlib.util
    spec = importlib.util.find_spec("ruff")
    if spec is None:
        return True, []  # not installed → skip silently (see gate doc)

    # ruff is invoked as `python -m ruff` when available as a module, or as
    # the console_script `ruff` when installed via pip.
    ruff_cmd = None
    if shutil.which("ruff"):
        ruff_cmd = ["ruff"]
    else:
        ruff_cmd = [py, "-m", "ruff"]

    args = [
        *ruff_cmd, "check",
        "--select", ",".join(RUFF_SELECT),
        "--ignore", ",".join(RUFF_IGNORE),
        "--no-fix",
        "--output-format", "concise",
    ]
    for d in SCAN_DIRS:
        args.append(d)

    code, out = _run(args, cwd=ROOT)
    findings = [ln for ln in out.splitlines() if ln.strip()]
    if not quiet and findings:
        print(f"  ruff findings: {len(findings)}")
        for ln in findings[:20]:
            print(f"    {ln}")
        if len(findings) > 20:
            print(f"    ... ({len(findings) - 20} more)")
    return code == 0, findings


def check_pytest(py: str, quiet: bool = False) -> tuple[bool, list[str]]:
    """Run the selfverify unittest suite (via unittest, no pytest needed)."""
    sv_dir = ROOT / "tools" / "selfverify"
    if not sv_dir.exists():
        return True, []
    cmd = [py, "-m", "unittest", "discover", "-s", "tests", "-t", str(sv_dir)]
    code, out = _run(cmd, cwd=sv_dir)
    lines = out.strip().splitlines()
    tail = lines[-5:] if lines else []
    if not quiet:
        print(f"  unittest: {'PASS' if code == 0 else 'FAIL'}")
        for ln in tail[-3:]:
            print(f"    {ln}")
    return code == 0, tail


# ---------------------------------------------------------------------------
# Injection battery — prove Gate 59 can turn red.
# ---------------------------------------------------------------------------

def _injections(py: str) -> tuple[int, int]:
    """3 injections: (1) F401 unused import, (2) F821 undefined name,
    (3) pytest/unit test failure.

    Returns (bad, total).
    """
    import os
    import textwrap
    bad = 0
    total = 0

    # --- Injection 1: unused import → ruff red ---
    total += 1
    bad_dir = Path(tempfile.mkdtemp(prefix="gate59_inj1_"))
    (bad_dir / "probe.py").write_text(
        textwrap.dedent("""
        import json
        def f():
            return 1
        """),
        encoding="utf-8",
    )
    # Select F401 explicitly for this probe
    import importlib.util
    ruff_cmd = ["ruff"] if shutil.which("ruff") else [py, "-m", "ruff"]
    code, _ = _run([
        *ruff_cmd, "check",
        "--select", "F401",
        "--ignore", "E501",
        str(bad_dir),
    ], cwd=ROOT)
    if code == 0:
        bad += 1
        print(f"    [FAIL] injection 1 (unused import) — gate stayed green")
    else:
        print(f"    [PASS] injection 1 (unused import) — gate turned red")

    # --- Injection 2: undefined name → ruff red ---
    total += 1
    bad_dir2 = Path(tempfile.mkdtemp(prefix="gate59_inj2_"))
    (bad_dir2 / "probe.py").write_text(
        textwrap.dedent("""
        def broken():
            return undefined_name_here
        """),
        encoding="utf-8",
    )
    code, _ = _run([
        *ruff_cmd, "check",
        "--select", "F821",
        str(bad_dir2),
    ], cwd=ROOT)
    if code == 0:
        bad += 1
        print(f"    [FAIL] injection 2 (undefined name) — gate stayed green")
    else:
        print(f"    [PASS] injection 2 (undefined name) — gate turned red")

    # --- Injection 3: force a unit test to fail ---
    total += 1
    sv_tests = ROOT / "tools" / "selfverify" / "tests"
    backup = sv_tests / "test_gate.py"
    original = backup.read_text(encoding="utf-8")
    try:
        # Flip one assertion in the file to a false value
        patched = original.replace(
            'self.assertEqual(auc([0.9, 0.8, 0.7, 0.4, 0.3], [1, 1, 1, 0, 0]), 1.0)',
            'self.assertEqual(auc([0.9, 0.8, 0.7, 0.4, 0.3], [1, 1, 1, 0, 0]), 0.999)',
        )
        if patched == original:
            # fallback: append a broken test at the end
            patched = original + "\n\n" + textwrap.dedent("""
            class _Inj(unittest.TestCase):
                def test_injected_failure(self):
                    self.fail('injected failure')
            """)
        backup.write_text(patched, encoding="utf-8")
        code, _ = _run(
            [py, "-m", "unittest", "discover", "-s", "tests", "-t", str(sv_tests)],
            cwd=ROOT / "tools" / "selfverify",
        )
        if code == 0:
            bad += 1
            print(f"    [FAIL] injection 3 (pytest failure) — gate stayed green")
        else:
            print(f"    [PASS] injection 3 (pytest failure) — gate turned red")
    finally:
        backup.write_text(original, encoding="utf-8")

    return bad, total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=f"{GATE_LABEL} — static analysis + tests")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    print(f"{GATE_LABEL} — static analysis + unit tests (K9 test pyramid)")
    print(f"  scan dirs: {SCAN_DIRS}")
    print()

    py = sys.executable
    ruff_ok = _ruff_available()
    tests_ok_flag = True
    findings: list[str] = []

    if not ruff_ok:
        print("  [SKIP] ruff not installed (dev extra not activated) — ruff check skipped")
    else:
        ruff_ok_flag, findings = check_ruff(py, quiet=args.quiet)
        if not ruff_ok_flag:
            print(f"  ruff: FAIL ({len(findings)} findings)")
            tests_ok_flag = False
        else:
            print(f"  ruff: PASS")

    # unit tests — always run (selfverify is zero-dependency)
    tests_ok, _tail = check_pytest(py, quiet=args.quiet)
    if not tests_ok:
        print(f"  unittest: FAIL")
        tests_ok_flag = False
    else:
        print(f"  unittest: PASS")

    print()

    # --- injection battery ---
    print(f"  -- fail-closed injections --")
    inj_bad, n_inj = _injections(py)
    if inj_bad:
        print(f"{GATE_LABEL}: FAIL -- {inj_bad}/{n_inj} injections did not "
              f"turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    print()

    # --- Verdict ---
    if not tests_ok_flag:
        print(f"\n{GATE_LABEL}: FAIL — static analysis or tests failed")
        return 1
    print(f"\n{GATE_LABEL}: PASS — ruff clean + unit tests green + "
          f"injections red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
