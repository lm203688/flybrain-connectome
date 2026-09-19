"""MaleCNS 连接表（connectome-weights）分析 —— 产出真实连接统计。

产出：
    data/male_cns/connectivity_stats.json
    控制台可读报告

注意：连接表体积大（1GB feather），优先用 pyarrow 做聚合，避免整表转 pandas。

用法:
    python analyze_connectivity.py
"""
import json
import os
import sys

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data', 'male_cns', 'flat-connectome')
ANN = os.path.join(DATA, 'body-annotations-male-cns-v1.0-minconf-0.5.feather')
CONN = os.path.join(DATA, 'connectome-weights-male-cns-v1.0-minconf-0.5.feather')
OUT = os.path.join(ROOT, 'data', 'male_cns', 'connectivity_stats.json')


def pick(cols, *keywords):
    """在列名里挑第一个「包含任一关键词」的列（不区分大小写）。"""
    lower = {str(c).lower(): c for c in cols}
    for k in keywords:
        for lc, orig in lower.items():
            if k in lc:
                return orig
    return None


def main():
    if not os.path.exists(CONN):
        print('连接表尚未下载完成:', CONN)
        sys.exit(1)

    print(f'读取连接表 {os.path.getsize(CONN)/1e6:.0f} MB ...')
    t = feather.read_table(CONN, memory_map=True)
    print(f'行数 {t.num_rows:,}  列 {t.num_columns}')
    print(f'列名: {t.column_names}')
    print(f'schema:\n{t.schema}')
    print()

    cols = t.column_names
    pre = pick(cols, 'pre', 'from', 'source', 'bodyid1', 'body1')
    post = pick(cols, 'post', 'to', 'target', 'bodyid2', 'body2')
    w = pick(cols, 'weight', 'synapse', 'count', 'n_syn')

    print(f'推定列: pre={pre}  post={post}  weight={w}')
    if pre is None or post is None:
        print('无法推定 pre/post 列，请人工检查 schema 后调整')
        sys.exit(2)
    print()

    n_edges = t.num_rows
    stats = {'rows': int(n_edges), 'columns': [str(c) for c in cols],
             'pre_col': str(pre), 'post_col': str(post), 'weight_col': str(w) if w else None}

    # ---------- 关键一步：收敛到「标注神经元 ↔ 标注神经元」子图 ----------
    # 全表 pre 有 183 万、post 有 8758 万个 body（含未标注碎片），
    # 直接拿全表报数会得到无物理意义的「下游 8758 万」。
    ann_all = None
    if os.path.exists(ANN):
        import pandas as pd  # noqa: F401
        ann_all = feather.read_table(ANN).to_pandas()

    scope = t
    if ann_all is not None:
        neurons = set(int(x) for x in ann_all.loc[ann_all['superclass'].notna(), 'bodyId'].tolist())
        nv = pa.array(sorted(neurons), type=pa.int64())
        m = pc.and_(pc.is_in(t[pre], value_set=nv), pc.is_in(t[post], value_set=nv))
        scope = t.filter(m)
        print()
        print('=== 口径收敛 ===')
        print(f'  全表        : {t.num_rows:,} 边 / {int(pc.sum(t[w]).as_py()) if w else t.num_rows:,} 突触')
        print(f'  真神经元子图: {scope.num_rows:,} 边 / {int(pc.sum(scope[w]).as_py()) if w else scope.num_rows:,} 突触'
              f'（{len(neurons):,} 个神经元）')
        stats['full_table'] = {
            'rows': int(t.num_rows),
            'synapses': int(pc.sum(t[w]).as_py()) if w else int(t.num_rows),
            'distinct_pre': int(pc.count_distinct(t[pre]).as_py()),
            'distinct_post': int(pc.count_distinct(t[post]).as_py()),
        }
        stats['neuron_subgraph'] = {
            'neurons': int(len(neurons)),
            'edges': int(scope.num_rows),
            'synapses': int(pc.sum(scope[w]).as_py()) if w else int(scope.num_rows),
            'distinct_pre': int(pc.count_distinct(scope[pre]).as_py()),
            'distinct_post': int(pc.count_distinct(scope[post]).as_py()),
        }
        t = scope
        n_edges = t.num_rows

    print(f'总突触数（weight 求和）: {int(pc.sum(t[w]).as_py()) if w else n_edges:,}')
    stats['synapses'] = int(pc.sum(t[w]).as_py()) if w else int(n_edges)
    stats['edges'] = int(n_edges)
    print(f'连接条数（有向边）: {n_edges:,}')

    # ---------- 出度 / 入度 ----------
    aggs = [(w, 'sum'), (w, 'count')] if w else []
    out_t = t.group_by(pre).aggregate(aggs) if aggs else None
    in_t = t.group_by(post).aggregate(aggs) if aggs else None

    fanout, fanin = {}, {}
    if aggs:
        out_ids = out_t.column(pre).to_pylist()
        out_sum = out_t.column(w + '_sum').to_pylist()
        in_ids = in_t.column(post).to_pylist()
        in_sum = in_t.column(w + '_sum').to_pylist()
        fanout = {i: (s or 0) for i, s in zip(out_ids, out_sum)}
        fanin = {i: (s or 0) for i, s in zip(in_ids, in_sum)}

        print(f'上游神经元数（有输出）: {len(out_ids):,}')
        print(f'下游目标数（有输入）  : {len(in_ids):,}')
        mean_fanout = sum(fanout.values()) / max(len(out_ids), 1)
        mean_fanin = sum(fanin.values()) / max(len(in_ids), 1)
        print(f'平均 fan-out（按突触数）: {mean_fanout:.1f}')
        print(f'平均 fan-in （按突触数）: {mean_fanin:.1f}')
        stats['mean_fanout'] = round(mean_fanout, 2)
        stats['mean_fanin'] = round(mean_fanin, 2)
        stats['neurons_with_output'] = int(len(out_ids))
        stats['neurons_with_input'] = int(len(in_ids))
    else:
        print('无 weight 列，跳过度分布统计')

    # ---------- 权重分布 ----------
    if w:
        wcol = t[w]
        qs = pc.quantile(wcol, q=[0.5, 0.9, 0.99, 0.999]).to_pylist()
        print(f'突触数分位数  p50={qs[0]:.0f}  p90={qs[1]:.0f}  p99={qs[2]:.0f}  p99.9={qs[3]:.0f}')
        stats['weight_quantiles'] = {'p50': float(qs[0]), 'p90': float(qs[1]),
                                     'p99': float(qs[2]), 'p999': float(qs[3])}

    # ---------- 枢纽神经元 ----------
    ann = None
    if os.path.exists(ANN):
        ann = feather.read_table(ANN).to_pandas()
        ann['bodyId'] = ann['bodyId'].astype(str)
        amap = ann.set_index('bodyId')[['type', 'superclass']].to_dict('index')
    else:
        amap = {}

    top = sorted(fanout.items(), key=lambda x: -x[1])[:20]
    print()
    print('--- 输出突触数最多的 20 个神经元（枢纽候选）---')
    hubs = []
    for body, sp in top:
        info = amap.get(str(body), {})
        print(f'  {str(body):>12}  输出突触 {sp:>8,}  类型={info.get("type") or "-":<18} 超类={info.get("superclass") or "-"}')
        hubs.append({'body': str(body), 'synapses': int(sp),
                     'fanout': int(fanout.get(body, 0)),
                     'fanin': int(fanin.get(body, 0)),
                     'type': (str(info.get('type')) if info.get('type') is not None and str(info.get('type')) != 'nan' else None),
                     'superclass': (str(info.get('superclass')) if info.get('superclass') is not None and str(info.get('superclass')) != 'nan' else None)})
    stats['top_hubs'] = hubs

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print()
    print(f'统计已写入: {OUT}')


if __name__ == '__main__':
    main()
