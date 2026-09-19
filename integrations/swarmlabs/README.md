# flybrain-connectome × SwarmLabs 集成 · Phase 4 收官

**日期**：2026-09-17 启动 · 2026-09-18 决策收敛 + 主线 1 落地
**状态**：Phase 4 全部完成 · R4/R5/R6 兑现 · E2E 验证完成 · **SwarmLabs 7 问题全部定稿** · **Motif 可追溯性落地（schema v1.1.1）**

---

## 1. 目录索引

### 需求与契约
| 文件 | 内容 | 读者 |
|---|---|---|
| `REQUIREMENTS_FOR_SWARMLABS.md` | R1-R6 改造需求书（**已同步 29 种 semantic + schema v1.1**） | SwarmLabs 开发 |
| `INTERFACE.md` | 双向接口契约 v1.1 | 双项目 |
| `QUESTIONS_FOR_SWARMLABS.md` | 需要 SwarmLabs 决策的 7 个问题（P0-P2 分级） | SwarmLabs 决策者 |

### 验证报告（按时间顺序）
| 文件 | 场景 | 关键结论 |
|---|---|---|
| `E2E_REPORT.md` | monod 单场景 | baseline vs blueprint 稳定 8-13% 加速（**后被 PROFILE 修正**） |
| `CROSS_DOMAIN_REPORT.md` | 3 跨域任务 × 4 蓝图 | 最优蓝图与任务类型相关（-3% 到 -22% 加速） |
| `BATCH_REPORT.md` | 10 单场景 × 2 配置 | **10/10 正确性保持**，8/10 wall 差异是噪声 |
| `PROFILE_REPORT.md` | cProfile 剖析 | **CPU 差异仅 +1-2%**，batch 的 -10% 是单次噪声 |
| `e2e_batch_stats.csv` | 5 场景 × 3 轮重复 | **1/5 显著加速**，4/5 在噪声范围内（统计显著性确认） |

### 工具脚本
| 文件 | 用途 |
|---|---|
| `check_swarmlabs_sync.py` | 一致性体检（sha256 + loader + 锚点） |
| `e2e_cross_domain.py` | 跨域任务对比（3 任务 × 4 配置） |
| `e2e_batch_scenarios.py` | 批量场景验证（10 场景 × 2 配置） |
| `e2e_batch_stats.py` | 批量统计显著性（5 场景 × 3 轮重复） |
| `blueprint_selector.py` | 蓝图选择启发式（10 条规则，基于实测数据） |
| `profile_compare.py` | cProfile 剖析对比 |
| `run_profile_quick.py` | profile 快速重跑 |
| `run_phase4_checks.py` | 一键验证（--quick / --ci / --full / --mode / --blueprint） |

### CI 集成
| 文件 | 内容 |
|---|---|
| `ci/flybrain-phase4.yml` | GitHub Actions workflow（手动触发模式） |
| `ci/README.md` | CI 集成指南（3 种方案对比） |

### 战略规划
| 文件 | 内容 |
|---|---|
| `API_EXPOSURE_STRATEGY.md` | API 对外暴露方案（3 种方案对比 + 实施清单） |
| `DATA_VERSIONING_STRATEGY.md` | 数据版本化策略（SemVer + 演进路线图） |

---

## 2. Phase 4 关键成果

### 兑现的 SwarmLabs 需求（R1-R6）
- **R1**：`--topology` CLI 参数 ✅
- **R2**：`build_workers()` 参数化（默认 4-agent 向后兼容）✅
- **R3**：`team.yaml` 加 `topology_file` 字段 ✅
- **R4**：PlannerAgent 按 module.capability 路由 ✅（实测 9 steps routed / 0 fallback）
- **R5**：`loop_report.json` 加 `topology_source` provenance ✅
- **R6**：PlannerAgent 消费 `edge.semantic` 做路由 ✅（29 种 semantic + route_rules）

### 主线 1 · Motif 可追溯性（2026-09-18 落地）
- **schema v1.1.1**（PATCH，向后兼容）：新增顶层 `motif_provenance` 字段
- 每个 blueprint 都能追溯到真实神经元：
  - `competitive_selection` → APL body 10540（10 万+ fan-out，inhibitory_hub）
  - `hierarchical` → reservoir_smallworld
  - `predictive_coding` → recurrent_feedback
  - 5 basic 蓝图 → `"none"`（人工设计，非生物先验）
- 每个 `.swarm.json` 都能回答"你的 agent team 来自哪个神经元"——LangGraph/AutoGen/CrewAI 永远回答不了
- `_verify.py` 40/40 通过（含 5 个 motif_provenance 校验）

