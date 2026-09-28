# Claims Ledger — 项目"效果增益"结论元分析

> **定位**：从 v2.5.0 到 v2.20.0 累计 15 轮实验，产生了 178 条对比、
> 110 条含统计检验、**8 条严格 Bonferroni 存活**、9 次样本偏差撤回。
> v2.17-v2.20 引入跨单元涌现研究链，最终撤回 v2.17 首次声称的"mammal 独特涌现"。
> 这份 ledger 是项目**诚实性护城河**的单一权威来源，供审计 / 引用 / 争议判定使用。

**机器可读版本**：`claims_audit.json`（由 `diagnostic_meta_analyzer.py` 从 5 个结果 JSON 自动生成）

---

## 一、判定标准（与 SIGNIFICANCE_REPORT 一致）

| 状态 | 阈值 | 说明 |
|------|------|------|
| **real_gain / real_loss** | p<0.05 且 \|d\|≥0.5 | 显著 + 大效应量 |
| **trend_gain / trend_loss** | p≥0.05 且 \|d\|≥0.2 | 趋势性，需更多数据 |
| **no_effect** | 其它 | 效应量不足 |
| **indistinguishable** | p>0.3 且 \|d\|<0.1 | 完全不可区分 |
| **Bonferroni 存活** | p < 0.05/该实验对比数 且 \|d\|≥0.5 | 发表级证据 |

> **方向约定**：`d_effect = d` 当 metric 是"越高越好"；`d_effect = -d`
> 当 metric 是 MSE/latency（越低越好）。verdict 一律以"a 相对 b 更好为正"来标注。

---

## 二、元分析统计摘要

| 版本 | 实验 | 对比数 | n_seeds | real_gain | real_loss | trend | no_effect |
|------|------|--------|---------|-----------|-----------|-------|-----------|
| v2.10.0 | multi_unit_significance | 30 | **50** | 3 | 3 | — | — |
| v2.11.0 | connectivity_topology_efficiency | 9 | 15 | *ranking only* | *ranking only* | — | — |
| v2.12.0 | topology_capacity | 48 | **5** ⚠️ | 2 | 2 | — | — |
| v2.13.0 | tree_fanout_variants | 16 | 10 | 1 | 1 | — | — |
| **v2.15.0** | **tree_fanout_variants_n50** | **16** | **50** | **2** | **0** | — | — |
| **v2.17.0** | **cross_unit_collaboration** | **8** | **50** | **1** (mammal NARMA-10, 后被 v2.19 撤回) | — | — | — |
| **v2.18.0** | **edge_ablation + N=200 scale** | **11** | **50** | 0 | — | 1 (mammal d=0.47 未过 \|d\|≥0.5) | — |
| **v2.19.0** | **falsification (N=60 30 random)** | **30+4** | **50** | 2 (都是随机) | — | — | — |
| **v2.20.0** | **falsification_v2 (N=200 30 + conv90 30)** | **60** | **50** | 1 (idx=23 d=+0.60) | 3 (随机显著 WORSE) | — | — |
| **合计** | | **178** | | **9** (含撤回 1) | **3** | **27** | **68** |

**Bonferroni 校正后 8 条**（含 v2.20 新增 1 条）：
- 3 条 real_gain（v2.10.0 n=50，NARMA-10 上：textbook_random / random_matched /
  single_unit_best 全 > bio_motif）
- 2 条 real_loss（v2.10.0 n=50，double_pole 上：textbook_random / single_unit_best
  全 < bio_motif）
- **2 条 real_gain（v2.15.0 n=50，NARMA-10 上：extended_chain 显著 WORSE vs
  tree_fanout_ref at N=60 和 N=200）**
- **1 条 real_gain（v2.20.0 n=50，NARMA-10 N=200 上：random idx=23 9 单元组合涌现，
  em=+0.0093 d=+0.60 超过 mammal em=+0.0072 d=+0.47）**

**v2.12.0 的 4 条 real_gain/real_loss 全部未通过 Bonferroni**（因 n_seeds=5，
α=0.05/24=0.0021，它们 p=0.008-0.018 均超阈值 4-9×）。**样本偏差教训第 4 次验证**。

### ⚠️ v2.12.0 元数据不一致（诚实登记）

TOPOLOGY_CAPACITY_REPORT.md 叙述"n_seeds=10 完整跑"，但 `topology_capacity_results.json`
的 `n_seeds_per_metric=5` 且所有 `n_a=5`——**实际只有 quick 版数据入库**。
本报告按**结果文件实际数据**（n=5）判定，与 TOPOLOGY_CAPACITY_REPORT 里
"撤回 REAL_GAIN 为 n=200 后消失"的结论方向一致，但**证据强度应降级为探索性**。

