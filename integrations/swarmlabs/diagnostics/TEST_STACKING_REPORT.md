# v2.9.1 组合堆叠能力测试报告

**日期**: 2026-09-25  
**版本**: v2.9.1  
**测试脚本**: `integrations/swarmlabs/diagnostics/test_stacking.py`

---

## 测试范围

本报告验证 flybrain-connectome 功能单元库的组合堆叠能力，包括：

1. **v2.9.0 新增端口验证** — 确认 `memory.associative`、`modulatory.orexin`、`modulatory.histamine`、`sensory.*`、`modulatory.*` 五个新增端口类型已正确注册
2. **端口类型兼容性检查** — 验证 `compose_from_units` 的端口类型校验正常工作
3. **多种组合形态测试** — 链式、树状、网状三种拓扑结构
4. **大规模组合测试** — 4-5 单元复杂组合
5. **组合完整性验证** — 检查组合后节点/边的结构完整性
6. **v2.9.0 新端口组合测试** — 验证新端口能在实际组合中工作
7. **组合能力统计** — 可组合单元对数量统计

---

## 测试结果

### 1. v2.9.0 新增端口验证 ✓

| 端口类型 | 状态 | 使用次数 |
|---|---|---|
| `memory.associative` | ✓ 存在 | 1 处 (`mushroom_body_associative_memory_unit`) |
| `modulatory.orexin` | ✓ 存在 | 1 处 (`hypothalamic_arousal_unit`) |
| `modulatory.histamine` | ✓ 存在 | 1 处 (`hypothalamic_arousal_unit`) |
| `sensory.*` | ✓ 存在 | 通配符 |
| `modulatory.*` | ✓ 存在 | 通配符 |

**PORT_TYPES 总数**: 83 (v2.9.0 新增 2 个通配 + 3 个具体端口)

---

### 2. 端口类型兼容性检查 ✓

- **正确端口类型匹配**: `compose_from_units` 正确接受匹配的端口类型
- **错误端口类型匹配**: 正确拒绝不存在的端口，返回清晰的错误信息

---

### 3. 多种组合形态测试 ✓

| 组合形态 | 单元数 | 边数 | 状态 |
|---|---|---|---|
| 链式 (chain) | 3 | 2 | ✓ |
| 树状 (tree) | 4 | 2 | ✓ |
| 网状 (network) | 4 | 3 | ✓ |

**组合形态成功率**: 100%

---

### 4. 大规模组合测试 ✓

| 组合 | 单元数 | 边数 | 状态 |
|---|---|---|---|
| 视觉链 (visual_to_escape) | 5 | 3 | ✓ |
| 嗅觉链 (olfactory_to_steering) | 4 | 3 | ✓ |

---

### 5. 组合完整性验证 ✓

- 组合后节点数: 2
- 组合后边数: 1
- 所有节点保留原始单元信息 (功能、系统、端口)
- 边连接正确

---

### 6. v2.9.0 新端口组合测试 ✓

- **memory.associative 端口组合**: ✓ 成功
- **modulatory.orexin/histamine 端口组合**: ✓ 成功
- 新端口在组合结果中可见

---

### 7. 组合能力统计

**可组合单元对**: 243 对

**端口类型使用频率 (前 10)**:

| 端口类型 | 使用次数 |
|---|---|
| `motor.command` | 27 |
| `sensory.visual` | 20 |
| `arousal.state` | 16 |
| `sensory.somatosensory` | 12 |
| `cortex.output` | 12 |
| `cortex.association` | 11 |
| `sensory.auditory` | 9 |
| `sensory.visual.motion` | 8 |
| `sensory.olfactory` | 8 |
| `cortex.feedback` | 8 |

---

## 总结

| 测试项 | 结果 |
|---|---|
| v2.9.0 新增端口验证 | ✓ PASS |
| 端口类型兼容性检查 | ✓ PASS |
| 多种组合形态测试 | ✓ PASS |
| 大规模组合测试 | ✓ PASS |
| 组合完整性验证 | ✓ PASS |
| v2.9.0 新端口组合测试 | ✓ PASS |
| **总体** | **✓ 全部通过** |

---

## 关键发现

1. **v2.9.0 端口补齐成功** — 所有 5 个新增端口类型已正确注册并在实际组合中工作
2. **组合系统稳定** — 支持链式、树状、网状三种拓扑结构
3. **大规模组合可行** — 5 单元组合验证通过
4. **端口类型校验有效** — 错误配置被正确拒绝
5. **243 个可组合单元对** — 单元库具有高度的组合灵活性

---

## 剩余缺口

1. **19/66 CONNECTION_TYPES 未使用** — 词汇缺口，需文献支撑
2. **13 未锚定未引用 profile** — 跨支词汇缺口
3. **v2.9.0 新端口无对应 IN 端口** — 目前只能作为 OUT 端口使用，需未来扩展
4. **缺少可视化** — 无单元/电路级可视化

---

## 运行方式

```bash
python integrations/swarmlabs/diagnostics/test_stacking.py
```

预期输出: `总体: ✓ 全部通过`