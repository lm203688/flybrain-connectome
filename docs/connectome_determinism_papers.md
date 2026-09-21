# Connectome Determinism & Cross-Species Wiring Rules

> 一手研究素材 — 为 `flybrain-connectome` 层2（模块组合规则库）提供证据锚点。
> 触发信号：新闻「把人脑神经元种进老鼠脑子，它还是一只老鼠」。
> 编写日期：2026-09-21。所有论断均指向具体论文 / URL；无法确认的字段标「未确认」。

---

## 1. 触发新闻 & 原始研究

### 1.1 原始论文（已确认 ✅）

**标题**：Developmental xenocortication using human-derived organoids in mice
**作者**：Konstantin Kaganovsky, Kevin W. Kelley, Tilo Gschwind, … Karl Deisseroth, Sergiu P. Pașca
**机构**：Stanford University（Pașca Lab）
**期刊 / 年份**：*Nature*，online 2026-09-16（正式卷期见链接）
**DOI**：`10.1038/s41586-026-11032-2`
**链接**：https://doi.org/10.1038/s41586-026-11032-2
**媒体报道（可读的中文/英文解读）**：
- NYT 转载（ekathimerini）：https://www.ekathimerini.com/nytimes/1315564/these-mice-have-partly-human-brains/
- Science / Science Robotics：https://robotics.sciencemag.org/content/article/human-neurons-flourish-mouse-brains-offering-new-view-neurodevelopmental-disorders
- Inside Precision Medicine：https://www.insideprecisionmedicine.com/topics/translational-research/human-cortical-organoids-expand-across-a-cortex-depleted-mouse-brain

### 1.2 关键实验设计与核心发现

- **谁移植谁**：把**人源皮层类器官（human cortical organoids，源自人干细胞）**移植进**基因工程「无皮层」免疫缺陷小鼠（apallial / XCX 小鼠）**——这些小鼠因 `Emx1-CRE; Esco2fl/fl` 杂交 + `Prkdc` 突变，几乎不发育新皮层/海马，也不排斥异种移植。
- **整合程度**：移植 3 个月后，人源组织占皮层体积的 **91.9%**；体积增长约 4.7 倍；人源神经元向宿主丘脑、上丘、苍白球的皮下结构投射，并接受宿主旧皮层、丘脑输入。弥散加权成像证实移植体与宿主间形成**稳定、一致的连接模式**。宽场钙成像记录到移植体神经元局部钙爆发并向其他区域传播。
- **行为观察（核心结论）**：
  - 旷场、CatWalk 步态、Y 迷宫工作记忆、三箱社交——**XCX 小鼠运动能力与社交均正常，与对照无差异**。
  - 条件性恐惧训练阶段僵直反应减少（获得性恐惧记忆存在障碍）——但这是**人源组织参与**而非「变成人」。
  - 缺氧损伤后，人源组织 HIF1α 显著升高、胶质细胞密度增加，而邻近小鼠皮层不升高——证明宿主小胶质细胞是针对**人源细胞**的缺氧损伤反应。
  - 出现小鼠模型中难以培养的 **L5-ET 神经元**与**冯·埃科诺莫神经元（VENs）样细胞**（人类/类人物种特有的长投射神经元）。
- **专家定性**（直接引用，见 NYT 转载）：
  > "You wouldn't be able to tell the difference." — Pașca
  > "It may have a large proportion of its brain made up of human cells, but **none of its behavior is made up of human behavior**." — Madeline Lancaster（MRC LMB）

### 1.3 直接支持本项目假说的引用原文（3-5 条）

