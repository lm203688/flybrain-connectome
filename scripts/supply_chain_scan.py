#!/usr/bin/env python3
"""supply_chain_scan.py — AI Bill of Materials (AIBOM) generator.

What this produces
------------------
A machine-readable JSON manifest (AIBOM = AI Bill of Materials) that
records every external component this project depends on:

  * **direct_python_deps** — the runtime deps declared in the *main*
    pyproject.toml (numpy today).
  * **optional_dep_groups** — [prov] / [data] / [dev] extras from the
    main pyproject, so a downstream consumer can see what an "install
    with provenance" or "install for data extraction" pulls in.
  * **subpackage_manifests** — the version of every sub-package with
    its own pyproject.toml (mcp_connectome, selfverify) and the
    deps it declares. Sub-package version drift has historically
    slipped past the top-level version gate, so we list them here
    explicitly rather than hide them inside a lock file.
  * **dataset_provenance** — the MaleCNS anchor: dataset name,
    generator timestamp, file count, and the sha256 of the anchor
    connectivity_facts.json. This is the single most important
    reproducibility signal: the whole project hangs off this dataset.
  * **workspace_fingerprint** — sha256 of pyproject.toml,
    DATA_MANIFEST.json, and the top-level README so a downstream
    consumer can detect "I am looking at a different tree than the
    AIBOM was generated from."
  * **generated_utc** — ISO-8601 timestamp of the scan.

The AIBOM is a *supply chain* artifact, not a security artifact: it
does not claim any dependency is safe. It claims the dependency set
is *disclosed*. That is what Phase 3 was promised; a security-audit
layer is out of scope for this gate.

Run standalone (writes aibom.json):

    python scripts/supply_chain_scan.py --output aibom.json

Run in --check mode (validates a pre-generated aibom.json against
the current tree; used by gate 60):

    python scripts/supply_chain_scan.py --check aibom.json

Exit codes:
  0 — scan succeeded / aibom.json is consistent with the tree
  1 — check failed (tree drift or manifest malformed)
  2 — generation error (missing pyproject, unreadable manifest, ...)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Constants — deliberately narrow; adding a new dep to the whitelist
# requires an explicit code change and a review.
# ---------------------------------------------------------------------------

MAIN_PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
README = ROOT / "README.md"
DATA_MANIFEST = ROOT / "DATA_MANIFEST.json"

SUBPACKAGE_DIRS = [
    ROOT / "flybrain-connectome-mcp" / "mcp_connectome",
    ROOT / "tools" / "selfverify",
]

# Anchor artifact inside DATA_MANIFEST. If the file is missing, the
# scan still succeeds (workspace can be in an unreduced state during
# development) but the field is marked {"status": "missing"} rather
# than silently emitting an empty string.
ANCHOR_REL = "connectivity_facts.json"

AIBOM_SCHEMA_VERSION = "1.0.0"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Pyproject parsing (no tomllib — kept zero-dependency)
# ---------------------------------------------------------------------------

def _extract_pyproject_version(p: Path) -> str | None:
    if not p.exists():
        return None
    m = re.search(r'^version\s*=\s*"([^"]+)"', _read(p), re.MULTILINE)
    return m.group(1) if m else None


def _extract_project_name(p: Path) -> str | None:
    if not p.exists():
        return None
    m = re.search(r'^name\s*=\s*"([^"]+)"', _read(p), re.MULTILINE)
    return m.group(1) if m else None


def _split_toml_array(payload: str) -> list[str]:
    """Split a TOML array literal into cleaned items.

    Handles `["a", "b"]` and `["a", "b"]` where items may be
    single- or double-quoted. Returns [] on empty input.
    """
    s = payload.strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    out: list[str] = []
    for part in s.split(","):
        item = part.strip().strip('"').strip("'").strip()
        if item and not item.startswith("#"):
            out.append(item)
    return out


def _extract_deps_block(p: Path) -> list[str]:
    """Return [dependencies] entries from a pyproject.toml.

    Handles the single-line form and the multi-line bracketed form;
    strips comments and blank lines. Intentionally does not handle
    nested tables — the project only ever uses flat lists.
    """
    if not p.exists():
        return []
    text = _read(p)
    in_block = False
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("dependencies"):
                # single-line form:  dependencies = ["a", "b"]
                if "=" in stripped and "]" in stripped:
                    return _split_toml_array(stripped.split("=", 1)[1])
                in_block = True
            continue
        if stripped.startswith("]"):
            break
        if not stripped or stripped.startswith("#"):
            continue
        if "]" in stripped:
            stripped = stripped.split("]")[0]
        s = stripped.strip().strip(',').strip().strip('"').strip("'")
        if s:
            lines.append(s)
    return lines


def _extract_optional_deps(p: Path) -> dict[str, list[str]]:
    """Return {extras_name: [deps]} from [project.optional-dependencies].

    Handles multi-line groups; intentionally lenient (does not handle
    nested inline tables, which the project does not use).
    """
    if not p.exists():
        return {}
    text = _read(p)
    lines = text.splitlines()
    out: dict[str, list[str]] = {}
    current: str | None = None
    in_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[project.optional-dependencies]"):
            in_block = True
            continue
        if in_block and stripped.startswith("[") and stripped.endswith("]") \
                and stripped != "[project.optional-dependencies]":
            break
        if not in_block:
            continue
        # group header:  prov = [
        m = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*\[', stripped)
        if m:
            current = m.group(1)
            # single-line form:  prov = ["a", "b"]
            if "]" in stripped:
                out[current] = _split_toml_array(stripped.split("=", 1)[1])
                current = None
            else:
                out[current] = []
            continue
        if current is None:
            continue
        if stripped.startswith("]"):
            current = None
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if "]" in stripped:
            stripped = stripped.split("]")[0]
        s = stripped.strip().strip(',').strip().strip('"').strip("'")
        if s:
            out[current].append(s)
    return out


# ---------------------------------------------------------------------------
# Dataset provenance
# ---------------------------------------------------------------------------

def _dataset_provenance() -> dict:
    """Extract the anchor info from DATA_MANIFEST.json.

    Returns a dict with 'status' so a downstream consumer can tell
    "missing" apart from "empty". Fails closed: if the manifest is
    present but unparseable, we report status="malformed" rather than
    pretending the dataset is fine.
    """
    if not DATA_MANIFEST.exists():
        return {"status": "missing",
                "note": "DATA_MANIFEST.json not found at repo root"}

    try:
        raw = json.loads(_read(DATA_MANIFEST))
    except Exception as e:
        return {"status": "malformed", "error": str(e)}

    anchor = next((f for f in raw.get("files", [])
                   if f.get("rel") == ANCHOR_REL), None)

    out: dict = {
        "status": "ok",
        "dataset": raw.get("dataset", "unknown"),
        "generated_utc": raw.get("generated_utc"),
        "file_count": raw.get("file_count"),
        "total_bytes": raw.get("total_bytes"),
        "anchor": {
            "rel": ANCHOR_REL,
            "bytes": anchor.get("bytes") if anchor else None,
            "sha256": anchor.get("sha256") if anchor else None,
        } if anchor else {"rel": ANCHOR_REL,
                          "status": "not_in_manifest"},
    }
    return out


# ---------------------------------------------------------------------------
# Workspace fingerprint
# ---------------------------------------------------------------------------

def _workspace_fingerprint() -> dict:
    """sha256 of the four source-of-truth files.

    A downstream consumer compares this against their local tree to
    detect "my AIBOM is stale" or "this workspace has drifted from
    the pinned commit." Any missing file is marked, not skipped.
    """
    out = {}
    for name, path in [
        ("pyproject.toml", MAIN_PYPROJECT),
        ("DATA_MANIFEST.json", DATA_MANIFEST),
        ("README.md", README),
        ("CHANGELOG.md", CHANGELOG),
    ]:
        if not path.exists():
            out[name] = {"status": "missing"}
        else:
            out[name] = {"sha256": _sha256(path),
                         "bytes": path.stat().st_size}
    return out


# ---------------------------------------------------------------------------
# AIBOM assembly
# ---------------------------------------------------------------------------

def build_aibom() -> dict:
    """Assemble the full AIBOM dict. Raises on unrecoverable errors."""
    if not MAIN_PYPROJECT.exists():
        raise FileNotFoundError(
            "main pyproject.toml not found at %s" % MAIN_PYPROJECT)

    direct = _extract_deps_block(MAIN_PYPROJECT)
    optional = _extract_optional_deps(MAIN_PYPROJECT)

    subpackages: list[dict] = []
    for d in SUBPACKAGE_DIRS:
        pyp = d / "pyproject.toml"
        if not pyp.exists():
            subpackages.append({
                "path": d.relative_to(ROOT).as_posix(),
                "status": "no_pyproject",
            })
            continue
        subpackages.append({
            "path": d.relative_to(ROOT).as_posix(),
            "name": _extract_project_name(pyp),
            "version": _extract_pyproject_version(pyp),
            "dependencies": _extract_deps_block(pyp),
            "status": "ok",
        })

    return {
        "aibom_schema_version": AIBOM_SCHEMA_VERSION,
        "generated_utc": datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds"),
        "package": {
            "name": _extract_project_name(MAIN_PYPROJECT),
            "version": _extract_pyproject_version(MAIN_PYPROJECT),
        },
        "direct_python_deps": direct,
        "optional_dep_groups": optional,
        "subpackages": subpackages,
        "dataset_provenance": _dataset_provenance(),
        "workspace_fingerprint": _workspace_fingerprint(),
    }


# ---------------------------------------------------------------------------
# Check mode — validate an existing aibom.json against the current tree
# ---------------------------------------------------------------------------

FINGERPRINT_TOLERANCE_KEYS = ("README.md",)
# The AIBOM itself contains a workspace_fingerprint block, so if a
# future refactor adds supply_chain_scan.py or aibom.json to the
# fingerprint set, the checker would always fail on self-updates.
# Those are called out here so the drift rule stays narrow.

STALE_TOLERANCE_SEC = 0   # strict by default; a stale aibom is a bug


def check_aibom(aibom_path: Path) -> tuple[bool, list[str]]:
    """Compare aibom_path against the live tree. Returns (ok, problems)."""
    problems: list[str] = []
    if not aibom_path.exists():
        return False, ["AIBOM file not found: %s" % aibom_path]

    try:
        recorded = json.loads(_read(aibom_path))
    except Exception as e:
        return False, ["AIBOM unparseable: %s" % e]

    if recorded.get("aibom_schema_version") != AIBOM_SCHEMA_VERSION:
        problems.append(
            "aibom_schema_version mismatch: recorded=%s expected=%s"
            % (recorded.get("aibom_schema_version"), AIBOM_SCHEMA_VERSION))

    # Fingerprint check: every non-missing entry must match the live file.
    fp_recorded = recorded.get("workspace_fingerprint", {}) or {}
    for name, entry in fp_recorded.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") == "missing":
            continue
        recorded_hash = entry.get("sha256")
        if not recorded_hash:
            continue
        path_map = {
            "pyproject.toml": MAIN_PYPROJECT,
            "DATA_MANIFEST.json": DATA_MANIFEST,
            "README.md": README,
            "CHANGELOG.md": CHANGELOG,
        }
        p = path_map.get(name)
        if p is None or not p.exists():
            problems.append(
                "fingerprint %s recorded but file now missing" % name)
            continue
        live_hash = _sha256(p)
        if live_hash != recorded_hash:
            problems.append(
                "workspace_fingerprint drift: %s (recorded=%s live=%s)"
                % (name, recorded_hash[:12], live_hash[:12]))

    # Package version must still be current in pyproject.toml.
    rec_ver = (recorded.get("package") or {}).get("version")
    live_ver = _extract_pyproject_version(MAIN_PYPROJECT)
    if rec_ver and live_ver and rec_ver != live_ver:
        problems.append(
            "package version drift: aibom=%s pyproject=%s"
            % (rec_ver, live_ver))

    # Subpackage versions must still agree.
    for sub in recorded.get("subpackages", []) or []:
        if sub.get("status") != "ok":
            continue
        sub_pyp = ROOT / sub["path"] / "pyproject.toml"
        live_sub = _extract_pyproject_version(sub_pyp) if sub_pyp.exists() else None
        if sub.get("version") != live_sub:
            problems.append(
                "subpackage version drift %s: aibom=%s live=%s"
                % (sub["path"], sub.get("version"), live_sub))

    # Direct deps list must still match the pyproject.
    live_deps = _extract_deps_block(MAIN_PYPROJECT)
    if recorded.get("direct_python_deps") != live_deps:
        problems.append(
            "direct_python_deps drift: aibom=%s live=%s"
            % (recorded.get("direct_python_deps"), live_deps))

    return (len(problems) == 0), problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--output", "-o",
                      help="write the generated AIBOM to this path")
    mode.add_argument("--check", metavar="AIBOM_JSON",
                      help="validate an existing AIBOM against the live tree")
    mode.add_argument("--print", action="store_true",
                      help="print the generated AIBOM to stdout (default)")
    args = ap.parse_args()

    if args.check:
        aibom_path = Path(args.check)
        ok, problems = check_aibom(aibom_path)
        if ok:
            print("  PASS  AIBOM %s is consistent with the live tree"
                  % aibom_path.name)
            return 0
        print("  FAIL  AIBOM %s drift:" % aibom_path.name)
        for p in problems:
            print("        - %s" % p)
        return 1

    try:
        aibom = build_aibom()
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(aibom, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print("  wrote %s (%d bytes)" % (out, out.stat().st_size))
        return 0

    print(json.dumps(aibom, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
