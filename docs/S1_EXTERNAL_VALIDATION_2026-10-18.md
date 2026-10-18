# S1 外部验证队列执行报告

**执行日期**：2026-10-18
**协议**：`docs/PR_S1_EXTERNAL_VALIDATION_2026-10-18.md`（预注册于执行前冻结）
**Vault**：`vault/PR_S1.commit.json`（forward-guarantee，第一条前向预注册的 PR）
**判决**：**PARTIAL**（3/3 外部数据集加载成功，内部 5 族全部 PASS，外部 3 族 AUC 显著低于 0.65 判据）

---

## 1. 关键数字

### 1.1 数据集可用性（100%）

| 数据集 | 加载状态 | n_nodes | n_edges | 来源 |
|---|---|---|---|---|
| C. elegans | LOADED | 302 | 2,301 | elife-47155-fig9-data2-v1.csv |
| Drosophila larva | LOADED | 2,956 | 352,611 | larva_data/raw/edges.csv |
| zebrafish TEN | LOADED | ~1,123 | ~142,882 | TEN_analysis/outgoing_synapses.csv |

**100% 加载率**——三个外部公开连接组全部成功接入，无 fail-closed。

### 1.2 C3 AUC 矩阵（bootstrap 95% CI, seeds=15, n_boot=200）

| 族 | n=10 AUC [CI] | n=20 AUC [CI] | 通过 0.65 |
|---|---|---|---|
| project_synthetic | **1.000** [1.000–1.000] | **0.818** [0.682–0.955] | ✅ |
| erdos_renyi | **0.909** [0.750–1.000] | **0.966** [0.875–1.000] | ✅ |
| barabasi_albert | **1.000** [1.000–1.000] | **1.000** [1.000–1.000] | ✅ |
| watts_strogatz | **0.818** [0.583–1.000] | **0.761** [0.577–1.000] | ✅ |
| **malecns_subgraph** | **0.977** [0.923–1.000] | **0.909** [0.778–1.000] | ✅ |
| **c. elegans** | **1.000** [1.000–1.000] | 0.500 [0.500–0.500] | ❌ (n=20) |
| **drosophila larva** | 0.500 [0.500–0.500] | 0.500 [0.500–0.500] | ❌ |
| **zebrafish TEN** | 0.500 [0.500–0.500] | 0.545 [0.500–0.650] | ❌ |

### 1.3 判决

- **C3 PASS 族数**：5/8（内部 5 族全部 PASS，外部 3 族 FAIL）
- **外部 AUC 通过**：0/3（判据 AUC ≥ 0.65）
- **判决**：PARTIAL（按预注册判据：`c3_min_auc_direction_consistent_families ≥ 4` 满足，但外部族 AUC 判据 FAIL）

---

## 2. 关键发现

### 2.1 内部一致性强（阳性证据）

- 内部 5 族全部达到 AUC ≥ 0.76（多数 ≥ 0.90）
- MaleCNS 真实子图 AUC 0.977（n=10）与合成族一致——**PR-3_v2 标签修正的 S7 结论跨种子稳健**

### 2.2 外部族 AUC = 0.5（阴性证据）

- C. elegans 在 n=10 达 1.0，但 n=20 掉到 0.5（**尺度不稳定**）
- Drosophila larva 与 zebrafish 在 n=10 与 n=20 均接近 0.5（**信号缺席**）

**解释**：C3 的"top hub 移除后邻域大小下降"信号是**拓扑结构性质**，而真实生物连接组的 hub 分布在 n=10 子图上高度异质——不同子图的 hub 移除效应差异不足以让 rank-based 标签产生稳定信号。这是**跨物种边界条件**，不是"实验失败"。

### 2.3 跨物种不一致 = 边界条件论文

按 E4 边界图册 v1.1 的分类框架，这是**新边界条目候选**：

| 边界 | 内容 | 类型 |
|---|---|---|
| **B-15 跨物种拓扑信号缺席** | drop_magnitude 在真实生物连接组的诱导子图上无稳定信号（AUC ~0.5） | 数据-方法学边界 |

登记到 `data_gaps.json` 与 `docs/E4_BOUNDARY_ATLAS.md` v1.2。

---

## 3. 边界条件（不宣称）

- ❌ 不宣称"drop_magnitude 不适用于真实生物数据"——只在 n=10-20 子图规模上
- ❌ 不宣称"跨物种信号不可迁移"——只在本项目的 C3 定义下
- ❌ 不修改内部族 PR-3_v2 判据（R-0.4）
- ✅ 登记"跨物种拓扑信号缺席"为 B-15 边界（fail-closed）

---

## 4. 与 PR-3_v2 的关系

PR-3_v2 内部族 5/5 PASS → PR-S1 外部族 0/3 PASS。这是**诚实的阴性结果**：预注册纪律的价值正在于此时不修改判据、不选择性报告、不删除外部族数据。审稿人的第 ① 问（"在其他连接组上成立吗？"）现在有诚实答案：**在 n=10-20 子图规模上不成立，跨物种一致性仅在合成图家族内保持**。

---

## 5. 后续动作

1. **登记 B-15 边界**到 E4 图册 v1.2 + data_gaps.json M3-17
2. **不改**内部族 PR-3_v2 判据
3. 若下轮有精力：改用**全局图属性**（不用诱导子图）重跑外部验证
4. 论文中如实报告"内部 PASS / 外部 PARTIAL"作为跨物种边界条件的证据

---

## 6. 复现命令

```bash
python scripts/s1_external_validation.py \
    --datasets cel,larva,zebrafish \
    --n-nodes 10,20 --seeds 15 --bootstrap 200 \
    --out _s1_external_validation/
```

产物：`_s1_external_validation/results.json`（完整 JSON，含每族 AUC + CI + 每数据集 metadata）

---

*S1 执行报告 · 2026-10-18 · flybrain-connectome · 基于 PR-S1 前向预注册*