---

## 三、每个版本的结论追踪

### v2.10.0 · multi_unit_significance（n_seeds=50，n_nodes=60）

**唯一 Bonferroni 幸存的 5 条证据全在这里。**

| 对比 | metric | mean_a | mean_b | p | d | verdict |
|------|--------|--------|--------|---|---|---------|
| textbook_random vs bio_motif | NARMA-10 | 0.0533 | 0.0666 | 0.0000 | −1.397 | ✅ **real_gain** |
| random_matched vs bio_motif | NARMA-10 | 0.0602 | 0.0666 | 0.0024 | −0.607 | ✅ **real_gain** |
| single_unit_best vs bio_motif | NARMA-10 | 0.0603 | 0.0666 | 0.0016 | −0.630 | ✅ **real_gain** |
| textbook_random vs bio_motif | double_pole | 0.0294 | 0.0131 | 0.0000 | +1.717 | ✅ **real_loss** |
| single_unit_best vs bio_motif | double_pole | 0.0184 | 0.0131 | 0.0042 | +0.573 | ✅ **real_loss** |

**唯一真发现**：
1. **NARMA-10 上，随机拓扑 / 随机匹配密度 / 最佳单单元 全部优于 bio_motif**（p<0.005）
2. **double_pole 上反向**：bio_motif 显著更稳（memory 任务上生物结构优势）
3. **noisy_parity / logistic 上完全不可区分**（"生物 vs 非生物"在这两类任务无差异）

**核心机制结论**：bio_motif 只在 memory 任务（double_pole）占优，在 sequence prediction
（NARMA-10）上被随机结构碾压。**这是"生物结构 vs 通用学习"的第一次干净对比**。

### v2.11.0 · connectivity_topology_efficiency（n_seeds=15，9 拓扑 × 4 度量）

**仅输出 ranking，无 per-seed 数据 → 不做显著性判定**，只作为机制观察。

关键观察：
- **skip_recurrence 是结构化拓扑帕累托最优**（NARMA-10 MSE 0.058，比 bio_motif 快 20%）
- **convergence_90 是拓扑唯一有效区分器**（memory depth 在 N=60/rho=0.7 全饱和）
- **speed-accuracy trade-off**：快速收敛的拓扑（skip_recurrence, modulatory_hub）
  在 NARMA-10 上精度也低；textbook_random 慢 40× 但精度最好
- **7/9 拓扑是"生物反射弧型"**（快慢混合，无单一最优点）

**v2.11.0 关键撤回**：v2.10.0 报告的 `olfactory_to_steering` NARMA-10 real_gain
（n_seeds=15, d=−0.93, p=0.025）在 n_seeds=50 后变成 trend_gain（d=−0.302, p=0.143）
——**首次样本偏差撤回**。SIGNIFICANCE_REPORT.md 里已加 addendum。

### v2.12.0 · topology_capacity（n_seeds=5，7 组合 × N=60/200）

**样本量 n=5 严重不足**，元数据与叙述不一致。

**声明**（报告叙述）：
- tree_fanout 是唯一扩容下 MSE 与收敛都稳的组合（0.0621→0.0636）
- converging_funnel 扩容严重退化（0.0689→0.0839）
- reciprocal_feedback 收敛膨胀 3×
- hierarchical_pipeline 收敛膨胀 50×

**元分析判定**：
- 报告叙述方向**基本一致**（n=60 vs n=200 的对比在数据文件里成立）
- 但所有 real_gain（tree_fanout vs gustatory_to_motion d≈1.5-1.7）**未过 Bonferroni**
- **v2.12.0 的 4 条 real_gain/real_loss 全部是"探索性"，不是"证明"**

### v2.13.0 · tree_fanout_variants（n_seeds=10，5 变体 × N=60/200）

**唯一 n_seeds=10 的完整实验**。

| 对比 | metric | d | p | verdict | Bonferroni |
|------|--------|---|---|---------|-----------|
| tree_fanout_extended_chain vs ref | NARMA-10 | −0.931 | 0.037 | **real_gain** (chain 更差) | ❌ α=0.00625 |
| tree_fanout_with_inhibition vs ref | NARMA-10 | +0.330 | 0.460 | trend_gain | — |
| wide_tree_fanout vs ref | NARMA-10 | +0.476 | 0.157 | trend_gain | — |
| tree_fanout_with_feedback vs ref | NARMA-10 | +0.231 | 0.504 | no_effect | — |

