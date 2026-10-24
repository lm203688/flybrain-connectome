# A 腿 arXiv 投稿分步指南 — 2026-10-19

> 目标：本周内完成 P-3 → P-2 两篇方法学短文向 arXiv 的提交。
> 全部 0 元。全流程约 3-4 小时（含安装工具）。
> 依据：`docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md` §4 checklist。

---

## 阶段 0 — 环境准备（约 30 分钟，只做一次）

### 0.1 安装 pandoc（Markdown → PDF 转换器）

Windows 上三种任选其一：

**方案 A（推荐）：winget**
```powershell
winget install --id JohnMacFarlane.Pandoc --accept-source-agreements --accept-package-agreements
```

**方案 B：官方安装包**（下载后一路下一步）
https://github.com/jgm/pandoc/releases/latest

**方案 C：Chocolatey**（如已装 choco）
```powershell
choco install pandoc -y
```

### 0.2 安装 TeX 发行版（PDF 生成引擎）

pandoc 生成 PDF 需要一个 TeX 引擎。推荐 **TinyTeX**（~100 MB，最小可用）：

```powershell
# 方案 A（推荐）：直接下载批处理安装脚本
Invoke-WebRequest "https://tinytex.yihui.org/install-bin-windows.bat" -OutFile "install_tinytex.bat"
.\install_tinytex.bat
```

安装目录 `%APPDATA%\TinyTeX`（约 `C:\Users\<你>\AppData\Roaming\TinyTeX`）。
装完把 `%APPDATA%\TinyTeX\bin\windows` 加入 PATH：
```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path","User") + ";$env:APPDATA\TinyTeX\bin\windows",
  "User"
)
# 关掉重开 PowerShell 生效
```

**方案 B：Chocolatey**（若已装 choco）
```powershell
choco install tinytex -y
```

**方案 C：Chocolatey 装 MiKTeX**（~300 MB，装完后按需自动下载包，最省心，但体积大）
```powershell
choco install miktex -y
```

或者用 **MiKTeX 官网**下载：https://miktex.org/download

**验证**（新开的 PowerShell 窗口）：
```powershell
pandoc --version    # 应显示 3.x
xelatex --version   # 应显示 XeTeX 3.x
```

若 `xelatex` 找不到，手动补 PATH（临时，仅当前会话）：
```powershell
$env:Path += ";$env:APPDATA\TinyTeX\bin\windows"
```

### 0.3 验证仓库状态（30 秒）

在浏览器打开：https://github.com/lm203688/flybrain-connectome
- 右上角确认显示 `Public`
- 顶部 tag 列表确认最新为 `v2.98.1`

---

## 阶段 1 — 生成 PDF（约 3 分钟，无需 TinyTeX）

**2026-10-19 实测最优路径**：pandoc 转 HTML + Edge 无头模式转 PDF。
**只依赖 pandoc + Windows 自带 Edge，无需装 TinyTeX / MiKTeX**。

### 1.1 补 pandoc 到 PATH（若已装）

```powershell
$env:Path = "$env:USERPROFILE\AppData\Local\Pandoc;$env:Path"
pandoc --version    # 应显示 3.x
```

### 1.2 生成 HTML（styles_arxiv.css 已在仓库根目录）

```powershell
cd C:\Users\Xing\Desktop\flybrain-connectome

# P-3
pandoc docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md `
  -o P3_submit.html `
  --standalone --toc --toc-depth=3 --number-sections `
  --metadata title="Four Disciplines for Self-Verification in Computational Experiments" `
  --metadata author="Li Xing" --metadata date="2026-10-19" --metadata lang=en `
  --syntax-highlighting=none -c styles_arxiv.css

# P-2
pandoc docs/PR2B_PREEXECUTION_REJECTION_PAPER.md `
  -o P2_submit.html `
  --standalone --toc --toc-depth=3 --number-sections `
  --metadata title="Preregistered Rejection as a First-Class Negative Result" `
  --metadata author="Li Xing" --metadata date="2026-10-19" --metadata lang=en `
  --syntax-highlighting=none -c styles_arxiv.css
```

