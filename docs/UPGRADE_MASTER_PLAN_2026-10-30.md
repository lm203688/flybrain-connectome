# flybrain-connectome 全面提升总纲（2026-10-30）

> **评估基线**：`v3.01.3`（2026-10-26）。本报告为**全量实测扫描**，不引用旧数字；
> 融合「技术专家 / AI 专家 / 互联网产业专家」三视角，结合 **2026–2028 前沿技术**与
> **开源生态融合**，给出一份**可执行、带验收、带风险**的分阶段提升方案。
> 它是已有《PROJECT_COMPREHENSIVE_UPGRADE_REPORT_2026-10-26》《PROJECT_FRONTIER_ELEVATION_2026-10-28》
> 《OPEN_SOURCE_FUSION_2026-10-11》的**收敛与升级版**，而非又一次并列评估。

---

## 0. 一句话结论

**项目科研已到国际前沿（真实连接组 + 机器强制纪律 + 诚实负结果），但"产品闭环、生态入口、规模化工程"三项落后半年以上。**
当前最稀缺的不是更多功能、门禁或文档，而是三件事：**① 一条可安装、可运行、可复现的黄金路径；② 一个能让外部用户第一次"跑起来并复算"的旗舰实验；③ 把 24 万个小文件与 90GB 数据体量压缩成可维护、可流式、可云原生的资产**。
补齐这三项，项目的"可验证结构实验平台"定位才能从仓库内部自证，变成生态里可被使用、检验、持续积累的能力。

---

## 1. 本次实测证据（2026-10-30，全部为当前工作区实测）

### 1.1 规模与体量（关键：文件爆炸 + 数据体量失衡）

| 维度 | 实测值 | 专家判断 |
|---|---|---|
| 总文件数 / 目录数 | **240,122 文件 / 901 目录** | 已达"文件系统不友好"量级，Windows 同步/备份/扫描显著变慢 |
| `.swc` 骨架文件 | **234,879**（`male_cns/skeletons-swc` 211,573） | **最大工程负债**：一神经元一文件，git/同步/拷贝灾难 |
| 数据目录体量 | `male_cns` **35.7GB**、`drosophila_connectome` **12.5GB**、备份 `flybrain-fsbackup-20261018-231013` **40.5GB** | 真实数据本体仅 ~5.6GB feather，其余是骨架/虚拟生物/重复备份 |
| 代码量 | MCP+integrations+scripts+selfverify = **256 个 .py / 85,122 LOC** | 已进入"需以架构边界管理复杂度"区间，禁止继续单文件膨胀 |
| Python | 声明 `>=3.10`，CI 测 3.10/3.12/3.13；**本机实测跑在 Python 3.14** | 版本下限/上限声明与实测不一致，需统一 |
| 公开数字 | 116 功能单元 / 270 模块画像 / **47 MCP 工具 + 47 HTTP dispatch（Gate 66）** / 16 CLI 子命令 / **64+ 门禁** / 7 notebook | 数量面很宽，但"数量"不再是进展信号 |

### 1.2 新鲜硬缺陷（本次实测命中，且均为"公开承诺未兑现"类）

| # | 缺陷 | 实测证据 | 严重度 |
|---|---|---|---|
| 1 | **单元测试在 Windows 失败** | `pytest tests/unit` → **2 failed / 11 passed**（`test_status_json_transport_gap_declared`、`test_run_capture_utf8_survives_non_ascii`） | 🔴 公开仓库在主开发平台不能全绿 |
| 2 | **PyPI 不可安装** | `https://pypi.org/pypi/flybrain-connectome/json` → **HTTP 404**；`dist/` 为空 | 🔴 README 首步 `pip install` 即失败 |
| 3 | **Windows 编码缺陷仍复现** | 上轮 P0-1 的 GBK 解码问题在 `test_run_capture_utf8_survives_non_ascii` 仍红 | 🔴 跨平台契约未闭环 |
| 4 | **SKILL.md 前置条件为假** | `skills/flybrain-connectome/SKILL.md` 写 `pip install flybrain-connectome`，但包不存在 | 🟠 生态入口文档失真 |
| 5 | **CI 无 Windows/macOS** | `.github/workflows/ci.yml` 仅 `ubuntu-latest`（gates 矩阵 + package job），无 pytest 树、无 Windows | 🟠 跨 OS 发布从未被验证 |
| 6 | **`.pytest_cache` 权限 + `nul` 文件** | 根目录存在 Windows 伪文件 `nul`（0 字节）；pytest 缓存写入被拒 | 🟡 仓库卫生 / 平台污染 |
| 7 | **备份/产物入库** | 40.5GB 备份目录、`*.bundle`、`SCI_SUBMISSION_PACKAGE_*.zip`、根实验产物均在仓库内 | 🟡 仓库膨胀，应走 LFS/Release 资产 |

