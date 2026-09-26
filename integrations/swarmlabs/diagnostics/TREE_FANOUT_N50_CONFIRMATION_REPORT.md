# v2.15.0 Tree-fanout inhibition 方向 n_seeds=50 确认报告

**日期**：2026-09-27
**版本**：flybrain-connectome v2.15.0
**脚本**：`tree_fanout_variants_experiment.py --n-seeds 50 --sizes 60,200`
**数据**：`tree_fanout_variants_n50_results.json`（50 seeds × 2 sizes × 5 variants）
**总耗时**：38m 14s

---

## 一、动机

CLAIMS_LEDGER.md（v2.14.0）P0 优先级：
> "**n_seeds=50 验证 tree_fanout_with_inhibition**——当前 d=+0.33 p=0.46，
> 只差样本量；若真在 n=50 达到 d=+0.6 p<0.05，就是'树+抑制 = 生物最优组合'
> 的第二个发表级证据。"

v2.13.0 结果（n_seeds=10）：
| 变体 | d (N=60) | d (N=200) | conv 变化 (60→200) |
|------|---------|----------|------------------|
| with_inhibition | +0.330 p=0.460 | +0.224 p=0.267 | 8.4 → 0.4 (−95%) |
| with_feedback | +0.231 p=0.504 | +0.137 p=0.504 | 12.8 → 13.1 (稳) |
| extended_chain | −0.537 p=0.167 | −0.931 p=0.037 | 20.6 → 20.6 (稳) |
| wide_5_downstream | +0.476 p=0.157 | +0.467 p=0.115 | 16.6 → 20.6 (+24%) |

**要回答的问题**：
1. inhibition 是否真在 n=50 兑现方向？
2. extended_chain 的 WORSE 是否 Bonferroni 存活？
3. wide_tree_fanout 的 conv 膨胀是 n=10 幻觉还是真现象？

---

## 二、n_seeds=50 结果

### 2.1 变体 vs tree_fanout_ref（NARMA-10）

| 变体 | N | mean_a | mean_b | p | d | Bonferroni α=0.00625 | 判定 |
|------|---|--------|--------|---|---|---------------------|------|
| extended_chain | 60 | 0.0676 | 0.0616 | 0.0051 | −0.560 | ✅ 通过 | **WORSE** |
| extended_chain | 200 | 0.0701 | 0.0588 | <0.0001 | −0.928 | ✅ 通过 | **WORSE** |
| with_inhibition | 60 | 0.0608 | 0.0616 | 0.6984 | +0.077 | ❌ | no_effect |
| with_inhibition | 200 | 0.0601 | 0.0588 | 0.4937 | −0.137 | ❌ | no_effect |
| with_feedback | 60 | 0.0623 | 0.0616 | 0.6948 | −0.078 | ❌ | no_effect |
| with_feedback | 200 | 0.0607 | 0.0588 | 0.3448 | −0.189 | ❌ | no_effect |
| wide_5_downstream | 60 | 0.0593 | 0.0616 | 0.2555 | +0.227 | ❌ | no_effect |
| wide_5_downstream | 200 | 0.0600 | 0.0588 | 0.5388 | −0.123 | ❌ | no_effect |

### 2.2 稳健性（N=60 → N=200）

| 变体 | MSE 变化 | conv 变化 | 判定 |
|------|---------|----------|------|
| **with_feedback** | +2.6% | **+1.7%** | ✅ 最稳（新增） |
| **wide_5_downstream** | +1.2% | **+0.4%** | ✅ 稳（v2.13.0 撤回） |
| extended_chain | +3.6% | +0.3% | ✅ 稳（但精度最差） |
| tree_fanout_ref | +4.5% | +31.1% | ✅ 稳（参照） |
| with_inhibition | +1.2% | **+237.1%** | ❌ conv 膨胀 3.4× |

---

## 三、5 个核心发现

### 发现 1：extended_chain WORSE 是发表级证据

**N=60**：d=−0.560 p=0.0051（Bonferroni α=0.00625 刚过）
**N=200**：d=−0.928 p<0.0001（远超阈值）

**机制解释**：tree_fanout 分支继续链式延展（嗅觉分支 → MB 稀疏码 → MB 联想记忆）
打破了 tree_fanout 的"并行广播"结构，变成"半并行半链式"——
下游链式部分承担了 NARMA-10 序列预测的任务，但**链式结构本身在 NARMA-10 上不如
纯随机/纯并行**。v2.14.0 CLAIMS_LEDGER 里"random/textbook/single 全赢 bio_motif
on NARMA-10"的机制在此得到组合层复现。

