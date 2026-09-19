# flybrain-connectome ↔ SwarmLabs 接口契约 v1

> 起草日期：2026-09-17
> 起草目的：让"生物神经元基地"和"科研 Agent Infra"两个项目形成**契约性**关系，
> 取代目前的"flybrain 生成一堆 JSON 躺着、SwarmLabs 有 loader 但不读"的装饰性共存。
>
> 契约是双向的：**flybrain 承诺产出什么、SwarmLabs 承诺消费什么**，
> 每一侧都写清楚当前差距、必须补齐什么、Phase 归属。

---

## 0. 边界（先声明，避免误伤）

| 项目 | 授权状态 | 内容范围 |
|---|---|---|
| **flybrain-connectome**（本项目） | **闭源** | 真实连接组数据 / motif 引擎 / C1 生成器 / API 服务 / 全部脚本与产物 |
| **SwarmLabs** | **开源**（MIT） | agent infra 平台 / agentteams runtime / agent_topology 客户端 |

**桥**：
- 数据面：`.swarm.json` 快照（含 motif + agent 拓扑）——flybrain 产出，SwarmLabs 消费
- 服务面：HTTP API `:8799`（apikey 鉴权）——flybrain 提供，SwarmLabs 客户端可选直连
- 代码面：`flybrain_connectome_client.py` drop-in 客户端——两侧各持一份副本，靠 `check_swarmlabs_sync.py` 校验一致

**禁止**：
- 把 flybrain 的 motif JSON、organism JSON、连接组数据推到 SwarmLabs 公开仓库
- 在 SwarmLabs 里硬编码 flybrain 的 API key / URL（只能环境变量或运行时拉取）
- SwarmLabs 侧对 `.swarm.json` 做任何写回或本地重推导（"单一真值在 flybrain"）

---

## 1. 现状盘点（v1.0，2026-09-17）

### 1.1 flybrain 侧产出的 swarm.json schema

位置：`flybrain-connectome-mcp/generated_organisms/swarmlabs/*.swarm.json`

已有字段（以 `specialized_cycled` 67-agent 样例为准）：

| 层级 | 字段 | 内容 | 是否满足消费 |
|---|---|---|---|
| 顶层 | `schema_version` | `1.0` | ✅ |
| 顶层 | `kind` | `swarmlabs_agent_swarm` | ✅ |
| 顶层 | `generated_utc` / `name` | 时间戳 + 实例名 | ✅ |
| `swarm.source` | provenance（motif 来源、API URL、sha256 快照） | 完整可追溯 | ✅ |
| `swarm.agentteams.role_map` | `cell→executor`、`tissue_rep→planner`、`guardrail→verifier` | 语义映射齐 | ✅ |
| `swarm.agentteams.thresholds` | `rel_converged=0.05` 等 | 与 SwarmLabs 一致 | ✅ |
| `swarm.agents[]` | `{id, role, swarm_role, module}` | **仅 4 个字段，粗粒度** | ⚠️ 见 §2.1 |
| `swarm.modules[]` | `{index, lead, members[], recurrent_weight}` | 有模块划分 | ⚠️ 见 §2.1 |
| `swarm.edges[]` | `{from, to, weight, kind, module}` | kind ∈ {inhibitory, recurrent, reservoir} | ⚠️ 见 §2.1 |
| `swarm.guardrails[]` | 5 条规则文本 | 语义明确 | ✅ |
| `swarm.metrics` | 拓扑指标（含 profile_breakdown） | 有 profile 分布 | ✅ |
| `swarm.validation` | `ok=true`，含 dangling_edges/weight_range | fail-closed 自检 | ✅ |

### 1.2 SwarmLabs 侧已有能力

位置：`swarmlabs/agent_topology/`

| 文件 | 能力 | 状态 |
|---|---|---|
| `flybrain_connectome_client.py` | HTTP API 客户端，`resolve_local_api_key()` 走 env/config 三级回退 | ✅ |
| `swarm_agent_topology_motifs.json` | motif 快照（3 个 motif） | ✅ |
| `load_organism_config.py::load_organism_config()` | 加载 `.swarm.json`，fail-closed 校验 | ✅ |
| `load_organism_config.py::validate_swarm_config()` | 独立复算校验，不信任生成器自报 | ✅ |
| `load_organism_config.py::to_agentteams_team()` | 把 swarm.json 转成 team.yaml 结构 | ✅ **但无人调用** |
| `check_swarmlabs_sync.py` | 两侧客户端/motif sha256 一致性体检 | ✅ 8/8 通过 |

