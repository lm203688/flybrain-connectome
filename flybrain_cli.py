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
  info       report the resolved toolkit / data / snapshot paths

Design notes
------------
* Standard library only — no pip install required to run in-repo.
* The toolkit is located through `resolve_layout()`: `$FLYBRAIN_HOME` first,
  then this file's directory, then the cwd. That makes all three shapes work:
  clone-and-run, `pip install -e .`, and a launcher installed elsewhere.
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
__version__ = "2.19.0"
_TOOLKIT_DIRNAME = "flybrain-connectome-mcp"
_TOOLKIT_MARKER = "synthetic_bio_topology.py"


def resolve_layout():
    """Locate the flybrain-connectome checkout that holds the toolkit.

    Returns ``(root, mcp_dir, mcp_pkg, motifs_dir)``.

    Resolution order — first match wins:

    1. ``$FLYBRAIN_HOME`` — explicit override; point it at a checkout.
    2. the directory of this file — clone-and-run, and ``pip install -e .``
       (an editable install maps this module back to the real checkout).
    3. the current working directory — a launcher installed elsewhere that is
       being run from inside a checkout.

    Each candidate is probed both as a repo root (``<c>/flybrain-connectome-mcp``)
    and as the toolkit directory itself.
    """
    cands = []
    env = os.environ.get("FLYBRAIN_HOME")
    if env:
        cands.append(Path(env).expanduser().resolve())
    cands.append(HERE)
    try:
        cands.append(Path.cwd().resolve())
    except OSError:  # pragma: no cover - deleted cwd
        pass

    seen = set()
    for root in cands:
        if root in seen:
            continue
        seen.add(root)
        for mcp in (root / _TOOLKIT_DIRNAME, root):
            if (mcp / _TOOLKIT_MARKER).exists():
                return root, mcp, mcp / "mcp_connectome", mcp / "motifs"
    # Nothing found: return the in-repo guess so error messages can name it.
    mcp = HERE / _TOOLKIT_DIRNAME
    return HERE, mcp, mcp / "mcp_connectome", mcp / "motifs"


ROOT, MCP_DIR, MCP_PKG, MOTIFS_DIR = resolve_layout()


