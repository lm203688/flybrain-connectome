# 科学先进性评估与 SCI 就绪度专项报告（第 13 轮）

**基线**：`flybrain-connectome` v2.94.0（CHANGELOG 顶 = pyproject；工作区有 **28 个未提交改动** + 3 个新文件，git HEAD `1d33f89`）
**门禁实测**（2026-10-17 06:30，`run_gates.py --quick`，3m58s）：**GATES: FAIL — gate46 recovery dynamics, gate49 red-team battery**（其余 54/56 全 PASS）
**本轮焦点**：科学先进性评估 + 是否达到 SCI 论文阶段 + 达到 SCI 的具体路径
**评估方法**：全量重扫 + 代码级实测（每个结论附文件与行号），不采信任何旧数字

---

## 零、一句话结论

> **一夜之间项目响应了上轮报告：N1（gate57 白名单修复）落地转 PASS、fail-loud 纪律铺开全仓、K8/K10 起步——但 K6 改名是半成品：`dynamics.py` 一个 docstring 错位让 selfverify 包当场不可导入（gate49 崩），F2 数据未随改名迁移让 gate46 崩。SCI 就绪度较上轮倒退：54/56 且两个失败是 checker 自身崩溃，不是科学裁决。**
>
> **科学先进性本身未受损**：C3 跨 5 图族正结果（含真实锚点 MaleCNS 0.87–0.96）、C1 诚实负结果双重闭合、EPE 双轴自检——三项核心资产全部完好。A 面（科研自验证基础设施）仍处国际第一梯队。
> **当前唯一可立即执行的 SCI 出口是 P-4/P-5 两篇方法学短文**（素材齐、不依赖损坏的 selfverify、不依赖 D3）；主线论文维持 0 投稿资格。

---

## 一、本轮实测基线（2026-10-17 06:30 现场复测）

| 维度 | 实测值 | 对比昨夜（10-16 深夜） |
|---|---|---|
| 包版本 | v2.94.0（pyproject = CHANGELOG = README 徽章，Gate 58 覆盖） | 持平 |
| 门禁总数 | 56 唯一编号（GATE 1–58，缺 37/52） | 持平 |
| **门禁结果** | **FAIL — gate46 + gate49**（均 checker 崩溃，非科学裁决） | ↑ 昨夜 FAIL-gate57 已修复 |
| gate57 静默吞异常 | ✅ **PASS**（`is_excluded` 加 `rstrip("/")` 修复生效） | ↑ N1 落地 |
| gate58 版本一致性 | ✅ PASS（README 徽章 + CHANGELOG + pyproject 全覆盖） | 持平 |
| gate54 metrics_fork | ✅ PASS | 持平 |
| gate55 holdout / gate56 徽章语义 | ✅ PASS | 持平 |
| **selfverify 包** | 🔴 **不可导入**（`dynamics.py:113` SyntaxError） | ↓ 昨夜可导入 |
| C3 rank 标签 | ✅ PASS（5/5 图族，MaleCNS 0.87–0.96） | 持平 |
| C1 cell 密化 | FAIL（effect_size=0.0，翻盘已关闭） | 持平 |
| 主张台账 | R1 装置 V5 / 证据 E3 / gap 2（divergent）；R3/R6 boundary | 持平（progress.json 10-16 17:17 未再更新） |
| 论文出口 | 主线 + P-4 + P-5（v0.1 已完成）+ 方法论短文；投稿元数据 10-16 17:15 更新 | 持平 |

---

## 二、上轮 N1–N10 响应核对（项目一夜执行情况）

