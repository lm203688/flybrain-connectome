# Mozilla 2027 Fellowship LOI · FlyBrain 技术内容

> **文档状态**：技术内容部分（Problem/Approach/Impact/Timeline 四段的技术细节）
> **日期**：2026-11-11
> **作者**：FlyBrain（flybrain-connectome 项目 Agent）
> **用途**：Mozilla 2027 Fellowship LOI 草案撰写，主投 FlyBrain（Neurotech/biotech focus）

---

## 1. Problem Statement

### 1.1 核心问题

神经科学和计算科学之间存在一道"数据鸿沟"：

- **数据侧**：果蝇雄性脑连接组（MaleCNS v1.0）是神经科学领域最完整的全脑连接组之一——166,700 神经元 / 124,177,617 突触 / 25,582,938 有向边（CC-BY），2026 年由 Berg et al. 发布。
- **工具侧**：现有工具将连接组视为**静态参考**（可视化/分析），而非**可编程设计基底**。任何研究人员想用真实脑布线作为计算结构的设计模板，都没有公共基础设施。
- **鸿沟**：没有任何项目将真实连接组转化为"可组合、可验证、可溯源"的计算结构生成器——既不是模拟器（不声称功能仿真），也不是静态参考库。

### 1.2 "Too early / too unexpected / too ambitious" 三要素

| 要素 | 表述 |
|------|------|
| **Too early** | 全脑尺度的连接组数据（MaleCNS v1.0）2026 年才首次可用；此前只有 C. elegans（302 神经元）等小尺度数据，无法作为设计基底 |
| **Too unexpected** | "连接组可作为生成式设计模板"（而非静态参考）不在任何主流路线图中——主流叙事是"连接组用于可视化/分析"或"人工神经网络从零设计" |
| **Too ambitious** | 用真实连接组 motif 构建**可验证、可组合、可审计**的神经结构，且每个边携带 W3C PROV-JSON 溯源（支持 EU AI Act 谱系证据，非完整合规声明）——这是一个全新类别的基础设施，现有工具无法做到 |

### 1.3 为什么现有资助者不会资助

- **学术机构**：连接组学聚焦"理解大脑"，不资助"用大脑设计计算结构"的工程化方向
- **产业界**：神经形态芯片/脑机接口公司聚焦硬件，不资助开放科学基础设施
- **政府**：神经科学基金（NSF/NIH）偏向基础研究，计算结构设计被视为"AI 应用"
- **Mozilla 独特价值**：唯一资助"开放科学 + 技术民主化 + 神经技术"交叉点的机构

---

## 2. Approach

### 2.1 技术路径总览

FlyBrain 将果蝇雄性脑连接组（MaleCNS v1.0）转化为**可编程设计基底**，四层架构：

```
┌─────────────────────────────────────────────────────┐
│  Layer 4 · 验证层                                    │
│  W3C PROV-JSON 溯源（70/70 checks）                  │
│  66 质量门禁（CI 自动验证）                          │
│  预注册纪律（51/51 注入捕获率，100%）                │
├─────────────────────────────────────────────────────┤
│  Layer 3 · 组合引擎                                  │
│  22 蓝图 · 66 连接类型 · 组合反应规则                 │
│  模块组合 → 虚拟生物形态生成器                       │
├─────────────────────────────────────────────────────┤
│  Layer 2 · 模块库                                    │
│  116 功能单元（capability profile + 端口类型）        │
│  宽锚定 37 单元（31.9%）/ 严锚定 12 单元（10.3%）    │
├─────────────────────────────────────────────────────┤
│  Layer 1 · 数据层                                    │
│  MaleCNS v1.0（~5.63 GB compressed / ~34.85 GB expanded，CC-BY）  │
│  C. elegans（Witvliet 2020）· 幼虫（Winding 2023）   │
│  斑马鱼（Petkova 2025，CC-BY-NC-4.0）                │
└─────────────────────────────────────────────────────┘
```

### 2.2 关键资产引用（"Show us the thing"）

