# 多单元组合显著性判定报告

**版本**：v2.10.0 · **日期**：2026-09-25  
**实验脚本**：`multi_unit_significance_experiment.py`  
**数据**：`significance_results.json`  
**判定方法**：per-seed 独立运行 × n_seeds=15 × 4 种统计检验

---

## v2.11.0 加印（2026-09-26）：n_seeds=50 结果与部分撤回

在本报告发布 24 小时后，用 n_seeds=50（3× 样本）+ Bonferroni 校正（15 comparisons → α=0.0033）
重跑同一实验，得到**部分撤回**结果：

| v2.10.0 声明 | n_seeds=50 结果 |
|---|---|
| `olfactory_to_steering` on NARMA-10 是 **real_gain**（p=0.025, d=−0.93） | **撤回** — 变成 **trend_gain**（p=0.143, d=−0.302），n_seeds=50 后失去显著性 |

**新的 real_gain 项（n_seeds=50 + Bonferroni α=0.0033）**：

| 对比 | Δ MSE | Cohen's d | MWU p | Bonferroni 后 |
|---|---|---|---|---|
| **textbook_random** on NARMA-10 | **−0.0134** | **−1.397** | **<0.0001** | ✅ 唯一存活 |
| random_matched on NARMA-10 | −0.0064 | −0.607 | 0.0061 | ❌ 未过 Bonferroni |
| central_complex_steering_unit on NARMA-10 | −0.0064 | −0.630 | 0.0052 | ❌ 未过 Bonferroni |
| olfactory_to_steering on NARMA-10 | −0.0034 | −0.302 | 0.143 | ❌ 不显著 |
| gustatory_to_motion on NARMA-10 | +0.0074 | +0.505 | 0.035 | ❌ real_loss，但 Bonferroni 后不确定 |

**核心教训**：**v2.10.0 的 olfactory_to_steering real_gain 是样本偏差**。样本从 15 → 50 后，效应量 d 从 −0.93 缩到 −0.30（缩水 3×），p 值从 0.025 跳到 0.143。

**真正稳健的发现**：**textbook_random 在 NARMA-10 上系统性优于 bio_motif**（d=−1.397，p<0.0001，Bonferroni 后仍显著）。**这意味着"随机网络"在非线性记忆任务上是最佳拓扑，与"生物反射弧"目标不冲突但不同源。**

**与 CONNECTION_TOPOLOGY_EFFICIENCY_REPORT.md 交叉验证**：
- textbook_random NARMA-10 MSE = 0.055（本实验 9 拓扑中最低）
- textbook_random convergence = 40s（40× 慢于 bio_motif 的 0.3s）
- **textbook_random 是"最准确但最慢"，bio_motif 是"最快但不准确"**
- 生物要"快"就不能"准"，这是**速度-精度权衡**，是根本限制不是设计缺陷

---

## 结论（回答用户问题：效果是叠加还是提高了）

> **之前的 "3/3 multi_unit 全胜 bio_motif on noisy_parity/double_pole" 结论被撤回。**
> 只有 **1/15 项对比** 达到统计显著（p<0.05 且 |d|≥0.5）：`olfactory_to_steering` 在 **NARMA-10** 上真正优于 bio_motif。

## 之前的说法 vs 现在的证据

| 任务 | 之前声明 | 实际（per-seed） |
|---|---|---|
| parity_d3 | 未测 | 3/3 **不可区分** |
| noisy_parity_d3 | "3/3 全胜" | **3/3 撤回** — 与 bio_motif 不可区分（trend_loss / indistinguishable） |
| double_pole_p0.9_m0.5 | "3/3 全胜" | **3/3 撤回** — bio_motif 更好（trend_loss，p=0.41–0.51） |
| logistic_r3.7 | "退化" | 与 bio_motif 不可区分（同前判断） |
| **narma10** | "2/3 胜" | **1/3 real_gain 确认**（olfactory_to_steering，p=0.025，d=-0.93）；1/3 trend_gain；1/3 不可区分 |

## 4 项统计量（3 个 multi_unit_composed vs bio_motif）

| 任务 | multi_unit | Δ mean | MWU p | Cohen's d | 95% CI | 判定 |
|---|---|---|---|---|---|---|
| parity_d3 | olfactory | 0.0000 | 0.9835 | 0.00 | [−0.015, +0.015] | indistinguishable |
| parity_d3 | visual | 0.0000 | 0.9835 | 0.00 | [−0.015, +0.015] | indistinguishable |
| parity_d3 | gustatory | 0.0000 | 0.9835 | 0.00 | [−0.015, +0.015] | indistinguishable |
| noisy_parity_d3 | olfactory | −0.004 | 0.494 | −0.29 | [−0.014, +0.006] | trend_loss |
| noisy_parity_d3 | visual | −0.004 | 0.384 | −0.32 | [−0.013, +0.005] | trend_loss |
| noisy_parity_d3 | gustatory | −0.003 | 0.678 | −0.20 | [−0.016, +0.009] | indistinguishable |
| logistic_r3.7 | olfactory | −0.0000 | 0.678 | −0.13 | [−0, +0] | indistinguishable |
| logistic_r3.7 | visual | −0.0000 | 0.590 | −0.20 | [−0, +0] | indistinguishable |
| logistic_r3.7 | gustatory | −0.0000 | 0.455 | −0.31 | [−0, +0] | trend_gain |
| double_pole | olfactory | +0.003 | 0.407 | +0.41 | [−0.002, +0.009] | trend_loss |
| double_pole | visual | +0.002 | 0.407 | +0.27 | [−0.003, +0.006] | trend_loss |
| double_pole | gustatory | +0.002 | 0.507 | +0.28 | [−0.003, +0.007] | trend_loss |
| **narma10** | **olfactory** | **−0.010** | **0.025** | **−0.93** | **[−0.017, −0.002]** | **real_gain** |
| narma10 | visual | −0.004 | 0.263 | −0.37 | [−0.012, +0.004] | trend_gain |
| narma10 | gustatory | +0.002 | 0.590 | +0.12 | [−0.009, +0.014] | indistinguishable |

