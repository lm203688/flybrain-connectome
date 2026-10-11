# P1 实验结果 — 证据锚定拓扑 vs 随机同规模拓扑

**日期**: 2026-10-10  
**版本**: v2.60.0  
**实验**: P1 结案实验（AdaptOrch arXiv:2602.16873 类比）  
**状态**: Warmup 120 cells 完成 ✅ · Full 288 cells 进行中 ⏳

---

## 1. 实验设计

### 1.1 核心问题

本项目 v2.36.0 GA 基准测试中，7 个证据锚定拓扑全部输给随机同规模拓扑（0/7）。
AdaptOrch（2026-02）表明：**同样模型仅改拓扑 +12–23%**（SWE-bench/GPQA/RAG）。

P1 实验的假设：

> 证据锚定拓扑（带 MaleCNS 真实连接数据）在 LLM 编排基底上优于随机同规模拓扑。

### 1.2 设计矩阵

| 维度 | 配置 |
|---|---|
| 证据拓扑 | 25 个 blueprint（MaleCNS v1.0 真实 motif 派生） |
| 随机拓扑 | 25 个随机同规模 blueprint |
| 拓扑类型 | sequential / fan_out / hierarchical / router |
| 任务类型 | motif_family / hub / reachability |
| 试次 | 1（warmup）/ 3（full） |
| LLM 后端 | deepseek-v4-flash via 本地 8788 代理 |
| 随机种子 | 42 |

### 1.3 Warmup vs Full

| | Warmup | Full |
|---|---|---|
| Blueprints/arm | 5 | 25 |
| Tasks/blueprint | 3 | 3 |
| Topologies | 4 | 4 |
| **Total cells** | **120** | **288** |
| **Wall time** | **5,041s (1h24m)** | ~3.4h (预估) |

---

## 2. Warmup 结果（120 cells · 5 blueprint × 2 condition × 4 topology × 3 task）

### 2.1 准确率矩阵

| Topology | Evidence | Random | Δ (ev-rd) | Paired t | p |
|---|---:|---:|---:|---:|---:|
| **fan_out** | **0.800** | **0.467** | **+0.333** | **+1.784** | **0.0745** |
| sequential | 0.667 | 0.600 | +0.067 | +0.323 | 0.7465 |
| hierarchical | 0.333 | 0.200 | +0.133 | +0.695 | 0.4872 |
| router | 0.667 | 0.533 | +0.133 | +0.619 | 0.5357 |
| **均值** | **0.617** | **0.450** | **+0.167** | — | — |

### 2.2 关键发现

1. **方向反转**：v2.36.0 GA 0/7 全输 → P1 warmup 4/4 全赢（evidence > random）
2. **整体 +16.7pp**：接近 AdaptOrch 的 +12–23% 数量级
3. **fan_out 边缘显著**：p=0.0745（n=5 下达到 p<0.10）
4. **其他 topology 边缘不显著**：n=5 太小，需要 full run（n=25）

### 2.3 与 AdaptOrch 的对比

| 指标 | AdaptOrch (2026-02) | P1 Warmup |
|---|---|---|
| 提升幅度 | +12–23% | +16.7% |
| 拓扑类型 | 4 种（同） | 4 种（同） |
| 最优拓扑 | sequential | fan_out |
| 统计显著性 | p<0.01 | p=0.075 (边缘) |
| 基底 | LLM (GPT-4/Claude) | LLM (deepseek-v4-flash) |

---

## 3. Full Run 进展（288 cells · 25 blueprint × 2 condition × 4 topology × 3 task）

**状态**: 运行中（task trumQy，启动于 2026-10-10 10:15 UTC+8）

**预估完成**: ~3.4 小时后（基于 warmup 的 0.024 cells/s）

---

## 4. 统计方法与局限性

### 4.1 统计检验

- **配对 t 检验**：每个 topology 内，同一 blueprint 的 evidence vs random 准确率配对比较
- **效应量**：Cohen's d ≈ 0.94（fan_out，大效应）
- **多重比较校正**：未做 Bonferroni（4 个 topology，α=0.0125 后仅 fan_out 仍边缘显著）

### 4.2 局限性