### 1.3 已兑现的强项（避免误判为"全是短板"）

- **真实数据锚定**：MaleCNS v1.0（166,700 神经元 / 124,177,617 突触，CC-BY）+ C.elegans / larva / zebrafish / mouse_v1 跨物种适配器。
- **机器强制科研纪律**：S1 外部验证、S2 lesion cascade、S3 统计强化（catch-rate 100%）、预注册 / 拒绝规则 / holdout / claim graph / receipt / mutation gate——**这是项目最稀缺、最难复制的资产**。
- **诚实边界**：PR-1 WEAK、PR-2 FAIL×3、PR-3 FAIL、PR-2b 预执行拒绝——**5 条中 4 条负结果，无一刷成 PASS**。
- **2026 三标准已对齐两项**：MCP（47 工具，HTTP 全覆盖 Gate 66）+ W3C PROV-JSON（EU AI Act 审计格式）；Agent Skills（`SKILL.md`）已补，但**包不存在导致其前置条件为假**。
- **差异化真实且可防御**：连接组 → Agent 拓扑 + PROV-JSON 溯源 + MCP + 机器纪律的交叉，无直接竞品（BRAPH 2 / TVB / brainlife / o8t 均在神经影像侧）。

---

## 2. 三视角专家诊断

### 2.1 技术专家视角：架构与工程

- **单包 monorepo**：`flybrain_cli.py`（1,241 行）+ 主生成器（~5,704 行）+ 模块注册表（~3,559 行）+ MCP server（~1,527 行）为顶层模块，`pyproject.toml` 仅打包 `flybrain_cli` 与 `flybrain-connectome-mcp`，`tool.setuptools.packages.find` 用连字符包名——**标准 Python 包化从未真正完成**，wheel 无法独立运行（依赖 `FLYBRAIN_HOME`/checkout）。
- **数据存储不可扩展**：`core.py` 注释强调 memory-mapped-friendly，但实际未用 `mmap_mode='r'`，并同载多份 int32/int64 数组（理论峰值 ~9.7GB）；**一神经元一 `.swc` 文件**（21 万+）是存储模式的根本问题。
- **测试名存实亡**：`testpaths=["tests"]` 只有 2 个单元文件，且 2 个在 Windows 失败；无 integration/e2e、无契约测试、无 property-based 测试、无覆盖率达标。
- **可观测性薄弱**：有 OTel trace（LangGraph runnable）+ PROV-JSON，但未声明 SEP-414/SEP-2704 兼容，运行事实与结构版本未统一关联。
- **性能定位缺失**：无公开 P50/P95 查询、峰值 RSS、并发、冷热启动指标；HTML 预览仍为 O(N²) 每帧 + 永久 `requestAnimationFrame`。

**结论**：技术面的"能力密度"很高，但**工程成熟度被"能力堆叠"掩盖**。需把 85k LOC 从顶层模块重构为有边界的包，把存储从"文件爆炸 + 全量内存"迁移为"列式 + 内存映射 + 内容寻址"。

### 2.2 AI 专家视角：AI4S / Agent 工程

