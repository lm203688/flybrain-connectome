# flybrain-connectome

> **Traceable synthetic bio-topology generator**, grounded in the real
> *Drosophila* male-brain connectome (**MaleCNS v1.0** — 166,700 neurons /
> 124,177,617 synapses, CC-BY).

`flybrain-connectome` turns a real, published brain wiring diagram into
**task-tailored multi-agent topologies** you can instantiate as agent swarms —
and it can prove, for every edge, *which real neuron / synapse class it came
from*. The motif provenance is serialized as **W3C PROV-JSON**, the same
standard EU AI Act auditors expect.

It is a **developer toolkit and research artifact**, not a trained model and
not a simulation of a fly. Read the [honest boundaries](#honest-boundaries)
before you quote it.

---

## What it is / what it is NOT

| ✅ This project | ❌ Not this project |
|---|---|
| A connectome **query service** (12 tools over HTTP + MCP) | A spiking-neuron simulator |
| A **motif-extraction** pipeline (real fly → derived motif doc) | A repository of the raw 5.63 GB data |
| A **synthetic topology generator** (bio-motifs → agent graphs) | A trained / fine-tuned model with weights |
| **W3C PROV** provenance on every generated artifact | A claim that the "virtual organism" is alive |

The killer offline feature: **`generate` needs no data** — it composes
topologies from a 7 KB derived motif snapshot. The connectome data is only
needed if you want to *query* the real brain.

---

## The four moats (measured, not marketed)

We ran the experiments. Two of the "obvious" advantages turned out to be
**false** under controlled testing, and we say so.

| # | Moat | Evidence | Status |
|---|---|---|---|
| 1 | **Traceability** — every generated edge traces to a real neuron/synapse class, serialized as W3C PROV-JSON | `_verify.py` **70/70**; `prov_json` top-level field (schema v1.2.1) | ✅ real |
| 2 | **Structural parsimony** — genetic search finds far leaner graphs than the biological prior | GA converges to 9–11 edges vs 57 locked → **−84% wire cost** | ✅ real |
| 3 | **Structural stability** — module-level fault isolation | **25 / 27** sampled topologies show modular H1 isolation (92.6%); spectral radius ρ held at 0.00–0.30% | ✅ real |
| 4 | **Local decision-making** — modules read out their own answers | multi-readout experiment **5 / 28** H1 (17.9%), only on simple/delay≤2 tasks | ⚠️ partial |

### What we explicitly do *not* claim

| Dimension | Result | Why we dropped the claim |
|---|---|---|
| **Raw compute advantage** | 0 / 7 topologies beat random structure | Matched-control ESN calibration; motif advantage 0/7, differences within noise |
| **Energy advantage** | 0 / 24 runs beat random | SNN energy proxy; median ratio 1.006 (±5%), no systematic gain |

Honesty is a feature. The reproducible experiment scripts live in
`integrations/swarmlabs/diagnostics/` and the reports in the repo root
(`SNN_ENERGY_REPORT.md`, `MULTI_READOUT_REPORT.md`, `FAULT_ISOLATION_REPORT.md`).

---

## Install

Two ways — both dependency-free (standard library only).

```bash
# 1) Clone and run in place (recommended; also gives you the data path + scripts)
git clone https://github.com/lm203688/flybrain-connectome.git
cd flybrain-connectome

# 2) Or install the console script
pip install .
flybrain --help
```

To **query the real connectome** you also need a local copy of MaleCNS v1.0
(CC-BY, ~5.63 GB). Point the service at it:

```bash
export FLYBRAIN_DATA_DIR=/path/to/your/male_cns
```

---

## Quickstart

### 1. Serve the connectome (optional — only for querying real data)

```bash
flybrain serve --port 8799
# or: python flybrain-connectome-mcp/run_api.py
```

### 2. Query the real brain

```bash
export FLYBRAIN_API_KEY=<your-key>   # set in config.json or env

flybrain query pair_synapses --args '{"pre":10540,"post":12569}'
# -> 711   (the real APL → DPM connection)

flybrain query connectome_overview
# -> {"total_synapses": 124177617, "annotated_neurons": 211577, ...}
```

### 3. Pull the derived motif document

```bash
flybrain motifs --out motifs.json      # live pull from the service
# offline snapshot (no server, no data): flybrain-connectome-mcp/motifs/swarm_agent_topology_motifs.json
```

### 4. Generate a synthetic bio-topology (offline, no data)

```bash
flybrain generate --blueprint predictive_coding_v2 --modules 5 --agents-per-module 8
# -> generated_organisms/<name>.{json,html} + swarmlabs/<name>.swarm.{json,yaml}
```

### 5. Verify everything still works

```bash
flybrain verify        # needs FLYBRAIN_DATA_DIR set to your data
```

---

## Repository layout

```
flybrain-connectome/
├── flybrain_cli.py                 ★ unified developer CLI (serve/query/motifs/generate/verify)
├── pyproject.toml                  MIT, zero deps, `flybrain` console script
├── LICENSE                         MIT
├── flybrain-connectome-mcp/
│   ├── mcp_connectome/             connectome query engine (core) + 12-tool MCP + HTTP API(:8799)
│   ├── motifs/                     drop-in client + derived motif snapshot
│   ├── synthetic_bio_topology.py   ★ C1 generator (motif → agent graph + SwarmLabs config + PROV)
│   ├── _verify.py                  end-to-end smoke test (70/70)
│   └── generated_organisms/        example artifacts (json/html + swarm configs)
├── integrations/swarmlabs/         consistency checkers + diagnostics (reproducible experiments)
└── docs/arxiv_paper.md             the science write-up
```

---

## HTTP API reference

Service: `flybrain-connectome-mcp/mcp_connectome/api_server.py`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET  /health` | none | liveness + version |
| `GET  /tools`  | key  | list the 12 tools + descriptions |
| `POST /query`  | key  | `{"tool": <name>, "args": {...}}` → `{"ok": true, "result": ...}` |

**Auth:** `Authorization: Bearer <key>` or `X-API-Key: <key>`. Keys come from
`config.json` (`api_keys`) or env `FLYBRAIN_API_KEY`. If none is configured the
server generates a temporary per-boot key and warns loudly — it never falls
back to a key committed to source.

**The 12 tools** (real names, do not invent):

`connectome_overview` · `neuron_info` · `pair_synapses` · `neuron_outputs` ·
`neuron_inputs` · `degree` · `search_neurons` · `superclass_projection` ·
`hub_targets` · `list_superclasses` · `pathway` · `export_swarm_motifs`

---

## Synthetic organism schema

`synthetic_bio_topology.design_organism(spec)` returns:

```jsonc
{
  "organism": {
    "nodes": [ {"id": "m0_rep", "role": "tissue_rep", "module": 0,
                "profile": "memory", "ref_superclass": "CB", ...} ],
    "edges": [ {"from": "m0_rep", "to": "m0_c0", "weight": -0.31,
                "kind": "inhibitory", "module": 0, "ref_body": 10540} ]
  },
  "metrics": {
    "n_nodes": 29, "n_edges": 18, "avg_degree": 1.24,
    "inhibition_ratio": 0.11, "n_modules": 4,
    "intra_module_edges": 14, "inter_module_edges": 4,
    "modularity_est": 0.778, "profile_breakdown": { ... }
  },
  "blueprint": "predictive_coding_v2",
  "motif_provenance": {            // 3-stage traceability
    "mode": "local_snapshot",
    "motif_synapse_stats": { ... },     // % of the 124M-synapse dataset
    "motif_query": "SELECT ...",        // runnable provenance query
    "blueprint_to_motif": { ... }
  },
  "prov_json": { ... }             // W3C PROV-JSON bundle (schema v1.2.1)
}
```

The **W3C PROV-JSON** (`prov_json`) bundle records `entity` / `activity` /
`agent` nodes with `wasDerivedFrom` / `wasAssociatedWith` / `wasAttributedTo`
edges, attributing every topology to `FlyCellAtlas` and the
`flybrain:dataset_anchor` (MaleCNS v1.0). It is consumable by yProv4ML,
MLflow2PROV, and MIT Sloan provenance tooling.

---

## Blueprint library

25 presets across three categories. Every blueprint traces to a real motif
(`inhibitory_hub` / `reservoir_smallworld` / `recurrent_feedback`) or is
honestly marked `motif: none` (synthetic orchestration, no bio-prior):

- **5 basic** — flat / hub / ring / layered / random reference topologies
- **16 biological** — e.g. `predictive_coding_v2` (recurrent_feedback+reward),
  `metacognitive_control` (inhibitory_hub), `habit_consolidation`
  (recurrent_feedback), `hierarchical_deep` (reservoir_smallworld) …
- **4 synthetic** — `rl_actor_critic`, `curiosity_driven`, `cognitive_control`,
  `multi_motif_blend` (honestly `motif: none`)

Nested composition `a+(b+c)` is parsed as isomorphic to `a+b+c`. Full list:

```python
from flybrain_connectome_mcp.synthetic_bio_topology import BLUEPRINTS  # (in-repo path)
# or after pip install: import synthetic_bio_topology as c1; c1.BLUEPRINTS
```

---

## Science & paper

The methodology, the four moats, and the two negative results are written up
in **[`docs/arxiv_paper.md`](docs/arxiv_paper.md)** (preprint-ready). Key
references:

- MaleCNS v1.0 — *Cell*, 2026-09-03 (CC-BY). The 166,700-neuron male-brain
  connectome this project is grounded in.
- Friston (2008) *Neuropsychologia* vs Fodor (1983) *The Modularity of Mind* —
  the massive-modularity debate our fault-isolation claim sits within.
- Double dissociation as the cognitive-neuroscience gold standard
  (Geddes 2014; Glenberg 2014; Campanella 2022; Vaidya *PNAS* 2010).
- `dataprov` (RI-SE, W3C PROV) — the provenance serialization we adopt.

---

## Development & testing

```bash
# end-to-end smoke test (needs FLYBRAIN_DATA_DIR -> your data)
flybrain verify

# consistency between this repo and any downstream consumer
python integrations/swarmlabs/check_swarmlabs_sync.py

# reproducible experiments
python integrations/swarmlabs/diagnostics/fault_isolation_experiment.py --quick
python integrations/swarmlabs/diagnostics/snn_energy_experiment.py
python integrations/swarmlabs/diagnostics/multi_readout_experiment.py
```

---

## License & data provenance

- **Code:** MIT — see [LICENSE](LICENSE).
- **Connectome data:** MaleCNS v1.0, CC-BY. The 5.63 GB dataset is **not**
  included in this repository. Obtain it from the original publication and set
  `FLYBRAIN_DATA_DIR`. All numbers in this project are derived from that real
  dataset; nothing is synthetically fabricated to look impressive.

> "Virtual organism" is a **software-layer analogy**: we reuse real topology
> *principles* (motif shapes, recurrence rates, inhibition patterns), not real
> cells. It is not a wet-lab construct and is not claimed to be one.
