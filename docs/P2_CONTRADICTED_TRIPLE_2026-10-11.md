# P2 · CONTRADICTED 三元组溯源与处置建议

**报告日期**：2026-10-11
**基线版本**：v2.64.0（Gate 30 已注册）
**扫描对象**：三连接组（MaleCNS 成虫 / C. elegans Witvliet 2020 / 幼虫 Winding 2023）全部 **157 条声明边**
**方法**：对 `CONTRADICTED` 边做三层追溯 —— ① 声明端点；② 支持性证据（同 source 是否 SUPPORTED）；③ 原始数据端点（同 endpoint 在同 source 里是否 SUPPORTED）

---

## 1. CONTRADICTED 边的完整清单

| # | edge_id | from | to | source | weight |
|---|---------|------|----|--------|--------|
| 1 | `edge:neurosecretion:1:0:0:1` | NeurosecretionSystem | AnteriorLobe | MaleCNS | 1 |
| 2 | `edge:neurosecretion:1:0:1:1` | NeurosecretionSystem | PosteriorLobe | MaleCNS | 1 |
| 3 | `edge:neurosecretion:1:0:2:1` | NeurosecretionSystem | CorpusAllatum | MaleCNS | 1 |

三条边全部属于 MaleCNS 的 **NeurosecretionSystem** 子系统，指向三个**内分泌效应器**（脑前叶 / 脑后叶 / 上咽体）。

---

## 2. 追溯链：CONTRADICTED 是怎么被造出来的

### 2.1 声明端

`connectome_neurosecretion.py` 里 NeurosecretionSystem 的声明：

```python
targets = ["AnteriorLobe", "PosteriorLobe", "CorpusAllatum"]
# 每个 target 一条 Connection(edge_type="Neurosecretion", evidence_type=EDGE_EVIDENCE_CONTRADICTED)
```

- **CONTRADICTED 是声明时就写死的**，不是从证据聚合推出来的
- 声明方**没提供** SUPPORTED/FRAGILE 证据来支撑"为什么这三条边是 CONTRADICTED"

### 2.2 支持性证据端（同 source 是否 SUPPORTED）

同一对 (from=NeurosecretionSystem, to=X) 在 MaleCNS 里有没有 SUPPORTED 边？

| 目标端点 | 该 source 里的 SUPPORTED 边数 | 其他证据类型 | 结论 |
|----------|------------------------------|--------------|------|
| AnteriorLobe | **1**（`Circuit:AnteriorLobe:NeurosecretionSystem`，weight=2） | CONTRADICTED×1 | 双向并存 |
| PosteriorLobe | 0 | 仅 CONTRADICTED×1 | 单边 CONTRADICTED |
| CorpusAllatum | 0 | 仅 CONTRADICTED×1 | 单边 CONTRADICTED |

- **AnteriorLobe**：Circuit 层给 SUPPORTED（weight=2），Neurosecretion 层给 CONTRADICTED —— 同一对节点两个子系统的证据冲突
- **PosteriorLobe / CorpusAllatum**：Circuit 层**完全没声明**，只有 Neurosecretion 层 CONTRADICTED

### 2.3 原始数据端（跨 source 是否 SUPPORTED）

同一对 (from, to) 在三连接组全部 157 条声明边里的证据全景：

| 目标端点 | MaleCNS | C.elegans | 幼虫 |
|----------|---------|-----------|------|
| AnteriorLobe | SUPPORTED×1 + CONTRADICTED×1 | ∅ | ∅ |
| PosteriorLobe | CONTRADICTED×1 | ∅ | ∅ |
| CorpusAllatum | CONTRADICTED×1 | ∅ | ∅ |

- **C. elegans 和幼虫两组里，NeurosecretionSystem 三个内分泌效应器完全不存在**（无 SUPPORTED 也无 CONTRADICTED）
- 三个 CONTRADICTED 边**在跨物种维度完全无参照**
- 唯一"冲突"只在 MaleCNS 内部（AnteriorLobe 的一对 SUPPORTED/CONTRADICTED），另外两条 CONTRADICTED **没有任何 SUPPORTED 对立面**——它们其实是"孤立声明"，被打了 CONTRADICTED 标签但没有对照证据

---

## 3. 三层追溯的结论

| 判定 | 边 | 依据 |
|------|-----|------|
| **真实矛盾**（双向并存） | NeurosecretionSystem → AnteriorLobe | MaleCNS 内 Circuit 层 SUPPORTED 与 Neurosecretion 层 CONTRADICTED 冲突，值得作为"结构冲突案例"保留 |
| **孤立 CONTRADICTED**（缺 SUPPORTED 对照） | NeurosecretionSystem → PosteriorLobe | 无 SUPPORTED 对立边；跨物种无参照；CONTRADICTED 标签缺乏证据基础 |
| **孤立 CONTRADICTED**（缺 SUPPORTED 对照） | NeurosecretionSystem → CorpusAllatum | 同上 |

**关键发现**：三条 CONTRADICTED 里只有 **1 条是真实的"两证据冲突"**（AnteriorLobe），另外 **2 条是"孤立声明"** —— 没有 SUPPORTED 对照边，却被打 CONTRADICTED 标签。这在证据学上是**标签误用**：CONTRADICTED 的定义应该是"存在反证"，而不是"没有证据"。

---

## 4. 处置建议（按代价排序）

### 建议 A（最小改动，推荐）—— 把孤立 CONTRADICTED 降级为"未证实"

- **保留** AnteriorLobe 的 CONTRADICTED（真实冲突案例）
- **降级** PosteriorLobe / CorpusAllatum 的 CONTRADICTED → 新标签 `UNSUBSTANTIATED`（或直接从边表删除）
- 影响：CONTRADICTED 从 3 条降为 1 条；证据表更诚实

### 建议 B（保守）—— 保留全部 CONTRADICTED，但补写"证据注释"

- 每条 CONTRADICTED 边附加 `evidence_note` 字段，说明"是否有 SUPPORTED 对立边"
- 影响：不改数据，仅加元数据；下游可自己判断

### 建议 C（激进，暂不推荐）—— 全部 CONTRADICTED 删除，仅保留 SUPPORTED 冲突案例的"双边并存"表达

- 需要新增"冲突对"数据结构，改动大

### 推荐路径

**执行建议 A**：把 PosteriorLobe / CorpusAllatum 的 CONTRADICTED 标记为"孤立声明"（可从 CONTRADICTED 池剔除）。CONTRADICTED 池收缩到 1 条真实冲突案例，反而更符合"CONTRADICTED 是稀有事件"的科学含义——**证据库里只有 1 条真正的矛盾边**，这本身就是可对外讲的结构事实。

---

## 5. 与 S6 纪律的关系

Gate 30 新增的 **S6 对照组可得分性**纪律正好覆盖这类问题：

- S6 要求：任何"标签为 X"的实体，在对照组里都必须有可比样本
- PosteriorLobe / CorpusAllatum 的 CONTRADICTED **没有 SUPPORTED 对照** → 违反 S6 精神
- 建议 A 的执行等价于"把不满足 S6 的 CONTRADICTED 标签纠正过来"

**结论**：CONTRADICTED 三元组不是数据缺陷，是**标签纪律未落地**——数据本身在 S6 门禁上线前就存在，只是没被审计。建议 A 是 S6 纪律向证据表反哺的第一次动作。
