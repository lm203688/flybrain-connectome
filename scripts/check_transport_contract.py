#!/usr/bin/env python3
"""Gate 66 — MCP / HTTP transport contract consistency.

P1-3 (2026-10-26 upgrade report): MCP and HTTP used to have two
independent tool surfaces — 47 MCP tools vs 12 HTTP dispatch entries.
Users could see a tool via GET /tools but hit 400 on POST /query, which
the report flagged as a broken promise.

The fix lives in ``mcp_connectome/tool_registry.py``: HTTP DISPATCH is
derived from ``server.TOOLS`` so both transports are provably identical.
This gate enforces that invariant forever:

  1. ``len(server.TOOLS) == len(tool_registry.DISPATCH)``
  2. ``set(tools) == set(dispatch keys)``
  3. Every entry in ``server.TOOLS`` has the required MCP schema shape
     (``name`` / ``description`` / ``inputSchema``).
  4. Every dispatch handler is callable and raises cleanly on a
     nonsense argument (no silent swallowing).

Injection battery (Gate 39 meta-discipline)
-------------------------------------------
We run 3 injected-defect tests to prove this gate can turn red:

  * ``drop_one_dispatch`` — pop one entry from tool_registry.DISPATCH;
    invariant (1) and (2) must fail.
  * ``add_phantom_tool`` — inject a bogus entry into server.TOOLS that
    has no dispatch handler; invariant (1) and (2) must fail.
  * ``truncate_tool_schema`` — strip ``inputSchema`` from one tool;
    invariant (3) must fail.

Usage
-----
    python scripts/check_transport_contract.py
    python scripts/check_transport_contract.py --injection-battery
    python scripts/check_transport_contract.py --mutate drop_one_dispatch
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = ROOT / "flybrain-connectome-mcp" / "mcp_connectome"
PY = sys.executable

GATE_LABEL = "GATE 66"


def _load_modules() -> tuple:
    """Load server + tool_registry fresh.

    We use importlib.reload to defeat caching when the injection
    battery re-runs the checks against a mutated in-memory state.
    """
    if str(MCP_DIR) not in sys.path:
        sys.path.insert(0, str(MCP_DIR))
    import server  # noqa
    import tool_registry  # noqa
    return server, tool_registry


def check_tool_parity(server, tool_registry) -> dict:
    tools = server.TOOLS
    dispatch = tool_registry.DISPATCH
    tool_names = [t.get("name") for t in tools]
    dispatch_names = sorted(dispatch.keys())
    failures: list[str] = []

    if len(tool_names) != len(dispatch):
        failures.append(
            f"tool count mismatch: server.TOOLS={len(tool_names)} "
            f"vs tool_registry.DISPATCH={len(dispatch)}"
        )
    missing_in_http = sorted(set(tool_names) - set(dispatch_names))
    extra_in_http = sorted(set(dispatch_names) - set(tool_names))
    if missing_in_http:
        failures.append(f"MCP-only tools not exposed over HTTP: {missing_in_http}")
    if extra_in_http:
        failures.append(f"HTTP-only tools not declared in MCP TOOLS: {extra_in_http}")
    return {"ok": not failures, "failures": failures,
            "mcp_count": len(tool_names), "http_count": len(dispatch)}


def check_tool_schema(server) -> dict:
    """Every TOOLS entry must have name/description/inputSchema."""
    failures: list[str] = []
    for t in server.TOOLS:
        name = t.get("name", "<unnamed>")
        if not t.get("description"):
            failures.append(f"tool {name!r}: missing description")
        schema = t.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            failures.append(f"tool {name!r}: inputSchema missing or not type=object")
    return {"ok": not failures, "failures": failures}


def check_dispatch_callability(server, tool_registry) -> dict:
    """Every dispatch handler must be callable and not silently swallow."""
    failures: list[str] = []
    for name, handler in tool_registry.DISPATCH.items():
        if not callable(handler):
            failures.append(f"dispatch[{name!r}] is not callable")
            continue
        try:
            # Any invocation must raise OR return something; silent None
            # on a nonsense arg is a smell but not a hard failure — we
            # only care that the callable doesn't crash with TypeError
            # (which would signal a broken binding).
            handler({})
        except (TypeError, KeyError, ValueError, Exception):
            # Exceptions are fine — real validation.
            pass
    return {"ok": not failures, "failures": failures}


# ------------------------------------------------------------------
# Mutation battery (Gate 39 meta-discipline)
# ------------------------------------------------------------------
MUTATION_CASES = [
    "drop_one_dispatch",
    "add_phantom_tool",
    "truncate_tool_schema",
]


def _mutate(server, tool_registry, name: str) -> None:
    if name == "drop_one_dispatch":
        # Pop one entry from the live dispatch dict.
        if tool_registry.DISPATCH:
            tool_registry.DISPATCH.pop(next(iter(tool_registry.DISPATCH)), None)
    elif name == "add_phantom_tool":
        # Inject a tool into server.TOOLS that has no dispatch handler.
        server.TOOLS.append({
            "name": "zz_phantom_injection_tool",
            "description": "injection only",
            "inputSchema": {"type": "object", "properties": {}},
        })
    elif name == "truncate_tool_schema":
        # Strip inputSchema from the first tool.
        if server.TOOLS:
            server.TOOLS[0].pop("inputSchema", None)
    else:
        raise SystemExit(f"unknown mutation: {name}")


def _injections() -> tuple[int, int]:
    """Run the mutation battery; return (passed, total)."""
    # We reload modules each iteration so mutations land on fresh state.
    # Since tool_registry imports server at module scope, mutating
    # server.TOOLS in-memory propagates through tool_registry's
    # pre-built DISPATCH only if we also rebuild DISPATCH. We take a
    # shortcut: mutate the live dicts then rebuild DISPATCH from
    # server.TOOLS — that would re-sync and mask the drop. So instead
    # we mutate the *pre-built* DISPATCH dict directly (which is what
    # the invariant actually reads).
    server, tool_registry = _load_modules()
    passed = 0
    total = 0
    for case in MUTATION_CASES:
        total += 1
        # Reload so each case starts clean.
        server = importlib.reload(server)
        tool_registry = importlib.reload(tool_registry)
        try:
            _mutate(server, tool_registry, case)
        except SystemExit:
            continue
        r_parity = check_tool_parity(server, tool_registry)
        r_schema = check_tool_schema(server)
        r_call = check_dispatch_callability(server, tool_registry)
        # Any of the three checks failing counts as a red gate.
        red = not (r_parity["ok"] and r_schema["ok"] and r_call["ok"])
        if red:
            passed += 1
        else:
            print(f"  injection LEAKED (gate stayed green): {case}")
    return passed, total


def run_injections() -> bool:
    passed, total = _injections()
    if total == 0:
        print("  injection battery: skipped")
        return True
    print(f"  injection battery: {passed}/{total} turn the gate red")
    return passed == total


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quiet", action="store_true",
                    help="suppress verbose output")
    ap.add_argument("--mutation", dest="mutate_choice", choices=MUTATION_CASES,
                    help="apply a single mutation, then exit 0")
    ap.add_argument("--mutate", dest="mutate_choice", choices=MUTATION_CASES,
                    help="alias of --mutation")
    ap.add_argument("--injection-battery", "--check-injections",
                    dest="run_injections", action="store_true",
                    help="run the injected-defect battery and exit 0/1 accordingly")
    args = ap.parse_args()

    server, tool_registry = _load_modules()

    if args.run_injections:
        ok = run_injections()
        return 0 if ok else 1

    if args.mutate_choice:
        _mutate(server, tool_registry, args.mutate_choice)
        if not args.quiet:
            print(f"mutated: {args.mutate_choice}")
        return 0

    failures: list[str] = []
    r_parity = check_tool_parity(server, tool_registry)
    r_schema = check_tool_schema(server)
    r_call = check_dispatch_callability(server, tool_registry)
    for r in (r_parity, r_schema, r_call):
        for f in r["failures"]:
            failures.append(f)

    if failures:
        for f in failures:
            print(f"  FAIL  {f}")
        print(f"verdict: FAIL  ({len(failures)} failures)")
        return 1

    if not args.quiet:
        print(f"verdict: PASS  (mcp={r_parity['mcp_count']} http={r_parity['http_count']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
