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

> **Repo status:** this repository is currently **private** (2026-09-22). It
> was made private as an immediate mitigation after Tier-2 IP was found in the
> public git history (see [CHANGELOG v1.3.0](CHANGELOG.md)). The Tier-1 code
> remains MIT-licensed; a history rewrite is planned to re-publicize it.
> Authorized collaborators can request access from the owner.

---

## What it is / what it is NOT

| ✅ This project | ❌ Not this project |
|---|---|
| A connectome **query service** (44 tools over HTTP + MCP) | A spiking-neuron simulator |
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

> **Note (2026-09-22):** this repo is **private** until the git-history
> rewrite is complete. You need a GitHub account with access to
> `lm203688/flybrain-connectome`; the clone commands below still work once
> you're authenticated (`gh auth login` or SSH keys).

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
# -> toolkit root [ok] · motif snapshot [ok, 7363 bytes] · tools exposed: 36
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
│   ├── mcp_connectome/             query engine (core) + 44-tool MCP + HTTP API (:8799)
│   ├── motifs/                     drop-in client + derived motif snapshot
│   ├── synthetic_bio_topology.py   ★ C1 generator (motif → agent graph + config + PROV)
│   ├── _verify.py                  end-to-end smoke test (70/70)
│   └── generated_organisms/        example artifacts (json/html + swarm configs)
├── integrations/swarmlabs/         consistency checkers + diagnostics (reproducible experiments)
├── scripts/                        run_gates.py · check_no_secrets.py · check_docs_consistency.py
│                                   check_mcp_tools.py · check_degraded_mode.py
│                                   check_generated_artifact.py · gh_publish.py
├── .github/workflows/ci.yml        the same gates, on py3.10/3.12/3.13 + packaged-CLI job
└── docs/                           arxiv_paper.md · mcp_setup.md · module_factory.md
```

---

## HTTP API reference

Service: `flybrain-connectome-mcp/mcp_connectome/api_server.py`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET  /health` | none | liveness + version |
| `GET  /tools`  | key  | list the 44 tools + descriptions |
| `POST /query`  | key  | `{"tool": <name>, "args": {...}}` → `{"ok": true, "result": ...}` |

**Auth:** `Authorization: Bearer <key>` or `X-API-Key: <key>`. Keys come from
`config.json` (`api_keys`) or env `FLYBRAIN_API_KEY`. If none is configured the
server generates a temporary per-boot key and warns loudly — it never falls
back to a key committed to source.

