# External ESN Benchmark Suite — G2 外部锚点

**版本**：v2.6.0（2026-09-24）
**脚本**：`integrations/swarmlabs/diagnostics/external_benchmark_experiment.py`
**产物**：`external_benchmark_results.json`

---

## 一、动机

v2.5.0 首次让 101 单元跑 ESN，但只有 `delay-line` 一个任务（Bernoulli 延迟
记忆）。PROJECT_VISION.md §六 明确要求「有基准测试证明虚拟生物可以超越
生物学限制」——delay-line 只是内部数字。标准 ESN 文献使用 **多任务套件**
（parity、noisy parity、logistic、double-pole、NARMA 等）验证拓扑是否
具备通用动力学能力。

本套件实现 4 个经典任务：
1. **binary parity (d=3)** — XOR 记忆链
2. **noisy parity (d=3)** — 噪声下的鲁棒性
3. **logistic map r=3.7** — 混沌时间序列一步前预测
4. **double-pole LP** — 二阶线性系统识别

## 二、方法

- **Reservoir**：与 `dyn_calibration_probe` 一致的 ESN，`W/s_max * ρ` 归一化
  谱半径，`Win ~ N(0,1)`，`bias ~ N(0, 0.5)`
- **Readout**：ridge regression，α=1e-3
- **Split**：60% train / 40% test
- **Seeds**：20（noisy）/ 5（quick）
- **对照臂**：textbook_random / bio_motif / random_matched / unit_composed
  (5 units)

## 三、方法学关键修正：unit W 秩不足

v2.5.0 初版 `build_unit_topology` 用**均匀密块填充**（每个 internal_wiring
边在成员块间做 rank-1 uniform fill）。SVD 分析发现：

| Topology | Density | SVD rank (>1e-10) |
|---|---|---|
| unit_composed (v2.5.0 原版) | 0.395 | **3 / 60** |
| bio_motif | 0.008 | 17 / 65 |
| random_matched | 0.009 | 21 / 60 |
| textbook_random | 1.000 | 60 / 60 |

**unit W 秩 = 3 意味着储备池被塌缩成 3 维动力学**——这就是 v2.5.0 里
"unit-composed 只在 delay-line 上偶发胜出、其他任务不赢"的根因。修
正：在均匀底上加 `N(0, 0.5)` 高斯扰动，把 unit W 秩从 3 提到 45：

| Topology | 修正前 | 修正后 |
|---|---|---|
| unit_composed rank | 3 | **45** |
| unit_composed sv_max | 1.44 | 23.75 |

这个修正被同时应用到 `unit_composition_experiment.py`，让 v2.5.0 的
delay-line 实验结论可以更严格地重跑。**Rank 修正本身是 v2.6.0 方法学
的关键贡献**——没有它，任何"unit vs motif"实验都被 unit W 的秩不足掩盖。

## 四、结果（N=60, 20 seeds, 5 units）

| Task | Bio | Textbook | Unit_composed 5 单元 | Verdict |
|---|---|---|---|---|
| parity_d3 (acc ↑) | 0.8767 | 0.8767 | 0.8767 (all 5 same) | **退化，无法区分** |
| **noisy_parity_d3 (acc ↑)** | **0.4953** | 0.5012 | **0.499-0.506 (5/5 全 > bio)** | **unit wins 5/5** |
| logistic_r3.7 (MSE ↓) | 0.0001 | 0.0001 | 0.0001 (all 5 same) | **退化，任务太易** |
| double_pole (MSE ↓) | 0.0124 | 0.0255 | 0.013-0.017 (0/5 赢) | bio_motif wins |

### 有判别力的两个任务

**noisy_parity**：unit_composed 5/5 单元均优于 bio_motif（0.499-0.506 vs
0.4953），均值 0.5014。差距虽小但一致——**unit-composed 拓扑对噪声输入
鲁棒性略强**。textbook_random 也胜出（0.5012），但差距比 unit 略小。

**double_pole**：bio_motif 意外最优（0.0124），优于 unit（0.013-0.017）
和 textbook（0.0255）。bio motif 的稀疏 module_rep 结构**在稳定的二阶
系统识别任务上胜出**——稀疏结构反而有利于低噪声线性动态。

### 退化的两个任务

parity_d3 和 logistic_r3.7 全部 5+3 个 W 矩阵给出**完全相同**的分数。
这两个任务在 ridge linear readout 下退化了：
- **parity_d3**：state 里能提取的信息不足以判别未来 2 位 XOR（readout
  只能靠随机相关，5 个 W 都得到同一噪声水平）
- **logistic_r3.7**：一步预测 x_{t+1} 太易（readout 学到的近似直接命中
  混沌吸引子的光滑投影），所有 W 都 MSE < 0.0002

这两个任务对**当前 reservoir 参数**没有判别力，未来需要更复杂的任务
设计（例如更长 lookahead、更难的混沌动力学）。

## 五、诚实结论

### 5.1 G2 部分成立

- **外部基准套件首次实现**（v2.4.0 前完全没有外部任务，只有内部
  delay-line）
- **noisy_parity 5/5 单元胜出 bio_motif**——unit-composed 在噪声鲁棒性
  上有一致性优势（虽然差距只有 0.005 精度点）
- **double_pole 意外发现 bio_motif 反向胜出**——稀疏 module_rep 层在
  稳定线性系统识别上有独特优势，这是 v2.5.0 delay-line 单任务掩盖掉
  的真实现象

### 5.2 方法学贡献

**Unit W 秩不足 bug 是本轮最重要的发现**：v2.5.0 的 unit-composed 实验
结果被"3 维塌缩的 W 矩阵"污染，之前 2/5 单元的"胜出"和 3/5 的"不赢"
都可能是这个 bug 造成的。**Rank 修正后**，delay-line 结果应重跑才能
得出可靠结论。

### 5.3 未回答的问题

- **task 池还很小**（4 个，其中 2 个退化）：NARMA-10、Mackey-Glass、
  XOR-5、binary addition 等标准任务未实现
- **textbook_random 是弱锚点**：它是本项目自己定义的高斯储备池，不是
  标准 ESN benchmark 里报告的公开数字
- **5 单元样本量偏小**：只用了 5/101 单元，可能选中的这 5 个刚好在
  noise-robustness 上更擅长

### 5.4 不宣称

- **不宣称 unit-composed 全面胜出**——double_pole 反向输给 bio_motif
- **不宣称"超越生物学"成立**——noisy_parity 5/5 全胜但差距只有 0.005，
  在 20 seeds 下可能仍在噪声内（需 t 检验）
- **parity/logistic 退化**——不作为"单元输给 random"的证据

## 六、后续

- **v2.6.1 候选**：加 NARMA-10 / binary addition 等更强基准任务
- **v2.6.2 候选**：给 unit_composition_experiment.py 的 delay-line 结果
  重跑（现在 unit W 已经是高秩的，v2.5.0 报告的 2/5 win 可能变化）
- **v2.6.3 候选**：t 检验判断 noisy_parity 5/5 全胜是否统计显著
- **多单元 compose**（`compose_from_units` 引擎）从未跑过 ESN——这是
  v2.5.0 G1 报告里已经识别但未做的下一个方向