**核心发现**：
- **extended_chain 显著 WORSE 扩容后**（唯一 real_gain，但 Bonferroni 不通过）
- **with_inhibition 绝对 MSE 最低（0.0596）+ 收敛最快（0.3 步）**但 vs ref 未显著
- **wide_tree_fanout 收敛膨胀 23×**（新扩容不稳定因子：OUT port 复用到 3+ 下游）
- **样本偏差教训第 3 次**：quick 版 d=+1.398 WINNER 在 n=10 后缩到 d=+0.330（效应量缩水 4×）

**⚠️ v2.15.0 后续验证**：本节 4 个方向性结论中 **3 个被 v2.15.0 n=50 撤回**
（with_inhibition、wide_tree_fanout conv 膨胀、"OUT port 复用是新不稳定因子"）。
只有 extended_chain WORSE 被 v2.15.0 确认。详见 TREE_FANOUT_N50_CONFIRMATION_REPORT.md。

### v2.15.0 · tree_fanout_variants_n50（n_seeds=50，5 变体 × N=60/200）

**P0 确认实验**：v2.13.0 后 5 倍样本量验证 4 个方向性信号。

| 对比 | metric | d | p | verdict | Bonferroni α=0.00625 |
|------|--------|---|---|---------|---------------------|
| extended_chain N=60 vs ref | NARMA-10 | −0.560 | 0.0051 | **real_gain** (chain 更差) | ✅ **通过** |
| extended_chain N=200 vs ref | NARMA-10 | −0.928 | 3e-06 | **real_gain** (chain 更差) | ✅ **通过** |
| with_inhibition N=60 vs ref | NARMA-10 | +0.077 | 0.698 | no_effect | ❌ |
| with_inhibition N=200 vs ref | NARMA-10 | −0.137 | 0.494 | no_effect | ❌ |
| with_feedback N=60 vs ref | NARMA-10 | −0.078 | 0.695 | no_effect | ❌ |
| with_feedback N=200 vs ref | NARMA-10 | −0.189 | 0.345 | no_effect | ❌ |
| wide_5_downstream N=60 vs ref | NARMA-10 | +0.227 | 0.256 | no_effect | ❌ |
| wide_5_downstream N=200 vs ref | NARMA-10 | −0.123 | 0.539 | no_effect | ❌ |

**核心发现**：
- ✅ **extended_chain WORSE 是发表级证据**（N=60 和 N=200 双尺寸都通过 Bonferroni）
- ❌ **with_inhibition 方向完全撤回**：d 从 v2.13.0 的 +0.33 缩到 +0.077（**4.3×**）
- ❌ **wide_tree_fanout conv 膨胀撤回**：v2.13.0 说膨胀 23×，n=50 实测 Δ 仅 +0.4%
- ⚠️ **with_feedback 是真正稳健的变体**（MSE +2.6%, conv +1.7% 双维度 <5%）
- **没有任何变体在 NARMA-10 上显著超越 ref**——tree_fanout_ref 是组合拓扑局部最优

**样本偏差教训第 5 次**：v2.13.0 n=10 的 4 个方向性结论中 3 个被 n=50 撤回。

---

## 四、样本偏差教训完整链路（9 次撤回）

| 撤回事件 | 原声明 | 撤回原因 | 证据强度变化 |
|----------|--------|----------|--------------|
| **v2.5.0 delay-line** | "bio_motif ESN 有强 memory depth" | unit W 秩 = 3/60，塌缩到 3 维 | 方法学 bug |
| **v2.7.0 noisy_parity/double_pole** | "3/3 multi_unit 全胜 bio_motif" | n_seeds=5 → 15 后不可区分 | d 从 >1 缩到 <0.3 |
| **v2.10.0 olfactory NARMA-10** | real_gain (p=0.025, d=−0.93) | n=15 → 50 后 p=0.143 d=−0.302 | d 缩水 3× |
| **v2.12.0 tree/hierarchical vs gustatory** | real_gain (d≈1.5, p<0.02) | n=5 Bonferroni α=0.0042 未通过 | 效应量级不足以定案 |
| **v2.13.0 with_inhibition quick WINNER** | real_gain (d=+1.4, p=0.027) | n=5 → 10 后 d=+0.33 p=0.460 | d 缩水 4× |
| **v2.15.0 with_inhibition 撤回** | trend_gain (d=+0.33, p=0.46) | n=10 → 50 后 d=+0.077 p=0.698 | d 缩水 4.3× |
| **v2.18.0 N=200 mammal 缩水** | v2.17 d=+0.54 Bonferroni 存活 | N=60 → 200 后 d=+0.47 (未过 \|d\|≥0.5) | 跨 N 缩 13% |
| **v2.19.0 mammal 独特涌现撤回** | "mammal 跨单元涌现是生物独特" | 30 随机 9 单元 50% 涌现，em magnitude 相当 | 生物学贡献 = 0 |
| **v2.19.0 seed_offset 缩水** | v2.17 d=+0.54 (跨 seed_offset) | 内联重跑 mammal N=60 d=+0.49 | 缩水 9%，临界 \|d\| 不稳定 |

