"""核实连接表的真实含义 —— 避免把「含未标注碎片的全表」当成「神经元网络」来报数。

疑问：
    连接表 151,856,684 行；pre 唯一值 1,834,661；post 唯一值 87,576,984。
    但 MaleCNS 只有 166,700 个标注神经元。「下游目标 8758 万」显然不是神经元数。
    必须把范围收敛到「标注神经元 ↔ 标注神经元」才是有物理意义的子图。

用法:
    python probe_connectivity.py
"""
import os

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data', 'male_cns', 'flat-connectome')


def main():
    conn = feather.read_table(os.path.join(DATA, 'connectome-weights-male-cns-v1.0-minconf-0.5.feather'),
                              memory_map=True)
    ann = feather.read_table(os.path.join(DATA, 'body-annotations-male-cns-v1.0-minconf-0.5.feather')).to_pandas()

    print(f'连接表总行数: {conn.num_rows:,}')

    # 1. (pre, post) 是否唯一？
    pairs = pa.table({'p': conn['body_pre'], 'q': conn['body_post']})
    grouped = pairs.group_by(['p', 'q']).aggregate([])
    uniq_pairs = grouped.num_rows
    print(f'唯一 (pre,post) 对数: {uniq_pairs:,}   → {"每对唯一，是聚合表" if uniq_pairs == conn.num_rows else "存在重复对"}')

    # 2. 收敛到标注神经元集合
    neuron_ids = set(int(x) for x in ann['bodyId'].tolist())
    print(f'标注 body 总数: {len(neuron_ids):,}（含胶质/伪影）')

    pre_vals = pa.array(sorted(neuron_ids), type=pa.int64())
    mask_pre = pc.is_in(conn['body_pre'], value_set=pre_vals)
    mask_post = pc.is_in(conn['body_post'], value_set=pre_vals)
    mask_both = pc.and_(mask_pre, mask_post)

    sub = conn.filter(mask_both)
    print()
    print('=== 收敛到「标注集合 ↔ 标注集合」===')
    print(f'  边数      : {sub.num_rows:,}')
    print(f'  突触总数  : {int(pc.sum(sub["weight"]).as_py()):,}')
    print(f'  参与的上游: {pc.count_distinct(sub["body_pre"]).as_py():,}')
    print(f'  参与的下游: {pc.count_distinct(sub["body_post"]).as_py():,}')

    # 3. 只保留 superclass 非空的真神经元
    neurons = set(int(x) for x in ann.loc[ann['superclass'].notna(), 'bodyId'].tolist())
    print(f'\n真神经元数（superclass 非空）: {len(neurons):,}')
    nv = pa.array(sorted(neurons), type=pa.int64())
    mask2 = pc.and_(pc.is_in(conn['body_pre'], value_set=nv), pc.is_in(conn['body_post'], value_set=nv))
    sub2 = conn.filter(mask2)
    print('=== 只保留真神经元 ===')
    print(f'  边数      : {sub2.num_rows:,}')
    print(f'  突触总数  : {int(pc.sum(sub2["weight"]).as_py()):,}')
    print(f'  上游神经元: {pc.count_distinct(sub2["body_pre"]).as_py():,}')
    print(f'  下游神经元: {pc.count_distinct(sub2["body_post"]).as_py():,}')
    if sub2.num_rows:
        fanout_mean = int(pc.sum(sub2['weight']).as_py()) / max(pc.count_distinct(sub2['body_pre']).as_py(), 1)
        print(f'  平均每个神经元输出突触: {fanout_mean:.1f}')

    # 4. 全表里未被标注的 pre 是些什么
    print()
    print('=== 全表口径（含未标注 body）===')
    print(f'  pre 唯一: {pc.count_distinct(conn["body_pre"]).as_py():,}')
    print(f'  post 唯一: {pc.count_distinct(conn["body_post"]).as_py():,}')
    print(f'  weight 求和: {int(pc.sum(conn["weight"]).as_py()):,}')


if __name__ == '__main__':
    main()