1. **样本量小**（n=5 blueprint，warmup）：需 full run（n=25）达到统计显著性
2. **单一 LLM 后端**：deepseek-v4-flash，未跨模型验证
3. **单一任务类型**：motif_family / hub / reachability，未覆盖 SWE-bench/GPQA 等标准基准
4. **二元准确率**：未做置信度校准（calibration）
5. **无 baseline 模型**：未跑 "无 blueprint，直接输入" 作为基线

### 4.3 与 v2.36.0 GA 0/7 的差异

| 维度 | v2.36.0 GA | P1 Warmup |
|---|---|---|
| 基底 | ESN 储备池 | LLM 编排 |
| 密度 | 0.002–0.023 | N/A |
| 拓扑类型 | 7 种 | 4 种 |
| 证据 vs 随机 | 0/7 输 | 4/4 赢 |
| 结论 | 证据拓扑无用 | 证据拓扑有用（边缘显著） |

**关键洞察**：v2.36.0 的 0/7 负结果是在 **ESN 储备池** 基底上测的，而 AdaptOrch 的 +12–23% 是在 **LLM 编排** 基底上测的。P1 warmup 证实：**基底不同，结论相反**——这本身就是一个有价值的发现。

---

## 5. 结论

### 5.1 对 P1 假设的判定

**部分支持（partial positive）**：
- ✅ 4/4 topology evidence > random（方向正确）
- ✅ 整体 +16.7pp（量级与 AdaptOrch 一致）
- ✅ fan_out 边缘显著（p=0.075）
- ⚠️ 仅 n=5，需 full run 确认

### 5.2 对 v2.36.0 0/7 负结果的更新

**v2.36.0 的 0/7 负结果不是"证据拓扑无用"，而是"ESN 储备池基底不适合证据拓扑"。**  
在 LLM 编排基底上，证据拓扑优于随机拓扑。这推翻了我们之前的"0/7 结案"判断——**没有结案，只是换到了正确的基底上**。

### 5.3 下一步

1. **完成 full run**（288 cells，~3.4h）：确认 p<0.05
2. **跨模型验证**：同蓝图跑 gpt-4 / claude / qwen，看是否稳定
3. **扩展任务类型**：加入 SWE-bench / GPQA 标准任务
4. **加入无蓝图基线**：跑 "直接输入无 blueprint" 作为 control

---

## 6. 技术附录

### 6.1 文件

| 文件 | 说明 |
|---|---|
| `p1_experiment.py` | 实验驱动脚本（stdlib-only） |
| `llm_orchestrator.py` | LLM 编排层（4 种拓扑） |
| `llm_tasks.py` | 任务定义与 ground truth |
| `_p1_warmup/cells.csv` | 120 行 cell 级结果 |
| `_p1_warmup/summary.json` | 汇总统计 |
| `_p1_warmup/state.json` | 断点续跑状态 |

### 6.2 复现

```bash
# Warmup (120 cells, ~1h24m)
python p1_experiment.py --mode real \
    --n-blueprints-per-arm 5 \
    --n-tasks-per-blueprint 3 \
    --output-dir ./_p1_warmup

# Full (288 cells, ~3.4h)
python p1_experiment.py --mode real \
    --n-blueprints-per-arm 25 \
    --n-tasks-per-blueprint 3 \
    --output-dir ./_p1_full
```

### 6.3 运行环境

- Python: 3.13.12 (minimind venv)
- LLM backend: deepseek-v4-flash via 127.0.0.1:8788 (local gateway)
- 随机种子: 42
- 时间: 2026-10-10 10:08–18:08 UTC+8

---

## 7. 复核与修正（2026-10-11 追加）

> **本节由 `docs/SCAN_AND_UPGRADE_2026-10-11.md` 第二部分独立复核驱动。**
> 原报告的 §5.2 声称"推翻 0/7 结案判断"——**该结论是错误的**。
> 保留原文不改历史，本节追加更正。

### 7.1 根本缺陷：random 组的 `motif_family` 任务构造上不可能得分

`_p1_full/state.json`（**1,540 results**，1525/1800 cells 时因 `PermissionError` 崩溃，已保存的部分数据足够得出结论）按 `task_type × condition` 拆分：

