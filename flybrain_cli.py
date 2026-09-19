#!/usr/bin/env python3
"""
flybrain — unified developer CLI for the flybrain-connectome toolkit.
==================================================================

A zero-third-party-dependency command line that wraps the project's three
public surfaces:

  serve      start the local HTTP API server (default :8799)
  query      call one connectome tool over HTTP
  motifs     export / pull the derived SwarmLabs motif document
  generate   compose a synthetic bio-topology (pass-through to the generator)
  verify     run the end-to-end smoke test (_verify.py)

Design notes
------------
* Standard library only — no pip install required to run in-repo.
* All module imports are resolved relative to THIS file, so the CLI works
  both when run from the repo root and after a `pip install` (the console
  script simply executes this module's `main()`).
* The connectome data (5.63 GB) is NEVER embedded. `serve`/`query` need a
  running service backed by your own local copy of MaleCNS v1.0; `generate`
  and `motifs --out` (offline snapshot) need no data at all.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MCP_DIR = HERE / "flybrain-connectome-mcp"
MCP_PKG = MCP_DIR / "mcp_connectome"
MOTIFS_DIR = MCP_DIR / "motifs"


def _add_paths() -> None:
    for p in (str(MCP_DIR), str(MCP_PKG), str(MOTIFS_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _default_data_dir() -> str:
    cand = HERE / "male_cns"
    return str(cand) if cand.exists() else ""


# ---------------------------------------------------------------------- #
# subcommands
# ---------------------------------------------------------------------- #
def cmd_serve(args) -> int:
    _add_paths()
    if not os.environ.get("FLYBRAIN_DATA_DIR"):
        d = _default_data_dir()
        if d:
            os.environ["FLYBRAIN_DATA_DIR"] = d
    if args.host:
        os.environ["FLYBRAIN_API_HOST"] = args.host
    if args.port:
        os.environ["FLYBRAIN_API_PORT"] = str(args.port)
    if args.api_key:
        os.environ["FLYBRAIN_API_KEY"] = args.api_key
    import api_server  # noqa: WPS433 (late import keeps --help dependency-free)
    api_server.main()
    return 0


def cmd_query(args) -> int:
    _add_paths()
    from flybrain_connectome_client import FlybrainHTTPClient, FlybrainUnavailable
    c = FlybrainHTTPClient(args.base_url, args.api_key)
    payload = json.loads(args.args) if args.args else {}
    try:
        result = c.query(args.tool, payload)
    except FlybrainUnavailable as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_motifs(args) -> int:
    _add_paths()
    from flybrain_connectome_client import FlybrainHTTPClient, FlybrainUnavailable
    c = FlybrainHTTPClient(args.base_url, args.api_key)
    try:
        doc = c.export_swarm_motifs(refresh=args.refresh)
    except FlybrainUnavailable as e:
        print("ERROR: %s" % e, file=sys.stderr)
        print("hint: the offline snapshot lives at "
              "flybrain-connectome-mcp/motifs/swarm_agent_topology_motifs.json",
              file=sys.stderr)
        return 1
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote %s (%d bytes)" % (args.out, len(text)))
    else:
        print(text)
    return 0


def cmd_generate(args) -> int:
    _add_paths()
    import synthetic_bio_topology as c1
    return c1.main(args.rest or [])


def cmd_verify(args) -> int:
    _add_paths()
    import _verify
    return _verify.main([])


# ---------------------------------------------------------------------- #
# argument parser
# ---------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="flybrain",
        description="flybrain-connectome developer CLI "
                    "(connectome service + traceable synthetic bio-topologies).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="start the HTTP API server")
    s.add_argument("--host", default=None, help="bind host (default 127.0.0.1)")
    s.add_argument("--port", type=int, default=None, help="bind port (default 8799)")
    s.add_argument("--api-key", default=None, help="override FLYBRAIN_API_KEY")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("query", help="call a connectome tool over HTTP")
    s.add_argument("tool", help="tool name, e.g. pair_synapses")
    s.add_argument("--args", default=None,
                   help='JSON object of tool args, e.g. \'{"pre":10540,"post":12569}\'')
    s.add_argument("--base-url", default=None, help="service base url")
    s.add_argument("--api-key", default=None, help="override FLYBRAIN_API_KEY")
    s.set_defaults(func=cmd_query)

    s = sub.add_parser("motifs", help="export / pull derived motifs")
    s.add_argument("--out", default=None, help="write motif doc to this file")
    s.add_argument("--refresh", action="store_true",
                   help="ask the service to re-extract motifs first")
    s.add_argument("--base-url", default=None, help="service base url")
    s.add_argument("--api-key", default=None, help="override FLYBRAIN_API_KEY")
    s.set_defaults(func=cmd_motifs)

    s = sub.add_parser("generate", help="compose a synthetic bio-topology")
    s.add_argument("rest", nargs=argparse.REMAINDER,
                   help="arguments passed through to synthetic_bio_topology "
                        "(try: generate --help after this)")
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("verify", help="run the end-to-end smoke test")
    s.set_defaults(func=cmd_verify)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
