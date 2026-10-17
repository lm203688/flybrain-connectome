#!/usr/bin/env python3
"""GATE 57 — silent exception swallowing (fail-loud discipline).

What this gate does
-------------------
The audit report (FOUNDATION_HARDENING_AUDIT_2026-10-16.md §K7) found
13 places with `except Exception: pass` and 2 bare `except:` in the
codebase. These violate the project's fail-closed philosophy: if an
error occurs silently, the gate reports GREEN while the system has
actually degraded.

Gate 57 does an AST scan of all Python files and flags:
  1. `except Exception: pass` (silent swallow)
  2. `except:` (bare except, catches KeyboardInterrupt/SystemExit too)
  3. `except Exception:` with empty body (no pass, no logging, no re-raise)

Whitelist: files under `flybrain-tier2-backup-*` or paths listed in
scripts/.gate57_whitelist.txt are excluded.

Each violation must have EITHER:
  (a) a `# noqa: SILENT` comment on the except line with a reason,
  (b) a logging.warning/logging.error call in the except block,
  (c) a re-raise (`raise` or `raise ... from ...`),
  (d) a return of an explicit failure value (None, False, -1, etc.)

Gate 39 meta-discipline: the `injections()` battery below creates a
mutated file with a new silent swallow and asserts the gate catches it.
"""
from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

GATE_ID = 57
GATE_LABEL = f"GATE {GATE_ID}"
PY = sys.executable

WHITELIST_FILE = SCRIPTS / ".gate57_whitelist.txt"
BACKUP_PREFIXES = ("flybrain-tier2-backup-", "archive/")

problems: list[str] = []
notes: list[str] = []


def ok(label: str, detail: str = "") -> None:
    print("  PASS  %-50s %s" % (label, detail))


def bad(label: str, detail: str) -> None:
    print("  FAIL  %-50s %s" % (label, detail))
    problems.append("%s: %s" % (label, detail))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def is_excluded(path: Path) -> bool:
    """Check if a file should be excluded from scanning."""
    rel = path.relative_to(ROOT)
    parts = rel.parts  # use .parts for cross-platform path components
    for prefix in BACKUP_PREFIXES:
        prefix_stripped = prefix.rstrip("/")
        for p in parts:
            if p.startswith(prefix_stripped):
                return True
    return False


def load_whitelist() -> set[str]:
    """Load whitelisted file paths from whitelist file."""
    if not WHITELIST_FILE.exists():
        return set()
    whitelist = set()
    for line in read(WHITELIST_FILE).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            whitelist.add(line)
    return whitelist


def check_noqa_comment(source: str, lineno: int) -> bool:
    """Check if the line has a # noqa: SILENT comment."""
    lines = source.splitlines()
    if lineno - 1 < len(lines):
        return "noqa: SILENT" in lines[lineno - 1]
    return False


def check_block_has_logging(body: list[ast.stmt]) -> bool:
    """Check if the except block contains logging.warning/error."""
    for stmt in body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute):
                if isinstance(call.func.value, ast.Name):
                    if call.func.value.id == "logging" and call.func.attr in ("warning", "error", "critical"):
                        return True
            elif isinstance(call.func, ast.Name):
                if call.func.id in ("warning", "error", "critical"):
                    return True
    return False


def check_block_has_reraise(body: list[ast.stmt]) -> bool:
    """Check if the except block re-raises."""
    for stmt in body:
        if isinstance(stmt, ast.Raise):
            return True
    return False


def check_block_has_failure_return(body: list[ast.stmt]) -> bool:
    """Check if the except block returns a failure value."""
    for stmt in body:
        if isinstance(stmt, ast.Return):
            # Check for None, False, -1, or empty tuple/list
            if stmt.value is None:
                return True
            if isinstance(stmt.value, ast.Constant):
                if stmt.value.value is None or stmt.value.value is False or stmt.value.value == 0:
                    return True
    return False