1. **行为是连接/环路层面的属性，而非细胞来源的身份**：Lancaster 原话——「它大脑大部分由人类细胞构成，但**没有任何一种行为是由人类行为构成的**」。→ 智能/行为由**拓扑（接入哪个环路、接受/发出什么连接）**决定，而非细胞类型身份。
2. **宿主环境「重编程」供体神经元**：Pașca 团队指出，把人源皮层神经元接入**远端靶标（体内其他神经结构）**提供了培养皿中无法复现的信号。→ 同样的人源细胞，在**不同连接生态位**中发育出不同命运，再次指向「连接 > 细胞类型」。
3. **同一物种行为由共享环路支撑**：XCX 小鼠在 Y 迷宫中表现优于「无皮层 apallial 小鼠」但逊于对照——说明保留/恢复的是**环路功能骨架**，而非细胞身份。
4. **跨物种神经元可功能性整合进宿主环路**（与本结论互补，见 §2 论文 #2）："a mouse can sense the world using neurons from another species"——鼠能用**大鼠**神经元闻世界。同样证明：**供体神经元只要接入正确环路就能承担功能**。

> 诚实声明：新闻的原始论文**已确认**（Nature 2026，DOI 见上）。但需注意——该论文**并没有**直接声称「智能完全由连接组决定」；它说的是人源神经元接入鼠脑后**行为仍主要表现为鼠**。这恰恰是本项目假说（拓扑决定行为）的**一致证据**，但属于「间接/支撑性」而非「证明性」。

---

## 2. 前沿论文综述（按与层2 相关性排序，共 17 篇）

> 排序逻辑：① 直接证明「连接/环路 > 细胞类型」（最高相关）→ ② 跨物种拓扑守恒 → ③ 结构 motif 库 → ④ 模块组合/吸引子语义 → ⑤ 反方（连接组不足以决定动力学，需状态/部分活动）。

### 【A 组】连接/环路 > 细胞类型（最高相关）

**#1 Throesch et al. 2024 — Functional sensory circuits built from neurons of two species**
- 机构：Scripps Research / Columbia / Salk / UT Southwestern
- 期刊/年：*Cell*，2024-04-25
- DOI：`10.1016/j.cell.2024.03.042` ｜ 链接：https://doi.org/10.1016/j.cell.2024.03.042
- 核心发现：用**囊胚互补（blastocyst complementation）**把**大鼠**多能干细胞注入小鼠囊胚，大鼠神经元在小鼠脑中发育并存活；当小鼠嗅神经元被沉默/杀死后，**大鼠神经元恢复嗅觉信息流，并 rescue 了「觅食」这一原始行为**（虽不如小鼠神经元完美）。结论："a mouse can sense the world using neurons from another species"。
- 对层2 启示：跨物种（鼠-鼠间 ~1000-2000 万年进化距离）神经元可承担宿主功能，只要接入正确环路 → **强烈支持「模块身份 = 接线角色」，而非细胞类型**。可作 `homolog_role_alignment` 规则的实证。

**#2 Pașca / Kaganovsky et al. 2026 — Developmental xenocortication（见 §1）**
- DOI：`10.1038/s41586-026-11032-2`
- 对层2 启示：人源神经元在鼠脑中功能性整合、行为仍表现为鼠 → 行为由**接入的环路拓扑**决定。

**#3 Özel & Desplan 2025 — Does a cell's "type" define its function?（Nature News & Views 评论）**
- 机构：Stowers Institute / NYU
- 期刊/年：*Nature* News & Views，2025-02-12
- DOI：未确认（评论文章，非研究论文）｜ 链接：https://www.stowers.org/news/does-a-cells-type-define-its-function
- 核心发现：评论一项斑马鱼视觉区研究——**分子上几乎相同的神经元，因邻近神经元与分子环境不同而呈现可测量的功能/形态多样性**。结论：cell type 只定义神经元的**潜在**功能，而非**全面决定**其功能。
- 对层2 启示：支持把「细胞类型」降为**可选属性**，把「接线位置/角色」升为**主属性**。

### 【B 组】跨物种拓扑守恒（comparative connectomics）