### 飞轮效应
- flybrain 侧 schema v1.1.1 补齐语义字段（task_hint / edge.semantic / module.capability / motif_provenance）
- 9 种蓝图（5 basic + 4 bio）+ 可堆叠组合
- SwarmLabs 侧从"4 个死板 agent"进化到"N-agent 可配置 infra"
- E2E 验证：20+ 场景 × 多配置，正确性 100% 保持

---

## 3. 真实性能定位（诚实）

| 场景 | Blueprint 影响 |
|---|---|
| 单场景任务 | CPU +1-2%（真实开销），wall 噪声主导 |
| 跨域任务 | -3% 到 -22%（真实加速，任务匹配产物） |
| 多步推理 | CPU +1-2%，wall 噪声主导 |

**一句话**：Blueprint 的**性能代价几乎为零**，真实价值在**审计性**（可追溯）和**跨域任务匹配**（差异化加速）。

---

## 4. 运行一致性体检

```bash
# 一键体检
python integrations/swarmlabs/check_swarmlabs_sync.py

# 带 E2E 验证
python integrations/swarmlabs/e2e_cross_domain.py --baseline-only
python integrations/swarmlabs/e2e_batch_scenarios.py
python integrations/swarmlabs/profile_compare.py
```

期望：
- `check_swarmlabs_sync.py`：26 个 organism 全部 OK（含组合标签）
- `e2e_cross_domain.py`：3 任务 × 4 配置全通过
- `e2e_batch_scenarios.py`：10 场景 × 2 配置，score 100% 一致
- `profile_compare.py`：CPU 差异 < 5%（超阈值需人工复核）

---

## 5. 闭源边界（硬约束）

- flybrain-connectome 是闭源项目，不推 GitHub
- SwarmLabs 是独立项目，集成走 `--topology` 传文件路径
- 两个项目不共享代码目录（保持独立）
- 唯一共享物是 motif 快照 JSON（通过 sha256 校验）

---

## 6. 决策后的方向（2026-09-18 定稿）

### SwarmLabs 回复摘要
| 问题 | 决策 | 落地状态 |
|---|---|---|
| Q1 scipy 依赖 | ✅ 接受 | SwarmLabs 侧 `requirements.txt` 添加 `scipy>=1.10`（**SwarmLabs 自己改**） |
| Q2 Blueprint 定位 | ✅ 审计 | 已固化到 PROFILE_REPORT 结论，未来开发聚焦审计性 |
| Q3 CI 集成 | ✅ 本地手动 | 用 `run_phase4_checks.py --quick` 手动跑，不推 Actions 自动触发 |
| Q4 API 暴露 | ⏸ 暂缓 | `API_EXPOSURE_STRATEGY.md` 已打归档标记 |
| Q5 Blueprint 启发式 | ⏸ 暂缓 | `blueprint_selector.py` 已打归档标记，用户手动指定蓝图 |
| Q6 Schema v1.2 | ⏸ 延后到 v1.3+ | `DATA_VERSIONING_STRATEGY.md` 已打延后标记，v1.2 4 字段不预实现 |
| Q7 语义路由 | ✅ 29 种完整 | 保持现状，未来有新蓝图再扩展 |

### 未来开发方向（激活项）
1. **Blueprint 审计能力深化**（Q2 接受后主线）：路由留痕、语义分布统计、next-hop 可追查
2. **生物学蓝图扩展**：更多生物学来源（predictive coding 变体、hierarchical 多层）—— 独立于 SwarmLabs，flybrain 侧自主推进
3. **数据源扩展到 100k+ 实体**：与 SwarmLabs 数据飞轮并行，不阻塞

### 搁置项（不做，除非 SwarmLabs 唤醒）
- API 对外暴露（Q4）
- Blueprint 启发式集成（Q5）
- Schema v1.2 新字段（Q6）

### 已完成的 Phase 4 交付物
- ✅ **统计显著性**：5 场景 × 3 轮 = 30 样本，1/5 显著加速
- ✅ **blueprint 选择启发式**：10 条规则（SwarmLabs 未采用，归档）
- ✅ **CI 集成文件**：GitHub Actions workflow（未激活，仅备查）
- ✅ **API 暴露方案**：3 种方案对比（SwarmLabs 未采用，归档）
- ✅ **数据版本化策略**：SemVer + 演进路线图（v1.2 延后）

---

## 7. 相关文件

- 主文档：`flybrain-connectome-mcp/motifs/SWARMLABS_INTEGRATION.md`（v2）
- 生成器：`flybrain-connectome-mcp/synthetic_bio_topology.py`
- 需求书：`integrations/swarmlabs/REQUIREMENTS_FOR_SWARMLABS.md`
- SwarmLabs 侧 loader：`swarmlabs/agent_topology/load_organism_config.py`