def check_block_is_empty(body: list[ast.stmt]) -> bool:
    """Check if the except block is empty or only has pass."""
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        return False
    return True


class SilentExceptionVisitor(ast.NodeVisitor):
    """AST visitor that finds silent exception swallowing."""

    def __init__(self, source: str, filename: str, whitelist: set[str]):
        self.source = source
        self.filename = filename
        self.whitelist = whitelist
        self.violations: list[dict] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Check for bare except
        is_bare = node.type is None

        # Check for except Exception
        is_exception = (
            isinstance(node.type, ast.Name) and
            node.type.id == "Exception"
        )

        # Skip if not a silent-except pattern
        if not (is_bare or is_exception):
            return

        # Check if block is empty or only pass
        if check_block_is_empty(node.body):
            # Check for noqa: SILENT
            if check_noqa_comment(self.source, node.lineno):
                return

            # Check if block has logging, re-raise, or failure return
            if check_block_has_logging(node.body):
                return
            if check_block_has_reraise(node.body):
                return
            if check_block_has_failure_return(node.body):
                return

            # Violation found
            self.violations.append({
                "file": self.filename,
                "lineno": node.lineno,
                "type": "bare" if is_bare else "except Exception",
                "body": "pass/empty",
                "reason": "silent exception swallow without logging/re-raise/failure return",
            })

        self.generic_visit(node)


def scan_file(path: Path, whitelist: set[str]) -> list[dict]:
    """Scan a single Python file for silent exception swallowing."""
    rel = str(path.relative_to(ROOT))
    if rel in whitelist:
        return []
    if is_excluded(path):
        return []

    try:
        source = read(path)
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    visitor = SilentExceptionVisitor(source, str(rel), whitelist)
    visitor.visit(tree)
    return visitor.violations


def find_python_files() -> list[Path]:
    """Find all Python files to scan."""
    py_files = []
    for pattern in ["**/*.py"]:
        for p in ROOT.glob(pattern):
            if p.is_file() and not is_excluded(p):
                # Skip test files, __pycache__, and generated files
                rel = str(p.relative_to(ROOT))
                if "__pycache__" in rel or rel.startswith("tests/") or "_test.py" in rel:
                    continue
                py_files.append(p)
    return py_files


