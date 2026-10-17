# 地基审计报告：楼越高，地基越要硬

> 基线：v2.94.0（CHANGELOG 顶部）· `pyproject.toml` 仍为 **2.91.0**（落后 3 个版本）
> 门禁实测：`run_gates.py --quick` → **PASS 50/50**（修复后复测）
>
> **修复前**：**FAIL — gate2 docs drift**（README 徽章写 51，实际 54 个唯一 `GATE N` 标签）。
> **本轮已执行 K1 修复**（徽章 51→54）→ gate2 转 PASS，全量 50/50。
> **报告定位**：**不做上层规划，只查底层。** 本报告不谈愿景、不谈论文、不谈竞品——只谈那些"现在不修、楼越高越危险"的东西。
> **评估方法**：代码级实测（grep + 运行 + 数值对照），每条结论附文件与行号。

---

## 零、核心判断：楼层高度与地基深度已经失衡

| 维度 | 楼层（已建高度） | 地基（承重能力） |
| --- | --- | --- |
| 门禁数量 | 55 条（本轮新增 54/55/56） | 🔴 **整体 FAIL**（gate2 文档漂移） |
| 版本治理 | CHANGELOG 已到 2.94.0 | 🔴 `pyproject.toml` 停在 **2.91.0**（落后 3 版） |
| 论文出口 | P-2/P-3/P-4/P-5 四篇短文 | 🟡 依赖 `metrics_fork`，论文数字**仍未机器验证** |
| 度量体系 | R1 主张靠 AUC 支撑 | 🔴 AUC **10 处独立实现**，无单一真源 |
| 自验证纪律 | 对外宣称 fail-closed | 🔴 底层 **13 处静默吞异常**（fail-silent） |
| 测试 | dev 依赖已声明 pytest/ruff/mypy | 🔴 **门禁从不执行它们**；真单测仅 3 个文件 |

> **一句话**：项目的**上层结构（门禁、命题图、收据、论文）越建越高，而支撑它们的地基（版本一致性、异常纪律、度量单一真源、自动化测试）基本停留在 v2.6x 的水平**。
>
> 更危险的是：**新增的门禁本身正在成为新的地基负担**——加了 3 条门禁（54/55/56），却没同步 README 徽章，于是 gate2 直接报红。**这就是"楼越建越高、地基跟不上"的实证。**

---

## 一、地基七宗罪（全部实测，附证据）

### ① 静默降级：13 处 `except Exception: pass` + 2 处裸 `except`

这是**最严重**的一条，因为它与项目的核心价值直接冲突：**项目对外宣称 fail-closed，底层却在 fail-silent。**

| 位置 | 后果 |
| --- | --- |
| **`scripts/fingerprint_organism.py:87`** 🔴 | **签名密钥读取失败 → 静默返回 `None` → 指纹变成"未签名"而非报错**。一个以 `sha256/hmac-sha256` 签名为卖点的项目，最坏情况是**悄悄失去签名** |
| **`scripts/vault.py:368`** 🔴 | holdout 保险库读取已提交字段时静默吞异常，随后继续做漂移比对 |
| `scripts/vault.py:101` | 日期回退（可接受，良性） |
| `flybrain-connectome-mcp/mcp_connectome/server.py:53` | 900 秒数据抽取子进程失败被吞（只丢"为什么失败"） |
| `flybrain-connectome-mcp/module_combinator.py:89` | core 可用性探测失败被吞 |
| `flybrain-connectome-mcp/profile_health.py:542` | profile 名提取失败 → 静默走 fallback |
| `scripts/check_degraded_mode.py:95,100` · `check_docs_consistency.py:73` · `check_physical_tiering.py:51` · `f3_generalization_matrix.py:190` · `compute_epistemic_progress.py:129` | 门禁/度量脚本自身的静默分支 |
| `integrations/swarmlabs/benchmark_module_stacking.py:239` · `diagnostics/topology_visualizer.py:98` | 集成层静默 |
| **`scripts/module_discovery/step1c_worm_modules.py:97,99`** 🔴 | **裸 `except:`**——连 `KeyboardInterrupt`/`SystemExit` 都吞，并 `return 1` 假装成功 |

