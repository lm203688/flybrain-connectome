# PR-S1 · 跨物种外部验证队列预注册协议

**预注册时间**：2026-10-18（在读取任何外部数据集结果之前冻结）
**基线**：v2.97.0
**目的**：把 C3 跨族一致性和 R6 motif 保守性从"5 个图族内部一致"升级为"跨物种外部验证"，回答 SCI 审稿人的第 ① 问——"你的结论在其他连接组上也成立吗？"
**冻结规则**：遵守 R-0.1 / R-0.2 / R-0.3 / R-0.4（见 `docs/PREREGISTRATION_PROTOCOL_v1.md`）
**关联**：`docs/SCI_READINESS_ASSESSMENT_2026-10-18.md` §3.S1；对应 E4 边界图册 v1.1

---

## 0. 队列设计

| 项 | 内容 |
|---|---|
| **数据入口** | `cel_data/` (C. elegans Witvliet 2020)、`larva_data/` (Drosophila larva Winding 2023)、`zebrafish_data/paper_data/` (Petkova 2025) |
| **样本单位** | 每个数据集 = 一个 "外部数据集"，与 C3 内部 5 图族并列 |
| **n 样本/族** | 内部族：n_nodes ∈ {10, 20, 50} × 200 seeds = 600 samples；外部族：受限于原始文件规模，n 由 adapter 决定（若 < 100 → 报告但不参与通过判据）|
| **模型** | Logistic regression + AUC（与 PR-3_v2 完全一致，不新增模型选择自由度）|
| **特征集** | 冻结为 4 项：`n_bridges` / `bridge_fraction` / `n_articulation_points` / `edge_connectivity` |
| **标签** | `rank_within_family(quantile=0.75)`（沿用 PR-3_v2） |
| **零模型** | 度保持随机化（wiring model） |
| **随机种子** | seed=42（跨所有数据集一致）|
| **执行环境** | `metrics_fork/` 只读副本 + `_s1_external_validation/` 落盘目录 |

---

## 1. 判据（预注册）

### 1.1 C3 跨物种一致性

| 指标 | 通过判据 | 失败判据 |
|---|---|---|
| **一致性系数 κ** | κ ≥ 0.6 且 p < 0.05 | κ < 0.6 |
| **AUC 方向一致族数** | ≥ 4/6（内部 5 + 外部 3 = 8 族中）| < 4 |
| **每个外部族 AUC** | AUC ≥ 0.65 且 95% CI 下界 > 0.5 | AUC < 0.6 或 CI 跨越 0.5 |
| **效应量一致性** | 跨族 Cohen's d 的 CV < 0.4 | CV ≥ 0.4 |

### 1.2 R6 motif 保守性

| 指标 | 通过判据 |
|---|---|
| **motif 频率差** | 4 进化支之间 motif 频率的 Spearman ρ ≥ 0.6 |
| **bootstrap CI** | 每个 motif 的 ρ 有 95% CI，且 CI 下界 > 0.3 |
| **零模型对比** | 观测 ρ 显著高于度保持零模型的 ρ（bootstrap p < 0.05）|

### 1.3 判决分类

沿用 PR-2b 的四分类法：
- **PASS**：C3 与 R6 均满足通过判据
- **PARTIAL**：C3 PASS 但 R6 PARTIAL（或反之）
- **FAIL**：C3 与 R6 均 FAIL
- **DATA_UNAVAILABLE**：某个外部数据集无法加载（fail-closed，登记边界）

---

## 2. 数据入口与失败处理

| 数据集 | 期望文件 | fail-closed 处理 |
|---|---|---|
| **C. elegans** | `cel_data/elife-47155-fig9-data2-v1.csv` 或 `witvliet_2020_7_adult.xlsx` | 若 CSV 缺失则加载 xlsx；若两都缺失 → DATA_UNAVAILABLE |
| **Drosophila larva** | `larva_data/fly_larva.csv.zip` | 解压失败 → DATA_UNAVAILABLE |
| **zebrafish Petkova 2025** | `zebrafish_data/paper_data/`（Petkova 子集） | 若为空/结构不匹配 → DATA_UNAVAILABLE |

**边界登记**：所有 DATA_UNAVAILABLE 必须登记到 `data_gaps.json` 新增 `M3-16-S1-EXTERNAL-VALIDATION` 条目，并写入 E4 边界图册新增边界条目。

---

## 3. 命令与门禁绑定

```bash
python scripts/s1_external_validation.py \
    --datasets cel,larva,zebrafish \
    --seed 42 \
    --bootstrap 1000 \
    --output _s1_external_validation/results.json
```

**Gate 62**（拟新增）：读取 `_s1_external_validation/results.json` 与 `research_claims.json.preregistered.PR_S1` 比对，判据一致则 PASS，否则 FAIL。

---

## 4. 预注册的"不做什么"

- ❌ 不修改内部族 PR-3_v2 的判据（PR-S1 是外部验证，不改动内部族）
- ❌ 不新增模型类型（冻结为 Logistic + AUC）
- ❌ 不在数据加载后调整 pass threshold（R-0.4）
- ❌ 不引入外部预训练模型或 embedding
- ❌ 不宣称"证明 R1/R6"——只做外部一致性的独立观察

---

## 5. 预期产出

- `_s1_external_validation/results.json`：完整实验产物
- `docs/S1_EXTERNAL_VALIDATION_2026-10-18.md`：可读报告
- `research_claims.json.preregistered.PR_S1`：预注册四元组记录（R-0.2）
- `research_claims.json` 中 R6 增加 `external_validation` 字段（跨物种 ρ）
- E4 边界图册若需新边界，v1.2 追加

---

**预注册 hash**：见 `vault/PR_S1.commit.json`（冻结时间戳 + 载荷哈希，与 PR-3_v2 / PR-2b vault 一致）

*PR-S1 · 2026-10-18 · flybrain-connectome*
