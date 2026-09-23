"""Physically separate Tier-2 IP: push to the private repo, delete from public.

Three modes, all driven by the single source of truth
``core_bridge.TIER2_ARTIFACTS`` (15 entries: 1 stubbed seam + 14 proprietary):

  --verify   Report which Tier-2 artifacts the private repo already holds.
  --push     Upload every Tier-2 artifact to ``flybrain-connectome-core``
             plus the two private-repo doc files.
  --delete   Remove every *non-stubbed* artifact from the public repo
             (requires ``--yes``; the stub stays in place).

``--push`` MUST complete before ``--delete`` runs, or the private repo is
missing IP that the public tree just lost. Gate 8
(``scripts/check_physical_tiering.py``) stays red until both sides are right.

Content sources for ``--push``, resolved in order:
  1. the local repo copy, unless the path is the stubbed seam (the local copy
     of ``module_combinator.py`` is the 5.5 KB public stub, not the IP);
  2. the local backup folder ``TIER2_BACKUP`` (default
     ``C:/Users/xing/Desktop/flybrain-tier2-backup-2026-09-22``).

Usage:
  python scripts/push_core.py --verify
  python scripts/push_core.py --push [--dry-run]
  python scripts/push_core.py --delete            # plan only, nothing removed
  python scripts/push_core.py --delete --yes
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "flybrain-connectome-mcp"))
import core_bridge as cb  # noqa: E402  (path inserted just above)

API = "https://api.github.com"
OWNER = "lm203688"
PUBLIC = "flybrain-connectome"
CORE = "flybrain-connectome-core"
BRANCH = "main"
USER_AGENT = "flybrain-pushcore/1.1"
BACKUP = Path(os.environ.get(
    "TIER2_BACKUP",
    r"C:/Users/xing/Desktop/flybrain-tier2-backup-2026-09-22"))

PRIVATE_DOCS = {
    "README.md": """# flybrain-connectome-core (Proprietary)

Core tier of `flybrain-connectome` — **PROPRIETARY, not open source**.

## Contents

- `module_combinator.py` — COMBINATION_RULES / NESTING_RULES /
  MULTIPLIER_SEMANTICS (7+4+3) and the organism unit libraries
- Discovery pipelines (`scripts/module_discovery/*.py`) with clustering params
- Data artifacts (`discovered_modules*.json`, `worm_modules.json`,
  `superclass_matrix.json`, `superclass_neuropil_matrix.json`,
  `candidate_combination_rules.json`)
- `scripts/data_driven_rules.py` — data-driven rule mining from the matrix

Note: the fingerprint *implementation* (`scripts/fingerprint_organism.py`) is Tier 1
and ships publicly — only the HMAC signing *key* is secret (Tier 3). A copy is kept
here for deploy convenience, not because the code is proprietary.

## Access

This repo is **private**. Access requires:

1. Written agreement with the maintainer
2. Explicit grant via GitHub collaborator invite

## License

Proprietary. See `LICENSE-CLAUSE.md` in the public repo
(`lm203688/flybrain-connectome`) for the three-tier split.

This repo constitutes **Tier 2** — closed, derived-from-CC-BY artifacts.

## Relationship to the public repo

The public repo ships a thin seam (`flybrain-connectome-mcp/module_combinator.py`)
in place of the real implementation. Tool calls that need Tier-2 rules return a
`tier2_required` envelope until the core package is installed:

```bash
pip install flybrain-connectome-core --token <api-key>
# or point at a checkout:
export FLYBRAIN_CORE=/path/to/checkout
```

A bare public install exposes 40 of the 44 MCP tools; installing the core
package restores the 4 combinator tools.
""",
    "LICENSE-CLAUSE.md": """# License & Anti-Plagiarism Tiering

**This is Tier 2 — Proprietary.**

See the parent repo `lm203688/flybrain-connectome` (MIT, public) for the full
three-tier description in `LICENSE-CLAUSE.md`.

## Summary of the split

| Tier | Scope | Location | License |
|------|-------|----------|---------|
| **1 — Open** | API schemas, CLI shells, docs, gate checks, stubs | `lm203688/flybrain-connectome` (public) | MIT |
| **2 — Closed** | Rule tables, discovery pipelines, data artifacts, HMAC signing | **This repo** | **Proprietary** |
| **3 — Service** | Runtime fingerprints, signed organism delivery | API-key gated endpoints | Service TOS |

## Redistribution

No redistribution of Tier 2 artifacts is permitted without prior written
permission from the maintainer.

## Research use

Academic research use is permitted under NDA; contact the maintainer via the
public repo's issues tracker.

## Upstream data licenses

- MaleCNS v1.0 (FlyWire) — CC-BY
- Cook et al. 2019 C. elegans — per Emmons Lab terms

