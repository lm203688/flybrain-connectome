# 项目全面评估与提升方案报告

**基线**：`flybrain-connectome` v2.92.0（2026-10-16）
**门禁实测**：`python scripts/run_gates.py --quick` → **47/47 PASS**（3m15s，本次复测）
**上一轮报告**：`docs/NEXT_STAGE_VISION_EPE_2026-10-16.md`（v2.91.0）
**报告日期**：2026-10-16
**评估方法**：全量目录扫描 + 实测复核（不采信任何旧结论）+ 2026-10 前沿检索

---

## 零、一句话结论

> **项目在"自验证基础设施"这条轴上已经做到国际前列，甚至超出了一个 2026-09 独立工作的同期设计（RAGWarrant）；但本轮实测挖到一个致命级新发现——项目的"最小可复现分叉" `metrics_fork/` 根本跑不通，而它正是三篇方法学短文对外承诺"读者可自行复现"的唯一凭据。**
>
> 换句话说：**项目把"诚实"做成了机器门禁，却唯独没有给"可复现性本身"装门禁**——这是项目第 5 次遇到"度量/声明不测其所称之物"，这一次，它落在**可复现层**，也恰好是 SCI 论文可信度所依赖的那一层。

---

## 一、本轮实测基线（全部现场复测，不引用旧数字）

| 维度 | 实测值 | 与上轮（v2.91.0）对比 |
|---|---|---|
| 包版本 | **v2.92.0** | ↑1 |
| 门禁 | **47/47 PASS** | 持平 |
| 门禁总数（唯一编号） | 51（gate1–51，缺 37/52，另有 53） | 持平 |
| 主要主张 R1–R6 | R1 `supported_after_metric_fix`；R3 `boundary_partial_falsification`；R6 `boundary_anchor_gap` | R1 状态已更新 |
| 预注册协议 | PR1 / PR2 / PR3 / PR4 / PR5 / PR2b(拒绝) / **PR3_v2** | ↑ 新增 PR3_v2 |
| C1 cell 密化（PR5） | **FAIL**，`effect_size = 0.0`，三布局 AUC 全 0.5 | 新 |
| C3 rank 标签（PR3_v2） | **跨族 AUC 0.73–1.00**（synthetic 0.73–0.91 / ER 0.92–0.99 / 含真实锚点） | 新 |
| 新增交付物 | `metrics_fork/`、`docs/arxiv_methodology_short_paper_2026-10-16.md`、`docs/PAPER_DECISION_MEMO_2026-10-16.md`、`progress.json`、`boundary_atlas.json` | 新 |
| 工作区 | **有未提交改动**（`metrics_fork/` 等为 `??` 未跟踪） | ⚠️ |

---

## 二、上一阶段任务完成度：**100% 落地，且已超出**

上一轮（EPE，v2.91.0）提出的 E/S/M 方案，项目已全部执行并外扩：

| 上轮建议 | 落地状态 | 证据 |
|---|---|---|
| E1 双轴进度信号 | ✅ | `progress.json`（`divergent_claims=["R1"]`） |
| E4 边界图册 | ✅ | `boundary_atlas.json`（7 条边界知识） |
| S1/S2 R1 口径收窄 + C3/C1 入册 | ✅ | R1 → `supported_after_metric_fix` |
| **（外扩）** VRO 全栈 | ✅ | 命题图 Gate 48 / 收据 9 条 / 红队 Gate 49 / 徽章 Gate 50 / 预注册拒绝注册表 Gate 53 |
| **（外扩）** 论文出口三拆 | ✅ | P-2 / P-3(≡P-5) / P-4 短文 + 主线论文 |
| **（外扩）** `metrics_fork/` 最小公开分叉 | 🟡 **新增但损坏**（见 §三） |

**判定**：任务执行层面**无遗留**。真正的问题不在"做了没有"，而在"做出来的东西是否成立"——这正是 §三。

---

## 三、本轮最重要的新发现：`metrics_fork/` 不可复现，且无任何门禁守护

### 3.1 它是什么

`metrics_fork/` 是项目为绕开 D3（仓库公开）硬门槛而设计的**"最小只读公开分叉"**：只含 3 个纯 Python 度量脚本（`robustness.py` / `controllability.py` / `recovery.py`）+ 数据集指针清单 + 更宽松的 Apache-2.0 许可。它的全部存在理由，是让方法学短文能宣称"**读者 pull 下来跑三条命令，就能得到论文的数字，或者发现我们错在哪**"。

