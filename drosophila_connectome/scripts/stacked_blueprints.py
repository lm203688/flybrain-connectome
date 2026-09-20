"""虚拟生物「堆叠方案」设计器 + 可行性验证器。

核心洞察：
    每个「板块」= 一个 blueprint，本身追溯到某个真实 MaleCNS motif
    （reservoir_smallworld / inhibitory_hub / recurrent_feedback）。
    不同 blueprint 组合（`_apply_blueprint` 已支持 `"a+b+c"` 语法）
    产生「某方面特别强」的虚拟生物。

    本脚本定义 5 个「某方面特别强」的堆叠方案，对每个方案执行：
      1. 组合解析：拆出 blueprint 组件
      2. Motif 追溯：追溯到几个不同 motif（护城河① 可追溯性保持）
      3. 真生成：调 design_organism 生成 organism，跑 _apply_blueprint
      4. 可行性指标：边数、fanout 爆炸、metrics、stability_target
      5. 冲突检测：多条规则同 (from,to,kind,semantic) 时的权重胜出情况

产出：
    male_cns/stacked_blueprints.json  -- 5 个方案的描述 + 可行性判断（~30 KB）
    male_cns/stacked_organisms/        -- 每个方案生成一个 example organism

用法：
    python stacked_blueprints.py                 # 生成全部 5 个方案 + 报告
    python stacked_blueprints.py --list          # 只打印方案摘要
    python stacked_blueprints.py --only visual   # 只跑某个方案（子串匹配）
    python stacked_blueprints.py --show-report   # 打印可行性报告
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# 加载 synthetic_bio_topology
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent  # flybrain-connectome/
MCP_DIR = PROJECT / 'flybrain-connectome-mcp'
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import synthetic_bio_topology as sbt  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════
# 5 个「某方面特别强」的堆叠方案
# ══════════════════════════════════════════════════════════════════════════
STACKED = [
    {
        'name': 'stack_visual_cognition',
        'label': '视觉认知专精',
        'combination': 'hierarchical+lateral_inhibition+attention_gate',
        'strength': '视觉抽象 + 对比度增强 + 选择性注意',
        'use_cases': ['图像分类多步推理', '视觉特征增强', '注意引导的视觉推理'],
        'expected_motifs': ['reservoir_smallworld', 'inhibitory_hub'],
        'expected_stability': 0.30,
        'rational': (
            '皮质层级 (hierarchical) 提供 V1→V2→IT 分层抽象；'
            '侧向抑制 (lateral_inhibition) 在 memory 之间突出局部信号；'
            '注意力门控 (attention_gate) 对输入做选择性过滤。'
            '三者组合形成「输入过滤 → 分层抽象 → 局部增强」的完整视觉认知链。'
        ),
    },
    {
        'name': 'stack_reinforcement_decision',
        'label': '强化决策专精',
        'combination': 'competitive_selection+reward_gated_selection+punishment_suppression',
        'strength': 'winner-take-all + 奖励强化 + 惩罚抑制',
        'use_cases': ['A/B 候选选择', '强化学习决策', '安全护栏 + 奖励调制'],
        'expected_motifs': ['inhibitory_hub'],
        'expected_stability': 0.30,
        'rational': (
            '竞争选择 (competitive_selection) 提供 winner-take-all 骨架；'
            '奖赏门控 (reward_gated_selection) 引入多巴胺偏置强化胜者；'
            '惩罚抑制 (punishment_suppression) 对错误动作施加广播抑制。'
            '三者全部追溯 inhibitory_hub（APL body 10540），'
            '单一 motif 的三重强化，形成「候选投票 → 奖励调制 → 惩罚否决」的完整决策链。'
        ),
    },
    {
        'name': 'stack_active_inference',
        'label': '主动推断专精',
        'combination': 'predictive_coding+working_memory_buffer+attention_working_combo',
        'strength': '生成模型 + 工作记忆 + 认知控制',
        'use_cases': ['主动推断', '假设-检验循环', '生成模型 + 注意力引导操作'],
        'expected_motifs': ['recurrent_feedback', 'inhibitory_hub'],
        'expected_stability': 0.30,
        'rational': (
            '预测编码 (predictive_coding) 提供自上而下预测 + 自下而上误差；'
            '工作记忆缓冲 (working_memory_buffer) 用 recurrent 实现活跃操作；'
            '注意力+工作组合 (attention_working_combo) 把两者串成完整认知控制链。'
            '双 motif 组合（recurrent_feedback 主 + inhibitory_hub 辅），'
            '形成「预测 → 误差 → 工作记忆操作 → 注意力状态上报」的闭环。'
        ),
    },
    {
        'name': 'stack_habit_automation',
        'label': '习惯自动化专精',
        'combination': 'habit_consolidation+fast_reflex+modular_isolation',
        'strength': '习惯固化 + 快速反射 + 模块隔离',
        'use_cases': ['技能自动化', '程序性记忆', '故障隔离的高 recurrent 回路'],
        'expected_motifs': ['recurrent_feedback', 'inhibitory_hub'],
        'expected_stability': 0.30,
        'rational': (
            '习惯固化 (habit_consolidation) 建立 memory→habit 的高 recurrent 回路；'
            '快速反射 (fast_reflex) 建立 sensory→motor 的跳跃通路（事后补记）；'
            '模块隔离 (modular_isolation) 强化模块内密化 + 跨模块极稀疏路由。'
            '两者组合（recurrent_feedback + inhibitory_hub）+ 1 个人工蓝图（fast_reflex, motif=none），'
            '形成「快反射执行 + 慢习惯固化 + 高隔离稳定」的习惯自动化范式。'
        ),
    },
    {
        'name': 'stack_meta_cognition',
        'label': '元认知控制专精',
        'combination': 'metacognitive_control+working_memory_buffer+attention_working_combo',
        'strength': '元认知监控 + 工作记忆 + 认知控制',
        'use_cases': ['自我修正', '认知监控', '多步任务的元层面控制'],
        'expected_motifs': ['inhibitory_hub', 'recurrent_feedback'],
        'expected_stability': 0.30,
        'rational': (
            '元认知控制 (metacognitive_control) 建立 metacognition 层做全局监控；'
            '工作记忆缓冲 (working_memory_buffer) 提供活跃操作的工作空间；'
            '注意力+工作组合 (attention_working_combo) 串起注意力到工作记忆的完整链。'
            '双 motif 组合（inhibitory_hub + recurrent_feedback），'
            '形成「工作记忆操作 → 元认知监控 → 认知控制调整」的元层面闭环。'
        ),
    },
]


# ══════════════════════════════════════════════════════════════════════════
# 可行性验证
# ══════════════════════════════════════════════════════════════════════════
def _trace_motifs(combination: str) -> dict:
    """从组合标签拆出所有用到的 motif 及追溯来源。"""
    parts = [p.strip() for p in combination.replace('(', '').replace(')', '').split('+')]
    motif_traces = {}
    for name in parts:
        entry = sbt.BLUEPRINT_SOURCE_MOTIF.get(name)
        if entry is None:
            continue
        motif = entry.get('motif')
        if motif in (None, 'none'):
            continue
        motif_traces.setdefault(motif, {'blueprints': [], 'anchor': entry.get('anchor')})
        motif_traces[motif]['blueprints'].append(name)
    return motif_traces


def _stack_feasibility(stack) -> dict:
    """对单个堆叠方案跑可行性判断：真生成 organism 并统计。"""
    combination = stack['combination']
    parts = [p.strip() for p in combination.split('+')]

    # 1. 组件检查：所有 blueprint 都必须存在
    missing = [p for p in parts if p not in sbt.BLUEPRINTS]
    if missing:
        return {'feasible': False, 'error': f'missing blueprints: {missing}'}

    # 2. 追溯 motif
    motif_traces = _trace_motifs(combination)
    n_distinct_motifs = len(motif_traces)

    # 3. 真生成：n_modules=10 覆盖全部 10 个 profile，agents_per_module=3
    spec = {
        'n_modules': 10,
        'agents_per_module': 3,
        'use_inhibitory_coordinator': True,
        'use_reservoir_buffer': True,
        'use_recurrent_memory': True,
        'recurrent_pct': 0.287,
        'blueprint': combination,
    }
    t0 = time.time()
    try:
        org = sbt.design_organism(spec, seed=42)
    except Exception as e:
        return {'feasible': False, 'error': f'design_organism failed: {e}'}
    gen_ms = (time.time() - t0) * 1000

    # 4. 统计
    nodes = org.get('organism', {}).get('nodes', [])
    edges = org.get('organism', {}).get('edges', [])
    n_nodes = len(nodes)
    n_edges_total = len(edges)
    blueprint_edges = [e for e in edges if e.get('blueprint') == combination]
    n_blueprint_edges = len(blueprint_edges)
    bp_added = org.get('blueprint_edges_added', n_blueprint_edges)

    # 5. fanout 爆炸检测：单一 blueprint 组合边数超过阈值 = 爆炸
    fanout_edge_count_threshold = 200  # 6 modules × 4 cells 场景的合理上限
    fanout_explosion = n_blueprint_edges > fanout_edge_count_threshold

    # 6. 权重冲突检测：统计有多少 (from,to,kind,semantic) 组合被多 blueprint 覆盖
    rule_keys = {}
    for p in parts:
        for rule in sbt.BLUEPRINTS[p]['cross_edges']:
            key = (rule['from_profile'], rule['to_profile'], rule['kind'], rule['semantic'])
            rule_keys.setdefault(key, []).append((p, rule['weight']))
    conflicts = {k: v for k, v in rule_keys.items() if len(v) > 1}
    n_conflicts = len(conflicts)

    # 7. 稳定性信息（在 motif_provenance.stability_summary.worst_case_target）
    metrics = org.get('metrics', {})
    mp = org.get('motif_provenance', {}) or {}
    stab_summary = mp.get('stability_summary', {}) or {}
    stability = stab_summary.get('worst_case_target')
    stability_targets = stab_summary.get('targets_seen', [])

    return {
        'feasible': True,
        'combination': combination,
        'n_components': len(parts),
        'components': parts,
        'motif_traces': motif_traces,
        'n_distinct_motifs': n_distinct_motifs,
        'n_motifs_matches_expected': n_distinct_motifs == len(stack['expected_motifs']),
        'organism_stats': {
            'n_nodes': n_nodes,
            'n_edges_total': n_edges_total,
            'n_blueprint_edges': n_blueprint_edges,
            'blueprint_edges_added': bp_added,
            'fanout_edge_count': n_blueprint_edges,
            'fanout_explosion': fanout_explosion,
            'fanout_edge_count_threshold': fanout_edge_count_threshold,
            'rule_conflicts': n_conflicts,
            'rule_conflict_details': {
                str(k): [{'bp': p, 'weight': w} for p, w in v]
                for k, v in conflicts.items()
            },
        },
        'metrics_snapshot': {k: metrics.get(k) for k in
                            ('n_nodes', 'n_edges', 'avg_degree', 'inhibition_ratio',
                             'intra_module_edges', 'inter_module_edges',
                             'modularity_est') if k in metrics},
        'stability_target': stability,
        'stability_targets_all': stability_targets,
        'expected_stability': stack['expected_stability'],
        # stability_target 越小越隔离；合理范围 [0.1, 0.4]
        'stability_in_range': (stability is not None
                               and 0.1 <= stability <= 0.4),
        'generation_ms': round(gen_ms, 1),
    }


def build_report(stacks=None) -> dict:
    """生成完整的堆叠方案报告。"""
    stacks = stacks or STACKED
    report = {
        'schema_version': '1.0.0',
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'n_stacks': len(stacks),
        'motif_library': sorted({m for s in STACKED for m in s['expected_motifs']}),
        'stacks': [],
    }
    for stack in stacks:
        result = _stack_feasibility(stack)
        entry = dict(stack)
        entry['feasibility'] = result
        report['stacks'].append(entry)

    # 汇总
    all_feasible = all(s['feasibility'].get('feasible') for s in report['stacks'])
    all_stability_ok = all(
        s['feasibility'].get('feasible') and s['feasibility'].get('stability_in_range')
        for s in report['stacks']
    )
    report['summary'] = {
        'all_feasible': all_feasible,
        'all_stability_ok': all_stability_ok,
        'n_feasible': sum(1 for s in report['stacks']
                          if s['feasibility'].get('feasible')),
        'n_stability_ok': sum(1 for s in report['stacks']
                              if s['feasibility'].get('feasible')
                              and s['feasibility'].get('stability_in_range')),
        'total_fanout_edges': sum(
            s['feasibility'].get('feasible') and
            s['feasibility'].get('organism_stats', {}).get('n_blueprint_edges', 0)
            for s in report['stacks']
        ),
    }
    return report


def _save_org(org, name, out_dir):
    """保存 example organism 到 male_cns/stacked_organisms/。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f'{name}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(org, f, ensure_ascii=False, indent=2)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true', help='只打印方案摘要')
    ap.add_argument('--only', help='子串匹配方案名')
    ap.add_argument('--show-report', action='store_true', help='打印可行性报告')
    ap.add_argument('--out-report', default=None,
                    help='报告输出路径（默认 male_cns/stacked_blueprints.json）')
    ap.add_argument('--out-orgs', default=None,
                    help='example organism 输出目录（默认 male_cns/stacked_organisms/）')
    args = ap.parse_args()

    stacks = STACKED
    if args.only:
        stacks = [s for s in STACKED if args.only in s['name']]

    if args.list:
        print(f'\n=== {len(stacks)} stacked blueprints ===\n')
        for s in stacks:
            print(f"  {s['name']:<32s}  {s['label']}")
            print(f"    combination: {s['combination']}")
            print(f"    strength:    {s['strength']}")
            print(f"    motifs:      {', '.join(s['expected_motifs'])}")
            print()
        return

    if args.out_report is None:
        args.out_report = str(PROJECT / 'male_cns' / 'stacked_blueprints.json')
    if args.out_orgs is None:
        args.out_orgs = str(PROJECT / 'male_cns' / 'stacked_organisms')

    print(f'Generating {len(stacks)} stacked organism examples...\n')
    report = build_report(stacks)

    # 保存 example organisms
    orgs_dir = Path(args.out_orgs)
    org_paths = {}
    for s in report['stacks']:
        if s['feasibility'].get('feasible'):
            spec = {
                'n_modules': 10,
                'agents_per_module': 3,
                'use_inhibitory_coordinator': True,
                'use_reservoir_buffer': True,
                'use_recurrent_memory': True,
                'recurrent_pct': 0.287,
                'blueprint': s['combination'],
            }
            org = sbt.design_organism(spec, seed=42)
            p = _save_org(org, s['name'], orgs_dir)
            org_paths[s['name']] = str(p)

    report['organism_paths'] = org_paths

    # 保存报告
    Path(args.out_report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_report, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 打印摘要
    s = report['summary']
    print(f"Report: {args.out_report}")
    print(f"Organisms: {args.out_orgs}/  ({len(org_paths)} files)\n")
    print(f"Summary: {s['n_feasible']}/{report['n_stacks']} feasible, "
          f"{s['n_stability_ok']}/{report['n_stacks']} stability OK")
    print(f"  all_feasible={s['all_feasible']}  all_stability_ok={s['all_stability_ok']}")
    print(f"  total blueprint edges: {s['total_fanout_edges']}\n")

    if args.show_report:
        for s in report['stacks']:
            print(f"\n=== {s['name']} ({s['label']}) ===")
            print(f"  combination: {s['combination']}")
            print(f"  strength:    {s['strength']}")
            f = s['feasibility']
            if not f.get('feasible'):
                print(f"  INFEASIBLE: {f.get('error')}")
                continue
            st = f['organism_stats']
            print(f"  feasible=True  motifs={f['n_distinct_motifs']}  "
                  f"matches_expected={f['n_motifs_matches_expected']}")
            print(f"  organism: nodes={st['n_nodes']} edges_total={st['n_edges_total']} "
                  f"blueprint_edges={st['n_blueprint_edges']} "
                  f"edges_added={st['blueprint_edges_added']}")
            print(f"  fanout_explosion={st['fanout_explosion']}  "
                  f"rule_conflicts={st['rule_conflicts']}")
            if f['stability_target'] is not None:
                print(f"  stability_target={f['stability_target']:.2f}  "
                      f"expected={f['expected_stability']}  "
                      f"in_range={f['stability_in_range']}")
            else:
                print(f"  stability_target=None  expected={f['expected_stability']}")
            m = f['metrics_snapshot']
            print(f"  metrics: avg_degree={m.get('avg_degree')}  "
                  f"inhibition={m.get('inhibition_ratio')}  "
                  f"modularity={m.get('modularity_est')}")
            print(f"  generation: {f['generation_ms']}ms")
    return 0


if __name__ == '__main__':
    sys.exit(main())
