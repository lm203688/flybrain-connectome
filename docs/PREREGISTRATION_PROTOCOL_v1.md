# 预注册协议 v1（Pre-registration Protocol）

**版本**：v1 · **建立日期**：2026-10-14 · **基线**：v2.69.0
**目的**：把项目的核心科学主张从「事后拟合」改为「**事前预测 + 一次性验证**」——这是把证据等级从 L2（可执行测试）抬到 **L3（前瞻性预测）** 和 **L4（干预/因果）** 的唯一合规途径。
**方法学框架**：Self-Interventional Learning 四元组（arXiv:2608.14894）——*self-intervention → consequence learning → held-out generalization → structural action*。
**配套文档**：`docs/FRONTIER_VALUE_ENHANCEMENT_2026-10-14.md`（V2，§六证实途径）

---

## 0. 冻结规则（先立规矩，防止自我篡改）

| 规则 | 内容 |
|---|---|
| **R-0.1 时间顺序** | 本文件所有阈值、样本量、判据必须**在看到验证集结果之前**写入。任何修改必须**新增版本段**（PR-x v2）并注明修改理由，不得原地覆盖。 |
| **R-0.2 机器固化** | 预注册阈值写入 `research_claims.json` 的 `preregistered` 字段，由 **Gate 43 / Gate 45** 读取比对；脚本内硬编码阈值与 JSON 不一致 → 门禁 FAIL。 |
| **R-0.3 一次性验证** | 验证集只允许**跑一次**。若需重跑，必须在协议中新增"二次独立验证集"段，并声明首次结果。 |
| **R-0.4 失败即发表** | 预注册失败**不得**修改判据使其通过。失败结论照样写入 `research_claims.json` 与 `CHANGELOG.md`（项目已有 4 个测量学缺陷的诚实记录惯例）。 |

---

## PR-1 — R1 前瞻性预测（修 median split）

### 问题（当前状态）
`_r1_mechanism_a/mechanism_binary.json`：`label_definition = "drop_magnitude < median(0.2133)"`，阈值在**同一批 100 个拓扑上**计算 → **数据依赖 + 丢弃连续信息**。这是可被一击必中的方法学漏洞。

### 预注册内容

| 项 | 预注册值 |
|---|---|
| **因变量** | `drop_magnitude`（`isolation_graded.py` 输出，连续量） |
| **预注册阈值** | **`drop_magnitude > 0.25`（绝对值，非分位数）** —— 依据：N=50 样本中 min=0.1011 / max=0.5556，0.25 位于分布中部偏上且为整数化绝对量，不随样本变动 |
| **标签** | 正例 = `drop_magnitude > 0.25`；负例 = 其余 |
| **特征集** | 冻结为 4 项：`n_bridges` / `bridge_fraction` / `n_articulation_points` / `edge_connectivity`（+ F1 后追加可控性特征，作为**独立预注册对比**） |
| **模型** | Logistic 回归 + AUC（**禁止**在 0/1 标签上做 OLS——Bernoulli 方差封顶，方法无效；已在 `mechanism_binary.json.method_note` 记录） |
| **训练集** | seed=42 派生的 100 个拓扑中，**前 60 个**（按 `topology_idx`） |
| **Held-out 集** | 同批次**后 40 个**，**只跑一次** |
| **零假设** | 标签置换 200 次 → AUC 零分布（当前实测 null = 0.5894 ± 0.0383） |
| **成功判据** | **held-out AUC ≥ 0.70 且 z ≥ 3.0** |
| **失败判据** | held-out AUC < 0.70 → 结论降级为"**阈值依赖的样本内相关**"，R1 status 回退到 `inconclusive` |

### 命令
```bash
python scripts/f1_mechanism_preregistered.py \
    --threshold 0.25 --feature-set frozen_v1 \
    --train-idx 0:60 --held-out-idx 60:100 \
    --permutations 200 --seed 42
# 门禁绑定：Gate 43 读取 research_claims.json.preregistered 比对 --threshold
```

---

## PR-2 — F4 干预实验（因果级证据）

### 设计（Self-Interventional Learning 四元组逐项对应）