### 1.3 HTML → PDF（Edge 无头模式）

**关键**：`--print-to-pdf` 参数必须用**绝对路径**（相对路径会 0x5 权限拒绝）。

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless --disable-gpu --no-sandbox --no-pdf-header-footer `
  --print-to-pdf="C:\Users\Xing\Desktop\flybrain-connectome\P3_submit.pdf" `
  "file:///C:/Users/Xing/Desktop/flybrain-connectome/P3_submit.html"

& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless --disable-gpu --no-sandbox --no-pdf-header-footer `
  --print-to-pdf="C:\Users\Xing\Desktop\flybrain-connectome\P2_submit.pdf" `
  "file:///C:/Users/Xing/Desktop/flybrain-connectome/P2_submit.html"
```

### 1.4 产出（2026-10-19 实测）

| 文件 | 大小 | 页数 |
|---|---|---|
| `P3_submit.pdf` | 523 KB | **18 页** |
| `P2_submit.pdf` | 434 KB | **16 页** |

### 1.5 备选：手动浏览器打印

若 Edge 无头模式有问题：双击 HTML → Ctrl+P → 另存为 PDF。

---

## 阶段 1（旧方案：pandoc + xelatex，仅当 TinyTeX 已装时用）

**先做 P-3**（`S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md`，475 行）：

```powershell
cd C:\Users\xing\Desktop\flybrain-connectome
pandoc docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md `
  -o P3_submit.pdf `
  --pdf-engine=xelatex `
  --toc --toc-depth=3 `
  --number-sections `
  --metadata title="Four Disciplines for Self-Verification in Computational Experiments" `
  --metadata author="Li Xing" `
  --metadata lang=zh `
  --standalone `
  --mathjax
```

**再做 P-2**（`PR2B_PREEXECUTION_REJECTION_PAPER.md`，392 行）：

```powershell
pandoc docs/PR2B_PREEXECUTION_REJECTION_PAPER.md `
  -o P2_submit.pdf `
  --pdf-engine=xelatex `
  --toc --toc-depth=3 `
  --number-sections `
  --metadata title="Preregistered Rejection as a First-Class Negative Result" `
  --metadata author="Li Xing" `
  --metadata lang=zh `
  --standalone `
  --mathjax
```

**如果 xelatex 报错缺包**，MiKTeX 会自动下载；TinyTeX 需手动补：
```powershell
tlmgr install fontspec xecjk titlesec
```

**产出**：
- `P3_submit.pdf`（预计 15-25 页）
- `P2_submit.pdf`（预计 12-20 页）

**打开检查**：PDF 应含标题、目录、参考文献。若参考文献显示 `[1] [2]` 而非具体文献名，说明 Markdown 引用块格式需调整。

---

## 阶段 2 — arXiv 账号与首次投稿准备（约 10 分钟）

### 2.1 创建/登录 arXiv 账号

打开：https://info.arxiv.org/help/createaccount.html

- 邮箱建议用个人常用邮箱（非 Gmail Plus 更好）
- 首次登录需等待 24-72 小时审核（arXiv 反垃圾机制）

### 2.2 类别选择说明

**P-3 主类别 `stat.ME`**（Methodology & Statistics）：
- https://arxiv.org/help/subjects#stat
- **首次投稿无需背书**（stat 大类免背书）

**P-2 主类别 `stat.ME`**：同上，免背书

**交叉列出**：
- `cs.LG`（Machine Learning）— 无需背书
- `q-bio.NC`（Neural & Cognitive）— **首次投稿需 1 名既有作者背书**
  - 背书来源：任何已在 arXiv 发表过文章的作者（可邮件请求）
  - 或：先只提 `stat.ME + cs.LG`（无背书门槛），后续修订时补 `q-bio.NC`

**建议**：首次投稿先只列 `stat.ME + cs.LG`，等 P-3 通过后再修订加 `q-bio.NC`。

---

## 阶段 3 — 提交 P-3（约 20 分钟）

### 3.1 打开 arXiv 提交页

浏览器打开：https://arxiv.org/help/submit

点击 **Submit New Preprint**。

### 3.2 填写元数据（来源：`docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md` §1）

**Title**:
```
Four Disciplines for Self-Verification in Computational Experiments
```

**Subtitle**（可选）:
```
Turning research discipline into machine-enforced gates
```

**Authors**:
```
Li Xing
```
机构：`Independent Researcher` / 邮箱：`lm203688@users.noreply.github.com`

**Abstract**（1,800 字符以内，从 submission_meta.json 复制）:
```
Reproducibility crises in computational research are often attributed
to researcher freedom — selective reporting, p-hacking, post-hoc
hypothesis revision. But a deeper failure mode is invisible: research
discipline without machine enforcement. Many research teams have
informal discipline (pre-registration, preregistered thresholds,
negative-result reporting), but the discipline exists only as prose
in a protocol document and can be silently violated by the analyst.

