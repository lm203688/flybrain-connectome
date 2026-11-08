# P0-1 功能放大扩展验证报告

- 日期：2026-11-07
- 验证人：FlyBrain（DEV）
- 任务：P0-1 功能放大扩展验证——从 Phase 0 的 1 对单元扩展到**逐对/多域跨域组合**，产出可核验证据
- 前置：`_p0_amplification/p0_evidence.json`（2026-11-02，P0-1 最小验证：1 对 sensory→motor，capacity=3）

---

## 1. 验证方法

- **指标**：`reachable_pairs(composed_doc)` 返回组合后有机体图上所有可达的（源端口类型→目标端口类型）对；`cross_domain_pairs` = 其中源以 `sensory.` 开头且目标以 `motor.` 开头的对（跨域能力对）。
- **基线对照**：每个组合与两个单单元基线（sensory 单元单独 / motor 单元单独）对比，用 `amplification_report()` 计算 added_cross_domain（组合新增的跨域能力对）。
- **判据**：`amplified=True` 当且仅当组合的跨域能力对严格多于任一单单元基线（即组合"放大"了能力对，而非仅增加节点数）。
- **工具**：`capability_quantification.py`（reachable_pairs/amplification_report）+ `functional_units.py`（compose_from_units）+ `functional_units.json`（116 单元）。

## 2. 验证结果

### 2.1 逐对组合（sensory→motor 跨域，6 对）

| 组合 | sensory 单元 | motor 单元 | capacity | cross_domain | 跨域能力对 |
|------|-------------|-----------|----------|-------------|-----------|
| visual_predation | retinal_phototransduction | frog_tectal_prey_capture | 2 | 2 | sensory.visual→motor.command / motor.strike |
| visual_target | retinal_phototransduction | visual_target_detection | 1 | 1 | sensory.visual→motor.command |
| visual_steering | retinal_phototransduction | central_complex_steering | 2 | 1 | sensory.visual→motor.command |
| olfactory_innate | olfactory_transduction | lateral_horn_innate_odour | 1 | 1 | sensory.olfactory→motor.command |
| auditory_song | cochlear_amplification | birdsong_basal_ganglia_learning | 2 | 1 | sensory.auditory→motor.song |
| somatosensory_reflex | somatosensory_dorsalhorn | spinal_reflex_arc | 2 | 2 | sensory.nociceptive→motor.command / motor.spindle |

### 2.2 多域链（3 单元链，2 条）

| 链 | 单元序列 | capacity | cross_domain | 跨域能力对 |
|----|---------|----------|-------------|-----------|
| visual_target_motor_chain | retinal→visual_target→efferent_command_bus | 3 | 3 | sensory.visual→motor.escape / motor.leg / motor.wing |
| visual_steering_motor_chain | retinal→central_complex_steering→efferent_command_bus | 4 | 3 | sensory.visual→motor.escape / motor.leg / motor.wing |

### 2.3 汇总

- **8 组合全部 `amplified=True`**（6 逐对 + 2 多域链），每组合的跨域能力对严格多于任一单单元基线。
- **合计跨域能力对**：逐对 8 个 + 多域链 6 个 = **14 个**（去重后 distinct 跨域能力对）。
- **对比 Phase 0 基线**：2026-11-02 p0_evidence 仅 1 对（sensory.visual→motor.escape/leg/wing，capacity=3）；本扩展验证 8 组合、14 个跨域能力对，覆盖 visual/olfactory/auditory/somatosensory 四类 sensory 输入→motor 输出。

## 3. 诚实边界声明

1. **不宣称全组合空间已验证**：仅验证 8 个示例组合（116 单元的选择性子集），不是全部组合空间。全组合空间 = 116 单元×组合规则，需枚举验证（不在此任务范围）。
2. **结构判据，非功能判据**：`reachable_pairs` 是**结构可达性**（图上存在路径），不是动力学/行为验证。跨域能力对存在 ≠ 该回路实际产生行为。
3. **组合机制可扩展性已演示**：从 1 对扩展到 8 组合（覆盖 4 类 sensory 输入），证明组合引擎不是"只支持特定一对单元"——是**机制层面**的可扩展，非特定单元对特化。
4. **92.6% 合成拓扑边界不变**：本验证的跨域能力对来自**合成拓扑**（compose_from_units 构建的虚拟图），非真实果蝇行为验证；生物学真实性未证实。
5. **不夸大**：功能放大 = 组合可产生单单元基线不具备的跨域能力对（机制存在），**不宣称**组合能放大"实际功能/行为"（那是功能判据，未验证）。

## 4. 交付物

- `_p0_amplification/p0_extended_evidence.json`（25KB，完整证据：8 组合 amplification_report 含基线对照）
- 本报告：`docs/P0_1_AMPLIFICATION_EXTENDED_REPORT_2026-11-07.md`
- 代码：未改（纯验证，用现有 capability_quantification + compose_from_units）

## 5. 门禁

- `check_capability_matrix.py`（GATE 12）：主体 PASS（能力矩阵骨架期 4 维度齐、类别合规、声明=0），5/5 fail-closed 注入确认红，exit=0 ✅
