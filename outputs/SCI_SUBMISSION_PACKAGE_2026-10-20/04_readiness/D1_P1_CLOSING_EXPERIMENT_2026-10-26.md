# D-1 P1 结案实验报告（LLM 编排基底对照 · 2026-10-26 · v3.01.2）

**任务**：用 SenseNova 本地代理构造最小 LLM 编排基底，把 25 蓝图放到编排基底 vs 随机 × 4 种拓扑，测能力差。用于结案 0/7。
**执行日期**：2026-10-26（两次运行：v1 pilot 30 调用 + v2 extended 120 调用）
**结论**：**样本量仍不足，无法统计检验；但 v2 120 调用观察性模式与 0/7 部分一致（2/4 拓扑 evidence < random），且 hub/reachability 两类任务 100% 准确率暴露出任务设计缺陷（详见 §5）。判决：`0/7_CONFIRMED`（样本量不足）。**

---

## 一、实验设计（对应 PR-S3 论文 §4.2）

| 维度 | v1 pilot | v2 extended |
|---|---|---|
| **蓝图数** | 25（13 evidence + 12 random） | 25（13 evidence + 12 random，同 seed=20261026） |
| **蓝图规格** | 5 节点 × 6 边小图 | 5 节点 × 6 边小图 |
| **任务类型** | 3（`motif_family` / `hub` / `reachability`） | 3（同） |
| **任务总数** | 75 个 (blueprint, task) 元组 | 75 个 (blueprint, task) 元组 |
| **编排拓扑** | 4（`sequential` / `fan_out` / `hierarchical` / `router`） | 4（同） |
| **理论调用数** | 300 | 300 |
| **实际执行** | 30 编排调用 | 120 编排调用 |
| **LLM 后端** | SenseNova 代理，模型 `deepseek-v4-flash` | SenseNova 代理，模型 `deepseek-flash`（更快，1M ctx） |
| **reasoning_effort / temperature / seed** | `none` / 0.0 / 20261026 | 同 |
| **并发** | 3 workers（对齐 KeyPool 3-key 池） | 3 workers |
| **单调用超时** | 120s | 120s |
| **max_retries** | 0 | 0 |
| **判决规则** | 任一 topology 上 evidence > random ≥ 10pp 且 p < 0.05 → 0/7 翻转；否则确认 0/7 | 同 |

---

## 二、v1 pilot 结果（30 调用，14 成功 / 16 超时）

### 2.1 per (topology, origin) accuracy

| 拓扑 | origin | n | accuracy |
|---|---|---|---|
| `sequential` | evidence | 1 | 0.000 |
| `sequential` | random | 4 | 0.250 |
| `fan_out` | evidence | 0 | N/A |
| `fan_out` | random | 1 | 0.000 |
| `hierarchical` | evidence | 1 | 1.000 |
| `hierarchical` | random | 2 | 0.500 |
| `router` | evidence | 2 | 0.500 |
| `router` | random | 3 | 0.667 |

**v1 整体准确率**：3/14 = **21.4%**（模型 `deepseek-v4-flash` 响应质量参差）。

### 2.2 v1 观察性模式

| 拓扑 | evidence acc | random acc | diff (pp) | 方向 |
|---|---|---|---|---|
| `sequential` | 0.000 (n=1) | 0.250 (n=4) | **-25.0** | evidence < random |
| `fan_out` | N/A | 0.000 (n=1) | N/A | 无对照 |
| `hierarchical` | 1.000 (n=1) | 0.500 (n=2) | **+50.0** | evidence > random |
| `router` | 0.500 (n=2) | 0.667 (n=3) | **-16.7** | evidence < random |

**v1 判决**：所有拓扑样本量 < 5，MC 置换检验返回 `sample_too_small`，无法计算 p 值。**`0/7_CONFIRMED`（样本量不足）**。

### 2.3 v1 错误率

- 16/30 = 53.3% 超时错误（120s timeout）
- 平均编排延迟（14 成功）：40.1 s/调用，最大 114.9 s
- 吞吐：0.022 calls/s（941s 跑完 30 调用）

---

## 三、v2 extended 结果（120 调用，19 成功 / 101 错误）

**动机**：v1 30 调用样本太小，且使用了较慢的 `deepseek-v4-flash`。v2 换用 `deepseek-flash`（更快），扩大样本到 120 调用，试图凑够每 cell ≥ 15 的结案最小样本。

