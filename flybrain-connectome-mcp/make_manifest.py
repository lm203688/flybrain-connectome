"""
make_manifest.py
-----------------
Build `DATA_MANIFEST.json` for the flybrain-connectome base folder.

Two sections:
  files[]       -- the authoritative MaleCNS v1.0 data under <base>/male_cns,
                   each with size + sha256, so the 5.6 GB copy can be verified
                   or re-downloaded anywhere.
  repo_files[]  -- the much smaller code / script / doc inventory across the
                   base (excluding the data dir, .backups and caches), so a
                   reader can see exactly which artifacts make up the project.

Run:
    python make_manifest.py
    python make_manifest.py --base C:\\Users\\xing\\Desktop\\flybrain-connectome
    python make_manifest.py --data-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BASE = Path(r"C:\Users\xing\Desktop\flybrain-connectome")

# never walk into these when inventorying code/docs
SKIP_DIRS = {".backups", "__pycache__", ".git", "node_modules", "archive"}
SKIP_SUFFIX = {".pyc", ".npy", ".feather", ".done"}
# the manifest can't meaningfully hash itself, and the marker is derived
SKIP_NAMES = {"DATA_MANIFEST.json", "DATA_MANIFEST.json.done"}


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def walk_files(root: Path, skip_dirs: set[str] | None = None,
               skip_suffixes: set[str] | None = None,
               skip_names: set[str] | None = None):
    skip_dirs = skip_dirs or set()
    skip_suffixes = skip_suffixes or set()
    skip_names = skip_names or set()
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        parts = set(p.relative_to(root).parts)
        if parts & skip_dirs:
            continue
        if p.suffix.lower() in skip_suffixes or p.name in skip_names:
            continue
        yield p


def build_manifest(base: Path, data_dir: Path | None = None,
                   data_only: bool = False) -> dict:
    base = base.resolve()
    data_dir = (data_dir or (base / "male_cns")).resolve()

    data_files, data_total = [], 0
    if data_dir.exists():
        for p in walk_files(data_dir):
            sz = p.stat().st_size
            data_files.append({"rel": str(p.relative_to(data_dir)),
                               "bytes": sz, "sha256": sha256_of(p)})
            data_total += sz

    manifest = {
        "dataset": "MaleCNS v1.0 (male Drosophila brain connectome), CC-BY",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "base": str(base),
        "root": str(data_dir),
        "file_count": len(data_files),
        "total_bytes": data_total,
        "files": data_files,
        "verify_hint": "逐文件比 sha256；缺失则从 gs://flyem-male-cns 重新下载（见 "
                       "drosophila_connectome/scripts/fetch_fast.py）",
    }

    if not data_only:
        repo_files, repo_total = [], 0
        for p in walk_files(base, SKIP_DIRS, SKIP_SUFFIX, SKIP_NAMES):
            if data_dir in p.parents:
                continue
            sz = p.stat().st_size
            repo_files.append({"rel": str(p.relative_to(base)),
                               "bytes": sz, "sha256": sha256_of(p)})
            repo_total += sz
        manifest["repo_file_count"] = len(repo_files)
        manifest["repo_total_bytes"] = repo_total
        manifest["repo_files"] = repo_files
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the flybrain DATA_MANIFEST")
    ap.add_argument("--base", default=str(DEFAULT_BASE))
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--data-only", action="store_true")
    args = ap.parse_args(argv)

    base = Path(args.base)
    out = Path(args.out) if args.out else base / "DATA_MANIFEST.json"
    m = build_manifest(base, Path(args.data_dir) if args.data_dir else None,
                       args.data_only)
    out.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print("files=%d (%.2f GB) repo_files=%d -> %s" % (
        m["file_count"], m["total_bytes"] / 1e9, m.get("repo_file_count", 0), out))
    # stdout can be unreliable in some shells — leave a marker file too
    Path(str(out) + ".done").write_text(
        "files=%d repo_files=%d -> %s" % (m["file_count"],
                                          m.get("repo_file_count", 0), out),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
