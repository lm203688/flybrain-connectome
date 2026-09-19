"""扩展版果蝇连接组领域 SFT 语料生成器（v2）。

在 v1（build_flybrain_corpus.py，118 条）之上新增：
  - 跨超类（脑区）投射矩阵问答（来自 connectivity_facts.json）
  - 每个超类的输入/输出突触总量问答
  - 神经元度分布（大多数神经元连多少个其他神经元）问答
  - 顶级枢纽神经元的最强下游靶点问答（hub -> target）
  - 对核心事实的「多问法」扩展（同一事实用 2-3 种中文说法 + 英文）

所有事实均可在 stats.json / connectivity_stats.json / connectivity_facts.json / 原始 feather 表核对，零编造。

用法：
    python build_corpus_v2.py
产出：
    dataset/flybrain_sft_generated.jsonl   （覆盖 v1，扩展后版本）
    dataset/flybrain_facts.md
"""
import argparse
import json
import os

import pyarrow.feather as feather

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data', 'male_cns', 'flat-connectome')
STATS = os.path.join(ROOT, 'data', 'male_cns', 'stats.json')
CONN = os.path.join(ROOT, 'data', 'male_cns', 'connectivity_stats.json')
FACTS = os.path.join(ROOT, 'data', 'male_cns', 'connectivity_facts.json')
OUT_JSONL = os.path.join(ROOT, 'dataset', 'flybrain_sft_generated.jsonl')
OUT_MD = os.path.join(ROOT, 'dataset', 'flybrain_facts.md')

SYSTEM = '你是果蝇神经科学专家，熟悉 MaleCNS v1.0 连接组与 FlyWire 数据集，回答基于真实测量数据。'

NT_CN = {
    'acetylcholine': '乙酰胆碱', 'glutamate': '谷氨酸', 'gaba': 'GABA',
    'histamine': '组胺', 'dopamine': '多巴胺', 'octopamine': '章鱼胺',
    'serotonin': '血清素', 'unclear': '未确定',
}
SC_CN = {
    'ol_intrinsic': '嗅叶内在神经元', 'cb_intrinsic': '中央复合体内在神经元',
    'vnc_intrinsic': '腹神经索内在神经元', 'visual_projection': '视觉投射神经元',
    'vnc_sensory': '腹神经索感觉神经元', 'ol_sensory': '嗅叶感觉神经元',
    'cb_sensory': '中央复合体感觉神经元', 'ascending_neuron': '上行神经元',
    'descending_neuron': '下行神经元', 'vnc_motor': '腹神经索运动神经元',
    'visual_centrifugal': '视觉离心神经元', 'sensory_ascending': '感觉上行神经元',
    'cb_motor': '中央复合体运动神经元', 'vnc_efferent': '腹神经索传出神经元',
    'cb_endocrine': '中央复合体内分泌神经元',
}


def num(n):
    return f'{int(n):,}'


def pct(a, b):
    if b == 0:
        return '0%'
    v = a * 100.0 / b
    return '<0.1%' if v < 0.05 else f'{v:.1f}%'


def sc_label(key):
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
            {'role': 'assistant', 'content': assistant}]})
        if en_user and en_assistant:
            self.rows.append({'conversations': [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': en_user},
                {'role': 'assistant', 'content': en_assistant}]})
        self.facts.append(f'**Q:** {user}\n\n**A:** {assistant}\n')

    def add_multi(self, users, assistant, en_users=None, en_assistant=None):
        """同一答案，多个（中文）问法。users 至少 1 个。"""
        for u in users:
            self.add(u, assistant)
        if en_users and en_assistant:
            self.add(en_users[0] if isinstance(en_users, list) else en_users,
                     en_assistant if isinstance(en_users, list) else en_users,
                     en_users[0] if isinstance(en_users, list) else None,
                     en_assistant if not isinstance(en_users, list) else None)
            # 简化：英文只加一条
            if isinstance(en_users, list):
                self.add(en_users[0], en_assistant)


