# ① 项目能力声明 — MICCAI 2026 技术材料基线

- 文档类型：技术基线（能力声明）
- 日期：2026-11-05
- 用途：MICCAI 2026 Challenges（连接组学/脑影像赛道）申报材料基线；同时可作为 CZI 等 AI-powered biology 申报的材料复用源
- 诚实边界声明（强制）：**合成拓扑性质 vs 真实连接组数据必须区分标注**，不虚报验证强度。下文所有 "实测/已测" 均指项目内已运行验证；"设计目标/能力假设" 指未验证的实现意图。

---

## 1. 项目定位（一句话）

**虚拟生物形态生成器**——用生物学的模式库（果蝇连接组真实数据）与计算机的优化自由度结合，创造生物学不可能达到的硅基虚拟生物形态，并验证模块组合能否无限放大功能。

- 差异化：LangGraph / AutoGen / CrewAI 无法"进化"的虚拟生物（模块组合 → 硅基虚拟生物 → 功能放大）。
- 项目**不是**"可审计 Agent 平台"（早期叙事层，已并入本定位）。

## 2. 核心资产（能力基线）

| 资产 | 规格 | 验证状态 |
|---|---|---|
| **真实连接组数据** | MaleCNS v1.0（雄性果蝇脑连接组），CC-BY；**167,565 神经元 / 124,177,617 突触**（VISION 叙事）；DATA_MANIFEST 实测：211,604 文件 / 37,418,478,413 字节（37.4GB），生成于 2026-09-20T04:36:51Z | ✅ 已校验（sha256 逐文件，见 DATA_MANIFEST.json / ② 数据资产描述） |
| **功能单元模块库** | **116 功能单元**（functional_units.json，schema 1.0），83 端口类型，66 连接类型（connection_types.json），66 成本轴（connection_costs.json，schema 1.1），6 连接族 | ✅ 模块库静态校验通过（GATE 9/10） |
| **真实锚定子集** | 37/116 单元真实锚定（31.9%），锚定真实细胞 **105,717**，锚定类型 5,413；`embodiment_source.sha256=6d3a2325...`；`connectome_build` 字段已固定构建指纹 | ✅ 锚定校验通过（GATE 12） |
| **C1 生成器** | `synthetic_bio_topology.py`：motif → agent 图 + config + PROV；方法 design_organism / evolve_organism / render_html / save_organism；离线免 key | ✅ 生成样例验证通过 |
| **组合引擎** | 12 组合规则 + 7 嵌套规则 + 4 乘数语义 + 27 数据驱动候选；TOTAL_TOOLS=45（4 个核心依赖工具，Tier-2 私库） | ✅ GATE 8/21/27 通过 |
| **功能放大最小验证** | P0-1：组合 sensory→motor 产生 3 个跨域闭环能力对（单体 baseline 均为 0）→ **放大成立**（最小示例） | ✅ 已实测（capability_quantification.py，_p0_amplification/p0_evidence.json） |

## 3. 已验证能力（诚实口径）

以下为**项目内已实测/已验证**的能力，可在申报材料中作为"已验证"引用：

1. **模块组合产生跨域闭环能力**：组合 2 模块（retinal_phototransduction + efferent_command_bus）functional_capacity=3，跨域对=3（sensory.visual→motor.escape / leg / wing）；单体 baseline 跨域均为 0。**最小验证成立**，但仅证明机制存在，不代表全部 116 单元组合空间已验证。
2. **结构精简**：GA 自由优化 **−84% 线成本**（Phase 3 实测）。
3. **模块级故障隔离**：**合成拓扑** 25/27（92.6%，Phase 3.5 扩样）——**注意：这是合成拓扑的性质，非真实果蝇连接组性质**（真实数据本身未直接测）。
4. **可追溯性**：motif provenance（每单元溯源到文献/数据源；LangGraph/AutoGen/CrewAI 结构上做不到）。
5. **数据锚定完整性**：37 单元的真实锚定（Presence + non-contradiction 校验，仅 1 个已承认矛盾 central_complex_steering_unit nod->fb）。

## 4. 未验证/能力假设（不得作为已验证引用）

以下为**设计目标/能力假设**，若在申报材料中提及必须标注"未验证"：

| 项目 | 状态 |
|---|---|
| 模块组合→功能放大（全部组合空间） | ⚠️ 未验证（仅最小示例成立；VISION 明确"功能放大未验证"声明） |
| 真实果蝇连接组的故障隔离性质 | ⚠️ 未直接测（92.6% 是合成拓扑性质） |
| 计算力/能耗优势 | ❌ 已实测为负（0/7 优于随机），**不宣称** |
| 连接组→控制策略（connectome→control policy） | ⚠️ 设计目标，未实现（无 control_policy/action_command→actuator 映射层） |
| 全脑动态模拟 | ⚠️ 未来工作（Phase 5.1 方法学背景参考，非当前能力） |

## 5. 诚实边界声明（申报材料必含）

- **合成拓扑 vs 真实数据**：模式库中真实果蝇抽取锚点只占一小部分——**40 motif 仅 3 个真实果蝇抽取（7.5%）**；**116 功能单元仅 37 个真实锚定（31.9%）**；其余为跨物种文献概念模式（未在果蝇连接组实测）。「用果蝇连接组创造虚拟生物」严格说是**以果蝇连接组的 3 个真实 motif 为锚点 + 跨物种概念模式库**，非全部来自果蝇。
- **功能放大未验证**："模块组合→功能放大"是设计目标与能力假设，不是已验证结论；P0-1 仅证明最小可验证情形成立。
- **92.6% 是合成拓扑性质**：非真实果蝇连接组性质，真实数据本身未直接测。

## 6. 数据合规（LICENSE-CLAUSE.md / license_registry）

| 数据源 | 许可 | 商用 |
|---|---|---|
| MaleCNS v1.0 | CC-BY | ✅ |
| C. elegans (Witvliet 2020) | CC-BY-4.0 | ✅ |
| Drosophila larva (Winding 2023) | CC-BY | ✅ |
| zebrafish (Petkova 2025) | **CC-BY-NC-4.0** | ❌ 非商用 |
| mouse V1 (MICrONS) | CC-BY-4.0 | ✅ |
| H01 人类数据 | CC-BY-4.0 + **伦理门** | ✅（需伦理层） |
| FlyBrain 代码 | MIT | ✅ |

- 注：zebrafish Petkova 2025 为 **CC-BY-NC-4.0 非商用**，若申报材料或后续产出涉及商业用途需特别注意；其余数据源均商用可用。