- **能力面**：47 MCP 工具、47 HTTP dispatch、16 CLI、64+ 门禁、116 单元、270 模块画像、LangGraph/CrewAI/AutoGen 导出、SKILL.md、PROV-JSON、AIBOM。AI4S 三标准（MCP 科学工具化 / Agent Skills / File-as-Bus）已对齐 MCP + File-as-Bus + Skills。
- **未兑现**：LangGraph 导出是"生成含 MockLLM + MemorySaver + OTel 的脚本"，**未见真实 LLM 下执行 + 节点异常恢复 + 中断续跑 + 人工审批 + OTel 导入开源后端**的端到端验收；CrewAI/AutoGen 仍是 adapter POC。
- **优化器未插件化**：GA 8/8 输随机（Phase 3 判定），未接入 EvoAgentX/AFlow/DSPy 等外部搜索作为插件，也未建立"预算记账 + holdout 隔离 + Pareto 晋级"的受控接口。
- **LLM 角色边界**：现有 `llm_orchestrator.py` 可承担"提议/解释/翻译"，但**不应做最终裁判、不改冻结阈值、不触 holdout**——这条纪律已写入愿景，需在实现中强制（确定性 schema 校验 + 反证 agent + 人工批准）。

**结论**：AI 面最该做的是**"把已生成的可运行候选，变成真实可运行、可恢复、可观测、可复算的实验"**，而不是再增加一个导出格式或门禁编号。

### 2.3 互联网产业专家视角：分发、成本、可见性、治理

- **分发/入口**：PyPI 404、无 Homebrew/npm/uv 入口、无 Docker Hub 镜像、无 Conda 包、无 GitHub Releases 资产——**"能力在，用户装不上"**。SKILL.md 前置条件为假。
- **成本与规模**：消费级硬件 + 全量内存 + 21 万小文件，**无法支撑"连接组即服务"的规模化**；数据层必须走向列式/分块/流式，否则任何云上多租户都不成立。
- **可见性（GEO/SEO）**：已有 GitHub Pages + demo + 9 篇论文 DOI + 公开仓库，但 0 star/fork（公开 API 核验），无独立复现。按 PROJECT_CONTEXT 的诚实口径，**不要做交易产品，只借"连接组→可审计 Agent 拓扑"叙事做技术可见性**——这是可行的产业路径。
- **安全与供应链**：有 `.secrets.baseline`、`check_no_secrets`、AIBOM、SBOM 意识、pre-commit——**是强项**；缺 CodeQL / OSSF Scorecard / Dependabot / SLSA provenance / 镜像签名。
- **治理**：MIT + 数据 CC-BY + 额外限制条款并存；`CODEOWNERS`/`CONTRIBUTING` 已有；缺**机器可读许可矩阵**与**数据版本单源（datasets.yaml）**。

**结论**：产业面最高杠杆是**发布工程**（PyPI + 容器 + 三 OS CI）与**资产化**（数据走 Release/LFS、备份与产物出仓），其次是**可观测 + 安全供应链**的现代化。

---

## 3. 前沿技术融合路线（2026–2028，按"对北极星贡献 × 落地成本"排序）

> **北极星**：每周被独立复跑并完成裁决的实验数。所有前沿技术都服务于"结构可相信、结果可复算、失败可保留"。

### 3.1 数据与存储层（最高杠杆，先做）

