# flybrain-connectome 项目目标

**版本**：1.0
**日期**：2026-09-18
**状态**：核心目标文件，后续所有项目推进以此为目标审核基础

---

## 一、项目愿景

**虚拟生物形态生成器**——用生物学的模式库 + 计算机的优化自由度，创造生物学不可能达到的虚拟生物形态。

生物学是"被锁死的版本"（受限于进化，只能优化生存），计算机可以"自由组合 + 持续优化"（可优化任何目标，可跨物种组合，可热更新）。虚拟生物不是复制生物学，而是**用生物学的模式库 + 计算机的优化自由度，创造生物学不可能达到的形态**。

---

## 二、核心定位

| 维度 | 定位 |
|---|---|
| **核心主张** | 虚拟生物形态生成器 |
| **差异化** | LangGraph/AutoGen/CrewAI 无法"进化"的虚拟生物 |
| **价值主张** | motif 可追溯（W3C PROV 标准）+ 结构精简 + 模块级故障隔离 + 局部可决策（计算力/能耗优势已实测为负，不宣称） |
| **目标用户** | AI 研究员 + 复杂系统工程师 + 科研人员 |
| **商业化路径** | 开发者工具（卖给 AI 研究员，¥100-1000/月） |

### 与生物学的关系

- **生物学**：模式库来源（124,177,617 突触 / 166,700 神经元的真实连接组）
- **计算机**：优化自由度（无限堆叠、跨物种组合、热更新、版本升级）
- **虚拟生物**：生物学模式库 + 计算机优化自由度 = 可追溯 + 结构更精简 + **模块级故障隔离**的虚拟形态
- **三个维度对比**：
  - ✅ 结构精简：GA 自由优化 -84% 线成本（Phase 3 实测）
  - ✅ 结构稳定性：6/7 拓扑模块级故障隔离（Phase 3.5 实测，生物学未证实）
  - ✅ 可追溯性：motif provenance（LangGraph/AutoGen/CrewAI 结构上做不到）
  - ❌ 计算力：已实测为负（0/7 优于随机），不宣称

---

## 三、核心优势（vs 生物学）

| 维度 | 生物学 | 虚拟生物 | 优势方 |
|---|---|---|---|
| 模块来源 | 进化积累（数百万年） | 人类设计（可快速迭代） | 虚拟生物 |
| 堆叠深度 | 受限于生物体规模 | 无限（虚拟空间） | 虚拟生物 |
| 优化自由度 | 只能优化生存 | 可优化任何目标 | 虚拟生物 |
| 跨物种组合 | 不可能 | 可组合不同物种的模块 | 虚拟生物 |
| 版本升级 | 不可能 | 可热更新、可回滚 | 虚拟生物 |
| 生物学先验 | 内置（但无法修改） | 可作为可选模块 | 虚拟生物 |

---

## 四、发展路径（4 阶段）

### Phase 1：模块库扩展（1-2 个月）
- 4 模块 → **10+ 模块**
  - 现有：sensory / memory / motor / integration
  - 新增：attention / working_memory / reward / punishment / habit / metacognition / ...
- 每个模块有 capability profile（能做什么、不能做什么）
- 模块可堆叠（深度组合，不只是 a+b）
- **验证目标**：模块堆叠是否真的能产生"超越生物学"的效果

### Phase 2：蓝图库扩展（2-3 个月） ✅ 已完成（2026-09-18）
- 12 蓝图 → **22 蓝图**（5 basic + 13 biological + 4 synthetic）
  - 6 个新生物 motif 蓝图（均追溯到 MaleCNS v1.0 真实 motif）：
    `hierarchical_deep`(reservoir_smallworld) / `predictive_coding_v2`(recurrent_feedback+reward) /
    `reward_gated_selection` / `punishment_suppression` / `metacognitive_control`(inhibitory_hub) /
    `habit_consolidation`(recurrent_feedback)
  - 4 个合成编排蓝图（基于 10 模块人工编排，诚实标记 `motif=none`）：
    `rl_actor_critic` / `curiosity_driven` / `cognitive_control` / `multi_motif_blend`
  - 新蓝图充分利用 Phase 1 的 reward/punishment/habit/metacognition 模块
