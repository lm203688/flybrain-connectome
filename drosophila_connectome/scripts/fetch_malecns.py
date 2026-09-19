"""MaleCNS v1.0 连接组分级下载器（纯标准库，免 gcloud/gsutil）。

设计原则：不盲目下全量 31GB。按用途分三档，默认只下「知识档」，
因为跑 LLM 领域 SFT 只需要结构化统计，不需要突触级原始数据。

用法:
    python fetch_malecns.py --tier knowledge     # 默认，约 1.9 GB
    python fetch_malecns.py --tier simulation    # 加仿真必需，约 8.8 GB
    python fetch_malecns.py --tier full          # 全量，约 31 GB
    python fetch_malecns.py --list               # 只列清单不下
    python fetch_malecns.py --tier knowledge --dry-run
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BUCKET = 'flyem-male-cns'
PREFIX = 'v1.0/connectome-data/flat-connectome/'
API = 'https://storage.googleapis.com/storage/v1/b/{bucket}/o'
DL = 'https://storage.googleapis.com/download/storage/v1/b/{bucket}/o/{obj}?alt=media'

# ---------------------------------------------------------------- 分级定义
# 每个文件的「为什么需要它」都写清楚，避免以后自己忘了为什么下这个。
TIERS = {
    'knowledge': [
        # (文件名, 用途说明)
        ('body-annotations-male-cns-v1.0-minconf-0.5.feather',
         '细胞类型标注表：flywireType/type/superclass/hemibrainType，做领域知识库的核心'),
        ('body-neurotransmitters-male-cns-v1.0.feather',
         '每个神经元的神经递质预测类型 —— 决定兴奋/抑制，也是知识问答素材'),
        ('body-stats-male-cns-v1.0-minconf-0.5.feather',
         '每个神经元的结构统计（上下游数量、突触总数）—— 用于生成度数分布/枢纽神经元等问答'),
        ('connectome-weights-male-cns-v1.0-minconf-0.5.feather',
         '连接表（谁连谁、几条突触、权重）—— 用于计算 rich-club / 模块化 / 回路 motif'),
    ],
    'simulation': [
        ('syn-points-male-cns-v1.0-minconf-0.5.feather',
         '突触前位点坐标级数据 —— 只有做无身仿真才需要'),
        ('syn-partners-male-cns-v1.0-minconf-0.5.feather',
         '突触伙伴配对明细（含位置）—— 只有做仿真才需要'),
        ('tbar-neurotransmitters-male-cns-v1.0.feather',
         'T-bar（突触前结构）级递质预测 —— 仿真时用于逐突触定符号'),
    ],
}


def list_objects(prefix=PREFIX):
    """列举 flat-connectome 下全部对象。"""
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
            return items


def human(n):
    for u in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}TB"


def download(name, out_dir, retries=3):
    """断点续传式下载（用 Range 头）。"""
    dest = os.path.join(out_dir, name)
    obj = urllib.parse.quote(PREFIX + name, safe='')
    url = DL.format(bucket=BUCKET, obj=obj)

    for attempt in range(1, retries + 1):
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        req = urllib.request.Request(url)
        if have:
            req.add_header('Range', f'bytes={have}-')
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                total_hdr = r.headers.get('Content-Length')
                if r.status == 206:
                    mode, total = 'ab', have + int(total_hdr or 0)
                else:
                    mode, total, have = 'wb', int(total_hdr or 0), 0
                t0, done = time.time(), have
                with open(dest, mode) as f:
                    while True:
                        chunk = r.read(1 << 22)  # 4MB
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            pct = done * 100 / total
                            sp = (done - have) / max(time.time() - t0, 0.01)
                            sys.stdout.write(
                                f"\r    {pct:5.1f}%  {human(done)}/{human(total)}  "
                                f"{human(sp)}/s   ")
                            sys.stdout.flush()
            sys.stdout.write("\n")
            final = os.path.getsize(dest)
            if total and final >= total:
                return True
            print(f"    不完整 ({human(final)}/{human(total)})，重试 {attempt}/{retries}")
        except Exception as e:
            print(f"    出错: {e}  (重试 {attempt}/{retries})")
            time.sleep(3)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', default='knowledge',
                    choices=['knowledge', 'simulation', 'full', 'all'])
    ap.add_argument('--out', default=None, help='输出目录，默认 ../data/male_cns/flat-connectome')
    ap.add_argument('--list', action='store_true', help='只列清单')
    ap.add_argument('--dry-run', action='store_true', help='只算体积不下')
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.out or os.path.normpath(os.path.join(here, '..', 'data', 'male_cns', 'flat-connectome'))
    os.makedirs(out_dir, exist_ok=True)

    print("正在列举 MaleCNS v1.0 flat-connectome ...")
    allobj = {i['name'].split('/')[-1]: int(i['size']) for i in list_objects()}
    print(f"共 {len(allobj)} 个文件，合计 {human(sum(allobj.values()))}")
    print()

    # 组装本次要下的清单
    if args.tier == 'full':
        want = [(n, '全量档：全部下载') for n in allobj]
    else:
        want = []
        for t in (['knowledge', 'simulation'] if args.tier in ('simulation', 'all')
                  else ['knowledge']):
            want += TIERS[t]
        # full 里独有的、不属于任何分级的文件，simulation/all 时也带上
        if args.tier in ('simulation', 'all'):
            known = {n for lst in TIERS.values() for n, _ in lst}
            want += [(n, '仿真档补充') for n in allobj if n not in known]

    total = sum(allobj.get(n, 0) for n, _ in want)
    print(f"本次档位: {args.tier}   文件数 {len(want)}   总体积 {human(total)}")
    print("-" * 74)
    for n, why in sorted(want, key=lambda x: -allobj.get(x[0], 0)):
        sz = human(allobj.get(n, 0))
        mark = "已存在" if os.path.exists(os.path.join(out_dir, n)) else ""
        print(f"  {sz:>10}  {n}")
        print(f"              {why}  {mark}")
    print("-" * 74)

    if args.list or args.dry_run:
        print("(仅清单模式，未下载)")
        return

    ok, fail = [], []
    for n, _ in sorted(want, key=lambda x: allobj.get(x[0], 0)):  # 先下小的
        dest = os.path.join(out_dir, n)
        if os.path.exists(dest) and os.path.getsize(dest) == allobj.get(n):
            print(f"  跳过（已完整）: {n}")
            ok.append(n)
            continue
        print(f"  下载 {n}  ({human(allobj.get(n,0))})")
        (ok if download(n, out_dir) else fail).append(n)

    print()
    print("=" * 74)
    print(f"完成 {len(ok)} 个，失败 {len(fail)} 个")
    if fail:
        print("失败清单:")
        for n in fail:
            print("  -", n)
        sys.exit(1)
    print(f"输出目录: {out_dir}")
    print(f"实际占用: {human(sum(os.path.getsize(os.path.join(out_dir,f)) for f in os.listdir(out_dir)))}")


if __name__ == '__main__':
    main()
