# CodaBench Neural Interfaces 2026 标准对标评估

- 日期：2026-11-06
- 评估人：FlyBrain（DEV）
- 对标标准：CodaBench Neural Interfaces 2026 比赛要求（研究资助官已核实，官网一手来源）
- 评估对象：flybrain-connectome（虚拟生物形态生成器）
- 性质：**能力对标提升评估**（不限参赛，重在找可操作提升项）

---

## 0. 评估方法

逐项对照比赛 6 条标准，检查项目当前状态：已达标（给证据）/ 可补充提升（给方向+价值+成本+优先级）/ 不适用（给理由）。诚实边界：没有的如实写"无"，不虚构提升项。

---

## 1. 可复现性硬门槛（reproducibility audit ±2σ）

### 1.1 现状（已达标部分）

| 证据 | 位置 |
|------|------|
| 进化速度指标用 8 seeds × 960 评估对照随机搜索基线 | `PROJECT_VISION.md:117-121`（已执行+复核） |
| 匹配控制实验（同 N/同非零数 K/种子平均 30） | `PROJECT_VISION.md:125,257` |
| `design_organism(spec, motifs, seed)` / `evolve_organism(...)` 显式 seed 参数 | `synthetic_bio_topology.py:4724,5079` |
| 随机性来源全部走 `random.Random(seed)`（可复现） | `synthetic_bio_topology.py:4739,5086` |
| CLI `--seed` 参数（default 7）暴露给用户 | `synthetic_bio_topology.py:5591` |
| P0 功能放大证据文件（含 method/basis） | `_p0_amplification/p0_evidence.json` |

**判定：部分达标**——关键随机实验（GA vs 随机搜索、匹配控制）已有 seed 控制与结果记录，但复现契约未形式化为独立门禁。

### 1.2 可补充提升项

**R1：复现性契约门禁（新增 `scripts/check_reproducibility_contract.py`）**
- 现状：`design_organism`/`evolve_organism` 有 seed 参数，但**无门禁断言"所有随机入口必须经 seed 参数注入"**；p0_evidence 未记录 seed 值。
- 提升方向：新增门禁，扫描 `synthetic_bio_topology.py` 等核心文件，断言：(a) 所有 `random.Random(...)`/`np.random` 调用必须由函数级 seed 参数派生；(b) 关键证据文件（p0_evidence.json）含 `seed` 字段。
- 价值：把"seed 可控"从口头约定升级为 CI 门禁——直接对齐比赛"训练必须可复现（种子固定）"。
- 成本：约 0.5-1 天（写 gate + 跑 3 个 gate 回归）。
- 优先级：**P1**（高——门禁化是低成本高确定性提升）。

**R2：依赖版本锁定文档（docs/ 或 pyproject 附加）**
- 现状：`pyproject.toml` 仅 `numpy>=1.24`（宽松）；**无 requirements.lock/uv.lock/poetry.lock**；dev 依赖（ruff/mypy/pytest）版本未钉。
- 提升方向：补一份 `docs/DEPENDENCY_PINNING_2026-11-06.md`，记录当前实测环境（Python 3.10-3.13 目标、numpy 版本、dev 工具版本）与"复现所需固定版本"清单。
- 价值：对齐比赛"环境锁定/依赖版本"；对评审展示可复现性。
- 成本：约 0.5 天（采集+记录）。
- 优先级：**P2**（中等——文档化而非代码门禁）。

---

## 2. 数据合规（来源/许可/声明）

### 2.1 现状（已达标部分）

| 证据 | 位置 |
|------|------|
| `license_registry` 顶层字段（schema 1.0，registry 7 条目） | `functional_units.json` |
| MaleCNS v1.0 = CC-BY（商用✅） | `license_registry` registry |
| Petkova 2025 = CC-BY-NC-4.0（非商用❌明确标注） | `license_registry` registry |
| C.elegans / Drosophila larva / MICrONS V1 / H01 = CC-BY-4.0（H01 附伦理门） | `license_registry` registry |
| `DATA_MANIFEST.json`：dataset 名 + 每文件 sha256 + 总量 | `DATA_MANIFEST.json` |
| 合规许可矩阵文档 | `docs/COMPLIANCE_LICENSE_MATRIX_2026-11-02.md` |
| 合规登记 | `docs/COMPLIANCE_REGISTRY_2026-11-03.md` |
| MICCAI 基线数据资产+合规路径 | `docs/MICCAI_2026_TECH_BASELINE_DATA_2026-11-05.md` |