### 3.2 实测结果：三条"可复现命令"全部失败

按 `metrics_fork/README.md` §"Re-running the paper's numbers" 与短文 §5 逐条实测：

```
$ python -m metrics.robustness    --graph ../_f4_intervention_n100/artifact.json --k 3
FileNotFoundError: '../_f4_intervention_n100/artifact.json'
$ python -m metrics.controllability --graph ../generated_organisms/pcv2_5x8.json
FileNotFoundError: '../generated_organisms/pcv2_5x8.json'
$ python -m metrics.recovery      --graph ../_f2_recovery/artifact.json --k 5 --steps 20
FileNotFoundError: '../_f2_recovery/artifact.json'
```

**三层缺陷，逐层加重**：

| 层 | 问题 | 实测证据 |
|---|---|---|
| L1 路径错 | 引用 `artifact.json`，实际文件名是 `f4_intervention.json` / `f2_recovery_dynamics.json` | `ls _f4_intervention_n100/` → 只有 `f4_intervention.{csv,json}` |
| L2 形状错 | 即便改对文件名，脚本仍崩：`KeyError: 'edges'`——因为那些 JSON 是**结果文件**（`{"summary","all_results"}`），不是**图文件**（`{"nodes","edges"}`） | 实测 `KeyError: 'edges'` |
| L3 输入不存在 | `generated_organisms/pcv2_5x8.json` **在仓库中根本不存在**；`generated_organisms/` 下只有 `swarmlabs/sample_prov_v1.2.1.json` | `find . -name "pcv2_5x8*"` → 空 |

补充：全项目**唯一**具有顶层 `nodes`+`edges` 结构的 JSON 是 `claim_graph.json`（命题图，不是拓扑图）。README 声称"任何 flybrain-connectome 生成的 organism JSON 都可用"——该说法**未经任何实测支撑**。

### 3.3 更严重的问题：它完全无门禁守护

```
$ grep -rn "metrics_fork" --include=*.py --include=*.json .
→ 只有 data_manifest.json 自述 + metrics/__init__.py 的 docstring
→ 没有任何 gate / test / CI 引用它
```

**51 条门禁，没有一条检查 `metrics_fork` 能不能跑。** 这就是它能以损坏状态通过全部 47/47 门禁、并写进对外短文的原因。

### 3.4 为什么这条发现是"决定性"的

项目过去 4 次踩的是同一个坑——**度量不测其所称之物**（P1 伪结果 → S6；R2 分辨率预检 → S7；PR-2b 机制证伪 → S8；PR-1 扰动分析 → S9）。为此项目建了 S6–S9 四纪律、Gate 39 元门禁、Gate 48 命题图。

**但这一次，坑出现在"可复现性"本身**，而可复现性是项目对外所有主张（尤其三篇方法学短文）的**信用底座**：

- `docs/arxiv_methodology_short_paper_2026-10-16.md` §Abstract 明写："a reader who pulls the upstream artifact and runs the three commands gets the paper's numbers, or finds where we got them wrong."
- 该承诺**当前为假**。
- 且该短文尚未提交（git 未跟踪），意味着这个假承诺**还没发出去**——这是唯一的幸运。

**结论**：这不是一次"文档笔误"，而是**自验证体系的一个结构性盲区**：项目给"实验结论"装了门禁，却没给"复现声明"装门禁。而这恰恰是 2026-09 前沿（`arXiv:2605.06508` "artifact evaluation 主要检查 artifact 是否如声称那样工作"）点名的领域。

---

## 四、完整性评估

评分口径：0–100，仅评"该项自身完备度"，不评"是否先进"。