| 四元组 | 本项目实现 |
|---|---|
| **structural action** | 对单个拓扑执行**一个**原子结构动作：`delete_edge(e)`，`e` 取自该拓扑的关键边集合 |
| **consequence learning** | 记录干预前后 `drop_magnitude` 的变化量 Δ |
| **held-out generalization** | 干预集与拟合集**拓扑不重叠**（干预用的 30 个拓扑不参与任何阈值/系数拟合） |
| **self-intervention** | 系统对自己生成的拓扑施加干预并观察后果，不引入外部数据 |

### 预注册内容

| 项 | 预注册值 |
|---|---|
| **单变量控制** | 每个拓扑**只删一条边**；节点集、边集其余部分、n_nodes 全部保持不变（避免多变量混淆） |
| **干预目标选择** | 优先删**桥边**（`bridge_fraction` 贡献边）；对照组删**非桥边**（随机选取） |
| **方向预测（预注册）** | H1：删桥边 → `drop_magnitude` **上升**（隔离增强 / 后果局部化）<br>H2：删非桥边 → `drop_magnitude` **变化幅度显著小于** H1 |
| **样本量** | 30 个拓扑 × 每个拓扑 1 次桥边干预 + 1 次非桥边干预 = 60 次干预 |
| **成功判据** | **方向命中率 ≥ 70%**（21/30），且 H1 组 Δ 显著大于 H2 组（配对检验） |
| **失败判据** | 命中率 < 70% → 结论为"**结构量与隔离度之间未观测到因果方向**"，作为**负结果**发表（项目已有 4 个负结果记录惯例） |

### 命令
```bash
python scripts/f4_intervention_test.py \
    --n-topologies 30 --action delete_bridge --control delete_nonbridge \
    --predict-direction increase --seed 42
# 门禁绑定：Gate 45 校验命中率 ≥ 0.70，且干预集与拟合集拓扑 ID 无交集
```

---

## PR-3 — F3 跨图族泛化（普适性）

| 项 | 预注册值 |
|---|---|
| **图族** | 5 个：① 项目合成（evidence/random/mixed）② Erdős–Rényi ③ Barabási–Albert ④ Watts–Strogatz ⑤ **MaleCNS 真实连接组子图**（唯一真实数据源） |
| **规模** | `n_nodes ∈ {10, 20, 50, 100}`（修正当前仅在 n=10 上取证的局限） |
| **流程** | 在 ① 上拟合系数 → 在 ②③④⑤ 上**只做预测不重拟合** |
| **成功判据** | **≥3 个图族**（必须含 ⑤ 真实连接组）AUC 方向一致且 ≥ 0.65 |
| **失败判据** | 仅 ① 成立 → 主张**如实收窄**为"合成拓扑族内规律"，并在论文中明确标注外推边界 |
| **必报项** | 泛化**失效边界**（哪个图族、哪个规模开始失效）—— 边界本身是可发表的结果 |

---

## PR-4 — F2 恢复动力学（修复退化分量）

| 项 | 预注册值 |
|---|---|
| **现状缺陷** | `mean_recovery_steps`：N=50 中 **32 个（64%）为 0.0**，仅 9 个取值，方差 0.0308 → 准退化 |
| **根因假设** | ① 极小图（n=10/11 边）路径长度变化空间趋零；② **完全断开的节点对被排除**，最严重后果不入度量；③ 只建模"旁路募集"一种代偿 |
| **替换度量** | `recovery_AUC`（故障后 t=1..T 功能恢复率曲线下面积）+ `t_half`（半恢复时间） |
| **三代偿机制** | R-a 旁路募集（已有）· **R-b 权重重分配** · **R-c 稳态增益**；三者做消融 |
| **成功判据** | `recovery_AUC` 零值占比 **< 30%**（当前 64%）且方差 > 0；三代偿消融至少给出 1 个显著主效应 |
| **过渡规则** | 未完成前，对外**只报 `drop_magnitude` + `affected_module_count` 两个分量**，第三分量标注 `under_reconstruction` |

---

## PR-2b — 度量替代预检（PR-2 的补救方案，预执行拒绝）

