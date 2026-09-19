"""列出 MaleCNS 连接组存储桶内容与体积，用于决定下载范围。

用法: python list_assets.py
纯标准库实现，无需 gcloud/gsutil。
"""
import json
import urllib.request
import urllib.parse

BUCKET = 'flyem-male-cns'


def gcs_list(bucket, prefix):
    """完整列举某前缀下所有对象（自动翻页）。"""
    items, token = [], None
    while True:
        q = {'prefix': prefix, 'maxResults': '1000'}
        if token:
            q['pageToken'] = token
        url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.load(r)
        items += d.get('items', [])
        token = d.get('nextPageToken')
        if not token:
            break
    return items


def gcs_dirs(bucket, prefix):
    """列举某前缀下的直接子目录与文件。"""
    url = (f"https://storage.googleapis.com/storage/v1/b/{bucket}/o?"
           + urllib.parse.urlencode({'prefix': prefix, 'delimiter': '/'}))
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def show(title, prefix):
    print("=" * 72)
    print(title, "  <-", prefix)
    print("=" * 72)
    d = gcs_dirs(BUCKET, prefix)
    for pr in d.get('prefixes', []):
        print("  DIR ", pr)
    for i in d.get('items', []):
        if i['name'].split('/')[-1]:
            print(f"  {int(i['size'])/1e6:>9.1f} MB   {i['name']}")
    print()


print("=" * 72)
print("A. flat-connectome 目录（连接表 / 注释所在，体积已汇总）")
print("=" * 72)
fs = [i for i in gcs_list(BUCKET, 'v1.0/connectome-data/flat-connectome/')
      if i['name'].split('/')[-1]]
tot = 0
for i in sorted(fs, key=lambda x: -int(x['size'])):
    sz = int(i['size'])
    tot += sz
    print(f"  {sz/1e6:>9.1f} MB   {i['name'].split('/')[-1]}")
print(f"  ---- 小计: {tot/1e6:.1f} MB / {len(fs)} 个文件")
print()

show("B. connectome-data 下的全部子目录", 'v1.0/connectome-data/')
show("C. database（neuPrint 数据库快照）", 'v1.0/database/')
show("D. v1.0 顶层文件", 'v1.0/')