| 层 | 维度 | 分数 | 说明 |
|---|---|---|---|
| **底座** | 数据与锚定 | 90 | MaleCNS v1.0 锚点 + 116 功能单元 / 66 连接类型；锚定率约 32%（G5 未达标） |
| | 门禁体系 | **95** | 47/47 PASS；Gate 39 元纪律（100% 注入覆盖）；Gate 43–53 论文级门禁 |
| | 接口/工具 | 92 | MCP 47 工具、116 单元、`selfverify` 可 pip 安装独立包 |
| | 文档一致性 | 94 | 文档一致性门禁 PASS |
| **中层** | 命题/证据治理 | **88** | 命题图 + 收据 + 徽章 + 双轴进度；**但徽章测"装置"非"证据"（未修）** |
| | 可复现层 | **35** | 🔴 **`metrics_fork` 不可复现且无门禁**（本轮新降） |
| **上层** | 论文出口 | 70 | 4 个可发表单元素材齐，但均依赖 D3 或 metrics_fork |
| | 生态/影响力 | 25 | 无外部用户、无引用、无社区 |
| | 商业化 | 15 | 无路径 |
| **综合** | — | **约 72** | 较上轮（78）**下调**，主因是新增的"可复现层 35 分"暴露了此前被高估的上层 |

**结论不变且更尖锐**：**头重脚轻**——底座极硬，上层极软；且本轮发现连"对外层"（metrics_fork）也是软的。

---

## 五、科学先进性评估

沿用三级判定：**L1 工程 / L2 度量 / L3 理论**。

| 级别 | 判定 | 依据 |
|---|---|---|
| **L1 工程** | ✅ 强 | 51 门禁、元门禁、fail-closed、`selfverify` 独立包、VRO 全栈（命题图/收据/红队/徽章）。同侪中罕见 |
| **L2 度量** | 🟡 **到而部分不可用** | C3 rank 标签让机制跨族 AUC 达 0.73–1.00（**真进步**）；但**徽章 V0–V5 测的是"验证装置存在"而非"证据强度"**（R1 拿 V5 却挂 WEAK/FAIL）；**`metrics_fork` 连跑都跑不通** |
| **L3 理论** | ❌ 未达 | PR-2 因果 FAIL、PR-3 v1 跨族 NULL、C1 cell 密化 FAIL——项目自己已把"可预测结构理论"收敛为"项目合成空间的弱局部相关" |

**先进性定位**：先进性在**"科研方法学与元科学基础设施"**，不在"科学发现"。这与项目 v2.27 起的"方向转移"完全一致，且本轮进一步被 **C1 的双重闭合**（模块层 + cell 层）所确证。

---

## 六、国际化定位

真实坐标 = **L2「结构证据与度量层」+ 新增 L2.5「科研方法学/元科学基础设施层」**。

- **L2（结构证据与度量）**：国际空位，但连续四轮收窄。
- **L2.5（元科学基础设施）**：**这是项目真正的独特位置**——把预注册、负结果、预执行拒绝、命题图、收据、红队做成**机器门禁**，而非文档约定。

**与 2026 前沿的坐标对照**：

| 2026 前沿工作 | 它做了什么 | 项目的位置 |
|---|---|---|
| **RAGWarrant**（arXiv:2609.34179，2026-09-28） | "make release judgment executable… preserve negative outcomes… machine-readable decisions… validate public claims… reproducible containerized job" | **同期独立收敛到同一设计**——项目领先约半个身位（多了命题图 + 徽章 + 预执行拒绝类别） |
| **aiprov**（arXiv:2607.25637） | 把 claim 做成"机器可查证阶梯" | 项目的 Gate 43–47 + 命题图是其工程化实例 |
| **S6–S9 / PR-2b** | 无直接对标 | **项目独有** |
| **Agentic Auto-Research is Fuzz Testing**（arXiv:2608.09855） | 指出"反馈架构而非生成能力是瓶颈"，需要"稠密进度信号 + 受保护验证" | 项目已握 80% 原料，缺 holdout 保险库 |

**判定**：项目在**元科学基础设施**这条轴上，**与国际前沿同期、局部领先**；在**科学发现**轴上**明确不占优**且不应追。

---

## 七、国际竞品比较

| 竞品 | 基底 | 主张 | 项目 vs 它 |
|---|---|---|---|
| **flywireproject.com** | MaleCNS v1.0 | 全脑 spiking 仿真、逐 spike 可复算 | 项目不占优（重资产赛道，不正面竞争） |
| **KAIST**（arXiv:2610.10014） | MaleCNS | 固定拓扑 → 语言模型 +25pp | 项目不占优（任务增益轴） |
| **FLM** | 冻结 LLM | connectome 无优势（负结果） | 同向，但项目的方法学更系统 |
| **ConnectomeX / FlyVision**（arXiv:2610.08418） | 果蝇视觉连接组 | 连接组 → 通用视觉归纳偏置 | 项目不占优（架构轴），但可引用其"连接组即归纳偏置"论证 |
| **SCGFM**（arXiv:2605.08689） | 图基础模型 | 拓扑为中心的可迁移知识 | 不同层，可融合 |
| **RAGWarrant**（arXiv:2609.34179） | — | 可执行发布判定 + 保留负结果 | **最直接的同期竞品**；项目局部领先 |
| **arXiv:2605.06508**（artifact security eval） | — | AE 检查 artifact 是否如声称工作 | **本轮发现的镜子**：项目 metrics_fork 恰好"不如声称工作" |