We describe four self-verification disciplines — S6 (control-group
scoreability), S7 (resolution pre-check), S8 (mechanism falsification
as output), and S9 (perturbation over correlation) — that each arose
from a concrete failure in our own project. Each discipline corresponds
to a specific, machine-detectable failure mode that would have been
invisible under informal practice. We formalize each discipline as a
tuple (D, Φ, σ) where D is a decision rule, Φ is a machine-computable
predicate, and σ is the enforcement severity (WARNING or FAILURE). All
four are enforced by Gate 30 in our project.

The contributions are: (1) formalization of the four disciplines as
decision rules with machine-computable predicates; (2) machine
enforcement (Gate 30) that verifies each discipline without analyst
trust; (3) case studies from five real experiments (P1, R2, R1, R4, C3
PR-3 v1→v2 flip) that each exposed a failure mode the informal
discipline would have missed; (4) a discipline-effectiveness
quantification via mutation-injection: 51/51 injections caught
(100.0%, Wilson 95% CI [93.0%, 100.0%]) at v2.98.1 after closing all
seven residual gate weaknesses enumerated at v2.98.0 baseline; (5) a
distinction between WARNING and FAILURE disciplines.

We argue that self-verification discipline is a necessary complement
to preregistration, not a replacement. Preregistration constrains what
is decided; self-verification constrains how the decision is enforced.
```

**Comments**:
```
Methodological note. 12 pages. Four disciplines each correspond to a
concrete failure in our own project, all machine-enforced by Gate 30.
Includes S6-S9 case studies with quantified effectiveness (16/34 = 47.1%
at v2.98.0 submission baseline, Wilson 95% CI [31.5%, 63.3%]; 51/51 =
100.0% at v2.98.1 post-submission hardening, Wilson 95% CI [93.0%,
100.0%]). Code and data at lm203688/flybrain-connectome (v2.98.1,
public since 2026-10-18). 60 gates PASS in full mode.
```

**License**: `CC-BY-4.0`

### 3.3 类别选择

- **Primary**: `stat.ME`（Methodology & Statistics）
- **Cross-lists**: 勾选 `cs.LG`（Machine Learning）
- **暂不勾** `q-bio.NC`（需背书，后续修订时加）

### 3.4 上传文件

点击 **Attach source files**：
- 首选：直接上传 `P3_submit.pdf`（PDF-only 提交）
- 备选：把 P-3 Markdown 源码打包成 `P3_source.tar.gz` + PDF 一起传

**注意**：
- 文件名不能有中文或空格
- 总大小上限 50 MB
- 单文件不超过 35 MB

### 3.5 提交前 5 项自检

```
□ PDF 能正常打开、目录正确、参考文献完整
□ 无 "first-ever / breakthrough / revolutionary" 等浮夸表述
□ License 明确标注 CC-BY-4.0
□ 代码 URL 可访问（https://github.com/lm203688/flybrain-connectome）
□ 无个人敏感信息（邮箱、公司名、未发表数据）
```

### 3.6 点击 Submit

- 提交后你会收到邮件确认（发件人：`noreply@arxiv.org`）
- 状态：**Submitted** → **Moderated**（24-72h） → **Accepted / Returned**
- 若 Accepted：arXiv ID 形如 `2610.XXXXX`
- 若 Returned：修改后按邮件说明重提

---

## 阶段 4 — 提交 P-2（约 20 分钟，流程同 P-3）

元数据同阶段 3，仅替换以下字段：

**Title**: `Preregistered Rejection as a First-Class Negative Result`

**Subtitle**: `A methodological note on pre-execution refusal in preregistered research`

**Abstract**（从 submission_meta.json 复制）:
```
Pre-registration has become standard practice for reducing researcher
degrees of freedom, and negative results from preregistered protocols
are increasingly valued. But preregistration discourse is asymmetric:
it tells researchers when to run an experiment and how to interpret
its result, but is silent on whether to run it at all. In particular,
when an analyst realizes — before execution — that the proposed
consequence measure is analytically coupled to the structural variable
it is supposed to measure independently, the standard workflow offers
no formal category for this refusal.