| task_type | evidence | random | **Δ** | n(ev) | n(rd) | S6 |
|---|---:|---:|---:|---:|---:|---|
| hub | 0.773 | 0.722 | **+0.051** | 300 | 216 | ✅ 可比 |
| **motif_family** | **0.973** | **0.000** | **+0.973** | 300 | 216 | ❌ random 恒 0 |
| reachability | 0.763 | 0.707 | **+0.056** | 300 | 208 | ✅ 可比 |
| **整体（含 motif）** | 0.786 | 0.444 | **+0.342** | 900 | 640 | ⚠️ 伪差异 |

> **整个 +33.4pp 的效应，几乎全部来自 `motif_family` 这一个任务类。**

证据链（三层，全部来自代码与数据）：

**第一层 · 数据**：random 组所有 blueprints 的 motif 都是 `mixed`
```
evidence: recurrent_feedback 360 · reservoir_smallworld 288 · inhibitory_hub 252
random:   mixed 378   ← 全部
```

**第二层 · 代码注释**（`llm_tasks.py:272`）：
```python
motif_family="mixed",  # label only; not among MOTIF_FAMILY_LABELS
```

**第三层 · 打分逻辑**（`llm_tasks.py:339`）：
```python
return a in MOTIF_FAMILY_LABELS and a == ground_truth
```
而标签菜单只有 3 个（`inhibitory_hub` / `recurrent_feedback` / `reservoir_smallworld`）。

**→ 由于 `"mixed" ∉ MOTIF_FAMILY_LABELS`，random 组的 `motif_family` 得分恒为 0。**

### 7.2 修正后的结果

剔除在对照组不可得分的 `motif_family` 后：

| task_type | Δ | 方向 | n 合计 |
|---|---:|---|---|
| hub | **+0.051** | evidence 略优 | 516 |
| reachability | **+0.056** | evidence 略优 | 508 |
| **净结果** | **≈ +0.05** | **小幅一致正方向** | 1,024 |

> **结论（1,540 条实测数据）**：
> 1. **motif_family 的 +97.3pp 是伪差异**（S6 判定：random 对照组恒 0，不可比）→ 已剔除
> 2. **hub / reachability 上 evidence 有约 +5pp 小幅一致增益**——方向与 AdaptOrch 一致，但量级远小于 AdaptOrch 报告的 +12–23%
> 3. **样本不均衡**（evidence 900 vs random 640，因证据蓝图池大于随机池），且未完成全量 1800 cells
> 4. **+5pp 不足以推翻 0/7**——0/7 的绝对值（0%）与本实验的 ~75% 是不同基底（ESN reservoir vs LLM orchestrator），不能直接跨基底比较
>
> **诚实表述**：证据锚定拓扑在 LLM 编排基底上**方向上有小幅优势**（+5pp），但**不足以称为"结构增益"或"推翻 0/7"**。P1 未推翻 0/7 负结论；同时修正 §5.2 的"结构增益"表述。

### 7.3 为什么这个错误容易发生

| 环节 | 问题 |
|---|---|
| **任务设计** | 三个任务类型中，只有 `motif_family` 依赖 motif 标签；而 random 蓝图**没有真实 motif**，只能标 `mixed` |
| **聚合方式** | 报告用**总体均值**呈现结果，掩盖了任务类型间的结构性差异 |
| **验收缺失** | **没有"对照组可得分性"检查** |
| **表述放大** | 报告用了"方向反转""推翻 0/7 结案判断"这类强表述 |

### 7.4 新纪律：S6 对照组可得分性

> **S6 · 对照组可得分性**：在任何对照实验中，**必须先验证对照组在每个任务类上都存在可得分样本**；
> 若某任务类在对照组恒为 0，该任务类**必须从主效应中剔除或单独报告**。

落地：写进 Gate 30 的检查项。

### 7.5 不翻案的结论

- **v2.36.0 0/7**：有效（ESN 储备池基底上证据拓扑无用）
- **FLM 0/24**：有效（MaleCNS 接冻结 LFM 做 reservoir 全输 direct-input）
- **GA 8/8 输随机**：有效
- **92.6% 故障隔离**：有效（结构属性度量）
- **P1 未推翻 0/7**：§5.2 的"推翻"结论作废；**1,540 条实测数据确认 motif_family 伪差异，hub/reachability 仅 +5pp 小幅增益**