**结论**：项目在**发现轴**（flywireproject/KAIST）不占优且不必追；在**元科学基础设施轴**（RAGWarrant/aiprov）**同期领先**；但在**可复现性轴**上，项目当前**低于** arXiv:2605.06508 所要求的底线。

---

## 八、技术壁垒与技术深度

### 8.1 真壁垒（按不可复制性排序）

| # | 壁垒 | 强度 | 代码级依据 |
|---|---|---|---|
| 1 | **元科学基础设施（门禁化的科研纪律）** | ★★★ | 51 门禁 + Gate 39 元门禁（100% 注入覆盖）+ Gate 43–47 论文级门禁 + Gate 48 命题图 + Gate 53 拒绝注册表 |
| 2 | **预执行拒绝类别（REJECT-BEFORE-RUN）** | ★★★ | `registry/preregistered_rejections.json` + Gate 47 + P-2 短文——**国际尚无可比实现** |
| 3 | **类型化结构证据库 + 锚定** | ★★ | 116 功能单元 / 66 连接类型 / MaleCNS 锚点 + `provenance.evidence_weight` |
| 4 | **双轴进度信号（装置 × 证据）** | ★★ | `scripts/compute_epistemic_progress.py` → `progress.json`（抓出 R1 装置/证据背离） |
| 5 | 结构指纹 / 故障隔离 | ★（**已降级**） | 隔离度量曾饱和；C1 进一步证伪计算增益 |

### 8.2 本轮深挖新增的一处"深度卡点"

项目深度卡在 L3 的根因，此前被描述为"不知道为何是 92.6%"。本轮精确定位为**两个不同层次的问题**：

1. **科学层**：`drop_magnitude` 家族在真实/通用图上趋近 null（PR-3 v1 FAIL）；C3 rank 标签只救回"族内可排序"，不恢复"跨族绝对阈值"。→ **机制是族内相对的，不是普适的。**
2. **工程层（新）**：**连"验证这套机制的工具"本身都没有被验证**——`metrics_fork` 无门禁、跑不通。

**第 2 条比第 1 条更值得警惕**：它说明项目的自验证纪律**尚未覆盖自身的基础设施**。项目反复证明"实验会被自己的纪律抓出问题"，但**从未证明"复现工具会被自己的纪律抓出问题"**。

### 8.3 壁垒的下一步方向

从"藏规则"转向"**可证伪性基础设施**"——把"验证层自身也接受验证"制度化。具体即：**为 `metrics_fork` 装一条门禁（拟 Gate 54），要求"文档里写的每条复现命令，必须真能跑出文档里写的数字"**。这条门禁一旦装上，就等于把本轮这个坑**永久封死**——这正是项目一贯的做法（把人工发现的问题固化成机器守住的边界）。

---

## 九、最新科技发展跟踪与技术融合

**2026-10 前后三条最强前沿，与本项目的对接**：

| 前沿 | 出处 | 对接点 | 建议 |
|---|---|---|---|
| **可执行发布判定 + 保留负结果 + 可复现打包** | RAGWarrant, arXiv:2609.34179 | 与 VRO 逐项同构 | **立即对标**：用它的 containerized job 思路修 `metrics_fork` |
| **AE 应检查"artifact 是否如声称工作"** | arXiv:2605.06508 | 本轮发现的直接镜像 | **立即内化**：成为 Gate 54 的设计依据 |
| **反馈架构是自主科研瓶颈** | arXiv:2608.09855 | 需要"稠密进度信号 + 受保护验证" | 项目已有进度信号（E1）；缺 holdout 保险库（E3） |
| 连接组→归纳偏置 | ConnectomeX, arXiv:2610.08418 | 可引用其论证支持"结构即先验" | 引用，不竞争 |
| 拓扑中心图基础模型 | SCGFM, arXiv:2605.08689 | 与 L3 目标同向 | **暂缓**（数据/算力重资产，判断正确） |
| 神经形态孪生 / 层级模块化储备池 | Nat Commun 2026-02 / 2026-07 | 恢复动力学、模块化↔记忆容量 | 保持引用，不作主线 |