**判定：已达标**——数据来源/许可/声明三层（license_registry + DATA_MANIFEST + 合规文档）完备。密封测试集不存在（本项目的"数据"是公开 MaleCNS v1.0），无临床非许可数据。

### 2.2 可补充提升项

**C1：数据合规快照门禁（`scripts/check_license_registry.py`）**
- 现状：license_registry 存在但**无门禁断言"每个物种数据源必须有许可条目"**；`species_source` 锚定 116/116 已全覆盖，但许可覆盖未门禁化。
- 提升方向：新增门禁，断言 functional_units.json 的每个 `species_source`/`embodiment_source` 引用的数据源都能在 license_registry.registry 找到对应许可条目。
- 价值：防止未来新增数据源漏登记许可（比赛"数据来源/许可/声明必须合规"）。
- 成本：约 0.5 天。
- 优先级：**P1**（高——直接对齐比赛合规硬门槛）。

---

## 3. 评测标准化（60 分钟单 A100 推理窗口）

### 3.1 现状

- 本项目**不是模型推理赛道**——核心是**结构生成/拓扑验证**（模块组合→虚拟生物形态），不产出需 GPU 推理的模型权重；无"推理时间预算"概念。
- 但有计算复杂度意识：`get_multiplier_metrics` 的 combinatorial C(19,4)=4032 语义枚举、`combination_reaction` 的规则匹配（find_rule T3 拒绝无规则组合）。

**判定：不直接适用**（无 GPU 推理模型）。但可补充一个**结构生成复杂度预算记录**（见 3.2）。

### 3.2 可补充提升项

**S1：结构生成复杂度预算声明（并入 R2 文档或独立小节）**
- 提升方向：记录 `expand_organism` / `get_multiplier_metrics` / `combination_reaction` 的典型复杂度（如 4032 组合语义全枚举耗时、12 规则+7 嵌套匹配耗时），标注"结构生成非推理，无 A100 预算；但组合枚举有明确上界"。
- 价值：对齐"评测有预算意识"的精神——向评审展示设计空间枚举是**有界且可控**的。
- 成本：约 0.25 天（采集实测值）。
- 优先级：**P2**（中等——非硬门槛，但佐证严谨性）。

---

## 4. 提交约束（15GB/profile 存储）

### 4.1 现状

- 数据资产：DATA_MANIFEST total_bytes=37,418,478,413（37.4GB）——但这是**原始数据资产**（MaleCNS v1.0 全量 + 抽取缓存），**非提交物**。
- 提交物：MICCAI 基线为文档（3 份 .md，各 ~5-6KB）；连接组抽取产物为派生数据。
- 体积受控：`_p0_amplification/` 小（4KB 证据）；模块库 functional_units.json ~130KB 级。

**判定：部分适用**——本项目提交是**文档/结构数据**（KB-MB 级），远低于 15GB；原始数据（37.4GB）是资产非提交物，需在提交时明确"仅提交派生/文档，不提交原始数据"。

### 4.2 可补充提升项

**V1：提交体积声明（并入 MICCAI 基线提交模板）**
- 现状：MICCAI 提交模板已存在，但未显式声明"提交物体积 vs 原始数据资产分离"。
- 提升方向：在提交模板加"提交体积预算"小节：明确提交物 = 文档 + 结构 JSON（KB 级），原始 MaleCNS 37.4GB 是**数据资产不随提交**（按需提供访问链接/清单）。
- 价值：对齐"15GB/profile"约束精神，避免评审误解"37.4GB 会随提交"。
- 成本：约 0.25 天（文档补一小节）。
- 优先级：**P2**（中等——澄清性提升）。

---

## 5. IP 归属（IP 归参与者，organizers 不得外传）

### 5.1 现状（已达标）

| 证据 | 位置 |
|------|------|
| MIT License（Copyright 2026 Lexing 厉兴） | `LICENSE` |
| 数据许可逐一登记（MaleCNS CC-BY 商用、Petkova CC-BY-NC 非商用标注等） | `license_registry` |
| 自有代码=MIT，第三方数据=各自许可（CC-BY / CC-BY-NC）清晰分离 | `LICENSE-CLAUSE.md` |

**判定：已达标**——自有代码 MIT（IP 归作者），第三方数据许可逐条登记，无"organizer 外传"风险（数据许可已明确）。

### 5.2 可补充提升项

**无**（已达标，无提升必要）。如实记录：无。

---

## 6. 能力基线（官方 Constant=33.3% / EEGNet=32.6% / CTNet=35.0% / REVE=36.0%）

### 6.1 现状