| 前沿方向 | 具体技术 | 融合价值 | 阶段 |
|---|---|---|---|
| 列式 + 内存映射 | **Arrow/Parquet 分区 + `mmap_mode='r'` + CSR/CSC**；`polars`/`duckdb` 做分析查询 | 把 9.7GB 峰值与 21 万小文件，换成按需加载、流式构建、内容寻址缓存 | P0 |
| 骨架批量存储 | `.swc` 合并为 **Zarr / HDF5 / 每神经元单行 Parquet**（`napari`/`ome-zarr` 兼容） | 21 万文件 → 数十个分块文件；git/同步/备份/云传输全部加速 | P0 |
| 查询加速 | **DuckDB/DataFusion** 替代手写过滤；**rustworkx / petgraph** 做高吞吐图算法 | 连接查询与图算法从"自己写"到"用经过验证的引擎" | P1 |
| 大规模执行 | **Dask / Ray**（数据并行）+ **JAX/CuPy**（GPU 向量化 ESN/GNN） | R1/R2 扩样、N≥100 规模化实验"随时跑" | P1 |
| 图表示检索 | **Qdrant / LanceDB / pgvector** 向量检索 + 自监督图嵌入（PyG/`G-reasoner`） | motif 检索、相似结构推荐、异常检测的实验先验 | P2 |
| 知识图谱 | **neo4j / oxigraph** 存 PROV-O + 跨数据集映射；**GraphRAG** 把 claim 图谱变可问答 | 从"查 JSON"到"问图谱"，证据谱系可 SPARQL 查询 | P2 |

### 3.2 科学 / AI4S 层（把"生成"变成"可复算实验"）

| 前沿方向 | 具体技术 | 融合价值 | 阶段 |
|---|---|---|---|
| 可执行 IR | **AgentGraphIR**（typed state / reducers / routers / retry / checkpoint / human-approval / trace / eval hooks），LangGraph 为后端，AutoGen 标 legacy | 让导出从"文件"变"可运行"，一次验收覆盖执行+恢复+人工+追踪 | P1 |
| 优化器插件 | **EvoAgentX / AFlow / DSPy / 随机 / BO** 统一 `SearchStrategy` 接口，项目持有 holdout + 预算 + 晋级 | 借外部优化生态，守住项目最独特的可信控制面 | P2 |
| 多保真实验 | L0 结构指标 → L1 ESN/率模型 → L2 GNN/LIF → L3 **FlyGym/NeuroMechFly** 具身；主动学习调度 | 让 AI for Science 落地为可测的"同预算信息增益"，而非聊天窗口 | P2 |
| 具身闭环 | **NeuroMechFly v2 / FlyGym**（MuJoCo + Gymnasium + 视觉/嗅觉）作标准身体层，项目出 controller + 协议 + 证据 | 结构—动力学—感知—行为—干预连成因果链 | P2 |
| 标准评测 | **NeuroBench** 算法/系统双轨；能量证据标 `simulated|estimated|measured` | 纠正"能耗已证伪"的过度外推 | P2 |
| 可信自演化 | 候选沙箱 + 最小权限 + canary + 回滚 + 人工批准 + 签名谱系 | 把已有结构签名/receipt 延伸到 Agent 发布治理 | P3 |

### 3.3 可观测 / 合规层（补齐"查不清"的最后一公里）

| 前沿方向 | 具体技术 | 融合价值 | 阶段 |
|---|---|---|---|
| 统一追踪 | **OpenTelemetry** 命名对齐 **SEP-414**；**Langfuse / Arize Phoenix / LangSmith** 导入 | 节点执行 ↔ 结构版本 ↔ 运行事实可互查 | P1 |
| 审计上下文 | **SEP-2704**（MCP audit context）在响应头挂 PROV-JSON | 从"有 PROV 数据"到"符合 MCP 生产化接口" | P1 |
| 三层谱系 | program claim → project decision → task artifact 三层 provenance 链（Frontiers in AI 2026 方向） | 对齐 MCP-native 分层 AI 科学家生态 | P1 |
| FAIR 研究包 | **RO-Crate + Workflow Run + 容器/环境 + 参数 + receipts** 可执行研究包 | 从"打包文件"到"可复现对象" | P2 |
| 合规矩阵 | PROV 只支持谱系证据；EU AI Act 的运行/风险/监督分别记录 | 避免"PROV 即合规"的过度宣传 | P2 |

---

## 4. 开源技术融合矩阵（按贡献 × 成本排序，标注"自研 vs 融合"）

> 原则：**能用成熟开源不重造**。项目专注结构约束、实验协议、反事实、证据与晋级——这是别人最难替代的部分。

