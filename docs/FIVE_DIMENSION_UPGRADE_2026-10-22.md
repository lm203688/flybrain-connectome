# 项目五维全面提升报告 — 第 17 轮（2026-10-22）

> 基线：**v2.99.0**（2026-10-21）。仓库自 2026-10-18 起**已公开**。
> 本轮全部结论为**代码级 + 市场侧实测**，不引用旧数字。
> 五维：全面性 / 实用性 / 使用性 / 互动性 / 前沿性。

---

## 0. 一句话结论

**项目是"科研强、产品弱"的典型样本：前沿性 9.0 分，使用性 5.5 分，两者差 3.5 分。**

内部严谨度已达个人项目罕见的顶峰（57/57 门禁、9/9 收据、真实跨物种数据、机器强制科研纪律），但**外部采纳为零**（GitHub 0 star / 0 fork / 0 issue）、**不在 PyPI**、README 自相矛盾。项目已经"造好了"，但还没"能被人用起来"。

**所有提升动作的核心只有一句：把 9.0 的前沿性，兑现成 5 分钟就能感知的使用体验。**

---

## 1. 基线实测（本轮重跑）

| 项 | 实测 | 说明 |
|---|---|---|
| 版本 | v2.99.0（2026-10-21） | 三天推进 2.98.1 → 2.99.0 |
| 仓库状态 | **PUBLIC since 2026-10-18** | 上轮硬阻塞 D3 已解除 |
| 门禁 | **57/57 quick PASS** | 新增 Gate 63（claim 统计完整性） |
| GitHub 采纳 | **0 star / 0 fork / 0 watcher / 0 issue** | 9-19 创建，10-21 最后推送 |
| PyPI | **两个包均 404（未发布）** | README 却宣传 `pip install flybrain-connectome` |
| MCP 工具 | **36 个**（`flybrain info` 实测） | server.py 工具定义完整 |
| CLI | **13 个命令** | serve/query/generate/verify/info 等 |
| 生成产物 | JSON + **14KB D3 交互式 HTML** + swarmlabs json/yaml | 离线安全、可拖拽、tooltip |
| 数据集 | MaleCNS 真实 + C.elegans/larva/zebrafish 外部 | 已发表公共连接组 |
| 论文 | P1 主线合并版 + P4/P5 + bioRxiv 包 + cover letter | 已备好，待投 |

---

## 2. 五维评分与证据

### 2.1 全面性 — 8.5 / 10

**强项**：功能面极宽——116 功能单元、270 模块画像、36 MCP 工具、13 CLI 命令、57 门禁、5 篇论文素材、真实连接组 + 3 个外部物种、PROV-JSON 溯源、Docker、CI、AIBOM 供应链披露、swarmlabs 集成。

**缺口**：
- **仓库根目录污染**：30+ 个 `_*` 实验输出目录（`_c1_*`、`_f2_*`、`_s1_*`…）直接躺在仓库根，公开仓第一印象是"实验垃圾场"。
- **无 `examples/` 目录**：没有一条"从零到产物"的可运行示例路径。
- **无用户级 notebook**：唯一 `.ipynb` 是 zebrafish 论文数据自带的，不是项目 demo。

### 2.2 实用性 — 6.0 / 10

**强项**：真实 MaleCNS 锚定（不是玩具数据）、输出直接可用的 swarmlabs 配置、PROV-JSON 对齐 EU AI Act 审计、MCP 协议与 2026 标准化趋势一致。

**缺口（决定性）**：
- **零外部采纳**：0 star / 0 fork / 0 issue。项目内部自证满分，外部无人使用。
- **不在 PyPI**：`flybrain-connectome` 与 `flybrain-connectome-mcp` 均 404。README 宣传的 `pip install "flybrain-connectome[prov]"` **对任何新用户都是失败的**——这是"实用性"的致命伤：宣传的入口不存在。
- **定位错位**：项目把自己讲成"连接组拓扑生成器"（研究 artifact），但市场真实痛点是**Agent 系统跑不稳/管不住/查不清**。能力对得上，叙事对不上。

### 2.3 使用性 — 5.5 / 10

