"""核实递质表与连接组的对应关系，避免语料写入错误事实。

疑问：
    body-neurotransmitters 有 1,835,518 行，而 MaleCNS 只有 166,700 个神经元。
    行数远大于神经元数 → 需要查清 'body' 到底是什么、是否混入了其它数据集。

用法:
    python probe_nt.py
"""
import os
from collections import Counter

import pyarrow.feather as feather

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, '..', 'data', 'male_cns', 'flat-connectome'))


def main():
    nt = feather.read_table(os.path.join(DATA, 'body-neurotransmitters-male-cns-v1.0.feather')).to_pandas()
    ann = feather.read_table(os.path.join(DATA, 'body-annotations-male-cns-v1.0-minconf-0.5.feather')).to_pandas()

    print(f"递质表 {nt.shape[0]:,} 行 x {nt.shape[1]} 列")
    print(f"唯一 body 数: {nt['body'].nunique():,}")
    print(f"body 样例: {list(nt['body'].head(8))}")
    print(f"body dtype: {nt['body'].dtype}")
    print()

    print("--- 各行内 id 类字段的唯一值数 ---")
    for c in ['body', 'cell_type']:
        print(f"  {c}: {nt[c].nunique():,} 唯一 / {len(nt):,} 行")
    print()

    print("--- cell_type 分布 Top 20 ---")
    ct = Counter(str(x) for x in nt['cell_type'].dropna())
    for k, v in ct.most_common(20):
        print(f"  {v:>10,}  {k}")
    print()

    ann_ids = set(ann['bodyId'].astype(str))
    nt_bodies = set(nt['body'].astype(str))
    inter = ann_ids & nt_bodies
    print("--- 集合关系 ---")
    print(f"  标注表神经元数        : {len(ann_ids):,}")
    print(f"  递质表 body 数        : {len(nt_bodies):,}")
    print(f"  交集（可映射的神经元）: {len(inter):,}")
    print(f"  标注中无递质记录的    : {len(ann_ids - nt_bodies):,}")
    print(f"  递质表中不在标注的    : {len(nt_bodies - ann_ids):,}")
    print()

    # 只看能映射上的神经元，其共识递质分布（这才是可信数字）
    sub = nt[nt['body'].astype(str).isin(inter)]
    print(f"--- 仅统计可映射神经元（{len(sub):,} 行）的共识递质 ---")
    c = Counter(str(x) for x in sub['consensus_nt'].dropna())
    tot = sum(c.values())
    for k, v in c.most_common(15):
        print(f"  {v:>10,}  {k}  ({v*100.0/tot:.1f}%)")
    print()

    # 其它数据集（不在标注里的那些 body）是什么
    other = nt[~nt['body'].astype(str).isin(ann_ids)]
    print(f"--- 非 MaleCNS 记录（{len(other):,} 行）的 cell_type Top 10 ---")
    c2 = Counter(str(x) for x in other['cell_type'].dropna())
    for k, v in c2.most_common(10):
        print(f"  {v:>10,}  {k}")
    print(f"  这些记录的共识递质分布:")
    c3 = Counter(str(x) for x in other['consensus_nt'].dropna())
    for k, v in c3.most_common(8):
        print(f"    {v:>10,}  {k}")


if __name__ == '__main__':
    main()
