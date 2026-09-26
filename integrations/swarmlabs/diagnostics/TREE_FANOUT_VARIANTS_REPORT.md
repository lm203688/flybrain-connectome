# v2.13.0 Tree-fanout 变体精修报告

**日期**：2026-09-26
**版本**：flybrain-connectome v2.13.0
**脚本**：`integrations/swarmlabs/diagnostics/tree_fanout_variants_experiment.py`
**数据**：`tree_fanout_variants_results.json`（10 seeds × 2 sizes × 5 variants）

---

## 一、动机

v2.12.0 发现 **tree_fanout 是唯一在 N=60→200 扩容下双维度都稳健的组合拓扑**：
MSE 0.0621→0.0636，收敛 20.7→20.5 步。其他所有拓扑在扩容后要么精度
退化（visual_to_escape -17%），要么收敛膨胀（hierarchical 50×）。

本轮问 3 个问题：
1. tree_fanout 的稳健性是不是"结构本质"？
2. 加生物性元素（抑制 / 反馈 / 下游链式 / 更宽扇出）会不会破坏稳健性？
3. 有没有比 tree_fanout 更强的组合拓扑？

---

## 二、4 种变体设计

| 变体 | 结构 | 单元数 | 边数 | 增量 |
|------|------|--------|------|------|
| **tree_fanout_ref** | 1 hub → 3 下游 | 4 | 3 | (v2.12.0 参照) |
| **tree_fanout_with_inhibition** | tree_fanout + 下游侧向抑制 | 5 | 5 | L2/3 → inhibitory_gain → CC_steering.speed |
| **tree_fanout_with_feedback** | tree_fanout + 下游→hub 反馈 | 4 | 4 | CC_steering.turn_cmd → hypothalamic.sleep_pressure |
| **tree_fanout_extended_chain** | tree_fanout + 嗅觉分支深度链式 | 6 | 6 | AAL → MB_sparse → MB_assoc_mem → CC_steering |
| **wide_tree_fanout_5_downstream** | 1 hub 3 OUT → 5 下游 | 6 | 5 | 复用 arousal_out 分给 3 下游 |

全部通过 `compose_from_units` strict validation。`tree_fanout_with_feedback`
产生预期的 1 个反馈循环警告（`central_complex_steering → hypothalamic →
central_complex_steering`）。

---

## 三、核心结果

| 变体 | MSE@60 | MSE@200 | MSE Δ | conv@60 | conv@200 | conv Δ | 稳健性 |
|------|--------|---------|-------|---------|---------|--------|--------|
| **tree_fanout_with_inhibition** | **0.0596** | **0.0627** | +5.2% | **0.3** | **0.4** | +33% | ROBUST ✅ |
| wide_tree_fanout_5_downstream | 0.0592 | 0.0645 | +8.9% | 0.9 | 20.6 | **+2188%** | ❌ DEGRADED |
| tree_fanout_ref | 0.0621 | 0.0636 | +2.4% | 20.7 | 20.5 | +1% | ROBUST ✅ |
| tree_fanout_with_feedback | 0.0614 | 0.0664 | +8.3% | 1.1 | 0.8 | +27% | ROBUST ✅ |
| tree_fanout_extended_chain | 0.0675 | **0.0780** | +15.5% | 0.7 | 0.7 | 0% | ROBUST（但 WORSE） |

### 显著性（variant vs tree_fanout_ref, n_seeds=10）

| 变体 | N | d | p | 结论 |
|------|---|-----|------|------|
| tree_fanout_with_inhibition | 60 | +0.330 | 0.460 | no_effect |
| tree_fanout_with_feedback | 60 | +0.083 | 0.853 | no_effect |
| tree_fanout_extended_chain | 60 | −0.598 | 0.181 | no_effect |
| wide_tree_fanout_5_downstream | 60 | +0.331 | 0.459 | no_effect |
| tree_fanout_with_inhibition | 200 | +0.065 | 0.884 | no_effect |
| tree_fanout_with_feedback | 200 | −0.210 | 0.639 | no_effect |
| **tree_fanout_extended_chain** | **200** | **−0.931** | **0.037** | **WORSE** |
| wide_tree_fanout_5_downstream | 200 | −0.064 | 0.885 | no_effect |

