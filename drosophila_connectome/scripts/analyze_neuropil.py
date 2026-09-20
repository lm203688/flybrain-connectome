"""分析 syn-partners 的 neuropil 空间维度，生成汇总 stats JSON。

背景：
    syn-partners-male-cns-v1.0-minconf-0.5.feather 是 MaleCNS v1.0 的突触空间数据
    （311,833,243 行 × 11 列）。直接加载太大（6.78 GB）不适合 MCP 服务热路径，
    但**聚合到 neuropil 粒度**后是极小 JSON，可安全暴露给 MCP 作为顶层空间信息。

产出：
    male_cns/neuropil_stats.json — 每个 neuropil 的突触数、涉及神经元数、脑区左右对比

用法：
    python analyze_neuropil.py                        # 生成 stats（约 30-60 秒）
    python analyze_neuropil.py --show                 # 打印已有 stats
    python analyze_neuropil.py --top 20                # 只输出前 N 个 neuropil

依赖：
    - pyarrow（≥ 10.0，读 feather 字典编码列）
    - 建议用 minimind venv：
        C:/Users/xing/.workbuddy/binaries/python/envs/minimind/Scripts/python.exe

性能：
    pyarrow compute.value_counts 走内存映射 + 字典索引，全 3.1 亿行统计约 30-60 秒。
    不用 pandas，避免整表转 DataFrame。
"""
import argparse
import json
import os
import time

import pyarrow.compute as pc

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
SYN_PARTNERS = os.path.join(
    PROJECT_ROOT, 'male_cns', 'flat-connectome',
    'syn-partners-male-cns-v1.0-minconf-0.5.feather'
)
STATS_OUT = os.path.join(PROJECT_ROOT, 'male_cns', 'neuropil_stats.json')


def analyze():
    t0 = time.time()
    import pyarrow.feather as feather
    print(f'[1/3] 加载 feather（memory-map）: {SYN_PARTNERS}')
    t = feather.read_table(SYN_PARTNERS)
    print(f'      {t.num_rows:,} 行 x {t.num_columns} 列  ({time.time()-t0:.1f}s)')

    print('[2/3] 统计 primary_post 分布 ...')
    t0 = time.time()
    npp = t.column('primary_post')
    vc = pc.value_counts(npp)
    # value_counts 返回 StructArray，每元素是 {'values': ..., 'counts': ...}
    counts = {p['values']: int(p['counts']) for p in vc.to_pylist()}
    print(f'      {len(counts)} 个 neuropil 类别  ({time.time()-t0:.1f}s)')

    print('[3/3] 统计每个 neuropil 涉及的神经元数（涉及 body_pre 和 body_post）...')
    t0 = time.time()
    # body_pre 是 int64，body_post 也是 int64，用 set 会太慢
    # 分 neuropil 处理：对每个 neuropil 单独取子集再 distinct
    bp = t.column('body_pre')
    bpost = t.column('body_post')
    per_neuropil = {}
    for name, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        mask = pc.equal(npp, name)
        unique_pre = len(pc.unique(bp.filter(mask)))
        unique_post = len(pc.unique(bpost.filter(mask)))
        per_neuropil[name] = {
            'synapses': int(cnt),
            'distinct_pre_neurons': int(unique_pre),
            'distinct_post_neurons': int(unique_post),
            'mean_synapses_per_pre': round(cnt / max(unique_pre, 1), 2),
        }
    print(f'      {len(per_neuropil)} 个 neuropil 完成  ({time.time()-t0:.1f}s)')

    # 汇总
    total = sum(v['synapses'] for v in per_neuropil.values())
    out = {
        'source_file': os.path.basename(SYN_PARTNERS),
        'source_size_bytes': os.path.getsize(SYN_PARTNERS),
        'total_synapse_pairs': total,
        'n_neuropil_categories': len(per_neuropil),
        'neuropils': per_neuropil,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'notes': (
            '基于 syn-partners 全量（minconf=0.5）聚合。'
            'primary_post 是 post 侧的脑区归属；<unspecified> 表示坐标不在任何已标 ROI 内。'
            'body_pre/body_post 为 body id（对应 annotations.json 里的 body）。'
        ),
    }
    os.makedirs(os.path.dirname(STATS_OUT), exist_ok=True)
    with open(STATS_OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n✓ 写入 {STATS_OUT}  ({os.path.getsize(STATS_OUT):,} bytes)')
    return out


def show(top=15):
    with open(STATS_OUT, encoding='utf-8') as f:
        d = json.load(f)
    print(f"总突触对: {d['total_synapse_pairs']:,}")
    print(f"neuropil 类别数: {d['n_neuropil_categories']}")
    print(f"生成时间: {d['generated_at']}")
    print()
    print(f"{'neuropil':<30} {'synapses':>13} {'pre_neurons':>13} {'post_neurons':>13}")
    print('-' * 72)
    for i, (name, v) in enumerate(d['neuropils'].items()):
        if i >= top:
            break
        print(f"{name:<30} {v['synapses']:>13,} {v['distinct_pre_neurons']:>13,} "
              f"{v['distinct_post_neurons']:>13,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--show', action='store_true', help='只打印已有 stats')
    ap.add_argument('--top', type=int, default=15, help='show 模式显示前 N 个')
    args = ap.parse_args()
    if args.show:
        show(args.top)
    else:
        analyze()


if __name__ == '__main__':
    main()