- ✅ 嵌套组合 `a+(b+c)` 已实现（解析器 `_normalize_blueprint_spec`，与平铺 `a+b+c` 同构）
- ✅ 每个蓝图均有 provenance（`BLUEPRINT_SOURCE_MOTIF` 全覆盖，无 unknown）
- ⚠️ 诚实边界：本阶段只扩展"设计空间"（蓝图/模块），未改变 SwarmLabs 引擎对拓扑不响应的事实；
  "超越生物学"的实证仍留给 Phase 3 的进化速度指标

### Phase 3：自动优化（2026-09-18 已执行 + 复核，**判定未达标**）
- 遗传算法在「10 模块 × 22 蓝图」空间自动搜索最优形态 ✅ 已实现
- 进化速度指标（决策 2）对照随机搜索基线 ✅ 已执行（8 seeds × 960 评估，同等预算）
- **结果**：
  - 架构约束下（与生物学先验同物种）：**随机搜索 8/8 seeds 严格优于 GA**（+29% 适应度）
  - 放开架构约束后：GA 8/8 seeds 收敛到 9–11 边最小形态（随机搜索 7/8 落在 18–43 边），
    线成本较锁定形态 −84%（57→9）——**"超越生物学"在结构精简维度成立**
  - 动态适应度：初判"无判别力"经复核**是标定错误**（任务取在能力悬崖外 + 列归一化抹掉谱半径 ρ +
    读出器欠定），修正后有真实动态范围（delay=5 时 R² 从 0.064 平滑升到 0.874）
  - **计算力优势已实测为负**：匹配控制实验（同 N、同非零数 K、种子平均 30）下，
    **生物 motif 0/7 拓扑优于随机结构**（差值 0.001–0.071，全在噪声内，4/7 反而更差）
- 复核诊断套件：`integrations/swarmlabs/diagnostics/dyn_calibration_probe.py`（`--quick` 1.5s）
- 详见 `integrations/swarmlabs/GA_PHASE3_REPORT.md`（§5.1 标定纠正 / §5.2 匹配控制 / §六 判定）
- **结论**：按降级路径收口——定位收敛为「可追溯的虚拟生物形态生成器」，
  差异化 = motif 溯源 + 结构精简，**不宣称计算力优势**（已实测为负，不是"未验证"）
- **根因与未检验方向**：flybrain 边只连 `module_rep`，密度 0.002–0.023，结构上不足以承载
  时间动力学（ESN 需 ~0.1+）。负结果是关于**模块代表层**设计空间的；
  **cell 级密化（模块内补递归边）后 motif 是否有优势 = 未检验**，是唯一可能翻盘的实验

### Phase 3.5：模块故障隔离（2026-09-18 执行 + 扩样，**新主张成立**）
- 实验目标：检验合成模块化拓扑能否做到生物学至今未证实的"模块级故障隔离"
  （Friston 2008 modularity of brain 争议的核心问题）
- 方法：ESN + 线性读出器 + delay=5，关停一个完整模块 vs 随机关停等量节点
- **结果（首轮 7 拓扑）**：
  - **6/7 拓扑表现为 H1 模块化**：模块关停降幅显著小于随机关停降幅
    （效应量 13-24 个百分点，远大于噪声）
  - **5/7 拓扑关停后谱半径 ρ 几乎不变**（0.00%）
- **结果（扩样至 27 拓扑，25 蓝图 + 2 GA 产物 + 2 bench）**：
  - **25/27 拓扑（92.6%）H1 模块化**——模块化隔离是**普遍结构属性**，不是巧合
  - 效应量中位 Δ 28 pp（最大 39.7 pp，最小 6.8 pp）
  - 25/27 拓扑谱半径 ρ 保持 0.00%–0.30%
  - 唯一两个例外都是极端样本：ga_locked（11 模块密度 0.039 过稀疏）
    与 evolved_target200（2 模块密度 0.323 无内部结构）
- 文献佐证：Friston 2008 争议至今未定论；生物学界有 double dissociation 证据
  （Geddes 2014 / Glenberg 2014 / Campanella 2022 / Vaidya PNAS 2010）但**未量化**
  "整个大脑模块隔离的比例"——本项目首次给出量化对照（92.6%）
- 详见：
  - `integrations/swarmlabs/diagnostics/FAULT_ISOLATION_REPORT.md`（F1-F5 完整报告）
  - `integrations/swarmlabs/diagnostics/f1_ext_full.out`（27 拓扑扩样原始输出）
  - `integrations/swarmlabs/DIRECTION_FEASIBILITY.md`（方向可行性 + 分阶段路线）