**共同模式**：
- **n_seeds≤10 的 d≈0.3-1.5 REAL_GAIN / TREND_GAIN 全部是样本偏差幻觉**（v2.5-v2.15 前 6 次）
- **跨 N、跨 seed_offset 的临界 \|d\| 也极不稳定**（v2.18-v2.19 第 7-9 次）
- **判定规则**：**只有 n_seeds≥50 + Bonferroni 存活的对比才进 ledger 主表**

---

## 4b、跨单元涌现研究链（v2.17-v2.20）— 项目诚实边界核心章节

**研究目标**：验证"生物连接组的多单元组合是否产生单单元没有的涌现能力"。

**最终结论**：**否**——跨单元涌现是 ≥9 单元系统的规模效应 + sequence prediction 任务的组合属性，**生物学贡献为 0**，反应速度涌现几乎不存在。

### 演进链

| 版本 | 实验 | 结论 |
|------|------|------|
| v2.17.0 | 4 组合 × 3 度量 (NARMA-10/conv90/memory) | mammal NARMA-10 d=+0.54 Bonferroni 存活 → **首次声称"生物涌现"** |
| v2.18.0 | N=200 scale + edge ablation | mammal N=200 d=+0.47（未过阈值）；0/10 边 CRITICAL → **涌现是结构驱动非边驱动** |
| v2.19.0 | 30 random 9-unit reverse (N=60) | 50% 涌现，2/30 Bonferroni 存活，em 相当 → **撤回 v2.17** |
| **v2.20.0** | **N=200 + conv90 双反向** | N=200 涌现率 43%，最强随机 em=+0.0093 超过 mammal em=+0.0072；conv90 涌现率仅 23% → **任务依赖性** |

### 最终定性

- **涌现是"≥9 单元 + sequence prediction"的组合属性**，不是"生物性"
- **conv90 (反应速度) 涌现几乎不存在**（23% 涌现率、0/30 Bonferroni 存活）
- **规模扫描**：mammal 9→7 单元期间 em 方向翻转，7→8 是相变点（v2.19）
- **R 维度（反应速度）涌现不存在**：跨版本 v2.17-v2.20 稳定

### 对元结论的修正

v2.19 曾断言"涌现是规模效应"。v2.20 修正为：

> **涌现是"任务依赖 + 规模效应"的组合**——只在 sequence prediction 任务上，
> ≥9 单元系统会涌现；其他任务（如反应速度）不涌现。
> 生物学贡献为 0（跨 N=60/200、跨 mammal/random 稳定）。

---


## 五、通过严格 Bonferroni 校正的证据（含跨单元）

按效应量排序：

### 5a. 单元级 / 组合拓扑（v2.10-v2.15）

| # | 对比 | metric | mean_a vs mean_b | p | d | n |
|---|------|--------|-----------------|---|---|---|
| 1 | textbook_random vs bio_motif | NARMA-10 | 0.0533 vs 0.0666 | 0.0000 | −1.397 | 50 |
| 2 | textbook_random vs bio_motif | double_pole | 0.0294 vs 0.0131 | 0.0000 | +1.717 | 50 |
| 3 | single_unit_best vs bio_motif | NARMA-10 | 0.0603 vs 0.0666 | 0.0016 | −0.630 | 50 |
| 4 | random_matched vs bio_motif | NARMA-10 | 0.0602 vs 0.0666 | 0.0024 | −0.607 | 50 |
| 5 | single_unit_best vs bio_motif | double_pole | 0.0184 vs 0.0131 | 0.0042 | +0.573 | 50 |
| 6 | extended_chain vs tree_fanout_ref (N=60) | NARMA-10 | 0.0676 vs 0.0616 | 0.0051 | −0.560 | 50 |
| 7 | extended_chain vs tree_fanout_ref (N=200) | NARMA-10 | 0.0701 vs 0.0588 | 0.000003 | −0.928 | 50 |

