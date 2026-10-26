# PR-S2 · Lesion Cascade 理论桥预注册协议

**预注册时间**：2026-10-18（在读取任何 lesion 结果之前冻结）
**基线**：v2.97.0
**目的**：把 Xu 2026 *Science*（DOI: 10.1126/science.adz5323）的"树突区室承载抽象规则"转成项目可检验命题——**"拓扑的模块化/区室化程度 predicts 级联失效容忍度"**。这是 B 腿从"工程演示"变成"可对话神经科学的命题"的关键一跃。
**冻结规则**：遵守 R-0.1 / R-0.2 / R-0.3 / R-0.4（见 `docs/PREREGISTRATION_PROTOCOL_v1.md`）
**关联**：`docs/SCI_READINESS_ASSESSMENT_2026-10-18.md` §3.S2；`docs/XU2026_DENDRITIC_COMPUTATION_IMPACT_2026-10-18.md`；E4 边界图册 v1.1（B-14 区室边界）

---

## 0. 命题陈述

**H1**（可证伪）：在 MaleCNS 子图上，逐步删除节点/模块后，**拓扑模块化程度越高，级联失效范围越小**（lesion tolerance 越大）。

**H2**（对照）：度保持随机化零模型（configuration model）下，同样数量的删除产生的级联失效范围**显著大于**观测拓扑（p < 0.05）。

**H3**（Xu 2026 桥接）：如果 Xu 2026 的"区室化承载计算"命题在本项目结构空间成立，则 lesion tolerance 应与"跨模块边比 bridge_fraction"负相关（模块化越强 → 桥边比越低 → 容错越强）。

---

## 1. 实验设计

| 项 | 内容 |
|---|---|
| **数据入口** | MaleCNS 真实子图（复用 PR-3_v2 的 `malecns_subgraph` 生成器 + 真实锚点 AUC 0.96）|
| **拓扑规模** | n_nodes ∈ {20, 50, 100}，每档 100 seeds |
| **删除策略** | 逐步删除节点/模块，直到图分裂（连通分量数 > 1）或达到删除预算 k_max = ⌈0.3·n⌉ |
| **级联失效范围** | `cascade_reach(k)` = 删除 k 步后最大连通分量的补集大小 / n |
| **零模型** | 度保持随机化（configuration model，`_wiring_null`）|
| **模块化度量** | `bridge_fraction`（已有指标） + 自算模块度（Girvan–Newman-like module score，简化为社区发现）|
| **随机种子** | seed=42 |
| **执行环境** | `metrics_fork/` 只读副本 + `_s2_lesion_cascade/` 落盘 |

---

## 2. 判据（预注册）

| 指标 | 通过判据 | 失败判据 |
|---|---|---|
| **方向（H1）** | lesion tolerance ≥ 零模型 + 0.05（相对改善） | 改善 < 0.05 |
| **显著性（H2）** | 观测 - 零模型 的 bootstrap p < 0.05（1000 次 bootstrap） | p ≥ 0.05 |
| **效应量** | Cohen's d ≥ 0.3（小-中效应） | d < 0.3 |
| **模块化预测（H3）** | lesion_tolerance 与 bridge_fraction 的 Spearman ρ ≤ -0.3 且 p < 0.05 | ρ > -0.3 或 p ≥ 0.05 |
| **CI 报告** | 每个 n_nodes 档报告 95% CI | 缺 CI → 降级为 PARTIAL |

### 2.1 判决分类

- **PASS**：H1、H2、H3 均满足
- **PARTIAL**：H1 和 H2 满足但 H3 FAIL（即容错存在但模块化的"区室化"预测不成立）
- **FAIL**：H1 或 H2 FAIL
- **DATA_UNAVAILABLE**：数据加载失败（fail-closed）

---

## 3. 命令与门禁绑定

```bash
python scripts/s2_lesion_cascade.py \
    --n-nodes 20,50,100 \
    --seeds 100 \
    --max-deletion-ratio 0.3 \
    --bootstrap 1000 \
    --output _s2_lesion_cascade/results.json
```

**Gate 63**（拟新增）：读取 `_s2_lesion_cascade/results.json` 与 `research_claims.json.preregistered.PR_S2` 比对。

---

## 4. 预注册的"不做什么"

- ❌ 不修改 R1 主张（R1 是 lesion 现象，PR-S2 是其机制预测）
- ❌ 不引入新的图类型（只用 malecns_subgraph）
- ❌ 不宣称"证明 Xu 2026"——只做命题层面的可证伪桥接
- ❌ 不跨物种（跨物种验证走 PR-S1）
- ❌ 不做亚细胞区室建模（B-14 边界，当前数据模型不可表达）

---

## 5. 预期产出

- `_s2_lesion_cascade/results.json`：完整实验产物
- `docs/S2_LESION_CASCADE_2026-10-18.md`：可读报告
- `research_claims.json.preregistered.PR_S2`：预注册四元组记录
- 若 PASS：为 P-5 短文增加"神经科学理论桥"章节
- 若 FAIL：登记到 E4 边界图册 v1.2 作为"理论桥未通"边界

---

**预注册 hash**：见 `vault/PR_S2.commit.json`

*PR-S2 · 2026-10-18 · flybrain-connectome*
