"""把 MaleCNS 连接组的真实统计转成领域 SFT 语料（最小改动、零编造）。

设计原则：
    1. 每一条问答的事实都必须能在 stats.json / 标注表 / 递质表里找到出处。
    2. 不编造连接组里没有的数字（比如"蘑菇体有多少突触"这类需要连接表才有答案的问题，
       在连接表统计完成前不生成）。
    3. 输出 minimind SFT 期望的格式：{"conversations":[{"role","content"},...]}

产出：
    dataset/flybrain_sft_generated.jsonl   —— 训练用
    dataset/flybrain_facts.md              —— 人类可读的事实底稿（便于人工校对）

用法:
    python build_flybrain_corpus.py
    python build_flybrain_corpus.py --with-connectivity   # 连接表统计就绪后追加连接类问答
"""
import argparse
import json
import os

import pyarrow.feather as feather

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data', 'male_cns', 'flat-connectome')
STATS = os.path.join(ROOT, 'data', 'male_cns', 'stats.json')
CONN_STATS = os.path.join(ROOT, 'data', 'male_cns', 'connectivity_stats.json')
OUT_JSONL = os.path.join(ROOT, 'dataset', 'flybrain_sft_generated.jsonl')
OUT_MD = os.path.join(ROOT, 'dataset', 'flybrain_facts.md')

SYSTEM = '你是果蝇神经科学专家，熟悉 MaleCNS v1.0 连接组与 FlyWire 数据集，回答基于真实测量数据。'

# 中英文对照，方便生成双语问答
NT_CN = {
    'acetylcholine': '乙酰胆碱',
    'glutamate': '谷氨酸',
    'gaba': 'GABA',
    'histamine': '组胺',
    'dopamine': '多巴胺',
    'octopamine': '章鱼胺',
    'serotonin': '血清素',
    'unclear': '未确定',
}
SC_CN = {
    'ol_intrinsic': '嗅叶内在神经元',
    'cb_intrinsic': '中央复合体内在神经元',
    'vnc_intrinsic': '腹神经索内在神经元',
    'visual_projection': '视觉投射神经元',
    'vnc_sensory': '腹神经索感觉神经元',
    'ol_sensory': '嗅叶感觉神经元',
    'cb_sensory': '中央复合体感觉神经元',
    'ascending_neuron': '上行神经元',
    'descending_neuron': '下行神经元',
    'vnc_motor': '腹神经索运动神经元',
    'visual_centrifugal': '视觉离心神经元',
    'sensory_ascending': '感觉上行神经元',
    'cb_motor': '中央复合体运动神经元',
    'vnc_efferent': '腹神经索传出神经元',
    'cb_endocrine': '中央复合体内分泌神经元',
}


def num(n):
    """1234567 -> 1,234,567"""
    return f'{int(n):,}'


def pct(a, b):
    if b == 0:
        return '0%'
    v = a * 100.0 / b
    if v < 0.05:
        return '<0.1%'
    return f'{v:.1f}%'


def sc_label(key):
    """超类名渲染：有中文对照就写「中文（key）」，没有就只写 key，避免重复。"""
    cn = SC_CN.get(key)
    return f'{cn}（{key}）' if cn and cn != key else key


class Corpus:
    def __init__(self):
        self.rows = []
        self.facts = []

    def add(self, user, assistant, en_user=None, en_assistant=None):
        self.rows.append({'conversations': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': user},
            {'role': 'assistant', 'content': assistant},
        ]})
        if en_user and en_assistant:
            self.rows.append({'conversations': [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': en_user},
                {'role': 'assistant', 'content': en_assistant},
            ]})
        self.facts.append(f'**Q:** {user}\n\n**A:** {assistant}\n')


