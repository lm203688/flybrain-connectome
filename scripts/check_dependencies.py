#!/usr/bin/env python3
"""
GATE 38 — Dependency self-check.

Runs FIRST in the gate battery to distinguish "missing dependency"
from "functional regression". Without this gate, a missing numpy
causes Gate 24 to report FAIL, which looks like a code defect but
is actually an environment problem.

Checks:
  1. Python version >= 3.10
  2. numpy >= 1.24 (needed by Gates 3, 4, 5, 6, 10, 24)
  3. pyarrow (needed by data extraction scripts)
  4. scipy (needed by some analysis scripts)

Exit codes:
  0 — all dependencies satisfied (or optional deps missing with --quick)
  1 — required dependency missing in non-quick mode
  2 — optional dependency missing (warning only)

Usage:
    python scripts/check_dependencies.py           # full check
    python scripts/check_dependencies.py --quick    # warn only
"""

from __future__ import annotations

import argparse
import importlib.metadata
import sys
import warnings


REQUIRED = [
    ("numpy", "1.24", "Gates 3, 4, 5, 6, 10, 24"),
    ("scipy", "1.10", "some analysis scripts"),
]

OPTIONAL = [
    ("pyarrow", "10.0", "data extraction (build_malecns_anchors.py)"),
    ("networkx", "2.8", "graph algorithms"),
    ("matplotlib", "3.5", "visualization"),
    ("tqdm", "4.60", "progress bars"),
    ("PIL", "9.0", "image processing"),
]


def _version_tuple(s: str) -> tuple[int, ...]:
    """Parse '1.24' -> (1, 24)."""
    parts = []
    for p in s.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)


def _check_package(name: str, min_version: str, purpose: str) -> tuple[bool, str]:
    """Check if package is installed with version >= min_version.
    
    Returns (ok, message).
    """
    # Try to import first (handles aliases like PIL -> Pillow)
    import_name = name
    if name == "PIL":
        import_name = "PIL"
    try:
        mod = __import__(import_name)
        # Get version from metadata (more reliable than __version__)
        try:
            dist_name = name
            if name == "PIL":
                dist_name = "Pillow"
            ver_str = importlib.metadata.version(dist_name)
        except (importlib.metadata.PackageNotFoundError, ValueError):
            ver_str = getattr(mod, "__version__", "unknown")
        
        ver_tuple = _version_tuple(ver_str.replace("+", "."))
        min_tuple = _version_tuple(min_version)
        
        if ver_tuple >= min_tuple:
            return True, f"  [ok]   {name}=={ver_str} (>= {min_version}) — {purpose}"
        else:
            return False, f"  [FAIL] {name}=={ver_str} (< {min_version}) — {purpose}"
    except ImportError:
        return False, f"  [FAIL] {name} not installed — {purpose}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate 38: dependency self-check")
    ap.add_argument("--quick", action="store_true",
                    help="warn only (optional deps)")
    args = ap.parse_args()

    print("GATE 38 — Dependency self-check")
    print(f"  Python: {sys.version.split()[0]}")
    print("=" * 60)

    # Check Python version
    py_ver = _version_tuple(sys.version.split()[0])
    if py_ver < (3, 10):
        print(f"  [FAIL] Python {sys.version.split()[0]} < 3.10 required")
        print(f"GATE 38: FAIL (Python version too low)")
        return 1
    else:
        print(f"  [ok]   Python {sys.version.split()[0]} >= 3.10")

    # Check required packages
    print(f"\n-- Required dependencies --")
    failures = 0
    for name, min_ver, purpose in REQUIRED:
        ok, msg = _check_package(name, min_ver, purpose)
        print(msg)
        if not ok:
            failures += 1

    # Check optional packages
    print(f"\n-- Optional dependencies --")
    warnings_count = 0
    for name, min_ver, purpose in OPTIONAL:
        ok, msg = _check_package(name, min_ver, purpose)
        print(msg)
        if not ok:
            warnings_count += 1

    print()
    if failures > 0:
        if args.quick:
            print(f"GATE 38: WARNING ({failures} required deps missing, "
                  f"{warnings_count} optional deps missing)")
            print(f"         Some gates may fail — install deps with: "
                  f"pip install numpy scipy")
            return 0
        else:
            print(f"GATE 38: FAIL ({failures} required deps missing)")
            print(f"         Install: pip install numpy>=1.24 scipy>=1.10")
            return 1
    else:
        if warnings_count > 0:
            print(f"GATE 38: PASS ({failures} required missing, "
                  f"{warnings_count} optional missing)")
        else:
            print(f"GATE 38: PASS (all dependencies satisfied)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