### 1.3 SwarmLabs 侧**没有**的能力（关键断点）

位置：`swarmlabs/agentteams/`

```python
# agentteams/run.py
def build_workers():
    return {"planner": PlannerAgent(), "executor": ExecutorAgent(),
            "verifier": VerifierAgent()}
```

**这一行是根因**：
- 3 个 agent 类**硬编码**，`team.yaml` 里的 `workers` 段只是文档装饰，改配置不改变行为
- `build_runtime()` 只从 `RUNTIMES` dict 里挑 runtime 类，不看拓扑
- `PlannerAgent` 不知道"module / memory / sensory"这些概念存在

因此目前 flybrain 的 motif 在 SwarmLabs 端**完全被跳过**，只有静态 4-agent 团队在跑。

> **已修复（2026-09-17）**：Phase 1 落地后 `build_workers()` 已能按 `.swarm.json` 拓扑
> 动态组建团队（详见 §3 Phase 1 与 §4 落地摘要）。本节保留为「改造前」快照以便对照。
>
> **Phase 3/4 也已落地（2026-09-17）**：`PlannerAgent` 已按 `module.capability` /
> `agent.task_hint` 三级路由，`loop_report.json::module_routing` 可见逐步路由决策；
> 67-agent 端到端已跑通且与 4-agent baseline 判定完全一致。但**诚实边界不变**：
> 路由产出的是「建议 + 留痕」，实际执行仍由规范 role 键的实例承担
> （Executor 只消费 `item["scenario"]` / `item["domain"]`，忽略 `routing`）。
> 详见 §4 的 Phase 3 / Phase 4 落地摘要与「本轮之后仍不成立的说法」。

---

## 2. 双向需求（契约的正文）

### 2.1 flybrain 侧需要补齐（由 SwarmLabs 消费需求倒逼）

优先级从 P0 到 P2，P0 必须先做完才能进入 Phase 3。

| ID | 缺失项 | 影响 | Phase |
|---|---|---|---|
| F1 | `agent.task_hint`：agent 该做什么类型的任务（如 `numeric_integration` / `literature_synthesis` / `calibration_check`） | 没有它 SwarmLabs 无法做**语义路由**——只能按 module 编号硬分配 | P0 |
| F2 | `edge.semantic`：边代表什么通信（baseline：`state_feedback` / `data_share` / `halt`；蓝图额外产出 `handoff` / `cross_state_feedback` / `synthesis` / `prediction_down` / `error_up` / `predicted_action` / `action_error` / `bypass_fast_path` / `async_record`） | 没有它 SwarmLabs 不知道"这条边是要触发一次消息传递还是数据快照" | P0 |
| F3 | `module.capability`：模块级能力声明（如 `can_do: [gp_surrogate, elo_rank]`） | 让 PlannerAgent 按能力路由而非按 role 硬编码 | P0 |
| F4 | `fallback`：模块/agent 故障时的替代路径 | 韧性——否则 257 节点拓扑里挂一个 agent 就全盘停 | P1 |
| F5 | `schema_version` 演进策略：1.0 → 1.1 → 2.0 的兼容承诺 | 长期维护——否则 SwarmLabs 每升级一次都要重新适配 | P1 |
| F6 | `agent.persona`：agent 的"角色描述"（用于 prompt 注入） | 让 agent 真正"像"某种生物功能单元，而不是无脸的 executor | P2 |

**产出规范**：
- v1.1 schema 是向后兼容的（旧消费者忽略新字段也能跑）
- 每个新字段必须有 `check_swarmlabs_sync.py` 里的独立复算校验

### 2.2 SwarmLabs 侧需要改造（由 flybrain 供给倒逼）

| ID | 改造点 | 影响 | Phase |
|---|---|---|---|
| S1 | `agentteams/run.py::build_workers()` 从硬编码改为**读取 team.yaml 或 topology_file** | 让 4-agent 变成 N-agent 可配置 | P0 |
| S2 | `agentteams/config/team.yaml` 新增可选 `topology_file` 字段，指向 `.swarm.json` 路径 | 让 team.yaml 变成真正配置而非文档 | P0 |
| S3 | `agentteams/core/runtime.py` 消费 topology_file 时调 `to_agentteams_team()` 动态生成 agent 实例 | 打通 loader → runtime 链路 | P0 |
| S4 | `PlannerAgent` 按 `module.capability` 做任务路由 | 从"按 role 派发"到"按能力派发" | P1 |
| S5 | 加 `--topology <file>` CLI 参数，不指定时保持向后兼容（4-agent） | 迁移路径不破坏现有 runs | P1 |
| S6 | `agentteams/runs/*/loop_report.json` 输出 `topology_source` 字段 | 可追溯"这次 run 用了哪个 motif" | P2 |

