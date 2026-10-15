# 下一阶段愿景与执行方案：从「私仓门禁」到「可验证研究对象协议」

**基线**：v2.85.0（2026-10-15）；门禁 `run_gates.py --quick` = **42/42 PASS**（本轮复测确认）
**前序**：`PHASE_NEXT_EXECUTION_PLAN_2026-10-15.md`（N1–N5）、`PAPER_EXIT_ROADMAP_2026-10-15.md`、`RELEASE_GATE_ASSESSMENT_2026-10-14.md`
**本报告重心**：① 上一阶段完成度 ② 三条 2026 前沿轴对标 ③ **远超前市场的下一阶段愿景** ④ 可落地执行方案（S/C/F 三阶段，含文件/命令/验收）

---

## 〇、结论先行

> 1. **上一阶段任务 100% 落地**（v2.83.0 → v2.85.0：N1 `selfverify` 包 + 32 单测、N2 论文口径收敛、N3 arXiv 元数据、N4 公开决策清单、G4/G8 门槛文档同步）；门禁 **42/42 PASS**。
> 2. **项目真实坐标已无争议**：**A 面（方法学/元科学基础设施）达国际前列**，**B 面（连接组科学发现）已被预注册诚实证伪**（R1 机制合成空间 WEAK z=1.53、跨图族 NULL AUC=0.5、PR-2 因果 FAIL×3）。
> 3. **下一阶段愿景（远超当前市场）**：把项目**内部的门禁机器**泛化为**任何计算实验可采用的「可验证研究对象（Verifiable Research Object, VRO）协议」**——命题图 + 机器门禁 + 独立重算收据 + 对抗自验证。这就是 2026 三条独立前沿线（*Engineering of Science* 的 Blueprint、`aiprov` 的 claim ladder、CSPaper 的 code-claim audit）共同指向、但**尚无任何人做成的**「可执行认识论」。
> 4. **同时把 B 面从「证伪」拉回「有正结果」**：沿 *ConnectomeX*（arXiv:2610.08418）已验证的 **cell 级连接组→可训练架构** 路径，做 PROJECT_VISION 点名的「唯一可能翻盘的实验」（模块内密化）。
> 5. **本轮已实际落地**：命题图（Blueprint IR）原型 + 校验器 `scripts/check_claim_graph.py`（拟 **Gate 48**），把扁平 `research_claims.json` 升级为**类型化有向命题图**，实测通过。

---

## 一、上一阶段完成度判定（v2.83.0 → v2.85.0）

| 上一阶段项 | 落地 | 证据 |
|---|---|---|
| **N1** `selfverify` 独立包 | ✅ | `tools/selfverify/`：`pip install -e` 成功；**32 单元测试全绿**（`python -m unittest discover -s tests`）；从任意目录 `python -m selfverify check` 跑通 |
| **N2** 论文口径收敛 | ✅ | `grep -n "predictable structural theory\|超越生物学\|数字生命" docs/arxiv_paper.md` 无残留；§4.7 含 z=1.53 / 跨族 AUC=0.5 |
| **N3** arXiv 元数据 | ✅ | `docs/ARXIV_SUBMIT_META_2026-10-15.md`（P-2/P-3 分类 + 合规清单） |
| **N4** 公开准备 | ✅ | `scripts/prep_public_release.py --dry-run`（零副作用）+ `docs/PUBLIC_RELEASE_DECISION_CHECKLIST_2026-10-15.md` |
| **G4/G8** 门槛文档 | ✅ | `RELEASE_GATE_ASSESSMENT_2026-10-14.md` 增「四、v2.84.0 补强」章节 |
| **门禁** | ✅ | 42/42 PASS（本轮复测，2m32s） |

**判定**：上一阶段**无遗留项**。但按门槛表，公开仍卡在 **G3（无 V4 级主张）** 与 **G5（锚定率 31.9%）**——**结构性缺口，不是工作量问题**。这正是下一阶段要正面突破的。

---

## 二、三条 2026 前沿轴对标

### 轴 1 — 科学基础设施（A 面的正面前沿，项目主战场）