We propose preregistered rejection as a third category of
preregistered output, alongside preregistered success and
preregistered failure. A preregistered rejection consists of (i) a
proposed experiment with its full four-tuple specification, (ii) a
pre-execution decision to refuse, (iii) an analytic or empirical
justification that the refusal can be verified independently of the
analyst's later beliefs, and (iv) a set of unexplored alternatives the
analyst considered but declined to pursue.

We illustrate the category with a case from our project: an
intervention study (PR-2) that FAILed at three sample sizes, motivated
by its own diagnosis, proposed a substitution (PR-2b) — replacing
drop_magnitude with recovery_AUC as the consequence variable. A
pre-execution analysis showed that the two quantities share a
component (bridge_fraction in the modulator; drop_magnitude as the
normalizer); the pre-execution analysis recorded an artifact rate of
95.2% on the intervention arm with 85.7% reverse separation on the
control arm, and a merged-arm |corr| = 0.902. The proposed experiment
was not run.

We formalize the category, describe its machine-enforcement (Gate 47),
and argue that preregistered rejection is a genuine scientific
contribution whose value is comparable to preregistered failure. When
no independent second read-out exists in the current metric family, the
boundary is a scope boundary — a call for a new instrument — not a
sample-size failure.
```

**Comments**（同 P-3 格式，替换页数与主题）：
```
Methodological note. 12 pages. Case study with machine-enforced gate
(Gate 47). Preregistered rejection is embedded in the Verifiable
Research Object (VRO) protocol: hash-committed receipt, red-team
adversarial suite, V5 verification badge, RO-Crate 1.1 export. Code
and data at lm203688/flybrain-connectome (v2.98.1, public since
2026-10-18). 60 gates PASS in full mode. Companion submission (P-3)
reports the discipline-effectiveness numbers quoted here; both
submissions pinned to v2.98.1.
```

上传 `P2_submit.pdf`，其余同阶段 3.3-3.6。

---

## 阶段 5 — 提交后回填（约 10 分钟）

### 5.1 等 24-72h arXiv 审核

- 若 Accepted：邮件含 arXiv IDs（`2610.XXXXX`, `2610.YYYYY`）
- 若 Returned：按邮件说明修改（常见：类别错误、内容合规、格式问题）

### 5.2 回填主线论文

编辑 `docs/arxiv_paper.md` References 段，添加：
```
15. Li Xing. Four Disciplines for Self-Verification in Computational
    Experiments. arXiv:2610.XXXXX [stat.ME], 2026.
16. Li Xing. Preregistered Rejection as a First-Class Negative Result.
    arXiv:2610.YYYYY [stat.ME], 2026.
```

### 5.3 回填 P-2 / P-3 互相引用

- P-2 §6 引用 P-3：`arXiv:2610.XXXXX`
- P-3 §5 讨论段引用 P-2：`arXiv:2610.YYYYY`

### 5.4 版本 bump

在 `CHANGELOG.md` 顶部新增：
```
## v2.99.0 (2026-10-19)

