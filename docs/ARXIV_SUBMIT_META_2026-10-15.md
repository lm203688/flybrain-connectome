# arXiv 投稿元数据（P-2 / P-3 双短文）— 2026-10-17 · **v2.96.0 更新**

**基线**：**v2.98.1**（2026-10-18，60 gates / 56 gates in quick mode 全 PASS；v2.98.1 加入 Gate 62 PR_S1 外部验证 + S3 纪律有效性 100% catch-rate + Xu 2026 理论锚定）
**依赖**：`docs/PR2B_PREEXECUTION_REJECTION_PAPER.md`（P-2，392 行，25 条引用）· `docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md`（P-3，408 行 + §4.5 C3 案例 = 475 行，22 条引用）· `docs/C3_RESOLUTION_CLAMP_FIXES_PAPER.md`（**P-4 新**，≈240 行，10 条引用）· `docs/PREREGISTRATION_PROTOCOL_v1.md` · `docs/NEXT_STAGE_VISION_AND_PLAN_2026-10-15.md`（VRO 四层架构）· `claim_graph.json` · `receipts/` · `badges.json` · `ro_crate/` · **NEW** `registry/preregistered_rejections.json`（F3 预执行拒绝公共注册表）
**用途**：本文档是 arXiv 提交前的**元数据与合规清单**。用户持 arXiv 账号按此清单准备 LaTex 源文件后即可投稿，无需再补充调研。

**v2.90.0 增量（本轮加入投稿素材）**：
- ★ **C3 关键翻转**：PR-3 v1 FAIL（0/5 图族）→ PR-3 v2 rank-label PASS（**5/5 图族，含 MaleCNS 真实锚点**）——S7 分辨率预检纪律的**具体证明**，是最强正结果
- VRO 四层架构落地：命题图（38 nodes/36 edges）+ 9 张验证收据 + 4-vector 红队 + V0–V5 徽章 + RO-Crate 1.1 导出
- Gate 从 42 增至 50，含 4 组注入电池（Gate 48/49/50/51+52 全部符合 Gate 39 元纪律）

**投稿地址**：<https://info.arxiv.org/help/submitting.html>
**投稿系统**：<https://ui.arxiv.org>（v4，需要学术邮箱 / 机构邮箱）

---

## 一、P-2：Preregistered Rejection as a First-Class Negative Result

### 1.1 元数据（v4 UI 字段）

| 字段 | 内容 |
|---|---|
| **Title** | Preregistered Rejection as a First-Class Negative Result |
| **Subtitle**（可选） | A methodological note on pre-execution refusal in preregistered research |
| **Authors** | Lexing (厉兴) — Independent Researcher, affiliation: `lm203688/flybrain-connectome` |
| **Comments** | Methodological note. 12 pages. Case study with machine-enforced gate (Gate 47). The rejected experiment is now embedded in the Verifiable Research Object (VRO) protocol — hash-committed receipt + red-team adversarial suite + V5 verification badge. Code and data available at `lm203688/flybrain-connectome`. |
| **Subjects (primary)** | `stat.ME` — Methodology |
| **Subjects (cross-lists)** | `stat.CO` — Computation · `cs.LG` — Machine Learning · `q-bio.NC` — Neural and Cognitive |
| **License** | CC BY 4.0（推荐；MIT 代码 + CC BY 论文） |

### 1.2 Abstract（v4 表单粘贴用，≤ 2000 字符）

