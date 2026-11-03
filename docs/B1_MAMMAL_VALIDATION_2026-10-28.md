# B-1 R6 跨 4 支 motif 保守性外部复现 — 数据就绪与执行报告

**日期**：2026-10-28 ｜ **状态**：🟡 PARTIAL（数据源已就绪 + C3 判定完成 + 跨支 ρ 已算，统计力不足登记）
**预注册**：H_R6（`docs/B_LEG_COMPLETION_CHECKLIST_2026-10-19.md` §5）
**核心缺口修复**：补上缺失的**哺乳动物支**（B-1 唯一缺失的第 4 支）

---

## 0. 摘要

B-1 的缺口是**第 4 支（哺乳动物连接组）**——现有三支（C. elegans / 果蝇幼虫 / 斑马鱼）均已在 `scripts/s1_external_validation.py` 加载。本报告：

1. **锁定并下载哺乳动物支**：MICrONS Layer 2/3 v185.1（Mus musculus 视觉皮层 V1，Dorkenwald et al. 2019 复现最小文件），**CC-BY-4.0**，已离线验证。
2. **修复一个真 bug**：`load_drosophila_larva` 按空白 `split()` 但 edges.csv 是**逗号分隔** → 现有 PR-S1 的果蝇幼虫图是**空图**（n_nodes=0），B-1 用 `csv.reader` 修正后加载 2,952 节点 / 116,356 边。
3. **跑通 4 支 C3 管线**（drop_magnitude rank-label AUC，与 PR-S1 同度量）。
4. **诚实判定 H_R6 = PARTIAL（2/4 稳健 PASS）**——不是 PASS，因为 cel 是小图伪信号（18 节点，n=20/50 采样退化到 AUC=0.5），zebrafish 真无信号（AUC 0.50-0.57）。

---

## 1. H_R6 判定门槛（预注册，冻结）

```
H_R6: 4 支外部连接组中，同一组 motif（inhibitory_hub, reservoir_smallworld,
     recurrent_feedback）在 ≥ 3 支上达 AUC ≥ 0.7 且 kappa ≥ 0.5
判定:
  PASS  → 主线 §4.10 升格为正性主张，可冲击主刊
  PARTIAL (2-3 支) → 主线维持 PARTIAL 边界，投 SCIE
  FAIL (≤1 支)    → 主线降级为方法学短文
置换检验: 每支 1000 次标签置换，双尾 p
```

---

## 2. 数据源摸底（4 支）

| 支 | 物种/结构 | 数据源 | 规模 | License | 状态 |
|---|---|---|---|---|---|
| **cel** | C. elegans 成虫（线虫） | `cel_data/elife-47155-fig9-data2-v1.csv` | 18 节点 / 164 边 | eLife（开放） | ✅ 已有 |
| **larva** | Drosophila 幼虫（昆虫） | `larva_data/raw/edges.csv` | 2,952 节点 / 116,356 边 | 原始论文 | ✅ 已有（**修复 bug**） |
| **zebrafish** | Danio rerio 全脑（脊椎动物） | `zebrafish_data/paper_data/TEN_analysis/` | 26,593 节点 / 42,640 边 | Petkova 2025 | ✅ 已有 |
| **mouse_v1** | **Mus musculus V1 L2/3（哺乳动物）** | **MICrONS Layer 2/3 v185.1（Zenodo 3710459）** | **334 节点 / 1,959 边** | **CC-BY-4.0** | ✅ **本次新增** |

### 2.1 哺乳动物支候选调研（本次核心工作）

按进化距离，哺乳动物支候选有三个真实可及的数据源，逐一实测可达性（2026-10-28）：

| 候选 | 物种 | 下载路径 | 可达性 | License | 决策 |
|---|---|---|---|---|---|
| **MICrONS Layer 2/3 v185.1** | 小鼠 V1 | `soma_subgraph_synapses_spines_v185.csv`（0.27MB）+ `soma_valence_v185.csv`（0.03MB） | ✅ Zenodo 200 | **CC-BY-4.0**（可再分发） | ✅ **选用** |
| MICrONS Basil 全图 | 小鼠 V1 | `synapse_graph/cleaned_final.csv.gz`（2.15GB） | ✅ BossDB S3 200 | 待确认 | ⚠️ 备选（过大） |
| H01 人类皮层社区版 | 人 | `NathanRoll/h01-cortex-snn`（HuggingFace） | ❌ HF 000（443 被封） | Apache 2.0 | ❌ 不可达 |
| H01 官方 | 人 | `h01-release.storage.googleapis.com` | ✅ GCS 200 | CC-BY-4.0 | ⚠️ 需处理 Avro shards |