**约束**：
- S1-S3 完成后必须跑通现有的 `request_monod.json` 样例（`--approve` 与 `--rollback` 不破坏）
- 每次拓扑切换都要在 `loop_report.json` 里留痕，方便审计

---

## 3. 分阶段落地路径

每阶段独立可验收、可回滚，跨阶段不产生强依赖。

### Phase 1 —— 让 SwarmLabs 真正用上 flybrain 拓扑（改造 SwarmLabs，flybrain 侧不动）

**目标**：`build_workers()` 从硬编码变成读配置，能加载 `.swarm.json` 并按里面的 agents 列表动态生成 agent 实例。

**flybrain 侧产出**：无（继续用现有 v1.0 swarm.json）
**SwarmLabs 侧改动**：
- `agentteams/run.py::build_workers()` 加参数化
- `agentteams/config/team.yaml` 加 `topology_file:` 字段
- `agentteams/core/runtime.py` 消费 topology_file
- 保留默认 4-agent 行为作为 fallback

**验收点**：
- `python -m agentteams.run --request samples/request_monod.json` 行为不变（4-agent 默认路径）
- 新增 `python -m agentteams.run --topology <path>/specialized_cycled.swarm.json`，能启动 67-agent 团队
- 现有所有 run（`runs/run-*`）可复现
- `_verify.py` 在 flybrain 侧仍 21/21 通过

### Phase 2 —— flybrain schema v1.1：补齐消费语义（改 flybrain，SwarmLabs 侧等）

**目标**：`.swarm.json` 输出从"拓扑结构"升级到"拓扑结构 + 任务语义"，让下游能做语义路由。

**flybrain 侧改动**：
- `synthetic_bio_topology.py` 在生成 agent 时补 `task_hint` 字段（按 module profile 派生）
- 在生成 edge 时补 `semantic` 字段（按 kind 映射：inhibitory→halt、recurrent→data_share、reservoir→request）
- 在生成 module 时补 `capability` 字段（按 profile：sensory→[perceive]、memory→[gp_surrogate]、motor→[execute]、integration→[rank]）
- `schema_version` 从 `1.0` 升到 `1.1`
- 5 个现有 organism 全部重新生成
- 更新 `check_swarmlabs_sync.py` 里的独立复算校验（新增字段检查）

**验收点**：
- 5 个 `.swarm.json` 全部有 `task_hint` / `edge.semantic` / `module.capability`
- `schema_version == "1.1"`
- SwarmLabs 侧的 `validate_swarm_config()` 独立复算通过
- `flybrain-connectome-mcp/_verify.py` 扩展到覆盖新字段（目标 24/24）

### Phase 3 —— SwarmLabs PlannerAgent 消费 task_hint（SwarmLabs 侧改）

**目标**：PlannerAgent 按 `module.capability` 路由任务，不再按 role 硬编码派发。

**SwarmLabs 侧改动**：
- `agentteams/agents/planner.py` 读取 team 里的 modules + capabilities
- 任务派发逻辑：`for module in modules: if task_hint in module.capability: dispatch(...)`
- fallback：无匹配时回退到 executor 硬编码路径

**验收点**：
- `loop_report.json` 里能看到"本任务被路由到 module X (capability=gp_surrogate)"
- 现有 run 结果无回归

### Phase 4 —— 闭环：真实科研任务端到端跑通（联合）

**目标**：选一个真实科研任务（Monod 化学动力学或 GP 代理模型校准），用 specialized_cycled 67-agent 拓扑端到端跑完，产出与 4-agent baseline 的可对比结果。

**验收点**：
- 67-agent 团队能完整跑完 `request_monod.json`
- 结果与 4-agent baseline 的 rel_err 差异 < 阈值（不劣化）
- `loop_report.json` 完整记录：topology_source / module 路由决策 / fallback 触发

---

## 4. 验收矩阵（一眼看全）