**融合判定**：项目对"图基础模型""神经形态孪生"**暂缓**的判断**正确**；本轮新增的对接口是**"可复现打包与 artifact 自检"**——这是一个**零依赖、可立即落地**的融合点。

---

## 十、提升方案（P0 / P1 / P2）

### P0（本周，零外部依赖，直接封堵本轮发现）

| 编号 | 行动 | 验收标准 | 对应门禁 |
|---|---|---|---|
| **P0-1** | **修复 `metrics_fork` 三命令**：改路径 + 提供真实图输入（从 `_f4_intervention_n100/` 等导出 `nodes/edges` 图，或新增 `metrics_fork/graphs/` 样例图），并让 README 命令逐条可跑 | 三条命令输出与短文 §5.2–5.4 数字一致 | — |
| **P0-2** | **新增 Gate 54「复现声明自检」**：解析 `metrics_fork/README.md` 与短文中的命令，逐条执行，比对输出 | 任一命令失败 → 门禁报红 | **Gate 54** |
| **P0-3** | **给 Gate 54 配注入测试**（遵守 Gate 39 元纪律） | 注入坏路径 → Gate 54 必须 FAIL | Gate 39 |
| **P0-4** | **修正 `data_manifest.json` 事实错误**：`malecns-v1.0` 的 `display_name` 写成 "Male **C. elegans** CNS connectome"，而 `species` 写的是 Drosophila——对外清单里的硬伤 | 名称与物种一致 | 文档一致性门禁 |
| **P0-5** | **提交工作区**：`metrics_fork/`、短文、`progress.json`、`boundary_atlas.json` 均未跟踪 | 工作区干净 | — |

### P1（2–4 周，把自验证扩到"复现层"）

| 编号 | 行动 | 说明 |
|---|---|---|
| **P1-1** | **E3 holdout 保险库**（上轮遗留，最高价值） | 把"看到结果后改判据"从道德问题变成机器问题；2026 前沿点名要求 |
| **P1-2** | **E1b 阶梯语义门禁**：让 V0–V5 徽章的谓词与名称一致（当前 V1 称"reproducible"却只查"有条证据边"） | 修 §五 的 L2 缺陷 |
| **P1-3** | **G5 锚定率 32% → ≥50%** | 数据工程，抬升 L2 |
| **P1-4** | **RAGWarrant 对标**：把 `metrics_fork` 升级为 containerized reproducible job | 零依赖，提升可复现等级 |

### P2（1–3 月，科学层）

| 编号 | 行动 | 说明 |
|---|---|---|
| **P2-1** | 分级恢复动力学（F2 遗留）：把 `mean_recovery_steps` 64% 为 0 的问题做成**动力学曲线**（参考 Neuromorphic Twin） | 抬 L2 |
| **P2-2** | 结构可控性解析预测（F1）：把 AUC=0.775 的统计预测升级为解析预测 | 唯一现实通往 L3 的路 |
| **P2-3** | 跨族重标定：C3 rank 标签的族内相对性 → 给出"跨族如何重标定"的规程 | 收窄口径 |

---

## 十一、SCI 论文阶段判定

### 11.1 可发表单元清单

| 单元 | 形态 | 素材 | 阻塞项 | 可投性 |
|---|---|---|---|---|
| **P-2** 预注册拒绝 | 方法学短文 | ✅ 完整 | 需公开 `registry/` + 2 脚本 | 🟡 可投（需最小公开） |
| **P-3/P-5** 科研自验证四纪律 | 方法学短文 | ✅ 完整 | 需公开 Gate 30 相关脚本 | 🟡 可投（需最小公开） |
| **P-4** Resolution-Clamp Fixes | 方法学短文 | ✅ 完整 | 需公开最小子集 | 🟡 可投（需最小公开） |
| **新** Reproducible Preregistration as First-Class Object | 方法学短文 | ✅ 完整 | 🔴 **依赖 `metrics_fork`，当前跑不通** | 🔴 **不可投（直到 P0-1/2 完成）** |
| **主线论文** `arxiv_paper.md` | 完整论文（455 行，自评 89/100） | ✅ 92% | 🔴 D3 仓库私有 | 🔴 不可投 |

