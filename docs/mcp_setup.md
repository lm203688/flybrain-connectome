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

## 2. The 45 tools

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
`rate_market_organism` · `search_market_organisms` · `delete_market_organism` ·
`list_combination_rules` · `validate_combination` · `expand_organism` ·
`get_multiplier_metrics`

**Functional-unit composition library** — offline, Tier-1, stdlib-only. This is
the layer that actually composes: 115 functional units (each ONE function,
delivered by a group of neuron populations with typed ports) + 66 connection
types (connection forms, constrained on port types). The unit list grew in
batches: 10 cognitive, 16 cross-clade (insect, bird, fish, cephalopod),
16 rhythm/state/error (annelid, ascidian, mollusc, pit viper, frog, cerebellum,
brainstem, hippocampus, barrel cortex), then Drosophila-shaped batches
v1.8.0–v2.1.0 (optic lobe, giant-fiber escape, male courtship & song, lateral
horn, feeding & grooming, ventral nerve cord, the efferent "E" pools, endocrine
release, centrifugal visual feedback).

**Embodiment layer (v1.7.0, densified v1.8.0, completed v1.9.0, v1.10.0 profile
expansion, v2.2.0 type-pair tier)** -- `functional_units/malecns_anchors.json`. It
anchors 57 of the 203 neuron populations to real annotated MaleCNS v1.0 cell types
(105,717 real cells over 4,872 types) and carries the measured connectivity
backbone: the complete 27x27 superclass matrix, cross-checked against
`connectivity_stats.json` (124,177,617 synapses / 25,582,938 edges -- both sources
agree). Each declared unit edge therefore carries the measured synapse count
between its populations' actual cell types, **plus a support tier re-derived from
the 4,872x4,872 type-pair matrix**: 109 edges are SUPPORTED (>=2 live type pairs),
6 FRAGILE (exactly one live pair carrying the whole profile-level non-zero), 1
CONTRADICTED. 37 of the 115 units have `provenance.embodied_in_malecns: true`; the
other 78 do not resolve to fly cells and each carries a machine-checkable
`provenance.unanchored_reason`. Twelve of those 78 are traced out of reconstructable
connectomes (four from the C. elegans adult reconstruction, v2.27.0; eight from the
Drosophila larva reconstruction, v2.28.0 + v2.29.0). The four C. elegans units
additionally carry `provenance.developmental_stages` (v2.30.0): the same four
circuits re-measured across all eight Witvliet 2020 reconstructions (L1 x4,
L2, L3, adult x2), so each unit reports the synapses its own cell classes carry
at L1 / L2 / L3 / adult. Those four rows are not additive (v2.34.0): the circuits
share cell classes -- AIA is in all four -- so one edge can be internal wiring
for several of them, and the four rows together overstate the wiring internal
to these circuits by 1.25-1.27x. Every unit therefore also carries
`provenance.developmental_stages.circuit_attribution` (sum / union / inflation
per stage) and `.shared_cell_classes_with`; the L1-only edge count in the
artifact caveat is measured into `stage_diffs`, not typed in. One of the four
also carries `.declared_vs_shipped` (v2.35.0): touch-avoidance declares 11 cell
classes but ships 10 members, because PLM has no edge in the adult
reconstruction and an unemitted class must not become a member; the
developmental series measures 11 because PLM does have edges in the merged
eight. The stage numbers therefore describe a slightly wider circuit than the
unit they attach to -- compare by that one class. They carry
`provenance.source_connectome`;
the remaining 66 are cross-species concept units. The eight Drosophila larva units
additionally carry `provenance.connectome_coverage` (v2.31.0): `larva_clusters.json`
walks all 116,922 larva edges and records, per unit, how many synapses have BOTH
endpoints resolving to a profile that unit declares -- 80,161 / 22.73% for the
olfactory unit down to 2,736 / 0.78% for the respiratory relay, 77.13% network-wide
and 3.52% frontier. Coverage there means traceable, not functionally
characterised. The eight per-unit rows are not additive either (v2.34.0): 19
larva profiles are declared by more than one unit, so the rows sum to 319,064
against the 271,956 covered total (1.17x) and each unit carries
`connectome_coverage.not_additive` with the shared-profile list, and
`connectome_coverage.member_id_caveat` (v2.36.0): the `_unannotated` suffix in
a `larv.*` profile id is bucket()'s modality-recognition fallback, not an
annotation verdict -- 13 of the 15 classes carrying it hold annotated cells
(`larv.kc_unannotated` is 144 Kenyon cells whose annotation is literally "KC"),
and 1,560 cells (52.77%) are the ones genuinely without an official
annotation. Being outside every unit is a coverage fact, not a labelling
claim.
**29 units** additionally carry `provenance.male_dimorphic` (v2.32.0): the MaleCNS
annotation table's own `dimorphism` column (2,368 bodies / 479 types) is streamed
over all 151,856,684 weight rows, and each unit records how far it sits from that
population -- 10.77% of network synapses touch a dimorphic body, only 1.28% have
both endpoints dimorphic. MaleCNS is male-only, so the ledger reports the
annotation, never a measured sex difference.

Audited in v2.33.0, which added three things every one of those 29 units now
carries. `body_scale`: the per-body synapse distribution (median 1,164 / p99
19,816 / max 271,220 over 191,696 annotated bodies), so a per-cell figure can be
read against this connectome instead of against a rule of thumb that the data
breaks -- `oviIN` at ~91k synapses per body is the 99.98th percentile of a
heavy tail, while the heaviest type by total (`TmY21`) is only the 72nd
percentile per body. `type_axis`: the ledger counts on the MaleCNS `type` axis,
which disagrees with `flywireType` on 33.08% of bodies -- `TmY21` is FlyWire's
`Tm36` -- and all 5,413 anchored type names are asserted to sit on that axis.
`dimorphism_provenance`: 150 of 479 types carry the curator's own
`matchingNotes` sentence and 327 are only `Roughly traced`. The per-type totals
are reconciled on every extraction (each pair charged once per dimorphic
endpoint, so they must sum to touching + both-ends = 14,966,115) and the
extractor refuses to write when they do not; v2.32.0's per-type column was
inflated by 3x the internal total and is corrected here.

**All 115 units** carry `provenance.function_axis` (v2.37.0): the function
categories the unit's own `capability` / `task_hint_pool` fields declare, which
is how the library is read by function rather than by the taxon its names come
from. A tag is a coverage label, not a performance claim. `GATE 11`
(`check_function_coverage.py`) checks that the coverage matrix reconciles with
the unit library and that the declared gap list matches the matrix -- it fails
when a gap is hidden, not when one exists. `flybrain function` prints the
matrix.

All 57 anchored populations are now referenced by
at least one unit (v2.1.0 wired the last five). A measured count of ZERO is a
recorded contradiction (currently one, in `central_complex_steering_unit`), never a
pass. `extracted_from_malecns` stays false everywhere: presence and non-contradiction
are checked, the declared microcircuit and connection form are not.

`list_functional_units` · `get_functional_unit` ·
`list_connection_types` · `list_evidence_ledger` · `compose_from_units`

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