| Phase | flybrain 侧改动 | SwarmLabs 侧改动 | 独立可验收？ | 回滚难度 | 状态 |
|---|---|---|---|---|---|
| 1 | 无 | `build_workers` + `team.yaml` + `runtime.py` + `leader.py`（4 文件） | ✅ | 低（改动局部，加参数不改默认） | ✅ **已完成（2026-09-17，见下方 Phase 1 落地摘要）** |
| 2 | `synthetic_bio_topology.py` + `_verify.py` + 重生成 8 个 organism | 无 | ✅ | 中（旧 schema 消费者会看到新字段但可忽略） | ✅ **已完成（2026-09-17）** |
| 3 | 无 | `planner.py` + `runtime.py` + `leader.py`（3 文件） | ✅ | 低（有 fallback 到 role 硬编码） | ✅ **已完成（2026-09-17，见下方 Phase 3 落地摘要）** |
| 4 | 无 | 端到端集成测试 + `agentteams/tools/compare_runs.py`（新工具） | ✅ | 中（保留 4-agent baseline 作对照） | ✅ **已完成（2026-09-17，见下方 Phase 4 落地摘要）** |

**Phase 2 落地摘要**：
- `MODULE_PROFILES` 加 `capability` / `task_hint_pool` / `lead_task_hint`
- `design_organism` 节点带 `task_hint`（cell 从 pool 派生、rep 用 lead_task_hint、coordinator 用 global_guardrail）
- `build_swarmlabs_config` 输出 agent.task_hint / agent.profile_name / edge.semantic / module.capability / module.profile_name
- swarm.json `schema_version` 从 `1.0` 升到 `1.1`（向后兼容，v1.0 消费者忽略新字段仍可解析）
- 备份在 `generated_organisms/swarmlabs/_backup_schema_v1.0/`
- `_verify.py` 从 21/21 升到 **25/25**（新增 4 项 v1.1 字段校验）
- `check_swarmlabs_sync.py` **13/13** 通过（含 8 个 organism 全部加载+独立复算校验）

**Phase 1 落地摘要（2026-09-17，SwarmLabs 侧）**：
- `core/runtime.py` 新增 `build_workers_from_topology(topology_file)`：消费 C1 `.swarm.json`，
  经 `load_organism_config` + `validate_swarm_config`（**独立复算，fail-closed**）+
  `to_agentteams_team()` 动态生成 agent 实例，返回 `(workers, topology_meta, team)`（S3）
- `run.py::build_workers(topology_file=None)`：从硬编码改为读拓扑（S1）；
  默认路径（无 topology）返回原 3-worker，**行为逐字节一致**
- `run.py` 新增 `--topology <file>` CLI，优先级 CLI → `team.yaml::team.topology_file` → 默认（S5）
- `config/team.yaml` 新增 `topology_file: null` 字段（S2）
- `agents/leader.py` 接受 `topology=` 并把 `topology_source` 写入 `loop_report.json`
  与 `result.json`（render 之前写入，两条产物都留痕）（S6）
- **验证**：
  - 默认路径回归 `run-20260917-144022` 与改动前 `run-20260917-143809` 数值完全一致
    （monod rel=0.0432 / inhibition rel=0.0232，span 12 = agent 4 + skill 7）
  - 拓扑路径 `--topology specialized_cycled.swarm.json` 跑通 `run-20260917-144036`：
    `specialized_cycled · 67 agents / 36 edges / 6 modules (schema v1.1, leader=coordinator)`，
    科学结论不变；`workers` 注册 69 项 = 66 agent_id 键 + 3 规范 role 键
  - fail-closed 自证：悬空边拓扑抛 `ValueError`，拒绝启动
- **诚实边界**：本阶段把 motif 拓扑**真正加载 + 校验 + 注册 + 留痕**，
  但实际「per-agent 语义路由」（把任务派到某个具体 `agent_id` 而非 role）是
  **Phase 3** 的事——当前 decompose 仍产出 3 个 role 任务，由规范 role 键的实例执行。
  Phase 1 消除的是「motif 被完全跳过」，不是「已按 67 个 agent 分工」。

**Phase 3 落地摘要（2026-09-17，SwarmLabs 侧）**：