> **为什么这是"地基"而非"装修"**：门禁越多，被门禁保护的代码路径越多；**而门禁只能检查它看得见的东西**。一个静默吞异常的分支，会让"门禁全绿"与"系统真的健康"之间出现**不可见的裂缝**。楼层越高，这条裂缝的后果越大。

### ② 度量分裂：AUC 有 10 处独立实现，无单一真源

| 文件 | 类型 | 签名 |
| --- | --- | --- |
| `scripts/c1_cell_densification.py:130` | 分类 AUC（成对，平局 0.5） | `_held_out_auc(pairs)` |
| `scripts/c3_rank_label_pr3_v2.py:105` | 分类 AUC（成对，平局 0.5） | `_auc(pairs)` |
| `scripts/mechanism_binary.py:99` | 分类 AUC（成对，平局 0.5） | **`auc_score(y_true, y_score)` ← 标签在前** |
| `tools/selfverify/selfverify/gate.py:12` | 分类 AUC（平均秩） | **`auc(scores, labels)` ← 分数在前** |
| `scripts/f2_recovery_dynamics.py:157` | ⚠️ **不是分类 AUC** | 见 ③ |
| 另有 5 处含 `def *auc*`（`check_claim_redteam`、`check_generalization_matrix`、`f1_controllability_features`、`f3_generalization_matrix`、`f6_motif_ablation`） | 未逐一核实 | — |

**好消息（实测）**：成对法与平均秩法在含平局数据上**数值完全一致**（6 个用例，`max|A−B| = 0.00e+00`）。数学没问题。

**坏消息（地基问题）**：
1. **签名不一致**：`mechanism_binary` 是`(y_true, y_score)`，`selfverify.gate` 是`(scores, labels)`。**参数顺序相反**——一旦调用方搞混，结果是静默错误的数字，不会报错。
2. **10 份拷贝**：任何一处未来修改（如换平局处理、加置信区间），其余 9 份不会同步。
3. **复杂度**：成对法是 **O(P×N)**；平均秩法是 **O(N log N)**。规模上去后成对法会先成为瓶颈。

### ③ 命名污染：`recovery_auc` 不是 AUC，且定义内含耦合

`scripts/f2_recovery_dynamics.py:157`：

```python
def _recovery_auc(curve, drop_magnitude):
    T = len(curve) - 1
    if T <= 0 or drop_magnitude <= 0: return 0.0
    total = sum(curve[1:]) / T
    return max(0.0, min(1.0, total / drop_magnitude))   # ← 分母就是 drop_magnitude
```

**它叫 AUC，但不是分类 AUC**，而是"恢复曲线均值 ÷ 跌落幅度"。**分母里直接装着 `drop_magnitude`。**

**实测后果（严谨对照）**：用真实 F2 数据（`_f2_recovery/f2_recovery_dynamics.json`，n=50，**无钳制**，range 0.18–0.55）：

| 量 | 值 |
| --- | --- |
| 观测 \|corr(modulator_Ra, recovery_auc)\| | **0.9847** |
| **定义性地板**（把恢复内容洗牌、只保留公式耦合，×2000） | **0.3395**（95% 带 0.117–0.556） |
| 真实恢复内容贡献 | **+0.645** |

**结论（必须诚实）**：
- ✅ **PR-2b 的"拒绝"决策在经验上是成立的**——0.985 远高于定义性地板 0.34，耦合是真的。
- 🔴 **但 PR-2b 的接受阈值 `|r| < 0.5` 落在定义性噪声带内（0.117–0.556）**——也就是说，**即使毫无真实耦合，仅凭公式也会产生约 0.34 的相关**；阈值 0.5 **没有对照这个地板做校准**。一个"纯定义性"的样本有机会刚好判成 ACCEPT。
- 🔴 **论文把 `|corr|=0.902` 作为"实测发现"呈现**，但读者不知道其中约 1/3 是度量定义自带的。

