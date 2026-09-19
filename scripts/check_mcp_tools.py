"""Gate: every tool advertised by the MCP server must actually work.

Why this exists
---------------
`_verify.py` (70/70) covers the generator + CLI path. It said nothing about the
MCP handlers, so five advertised tools shipped broken (`NameError: HERE`) while
all gates stayed green. This script closes that gap: it enumerates `tools/list`,
calls **every** tool with a minimal valid argument set, and fails if any returns
`isError: true` — the "advertised but dead" class of bug.

Run:
    python scripts/check_mcp_tools.py            # needs FLYBRAIN_DATA_DIR
    python scripts/check_mcp_tools.py --offline   # skip real-data tools
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "flybrain-connectome-mcp" / "mcp_connectome" / "server.py"

# Minimal valid arguments per tool. Data-backed tools need FLYBRAIN_DATA_DIR.
ARGS = {
    "connectome_overview": {},
    "neuron_info": {"body": 10540},
    "pair_synapses": {"pre": 10540, "post": 12569},
    "neuron_outputs": {"body": 10540, "limit": 3},
    "neuron_inputs": {"body": 12569, "limit": 3},
    "degree": {"body": 10540},
    "search_neurons": {"query": "APL", "limit": 3},
    "superclass_projection": {"superclass": "APL"},
    "hub_targets": {"name": "APL", "limit": 3},
    "list_superclasses": {},
    "pathway": {"source": 10540, "target": 12569, "max_via": 1},
    "export_swarm_motifs": {},
    "list_blueprints": {},
    "list_modules": {},
    "list_bio_motifs": {},
    "batch_generate_topologies": {
        "spec_list": [
            {"blueprint": "sequential", "n_modules": 3, "agents_per_module": 4},
            {"blueprint": "hierarchical_deep", "n_modules": 3, "agents_per_module": 4},
        ],
        "seed": 42, "max_nodes": 64,
    },
    "get_provenance_bundle": {"blueprint": "predictive_coding_v2"},
}

DATA_TOOLS = {
    "connectome_overview", "neuron_info", "pair_synapses", "neuron_outputs",
    "neuron_inputs", "degree", "search_neurons", "superclass_projection",
    "hub_targets", "list_superclasses", "pathway",
}

# Tools whose payload must additionally be valid JSON (machine consumers rely on it).
JSON_TOOLS = {"export_swarm_motifs", "list_blueprints", "list_modules",
              "list_bio_motifs", "batch_generate_topologies",
              "get_provenance_bundle"}


def _speak(python: str, env: dict, reqs: list[dict], timeout: int):
    payload = "\n".join(json.dumps(r) for r in reqs) + "\n"
    p = subprocess.run([python, str(SERVER)], input=payload, capture_output=True,
                       text=True, env=env, timeout=timeout, encoding="utf-8",
                       errors="replace")
    out = []
    for line in (p.stdout or "").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out, p.stderr or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--offline", action="store_true",
                    help="only exercise tools that need no connectome data")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    env = dict(os.environ)
    env.setdefault("NO_PROXY", "127.0.0.1,localhost")
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
              "ALL_PROXY", "all_proxy"):
        env.pop(k, None)

    data_dir = env.get("FLYBRAIN_DATA_DIR") or str(ROOT / "male_cns")
    have_data = Path(data_dir).exists()
    if not have_data:
        print("[warn] FLYBRAIN_DATA_DIR not found (%s); data-backed tools skipped"
              % data_dir)

    # 1. handshake + enumerate
    init, err = _speak(args.python, env, [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "check-mcp-tools", "version": "1.0"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ], args.timeout)
    if not init:
        print("FATAL: no response from MCP server. stderr:\n%s" % err[:1000])
        return 1

    by_id = {m.get("id"): m for m in init}
    if 1 not in by_id:
        print("FATAL: initialize failed: %s" % json.dumps(init)[:400])
        return 1
    tools = by_id[2]["result"]["tools"]
    names = [t["name"] for t in tools]
    print("advertised tools: %d" % len(names))

    fails = []
    for t in tools:
        if not t.get("description") or "inputSchema" not in t:
            fails.append("%s: missing description or inputSchema" % t["name"])
        if t["name"] not in ARGS:
            fails.append("%s: advertised but has no smoke-test arguments "
                         "(add it to ARGS in this script)" % t["name"])

    # 2. call every tool
    skip = DATA_TOOLS if (args.offline or not have_data) else set()
    calls, order = [], []
    for i, name in enumerate(names, start=100):
        if name in skip or name not in ARGS:
            continue
        calls.append({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                      "params": {"name": name, "arguments": ARGS[name]}})
        order.append((i, name))

    results, err = _speak(args.python, env, calls, args.timeout)
    got = {m.get("id"): m for m in results}
    ok_count = 0
    for rid, name in order:
        m = got.get(rid)
        if m is None:
            fails.append("%s: no response" % name)
            print("  [NO REPLY] %s" % name)
            continue
        res = m.get("result", {})
        text = ""
        if isinstance(res.get("content"), list) and res["content"]:
            text = res["content"][0].get("text", "")
        if res.get("isError"):
            fails.append("%s: isError -> %s" % (name, text[:160]))
            print("  [ERROR ] %s -> %s" % (name, text[:110].replace("\n", " ")))
            continue
        if not text.strip():
            fails.append("%s: empty payload" % name)
            print("  [EMPTY ] %s" % name)
            continue
        if name in JSON_TOOLS:
            try:
                json.loads(text)
            except json.JSONDecodeError as e:
                fails.append("%s: payload is not JSON (%s)" % (name, e))
                print("  [BADJS ] %s" % name)
                continue
        ok_count += 1
        print("  [ok    ] %s (%d chars)" % (name, len(text)))

    if skipped := [n for n in names if n in skip]:
        print("skipped (need data): %s" % ", ".join(sorted(skipped)))

    print()
    if fails:
        print("MCP TOOL GATE: FAIL (%d problem(s))" % len(fails))
        for f in fails:
            print("  -", f)
        return 1
    print("MCP TOOL GATE: PASS — %d/%d callable, all advertised tools alive"
          % (ok_count, len(order)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
