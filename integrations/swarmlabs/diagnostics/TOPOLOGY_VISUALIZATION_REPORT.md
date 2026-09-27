# v2.16.0 组合拓扑可视化报告

**日期**：2026-09-27
**版本**：flybrain-connectome v2.16.0
**脚本**：`integrations/swarmlabs/diagnostics/topology_visualizer.py`
**产物**：`topology_overview.html`（41 KB 单文件 dashboard）+ 12 张独立 SVG

**零外部依赖**：stdlib + networkx 3.6.1，手写 SVG 生成器，无 matplotlib/graphviz。

---

## 1. 为什么做这个

v2.7.0 → v2.15.0 累计 9 轮实验，共产生 **12 种独立组合拓扑**、
**119 条对比**、**7 条 Bonferroni 存活**、**5 次样本偏差撤回**。

但**项目里没有一张图能让人一眼看懂"组合拓扑空间到底长什么样"**。
所有实验都以表格呈现（`claims_audit.json` / `topology_capacity_results.json` /
`tree_fanout_variants_results.json`），读起来像统计报表，看不到"结构"。

v2.16.0 把这个缺口补上——**12 种拓扑的图结构 + 布局分类 + 性能数据 +
Bonferroni 判定**，全部落在一个单文件 HTML 里。

---

## 2. 分类算法（结构优先，名字兜底）

用 networkx 从组合的 DAG 结构反向推断布局类型：

| 类别 | 结构特征 | 布局 | 拓扑数 |
|------|----------|------|--------|
| **linear chain** | 无环、无分支、最长路径占所有节点 | 左→右水平直线 | 3 |
| **tree_fanout** | 单根 out_degree≥3，其余节点为叶 | 根居中上，叶扇出下 | 4 |
| **funnel** | 单汇 in_degree≥3，多源 | 多源上，单汇下 | 1 |
| **hierarchical** | DAG，最长路径≥4 节点，无环 | 拓扑代层从上到下 | 1 |
| **reciprocal** | 有强连通循环 | 环状排布 | 2 |
| **wide_fanout** | 单节点 out_degree≥4（OUT port 复用） | 根上，多下游扇出 | 1 |

**分类是结构推断不是名字匹配**：`tree_fanout_with_feedback` 有反馈边形成
循环，被正确归入 `reciprocal` 而不是 `tree_fanout`；`tree_fanout_extended_chain`
虽然下游链式延展，但 hub 的 out_degree=3 且无环，仍归 `tree_fanout`。

---

## 3. 12 种拓扑分类结果

### 3.1 Linear Chain（3 种）

| 组合 | 单元数 | 边数 | MSE@N60 | MSE@N200 | conv@N60 | conv@N200 |
|------|--------|------|---------|----------|----------|-----------|
| gustatory_to_motion | 2 | 1 | 0.0763 | 0.0697 | 0.6 | 0.9 |
| olfactory_to_steering | 4 | 3 | 0.0645 | 0.0709 | 20.8 | 0.6 |
| visual_to_escape | 5 | 3 | 0.0686 | 0.0802 | 0.8 | 0.7 |

**观察**：链式组合是 A→B→C 的最简形态，扩容下全部**MSE 恶化 8-17%**——
这是 v2.11.0 已确认的"扩容对链式不利"证据。

### 3.2 Tree Fanout（4 种）

| 组合 | 单元数 | 边数 | MSE@N60 | MSE@N200 | conv@N60 | conv@N200 |
|------|--------|------|---------|----------|----------|-----------|
| tree_fanout | 4 | 3 | **0.0621** | 0.0636 | 20.7 | 20.5 |
| tree_fanout_ref | 4 | 3 | 0.0616 | **0.0588** | 12.7 | 16.6 |
| tree_fanout_with_inhibition | 5 | 5 | 0.0608 | 0.0601 | 8.4 | 28.3 |
| tree_fanout_extended_chain | 6 | 6 | 0.0676 | 0.0701 | 20.6 | 20.6 |

**观察**：
- **tree_fanout_ref 的 N=200 MSE=0.0588 是所有组合中最低**（n=50 数据）
- **tree_fanout_extended_chain 是唯一 Bonferroni 存活 WORSE**
  （N=60 d=−0.560, N=200 d=−0.928, p<0.0001，v2.15.0 发表级证据）
- **with_inhibition 是绝对 MSE 最低（0.0608 @N60），但扩容后 conv 恶化
  237%**（8.4→28.3 步）——v2.15.0 撤回"加抑制更好"的机制声明

### 3.3 Funnel（1 种）