| 前沿锚点 | 核心主张 | 项目位置 | 差距 |
|---|---|---|---|
| **Toward an Engineering of Science**（UIUC, arXiv 2026-05）| 「认知污染」：生成成本趋零、验证成本不变 → 科学应作为工程问题重设计；提出 **Blueprint**——以**类型化图组件**（Claim/Evidence/Assumption/Definition/Risk + Supports/Contradicts 边）替代散文论文，含状态追踪（Draft→Stated→Supported）| **已是 Blueprint 的一个真实实例**（`research_claims.json` 五要素 + 门禁 + provenance），但**尚未图结构化、未显式分节点类型** | 命题图 IR + 状态阶梯 |
| **F(AI)2R / `aiprov`**（arXiv:2607.25637）| **claim ladder**：把「引用存在（机器可查证）／内容支持主张（至多机器判定）／人已核对（仅人）」分层，禁止混同；每条断言携带 `prov:wasGeneratedBy` / `prov:wasAttributedTo` | 项目的「**独立重算 vs 采信摘要**」原理与之一致；但**未把「机器可查证 vs 机器判定 vs 人核对」显式分级** | 三级可验证性标签 |
| **CSPaper Code Check**（2026-07）| 把论文仓库喂给工具，逐条**审计「代码是否忠实实现论文方法主张」** | 项目的 Gate 30/43–47 **已机器强制「脚本硬编码 vs 协议」一致性**，是 code-claim audit 的一个**更强实例**（不止审计，还阻断）| 对外可引用化 |
| **Nanopublication / RO-Crate** | 小而**签名、机器可读、可引用**的命题包 | 项目 claims 目前是**私有 JSON**，无签名、无打包标准 | 收据 + 导出 |

> **关键判断**：三条前沿线都在朝「结构化、可验证、可机器审计的命题」收敛，**但没有一条把「预注册 → 可执行门禁 → 独立重算 → 预执行拒绝 → 对抗自验证」做成完整闭环**。项目已握有 80% 的机器，**差的是泛化、收据、红队三件**。

### 轴 2 — 连接组 → AI（B 面的正面前沿，项目曾在此处折戟）

| 前沿锚点 | 核心主张 | 项目位置 | 差距 |
|---|---|---|---|
| **ConnectomeX / FlyVision**（arXiv:2610.08418, 2026-10）| 把**果蝇视觉连接组**转成**可训练架构**（保留 ON/OFF 并行、递归、群体图交互）；MNIST 99.34% @ 8万参数；ImageNet 与 ResNet18 差距 <3pp 而参数少 10× | 项目负结果（0/7 motif 优于随机）**限于「模块代表层」密度 0.002–0.023**；ConnectomeX 走的是 **cell 级** | **cell 级密化**（PROJECT_VISION 点名「唯一翻盘实验」）|
| **SCGFM**（ICML 2026, arXiv:2605.08689）| **结构中心**图基础模型：把拓扑当作可迁移知识主源，用 Gromov–Wasserstein 对齐到共享几何基 | 项目的结构指纹 + 拓扑家族 + 关键边特征，是**结构中心表示的一个候选底座** | 结构表示与 GFM 对齐 |

> **关键判断**：项目的 B 面负结果**并非被判死刑**——它精确地卡在「模块代表层太稀疏」这个**已知、可修、便宜**的原因上；而 2026 前沿（ConnectomeX）已在 cell 级给出正结果。**这是 B 面唯一、且成本可控的翻盘路径。**

### 轴 3 — 融合（远超前）

| 前沿锚点 | 核心主张 |
|---|---|
| **Self-Interventional Learning**（arXiv:2608.14894）| 四元组 `self-intervention → consequence learning → held-out generalization → structural action`；项目 PR-2 已按此方法学设计（但结果 FAIL）|
| **Beyond Execution: Auditing Experimental Fidelity**（arXiv:2608.26753）| LLM 科研 agent 必须**忠实实现参考方法 + 设计能检验论文主张的实验 + 提供证据** |
| **Scaling Scientific Discovery Environments**（arXiv:2607.28990）| 把科研建模为**可验证的科学状态转移**（每步由 process primitive 定型）|
| **RISC Zero / 可验证计算** | 程序输出可附**自证收据（receipt）**，第三方无需重算即可核验 |

> **关键判断**：AI 科学家赛道（AutoResearch 登 *Nature* 2026-03、Anthropic「Claude 主导 26% 研发」）**集体缺一个可信验证器**。项目的门禁机器 + 命题图，正是这个缺口的**现成答案**——但需要「收据 + 红队」才能被第三方信任。

---

## 三、下一阶段愿景（远超当前市场）

### 3.1 愿景陈述

