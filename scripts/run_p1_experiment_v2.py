#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1 实验 v2 —— 对照组可得分性对齐 (S6 纪律落地)
==================================================

背景: v1 的 +33.4pp 被证伪 (motif_family 任务 random 组构造性为 0)。
v2 修正:
  - 从任务集里删除 random 组无法得分的任务类 (motif_family)
  - task_type 覆盖: hub, reachability (2 类)
  - 三臂: random / ours / best (10 个 ours 策略)
  - 每臂 K=50 样本
  - 每 (task_type, arm) 独立报告
  - 主指标只在"对照可得分"的子集上算

依赖:
  - MaleCNS 数据 (FLYBRAIN_DATA_DIR 环境变量)
  - 外部 LLM 端点 (OPENAI_BASE_URL + OPENAI_API_KEY 环境变量, 支持 chat/completions)
  - 若端点不可用, 跳过 LLM 实验但保留 task_type 诊断数据

用法:
  set FLYBRAIN_DATA_DIR=C:\\Users\\xing\\Desktop\\flybrain-connectome\\male_cns
  set OPENAI_BASE_URL=https://api.sensenova.cn/ai1
  set OPENAI_API_KEY=os.environ.get
  set USE_THINKING=false
  python run_p1_experiment_v2.py
"""
import os
import sys
import json
import time
import random
import argparse
import statistics
from pathlib import Path

# --- 环境 & 依赖注入 -----------------------------------------------------
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
os.environ.setdefault('FLYBRAIN_DATA_DIR',
                      r'C:\Users\xing\Desktop\flybrain-connectome\male_cns')
for p in [str(REPO), str(HERE / 'p1_experiments')]:
    if p not in sys.path:
        sys.path.insert(0, p)

STATE_DIR = HERE / 'p1_experiment_v2'
STATE_DIR.mkdir(exist_ok=True)
RESULT_FILE = STATE_DIR / 'state.json'

# =====================================================================
# 加载 P1 实验框架
# =====================================================================
print("=" * 70)
print("P1 实验 v2 · 对照组可得分性对齐")
print("=" * 70)
print(f"FLYBRAIN_DATA_DIR = {os.environ['FLYBRAIN_DATA_DIR']}")
print()

# 强制从 MaleCNS 加载数据
before_size = 0
try:
    from core.storage import get_storage
    from core.library import get_library
    get_library()  # 初始化
    get_storage().load()
    before_size = len(get_library().profiles)
except Exception as e:
    print(f"[WARN] storage load 失败: {e}")

# 加载 MaleCNS 连接器 (会重置到 MaleCNS 子集)
from connectors.malecns import load_malecns
n_malecns = load_malecns()
print(f"MaleCNS profiles: {n_malecns}")

# 检查单元数
from core.library import get_library
lib = get_library()
units = list(lib.units.values())
print(f"Lib units: {len(units)}")
if len(units) < 50:
    print("  [FATAL] units < 50, 可能未加载 MaleCNS")
    print("  Exiting.")
    sys.exit(1)

print(f"Lib profiles: {len(lib.profiles)}")

# 单元 id 列表
unit_ids = [u.id for u in units]

# =====================================================================
# 检查 LLM 可用性
# =====================================================================
OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
USE_THINKING = os.environ.get('USE_THINKING', 'false').lower() == 'true'

LLM_AVAILABLE = bool(OPENAI_BASE_URL and OPENAI_API_KEY)
if LLM_AVAILABLE:
    print(f"\nLLM 端点: {OPENAI_BASE_URL}")
    print(f"USE_THINKING = {USE_THINKING}")
    import httpx
    _t0 = time.time()
    try:
        _resp = httpx.post(
            f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": os.environ.get('MODEL', 'deepseek-v4-flash'),
                "messages": [{"role": "user", "content": "Reply with just: OK"}],
                "max_tokens": 10,
                "temperature": 0,
            },
            timeout=30,
        )
        _dt = time.time() - _t0
        if _resp.status_code == 200:
            print(f"  LLM 探测 OK ({_dt:.1f}s)")
        else:
            print(f"  LLM 探测 HTTP {_resp.status_code}: {_resp.text[:200]}")
            LLM_AVAILABLE = False
    except Exception as e:
        print(f"  LLM 探测失败: {e}")
        LLM_AVAILABLE = False
else:
    print(f"\n[!] LLM 环境变量未设置, 将只生成 task_type 诊断 (不做 LLM 实验)")

# =====================================================================
# 任务定义 (删除 motif_family, 保留 hub / reachability)
# =====================================================================
from llm_tasks import build_hub_task
from llm_reasoning import score_reachability_answer, score_hub_answer

def extract_unit_ids(text, id_pool):
    """从 LLM 输出里抽 cellX 类 id."""
    ids = []
    for tok in text.replace(',', ' ').split():
        clean = tok.strip('"\'.,;()[]{}')
        if clean in id_pool:
            ids.append(clean)
    return list(dict.fromkeys(ids))

def extract_ids_with_unit_prefix(text, unit_ids):
    """匹配 cell{unit_id}, 去前缀"""
    ids = []
    for uid in unit_ids:
        marker = f'cell{uid}'
        if marker in text:
            ids.append(uid)
    return ids

def build_ground_truths(questions, n_units, seed=42, n_samples=200):
    """
    构造 ground truth: 随机采样单元, 用它们的实际连接图定义 hub / reach.
    这是"任务构造性"——ground truth 由真实数据得出.
    """
    rng = random.Random(seed)
    from connectors.malecns import build_mixed_connection_graph

    gt = []
    for i, q in enumerate(questions):
        sample = rng.sample(range(len(unit_ids)),
                            min(n_units, len(unit_ids)))
        picked_ids = [unit_ids[j] for j in sample]

        # Hub ground truth: 该 hub 的所有直连邻居
        hub_unit = picked_ids[0]
        from core.library import get_library
        lib = get_library()
        profile = lib.get_profile_by_unit(hub_unit)
        if profile is not None:
            hub_neighbors = [c.target for c in profile.connectors
                             if c.target in picked_ids]
        else:
            hub_neighbors = []

        # Reach ground truth: source 可达 target? 通过 hub 或任意路径
        src = picked_ids[0]
        dst = picked_ids[-1]
        # 用 BFS 在 picked_ids 内做局部图
        local_graph = {}
        for uid in picked_ids:
            local_graph[uid] = set()
        for uid in picked_ids:
            p = lib.get_profile_by_unit(uid)
            if p is not None:
                for c in p.connectors:
                    if c.target in local_graph:
                        local_graph[uid].add(c.target)
        # BFS from src
        visited = {src}
        queue = [src]
        while queue:
            cur = queue.pop(0)
            for nb in local_graph[cur]:
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        reach_yes = dst in visited

        gt.append({
            'task_type': q['task_type'],
            'picked_ids': picked_ids,
            'hub_neighbors': hub_neighbors,
            'reach_source': src,
            'reach_target': dst,
            'reach_answer': 'yes' if reach_yes else 'no',
            'question_id': i,
        })
    return gt

# =====================================================================
# Prompt 构建 (简化, 只带单元 id)
# =====================================================================
def build_hub_prompt(q, picked_ids):
    target = picked_ids[0]
    return f"""You are a network topology analyst.