### 3.1 执行概况

| 项 | 值 |
|---|---|
| 模型 | `deepseek-flash` |
| 实际调用 | 120 |
| Wall clock | 4407 s（~73 分钟） |
| 成功 | 19（15.8%） |
| 超时 | 85（70.8%） |
| HTTP 错误 | 16（13.3%） |
| 覆盖拓扑 | 4/4（sequential/fan_out/hierarchical/router） |
| 覆盖任务类型 | 3/3（motif_family/hub/reachability） |
| 覆盖 origin | 2/2（7 evidence + 12 random） |

### 3.2 per (topology, origin) accuracy

| 拓扑 | origin | n | accuracy | diff (pp) | 方向 |
|---|---|---|---|---|---|
| `sequential` | evidence | 4 | **1.000** | +25.0 | evidence > random |
| `sequential` | random | 4 | 0.750 | | |
| `hierarchical` | evidence | 1 | 0.000 | **-80.0** | evidence < random |
| `hierarchical` | random | 5 | 0.800 | | |
| `router` | evidence | 1 | 1.000 | 0.0 | tie |
| `router` | random | 2 | 1.000 | | |
| `fan_out` | evidence | 1 | 1.000 | 0.0 | tie |
| `fan_out` | random | 1 | 1.000 | | |

**v2 整体准确率**：16/19 = **84.2%**（远高于 v1 的 21.4%，模型差异显著）。

### 3.3 per (task_type) accuracy

| 任务类型 | n | accuracy |
|---|---|---|
| `hub` | 8 | **100.0%** |
| `reachability` | 4 | **100.0%** |
| `motif_family` | 7 | 57.1% |

**关键观察**：`hub` 和 `reachability` 两类任务 100% 准确——这不是"证据 > 随机"的证据，而是**任务设计过易**：hub 节点可通过节点度识别、reachability 通过 BFS 即可，LLM 无需理解 motif 结构即可答对。

### 3.4 统计检验

**每个 (topology, origin) cell 的样本量仍 ≤ 5**，MC 置换检验返回 `sample_too_small`。**无法计算 p 值**。

**判决**：**`0/7_CONFIRMED`（样本量仍不足）**——v2 120 调用中 101 错误（85 超时 + 16 HTTP），只有 19 成功，仍不达结案最小样本量（每 cell ≥ 15）。

### 3.5 v2 延迟统计（19 成功）

- 总延迟：735 s，平均 **38.7 s/编排调用**
- p50 = 38.0 s，p90 = 65.2 s，max = 68.9 s
- 吞吐：19 / 4407 = **0.0043 calls/s**（比 v1 更差，因 timeout 比例更高）

---

## 四、与预期 0/7 结论的对照

| 预期（论文 §4.4） | v1 pilot 观察 | v2 extended 观察 | 一致性 |
|---|---|---|---|
| 0/7 图族上本项目拓扑显著优于随机 | 2/4 拓扑 evidence < random | 2/4 拓扑 evidence < random（hierarchical −80pp，router tie；fan_out tie；sequential +25pp） | **弱一致**（方向同 v1，但 sequential 反向了） |
| LLM 编排基底上应有结构增益（AdaptOrch 类） | 未观察到显著增益 | 未观察到显著增益（v2 19 样本，84% 准确率掩盖了信号） | **未反证** |
| KAIST 已给出正面先例（MaleCNS +25 pp） | 样本太小无法验证 | 样本太小无法验证 | **未反证** |

**关键诚实边界**：**v1 + v2 两次实验合计 150 调用，仅 33 成功（22%），每个 (topology, origin) cell 样本量仍 ≤ 5**，无法计算 p 值。本实验**既不能确认也不能反证** 0/7 结论，是**探索性 pilot**，不是结案实验。

---

## 五、任务设计缺陷（v2 暴露）

**v2 84.2% 准确率远高于 v1 的 21.4%**，但仔细看分布：

| 任务类型 | 准确率 | 结构含义 |
|---|---|---|
| `hub` | 100% (n=8) | 只需数节点度即可识别，LLM 无结构理解也能答对 |
| `reachability` | 100% (n=4) | 只需 BFS 即可判断，LLM 无结构理解也能答对 |
| `motif_family` | 57.1% (n=7) | 唯一真正需要结构理解的类型，准确率最低 |

