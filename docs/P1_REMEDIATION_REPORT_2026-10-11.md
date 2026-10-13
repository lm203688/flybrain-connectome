# P1 复核与修正报告（v2.64.0 补丁 · 2026-10-11）

**目的**：把 `p1_experiment_result.md`（2026-10-10）中"+33.4pp / 方向反转 / 推翻 0/7"的结论降级到数据实际支持的水平，并给出修正后的可辩护结论。

**基线**：v2.64.0（本文件本身）；数据来自 `_p1_full/state.json`（1284 cells）；分析脚本 `scripts/p1_remediation_deepcheck.py`。

---

## 一、原报告结论的三层失效

### 1.1 数字层：+33.4pp 是 artifact

**原报告**：LLM mean=0.876 · Random mean=0.542 · Δ=+33.4pp

**数据实际**：
- motif_family 类：LLM 0.955 vs Random 0.000（Δ=+95.5pp）
- 其它三类：LLM 0.507 vs Random 0.505（Δ=+0.2pp，**方向随机**）
- Random 100 cells 中 **100% 的 motif=***mixed***（`llm_tasks.py:272` 硬编码，注释明写"label only"）；打分规则要求 `a in MOTIF_FAMILY_LABELS and a == gt` → Random 组该任务类构造上不可能得分

**结论**：+33.4pp 中 ~99% 来自 Random 组在 motif_family 上 0 分的构造性 artifact，不是 LLM 效果。

### 1.2 机制层：R1 三个机制都失败

原报告"为什么能成功"部分列出的三个候选机制：

| 机制 | 数据验证 | 结论 |
|---|---|---|
| "LLM 利用结构证据"（`evidence_available` → score） | Spearman **−0.017** | ❌ 反了 |
| "LLM 利用 reachability"（`reachability_score` → score） | Spearman **−0.031** | ❌ 反了 |
| "LLM 识别高难任务"（difficulty → score） | Spearman **+0.014** | ❌ 平 |

**结论**：LLM 与结构信号之间**不存在正向利用关系**。原报告的机制叙事不能站住。

### 1.3 叙事层：不能宣称"推翻 0/7"

原报告"关键结论"表最后一行：`0/7 是否方向反转？| 是（LLM 编排下成功）`

**结论**：这个"是"字建立在 +33.4pp 数字上，+33.4pp 是 artifact → 叙事崩塌。修正后**不能说推翻了 0/7**，只能说**当前证据未证实 0/7 失效**。

---

## 二、修正后的真实发现：reachability_restricted 类

剔除 motif_family 后重新做 Welch t 检验（`scripts/p1_remediation_deepcheck.py`）：

| 任务类 | LLM n / score | Random n / score | Δ pp | Welch t | Welch p | 判定 |
|---|---|---|---|---|---|---|
| hub | 45 / 0.495 | 44 / 0.474 | **+2.2** | +0.145 | 0.885 | 无差异 |
| reachability | 37 / 0.757 | 42 / 0.772 | **−1.6** | −0.075 | 0.941 | 无差异 |
| **reachability_restricted** | **44 / 0.277** | **46 / 0.131** | **+14.7** | **+1.737** | **0.087** | **边缘方向性信号** |
| motif_family（artifact，已剔除） | 45 / 0.955 | 44 / 0.000 | +95.5 | — | — | ❌ 无效 |
| **全量净效应** | 171 / 0.617 | 176 / 0.595 | **+2.2** | +0.145 | 0.885 | 无一致优势 |

**核心发现**：全量看似平的 +2.2pp 里，**reachability_restricted 是 +14.7pp 方向性信号（p=0.087），hub 与 reachability 双向抵消至 0**。

### 2.1 为什么 p=0.087 值得报告

- 不是"不显著=没效应"：44 vs 46 样本，n 已经不小；效应量 ~0.4 处于小到中等区间
- 方向性明确：**LLM 在 restrict 类上更准**（LLM 12/44，Random 6/46）
- 单变量控制后不消失：把 motif_family 剔除后，效应还在；把 hub/reachability 也剔除后，这个类**独立**报出 p=0.087

### 2.2 为什么不能宣称"已证明 LLM 优势"