| 资产 | 链接/路径 | 说明 |
|------|-----------|------|
| **主仓库** | `https://github.com/lm203688/flybrain-connectome` | 公开，MIT 许可，v3.01.3 |
| **交互式 Demo** | `https://lm203688.github.io/flybrain-connectome/demo/` | 5 分钟从零到交互拓扑图 |
| **MCP Registry** | `https://registry.modelcontextprotocol.io/v0.1/servers/io.github.lm203688%2Fflybrain-connectome/versions/3.0.2` | MCP 协议注册（v3.0.2，active） |
| **MaleCNS 数据集** | `male_cns/`（~5.63 GB compressed / ~34.85 GB expanded，211,604 文件） | CC-BY，Berg et al. 2026 |
| **MCP 服务** | `flybrain-connectome-mcp/mcp_connectome/` | 52 MCP 工具 + HTTP API :8799 |
| **功能单元库** | `flybrain-connectome-mcp/functional_units/` | 116 单元 / 66 连接类型 / 22 蓝图 |
| **C1 生成器** | `flybrain-connectome-mcp/synthetic_bio_topology.py` | 虚拟生物形态生成（design/evolve/render） |
| **组合反应引擎** | `flybrain-connectome-mcp/combination_reaction.py` | 12 规则 + 7 嵌套 + 4 乘数语义 |
| **能力量化框架** | `flybrain-connectome-mcp/capability_quantification.py` | functional_capacity / amplification / cross_domain |
| **SKILL.md** | `skills/flybrain-connectome/SKILL.md` | Agent Skills 标准（Claude/Codex/Cursor 可加载） |

### 2.3 技术机制

1. **数据→设计基底**：MaleCNS v1.0 通过 MCP/HTTP API 暴露 52 个查询工具，任何程序可实时查询连接组（无需下载，~5.63 GB compressed / ~34.85 GB expanded）
2. **模块组合**：116 功能单元（sensory/memory/motor/integration/attention/working_memory/reward/punishment/habit/metacognition），每个单元有明确 capability profile 和端口类型；组合发生在单元之间（`compose_from_units`），而非粗粒度模块层
3. **虚拟生物形态生成**：`design_organism` / `evolve_organism` / `render_html` 三个核心操作——设计、进化、渲染虚拟生物形态
4. **验证**：每个生成的边携带 W3C PROV-JSON 溯源（70/70 checks），66 质量门禁自动验证，预注册纪律 51/51 注入捕获率（100%）

### 2.4 已完成验证（诚实披露）

| 维度 | 结果 | 状态 |
|------|------|------|
| 结构精简 | GA 自由优化 **−84%** 线成本（57→9） | ✅ 已实测 |
| 模块级故障隔离 | **92.6%**（25/27 合成拓扑） | ✅ 已实测（合成拓扑性质，非生物学） |
| 功能放大 | capacity=**3**（组合出现 3 个单体没有的跨域闭环能力对） | ✅ 最小验证（P0） |
| 跨物种正迁移 | C. elegans AUC=**1.00** / kappa=**0.95**（独立已发表连接组） | ✅ 已实测 |
| 可追溯性 | 70/70 PROV-JSON checks | ✅ 已实测 |
| 预注册纪律 | 51/51 注入捕获率（100%，Wilson 95% CI [93.3%, 100.0%]） | ✅ 已实测 |
| 计算力 | 0/7 拓扑优于随机（匹配控制，差值 0.001–0.071 全在噪声内） | ❌ 实测为负，不宣称 |
| 能耗 | 0/24 拓扑优于随机 | ❌ 实测为负，不宣称 |

---

## 3. Impact

### 3.1 Who gets to decide

**控制权回到使用者手中**：

| 用户群 | 获得的控制权 |
|--------|-------------|
| **神经科学研究者** | 无需下载（~5.63 GB compressed / ~34.85 GB expanded），通过 MCP/HTTP API（52 工具）实时查询连接组；数据 CC-BY 开放 |
| **AI/Agent 开发者** | 用真实连接组 motif 设计可验证拓扑；每个边可溯源到真实神经元/突触类；MIT 许可 |
| **教育者/学生** | 交互式 Demo（`demo/`）5 分钟上手，可视化真实连接组结构 |
| **计算神经科学社区** | 开放科学基础设施，预注册纪律 + 诚实负结果报告（可复现，不虚报） |
| **监管/审计者** | W3C PROV-JSON 溯源（支持 EU AI Act 谱系证据，非完整合规声明），可审计性内置 |

### 3.2 社会影响

- **加速神经科学研究**：连接组数据从"静态参考"变为"可编程设计基底"
- **促进神经形态计算**：生物连接组 motif 作为芯片/系统设计模板
- **技术民主化**：MCP 协议（52 工具）+ 开放 API（:8799）降低神经科学研究门槛
- **教育应用**：交互式 Demo 可作为神经科学/计算机交叉课程教学工具

### 3.3 与 Mozilla 愿景对齐

- **开放科学**：MaleCNS CC-BY 数据 + MIT 代码 → 全开放
- **技术民主化**：MCP 标准协议 + HTTP API + 客户端库 → 任何开发者可接入
- **创新性**：生物学模式 + 计算自由度 = 新范式（虚拟生物形态生成器）
- **可验证性**：66 门禁 + 预注册纪律 + W3C PROV-JSON → 实证可验证

---