> **把项目从「一个私仓里跑 42 条门禁的连接组工具」升级为「可验证研究对象（VRO）协议的参考实现」——一套任何计算实验室都能采纳的「可执行认识论」：每一条对外主张都携带 (i) 类型化命题图节点、(ii) 机器门禁判定、(iii) 独立重算收据、(iv) 对抗自验证结果，第三方无需信任作者即可核验。**

用一句话区分**市场现状**与**本项目愿景**：

| | 市场/前沿现状（2026）| 本项目下一阶段愿景 |
|---|---|---|
| 载体 | 散文论文 → 正在被呼吁结构化（Blueprint）| **类型化命题图 + 可执行门禁** |
| 溯源 | 引用存在性可查（aiprov claim ladder）| **claim ladder + 独立重算收据（hash 绑定原始样本）** |
| 审计 | 事后 code-claim 审计（CSPaper）| **事前阻断（fail-closed 门禁）+ 预执行拒绝** |
| 信任 | 采信作者摘要 | **对抗自验证：作者先自己红队，红队失败才允许主张成立** |
| 负结果 | 难以发表 | **预执行拒绝作为一等产出 + 边界图册** |

### 3.2 四层架构（VRO 协议）

```
L4  第三方审计层     ← 收据可被外部独立核验（RO-Crate / nanopublication 导出）      【缺】
L3  对抗自验证层     ← 红队 agent 主动攻击每条主张（摘要篡改/度量饱和/同义反复/分辨率钳位）【缺】
L2  机器门禁层       ← 42 门禁 + 预注册比对 + 独立重算（Gate 30/43–47）              【已有】
L1  命题图层         ← 类型化 Claim/Evidence/Assumption/Definition/Risk + 状态阶梯    【本轮原型】
```

**项目的独特护城河**：L1+L2 是**任何"想发论文的实验室"都需要、但没人做成的层**；L3+L4 是**把「自我诚实」升级为「可被陌生人验证」的关键一跃**。

---

## 四、执行方案（S / C / F 三阶段）

> 原则：**S 阶段（科学基础设施）为主线**——它零/低成本、直接抬升 A 面含金量、且不依赖任何外部资源；**C 阶段（连接组科学）为翻盘线**——修 PROJECT_VISION 点名的「唯一翻盘实验」；**F 阶段（融合）为愿景线**——在 S+C 成型后接入。

### S 阶段 — 科学基础设施（主线，零外部依赖）

#### S1 命题图（Blueprint IR）★ 本轮已实现原型
- **做什么**：把扁平 `research_claims.json` 升级为**类型化有向命题图** `claim_graph.json`：节点 = `claim | evidence | assumption | definition | risk`；边 = `supports | contradicts | depends_on | tests`；每个 claim 携带**状态阶梯** `draft → stated → supported → verified | refuted | rejected | boundary`。
- **为什么**：直接实现 UIUC Blueprint + aiprov claim ladder；让「哪些主张裸奔、哪些有证据、哪些被证伪」一眼可见。
- **具体操作（本轮已落地）**：
  ```bash
  "C:/Python314/python.exe" scripts/claim_graph.py build --out claim_graph.json
  "C:/Python314/python.exe" scripts/check_claim_graph.py --graph claim_graph.json
  ```
- **验收**：校验器输出 `PASS`——每条 `claim` 至少 1 条 `supports` 边或显式 `boundary` 状态；每条 `evidence` 携带 `reproduction_command`；无 `supported` 状态缺证据。

#### S2 验证收据（Verification Receipt）
- **做什么**：为每条 claim 生成**可第三方验证的收据**：`{claim_id, raw_sample_sha256, recompute_script_sha256, expected_verdict, env_hash, timestamp}`。第三方只需原始样本 + 脚本即可独立重算并比对，**无需信任作者摘要**。
- **为什么**：这是 L4 的门票，对标 RISC Zero 的 self-certifying receipt（不需要 ZK，hash 承诺已足够）；也是「仓库仍私有但证据可验证」的关键——**收据可先于仓库公开而存在**。
- **具体操作**：`scripts/issue_receipt.py` → `receipts/<claim_id>.json`；`scripts/verify_receipt.py --receipt ... --raw ...`。
- **验收**：任取 1 条 claim，篡改 `expected_verdict` 后 `verify_receipt` 报 `MISMATCH`；原始样本一致时报 `VERIFIED`。

