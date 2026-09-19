# SwarmLabs × flybrain-connectome 集成指南 v2（A/B 已落地）

> 原则：**蜂群科研不嵌入果蝇数据**。flybrain 的 166,700 神经元 / 1.24 亿突触
> 始终留在基地文件夹 `C:\Users\xing\Desktop\flybrain-connectome`，通过 MCP / HTTP API
> 被调用；SwarmLabs 只持有**派生的 motif 模板 JSON** 与**合成拓扑 config**。
>
> v2 相对 v1 的两处实质变化：
> **A** 生成器不再读第二份静态 motif —— 运行时调服务的 `export_swarm_motifs`，快照仅作离线兜底。
> **B** C1 合成的拓扑直接吐出 SwarmLabs Agent 群能加载的 yaml/json（带校验，fail-closed）。

---

## 0. 基地文件夹里已就绪的资产

| 资产 | 位置（相对基地根） | 说明 |
|---|---|---|
| 真实数据 | `male_cns/` | 5.63 GB / 18 文件，全本地，含 connectome_cache |
| 数据校验清单 | `DATA_MANIFEST.json` | 数据 + 代码/文档双清单，逐文件 size+sha256 |
| MCP 服务 | `flybrain-connectome-mcp/mcp_connectome/server.py` | 12 工具（stdio，零第三方 SDK） |
| HTTP 服务 | `flybrain-connectome-mcp/run_api.py` | 12 工具，`127.0.0.1:8799`，Bearer 鉴权 |
| motif 抽取 | `flybrain-connectome-mcp/extract_motifs.py` | 从真实连接组重算三个 motif |
| motif 快照 | `flybrain-connectome-mcp/motifs/swarm_agent_topology_motifs.json` | 离线兜底真值 |
| **C1 生成器** | `flybrain-connectome-mcp/synthetic_bio_topology.py` | 虚拟生物拓扑合成 + A + B |
| drop-in 客户端 | `flybrain-connectome-mcp/motifs/flybrain_connectome_client.py` | SwarmLabs 直接复制 |
| 集成快照 | `integrations/swarmlabs/` | SwarmLabs 侧同步校验器（不复制代码，只校验一致性） |

MCP 已注册到本机 `~/.workbuddy/mcp.json` 的 `drosophila-connectome`，指向 HTTP/stdio
服务与 `male_cns` 稳定路径。

---

## 1. 起服务

```bat
:: 方式一（推荐，带日志到 api_runtime.log）
set FLYBRAIN_DATA_DIR=C:\Users\xing\Desktop\flybrain-connectome\male_cns
C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe ^
  C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp\run_api.py

:: 方式二
C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp\start_api.bat
```

自检：`curl http://127.0.0.1:8799/health` → `{"status":"ok", ..., "tools":12}`

---

## 2. A —— motif 来源：运行时连服务，快照只兜底

C1 的 `--motif-source`：

| 值 | 行为 | 语义 |
|---|---|---|
| `api` | 必须连上服务；失败**直接非 0 退出**，不静默降级 | 「服务真的活着」的硬门禁 |
| `auto`（默认） | 服务 → API 热缓存 → 离线快照，逐级回退 | 生产：实时优先，服务挂了不停工 |
| `local` | 只读快照，完全不碰网络 | 断网 / 可复现实验 |

**key 优先级**：`--api-key` → 环境变量 `FLYBRAIN_API_KEY` → 服务自己的
`mcp_connectome/config.json`（仅同机可用）。因此在本机**不设任何环境变量也能走实时**
（实测 `mode=api`）；下游项目拿到的是客户端副本、没有那个 config 文件，所以仍必须显式给 key。

**鉴权失败不降级**：401/403 被判定为**配置错误**而非服务故障，即使在 `auto` 下也直接
抛错退出。理由：key 写错却悄悄用旧快照，等于把配置错误藏起来。要离线就显式 `--motif-source local`。

```bash
python synthetic_bio_topology.py --motif-source auto     # 默认：实时优先
python synthetic_bio_topology.py --motif-source api      # 硬门禁（key 走 env/--api-key/local config）
python synthetic_bio_topology.py --motif-source local    # 完全离线
python synthetic_bio_topology.py --motif-source api --refresh   # 让服务重跑 extract_motifs
python synthetic_bio_topology.py --motif-source api --refresh-snapshot  # 顺手刷新离线快照
```

**可追溯性**：三种模式都把来源写进产物 `motif_provenance`：

```json
{"requested_source": "auto", "mode": "api", "transport": "http",
 "served_from": "service:http://127.0.0.1:8799",
 "doc_sha256": "b9755a4519be...", "motif_generated_utc": "2026-09-16T22:29:57Z",
 "fallback_reason": null}
```

任何一份拓扑都能回答「它是基于实时服务，还是基于某天的冻结快照」。

实测（2026-09-17）：

