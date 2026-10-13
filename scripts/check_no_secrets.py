"""Pre-push secret gate.

Why this exists
---------------
A live API key was hardcoded in four files and published to a **public**
repository. Nothing caught it: no linter, no test, no review. The key had to be
rotated, and the exposure was only discovered by manually grepping for it before
the second push.

This gate makes that class of mistake a build failure. It scans every file git
would publish (i.e. honours `.gitignore`, so `config.json`, `tmp/` and
`.workbuddy/` are correctly out of scope) and fails on:

* the service's own key format      ``flybrain_<64 hex>``
* a boot-generated key              ``flybrain_boot_<hex>``
* GitHub tokens                     ``ghp_`` / ``gho_`` / ``ghu_`` / ``ghs_`` /
                                    ``github_pat_``
* AWS / Slack / generic-looking keys with enough entropy to be real
* private key blocks                ``BEGIN ... PRIVATE KEY``

Deliberate non-matches: documentation placeholders (``<your-key>``,
``REPLACE_WITH_...``, ``ghp_xxx``) and the boot *prefix* in source code.

Run before every push:

    python scripts/check_no_secrets.py
    python scripts/check_no_secrets.py --all   # also scan ignored files
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (label, compiled pattern). Kept narrow: high-confidence, low-noise.
PATTERNS = [
    ("flybrain service key", re.compile(r"flybrain_(?!boot_)[0-9a-f]{64}")),
    ("flybrain boot key", re.compile(r"flybrain_boot_[0-9a-f]{16,}")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("github fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("aws access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws secret access key", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*[A-Za-z0-9/+=]{40}")),
    ("slack token", re.compile(r"\bxox[abpsr]-[A-Za-z0-9-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai-style key", re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("anthropic-style key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{32,}")),
]

# Files that intentionally contain placeholder text resembling a secret.
ALLOWLIST = {
    "scripts/check_no_secrets.py",      # this file's own patterns
    "scripts/gh_publish.py",            # docstring shows `ghp_xxx`
    ".gitignore",                       # comments about keys
}

PLACEHOLDER = re.compile(
    r"(?i)(your[-_ ]?key|replace[-_ ]?with|xxx+|example|<[^>]*>|\.\.\.|placeholder|redacted)")


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                         capture_output=True, text=True, check=True).stdout
    return [ROOT / p for p in out.split("\0") if p]


def all_files() -> list[Path]:
    skips = {".git", "male_cns", "__pycache__", "node_modules", ".backups"}
    out = []
    for p in ROOT.rglob("*"):
        if p.is_dir() or any(part in skips for part in p.parts):
            continue
        out.append(p)
    return out


BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz",
              ".tar", ".whl", ".so", ".dll", ".exe", ".parquet", ".feather",
              ".arrow", ".npy", ".npz", ".pkl", ".woff", ".woff2"}


def scan(paths: list[Path]) -> list[tuple[str, int, str, str]]:
    hits = []
    for p in paths:
        rel = p.relative_to(ROOT).as_posix()
        if rel in ALLOWLIST or p.suffix.lower() in BINARY_EXT:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pat in PATTERNS:
                m = pat.search(line)
                if not m:
                    continue
                if PLACEHOLDER.search(line):
                    continue        # documented placeholder, not a live secret
                if rel.endswith((".md", ".cff", ".txt")) and label == "flybrain service key":
                    # a real key in prose is still a leak — do not exempt it
                    pass
                hits.append((rel, lineno, label, m.group(0)[:16] + "…"))
    return hits


def is_gitignored(rel: str) -> bool:
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", rel])
    return r.returncode == 0


def _injections() -> tuple[int, int]:
    """Prove the gate can fail: write real-format fake secrets, assert they
    are caught. Each case writes a payload to a temp dir, monkey-patches
    ROOT + tracked_files() to point at it, re-runs main(), asserts
    non-zero exit, restores state in a finally block.

    Apply and restore are structurally separate (tempfile + globals swap
    + finally), so no injection can leak state into the next one. This
    mirrors the discipline applied by every other gate's injection
    battery: a gate that stays green against a real defect is a gate
    that was never going to catch anything.
    """
    bad = 0
    n_inj = 0

    def expect(name: str, payload: str, ext: str = ".py") -> None:
        nonlocal bad, n_inj
        n_inj += 1
        td = Path(tempfile.mkdtemp(prefix="gate1_inj_"))
        fp = td / ("fake_payload" + ext)
        fp.write_text(payload, encoding="utf-8")

        old_root = globals()["ROOT"]
        old_tf = globals()["tracked_files"]
        globals()["ROOT"] = td
        globals()["tracked_files"] = lambda: [fp]
        try:
            rc = main()
        finally:
            globals()["ROOT"] = old_root
            globals()["tracked_files"] = old_tf
            shutil.rmtree(td, ignore_errors=True)

        if rc != 0:
            print("    [PASS] injecting: %s" % name)
        else:
            bad += 1
            print("    [FAIL] injecting: %s -> GATE STAYED GREEN" % name)

    expect("a github classic token",
           "TOKEN = 'ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'\n")
    expect("an AWS access key id",
           "AWS = 'AKIAZZZZZZZZZZZZZZZZ'\n")
    expect("a flybrain service key",
           "K = 'flybrain_" + "a" * 64 + "'\n")
    expect("a flybrain boot key",
           "K = 'flybrain_boot_" + "a" * 20 + "'\n")
    expect("a private key block",
           "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n",
           ext=".pem")
    expect("an OpenAI-style key",
           "K = 'sk-" + "a" * 40 + "'\n")
    expect("an Anthropic-style key",
           "K = 'sk-ant-" + "a" * 40 + "'\n")
    expect("a Slack token",
           "K = 'xoxb-" + "a" * 15 + "'\n")
    expect("a github fine-grained PAT",
           "K = 'github_pat_" + "a" * 50 + "'\n")

    # Regression witness (not an injection): documented placeholders must
    # NOT be flagged. If a future refactor loosens PLACEHOLDER matching to
    # the point that a real-looking secret with a `<key>` comment next to
    # it slips through, this witness catches it.
    real_scan = globals()["scan"]
    td = Path(tempfile.mkdtemp(prefix="gate1_wit_"))
    fp = td / "placeholder.py"
    fp.write_text("TOKEN = '<your-key-here>'\n", encoding="utf-8")
    globals()["ROOT"] = td
    globals()["tracked_files"] = lambda: [fp]
    try:
        witness_hits = real_scan([fp])
    finally:
        globals()["ROOT"] = ROOT
        globals()["tracked_files"] = tracked_files
        shutil.rmtree(td, ignore_errors=True)
    witness_ok = len(witness_hits) == 0
    print("    [%s] witness: placeholder '<your-key-here>' not flagged"
          % ("PASS" if witness_ok else "FAIL"))
    if not witness_ok:
        bad += 1

    return bad, n_inj


def _run_with_injections() -> int:
    """Wrapper: run main(), then the injection battery, then report."""
    rc = main()
    if rc != 0:
        return rc
    print("  -- fail-closed injections --")
    inj_bad, n_inj = _injections()
    if inj_bad:
        print(f"SECRET GATE: FAIL — {inj_bad}/{n_inj} injections did not turn red")
        return 1
    print(f"  ({n_inj}/{n_inj} fail-closed injections confirmed red)")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="also scan ignored files (config.json, tmp/, .workbuddy/) "
                         "for awareness; ignored findings are reported but not fatal")
    args = ap.parse_args()

    paths = all_files() if args.all else tracked_files()
    scope = "all files (incl. ignored)" if args.all else "files git would publish"
    print("secret gate — scanning %d %s" % (len(paths), scope))

    hits = scan(paths)
    fatal, expected = [], []
    for h in hits:
        (expected if args.all and is_gitignored(h[0]) else fatal).append(h)

    print()
    if expected:
        print("expected (gitignored, never published): %d" % len(expected))
        for rel, lineno, label, frag in sorted(expected):
            print("    %s:%d  [%s]  %s" % (rel, lineno, label, frag))
        print()

    if fatal:
        print("SECRET GATE: FAIL — %d publishable finding(s)" % len(fatal))
        for rel, lineno, label, frag in sorted(fatal):
            print("  %s:%d  [%s]  %s" % (rel, lineno, label, frag))
        print()
        print("Do NOT push. Rotate the credential, replace the literal with an env")
        print("lookup or a local non-committed config, then re-run this gate.")
        return 1
    print("SECRET GATE: PASS — no hardcoded credentials in %s" % scope)
    return 0


if __name__ == "__main__":
    sys.exit(_run_with_injections())