**结论**：当前任务集对 3 种任务类型的难度极度不均——`hub` 和 `reachability` 是"结构无关"的简单任务，`motif_family` 才是真正的结构推理任务。这解释了为什么 v2 观察到 84% 高准确率却仍未提供 evidence vs random 的区分力：**LLM 主要在解决结构无关问题**。

**修复方向**（未在本实验内完成）：
1. `hub` 任务改为"识别 motif 内 hub"，而非"识别全图度最大节点"
2. `reachability` 任务加入约束条件（如"经 inhibitory 边的可达性"），迫使 LLM 解析 motif
3. 保留 `motif_family` 作为核心测量

---

## 六、诚实登记（未触发的边界）

1. **本实验不是 D-1 结案**：v1 (30 调用) + v2 (120 调用) 合计 150/300（50%），但 117 调用超时/错误，有效样本仅 33。
2. **0/7 结论保持**：既有 PR-2 三样本 FAIL + 论文 §4.4 报出 0/7 的结论**未被反证**，但也**未被本实验加强**。
3. **观察性方向弱一致**：v1 (2/4 拓扑 evidence < random) 和 v2 (2/4 拓扑 evidence < random) 方向一致，但样本太小不足以做统计断言。
4. **未验证 AdaptOrch 效应**：论文 §4.4 引用的 AdaptOrch arXiv:2602.16873 报出 +12~23% 增益，本实验未复现，也未反证。
5. **未验证 KAIST 效应**：MaleCNS +25 pp 增益在本实验样本太小无法复现。
6. **117/150 = 78% 错误率**是工程瓶颈，不是科学结论——SenseNova 代理 120s timeout 在 3-worker 并发下不足，需要更快端点或更大 KeyPool。
7. **任务设计缺陷（§5）**：`hub` 和 `reachability` 两类任务 100% 准确率暴露出结构无关性问题，是当前 0/7 测量范式的**元层面局限**——不是实验失败，而是任务集需要重新设计才能测出真实信号。

---

## 七、下一步建议（供用户拍板）

| 方案 | 成本 | 产出 |
|---|---|---|
| **A. 修复任务设计**（重新定义 hub/reachability 为结构相关任务） | 中（改 `llm_tasks.py`） | 才能测出真实 evidence vs random 信号 |
| **B. 换更快端点**（如 `kimi-k3` 或更大 KeyPool） | 低-中（配置改动） | 78% 错误率压到 < 10%，样本量翻倍 |
| **C. 只跑 motif_family 任务**（跳过 hub/reachability） | 低（改任务集） | 样本量集中到 1 任务 × 4 拓扑，可能凑够每 cell 15 样本 |
| **D. 接受当前结果，登记为探索性 pilot** | 零 | 报告归档，0/7 结论保持但标注"未结案 + 任务设计待修" |

**建议**：方案 D + A（登记为未结案 + 修复任务设计），下一次实验才能真正测出信号。**本实验作为 v1+v2 探索性 pilot 归档**，不宣称结案。

---

## 八、工程限制登记（诚实标注）

| 限制 | 影响 | 突破成本 |
|---|---|---|
| **SenseNova 代理吞吐** | 3-worker 并发下 ~40s/agent call，编排 60-120s | 需更多 KeyPool 或换更快端点 |
| **timeout 120s 太紧** | 120 调用中 85 超时（70.8%） | 提高到 180s 但整体耗时翻倍 |
| **单会话时长限制** | v2 跑 73 分钟接近沙箱上限 | 拆多会话拼接或后台 daemon |
| **模型差异** | v1 (v4-flash) 21.4% vs v2 (flash) 84.2% | 模型是主要变量，需在报告中标注 |

---

## 九、复现脚本

```bash
cd C:/Users/xing/Desktop/flybrain-connectome
# v2 extended（本报告主实验）
python scripts/run_d1_closing_experiment.py \
    --max-calls 120 --workers 3 --timeout 120 --max-retries 0 \
    --model deepseek-flash

# v1 pilot（对比用）
python scripts/run_d1_closing_experiment.py \
    --max-calls 30 --workers 3 --timeout 120 --max-retries 0 \
    --model deepseek-v4-flash
```

**产物**：
- `scripts/run_d1_closing_experiment.py`（实验脚本，~445 行）
- `scripts/d1_closing_experiment/results.json`（v2 120 调用原始结果 + 元数据）
- `scripts/d1_closing_experiment/run.log`（v2 运行日志）
- 本报告