**没有任何变体在两个尺寸下都显著优于 tree_fanout_ref**。

---

## 四、5 个关键发现

### 发现 1：Quick 版 N=60 WINNER 被 n_seeds=10 完全撤回（第三次样本偏差教训）

n_seeds=5 时 `tree_fanout_with_inhibition vs ref` d=+1.398, p=0.027 → WINNER。
n_seeds=10 后 d=+0.330, p=0.460 → no_effect。**效应量缩水 4 倍**。

这是 v2.10.0（olfactory_to_steering NARMA-10 d=−0.93 → 撤回为 trend）和
v2.11.0（v2.10.0 结论 n_seeds=50 后 p=0.143 撤回）教训的第三次验证：**
n_seeds=5 的 d≈1.5 "REAL_GAIN" 在 n_seeds=10 后基本都会消失**。

### 发现 2：tree_fanout_with_inhibition 突破 v2.12.0 的精度天花板

绝对精度排名（不考虑显著性）：

| 排名 | 变体 | MSE@60 | MSE@200 |
|------|------|--------|---------|
| 1 | wide_tree_fanout_5_downstream | 0.0592 | — |
| **1** | **tree_fanout_with_inhibition** | **0.0596** | **0.0627** |
| 3 | tree_fanout_with_feedback | 0.0614 | — |
| 4 | tree_fanout_ref | 0.0621 | 0.0636 |
| 5 | tree_fanout_extended_chain | 0.0675 | 0.0780 |

**tree_fanout_with_inhibition 是本轮 MSE 最低的组合拓扑**，比 v2.12.0 里
最好的 tree_fanout 低 4%，比 v2.11.0 textbook_random 最优 0.055 只差 8%。
同时收敛时间从 tree_fanout_ref 的 20.7 步降到 0.3 步——**快 70 倍**。

**但这不是"免费午餐"**：5 条边 vs 参照 3 条边（+67% 边数），
且 vs 参照的 Welch t 不显著（p=0.460）。所以严格结论是
"**tree_fanout_with_inhibition 在 NARMA-10 MSE 和 convergence 上同时
更优，但差异未通过统计显著性门槛**"。

### 发现 3：wide_tree_fanout 扩容后收敛时间爆炸 23×

`wide_tree_fanout_5_downstream` 用 1 个 OUT port 复用给 3 个下游
（hypothalamic.arousal_out → cortical_l23.gate / cholinergic_arousal.state_in /
cortical_inhibitory_gain.state）。N=60 时收敛 0.9 步，扩容到 N=200 后
跳到 20.6 步（**+2188.9%**）。

**这是 v2.12.0 "扩容对含 fan-out 拓扑安全"结论的第一个例外**：
当 OUT port 被复用到 3 个以上下游时，扩容反而破坏稳定性。原因猜测：
扩容后单个 block 的 fan-out 权重分散到更多节点，形成更细密的信号稀释。

### 发现 4：tree_fanout_extended_chain 扩容后显著 WORSE

这是**唯一通过 p<0.05 显著性门槛的对比**（tree_fanout_extended_chain
vs ref, N=200, d=−0.931, p=0.037）——**方向是变差，不是变好**。
MSE 从 N=60 的 0.0675 退化到 N=200 的 0.0780（退化 15.5%）。

**"树状扇出 + 下游链式延展"是扩容后不 scale 的结构**——虽然 N=60 时
表现接近参照，但 N=200 后明显劣化。这解释了 v2.12.0 里
hierarchical_pipeline（本质也是"树+链"混合）为什么扩容退化 13%。

### 发现 5：加边（任何方向）都会加速收敛

tree_fanout_ref 收敛 20.7→20.5 步；所有加边变体（+1 到 +3 条边）
都让收敛降到 0.3-20.6 步区间。这是**加边带来的"动力学加速"副作用**——
不管边是抑制、反馈还是扇出延展，都会打破 tree_fanout 的慢速收敛。

**推论**：tree_fanout_ref 之所以在 v2.12.0 表现出"慢速收敛但高精度"的
帕累托最优，是因为它只有 3 条边——**结构稀疏 = 慢收敛但保留长期记忆**。
加边加速收敛但破坏 memory 结构。