- 脚本：`integrations/swarmlabs/diagnostics/fault_isolation_experiment.py`（--quick 5.9s / 全量 20.8s）
- **结论**：**"超越生物学"在结构稳定性维度成立**——这是生物学至今未**系统量化**的能力

### Phase 4：三条护城河深化（2026-09-19 完成）
- **可追溯 v2**：schema v1.2.0 三段溯源（stage1 神经元锚点 / stage2 突触统计 / stage3 可运行查询）
- **精简 v2**：GA 稳定性适应度（STABILITY_WEIGHT=0.5, TARGET=0.30），ratio 从 0.42 降到 0.32
- **稳定性 v2**：3 个新稳定性蓝图 + _verify.py 集成稳定性检查
- **可追溯 v2.1**：W3C PROV-JSON 标准化（via dataprov），EU AI Act 合规硬门槛
  - schema v1.2.1 新增 `prov_json` 字段（W3C PROV-JSON bundle，via dataprov）
  - 可被任何 W3C PROV 标准工具摄入（yProv4ML, MLflow2PROV, MIT Sloan Data Provenance Explorer, PROV-O SPARQL）
  - `_verify.py` 70/70 全通过（含 8 条 PROV-JSON 校验）
- 产物：`generated_organisms/swarmlabs/sample_prov_v1.2.1.json`（6.7KB PROV-JSON bundle）

### Phase 5：打开未测维度（2026-09-19 完成）
- **能耗维度（Phase 5.1）**：SNN 模拟器 + 6 拓扑 × 4 delay = 24 run，H1 命中 **0/24 (0%)**
  - 拓扑结构对能耗影响很小（±5% 范围），冗余/分层蓝图略节能但精度也略低
  - **诚实结论**：能耗维度实测为负，不宣称能耗优势
  - 产物：`diagnostics/snn_energy_experiment.py` + `SNN_ENERGY_REPORT.md`
- **无意识决策维度（Phase 5.2）**：多读出实验 7 拓扑 × 4 delay = 28 run，H1 命中 **5/28 (17.9%)**
  - 层级/预测编码/冗余蓝图在简单任务（delay≤2）上模块能独立支持子任务
  - 模块独立读出能**超越**中央读出（比值最高 1.59×）
  - **诚实边界**：H1 只在 delay≤2 出现，不是真正的复杂无意识决策
  - 产物：`diagnostics/multi_readout_experiment.py` + `MULTI_READOUT_REPORT.md`
- **护城河更新**：从三条扩到四条（第四条"局部可决策"部分成立，仅简单任务）
- **不宣称**：计算力优势（Phase 3 实测为负）、能耗优势（Phase 5.1 实测为负）

**下一步**：Phase 6 商业化（API 化 + 开发者工具 + GitHub 开源 + arXiv 论文）

---

## 五、关键决策

### 决策 1：Phase 1 的模块扩展范围
- **选项**：保守（4 → 6） vs 激进（4 → 10）
- **决定**：✅ **激进（4 → 10）**
- **理由**：虚拟生物的优势在于"自由堆叠"，模块太少无法体现

### 决策 2：Phase 3 的"超越生物学"基准
- **选项**：任务性能 vs 能量效率 vs 进化速度
- **决定**：✅ **进化速度**
- **理由**：计算机天然优势，最容易验证（虚拟生物的优化迭代速度 vs 真实生物的进化速度）

### 决策 3：商业化路径
- **选项**：科研工具 vs 开发者工具 vs SaaS 平台
- **决定**：✅ **开发者工具**
- **理由**：AI 研究员是真实需求，且愿意付费

---

## 六、审核标准

**后续所有项目推进必须回答以下问题**：

1. **模块化**：是否增加了模块库/蓝图库？
2. **堆叠性**：是否支持深度组合（不只是 a+b，而是 a+(b+c)）？
3. **优化自由度**：是否支持自动优化（遗传算法/进化策略）？
4. **超越生物学**：是否有基准测试证明虚拟生物可以超越生物学限制？
5. **可追溯性**：每个虚拟生物是否可追溯到生物 motif（schema v1.1.1）？

