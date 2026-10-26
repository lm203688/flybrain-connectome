#!/usr/bin/env python3
"""
flybrain-connectome-mcp / api_server.py
--------------------------------------
Zero-dependency HTTP API server that exposes the connectome query engine
(mcp_connectome.core) to OTHER projects via an API key.

Other projects call it like:

    curl -X POST http://127.0.0.1:8799/query \
         -H "Authorization: Bearer <API_KEY>" \
         -H "Content-Type: application/json" \
         -d '{"tool":"pair_synapses","args":{"pre":10540,"post":12569}}'

Endpoints
    GET  /health   -> {"status":"ok", ...}                 (no auth)
    GET  /tools    -> list of tool names + descriptions      (auth required)
    POST /query    -> {"tool":..., "args":{...}}             (auth required)
                      -> {"ok":true, "result": <python obj as JSON>}

Auth
    Authorization: Bearer <key>   OR   X-API-Key: <key>
    Keys come from config.json (api_keys) and/or env FLYBRAIN_API_KEY.

Config (config.json, all fields overridable by env vars)
    data_dir        where .../data/male_cns lives (also FLYBRAIN_DATA_DIR)
    host            bind host            (also FLYBRAIN_API_HOST, default 127.0.0.1)
    port            bind port            (also FLYBRAIN_API_PORT, default 8799)
    api_keys        list of accepted keys
"""
import os
import sys
import json
import logging
import secrets
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = Path(__file__).resolve().parent
# Repo root = two levels up from mcp_connectome/ (mcp_connectome -> flybrain-connectome-mcp -> repo root).
ROOT = HERE.parent.parent

# ---- load config (config.json next to this file) ----
_cfg_path = HERE / "config.json"
cfg: dict = {}
if _cfg_path.exists():
    try:
        cfg = json.load(open(_cfg_path, encoding="utf-8"))
    except Exception:
        cfg = {}

# data location must be set BEFORE importing core (core reads it at import time)
DATA_DIR = os.environ.get("FLYBRAIN_DATA_DIR", cfg.get("data_dir"))
if DATA_DIR:
    os.environ["FLYBRAIN_DATA_DIR"] = str(DATA_DIR)

HOST = os.environ.get("FLYBRAIN_API_HOST", cfg.get("host", "127.0.0.1"))
PORT = int(os.environ.get("FLYBRAIN_API_PORT", cfg.get("port", 8799)))

api_keys: list = list(cfg.get("api_keys", []))
if os.environ.get("FLYBRAIN_API_KEY"):
    api_keys.append(os.environ["FLYBRAIN_API_KEY"])
if not api_keys:
    # No key configured anywhere. Do NOT fall back to a public constant: a key
    # committed to source/docs can be read by anyone who has the README, which
    # silently defeats the auth layer. Generate a per-boot random key and fail
    # loud so the misconfiguration is visible in the log.
    api_keys = ["flybrain_boot_" + secrets.token_hex(24)]
    # logging.warning (not a bare stderr write): boot-time runs go through
    # run_api.py + pythonw.exe, which has no console, so stderr is invisible
    # there. logging.warning lands in api_runtime.log, and still reaches
    # stderr via logging.lastResort when the module is run directly.
    logging.warning(
        "flybrain api: config.json has no api_keys and FLYBRAIN_API_KEY is unset "
        "-> generated a TEMPORARY per-boot key: %s "
        "(set FLYBRAIN_API_KEY or config.json.api_keys to make it stable)",
        api_keys[0],
    )

# import the query engine (package-local `core`)
sys.path.insert(0, str(HERE))
import core                                                  # noqa: E402
import server as _srv                                        # noqa: E402  (for TOOLS docs)

DISPATCH = {
    "connectome_overview":    lambda a: core.connectome_overview(),
    "neuron_info":            lambda a: core.neuron_info(int(a["body"])),
    "pair_synapses":          lambda a: core.pair_synapses(int(a["pre"]), int(a["post"])),
    "neuron_outputs":         lambda a: core.neuron_outputs(int(a["body"]), int(a.get("top", 20))),
    "neuron_inputs":          lambda a: core.neuron_inputs(int(a["body"]), int(a.get("top", 20))),
    "degree":                 lambda a: core.degree(int(a["body"])),
    "search_neurons":         lambda a: core.search_neurons(a.get("query", ""), a.get("field", "type"), int(a.get("limit", 20))),
    "superclass_projection":  lambda a: core.superclass_projection(a["superclass"]),
    "hub_targets":            lambda a: core.hub_targets(str(a.get("name", ""))),
    "list_superclasses":      lambda a: core.list_superclasses(),
    "pathway":                lambda a: core.pathway(int(a["source"]), int(a["target"]), int(a.get("max_via", 1))),
    "export_swarm_motifs":  lambda a: _srv.export_swarm_motifs(bool(a.get("refresh", False))),
}


def _check_auth(headers) -> bool:
    auth = headers.get("Authorization", "") or headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() in api_keys
    xkey = headers.get("X-API-Key") or headers.get("x-api-key")
    if xkey:
        return xkey in api_keys
    return False


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silence default stderr logging
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, {
                "status": "ok",
                "service": "flybrain-connectome",
                "version": "3.01.0",
                "api_keys_configured": len(api_keys),
                "tools": len(_srv.TOOLS),
            })
        elif self.path.startswith("/tools"):
            if not _check_auth(self.headers):
                self._send(401, {"ok": False, "error": "missing or invalid API key"})
                return
            self._send(200, {"tools": [
                {"name": t["name"], "description": t["description"]} for t in _srv.TOOLS]})
        elif self.path.startswith("/api/v1/export/aibom"):
            # Phase 3: AI Bill of Materials (AIBOM) export.
            # No auth required — the AIBOM is a *disclosure* artifact, not
            # a secret. Its whole purpose is to be publicly readable by
            # third parties evaluating supply-chain disclosure.
            aibom_path = ROOT / "aibom.json"
            if not aibom_path.exists():
                self._send(404, {"ok": False,
                                 "error": "aibom.json not found at repo root; "
                                          "run scripts/check_supply_chain.py --regenerate"})
                return
            try:
                data = json.loads(aibom_path.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                self._send(500, {"ok": False,
                                 "error": "aibom.json malformed: %s" % e})
                return
            self._send(200, {"ok": True, "aibom": data})
        else:
            self._send(404, {"ok": False, "error": "unknown endpoint"})

    def do_POST(self):
        if not self.path.startswith("/query"):
            self._send(404, {"ok": False, "error": "unknown endpoint"})
            return
        if not _check_auth(self.headers):
            self._send(401, {"ok": False, "error": "missing or invalid API key"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads((raw or b"{}").decode("utf-8") or "{}")
        except Exception as e:  # noqa: BLE001
            self._send(400, {"ok": False, "error": "bad JSON: %s" % e})
            return
        tool = payload.get("tool")
        args = payload.get("args", {}) or {}
        if tool not in DISPATCH:
            self._send(400, {"ok": False, "error": "unknown tool: %s" % tool,
                             "available": sorted(DISPATCH)})
            return
        try:
            result = DISPATCH[tool](args)
            self._send(200, {"ok": True, "tool": tool, "result": result})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"ok": False, "tool": tool, "error": str(e)})


def main():
    core.ensure_cache(verbose=True)
    print("[api] flybrain-connectome HTTP API -> http://%s:%d" % (HOST, PORT), flush=True)
    print("[api] api keys configured: %d (rotate before any public exposure)" % len(api_keys), flush=True)
    srv = ThreadingHTTPServer((HOST, PORT), _Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
