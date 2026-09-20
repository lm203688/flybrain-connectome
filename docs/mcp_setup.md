# Connecting an MCP client

`flybrain-connectome` exposes the same surface over two transports:

| transport | where | auth | needs `FLYBRAIN_DATA_DIR` |
|---|---|---|---|
| **MCP stdio** | `flybrain-connectome-mcp/mcp_connectome/server.py` | none (local process) | only for the 11 data-backed tools |
| **HTTP** | `flybrain-connectome-mcp/mcp_connectome/api_server.py` | API key | only for the 11 data-backed tools |

The server is a hand-rolled JSON-RPC 2.0 loop over stdio (protocol
`2024-11-05`, newline-delimited JSON) with **no third-party MCP SDK**, so it runs
on any Python 3.10+ that can import `numpy` + `pyarrow`.

---

## 1. Register the stdio server

Use an absolute path to `server.py`, and set `FLYBRAIN_DATA_DIR` in the
server's environment — MCP clients launch the process themselves, so a shell
`export` will not reach it.

### WorkBuddy / CodeBuddy — `~/.workbuddy/mcp.json`

```json
{
  "mcpServers": {
    "drosophila-connectome": {
      "type": "stdio",
      "command": "python",
      "args": ["/abs/path/to/flybrain-connectome/flybrain-connectome-mcp/mcp_connectome/server.py"],
      "env": {
        "FLYBRAIN_DATA_DIR": "/abs/path/to/your/male_cns"
      }
    }
  }
}
```

### Claude Desktop — `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "drosophila-connectome": {
      "command": "python",
      "args": ["/abs/path/to/flybrain-connectome/flybrain-connectome-mcp/mcp_connectome/server.py"],
      "env": { "FLYBRAIN_DATA_DIR": "/abs/path/to/your/male_cns" }
    }
  }
}
```

### Cursor / other MCP clients

Same shape: `command` + `args` + `env`. Point `command` at the interpreter that
has `numpy` and `pyarrow`; the toolkit itself has no dependencies.

> **On `FLYBRAIN_DATA_DIR`.** The connectome index is loaded lazily, so a wrong
> path does **not** break the server: `initialize` and `tools/list` succeed, and
> the 6 offline-capable tools (the 5 generator tools plus `export_swarm_motifs`)
> work normally. Only the 11 data-backed tools fail, and they fail with a clear
> message naming the missing file, e.g.
> `ERROR: [WinError 3] Failed to open local file '.../flat-connectome...'`.
> Symptom to watch for: "generation works but `pair_synapses` errors" means the
> data path is wrong, not the install. Run `flybrain info` to confirm.

---

## 2. The 36 tools

**Real-connectome queries** — the 11 marked ⚠ need `FLYBRAIN_DATA_DIR`;
`export_swarm_motifs` works from the bundled snapshot (only `refresh=true`
reads the data):

`connectome_overview` ⚠ · `neuron_info` ⚠ · `pair_synapses` ⚠ ·
`neuron_outputs` ⚠ · `neuron_inputs` ⚠ · `degree` ⚠ · `search_neurons` ⚠ ·
`superclass_projection` ⚠ · `hub_targets` ⚠ · `list_superclasses` ⚠ ·
`pathway` ⚠ · `export_swarm_motifs`

**Generator surface** — offline, served from the derived motif snapshot:

`list_blueprints` · `list_modules` · `list_bio_motifs` ·
`batch_generate_topologies` · `get_provenance_bundle` ·
`list_stacked_blueprints` · `get_stacked_feasibility` ·
`list_neuropils` · `get_neuropil_detail` ·
`get_module` · `check_module_compatibility` · `compose_virtual_organism` · `list_virtual_organisms` ·
`list_presets` · `get_preset` · `apply_preset` ·
`organism_to_swarmlabs` · `get_module_agent_roles` ·
`save_market_organism` · `load_market_organism` · `list_market_organisms` ·
`rate_market_organism` · `search_market_organisms` · `delete_market_organism`

Tool schemas are authoritative in source: `TOOLS` in
`flybrain-connectome-mcp/mcp_connectome/server.py`. Do not invent tool names —
`scripts/check_docs_consistency.py` fails the build if the docs and the
registry disagree.

`get_provenance_bundle` is the one to reach for when you need the W3C PROV-JSON
lineage of a topology (EU AI Act audits, yProv4ML / MLflow2PROV ingestion).

---

## 3. HTTP instead of stdio

```bash
export FLYBRAIN_DATA_DIR=/abs/path/to/your/male_cns
export FLYBRAIN_API_KEY=$(python -c "import secrets;print('flybrain_'+secrets.token_hex(32))")
flybrain serve --port 8799
```

`config.json` is read from the same directory as `api_server.py`. Copy
`config.example.json` to `config.json` and set `api_keys` for a stable key that
survives restarts. Note the file is **gitignored** on purpose — a live key must
never be committed.

Then, from another shell:

```bash
flybrain query pair_synapses --args '{"pre":10540,"post":12569}'   # -> 711
flybrain motifs --out motifs.json
```

`flybrain query` resolves the key as `--api-key` → `$FLYBRAIN_API_KEY` →
`config.json:api_keys[0]`, so on the same machine it works with nothing
exported.

Endpoints: `GET /health` (no auth), `GET /tools` (key), `POST /query` (key).
Auth accepts `Authorization: Bearer <key>` or `X-API-Key: <key>`.

---

## 4. Verify the wiring

```bash
# every advertised tool must actually respond (catches "advertised but dead")
python scripts/check_mcp_tools.py

# offline only — skips the 12 data-backed tools
python scripts/check_mcp_tools.py --offline
```

This gate exists because five advertised tools once shipped broken while every
other check stayed green. It enumerates `tools/list`, calls **each** tool with a
minimal valid argument set, and fails on any `isError` response or non-JSON
payload where JSON is promised.

---

## 5. Troubleshooting

| symptom | cause | fix |
|---|---|---|
| client shows the server as failed immediately | wrong `command` path, or `numpy`/`pyarrow` missing from that interpreter | run `python <abs>/server.py` by hand; it should sit silently waiting for JSON on stdin |
| generator tools work but data queries error with `Failed to open local file` | `FLYBRAIN_DATA_DIR` not set **in `env`** | set it in the client config, not in your shell — the client launches the process, so a shell `export` never reaches it |
| `401` on `/tools` or `/query` | key missing or wrong | set `FLYBRAIN_API_KEY`; `X-API-Key` also works |
| `ERROR: cannot reach http://127.0.0.1:8799` | service not running, or a stale process holds the port | check `/health`; kill the PID on 8799 and restart |
| tools missing from the list | client cached an older `tools/list` | restart the client |

---

## 6. Advanced features (v1.1.0+)

- **Module variants** — per-module parameter overrides (`sensory_vision`,
  `sensory_sound`, etc.) produce measurably different topologies.
- **SwarmLabs integration** — export any organism as a multi-agent team spec
  (`organism_to_swarmlabs`).
- **Virtual-organism market** — save, load, list, rate, search, and delete
  custom combinations (`save_market_organism` etc.).

See [docs/module_factory.md](module_factory.md) for full usage examples and
API reference.