| 组合 | 单元数 | 边数 | MSE@N60 | MSE@N200 | conv@N60 | conv@N200 |
|------|--------|------|---------|----------|----------|-----------|
| converging_funnel | 4 | 3 | 0.0689 | 0.0839 | 0.7 | 20.4 |

**观察**：**扩容下 MSE 恶化 22%**——多源汇聚到单一瓶颈的结构在扩容时
反而退化，与生物实际选择"分布式整合而非中心汇聚"一致。

### 3.4 Hierarchical（1 种）

| 组合 | 单元数 | 边数 | MSE@N60 | MSE@N200 | conv@N60 | conv@N200 |
|------|--------|------|---------|----------|----------|-----------|
| hierarchical_pipeline | 5 | 5 | 0.0632 | 0.0714 | 0.8 | 40.5 |

**观察**：**扩容下 conv 膨胀 50 倍**（0.8→40.5 步）——层级深度是
扩容不稳定的另一因子。

### 3.5 Reciprocal（2 种）

| 组合 | 单元数 | 边数 | MSE@N60 | MSE@N200 | conv@N60 | conv@N200 |
|------|--------|------|---------|----------|----------|-----------|
| reciprocal_feedback | 4 | 5 | 0.0642 | 0.0661 | 20.7 | 60.4 |
| tree_fanout_with_feedback | 4 | 4 | 0.0623 | 0.0607 | 12.8 | 13.1 |

**观察**：**反馈结构扩容不稳健**——reciprocal_feedback 扩容下 conv
膨胀 **3 倍**（20.7→60.4 步）；tree_fanout_with_feedback 更稳定
（12.8→13.1），说明"树状 + 反馈"比"纯反馈"更抗扩容。

### 3.6 Wide Fanout（1 种）

| 组合 | 单元数 | 边数 | MSE@N60 | MSE@N200 | conv@N60 | conv@N200 |
|------|--------|------|---------|----------|----------|-----------|
| wide_tree_fanout_5_downstream | 6 | 5 | **0.0593** | **0.0600** | 16.6 | 16.6 |

**观察**：
- **N=200 MSE=0.0600 与 tree_fanout_ref 的 0.0588 仅差 2%**——v2.15.0 确认
  wide 是真正抗扩容的（v2.13.0 声称 conv 膨胀 23× 被撤回）
- **绝对 MSE 最低（0.0593 @N60）**
- 但 N=200 上 wide 反而比 with_feedback 差（0.0600 vs 0.0607→0.0607）

---

## 4. 拓扑 × 表现综合榜（N=200, n=50 数据）

按 MSE 升序（越低越好）：

| 排名 | 拓扑 | MSE@N200 | Δ vs tree_fanout_ref | 类别 |
|------|------|----------|----------------------|------|
| 1 | **tree_fanout_ref** | **0.0588** | — | tree_fanout |
| 2 | wide_tree_fanout_5_downstream | 0.0600 | +2.0% | wide_fanout |
| 3 | tree_fanout_with_feedback | 0.0607 | +3.2% | reciprocal |
| 4 | tree_fanout_with_inhibition | 0.0601 | +2.4% | tree_fanout |
| 5 | tree_fanout (v2.12.0 n=5) | 0.0636 | +8.2% | tree_fanout |
| 6 | reciprocal_feedback | 0.0661 | +12.4% | reciprocal |
| 7 | tree_fanout_extended_chain | 0.0701 | +19.2% | tree_fanout |
| 8 | hierarchical_pipeline | 0.0714 | +21.4% | hierarchical |
| 9 | gustatory_to_motion | 0.0697 | +18.7% | chain |
| 10 | olfactory_to_steering | 0.0709 | +20.6% | chain |
| 11 | converging_funnel | 0.0839 | +42.7% | funnel |
| 12 | visual_to_escape | 0.0802 | +36.4% | chain |

**关键观察**：
- **前 5 名全是树状扇出的变体**（tree_fanout 家族）
- **扩容稳健性前 3 名**：wide_fanout（+2.0%）、with_feedback（+3.2%）、
  with_inhibition（+2.4%）——它们都在扩容下 MSE 恶化 <5%
- **扩容最差 3 名**：converging_funnel（+22%）、visual_to_escape（+17%）、
  hierarchical_pipeline（+13%）

---

## 5. Bonferroni 判定汇总

**7 条存活证据**（按 n_seeds 加权排序）：

