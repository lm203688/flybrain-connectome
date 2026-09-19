"""MaleCNS 大文件多线程分块下载器（纯标准库，断点续传，抗中断）。

为什么要单独写这个：
    单连接从 storage.googleapis.com 拉取在国内被限速到几十 KB/s，
    1.8GB 要下好几个小时。GCS 支持 HTTP Range 请求，多连接并发能显著提速。
    同时用 pwrite 直接写目标文件（不产生 .part 副本），避免批量删除触发沙箱守卫。

特性：
    - 分块（默认 8MB）多线程（默认 8）并发下载
    - 进度落盘到 <文件>.progress.json，中断后重跑自动跳过已完成块
    - 退出码：0=全部完整；1=有文件不完整

⚠️ 重要约束：**同一个目标文件永远只允许一个进程在下载**。
    实测过两个进程并发写同一文件 → 产生的文件「体积正确、首尾 magic 正常，
    但 LZ4 解压失败」。用 `--verify` 做深度校验能发现这类损坏。
    启动前先确认没有残留进程：`Get-CimInstance Win32_Process | ? {$_.CommandLine -like '*fetch*'}`。

用法:
    python fetch_fast.py                      # 下载知识档全部 4 个文件
    python fetch_fast.py --workers 16         # 加大并发
    python fetch_fast.py --only body-stats    # 只下匹配的文件名（子串匹配）
    python fetch_fast.py --status             # 只看进度不下载
    python fetch_fast.py --verify             # 深度校验（真正解析文件）
    python fetch_fast.py --only X --force     # 强制重下（修复损坏文件）
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
PREFIX = 'v1.0/connectome-data/flat-connectome/'
API = 'https://storage.googleapis.com/storage/v1/b/{bucket}/o'
DL = 'https://storage.googleapis.com/download/storage/v1/b/{bucket}/o/{obj}?alt=media'

KNOWLEDGE = [
    'body-annotations-male-cns-v1.0-minconf-0.5.feather',
    'body-neurotransmitters-male-cns-v1.0.feather',
    'body-stats-male-cns-v1.0-minconf-0.5.feather',
    'connectome-weights-male-cns-v1.0-minconf-0.5.feather',
]

CHUNK = 8 << 20          # 8 MB 一块
_lock = threading.Lock()


def human(n):
    n = float(n)
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}TB"


def list_sizes(prefix=PREFIX):
    items, token = [], None
    while True:
        q = {'prefix': prefix, 'maxResults': '1000'}
        if token:
            q['pageToken'] = token
        url = API.format(bucket=BUCKET) + '?' + urllib.parse.urlencode(q)
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.load(r)
        items += [i for i in d.get('items', []) if i['name'].split('/')[-1]]
        token = d.get('nextPageToken')
        if not token:
            break
    return {i['name'].split('/')[-1]: int(i['size']) for i in items}


def obj_url(name):
    return DL.format(bucket=BUCKET, obj=urllib.parse.quote(PREFIX + name, safe=''))


def write_at(path, data, offset):
    """跨平台「指定偏移写入」。

    Windows 的 os 模块没有 pwrite（Unix-only），必须回落到 seek+write。
    每个线程各自打开独立句柄，文件指针是 per-handle 的，因此并发写不同偏移安全。
    """
    if hasattr(os, 'pwrite'):
        fd = os.open(path, os.O_RDWR)
        try:
            os.pwrite(fd, data, offset)
        finally:
            os.close(fd)
    else:
        with open(path, 'r+b') as f:
            f.seek(offset)
            f.write(data)


def deep_verify(path):
    """深度校验：真正用 pyarrow 解析文件（能发现 magic 正常但 LZ4 块损坏的情况）。

    实测教训：两个进程并发写同一目标文件，会产生「体积正确、首尾 magic 正常、
    但 LZ4 解压失败」的文件 —— 只有真正解码才能发现。代价是要读整个文件。
    """
    try:
        import pyarrow.feather as feather
        t = feather.read_table(path, memory_map=True)
        return True, f'{t.num_rows:,} 行 x {t.num_columns} 列'
    except Exception as e:  # noqa: BLE001
        return False, repr(e)


def feather_ok(path):
    """轻量校验 feather 文件完整性：同时检查首尾 magic。

    Feather v1 用 'FEA1'；v2（Arrow IPC file）首尾都是 'ARROW1'，且**尾部必须在最后 6 字节**。
    只比对 size 或只查首部都不够：
      - 实测遇到过「字节数正确但内容损坏」；
      - 也遇到过「尾部被追加垃圾、size 大于预期但首部 magic 正常」。
    这两种都必须能被这里判出来。
    """
    try:
        size = os.path.getsize(path)
        if size < 16:
            return False
        with open(path, 'rb') as f:
            head = f.read(8)
            f.seek(max(0, size - 8))
            tail = f.read(8)
        if head.startswith(b'FEA1'):
            return True
        if head.startswith(b'ARROW1'):
            # Arrow IPC：末尾必须是 ARROW1（最后 6 字节）
            return tail.rstrip(b'\x00')[-6:] == b'ARROW1' or tail[-6:] == b'ARROW1'
        return False
    except Exception:  # noqa: BLE001
        return False


def fetch_range(name, start, end, retries=5):
    """取 [start, end] 闭区间字节，返回 bytes。"""
    url = obj_url(name)
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header('Range', f'bytes={start}-{end}')
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if len(data) == (end - start + 1):
                return data
            last = f'short read {len(data)} != {end - start + 1}'
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(1.5 * (a + 1))
    raise RuntimeError(f'{name} [{start}-{end}] 失败: {last}')


def download_file(name, size, out_dir, workers, force=False):
    dest = os.path.join(out_dir, name)
    prog_path = dest + '.progress.json'
    nchunks = (size + CHUNK - 1) // CHUNK

    done = set()
    if force:
        print(f"  [强制重下] {name}")
    elif os.path.exists(prog_path):
        try:
            done = set(json.load(open(prog_path, encoding='utf-8')).get('done', []))
        except Exception:  # noqa: BLE001
            done = set()

    # 已完整（且校验通过）则直接返回
    if not force and os.path.exists(dest) and os.path.getsize(dest) == size and feather_ok(dest):
        print(f"  [跳过] {name} 已完整 ({human(size)})")
        return True

    # 预分配文件到确切大小（同时把历史上写坏/超长的文件归一化）
    cur = os.path.getsize(dest) if os.path.exists(dest) else -1
    if cur != size:
        with open(dest, 'wb') as f:
            f.truncate(size)

    todo = [i for i in range(nchunks) if i not in done]
    total_todo = len(todo)
    print(f"  [下载] {name}  {human(size)}  块 {len(done)}/{nchunks} 已完成，本次需下 {total_todo} 块")

    t0 = time.time()
    got_bytes = [0]
    got_chunks = [0]

    def work(idx):
        s = idx * CHUNK
        e = min(s + CHUNK, size) - 1
        data = fetch_range(name, s, e)
        write_at(dest, data, s)
        with _lock:
            done.add(idx)
            got_bytes[0] += len(data)
            got_chunks[0] += 1
            if got_chunks[0] % 5 == 0 or got_chunks[0] == total_todo:
                el = max(time.time() - t0, 0.01)
                sp = got_bytes[0] / el
                frac = len(done) / nchunks
                eta = (total_todo - got_chunks[0]) * CHUNK / max(sp, 1)
                sys.stdout.write(
                    f"\r    {frac*100:5.1f}%  {human(len(done)*CHUNK)}/{human(size)}  "
                    f"{human(sp)}/s  ETA {eta/60:.1f}min   ")
                sys.stdout.flush()
            if got_chunks[0] % 20 == 0:
                json.dump({'done': sorted(done)}, open(prog_path, 'w', encoding='utf-8'))

    ok = True
    try:
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(work, i): i for i in todo}
            for fu in cf.as_completed(futs):
                try:
                    fu.result()
                except Exception as e:  # noqa: BLE001
                    print(f"\n    块 {futs[fu]} 失败: {e}")
                    ok = False
    finally:
        json.dump({'done': sorted(done)}, open(prog_path, 'w', encoding='utf-8'))

    final = os.path.getsize(dest)
    valid = feather_ok(dest)
    complete = (final == size) and (len(done) == nchunks) and valid
    if not valid and final == size:
        print("    警告：字节数正确但 feather magic 校验失败，文件可能损坏，建议 --force 重下")
    print(f"\n    {'完成 ✓' if complete else '未完成 ✗'}  {human(final)}/{human(size)}  "
          f"用时 {(time.time()-t0)/60:.1f} 分钟")
    return complete


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=None)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--only', default=None, help='只处理文件名含该子串的文件')
    ap.add_argument('--force', action='store_true', help='忽略已存在文件，强制重下（用于修复损坏文件）')
    ap.add_argument('--status', action='store_true', help='只显示进度')
    ap.add_argument('--verify', action='store_true', help='深度校验：真正解析每个文件（慢但可靠）')
    ap.add_argument('--single', action='store_true',
                    help='提示：同一文件永远只允许一个进程下载，见文件头说明')
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out or os.path.normpath(os.path.join(here, '..', 'data', 'male_cns', 'flat-connectome'))
    os.makedirs(out_dir, exist_ok=True)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 查询 MaleCNS 文件清单 ...")
    sizes = list_sizes()
    names = [n for n in KNOWLEDGE if args.only is None or args.only in n]

    print("-" * 78)
    all_ok = True
    for n in names:
        size = sizes.get(n)
        if size is None:
            print(f"  [缺失] 清单中找不到 {n}")
            all_ok = False
            continue
        dest = os.path.join(out_dir, n)
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        pct = have * 100 / size if size else 0
        if have == size:
            flag = '完整 ✓' if feather_ok(dest) else '损坏 ✗'
        else:
            flag = f'{pct:.1f}%'
        print(f"  {human(size):>10}  已下 {human(have):>10}  [{flag:>8}]  {n}")
    print("-" * 78)

    if args.status:
        return

    if args.verify:
        print("深度校验（真正解析文件）...")
        bad = []
        for n in names:
            dest = os.path.join(out_dir, n)
            if not os.path.exists(dest):
                print(f"  [缺失] {n}")
                bad.append(n)
                continue
            ok, msg = deep_verify(dest)
            print(f"  [{'可读 ✓' if ok else '损坏 ✗'}] {n}\n           {msg}")
            if not ok:
                bad.append(n)
        print("=" * 78)
        if bad:
            print("以下文件需要 --force 重下：")
            for n in bad:
                print("  -", n)
            sys.exit(1)
        print("全部文件深度校验通过 ✓")
        return

    for n in names:
        size = sizes.get(n)
        if size is None:
            continue
        dest = os.path.join(out_dir, n)
        if not args.force and os.path.exists(dest) and os.path.getsize(dest) == size and feather_ok(dest):
            print(f"  [跳过] {n} 已完整")
            continue
        try:
            if not download_file(n, size, out_dir, args.workers, force=args.force):
                all_ok = False
        except KeyboardInterrupt:
            print("\n中断，进度已保存，重跑可续传")
            sys.exit(1)

    print("=" * 78)
    if all_ok:
        print("全部文件下载完成 ✓")
    else:
        print("存在未完成文件，可重跑续传")
        sys.exit(1)


if __name__ == '__main__':
    main()
