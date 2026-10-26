#!/usr/bin/env python3
"""tool_registry.py — single source of truth for the HTTP /query dispatcher.

P1-3 (2026-10-26 upgrade report): MCP exposes 47 tools while HTTP /query
only exposed 12 (a broken promise — users could see the tool in /tools
but get a 400 from /query).  Before this module, ``api_server.DISPATCH``
was a hand-written list of 12 core.connectome lambdas; every MCP tool
added to ``server.TOOLS`` had to be manually duplicated here or the two
transports silently diverged.

This module re-exposes every tool in ``server.TOOLS`` through a single
``http_dispatch(name, args)`` call that delegates to ``server.handle_call``.
The result is:

  * MCP and HTTP now see an identical tool surface (47 == 47).
  * A new MCP tool is automatically reachable over HTTP — no duplication.
  * ``project_status.json`` reports ``transport_gap.mcp_only_tools = 0``.

Design notes
------------
* ``server.handle_call`` already returns JSON strings for most tools
  and formatted text for a few human-readable ones (list_superclasses,
  superclass_projection, pathway, hub_targets).  We parse the string
  as JSON when possible and fall back to returning it raw; either way
  the API client sees ``result`` populated with the same information
  the MCP tool would emit.
* We intentionally do NOT rewrite server.py to have a parallel
  "object-valued" dispatch table — that would double the maintenance
  surface.  Delegation keeps the two transports provably identical.
* Heavy / long-running tools (batch_generate_topologies, compose_virtual_
  organism, expand_organism) are exposed on both transports.  They are
  rate-limited in practice by the fact that HTTP is a localhost service
  with per-key auth; if a public exposure comes up, we can add a
  per-tool timeout policy in api_server.do_POST without touching this
  module.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
# server.py imports `core` at module scope; ensure the package-local
# import resolves even when api_server runs with a different sys.path.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import server as _srv  # noqa: E402


def _try_json(text: str) -> Any:
    """Parse a JSON string if possible; return the raw string otherwise."""
    if not isinstance(text, str):
        return text
    s = text.strip()
    # Fast reject — most handler outputs start with '{' or '['.
    if not s or (s[0] not in "{["):
        return text
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return text


def list_tool_names() -> list[str]:
    """Return the canonical list of exposed tool names."""
    return [t["name"] for t in _srv.TOOLS]


def get_tool(name: str) -> dict:
    """Return the full TOOLS entry for ``name`` or raise KeyError."""
    for t in _srv.TOOLS:
        if t.get("name") == name:
            return t
    raise KeyError(f"unknown tool: {name}")


def build_http_dispatch() -> dict[str, Callable[[dict], Any]]:
    """Build a dispatch dict {name: callable(args)->result}.

    Every name in ``server.TOOLS`` is present.  Each callable delegates
    to ``server.handle_call`` and unwraps the returned JSON string when
    possible so HTTP callers get structured objects on the hot paths.
    """
    dispatch: dict[str, Callable[[dict], Any]] = {}
    for t in _srv.TOOLS:
        name = t["name"]

        def _make_handler(n: str) -> Callable[[dict], Any]:
            def handler(args: dict) -> Any:
                out = _srv.handle_call(n, args or {})
                return _try_json(out)
            return handler

        dispatch[name] = _make_handler(name)
    return dispatch


# Pre-built dispatch table — same shape as the old api_server.DISPATCH,
# but derived from server.TOOLS so it always stays in sync.
DISPATCH = build_http_dispatch()
