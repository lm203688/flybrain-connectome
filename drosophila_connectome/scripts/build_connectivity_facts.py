"""从 MaleCNS 连接权重表提取「连接级」真实事实，供领域语料扩展使用。

与 connectivity_stats.json 的区别：
    connectivity_stats.json 只给了「神经元子图总边数 / 总突触 / 度分位 / top hubs」。
    本脚本进一步算出：
      1) 跨超类（superclass）投射矩阵 —— 哪类脑区主要投射到哪类脑区；
      2) 每个超类的输入 / 输出突触总量；
      3) 每个神经元的入/出突触分布桶（degree distribution）；
      4) 顶级枢纽神经元各自「最强下游靶点」是哪一类神经元（hub → target）。

全部事实来自 body-annotations + connectome-weights 两张真实表，零编造。
实现：numpy 向量化 + searchsorted 映射，分块流式读取 1GB 连接表，33GB 内存下安全。

用法：
    python build_connectivity_facts.py
产出：
    data/male_cns/connectivity_facts.json
"""
import json
import os

import numpy as np
import pyarrow as pa
import pyarrow.feather as feather

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
ANN = os.path.join(ROOT, 'data', 'male_cns', 'flat-connectome',
                   'body-annotations-male-cns-v1.0-minconf-0.5.feather')
CW = os.path.join(ROOT, 'data', 'male_cns', 'flat-connectome',
                 'connectome-weights-male-cns-v1.0-minconf-0.5.feather')
OUT = os.path.join(ROOT, 'data', 'male_cns', 'connectivity_facts.json')