- `agentteams/agents/planner.py` 重写：
  - `STEP_TASK_HINTS`：把计划步骤映射到 task_hint **候选池**（一个步骤可有多个候选，
    按序尝试，不是一对一映射——因为同一语义在不同拓扑里可能落在不同 module）
  - `route(task_hint)`：INTERFACE.md R4 的契约签名；`modules=None`（默认路径）时返回 `[]`，不抛错
  - `route_detail(task_hint)`：返回 `{task_hint, agents, module_index, profile_name, capability_hit, matched_by, fallback, reason}`
  - `_members_of(module)`：lead 优先排前，其余 members 跟随
  - **三级匹配 + 一级兜底**，每级都在 `matched_by` 里留痕：

    | 级别 | 依据 | `matched_by` |
    |---|---|---|
    | 1 | `module.capability` 直命 | `module.capability` |
    | 2 | `agent.task_hint` 精命 | `agent.task_hint` |
    | 3 | 前缀 / 子串模糊 | `fuzzy` |
    | 4 | 全未命中 → 回退 role 硬编码路径 | `fallback=True`，记入 `fallback_steps` |

- `core/runtime.py`：`build_workers_from_topology()` 建**共享单一 `PlannerAgent` 实例**
  （路由索引只建一次，不随 67 agent 数膨胀），注册时按 role 复用同一实例
- `agents/leader.py`：新增 `_collect_routing(rdicts)`，把逐步 routing 提炼成
  `loop_report["module_routing"]`
  - **为什么不交给 Executor**：`ExecutorAgent` 只消费 `plan.values()[*].plan[*]` 的
    `item["scenario"]` / `item["domain"]`，**忽略 `routing`**；且 `routing.agents` 是
    `agent_id` 列表，Executor 没有 per-agent 语义。若把 routing 交给 Executor，
    会得到一个写了但没人读的字段。故由 Leader 从 rdicts 提炼后写入报告，才真正可验收。
- **默认路径逐字节不变**：`route()` 返回 `[]`、`topology_note()` 返回 `None`，
  `loop_report.json` 顶层键仍为 `['collect','analyze','evaluate','optimize','rows']`
  （**无** `module_routing` / `topology_source`）
- **实测**（`run-20260917-150124`，`--topology specialized_cycled.swarm.json`）：
  - `summary`：`n_modules=6, n_agents_indexed=67, n_steps_routed=6, n_fallback=0, fallback_steps=[]`
  - 索引到 `capabilities` 15 个、`profiles` 4 个（sensory / memory / motor / integration）
  - 逐步路由示例：

    | 步骤 | task_hint | module | profile | agents | matched_by |
    |---|---|---|---|---|---|
    | `virtual_experiment.validate` | `experiment_run` | 2 | motor | m2_a0, m2_a4, m2_a8 | `agent.task_hint` |
    | `active_learning.rank_candidates` | `candidate_rank` | 3 | integration | … | `agent.task_hint` |
    | `uq.calibration_report` | `output_check` | 2 | motor | … | `agent.task_hint` |

  - 单元级验证：`gp_surrogate` 走**级别 1**（`module.capability` 直命，module 1，n=11）；
    `candidate_rank` / `experiment_run` / `output_check` 走**级别 2**；
    `nonexistent_thing` 正确 `fallback=True`
- **诚实边界**：验收点「`loop_report.json` 里能看到『本任务被路由到 module X』」**已满足**；
  但路由是**建议 + 留痕**，不是**改派执行**。decompose 仍产出 3 个 role 任务，
  Executor 仍按 role 取实例。因此**不能**对外声称「已按 67 个 agent 分工」。

**Phase 4 落地摘要（2026-09-17，联合）**：

- 新工具 `agentteams/tools/compare_runs.py`：**只读**比对两次 run 目录
  - 判定字段：`JUDGE_FIELDS = ("rel", "coverage", "cal_err", "maturity")`，`TOL = 1e-12`
  - `PASS` = 判定完全一致 **AND** 场景集合一致 **AND** candidate 有 `module_routing`
  - 退出码 `0`/`1`，可直接进 CI；`--out` 落 JSON 证据
- **对照 A**（4-agent vs 67-agent，证据 `docs/artifacts/phase4_compare_4agent_vs_67agent.json`）：

  | 检查项 | 结果 |
  |---|---|
  | `PASS` | **True** |
  | 场景集合 | 一致（`microbio_monod` / `microbio_inhibition`，无 `only_baseline` / `only_candidate`） |
  | `judgement_identical` | true，`judgement_diffs = []` |
  | rel | 0.0432 / 0.0232（两边逐位相同） |
  | coverage / cal_err / maturity | 1.0 / 0.05 / 已收敛（两边相同） |
  | `topology_source` | baseline=None agents · **candidate=67 agents**（n_edges=36, n_modules=6, n_workers_registered=69, validation_ok=true, schema 1.1） |
  | `module_routing` | baseline 无 · candidate 有（`n_steps_routed=6`, `n_fallback=0`） |
  | 顾问层 | 两边 `status=ok`，model=`flybrain:latest`，`affects_judgement=false` |

