# R1 扩样报告 —— 隔离实验扩到 N≥100

- 生成日期：2026-10-10 09:25 UTC
- 数据集：`isolation_dataset_N100.json`
- 基线：`ISOLATION_PREDICTOR_REPORT.md`（N=27, in-sample R²=0.15）

## 一、方法

- 合成网格：k∈{2..6} × c∈{3..6} × n_inter∈{0,1,2,3,5,8} × densify_fr∈{0.50, 0.75, 1.00} × motif∈{chain, ring, star, random}
- 目标拓扑数：120（实际有效：48）
- 每拓扑 N_SEEDS=30，N_RANDOM=15，与既有实验完全一致
- Held-out 分割：按 label 哈希稳定拆分，避免同拓扑同 seed 跨集
- 特征集：**沿用既有 9 个结构特征**（不引入新变量）
- 判定阈值 ±0.05：与既有实验完全一致

## 二、分类结果（普适性检验）

| 类别 | 数量 | 占比 | 旧基线（N=27）|
|---|---|---|---|
| H1 模块化 | 23 | 47.9% | 25/27 = 92.6% |
| H2 耦合 | 6 | 12.5% | 0/27 = 0% |
| H3 无结构 | 19 | 39.6% | 2/27 = 7.4% |

**判断**：如果 H1 占比与 27 拓扑基本一致（92.6%），说明**『模块化普遍带来故障隔离』**的结论具有普适性；如果显著偏离，说明原结论只在特定结构子集成立。

## 三、结构特征与隔离强度的相关

| 特征 | r（N=48） | 旧（N=27） |
|---|---|---|
| k | +0.000 | +0.131 |
| n | +0.000 | +0.152 |
| density | -0.451 | +0.254 |
| modularity_q | -0.200 | -0.335 |
| spectral_radius | -0.372 | +0.277 |
| intra_inter_ratio | -0.411 | +0.152 |
| mean_intra_density | -0.417 | +0.182 |
| med_size_over_n | +0.000 | +0.149 |
| module_size_cv | +0.000 | +0.000 |

## 四、Held-out 预测性

- 特征：**['density', 'mean_intra_density']**（按 |r| 前 2 名）
- 系数：[0.2947, -4.9544, 1.75469]
- **in-sample R² = 0.3278**
- **held-out R² = 0.1230**
- train acc: 19/33（baseline always-H1: 16/33）
- **test acc: 10/15**（baseline always-H1: 7/15）

**判据**：
- held-out R² 显著大于 0 且 test acc 显著优于 always-H1 → 结构性特征**可预测**隔离程度（推翻旧结论 R²=0.15）
- held-out R² 接近 0 或负，test acc ≈ always-H1 baseline → 结构性特征**不可预测**（确认旧结论 R²=0.15）
- 介于两者 → 需要机制特征（模块-任务对齐度），这正是 I-2 要做的

## 五、诚实边界

1. 合成拓扑是模块化图族的采样，不是真实连接组；用于测试命题普适性，不主张"生物脑一定如此"。
2. `n_inter` 与 `densify_fr` 直接控制结构-任务对齐度，这也是 R1 P2/P3 的机制假说变量；报告里保留了 `params` 字段以便追溯。
3. Held-out 分割按 label 哈希稳定，避免同 seed 同参数跨集造成泄漏；但这仍是"同分布内 held-out"，不是"跨生成方式"的泛化测试。
4. 弱基线（R²<1e-3）被跳过但记录在 `skipped` 字段，可复算。

## 六、复现

```bash
PY="C:/Users/xing/.workbuddy/binaries/python/envs/minimind/Scripts/python.exe"
$PY integrations/swarmlabs/diagnostics/isolation_expander.py           # 全量 120
$PY integrations/swarmlabs/diagnostics/isolation_expander.py --quick   # 40 拓扑
```