def main():
    # ---------- 1. 注解表：建立「神经元 bodyId -> 超类 / 类型 / 紧凑索引」 ----------
    print('[1/4] 读取注解表 ...')
    ann = feather.read_table(ANN).to_pandas()
    neurons = ann[ann['superclass'].notna()].copy()
    neuron_ids = neurons['bodyId'].to_numpy().astype(np.int64)
    neuron_sc = neurons['superclass'].to_numpy().astype(object)
    neuron_type = neurons['type'].fillna('').to_numpy().astype(object)

    order = np.argsort(neuron_ids)
    sorted_ids = neuron_ids[order]
    sorted_sc = neuron_sc[order]
    sorted_type = neuron_type[order]
    N = len(sorted_ids)

    sc_list = sorted(set(neuron_sc.tolist()))
    nSC = len(sc_list)
    sc_index = {s: i for i, s in enumerate(sc_list)}
    sc_of_sorted = np.array([sc_index[s] for s in sorted_sc], dtype=np.intp)
    # bodyId -> type（仅神经元）
    id_to_type = {int(b): t for b, t in zip(neuron_ids, neuron_type)}
    id_to_sc = {int(b): s for b, s in zip(neuron_ids, neuron_sc)}
    print(f'      神经元数 N={N:,}，超类数 nSC={nSC}')

    # ---------- 2. 第一遍：跨超类矩阵 + 每神经元入/出突触 ----------
    print('[2/4] 流式扫描连接表（第一遍：跨超类矩阵 + 度）...')
    matrix = np.zeros((nSC, nSC), dtype=np.int64)
    fanout = np.zeros(N, dtype=np.int64)
    fanin = np.zeros(N, dtype=np.int64)
    total_syn = 0

    reader = pa.ipc.open_file(CW)
    n_rg = reader.num_record_batches
    for i in range(n_rg):
        rg = reader.get_batch(i)
        pre = rg.column('body_pre').to_numpy().astype(np.int64)
        post = rg.column('body_post').to_numpy().astype(np.int64)
        w = rg.column('weight').to_numpy().astype(np.int64)

        ip = np.searchsorted(sorted_ids, pre)
        ip = np.clip(ip, 0, N - 1)
        mpre = sorted_ids[ip] == pre
        ipost = np.searchsorted(sorted_ids, post)
        ipost = np.clip(ipost, 0, N - 1)
        mpost = sorted_ids[ipost] == post
        both = mpre & mpost
        if not both.any():
            continue
        cpre = ip[both]
        cpost = ipost[both]
        wb = w[both].astype(np.int64)
        total_syn += int(wb.sum())

        np.add.at(fanout, cpre, wb)
        np.add.at(fanin, cpost, wb)
        sc_pre = sc_of_sorted[cpre]
        sc_post = sc_of_sorted[cpost]
        flat = sc_pre * nSC + sc_post
        np.add.at(matrix.ravel(), flat, wb)

    print(f'      神经元子图总突触（本脚本重算）= {total_syn:,}')

    # ---------- 3. 派生：枢纽、度分布、跨超类投射 ----------
    print('[3/4] 派生枢纽 / 度分布 / 跨超类投射 ...')
    total_deg = fanout + fanin
    hub_order = np.argsort(total_deg)[::-1]
    top_hub_ids = sorted_ids[hub_order[:40]]
    hub_set = set(int(x) for x in top_hub_ids.tolist())

    # 度分布桶（按出突触）
    bins = [0, 1, 11, 101, 501, 1001, 5001, 10001, 50001, 10**9]
    labels = ['0', '1-10', '11-100', '101-500', '501-1000',
              '1001-5000', '5001-10000', '10001-50000', '>50000']
    fanout_hist, _ = np.histogram(fanout, bins=bins)
    fanin_hist, _ = np.histogram(fanin, bins=bins)
    degree_buckets = [{'range': labels[i], 'neurons_out': int(fanout_hist[i]),
                       'neurons_in': int(fanin_hist[i])}
                      for i in range(len(labels))]

    # 跨超类投射（含自连接），按突触数取前 40
    cells = []
    for a in range(nSC):
        for b in range(nSC):
            s = int(matrix[a, b])
            if s > 0:
                cells.append((sc_list[a], sc_list[b], s))
    cells.sort(key=lambda x: -x[2])
    cross_superclass = [{'from': a, 'to': b, 'synapses': s,
                         'pct_of_total': round(s * 100.0 / total_syn, 2)}
                        for a, b, s in cells[:40]]

    # 每个超类的输入/输出总量
    sc_out_total = matrix.sum(axis=1)
    sc_in_total = matrix.sum(axis=0)
    sc_neuron_count = np.array([int((neuron_sc == s).sum()) for s in sc_list])
    superclass_io = [{'superclass': sc_list[i],
                      'n_neurons': int(sc_neuron_count[i]),
                      'out_synapses': int(sc_out_total[i]),
                      'in_synapses': int(sc_in_total[i])}
                     for i in range(nSC)]

    # ---------- 4. 第二遍：顶级枢纽的最强下游靶点 ----------
    print('[4/4] 流式扫描连接表（第二遍：枢纽下游靶点）...')
    pair_sum = {}  # (pre_body, post_body) -> synapses
    for i in range(n_rg):
        rg = reader.get_batch(i)
        pre = rg.column('body_pre').to_numpy().astype(np.int64)
        post = rg.column('body_post').to_numpy().astype(np.int64)
        w = rg.column('weight').to_numpy().astype(np.int64)
        ip = np.searchsorted(sorted_ids, pre)
        ip = np.clip(ip, 0, N - 1)
        mpre = sorted_ids[ip] == pre
        ipost = np.searchsorted(sorted_ids, post)
        ipost = np.clip(ipost, 0, N - 1)
        mpost = sorted_ids[ipost] == post
        both = mpre & mpost
        if not both.any():
            continue
        pre_b = pre[both]
        post_b = post[both]
        wb = w[both].astype(np.int64)
        # 只保留 pre 属于枢纽的
        keep = np.array([int(x) in hub_set for x in pre_b.tolist()])
        if not keep.any():
            continue
        kp, kpost, kw = pre_b[keep], post_b[keep], wb[keep]
        for a, b, s in zip(kp.tolist(), kpost.tolist(), kw.tolist()):
            key = (int(a), int(b))
            pair_sum[key] = pair_sum.get(key, 0) + int(s)

    top_pairs = []
    from collections import defaultdict
    by_hub = defaultdict(list)
    for (a, b), s in pair_sum.items():
        by_hub[a].append((b, s))
    for hid in top_hub_ids.tolist():
        hid = int(hid)
        targets = sorted(by_hub.get(hid, []), key=lambda x: -x[1])[:3]
        tgt_list = []
        for tb, s in targets:
            tb = int(tb)
            tgt_list.append({
                'target_body': tb,
                'target_type': id_to_type.get(tb, '') or '未注释片段',
                'target_superclass': id_to_sc.get(tb, '未注释片段'),
                'synapses': s,
            })
        top_pairs.append({
            'hub_body': hid,
            'hub_type': id_to_type.get(hid, '') or '未注释',
            'hub_superclass': id_to_sc.get(hid, '未注释'),
            'hub_total_synapses': int(total_deg[np.searchsorted(sorted_ids, hid)]),
            'hub_fanout': int(fanout[np.searchsorted(sorted_ids, hid)]),
            'hub_fanin': int(fanin[np.searchsorted(sorted_ids, hid)]),
            'top_targets': tgt_list,
        })

    # ---------- 写盘 ----------
    out = {
        'total_synapses': total_syn,
        'n_neurons': N,
        'n_superclasses': nSC,
        'superclass_list': sc_list,
        'superclass_io': superclass_io,
        'cross_superclass_top': cross_superclass,
        'degree_buckets': degree_buckets,
        'top_hubs_with_targets': top_pairs,
        'mean_fanout': round(float(fanout.mean()), 1),
        'mean_fanin': round(float(fanin.mean()), 1),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'已写出 -> {OUT}  ({os.path.getsize(OUT)/1024:.1f} KB)')
    print(f'跨超类投射 top3: {cross_superclass[:3]}')
    print(f'度分布(出): {[d["neurons_out"] for d in degree_buckets]}')


if __name__ == '__main__':
    main()