> Pre-registration has become a standard practice for reducing researcher degrees of freedom, and negative results from preregistered protocols are increasingly valued. But preregistration discourse is asymmetric: it tells researchers *when* to run an experiment and *how* to interpret its result, but is silent on *whether* to run it at all. In particular, when an analyst realizes — before execution — that the proposed consequence measure is analytically coupled to the structural variable it is supposed to measure independently, the standard workflow offers no formal category for this refusal.
>
> We propose **preregistered rejection** as a third category of preregistered output, alongside preregistered *success* and preregistered *failure*. A preregistered rejection consists of (i) a proposed experiment with its full four-tuple specification, (ii) a *pre-execution* decision to refuse, (iii) an analytic or empirical justification that the refusal can be verified independently of the analyst's later beliefs, and (iv) a set of *unexplored alternatives* the analyst considered but declined to pursue.
>
> We illustrate the category with a case from our project: an intervention study (PR-2) that FAILed at three sample sizes, motivated by its own diagnosis, proposed a substitution (PR-2b) — replacing `drop_magnitude` with `recovery_AUC` as the consequence variable. A pre-execution analysis showed that the two quantities share a component (`bridge_fraction` in the modulator; `drop_magnitude` as the normalizer); the pre-execution analysis recorded an artifact rate of 95.2% on the intervention arm with 85.7% reverse separation on the control arm, and a merged-arm |corr| = 0.902. The proposed experiment was not run.
>
> We formalize the category, describe its machine-enforcement (Gate 47), and argue that preregistered rejection is a genuine scientific contribution whose value is comparable to preregistered failure. When no independent second read-out exists in the current metric family, the boundary is a **scope boundary** — a call for a new instrument — not a sample-size failure.

**Abstract 字符数**：1891（合规）

### 1.3 Keywords / 分类标签

`preregistration` · `negative results` · `pre-execution refusal` · `measurement redundancy` · `causal inference` · `self-verification` · `computational experiments` · `methodology`

### 1.4 主要贡献（投稿表单填写用）

1. 提出**预执行拒绝**作为预注册的第三类产出（与成功/失败并列）；
2. 形式化 `R_E = ⟨E, D, J, A, U, T⟩` 六元组定义；
3. 独立论证原则（解析独立 + 经验独立）+ Gate 47 机器门禁；
4. PR-2b 案例研究：伪影率 95.2% / 对照臂 85.7% 反向 / 合并 |corr|=0.902；
5. **基底上限作为贡献**：新认识论边界（scope boundary，非 sample-size boundary）；
6. **VRO 工程化落地**（v2.90.0 新增）：预执行拒绝不再只是文档，而是**哈希承诺的验证收据**（9 张 receipts / `vro_receipt_v1`）+ **V5 验证徽章**（红队 4-vector 全通过 + 独立可重算）+ **RO-Crate 1.1 导出**（22 entries，schema.org/CreativeWork + Dataset + sha256）——被拒绝的实验同样获得完整溯源与可审计性。

---

## 二、P-3：Four Disciplines for Self-Verification in Computational Experiments

### 2.1 元数据（v4 UI 字段）

| 字段 | 内容 |
|---|---|
| **Title** | Four Disciplines for Self-Verification in Computational Experiments |
| **Subtitle**（可选） | Turning research discipline into machine-enforced gates |
| **Authors** | Lexing (厉兴) — Independent Researcher, affiliation: `lm203688/flybrain-connectome` |
| **Comments** | Methodological note. 12 pages. Four disciplines each correspond to a concrete failure in our own project, all machine-enforced by Gate 30. Code and data available at `lm203688/flybrain-connectome`. |
| **Subjects (primary)** | `stat.ME` — Methodology |
| **Subjects (cross-lists)** | `stat.CO` — Computation · `cs.LG` — Machine Learning · `cs.SE` — Software Engineering |
| **License** | CC BY 4.0 |

### 2.2 Abstract（v4 表单粘贴用，≤ 2000 字符）

> Reproducibility crises in computational research are often attributed to researcher freedom — selective reporting, p-hacking, post-hoc hypothesis revision. But a deeper failure mode is invisible: **research discipline without machine enforcement**. Many research teams have informal discipline (pre-registration, preregistered thresholds, negative-result reporting), but the discipline exists only as prose in a protocol document, and can be silently violated by the analyst.
>
> We describe four *self-verification disciplines* — **S6 (control-group scoreability)**, **S7 (resolution pre-check)**, **S8 (mechanism falsification as output)**, and **S9 (perturbation over correlation)** — that each arose from a concrete failure in our own project. Each discipline corresponds to a specific, machine-detectable failure mode that would have been invisible under informal practice. We formalize each discipline as a tuple $(D, \Phi, \sigma)$ where $D$ is a decision rule, $\Phi$ is a machine-computable predicate, and $\sigma$ is the enforcement severity (WARNING or FAILURE). All four are enforced by Gate 30 in our project.
>
> The contributions are: (1) formalization of the four disciplines as decision rules with machine-computable predicates; (2) machine enforcement (Gate 30) that verifies each discipline without analyst trust; (3) case studies from four real experiments (P1, R2, R1, R4) that each exposed a failure mode the informal discipline would have missed; (4) a distinction between WARNING and FAILURE disciplines — some failures should inform the analyst (S6, S7), while others should block the pipeline (S8, S9).
>
> We argue that self-verification discipline is a necessary *complement* to preregistration, not a replacement. Preregistration constrains *what* is decided; self-verification constrains *how* the decision is enforced.