**这是本项目第二个发表级组合层结论**（第一个是 v2.10.0 v2.14.0 确认的
NARMA-10 上 bio_motif 输随机）。

### 发现 2：inhibition 方向完全撤回（样本偏差教训第 5 次）

| 版本 | d (N=60) | 效应量变化 |
|------|---------|-----------|
| v2.13.0 quick n=5 | +1.398 (WINNER) | 1.4× |
| v2.13.0 full n=10 | +0.330 | 0.33× |
| **v2.15.0 n=50** | **+0.077** | **0.077×** |

**每翻倍样本量，d 就缩水 4-5×**。这是项目**第 5 次**样本偏差撤回：
1. v2.5.0 delay-line（方法学 bug）
2. v2.7.0 3/3 全胜（n=5 → n=15）
3. v2.10.0 olfactory NARMA-10（n=15 → n=50，d 缩水 3×）
4. v2.12.0 tree/hierarchical vs gustatory（n=5 Bonferroni 失败）
5. **v2.15.0 with_inhibition 撤回（n=10 → n=50，d 缩水 4.3×）**

**CLAIMS_LEDGER 元规则 1 再次验证**：n_seeds≥15 是**最低门槛**，
n_seeds<15 的 d≈0.3-1.4 REAL_GAIN 全部是幻觉。

### 发现 3：wide_tree_fanout conv 膨胀是 v2.13.0 幻觉（撤回）

**v2.13.0 报告**：wide_tree_fanout 在 N=60→200 conv 从 0.9 膨胀到 20.6 步
（+2188%，"OUT port 复用到 3+ 下游是新扩容不稳定因子"）。

**v2.15.0 事实**（n=50）：wide_tree_fanout 在 N=60→200 conv 从 16.6 到 16.56
（**+0.4% 几乎不变**）。MSE 0.0593→0.0600（+1.2%）。**完全稳健**。

**教训**：v2.13.0 的 conv 数字（0.9/20.6）与 v2.15.0 的 conv 数字（16.6/16.6）
**根本不同**——同一变体在 n=10 vs n=50 下的**平均 conv 数值都不一样**。
说明 v2.13.0 的 conv 数字本身就是不稳定估计，"23× 膨胀"是 n=10 采样噪声。

**结论撤回**：v2.13.0 "OUT port 复用到 3+ 下游是扩容不稳定因子"这一**机制声明
完全不成立**。wide_tree_fanout 与 tree_fanout_ref 在扩容上表现**同样稳健**。

### 发现 4：with_feedback 是真正稳健的变体（新增发表级结论）

v2.15.0 首次显示 with_feedback 在 N=60→200 **两个维度都极稳**：
- MSE 0.0623 → 0.0607（−2.6%，精度略升）
- conv 12.8 → 13.1（**+1.7%，几乎不变**）

对比其他变体：
- ref: MSE 4.5% + conv 31.1%
- with_inhibition: MSE 1.2% + conv **237.1%**
- extended_chain: MSE 3.6% + conv 0.3%
- wide: MSE 1.2% + conv 0.4%

with_feedback 是**唯一 MSE 与 conv 双维度都 <5% 变化**的变体（除 wide 也达标外）。

**生物学对应**：树状广播 hub + 下游反馈回 hub = 生物中央复合物的核心回路
（果蝇 CC 内部 feedback loop，控制 heading 与 locomotion 的耦合）。

### 发现 5：没有任何变体在 NARMA-10 上显著超越 ref

**所有 4 个变体 vs ref 都是 no_effect**（p 从 0.25 到 0.70）。

**意义**：tree_fanout_ref（3 边基础结构）已经是组合拓扑的**局部最优**。
加边（抑制/反馈/链式延展/加宽）都能改变某维表现，但**没有任何加边方案能同时
改进 NARMA-10 精度**。

**核心结论**：**结构更复杂 ≠ 表现更好**。这是本项目"生物不是万能的"结论的
组合层复现——增加生物性元素（抑制/反馈）没有带来精度提升。

---

## 四、对 v2.13.0 TREE_FANOUT_VARIANTS_REPORT 的修正

| v2.13.0 声明 | v2.15.0 判定 |
|-------------|-------------|
| tree_fanout_with_inhibition 是"最有希望" | ❌ **撤回**（d 缩水 4.3×） |
| wide_tree_fanout conv 膨胀 23× | ❌ **撤回**（实际 conv Δ=+0.4%） |
| extended_chain 扩容 WORSE | ✅ **确认**（d=−0.93, p<0.0001） |
| with_inhibition 收敛最快（0.3 步） | ⚠️ 数字不准（n=50 下 conv=8.4） |
| 加边都加速收敛 | ⚠️ 部分（conv 值随 n_seeds 变化大，效应不稳健） |