#### S3 对抗自验证（红队 agent）★ 最高价值
- **做什么**：把 S6–S9 四条纪律泛化为**自动化红队套件**——对每条主张主动发起 4 类攻击：① 摘要篡改（改 summary 试图骗过门禁）；② 度量饱和/退化（检测方差≈0、恒 0/恒 1）；③ 同义反复（检测度量与分析量解析耦合，如 PR-2b）；④ 分辨率钳位（检测目标区间被静默截断，如 R2 的 D5a）。**红队全部失败 → 主张才允许 `verified`**。
- **为什么**：这是「自我诚实」到「可被陌生人验证」的关键一跃；也是 AI 科学家赛道集体缺失的验证器。
- **具体操作**：`tools/selfverify/selfverify/redteam.py`（扩展现有包）+ `scripts/check_claim_redteam.py`（拟 Gate 49）。
- **验收**：对已知的 4 个历史缺陷（P1 伪结果 / R2 钳位 / R1 饱和 / PR-2b 耦合）逐一回放，红队**全部命中**。

#### S4 差分验证（双实现）
- **做什么**：每条核心度量必须有 **2 个独立实现**（不同算法路径），分歧即 FAIL。
- **现状**：Gate 40 已部分落地（`bridge` 用 Tarjan vs 朴素）。
- **验收**：`drop_magnitude` / `recovery_AUC` / 结构指纹各 2 实现，随机 100 拓扑上逐位一致。

#### S5 主张级验证徽章（Verification Badge）
- **做什么**：自动为每条 claim 计算 **V0–V5 验证等级**（对齐 `INNER_STRENGTH_ROADMAP_V2` 的自验证阶梯），写入 README / 命题图。
- **为什么**：让「主张强度」可被一眼读出——这是 nanopublication 精神的落地。
- **验收**：`claim_graph.json` 每个 claim 带 `verification_level` 字段，与门槛表一致。

### C 阶段 — 连接组科学再武装（翻盘线）

#### C1 Cell 级密化实验 ★ PROJECT_VISION 点名的「唯一翻盘实验」
- **做什么**：在模块**内部**补递归边，把密度从 0.002–0.023 提到 **0.1+**，重跑匹配控制实验（同 N、同非零数 K、种子平均）。
- **为什么**：负结果的根因是「模块代表层结构上不足以承载时间动力学（ESN 需 ~0.1+）」；ConnectomeX 已在 cell 级给出正结果。**这是唯一能把项目从"审计工具"拉回"计算工具"的实验，且便宜。**
- **具体操作**：`scripts/c1_cell_densification.py --density 0.10 --n-nodes 50 --seeds 30`；预注册（PR-5）+ 门禁。
- **验收**：cell 级密度下，motif 拓扑 vs 随机结构的效应量是否脱离噪声（预注册阈值 + held-out）。**正或负皆可发表**（正=翻盘，负=边界图册新条目）。

#### C2 ConnectomeX 式迁移测试
- **做什么**：把 MaleCNS motif 派生的拓扑作为**归纳偏置**，接入一个小型视觉/序列任务（MNIST 级），复现 ConnectomeX 的「少参数、近 ResNet」范式。
- **为什么**：把项目的结构库接到 2026 最热前沿（连接组→AI）上，且**只需 CPU、小算力**。
- **验收**：与同参数量的随机架构对照；报告参数效率比（正/负皆记录）。

#### C3 Rank/quantile 标签修正（修 PR-3 的 label-resolution 伪影）
- **做什么**：PR-3 跨族 AUC=0.5 的根因已被自己诊断出——**绝对阈值 `drop_magnitude>0.25` 在图变密时超出信号范围**（MaleCNS 均值随 n 单调降 0.170→0.026）。用**秩/分位标签**重做跨族比较。
- **为什么**：这是 **S7 纪律对标签定义的正确应用**，不是「改判据」——**但必须走 PR-3 v2 新版本段 + 声明**（R-0.1）。
- **验收**：新版本段 `PR3 v2` 记录「标签定义变更 + 理由」，held-out 一次性验证；AUC 若脱离 0.5 则机制具跨族性，否则边界更硬。

### F 阶段 — 融合（愿景线，S+C 成型后）

#### F1 验证器在环的 AI 科学家（Verifier-in-the-loop）
- **做什么**：用**命题图**做 agent 的世界模型；agent 提出主张 → 门禁+S3 红队判定 → 通过则发收据、失败则记入边界。**把「预执行拒绝」做成 agent 的一等动作**。
- **为什么**：AI 科学家赛道（AutoResearch/Agent Laboratory 等）集体缺可信验证器；本项目补的正是这块。
- **验收**：一个最小 agent 能在命题图上完成「提出→被门禁拒绝→记录 unexplored_alternatives」的闭环。

