#!/usr/bin/env python3
"""GATE 54 — metrics_fork reproducibility self-check.

Why this gate exists
--------------------
Prior to this gate, `metrics_fork/` was a reproducibility *claim* with no
gate guarding it. `docs/PROJECT_ASSESSMENT_AND_ENHANCEMENT_2026-10-16.md`
§3 records three defects that were all present simultaneously:

* The README's "Re-running the paper's numbers" table pointed at three
  upstream result artifacts (`_f4_intervention_n100/artifact.json`,
  `generated_organisms/pcv2_5x8.json`, `_f2_recovery/artifact.json`) that
  are `{"summary","all_results"}` result files, not `{"nodes","edges"}`
  graph files. Running them raised `KeyError: 'edges'`.
* No gate, test, or CI step referenced `metrics_fork/`.
* `data_manifest.json` had a species-label contradiction:
  `display_name = "Male C. elegans CNS connectome"` alongside
  `species = "Drosophila melanogaster (male)"`.

Gate 54 turns "reproducibility" from a claim into a machine-checked claim:

1. **Tree check** — every required file is present.
2. **License check** — LICENSE declares Apache-2.0.
3. **Command execution** — every `python -m metrics.*` command shown in the
   README's self-contained smoke-test block is executed against the shipped
   `graphs/sample_topology.json`. Each must exit 0 and print parseable JSON.
4. **Manifest consistency** — `display_name` and `species` in
   `data_manifest.json` must not contradict each other across species
   genus boundaries (e.g. "C. elegans" in display_name vs "Drosophila"
   in species = contradiction).
5. **Upstream-artifact disclaimer** — if the README's paper-numbers table
   points at paths *outside* `metrics_fork/`, a disclaimer must explain
   those are result files, not graph files.

Gate 39 meta-discipline: the `injections()` battery below re-runs the
full check on mutated copies of the fork tree and asserts each mutation
turns the gate red. If any mutation survives, the gate is degenerate and
this file FAILs — because a gate that never proved it could go red is
a gate that will never catch anything.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FORK = ROOT / "metrics_fork"

GATE_ID = 54
GATE_LABEL = f"GATE {GATE_ID}"

PY = sys.executable

# ---------------------------------------------------------------------------
# Required files
# ---------------------------------------------------------------------------

REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "data_manifest.json",
    "metrics/__init__.py",
    "metrics/robustness.py",
    "metrics/controllability.py",
    "metrics/recovery.py",
    "graphs/sample_topology.json",
)

REQUIRED_TOPOLOGY_KEYS = ("nodes", "edges")

# ---------------------------------------------------------------------------
# Command extraction from README
# ---------------------------------------------------------------------------

# Only match the smoke-test block (lines that reference sample_topology.json)
# so the upstream-artifact table (which intentionally points outside the
# fork) does not get executed and produce spurious failures.
SMOKE_CMD_RE = re.compile(
    r"^\s*python\s+-m\s+metrics\.(robustness|controllability|recovery)\b"
    r"(.*?sample_topology\.json.*?)\s*$",
    re.MULTILINE,
)

# Also catch every `python -m metrics.*` line for completeness reporting.
ALL_CMD_RE = re.compile(
    r"^\s*python\s+-m\s+metrics\.(robustness|controllability|recovery)\b(.*)$",
    re.MULTILINE,
)

UPSTREAM_PATH_HINT = re.compile(
    r"(\.json|\.py)\s*\(upstream\)"
    r"|`_f[0-9]_[a-z_]+/[a-zA-Z0-9_.-]+`"
    r"|`generated_organisms/[a-zA-Z0-9_.-]+`",
)

DISCLAIMER_HINT = re.compile(
    r"result files?\.?\s+(?:not|→|->)\s+graph files?"
    r"|KeyError:?\s*['\"]edges['\"]"
    r"|first be\s+exported to the graph shape",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_tree(fork: Path) -> list[str]:
    """Return list of missing required files (empty = OK)."""
    missing = []
    for rel in REQUIRED_FILES:
        if not (fork / rel).is_file():
            missing.append(rel)
    return missing


def check_license(fork: Path) -> list[str]:
    """Return list of license violations (empty = OK)."""
    lic = (fork / "LICENSE").read_text(encoding="utf-8", errors="replace")
    if "Apache License" not in lic or "Version 2.0" not in lic:
        return ["LICENSE does not declare Apache-2.0"]
    return []


def check_topology_shape(fork: Path) -> list[str]:
    """The shipped smoke-test graph must be a valid nodes/edges JSON."""
    p = fork / "graphs" / "sample_topology.json"
    try:
        g = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [f"sample_topology.json unparseable: {e}"]
    for k in REQUIRED_TOPOLOGY_KEYS:
        if k not in g:
            return [f"sample_topology.json missing top-level key '{k}'"]
    if not isinstance(g["nodes"], list) or not isinstance(g["edges"], list):
        return ["sample_topology.json nodes/edges must be lists"]
    if len(g["nodes"]) < 2:
        return ["sample_topology.json needs >= 2 nodes for a meaningful metric"]
    return []


def check_manifest_consistency(fork: Path) -> list[str]:
    """display_name and species must agree on genus.

    A species contradiction is exactly what the upstream report flagged:
    `display_name = "Male C. elegans CNS connectome"` while
    `species = "Drosophila melanogaster (male)"`. This is a factual bug
    that would show up in the paper's methodology short paper as-is.
    """
    p = fork / "data_manifest.json"
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [f"data_manifest.json unparseable: {e}"]

    contradictions = []
    for ds in m.get("datasets", []):
        dn = (ds.get("display_name") or "").lower()
        sp = (ds.get("species") or "").lower()
        dn_short = dn
        sp_short = sp
        # Rule 1: display_name mentions C. elegans but species says Drosophila
        # (or vice versa). Also check the reverse direction.
        dn_cel = "c. elegans" in dn or "caenorhabditis" in dn
        sp_cel = "c. elegans" in sp or "caenorhabditis" in sp
        dn_dros = "drosophila" in dn
        sp_dros = "drosophila" in sp

        if (dn_cel and sp_dros) or (sp_cel and dn_dros):
            contradictions.append(
                f"{ds.get('id','?')}: display_name={dn!r} vs species={sp!r} "
                f"(cross-genus contradiction)"
            )
        # Rule 2: display_name must contain the species' genus token
        # (or its well-known short form) when the entry is not a series
        # that spans multiple species.
        if sp_dros and not dn_dros:
            # display_name should at least mention Drosophila, or reference
            # the historical "MaleCNS" filename explicitly.
            if "malecns" not in dn and "male cns" not in dn:
                contradictions.append(
                    f"{ds.get('id','?')}: species=Drosophila but "
                    f"display_name={dn!r} does not mention Drosophila"
                )
        del dn_short, sp_short  # kept for possible future use
    return contradictions


def extract_smoke_commands(readme_text: str) -> list[tuple[str, list[str]]]:
    """Return [(module_name, argv_tail), ...] for smoke-test commands."""
    cmds = []
    for m in SMOKE_CMD_RE.finditer(readme_text):
        mod = m.group(1)
        rest = m.group(2).strip()
        # Strip trailing markdown fence/backtick.
        rest = rest.rstrip("`")
        args = shlex.split(rest) if rest else []
        cmds.append((mod, args))
    return cmds


def run_command(cmd_argv: list[str], fork: Path,
                timeout: float = 15.0) -> tuple[int, str, str]:
    """Run a metric command in the fork directory; return (rc, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd_argv, cwd=str(fork), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        return -1, e.stdout or "", e.stderr or f"timeout after {timeout}s"


def check_commands(fork: Path) -> list[str]:
    """Execute every smoke-test command; each must exit 0 + print valid JSON."""
    readme = (fork / "README.md").read_text(encoding="utf-8", errors="replace")
    cmds = extract_smoke_commands(readme)

    failures: list[str] = []
    if not cmds:
        return ["README smoke-test block has no `python -m metrics.*` commands"]

    for mod, args in cmds:
        argv = [PY, "-m", f"metrics.{mod}"] + args
        rc, out, err = run_command(argv, fork)
        label = " ".join(argv[2:])
        if rc != 0:
            tail = (err.strip().splitlines() or [""])[-1]
            failures.append(f"{label} exited {rc}: {tail}")
            continue
        stripped = out.strip()
        if not stripped:
            failures.append(f"{label} printed empty stdout")
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError as e:
            failures.append(f"{label} stdout is not JSON: {e}")
    return failures


def check_upstream_disclaimer(fork: Path) -> list[str]:
    """If README points at upstream artifact paths, disclaimer is required."""
    readme = (fork / "README.md").read_text(encoding="utf-8", errors="replace")
    has_upstream_path = bool(UPSTREAM_PATH_HINT.search(readme))
    if not has_upstream_path:
        return []  # nothing to guard
    if DISCLAIMER_HINT.search(readme):
        return []
    return [
        "README references upstream artifact paths but has no disclaimer "
        "explaining they are result files (not graph shape). "
        "Add a note near the paper-numbers table stating that these "
        "commands require exporting result files to the {nodes,edges} "
        "shape before they can be executed."
    ]


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def check_all(fork: Path) -> tuple[bool, list[str], dict]:
    """Return (ok, failures, report)."""
    failures: list[str] = []

    tree_missing = check_tree(fork)
    if tree_missing:
        failures.extend(f"missing required file: {p}" for p in tree_missing)

    failures.extend(check_license(fork))
    failures.extend(check_topology_shape(fork))
    failures.extend(check_manifest_consistency(fork))
    failures.extend(check_commands(fork))
    failures.extend(check_upstream_disclaimer(fork))

    readme = (fork / "README.md").read_text(encoding="utf-8", errors="replace")
    all_cmds = [(m.group(1), m.group(2).strip())
                for m in ALL_CMD_RE.finditer(readme)]
    smoke_cmds = extract_smoke_commands(readme)

    report = {
        "schema_version": "1.0",
        "gate_id": GATE_ID,
        "fork_path": str(fork),
        "ok": not failures,
        "failures": failures,
        "n_smoke_commands": len(smoke_cmds),
        "n_all_command_refs": len(all_cmds),
        "smoke_commands": [f"python -m metrics.{m} {' '.join(a)}"
                           for m, a in smoke_cmds],
        "datasets_checked": len(json.loads(
            (fork / "data_manifest.json").read_text(encoding="utf-8")
        ).get("datasets", [])),
    }
    return (not failures), failures, report


# ---------------------------------------------------------------------------
# Injection battery (Gate 39 meta-discipline)
# ---------------------------------------------------------------------------

def _copy_fork(dst: Path) -> Path:
    shutil.copytree(FORK, dst)
    return dst


def _restore(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _run_on(fork_copy: Path) -> bool:
    ok, _fail, _rep = check_all(fork_copy)
    return ok


def injections() -> list[dict]:
    """Return list of {name, description, mutated_ok}.

    For the battery to pass, EVERY injected mutation must make the check
    return False (go red). If any mutation passes (returns True), that
    mutation does not exercise a real defect and this gate is degenerate.
    """
    cases = []

    with tempfile.TemporaryDirectory(prefix="gate54_inj_") as td:
        tmp_root = Path(td)

        # Injection 1: delete sample_topology.json → commands cannot run.
        inj_dir = tmp_root / "inj1"
        _copy_fork(inj_dir)
        (inj_dir / "graphs" / "sample_topology.json").unlink()
        ok = _run_on(inj_dir)
        cases.append({
            "name": "delete_sample_topology",
            "description": "Remove graphs/sample_topology.json so every "
                           "smoke command fails to open its input.",
            "mutated_ok": ok,
        })

        # Injection 2: strip 'edges' from sample_topology → robustness.py
        # raises KeyError, matching the exact bug the upstream report saw.
        inj_dir = tmp_root / "inj2"
        _copy_fork(inj_dir)
        gp = inj_dir / "graphs" / "sample_topology.json"
        g = json.loads(gp.read_text(encoding="utf-8"))
        g.pop("edges", None)
        gp.write_text(json.dumps(g, indent=2), encoding="utf-8")
        ok = _run_on(inj_dir)
        cases.append({
            "name": "strip_edges_from_topology",
            "description": "Delete the edges key → metrics raise KeyError, "
                           "reproducing the upstream 'result file vs graph "
                           "file' bug inside the fork's own fixture.",
            "mutated_ok": ok,
        })

        # Injection 3: reintroduce the display_name/species contradiction.
        inj_dir = tmp_root / "inj3"
        _copy_fork(inj_dir)
        mp = inj_dir / "data_manifest.json"
        m = json.loads(mp.read_text(encoding="utf-8"))
        for ds in m["datasets"]:
            if ds.get("id") == "malecns-v1.0":
                ds["display_name"] = "Male C. elegans CNS connectome"
                break
        mp.write_text(json.dumps(m, indent=2), encoding="utf-8")
        ok = _run_on(inj_dir)
        cases.append({
            "name": "contradict_display_name_species",
            "description": "Set display_name='Male C. elegans CNS connectome' "
                           "under species='Drosophila melanogaster (male)' "
                           "— reproduces the exact bug Gate 54 is designed "
                           "to catch.",
            "mutated_ok": ok,
        })

        # Injection 4: change LICENSE to non-Apache text.
        inj_dir = tmp_root / "inj4"
        _copy_fork(inj_dir)
        (inj_dir / "LICENSE").write_text("MIT License\n\nPermission is hereby...",
                                         encoding="utf-8")
        ok = _run_on(inj_dir)
        cases.append({
            "name": "wrong_license",
            "description": "Overwrite LICENSE with MIT text so the "
                           "Apache-2.0 declaration check fails.",
            "mutated_ok": ok,
        })

        # Injection 5: delete the upstream-artifact disclaimer so the
        # README's paper-numbers table points at upstream paths without
        # explaining they are result files, not graph files.
        inj_dir = tmp_root / "inj5"
        _copy_fork(inj_dir)
        rp = inj_dir / "README.md"
        txt = rp.read_text(encoding="utf-8")
        # Strip every line that matches the DISCLAIMER_HINT regex, plus
        # any surrounding blockquote lines (>) and the lines that
        # describe the reproducibility status. This must match BOTH the
        # legacy blockquote disclaimer ("Note on the ...") and the
        # current "Reproducibility status (as of v2.94.0)" section.
        new_txt = DISCLAIMER_HINT.sub("", txt)
        # Also strip any leftover blockquote lines that were part of the
        # disclaimer block (lines starting with > that follow a removed
        # disclaimer line). A simple heuristic: remove consecutive >-
        # prefixed lines that mention "upstream" or "result" or "graph".
        import re as _re
        new_txt = _re.sub(
            r">\s*\*\*Note on the[^*]*\*\*[^\n]*\n(?:>\s*[^\n]*\n)*",
            "",
            new_txt,
        )
        # Also remove the "Reproducibility status" paragraph and the
        # v2.94.0 fix blockquote, since those are the current form of
        # the disclaimer.
        new_txt = _re.sub(
            r"\*\*Reproducibility status[^*]*\*\*[^\n]*\n(?:[^\n]*\n)*?"
            r"(?=\n\*\*|\n##|\Z)",
            "",
            new_txt,
        )
        rp.write_text(new_txt, encoding="utf-8")
        ok = _run_on(inj_dir)
        cases.append({
            "name": "strip_disclaimer",
            "description": "Remove the README note explaining that upstream "
                           "artifacts are result files, not graph files. "
                           "The paper-numbers table then silently points "
                           "at broken paths.",
            "mutated_ok": ok,
        })

    return cases


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="GATE 54 — metrics_fork reproducibility self-check")
    ap.add_argument("--fork", type=Path, default=FORK,
                    help=f"path to metrics_fork (default: {FORK})")
    ap.add_argument("--json-out", type=Path, default=None,
                    help="write structured report to PATH")
    ap.add_argument("--skip-injections", action="store_true",
                    help="skip the injection battery (only for CI smoke runs)")
    args = ap.parse_args()

    fork = args.fork.resolve()
    if not fork.is_dir():
        print(f"{GATE_LABEL}: FAIL — fork directory not found: {fork}")
        return 1

    print(f"{GATE_LABEL} — metrics_fork reproducibility self-check")
    print(f"  fork: {fork}")
    print()

    ok, failures, report = check_all(fork)

    print(f"  smoke commands parsed : {report['n_smoke_commands']}")
    print(f"  all command refs      : {report['n_all_command_refs']}")
    print(f"  datasets checked      : {report['datasets_checked']}")
    print()

    for cmd in report["smoke_commands"]:
        print(f"    · {cmd}")
    print()

    if failures:
        print("  [FAIL] defects detected:")
        for f in failures:
            print(f"    ✗ {f}")
    else:
        print("  [PASS] tree, license, commands, manifest, and "
              "disclaimer all consistent")
    print()

    # Gate 39 meta-discipline: prove the gate can go red.
    if not args.skip_injections:
        print("  injection battery (Gate 39 meta-discipline):")
        cases = injections()
        any_green = False
        for c in cases:
            status = "RED" if not c["mutated_ok"] else "GREEN (DEGENERATE)"
            if c["mutated_ok"]:
                any_green = True
            print(f"    {'✓' if not c['mutated_ok'] else '✗'} "
                  f"{c['name']}: {status}")
            print(f"        · {c['description']}")
        if any_green:
            print()
            print("  [FAIL] at least one injection mutation passed the check; "
                  "the gate is degenerate for that defect class")
            failures.append("injection battery: at least one mutation did "
                            "not turn the gate red")
        else:
            print()
            print("  [PASS] every injected defect turned the gate red "
                  "(gate is not degenerate)")

    report["injections"] = [] if args.skip_injections else injections()
    report["ok"] = not failures

    out_path = args.json_out or (SCRIPTS / "_gate54_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n  report: {out_path}")
    print()

    if failures:
        print(f"{GATE_LABEL}: FAIL — {len(failures)} defect(s)")
        return 1
    print(f"{GATE_LABEL}: PASS — metrics_fork is reproducible "
          f"({report['n_smoke_commands']} smoke commands exit 0 with valid "
          f"JSON, manifest internally consistent, injection battery all red)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