def check_all(strict: bool = False) -> tuple[bool, list[str]]:
    """Run all silent exception checks. Returns (passed, problems)."""
    global problems
    problems = []

    print("=" * 60)
    print(f"{GATE_LABEL} — silent exception swallowing")
    print("=" * 60)

    whitelist = load_whitelist()
    py_files = find_python_files()

    print(f"\nScanning {len(py_files)} Python files...")
    print(f"Whitelist: {len(whitelist)} paths\n")

    all_violations: list[dict] = []
    files_with_violations = 0

    for path in py_files:
        violations = scan_file(path, whitelist)
        if violations:
            files_with_violations += 1
            for v in violations:
                all_violations.append(v)

    # Report violations
    if all_violations:
        print(f"Found {len(all_violations)} violation(s) in {files_with_violations} file(s):\n")
        for v in all_violations:
            print(f"  {v['file']}:{v['lineno']}")
            print(f"    {v['type']}: {v['body']}")
            print(f"    Reason: {v['reason']}")
            print()

        bad("silent exception check",
            f"{len(all_violations)} silent exception(s) found")
    else:
        ok("silent exception check", f"{len(py_files)} files scanned, 0 violations")

    # Summary
    print("=" * 60)
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
    """Test that the gate catches new silent exception swallowing."""
    cases = []

    # Injection 1: bare except with pass
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / "test_silent.py"
        test_file.write_text(
            'def foo():\n'
            '    try:\n'
            '        do_something()\n'
            '    except:\n'
            '        pass\n',
            encoding="utf-8"
        )

        result = subprocess.run(
            [PY, "-c", f"""
import sys
sys.path.insert(0, r'{SCRIPTS}')
import check_silent_exceptions as mod
mod.ROOT = Path(r'{tmp_path}')
mod.WHITELIST_FILE = Path(r'{tmp_path}/.gate57_whitelist.txt')
violations = mod.scan_file(Path(r'{test_file}'), set())
sys.exit(0 if violations else 1)
"""],
            capture_output=True, text=True
        )
        cases.append({
            "name": "bare except with pass",
            "passed": result.returncode == 0,
            "description": "Bare except: pass → should be caught"
        })

    # Injection 2: except Exception with pass
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / "test_silent2.py"
        test_file.write_text(
            'def foo():\n'
            '    try:\n'
            '        do_something()\n'
            '    except Exception:\n'
            '        pass\n',
            encoding="utf-8"
        )

        result = subprocess.run(
            [PY, "-c", f"""
import sys
sys.path.insert(0, r'{SCRIPTS}')
import check_silent_exceptions as mod
mod.ROOT = Path(r'{tmp_path}')
mod.WHITELIST_FILE = Path(r'{tmp_path}/.gate57_whitelist.txt')
violations = mod.scan_file(Path(r'{test_file}'), set())
sys.exit(0 if violations else 1)
"""],
            capture_output=True, text=True
        )
        cases.append({
            "name": "except Exception with pass",
            "passed": result.returncode == 0,
            "description": "except Exception: pass → should be caught"
        })

    # Injection 3: except Exception with noqa: SILENT (should be allowed)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / "test_silent3.py"
        test_file.write_text(
            'def foo():\n'
            '    try:\n'
            '        do_something()\n'
            '    except Exception:  # noqa: SILENT — intentional fallback\n'
            '        pass\n',
            encoding="utf-8"
        )

        result = subprocess.run(
            [PY, "-c", f"""
import sys
sys.path.insert(0, r'{SCRIPTS}')
import check_silent_exceptions as mod
mod.ROOT = Path(r'{tmp_path}')
mod.WHITELIST_FILE = Path(r'{tmp_path}/.gate57_whitelist.txt')
violations = mod.scan_file(Path(r'{test_file}'), set())
sys.exit(0 if not violations else 1)
"""],
            capture_output=True, text=True
        )
        cases.append({
            "name": "except Exception with noqa: SILENT",
            "passed": result.returncode == 0,
            "description": "except Exception: pass with noqa: SILENT → should be allowed"
        })

    # Injection 4: except Exception with logging.warning (should be allowed)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_file = tmp_path / "test_silent4.py"
        test_file.write_text(
            'import logging\n'
            'def foo():\n'
            '    try:\n'
            '        do_something()\n'
            '    except Exception as e:\n'
            '        logging.warning("caught: %s", e)\n',
            encoding="utf-8"
        )

        result = subprocess.run(
            [PY, "-c", f"""
import sys
sys.path.insert(0, r'{SCRIPTS}')
import check_silent_exceptions as mod
mod.ROOT = Path(r'{tmp_path}')
mod.WHITELIST_FILE = Path(r'{tmp_path}/.gate57_whitelist.txt')
violations = mod.scan_file(Path(r'{test_file}'), set())
sys.exit(0 if not violations else 1)
"""],
            capture_output=True, text=True
        )
        cases.append({
            "name": "except Exception with logging.warning",
            "passed": result.returncode == 0,
            "description": "except Exception with logging.warning → should be allowed"
        })

    return cases


def run_injections() -> bool:
    """Run injection battery. Returns True if all injections behave correctly."""
    print("\n" + "=" * 60)
    print(f"{GATE_LABEL} — injection battery")
    print("=" * 60)

    cases = injections()
    all_passed = True
    for case in cases:
        status = "PASS" if case["passed"] else "FAIL"
        print(f"  {status:6s} {case['name']:40s} {case['description']}")
        if not case["passed"]:
            all_passed = False

    if all_passed:
        print(f"\n  Injection battery: PASS (all {len(cases)} correct)")
        return True
    else:
        print(f"\n  Injection battery: FAIL (some injections incorrect)")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Gate 57: silent exception check")
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