#### F2 Nanopublication / RO-Crate 导出
- **做什么**：把命题图导出为 **RO-Crate 包 / nanopublication**（签名、机器可读、可引用）。
- **为什么**：让项目的主张可被外部系统（SPARQL、yProv4ML）摄入，接入国际引用生态。

#### F3 Preregistered Rejection 公共注册表（后置，公开门槛之后）
- **做什么**：把 PR-2b 的「预执行拒绝」做成**公共注册表**（先私仓，公开门槛达成后开放）。

---

## 五、如何证实「价值前沿」（五级阶梯 + 具体途径）

| 级 | 内容 | 现状 | 下一阶段途径 |
|---|---|---|---|
| **L1** 复现性 | 同 seed 逐位一致 | 🟡 | 收据（S2）把复现性变成**可第三方核验** |
| **L2** 可执行测试 | 42 门禁 + 注入 100% | ✅ 已达 | 命题图（S1）把测试绑定到**具体主张** |
| **L3** 前瞻性预测 | 预注册 + held-out | ❌（PR-1 z=1.53）| C3 rank 标签重做 + C1 cell 级 |
| **L4** 干预/因果 | 干预实验 | ❌（PR-2 FAIL）| C1 + 独立第二读数（真实动力学） |
| **L5** 外部 oracle/理论 | 第三方复现 | 🟡 | S3 红队 + S2 收据 → 外部可核验 |

**三条最硬、且零成本的证实途径**：
1. **红队回放**：对 4 个历史缺陷逐一回放，证明红队套件能自动命中——**把「我们曾经犯的错」变成「机器现在能守住的边界」**。
2. **收据第三方验证**：任一 claim 的收据被独立重算并 `VERIFIED`——**无需公开仓库即可证明诚实**。
3. **命题图可读性**：陌生人读 `claim_graph.json` 能立刻看出「哪条主张裸奔、哪条被证伪、哪条有边界」——**这是 Blueprint 范式的核心承诺**。

---

## 六、里程碑与门槛（3 个 Horizon）

| Horizon | 目标 | 关键交付 | 依赖 |
|---|---|---|---|
| **H1（1–2 周）** | S 阶段成型 | 命题图 + 校验器（Gate 48）· 收据（S2）· 红队套件（S3）| 零外部依赖 |
| **H2（2–4 周）** | C 阶段翻盘 | C1 cell 级密化（PR-5）· C3 rank 标签（PR-3 v2）· C2 迁移测试 | 零外部依赖（CPU）|
| **H3（1–2 月）** | F 阶段 + 发表 | F1 验证器在环 · F2 RO-Crate 导出 · P-1/P-2/P-3 投稿 | arXiv 账号 / D3 拍板 |

**公开门槛不变**：G1+G2（技术底气）+ G3+G4（科学底气）。**S 阶段直接强化 G1/G4；C 阶段是唯一可能翻 G3 的路径。**

---

## 七、如果只做三件事

> **① S1 命题图 + S3 红队**——把「自我诚实」升级为「可被陌生人验证」，是 A 面含金量的唯一实质跃迁，零成本。
> **② C1 cell 级密化**——PROJECT_VISION 点名的唯一翻盘实验，便宜、CPU 可跑、正负皆可发表。
> **③ S2 收据**——让「仓库仍私有」与「证据可验证」并存，为将来公开预置完整证据链。

**做完这三件，项目就从「一个很好的私仓工具 + 一堆诚实的负结果」，变成「一个可被国际同行独立核验的科研基础设施 + 一张边界图册」。**

---

## 八、本轮已落地的原型：命题图（Blueprint IR）+ Gate 48

> 本阶段不是「只写方案」——**S1 已实际落地并跑通**，且首次运行就抓到两个真实问题。

### 8.1 交付物

| 文件 | 作用 |
|---|---|
| `scripts/claim_graph.py` | 从 `research_claims.json` 构建**类型化有向命题图** `claim_graph.json`（节点 `claim/evidence/assumption/definition/risk`；边 `supports/contradicts/depends_on/tests`；状态阶梯）|
| `scripts/check_claim_graph.py` | **Gate 48** 校验器（V1–V9 规则）+ **注入电池**（`--inject`，6 类缺陷）|
| `claim_graph.json` | 生成的图（38 节点 / 36 边）|