### 11.2 判定

> **尚未达到可投 SCI/arXiv 的状态，但距离从"缺仓库"变成了"缺一条门禁"。**

- **好消息**：四个方法学短文单元素材齐备；主线论文自评 89/100；项目已把"预注册 + 负结果 + 预执行拒绝"做成国际罕见的完整形态。
- **坏消息（本轮新增）**：**项目把"可复现"写进了摘要，却没能让可复现命令真的跑起来**。在 arXiv:2605.06508 的标准下，这属于"artifact 不 work as claimed"——**审稿人/读者第一条命令就会撞上 `FileNotFoundError`**。
- **性质判定**：这不是"再补实验"的问题，而是**"把已有能力接上验证电路"**的问题。P0-1 ~ P0-3 完成后，**"Reproducible Preregistration" 这篇短文即可投 arXiv（cs.CY / cs.LG）**，无需公开整仓。

### 11.3 三档目标

| 档 | 条件 | 当前差距 |
|---|---|---|
| **保底** | P-2 / P-3 / P-4 三篇方法学短文投 arXiv | 仅差"最小公开子集"（可只公开 `metrics_fork` + `registry/`） |
| **中档** | + Reproducible Preregistration 短文 | **差 P0-1/P0-2/P0-3（约 1 周）** |
| **高档** | 主线论文投 arXiv/期刊 | 差 D3 仓库公开（用户拍板）+ 结构可控性解析预测（P2-2） |

---

## 十二、如果只做三件事

1. **修 `metrics_fork` 并装 Gate 54**（P0-1/P0-2/P0-3）——把项目从"声称可复现"变成"机器证明可复现"，一周内可完成，零外部依赖，直接解锁一篇 arXiv 短文。
2. **建 holdout 保险库**（P1-1）——2026 前沿（arXiv:2608.09855）点名的"受保护验证"，是"远超市场"的确切落点。
3. **提交工作区**（P0-5）——`metrics_fork/` 等仍是未跟踪状态，工作区长期脏会掩盖真实状态（且本轮发现的损坏正是因为没有 commit、没有门禁、没有 CI 覆盖）。

---

## 附录 A：本轮实测证据索引

- 门禁：`python scripts/run_gates.py --quick` → 47/47 PASS（3m15s）
- `metrics_fork` 实测：三条命令 → `FileNotFoundError`；改用正确文件名 → `KeyError: 'edges'`
- `grep -rn "metrics_fork"` → 无任何 gate/test 引用
- `find . -name "artifact.json"` → 空；`find . -name "pcv2_5x8*"` → 空
- C1：`_c1_cell_densification/c1_results.json` → `verdict=FAIL, effect_size=0.0`
- C3：`_c3_rank_label_pr3v2/c3_results.json` → 跨族 AUC 0.73–1.00
- 命题状态：`research_claims.json` → R1 `supported_after_metric_fix` / R3 `boundary_partial_falsification` / R6 `boundary_anchor_gap`

## 附录 B：本报告与前几轮的关系

| 轮次 | 报告 | 核心新发现 |
|---|---|---|
| 1 | `SCI_READINESS_AND_ENHANCEMENT_2026-10-12.md` | 92.6% 机制未解；仓库私有 |
| 2 | `PROJECT_DEEP_DIVE_AND_ENHANCEMENT_2026-10-13.md` | 92.6% 是饱和二元量（阶跃函数） |
| 3 | `FRONTIER_VALUE_ENHANCEMENT_2026-10-14.md` | `mean_recovery_steps` 64% 为 0 |
| 4 | `PHASE_NEXT_EXECUTION_PLAN_2026-10-15.md` | 预注册把乐观结论证伪为"跨族 null" |
| 5 | `NEXT_STAGE_VISION_EPE_2026-10-16.md` | 徽章测"装置"非"证据"（R1 V5/E3 背离） |
| **6（本报告）** | `PROJECT_ASSESSMENT_AND_ENHANCEMENT_2026-10-16.md` | **`metrics_fork` 不可复现且无门禁——可复现层是自验证体系的盲区** |