- **对照 B**（同 67-agent 拓扑，顾问层 ON vs OFF，证据
  `docs/artifacts/phase4_compare_advisory_on_off.json`）：同样 `PASS=True`、判定逐位一致、
  `affects_judgement=false`。这一份的作用是证明**顾问层是纯旁路**——开启本地小模型后，
  判定字段一个都没有变动。
- 回归：默认 4-agent 路径与改动前完全一致（monod rel=0.0432 / inhibition rel=0.0232、
  span 12、审计 14）
- **诚实边界**：`rel` 完全一致是**同种子确定性重算**的预期结果，**不是**「拓扑提升了精度」。
  Phase 4 证明的是「不劣化 + 拓扑可追溯」，**不是**「67-agent 比 4-agent 更准」。

**R6 / Phase 5 落地摘要（2026-09-17 晚，SwarmLabs 侧，对应 flybrain 需求书 REQUIREMENTS_FOR_SWARMLABS.md）**：

- **前提纠正（重要）**：该需求书声称 R1–R4「未实施、等 SwarmLabs 改」——**不实**。
  实际 R1(`--topology`)/R2(`build_workers` 参数化)/R3(`team.yaml::topology_file`)/
  R4(`PlannerAgent` capability 路由)/R5(`loop_report.topology_source`) 均已在 2026-09-17 早些时候
  随 Phase 1/3 落地（见上方 Phase 1/3 落地摘要）。需求书是更早状态的快照，已过期。
- **本批唯一新增：R6（blueprint + edge.semantic 路由）**：
  - `agentteams/agents/planner.py`：`SEMANTIC_ROUTE`（按**真实 28 个** organism 文件**全量校准**的
    **29 种** `edge.semantic` 取值，覆盖 baseline + 各蓝图全部真实标签；需求书 R6 片段只列了 9 种，已补全）、
    `route_next(task, current_agent_id)`、`blueprint_note()`；`run()` 在 blueprint/edges 存在时产出 `out["blueprint_routing"]`。
  - `agentteams/core/runtime.py::build_workers_from_topology`：构造共享 `PlannerAgent` 时
    透传 `blueprint` / `blueprint_info` / `edges`。
  - `agentteams/agents/leader.py`：新增 `_collect_blueprint_routing`，把 `blueprint_routing`
    落到 `loop_report.json`（与 `module_routing` 同口径）。
- **验收**：
  - `bp_predictive_coding` 拓扑跑通：`43 agents / 38 edges / 6 modules`，
    `loop_report.blueprint_routing.semantic_distribution` =
    `{state_feedback:6, data_share:16, halt:11, prediction_down:2, error_up:1, predicted_action:1, action_error:1}`，
    8 个抽样 next-hop 均可审计；`topology_source.blueprint=prediction_coding`。
  - 默认 4-agent 路径 `loop_report` **无** `blueprint_routing` / `module_routing` / `topology_source`（回归逐字节一致）。
  - **词汇覆盖率（2026-09-17 深夜补全）**：重新扫描 28 个 `.swarm.json` 得 29 种真实 `edge.semantic`，
    `SEMANTIC_ROUTE` 全部命中（**0 未映射**）；此前 12 词版本会令 17 种语义静默回退 legacy——
    那正是「蓝图仍是死数据」的缺口，本批已补。
  - **flybrain 侧对 R6 的定位（转达，2026-09-17 深夜）**：「R6 是让蓝图从'死数据'变'活拓扑'的关键；
    只做 R1–R3 的话 agent 数量对了但消息流转还是 role 硬编码，生物拓扑的价值只兑现 20%。」
    本批把词汇覆盖从 12/29 补到 29/29，是兑现这句话的关键一步；但须同步声明：当前 R6 产出的是
    **可审计的路由建议**（advice+trace），尚未接管真实消息流转（那属 Phase 5），故「活拓扑」目前指
    「活的可审计拓扑」，不是「活的调度执行」。
  - 单元级：`route_next` 对 `prediction_down` 边 → `downstream_executor`；`halt` 边 → `guardrail_verifier`；
    blueprint=None 但 edges 有语义时仍走 edge.semantic（非 legacy）；无 edges 时 legacy。
