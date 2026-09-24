# Unit Composition Experiment — G1 单元回灌引擎

**版本**：v2.5.0（2026-09-24）
**脚本**：`integrations/swarmlabs/diagnostics/unit_composition_experiment.py`
**产物**：`unit_composition_results.json`

---

## 一、动机

v2.4.0 之前所有 diagnostics 都跑在 `design_organism` 的**模块代表层**
（4-10 个 module_rep，密度 0.002-0.023）。101 个功能单元一直躺在数据
库里，从未参与过 ESN 层实验。PROJECT_VISION.md §4 Phase 3 明确记录：

> 负结果是关于**模块代表层**设计空间的；**cell 级密化（模块内补递归
> 边）后 motif 是否有优势 = 未检验**，是唯一可能翻盘的实验。

本项目一直缺一个「让单元库直接跑 ESN」的入口。G1 = 101 单元回灌引擎
就是第一次尝试。**结果不是「单元库碾压 bio motif」**——诚实结论在下面。

## 二、方法

### 2.1 Unit-composed W 构造

对每个单元：
- `members` 按 `count_ratio` 缩放到 N 个节点
- `internal_wiring` 的每条边按源/目标成员的节点范围做**均匀密块填充**
  （所有对都填原始 weight，不做稀疏采样）
- 保留 feedback/feedforward 权重符号

### 2.2 四臂对照

| Arm | 来源 | 密度 |
|---|---|---|
| A textbook_random | `random_W(N, seed)` 高斯储备池 | 1.000 |
| B bio_motif | `design_organism` module_rep 层 | 0.008 |
| C random_matched | 匹配 bio_motif 边数的稀疏随机 | 0.008 |
| D unit_composed | 本实验新增，逐单元 | 0.21-0.47 |

### 2.3 指标

- **r2_score(delay)**：Bernoulli 延迟线（沿用 `dyn_calibration_probe`）
- **fault_isolation**：模块关停 vs 随机关停降幅对比
- **delay=3,5**：3 在 ESN 舒适区，5 开始逼近能力悬崖

## 三、结果（N=60, 30 seeds）

| 拓扑 | N | 密度 | delay=3 R² | delay=5 R² |
|---|---|---|---|---|
| textbook_random | 60 | 1.000 | **0.999** | 0.868 |
| bio_motif | 65 | 0.008 | 0.427 | 0.002 |
| random_matched | 65 | 0.008 | 0.860 | 0.011 |
| wing_flight_steering | 60 | 0.220 | 0.404 | 0.003 |
| **mushroom_body_LH_reciprocal** | 60 | 0.395 | **0.650** | 0.004 |
| antennal_lobe_CC_feedback | 60 | 0.275 | 0.067 | 0.003 |
| gustatory_centrifugal | 60 | 0.212 | 0.053 | 0.003 |
| **central_complex_steering** | 60 | 0.468 | **0.926** | 0.004 |

**ratio (r2) vs bio_motif**：min=0.12×, max=2.17×, mean=0.98×（n=5）
**unit_composed 胜出**：r2 2/5、success 2/5、fault_isolation 1/5

## 四、诚实结论

### 4.1 单元组合层**没有系统性胜出** bio motif

- 中位数基本持平（mean ratio 0.98×）
- 唯一显著胜出的是 `central_complex_steering_unit`（2.17× bio_motif，
  r2=0.926 逼近 textbook）——该单元的 `internal_wiring` 有 4 条边、
  只有 3 个成员，密度刚好落在 0.468 的 sweet spot
- 其他 4 个单元 1/5 到 1.4× bio_motif，多数持平或更差

### 4.2 「cell 级密化后 motif 是否有优势」的**部分是**

Phase 3 报告的根因是模块代表层密度 0.002-0.023「结构上不足以承载
时间动力学」。本实验单元组合层密度 0.21-0.47（**约 25-60× 更密**），
- **2/5 单元显著优于 bio motif**：说明「更密 → 有优势」的因果链**存在**
- **但优势不是必然**：只有 `central_complex_steering` 拿到高收益，其他
  密集化单元（`wing_flight_steering` 0.220、`antennal_lobe` 0.275）
  并没有赢

### 4.3 delay=5 全线崩塌

bio_motif、random_matched、unit_composed 全部 r2 < 0.01。这不是单元
组合层的问题——textbook_random 也只有 0.868。ESN 延迟线本身在 delay
= 5 已接近能力悬崖，这个任务无法区分拓扑。

### 4.4 未回答的问题

- **单任务局限**：delay 线是记忆类任务，可能不适合评估某些单元
  （`antennal_lobe` 是感知-导航，`gustatory` 是离心反馈，任务错配）
- **无外部基准**：本实验只有内部对照，没有跑标准 ESN benchmark 套件
  （parity、noisy parity、binary addition）——**G2 就是这个**
- **单元×单元组合未测**：本实验只跑单单元。多单元 compose 出来的
  「大器官」拓扑还没试过

## 五、意义

**G1 的价值不是「单元库赢了」，而是「单元库第一次跑在引擎上」**：

1. 建立了 unit-composed W 的构造方式，可复用
2. 证明存在单元（如 central_complex_steering）能逼近 textbook
3. 暴露了 4 类单元的密度不 sweet（wing/antennal/gustatory 都 < 0.5×
   bio_motif）——**这些单元的 internal_wiring 结构需要复核**，是单元库
   自身的可改进点
4. 明确了 G2（外部 benchmark）的必要性

## 六、后续

- **G2**：加标准 ESN 任务套件（parity / noisy-parity / binary addition），
  看单元在不同任务上的表现差异
- **v2.5.1 候选**：把 `internal_wiring` 中权重过小的边（如 0.1）做
  加权密化调整，或加稀疏采样开关
- **v2.5.2 候选**：多单元 compose（`compose_from_units` 已有引擎）后
  的整机拓扑实验

## 七、不宣称

- 不宣称单元组合层「超越生物学」——本实验 5 单元中位数持平 bio motif
- 不宣称计算力优势——delay=5 全线崩，delay=3 里 bio motif 也不赢
- 不宣称结构稳定性优势——fault_isolation 中位数没赢 bio motif

**核心结论**：单元库回灌引擎可行，但需要**任务多样性**和**多单元
组合**才能真正验证单元级结构价值。单单元 × 单任务 × 单 delay 的结论
不能推广到整个库。
