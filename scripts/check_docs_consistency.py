"""Docs-vs-code drift gate.

Every check below corresponds to a drift that actually shipped in this repo:

* README said "12 tools" while ``GET /tools`` returned **17** → five tools were
  documented as absent and five real ones undocumented.
* ``~/.workbuddy/mcp.json`` advertised "11 个工具" (a third, older number).
* ``_motif_provenance()`` stamped ``schema_version: 1.2.0`` inside an organism
  stamped ``1.2.1`` — two hardcoded literals that could diverge silently.

The gate parses the *source of truth* out of the code and requires the prose to
agree with it. Run it before every push:

    python scripts/check_docs_consistency.py
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPO = ROOT / "flybrain-connectome-mcp" / "synthetic_bio_topology.py"
SERVER = ROOT / "flybrain-connectome-mcp" / "mcp_connectome" / "server.py"
API = ROOT / "flybrain-connectome-mcp" / "mcp_connectome" / "api_server.py"
CLI = ROOT / "flybrain_cli.py"
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
MCP_JSON = Path.home() / ".workbuddy" / "mcp.json"

problems: list[str] = []
notes: list[str] = []


def ok(label: str, detail: str = "") -> None:
    print("  PASS  %-46s %s" % (label, detail))


def bad(label: str, detail: str) -> None:
    print("  FAIL  %-46s %s" % (label, detail))
    problems.append("%s: %s" % (label, detail))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _module_constants(path: Path, names: tuple[str, ...]) -> dict:
    """Extract simple module-level literal assignments without importing.

    Importing synthetic_bio_topology.py pulls the connectome stack; parsing the
    AST keeps this gate fast and side-effect free. Both plain assignments and
    annotated ones (``BLUEPRINTS: dict[str, dict] = {...}``) are handled — the
    annotated form is an ``ast.AnnAssign`` and is easy to miss.
    """
    tree = ast.parse(read(path))
    out = {}
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
        for tgt in targets:
            if tgt.id in names:
                try:
                    out[tgt.id] = ast.literal_eval(node.value)
                except Exception:  # noqa: BLE001
                    pass
    return out


def _mcp_tool_names() -> list[str]:
    """Parse the ``TOOLS = [...]`` registry in server.py."""
    tree = ast.parse(read(SERVER))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "TOOLS":
                    try:
                        entries = ast.literal_eval(node.value)
                    except Exception:  # noqa: BLE001
                        continue
                    return [e["name"] for e in entries if isinstance(e, dict)]
    return []


def main() -> int:
    readme = read(README)
    print("docs/code consistency gate")
    print("=" * 68)

    # ---------------------------------------------------------------- tools
    print("[1] tool registry  (server.py TOOLS  <-> README / mcp.json)")
    tools = _mcp_tool_names()
    if not tools:
        bad("server.py TOOLS parse", "could not parse the TOOLS registry")
    else:
        ok("source of truth", "%d tools" % len(tools))

        # README count
        counts = re.findall(r"(\d+)\s*[- ]?tools?\b", readme, flags=re.I)
        counts += re.findall(r"(\d+) 个工具", readme)
        wrong = sorted({int(c) for c in counts} - {len(tools)})
        if wrong:
            bad("README tool count", "README says %s, registry has %d"
                % (wrong, len(tools)))
        elif not counts:
            bad("README tool count", "README never states a tool count")
        else:
            ok("README tool count", "%s == %d" % (sorted(set(counts)), len(tools)))

        # every tool name must appear in each prose doc that claims to list them
        for doc in (README, ROOT / "docs" / "mcp_setup.md"):
            if not doc.exists():
                notes.append("%s not found; skipped" % doc.name)
                continue
            text = read(doc)
            missing = [t for t in tools if t not in text]
            if missing:
                bad("%s lists every tool" % doc.name,
                    "missing: %s" % ", ".join(missing))
            else:
                ok("%s lists every tool" % doc.name,
                   "%d/%d named" % (len(tools), len(tools)))
            if ("%d tools" % len(tools)) not in text:
                bad("%s states the total" % doc.name,
                    'never says "%d tools"' % len(tools))
            else:
                ok("%s states the total" % doc.name, "%d tools" % len(tools))

        # mcp.json description (optional; lives outside the repo)
        if MCP_JSON.exists():
            try:
                cfg = json.loads(read(MCP_JSON))
                desc = (cfg.get("mcpServers", {})
                           .get("drosophila-connectome", {}).get("description", ""))
                nums = sorted({int(n) for n in re.findall(r"(\d+)\s*个工具", desc)})
                if nums and nums != [len(tools)]:
                    bad("mcp.json tool count", "says %s, registry has %d" % (nums, len(tools)))
                elif nums:
                    ok("mcp.json tool count", "== %d" % len(tools))
                else:
                    notes.append("mcp.json description states no tool count")
            except Exception as e:  # noqa: BLE001
                notes.append("mcp.json unreadable (%s)" % e)
        else:
            notes.append("mcp.json not found; skipped the registration check")

    # ------------------------------------------------------------- versions
    print("[2] versions  (pyproject  <->  cli  <->  api health  <->  server)")
    py = re.search(r'^version\s*=\s*"([^"]+)"', read(PYPROJECT), flags=re.M)
    py_ver = py.group(1) if py else None
    cli_ver = _module_constants(CLI, ("__version__",)).get("__version__")
    api_ver = re.search(r'"version"\s*:\s*"([^"]+)"', read(API))
    api_ver = api_ver.group(1) if api_ver else None
    srv_ver = re.search(r'"version"\s*:\s*"([^"]+)"', read(SERVER))
    srv_ver = srv_ver.group(1) if srv_ver else None

    for label, val in (("pyproject", py_ver), ("flybrain_cli.__version__", cli_ver),
                       ("api_server health", api_ver), ("server serverInfo", srv_ver)):
        if val is None:
            bad("version parse: %s" % label, "not found")
    seen = {v for v in (py_ver, cli_ver, api_ver, srv_ver) if v}
    if len(seen) == 1:
        ok("package/service version agrees", "all == %s" % seen.pop())
    elif seen:
        bad("package/service version", "disagree: pyproject=%s cli=%s api=%s server=%s"
            % (py_ver, cli_ver, api_ver, srv_ver))

    # --------------------------------------------------------------- schema
    print("[3] schema & counts  (generator constants  <->  README)")
    consts = _module_constants(TOPO, (
        "SCHEMA_VERSION", "MOTIF_PROVENANCE_SCHEMA_VERSION",
        "MODULE_PROFILES", "BLUEPRINTS", "BLUEPRINT_SOURCE_MOTIF"))
    schema = consts.get("SCHEMA_VERSION")
    prov_schema = consts.get("MOTIF_PROVENANCE_SCHEMA_VERSION")
    n_blueprints = len(consts.get("BLUEPRINTS") or {})
    n_modules = len(consts.get("MODULE_PROFILES") or {})
    motif_map = consts.get("BLUEPRINT_SOURCE_MOTIF") or {}

    if schema:
        if ("schema v%s" % schema) not in readme and schema not in readme:
            bad("README states schema version", "generator is v%s, README silent" % schema)
        else:
            ok("README states schema version", "v%s" % schema)
    if prov_schema and schema and prov_schema == schema:
        bad("prov vs top-level schema", "both %s — the split was meant to be explicit"
            % schema)
    else:
        ok("schema split explicit", "organism=%s motif_provenance=%s"
           % (schema, prov_schema))

    for label, n, pat in (("blueprint", n_blueprints, r"\b(\d+)\s+(?:presets?|blueprints?)\b"),
                          ("module", n_modules, r"\b(\d+)\s+modules?\b")):
        if not n:
            bad("%s count parse" % label, "constant not found")
            continue
        found = sorted({int(m) for m in re.findall(pat, readme, flags=re.I)})
        if n not in found:
            bad("README %s count" % label, "README says %s, code has %d" % (found or "nothing", n))
        else:
            ok("README %s count" % label, "%d" % n)

    # bio-prior bookkeeping: README claims every non-bio blueprint is marked
    if motif_map and n_blueprints:
        def _motif(v):
            return v.get("motif", "none") if isinstance(v, dict) else (v or "none")
        non_bio = [b for b, v in motif_map.items() if _motif(v) == "none"]
        ok("blueprints marked non-bio", "%d of %d" % (len(non_bio), n_blueprints))
        if len(non_bio) + len(motif_map) != n_blueprints + len(non_bio):
            notes.append("BLUEPRINT_SOURCE_MOTIF and BLUEPRINTS have different sizes")

    # ---------------------------------------------------------- data anchors
    print("[4] dataset anchors  (README numbers  <->  literals in code)")
    topo_src = read(TOPO)
    for anchor in ("124177617", "166700"):
        pretty = "{:,}".format(int(anchor))
        if pretty not in readme:
            bad("README anchor %s" % pretty, "not present in README")
        elif anchor not in topo_src:
            bad("code anchor %s" % anchor, "README cites it but code has no such literal")
        else:
            ok("anchor %s consistent" % pretty, "in README and code")

    print("=" * 68)
    for n in notes:
        print("  note: %s" % n)
    if problems:
        print("DOCS CONSISTENCY: FAIL (%d)" % len(problems))
        for p in problems:
            print("  -", p)
        return 1
    print("DOCS CONSISTENCY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