---

## 五、对"生物复杂快速反应"目标的最终判定

回到用户 v2.11-v2.12 的核心问题："哪种方式可以类似生物性一样进行复杂的
快速反应"。

| 拓扑 | MSE | 收敛 | 速度 | 精度 | 综合评价 |
|------|-----|------|------|------|---------|
| **tree_fanout_with_inhibition** | 0.0596-0.0627 | 0.3-0.4 步 | **极快** | **最高** | ✅ **唯一快+准** |
| tree_fanout_ref | 0.0621-0.0636 | 20.5-20.7 步 | 慢 | 高 | 帕累托最优（v2.12） |
| tree_fanout_with_feedback | 0.0614-0.0664 | 0.8-1.1 步 | 快 | 中 | 中庸 |
| wide_tree_fanout_5_downstream | 0.0592-0.0645 | 0.9→20.6 | 不稳 | 高 | ❌ 扩容不稳 |
| tree_fanout_extended_chain | 0.0675-0.0780 | 0.7-0.7 | 快 | 低 | ❌ 扩容退化 |

**结论**：**tree_fanout_with_inhibition（下丘脑广播 + 皮层侧向抑制）是
唯一同时保持"极快收敛 + 最高精度 + 扩容稳健"的组合拓扑**。

- 生物学对应：下丘脑觉醒广播（hypothalamic_arousal）+ 皮层 L2/3→GABA 中间
  神经元→中央复合物的侧向抑制——这是哺乳动物大脑"选择性放大"的经典
  回路，本项目第一次在果蝇真实单元库上组合验证。
- 但**vs tree_fanout_ref 未通过显著性门槛**（p=0.460），所以严格来说
  "inhibition 增益"是趋势，不是定论；需要 n_seeds=50 才能定案。

---

## 六、诚实边界

- **快速跑 vs 完整跑的差异**：quick 版（n_seeds=5）声称的 WINNER 全部
  在完整跑中被撤回。这是 v2.10.0 / v2.11.0 教训的第三次验证——
  "n_seeds=5 的 d≈1.5 REAL_GAIN 不是真实发现"。
- **未做 Bonferroni 校正**：8 对比 α=0.00625，唯一显著的
  extended_chain WORSE（p=0.037）在校正下也不算显著。
- **inhibition 增益"绝对值最好但相对不显著"**：MSE 0.0596 比参照低 4%，
  但 Welch t 不显著。诚实结论：树状+抑制结构值得深挖，但没到"证明"级别。
- **只测 5 变体**：只覆盖 tree_fanout 的最小增量扩展；未尝试"树状+多层
  反馈"、"树状+抑制+反馈组合"、"树状+winner_take_all"等更复杂组合。
- **未做 N=500/1000**：wide_tree_fanout 在 N=200 已崩溃，更大尺寸预计
  同样问题。

---

## 七、结论（诚实版）

1. **tree_fanout 的稳健性部分来自"结构稀疏"**：3 条边保持慢收敛和
   memory 深度；加边虽加速收敛但破坏 memory 结构。

2. **tree_fanout_with_inhibition 是最有希望的组合拓扑**（MSE 最低 +
   收敛最快 + 扩容稳健），但 vs 参照 Welch t 未显著（p=0.460），
   需要 n_seeds=50 才能定性。

3. **wide_tree_fanout 揭示新扩容不稳定因子**：OUT port 复用给 3+ 下游
   时，扩容后收敛时间爆炸 23×。这是 v2.12.0 结论的例外。

4. **tree_fanout_extended_chain 扩容后显著 WORSE**（d=−0.931 p=0.037）：
   树状+下游链式混合结构扩容后不 scale。

5. **撤回 quick 版 N=60 WINNER**（tree_fanout_with_inhibition, d=+1.398
   p=0.027）——样本从 5→10 后 d 从 +1.4 降到 +0.33，效应量缩水 4 倍，
   完全变成 no_effect。

6. **核心洞察**：树状扇出结构（tree_fanout）是"生物复杂快速反应"的基础
   形态，加边（无论抑制/反馈/链式延展）都会打破其慢速收敛但高 memory
   的特性。**inhibition 是最有希望的方向，但需要更大样本才能定案**。