| 排名 | 开源技术 | 类别 | 融合价值 | 成本 | 阶段 | 自研/融合 |
|---|---|---|---|---|---|---|
| 1 | **uv + hatchling/pixi** | 打包/环境 | 干净环境一键装、跨 OS、锁定依赖、`pip install` 从假变真 | 低 | P0 | 融合 |
| 2 | **polars / pyarrow / duckdb** | 列式数据 | 替代全量 numpy + 手写过滤，按需加载、流式 | 中 | P0 | 融合 |
| 3 | **zarr / ome-zarr / h5py** | 批存储 | 21 万 `.swc` → 分块；napari 可浏览 | 中 | P0 | 融合 |
| 4 | **pytest + hypothesis + pytest-xdist + pytest-cov** | 测试 | 建真测试树、属性测试、并行、覆盖率达标 | 低 | P0 | 融合 |
| 5 | **GitHub Actions（Windows/macOS 矩阵）+ uv** | CI | 三 OS 发布验证；Windows 编码缺陷进 CI 必红 | 低 | P0 | 融合 |
| 6 | **CodeQL + OSSF Scorecard + Dependabot + SLSA + SBOM(CycloneDX)** | 安全/供应链 | 从"有 secrets 扫描"到"供应链现代化" | 中 | P0 | 融合 |
| 7 | **LangGraph（真实后端）** | Agent 运行时 | 可执行、checkpoint、人工、流式、中断 | 中 | P1 | 融合 |
| 8 | **OpenTelemetry + Langfuse/Phoenix** | 可观测 | 轨迹、成本、评估、与 PROV 关联 | 中 | P1 | 融合 |
| 9 | **rustworkx / networkx / igraph** | 图算法 | 高吞吐、经过验证的图计算 | 中 | P1 | 融合 |
| 10 | **dataprov（已有）+ RO-Crate** | 溯源/FAIR | PROV-JSON 标准化 + 可执行研究包 | 中 | P1 | 融合 |
| 11 | **NeuroMechFly/FlyGym + MuJoCo** | 具身 | 标准身体层，接入感觉—运动闭环 | 高 | P2 | 融合 |
| 12 | **EvoAgentX / AFlow / DSPy** | 优化器 | 插件化搜索，不做通用优化算法 | 中 | P2 | 融合 |
| 13 | **PyTorch Geometric / JAX + CuPy** | GNN/GPU | 结构表征、多保真动力学、GPU 加速 | 高 | P2 | 融合 |
| 14 | **Qdrant / LanceDB + 图嵌入** | 向量/检索 | motif 检索、相似推荐、实验先验 | 中高 | P2 | 融合 |
| 15 | **Dask / Ray** | 分布式 | 规模化实验、跨机并行 | 高 | P2 | 融合 |
| 16 | **neo4j / oxigraph（RDF/PROV-O）** | 知识图谱 | 证据谱系可 SPARQL、GraphRAG 问答 | 高 | P2 | 融合 |
| 17 | **NeuroBench harness** | 标准评测 | 能耗/时延/效率标准口径 | 中 | P2 | 融合 |
| 18 | **MLflow / DVC** | 实验追踪 | 与 receipts/claim 关联的版本化实验 | 中 | P3 | 融合 |
| 19 | **uv + GitHub Releases + Docker 多架构 + Homebrew** | 分发 | 多入口分发（PyPI/容器/包管理器） | 中 | P1 | 融合 |
| 20 | **JEV / 端侧小模型（Laya 421M）** | 决策/验证 | 已有两级"小模型预筛→大模型深验"，推广到实验侧 | 低 | P0 | 自研+融合 |

**自研保留项**（不外包）：结构约束与中间表示、实验协议与预注册、反事实/对照生成、claim/receipt 裁决、晋级与回滚、W3C PROV 谱系、跨数据集映射与许可矩阵。

---

## 5. 分阶段提升方案（P0→P4，含完成定义）

### P0：0–2 周 —「发布真相与工程收口」（最高杠杆，先修"装不上/测不过/跑不绿"）

