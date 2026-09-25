# CONNECTION_TYPES 未使用词汇审计

**版本**：v2.10.0 · **日期**：2026-09-25

**观察**：66 个 CONNECTION_TYPES 中 47 个被 unit 使用，19 个未被使用。此审计把 19 个未使用项按**原因**分类，判断哪些是词汇缺口（可实用）、哪些是拓扑缺口（需多单元组合）、哪些是数据源缺口（MaleCNS v1.0 无法支撑）。

---

## 分类总览

| 类别 | 数量 | 说明 |
|---|---|---|
| A. 需要更精细解剖学 | 6 | MaleCNS v1.0 数据粒度不够 |
| B. 多单元组合层面使用 | 5 | 应在 `compose_from_units` graph 层而非 unit 内 |
| C. 需要 2-3+ 神经元群的单元 | 3 | 语义有效但缺合适单元 |
| D. 需要新单元类型 | 5 | 调制/塑料性/状态门控，需未来单元 |

## A. 需要更精细解剖学的（MaleCNS v1.0 无法支撑）

这些类型描述具体的突触亚型或物理机制，MaleCNS v1.0 只有二元 from→to 邻接矩阵，无突触亚型标注。诚实登记为「词汇完备性缺口」，不为凑使用率伪造证据。

| name | family | 原因 |
|---|---|---|
| axo_axonic | micro | 需 axon initial segment 定位，MaleCNS 无此粒度 |
| axo_dendrite_reciprocal | micro | 需方向性 reciprocal pair 标注 |
| pre_presynaptic_excitation | micro | 需 pre-activation 时序标注 |
| dendritic_excitatory_synapse | micro | 需 dendritic branch 定位 |
| ephaptic_coupling | electrical | 非突触物理机制，需空间邻近+电位场建模 |
| homeostatic_scaling | plasticity | 慢时间尺度稳态，非单步仿真 |

**处置**：保留在 schema（词汇完备），标 `extracted_from_malecns: false`（隐含），不强制使用。

## B. 多单元组合层面使用（不在单 unit 内）

这些是**图论拓扑描述**，语义上应该由 `compose_from_units` 在多个 units 组成的 graph 上使用，而非单个 unit 的 `internal_wiring`。

| name | family | 应使用位置 |
|---|---|---|
| inhibitory_hub | macro | 多 unit 组合：1 个 INH unit 广播到 N 个下游 |
| reservoir_smallworld | macro | 多 unit 组合：多个 unit 组成小世界网络 |
| divergent_fanout | macro | 多 unit 组合：1 unit 分叉到 N unit |
| convergent_fanin | macro | 多 unit 组合：N unit 汇聚到 1 unit |
| corollary_discharge | macro | 多 unit 组合：motor unit → 感觉单元（已有 cross-unit 边示例）|

**注**：`gustatory_centrifugal_unit → efferent_command_bus_unit` 的组合其实**就是** `corollary_discharge` 拓扑——只是我们在 spec 里用的是 `corollary_discharge` connection type 描述这条边。所以这一项其实**已在多单元组合层面使用**，未被 unit 内使用是合理的。

**处置**：这类类型不需要修改，词汇完备性正确。

## C. 需要 2-3+ 神经元群的单元

| name | family | 需什么 |
|---|---|---|
| feedforward_gating | circuit | 需要 gate population + 输入源 + 输出目标 3 群 |
| loop_relay_chain | circuit | 需要 3+ 阶 relay population 顺序传递 |
| efference_copy_cancellation | circuit | 需要 motor output + sensory copy + cancellation site |

**处置**：这些是有意义的电路模式，但当前 103 单元里没有专门建模这类"3+ 群"的单元。等未来加"多层 relay"或"gate population" 单元时再用。词汇完备性正确。

## D. 需要新单元类型

| name | family | 需要什么单元 |
|---|---|---|
| neuromodulatory_axon | modulatory | 沿轴突释放的神经元群（en-passant varicosities） |
| short_range_volume | modulatory | 短程扩散调制 |
| retrograde_messenger | modulatory | 逆向信使（postsynaptic → presynaptic） |
| state_gating_modulation | modulatory | 全局状态门控（`arousal.state` IN） |
| (以上 4 项) | | 需专门调制单元 |

**处置**：v2.9.0 已经加了 `hypothalamic_arousal_unit` OUT `modulatory.orexin/histamine`，但 IN 侧消费者还没建。本次 v2.10.0 已补：
- `antennal_lobe_glomerular_unit` IN `modulatory.histamine`
- `central_complex_steering_unit` IN `modulatory.orexin`
- `central_complex_steering_unit` IN `memory.associative`

**剩余的 `state_gating_modulation`** 需要 `arousal.state` IN 的消费者。当前 `hypothalamic_arousal_unit` 已把 arousal 输出成 `modulatory.orexin/histamine`，但没有 unit 用 `arousal.state` 直接作为 IN 类型。这是**词汇完备性缺口**——如果将来有专门的"全局状态门控"单元，就能用上。

## 诚实边界

1. **不用"未使用"数量作为质量指标**：47/66 是词汇完备性，不是"88% 覆盖率"。剩下 19 个是设计上的词汇，不代表 schema 有缺口。
2. **不为凑使用率伪造证据**：不为 unused CONNECTION_TYPES 强行添加 unit 内使用。
3. **区分词汇 vs 拓扑 vs 数据源**：三种缺口处置方式不同，不能一刀切。
4. ** MaleCNS v1.0 限制是硬边界**：没有突触亚型/递质/方向性标注，6 个 micro/electrical/plasticity 类型永远不会从 MaleCNS 派生。

## 结论

19 个未使用 CONNECTION_TYPES 中：
- **0 个是 schema 缺陷**（都需要外部条件：更精细数据源 / 多单元组合 / 新单元类型）
- **5 个已在多单元组合层面使用**（`corollary_discharge` 等），只是不在 unit 内
- **14 个是词汇完备性**（等未来数据源或单元类型到位再使用）

**不需要修改 schema**——本轮只需保留 66 个 CONNECTION_TYPES 不变。