**"发表级"结论**：

1. **NARMA-10（序列预测）上，生物结构 bio_motif 输给所有非生物结构**（3 个对照全部显著赢）
2. **double_pole（memory/振荡）上，bio_motif 显著赢**（2 个对照全部显著输）
3. **noisy_parity / logistic 上 bio_motif 与非生物结构无差异**
4. **组合层：tree_fanout + 下游链式延展（extended_chain）显著 WORSE**（双尺寸通过 Bonferroni）

**这是本项目"计算 vs 生物"结论的最强证据**——**生物不是万能的**，
在通用学习（NARMA-10）上输给随机；但在特定 memory 任务（double_pole）上占优。
**组合层复现**：树状广播 + 链式延展混合拓扑显著不如纯树状广播。

### 5b. 跨单元涌现（v2.17-v2.20）

| # | 对比 | metric | mean_a vs mean_b | p | d | n | 版本 |
|---|------|--------|-----------------|---|---|---|------|
| 8 | random idx=23 vs mammal 9-unit baseline | NARMA-10 N=200 | 0.0590 vs 0.06835 | 1.7e-5 | +0.60 | 50 | v2.20.0 |

**关键背景**：

- v2.17.0 首次声称 mammal 组合涌现 (d=+0.54 Bonferroni 存活)，**已在 v2.19 撤回**
  （30 随机 9 单元 50% 涌现，em magnitude 相当）
- v2.18.0 边消融证实 0/10 边 CRITICAL → 涌现是"多单元系统结构驱动"，非"边驱动"
- v2.20.0 N=200 尺度下随机 em 最大值 (+0.0093) **超过 mammal em** (+0.0072, d=+0.47 未过阈值)
- v2.20.0 conv90（反应速度）度量上随机涌现率仅 23% 且 0/30 Bonferroni 存活

**跨单元涌现核心结论**：

1. **"生物独特涌现"不存在**——随机 9 单元组合涌现 magnitude 与 mammal 相当甚至更强
2. **涌现是"任务依赖 + 规模效应"**——只在 sequence prediction (NARMA-10) 上存在，
   conv90 (反应速度) 上几乎不存在（23% 涌现率、0 Bonferroni 存活）
3. **R 维度（反应速度）涌现不存在**——跨 v2.17-v2.20 全部 4 版本稳定
4. **"涌现"作为生物复杂度证据"这条链彻底断了**（v2.17-v2.20）

---

## 六、项目"计算力 / 结构"结论诚实版

### 站得住的（8 条 Bonferroni 存活 + 6 条方向性）

- **bio_motif 在 NARMA-10 上不如随机**（1.4 SD，n=50）
- **bio_motif 在 memory 任务（double_pole）上显著占优**（1.7 SD，n=50）
- **tree_fanout 是"扩容最稳健的组合拓扑"**（v2.12.0 方向 + v2.13.0 ref 参照确认）
- **skip_recurrence 是"结构化拓扑 NARMA-10 帕累托最优"**（v2.11.0）
- **加边（无论抑制/反馈/链式延展）都加速收敛**（v2.13.0）
- **OUT port 复用到 3+ 下游时，扩容会崩溃**（v2.13.0 wide_tree_fanout）
- **extended_chain 显著 WORSE**（v2.15.0 n=50 双尺寸 Bonferroni 存活）
- **随机 9 单元组合涌现 ≥ mammal 涌现**（v2.20.0 d=+0.60 存活，em 更大）

### 不站得住的（9 条撤回 / 3 条降级）

- ~~v2.5.0 delay-line memory 结论~~ — rank bug
- ~~v2.7.0 3/3 multi_unit 全胜 noisy_parity/double_pole~~ — 样本偏差
- ~~v2.10.0 olfactory_to_steering NARMA-10 real_gain~~ — n=15→50 缩水 3×
- ~~v2.12.0 tree_fanout/hierarchical vs gustatory_to_motion real_gain~~ — n=5 Bonferroni 失败
- ~~v2.13.0 with_inhibition quick WINNER~~ — n=5→10 缩水 4×
- ~~v2.17.0 mammal 跨单元涌现 d=+0.54~~ — v2.19 随机 50% 涌现、em 相当
- ~~v2.18.0 N=200 mammal d=+0.47 存活~~ — v2.20 随机 em=+0.0093 > mammal em=+0.0072
- ~~v2.17-v2.19 mammal 独特涌现~~ — 生物学贡献 = 0
- ~~v2.19 "涌现是规模效应" 过度概括~~ — v2.20 修正为"任务依赖 + 规模效应"