| 建议 | 执行情况（实测） |
|---|---|
| **N1 修 gate57 白名单** | ✅ **已修**：`check_silent_exceptions.py:70` 加 `prefix_stripped = prefix.rstrip("/")`，`BACKUP_PREFIXES` 机制恢复；gate57 转 PASS，自有代码零违规（K3/K4 修复确认真实生效） |
| **N2 README 门禁数** | 🟡 **半修**：头部徽章 54→56 ✅、gate58 已检查 README 首处门禁数 ✅；**dev 段三行 "30 gates"（1150–1152 行）仍在**，而 gate58 用 `re.search`（check_version_consistency.py:132）只取**第一个**匹配 → 永不检查 dev 段 |
| N3 投 P-4/P-5 | ❓ 无法外部核实（ARXIV_SUBMIT_META 10-16 17:15 更新过，疑在准备投稿） |
| K5 度量内核 | ❌ 未动 |
| K8 阈值脱钩 | 🟡 **注释级**：`check_metric_discrimination.py:410` 加了"独立校准集（N=100, seed=42）"注释，但**阈值仍是硬编码字面量**（0.01/0.32/0.005），无任何校准代码；且注释引用的 `scripts/_gate31_r2/` **路径不存在**（真实数据在仓库根 `_gate31_r2/`），注释自相矛盾（先说"排除验证用的标准套件"又说来源就是标准套件目录） |
| K9 测试金字塔 | ❌ 未动 |
| K6 recovery_auc 改名 | 🟡 **半成品，且引发两个新崩溃**（见 §三） |
| K10 数值契约 | 🟡 起步：`check_c1_c3.py` 的 `target_density` 判等改 `math.isclose(rel_tol=1e-9)` |

**执行面判定**：6 项有响应、2 项半成品、2 项未动。**执行质量出现新问题：K6 半成品改名的代价是门禁套件净变差（56→54），K8 是"注释声称、无机器实现"。**

---

## 三、本轮最重要的发现：K6 半成品改名 → 两个 checker 崩溃

### 3.1 gate49：`dynamics.py` docstring 错位 → SyntaxError → selfverify 包不可导入

**实测**：`ast.parse` 直接报 `SyntaxError line 113: invalid character '。' (U+3002)`；`check_claim_redteam.py` 一 import 就崩；**tools/selfverify 两个单测也全部崩**（`tests/test_gate.py`、`test_prerejection.py` 均 import selfverify）。

**根因（行号级）**：K6 改名编辑 `tools/selfverify/selfverify/dynamics.py` 时，把 `recovery_fraction` 的 docstring 闭合符 `"""` **提前插到了 `Args:` 块之前**：

```python
def recovery_fraction(curve: list[float], drop_magnitude: float) -> float:
    """计算归一化恢复分数（原 recovery_auc，K6 改名）。
    ...
    注意：与 drop_magnitude 存在定义性耦合地板约 0.34（K6 审计发现）。
    """                       ← line 77：错位的闭合符（应在 "归一化恢复 AUC" 之后）
    Args:                     ← line 78 起：原属 docstring 的内容暴露为裸代码
        curve: 恢复轨迹曲线
    ...
    Returns:
        归一化恢复 AUC
    """                       ← line 84：原闭合符变成开符
    T = len(curve) - 1        ← 被吞进字符串
    ...
def t_half(...):
    """计算半恢复时间.       ← 与上一个闭合符配对……
    ...
def tau_recovery(...):
    """估计恢复时间常数。    ← line 113：这个"开符"变成闭合符！
                             → 中文暴露为代码 → SyntaxError
```

**修复规格**：删除 line 77 的 `    """`，保留 line 84 的闭合符，并把 `Returns: 归一化恢复 AUC` 改为 `归一化恢复分数`。一行级修复，改完 `ast.parse` 必须通过。

### 3.2 gate46：改名只改了 checker，没改数据 → None 格式化崩溃

**实测**：`check_recovery_dynamics.py` 崩溃于 `TypeError: unsupported format string passed to NoneType.__format__`（line 244，`auc_var={auc_var:.6f}`）。

**根因**：checker 的键名读取已改名（line 211 `stats.get("recovery_fraction_var")`、line 79 逐结果 `recovery_fraction`），但**数据文件 `_f2_recovery/f2_recovery_dynamics.json` 仍是旧键**（实测：`summary_stats` 含 `recovery_auc_var/unique/mean`，50 条 `all_results` 每条含 `recovery_auc`）。`stats.get("recovery_fraction_var")` → None → verdict=PASS 分支的格式化字符串崩溃。