> **本段是「预执行拒绝」而非预注册实验**：判据在跑之前写定，跑出来的不是实验结果，
> 而是**「这个实验值不值得跑」**的裁决。这是 R-0.4「失败即发表」的延伸——
> 把"没有跑的实验"连同拒绝理由一并固化，比事后辩解更值钱。

### 起因
PR-2 在 n=10（38.9%）与 n=50（H1 71.4% / composite 42.9%）两次 FAIL。n=50 的诊断指出
`drop_magnitude` 在 n=50 已不饱和（方差恢复），但效应量过小（mean_delta ≈ −0.0004），
桥边与非桥边信号不可区分。上一轮因此提议：**改用 `recovery_AUC`（PR-4 的度量）作 PR-2 的后果变量**，
理由是它"更细粒度、不饱和"。

这个提议在跑之前必须被检验，因为它可能是一个**同义反复（tautology）**。

### 待检验的机制断言
`scripts/f2_recovery_dynamics.py` 中：

```
modulator_Ra = 1 - bridge_fraction - 0.5 * ap_fraction      # 含 bridge_fraction
recovery_AUC = mean_t( r(t) ) / drop_magnitude               # 以 drop_magnitude 归一
```

即 `recovery_AUC` 是 `(1 - bridge_fraction)` 的单调函数，**且被 PR-2 本身测量的量归一化**。
若两条都成立，`delete_bridge` 会**由构造**移动 `recovery_AUC`，此时"方向命中率 > 70%"
不承载任何因果信息。

注意方向的反直觉之处：删一条桥边会**降低** `bridge_fraction`（分母 `n_edges` 同时减少，
`(B-1)/(E-1) < B/E`），从而**抬高** R-a 调节器、**抬高** `recovery_AUC`——
也就是它会在"你切断了系统"的时候报告"恢复能力上升"。这是**分母伪影**，不是效应。

### 拒绝判据（跑之前写定）
在 `delete_bridge` vs `delete_nonbridge` 的配对拓扑上，两者同时成立即 **REJECT**：

| 判据 | 阈值 | 检验对象 |
|---|---|---|
| **(i) 解析耦合** | `|corr(Δbridge_fraction, Δrecovery_AUC)| ≥ 0.50` | 桥边臂（干预组） |
| **(ii) 伪影率** | 删桥边后 `recovery_AUC` 上升的占比 ≥ **90%** | 桥边臂（干预组） |

方向假说：若把 `recovery_AUC` 当 PR-2 后果变量，其声明方向应为 **下降**（故障后代偿恶化）。
因此 (ii) 的"上升占比"越高，越说明该度量在报告与结构动作相反的伪影。

### 命令
```bash
python scripts/f4b_metric_substitution_check.py \
    --n-topologies 30 --n-nodes 50 --start-idx 200 --seed 42 \
    --coupling-corr-min 0.5 --artifact-rate-min 0.90 \
    --output-dir ./_f4b_metric_substitution
# 门禁绑定：Gate 45 校验 research_claims.json.preregistered.PR2b 与本段阈值一致
```

### 实测结果（2026-10-14，n=50，21 对可配对拓扑）

| 量 | 桥边臂 | 非桥边臂 |
|---|---|---|
| 均值 Δbridge_fraction | −0.0097 | +0.0124 |
| 均值 Δrecovery_AUC | **+0.0079** | **−0.0076** |
| 均值 Δdrop_magnitude | −0.0001 | −0.0002 |

| 判据 | 实测 | 阈值 | 触发 |
|---|---|---|---|
| (i) 解析耦合 `|corr|` | 0.3537（桥边臂） | ≥ 0.50 | ❌ |
| (ii) 伪影率 | **95.2%**（20/21） | ≥ 90% | ✅ |
| **规则裁决** | | | **ACCEPT** |

### 拒绝规则自身欠功率（本次最重要的产出）

规则判 ACCEPT，但 (i) 未触发的原因不是"没有耦合"，而是**样本方差被压缩**：