| 工作包 | 具体动作 | 完成定义 |
|---|---|---|
| **P0-1 包重构** | `flybrain_cli.py` + MCP + 生成器拆为标准 `flybrain_connectome/` 包（core/schemas/datasets/generators/runtimes/experiment/adapters/provenance/cli）；资源用 `importlib.resources`；`uv build` 出 wheel | 空目录、无仓库、无环境变量下 `generate/audit/export/demo` 全部成功 |
| **P0-2 PyPI + 分发** | `uv publish` → TestPyPI → PyPI Trusted Publishing；`dist/` 清理；GitHub Releases 挂资产；评估 Homebrew/uvx | 三 OS `pip install flybrain-connectome` 与 demo 通过 |
| **P0-3 测试重建** | 建 `tests/unit|integration|e2e`；Windows 编码修复（集中 subprocess helper，`encoding='utf-8', errors='replace'`）；hypothesis + xdist + cov | 干净环境 `pytest` 全绿；Windows 2 个红转绿；覆盖率按核心包有基线并逐周提升 |
| **P0-4 三 OS CI** | CI 矩阵加 `windows-latest`/`macos-latest`；pytest 树入 CI；`uv` 安装 | 三 OS 全绿；编码缺陷进 CI 即红 |
| **P0-5 数据层改造（第一批）** | `mmap_mode='r'` + 按需单向索引；`.swc` 骨架批量打包为 Parquet/Zarr；内容寻址缓存 | 峰值 RSS 与首次构建时间显著下降且结果一致；文件数从 24 万 → 千级 |
| **P0-6 安全/供应链** | CodeQL + Scorecard + Dependabot + SBOM(CycloneDX)；许可矩阵单页 | 无高危依赖告警；许可无冲突；SBOM/AIBOM 含数据许可 |
| **P0-7 仓库卫生** | 40.5GB 备份、`*.bundle`、`SCI_*.zip`、根实验产物、`nul` 出仓/入 LFS/Release；`.pytest_cache` 修复 | 仓库体积与文件数显著下降；无平台伪文件 |
| **P0-8 公开真相** | 所有数量/命令/门禁/工具由构建时生成 `project_status.json`，README/Pages/paper 引用 | 无 58/58、36 工具等旧值；无虚假默认 PROV 承诺 |

**阶段出口**：外部用户在三大 OS 上从 PyPI 安装，完成一个带明确证据等级的 demo；所有公开数字一致；发布检查全绿。

### P1：3–6 周 —「一条真实黄金路径」

| 工作包 | 具体动作 | 完成定义 |
|---|---|---|
| **P1-1 AgentGraphIR + LangGraph runnable（真）** | 定义 IR；LangGraph 真实后端；验收：mock LLM 下执行、节点异常恢复、checkpoint 续跑、人工审批暂停/恢复、OTel 导入 ≥1 开源后端、拓扑 hash 关联每次执行 | 全通过才写"supports runnable LangGraph export" |
| **P1-2 MCP/SEP 生产化** | 声明 SEP-2704（audit context 挂 PROV-JSON）+ SEP-414（OTel 命名对齐）；MCP-native 三层 provenance | 标准接口可被第三方工具摄入 |
| **P1-3 单实验工作台** | 只做一个模板"原始 motif vs 保度重连的模块扰动恢复"；Run/Compare/Evidence 三视图；同一 experiment_id 可在 CLI 复跑 | 5 名目标用户 ≥4/5 在 15 分钟内完成安装/运行/对照/导出 |
| **P1-4 数据层改造（第二批）** | DuckDB/DataFusion 查询；rustworkx 图算法；公开 P50/P95/RSS/并发指标 | 查询性能按版本追踪，结果与旧路径一致 |

**阶段出口**：一个用户在干净环境可完成的"提出结构→运行→干预→比较→复跑"闭环，且可观测。

### P2：7–12 周 —「旗舰科学实验 + 多保真」