- **诚实边界（与 R4 同一口径）**：R6 是「建议 + 留痕」——`route_next` 把语义边解析成
  「谁→我」的下一步意图并写进报告，**不改写 dispatch**：实际派发仍由规范 role 键实例承担。
  需求书 R6 期望的「让蓝图真正驱动消息流转」在「执行」意义上**仍未达成**，属 Phase 5 的
  dispatch 重写（未做）。在此之前，任何「蓝图已驱动 agent 间协作调度」的说法都不成立。

**本地小模型接入（作为项目完整性的一环，2026-09-17）**：

- `agentteams/skills/local_model.py`（新 Skill，`local_model.advisory`）
- 调用链：`Leader._run_local_model_advisory()` → `ctx.invoke_skill(role, "local_model.advisory")`
  → Ollama `POST /api/chat`
- 模型选择：`auto` 按候选顺序 `flybrain:latest` → `minimind:latest` → `ornith-1.5:35b`
- 实测：`flybrain:latest`（63.91M，digest `fefa0276a585…`）调用成功，
  `generation={temperature: 0, seed: 0, max_tokens: 256}`，latency ≈ 75–2074 ms，
  `prompt_sha256` / `response_sha256` 齐备，trace + audit 均有 `local_model.advisory` span
- **权限最小化**：本地模型声明 `side_effect="external"`，但 `policy.yaml` 只对
  `local_model.advisory` 开**逐 Skill 白名单**（`allow_external_skills`），
  leader 的整条外呼通道保持关闭（`allow_external: false`）——让「需要外呼的单一能力」
  可被最小化授权，而不必打开角色的全部外呼权限。
- **只读顾问层边界**：本项目 `contracts.py` 明文「刻意不引入 LLM 依赖」，Agent 智能
  全部来自确定性科学计算。本地小模型被严格限制为**零裁决权**的旁路：
  输出只进 `loop_report.local_model_advisory`，并自带
  `counted_in_team_stats: false` / `authority: "none"` / `layer: "advisory_bypass"`。
- 三条降级路径均已实测：模型不存在 → `unavailable`；Ollama 不可达 → `unavailable` + reason；
  主流程仍报 `团队状态: ok`，不崩。
- **默认关闭**：`team.yaml::local_model.enabled: false`，保证既有 runs 可复现；
  `run.py --local-model [model]` / `--no-local-model` 显式开关。
- **诚实披露模型质量**：`flybrain:latest` 的实际输出**未提及场景 key、语义明显退化**，
  例如「该超类含 2 个微生物，共 2 个微生物，且随机对照试验结果。」
  产物里的 `quality` 字段把这一事实做成了可读字段（`mentions_any_scenario: false`）。
  **它的价值是证明本地训练的小模型可被调用、且调用全程可溯源，而不是承担科学判断**——
  任何把它当作「科学结论生成器」的用法都不成立。

**本轮之后仍不成立的说法（防止过度宣称）**：

- ❌「已按 67 个 agent 分工」——路由是建议 + 留痕，执行仍按 role
- ❌「67-agent 比 4-agent 更准」——判定逐位相同，同种子确定性重算
- ❌「本地小模型参与科学判断」——零裁决权旁路，`affects_judgement=false`
- ❌「67 条边 / 257 节点拓扑已在真实科研任务上验证」——Phase 4 用的是仓库内 Monod /
  inhibition 场景，非外部湿实验数据；`edge.semantic` 已被 R6 消费（advice+trace，未改写 dispatch）

---

## 5. 闭源边界守护清单

Phase 全部执行期间持续检查：

- [ ] SwarmLabs 公开仓库不出现 `flybrain_connectome_client.py` 之外引用 flybrain 内部路径的代码
- [ ] SwarmLabs 不提交任何 `.swarm.json` 到 git（只作运行时输入，不进源码树）
- [ ] flybrain 侧 `mcp_connectome/config.json` 里的 apikey 不进任何公开仓
- [ ] `motifs/*.json` 快照在 SwarmLabs 侧的 sha256 必须能被 `check_swarmlabs_sync.py` 校验
- [ ] 每次 Phase 完成前跑一次 `python integrations/swarmlabs/check_swarmlabs_sync.py`，8/8 通过

---

## 6. 未决事项（待用户拍板）