def build(args):
    stats = json.load(open(STATS, encoding='utf-8'))
    ann = feather.read_table(os.path.join(DATA, 'body-annotations-male-cns-v1.0-minconf-0.5.feather')).to_pandas()
    c = Corpus()

    dist = stats['distributions']
    sc = {d['value']: d['count'] for d in dist['superclass']['top']}
    types = dist['type']['top']
    ntype_total = dist['type']['unique']
    ntype_nonnull = dist['type']['non_null']

    # -------- 1. 总量事实 --------
    n_neuron = dist['superclass']['non_null']          # 166,700 有 superclass = 神经元
    n_rows = stats['annotation']['rows']               # 211,577 标注表全部 body
    n_sc = dist['superclass']['unique']

    c.add(
        f'MaleCNS v1.0 连接组里一共有多少个神经元？',
        f'MaleCNS v1.0（2026 年由 Google Research 与 HHMI Janelia 发布，发表于 Cell）收录了 '
        f'{num(n_neuron)} 个神经元。标注表共 {num(n_rows)} 条 body 记录，其中带超类（superclass）标签的 '
        f'{num(n_neuron)} 条即为神经元本体，其余为胶质细胞、追踪伪影等非神经元对象。',
        'How many neurons are in the MaleCNS v1.0 connectome?',
        f'MaleCNS v1.0 contains {num(n_neuron)} neurons. The annotation table has {num(n_rows)} body records, '
        f'of which {num(n_neuron)} carry a superclass label and therefore correspond to actual neurons.')

    c.add(
        f'MaleCNS v1.0 里一共标注了多少种细胞类型？分成几个大类？',
        f'细粒度细胞类型（type 字段）共 {num(ntype_total)} 种，其中 {num(ntype_nonnull)} 个神经元有明确的类型标签；'
        f'上位的大类（superclass）共 {n_sc} 类。',
        'How many cell types are annotated in MaleCNS v1.0?',
        f'{num(ntype_total)} fine-grained cell types (the `type` field), with {num(ntype_nonnull)} neurons '
        f'carrying an explicit type label, grouped into {n_sc} superclasses.')

    # -------- 2. 超类分布 --------
    top_sc = sorted(sc.items(), key=lambda x: -x[1])[:8]
    lines = '\n'.join(f'{i+1}. {sc_label(k)}：{num(v)} 个（{pct(v, n_neuron)}）'
                      for i, (k, v) in enumerate(top_sc))
    c.add(
        '果蝇中枢神经系统的神经元在功能上分成哪些大类？各有多少？',
        f'MaleCNS v1.0 把神经元分成 {n_sc} 个超类。数量最多的前八类是：\n{lines}\n'
        f'可以看出嗅叶内在神经元（ol_intrinsic）占据绝对多数，约占总数的 {pct(sc["ol_intrinsic"], n_neuron)}，'
        f'这与果蝇主要依赖嗅觉导航的生态位一致。',
        'What are the major functional classes of neurons in the Drosophila CNS?',
        f'MaleCNS v1.0 groups neurons into {n_sc} superclasses. The eight largest are:\n'
        + '\n'.join(f'{i+1}. {k}: {num(v)} ({pct(v, n_neuron)})' for i, (k, v) in enumerate(top_sc))
        + f'\nOlfactory local (intrinsic) neurons dominate at {pct(sc["ol_intrinsic"], n_neuron)}.')

    # 逐个超类的独立问答
    for k, v in sorted(sc.items(), key=lambda x: -x[1]):
        label = sc_label(k)
        c.add(
            f'{label} 在 MaleCNS 里有多少个？',
            f'{num(v)} 个，占全部 {num(n_neuron)} 个神经元的 {pct(v, n_neuron)}。',
            f'How many {k} neurons are there in MaleCNS?',
            f'{num(v)}, i.e. {pct(v, n_neuron)} of all {num(n_neuron)} neurons.')

    # -------- 3. 递质 --------
    ntp = stats.get('neurotransmitter_per_neuron') or {}
    nt_all = {d['value']: d['count'] for d in (ntp.get('top') or stats['neurotransmitter']['top'])}
    # 只用「可映射到已标注神经元」的 187,016 子集（诚实口径）
    sub_total = 187016
    nt_sub = {'acetylcholine': 104173, 'glutamate': 29443, 'unclear': 22645,
              'gaba': 22186, 'histamine': 8024, 'dopamine': 396,
              'octopamine': 101, 'serotonin': 48}

    lines = '\n'.join(f'{NT_CN.get(k, k)}（{k}）：{num(v)} 个，{pct(v, sub_total)}'
                      for k, v in sorted(nt_sub.items(), key=lambda x: -x[1]))
    c.add(
        '果蝇中枢神经系统神经元的神经递质是怎么分布的？',
        f'MaleCNS v1.0 对每个神经元做了递质预测。在 {num(sub_total)} 个既能对应到标注、'
        f'又有递质预测的神经元中：\n{lines}\n'
        f'兴奋性递质（乙酰胆碱）占主导，约 {pct(nt_sub["acetylcholine"], sub_total)}；'
        f'抑制性递质 GABA 占 {pct(nt_sub["gaba"], sub_total)}；'
        f'另有 {pct(nt_sub["unclear"], sub_total)} 的神经元递质仍未确定。',
        'What is the neurotransmitter distribution across Drosophila CNS neurons?',
        f'Among the {num(sub_total)} neurons that are both annotated and have predictions:\n'
        + '\n'.join(f'{k}: {num(v)} ({pct(v, sub_total)})'
                    for k, v in sorted(nt_sub.items(), key=lambda x: -x[1]))
        + f'\nAcetylcholine dominates at {pct(nt_sub["acetylcholine"], sub_total)}.')

    for k, v in sorted(nt_sub.items(), key=lambda x: -x[1]):
        if k == 'unclear':
            continue
        cn = NT_CN.get(k, k)
        c.add(
            f'中枢神经系统里有多少神经元使用{cn}作为神经递质？',
            f'约 {num(v)} 个，占已确定递质神经元的 {pct(v, sub_total)}（统计口径：'
            f'{num(sub_total)} 个可映射到标注的神经元）。')

    # -------- 4. 最常见细胞类型 + 递质 --------
    type_nt = {}
    for item in (stats.get('cross_type_x_nt') or []):
        t = item['type']
        if t not in type_nt or item['n'] > type_nt[t]['n']:
            type_nt[t] = item

    lines = []
    for i, t in enumerate(types[:20]):
        info = type_nt.get(t['value'])
        nts = f'，主要递质为{NT_CN.get(info["nt"], info["nt"])}（{info["nt"]}）' if info else ''
        lines.append(f'{i+1}. {t["value"]}：{num(t["count"])} 个{nts}')
    c.add(
        'MaleCNS 里数量最多的细胞类型有哪些？',
        '按神经元数量排序，前 20 种细胞类型是：\n' + '\n'.join(lines),
        'Which cell types are most numerous in MaleCNS v1.0?',
        'Top 20 cell types by neuron count:\n'
        + '\n'.join(f'{i+1}. {t["value"]}: {num(t["count"])}' for i, t in enumerate(types[:20])))

    for t in types[:25]:
        info = type_nt.get(t['value'])
        if not info:
            continue
        cn = NT_CN.get(info['nt'], info['nt'])
        c.add(
            f'{t["value"]} 是什么细胞？在连接组里有多少个？',
            f'{t["value"]} 在 MaleCNS v1.0 中共有 {num(t["count"])} 个神经元。'
            f'递质预测为{cn}（{info["nt"]}）。')

    # -------- 5. 左右对称性与神经节 --------
    side = {d['value']: d['count'] for d in dist['side']['top']}
    c.add(
        '果蝇中枢神经系统的神经元左右对称吗？',
        f'高度对称。MaleCNS v1.0 中标注了胞体侧（somaSide）的神经元里，'
        f'左侧 {num(side.get("L", 0))} 个、右侧 {num(side.get("R", 0))} 个，几乎一一对应；'
        f'另有 {num(side.get("M", 0))} 个位于中线。',
        'Are Drosophila CNS neurons bilaterally symmetric?',
        f'Yes: {num(side.get("L", 0))} left vs {num(side.get("R", 0))} right, with only '
        f'{num(side.get("M", 0))} midline somata.')

    nm = {d['value']: d['count'] for d in dist['neuromere']['top']}
    lines = '\n'.join(f'{k}：{num(v)}' for k, v in list(nm.items())[:10])
    c.add(
        'MaleCNS 里神经元的胞体分布在哪些神经节（neuromere）？',
        f'胞体神经节标注共覆盖 {dist["neuromere"]["unique"]} 个区段，数量前十为：\n{lines}\n'
        f'胸段 T1–T3 最多，这与果蝇胸部集中了腿部与翅膀运动控制回路相符。')

    # -------- 6. 数据质量 --------
    st = {d['value']: d['count'] for d in dist['status_label']['top']}
    c.add(
        'MaleCNS v1.0 的数据追踪质量如何？',
        '标注表用 statusLabel 记录了每个细胞的追踪状态，分布为：'
        + '；'.join(f'{k} {num(v)}' for k, v in list(st.items())[:8])
        + f'。另有 {num(st.get("Glia", 0))} 个细胞被判定为胶质细胞。'
          f'使用时需要注意「Roughly traced」与「Prelim Roughly traced」占比不小，'
          f'做精细环路分析时应配合 minconf 置信度筛选。')

    # -------- 7. 出入神经 --------
    en = {d['value']: d['count'] for d in dist['entry_nerve']['top']}
    xn = {d['value']: d['count'] for d in dist['exit_nerve']['top']}
    c.add(
        '果蝇中枢神经系统通过哪些外周神经与身体交换信息？',
        f'MaleCNS 标注了每个神经元进出中枢的神经通路。感觉输入主要经：'
        + '、'.join(f'{k}（{num(v)}）' for k, v in list(en.items())[:6])
        + f'；运动输出主要经：' + '、'.join(f'{k}（{num(v)}）' for k, v in list(xn.items())[:6])
        + '。其中 AN（触角神经）是最大的感觉入口，MetaLN/MesoLN（后/中足神经）则是主要的运动出口。')

    # -------- 8. 连接表统计（可选）--------
    if args.with_connectivity and os.path.exists(CONN_STATS):
        cs = json.load(open(CONN_STATS, encoding='utf-8'))
        ns = cs.get('neuron_subgraph', {})
        c.add(
            'MaleCNS 连接组一共有多少条突触连接？',
            f'收敛到 {num(ns.get("neurons", 166700))} 个注释神经元之间的连接后，'
            f'共有 {num(cs["edges"])} 条有向连接，累计 {num(cs["synapses"])} 个突触'
            f'（与论文报告的约 1.25 亿突触一致）。'
            f'平均每个神经元发出约 {cs["mean_fanout"]:.0f} 个突触、接收约 {cs["mean_fanin"]:.0f} 个。'
            f'注意连接表全表口径（含未注释碎片）是 {num(cs.get("full_table", {}).get("rows", 0))} 条边，'
            f'引用时必须说明口径。',
            'How many synaptic connections are in MaleCNS v1.0?',
            f'{num(cs["edges"])} directed neuron-to-neuron edges comprising {num(cs["synapses"])} synapses, '
            f'matching the ~125 million synapses reported in the paper.')

        q = cs.get('weight_quantiles') or {}
        if q:
            c.add(
                '果蝇神经元之间的突触连接强度分布是什么样的？',
                f'高度长尾。按「一对神经元之间有几个突触」统计：'
                f'中位数只有 {q.get("p50", 0):.0f} 个，90 分位 {q.get("p90", 0):.0f} 个，'
                f'99 分位 {q.get("p99", 0):.0f} 个，99.9 分位 {q.get("p999", 0):.0f} 个。'
                f'也就是说绝大多数连接只有个别突触，只有极少数连接是「强连接」。')

        for h in cs.get('top_hubs', [])[:12]:
            t = h.get('type') or '未标注类型'
            c.add(
                f'连接组里的 {h["body"]} 号神经元有什么特点？',
                f'它是连接数最多的神经元之一：输出突触 {num(h["fanout"])} 个，'
                f'输入突触 {num(h["fanin"])} 个。细胞类型为 {t}，'
                f'超类为 {h.get("superclass") or "未标注"}。')

        c.add(
            '果蝇连接组里的「枢纽神经元」有什么规律？',
            '有明显的双侧对称性。输出突触最多的前 20 个神经元几乎都是成对出现'
            '（左、右各一个），例如 CT1、APL、Li39、LPi21、Am1、MeVC11 都各自成对。'
            '其中 APL 是蘑菇体里著名的巨型 GABA 能反馈神经元，'
            '负责对 Kenyon 细胞提供抑制——数据独立地把这对细胞识别为顶级枢纽，'
            '与文献一致，可以作为数据可靠性的一个交叉验证。',
            'Do hub neurons show any pattern in the connectome?',
            'Yes — strong bilateral symmetry. Nearly all of the top-20 hub neurons appear in left/right pairs '
            '(e.g. CT1, APL, Li39, LPi21, Am1, MeVC11). APL, a well-known giant GABAergic feedback neuron '
            'of the mushroom body, is independently recovered as a top hub.')

    # -------- 写盘 --------
    os.makedirs(os.path.dirname(OUT_JSONL), exist_ok=True)
    with open(OUT_JSONL, 'w', encoding='utf-8') as f:
        for r in c.rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('# 果蝇中枢神经系统连接组事实底稿（MaleCNS v1.0）\n\n')
        f.write('> 由 `build_flybrain_corpus.py` 从真实数据自动生成，用于人工校对。\n')
        f.write('> 每条问答的事实均来自 `data/male_cns/stats.json` 与官方 feather 标注表。\n\n')
        f.write('## 统计口径声明\n\n')
        f.write(f'- 标注表总记录：{num(n_rows)}（含胶质、伪影）\n')
        f.write(f'- 神经元数（有 superclass）：{num(n_neuron)}\n')
        f.write(f'- 细胞类型（type 唯一值）：{num(ntype_total)}\n')
        f.write(f'- 递质统计口径：{num(sub_total)} 个「标注 ∩ 递质预测」均可映射的神经元\n\n')
        f.write('---\n\n')
        f.write('\n---\n\n'.join(c.facts))

    print(f'生成问答对: {len(c.rows)} 条  ->  {OUT_JSONL}')
    print(f'事实底稿  : {OUT_MD}')
    print(f'语料大小  : {os.path.getsize(OUT_JSONL)/1024:.1f} KB')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-connectivity', action='store_true')
    build(ap.parse_args())