| 工作包 | 具体动作 | 完成定义 |
|---|---|---|
| **P2-1 旗舰实验** | 预注册"连接组结构是否提高扰动后感觉—运动恢复能力"；六类对照（原始子图/保度重连/保模块重连/随机/参数匹配 MLP-GNN/无结构先验）；参数×结构四臂分离；holdout 一次性开启 | 结果回答清晰问题，他人可复算；负结果也按同一流程发布 |
| **P2-2 具身最小闭环** | NeuroMechFly/FlyGym 一个感觉—运动任务，结构后端作可替换 controller | 感知→结构→行为→干预闭环，能量证据分级 |
| **P2-3 优化器插件** | `SearchStrategy` 接口 + ≥1 外部优化器 + 同预算竞赛；holdout 不可触 | 优化器不可触 holdout，结果可比较 |
| **P2-4 图表示/检索** | Qdrant/LanceDB + 图嵌入；motif 检索与相似推荐 | 校准、外推、不确定性达标 |

**阶段出口**：第一条真正有外部竞争力的结构—功能证据（或高质量边界论文）+ 公开 benchmark。

### P3：3–6 月 —「可信优化与多保真平台」

- 多保真 L0–L3 调度、Pareto 前沿、预算记账、holdout 权限、回滚；Workflow Run RO-Crate；OTel + PROV 经 experiment/run ID 关联；扩展一个可独立外验的数据源（如 MICrONS/ZAPBench），**前提是能独立外验，而非只加适配器**。

### P4：6–12 月 —「外部证据网络 + 数字孪生升维」

- ≥2 外部团队独立复现旗舰实验；公开 leaderboard（默认展示置信区间/成本/证据等级）；问题驱动加入发育/修复/区室/神经调质之一；有真实校准数据后才升级"校准型数字孪生"；自演化只在沙箱 + 受控发布下开放。

---

## 6. 关键架构决策（本方案的骨架）

### 6.1 一个平台，两条应用线，显式映射

平台 = **连接组约束的可验证结构实验平台**。两条线：**生物数字孪生**（节点=神经元/细胞群，边=突触，验证对象=活动/扰动/行为）与 **Agent 拓扑**（节点=模型/工具/函数，边=消息/控制流，验证对象=任务/成本/恢复）。共用同一图 IR，但必须经 `TranslationContract` 显式说明保留/舍弃/灵感命名。**禁止**把"神经元—突触"直接等同于"Agent—消息"，也禁止把小尺度 ESN 负结果外推为连接组对所有计算任务无效。

### 6.2 一个版本化可执行 IR（Structure/Experiment）

`structure` / `node_dynamics` / `edge_dynamics` / `state_schema` / `input_encoder` / `output_decoder` / `plasticity` / `interventions` / `metrics` / `evidence_refs`。同一结构可在 ESN/率模型/LIF/GNN/Agent 后端运行，结果必须标后端，禁止跨后端混写。每个产物同时带 `biological_evidence` 与 `task_evidence` 两个独立区块。

### 6.3 发布 = 标准包 + 资产外置

仓库收敛为 monorepo 但发布标准 wheel；原始大数据外置，通过内容寻址 + `datasets.yaml`（版本/引用/许可/哈希/计数口径/已知局限）单源管理；备份/产物/大文件走 LFS 或 Release 资产。

### 6.4 LLM 的边界

LLM 只做四件事：生成候选 IR、把自然语言限制编译为类型化端口/路由、从失败轨迹提出可证伪机制、转写带证据链接的报告。**不做最终裁判、不改冻结阈值、不触 holdout、不在无 schema 校验下执行高风险演化**。神经—符号回路：LLM 提议 → JSON Schema 验收 → 确定性模拟 → 反证 agent → 受保护裁决 → 人工批准。

### 6.5 北极星与 KPI

北极星 = **每周被独立复跑并完成裁决的实验数**（无外部用户时以干净容器/不同 OS 的自动复跑代替，但必须标 `internal replay`，不伪装成 `independent replication`）。四层 KPI：用户价值（首次成功实验 <15 分钟、无指导完成率）、科学价值（有对照比例、外部复现数、holdout 违规=0）、工程质量（三 OS 发布成功率、P95、峰值 RSS）、前沿能力（同预算信息增益、多保真成本节约）。

