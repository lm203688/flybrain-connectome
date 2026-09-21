"""把 IP 文件推到 private repo lm203688/flybrain-connectome-core。

与 gh_publish.py 同机制（Contents API），但推私有仓。
用法:
  python scripts/push_core.py --path scripts/module_discovery/step1_build_matrix.py -m "msg"
  python scripts/push_core.py --list  # 列出待推 IP 文件
"""
from __future__ import annotations
import os, sys, json, base64, argparse, subprocess
import urllib.parse, urllib.request, urllib.error

API = "https://api.github.com"
OWNER = "lm203688"
REPO = "flybrain-connectome-core"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tier 2 IP 文件清单（要推到 private 仓的）
IP_FILES = [
    "scripts/module_discovery/step1_build_matrix.py",
    "scripts/module_discovery/step1b_neuropil_cluster.py",
    "scripts/module_discovery/step1c_worm_modules.py",
    "scripts/module_discovery/step2_cluster.py",
    "scripts/module_discovery/step3_build_library.py",
    "scripts/module_discovery/README.md",
    "scripts/fingerprint_organism.py",
    "flybrain-connectome-mcp/module_combinator.py",
    "male_cns/superclass_matrix.json",
    "male_cns/discovered_modules.json",
    "male_cns/discovered_modules_neuropil.json",
    "data/worm/worm_modules.json",
]

# Tier 2 目录说明文件（要在 private 仓写）
PRIVATE_DOCS = {
    "README.md": """# flybrain-connectome-core (Proprietary)

Core tier of `flybrain-connectome` — **PROPRIETARY, not open source**.

## Contents

- `MODULE_PROFILES` (19 module capability definitions)
- `COMBINATION_RULES` / `NESTING_RULES` / `MULTIPLIER_SEMANTICS` (7+4+3)
- Discovery pipelines (`module_discovery/*.py`) with clustering parameters
- Data artifacts (`discovered_modules*.json`, `worm_modules.json`, `superclass_matrix.json`)
- HMAC fingerprint signing (`fingerprint_organism.py`)

## Access

This repo is **private**. Access requires:

1. Written agreement with the maintainer
2. Explicit grant via GitHub collaborator invite

## License

Proprietary. See `LICENSE-CLAUSE.md` in the public repo
(`lm203688/flybrain-connectome`) for the three-tier split.

This repo constitutes **Tier 2** — closed, derived-from-CC-BY artifacts.

## Relationship to the public repo

The public repo (`lm203688/flybrain-connectome`) ships stub versions of the
files listed above. To activate full functionality:

```bash
pip install flybrain-connectome-core --token <api-key>
# or set:
export FLYBRAIN_CORE=***  # path to a local checkout
```

The public stubs detect `flybrain-core` availability via `try/except ImportError`
and degrade gracefully to reduced functionality.
""",
    "LICENSE-CLAUSE.md": """# License & Anti-Plagiarism Tiering

**This is Tier 2 — Proprietary.**

See the parent repo `lm203688/flybrain-connectome` (MIT, public) for the full
three-tier description in `LICENSE-CLAUSE.md`.

## Summary of the split

| Tier | Scope | Location | License |
|------|-------|----------|---------|
| **1 — Open** | API schemas, CLI shells, docs, gate checks, stubs | `lm203688/flybrain-connectome` (public) | MIT |
| **2 — Closed** | Module parameters, discovery pipelines, data artifacts, HMAC signing | **This repo** | **Proprietary** |
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


def _tls_ctx():
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _load_token():
    env = os.environ.get("GITHUB_TOKEN")
    if env:
        return env
    secrets_path = os.path.expanduser("~/.workbuddy/secrets/github.json")
    with open(secrets_path, encoding="utf-8") as f:
        d = json.load(f)
    for v in d.values():
        if isinstance(v, str) and v.startswith("ghp_"):
            return v
    for v in d.values():
        if isinstance(v, str) and len(v) > 30:
            return v
    raise SystemExit("no GITHUB_TOKEN found")


def _http(method, url, token, data=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "flybrain-pushcore/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60, context=_tls_ctx()) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def _get_sha(token, path):
    enc = urllib.parse.quote(path, safe="/")
    url = f"{API}/repos/{OWNER}/{REPO}/contents/{enc}?ref=main"
    status, body = _http("GET", url, token)
    if status != 200:
        return None
    import re
    m = re.search(r'"sha"\s*:\s*"([0-9a-f]+)"', body)
    return m.group(1) if m else None


def _put_file(token, path, content_bytes, message, content_type="base64"):
    enc = base64.b64encode(content_bytes).decode("ascii")
    sha = _get_sha(token, path)
    body = {
        "message": message,
        "content": enc,
        "content_type": content_type,
        "branch": "main",
    }
    if sha:
        body["sha"] = sha
    url = f"{API}/repos/{OWNER}/{REPO}/contents/{urllib.parse.quote(path, safe='/')}"
    status, resp = _http("PUT", url, token, body)
    return status, resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", help="file path relative to repo root")
    ap.add_argument("--text", help="inline content (alternative to --path)")
    ap.add_argument("--dest", help="destination path in private repo (default: same as --path)")
    ap.add_argument("--list", action="store_true", help="list planned IP files")
    ap.add_argument("--all", action="store_true", help="push all IP files + docs")
    ap.add_argument("-m", "--message", default="chore: sync core tier")
    a = ap.parse_args()

    token = _load_token()

    if a.list:
        print("IP files (Tier 2, to migrate to private repo):")
        for p in IP_FILES:
            fp = os.path.join(ROOT, p)
            exists = os.path.exists(fp)
            size = os.path.getsize(fp) if exists else 0
            print(f"  [{'x' if exists else ' '}] {p}  ({size} bytes)")
        print("Plus docs:")
        for p in PRIVATE_DOCS:
            print(f"  [+] {p}")
        return

    if a.all:
        targets = []
        for p in IP_FILES:
            fp = os.path.join(ROOT, p)
            if not os.path.exists(fp):
                print(f"SKIP (missing): {p}")
                continue
            with open(fp, "rb") as f:
                data = f.read()
            targets.append((p, data))
        for p, text in PRIVATE_DOCS.items():
            targets.append((p, text.encode("utf-8")))
        for path, data in targets:
            status, resp = _put_file(token, path, data, a.message)
            ok = status in (200, 201)
            print(f"[{'OK' if ok else 'FAIL'}] {path}  ({status})")
            if not ok:
                print(f"   {resp[:300]}")
        return

    if a.path:
        fp = os.path.join(ROOT, a.path)
        if not os.path.exists(fp):
            print(f"NOT FOUND: {fp}")
            return
        with open(fp, "rb") as f:
            data = f.read()
        dest = a.dest or a.path
        status, resp = _put_file(token, dest, data, a.message)
        print(f"PUT {dest}: {status}")
        print(resp[:400])
        return

    if a.text and a.dest:
        status, resp = _put_file(token, a.dest, a.text.encode("utf-8"), a.message)
        print(f"PUT {a.dest}: {status}")
        print(resp[:400])
        return

    ap.print_help()


if __name__ == "__main__":
    main()