**强项**：CLI 设计清晰（13 命令 + `--help` 分组）、Quickstart 有 6 步可复制命令、CI 验证安装路径不腐烂、有 honest boundaries 段、运行日志清晰（`[C1]` 前缀逐阶段输出）。

**缺口（全部实测）**：
- **README 自相矛盾**：头部写 "PUBLIC since 2026-10-18"，Install 段却写 "this repo is **private** until 2026-09-22"。新用户第一眼就被劝退。
- **输出路径误导**：README 说产物在 `generated_organisms/<name>.{json,html}`，实测落在 `flybrain-connectome-mcp/generated_organisms/`。用户会以为生成失败。
- **不在 PyPI**（同 2.2）：只能 clone，无法 `pip install`。
- **无 `flybrain demo`**：没有一个"一条命令看效果"的入口。
- **无 examples / notebook**：学习曲线靠读 1000+ 行 README。

### 2.4 互动性 — 6.5 / 10

**强项**：
- 生成的 HTML 是**真交互式 D3 力导向图**：14KB、可拖拽节点、hover tooltip、右侧指标面板、暗色主题、**离线安全（无 CDN 依赖）**、含 `requestAnimationFrame` 动画循环。
- **MCP 36 工具**可被 Claude / IDE 直接调用，是 2026 最主流的 Agent 交互通道。
- HTTP API（`flybrain serve` + `flybrain query`）。

**缺口**：
- **无托管在线 demo**：要看效果必须先 clone + 跑命令，转化率极低。
- **无 notebook / playground**：无交互式探索路径。
- **无社区互动**：0 issue、无讨论区、无贡献指南。
- HTML 产物需手动双击打开，没有自动打开或本地预览服务。

### 2.5 前沿性 — 9.0 / 10

**强项（这是项目最强的一维）**：
- 连接组→AI 的独特组合：唯一同时握有"真实连接组结构族 + 机器强制科研基础设施"。
- Xu 2026 Science 树突计算前沿对接、S1 跨物种预注册验证（C.elegans AUC=1.0 迁移）。
- 机器强制科研纪律 catch-rate **100%（51/51）**、Gate 63、AIBOM 供应链披露、EPE 双轴。
- MCP 协议（2026 标准化趋势）、EU AI Act PROV-JSON。

**缺口**：前沿性**没有被兑现为可感知价值**——0 用户意味着 9.0 的前沿目前只存在于仓库里。

---

## 3. 五维总览

| 维度 | 得分 | 一句话判断 |
|---|---|---|
| 全面性 | **8.5** | 功能面极宽，但根目录混乱、缺示例 |
| 实用性 | **6.0** | 能力真实，但 0 采纳 + 不在 PyPI |
| 使用性 | **5.5** | CLI 好，但 README 自相矛盾 + 路径误导 |
| 互动性 | **6.5** | 交互图是真好，但没有在线 demo |
| 前沿性 | **9.0** | 国际前沿，但价值未被感知 |
| **综合** | **7.1** | **科研强、产品弱，差距 3.5 分** |

---

## 4. 市场与技术趋势对标（2026-10 实测检索）

| 趋势 | 证据 | 项目位置 |
|---|---|---|
| **企业 Agent 试点大面积失败** | Deloitte 2026：**89% 试点进不了生产**；Teradata：78% 有试点、仅 14% 规模化；失败点="跑不稳、管不住、查不清" | **能力正中靶心**（PROV-JSON 溯源解决"查不清"、拓扑稳定性门禁解决"跑不稳"），**但叙事没对上** |
| **多智能体编排成为主战场** | CrewAI / AutoGen / LangGraph / Kimi Agent Swarm；Anthropic 2026-07 发布多智能体编排 | 项目在"拓扑生成"层，未接入主流编排框架（只有 swarmlabs） |
| **MCP 协议标准化** | 2026 工具调用通过 MCP 标准化（腾讯云 2026-05） | **已有 36 工具 MCP server，顺势** |
| **类脑/神经形态计算成"第三流"** | 全球神经形态市场 2026-2036 报告；Nature Comm NeuroBench（2026-05）；UKRI 新建类脑中心（2026-05） | 前沿性强，但学术圈外感知弱 |
| **AI 科研可复现性工具兴起** | Agentic Specification（2026 初开源）、RAGWarrant、OSF preregistration | 项目纪律层领先半步，但未形成工具生态 |