### ④ 测试地基：dev 依赖声明了 pytest/ruff/mypy，门禁从不执行

```text
$ grep -niE "pytest|ruff|mypy|black" scripts/run_gates.py
（无输出）
$ ls scripts/ | grep -iE "lint|ruff|mypy|pytest|cov"
（无输出）
```

- `pyproject.toml` 的 `dev` extra 里白纸黑字写着 `pytest>=8.0`、`pytest-cov>=5.0`、`ruff>=0.5`、`mypy>=1.10`、`black>=24.0`、`pre-commit>=3.7`。
- 但**55 条门禁里没有一条运行它们**，`.pre-commit-config.yaml` 存在但不在门禁链里，CI（`ci.yml`）与门禁链是两套东西。
- **真单元测试仅 3 个文件**：`tools/selfverify/tests/{test_gate,test_prerejection}.py`、`integrations/swarmlabs/diagnostics/test_stacking.py`。另有 2 个 `*_test.py` 实为实验脚本（`check_intervention_test.py`、`f4_intervention_test.py`）。
- 对比：**250 个 py 文件**（排除 archive/backup/第三方数据）。

> **这是最典型的"楼越高越危险"**：项目用 55 条门禁证明"科学主张成立"，但**没有任何一条门禁在证明"代码本身正确"**。门禁测的是产物（JSON 里的数字），不是产生数字的代码。

### ⑤ 版本与文档漂移（本轮正在扩大）

| 项 | 值 |
| --- | --- |
| `pyproject.toml` version | **2.91.0** |
| `CHANGELOG.md` 顶部 | **2.94.0** |
| 落后 | **3 个版本** |
| README 徽章门禁数 | **51** |
| `run_gates.py` 实际 invoke | **55** |
| **gate2 docs consistency** | 🔴 **FAIL** |

**这条已经在报红了**——不是"潜在风险"，是**当前状态**。而且它的成因极具代表性：**新增了 3 条门禁（54/55/56），却没有同步任何元数据**。

### ⑥ 确定性：固定种子 + 在同一种子上校准阈值

```text
scripts/check_metric_discrimination.py:410:
  # min_variance values are calibrated from A1 (N=50, seed=42) where:
```

- 多处门禁使用**单一固定种子**：`seed=42`（`check_combination_reaction.py:136`、`check_llm_orchestrator.py:311/455`、`check_population.py:84/110/144/170/194`）、`seed=7`、`seed=0`、`seed=1..5`。
- **`check_metric_discrimination.py` 的方差阈值是在 `seed=42`（N=50）上校准的，而该门禁自己又用 `seed=42` 跑** → **阈值与验证用的是同一个实现**，这是**循环论证**：门禁永远绿，因为阈值就是从这个种子长出来的。

**地基含义**：这类门禁能抓住"代码改动导致的行为变化"，但**抓不住"换个种子就崩"**。而后者才是科学结论真正需要的稳健性。

### ⑦ 门禁在资源压力下会"假红"（flaky gate）

实测经过：一次批量运行中 `gate10 embodiment` 报 FAIL，但**同一脚本单独运行两次均 PASS**（45 项检查全绿）。复跑全量门禁后 → **PASS 50/50**。

**判定**：这是**环境资源压力导致的假红**（本次同机并发跑渲染进程时出现过 `OSError: [WinError 1455] 页面文件太小`），不是代码缺陷。

**但作为地基问题它依然成立**：
- 一条会在资源紧张时报红的门禁，**会侵蚀"全绿"这条信号的可信度**——你无法区分"真回归"与"机器当时很忙"。
- 门禁没有**超时/资源护栏**，也没有**重试与结果稳定性记录**（没有"这条门禁过去 N 次的通过率"）。
- **建议（承重结构 7）**：`run_gates.py` 记录每条门禁的耗时与返回码历史；对超时/OSError 类失败标注为 `INFRA` 而非 `FAIL`，并允许一次自动重试后再判定。