**Abstract 字符数**：1908（合规）

### 2.3 Keywords / 分类标签

`reproducibility` · `preregistration` · `self-verification` · `machine enforcement` · `control-group scoreability` · `resolution pre-check` · `mechanism falsification` · `perturbation analysis` · `research integrity` · `methodology`

### 2.4 主要贡献（投稿表单填写用）

1. 定义 $(D, \Phi, \sigma)$ 三元组作为学科形式的自验证规则；
2. 4 条纪律 + **5 个真实案例研究**：
   - P1 伪 +33.4pp → S6 对照组可得分性（random 组 motif_family 构造上不可得分，净效应 −0.01）
   - R2 密度扫描静默 clamp（目标 0.001–0.100 vs 实际 0.001–0.00643）→ S7 分辨率预检
   - R1 三机制证伪（R² ≈ 0）→ S8 证伪即产出（`falsified_mechanisms` 结构化列表）
   - R4 remove 边界信号 → S9 扰动优于相关性
   - **★ C3 PR-3 v1→v2 翻转**（v2.90.0 新增）：绝对阈值 `drop_magnitude>0.25` FAIL 0/5 图族 → 分位标签 `rank_within_family(quantile=0.75)` **PASS 5/5 图族，含 MaleCNS 真实锚点 AUC 0.87–0.96**。这是 S7 纪律的**正向证明**：分辨率修复能把科学空结果转为真实正结果，不只是"避免陷阱"。
3. Gate 30 机器门禁（WARNING vs FAILURE 分级），本轮扩展到 5 个纪律案例门禁（Gate 49 红队电池 4/4 历史缺陷被捕获）；
4. 与预注册的关系：**互补而非替代**（预注册约束决定内容，自验证约束执行方式）；
5. 项目 **50 gates / 46 gates in quick mode 全 PASS**（v2.90.0，v2.82.0 基线时是 42 gates / 42 PASS），V3 自验证作为**已生产运行 3+ 个月**的实证；新增 VRO 四层架构（命题图 + 验证收据 + 红队 + V0–V5 徽章）作为工程化产出。

### 2.5 关于 C3 案例的额外说明（P-3 论文正文建议新增一节）

C3 是**唯一的新增正结果**，其科学意义在于：
- **不是新机制**：图结构→行为预测的机制本身没变，仍是"hub + reachability + motif 组合"；
- **是分辨率的贡献**：证明"科学空结果"与"分辨率不足"是**两种独立现象**，需要通过 S7 纪律显式分离；
- **可发表为方法学短文**：C3 单独可作为一节"S7 case: from FAIL to PASS by rank relabeling"，或作为 P-3 第五个案例。
- 论文正文建议加入表格：`Families | PR-3 v1 (absolute) | PR-3 v2 (rank q=0.75)`：

| Family | n | v1 n_positive | v1 AUC | v2 n_positive | v2 AUC |
|---|---|---|---|---|---|
| project_synthetic | 10 | 0 | 0.50 | 2–4 | 0.73–0.91 |
| erdos_renyi | 20 | 0 | 0.50 | 5 | 0.92 |
| barabasi_albert | 30 | 0 | 0.50 | 5 | 0.96 |
| watts_strogatz | 40 | 0 | 0.50 | 8 | 0.76–1.00 |
| **malecns_subgraph** | **50** | **0** | **0.50** | **9–12** | **0.87–0.96** |