**#4 van den Heuvel 2016 — Comparative Connectomics**
- 期刊/年：*Trends in Cognitive Sciences*，2016
- DOI：`10.1016/j.tics.2016.03.001` ｜ 链接：https://www.cell.com/trends/cognitive-sciences/abstract/S1364-6613(16)00048-6
- 核心发现：系统比较多物种连接组，提出**两条保守接线主题**：(1) 网络组织成**社区/模块**（服务专门功能）；(2) 通过**短通信路径、hub、rich-club**实现高拓扑整合。差异主要支持**认知/行为的适应性分化**。
- 对层2 启示：模块（社区）与 hub 是**跨物种不变的骨架**——印证本项目 `cross_species_consistency()` 中 "shared functional skeleton: sensory → inter → motor" 的判断。

**#5 Goulas, Majka, Rosa, Hilgetag 2019 — A blueprint of mammalian cortical connectomes**
- 期刊/年：*PLOS Biology*，2019-03-22
- DOI：`10.1371/journal.pbio.2005346` ｜ 链接：https://doi.org/10.1371/journal.pbio.2005346
- 核心发现：比较 mouse / cat / marmoset / macaque 皮层连接组，发现**物种共有**的「network core（网络核心）」与**物种特异**的细胞构造-连接耦合。结论：部分组织原则跨哺乳动物保守，部分特异 → 翻译物种间发现需谨慎。
- 对层2 启示：给「哪些规则可跨物种保守、哪些要打补丁」提供了**分层依据**。

**#6 Stürner / Eichler et al. 2025 — Comparative connectomics of Drosophila descending and ascending neurons**
- 期刊/年：*Nature*，2025-07（online 2025-04-30）
- DOI：`10.1038/s41586-025-08925-z` ｜ 链接：https://doi.org/10.1038/s41586-025-08925-z
- 核心发现：整合 3 套 EM 数据集，给出果蝇雌/雄中枢神经系统中**全部上行（AN）与下行（DN）神经元**的连接组描述；发现跨颈部的 **DN-AN 连接链**，可能支撑**运动序列**；并给出性行为（求偶、鸣叫、产卵）的性别二态环路。
- 对层2 启示：连接组在**整个 CNS 层面**跨性别/跨数据集可对齐 → 支持「同角色模块可跨个体/性别复用」的嵌套/层级组合语义。

### 【C 组】结构 motif 库（building blocks）

**#7 Sporns & Kötter 2004 — Motifs in Brain Networks**
- 期刊/年：*PLOS Biology*，2004
- DOI：`10.1371/journal.pbio.0020369` ｜ 链接：https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.0020369
- 核心发现：提出**结构 motif（3 节点 13 类）**作为脑网络的「结构积木」；发现真实脑网络**最大化功能 motif 数量与多样性，同时维持较小的结构 motif 数量**。定义了 reciprocal / feedforward loop / 3-unicycle 等关键 motif。
- 对层2 启示：这是「**motif 即组合原子**」的理论源头——本项目层2 的 `COMBINATION_RULES`（feedforward / feedback / recurrent / bidirectional）可映射到这些 motif 类。

**#8 Dorkenwald / Schlegel et al. 2024 — Network statistics of the whole-brain connectome of Drosophila**
- 期刊/年：*Nature*，2024-10
- DOI：`10.1038/s41586-024-07968-y` ｜ 链接：https://www.nature.com/articles/s41586-024-07968-y
- 核心发现：在 FlyWire 全脑连接组上计算 **2-节点与 3-节点 motif** 的丰度，关联神经递质组成与细胞类型，并**跨动物比较**。发现果蝇脑具 **rich-club 组织**（30% 连接组为高度连接神经元），并识别出可作**整合者/广播者**的 rich-club 子集；在 78 个神经髓（neuropil）子网络上分析。
- 对层2 启示：直接给出「**rich-club / hub 广播**」「**reciprocal / feedforward loop / 3-unicycle**」在真实全脑连接组的丰度 → 可量化校准本项目的 `modulation_to_all`（广播）、`relay_bidirectional`、`memory_self_loop` 等规则。