### ⑧ 可复现：Gate 54 是真的，但论文数字仍未机器验证

**必须公允肯定**：Gate 54（`scripts/check_metrics_fork.py`）是**一条真门禁**——它解析 README 的冒烟命令、逐条执行、要求退出码 0 且输出可解析 JSON、检查 LICENSE/物种矛盾/免责声明，并带 **5 条注入电池**（删图、剥 edges、改回物种矛盾、换 LICENSE、删免责声明），遵守 Gate 39 元纪律。**这是把上轮发现固化成机器边界的正确做法。**

**但它有一个明确的边界**（`check_metrics_fork.py:86-90`）：

```python
SMOKE_CMD_RE = re.compile(
    r"^\s*python\s+-m\s+metrics\.(robustness|controllability|recovery)\b"
    r"(.*?sample_topology\.json.*?)\s*$",   # ← 只匹配含 sample_topology.json 的行
)
```

→ **只执行冒烟命令；论文数字表（§5.2–5.4）指向的上游路径命令不执行**，仅检查"有没有写免责声明"。

**所以**：`docs/arxiv_methodology_short_paper_2026-10-16.md` 摘要里那句"reader who pulls the upstream artifact and runs the three commands gets the paper's numbers"——**至今没有任何机器验证**。已验证的是"冒烟测试能跑 + 有免责声明"。

---

## 二、为什么这些是"地基"而不是"装修"

| 缺陷 | 现在（55 门禁 / 4 篇论文）的代价 | 楼再高一层（公开仓 / 投稿 / 外部复现）的代价 |
| --- | --- | --- |
| 静默吞异常 | 门禁绿但内部降级 | **外部复现者得到"看似成功"的错误结果，且无从察觉** |
| AUC 10 份拷贝 | 数字一致（已验证） | **任何一处修改 → 跨论文数字不可比，且无人知道** |
| `recovery_auc` 命名污染 | PR-2b 结论正确 | **审稿人追问"为什么叫 AUC"时无法解释；阈值未校准会被方法学审稿抓** |
| 无自动化测试 | 靠门禁兜底 | **门禁测产物不测代码 → 重构即事故** |
| 版本漂移 3 版 | gate2 报红 | **引用混乱：读者不知道该引哪个版本** |
| 固定种子自校准 | 门禁恒绿 | **"稳健性"无法宣称** |

---

## 三、为建更高楼所需的承重结构（面向未来的设计）

这些不是"现在的 bug"，而是**为了将来能承受更高楼层而必须预埋的结构**。

### 承重结构 1：度量单一真源（`metrics_kernel`）

- 新建 `flybrain-connectome-core/metrics_kernel/`：`auc`、`corr`、`variance`、`bootstrap_ci` 各一份实现。
- 全部 10 处改为 import。**签名统一为 `auc(scores, labels)`**。
- 配 **性质测试**（property-based）：`auc` ∈ [0,1]、`auc(反转标签) = 1 - auc`、`auc(全平局) = 0.5`、`auc` 对分数单调变换不变。
- **验收**：`grep -rn "def.*auc" --include=*.py` 只剩 1 处。

### 承重结构 2：fail-loud 纪律（`--strict` + 静态门禁）

- 制定规则：**除显式白名单外，禁止 `except Exception: pass`**。
- 新增 **Gate 57「静默吞异常」**：AST 扫描全仓，命中的必须满足其一——(a) 在白名单、(b) 有 `# noqa: SILENT` 且附理由、(c) 记录了 warning。
- **优先级**：`fingerprint_organism.py:87`（签名密钥）与 `module_discovery/step1c_worm_modules.py:97,99`（裸 except）**必须首修**。
- **验收**：Gate 57 绿；且注入"新增一处静默吞异常"时必须报红。

### 承重结构 3：确定性分层（回归种子 vs 结论种子）