The Tier 2 artifacts are **derived from** these sources and inherit their
upstream licenses; this does not affect the proprietary status of our
clustering assignments, module definitions, and rule tables.
""",
}


def _tls_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _http(method: str, url: str, token: str, data=None):
    """Return (status, body_text) without raising on HTTP errors."""
    headers = {
        "Authorization": "Bearer %s" % token,
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60, context=_tls_ctx()) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def _resolve_token() -> str | None:
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok
    sec = Path.home() / ".workbuddy" / "secrets" / "github.json"
    if not sec.exists():
        return None
    try:
        data = json.loads(sec.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, str) and value.startswith(("ghp_", "github_pat_")):
                return value
    return None


def _enc(rel: str) -> str:
    return urllib.parse.quote(rel.replace(os.sep, "/"), safe="/")


def _contents_url(repo: str, rel: str) -> str:
    return "%s/repos/%s/%s/contents/%s?ref=%s" % (API, OWNER, repo, _enc(rel), BRANCH)


def _get_sha(token: str, repo: str, rel: str) -> str | None:
    status, body = _http("GET", _contents_url(repo, rel), token)
    if status != 200:
        return None
    try:
        return json.loads(body).get("sha")
    except Exception:  # noqa: BLE001
        return None


def _tree_paths(token: str, repo: str):
    status, body = _http("GET",
                         "%s/repos/%s/%s/git/trees/%s?recursive=1" % (API, OWNER, repo, BRANCH),
                         token)
    if status != 200:
        return None
    try:
        return {i.get("path", "") for i in json.loads(body).get("tree", [])
                if i.get("type") == "blob"}
    except Exception:  # noqa: BLE001
        return None


def put_file(token: str, repo: str, rel: str, content: bytes, message: str):
    sha = _get_sha(token, repo, rel)
    data = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        data["sha"] = sha
    status, body = _http("PUT", _contents_url(repo, rel), token, data)
    return status in (200, 201), status, body


def delete_file(token: str, repo: str, rel: str, message: str):
    sha = _get_sha(token, repo, rel)
    if not sha:
        return True, 404, "already absent"
    status, body = _http("DELETE", _contents_url(repo, rel), token,
                         {"message": message, "sha": sha, "branch": BRANCH})
    return status in (200, 204), status, body


def resolve_source(rel: str, stubbed: bool) -> Path | None:
    """Local repo copy wins, except the stubbed seam (local = public stub)."""
    local = ROOT / rel
    if not stubbed and local.exists():
        return local
    backup = BACKUP / rel.replace("/", os.sep)
    if backup.exists():
        return backup
    return None


def _banner(mode: str, artifacts) -> None:
    print("=" * 72)
    print("TIER-2 PHYSICAL SEPARATION  (%s, %d artifacts)" % (mode, len(artifacts)))
    print("  public : %s/%s" % (OWNER, PUBLIC))
    print("  private: %s/%s" % (OWNER, CORE))
    print("  backup : %s%s" % (BACKUP, "" if BACKUP.exists() else "   [MISSING]"))
    print("=" * 72)


def do_verify(token, artifacts) -> int:
    remote = _tree_paths(token, CORE)
    if remote is None:
        print("[err] cannot list %s/%s tree" % (OWNER, CORE))
        return 1
    missing = []
    for rel, _stubbed in artifacts:
        present = rel in remote
        if not present:
            missing.append(rel)
        print("  [%s] %s" % ("ok  " if present else "MISS", rel))
    print("-" * 72)
    print("covered %d/%d, missing %d"
          % (len(artifacts) - len(missing), len(artifacts), len(missing)))
    return 0 if not missing else 1


def do_push(token, artifacts, dry_run: bool) -> int:
    targets = []
    for rel, stubbed in artifacts:
        source = resolve_source(rel, stubbed)
        if source is None:
            print("[skip] no source for %s (not local, not in backup)" % rel)
            continue
        kind = "stub" if stubbed else "ip  "
        targets.append((rel, source.read_bytes(), kind))
    for rel, text in PRIVATE_DOCS.items():
        targets.append((rel, text.encode("utf-8"), "doc "))

    if not targets:
        print("[warn] nothing to push")
        return 1

    ok_all = True
    for rel, content, kind in targets:
        if dry_run:
            print("[dry] PUT %-4s %-56s %7d B" % (kind, rel, len(content)))
            continue
        ok, status, body = put_file(token, CORE, rel, content,
                                    "tier2: %s %s" % (kind.strip(), rel))
        print("[%s] PUT %-4s %-56s %7d B  -> %d"
              % ("ok  " if ok else "FAIL", kind, rel, len(content), status))
        if not ok:
            ok_all = False
            print("       " + body[:220])
    print("-" * 72)
    print("push %s" % ("complete" if ok_all else "INCOMPLETE"))
    return 0 if ok_all else 1


def do_delete(token, artifacts, confirmed: bool, dry_run: bool) -> int:
    targets = [rel for rel, stubbed in artifacts if not stubbed]
    if not confirmed:
        print("[info] destructive: %d artifacts would be removed from %s/%s"
              % (len(targets), OWNER, PUBLIC))
        for rel in targets:
            print("  would delete %s" % rel)
        print("[info] the seam flybrain-connectome-mcp/module_combinator.py stays")
        print("[info] re-run with --yes to execute")
        return 0
    ok_all = True
    for rel in targets:
        if dry_run:
            print("[dry] DELETE %s" % rel)
            continue
        ok, status, body = delete_file(token, PUBLIC, rel,
                                       "security: remove Tier-2 artifact %s" % rel)
        print("[%s] DELETE %-56s -> %d" % ("ok  " if ok else "FAIL", rel, status))
        if not ok:
            ok_all = False
            print("       " + body[:220])
    print("-" * 72)
    print("delete %s" % ("complete" if ok_all else "INCOMPLETE"))
    return 0 if ok_all else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--yes", action="store_true",
                    help="actually perform destructive deletes")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    modes = [m for m, on in (("--verify", args.verify), ("--push", args.push),
                             ("--delete", args.delete)) if on]
    if len(modes) != 1:
        ap.error("choose exactly one of --verify, --push, --delete")
    mode = modes[0][2:]

    token = _resolve_token()
    if not token:
        print("[err] missing GITHUB_TOKEN (env or ~/.workbuddy/secrets/github.json)")
        return 2

    artifacts = list(cb.TIER2_ARTIFACTS)
    _banner(mode.upper(), artifacts)

    if mode == "verify":
        return do_verify(token, artifacts)
    if mode == "push":
        return do_push(token, artifacts, args.dry_run)
    return do_delete(token, artifacts, args.yes, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
