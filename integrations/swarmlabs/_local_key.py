"""Same-machine API-key resolution for the dev/experiment scripts.

These scripts used to hardcode the live API key. It ended up published in a
public repository, so it was rotated and every literal removed. Never
re-introduce one — `scripts/check_no_secrets.py` fails the build if you do.

Resolution order (first hit wins):

1. ``$FLYBRAIN_API_KEY``
2. the service's own ``mcp_connectome/config.json`` → ``api_keys[0]``
   (gitignored; the authoritative local source)

Returns ``""`` when neither exists, which is fine for anything running with
``--motif-source local`` — that path reads the committed motif snapshot and
never needs a key.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_CANDIDATES = (
    REPO_ROOT / "flybrain-connectome-mcp" / "mcp_connectome" / "config.json",
    Path(os.environ.get("FLYBRAIN_HOME", "")) / "flybrain-connectome-mcp"
    / "mcp_connectome" / "config.json",
)


def local_api_key() -> str:
    """Return the local service key, or '' if none is configured."""
    env = os.environ.get("FLYBRAIN_API_KEY")
    if env:
        return env
    for p in CONFIG_CANDIDATES:
        try:
            keys = json.loads(p.read_text(encoding="utf-8")).get("api_keys") or []
            if keys:
                return str(keys[0])
        except (OSError, ValueError):
            continue
    return ""


if __name__ == "__main__":
    k = local_api_key()
    print("FLYBRAIN_API_KEY resolved: %s" % ("%s… (%d chars)" % (k[:14], len(k)) if k else "(none)"))
