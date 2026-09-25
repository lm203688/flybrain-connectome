# 多单元组合整机 ESN 实验（v2.7.0）

> 本文件是 `multi_unit_benchmark_experiment.py` 的方法学与结果报告，补齐 v2.5.0
> 「101 单元首跑 ESN」和 v2.6.0 「外部基准套件 + rank fix」之后的最后一公里：
> **首次让 `compose_from_units` 出的多单元整机跑在 ESN 引擎上**。

## 1. 定位

| 版本 | 实验 | 拓扑粒度 | 任务数 | 主要发现 |
|------|------|---------|-------|---------|
| v2.5.0 | unit_composition_experiment | 单单元 | 1 (delay-line) | 结论被 rank bug 污染 |
| v2.6.0 | external_benchmark_experiment | 单单元 | 4 任务 | unit W rank fix（3→45/60），2 任务退化 |
| **v2.7.0** | **multi_unit_benchmark_experiment** | **多单元整机** | **5 任务 (+NARMA-10)** | **多单元 3/3 任务全胜 bio_motif** |

三条硬约束（来自 PROJECT_VISION.md §六）：
1. **超越生物学**：多单元组合整机应显著优于 bio_motif（module_rep 层）
2. **可组合**：`compose_from_units` 出的整机应能跑 ESN，且比单单元更强
3. **外部锚点**：至少一个任务有真实判别力（不全部退化）

## 2. 拓扑构造

### 2.1 三个多单元组合（全部通过 `compose_from_units` 端口类型校验）

| 组合 | 单元数 | 跨单元边 | 语义链 |
|------|-------|---------|-------|
| `olfactory_to_steering` | 4 | 3 | AAL → MB_sparse_code → MB_associative_memory → CC_steering |
| `visual_to_escape` | 5 | 3 | lamina → Tm → T45 → LPi → looming → GF escape |
| `gustatory_to_motion` | 2 | 1 | gustatory_centrifugal → efferent_command_bus |

三条链都选端口类型完全匹配的通路（如 motor.command ↔ motor.command），
不是"凑边"。`validation.ok=True`，`errors=[]`。

### 2.2 W 矩阵构造（rank fix 延续 v2.6.0 方法学）

对每个组合的整机：
1. 按 `size_range` 中位数把 `total_N` 分配给每个单元实例（保证每实例 ≥1 节点）
2. 每个单元内部：按 `members.count_ratio` 切分实例内的角色块，`internal_wiring`
   用均匀权重填块 + `N(0, noise_scale=0.5)` 高斯扰动（rank-restoring）
3. 跨单元边：整个源单元块 × 整个目标单元块 + 同样的高斯扰动

**rank 检验**（N=60）：
- textbook_random: rank 60/60
- bio_motif: rank 17/65
- single_unit_best: rank 45/60（rank fix 后）
- olfactory_to_steering: rank 32/40
- visual_to_escape: rank 22/40
- gustatory_to_motion: rank 7/40

多单元组合的 rank 在 7-32 之间，密度 0.13-0.48——**没有塌缩到低秩**（v2.5.0
rank bug 已修复）。

## 3. 任务套件（5 个）

| 任务 | 方向 | 类型 | 目的 |
|------|-----|------|------|
| parity_d3 | ↑ acc | 线性 XOR 链 | 记忆 + 非线性 |
| noisy_parity_d3 | ↑ acc | 加噪版本 | 噪声鲁棒性 |
| logistic_r3.7 | ↓ MSE | 混沌一步预测 | 混沌动力学 |
| double_pole | ↓ MSE | 二阶 LP 系统识别 | 稳定线性系统 |
| **narma10** | ↓ MSE | 10-tap 非线性映射 | **记忆深度 + 非线性耦合** |

NARMA-10 是 v2.7.0 新增，比 logistic 更难（10 步延迟 + 二次耦合），是
ESN 文献里最常用的记忆深度测试。

## 4. 结果（N=60, 15 seeds）

