# drosophila-connectome · MCP 连接组查询/分析工具

把 **MaleCNS v1.0 雄性果蝇脑连接组**（166,700 神经元 / 1.25 亿突触，CC-BY）封装成
一个可查询、可分析的 MCP 工具服务器。零外部依赖（纯标准库实现 MCP 协议），
只依赖 `numpy` + `pyarrow`（已含于 minimind 虚拟环境）。

这是「果蝇脑虚拟实验室 + 知识引擎」的底座：既能被 LLM/Agent 当作工具调用
（X 是否连接 Y？蘑菇体输入有哪些？APL 的最强下游靶点？），也能作为
SwarmLabs / Coze 知识库的结构化数据后端。

## 目录
```
mcp_connectome/
  core.py     # 索引构建 + 精确查询（pair / outputs / inputs / degree / pathway / search）
  server.py   # MCP stdio 服务器（JSON-RPC 2.0，无第三方 SDK）
  demo.py     # 端到端自检（对照已发布 facts 的真实数字）
  README.md
```
数据缓存位于 `data/male_cns/connectome_cache/`（首次 `python -m mcp_connectome.core`
构建，约 1 分钟；之后加载秒级）。

## 运行

### 1) 构建索引缓存（首次）
```bash
cd drosophila_connectome
/c/Users/xing/.workbuddy/binaries/python/envs/minimind/Scripts/python.exe -m mcp_connectome.core
```

### 2) 自检（无需 MCP 客户端）
```bash
/c/Users/xing/.workbuddy/binaries/python/envs/minimind/Scripts/python.exe -m mcp_connectome.demo
# 7 passed, 0 failed
```

### 3) 作为 MCP 服务器启动（stdio）
```bash
/c/Users/xing/.workbuddy/binaries/python/envs/minimind/Scripts/python.exe mcp_connectome/server.py
```
服务器从 stdin 逐行读 JSON-RPC，向 stdout 写 JSON-RPC 响应。

## 接入 WorkBuddy / 任意 MCP 客户端

把下面这段合并进 `~/.workbuddy/mcp.json` 的 `mcpServers`：

```json
{
  "mcpServers": {
    "drosophila-connectome": {
      "command": "C:/Users/xing/.workbuddy/binaries/python/envs/minimind/Scripts/python.exe",
      "args": ["C:/Users/xing/WorkBuddy/2026-08-31-22-43-44/drosophila_connectome/mcp_connectome/server.py"]
    }
  }
}
```

保存后到 WorkBuddy 连接器管理页面对 `drosophila-connectome` 点 **Trust** 启用。

## 暴露的工具（11 个）

| 工具 | 作用 | 示例参数 |
|---|---|---|
| `connectome_overview` | 数据集高层真实统计 | — |
| `neuron_info` | 神经元元数据 + 递质预测 + 连接度 | `body: 10540` |
| `pair_synapses` | A→B 之间突触数 | `pre:10540, post:12569` |
| `neuron_outputs` | 最强下游靶点 Top-N | `body:10540, top:20` |
| `neuron_inputs` | 最强上游输入源 Top-N | `body:12569, top:20` |
| `degree` | 发出/接收突触总数 | `body:10540` |
| `search_neurons` | 按类型/超类/名称模糊搜 | `query:"APL", field:"type"` |
| `superclass_projection` | 某脑区上下游投射 | `superclass:"olfactory"`（别名→ol_intrinsic） |
| `hub_targets` | 命名枢纽的最强靶点 | `name:"CT1"` |
| `pathway` | source→target 是否连通 + 跳数 | `source:10540, target:12569` |
| `list_superclasses` | 列出可用脑区 token | — |

## 数据口径与诚实声明

- **所有数字均来自 MaleCNS v1.0 原始数据，零合成。** 自检中
  `pair_synapses(APL→DPM)=711`、`APL fan-out=102263 / fan-in=119935`、`total=124,177,617`
  与预计算 `connectivity_facts.json` 及论文 1.25 亿突触完全一致。
- **「神经元子图」口径**：`neuron_outputs / neuron_inputs / degree` 默认只统计
  两端都是「已注释神经元」(superclass 非空) 的边，与 `connectivity_facts.json` 一致。
  设 `neuron_only=False` 可含碎片/未注释片段。
- **连接组是接线图，不是权重**：本工具回答「谁连谁、连多少」，不做反向传播训练、
  不做脉冲仿真。脉冲/机器人控制属另一技术栈（见项目规划文档）。
- 路径查询 `pathway` 当前支持 1–2 跳（含中转），超过则报未连通。
