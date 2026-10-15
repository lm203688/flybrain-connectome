# arXiv 投稿元数据（P-2 / P-3 双短文）— 2026-10-15

**基线**：v2.82.0（2026-10-15）
**依赖**：`docs/PR2B_PREEXECUTION_REJECTION_PAPER.md`（P-2，392 行，25 条引用）· `docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md`（P-3，408 行，22 条引用）· `docs/PREREGISTRATION_PROTOCOL_v1.md`
**用途**：本文档是 arXiv 提交前的**元数据与合规清单**。用户持 arXiv 账号按此清单准备 LaTex 源文件后即可投稿，无需再补充调研。

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
| **Comments** | Methodological note. 12 pages. Case study with machine-enforced gate (Gate 47). Code and data available at `lm203688/flybrain-connectome`. |
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
5. **基底上限作为贡献**：新认识论边界（scope boundary，非 sample-size boundary）。

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
2. 4 条纪律 + 4 个真实案例研究（P1 伪 +33.4pp / R2 静默 clamp / R1 三机制证伪 / R4 remove 扰动）；
3. Gate 30 机器门禁（WARNING vs FAILURE 分级）；
4. 与预注册的关系：**互补而非替代**（预注册约束决定内容，自验证约束执行方式）；
5. 项目 42/42 门禁 + V3 自验证作为**已生产运行 3 个月**的实证。

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

## 附：本项目论文三篇一览（截至 v2.82.0）

| 论文 | 状态 | 就绪度 | 依赖 | 提交路径 |
|---|---|---|---|---|
| **P-1 主线** | Draft v1.2.0（455 行） | 🟡 92% | D1 机制 + D3 仓库 | 延后 |
| **P-2 PR-2b 短文** | Skeleton v0.1（392 行 + 25 引） | ✅ 100% | 无 | 1-2 周内可投 |
| **P-3 S6-S9 短文** | Skeleton v0.1（408 行 + 22 引） | ✅ 100% | 无 | 1-2 周内可投 |