1. ~~**Phase 1 起点**：确认按 §3 Phase 1 的方案改 SwarmLabs `build_workers()`？~~
   ✅ **已定并落实（2026-09-17）**：按 §3 Phase 1 方案实施，默认路径向后兼容、
   `--topology` 显式启用。实际顺序与"备选"相反但更优——Phase 2（schema v1.1）先就绪，
   Phase 1 直接消费 v1.1 的 `task_hint` / `module.capability`，两阶段一次收敛。
2. ~~**Phase 4 的真实任务**：用 `request_monod.json` 还是 v3 microbiology API 的某个场景？~~
   ✅ **已按「不劣化对照」口径落实（2026-09-17）**：用仓库内已收敛的
   `microbio_monod` + `microbio_inhibition` 两组场景做 4-agent vs 67-agent 逐字段比对
   （`PASS=True`，judgement_diffs 为空）。**但这不等于「真实科研任务验证」**：
   该口径只证明确定性重算下不劣化 + 拓扑可追溯，未引入外部湿实验数据。
   `request_monod.json` 路径仍未跑通，如需「真实任务」口径需另开一轮。
3. **schema 版本演进**：`schema_version` 从 `1.0` → `1.1` 是加字段（向后兼容），还是 `2.0` 大改（破坏兼容）？建议 1.1，保持兼容。
   ✅ **已定为 1.1（2026-09-17）**，且已有 v1.0 快照备份
   （`generated_organisms/swarmlabs/_backup_schema_v1.0/`）与 `_verify.py` 25/25 校验。
4. **`edge.semantic` 已被消费（2026-09-17 修正，2026-09-17 深夜补全词汇）**：2026-09-17 深夜重新全量扫描
   **28 个** `.swarm.json`，得 **29 种**真实 `edge.semantic` 取值：baseline
   `state_feedback` / `data_share` / `halt`（全部文件共有）+ `handoff` / `cross_state_feedback` /
   `synthesis`（deep_reasoning）、`prediction_down` / `error_up` / `predicted_action` / `action_error`
   （predictive_coding）、`bypass_fast_path` / `async_record`（fast_reflex），以及此前漏扫、本次补全的
   `suppress_loser` / `surround_suppression`（competitive_selection / lateral_inhibition）、
   `candidate_vote` / `fanout_hypothesis` / `shared_stimulus` / `converge` / `execute` / `report` /
   `report_state` / `report_action` / `action_report` / `broadcast_observation` /
   `low_level_feedforward` / `high_level_abstract` / `cognitive_command` / `hierarchical_refine` /
   `feedforward_signal`。**注意**早期 §2.1 F2 写的 `request/verify/data_share/halt` 是错的；
   flybrain 需求书 R6 片段也只列了 9 种（`handoff`/`execute`/`report`/`synthesis`/`prediction_down`/
   `error_up`/`bypass_fast_path`/`suppress_loser`/`surround_suppression`）——SwarmLabs 侧 R6 已按
   **全量 29 种**把 `edge.semantic` 接进 PlannerAgent（`SEMANTIC_ROUTE` 映射 → `route_next()` →
   `loop_report.blueprint_routing`，含 8 个抽样 next-hop 可作审计证据），**0 未映射**（此前 12 词版本
   会让 17 种语义静默回退 legacy，等于「蓝图仍是死数据」）。
   **诚实边界不变**：R6 是「建议 + 留痕」——`route_next` 解析出「谁→我」的下一步意图
   （next_planner / downstream_executor / upstream_planner / guardrail_verifier 等），
   但**不改写 dispatch**：实际派发仍由规范 role 键实例承担。真正「按边语义驱动消息传递」
   的改造仍属 **Phase 5**，未做；在此之前，任何「拓扑边已参与协作调度执行」的说法都不成立。

---

## 附录 A：契约文件位置清单

- 本文件：`flybrain-connectome/integrations/swarmlabs/INTERFACE.md`
- 一致性校验器：`flybrain-connectome/integrations/swarmlabs/check_swarmlabs_sync.py`
- 集成说明：`flybrain-connectome/integrations/swarmlabs/README.md`
- SwarmLabs 侧 loader：`swarmlabs/agent_topology/load_organism_config.py`
- SwarmLabs 侧 motif 快照：`swarmlabs/agent_topology/swarm_agent_topology_motifs.json`
- flybrain 侧生成器：`flybrain-connectome/flybrain-connectome-mcp/synthetic_bio_topology.py`
- flybrain 侧验证套件：`flybrain-connectome/flybrain-connectome-mcp/_verify.py`
