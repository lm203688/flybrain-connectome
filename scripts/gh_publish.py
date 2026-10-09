"""GitHub 发布工具（本项目专用）— 经 Contents API 推送，绕过 github.com DNS 封禁。

与 swarmlabs/scripts/gh_push.py 同机制，但 root 固定为本仓库根，默认推到
lm203688/flybrain-connectome。用于把「开源版」源码增量推到 GitHub。

安全：只创建/更新指定文件，绝不删除。删除类操作不在接口内。

用法:
  set GITHUB_TOKEN=ghp_xxx            # 或放 ~/.workbuddy/secrets/github.json
  python scripts/gh_publish.py <file1> [file2 ...] -m "commit msg"
  # 推送整个已 git add 的树：
  python scripts/gh_publish.py --staged -m "feat: initial open-source release"
"""
from __future__ import annotations

import os
import sys
import json
import base64
import argparse
import subprocess
import urllib.parse
import urllib.request
import urllib.error

API = "https://api.github.com"
OWNER = "lm203688"
REPO = "flybrain-connectome"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tls_ctx():
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _http(method, url, token, data=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "flybrain-ghpublish/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(data).encode("utf-8")
    else:
        payload = None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_tls_ctx()) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def _get_sha(token, path, branch="main"):
    enc = urllib.parse.quote(path.replace(os.sep, "/"), safe="/")
    url = f"{API}/repos/{OWNER}/{REPO}/contents/{enc}?ref={branch}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "User-Agent": "flybrain-ghpublish/1.0", "X-GitHub-Api-Version": "2022-11-28"})
    buf = ""
    try:
        with urllib.request.urlopen(req, timeout=30, context=_tls_ctx()) as r:
            if r.status != 200:
                return None
            while True:
                chunk = r.read(8192)
                if not chunk:
                    return None
                buf += chunk.decode("utf-8", "replace")
                m = __import__("re").search(r'"sha"\s*:\s*"([0-9a-f]+)"', buf)
                if m:
                    return m.group(1)
                if len(buf) > 65536:
                    return None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        return None
    except Exception:  # noqa: BLE001
        return None


def _create_repo(token):
    st, body = _http("POST", f"{API}/user/repos", token, {
        "name": REPO, "private": False, "auto_init": False,
        "description": "Traceable synthetic bio-topology generator grounded in "
                       "the real Drosophila male-brain connectome (MaleCNS v1.0).",
        "license_template": "mit",
    })
    if st in (201, 200):
        print("[ok] created repo %s/%s" % (OWNER, REPO))
        return True
    if st == 422:  # already exists
        print("[info] repo %s/%s already exists" % (OWNER, REPO))
        return True
    print("[warn] create repo returned %d: %s" % (st, body[:200]))
    return False


def push_file(token, path, content, message, branch="main"):
    enc = urllib.parse.quote(path.replace(os.sep, "/"), safe="/")
    url = f"{API}/repos/{OWNER}/{REPO}/contents/{enc}?ref={branch}"
    sha = _get_sha(token, path, branch)
    data = {"message": message, "content": base64.b64encode(content).decode("ascii"),
            "branch": branch}
    if sha:
        data["sha"] = sha
    st, body = _http("PUT", url, token, data)
    ok = st in (200, 201)
    print(f"[{'ok' if ok else 'FAIL'}] PUT {path} status={st}"
          + ("" if sha else " (new)"))
    if not ok:
        print("   ", body[:200])
    return ok


def _resolve_token():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        sec = json.load(open(os.path.expanduser("~/.workbuddy/secrets/github.json"),
                            encoding="utf-8"))
        return sec.get("GITHUB_TOKEN")
    except Exception:  # noqa: BLE001
        return None


def _staged_files():
    out = subprocess.check_output(["git", "-C", ROOT, "diff", "--cached",
                                   "--name-only"], text=True)
    return [l.strip() for l in out.splitlines() if l.strip()]


def _files_in_commit(ref):
    """Files touched by a commit.

    `--staged` is only useful *before* committing: once the commit exists the
    index equals HEAD and `git diff --cached` is empty. The normal workflow is
    commit-then-push, so read the commit instead.

    NOTE: with a range like ``A..B`` this is a *cumulative* diff A→B, not the
    union of individual commits — use ``--tracked`` for a full-tree sync.
    """
    out = subprocess.check_output(
        ["git", "-C", ROOT, "diff-tree", "--no-commit-id", "--name-only",
         "-r", "--diff-filter=ACMR", ref], text=True)
    return [l.strip() for l in out.splitlines() if l.strip()]


def _tracked_files():
    """Every file git tracks — i.e. everything .gitignore allows to be published."""
    out = subprocess.check_output(["git", "-C", ROOT, "ls-files", "-z"],
                                  text=True)
    return [l for l in out.split("\0") if l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("-m", "--message", required=True)
    ap.add_argument("--staged", action="store_true",
                    help="push everything already `git add`-ed (pre-commit only)")
    ap.add_argument("--commit", default=None, metavar="REF",
                    help="push every file changed by REF (HEAD, or a commit hash)")
    ap.add_argument("--tracked", action="store_true",
                    help="push every git-tracked file (full-tree sync; use for the "
                         "first push or to guarantee the remote matches HEAD)")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = _resolve_token()
    if not token:
        print("[err] 缺少 GITHUB_TOKEN（env 或 ~/.workbuddy/secrets/github.json）")
        return 2

    if not _create_repo(token):
        return 1

    if args.tracked:
        files = _tracked_files()
    elif args.commit:
        files = _files_in_commit(args.commit)
    elif args.staged:
        files = _staged_files()
    else:
        files = args.files

    if not files:
        print("[warn] 没有要推送的文件")
        return 0

    all_ok = True
    for f in files:
        full = f if os.path.isabs(f) else os.path.join(ROOT, f)
        if not os.path.exists(full):
            print(f"[skip] 不存在: {full}")
            continue
        rel = os.path.relpath(full, ROOT).replace("\\", "/")
        if args.dry_run:
            print(f"[dry] {full}  ->  {OWNER}/{REPO}:{rel}")
            continue
        with open(full, "rb") as fh:
            content = fh.read()
        # core.autocrlf=true would otherwise push CRLF bytes to the remote while
        # the git blob (and thus the repo checkout) is LF — the previous release
        # shipped CRLF on the remote with a real-content-diff of 0. Normalize
        # CRLF -> LF for text files so the remote matches the repository; binary
        # files (null bytes present) are left untouched.
        if b"\x00" not in content[:65536] and b"\r\n" in content:
            content = content.replace(b"\r\n", b"\n")
        if not push_file(token, rel, content, args.message, args.branch):
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