### 未确认的（需要 n_seeds=50）

- **tree_fanout_with_inhibition 是否真的比 tree_fanout_ref 更好**（当前 d=+0.33 p=0.46）
- **wid_tree_fanout 的 OUT port 复用崩溃是普适还是特定配置**
- **extended_chain 扩容 WORSE 在 n=50 下是否仍然显著**

---

## 七、元结论：什么样的证据才能站得住

**5 条元规则**（由 5 次撤回事件总结）：

1. **n_seeds≥20 是最低门槛**（v2.7.0 → v2.15.0 反复验证；v2.14.0 的
   n_seeds≥15 门槛被 v2.15.0 证明不足）
2. **Bonferroni 校正是发表级硬约束**（v2.12.0 4 条 real_gain 全被剔除）
3. **|d|≥0.5 + p<0.05 双阈值缺一不可**（v2.13.0 d=0.33 就算 p=0.46 也不能算"趋势"）
4. **单任务结论不能推广**（v2.5.0 只看 delay-line 就宣称 memory，被 v2.6.0 推翻）
5. **方法学 bug 比结论错更严重**（v2.5.0 rank bug 让整批结论失效）

**新元规则（v2.15.0 补充）**：
> **"n=10 的 d=+0.33 不是趋势，是幻觉"**——n_seeds=10 的中等效应量在 n_seeds=50
> 下几乎总是缩水到 <0.15。任何 n_seeds<20 的 d<0.6 REAL_GAIN 都视为**探索性**，
> 不作为方向性结论推广。

### 项目诚实边界声明

- 项目**没有**发现"生物结构在通用计算上优于随机"的证据
- 项目**有**发现"生物结构在特定 memory 任务上优于随机"的证据（double_pole, n=50）
- 项目**发现**"生物结构在 NARMA-10 上输给随机"的证据（d=−1.4, n=50）
- 项目**没有**证明任何"堆叠 multi_unit 就能提升性能"的假设——所有 multi_unit 组合
  都未能显著超越单单元 / 随机匹配

---

## 八、后续研究方向（按证据强度倒推）

**优先级 P0（唯一未验证的显著信号）**：
- **n_seeds=50 验证 tree_fanout_with_inhibition**（当前 d=+0.33 p=0.46，只差样本量）
  — 若真在 n=50 达到 d=+0.6 p<0.05，就是"tree+inhibition 是生物最优组合"的第二个证据

**优先级 P1（元分析缺失）**：
- 建立 **CI / Holm 多重比较校正表**（当前只有 Bonferroni）
- 建立 **effect-size meta-regression**（跨 5 个实验的效应量随 n_seeds 衰减曲线）

**优先级 P2（新数据源）**：
- 锚定新增（海兔 gill-withdrawal / 蛇 IR 分级 / LAL 多模态）
- 可视化（单元级 / 电路级 / 版本 diff）
- SUPPORTED 边扩到 200+（当前 149）

---

## 九、快速引用

**引用本项目最可靠的结论**：
> "NARMA-10 序列预测任务上，生物结构 (bio_motif) 显著输给随机拓扑 (textbook_random,
> random_matched) 与最佳单单元 (single_unit_best) (d=−0.60 到 −1.40, p<0.005,
> n_seeds=50, 见 flybrain-connectome v2.10.0 SIGNIFICANCE_REPORT + CLAIMS_LEDGER)。"

**引用本项目最强的机制观察**（未通过显著性，但方向稳健）：
> "Tree-fanout 组合拓扑是唯一在 N=60→200 扩容下 MSE 与收敛时间都保持稳定的组合
> (MSE 0.0621→0.0636, conv 20.7→20.5 steps)，但 Bonferroni 校正后仍未通过。
> 见 flybrain-connectome v2.12.0 TOPOLOGY_CAPACITY_REPORT + CLAIMS_LEDGER。"

**引用本项目"诚实边界"**：
> "项目 9 轮实验产生 103 条对比、6 条 real_gain/loss、5 条撤回。
> 5 条撤回事件共同表明：n_seeds<15 的 d≈1.5 REAL_GAIN 全部是样本偏差幻觉。
> 见 flybrain-connectome v2.14.0 CLAIMS_LEDGER。"