def _add_paths() -> None:
    for p in (str(MCP_DIR), str(MCP_PKG), str(MOTIFS_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _require_toolkit() -> None:
    """Fail loudly with an actionable message instead of an ImportError trace."""
    if not (MCP_DIR / _TOOLKIT_MARKER).exists():
        sys.stderr.write(
            "ERROR: cannot locate the flybrain-connectome toolkit.\n"
            "  looked in : %s\n"
            "  and also  : %s\n"
            "Fix: run the CLI from inside a checkout, or point FLYBRAIN_HOME at one:\n"
            "  export FLYBRAIN_HOME=/path/to/flybrain-connectome\n"
            "Clone: https://github.com/lm203688/flybrain-connectome\n"
            % (MCP_DIR, HERE))
        raise SystemExit(2)


def _default_data_dir() -> str:
    cand = ROOT / "male_cns"
    return str(cand) if cand.exists() else ""


def _resolve_key(explicit: str | None = None) -> str | None:
    """Same-machine key discovery, in precedence order.

    1. ``--api-key`` on the command line
    2. ``$FLYBRAIN_API_KEY``
    3. ``mcp_connectome/config.json`` → ``api_keys[0]`` (via the client's
       ``resolve_local_api_key``), so a local service works without exporting
       anything. A downstream copy of the client has no such file and returns
       nothing, which is why this is a fallback and not the primary path.
    """
    if explicit:
        return explicit
    env = os.environ.get("FLYBRAIN_API_KEY")
    if env:
        return env
    try:
        from flybrain_connectome_client import resolve_local_api_key
        key, _src = resolve_local_api_key()
        return key or None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------- #
# subcommands
# ---------------------------------------------------------------------- #
def cmd_serve(args) -> int:
    _add_paths()
    _require_toolkit()
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
    _require_toolkit()
    from flybrain_connectome_client import FlybrainHTTPClient, FlybrainUnavailable
    c = FlybrainHTTPClient(args.base_url, _resolve_key(args.api_key))
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
    _require_toolkit()
    from flybrain_connectome_client import FlybrainHTTPClient, FlybrainUnavailable
    c = FlybrainHTTPClient(args.base_url, _resolve_key(args.api_key))
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
    _require_toolkit()
    import synthetic_bio_topology as c1
    return c1.main(args.rest or [])


def cmd_generate_raw(rest: list[str]) -> int:
    """Forward argv verbatim to the C1 generator.

    We deliberately bypass argparse for `generate`: `nargs=REMAINDER` is
    unreliable for leading `--flags` inside a sub-parser (Python >= 3.13 mixes
    values into the leftover list, breaking flag/value pairing). Forwarding the
    raw tail keeps the generator's own CLI authoritative and makes
    `flybrain generate --help` print the real generator options.
    """
    _add_paths()
    _require_toolkit()
    import synthetic_bio_topology as c1
    saved = sys.argv[0]
    sys.argv[0] = "flybrain generate"
    try:
        return c1.main(rest)
    finally:
        sys.argv[0] = saved


def cmd_verify(args) -> int:
    _add_paths()
    _require_toolkit()
    if not os.environ.get("FLYBRAIN_DATA_DIR"):
        d = _default_data_dir()
        if d:
            os.environ["FLYBRAIN_DATA_DIR"] = d
    import _verify
    return _verify.main([])


def cmd_info(args) -> int:
    """Report what this launcher resolved — the one command that diagnoses
    a broken install (wrong toolkit root, missing data dir, missing snapshot)."""
    ok = (MCP_DIR / _TOOLKIT_MARKER).exists()
    snap = MOTIFS_DIR / "swarm_agent_topology_motifs.json"
    data = os.environ.get("FLYBRAIN_DATA_DIR") or _default_data_dir()
    print("flybrain-connectome — launcher report")
    print("  cli version      : %s" % __version__)
    print("  this file        : %s" % Path(__file__).resolve())
    print("  cwd              : %s" % Path.cwd())
    print("  FLYBRAIN_HOME    : %s" % (os.environ.get("FLYBRAIN_HOME") or "(unset)"))
    print("  toolkit root     : %s  %s" % (ROOT, "[ok]" if ok else "[MISSING]"))
    print("  toolkit dir      : %s" % MCP_DIR)
    print("  motif snapshot   : %s  %s"
          % (snap, "[ok, %d bytes]" % snap.stat().st_size if snap.exists() else "[MISSING]"))
    print("  data dir         : %s  %s" % (data or "(unset)", "[ok]" if data and Path(data).exists() else "[missing]"))
    print("  api key          : %s" % ("set" if (os.environ.get("FLYBRAIN_API_KEY")
          or (MCP_PKG / "config.json").exists()) else "not configured"))
    if ok:
        try:
            _add_paths()
            from server import TOOLS  # noqa: WPS433
            print("  tools exposed    : %d" % len(TOOLS))
        except Exception as e:  # noqa: BLE001
            print("  tools exposed    : (could not load: %s)" % e)
    else:
        print("\nToolkit missing — set FLYBRAIN_HOME or run from inside a checkout.")
        return 2
    return 0


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
                        "(run `flybrain generate --help` to see them)")
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("verify", help="run the end-to-end smoke test")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("info", help="report the resolved toolkit/data paths")
    s.set_defaults(func=cmd_info)
    return ap


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # `generate` is a thin pass-through to synthetic_bio_topology's own CLI.
    # Handle it before argparse so flags are forwarded verbatim (see
    # cmd_generate_raw for why REMAINDER is not used here).
    if raw and raw[0] == "generate":
        return int(cmd_generate_raw(raw[1:]))

    ap = build_parser()
    args, unknown = ap.parse_known_args(raw)
    if unknown:
        ap.error("unrecognized arguments: %s" % " ".join(unknown))
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