---

## 7. 风险与防止路线偏离

| 风险 | 早期信号 | 预防 |
|---|---|---|
| 平台过大、主线失焦 | 同时推进全脑/Agent/基础模型/商业化 | 每阶段只一个旗舰实验 + 一个发布出口 |
| AI 生成超验证能力 | 候选/文档增长快于真实 run | LLM 只能提议；预算/schema/holdout 强制 |
| 生物—Agent 概念偷换 | 用生物 provenance 宣传任务性能 | 双证据区 + TranslationContract + 文案门禁 |
| 负结果过度普遍化 | "连接组无计算价值"式绝对表述 | claim 绑定基底/任务/尺度/适用域 |
| 门禁复杂但产品脆弱 | 内部全绿、外部安装/运行失败 | 干净环境、真实后端、用户任务入发布门禁 |
| 数据/许可漂移 | 同数据不同计数/引用 | datasets.yaml 单源 + hash + 许可矩阵 |
| 优化过拟合 | 反复访问测试集、阈值随结果变 | 受保护 holdout + 一次性开启 + 访问记账 |
| 自演化安全 | 候选直改稳定版、权限过大 | 沙箱 + 最小权限 + canary + 回滚 + 人工批准 |
| 合规过度宣传 | "PROV 即 EU AI Act 合规" | 合规矩阵；PROV 只支持谱系证据，运行/风险/监督分别记录 |

---

## 8. 立即行动清单（按周）

**本周（P0 启动）**：① 修 Windows 2 个测试红 + 集中 subprocess helper；② `uv build` 出 wheel 并验证空目录可运行；③ 把 `.swc` 骨架批量打包计划落第一版脚本；④ 清理 `nul` + 备份/产物出仓；⑤ CI 加 Windows 矩阵。

**两周内**：① PyPI Trusted Publishing + 三 OS 安装验证；② 建真 pytest 树 + hypothesis + 覆盖率基线；③ 数据层 `mmap_mode` + 单向索引改造 + 性能基线；④ CodeQL/Scorecard/Dependabot/SBOM。

**六周内**：① LangGraph 真实可运行后端（执行/恢复/人工/OTel 全过）；② SEP-2704/414 声明 + 三层 provenance；③ 单实验工作台（Run/Compare/Evidence）+ 5 用户可用性测试。

**十二周内**：① 预注册结构—恢复旗舰实验（六类对照 + 参数×结构分离 + holdout）；② FlyGym 一个感觉—运动最小闭环。

**一年内**：① 外部复现网络 + 公开 leaderboard；② 多保真可信优化平台；③ 有真实校准数据后再投入更大数字孪生/自演化。

---

## 9. 结论

项目已越过"能否做出许多组件"阶段。**必须完成三次转变**：① 从仓库内部自证 → 外部干净环境与真实工作流验证（先修发布/契约/测试）；② 从结构生成与静态谱系 → 结构—动力学—功能—干预的可执行证据（用一个旗舰实验建立真正科学高度）；③ 从所有能力自己实现 → 开放生态中的可信控制面（复用标准运行时/优化器/观测/具身平台，把研发资源集中在**证据、对照、反事实、晋级**上）。

**若只能选一条主线**：**"可复跑的连接组结构反事实实验平台"**。它保留当前科研纪律差异化，又能自然扩展到 Agent 拓扑与数字生命；既允许接入最新 GNN、世界模型、自演化 Agent 与主动学习，又不会被任何单一模型淘汰。最终应让竞争者即使有更大模型、更炫仿真、更多 Agent 工具，仍愿意用 FlyBrain 回答一个问题：**这个结构为什么值得被相信，在什么条件下成立，失败后如何复现与回滚。**

---

*评估：技术 + AI + 互联网产业三视角 · 证据：2026-10-30 工作区全量实测（文件统计/测试运行/CI 审查/PyPI 核验/代码量）· 基线 v3.01.3。*