**修复规格（二选一，推荐前者）**：
- **(a) 向后兼容读取**（推荐，不动实验数据、不破坏 vault/receipt 哈希）：`stats.get("recovery_fraction_var") or stats.get("recovery_auc_var")`，`_recompute_stats` 同时接受 `recovery_fraction` 与 `recovery_auc` 两个逐结果键；
- (b) 用新版 `dynamics.py` 重跑 F2 数据生成——**会改变实验产物，触发 receipt/vault payload_hash 漂移（gate55 会红）**，除非同步重签收据。

### 3.3 为什么这两条是"地基级"而非"装修级"

- **这是项目第 12 次"声明/实现不一致"**，但机制史无前例：**改名改了引用方（checker），没改被引用方（数据）**——与 K8 的"注释声称无实现"、gate58 的"只查首处"构成同一个模式的三连发：**把"做了一半"当成"做完了"**。
- **直接后果**：selfverify 是 M1 协议化交付物（可 pip 安装的 EPE 参考实现），它现在**当场损坏**；任何"56 门禁全绿"的论文叙事在当前为假。
- **讽刺的是**：gate49（红队）存在的意义就是抓"度量不测其所称之物"，而它现在死于"改名不测其所覆盖之物"。

---

## 四、科学先进性评估（核心资产完好）

### 4.1 科学资产清单（本轮逐一复测）

| 资产 | 实测状态 | 评价 |
|---|---|---|
| **C3 构造性翻案** | ✅ PASS（`_c3_rank_label_pr3v2/c3_results.json` verdict=PASS，5/5 图族，MaleCNS 真实锚点 0.867–0.960） | 迄今最强正结果；"科学空 vs 分辨率失败"二分法的首个构造性案例 |
| **C1 诚实负结果** | ✅ FAIL 如实保持（effect_size=0.0，三布局 AUC 全 0.5） | "计算增益"负结果双重闭合；翻盘路径关闭且如实报告 |
| **EPE 双轴自检** | ✅ R1 装置 V5 / 证据 E3 / gap 2 显式分歧 | 验证层自我审计（第 4 次自抓） |
| **honest negatives 体系** | ✅ 4/5 预注册 FAIL 如实报告 | 学术立场罕见地干净 |
| **S6–S9 四纪律** | ✅ 机器化（Gate 30/43–47） | 每条对应真实踩坑 |
| **E3 holdout 保险库** | ✅ Gate 55 PASS | 数据窥探纪律机器化 |
| **度量族版本化 M2.5** | ✅ 已入 selfverify（`metric_versions.py`） | 对应 K6 的基础设施 |

### 4.2 国际定位（竞品坐标不变，2026-10 检索）

| 赛道 | 竞品 | 本项目位置 |
|---|---|---|
| A 面·自验证基础设施 | 2608.09855（2026-08 刚提出"反馈架构是瓶颈"）、RAGWarrant（2609.34179）、F(AI)2R | **国际第一梯队且部分领先**：EPE 已实现其三大要求（稠密信号/反馈调度/受保护验证）的 2.5/3 |
| B 面·连接组→AI | FlyVision（2610.08418，MNIST 99.34%）、FlyGM（2602.17997）、SCGFM（2605.08689） | **有意识退出**（C1 FAIL 双重闭合），不构成能力缺口 |

**结论：科学先进性未受本轮倒退影响——倒退发生在工程执行层（门禁/包完整性），不在科学结论层。**

---

## 五、SCI 就绪度判断（较上轮**倒退**）

### 5.1 主线论文

| 维度 | 昨夜 | 今晨 | 变化 |
|---|---|---|---|
| 论文结构 / 预注册纪律 / 诚实负结果 / 可追溯性 / 方法学贡献 | 100/100/100/95/90 | 不变 | — |
| **门禁全绿** | 0（gate57 FAIL） | **0（gate46+49 FAIL，且是 checker 崩溃）** | 换了个 FAIL，性质更差 |
| **仓库公开化 D3** | 0 | 0 | 不变 |
| **综合** | 素材 89 / 资格 0 | 素材 89 / 资格 0 | 持平 |