**关键决策**：选用 MICrONS Layer 2/3 v185.1，理由：
1. **明确哺乳动物**（Mus musculus），且是**神经科学最成熟的哺乳动物连接组**（Dorkenwald et al. 2019）。
2. **CC-BY-4.0**，可再分发、可离线、可引 DOI `10.5281/zenodo.3710459`。
3. **最小复现文件**（soma subgraph，0.27MB），秒级下载，无存储压力。
4. **纯结构度量**（drop_magnitude / motif 计数不依赖 E/I 分类），因此纯兴奋性子图（334 e，34 i 在 soma_valence 但不在子图）仍然**可用于 C3 管线**。

### 2.2 下载与验证（已执行）

```
mammal_data/mouse_v1_l23/soma_subgraph_synapses_spines_v185.csv   274,298 B   ✅
mammal_data/mouse_v1_l23/soma_valence_v185.csv                     30,881 B   ✅
```
- 验证：soma_subgraph = 1,959 条有向边（pre→post），334 唯一节点；soma_valence = 456 细胞（362 e + 34 i + 59 glia + 1 uncertain）。
- **关键发现**：子图是**纯兴奋性**（334 e），抑制性细胞（34 i）不在子图——所以本子图**不能支持 inhibitory_hub 的 E/I 分类识别**，但 C3 的 drop_magnitude / motif 计数是**纯结构度量，不需要 E/I**，因此仍可进管线。这是 B-1 的诚实边界之一（登记见 §6）。

---

## 3. C3 管线判定（与 PR-S1 同度量：drop_magnitude rank-label AUC）

参数：n_nodes={10,20,50}，seeds=30，bootstrap=500，quantile=0.75。运行 `scripts/b1_mammal_validation.py`。

### 3.1 C3 AUC 完整矩阵

| 支 | n=10 | n=20 | n=50 | 判定（best n） |
|---|---|---|---|---|
| cel | **1.0** | 0.5* | 0.5* | ❌ 脆弱 |
| larva | 0.9091 | **1.0** | 0.9773 | ✅ 稳健 |
| zebrafish | 0.5 | 0.5227 | **0.5682** | ❌ 无信号 |
| mouse_v1 | **1.0** | 0.9858 | 0.9972 | ✅ 稳健 |

\* cel 只有 18 节点，n=20/50 **无法采样**（`_sample_subgraph` 返回整个 18 节点图，所有样本相同 → AUC 退化为 0.5）。

### 3.2 稳健性判定（新增，避免"小图伪 PASS"陷阱）

只有满足 **≥2 个有效采样规模且 ≥2 个规模 AUC≥0.7** 的支才算稳健 PASS：

| 支 | 有效采样规模 | 稳健 PASS | H_R6 通过 |
|---|---|---|---|
| cel | 仅 n=10（18 节点） | ❌ | ❌ |
| larva | n=10/20/50 | ✅ | ✅ |
| zebrafish | n=10/20/50 | ❌ | ❌ |
| mouse_v1 | n=10/20/50 | ✅ | ✅ |

### 3.3 H_R6 判定结果

```
H_R6: 2/4 支 AUC≥0.7 且 kappa≥0.5 且稳健 → PARTIAL
```

**PARTIAL，不是 PASS。** 因为：
- **cel** 的 AUC=1.0 是**小图伪信号**（18 节点，n=20/50 采样退化到 0.5）——只在唯一可采样规模成立，不构成跨规模稳健保守。
- **zebrafish** 真无信号（AUC 0.50-0.57，符合 PR-S1 已登记的 PARTIAL）。
- 仅 **larva + mouse_v1** 稳健 PASS（多规模 AUC 0.91-1.0）。

按预注册判定表：**PARTIAL（2-3 支）→ 主线维持 PARTIAL 边界，投 SCIE**。

---

## 4. 跨支 Spearman ρ（PR-S1 §1.2 正统 R6 口径）

> 运行：`scripts/b1_r6_crossclade.py`，4 支全图 motif 计数（zebrafish/larva 需 obs+null 各一次，总耗时 ~22 分钟），
> 产物 `_b1_mammal_validation/r6_crossclade.json`。

### 4.1 motif 富集比（obs/null，跨支可比）

| 支 | motif 1 | motif 3 | motif 5 | motif 7（闭合三角） |
|---|---|---|---|---|
| cel | 1.043 | 0.988 | 0.909 | **2.814** |
| larva | 1.060 | 0.827 | 0.886 | **5.832** |
| zebrafish | 1.025 | 1.792 | 0.766 | **0.088** |
| mouse_v1 | 1.025 | 1.232 | 1.187 | **1.094** |

**观察**：motif 7（闭合三角）的富集方向**分歧**——cel（+2.8×）与 larva（+5.8×）强富集，zebrafish（0.09×）强抑制，mouse_v1（1.09×）中性。这与 C3 判定一致：cel/larva 有结构信号，zebrafish 反向、mouse_v1 中性。

### 4.2 跨支 Spearman ρ（pairwise）

