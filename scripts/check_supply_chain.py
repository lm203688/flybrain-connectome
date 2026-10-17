#!/usr/bin/env python3
"""GATE 60 — AIBOM supply-chain disclosure gate.

What this gate does
-------------------
Phase 3 promised a machine-generated supply-chain manifest: an AI
Bill of Materials (AIBOM) that discloses every external component
this project depends on. Gate 60 enforces that the AIBOM actually
exists on disk, is well-formed, and is in sync with the live tree.

It catches:
  1. Missing AIBOM — no aibom.json committed → build fails.
  2. Malformed AIBOM — JSON parse error or schema mismatch.
  3. Tree drift — any file in workspace_fingerprint changed since
     the AIBOM was generated (a stale manifest is a lie).
  4. Dep drift — direct_python_deps or subpackage versions differ
     from pyproject.toml.

The gate is *supplementary*: it does not itself scan for malicious
deps or vulnerable versions. That would require a network call and
a CVE database, neither of which fits this repo's offline discipline.
What the AIBOM does is force disclosure — a hidden dep cannot hide
because the fingerprint would drift.

Run:
    python scripts/check_supply_chain.py              # full check
    python scripts/check_supply_chain.py --regenerate  # write new aibom.json

Exit codes:
  0 — AIBOM present, well-formed, in sync with the tree
  1 — AIBOM missing, malformed, or drifted
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
AIBOM_PATH = ROOT / "aibom.json"

# Load supply_chain_scan.py by path — it is a script, not a package.
_scan_spec = importlib.util.spec_from_file_location(
    "supply_chain_scan", SCRIPTS / "supply_chain_scan.py")
_scan = importlib.util.module_from_spec(_scan_spec)
_scan_spec.loader.exec_module(_scan)

GATE_LABEL = "GATE 60"
problems: list[str] = []
notes: list[str] = []


def ok(label: str, detail: str = "") -> None:
    print("  PASS  %-50s %s" % (label, detail))


def bad(label: str, detail: str) -> None:
    print("  FAIL  %-50s %s" % (label, detail))
    problems.append("%s: %s" % (label, detail))


def check_all() -> tuple[bool, list[str]]:
    print("=" * 60)
    print(f"{GATE_LABEL} — AIBOM supply-chain disclosure")
    print("=" * 60)
    print()

    if not AIBOM_PATH.exists():
        bad("AIBOM file", "aibom.json not found at repo root")
        print()
        print("  Fix: python scripts/supply_chain_scan.py --output aibom.json")
        return False, problems

    ok("AIBOM file present", "%s (%d bytes)" % (AIBOM_PATH.name, AIBOM_PATH.stat().st_size))

    import json
    try:
        recorded = json.loads(AIBOM_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        bad("AIBOM JSON", "unparseable: %s" % e)
        return False, problems
    ok("AIBOM JSON", "parsed")

    if recorded.get("aibom_schema_version") != _scan.AIBOM_SCHEMA_VERSION:
        bad("aibom_schema_version",
            "recorded=%s expected=%s"
            % (recorded.get("aibom_schema_version"), _scan.AIBOM_SCHEMA_VERSION))
    else:
        ok("aibom_schema_version", _scan.AIBOM_SCHEMA_VERSION)

    # Full consistency check via the scanner's own checker.
    check_ok, problems_ = _scan.check_aibom(AIBOM_PATH)
    if check_ok:
        ok("workspace consistency", "all fingerprints + deps agree with the live tree")
    else:
        for p in problems_:
            bad("workspace consistency", p)

    # Report the disclosed surface so the gate output is informative.
    n_direct = len(recorded.get("direct_python_deps", []))
    n_optional_groups = len(recorded.get("optional_dep_groups", {}))
    n_sub = sum(1 for s in recorded.get("subpackages", []) if s.get("status") == "ok")
    notes.append(
        "disclosed: %d direct deps, %d optional groups, %d subpackages, "
        "dataset=%s"
        % (n_direct, n_optional_groups, n_sub,
           recorded.get("dataset_provenance", {}).get("dataset", "?")))

    return len(problems) == 0, problems


def _injections() -> tuple[int, int]:
    """Injection battery — prove Gate 60 turns red on real defects.

    Each case writes a bad aibom.json to a temp dir, points AIBOM_PATH
    at it, runs check_all(), asserts at least one problem was recorded,
    and restores state in a finally block. Apply and restore are
    structurally separate so no injection can leak state into the next.
    """
    import json
    import shutil
    import tempfile
    bad_count = 0
    n_inj = 0

    def run_case(name: str, make_json) -> None:
        nonlocal bad_count, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate60_inj_"))
        old_aibom = globals()["AIBOM_PATH"]
        fp = td / "aibom.json"
        make_json(fp)
        globals()["AIBOM_PATH"] = fp
        try:
            problems.clear()
            notes.clear()
            check_all()
            n_problems = len(problems)
            if n_problems == 0:
                bad_count += 1
                print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)
            else:
                print("    [PASS] injecting: %s (%d problem(s))"
                      % (name, n_problems))
        finally:
            globals()["AIBOM_PATH"] = old_aibom
            shutil.rmtree(td, ignore_errors=True)

    def gen_good() -> dict:
        return _scan.build_aibom()

    # 1. Missing AIBOM — do NOT create the file
    def make_missing(fp):
        pass  # file absent
    run_case("missing aibom.json", make_missing)

    # 2. Malformed JSON
    def make_malformed(fp):
        fp.write_text("{not valid json", encoding="utf-8")
    run_case("malformed JSON", make_malformed)

    # 3. Schema drift
    def make_schema_drift(fp):
        good = gen_good()
        good["aibom_schema_version"] = "0.0.0"
        fp.write_text(json.dumps(good), encoding="utf-8")
    run_case("aibom_schema_version drift", make_schema_drift)

    # 4. Direct deps drift
    def make_dep_drift(fp):
        good = gen_good()
        good["direct_python_deps"] = ["numpy>=0.0.1", "some_fake_dep"]
        fp.write_text(json.dumps(good), encoding="utf-8")
    run_case("direct_python_deps drift", make_dep_drift)

    # 5. Fingerprint drift (tamper a recorded hash)
    def make_fp_drift(fp):
        good = gen_good()
        fp_entry = good["workspace_fingerprint"].get("pyproject.toml")
        if isinstance(fp_entry, dict) and fp_entry.get("sha256"):
            fp_entry["sha256"] = "0" * 64
        fp.write_text(json.dumps(good), encoding="utf-8")
    run_case("workspace_fingerprint drift", make_fp_drift)

    return bad_count, n_inj


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regenerate", action="store_true",
                    help="write a fresh aibom.json from the current tree")
    ap.add_argument("--injections", action="store_true",
                    help="run the injection battery (used by Gate 39)")
    args = ap.parse_args()

    if args.regenerate:
        try:
            aibom = _scan.build_aibom()
        except Exception as e:
            print("ERROR: %s" % e)
            return 2
        import json
        AIBOM_PATH.write_text(
            json.dumps(aibom, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print("  regenerated %s (%d bytes)"
              % (AIBOM_PATH, AIBOM_PATH.stat().st_size))
        return 0

    if args.injections:
        n_bad, n_inj = _injections()
        print()
        print("  injection battery: %d/%d mutations caught" % (n_inj - n_bad, n_inj))
        return 1 if n_bad else 0

    ok_state, _ = check_all()
    for n in notes:
        print("  note  %s" % n)
    print()
    print("  %s" % ("PASS" if ok_state else "FAIL"))
    if problems:
        print("  problems:")
        for p in problems:
            print("    - %s" % p)
    return 0 if ok_state else 1


if __name__ == "__main__":
    sys.exit(main())
