"""分析 MaleCNS v1.0 空间维度：syn-partners + tbar-nt → 每个 neuropil 的突触数、神经元数、神经递质分布。

产出：
    male_cns/neuropil_stats.json — 每个 neuropil 的突触数、涉及神经元数、脑区左右对比、
                                   神经递质概率分布（tbar-nt）

用法：
    python analyze_neuropil.py                        # 生成 stats（约 60-120 秒）
    python analyze_neuropil.py --show                 # 打印已有 stats
    python analyze_neuropil.py --top 20                # 只输出前 N 个 neuropil

依赖：
    - pyarrow（≥ 10.0，读 feather 字典编码列）
    - 建议用 minimind venv：
        C:/Users/xing/.workbuddy/binaries/python/envs/minimind/Scripts/python.exe

性能：
    syn-partners: 311.8M 行 → primary_post 分布 ~30-60s
    tbar-nt:      45.6M 行 → 神经递质概率 ~15-30s
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
TBAR_NT = os.path.join(
    PROJECT_ROOT, 'male_cns', 'flat-connectome',
    'tbar-neurotransmitters-male-cns-v1.0.feather'
)
STATS_OUT = os.path.join(PROJECT_ROOT, 'male_cns', 'neuropil_stats.json')

NT_COLS = [
    'nt_acetylcholine_prob', 'nt_dopamine_prob', 'nt_gaba_prob',
    'nt_glutamate_prob', 'nt_histamine_prob', 'nt_octopamine_prob',
    'nt_serotonin_prob',
]
NT_NAMES = ['acetylcholine', 'dopamine', 'gaba', 'glutamate',
            'histamine', 'octopamine', 'serotonin']


def _neuropil_synapse_stats():
    """syn-partners 全量聚合：每个 neuropil 的突触数 + 涉及神经元数。"""
    t0 = time.time()
    import pyarrow.feather as feather
    print(f'[1/4] 加载 syn-partners: {SYN_PARTNERS}')
    t = feather.read_table(SYN_PARTNERS)
    print(f'      {t.num_rows:,} 行 x {t.num_columns} 列  ({time.time()-t0:.1f}s)')

    print('[2/4] 统计 primary_post 分布 ...')
    t0 = time.time()
    npp = t.column('primary_post')
    vc = pc.value_counts(npp)
    counts = {p['values']: int(p['counts']) for p in vc.to_pylist()}
    print(f'      {len(counts)} 个 neuropil 类别  ({time.time()-t0:.1f}s)')

    print('[3/4] 统计每个 neuropil 涉及的神经元数 ...')
    t0 = time.time()
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
    del t, npp, bp, bpost, mask
    return per_neuropil


def _neuropil_neurotransmitter_stats():
    """tbar-nt 聚合：每个 neuropil 的神经递质概率均值 + 涉及 body 数。"""
    if not os.path.exists(TBAR_NT):
        print(f'[4/4] tbar-nt 不存在，跳过神经递质分析: {TBAR_NT}')
        return {}

    t0 = time.time()
    import pyarrow.feather as feather
    print(f'[4/4] 加载 tbar-nt: {TBAR_NT}')
    t = feather.read_table(TBAR_NT)
    print(f'      {t.num_rows:,} 行 x {t.num_columns} 列  ({time.time()-t0:.1f}s)')

    print('      统计每个 neuropil 的神经递质概率均值 ...')
    t0 = time.time()
    primary = t.column('primary')
    body = t.column('body')

    # 先统计 primary 分布
    vc = pc.value_counts(primary)
    counts = {p['values']: int(p['counts']) for p in vc.to_pylist()}

    per_neuropil_nt = {}
    nt_arrays = {col: t.column(col) for col in NT_COLS}

    for name, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        mask = pc.equal(primary, name)
        unique_bodies = len(pc.unique(body.filter(mask)))
        # 每个 nt 列的均值
        nt_means = {}
        for col, nt_name in zip(NT_COLS, NT_NAMES):
            vals = nt_arrays[col].filter(mask)
            if len(vals) > 0:
                mean_val = float(pc.mean(vals))
            else:
                mean_val = None
            nt_means[nt_name] = round(mean_val, 6) if mean_val is not None else None
        per_neuropil_nt[name] = {
            'tbar_synapses': int(cnt),
            'distinct_bodies': int(unique_bodies),
            'neurotransmitters': nt_means,
        }
    print(f'      {len(per_neuropil_nt)} 个 neuropil 完成  ({time.time()-t0:.1f}s)')
    del t, primary, body, mask, nt_arrays
    return per_neuropil_nt


def analyze(nt_only=False):
    t0 = time.time()
    if nt_only:
        print('[--nt-only] 仅重跑神经递质分析 ...')
        # 加载已有的 neuropil stats
        with open(STATS_OUT, encoding='utf-8') as f:
            prev = json.load(f)
        per_neuropil = prev['neuropils']
        # 清除旧的神经递质数据
        for v in per_neuropil.values():
            v.pop('neurotransmitters', None)
            v.pop('tbar_synapses', None)
            v.pop('distinct_bodies_tbar', None)
    else:
        per_neuropil = _neuropil_synapse_stats()
    nt_stats = _neuropil_neurotransmitter_stats()

    # 合并神经递质数据到已有 stats
    for name in per_neuropil:
        if name in nt_stats:
            per_neuropil[name]['neurotransmitters'] = nt_stats[name]['neurotransmitters']
            per_neuropil[name]['tbar_synapses'] = nt_stats[name]['tbar_synapses']
            per_neuropil[name]['distinct_bodies_tbar'] = nt_stats[name]['distinct_bodies']

    total = sum(v['synapses'] for v in per_neuropil.values())
    total_tbar = sum(v.get('tbar_synapses', 0) for v in per_neuropil.values())
    out = {
        'source_file_syn_partners': os.path.basename(SYN_PARTNERS),
        'source_size_bytes_syn_partners': os.path.getsize(SYN_PARTNERS),
        'source_file_tbar_nt': os.path.basename(TBAR_NT) if os.path.exists(TBAR_NT) else None,
        'source_size_bytes_tbar_nt': os.path.getsize(TBAR_NT) if os.path.exists(TBAR_NT) else None,
        'total_synapse_pairs': total,
        'total_tbar_synapses': total_tbar,
        'n_neuropil_categories': len(per_neuropil),
        'neuropils': per_neuropil,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'notes': (
            'syn-partners 全量（minconf=0.5）聚合：突触对数 + 涉及神经元数。'
            'tbar-nt 全量聚合：每个 neuropil 的神经递质概率均值（7 种递质）。'
            'primary_post/primary 是脑区归属；<unspecified> 表示坐标不在任何已标 ROI 内。'
        ),
    }
    os.makedirs(os.path.dirname(STATS_OUT), exist_ok=True)
    with open(STATS_OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\n✓ 写入 {STATS_OUT}  ({os.path.getsize(STATS_OUT):,} bytes)')
    print(f'  总耗时: {time.time()-t0:.1f}s')
    return out


def show(top=15):
    with open(STATS_OUT, encoding='utf-8') as f:
        d = json.load(f)
    print(f"总突触对: {d['total_synapse_pairs']:,}")
    print(f"总 tbar 突触: {d.get('total_tbar_synapses', 0):,}")
    print(f"neuropil 类别数: {d['n_neuropil_categories']}")
    print(f"生成时间: {d['generated_at']}")
    print()
    header = f"{'neuropil':<30} {'synapses':>13} {'pre_neurons':>13} {'post_neurons':>13}"
    print(header)
    print('-' * 72)
    for i, (name, v) in enumerate(d['neuropils'].items()):
        if i >= top:
            break
        print(f"{name:<30} {v['synapses']:>13,} {v['distinct_pre_neurons']:>13,} "
              f"{v['distinct_post_neurons']:>13,}")

    # 显示前 5 个有神经递质数据的 neuropil
    nt_neuropils = [(n, v) for n, v in d['neuropils'].items()
                    if 'neurotransmitters' in v]
    if nt_neuropils:
        print(f"\n=== 神经递质分布（前 5 个 neuropil）===")
        for name, v in nt_neuropils[:5]:
            nt = v['neurotransmitters']
            parts = [f"{nt_name[:6]}={nt[nt_name]:.3f}" if nt[nt_name] else f"{nt_name[:6]}=-"
                     for nt_name in NT_NAMES]
            print(f"  {name:<20}  {' '.join(parts)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nt-only', action='store_true', help='仅重跑神经递质分析（保留已有 syn-partners stats）')
    ap.add_argument('--show', action='store_true', help='只打印已有 stats')
    ap.add_argument('--top', type=int, default=15, help='show 模式显示前 N 个')
    args = ap.parse_args()
    if args.show:
        show(args.top)
    else:
        analyze(nt_only=args.nt_only)


if __name__ == '__main__':
    main()