**不符合审核标准的工作**：
- ❌ 只做静态审计展示（没有"可追溯 + 结构精简"两条硬指标，也没有 cell 级密化的实证路径）
- ❌ 只做性能优化（没有"模块化堆叠"的架构）
- ❌ 只做前端展示（没有"自动优化"的引擎）
- ❌ 只做生物学模拟（没有"计算机优化自由度"）

---

## 七、与 SwarmLabs 的关系

- **flybrain-connectome**：虚拟生物形态生成器（闭源，生物神经元数据 + 生成器）
- **SwarmLabs**：科研 Agent Infra（开源，消费 flybrain 的虚拟生物拓扑）
- **关系**：flybrain 是"虚拟生物设计平台"，SwarmLabs 是"虚拟生物运行平台"

---

## 八、诚实边界

- **当前阶段**：Phase 1 + Phase 2 + Phase 3 均已执行 — 设计空间扩展达成（10 模块 / 22 蓝图），
  自动优化已实测但**判定未达标**，定位按降级路径收口
- **已验证**：
  - motif 可追溯性（schema v1.1.1，blueprint → 真实 motif → 真实神经元）
  - 模块堆叠基础（22 蓝图 + 组合语法 `a+b` / `a,b` / **嵌套 `a+(b+c)`** / 去重）
  - 模块库扩展至 **10**（决策 1 激进 4→10 已达成；sensory/memory/motor/integration/attention/working_memory/reward/punishment/habit/metacognition）
  - 蓝图库扩展至 **22**（5 basic + 13 biological + 4 synthetic；Phase 2 已完成）
  - 模块堆叠机制正确（4 模块→21 agents，6 模块→31 agents，10 模块→71 agents；新模块均带 capability profile）
  - 嵌套组合 `a+(b+c)` 与平铺 `a+b+c` 同构（_verify 45/45 通过，含 3 条 Phase 2 新增校验）
  - 全部蓝图 provenance 全覆盖（无 unknown）；合成蓝图诚实标记 `motif=none`
- **部分验证 / 已实测为负**：模块堆叠是否能"超越生物学"（Phase 1/2/3 核心验证目标）
  - 基准实验（`benchmark_module_stacking.py`，5 配置 × 5 场景 × 3 轮）与生物学对照实验结论一致：
    **SwarmLabs 引擎对拓扑不按 score 区分**（所有配置 score=100/converged=1.0）。
    ⚠️ 该事实**不能**解读为"拓扑不重要"——这只说明他们的评估器无信息量。
  - Phase 3 GA 已用"进化速度"指标（决策 2）实测，结果见 §六：
    - 与生物学先验同物种的公平比较中，**随机搜索严格优于 GA**（8/8 seeds，+29% 适应度）—— GA 无增值
    - 仅当允许砍掉生物学必然结构（递归记忆 / 储备库缓冲）时，GA 才赢（线成本 −84%）
  - **计算力维度已实测，结果为负**（不是"未验证"）：自建储备池评估器 + 匹配控制实验
    （同 N、同非零数 K、种子平均 30）下，**生物 motif 0/7 优于随机结构**；
    负结果归因于设计空间密度 0.002–0.023（结构上不足以承载记忆），非实验失误。
    此前"动态适应度无判别力"的说法经复核为**标定错误**，已纠正（见报告 §5.1）。
  - **新增：结构稳定性维度已实测，结果为正**（2026-09-18）：模块故障隔离实验
    （`fault_isolation_experiment.py`，7 拓扑 × N_SEEDS=30）下，
    **6/7 拓扑表现出模块级故障隔离**（模块关停降幅比随机关停小 13-24 个百分点），
    **5/7 拓扑关停后谱半径 ρ 几乎不变**（0.00%），其他模块内部动力学完全保留。
    这是**生物学至今未证实的能力**（Friston 2008 modularity of brain 争议）。
  - **结论：「超越生物学」现成立于两个维度：结构精简（Phase 3）+ 结构稳定性（Phase 3.5）；
    计算力维度已实测为负，不再宣称。**
- **风险已兑现，但降级是"收窄主张"不是"项目没意义"**：Phase 3 未在"进化速度"与"计算力"上
  超越生物学，项目定位已按 MEMORY 写入的降级路径收口为「可追溯的虚拟生物形态生成器」——
  差异化 = motif 溯源 + 结构精简 + **结构稳定性（模块级故障隔离）**。可追溯性是
  LangGraph/AutoGen/CrewAI 结构上做不到的（无法回答"你的 agent team 来自哪个神经元"），
  结构稳定性是生物学至今未证实的——这两条都是真实护城河，不是残值。

