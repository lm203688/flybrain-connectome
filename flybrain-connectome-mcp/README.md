# flybrain-connectome-mcp

把 **果蝇雄性脑连接组 (MaleCNS v1.0, Schlegel et al. 2026, CC-BY)** 变成可被
程序直接查询/分析的独立服务。两种接入方式共享同一套内存索引查询引擎：

1. **MCP stdio 服务器** — 给 WorkBuddy / Claude / Cursor 等 MCP 客户端当工具用
   （`python -m mcp_connectome.server`，零第三方 SDK）。
2. **HTTP API + apikey** — 给**其他项目**通过 `Authorization: Bearer <key>` 远程调用
   （`python mcp_connectome/api_server.py`，零依赖标准库 http.server）。

> 数据本体（1.8 GB feather + 3.6 GB 索引缓存）仍留在
> `../drosophila_connectome/data/male_cns/`，本仓库只放代码 + 服务。
> 用环境变量 `FLYBRAIN_DATA_DIR` 指向它即可，无需复制。

---

## 目录结构

```
flybrain-connectome-mcp/
├── mcp_connectome/
│   ├── __init__.py
│   ├── core.py          # 查询引擎：6 个 .npy 双排序索引 + 注解/递质缓存
│   ├── server.py        # MCP stdio 服务器（JSON-RPC 2.0，11 个工具）
│   ├── api_server.py    # HTTP API + apikey 鉴权（供其他项目调用）
│   ├── demo.py          # 端到端自检（对照已发布 facts）
│   ├── config.json      # 数据目录 / 端口 / api_keys
│   └── pyproject.toml
├── start_api.bat        # Windows 一键启动 API
└── README.md
```

## 真实数据（全部可溯源，零合成）

- 总突触 **124,177,617**（对论文 1.25 亿 ✓）
- APL → DPM = **711** 突触；APL fan-out **102,263** / fan-in **119,935**
- 跨脑区投射：嗅叶→嗅叶自 recur **28.74%**、中央复合体→中央复合体 **27.67%**
- 索引由 `drosophila_connectome/scripts/build_connectivity_facts.py` 预计算，
  总突触重算与上游统计完全一致。

---

## 1) 作为 MCP 工具（接 WorkBuddy）

把下面这段合并进 `~/.workbuddy/mcp.json` 的 `mcpServers`，
到连接器管理页面对 `drosophila-connectome` 点 **Trust** 即可。

```json
{
  "mcpServers": {
    "drosophila-connectome": {
      "type": "stdio",
      "command": "C:\\Users\\xing\\.workbuddy\\binaries\\python\\envs\\minimind\\Scripts\\python.exe",
      "args": ["C:\\Users\\xing\\WorkBuddy\\2026-08-31-22-43-44\\flybrain-connectome-mcp\\mcp_connectome\\server.py"],
      "env": {
        "FLYBRAIN_DATA_DIR": "C:\\Users\\xing\\WorkBuddy\\2026-08-31-22-43-44\\drosophila_connectome\\data\\male_cns"
      },
      "description": "果蝇雄性脑连接组 (MaleCNS v1.0) 查询/分析，11 个工具",
      "disabled": false
    }
  }
}
```

暴露的工具：`connectome_overview` / `neuron_info` / `pair_synapses` /
`neuron_outputs` / `neuron_inputs` / `degree` / `search_neurons` /
`superclass_projection` / `hub_targets` / `list_superclasses` / `pathway`。

---

## 2) 作为 HTTP API（给其他项目 via apikey）

启动（Windows）：
```bat
start_api.bat
```
或 Linux/Mac：
```bash
FLYBRAIN_DATA_DIR=.../drosophila_connectome/data/male_cns \
  python mcp_connectome/api_server.py
```
默认监听 `http://127.0.0.1:8799`，密钥在 `config.json` 的 `api_keys`
（也可用环境变量 `FLYBRAIN_API_KEY` 追加，`FLYBRAIN_API_PORT` / `FLYBRAIN_API_HOST` 改端口/地址）。

### 其他项目调用示例

```bash
# 健康检查（无需密钥）
curl http://127.0.0.1:8799/health

# 列出工具（需密钥）
curl -H "Authorization: Bearer $FLYBRAIN_API_KEY" \
     http://127.0.0.1:8799/tools

# 查询：APL(10540) 到 DPM(12569) 有多少突触
curl -X POST http://127.0.0.1:8799/query \
     -H "Authorization: Bearer $FLYBRAIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"tool":"pair_synapses","args":{"pre":10540,"post":12569}}'
# -> {"ok":true,"tool":"pair_synapses","result":711}

# 错误密钥会被拒绝（401）
curl -X POST http://127.0.0.1:8799/query -H "Authorization: Bearer wrong" \
     -d '{"tool":"pair_synapses","args":{"pre":1,"post":2}}'
# -> {"ok":false,"error":"missing or invalid API key"}
```

Python 客户端：
```python
import os
import requests
r = requests.post("http://127.0.0.1:8799/query",
    headers={"Authorization": "Bearer " + os.environ["FLYBRAIN_API_KEY"]},
    json={"tool": "superclass_projection", "args": {"superclass": "olfactory"}})
print(r.json()["result"])
```

> **密钥策略**：本项目**不附带任何默认 key**。`config.json` 被 gitignore，你必须自己生成
> 一个（`python -c "import secrets;print('flybrain_'+secrets.token_hex(32))"`）写进 `api_keys`，
> 或部署时注入 `FLYBRAIN_API_KEY`。两者都没有时，服务每次启动会随机生成临时 key 并告警。
> `scripts/check_no_secrets.py` 会在推送前拦截任何写死的 key。

---

## 3) 领域问答 Agent（可选）

`../drosophila_connectome/dataset/flybrain_sft_generated.jsonl`（604 条中英双语 SFT 语料，
事实全部可溯源）训练出的 `flybrain` 领域模型，可作为"自然语言问答"层，
与上面的查询/分析工具（"精确查证"层）互补：Agent 负责解释，工具负责算数。
训练与转换链路在 `../minimind/`：
`run_domain_sft_cpu.sh` → `convert_to_hf.py` → `convert_hf_to_gguf.py` → `ollama create flybrain`。

---

## 自检

```bash
FLYBRAIN_DATA_DIR=.../drosophila_connectome/data/male_cns \
  python -m mcp_connectome.demo
```
预期 7 passed / 0 failed（数字对照已发布 facts）。
