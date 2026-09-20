# flybrain-connectome

[![ci](https://github.com/lm203688/flybrain-connectome/actions/workflows/ci.yml/badge.svg)](https://github.com/lm203688/flybrain-connectome/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

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
| A connectome **query service** (21 tools over HTTP + MCP) | A spiking-neuron simulator |
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

The toolkit is **standard-library only** — no `requirements.txt`, nothing to
build. Pick either setup:

### A. Clone and run (recommended, verified end-to-end)

```bash
git clone https://github.com/lm203688/flybrain-connectome.git
cd flybrain-connectome
python flybrain_cli.py --help
```

### B. Editable install (puts `flybrain` on your PATH)

```bash
git clone https://github.com/lm203688/flybrain-connectome.git
cd flybrain-connectome
pip install -e .
flybrain info
```

`pip install -e .` is *editable*: the `flybrain` entry point maps back to the
checkout, which is precisely what lets it find the toolkit. A plain
`pip install .` ships only the launcher, so point it at a checkout explicitly:

```bash
pip install .
export FLYBRAIN_HOME=/path/to/flybrain-connectome
flybrain info
```

> **This path is verified in CI, not just documented.** The `package` job in
> `.github/workflows/ci.yml` runs `pip install ".[prov]"`, invokes the console
> script, resolves the toolkit via `FLYBRAIN_HOME`, generates an organism, and
> asserts the artifact's invariants — so the install instructions cannot
> silently rot.

### C. Optional: the standardized provenance bundle

Structural provenance (`motif_provenance`, with the snapshot sha256) is always
recorded. The *standardized* W3C PROV-JSON bundle (`prov_json`) is serialized
by the optional [`dataprov`](https://github.com/RI-SE/dataprov) package:

```bash
pip install "flybrain-connectome[prov]"   # or simply: pip install dataprov
```

Without it the toolkit still runs: `prov_json` becomes `null` and
`get_provenance_bundle` answers with `prov_available: false` plus the reason,
rather than crashing. Both arms are asserted by
`scripts/check_degraded_mode.py` — absent must degrade, present must actually
produce the bundle.

### Always check what you got

```bash
flybrain info
```

reports the resolved toolkit root, the motif snapshot, the data dir, API-key
status, and how many tools are exposed. Run it first whenever something looks
wrong — it turns "ImportError" into a named, fixable problem.

### To query the real connectome you also need the data

MaleCNS v1.0 is CC-BY, ~5.63 GB, and deliberately **not** in this repo:

```bash
export FLYBRAIN_DATA_DIR=/path/to/your/male_cns
```

`generate` and the bundled motif snapshot need **no** data at all.

---

## Quickstart

> Every `flybrain <cmd>` below also works as `python flybrain_cli.py <cmd>`
> (setup A), so you can try the project without installing anything.

### 0. Sanity-check the install

```bash
flybrain info
# -> toolkit root [ok] · motif snapshot [ok, 7363 bytes] · tools exposed: 21
```

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
├── flybrain_cli.py                 ★ developer CLI (serve/query/motifs/generate/verify/info)
├── pyproject.toml                  zero deps, `flybrain` console script
├── LICENSE · CITATION.cff · CHANGELOG.md
├── flybrain-connectome-mcp/
│   ├── mcp_connectome/             query engine (core) + 21-tool MCP + HTTP API (:8799)
│   ├── motifs/                     drop-in client + derived motif snapshot
│   ├── synthetic_bio_topology.py   ★ C1 generator (motif → agent graph + config + PROV)
│   ├── _verify.py                  end-to-end smoke test (70/70)
│   └── generated_organisms/        example artifacts (json/html + swarm configs)
├── integrations/swarmlabs/         consistency checkers + diagnostics (reproducible experiments)
├── scripts/                        run_gates.py · check_no_secrets.py · check_docs_consistency.py
│                                   check_mcp_tools.py · check_degraded_mode.py
│                                   check_generated_artifact.py · gh_publish.py
├── .github/workflows/ci.yml        the same gates, on py3.10/3.12/3.13 + packaged-CLI job
└── docs/                           arxiv_paper.md · mcp_setup.md
```

---

## HTTP API reference

Service: `flybrain-connectome-mcp/mcp_connectome/api_server.py`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET  /health` | none | liveness + version |
| `GET  /tools`  | key  | list the 21 tools + descriptions |
| `POST /query`  | key  | `{"tool": <name>, "args": {...}}` → `{"ok": true, "result": ...}` |

**Auth:** `Authorization: Bearer <key>` or `X-API-Key: <key>`. Keys come from
`config.json` (`api_keys`) or env `FLYBRAIN_API_KEY`. If none is configured the
server generates a temporary per-boot key and warns loudly — it never falls
back to a key committed to source.

**The 21 tools** (real names, do not invent — verified against `GET /tools`
by `scripts/check_docs_consistency.py`):

*Real-connectome queries — the 11 marked ⚠ need `FLYBRAIN_DATA_DIR`:*

`connectome_overview` ⚠ · `neuron_info` ⚠ · `pair_synapses` ⚠ ·
`neuron_outputs` ⚠ · `neuron_inputs` ⚠ · `degree` ⚠ · `search_neurons` ⚠ ·
`superclass_projection` ⚠ · `hub_targets` ⚠ · `list_superclasses` ⚠ ·
`pathway` ⚠ · `export_swarm_motifs`

*Generator surface — offline-capable, served from the motif snapshot:*

`list_blueprints` · `list_modules` · `list_bio_motifs` ·
`batch_generate_topologies` · `get_provenance_bundle` ·
`list_stacked_blueprints` · `get_stacked_feasibility` ·
`list_neuropils` · `get_neuropil_detail`

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

## Blueprint & module library

**25 blueprints** across three categories, composed from a **10 modules**
(sensory / memory / motor / integration / attention / working_memory / reward /
punishment / habit / metacognition). Every blueprint traces to a real motif
(`inhibitory_hub` / `reservoir_smallworld` / `recurrent_feedback`) or is
honestly marked `motif: none` (synthetic orchestration, no bio-prior) — 16
bio-prior, 9 not:

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

Machine-readable equivalents (same data, over HTTP/MCP): `list_blueprints`,
`list_modules`, `list_bio_motifs`.

---

## Science & paper

The methodology, the four moats, and the two negative results are written up
in **[`docs/arxiv_paper.md`](docs/arxiv_paper.md)** (preprint-ready). Key
references:

- MaleCNS v1.0 — *Cell*, 2026-09-03 (CC-BY). The 166,700-neuron male-brain
  connectome this project is grounded in. Obtainable from
  `male-cns.janelia.org/download` / `gs://flyem-male-cns/v1.0/`; queryable as
  neuPrint dataset `male-cns:v1.0`.
- Friston (2008) *Neuropsychologia* vs Fodor (1983) *The Modularity of Mind* —
  the massive-modularity debate our fault-isolation claim sits within.
- Double dissociation as the cognitive-neuroscience gold standard
  (Geddes 2014; Glenberg 2014; Campanella 2022; Vaidya *PNAS* 2010).
- `dataprov` (RI-SE, W3C PROV) — the provenance serialization we adopt.

**Citing this work:** see [`CITATION.cff`](CITATION.cff) (GitHub renders a
"Cite this repository" button from it). Release-by-release changes, including
which claims were retracted, are in [`CHANGELOG.md`](CHANGELOG.md).

**Using it from an MCP client:** see [`docs/mcp_setup.md`](docs/mcp_setup.md)
for client configs, the 21-tool reference, and troubleshooting.

---

## Development & testing

**One command runs every offline gate** — the same set CI runs, so "green
locally" and "green in CI" cannot diverge:

```bash
python scripts/run_gates.py              # 5 gates, no dataset needed
python scripts/run_gates.py --with-data  # + `flybrain verify` (70 assertions)
```

Individually:

```bash
# credential gate — MUST pass before any push (see CHANGELOG 1.0.0)
python scripts/check_no_secrets.py

# docs-vs-code drift gate: tool count/names, versions, schema, blueprint count
python scripts/check_docs_consistency.py

# every advertised MCP tool must actually respond (needs FLYBRAIN_DATA_DIR)
python scripts/check_mcp_tools.py

# a missing OPTIONAL dependency must degrade, not crash — and must not
# silently skip producing provenance when the dependency IS installed
python scripts/check_degraded_mode.py

# the generated artifact is structurally real (not just "exit code 0")
python scripts/check_generated_artifact.py --dir <out-dir> --name <organism>

# end-to-end smoke test (needs FLYBRAIN_DATA_DIR -> your data)
flybrain verify

# consistency between this repo and any downstream consumer
python integrations/swarmlabs/check_swarmlabs_sync.py

# reproducible experiments
python integrations/swarmlabs/diagnostics/fault_isolation_experiment.py --quick
python integrations/swarmlabs/diagnostics/snn_energy_experiment.py
python integrations/swarmlabs/diagnostics/multi_readout_experiment.py
```

`scripts/check_mcp_tools.py --offline` skips the 11 data-backed tools, which is
what CI does (the dataset is never downloaded in CI). So CI proves the
generator surface and the packaging, while the data path is proved by
`flybrain verify` on a machine that has the connectome.

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
