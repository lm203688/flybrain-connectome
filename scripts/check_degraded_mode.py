#!/usr/bin/env python3
"""Verify the toolkit degrades *honestly* when an optional dependency is absent.

`dataprov` is optional (see `[project.optional-dependencies].prov` in
pyproject.toml). `_prov_json()` returns ``None`` when it cannot be imported,
which is a deliberate graceful degradation — but that `None` is dangerous,
because callers that assume a dict blow up. That is exactly what happened:

    get_provenance_bundle -> ERROR: 'NoneType' object has no attribute 'keys'

The tool was advertised, and died — in CI only, because every developer machine
had dataprov installed. A crash on a missing *optional* dependency is a bug
that local testing cannot see by construction, so it needs its own probe.

This checker runs the MCP server twice and asserts BOTH arms:

  blocked arm  — `dataprov` shadowed by a module that raises ImportError.
                 No advertised tool may return an error; the PROV tool must
                 still answer, setting prov_available=false, keeping the
                 structural `motif_provenance`, and explaining why.

  control arm  — `dataprov` importable (when it is installed here). The PROV
                 tool must actually produce a bundle. Without this arm the
                 suite would happily "pass" a build that silently never
                 serializes provenance — the opposite failure, equally bad.

Usage:
    python scripts/check_degraded_mode.py
    python scripts/check_degraded_mode.py --python /path/to/python
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "flybrain-connectome-mcp" / "mcp_connectome" / "server.py"

# Tools served from the derived motif snapshot — callable with no dataset, so
# they are the ones that must keep working in a degraded environment.
OFFLINE_TOOLS = [
    "export_swarm_motifs", "list_blueprints", "list_modules",
    "list_bio_motifs", "batch_generate_topologies", "get_provenance_bundle",
]

ARGS = {
    "get_provenance_bundle": {"blueprint": "predictive_coding_v2"},
    "batch_generate_topologies": {
        "spec_list": [{"blueprint": "sequential", "n_modules": 3,
                       "agents_per_module": 4}], "seed": 42},
}


def _call_server(python: str, extra_path: str | None) -> dict:
    """Spawn the stdio server and return {tool: (is_error, parsed_or_text)}."""
    env = dict(os.environ)
    env.pop("FLYBRAIN_API_KEY", None)  # local stdio transport takes no key
    if extra_path:
        env["PYTHONPATH"] = extra_path + os.pathsep + env.get("PYTHONPATH", "")

    reqs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}]
    for i, tool in enumerate(OFFLINE_TOOLS, start=2):
        reqs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                     "params": {"name": tool, "arguments": ARGS.get(tool, {})}})

    p = subprocess.run([python, str(SERVER)],
                       input="\n".join(json.dumps(r) for r in reqs) + "\n",
                       capture_output=True, text=True, env=env, timeout=900,
                       encoding="utf-8", errors="replace")
    out: dict = {}
    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = msg.get("id")
        if not isinstance(rid, int) or rid < 2:
            continue
        tool = OFFLINE_TOOLS[rid - 2]
        res = msg.get("result") or {}
        text = ""
        try:
            text = res["content"][0]["text"]
        except Exception:  # noqa: BLE001
            pass
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:  # noqa: BLE001
            pass
        out[tool] = (bool(res.get("isError")), parsed, text)
    if not out:
        raise RuntimeError("server produced no tool responses; stderr: %s"
                           % (p.stderr or "")[:400])
    return out


def _assert_batch_honest(res: dict, arm: str) -> str:
    """`batch_generate_topologies` must not hide failures inside a success.

    It wraps each spec in try/except, so a crash becomes a per-item ``error``
    while the envelope still says isError=false. An envelope that reports
    attempts as if they were successes is indistinguishable from a working
    tool, which is how the dataprov crash stayed invisible.
    """
    err, parsed, text = res["batch_generate_topologies"]
    if parsed is None:
        raise RuntimeError("%s: batch_generate_topologies returned non-JSON: %s"
                           % (arm, text[:200]))
    for field in ("attempted", "succeeded", "failed"):
        if field not in parsed:
            raise RuntimeError("%s: batch envelope has no '%s' count — attempts "
                               "and successes are not distinguishable" % (arm, field))
    if parsed["failed"] != 0:
        detail = [r.get("error") for r in parsed.get("results", []) if "error" in r]
        raise RuntimeError("%s: %d/%d specs failed inside a success envelope: %s"
                           % (arm, parsed["failed"], parsed["attempted"], detail[:2]))
    if parsed["succeeded"] != parsed["attempted"]:
        raise RuntimeError("%s: succeeded=%d but attempted=%d"
                           % (arm, parsed["succeeded"], parsed["attempted"]))
    return ("%s: batch envelope honest — attempted=%d succeeded=%d failed=%d"
            % (arm, parsed["attempted"], parsed["succeeded"], parsed["failed"]))


def check_blocked(python: str) -> list[str]:
    log: list[str] = []
    blocker = Path(tempfile.mkdtemp(prefix="nodataprov_"))
    try:
        (blocker / "dataprov.py").write_text(
            'raise ImportError("dataprov is deliberately unavailable in this probe")\n',
            encoding="utf-8")
        res = _call_server(python, str(blocker))

        bad = [t for t, (err, _, _) in res.items() if err]
        if bad:
            for t in bad:
                detail = res[t][2] or "(no text)"
                log.append("    %-28s %s" % (t, detail.splitlines()[0][:110]))
            raise RuntimeError("advertised tool(s) errored with the optional "
                               "dependency absent: %s" % ", ".join(bad))
        log.append("  blocked arm: all %d offline tools answered, none errored"
                   % len(res))

        err, parsed, text = res["get_provenance_bundle"]
        if parsed is None:
            raise RuntimeError("get_provenance_bundle did not return JSON: %s"
                               % text[:200])
        if parsed.get("prov_available") is not False:
            raise RuntimeError("prov_available should be False without dataprov, got %r"
                               % parsed.get("prov_available"))
        if parsed.get("prov_json") is not None:
            raise RuntimeError("prov_json should be null without dataprov")
        if not parsed.get("motif_provenance"):
            raise RuntimeError("structural motif_provenance vanished — the "
                               "degradation dropped the traceability record too")
        if not parsed.get("prov_unavailable"):
            raise RuntimeError("degradation was silent: no explanation field")
        if "dataprov" not in parsed["prov_unavailable"]:
            raise RuntimeError("explanation does not name the missing package")
        log.append("  blocked arm: prov_available=False, prov_json=null, "
                   "motif_provenance preserved, reason names 'dataprov'")
        log.append("  " + _assert_batch_honest(res, "blocked arm"))
    finally:
        shutil.rmtree(blocker, ignore_errors=True)
    return log


def check_control(python: str) -> list[str]:
    log: list[str] = []
    try:
        import dataprov  # noqa: F401
        have = True
    except ImportError:
        have = False
    if not have:
        log.append("  control arm: SKIPPED — dataprov is not installed in this "
                   "interpreter, so the positive path cannot be exercised here. "
                   "CI installs it (`pip install dataprov`).")
        return log

    res = _call_server(python, None)
    bad = [t for t, (err, _, _) in res.items() if err]
    if bad:
        raise RuntimeError("tool(s) errored with dataprov present: %s" % ", ".join(bad))
    _, parsed, text = res["get_provenance_bundle"]
    if parsed is None:
        raise RuntimeError("get_provenance_bundle returned non-JSON: %s" % text[:200])
    if parsed.get("prov_available") is not True:
        raise RuntimeError("dataprov is installed but no bundle was produced — "
                           "provenance is silently missing (prov_available=%r)"
                           % parsed.get("prov_available"))
    span = json.dumps(parsed.get("prov_json") or {}, ensure_ascii=False)
    for token in ("wasAssociatedWith", "FlyCellAtlas"):
        if token not in span:
            raise RuntimeError("bundle is present but lost %r" % token)
    log.append("  control arm: prov_available=True, bundle=%d bytes, "
               "chain intact (wasAssociatedWith + FlyCellAtlas)" % len(span))
    log.append("  " + _assert_batch_honest(res, "control arm"))
    return log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter used to spawn the MCP server")
    args = ap.parse_args()

    print("degraded-mode check — optional dependency: dataprov")
    print("  server: %s" % SERVER)
    try:
        log = check_blocked(args.python)
        log += check_control(args.python)
    except Exception as e:  # noqa: BLE001
        print()
        print("DEGRADED-MODE CHECK: FAIL — %s" % e)
        return 1
    for line in log:
        print(line)
    print()
    print("DEGRADED-MODE CHECK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