**#9 鼠脑 motif 2026（preprint）— From local motifs to global dynamical stability in the mouse brain connectome**
- 机构：bioRxiv 预印本（2026-02-27）
- DOI：未确认（preprint，`10.64898/2026.02.27.708665v1`）｜ 链接：https://biorxiv.org/content/10.64898/2026.02.27.708665v1.full-text
- 核心发现：用 1,877 个完整重建小鼠神经元（bouton-net）做 **13 类 triad motif 普查**，将网络划分为 12 个模块；证明** triad motif 可有效区分真实生物网络与随机/SBM 网络**，且 motif 模式在模块间**一致守恒**。
- 对层2 启示：motif 是**模块级**而非全脑级守恒 → 支持「先定义最小 motif 单元，再组合成模块」的层2 设计哲学。

### 【D 组】模块组合语义 / 吸引子 / 动力学

**#10 Khona & Fiete 2022 — Attractor and integrator networks in the brain**
- 期刊/年：*Nature Reviews Neuroscience*，2022-12
- DOI：`10.1038/s41583-022-00642-0` ｜ 链接：https://www.nature.com/articles/s41583-022-00642-0
- 核心发现：综述**吸引子网络**如何在脑中实现工作记忆、误差校正、噪声积分；指出 **point attractor（递归兴奋+全局抑制）**、**line attractor（连续流形）**、**ring attractor（循环连接）**、**winner-take-all** 等不同连接 motif 产生不同计算；并提出通过**复用/重组同一组模块化吸引子**来兼顾鲁棒性与灵活性。
- 对层2 启示：这是「**层级封装吸引子（hierarchical attractor encapsulation）**」与「**抑制性平衡调制**」两条新规则的理论依据（见 §3）。

**#11 Barabási & Barabási 2020 — A Genetic Model of the Connectome**
- 期刊/年：*Neuron*，2020-02（online 2019）
- DOI：`10.1016/j.neuron.2019.10.031` ｜ 链接：https://www.pubmed.ncbi.nlm.nih.gov/31806491/
- 核心发现：提出连接组由**神经元遗传 barcode（转录因子组合）**经 **biclique 算子**生成；在 C. elegans、C. intestinalis、果蝇嗅球连接组中识别出**统计显著的 biclique motif**，且同一 biclique 内神经元共享显著基因表达 → 基因身份→接线规则→连接组的可证伪框架。
- 对层2 启示：连接不是随机的，而是**由紧凑规则（biclique / 接线算子）批量生成** → 支持本项目「组合规则是少量可复用算子」的核心设计；同时提示可把「基因 barcode → 接线权限」作为一层语义。

**#12 Pospisil et al. 2024 — The fly connectome reveals a path to the effectome**
- 期刊/年：*Nature*，2024-10
- DOI：`10.1038/s41586-024-07982-0` ｜ 链接：https://doi.org/10.1038/s41586-024-07982-0
- 核心发现：在 FlyWire 连接组上引入 **effectome（因果效应模型）**——用随机光遗传扰动数据 + 连接组作先验，估计「神经元 A 实际多强地影响 B」。发现**主导动力学回路只涉及相对较小的人群** → 神经元级成像/刺激/鉴定可行。
- 对层2 启示：连接组（结构）需结合**因果效应强度（动态）**才有预测力 → 为「组合规则需叠加状态/强度语义」提供依据（呼应 §3 的 temporal_state_gate）。

### 【E 组】果蝇连接组「旗舰」论文（层2 数据锚点来源）

**#13 Dorkenwald et al. (FlyWire Consortium) 2024 — Neuronal wiring diagram of an adult brain**
- 期刊/年：*Nature*，2024-10
- DOI：`10.1038/s41586-024-07558-y` ｜ 链接：https://doi.org/10.1038/s41586-024-07558-y
- 核心发现：**首个成年果蝇全脑连接组**——139,255 个神经元、约 5×10⁷ 化学突触；含细胞类/型、神经索（projectome）、神经递质预测；从感觉/上行→运动/内分泌/下行追踪信息流。**本项目层2 的 `discovered_modules.json` 即源于此数据集。**
- 对层2 启示：这是所有果蝇侧规则的数据根。