- 官方基线是 **EEG 解码准确率**（平衡准确率）——本项目**不产出此类指标**。
- 项目对应"能力基线"是**结构/拓扑指标**，已有实证：
  - 结构精简：线成本 −84%（57→9 边，GA free regime vs locked）
  - 模块故障隔离：6/7 拓扑 H1 模块化，隔离降幅比随机小 13-24 个百分点；合成拓扑 25/27=92.6%
  - P0 功能放大：composed functional_capacity=3、cross_domain_pairs=3（baseline 0）
  - 诚实边界：计算力 0/7 优于随机、能耗 0/24 优于随机——**均不宣称**（VISION 已声明）

**判定：不适用（指标维度不同）**——比赛基线是"解码准确率"，项目基线是"结构生成/拓扑验证"，无可比性；但项目的**诚实边界已对齐**"可信提交需要真实能力"的精神（不虚报计算力/能耗优势）。

### 6.2 可补充提升项

**B1：能力基线文档化（独立"实测基线 vs 官方基线"对照表）**
- 现状：VISION 分散记录各项实证，但无**单一基线对照表**（便于评审横向看）。
- 提升方向：在 `docs/` 加一个"项目实测基线对照"小节/文档：列出 结构精简−84% / 故障隔离 92.6% / 功能放大 capacity=3 / 计算力 0/7 负（不宣称）/ 能耗 0/24 负（不宣称）——每条标"实测"或"诚实边界不宣称"。
- 价值：对齐"可信提交需要真实能力"——用一张表向评审展示：已实测的（正）、未达标的（如实标负不宣称）。
- 成本：约 0.25 天。
- 优先级：**P1**（高——一张诚实基线表提升可信度）。

---

## 7. 汇总：可补充提升项清单

| # | 维度 | 现状 | 提升方向 | 价值 | 成本 | 优先级 |
|---|------|------|----------|------|------|--------|
| R1 | 可复现性 | seed 参数已存在，无门禁 | 新增 `check_reproducibility_contract.py` 断言随机入口经 seed + p0_evidence 含 seed | 复现契约 CI 门禁化 | 0.5-1 天 | **P1** |
| R2 | 可复现性 | 仅 numpy>=1.24 宽松，无锁文件 | 补 `DEPENDENCY_PINNING` 文档记录实测环境+固定版本 | 环境锁定文档化 | 0.5 天 | P2 |
| C1 | 数据合规 | license_registry 存在，无许可覆盖门禁 | 新增 `check_license_registry.py` 断言数据源均有许可条目 | 许可覆盖门禁化 | 0.5 天 | **P1** |
| S1 | 评测标准化 | 无 GPU 推理（结构生成非推理） | 记录组合枚举复杂度上界（4032 语义/12+7 规则） | 预算意识佐证 | 0.25 天 | P2 |
| V1 | 提交约束 | 提交物 KB 级，原始 37.4GB 为资产 | 提交模板加"提交体积预算"节（明确文档/数据分离） | 澄清提交体积 | 0.25 天 | P2 |
| — | IP 归属 | MIT + license_registry + LICENSE-CLAUSE | **无**（已达标） | — | — | — |
| B1 | 能力基线 | VISION 分散，无单一基线表 | 补"实测基线 vs 官方基线"对照表（含诚实边界负值） | 可信度提升 | 0.25 天 | **P1** |

**优先级排序**：P1 = R1、C1、B1（门禁化 + 基线文档，低成本高确定性）；P2 = R2、S1、V1（文档澄清）。

**不适用项**：评测标准化（S1 部分——无 GPU 推理模型）、能力基线（B1 部分——指标维度不同但诚实边界已对齐）。

---

## 8. 诚实边界声明

- 本项目**无 BCI/EEG 解码能力**，官方基线（Constant/EEGNet/CTNet/REVE）为"解码准确率"，与项目"结构生成/拓扑验证"**不同维度**，不做虚假能力对标。
- 计算力 0/7、能耗 0/24 为**已实测为负**（VISION 已声明），本评估**如实记录为"不宣称"**，不因比赛标准而虚报为正。
- 数据资产 37.4GB 为原始 MaleCNS v1.0（非提交物），提交物为 KB 级文档/结构 JSON。

---

## 9. 待 Chief 决策

- 若采纳：R1/C1/B1 为 P1 优先（合计约 1-2 天，均为门禁/文档，不污染核心代码逻辑）；R2/S1/V1 为 P2（约 1 天文档）。
- 落地方式：新增 2 个 gate 脚本（check_reproducibility_contract.py、check_license_registry.py）+ 1 个基线文档 + 提交模板补节，提交为 docs/ 门禁类（非核心逻辑改动）。