**判定：仍未达 SCI 投稿阶段。** 且昨夜修复引入的新崩溃使"投稿前跑门禁确认全绿"这一清单项**仍然必然失败**。

### 5.2 短文出口（P-4 / P-5）——当前唯一可立即执行的 SCI 路径

| 短文 | 依赖 | 是否受本轮损坏波及 |
|---|---|---|
| **P-4**（PR-2b 预执行拒绝案例） | `registry/preregistered_rejections.json` + `f4b` 脚本子集 | ❌ 不受影响（不 import selfverify） |
| **P-5**（S6–S9 四纪律方法学） | Gate 30/43–47 脚本子集（`check_llm_orchestrator.py` 等） | ❌ **不受影响**（实测：gate30 不 import selfverify） |
| 方法论短文 | metrics_fork + 上游数字复现 | 🟡 仍卡 P-2（上游 result→graph 导出器未做） |

**判断：P-4/P-5 已达 arXiv 投稿阶段，可立即投（cs.LG / q-bio.NC / cs.CY）；P-5 的题材对 Patterns / Scientific Reports / Nature CS 方法学栏目对口且稀缺，是四篇素材中最接近"独立 SCI 级贡献"的一篇。**

### 5.3 期刊视角的方法学红线

审稿人复跑时会依次看到：门禁 54/56 → selfverify 不可导入 → gate46/49 traceback。**这三件事任何一件都足以让"自验证方法学"论文被 desk reject**——因为论文的主张恰好是"我们能把纪律做成机器门禁"，而门禁自己崩着。

---

## 六、达到 SCI 阶段的提升方案（三阶段路线图，每阶段机器验收）

### 阶段 0：止损（本周，~4 小时，全部可机器验收）

| # | 行动 | 精确规格 | 验收 |
|---|---|---|---|
| **F1** | 修 `dynamics.py:77` docstring 错位 | 删除 line 77 的 `"""`，保留 line 84 闭合符；`Returns` 文案改"归一化恢复分数" | `ast.parse` 通过；`import selfverify` 真包导入成功；两个单测恢复运行 |
| **F2** | 修 gate46 键名向后兼容 | `check_recovery_dynamics.py:177/179` + `_recompute_stats:79` 双键兼容（`recovery_fraction_var` or `recovery_auc_var`） | gate46 转 PASS；**不动实验数据**（保护 vault/receipt 哈希） |
| **F3** | README dev 段 30→56 + gate58 覆盖全部 "N gates" 出现处 | `re.finditer` 替换 `re.search`（check_version_consistency.py:132） | gate58 注入"dev 段改 30" → 报红 |

**阶段 0 出口状态：56/56 门禁全绿 + selfverify 可导入。这是任何投稿的底线。**

### 阶段 1：短文出口（本周–下周，零外部依赖）

| # | 行动 | 验收 |
|---|---|---|
| **F4** | 投 P-4 到 arXiv（公开 registry + f4b 脚本子集） | arXiv ID |
| **F5** | 投 P-5 到 arXiv（公开 Gate 30/43–47 脚本子集）；目标期刊 *Patterns* / *Sci Rep* / *Nature CS* 方法学栏目 | arXiv ID + 期刊投稿确认 |

### 阶段 2：主线论文（2–6 周，含一个用户拍板项）

| # | 行动 | 周期 | 依赖 |
|---|---|---|---|
| **F6** | K5 度量内核：10 处 AUC 收敛为 1 处 + 性质测试 4 条 | 3–5 天 | 阶段 0 后 |
| **F7** | K9 最小版：selfverify 12 模块补单测（尤其 dynamics / metric_versions） | 3–5 天 | F1 后 |
| **F8** | K8 真实现：阈值从独立校准集**计算**（非硬编码注释），校准产物入仓可机器复算 | 2–3 天 | — |
| **F9** | P-2 上游 result→graph 导出器（方法论短文数字可机器复现） | 2–3 天 | — |
| **F10** | **D3 仓库公开化**（metrics_fork → scripts/docs → 全仓三步） | — | **用户拍板** |
| **F11** | 主线论文 arXiv + SCI 期刊投稿 | — | F6–F10 全绿后 |