**#14 Schlegel et al. 2024 — Whole-brain annotation and multi-connectome cell typing of Drosophila**
- 期刊/年：*Nature*，2024-10
- DOI：`10.1038/s41586-024-07686-5` ｜ 链接：https://doi.org/10.1038/s41586-024-07686-5
- 核心发现：在 FlyWire 上系统注释 **8,453 个细胞类型**（4,581 个为新）；提出新 cell type 定义（与同脑内其他细胞更相似、而非与异脑细胞）；发现**蘑菇体功能稳态**（兴奋输入总量调整但 E/I 比维持）。
- 对层2 启示：cell type 是**次级标签**，且存在功能稳态 → 强化「cell type 不是主属性」；E/I 比维持为 `inhibitory_balance` 规则提供实证。

**#15 Shiu et al. 2024 — A Drosophila computational brain model reveals sensorimotor processing**
- 期刊/年：*Nature*，2024-10
- DOI：`10.1038/s41586-024-07763-9` ｜ 链接：https://doi.org/10.1038/s41586-024-07763-9
- 核心发现：仅用**突触级连接 + 预测神经递质身份**构建 leaky integrate-and-fire 全脑模型，准确预测味觉/机械觉驱动的**摄食与梳理行为**的神经元响应；光遗传验证。**证明「纯连接组 + 递质」即可描述完整感觉运动转换**。
- 对层2 启示：这是「连接组→行为」最直接的**正向证据**（注意它与 §F 的反方形成张力，见下）。

### 【F 组】反方 / 必要限定（诚实呈现）

**#16 Beiran & Litwin-Kumar 2025 — Prediction of neural activity in connectome-constrained recurrent networks**
- 期刊/年：*Nature Neuroscience*，2025-12
- DOI：`10.1038/s41593-025-02080-4` ｜ 链接：https://doi.org/10.1038/s41593-025-02080-4
- 核心发现：用「teacher（真实连接组）— student（同连接、不同生物物理参数）」范式证明：**仅有连接组往往不足以约束递归网络的动力学**（存在简并/退化）；但**记录少量神经元**即可打破简并，使 student 与 teacher 一致。
- 对层2 启示（关键限定）：层2 不能只押注「结构连接 = 功能」；必须引入**状态/部分活动/生物物理参数**作为补充语义——即 §3 的 `temporal_state_gate` 规则。**这是本项目最重要的「诚实护栏」：连接组决定可能的解空间，但不唯一确定动力学。**

**#17 Quian Quiroga 2020 — Closing the gap between mind and brain with the dynamic connectome**
- 期刊/年：*PNAS*，2020
- DOI：`10.1073/pnas.2005329117` ｜ 链接：https://www.pnas.org/content/early/2020/04/17/2005329117
- 核心发现：静态连接组无法解释同一刺激下的行为变异（双目竞争、主观感知）；需引入 **dynamic connectome（结构解剖连接 + 神经调质动态）**。
- 对层2 启示：支持 `modulation_to_all`（神经调质广播）作为**动态状态层**，而非被弃用的装饰。

### 【附】其他相关（未展开，供深挖）
- **C. elegans hub neurons 2022** — Current Biology，文章号 S0960-9822(22)01001-6；DOI 未确认（疑 `10.1016/j.cub.2022.07.001`）。结论：直接连接强度预测功能相关差，**网络拓扑（hub、triplet motif、输入相似性）足够**预测功能关系；抑制 hub 神经元破坏全脑动力学。
- **Chimeric brain models 2025** — Neuron 综述，文章号 S0896627325002569；DOI 未确认（疑 `10.1016/j.neuron.2025.05.017`）。系统综述人-鼠嵌合脑模型。

---

## 3. 对层2 的启示（给下游代码用）

### 3.1 现有 7 条组合规则的「果蝇特有 vs 跨物种保守」判定

