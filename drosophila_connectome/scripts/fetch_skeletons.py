"""MaleCNS Skeletons SWC 目录下载器（166,700 神经元 3D 骨架）。

背景：
    其他 MaleCNS 数据都是单个 feather 大文件，用 fetch_fast.py / fetch_extra.py
    走「分块多线程」下载。Skeletons SWC 不同——是**目录**，每个神经元一个 .swc
    小文件（平均 52 KB，166,700 个文件，总量约 8-10 GB）。分块下载对小文件毫无
    意义，正确姿势是「多文件并发单连接」。

    数据位置：
      gs://flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/
        -> Male CNS EM 坐标系，8nm 单位
      gs://flyem-male-cns/v1.0/segmentation/skeletons-malecns-mirrored/skeletons-swc/
        -> 已镜像到 L/R 对称，本项目不用（保留原始坐标）

用法：
    python fetch_skeletons.py                              # 下载全部（默认 32 并发）
    python fetch_skeletons.py --workers 64                 # 加大并发
    python fetch_skeletons.py --out D:/skeletons           # 指定输出目录
    python fetch_skeletons.py --status                     # 只看进度
    python fetch_skeletons.py --verify                     # 校验：文件数、大小一致性
    python fetch_skeletons.py --limit 100                  # 只下前 100 个（调试用）

约束：
    - 小文件不需要分块，并发数决定吞吐
    - 断点续传：已存在且大小一致的文件直接跳过
    - 网络重试：每个文件最多 3 次
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BUCKET = 'flyem-male-cns'
PREFIX = 'v1.0/segmentation/skeletons-malecns/skeletons-swc/'
API = 'https://storage.googleapis.com/storage/v1/b/{bucket}/o'
DL = 'https://storage.googleapis.com/download/storage/v1/b/{bucket}/o/{obj}?alt=media'

MAX_RETRY = 3
PROGRESS_FILE = '.progress_skeletons.json'

_lock = threading.Lock()
_progress = {'total': 0, 'done': 0, 'failed': 0, 'bytes': 0, 'start': 0}


def list_skeletons():
    """列出全部 SWC 文件（分页遍历）。

    注意：不保留原始 dict 以避免 211573 items × ~300 B/dict 的
    累积内存（每页 JSON parse 后立即抽 tuple 释放）。
    """
    items = []
    cont = ''
    while True:
        q = {'prefix': PREFIX, 'maxResults': 10000}
        if cont:
            q['pageToken'] = cont
        url = (API.format(bucket=BUCKET) + '?' + urllib.parse.urlencode(q))
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.load(r)
        # 立即抽 tuple，丢弃 dict（每页 10000 项 × ~300 B = 3 MB）
        for it in d.get('items', []):
            items.append((it['name'], int(it['size'])))
        cont = d.get('nextPageToken', '')
        print(f'  listing: {len(items)} files so far...', flush=True)
        if not cont:
            break
    return items


def download_one(name, size, out_dir, dst=None):
    """下载单个 SWC 文件，带重试和断点续传。"""
    if dst is None:
        dst = os.path.join(out_dir, os.path.basename(name))
    # 断点续传：已存在且大小一致直接跳过
    if os.path.exists(dst) and os.path.getsize(dst) == size:
        with _lock:
            _progress['done'] += 1
            _progress['bytes'] += size
        return True, 'skip'

    url = DL.format(bucket=BUCKET, obj=urllib.parse.quote(name, safe=''))
    for attempt in range(1, MAX_RETRY + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(dst, 'wb') as f:
                while True:
                    chunk = r.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            # 大小校验
            if os.path.getsize(dst) == size:
                with _lock:
                    _progress['done'] += 1
                    _progress['bytes'] += size
                return True, 'ok'
            else:
                # 大小不一致，删除重试
                try:
                    os.remove(dst)
                except OSError:
                    pass
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                TimeoutError) as e:
            if attempt == MAX_RETRY:
                with _lock:
                    _progress['failed'] += 1
                return False, f'fail after {MAX_RETRY} retries: {e}'
            time.sleep(0.5 * attempt)
    return False, 'unknown error'


def run(items, out_dir, workers, limit=None):
    if limit:
        items = items[:limit]
    _progress.update({'total': len(items), 'done': 0, 'failed': 0,
                      'bytes': 0, 'start': time.time()})
    os.makedirs(out_dir, exist_ok=True)
    print(f'Target: {len(items)} files, out_dir={out_dir}')

    done_every = max(1, len(items) // 20)
    last_report = 0
    t0 = time.time()

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(download_one, n, s, out_dir): n
                for n, s in items}
        for fut in cf.as_completed(futs):
            ok, msg = fut.result()
            with _lock:
                cur_done = _progress['done']
                cur_failed = _progress['failed']
            if not ok and msg != 'skip':
                # 只打印失败，不刷屏
                print(f'  [FAIL] {futs[fut]}: {msg}', flush=True)
            if cur_done - last_report >= done_every:
                last_report = cur_done
                elapsed = time.time() - t0
                speed = _progress['bytes'] / elapsed if elapsed > 0 else 0
                pct = cur_done * 100 / _progress['total']
                eta = (len(items) - cur_done) / (cur_done / elapsed) if cur_done else 0
                print(f'  [{pct:5.1f}%] {cur_done}/{len(items)}  '
                      f'{_progress["bytes"]/1e6:.0f} MB  '
                      f'{speed/1e6:.2f} MB/s  ETA {eta/60:.1f}min  '
                      f'failed={cur_failed}', flush=True)

    elapsed = time.time() - _progress['start']
    print(f'\nDone: {_progress["done"]}/{_progress["total"]}  '
          f'failed={_progress["failed"]}  '
          f'{_progress["bytes"]/1e9:.2f} GB in {elapsed/60:.1f}min')


def status(out_dir, items):
    if not os.path.exists(out_dir):
        print('output dir not found')
        return
    have_files = set(os.listdir(out_dir))
    total = len(items)
    done = sum(1 for n, _ in items if os.path.basename(n) in have_files)
    bytes_have = 0
    for n in have_files:
        p = os.path.join(out_dir, n)
        if os.path.isfile(p):
            bytes_have += os.path.getsize(p)
    print(f'  expected: {total} files')
    print(f'  present:  {done} files ({done*100/total:.1f}%)')
    print(f'  size:     {bytes_have/1e9:.2f} GB')


def verify(out_dir, items):
    print('Verifying skeletons directory...')
    have_files = set(os.listdir(out_dir))
    total_size = sum(s for _, s in items)
    bad = 0
    missing = 0
    wrong_size = 0
    for name, size in items:
        base = os.path.basename(name)
        p = os.path.join(out_dir, base)
        if base not in have_files:
            missing += 1
        elif not os.path.isfile(p):
            bad += 1
        elif os.path.getsize(p) != size:
            wrong_size += 1
    print(f'  total expected: {len(items)} files / {total_size/1e9:.2f} GB')
    print(f'  missing: {missing}')
    print(f'  wrong size: {wrong_size}')
    print(f'  other bad: {bad}')
    ok = (missing == 0 and wrong_size == 0 and bad == 0)
    print(f'\n  {"ALL OK ✓" if ok else "INCOMPLETE ✗"}')
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out',
                    default='C:/Users/xing/Desktop/flybrain-connectome/male_cns/skeletons-swc')
    ap.add_argument('--workers', type=int, default=32)
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--limit', type=int, default=None,
                    help='only download the first N files (debug)')
    args = ap.parse_args()

    print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Listing skeletons SWC files...')
    items = list_skeletons()
    total_bytes = sum(s for _, s in items)
    print(f'Found {len(items)} files, total {total_bytes/1e9:.2f} GB\n')

    if args.status:
        status(args.out, items)
        return
    if args.verify:
        verify(args.out, items)
        return
    run(items, args.out, args.workers, limit=args.limit)


if __name__ == '__main__':
    main()