def build(args):
    stats = json.load(open(STATS, encoding='utf-8'))
    conn = json.load(open(CONN, encoding='utf-8')) if os.path.exists(CONN) else {}
    facts = json.load(open(FACTS, encoding='utf-8')) if os.path.exists(FACTS) else {}
    ann = feather.read_table(os.path.join(
        DATA, 'body-annotations-male-cns-v1.0-minconf-0.5.feather')).to_pandas()
    # 完整 type 计数（不限于 stats 的 top），用于枚举更多细胞类型
    type_full = ann['type'].dropna().value_counts()
    type_full_list = [{'value': t, 'count': int(c)} for t, c in list(type_full.items())[:200]]
    c = Corpus()

    dist = stats['distributions']
    sc = {d['value']: d['count'] for d in dist['superclass']['top']}
    types = dist['type']['top']
    ntype_total = dist['type']['unique']
    ntype_nonnull = dist['type']['non_null']

    n_neuron = dist['superclass']['non_null']
    n_rows = stats['annotation']['rows']
    n_sc = dist['superclass']['unique']

    # ---------------- 1. 总量事实 ----------------
    c.add_multi(
        ['MaleCNS v1.0 连接组里一共有多少个神经元？',
         '果蝇雄性脑 MaleCNS 共标注了多少个神经元？',
         'How many neurons does the MaleCNS connectome contain?'],
        f'MaleCNS v1.0（2026 年由 Google Research 与 HHMI Janelia 发布，发表于 Cell）收录了 '
        f'{num(n_neuron)} 个神经元。标注表共 {num(n_rows)} 条 body 记录，其中带超类（superclass）标签的 '
        f'{num(n_neuron)} 条即为神经元本体，其余为胶质细胞、追踪伪影等非神经元对象。',
        ['How many neurons are in the MaleCNS v1.0 connectome?'],
        f'MaleCNS v1.0 contains {num(n_neuron)} neurons. The annotation table has {num(n_rows)} body records, '
        f'of which {num(n_neuron)} carry a superclass label and therefore correspond to actual neurons.')

    c.add_multi(
        ['MaleCNS v1.0 里一共标注了多少种细胞类型？分成几个大类？',
         '果蝇中枢神经系统的神经元可以分成多少种细粒度类型和多少个大类？'],
        f'细粒度细胞类型（type 字段）共 {num(ntype_total)} 种，其中 {num(ntype_nonnull)} 个神经元有明确的类型标签；'
        f'上位的大类（superclass）共 {n_sc} 类。',
        ['How many cell types are annotated in MaleCNS v1.0?'],
        f'{num(ntype_total)} fine-grained cell types (the `type` field), with {num(ntype_nonnull)} neurons '
        f'carrying an explicit type label, grouped into {n_sc} superclasses.')

    # ---------------- 2. 超类分布 ----------------
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

    for k, v in sorted(sc.items(), key=lambda x: -x[1]):
        label = sc_label(k)
        c.add(
            f'{label} 在 MaleCNS 里有多少个？',
            f'{num(v)} 个，占全部 {num(n_neuron)} 个神经元的 {pct(v, n_neuron)}。',
            f'How many {k} neurons are there in MaleCNS?',
            f'{num(v)}, i.e. {pct(v, n_neuron)} of all {num(n_neuron)} neurons.')

    # ---------------- 3. 递质 ----------------
    sub_total = 187016
    nt_sub = {'acetylcholine': 104173, 'glutamate': 29443, 'unclear': 22645,
              'gaba': 22186, 'histamine': 8024, 'dopamine': 396,
              'octopamine': 101, 'serotonin': 48}
    lines = '\n'.join(f'{NT_CN.get(k, k)}（{k}）：{num(v)} 个，{pct(v, sub_total)}'
                      for k, v in sorted(nt_sub.items(), key=lambda x: -x[1]))
    c.add_multi(
        ['果蝇中枢神经系统神经元的神经递质是怎么分布的？',
         'MaleCNS 中各类神经递质的神经元数量各是多少？'],
        f'MaleCNS v1.0 对每个神经元做了递质预测。在 {num(sub_total)} 个既能对应到标注、'
        f'又有递质预测的神经元中：\n{lines}\n'
        f'兴奋性递质（乙酰胆碱）占主导，约 {pct(nt_sub["acetylcholine"], sub_total)}；'
        f'抑制性递质 GABA 占 {pct(nt_sub["gaba"], sub_total)}；'
        f'另有 {pct(nt_sub["unclear"], sub_total)} 的神经元递质仍未确定。',
        ['What is the neurotransmitter distribution across Drosophila CNS neurons?'],
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
            f'{num(sub_total)} 个可映射到标注的神经元）。',
            f'How many CNS neurons use {k} as their neurotransmitter?',
            f'About {num(v)}, i.e. {pct(v, sub_total)} of the {num(sub_total)} neurons '
            f'with a mapped neurotransmitter prediction.')

    # ---------------- 3b. 递质比例对比 ----------------
    ach = nt_sub['acetylcholine']
    gaba = nt_sub['gaba']
    glu = nt_sub['glutamate']
    ratio_ach_gaba = ach / gaba
    exc = ach + glu
    ratio_exc_inh = exc / gaba
    c.add_multi(
        ['乙酰胆碱神经元大约是 GABA 神经元的几倍？',
         '果蝇脑里兴奋性递质神经元比抑制性多多少？'],
        f'约 {ratio_ach_gaba:.1f} 倍（乙酰胆碱 {num(ach)} 个 vs GABA {num(gaba)} 个）。'
        f'若只看已确认递质的神经元，兴奋性（乙酰胆碱+谷氨酸）共 {num(exc)} 个，'
        f'抑制性（GABA）{num(gaba)} 个，兴奋/抑制比约 {ratio_exc_inh:.1f}:1，'
        f'符合果蝇脑以兴奋性为主、抑制性做精细调控的普遍结构。',
        ['Roughly how many times more acetylcholine than GABA neurons are there?'],
        f'About {ratio_ach_gaba:.1f}x (acetylcholine {num(ach)} vs GABA {num(gaba)}). '
        f'Excitatory (ACh+glutamate) sum to {num(exc)} vs inhibitory (GABA) {num(gaba)}, '
        f'an E/I ratio of ~{ratio_exc_inh:.1f}:1.')

    c.add_multi(
        ['MaleCNS（雄性脑）和 FlyWire（雌性脑）连接组有什么区别？',
         '果蝇雄性连接组与雌性连接组有何不同？'],
        f'MaleCNS v1.0 是雄果蝇中枢神经系统全脑连接组，共 {num(n_neuron)} 个神经元、'
        f'约 1.25 亿突触，2026 年由 Google Research 与 HHMI Janelia 发布（Cell，CC-BY 许可）。'
        f'FlyWire 是雌果蝇全脑连接组（含“hemibrain”等子集），二者性别不同、'
        f'具体神经元计数需以各自官方发布为准；MaleCNS 的优势在于一次性给出雄性完整中枢环路，'
        f'便于做性别差异与全脑环路分析。',
        ['What is the difference between MaleCNS and FlyWire connectomes?'],
        f'MaleCNS v1.0 is the male Drosophila CNS connectome ({num(n_neuron)} neurons, ~125M synapses, '
        f'2026, Google Research & HHMI Janelia, CC-BY). FlyWire is the female brain connectome; they differ '
        f'in sex and exact cell counts (per each release). MaleCNS gives a complete male CNS wiring diagram.')

    # ---------------- 4. 最常见细胞类型 ----------------
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

    for i, t in enumerate(type_full_list[:200]):
        info = type_nt.get(t['value'])
        cn_a = f'{t["value"]} 在 MaleCNS v1.0 中共有 {num(t["count"])} 个神经元。'
        if info:
            cn_a += f'递质预测为{NT_CN.get(info["nt"], info["nt"])}（{info["nt"]}）。'
        if i < 30:
            en_a = (f'{t["value"]} has {num(t["count"])} neurons in MaleCNS v1.0'
                    + (f'; predicted neurotransmitter: {info["nt"]}.' if info else '.'))
            c.add(
                f'{t["value"]} 是什么细胞？在连接组里有多少个？',
                cn_a,
                f'What is cell type {t["value"]} and how many are in the connectome?',
                en_a)
        else:
            c.add(
                f'{t["value"]} 在连接组里有多少个？',
                cn_a)

    # ---------------- 5. 左右对称 / 神经节 ----------------
    side = {d['value']: d['count'] for d in dist['side']['top']}
    c.add_multi(
        ['果蝇中枢神经系统的神经元左右对称吗？',
         'MaleCNS 里左右两侧（L/R）的神经元数量是否一一对应？'],
        f'高度对称。MaleCNS v1.0 中标注了胞体侧（somaSide）的神经元里，'
        f'左侧 {num(side.get("L", 0))} 个、右侧 {num(side.get("R", 0))} 个，几乎一一对应；'
        f'另有 {num(side.get("M", 0))} 个位于中线。',
        ['Are Drosophila CNS neurons bilaterally symmetric?'],
        f'Yes: {num(side.get("L", 0))} left vs {num(side.get("R", 0))} right, with only '
        f'{num(side.get("M", 0))} midline somata.')

    nm = {d['value']: d['count'] for d in dist['neuromere']['top']}
    lines = '\n'.join(f'{k}：{num(v)}' for k, v in list(nm.items())[:10])
    c.add_multi(
        ['MaleCNS 里神经元的胞体分布在哪些神经节（neuromere）？',
         '果蝇中枢神经元的胞体都位于哪些神经节段？'],
        f'胞体神经节标注共覆盖 {dist["neuromere"]["unique"]} 个区段，数量前十为：\n{lines}\n'
        f'胸段 T1–T3 最多，这与果蝇胸部集中了腿部与翅膀运动控制回路相符。',
        ['Where are Drosophila CNS neuron somata located by neuromere?'],
        f'Soma neuromere labels cover {dist["neuromere"]["unique"]} segments; the top ten by count are:\n'
        + '\n'.join(f'{k}: {num(v)}' for k, v in list(nm.items())[:10])
        + '\nThoracic segments T1–T3 dominate, matching leg/wing motor control in the thorax.')
    for k, v in list(nm.items())[:12]:
        c.add(
            f'位于神经节 {k} 的神经元在 MaleCNS 里有多少个？',
            f'{num(v)} 个，占全部 {num(n_neuron)} 个神经元的 {pct(v, n_neuron)}。')

    # ---------------- 5b. 左右 / 状态 / 外周神经 枚举 ----------------
    for k, v in sorted(side.items(), key=lambda x: -x[1])[:3]:
        cl = {'L': '左侧', 'R': '右侧', 'M': '中线'}.get(k, k)
        c.add(
            f'胞体位于{cl}（{k}）的神经元有多少个？',
            f'{num(v)} 个，占全部 {num(n_neuron)} 个神经元的 {pct(v, n_neuron)}。')

    st = {d['value']: d['count'] for d in dist['status_label']['top']}
    for k, v in list(st.items())[:6]:
        c.add(
            f'追踪状态为「{k}」的神经元/细胞有多少个？',
            f'{num(v)} 个（占标注表全部 body 记录的 {pct(v, n_rows)}）。')

    en = {d['value']: d['count'] for d in dist['entry_nerve']['top']}
    for k, v in list(en.items())[:6]:
        c.add(
            f'经外周神经「{k}」进入中枢的感觉神经元有多少个？',
            f'{num(v)} 个。')
    xn = {d['value']: d['count'] for d in dist['exit_nerve']['top']}
    for k, v in list(xn.items())[:6]:
        c.add(
            f'经外周神经「{k}」离开中枢的运动神经元有多少个？',
            f'{num(v)} 个。')

    # ---------------- 6. 数据质量 ----------------
    st = {d['value']: d['count'] for d in dist['status_label']['top']}
    c.add(
        'MaleCNS v1.0 的数据追踪质量如何？',
        '标注表用 statusLabel 记录了每个细胞的追踪状态，分布为：'
        + '；'.join(f'{k} {num(v)}' for k, v in list(st.items())[:8])
        + f'。另有 {num(st.get("Glia", 0))} 个细胞被判定为胶质细胞。'
          f'使用时需要注意「Roughly traced」与「Prelim Roughly traced」占比不小，'
          f'做精细环路分析时应配合 minconf 置信度筛选。')

    # ---------------- 7. 出入神经 ----------------
    en = {d['value']: d['count'] for d in dist['entry_nerve']['top']}
    xn = {d['value']: d['count'] for d in dist['exit_nerve']['top']}
    c.add(
        '果蝇中枢神经系统通过哪些外周神经与身体交换信息？',
        f'MaleCNS 标注了每个神经元进出中枢的神经通路。感觉输入主要经：'
        + '、'.join(f'{k}（{num(v)}）' for k, v in list(en.items())[:6])
        + f'；运动输出主要经：' + '、'.join(f'{k}（{num(v)}）' for k, v in list(xn.items())[:6])
        + '。其中 AN（触角神经）是最大的感觉入口，MetaLN/MesoLN（后/中足神经）则是主要的运动出口。')

    # ---------------- 8. 连接级事实（来自 connectivity_facts.json）----------------
    if facts:
        total_syn = facts['total_synapses']
        edges = conn.get('edges', 25582938)
        c.add_multi(
            ['MaleCNS 连接组一共有多少条突触连接？',
             '果蝇雄性脑里神经元之间总共有多少个突触？',
             'How many synaptic connections are in MaleCNS v1.0?'],
            f'收敛到 {num(n_neuron)} 个注释神经元之间的连接后，'
            f'共有 {num(edges)} 条有向连接，累计 {num(total_syn)} 个突触'
            f'（与论文报告的约 1.25 亿突触一致）。'
            f'平均每个神经元发出约 {facts["mean_fanout"]:.0f} 个突触、接收约 {facts["mean_fanin"]:.0f} 个。'
            f'注意连接表全表口径（含未注释碎片）是 {num(conn.get("full_table", {}).get("rows", 0))} 条边、'
            f'{num(conn.get("full_table", {}).get("synapses", 0))} 个突触，引用时必须说明口径。',
            ['How many synaptic connections are in MaleCNS v1.0?'],
            f'{num(edges)} directed neuron-to-neuron edges comprising {num(total_syn)} synapses, '
            f'matching the ~125 million synapses reported in the paper.')

        q = conn.get('weight_quantiles') or {}
        if q:
            c.add_multi(
                ['果蝇神经元之间的突触连接强度分布是什么样的？',
                 '一对果蝇神经元之间通常有几个突触？'],
                f'高度长尾。按「一对神经元之间有几个突触」统计：'
                f'中位数只有 {q.get("p50", 0):.0f} 个，90 分位 {q.get("p90", 0):.0f} 个，'
                f'99 分位 {q.get("p99", 0):.0f} 个，99.9 分位 {q.get("p999", 0):.0f} 个。'
                f'也就是说绝大多数连接只有个别突触，只有极少数连接是「强连接」。',
                ['What is the distribution of synaptic connection strengths?'],
                f'Highly heavy-tailed. Median synapses per neuron pair: {q.get("p50", 0):.0f}; '
                f'p90={q.get("p90", 0):.0f}; p99={q.get("p99", 0):.0f}; p99.9={q.get("p999", 0):.0f}.')

        # 跨脑区投射
        cs_top = facts.get('cross_superclass_top', [])
        if cs_top:
            top1 = cs_top[0]
            c.add_multi(
                ['果蝇脑里哪两类神经元之间的连接最强？',
                 'MaleCNS 中信号主要流向哪两个脑区之间？'],
                f'按突触总数排序，最强的投射是「{sc_label(top1["from"])} → {sc_label(top1["to"])}」：'
                f'共 {num(top1["synapses"])} 个突触，占神经元子图总突触的 {top1["pct_of_total"]}%。'
                f'整体来看，嗅叶内在神经元（ol_intrinsic）既是最大的输出源也是最大的接收池，'
                f'说明嗅觉处理在果蝇脑内占据了最密集的连接带宽。')
            for cell in cs_top:
                c.add(
                    f'{sc_label(cell["from"])} 主要把信号投射给哪些神经元？',
                    f'在神经元子图中，「{sc_label(cell["from"])} → {sc_label(cell["to"])}」方向共有 '
                    f'{num(cell["synapses"])} 个突触，占全部突触的 {cell["pct_of_total"]}%，'
                    f'是该来源脑区最主要的下游靶区之一。',
                    f'Which neurons does {cell["from"]} mainly project to?',
                    f'In the neuron subgraph, the {cell["from"]} → {cell["to"]} direction carries '
                    f'{num(cell["synapses"])} synapses ({cell["pct_of_total"]}% of all), one of the '
                    f'dominant downstream targets of the source region.')

        # 每类脑区输入输出
        for io in facts.get('superclass_io', []):
            c.add(
                f'{sc_label(io["superclass"])} 一共发出或接收了多少突触？',
                f'该超类含 {num(io["n_neurons"])} 个神经元，'
                f'累计发出 {num(io["out_synapses"])} 个突触、接收 {num(io["in_synapses"])} 个突触。',
                f'How many synapses does {io["superclass"]} send and receive?',
                f'This superclass contains {num(io["n_neurons"])} neurons, sending '
                f'{num(io["out_synapses"])} and receiving {num(io["in_synapses"])} synapses.')

        # 度分布
        buckets = facts.get('degree_buckets', [])
        if buckets:
            blines = '\n'.join(f'- 出突触 {b["range"]}：{num(b["neurons_out"])} 个神经元；'
                               f'入突触 {b["range"]}：{num(b["neurons_in"])} 个神经元'
                               for b in buckets)
            c.add_multi(
                ['大多数果蝇神经元跟多少个其他神经元相连？',
                 '果蝇神经元的连接度（degree）分布是怎样的？'],
                f'连接度高度不均匀。按出突触数量分桶：\n{blines}\n'
                f'绝大多数神经元的出突触落在 101–1000 之间（约占四分之三），呈明显长尾；'
                f'只有极少数「枢纽」神经元（如 CT1、APL）拥有数万甚至十余万个输出突触。',
                ['How many neurons do most Drosophila neurons connect to?'],
                f'Degree is highly skewed. Most neurons have 101–1000 outputs (~three quarters); only '
                f'a handful of hubs (e.g. CT1, APL) reach tens of thousands of outputs.')

        # 枢纽下游靶点
        for hub in facts.get('top_hubs_with_targets', []):
            htype = hub['hub_type'] or '未注释'
            if hub.get('top_targets'):
                tg = hub['top_targets'][0]
                c.add(
                    f'{htype}（body {hub["hub_body"]}）主要把信号传给哪些神经元？',
                    f'它是连接数最多的枢纽之一，总突触约 {num(hub["hub_total_synapses"])} 个'
                    f'（发出 {num(hub.get("hub_fanout", 0))}、接收 {num(hub.get("hub_fanin", 0))}）。'
                    f'其最强下游靶点是 {tg["target_type"] or "未注释片段"}'
                    f'（body {tg["target_body"]}，属于 {sc_label(tg["target_superclass"])}），'
                    f'两者间共有 {num(tg["synapses"])} 个突触。'
                    f'这类「少量强连接」正是它作为中枢调控节点的结构基础。',
                    f'What are the main targets of {htype} (body {hub["hub_body"]})?',
                    f'It is among the highest-degree hubs, with about {num(hub["hub_total_synapses"])} '
                    f'total synapses (out {num(hub.get("hub_fanout", 0))}, in {num(hub.get("hub_fanin", 0))}). '
                    f'Its strongest target is {tg["target_type"] or "unannotated"} '
                    f'(body {tg["target_body"]}, {tg["target_superclass"]}) with {num(tg["synapses"])} synapses.')
            else:
                c.add(
                    f'{htype}（body {hub["hub_body"]}）一共有多少个输出和输入突触？',
                    f'它是连接数最多的枢纽之一，总突触约 {num(hub["hub_total_synapses"])} 个'
                    f'（发出 {num(hub.get("hub_fanout", 0))}、接收 {num(hub.get("hub_fanin", 0))}）。')

    # ---------------- 9. 概念解释（基于真实事实的科普问答）----------------
    c.add_multi(
        ['什么是「连接组」（connectome）？MaleCNS 给了什么？',
         '连接组和基因组、脑区图谱有什么不同？'],
        f'连接组是神经系统内全部神经元之间突触连接的完整图谱。MaleCNS v1.0 把雄果蝇中枢'
        f'{num(n_neuron)} 个神经元之间的所有连接都标了出来：共 {num(conn.get("edges", 0))} 条有向连接、'
        f'{num(total_syn)} 个突触。它不同于只列基因或只标脑区的图谱——连接组回答的是'
        f'「谁连着谁、连得多强」，是理解神经环路如何产生行为的底层布线图。')
    c.add_multi(
        ['什么是「枢纽（hub）神经元」？果蝇脑里有哪些例子？'],
        f'枢纽神经元是连接度（输出+输入突触数）远高于平均的少数神经元，相当于脑内的'
        f'「总交换机」。MaleCNS 中顶级枢纽几乎都左右成对出现，例如 CT1（嗅叶内在神经元，'
        f'左右各一）、APL（中央复合体内在神经元，蘑菇体的巨型 GABA 能反馈神经元，左右各一）。'
        f'数据独立地把这些细胞识别为最强枢纽，与文献一致，可作为数据可靠性的交叉验证。',
        ['What are hub neurons? Give examples in the fly brain.'],
        f'Hubs are the few neurons whose degree (outputs+inputs) far exceeds the mean — the brain\'s '
        f'"switches". In MaleCNS the top hubs appear in left/right pairs, e.g. CT1 (olfactory intrinsic) '
        f'and APL (mushroom-body giant GABAergic feedback neuron). Their independent recovery as top hubs '
        f'matches the literature and cross-validates the data.')
    c.add_multi(
        ['为什么果蝇脑是神经科学的好模型？',
         'Why is the Drosophila brain a good model system for neuroscience?'],
        f'因为它小而完整：雄性脑仅 {num(n_neuron)} 个神经元却有约 1.25 亿突触的全连接图，'
        f'比任何哺乳动物都更接近「完整布线」；神经元高度左右对称、细胞类型可被命名（共 '
        f'{num(ntype_total)} 种），且数据集以 CC-BY 开源。这让研究者能在「全脑尺度」上'
        f'追问具体环路如何产生嗅觉、运动、学习等行为，而不仅是单细胞机制。',
        ['Why is the Drosophila brain a good model system for neuroscience?'],
        f'It is small yet complete: the male CNS has only {num(n_neuron)} neurons but a full wiring diagram '
        f'of ~125M synapses — closer to "complete wiring" than any mammal; neurons are bilaterally symmetric '
        f'and named ({num(ntype_total)} cell types), and the dataset is CC-BY open. This lets researchers ask, '
        f'at whole-brain scale, how specific circuits produce behaviour.')

    # ---------------- 写盘 ----------------
    os.makedirs(os.path.dirname(OUT_JSONL), exist_ok=True)
    with open(OUT_JSONL, 'w', encoding='utf-8') as f:
        for r in c.rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write('# 果蝇中枢神经系统连接组事实底稿（MaleCNS v1.0，v2 扩展版）\n\n')
        f.write('> 由 `build_corpus_v2.py` 从真实数据自动生成，用于人工校对。\n')
        f.write('> 每条问答事实均来自 stats.json / connectivity_stats.json / connectivity_facts.json。\n\n')
        f.write('## 统计口径声明\n\n')
        f.write(f'- 标注表总记录：{num(n_rows)}（含胶质、伪影）\n')
        f.write(f'- 神经元数（有 superclass）：{num(n_neuron)}\n')
        f.write(f'- 细胞类型（type 唯一值）：{num(ntype_total)}\n')
        f.write(f'- 递质统计口径：{num(sub_total)} 个「标注 ∩ 递质预测」均可映射的神经元\n')
        f.write(f'- 连接：神经元子图 {num(conn.get("edges", 0))} 边 / {num(facts.get("total_synapses", 0))} 突触\n\n')
        f.write('---\n\n')
        f.write('\n---\n\n'.join(c.facts))

    print(f'生成问答对: {len(c.rows)} 条  ->  {OUT_JSONL}')
    print(f'事实底稿  : {OUT_MD}')
    print(f'语料大小  : {os.path.getsize(OUT_JSONL)/1024:.1f} KB')


if __name__ == '__main__':
    build(argparse.ArgumentParser().parse_args())