| 现有规则 | 语义 | 判定 | 依据 |
|---|---|---|---|
| `sensory_to_recurrent` | 感觉→记忆核（feedforward） | **保守** | 感觉→中间→运动三层漏斗在 C. elegans、鼠、灵长类均守恒（#4, #5, #13） |
| `recurrent_to_motor` | 记忆→运动（decision_output） | **保守** | 同上；果蝇 DN/AN 链支撑运动序列（#6） |
| `recurrent_to_visual` | 记忆→视觉（feedback_gate） | **偏果蝇/脊椎眼相关** | 反馈门控在视觉系统突出；需验证非视觉物种是否有等价 |
| `relay_bidirectional` | relay 双向 | **保守** | 上行/下行神经元双向通信（#6）；hub 双向连接（#8） |
| `modulation_to_all` | 神经调质广播 | **保守** | 神经调质为全局状态层（#17）；动态连接组（#17） |
| `sensor_array_fanin` | 同感道 fan-in | **保守** | 模块内高内聚是普遍 motif 属性（#9） |
| `memory_self_loop` | 记忆核递归 | **保守** | rich-club/递归闭环为通用记忆基质（#8, #10） |

> 结论：**7 条中至少 6 条可跨物种保守**（仅 `recurrent_to_visual` 的 feedback_gate 语义偏感官特异，可泛化为 `feedback_gate_to_output`）。

### 3.2 现有 4 条嵌套规则 / 3 条乘数的判定
- `module_multicopy`：**保守**（多副本阵列在感觉/运动阵列普遍）。
- `hierarchical_containment`：**部分保守**（层级在脊椎动物皮层 laminar 结构存在，但果蝇层级更扁平）。
- `modulation_wraps_any`：**保守**（调制层包裹全局）。
- `no_self_containment`：**保守**（避免不可判定自引用，是计算安全规则）。
- 乘数：`combinatorial`（纯组合学，保守）、`structural`（故障隔离，保守）、`performance`（**未实测，禁止宣称**——与 #16 的反方一致，务必保留该护栏）。

### 3.3 前沿论文提供、但层2 目前没有的「新组合语义」

1. **时间锁定组合（temporal lockstep / state-gated）** — 来自 #16、#17：连接组只约束解空间，需**状态/部分活动**打破简并。→ 新增规则：连接仅在**特定神经调质状态/时间窗**内生效。
2. **层级封装（hierarchical attractor encapsulation）** — 来自 #10、#6：复用同一组模块化吸引子承担多功能。→ 新增规则：一个模块可**封装子模块作为可复用吸引子单元**。
3. **抑制性调制（inhibitory balance）** — 来自 #10、#14：E/I 比维持、point/line/ring attractor 依赖兴奋-抑制平衡。→ 区别于 `modulation_to_all`（广播），新增**抑制性平衡作为组合门控元素**。
4. **递归循环 vs 前馈管道（loop-vs-pipeline classifier）** — 来自 #7、#8：feedforward loop 做计算、recurrent 做记忆/积分。→ 显式区分两类方向语义（现有 `memory_self_loop` 仅为特例）。
5. **跨物种同源角色对齐（homolog role alignment）** — 来自 #1、#2、#4：不同物种神经元接入正确环路即承担功能。→ 新增规则：**模块身份由接线角色定义，可跨物种对齐绑定**。

### 3.4 具体建议：应新增哪 3-5 条组合规则？嵌套规则从 4 扩到几条？

**新增 5 条 CombinationRule（建议）：**

1. **`state_gated_combination`**（时间/状态门控组合）
   - 语义：某连接仅在**指定神经调质状态或时间窗**内计算生效；否则视为「结构存在但功能静默」。
   - 依据：#16（连接组不约束动力学，需部分活动/状态）、#17（dynamic connectome）。
   - 验证方式：在 SNN/ESN 引擎中注入不同调质状态向量，对比同拓扑不同状态下的输出可分性；或对照 FlyWire effectome（#12）的因果效应强度。

2. **`inhibitory_balance_gate`**（抑制性平衡调制）
   - 语义：在组合中加入**抑制性反馈边**，约束兴奋-抑制比以维持 point/line/ring attractor。
   - 依据：#10（吸引子动力学依赖 E/I 平衡）、#14（蘑菇体 E/I 比稳态）。
   - 验证方式：构造含/不含抑制平衡边的同源拓扑，测其吸引子稳定性与抗噪性（对照 #10 的鲁棒性-容量权衡）。