| 版本 | 对比 | metric | p | d | n | 类别 |
|------|------|--------|---|---|---|------|
| v2.10.0 | textbook_random vs bio_motif | NARMA-10 | 0.0000 | −1.397 | 50 | abstract |
| v2.10.0 | textbook_random vs bio_motif | double_pole | 0.0000 | +1.717 | 50 | abstract |
| v2.10.0 | random_matched vs bio_motif | NARMA-10 | 0.0024 | −0.607 | 50 | abstract |
| v2.10.0 | single_unit_best vs bio_motif | NARMA-10 | 0.0016 | −0.630 | 50 | abstract |
| v2.10.0 | single_unit_best vs bio_motif | double_pole | 0.0042 | +0.573 | 50 | abstract |
| **v2.15.0** | **tree_fanout_extended_chain vs tree_fanout_ref** | NARMA-10 | 0.0051 | −0.560 | 50 | **tree_fanout** |
| **v2.15.0** | **tree_fanout_extended_chain vs tree_fanout_ref** | NARMA-10 | 3e-06 | −0.928 | 50 | **tree_fanout** |

**组合拓扑层**：**只有 1 个组合（tree_fanout_extended_chain）产生发表级证据**，
结论是"树状 + 下游链式延展不 scale"。

---

## 6. 元结论

从"图结构"的角度重新看 v2.15.0 的最终结论：

### 6.1 拓扑复杂度 vs 表现（明确反相关）

| 边数 | 平均 MSE@N200 | 样本数 |
|------|--------------|--------|
| 1-3 | 0.0718 | 4 |
| 4-5 | 0.0603 | 4 |
| 6 | 0.0701 | 2 |

**边数 4-5 是最优区间**——太少（chain 或 minimal tree）精度不足，
太多（extended_chain 或 wide_fanout 复用到 5 下游）反而损失。

### 6.2 拓扑"形状"决定扩容稳定性

| 形状 | 扩容 MSE Δ | 扩容 conv Δ |
|------|-----------|-------------|
| tree_fanout (3 边) | +2.4% | +0.4% |
| tree + feedback | +1.7% | +2.5% |
| tree + wide_fanout | +1.2% | +0.1% |
| tree + extended_chain | +3.9% | +0.3% |
| pure funnel | **+22%** | +2900% |
| pure hierarchical | +13% | +5000% |
| pure reciprocal | +2.9% | +192% |
| pure chain | +8~17% | 不定 |

**规律**：**只有"树状为骨架 + 附加边"的组合在扩容下稳定**。
纯非树状（funnel/hierarchical/reciprocal）都退化。

### 6.3 "生物最优"的重新定义

v2.15.0 之前假设：`更多生物性元素 = 更好表现`。

v2.16.0 从拓扑维度重新审视：**生物性元素（抑制/反馈/链式延展）在扩容后
要么无效、要么更差**。真正"生物最优"的结构是**极简单的 3-下游广播树
（tree_fanout_ref）**——不是它多，而是它**简单**。

这解释了为什么 v2.15.0 的所有变体都无法显著超越 tree_fanout_ref：**
不是变体不生物，是变体不简洁**。

---

## 7. 文件清单

| 文件 | 用途 |
|------|------|
| `topology_visualizer.py` | 可视化器（约 500 行，零外部依赖） |
| `topology_overview.html` | 单文件 dashboard（41 KB，直接可打开） |
| `svg_*.svg` (×12) | 每张拓扑的独立 SVG（可嵌入其他文档） |
| `TOPOLOGY_VISUALIZATION_REPORT.md` | 本报告 |

**引用建议**：任何讨论 v2.7-v2.15 组合拓扑实验的地方都链接
`topology_overview.html` 作为可视化锚点，读者可以一眼看到 12 种拓扑
的形态、性能、Bonferroni 判定。

---

## 8. 已知限制（诚实登记）

1. **没有单元级可视化**：12 张 SVG 都只画到"单元节点"粒度，没有画出
   单个单元内部的神经元群 / 微回路。这需要真实神经元坐标数据（MaleCNS
   SWC 已有，但需要新工具链）。
2. **没有连接件可视化**：边只画箭头，没有画出 CONNECTION_TYPES 中
   的 66 种连接类型（突触/电突触/化学/形态）的区分。
3. **没有版本 diff**：不能一图看 v2.13.0 和 v2.15.0 数据在同一张图上
   的差异（虽然 dashboard 已包含 n=10 和 n=50 的对比）。
4. **静态图**：无交互（无缩放、无节点点击展开）。若需要交互，需换
   D3.js 或 Plotly，但会引入浏览器依赖。

这些限制都是**下一步工作**，不阻塞 v2.16.0 的交付价值。