**The 44 tools** (real names, do not invent — verified against `GET /tools`
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
`list_neuropils` · `get_neuropil_detail` · `get_module` ·
`check_module_compatibility` · `compose_virtual_organism` · `list_virtual_organisms` ·
`list_presets` · `get_preset` · `apply_preset` ·
`organism_to_swarmlabs` · `get_module_agent_roles` ·
`save_market_organism` · `load_market_organism` · `list_market_organisms` ·
`rate_market_organism` · `search_market_organisms` · `delete_market_organism` ·
`list_combination_rules` · `validate_combination` · `expand_organism` · `get_multiplier_metrics`

*Functional-unit composition library — the composable layer above neuron types:*

`list_functional_units` · `get_functional_unit` ·
`list_connection_types` · `compose_from_units`

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

**25 blueprints** across three categories, composed from **136 modules**:
**10 cognitive-function modules** (sensory / memory / motor / integration / attention /
working_memory / reward / punishment / habit / metacognition) + **126 cross-species
neuron types** spanning cortical pyramidal (L2/3 CX1/CX5, L4b/L4c, L5 basal tuft, L6 reticulo-thalamic,
L7 temporal, Mayeret) + intermediate interneurons (Calbindin/LAMP/NPH/NPF/VLAC/SST-dendritic/
SST-somatic/KCN, plus PV/SST/VIP/chandelier/basket) + modulatory systems (dopaminergic
A9/A11/VMC/VTA/SNC, serotonergic dorsal/ventral/median raphe, noradrenergic LC, cholinergic
MT/horizontal, histaminergic TM, orexin) + retinal (bipolar cone/rod, amacrine ACL1/ACL2,
midget/PV ganglion, horizontal) + spinal/cerebellar (α/γ motor, Icc/Ih/Ihp interneurons,
glycinergic, nociceptive, Purkinje/granule/stellate, inferior olive) + thalamic/basal ganglia
(LGN/MD/VA/VL/VPL/VPM/RTN, STN, red nucleus, striatal D1/D2 MSN) + limbic/edge
(hippocampal CA1/CA2/CA3/CA4/granule/subiculum, amygdala BLA/LA, septum, entorhinal L2/L3,
grid cell) + special senses (pineal, melanopsin, olfactory, vestibular, cochlear outer hair)
+ reactive astrocyte

+ **four clades whose neurons have no vertebrate-cortex counterpart** (35 further types,
each carrying its own `biological_reference`):

- **insect (14)** — Kenyon cell / mushroom-body output / PPL1-PAM dopaminergic / APL,
  antennal-lobe projection and local neurons, protocerebral bridge / ellipsoid body /
  fan-shaped body / noduli / ring neurons, s-LNv and lateral clock neurons, descending neuron
- **bird (6)** — HVC, RA, LMAN, Area X, DLM, NIf (the song system)
- **fish (8)** — Mauthner cell, reticulospinal neuron, lateral-line hair cell,
  ampullary and tuberous electroreceptors, ELL pyramidal cell, electrosensory inhibitory
  interneuron, electric-organ pacemaker neuron
- **cephalopod (7)** — vertical-lobe large / amacrine / small cells, superior frontal lobe
  cell, chromatophore motor neuron, arm motor neuron, arm sensory afferent

Every blueprint traces to one of
**40 topology motifs** (3 original MaleCNS-extracted + 37 conceptual patterns spanning
anatomical / functional / plasticity / specialized categories) or is honestly marked
`motif: none` (synthetic orchestration, no bio-prior) — 16 bio-prior, 9 not:

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

## Functional-unit & connection-type library

The neuron list above is the *vocabulary*. It is not the *unit of composition*: a
single neuron type does nothing on its own, and wiring two of them together means
nothing. What composes is a **function with a known interface**. So the library is
split into two tiers, and the upper tier is the one you actually build from:

- **56 functional units** — each is ONE function (phototransduction, action
  selection, theta pacing, gliotransmission, sparse mushroom-body coding, ring-attractor
  heading, song timing, Mauthner escape, active electrolocation, camouflage …) delivered
  by a **group** of neuron populations (1–6 of them, taken from the 136-module vocabulary)
  wired into an internal sub-circuit, and exposing **typed ports** (`light` in →
  `high_res` out; `candidates` + `value` in → `selected_action` out).
  **16 of the 56 are cross-clade** (insect / bird / fish / cephalopod) and 40 are the
  mammal-cortex-shaped set.
- **58 connection types** — each is one connection FORM, constrained on the port
  types it may join, in six families:
  **micro** (axo-dendritic / axo-somatic / axo-axonic / dendro-dendritic …
  point-to-point contact sites) · **circuit** (feedforward / feedback / lateral /
  mutual / recurrent / disinhibition / winner-take-all / global inhibitory gain control /
  synfire chain / efference-copy cancellation …) · **modulatory**
  (diffuse / volume / retrograde / state gating) · **electrical** (gap junction /
  ephaptic / mixed electro-chemical / tripartite astrocyte) · **plasticity** (STDP /
  LTP-LTD / short-term / homeostatic scaling / modulator-gated / repeated-activation LTS) ·
  **macro** (topographic mapping / divergent fan-out / convergent fan-in / corollary
  discharge / global broadcast / sparse expansion / command-neuron recruitment).

So the algebra is `virtual organism = units (nodes) + connection types (typed
edges)`, and every edge is mechanically checkable because both endpoints declare
port types:

```
unit A .out_port[type]  --connection_type(from_port, to_port)-->  unit B .in_port[type]
```

`compose_from_units` enforces port-type compatibility, required-port
satisfaction, external drivability/readability of the whole organism, and
reports feedback loops as warnings (an intentional feedback loop is a
first-class citizen here). An unsatisfied *required* input on the organism
boundary is the organism's external input, not a defect — pass
`allow_boundary_inputs: false` to validate an interior sub-chain instead.

Three canonical chains ship as fixtures and are re-validated by Gate 9 on every
run — `--demo mammal` (retina → thalamus → cortex → basal ganglia → motor
thalamus), `--demo insect` (antennal lobe → mushroom body sparse code → learned
valence → central complex heading/steering, clock-biased) and
`--demo electrosensory` (EOD pacemaker → efference-copy cancellation →
electrolocation, plus a passive-electric cue into the Mauthner escape command).
`--demo` with no argument runs all three.

**Honest boundary.** These units are curated from comparative-neuroscience
literature with a named reference each (`provenance.extracted_from_malecns` is
`false` for all 56) — they are NOT extracted from MaleCNS v1.0, unlike the three
original fly motifs. Member ratios are composition weights, not measured cell
counts. Treat the layer as a composable scaffold with literature provenance, not
as a measured cell assembly.

Machine-readable equivalents: `list_functional_units`, `get_functional_unit`,
`list_connection_types`, `compose_from_units`. Regenerate + verify with
`python scripts/gen_functional_units.py` and `scripts/check_functional_units.py`
(Gate 9, which fails the build if the artifacts drift from the generator, if a
member neuron does not exist in the vocabulary, or if the composer stops
rejecting malformed wiring).

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

**Using it from an MCP client:** see [`docs/mcp_setup.md`](docs/mcp_setup.md).
**Module variants, SwarmLabs integration, and the organism market (v1.1.0):**
see [`docs/module_factory.md`](docs/module_factory.md).
for client configs, the 44-tool reference, and troubleshooting.

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

- **Code:** MIT — see [LICENSE](LICENSE). The repo is currently **private**
  (2026-09-22); see [LICENSE-CLAUSE.md](LICENSE-CLAUSE.md) for the 3-tier
  split and the re-publicization plan.
- **Connectome data:** MaleCNS v1.0, CC-BY. The 5.63 GB dataset is **not**
  included in this repository. Obtain it from the original publication and set
  `FLYBRAIN_DATA_DIR`. All numbers in this project are derived from that real
  dataset; nothing is synthetically fabricated to look impressive.

> "Virtual organism" is a **software-layer analogy**: we reuse real topology
> *principles* (motif shapes, recurrence rates, inhibition patterns), not real
> cells. It is not a wet-lab construct and is not claimed to be one.