3. **`hub_integration`**（枢纽整合广播）
   - 语义：允许少量 **rich-club / hub 神经元**作为广播整合节点，把局部模块信号汇聚到全局。
   - 依据：#8（果蝇 rich-club 占 30%，为整合者/广播者）、#12（主导回路为小人群）、C. elegans hub（附录）。
   - 验证方式：在拓扑中标记 hub 节点（度/介数阈值），验证其删除是否系统性破坏全局信息整合（对照 C. elegans hub 抑制实验）。

4. **`hierarchical_attractor_encapsulation`**（层级吸引子封装）
   - 语义：允许一个模块**封装子模块作为可复用吸引子单元**（如「记忆核」内再封装一个 ring attractor）。
   - 依据：#10（模块化吸引子复用/重组）、#6（DN-AN 链跨颈封装运动序列）。
   - 验证方式：构造「容器模块 + 内部吸引子」，验证其在不同任务下可被独立调取而不污染外层（对照 #10 的多功能复用）。

5. **`homolog_role_alignment`**（同源角色对齐 / 跨物种绑定）
   - 语义：当两个模块的**接线角色（输入/输出类别）匹配**时，允许跨物种/跨细胞类型绑定为同一功能单元。
   - 依据：#1（鼠用大鼠神经元闻世界）、#2（人源神经元接入鼠脑）、#4（保守社区结构）。
   - 验证方式：以 `cross_species_consistency()` 已有的 conserved_categories 为锚，构造「鼠感觉阵列 ↔ 果蝇感觉阵列」角色对齐测试，验证行为级等效。

**嵌套规则：从 4 条扩到 7 条**（新增 3 条）：
- `inhibitory_wrap`（抑制层可包裹任何组合，作为平衡门控层）——依据 #10、#14。
- `attractor_encapsulation`（与 CombinationRule #4 对应的嵌套侧，允许模块内嵌吸引子，max_depth 提升）——依据 #10、#6。
- `cross_species_role_binding`（允许跨物种模块按角色绑定为单一功能单元，带对齐约束）——依据 #1、#2。
> 保留 `no_self_containment` 作为计算安全护栏不变。

---

## 4. 跨物种拓扑不变性（connectome invariants）

> 目标：列出「不依赖物种/细胞类型的通用拓扑规则」，作为本项目「功能全覆盖最小单位库」的**验证锚点**。

可从前沿文献提取的**不变量清单**：

1. **社区/模块结构（community structure）** — #4、#9：网络自发聚成功能专门社区；模块内高内聚、模块间低耦合。→ 锚点：每个功能单元须为内聚社区。
2. **rich-club / hub 整合** — #8、#12、C. elegans hub：少量高连接节点承担全局整合/广播。→ 锚点：最小单位库须包含可识别的 hub 角色。
3. **feedforward loop（前馈环）motif** — #7、#8：普遍出现，支撑局部计算。→ 锚点：前馈类组合原子。
4. **reciprocal（互惠）motif** — #7、#8：双向连接普遍存在。→ 锚点：双向/relay 组合原子。
5. **3-unicycle motif** — #8：与局部计算/信息流相关。→ 锚点：闭环类组合原子。
6. **感觉→中间→运动 三层漏斗** — #4、#5、#13：`sensory → inter → motor` 为基本骨架。→ 锚点：任何「功能全覆盖最小单位库」必须含此骨架。
7. **短通信路径 / small-world** — #4：高效整合依赖短路径 + hub。→ 锚点：组合后平均路径长度须落在 small-world 区间。
8. **兴奋-抑制平衡（E/I balance）** — #10、#14：吸引子与稳态依赖 E/I 比。→ 锚点：每个含递归的单元须含抑制平衡约束。
9. **网络核心（network core）** — #5：跨哺乳动物保守的通信核心。→ 锚点：核心节点集合可跨物种对齐。
10. **接线经济（wiring economy / 距离惩罚）** — #4、#5：连接优先连空间/拓扑近邻。→ 锚点：虚拟拓扑生成时的距离代价项。
11. **递归闭环 = 记忆基质** — #8、#10：recurrent 闭环支撑持续活动/工作记忆。→ 锚点：记忆类单元必含自环/闭环。
12. **statistical connectivity 可预测性** — PNAS 2012（statistical connectivity…）：皮层微环路大量由**形态非特异重叠**形成，chemospecific 仅少数情况需要。→ 锚点：组合规则的默认假设应为「统计/几何优先」，chemospecific 作例外。