| 场景 | 结果 |
|---|---|
| `api` + 服务在线 | `mode=api`，sha256 与快照一致（证明两路同源） |
| `auto` + 服务在线、**不设任何环境变量** | `mode=api` ✓（key 自动取自同机 config） |
| `api` + `--refresh` | 服务真的重跑了抽取（40.2s），返回 `generated_utc` 更新的新文档 ✓ |
| `api` + 服务未起 | `MotifSourceError`，退出码 1 ✓（不静默降级） |
| **key 错误**（`--api-key WRONG_KEY`） | 401 → `MotifSourceError`，退出码 1 ✓（配置错误不当故障处理） |
| `auto` + 服务未起（有缓存） | `mode=api_cache` + `fallback_reason` ✓ |
| `auto` + 服务未起（无缓存） | `mode=local_snapshot` + `fallback_reason` ✓ |
| `local` | 不产生任何网络请求 ✓ |

---

## 3. B —— C1 拓扑 → SwarmLabs 可实例化 config

每个虚拟生物同时产出：

```
generated_organisms/
  <name>.json                    原始 organism
  <name>.html                    交互式力导向预览
  swarmlabs/<name>.swarm.json    ★ SwarmLabs 可实例化 config（规范真值）
  swarmlabs/<name>.swarm.yaml     同一对象的 YAML 镜像
```

config 关键字段：`swarm.agentteams.leader`（抑制枢纽 = leader）、`swarm.agents[]`
（含 `swarm_role`：leader/planner/executor/verifier）、`swarm.modules[]`、
`swarm.edges[]`（带权边表 + kind）、`swarm.guardrails[]`（拓扑不变式）、
`swarm.validation`、`swarm.source.motif_provenance`。

SwarmLabs 侧加载（仓库 `swarmlabs/agent_topology/`）：

```bash
python agent_topology/load_organism_config.py <path>\<name>.swarm.yaml
python agent_topology/load_organism_config.py <path>\<name>.swarm.json \
    --merge-team agentteams/config/team.yaml --out merged_team.json
```

`load_organism_config.py` **独立复算**校验（不信任文件自带的 validation 块），
命中悬空边 / 权重越界 / 负权边不是 inhibitory / 非自环 recurrent / leader 掉进模块内
任一条 → 抛 `SwarmConfigError` 拒绝产出 team（fail-closed）。

---

## 4. 调用示例（SwarmLabs 代码里）

```python
from flybrain_connectome_client import FlybrainHTTPClient, build_agent_topology

c = FlybrainHTTPClient("http://127.0.0.1:8799")      # key 从 FLYBRAIN_API_KEY 读
print(c.pair_synapses(10540, 12569))                 # -> 711（已解包）
motifs = c.export_swarm_motifs(refresh=False)        # 运行时拉取派生 motif

# 离线可跑：只用 motif JSON 生成 Agent 边表
topo = build_agent_topology(motifs["motifs"]["inhibitory_hub"], K_workers=12)
# topo["edges"] 即多 Agent 图的可实例化边表（负权=护栏）
```

> 注意 v2 语义变化：typed helper 现在返回**解包后的 result**（`711`），
> 不再是服务信封（`{"ok":true,"result":711}`）。需要信封用 `c.call(tool, args)`。

---

## 5. 三种 motif → 蜂群科研用途映射

| Motif | 生物原型（真实数字） | 在蜂群科研的落地 |
|---|---|---|
| `inhibitory_hub` | APL 单枢纽广播抑制（fan_out 102,263；APL→DPM 711） | 1 个协调/护栏 agent 对 top-K worker 发负权边，防失控/超提交 |
| `reservoir_smallworld` | 小世界布线（fanout 101–1000 占 49.36%） | K 个松散 agent 当集体短期记忆，readout agent 读状态 |
| `recurrent_feedback` | 子系统自循环（ol_intrinsic 28.74%） | 模块输出回灌自身，跨步保活状态，无需外部存储 |

---

## 6. 刷新 / 重建

- **motif 过期**：`--refresh`（服务侧重跑 `extract_motifs.py`），或直接跑
  `flybrain-connectome-mcp/extract_motifs.py`；再把新 JSON 同步给 SwarmLabs。
- **一致性校验**：`python integrations/swarmlabs/check_swarmlabs_sync.py`
  比对 base 与 swarmlabs 两侧客户端 / motif 快照的 sha256。
- **数据损坏/换机**：用 `DATA_MANIFEST.json` 逐文件比 sha256；
  缺失则从 `gs://flyem-male-cns` 用 `drosophila_connectome/scripts/fetch_fast.py` 重下。
- **API key 轮换**：改 `mcp_connectome/config.json` 的 `api_keys`（或 env
  `FLYBRAIN_API_KEY`），同步更新 SwarmLabs 的 `flybrain_connectome.yaml`。

---

## 7. 诚实注意事项

- `APL` 的 `neurotransmitter` 字段在该数据集里为**空**；"GABAergic" 来自文献，非文件标注。
- motif 是**拓扑模式**，不是神经元数据；真实 16 万神经元永远只在 flybrain 项目。
- 实测数字（均来自真实连接组）：总突触 124,177,617；APL→DPM 711；
  fanout 101–1000 占比 49.36%；ol_intrinsic 自循环 28.74%。
- 当前 dev API key `flybrain_dev_9a8b...` 是**本机开发占位**，公开暴露前必须轮换。
- 「虚拟生物」是**软件层类比**（Xenobots/Neurobots 的软件版），不是真细胞；
  它只复用真实连接组的拓扑原则，不做脉冲仿真、不做生物体建模。