- arXiv submissions: P-3 (2610.XXXXX), P-2 (2610.YYYYY)
- B-leg tasks tracked in docs/B_LEG_COMPLETION_CHECKLIST_2026-10-19.md
```

`pyproject.toml` / `flybrain_cli.py` / `api_server.py` / `server.py` / `aibom.json` 版本号全部 `2.98.1` → `2.99.0`（7 处）。

跑门禁：
```powershell
python scripts/run_gates.py --quick
python scripts/run_gates.py --with-data
```

推送（走 Contents API）：
```powershell
python scripts/gh_publish.py --commit "<新commit>"
```

---

## 关键链接汇总

| 用途 | URL |
|---|---|
| **arXiv 提交入口** | https://arxiv.org/help/submit |
| **arXiv 账号创建** | https://info.arxiv.org/help/createaccount.html |
| **arXiv 首次投稿说明** | https://info.arxiv.org/help/first_submission.html |
| **arXiv 提交 FAQ** | https://info.arxiv.org/help/submit_faq.html |
| **arXiv 类别说明 (stat.ME)** | https://arxiv.org/help/subjects#stat |
| **arXiv 类别说明 (cs.LG)** | https://arxiv.org/help/subjects#cs |
| **arXiv 类别说明 (q-bio.NC)** | https://arxiv.org/help/subjects#q-bio |
| **arXiv License 选择** | https://info.arxiv.org/help/licenseindex.html |
| **pandoc 官方下载** | https://github.com/jgm/pandoc/releases |
| **pandoc Windows winget** | `winget install --id JohnMacFarlane.Pandoc` |
| **TinyTeX 主站** | https://yihui.org/tinytex/ |
| **TinyTeX Windows 批处理** | https://tinytex.yihui.org/install-bin-windows.bat |
| **TinyTeX Windows PowerShell** | https://tinytex.yihui.org/install-bin-windows.ps1 |
| **MiKTeX 下载** | https://miktex.org/download |
| **TeX Live 在线安装** | https://tug.org/texlive/acquire-netinstall.html |
| **arXiv 源文件命名规范** | https://info.arxiv.org/help/submit_faq.html#naming |
| **Code URL（本项目）** | https://github.com/lm203688/flybrain-connectome |
| **项目 CHANGELOG** | https://github.com/lm203688/flybrain-connectome/blob/main/CHANGELOG.md |
| **项目 LICENSE** | https://github.com/lm203688/flybrain-connectome/blob/main/LICENSE |
| **B 腿任务清单** | `docs/B_LEG_COMPLETION_CHECKLIST_2026-10-19.md` |

---

## 常见问题

**Q1: pandoc 报错 `xelatex not found`？**
A: 没装 TeX 发行版，或装了没加 PATH。按阶段 0.2 装 TinyTeX，或临时：
```powershell
$env:Path += ";$env:APPDATA\TinyTeX\bin\windows"
```

**Q2: arXiv 说我的第一次投稿需要 endorsement？**
A: 只勾 `stat.ME + cs.LG`（免背书），先不提 `q-bio.NC`。等 P-3 通过后修订时再加 `q-bio.NC`。

**Q3: PDF 参考文献显示为空 `[1]`？**
A: Markdown 引用块用了 pandoc 的 `@key` 格式，需在 pandoc 命令加 `--filter pandoc-citeproc`，或在 References 段手工编号。

**Q4: PDF 太长（>30 页）？**
A: 单篇上限 60 MB，页数无硬上限。但建议 ≤ 30 页可读性更好。

**Q5: 修改已提交的稿件？**
A: 提交新修订版（v2, v3），旧版本仍保留。arXiv 支持无限修订。

**Q6: 提交后多久被 Accept？**
A: 通常 24-72 小时。周末提交会顺延到下个工作日。

**Q7: 提交被 Return 怎么办？**
A: 按邮件修改后重提。常见原因：
- License 未明确选择 → 选 CC-BY-4.0
- 类别错误 → 主类别和交叉类别要匹配内容
- 内容合规问题 → 检查有无未发表数据、个人隐私

**Q8: 提交后要付费吗？**
A: arXiv 100% 免费，全类别免 APC。只有走 SCI 期刊的 Open Access 通道才付 APC（$2,295-$4,390）。