- **回归种子**（固定，如 42）：只用于"代码改动是否改变行为"——门禁用。
- **结论种子**（多组，如 10 组）：任何进入论文/主张的数字，必须报 **多种子均值 ± 离散**，且阈值**不得**在结论种子上校准。
- **验收**：每个对外数字附 `n_seeds ≥ 10`；`check_metric_discrimination.py` 的阈值改为在**独立于验证集**的样本上校准，并在代码注释里写明校准来源。

### 承重结构 4：版本单一真源

- 版本号只写在**一处**（建议 `pyproject.toml`），CHANGELOG / README 徽章 / CITATION / 门禁数**全部由脚本生成或校验**。
- **验收**：新增 Gate 58「版本与徽章同步」：`pyproject.version == CHANGELOG 顶部 == README 徽章门禁数 == run_gates 实际数`。
- 这一条**现在就能修，且能立刻让 gate2 由红转绿**。

### 承重结构 5：测试金字塔（目前只有塔尖）

| 层 | 现状 | 目标 |
| --- | --- | --- |
| 单测（函数级） | 3 个文件 | 度量内核、vault、fingerprint 100% 覆盖 |
| 性质测试 | 无 | `auc`/`corr` 的 4 条不变量 |
| 契约测试（schema） | 部分 | 所有 `*_results.json` 有 schema + 校验 |
| 门禁测试（产物级） | 55 条 ✅ | 保持 |
| **CI 一致性** | CI 与门禁两套 | **CI 直接调用 `run_gates.py`，门禁链里跑 pytest + ruff** |

### 承重结构 6：数值契约

- 禁止浮点 `==` 判等（`check_c1_c3.py:50/65`、`check_repair.py:90/183/195/200-202`、`isolation_graded.py:559` 等处改为 `math.isclose` + 显式 `rel_tol`）。
- 所有退化判定（"方差为 0"）必须写**容差**，并把容差作为预注册字段。

---

## 四、啃硬骨头执行清单（按痛苦度从高到低，痛苦度高的先做）

| # | 硬骨头 | 痛苦度 | 周期 | 验收（可机器判定） |
| --- | --- | --- | --- | --- |
| **K1** | **修 gate2**：README 徽章门禁数 51→54 | 低 | 0.5 天 | ✅ **本轮已执行并验证**：gate2 转 PASS，全量 **50/50** |
| **K2** | **Gate 58 版本单一真源**（防止再次漂移） | 中 | 1 天 | 注入"改 pyproject 不改 CHANGELOG" → 报红 |
| **K3** | **`fingerprint_organism.py:87` 签名密钥失败改为抛错**（或至少 warn + 显式降级标记） | 低 | 0.5 天 | 注入"坏配置文件" → 抛错或标记未签名 |
| **K4** | **裸 `except` 清除**（`step1c_worm_modules.py:97,99`） | 低 | 0.5 天 | AST 扫描无裸 except |
| **K5** | **度量内核 `metrics_kernel` + 10 处收敛** | **高** | 3–5 天 | `grep "def.*auc"` 剩 1 处；性质测试 4 条通过 |
| **K6** | **`recovery_auc` 改名 + 阈值校准**（改名 `recovery_fraction`，并在论文说明其与 drop_magnitude 的定义性耦合地板 0.34） | 中 | 1–2 天 | 论文/代码/门禁三处命名一致；PR-2b 段落补地板说明 |
| **K7** | **Gate 57 静默吞异常门禁**（含白名单与 noqa 机制） | **高** | 2–3 天 | Gate 57 绿 + 注入测试报红 |
| **K8** | **确定性分层**：结论数字多种子 + 阈值脱钩校准 | **高** | 3–5 天 | 对外数字均带 `n_seeds≥10`；`check_metric_discrimination` 阈值来源与验证集分离 |
| **K9** | **测试金字塔补齐**：门禁链里跑 pytest + ruff；度量内核/vault 单测 | **高** | 1–2 周 | `run_gates.py` 含 pytest/ruff；覆盖率报告产出 |
| **K10** | **数值契约**：浮点判等改 isclose + 容差入预注册 | 中 | 2–3 天 | Gate：无裸浮点 `==` 判等（白名单外） |