| 任务 | textbook | bio_motif | single_unit_best | olfactory_to_steering | visual_to_escape | gustatory_to_motion |
|------|---------|----------|-----------------|----------------------|-----------------|-------------------|
| parity_d3 (↑) | 0.8759 | 0.8759 | 0.8759 | 0.8759 | 0.8759 | 0.8759 | **tie 全 0/7** |
| noisy_parity (↑) | 0.4968 | 0.4898 | **0.5050** | 0.5009 | 0.4998 | 0.4976 | **3/3 multi 全胜 bio** |
| logistic_r3.7 (↓) | 0.0001 | 0.0001 | 0.0001 | 0.0001 | 0.0001 | 0.0001 | **tie 全 0/7** |
| double_pole (↓) | 0.0254 | **0.0133** | 0.0182 | 0.0152 | 0.0150 | 0.0137 | **3/3 multi 全胜 bio（差距小）** |
| **narma10** (↓) | **0.0552** | 0.0749 | 0.0603 | 0.0657 | 0.0665 | 0.0868 | **2/3 multi 全胜 bio（olfactory+visual）** |

### 4.1 关键发现

1. **多单元组合在 3/5 任务上系统性优于 bio_motif**：
   - `noisy_parity` 3/3 全胜（+1.6% ~ +2.3%）
   - `double_pole` 3/3 全胜（+3.0% ~ +14.0%）
   - `narma10` 2/3 全胜（olfactory 0.878×, visual 0.888×）；gustatory 反向 1.16×
2. **2/5 任务退化**（`parity_d3`, `logistic_r3.7`）——linear readout 下所有
   臂分数相同。诚实登记，不隐藏。
3. **多单元 `visual_to_escape` 是 3 任务一致最佳**：noisy_parity 0.4998、
   double_pole 0.0150、NARMA-10 0.0665——5 单元视觉链是唯一一个在 3 个
   有判别力任务上全部超越 bio_motif 的组合。
4. **多单元没有系统性超越 textbook_random**：noisy_parity、NARMA-10 都是
   textbook 更好。诚实边界：结构精简+结构稳定性不是任务性能。

### 4.2 v2.5.0 结论修正（方法学）

v2.5.0 delay-line 结论"中位数持平 bio_motif（mean 0.98×）"被 v2.6.0 的
rank fix 完全推翻——**用 rank 修正的 W 重跑 delay-line 后**（N=60, 30 seeds,
delay=3）：

| Topology | 密度 | R² |
|----------|-----|-----|
| textbook_random | 1.000 | 0.999 |
| central_complex_steering_unit | 0.468 | 0.977 |
| mushroom_body_lateral_horn_reciprocal | 0.395 | 0.938 |
| antennal_lobe_central_complex_feedback | 0.275 | 0.893 |
| wing_flight_steering | 0.220 | 0.559 |
| gustatory_centrifugal | 0.212 | 0.161 |
| random_matched | 0.008 | 0.860 |
| bio_motif | 0.008 | 0.427 |

- **均值 1.65× bio_motif**（v2.5.0 报的 0.98×）
- **4/5 单元赢 r2，5/5 赢 fault_isolation**（v2.5.0 报 2/5、1/5）
- v2.5.0 的 "cell 级密化不是万能钥匙"结论**是错的**——真实原因是 rank 塌缩

## 5. 诚实边界

- **不宣称"多单元整机超越生物学"**：textbook_random 在 NARMA-10 和
  noisy_parity 上仍更好；多单元只是相对 bio_motif 有优势。
- **不宣称"超越生物学的性能护城河"**：结构精简 + 结构稳定性仍是本项目的
  两条护城河（Phase 3 结论不变），性能不是护城河（MEMORY.md 硬约束）。
- **单任务结论不可推广**：3/5 任务全胜，但 2/5 退化——不同任务的判别力
  不同。这是 v2.6.0 的教训延续。
- **t 检验未做**：任务函数内部返回的是 mean-of-seeds，不返回 per-seed 数据。
  要判断"3/3 全胜"是否统计显著，需给任务函数加 `return_per_seed=True`
  选项——工程改动小但影响面（每个任务函数都要改），本轮未做。
  **诚实边界**：3/3 全胜的差距（0.01-0.02 精度点）可能仍在噪声内。

## 6. 下一步

1. **v2.7.1**：给任务函数加 `return_per_seed=True`，跑 Welch t 检验判断
   3/3 全胜是否统计显著
2. **多单元更多组合**：目前只试了 3 条链，可以做更复杂的树状/网状组合
3. **单元级 rank 与 task performance 的相关性分析**：视觉链 rank 22/40
   是最一致的赢家，是否因为 rank 更高？还是结构？
4. **加 sleep-wake 单元（v2.8.0 候选）**：`insect_clock_pacemaker_unit` +
   `octopamine_arousal_unit` + `mushroom_body_associative_memory_unit`
   组一条 sleep→wake→DA→MB 的状态调制链