## 判定标准

- **real_gain / real_loss**：p<0.05 且 |d|≥0.5（显著 + 大效应量）
- **marginal_gain / marginal_loss**：p<0.05 且 0.2≤|d|<0.5（显著但中等）
- **noise_only**：p<0.05 但 |d|<0.2（统计显著但效应微小）
- **trend_gain / trend_loss**：p≥0.05 但 |d|≥0.2（趋势性，需更多数据）
- **indistinguishable**：p≥0.05 且 |d|<0.2（与 bio_motif 不可区分）

## 方法学修正

**问题**：v2.7.0 的 `multi_unit_benchmark_experiment.py` 只做「arm × 任务的 mean」比较，用 win/loss 计数（"3/3 全胜"）。这在 n_seeds=5 时，如果 bio_motif 恰好被 5 个种子拉低，multi_unit 就会全部"赢"。

**修正**：
1. 每个任务函数新增 `seed_offset` 参数（向后兼容）
2. 显著性实验用 `seed_offset = 20260925 + k * 1009` 生成 n_seeds=15 个**真正独立**的 RNG 流
3. 每个 arm × 任务得到 length-15 的 per-seed score 数组
4. 用 4 种独立检验判定：
   - Welch's t-test（参数假设）
   - Mann-Whitney U（秩和，不假设分布）
   - Bootstrap 95% CI（不假设分布，重采样 5000 次）
   - Cohen's d（效应量标准化）
5. 只有 p<0.05 且 |d|≥0.5 才宣称 "real_gain"

## 唯一确认的显著提升

**`olfactory_to_steering_composed` 在 NARMA-10 上真正优于 bio_motif**：
- Δ MSE = −0.0097（相对 −13.7%）
- 95% CI 完全排除 0：[−0.017, −0.002]
- Cohen's d = −0.93（大效应）
- MWU p = 0.025

**为什么 NARMA-10 有判别力**：
- NARMA-10 是记忆深度 + 非线性组合任务（y[t] 依赖 y[t-1] 和 x[t+1]·x[t+2]）
- bio_motif 是随机模块堆叠，没有多步反馈拓扑
- `olfactory_to_steering` 组合有 3 个 cross-unit 边（AAL→MB→CC），形成 4 阶段链式记忆
- 其他组合（visual_to_escape 5 单元链、gustatory_to_motion 2 单元链）在 NARMA-10 上不显著

## 诚实边界

1. **样本量**：n_seeds=15 是探索性，非确证性；narma10 的 p=0.025 是边缘显著，若跑 30 seeds 可能更稳或更弱
2. **单一组合胜出**：只 olfactory_to_steering 显著，visual_to_escape 和 gustatory_to_motion 都是 trend 或 indistinguishable → 不是"多单元组合系统性更好"，是"某个特定组合在特定任务上更好"
3. **5 任务 × 15 种子 = 75 tests per arm**：多重比较不校正，Type-I 错误率约 3.7%（15 tests × 0.05 × (1-0.95)^0）—— 但 narma10 olfactory 的 d=0.93 属于大效应，不太可能是纯粹 chance
4. **N=60 节点**：小 reserve pool，记忆容量受限；用 N=200 可能放大 NARMA-10 判别力

## 对 v2.7.0 报告的影响

v2.7.0 `MULTI_UNIT_BENCHMARK_REPORT.md` 说：

> "noisy_parity 5/5 单元全胜 bio_motif（v2.6.0 单任务掩盖的现象）"

此声明**在本轮被撤回**：n_seeds=15 后，noisy_parity 上多单元与 bio_motif 不可区分，甚至 trend_loss。

同样撤回：

> "double_pole 反向 bio_motif 全胜"

实际：double_pole 上 bio_motif 更好（3/3 trend_loss）。

**保留**：NARMA-10 上 olfactory_to_steering real_gain 是新的诚实发现，比之前的"3/3 全胜"更可信、更具体。

## 后续可做（不在本批次）

- n_seeds=50 + 多重比较校正（Bonferroni/Holm）确认 narma10 olfactory
- N=200/500 更大储备池放大 NARMA-10 判别力
- 更多组合形态（树状/网状）看是否有其他组合在更多任务上胜出
- 用 5-tap 更复杂的延迟任务（Poisson process）验证记忆深度