---

## 五、地基成熟度阶梯（F0–F5）——用来自评"地基深度"

| 级别 | 含义 | 项目现状 |
| --- | --- | --- |
| **F0** | 能跑 | ✅ |
| **F1** | 有门禁守产物 | ✅（55 条） |
| **F2** | 门禁自证可报红（注入电池） | ✅（Gate 39，100% 覆盖） |
| **F3** | **代码层有自动化测试** | ❌ **缺失**（3 个单测文件） |
| **F4** | **度量单一真源 + 数值契约** | ❌ **缺失**（AUC ×10、裸浮点判等） |
| **F5** | **异常纪律 + 版本单一真源 + 确定性分层** | 🔴 **反向**（13 处静默吞异常、版本落后 3 版、阈值自校准） |

**当前：F2。** 目标是 **F4**，F5 视公开计划而定。

> 对照一下：项目的**科学主张治理**已经在用 F2 以上的纪律（命题图、收据、预注册、红队），而**代码地基**停在 F2。**这个落差本身就是最大的风险**——因为所有科学主张最终都由这些代码产生。

---

## 六、如果只做三件事（按"投入产出 × 防塌方"排序）

> **K1 已在本轮执行完毕**（徽章 51→54，gate2 转 PASS，全量 50/50）。剩下三件：

1. **K3 + K4（1 天）**：签名密钥静默降级改抛错 + 清除裸 `except`。
   → **这两处是唯一可能让项目"悄悄失去安全属性"的地方**（指纹静默变未签名），且修起来只要 1 天。
2. **K2（1 天）**：版本单一真源 Gate 58（pyproject 2.91.0 ↔ CHANGELOG 2.94.0 的 3 版漂移**当前无任何门禁覆盖**）。
   → **永久消除"加功能不改元数据"这类漂移**。K1 修的是这一次，K2 修的是这一类。
3. **K5 度量内核（3–5 天，唯一真正痛苦的）**：把 10 处 AUC 收敛为 1 处 + 性质测试。
   → 这是**唯一能防止"未来某次改动让跨论文数字不可比"**的结构。痛苦但无可回避——**项目的全部科学结论都由 AUC 承载，而它目前有 10 份没有互相校验的拷贝。**

---

## 附：本轮实测证据索引

- 门禁（修复前）：`run_gates.py --quick` → **FAIL — gate2 docs drift**（徽章 51 vs 实际 54 个唯一 `GATE N` 标签）
- 门禁（K1 修复后复测）：**PASS 50/50** ✅；`check_docs_consistency.py` → **DOCS CONSISTENCY: PASS** ✅
- 门禁 flaky 观察：一次批量运行中 `gate10` 假红；单独跑两次均 PASS（45 项检查）；复跑全量 → PASS
- 版本：`pyproject.toml` = 2.91.0；`CHANGELOG.md` 顶 = 2.94.0（gate2 版本段仅校验 pyproject↔cli↔api↔server，四处均 2.91.0 故 PASS，**CHANGELOG 漂移无门禁覆盖**）
- 静默异常：`grep -rn -A1 "except Exception" | grep pass` → 13 处（排除 backup/第三方）
- 裸 except：`scripts/module_discovery/step1c_worm_modules.py:97,99`
- AUC：4 处已确认分类 AUC 实现 + `f2_recovery_dynamics.py:157` 同名异物；两类实现数值一致（`max|A−B|=0.00e+00`）
- `recovery_auc` 定义性耦合地板：**0.3395**（95% 带 0.117–0.556，真实数据洗牌 ×2000）；观测 0.9847
- 测试：真单测 3 文件 vs 250 py 文件；`grep "pytest|ruff|mypy" run_gates.py` → 空
- 种子自校准：`scripts/check_metric_discrimination.py:410`
- **已修复确认**：`data_manifest.json` 物种矛盾已订正为 "Male Drosophila CNS connectome" ✅；Gate 54 为真门禁（5 条注入电池）✅