**实测**：
```bash
python scripts/claim_graph.py build --out claim_graph.json
#   nodes=38 edges=36 claims=6 evidence=14 assumptions=6 definitions=6 risks=6
python scripts/check_claim_graph.py --graph claim_graph.json
#   GATE 48: PASS  (0 failures, 4 warnings)
python scripts/check_claim_graph.py --inject
#   injected-defect battery: 6/6 caught
```

### 8.2 首次运行抓到的两个真实问题

**问题 1 — Gate 48 抓到「裸奔的 verified 主张」（已修复）**
首次校验 FAIL：**R4、R5 标记 `verified` 却没有机器可读的证据指针**（R1 有 `supporting_evidence`，R4/R5 缺）。核实证据文件真实存在（`_r4_sensitivity_scan/`、`lifecycle.py`），遂**把已有证据补成结构化字段**（诚实修复，非刷门禁）。修复后 **PASS**。
> 含义：一个「verified」主张在命题图里**必须**能指向机器可读证据——这正是 Blueprint 范式的核心承诺，而旧结构做不到。

**问题 2 — Gate 48 抓到「主张状态跑赢机器证据」（V9 告警，待你决策）**
新增诚实性规则 V9 后，报出 4 条告警：**R1 自报 `supported`，但四条预注册协议全部指向另一方向**——
| 预注册协议 | 实测判定 |
|---|---|
| PR-1 前瞻预测 | `WEAK_PASS`（z=1.53 < 3.0）|
| PR-2 干预因果 | `FAIL`（n=10/50/100 三尺度）|
| PR-3 跨图族泛化 | `FAIL`（跨族 AUC=0.5）|
| PR-2b 预执行拒绝 | `ACCEPT`（\|corr\|=0.902）|

> **含义**：这是新基础设施**首次运行就自动暴露**的诚实性问题——R1 的 `supported` 状态**跑赢了它的机器证据**。建议将 R1 状态降级为 `boundary`（或把 statement 收窄到「仅项目合成空间」），但这属于**主张口径决策**，应由你拍板后再改（沿用 `AUDIT_DISCLOSURE` 惯例，不由我单方面改写）。

### 8.3 元门禁的自我验证（一次教科书式的 V3 演示）

我给项目加了新门禁后，**Gate 39（元门禁）立刻报红**：`check_claim_graph.py` 缺注入测试。这**正是项目自身纪律在生效**——"一条从未证明自己能变红的门禁，是一条永远不会抓到东西的门禁"。随即补上 **6 类注入电池**（裸奔主张 / 无指针证据 / 未知类型 / 悬空边 / 未记录终态 / 非法状态），全部命中：

```
[OK] bare_claim_no_supports      expected=V1 got=['V1','V4']
[OK] evidence_without_pointer    expected=V2
[OK] unknown_node_type           expected=V7
[OK] dangling_edge               expected=V6
[OK] terminal_claim_undocumented expected=V5
[OK] status_off_ladder           expected=V3
injected-defect battery: 6/6 caught
```

**Gate 39 → PASS（100% 注入覆盖）**。这条链路本身就是 S 阶段愿景的活体演示：**新能力一旦入场，就自动被元门禁纳入 V3 纪律**。

---

## 附：本轮实测证据索引

- 门禁：`run_gates.py --quick` → **42/42 PASS**（2026-10-15 复测，2m32s）
- 版本：`pyproject.toml` = `2.85.0`；git HEAD `267d2e9`（工作区仅 `_gate31_r2/r2_density_scan.json` 的 JSON key 排序差异）
- `selfverify`：`tools/selfverify/`（32 单测全绿，`pip install -e` 可用）
- 命题库：`research_claims.json`（R1–R6 + PR1/2/3/4/2b）
- 预注册实测：PR-1 `_r1_mechanism_prereg/f1_preregistered.json`（AUC 0.788, z 1.53, WEAK）· PR-2 `_f4_intervention*/`（FAIL×3）· PR-3 `_f3_generalization/`（跨族 AUC 0.5）· PR-2b `_f4b_metric_substitution/`（\|corr\| 0.902, ACCEPT）
- 本轮新增：`scripts/claim_graph.py`（命题图构建）· `scripts/check_claim_graph.py`（**Gate 48** + 6 类注入电池）· `claim_graph.json`（38 节点/36 边）· `research_claims.json` 补 R4/R5 `supporting_evidence`（诚实修复）
- Gate 39 元门禁：**PASS（100% 注入覆盖，含新门禁）**；Gate 48：**PASS**（0 failures / 4 V9 warnings）