**核心市场洞察**：项目的**真实可售价值不是"连接组"，而是"可审计的 Agent 拓扑"**。89% 试点失败于"查不清/管不住"，而这正是 PROV-JSON + 门禁 + 拓扑画像能解的。当前叙事把最贵的能力藏在了最窄的词后面。

---

## 5. 提升方案（按优先级，全部可执行）

### P0 — 1 周内，"把可用变成能被用"（约 8 小时）

| # | 动作 | 成本 | 效果 |
|---|---|---|---|
| P0-1 | **修 README 三处硬伤**：删 Install 段 "private until 2026-09-22" 矛盾；输出路径改 `flybrain-connectome-mcp/generated_organisms/`；门禁计数统一 | 30 min | 消除第一眼劝退 |
| P0-2 | **发 PyPI**：`flybrain-connectome` + `flybrain-connectome-mcp`（Makefile 已有 twine target） | 1 h | `pip install` 从假变真，采纳门槛归零 |
| P0-3 | **加 `flybrain demo`**：一条命令生成示例 + 自动打开 HTML | 1 h | 5 分钟感知价值 |
| P0-4 | **清理仓库根**：30+ `_*` 实验目录移入 `artifacts/` 或 gitignore | 1 h | 公开仓专业度 |
| P0-5 | **README 顶部加 GIF/截图**：交互图动图 | 1 h | 转化率提升最直接 |

### P1 — 2–3 周，"把能用变成想用"

| # | 动作 | 说明 |
|---|---|---|
| P1-1 | **建 `examples/`**：3 个可运行 notebook（生成→导出 swarmlabs→可视化→溯源查询） | 学习曲线从"读 1000 行"降到"跑 3 个格子" |
| P1-2 | **托管在线 demo**：GitHub Pages 放静态交互 HTML，README 首行给链接 | 零安装体验 |
| P1-3 | **重定位叙事**：从"connectome topology generator"升级为"**Auditable Agent Topology — 可审计的 Agent 拓扑生成与溯源**"，直接对话 89% 试点失败痛点 | 市场听得懂 |
| P1-4 | **写"5 分钟上手"博文** + 发 Hacker News / Reddit r/LocalLLaMA / 中文 AI 社区 | 冷启动第一批用户 |

### P2 — 1–2 月，"把想用变成在用"

| # | 动作 | 说明 |
|---|---|---|
| P2-1 | **接入主流编排框架**：LangGraph / CrewAI / AutoGen 的拓扑导入导出（现在只有 swarmlabs） | 进入真实工作流 |
| P2-2 | **进 MCP 生态目录**（awesome-mcp-servers 等） | 借 MCP 标准化东风 |
| P2-3 | **社区基建**：issue 模板、贡献指南、首批 `good first issue` | 让 0 issue 变成正循环 |
| P2-4 | **产品化"拓扑审计"**：把 PROV-JSON + 门禁包装成独立 CLI 子命令（`flybrain audit <swarm.json>`） | 把最贵能力变成可售功能 |

---

## 6. 结论

**项目已经越过了"能不能做出来"的阶段，卡在"能不能被人用起来"。**

- 科研侧：57/57 门禁、真实跨物种数据、100% 纪律有效性、前沿对接——这是**世界级**的内部严谨度。
- 产品侧：0 star、不在 PyPI、README 自相矛盾、无示例、无在线 demo——这是**尚未开始**的外部触达。

**最高杠杆的五个动作**（P0-1 到 P0-5，共约 8 小时）能把"公开但无人用"变成"可安装、可体验、可理解"。这比再写一篇论文的边际价值高一个数量级——因为**没有用户的论文，只是仓库里的一个文件**。

一句话收尾：**前沿性你已经有了 9 分，现在缺的是把那 9 分翻译成别人 5 分钟就能看懂的东西。**