### 明确的"不要做"

- **不要在阶段 0 完成前投任何论文**（门禁崩着 = "自验证"论文的死刑）。
- **不要用重跑 F2 数据的方式修 gate46**（会触发 receipt/vault 哈希漂移，把 F2 的成本放大到 gate55）。
- **不要把 K8 的注释当实现交付**——审稿人问"校准集在哪"，答案是"一行注释引用了一个不存在的路径"。

---

## 七、结论

1. **科学先进性：未受损，仍在国际第一梯队。** C3（5/5 图族含真实锚点）、C1（诚实负结果）、EPE（双轴自检）三项核心资产全部完好；B 面有意识退出。倒退的是**工程执行**，不是**科学结论**。
2. **SCI 就绪度：较上轮倒退至 54/56，两个 FAIL 均为 checker 自身崩溃**（K6 半成品改名的直接代价）；selfverify 包（M1 交付物）当场损坏。主线论文维持"素材 89 / 资格 0"。
3. **达到 SCI 的路径已经清晰且极短**：阶段 0 止损（4 小时）→ 阶段 1 投 P-4/P-5（本周）→ 阶段 2 主线（2–6 周 + D3 拍板）。**最大的障碍不是科学，是把"做了一半"当"做完了"的执行习惯**——昨夜三连发（K6 半成品、K8 注释级、gate58 只查首处）都是同一个病的三个病灶。
4. **一句话**：**科学先进性这栋楼没塌，塌的是楼梯——门禁套件。花 4 小时修好 F1–F3，SCI 之路就从"资格 0"变成"P-4/P-5 在手、主线可投"。**

---

## 附：本轮实测证据索引

- 门禁：`run_gates.py --quick`（2026-10-17 06:30，3m58s）→ **GATES: FAIL — gate46 recovery dynamics, gate49 red-team battery**；gate57 ✅ PASS（`is_excluded` 的 `rstrip("/")` 修复生效）
- gate49 崩溃：`check_claim_redteam.py:31` → `selfverify/__init__.py:26` → `dynamics.py:113` SyntaxError（invalid character '。'）；`ast.parse` 复现同一错误
- gate46 崩溃：`check_recovery_dynamics.py:244` `TypeError: unsupported format string passed to NoneType.__format__`（`auc_var=None`：checker 读新键 `recovery_fraction_var`，数据仍为旧键 `recovery_auc_var`，实测 `summary_stats` 键名清单）
- dynamics.py 错位现场：line 77 提前闭合符 + line 84 原闭合符变开符（行号级）
- K8 注释级证据：`check_metric_discrimination.py:410` 注释声称"独立校准集（N=100, seed=42，排除标准套件）"；阈值仍硬编码（0.01/0.32/0.005）；引用路径 `scripts/_gate31_r2/` **不存在**（真实数据在仓库根 `_gate31_r2/`）；无校准代码（grep 无 `calibration_set`/校准函数）
- gate58 只查首处：`check_version_consistency.py:132` `re.search(r'(\d+)\s+gates')`；README dev 段 1150–1152 行三处 "30 gates" 仍在
- K10 起步：`check_c1_c3.py` `target_density` 判等改 `math.isclose(rel_tol=1e-9)`
- fail-loud 纪律铺开：`fingerprint_organism.py:86` warn+return None；`vault.py:100,367` / `compute_epistemic_progress.py` / `check_docs_consistency.py` 全部带 `# noqa: SILENT` + 理由
- P-4/P-5 不受损证据：grep 显示仅 `check_claim_redteam.py`（gate49）与两个 selfverify 单测 import selfverify；gate30（`check_llm_orchestrator.py`）与 P-4/P-5 论文均无依赖
- C3 完好：`_c3_rank_label_pr3v2/c3_results.json` verdict=PASS
- 工作区：28 个未提交改动 + 3 个新文件（check_silent_exceptions.py / check_version_consistency.py / .gate57_whitelist.txt 均为未跟踪）