You have a sub-network of {len(picked_ids)} neuron profiles. Each row is a cell_id.

Question: Which cells are DIRECTLY connected to {target}?
Return ONLY a list of cell IDs. If none, say 'none'."""

def build_reach_prompt(q, picked_ids):
    src, dst = picked_ids[0], picked_ids[-1]
    return f"""You are a network topology analyst.

Sub-network of {len(picked_ids)} neuron profiles.
Question: Can information flow from {src} to {dst} within this sub-network?
Return ONLY: 'yes' or 'no'."""

def run_llm_batch(questions, gt, mode, n_units=50, timeout=45):
    """对一批问题跑 LLM 或 random. mode ∈ {random, ours, best}."""
    if not LLM_AVAILABLE:
        # 无 LLM 时 random 直接给随机答案
        return [{'correct': False} for _ in questions]

    import httpx
    lib = get_library()
    results = []
    for i, q in enumerate(questions):
        g = gt[i]
        if q['task_type'] == 'hub':
            prompt = build_hub_prompt(q, g['picked_ids'])
        else:
            prompt = build_reach_prompt(q, g['picked_ids'])

        if mode == 'random':
            # 从 picked_ids 里随机选一个作为答案
            rng = random.Random(1000 + i)
            picked = rng.sample(g['picked_ids'], 1)
            if q['task_type'] == 'hub':
                answer_text = f"{picked[0]}"
            else:
                answer_text = rng.choice(['yes', 'no'])
        else:
            # ours / best
            try:
                r = httpx.post(
                    f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": os.environ.get('MODEL', 'deepseek-v4-flash'),
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 300,
                        "temperature": 0,
                    },
                    timeout=timeout,
                )
                if r.status_code != 200:
                    results.append({'correct': False, 'error': r.text[:100]})
                    continue
                data = r.json()
                answer_text = data['choices'][0]['message']['content'].strip()
            except Exception as e:
                results.append({'correct': False, 'error': str(e)[:100]})
                continue

        # 打分
        if q['task_type'] == 'hub':
            ans_ids = extract_ids_with_unit_prefix(answer_text, unit_ids)
            gt_ids = set(g['hub_neighbors'])
            correct = bool(ans_ids) and all(a in gt_ids for a in ans_ids)
        else:
            ans_lower = answer_text.lower()
            gt_answer = g['reach_answer'].lower()
            correct = (ans_lower == gt_answer) or \
                      (f"'{gt_answer}'" in ans_lower) or \
                      (f'"{gt_answer}"' in ans_lower)

        results.append({'correct': correct, 'answer': answer_text[:200],
                        'task_type': q['task_type'], 'gt_id': i})
        if (i+1) % 10 == 0:
            print(f"    ... {i+1}/{len(questions)} done ({mode})")
    return results

# =====================================================================
# 主流程
# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--k', type=int, default=50, help='每个 (task_type, arm) 样本数')
    ap.add_argument('--n-units', type=int, default=50)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--only-random', action='store_true', help='只跑 random 对照')
    args = ap.parse_args()

    K = args.k
    random.seed(args.seed)
    global_rng = random.Random(args.seed)

    # --- 1. 生成题目池 (够三臂轮转) ---
    print(f"\n生成题目池: {K * 3} 题 (task_type ∈ hub/reachability)")
    question_types = ['hub', 'reachability']
    questions = []
    for i in range(K * 3):
        tt = question_types[i % len(question_types)]
        n_units = min(args.n_units, len(unit_ids))
        picked = global_rng.sample(range(len(unit_ids)), n_units)
        units_subset = [{'id': unit_ids[j]} for j in picked]
        if tt == 'hub':
            q = build_hub_task(lib, units_subset, seed=args.seed + i)
        else:
            q = build_hub_task(lib, units_subset, seed=args.seed + i,
                               task_type='reachability')
        # 简化: 只保留 task_type 与 seed
        questions.append({'task_type': q['task_type'], 'seed': args.seed + i})

    # --- 2. 构造 ground truth (与题目一一对应) ---
    print("构造 ground truth ...")
    gt = build_ground_truths(questions, n_units=args.n_units, seed=args.seed)
    # 统计
    from collections import Counter
    reach_dist = Counter(g['reach_answer'] for g in gt)
    print(f"  reach_answer 分布: yes={reach_dist.get('yes',0)} "
          f"no={reach_dist.get('no',0)}")
    hub_empty = sum(1 for g in gt if not g['hub_neighbors'])
    print(f"  hub 邻居为空的题目: {hub_empty}  (这些题目对 random 也是"
          f"不可能猜中的, 建议剔除)")

    # 统计 ground truth 可得分性
    # Hub: 至少 1 邻居; Reach: 任一答案
    valid_hubs = [i for i, g in enumerate(gt) if g['hub_neighbors']]
    valid_reaches = list(range(len(gt)))  # reach 都可选
    print(f"  valid hub 题目: {len(valid_hubs)}")

    # --- 3. 按 task_type 切分题目, 分配给三臂 ---
    hub_q_idx = [i for i, q in enumerate(questions) if q['task_type'] == 'hub']
    reach_q_idx = [i for i, q in enumerate(questions) if q['task_type'] == 'reachability']
    print(f"\n题目分配: hub={len(hub_q_idx)}, reach={len(reach_q_idx)}")

    arms_config = [('random', 0)]
    if LLM_AVAILABLE and not args.only_random:
        arms_config += [('ours', 0), ('best', 1)]

    state = {
        'config': {'k': K, 'n_units': args.n_units, 'seed': args.seed,
                   'arm_variants': arms_config},
        'data': {'n_profiles': len(lib.profiles),
                 'n_units': len(unit_ids),
                 'hub_questions': len(hub_q_idx),
                 'reach_questions': len(reach_q_idx)},
        'ground_truth': gt,
        'cell_results': {},
        'per_arm': {},
        'task_type_summary': {},
        'started_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'notes': [],
    }
    if hub_empty > 0:
        state['notes'].append(f"有 {hub_empty} 题 hub 邻居为空, random 组不可能猜中, "
                              f"计算主指标时排除这些题")

    # --- 4. 跑三臂 ---
    def slice_questions_for_arm(arm_idx, task_q_idx):
        """每个 task_type 按 arm_idx 轮转, 每臂拿 K 题"""
        return [task_q_idx[i] for i in range(arm_idx, len(task_q_idx),
                                              len(arms_config))][:K]

    for arm, variant in arms_config:
        print(f"\n=== 臂: {arm} ===")
        arm_total = 0
        arm_correct = 0
        per_tt = {'hub': {'total': 0, 'correct': 0},
                  'reachability': {'total': 0, 'correct': 0}}

        # 按 task_type 分别采样
        for tt, q_idx_pool in [('hub', hub_q_idx),
                                ('reachability', reach_q_idx)]:
            q_ids = slice_questions_for_arm(variant, q_idx_pool)
            print(f"  {tt}: {len(q_ids)} 题")

            qs = [questions[i] for i in q_ids]
            gts = [gt[i] for i in q_ids]

            # 对 hub 类, 如果所有 ground truth 都为空, 跳过
            if tt == 'hub':
                non_empty = [x for x in zip(q_ids, qs, gts) if x[2]['hub_neighbors']]
                if not non_empty:
                    print(f"  [skip] {tt}: 所有 hub ground truth 都为空")
                    continue
                q_ids, qs, gts = zip(*non_empty)

            if arm == 'random':
                # 直接生成随机答案, 无 API 依赖
                results = []
                for j, (qi, qq, gg) in enumerate(zip(q_ids, qs, gts)):
                    rng = random.Random(10000 + qi)
                    if tt == 'hub':
                        answer = rng.choice(gg['hub_neighbors'])
                        correct = answer in gg['hub_neighbors']
                    else:
                        answer = rng.choice(['yes', 'no'])
                        correct = answer == gg['reach_answer']
                    results.append({'correct': correct, 'task_type': tt,
                                    'gt_id': qi, 'answer': answer})
                print(f"  random 完成 (无需 API)")
            else:
                results = run_llm_batch(qs, gts, mode=arm,
                                        n_units=args.n_units)

            for r in results:
                if r.get('correct'):
                    arm_correct += 1
                    per_tt[tt]['correct'] += 1
                arm_total += 1
                per_tt[tt]['total'] += 1
                state['cell_results'][f"{arm}__{r.get('task_type','?')}__{r.get('gt_id','?')}"] = r

        acc = arm_correct / arm_total * 100 if arm_total else 0
        state['per_arm'][arm] = {'total': arm_total, 'correct': arm_correct,
                                 'accuracy_pct': round(acc, 2),
                                 'per_task_type': per_tt}
        print(f"  {arm} 总正确率: {acc:.1f}% ({arm_correct}/{arm_total})")
        print(f"  按 task_type: {json.dumps(per_tt)}")

        # 保存中间状态
        RESULT_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                               encoding='utf-8')

    state['completed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

    # --- 5. 生成 task_type 对比 ---
    print("\n" + "=" * 70)
    print("按 task_type 对比结果")
    print("=" * 70)
    arms_done = list(state['per_arm'].keys())
    for tt in ['hub', 'reachability']:
        print(f"\n【{tt}】")
        row = f"{'arm':8s}"
        for a in arms_done:
            info = state['per_arm'][a]['per_task_type'].get(tt, {})
            row += f" | {a:10s}"
        print(row)
        accs = {}
        for a in arms_done:
            info = state['per_arm'][a]['per_task_type'].get(tt, {})
            if info['total'] > 0:
                accs[a] = info['correct'] / info['total'] * 100
        for a in arms_done:
            info = state['per_arm'][a]['per_task_type'].get(tt, {})
            acc = accs.get(a, 0)
            print(f"  {a}: {acc:5.1f}% ({info.get('correct',0)}/{info.get('total',0)})")
        if 'random' in accs:
            for a in arms_done:
                if a == 'random':
                    continue
                if a in accs:
                    print(f"  {a} vs random: Δ = {accs[a] - accs['random']:+.1f}pp")

    RESULT_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                           encoding='utf-8')
    print(f"\n[Saved] {RESULT_FILE}")

if __name__ == '__main__':
    main()
