#!/usr/bin/env python3
"""独立复核：P1 per-cell task effect（按 task_type 拆分，验证 motif_family 单类效应）

背景：
- p1_experiment_result.md 声称 P1 相对 Baseline +33.4pp，方向反转（0/7 → 0/1）
- 但报告没有按 task_type 拆分；state.json 有 per-cell task_type 字段
- 若效应集中在单一 task_type（尤其 motif_family），说明机制归因未成立
"""
import json, statistics
from pathlib import Path
from collections import defaultdict

STATE = Path("C:/Users/xing/Desktop/flybrain-connectome/_p1_full/state.json")
data = json.loads(STATE.read_text(encoding="utf-8"))

cells = data.get("cells", []) or data.get("pilot", {}).get("cells", [])
print(f"cells: {len(cells)}")
print(f"keys per cell: {sorted(cells[0].keys()) if cells else 'none'}")

# group by (condition, task_type)
groups = defaultdict(list)
for c in cells:
    cond = c.get("condition")
    tt = c.get("task_type")
    score = c.get("score", c.get("accuracy", 0))
    if cond and tt is not None and score is not None:
        groups[(cond, tt)].append(float(score))

task_types = sorted({tt for (_, tt) in groups.keys()})
conditions = sorted({cond for (cond, _) in groups.keys()})
print(f"conditions: {conditions}")
print(f"task_types: {task_types}")
print()

# Table: per task_type, per condition mean score, delta P1 - Baseline
print(f"{'task_type':<20} {'cells_total':<12} {'mean_P1':<10} {'mean_Base':<10} {'delta_pp':<10} {'n_P1':<6} {'n_Base':<6}")
print("-" * 90)
total_p1, total_base = [], []
for tt in task_types:
    p1_scores = groups.get(("P1", tt), [])
    base_scores = groups.get(("Baseline", tt), groups.get(("baseline", tt), []))
    total_p1 += p1_scores
    total_base += base_scores
    m_p1 = statistics.mean(p1_scores) * 100 if p1_scores else 0
    m_base = statistics.mean(base_scores) * 100 if base_scores else 0
    print(f"{tt:<20} {len(p1_scores)+len(base_scores):<12} {m_p1:<10.2f} {m_base:<10.2f} {(m_p1-m_base):+8.2f}   {len(p1_scores):<6} {len(base_scores):<6}")

print("-" * 90)
m_p1_all = statistics.mean(total_p1) * 100 if total_p1 else 0
m_base_all = statistics.mean(total_base) * 100 if total_base else 0
print(f"{'TOTAL':<20} {len(total_p1)+len(total_base):<12} {m_p1_all:<10.2f} {m_base_all:<10.2f} {(m_p1_all-m_base_all):+8.2f}   {len(total_p1):<6} {len(total_base):<6}")

# Concentration analysis: which task_type contributes most to the delta?
print("\n--- 效应集中度分析（各 task_type 贡献占比）---")
delta_total = 0
contributions = []
for tt in task_types:
    p1s = groups.get(("P1", tt), [])
    bs = groups.get(("Baseline", tt), groups.get(("baseline", tt), []))
    if p1s and bs:
        d = statistics.mean(p1s) - statistics.mean(bs)
        # weighted by sample count
        weight = (len(p1s) + len(bs)) / (len(total_p1) + len(total_base))
        contrib = d * weight * 100
        contributions.append((tt, contrib, d, len(p1s)+len(bs)))
        delta_total += contrib

contributions.sort(key=lambda x: abs(x[1]), reverse=True)
print(f"总 delta = {delta_total:+.2f}pp")
for tt, contrib, d, n in contributions:
    pct = (abs(contrib)/abs(delta_total)*100) if delta_total else 0
    print(f"  {tt:<20} contrib={contrib:+.2f}pp ({pct:.1f}% of total), per-task delta={d*100:+.2f}pp, n={n}")

# Check if motif_family alone accounts for the majority
motif_contrib = next((c for c in contributions if c[0] == "motif_family"), (0,))
if len(motif_contrib) >= 2 and delta_total:
    pct = abs(motif_contrib[1])/abs(delta_total)*100
    print(f"\n>>> motif_family 单独贡献: {pct:.1f}%")
    if pct > 70:
        print(">>> 结论：效应高度集中在 motif_family 单一任务类型 → 机制归因不成立，需按 task_type 拆分报告")
    else:
        print(">>> 效应分布相对均衡，机制归因初步成立")
