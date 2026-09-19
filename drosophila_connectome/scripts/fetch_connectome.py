#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_connectome.py
===================
通过 Google Cloud Storage JSON API 匿名下载「公开」存储桶对象，无需安装 gsutil / gcloud。
适用于果蝇连接组等公开数据集（MaleCNS v1.0、FlyWire 等，均 CC-BY 公开）。

用法:
  python fetch_connectome.py <bucket> <prefix> <out_dir> [--ext csv,json,parquet] [--dry]

示例:
  python fetch_connectome.py flyem-male-cns v1.0/connectome-data/flat-connectome/ ./male_cns/connectivity --ext csv,json,parquet
  python fetch_connectome.py flyem-male-cns v1.0/connectome-data/annotations/ ./male_cns/annotations --ext csv,json

说明:
  - 仅用 Python 标准库 (urllib)，可在任意装了 Python 的机器运行。
  - 公开桶可匿名列出+下载；私有桶会 403，此时需 gsutil + 凭据。
  - --dry 只列出不下载，用于先评估体积。
"""
import sys
import os
import json
import argparse
import urllib.parse
import urllib.request

API = "https://storage.googleapis.com/storage/v1/b/{bucket}/o"


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "drosophila-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def list_objects(bucket, prefix, delimiter="/"):
    """返回 (items, prefixes)。items 为对象元信息列表，prefixes 为子目录。"""
    items, prefixes = [], []
    base = API.format(bucket=bucket)
    url = f"{base}?prefix={urllib.parse.quote(prefix, safe='')}"
    if delimiter:
        url += f"&delimiter={urllib.parse.quote(delimiter, safe='')}"
    while url:
        data = _get(url)
        items.extend(data.get("items", []))
        prefixes.extend(data.get("prefixes", []))
        nxt = data.get("nextPageToken")
        url = f"{base}?prefix={urllib.parse.quote(prefix, safe='')}&delimiter={urllib.parse.quote(delimiter, safe='')}&pageToken={urllib.parse.quote(nxt, safe='')}" if nxt else None
    return items, prefixes


def download_object(bucket, name, out_path, timeout=600):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    url = f"https://storage.googleapis.com/{bucket}/{urllib.parse.quote(name, safe='')}"
    req = urllib.request.Request(url, headers={"User-Agent": "drosophila-fetch/1.0"})
    total = 0
    with urllib.request.urlopen(req, timeout=timeout) as r, open(out_path, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    return total


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024.0
    return f"{n:.1f}PB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bucket")
    ap.add_argument("prefix")
    ap.add_argument("out_dir")
    ap.add_argument("--ext", default="", help="逗号分隔的扩展名过滤, 如 csv,json,parquet")
    ap.add_argument("--dry", action="store_true", help="只列出不下载")
    args = ap.parse_args()

    exts = [e.strip().lower() for e in args.ext.split(",") if e.strip()] if args.ext else None
    items, prefixes = list_objects(args.bucket, args.prefix)

    # 递归进入子目录(若 delimiter 产生 prefixes 且用户未限定扩展名只想看顶层, 这里默认也下钻一层)
    targets = []
    for it in items:
        name = it["name"]
        size = int(it.get("size", 0))
        if exts:
            if not any(name.lower().endswith("." + e) for e in exts):
                continue
        targets.append((name, size))

    if args.dry:
        print(f"[DRY] bucket={args.bucket} prefix={args.prefix}")
        for name, size in targets:
            print(f"  {human(size):>10}  {name}")
        for p in prefixes:
            print(f"  [dir]       {p}")
        tot = sum(s for _, s in targets)
        print(f"[DRY] 待下载 {len(targets)} 个文件, 共 {human(tot)}")
        return

    os.makedirs(args.out_dir, exist_ok=True)
    tot = 0
    for name, size in targets:
        rel = name[len(args.prefix):].lstrip("/")
        out_path = os.path.join(args.out_dir, rel)
        print(f"[GET] {human(size):>10}  {name}  ->  {out_path}")
        try:
            got = download_object(args.bucket, name, out_path)
            tot += got
        except Exception as e:
            print(f"  [ERR] {name}: {e}")
    print(f"[DONE] 共下载 {human(tot)} 到 {args.out_dir}")


if __name__ == "__main__":
    main()
