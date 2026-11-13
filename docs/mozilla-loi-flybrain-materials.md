# Mozilla LOI FlyBrain 素材采集

- **采集时间**：2026-11-11
- **用途**：Mozilla 2027 Fellowship LOI §7 资产表（11-30 定稿，12-17 截止）
- **纪律**：只引用真实存在资产，不存在的明确写"不存在"，不确定标"未核实"，不编造

---

### 素材1：脑电解码代码库
- 状态：已核实
- 内容：**不存在**。项目内无 BCI/EEG 资产，无脑电解码代码库、无相关仓库地址、无关键文件。
- 来源：`docs/NEURAL_INTERFACES_TRACK2_BCI_2027_REFERENCE_2026-11-07.md`、`docs/CODA_BENCH_STANDARD_BENCHMARK_2026-11-06.md`（均明确"项目无 BCI/EEG 资产"）；全项目 grep EEG|脑电|decoding|解码 命中均为误匹配

### 素材2：Demo 链接
- 状态：已核实
- 内容：在线 Demo 存在，GitHub Pages 部署。
- 来源：
  - 在线：`https://lm203688.github.io/flybrain-connectome/demo/`
  - 本地：`docs/demo/`（index.html / topology.html / topology.json / .nojekyll / README.md）

### 素材3：数据集（MaleCNS）
- 状态：已核实
- 内容：
  - 名称：MaleCNS v1.0（果蝇雄性中枢神经系统连接组）
  - 规模：166,700 神经元 / 124,177,617 突触 / 25,582,938 有向边（neuron_subgraph；full_table 311,833,243 突触 / 151,856,684 rows）
  - 来源：项目站 `male-cns.janelia.org` / GCS `gs://flyem-male-cns/v1.0/` / neuPrint `male-cns:v1.0`
  - 许可：CC-BY
  - 引用：Berg et al. 2026, *Cell*, 189(18), 5504–5526.e15, doi:10.1016/j.cell.2026.08.015（PII S0092867426009426；bioRxiv 预印本 doi:10.1101/2025.10.09.680999, CC-BY）
  - ⚠️ 引用口径已统一（2026-11-12）：全仓错误 "Xu et al. 2020, *Neuron*"（其 DOI 实为 Pribiag & Lim 阿片记忆论文）与 "Schlegel et al. 2026"（MaleCNS 第四作者）已统一改回 Berg et al. 2026, *Cell*（MaleCNS 第一作者 Stuart Berg）；`datasets.yaml` 单一真源仍待建
- 来源：`male_cns/connectivity_stats.json`

### 素材4：论文/会议记录
- 状态：已核实
- 内容：存在论文草稿，但**均未实际投稿/发表**。
  - 主线：`docs/arxiv_paper.md`（v1.2.0）
  - 方法学短文：`docs/arxiv_methodology_short_paper_2026-10-16.md`
  - 其他草稿：`docs/PAPER_P1_MAINLINE_MERGED.md`、`docs/PAPER_P3_JOSS_PREREG_DISCIPLINE.md`、`docs/PAPER_P4_CASE_STUDY.md`、`docs/PAPER_P5_CASE_STUDY.md`、`docs/PR2B_PREEXECUTION_REJECTION_PAPER.md`、`docs/C3_RESOLUTION_CLAMP_FIXES_PAPER.md`、`docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md`
  - 文献综述：`docs/connectome_determinism_papers.md`（17 篇）
  - 投稿包：`outputs/SCI_SUBMISSION_PACKAGE_2026-10-20/`（01_manuscripts / 02_submission_guides / 03_evidence_reports / 04_readiness / 06_latex_manuscript）
  - 诚实边界：未实际投稿 arXiv/bioRxiv/JOSS，无正式发表场所，无会议记录
- 来源：`docs/`、`outputs/SCI_SUBMISSION_PACKAGE_2026-10-20/`

### 素材5：共形预测精度指标
- 状态：已核实
- 内容：**不存在**。全项目 grep conformal|共形|Conformal 零匹配，无共形预测精度指标、无测试集。
- 来源：FlyBrain 验证层 = PROV-JSON 70/70 + 66 门禁 + 预注册 51/51；共形预测是 SwarmLabs 能力，不在 FlyBrain

### 素材6：Neural Interfaces 2026 Track2 BCI 参赛记录
- 状态：已核实
- 内容：**未参赛，无提交记录**。
  - 注册状态：已关闭（所有四轨 11-01/11-02 关闭）
  - 项目内无 BCI/EEG 资产、无提交物
  - 基线 EEGNet 32.6% < chance 33.3%
  - 决策：不参赛（定位不契合，2026-11-06/11-07 已确认）
- 来源：`docs/Neural-Interfaces-2026-赛程节点评估-2026-11-11.md`

---

## 汇总（6 项有无判断）

| # | 素材 | 有无 |
|---|------|------|
| 1 | 脑电解码代码库 | ❌ 不存在 |
| 2 | Demo 链接 | ✅ 存在 |
| 3 | 数据集 MaleCNS | ✅ 存在 |
| 4 | 论文/会议记录 | ✅ 草稿存在（未投稿/未发表） |
| 5 | 共形预测精度指标 | ❌ 不存在 |
| 6 | Neural Interfaces 2026 参赛记录 | ❌ 未参赛 |

**边界遵守**：只写文档，未 commit、未 push、未改代码。