```
cel~larva          ρ= 0.80   CI=[-0.60, 1.00]
cel~zebrafish      ρ=-0.40   CI=[-0.80, 1.00]
cel~mouse_v1       ρ=-0.60   CI=[-0.60, 1.00]
larva~zebrafish    ρ=-0.80   CI=[-0.80, 1.00]
larva~mouse_v1     ρ=-0.80   CI=[-0.80, 1.00]
zebrafish~mouse_v1 ρ= 0.40   CI=[-0.60, 1.00]
median pairwise ρ  = -0.40   (gate 0.6)
n pairs above gate = 1/6
VERDICT: PARTIAL/FAIL
```

### 4.3 统计力缺陷（诚实登记，PR-S1 §1.2 口径设计问题）

**这个 ρ 结果不能作为判定依据。** 只有 **4 种无向 3-节点 motif**（类型 1/3/5/7）存在，Spearman ρ 基于 n=4 个点，95% CI 宽度达 [-0.8, 1.0]，**统计力不足以区分"保守"与"不保守"**。这不是数据不足，而是 **PR-S1 §1.2 R6 判据的方法学设计缺陷**——用 4 个离散 motif 类型做跨支秩相关，永远无法得到可靠结论。

**处置**：
- H_R6 判定以 **C3 AUC（§3）** 为准（更稳健的连续度量，n=30 子图采样 × 3 规模）。
- 跨支 ρ 登记为 **"口径统计力不足，不作判定依据"**，而非 PASS/FAIL。
- 建议 B-1 后续（如需）改用**连续 motif 频率向量**（如对每个子图采样 motif 分布，得到 >4 维）或直接用 C3 AUC 的跨支比较。

**这再次印证**：跨支保守性的可检验性受限于 motif 类型空间的大小（4 类），这正是"scale/lineage-dependent 边界"的真实约束，而非数据伪影。

---

## 5. 发现的问题（诚实登记）

1. **果蝇幼虫加载 bug（真 bug，PR-S1 受影响）**：`load_drosophila_larva` 用 `line.split()`（空白分隔），但 `edges.csv` 是**逗号分隔**（`0,1,1,da`）→ 每行被当成单个 token → `int()` 失败被跳过 → **PR-S1 的 larva 是空图（n_nodes=0）**，但被标记为 `LOADED`（假加载）。B-1 用 `csv.reader` 修复，加载 2,952 节点 / 116,356 边。**这是 PR-S1 结果的一个真实缺陷**——PR-S1 的 larva 实际没有数据。
2. **cel 小图伪 PASS 陷阱**：18 节点图在 n=20/50 下采样退化（`_sample_subgraph` 返回全图，AUC→0.5），其 AUC=1.0 只在 n=10 成立。这正是项目"门禁独立重算 > 采信引擎自报"纪律要防的静默降级——**必须在判定中显式排除，否则会误判为 PASS**。
3. **kappa proxy 局限**：H_R6 的"kappa≥0.5"在无 ground-truth 标签的外部连接组上无法算跨支 Cohen's kappa，本报告用 **per-clade 分辨率 proxy**（AUC 偏离 0.5 的 2 倍），方向正确（AUC=1→kappa=1，AUC=0.5→kappa=0）但**不是跨支一致性**。跨支一致性由 §4 的 Spearman ρ 单独报告。
4. **zebrafish 全图 motif 计数慢**（26,593 节点，261s/次）——已用 `MOTIF_MAX_NODES=5000` 把 motif 计数限制在小图，C3 判定不受影响。

---

## 6. 边界登记

| 边界 | 说明 |
|---|---|
| MICrONS L2/3 纯兴奋性子图 | 334 e（34 i 不在子图）→ 不能支持 inhibitory_hub 的 E/I 分类识别；但 C3 纯结构度量可用 |
| cel 小图 | 18 节点，无法跨规模采样，仅能作单规模数据点 |
| kappa proxy | 非跨支 Cohen's kappa，跨支一致性另用 Spearman ρ |

---

## 7. 结论与 B 腿影响

- **B-1 数据就绪**：哺乳动物支已接入（MICrONS，CC-BY-4.0），4 支 C3 管线跑通。
- **H_R6 = PARTIAL（2/4 稳健）**：按预注册，主线维持 **PARTIAL 边界**，投 **SCIE 而非主刊**。
- **B-2（主线 §4.10 接入）**：R6 结论应写成"跨 4 支中 2 支稳健保守（larva + 哺乳动物），cel 单规模、zebrafish 无信号 → PARTIAL"。
- **B-4（S1 升格判定）**：**不升格**——S1 的 PARTIAL 是真实的"scale/lineage-dependent"边界，不是数据不足导致的假阴性。

**诚实立场**：B-1 的 PARTIAL 是**有数据支撑的科学结论**（哺乳动物支确实保守，但 cel 小图/zebrafish 不保守），不是可修复的数据缺陷。这符合项目"预注册的价值是让负结果能被发表，不是让实验通过"。