| 样本 | `corr(Δbridge_fraction, Δrecovery_AUC)` | `var(Δbridge_fraction)` |
|---|---|---|
| 桥边臂（规则指定样本） | −0.3537 | 4.82e-05 |
| **双臂合并** | **−0.9020** | **2.38e-04** |
| 非桥边臂单臂 | −0.9056 | — |

合并样本的方差是桥边臂的 **4.9 倍**。解析耦合在具备功率的样本上被**确认**（|r| = 0.90–0.91），
而"单调"这个要问的问题在桥边臂内本来就无从检验（桥边全被删掉，`bridge_fraction` 只在
1e-3 量级抖动）。这正是本项目 **S7 分辨率预检纪律**应用于门禁自身：
**先验证检测手段的分辨力是否匹配待检验命题的几何尺度，再读结论。**

### 裁决与理由

**PR-2b 不执行。** 拒绝成立，但依据**不是**规则的 verdict：

1. **解析检查**：`modulator_Ra` 显式包含 `bridge_fraction`，`recovery_AUC` 显式被
   `drop_magnitude` 归一化——耦合可**查代码即证**，无需经验估计。
2. **伪影率 95.2%**：21 对中 20 对删桥边后 `recovery_AUC` 上升，85.7% 的非桥边臂则下降，
   两个臂在方向上近乎完全分离。一个能把两臂分到 95%/86% 的度量，是在**跟随干预动作**，不是独立读数。
3. **规则欠功率**已如实记录（`power_diagnostic.rule_underpowered = true`），
   判据阈值**未被修改**。规则保持 ACCEPT 是规格缺陷的证据，不是放行依据。

**未走的路径（必须披露）**：本可在 n=100 / n=200 上重试，或换用 `t_half`。
均不执行——`t_half` 与 `recovery_AUC` 由同一条轨迹派生，耦合性质相同；
扩大 n 只改变效应量，不改变"分母伪影"这一构造级缺陷。

**结论边界**：`drop_magnitude` 在 n ≤ 100 的桥边干预下效应量 ≤ |0.001|，
与任何"细粒度"替代度量的信号分离度同量级。本项目的干预级证据（L4）**当前不可达**，
不是实验没跑够，而是**现有度量族内没有独立的第二读数**。要突破需要一个
**不由 `bridge_fraction` 派生**的后果量（例如真实动力学下的功能读出），
这超出本项目当前的计算基底。

---

## 验收矩阵（一眼看清当前在哪一档）

| 协议 | 对应门禁 | 当前 | 通过判据 |
|---|---|---|---|
| PR-1 前瞻性预测 | **Gate 43** | ❌ WEAK（AUC 0.788 ✅，z=1.53 ❌） | held-out AUC ≥ 0.70，z ≥ 3.0 |
| PR-2 干预/因果 | **Gate 45** | ❌ FAIL（n=10/50/100 三次，命中率 38.9%→71.4%→59.1%） | 方向命中率 ≥ 70% |
| PR-2b 度量替代预检 | **Gate 45** | ⛔ **预执行拒绝**（伪影率 95.2%，合并耦合 r=−0.90） | — |
| PR-3 跨图族泛化 | **Gate 44** | ❌ FAIL（n=10/20/50/100 共 20 格，2/5 图族，真实连接组始终 0 正例） | ≥3 图族（含真实）AUC ≥ 0.65 |
| PR-4 恢复动力学 | **Gate 46** | ✅ PASS（零值 0%，方差 0.0114） | 零值占比 < 30% |

**证据等级推进路径**：L2（已达：37 门禁 + 注入 100%）→ **L3（PR-1）→ L4（PR-2）→ L5（F1 解析理论 / 第三方复现）**。

---

## 与公开仓战略的关系

本协议的**全部内容无需公开仓库即可执行**：预注册的时间戳意义由 `research_claims.json` 的 `preregistered` 字段 + `CHANGELOG.md` + git 提交历史共同提供（内部可追溯）。
待 G1–G8 门槛达成、决定公开时，本文件连同 git 历史一并公开即可构成完整的时间戳证据链——**因此现在必须严格按 R-0.1 冻结规则执行，不得事后修改**。