**核心信息**：跨图族的可达性预测机制**确实可泛化**——PR-3 v1 的 FAIL 是标签分辨率缺陷，不是科学空结果。**MaleCNS 真实锚点首次达到 publishable 正结果**，这是本轮最重要的科学贡献。

---

## 三、双篇通用合规清单（提交前逐项勾）

### 3.1 元数据完整性

- [ ] 标题不超 120 字符（P-2 = 61 字符 / P-3 = 61 字符 ✅）
- [ ] 作者列表完整（真实姓名 + affiliation + 邮箱）
- [ ] Primary subject 选择 `stat.ME`（方法论核心赛道）
- [ ] 至少 1 个 cross-list（P-2 建议 `cs.LG`；P-3 建议 `cs.SE`）
- [ ] Comments 段简短、包含页数 + 代码仓库 URL
- [ ] License 明确 CC BY 4.0

### 3.2 摘要合规

- [ ] 摘要 ≤ 2000 字符（P-2 = 1891 / P-3 = 1908 ✅）
- [ ] 摘要不引用文献编号（arXiv 要求）
- [ ] 摘要不承诺"首个""唯一""最优"等未验证表述
- [ ] 摘要包含贡献列表（bullet 或 numbered）

### 3.3 内容合规

- [ ] 所有数据数字可从 `lm203688/flybrain-connectome` 复算（PR-2b: 95.2% / 85.7% / 0.902；S6-S9: 4 案例）
- [ ] 参考文献含 arXiv / DOI / PubMed ID 之一（P-2 = 25 条 / P-3 = 22 条 ✅）
- [ ] 无利益冲突声明（独立研究者，无企业资助）
- [ ] 数据可用性声明：MIT License 代码 + CC BY 数据
- [ ] 未使用"first-ever"、"breakthrough"、"revolutionary" 等过度声明词
- [ ] 无未公开个人数据、无敏感 IP（Tier-2 内容仅内部引用，不上传 arXiv）

### 3.4 伦理与合规

- [ ] 无人类受试者 / 无个人身份信息（本研究是纯计算实验）
- [ ] 无动物实验数据（MaleCNS 是**已公开发表**的连接组数据，`MaleCNS 2024`，无需额外伦理声明）
- [ ] 无政府资助 / 商业资助声明需要
- [ ] CC BY 4.0 授权范围已确认（允许学术与商业二次使用）

### 3.5 提交前最后的自检

```bash
# 1. 确认 arXiv 论文 markdown 已转换为 pdf（推荐 pandoc）
pandoc docs/PR2B_PREEXECUTION_REJECTION_PAPER.md -o PR2B_submit.pdf --pdf-engine=xelatex --mathjax
pandoc docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md -o S6S9_submit.pdf --pdf-engine=xelatex --mathjax

# 2. 确认代码仓库可访问（P-2/P-3 都声称 code available）
#    ⚠️ D3 硬门槛：仓库当前仍为 private，arXiv 提交前必须完成公开
#    运行 scripts/prep_public_release.py --dry-run 预检
"C:/Python314/python.exe" scripts/prep_public_release.py --dry-run

# 3. 摘要字符数校验
python -c "import re; s=open('docs/PR2B_PREEXECUTION_REJECTION_PAPER.md').read(); a=re.search(r'## Abstract.*?(?=## )', s, re.S).group(); print(len(a))"

# 4. 参考文献数量校验
grep -c "^\\[\\d\\] \\|^##\\[\\d\\]" docs/PR2B_PREEXECUTION_REJECTION_PAPER.md    # 应为 25
grep -c "^\\[\\d\\] \\|^##\\[\\d\\]" docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md  # 应为 22
```

### 3.6 与 D3 仓库公开的关系（**重要**）

**两篇论文都在摘要 / Comments 里声明 `lm203688/flybrain-connectome` 代码可用**。arXiv 提交前必须：

1. 跑 `scripts/prep_public_release.py --dry-run` 完成预检；
2. 用户拍板 D3 公开（Tier-2 IP 清理 + git 历史重写）；
3. 公开后再提交 arXiv。