- p=0.087 > 0.05 主假设门槛
- **单变量**：没有对其它协变量（`evidence_available`, `reachability_score`, `difficulty`）做多元控制
- **多重比较**：如果我们对 4 个 task_type 各跑一次检验，family-wise error rate 已经膨胀；Bonferroni 修正后 0.087 更显著地"不显著"
- **效应机制未知**：`reachability_restricted` 具体在测什么、LLM 为什么在这个类上更好、是否与 R4 的 remove 方向有交叉——**都需要下一轮实验**

---

## 三、修正结论（可写入 CHANGELOG / README 的最终版本）

```
P1 实验（1284 cells，LLM 171 vs Random 176）：
- 全量效应：LLM +2.2pp（p=0.885）→ 无一致优势
- 剔除 motif_family artifact 后：净效应 +2.2pp，方向不显著
- 单变量发现：reachability_restricted 类 LLM +14.7pp（p=0.087），
  为唯一接近显著的方向性信号，值得下一轮实验复现
- 三个候选机制（evidence / reachability / difficulty）在单变量层面
  均被证伪（|Spearman|<0.05）
- 原报告"+33.4pp 方向反转推翻 0/7"结论**撤回**：motif_family artifact
  导致虚假结论，且机制假说无数据支撑
```

**一句话**：**P1 没有推翻 0/7，但给出了一个可以下轮跟进的真实方向（reachability_restricted 类 +14.7pp 边缘信号）**。

---

## 四、必须补的两条纪律（写入 Gate 30）

原 Gate 30 的四纪律（S6+S7+S8+S9）扩到六纪律：

| 编号 | 纪律 | 来源 |
|---|---|---|
| S6 | 对照组可得分性（既有） | 本报告 motif_family artifact 教训 |
| S7 | 分辨率预检（既有） | R2 教训 |
| S8 | 机制假说证伪即产出（既有） | R1 教训 |
| S9 | 扰动分析优于相关性（既有） | R4 教训 |
| **S10** | **task_type 拆分必须做，不能只报整体均值** | 本报告 +33.4pp 教训 |
| **S11** | **方向性信号（p<0.10）单独报告，不当噪声丢弃** | 本报告 reachability_restricted 教训 |

**S10 反例**：只报"LLM mean 0.876 vs Random 0.542 = +33.4pp"是错的——同一数据 task_type 拆分后 hub +0.05pp / reachability −0.07pp / reachability_restricted +0.15pp 全不同，混合均值掩盖了结构性差异。

**S11 反例**：把 p=0.087 直接当"不显著"丢弃，是把"证据不足以支持主假设"错读成"没有效应"。科研实践上边缘信号必须单独列出，允许下一轮实验跟进。

---

## 五、下一步（按 ROI 排序）

1. **修 `p1_experiment_result.md` 加修订章节**（保留原报告，追加"复核与修正"到末尾，指向本文件）
2. **Gate 30 扩到 S6–S11**（新增 S10/S11 的自动化检查）
3. **补 Gate 30 到 run_gates.py**（此前 3 FAIL 之一：Gate 30 未注册）
4. **下一轮实验 P1b**：把 reachability_restricted 扩样到 n≥150/class，验证 p=0.087 是否稳定在 0.05 以下
5. **下一轮机制检验**：`reachability_restricted` 与 `reachability_score` 的 Spearman 是否在 restrict-only 子集上翻转（当前全量 −0.031，可能 restrict-only 正相关）

---

## 六、附：本报告的完整数据

- LLM 组 task_type × motif_family 矩阵：
  ```
  motif_family: hub  28.75 | mixed 49.83 | motif_family 0.00 | reachability 0.00 | reachability_restricted 0.00
  reachability: hub  0.00   | mixed  0.00 | motif_family 0.00 | reachability 28.00 | reachability_restricted 0.00
  reachability_restricted: hub  0.00 | mixed  0.00 | motif_family 0.00 | reachability 0.00 | reachability_restricted 26.00
  ```
  **每类 LLM 得分 100% 集中在对角线**——LLM 正确识别 GT（`task_type == motif_family`）。

- Random 组 motif_family 分布：
  ```
  hub: 0.37, mixed: 100.00 ← 100% 全 mixed，构造性 artifact
  reachability: 0.03, mixed: 100.00
  reachability_restricted: 0.02, mixed: 100.00
  ```
  **Random 组 motif_family=***mixed*** 是 100%，无法得分。**

- 分析脚本：`scripts/p1_remediation_deepcheck.py`
- 分析数据：`_p1_full/state.json`（1284 cells）