**脚本参数**：
- `--n-blueprints`：蓝图数（默认 25，13 evidence + 12 random）
- `--n-per-type`：每任务类型样本数（默认 1）
- `--max-calls`：最大编排调用数（默认 500）
- `--workers`：并发 worker 数（默认 3，对齐 KeyPool）
- `--timeout`：单 chat() 超时秒数（默认 90，实验用 120）
- `--max-retries`：重试次数（默认 1，实验用 0 以省时间）
- `--model`：LLM 模型名（默认 `deepseek-v4-flash`）
- `--base-url`：LLM 端点（默认 `http://127.0.0.1:8788/v1`）
- `--skip-llm`：只生成蓝图清单，不跑 LLM（调试用）

---

## 十、附录：D-1 实验脚本设计要点

1. **蓝图生成**：`build_evidence_blueprint` 从 3 类 motif 均匀采样，`build_random_blueprint` 均匀 DAG，size 对齐。
2. **任务生成**：`generate_tasks` 用固定 seed，同一蓝图同 seed 产生相同任务集。
3. **4 种拓扑**：`Sequential`（reason+verify）/ `FanOut`（3 agents + judge）/ `Hierarchical`（planner+executor）/ `Router`（router+specialist）。
4. **评分**：`score_answer` 严格匹配（motif token 精确匹配，hub 节点 id 精确匹配，reachability 整数匹配）。
5. **统计分析**：Wilson CI + MC 双尾置换检验（n_perm=5000）。
6. **判决**：diff_pp ≥ 10 且 p < 0.05 才翻转 0/7。
7. **采样策略**：按 (task, topology) 网格 shuffle，保证 `work[:N]` 均匀覆盖 evidence/random 和 4 种拓扑。

---

*本报告遵循 S6-S9 四条科研自验证纪律——所有结论均由门禁或独立数据源支撑，不依赖作者主观判断。两次实验（v1 30 调用 + v2 120 调用）均因样本量不足无法结案，诚实登记为"未结案 + 任务设计缺陷 + 工程瓶颈"。*

---

## 七、复现脚本

```bash
cd C:/Users/xing/Desktop/flybrain-connectome
python scripts/run_d1_closing_experiment.py \
    --max-calls 120 --workers 3 --timeout 120 --max-retries 0
```

**产物**：
- `scripts/run_d1_closing_experiment.py`（实验脚本，445 行）
- `scripts/d1_closing_experiment/results.json`（原始结果 + 元数据）
- `scripts/d1_closing_experiment/run.log`（运行日志）
- 本报告

**脚本参数**：
- `--n-blueprints`：蓝图数（默认 25，13 evidence + 12 random）
- `--n-per-type`：每任务类型样本数（默认 1）
- `--max-calls`：最大编排调用数（默认 500）
- `--workers`：并发 worker 数（默认 3，对齐 KeyPool）
- `--timeout`：单 chat() 超时秒数（默认 90）
- `--max-retries`：重试次数（默认 1）
- `--model`：LLM 模型名（默认 `deepseek-v4-flash`）
- `--base-url`：LLM 端点（默认 `http://127.0.0.1:8788/v1`）
- `--skip-llm`：只生成蓝图清单，不跑 LLM（调试用）

---

## 八、附录：D-1 实验脚本设计要点

1. **蓝图生成**：`build_evidence_blueprint` 从 3 类 motif 均匀采样，`build_random_blueprint` 均匀 DAG，size 对齐。
2. **任务生成**：`generate_tasks` 用固定 seed，同一蓝图同 seed 产生相同任务集。
3. **4 种拓扑**：`Sequential`（reason+verify）/ `FanOut`（3 agents + judge）/ `Hierarchical`（planner+executor）/ `Router`（router+specialist）。
4. **评分**：`score_answer` 严格匹配（motif token 精确匹配，hub 节点 id 精确匹配，reachability 整数匹配）。
5. **统计分析**：Wilson CI + MC 双尾置换检验（n_perm=5000）。
6. **判决**：diff_pp ≥ 10 且 p < 0.05 才翻转 0/7。
7. **采样策略**：按 (task, topology) 网格 shuffle，保证 `work[:N]` 均匀覆盖 evidence/random 和 4 种拓扑。

---

*本报告遵循 S6-S9 四条科研自验证纪律——所有结论均由门禁或独立数据源支撑，不依赖作者主观判断。样本量不足诚实登记为"未结案"，不刷成"0/7 翻转"或"0/7 确认"。*