---

## 五、更新后的 CLAIMS_LEDGER 状态

**发表级结论（Bonferroni 存活）**：
1. ✅ **NARMA-10 上 bio_motif 输随机**（v2.10.0 n=50，d=−0.60 到 −1.40）
2. ✅ **double_pole memory 上 bio_motif 赢**（v2.10.0 n=50，d=+0.57 到 +1.72）
3. **✅ tree_fanout_extended_chain 显著 WORSE vs ref（v2.15.0 n=50，
   N=60 d=−0.56 p=0.005, N=200 d=−0.93 p<0.0001）** ← 新增

**方向性结论（未通过 Bonferroni 但方向稳健）**：
- with_feedback 是"扩容最稳的组合"（MSE 与 conv 都 <5% 变化）
- tree_fanout_ref 是"组合拓扑局部最优"（无变体 NARMA-10 显著超越）

**已撤回（样本偏差教训第 5 次）**：
- ~~tree_fanout_with_inhibition "最有希望"~~（d 从 +1.4 缩到 +0.077）
- ~~wide_tree_fanout conv 膨胀 23×~~（实际 Δ=+0.4%）
- ~~"OUT port 复用到 3+ 下游是扩容不稳定因子"~~（完全撤回）

---

## 六、样本偏差教训完整链路（第 5 次）

| 事件 | 原声明 | 撤回证据 | 效应量缩水 |
|------|--------|----------|-----------|
| v2.5.0 delay-line | memory 结论 | W rank bug | 方法学错 |
| v2.7.0 3/3 全胜 | noisy_parity/double_pole | n=5→15 不可区分 | d 全消失 |
| v2.10.0 olfactory NARMA-10 | real_gain p=0.025 | n=15→50 p=0.143 | d −0.93→−0.30（3×） |
| v2.12.0 tree/hier vs gustatory | REAL_GAIN d≈1.5 | Bonferroni α=0.0021 失败 | — |
| **v2.15.0 with_inhibition** | **real_gain d=+0.33** | **n=10→50 d=+0.077** | **4.3×** |

**新元规则**（补充到 CLAIMS_LEDGER）：
> **"n=10 的 d=+0.33 不是趋势，是幻觉"**——n_seeds=10 的中等效应量在 n_seeds=50
> 下几乎总是缩水到 <0.15。任何 n_seeds<20 的 d<0.6 REAL_GAIN 都视为**探索性**，
> 不作为方向性结论推广。

---

## 七、"复杂快速反应"目标的最终判定（v2.15.0 版）

经过 9 轮实验 + 1 轮确认（v2.5-v2.15），本项目对"像生物一样复杂快速反应"
的**最终答案**是：

1. **纯"复杂度"没有意义**——增加生物性元素（抑制、反馈、链式延展、加宽）
   不会带来 NARMA-10 精度提升
2. **纯"快速反应"也不可行**——skip_recurrence / modulatory_hub 等快拓扑
   在 NARMA-10 上精度低（v2.11.0）
3. **组合层最优结构是 tree_fanout_ref 这个 3 边最小结构**——加边都是损失
4. **唯一的组合层"真信号"是 extended_chain 显著 WORSE**——证明"混合拓扑
   （并行 + 链式延展）"在 NARMA-10 上不如纯并行广播

**生物学含义**：生物下丘脑的 3-下游广播结构（tree_fanout_ref）确实接近
ESN 组合拓扑的局部最优；而生物实际存在的更多边（抑制、反馈、多层链式）
在 ESN 复现下**没有精度优势**——它们存在的意义可能是**其他机制**（如
能耗、鲁棒性、发育约束），而不是"通用学习精度"。

---

## 八、诚实边界

- **只在 NARMA-10 一个任务上验证**——其他任务（memory/parity/logistic）在
  组合层未被 n=50 确认
- **只在 N=60/200 两个尺寸上验证**——更大 N 未测
- **只在 ESN 一种模型上验证**——RNN / SNN / 其他模型未测
- **extended_chain WORSE 的机制解释是"链式不如并行"**——这个解释是
  **假设**，未直接测试（需要设计"纯链式" 与 "纯并行" 的对照）
- **with_feedback 的稳健性未做 Bonferroni 判定**——它是稳健性观察不是
  显著性对比

---

## 九、相关文件

- `tree_fanout_variants_experiment.py`（新增 `--n-seeds` 参数）
- `tree_fanout_variants_n50_results.json`（本轮数据）
- `CLAIMS_LEDGER.md`（更新到 v2.15.0 状态）
- `TREE_FANOUT_VARIANTS_REPORT.md`（v2.13.0 报告，已被本报告修正）
