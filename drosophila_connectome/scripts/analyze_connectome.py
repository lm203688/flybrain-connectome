"""MaleCNS 连接组标注数据分析 —— 产出真实统计，作为领域语料的事实来源。

只用已下载的小体积文件（annotations + neurotransmitters），
不依赖那两个还在下的大文件。

产出：
    data/male_cns/stats.json   —— 结构化统计结果
    控制台打印可读报告

用法:
    python analyze_connectome.py
"""
import json
import os
import sys
from collections import Counter

try:
    import pyarrow.feather as feather
except ImportError:
    print("需要 pyarrow：pip install pyarrow")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, '..', 'data', 'male_cns', 'flat-connectome'))
OUT = os.path.normpath(os.path.join(HERE, '..', 'data', 'male_cns', 'stats.json'))


def load(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return None
    return feather.read_table(p).to_pandas()


def topn(counter, n=25):
    return [{'value': str(k), 'count': int(v)} for k, v in counter.most_common(n)]


def main():
    stats = {}

    # ---------- 1. 细胞类型标注 ----------
    ann = load('body-annotations-male-cns-v1.0-minconf-0.5.feather')
    if ann is None:
        print("缺少 annotations 文件")
        sys.exit(1)

    print("=" * 78)
    print("MaleCNS v1.0 连接组标注分析")
    print("=" * 78)
    print(f"标注表: {ann.shape[0]:,} 行 x {ann.shape[1]} 列")
    print(f"列名: {list(ann.columns)}")
    print()

    stats['annotation'] = {
        'rows': int(ann.shape[0]),
        'columns': [str(c) for c in ann.columns],
    }

    # 逐个候选列做分布统计（列名可能随版本变化，用模糊匹配）
    # 注意：必须「精确名优先」，否则 find_col('type') 会误命中 flywireType。
    def find_col(*keys):
        exact = {str(c).lower(): c for c in ann.columns}
        for k in keys:
            if k.lower() in exact:
                return exact[k.lower()]
        for c in ann.columns:
            lc = str(c).lower()
            if any(k.lower() in lc for k in keys):
                return c
        return None

    field_map = {
        'flywire_type': find_col('flywireType', 'flywire_type'),
        'type': find_col('type'),
        'supertype': find_col('supertype'),
        'subclass': find_col('subclass'),
        'superclass': find_col('superclass', 'super_class'),
        'hemibrain_type': find_col('hemibrainType', 'hemibrain'),
        'manc_type': find_col('mancType', 'manc'),
        'side': find_col('somaSide', 'side'),
        'status_label': find_col('statusLabel', 'status'),
        'neuromere': find_col('somaNeuromere', 'neuromere'),
        'entry_nerve': find_col('entryNerve'),
        'exit_nerve': find_col('exitNerve'),
        'receptor_type': find_col('receptorType'),
    }

    print("--- 字段映射 ---")
    for k, v in field_map.items():
        print(f"  {k:>16} -> {v}")
    print()

    dist = {}
    for key, col in field_map.items():
        if col is None:
            continue
        vals = ann[col].dropna()
        c = Counter(str(x) for x in vals)
        dist[key] = {
            'column': str(col),
            'non_null': int(len(vals)),
            'unique': int(len(c)),
            'top': topn(c, 30),
        }
        print(f"--- {key} ({col}) ---")
        print(f"  非空 {len(vals):,}  唯一值 {len(c):,}")
        for item in dist[key]['top'][:15]:
            print(f"    {item['count']:>8,}  {item['value']}")
        print()

    stats['distributions'] = dist

    # ---------- 2. 神经递质 ----------
    nt = load('body-neurotransmitters-male-cns-v1.0.feather')
    if nt is not None:
        print("=" * 78)
        print(f"神经递质表: {nt.shape[0]:,} 行 x {nt.shape[1]} 列")
        print(f"列名: {list(nt.columns)}")
        print()
        nt_col = None
        for cand in ('consensus_nt', 'predicted_nt'):
            if cand in [str(c) for c in nt.columns]:
                nt_col = cand
                break
        if nt_col is None:
            for c in nt.columns:
                if 'nt' in str(c).lower():
                    nt_col = c
                    break
        if nt_col is not None:
            c = Counter(str(x) for x in nt[nt_col].dropna())
            tot = sum(c.values())
            print(f"--- 递质分布 ({nt_col}) ---  唯一 {len(c)}  总计 {tot:,}")
            for k, v in c.most_common(20):
                print(f"    {v:>10,}  {k}  ({v*100.0/max(tot,1):.1f}%)")
            stats['neurotransmitter'] = {
                'rows': int(nt.shape[0]),
                'columns': [str(c) for c in nt.columns],
                'column': str(nt_col),
                'total': int(tot),
                'top': topn(c, 40),
            }
            # 每神经元的共识递质分布（去重到神经元级别）
            if 'body' in [str(c) for c in nt.columns] and 'consensus_nt' in [str(c) for c in nt.columns]:
                per = nt.drop_duplicates(subset=['body'])[['body', 'consensus_nt']]
                c2 = Counter(str(x) for x in per['consensus_nt'].dropna())
                tot2 = sum(c2.values())
                print()
                print(f"--- 每神经元共识递质（去重后 {len(per):,} 个神经元）---")
                for k, v in c2.most_common(20):
                    print(f"    {v:>10,}  {k}  ({v*100.0/max(tot2,1):.1f}%)")
                stats['neurotransmitter_per_neuron'] = {
                    'neurons': int(len(per)),
                    'total_classified': int(tot2),
                    'top': topn(c2, 40),
                }
        print()

    # ---------- 3. 交叉：细胞类型 × 递质 ----------
    if nt is not None and nt_col is not None:
        id_cols = [c for c in ann.columns if 'id' in str(c).lower()]
        stats['id_columns'] = [str(c) for c in id_cols]
        print(f"可用于合并的 id 列: {id_cols}")
        nt_id = 'body' if 'body' in [str(c) for c in nt.columns] else None
        if nt_id is None:
            for c in nt.columns:
                if 'id' in str(c).lower() or str(c) == 'body':
                    nt_id = c
                    break
        print(f"递质表 id 列: {nt_id}")
        if nt_id is not None and 'bodyId' in [str(c) for c in ann.columns]:
            try:
                left = ann[['bodyId', 'type', field_map['superclass']]].rename(
                    columns={field_map['superclass']: 'superclass'})
                right = nt[[nt_id, 'consensus_nt']].rename(columns={nt_id: 'bodyId'})
                right = right.drop_duplicates(subset=['bodyId'])
                left['bodyId'] = left['bodyId'].astype(str)
                right['bodyId'] = right['bodyId'].astype(str)
                m = left.merge(right, on='bodyId', how='inner')
                print(f"交叉表: {len(m):,} 行（匹配上的神经元）")
                ct = m.groupby(['superclass', 'consensus_nt']).size().reset_index(name='n')
                ct = ct.sort_values('n', ascending=False)
                print("--- 超类 × 共识递质 Top 20 ---")
                for _, r in ct.head(20).iterrows():
                    print(f"    {int(r['n']):>8,}  {r['superclass']}  ×  {r['consensus_nt']}")
                stats['cross'] = {
                    'matched': int(len(m)),
                    'superclass_x_nt_top': [
                        {'superclass': str(r['superclass']), 'nt': str(r['consensus_nt']), 'n': int(r['n'])}
                        for _, r in ct.head(80).iterrows()],
                }
                # 具体细胞类型的递质（做 QA 用）
                tt = m.dropna(subset=['type']).groupby(['type', 'consensus_nt']).size().reset_index(name='n')
                tt = tt.sort_values('n', ascending=False)
                print()
                print("--- 具体细胞类型 × 共识递质 Top 15 ---")
                for _, r in tt.head(15).iterrows():
                    print(f"    {int(r['n']):>8,}  {r['type']}  ->  {r['consensus_nt']}")
                stats['cross_type_x_nt'] = [
                    {'type': str(r['type']), 'nt': str(r['consensus_nt']), 'n': int(r['n'])}
                    for _, r in tt.head(200).iterrows()]
            except Exception as e:  # noqa: BLE001
                print('交叉分析跳过:', repr(e))
        print()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print("=" * 78)
    print(f"统计已写入: {OUT}")
    print(f"文件大小: {os.path.getsize(OUT)/1024:.1f} KB")


if __name__ == '__main__':
    main()