---

## 九、下一步

**Phase 1 模块扩展（4→10）✅ 已完成**（2026-09-18）：
1. ✅ 加 2 个新模块（attention + working_memory）→ 扩至 6
2. ✅ 加 3 个新蓝图（基于新模块）→ 扩至 12
3. ✅ 基准实验验证模块堆叠机制正确（benchmark_module_stacking.py，全量运行通过）
4. ✅ 决策 1 激进路线：再补 4 模块（reward/punishment/habit/metacognition）→ **模块库 = 10**
5. ✅ _verify.py 42/42 通过（含 2 条新增模块库校验）；10 模块样例 sample_10module.swarm.json 校验通过 + motif 可追溯

**Phase 2 蓝图库扩展（12→22）✅ 已完成**（2026-09-18）：
1. ✅ 6 个新生物 motif 蓝图（hierarchical_deep / predictive_coding_v2 / reward_gated_selection / punishment_suppression / metacognitive_control / habit_consolidation）
2. ✅ 4 个合成编排蓝图（rl_actor_critic / curiosity_driven / cognitive_control / multi_motif_blend，诚实标记 motif=none）
3. ✅ 嵌套组合 `a+(b+c)` 解析器（`_normalize_blueprint_spec`，与平铺 `a+b+c` 同构）
4. ✅ provenance 全覆盖（`BLUEPRINT_SOURCE_MOTIF` 22/22，无 unknown）
5. ✅ _verify.py **45/45 通过**（+3 条 Phase 2 校验：provenance 完整性 / 合成蓝图诚实标记 / 嵌套同构）
6. ✅ 实物证据：sample_phase2_rl / sample_phase2_nested / sample_phase2_habit_meta（71 agents / 10 profiles / ok=True）

**Phase 3 自动优化 ✅ 已执行，判定未达标**（2026-09-18）：
1. ✅ 遗传算法实现（算术混合 + 蓝图交叉 + 精英保留 + 锦标赛 + 变异，pop 24 × 40 代）
2. ✅ 进化速度指标（决策 2）：与随机搜索同等预算（960 评估/seed）对照，8 seeds 复现
3. ✅ 对照基线：人工最优（68 边）vs GA（locked 57 边 / free 9 边）vs 随机搜索（locked 50 边 / free 25 边）
4. ⚠️ **判定未达标**：locked regime 随机搜索 8/8 优于 GA；free regime GA 收敛到 9–11 边（−84%）
5. ⚠️ 动态适应度：初判"无判别力"经复核为**标定错误**（报告 §5.1）；自建评估器后
   以匹配控制实验实测，**生物 motif 0/7 优于随机结构**，计算力优势为负（报告 §5.2）
6. ✅ 产物校验：两个最优形态均 schema v1.1.1 / ok=True / 0 悬空边 / 10 profiles / motif 可追溯
7. ✅ 复核诊断套件：`diagnostics/dyn_calibration_probe.py`（三轮：标定 / 稳健性 / 匹配控制）
8. 📄 详见 `integrations/swarmlabs/GA_PHASE3_REPORT.md`

**下一步 — Phase 3 收口（推荐 1 + 2 + 3）**：
1. **诚实降级（立即）**：定位收敛为「可追溯的虚拟生物形态生成器」，差异化 = motif 溯源 + 结构精简
2. **Cell 级密化实验（1–2 天，最该做）**：当前负结果限于模块代表层（密度 0.002–0.023）。
   在模块内部补递归边把密度提到 0.1+，重跑匹配控制实验 ——
   **这是唯一能把项目从"审计工具"拉回"计算工具"的实验，且便宜**
3. **穷举替代 GA（1 天）**：可行域小得多且景观几乎单调，穷举可得**确定性最小可行形态表**，
   直接作为前端/商业化参数库（GA 在此 regime 无增值，8/8 输，不该继续投入）
4. **不再等 SwarmLabs 修 score**：他们的评估器对拓扑恒 100/1.0 是他们的问题；
   已有自己的运行时（报告 §5.1/§5.2），绕开即可

---

**文件用途**：后续所有项目推进、功能叠加、技术决策都必须以此目标文件为审核基础。不符合本目标的工作应拒绝或重新设计。