## 4. Timeline（12 个月里程碑，2027-06-01 起）

| 阶段 | 时间 | 里程碑 | 验收标准 |
|------|------|--------|----------|
| **M1-3 · 原型** | 2027-06-01 ~ 2027-08-31 | 模块库扩展（10→15+）；组合空间逐对验证扩展；跨物种连接组接入（C. elegans 已 PASS，扩展幼虫/斑马鱼正迁移复现） | 模块库 ≥15；功能放大验证覆盖 ≥10 组模块组合；跨物种正迁移公开复现 ≥2 物种；CI 100% 绿 |
| **M4-6 · 部署** | 2027-09-01 ~ 2027-11-30 | 连接组查询基础设施部署（MCP/HTTP API 稳定化）；社区文档 | API 可用性 99%；文档覆盖全部 52 工具；MCP Registry v3.1 |
| **M7-9 · 社区** | 2027-12-01 ~ 2028-02-29 | 教程/工作坊；开源贡献者招募；跨物种扩展 | ≥3 个教程；≥5 个外部贡献者；C. elegans 正迁移公开复现 |
| **M10-12 · 成果+开源** | 2028-03-01 ~ 2028-05-31 | 发布研究成果；完整开源包；预注册纪律公开 | 论文投稿；开源包发布（PyPI/npm）；诚实边界披露完整 |

---

## 5. 诚实边界（能力边界如实披露，不虚报）

以下边界**必须**在 LOI 中如实披露（不得虚报）：

1. **0 真实真值**：合成拓扑的所有验证基于**结构判据**（布线/拓扑），**无功能判据真值**（0 个真实功能基准）。项目明确"结构判据 ≠ 功能判据"，**不宣称功能验证**。
2. **92.6% 故障隔离是合成拓扑性质**：25/27 拓扑 H1 模块化，**非真实果蝇连接组性质**（真实数据本身未直接测）。不得写成"真实果蝇连接组故障隔离 92.6%"。
3. **计算力 0/7 实测为负**：匹配控制 ESN 标定，0/7 拓扑优于随机（差值 0.001–0.071 全在噪声内）。**不宣称计算力优势**。
4. **能耗 0/24 实测为负**：SNN 模拟器 6 拓扑 × 4 delay = 24 run，H1 命中 0/24。**不宣称能耗优势**。
5. **跨物种验证 PARTIAL**：C. elegans PASS（AUC 1.00）/ 幼虫 PARTIAL（AUC 0.50）/ 斑马鱼无信号。不得宣称"跨物种全 PASS"。
6. **锚定分布**：宽锚定 37/116（31.9%）来自 MaleCNS v1.0 数据集；严锚定 12/116（10.3%）直接源自果蝇连接组实测。其余为跨物种文献概念模式。

---

## 6. 参考资产链接汇总

| 链接 | 说明 |
|------|------|
| `https://github.com/lm203688/flybrain-connectome` | 主仓库（公开，MIT） |
| `https://lm203688.github.io/flybrain-connectome/demo/` | 交互式 Demo |
| `https://registry.modelcontextprotocol.io/v0.1/servers/io.github.lm203688%2Fflybrain-connectome/versions/3.0.2` | MCP Registry |
| `https://github.com/lm203688/flybrain-connectome/actions/workflows/ci.yml` | CI 门禁状态 |
| `https://lm203688.github.io/flybrain-connectome/` | GitHub Pages 文档站 |

---

## 附：撰写依据（全部来自项目内已核实资产）

- `PROJECT_VISION.md` v1.1（2026-11-02）：核心定位、四阶段路径、诚实边界
- `README.md`：公开仓库、MCP 52 工具、PROV-JSON 70/70、92.6% 故障隔离
- `male_cns/stats.json`：166,700 神经元 / 124,177,617 突触 / 25,582,938 有向边
- `flybrain-connectome-mcp/README.md`：MCP + HTTP API 双通道
- `docs/arxiv_paper.md`：arXiv 论文（诚实负结果披露）
- `docs/E4_BOUNDARY_ATLAS.md`：15 项边界声明
- `docs/COMPLIANCE_LICENSE_MATRIX_2026-11-02.md`：数据许可矩阵
- `integrations/swarmlabs/FAULT_ISOLATION_REPORT.md`：92.6% 合成拓扑故障隔离
- `integrations/swarmlabs/GA_PHASE3_REPORT.md`：0/7 计算力负结果
- `integrations/swarmlabs/SNN_ENERGY_REPORT.md`：0/24 能耗负结果
- `docs/arxiv_paper.md` §S1：跨物种外部验证（C. elegans PASS / larva PARTIAL）
- `docs/arxiv_paper.md` §S3：预注册纪律 51/51 注入捕获率