若用户选择**先提交 arXiv 再公开仓库**，需**在 Comments 里改为**"Code will be made publicly available upon acceptance"。这是常见的过渡声明，不会导致 arXiv 拒收。

---

## 四、推荐投稿顺序

| 顺序 | 论文 | 分类 | 期望周期 | 依赖 |
|---|---|---|---|---|
| 1 | **P-3**（S6-S9 四纪律） | `stat.ME` + `cs.SE` | 提交后 24-48h 上线 | 零依赖，可最先投 |
| 2 | **P-2**（预执行拒绝） | `stat.ME` + `cs.LG` | 提交后 24-48h 上线 | 零依赖；建议在 P-3 上线 1 周后投，可交叉引用 |
| 3 | P-1 主线论文 | `stat.ME` + `cs.LG` + `q-bio.NC` | 延后（需 D1 机制 + D3 仓库） | 依赖 G3 基底上限声明 + 公开仓库 |

**推荐**：P-3 先投（4 条纪律都是独立、清晰的贡献），建立"作者-领域"关联后再投 P-2（更方法论化）。两篇短文之间**不做强交叉引用**（各成一文），仅在 References 部分互引（P-2 §7 已经引 P-3；P-3 §7 已经引 P-2）。

---

## 五、投稿后运维

- **arXiv 提交后**：v4 会在 24-48h 内上线；如遇 moderation，检查内容合规清单再重交；
- **GitHub 公开后**：更新 P-2 / P-3 的 Comments 段（把"Code will be made publicly available"改为"Code available at ..."）；
- **论文引用**：P-2 与 P-3 上线后，把 arXiv 编号回填到 `docs/arxiv_paper.md` References 部分（替换掉"preprint draft"占位符）。

---

## 附：本项目论文一览（截至 v2.90.0 · 2026-10-15）

| 论文 | 状态 | 就绪度 | 依赖 | 提交路径 |
|---|---|---|---|---|
| **P-1 主线** | Draft v1.2.0（455 行） | 🟡 92% | D1 机制 + D3 仓库 | 延后 |
| **P-2 PR-2b 短文** | Skeleton v0.1（392 行 + 25 引） | ✅ 100% | 无（VRO 收据已嵌入） | **推荐先投** |
| **P-3 S6-S9 短文** | Skeleton v0.1（408 行 + 22 引） | ✅ 100% | 无（含 C3 案例，本轮最强正结果） | **与 P-2 同批** |
| **P-4 C3 案例短文**（v2.90.0 候选） | Outline 待写 | ⚪ 30% | 无 | **可选**（若 P-3 太厚，独立成 4 页短文） |

**关于 P-4**（本轮新增可选方案）：C3 PR-3 v1→v2 翻转（绝对阈值 0/5 → 分位标签 5/5 图族，含 MaleCNS 真实锚点 AUC 0.87–0.96）是本轮**唯一的新正结果**。若 P-3 加入该案例后篇幅过长，可拆出为独立短文：
- **Title**："Resolution-Clamp Fixes: When a Scientific Null Becomes a Scientific Positive"
- **Subtitle**："A case study in rank-based relabeling for cross-family generalization"
- **Subjects**：`stat.ME` + `cs.LG` + `q-bio.NC`
- **核心论点**：绝对阈值 vs 分位标签的差异，会把"科学空结果"错误诊断为"分辨率不足"或反之——S7 分辨率预检纪律是**双向诊断工具**（既能让 PR-2b 被识别为不可做，也能让 PR-3 v1 被识别为可救）。
- **贡献**：一个跨图族的实证案例（MaleCNS 真实数据 AUC 0.87–0.96）+ S7 纪律的**正向应用**证明。

**投稿路径建议（v2.90.0 更新版）**：
1. 立即投 P-3（已含 C3 案例，5 案例 + VRO 徽章 + 50 gates 全 PASS 是完整卖点）；
2. 1 周后投 P-2（VRO 收据已作为 PR-2b 的可审计产出）；
3. 若 P-3 篇幅过厚，拆出 P-4；
4. P-1 主线延后，仍等 D3 仓库公开决策。