> 注：这些不变量是**结构性**（拓扑）的；#16、#17 提醒——它们决定**可能的解空间**，但不唯一决定动力学，需叠加状态/活动语义（见 §3.3）。

---

## 5. 下一步深挖方向（研究问题 + 数据 + 工具 + 预计天数）

> 说明：「预计天数」为粗估（含文献精读、数据对齐、原型验证），非承诺值。

**Q1：能否把果蝇 7 条组合规则按 §3.1 的「保守/特有」判定，映射成跨物种通用骨架 + 果蝇补丁两层？**
- 需要数据：`discovered_modules.json`、worm `worm_modules.json`、`cross_species_consistency()` 输出、#4/#5 的跨物种连接组摘要。
- 可用工具：Python（现有 `module_combinator.py`）、NetworkX（拓扑比对）、FlyWire Codex（https://codex.flywire.ai）。
- 预计天数：3-5 天（主要是规则分层重构 + 单测）。

**Q2：`state_gated_combination` 规则在 SNN/ESN 引擎中能否被实证为「必要」而非装饰？**
- 需要数据：FlyWire effectome 因果强度（#12）、神经调质映射（#17）、现有 24 SNN + 7 ESN 场景。
- 可用工具：现有 SNN/ESN 仿真管线、`get_multiplier_metrics()` 扩展。
- 预计天数：5-7 天（注入状态向量、做可分性实验；注意 `performance` 乘数仍禁止宣称提升）。

**Q3：motif 级守恒如何量化校准现有规则的概率/方向字段？**
- 需要数据：#8 的果蝇 triad motif 丰度表、#9 的小鼠 triad motif 模块分布、#7 的 13-motif 谱。
- 可用工具：NetworkX motif census、与 `COMBINATION_RULES` 的 `probability` 字段对齐。
- 预计天数：4-6 天。

**Q4：跨物种 `homolog_role_alignment` 能否用鼠-大鼠（#1）或人-鼠（#2）嵌合数据反推「角色对齐约束」？**
- 需要数据：#1 Cell 2024 的鼠-大鼠嗅环路数据、#2 Nature 2026 的 XCX 连接模式、FlyWire + 鼠连接组对齐。
- 可用工具：跨物种配准（Allen CCF / FlyWire 坐标）、角色图同构匹配。
- 预计天数：7-10 天（数据获取与对齐成本高）。

**Q5：嵌套规则从 4 扩到 7 后，`validate_nesting` 的 max_depth 与 `no_self_containment` 护栏是否仍完备？**
- 需要数据：现有 `NESTING_RULES`、拟新增 3 条、`validate_combination` 冲突逻辑。
- 可用工具：Python 静态分析 + 递归展开测试。
- 预计天数：2-3 天（纯代码层，不碰 `module_combinator.py` 之外的主逻辑——本综述只给规格，落地由主 agent 执行）。

---

### 附：本文件诚实性声明
- 触发新闻原始论文：**已确认**（Nature 2026，`10.1038/s41586-026-11032-2`）。
- 所有列出 DOI 均来自 PubMed / Nature / Cell / PLOS / bioRxiv 检索结果；标注「未确认」的字段（部分 Neuron/Curr Biol 综述 DOI、评论文章）确实未能从权威来源确认，未编造。
- 未修改 `flybrain-connectome-mcp/module_combinator.py`（按硬约束，仅产出本综述）。
- 反方证据（#16、#17）已诚实纳入，避免「连接组决定论」被过度解读。
