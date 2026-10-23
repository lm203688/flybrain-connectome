# flybrain-connectome

[![ci](https://github.com/lm203688/flybrain-connectome/actions/workflows/ci.yml/badge.svg)](https://github.com/lm203688/flybrain-connectome/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#requirements)
[![version](https://img.shields.io/badge/version-3.00.0-orange.svg)](CHANGELOG.md)
[![docker](https://img.shields.io/badge/docker-2.90.0-2496ED.svg)](#docker)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen.svg)](.pre-commit-config.yaml)

**v3.00.0 · 2026-10-23 · 116 functional units · 270 module profiles · 61 gates · EPE 全栈 + AIBOM 供应链披露 + 收据完整性门禁 + Gate 60/61/62/63 + fail-loud 纪律 + 版本单一真源 + Xu 2026 树突计算前沿对照 + E4 区室边界 + S1 外部验证 + S2 lesion cascade + S3 统计强化 + 纪律有效性量化（catch-rate 100%，W1–W7 全部关闭）+ Gate 63 research_claims 顶层统计完整性 + 作者署名规范化（P-3 / P-4 → Li Xing + ORCID）+ bioRxiv 投稿准备包 + flybrain demo 一条命令 + 5 分钟上手**

> ### The 89% problem
>
> Deloitte's 2026 agent-pilot survey found **89% of enterprise agent pilots
> never reach production**. Teradata: 78% have pilots, only 14% scaled. The
> failure pattern repeats across industries in three words:
>
> **"跑不稳、管不住、查不清"** — unstable, ungovernable, unauditable.
>
> `flybrain-connectome` addresses the third word. Every agent edge in a
> generated topology traces back to a real neuron or synapse class in the
> *Drosophila* male brain connectome, serialized as **W3C PROV-JSON** — the
> same format EU AI Act auditors expect. Your agent swarm isn't a black box;
> it's a verifiable structure with biological provenance.
>
> **[5-minute quickstart](docs/QUICKSTART_5MIN.md)** — from zero to an
> interactive D3 topology graph in five minutes, no data download.

> **Auditable Agent Topology — 可审计的 Agent 拓扑生成与溯源**, grounded in
> the real *Drosophila* male-brain connectome (**MaleCNS v1.0** — 166,700
> neurons / 124,177,617 synapses, CC-BY).

`flybrain-connectome` turns a real, published brain wiring diagram into
**task-tailored multi-agent topologies** you can instantiate as agent swarms —
and it can prove, for every edge, *which real neuron / synapse class it came
from*. The motif provenance is serialized as **W3C PROV-JSON**, the same
standard EU AI Act auditors expect.

It is a **developer toolkit and research artifact**, not a trained model and
not a simulation of a fly. Read the [honest boundaries](#honest-boundaries)
before you quote it.

> **Repo status:** **PUBLIC** since 2026-10-18. History was audited and cleaned
> before publicization (see [CHANGELOG v1.3.0](CHANGELOG.md) for the original
> Tier-2 IP leak and [docs/D3_REPOSITORY_PUBLICITY_DECISION_2026-10-18.md](docs/D3_REPOSITORY_PUBLICITY_DECISION_2026-10-18.md)
> for the 16-step publicization runbook that was executed). The Tier-1 code is
> MIT-licensed and reachable at https://github.com/lm203688/flybrain-connectome.
> Tier-2 raw data (MaleCNS 5.63 GB, C. elegans Witvliet 2020, Drosophila larva
> edges.csv, Petkova 2025 zebrafish) is fetched via the documented data pipeline
> — see §"Requirements" and the S1 external-validation script.

---

## What it is / what it is NOT

| ✅ This project | ❌ Not this project |
|---|---|
| A connectome **query service** (47 tools over HTTP + MCP) | A spiking-neuron simulator |
| A **motif-extraction** pipeline (real fly → derived motif doc) | A repository of the raw 5.63 GB data |
| A **synthetic topology generator** (bio-motifs → agent graphs) | A trained / fine-tuned model with weights |
| **W3C PROV** provenance on every generated artifact | A claim that the "virtual organism" is alive |

The killer offline feature: **`generate` needs no data** — it composes
topologies from a 7 KB derived motif snapshot. The connectome data is only
needed if you want to *query* the real brain.

---

## Honest status of the unit library

The 116 functional units are split cleanly by how their evidence comes
together. This is the number to remember when reading any downstream
claim:

| Bucket | Count | Meaning |
|---|---|---|
| Anchored to real *Drosophila* male-brain cells | **37 / 116 (31.9 %)** | `embodiment.real_cells_anchored > 0` — each edge traces to actual MaleCNS v1.0 neurons |
| Cross-species declarations, unanchored | **79 / 116 (68.1 %)** | `provenance.unanchored_reason` = `identity_not_in_drosophila` or `taxon_no_malecns_data` — the circuit exists in the literature for another species, not in the MaleCNS connectome |

The 68.1 % bucket is not a defect and not a hidden error. It is a
**comparative-neuroscience scaffold**: bird song, mammalian cortical
layers, fish Mauthner, cephalopod vertical lobe, Aplysia and leech
CPGs, insect mushroom-body — all are wired into the library with named
references and can be composed like the anchored ones, but they are
**not** measured in a real connectome the way the 37 anchored units
are. Reading the library correctly means reading those two numbers
together, not the 116 by itself.

## How to use this — tiered by what you can actually get today

Rather than a single "this is a X" pitch, the useful things this
project does break down into three tiers. Which one you actually need
depends on what you are building.

**Tier 1 — usable today, offline, no data download.**
Neuron-circuit search across 3 species × 4 axes (`system` / `function` /
`species` / `provenance`); compose a virtual-organism topology from any
subset of units; run the four canonical DEMOs (mammal, insect,
electrosensory, swim) end-to-end. This is the *developer tool* the
project actually is. `flybrain search`, `flybrain compose`, `flybrain
generate` cover it.

**Tier 2 — for people designing AI-agent scaffolds.**
The composed topologies trace back to real circuitry via W3C PROV-JSON,
which means a downstream agent framework (LangGraph / CrewAI / AutoGen
/ SwarmLabs) can pick up a starting topology and audit where each
wiring decision came from. **This is not a general agent infra** — it
is a biology-prior layer you plug into one.

**Tier 3 — what this project explicitly does not do.**
It does not beat biology at anything (Phase 3 measured negative and
is not claimed). It does not replace any EM reconstruction pipeline.
It does not ship a trained model or a spiking simulator. If someone
reads a v1.x changelog entry that promises any of those, the honest
answer is "that was aspirational; the withdrawal is documented in
`docs/PROJECT_REALITY_ASSESSMENT.md`".

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

The toolkit needs one runtime dependency (`numpy`, because the connectome
engine imports it at module level) plus optional extras for provenance and
columnar IO. No other third-party code is required. Pick either setup:

> **Repo status:** **PUBLIC** since 2026-10-18. No authentication required —
> the clone commands below work directly. History was audited and cleaned
> before publicization (see [CHANGELOG v1.3.0](CHANGELOG.md) for the original
> Tier-2 IP leak and [docs/D3_REPOSITORY_PUBLICITY_DECISION_2026-10-18.md](docs/D3_REPOSITORY_PUBLICITY_DECISION_2026-10-18.md)
> for the 16-step publicization runbook).

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
pip install dataprov                     # or: pip install "flybrain-connectome[prov]" (once on PyPI)
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
# -> flybrain-connectome-mcp/generated_organisms/<name>.{json,html} + flybrain-connectome-mcp/swarmlabs/<name>.swarm.{json,yaml}
```

### 5. Read the C. elegans developmental axis

```bash
flybrain stages         # L1 x4 / L2 / L3 / adult x2, measured per animal
flybrain stages --caveat            # why the L1 columns are a floor
flybrain stages --unit cel_amphid_chemosensory_unit
```

### 6. Read the larva connectome cluster ledger

```bash
flybrain larva-clusters             # network totals + per-unit coverage
flybrain larva-clusters --top 20    # the 20 biggest clusters
flybrain larva-clusters --unannotated
flybrain larva-clusters --caveat    # what "covered" does and does not mean
```

### 7. Read the MaleCNS male-dimorphic ledger

```bash
flybrain composition               # can declared combinations actually form?
flybrain costs                      # latency/energy per connection type
flybrain function                   # coverage by FUNCTION, not by species
flybrain function --vision          # only what PROJECT_VISION requires
flybrain dimorphism                 # 2,368 cells nobody has looked at
flybrain dimorphism --provenance    # ... with the curator note behind each sex label
flybrain dimorphism --top 20 --internal
flybrain dimorphism --caveat        # what "male-specific" does not mean here
```

### 8. Verify everything still works

```bash
flybrain verify        # needs FLYBRAIN_DATA_DIR set to your data
```

### 9. Profile a topology (offline, no data)

The topology-aware layer turns "what shape is this organism?" into a callable,
reproducible answer — density, degree spread, reciprocity, modularity Q,
transitivity, spectral radius (power iteration, no numpy), feedback-edge
fraction, a directed 3-node motif census, and a deterministic structural
signature. It is honest by construction: `not_measured` names what a
*structural* profile cannot speak to (dynamics, energy, task performance).

```bash
flybrain generate --blueprint predictive_coding_v2 --modules 5 --agents-per-module 6 --name demo
flybrain profile generated_organisms/demo.json
flybrain profile generated_organisms/demo.json --json          # full profile
flybrain profile generated_organisms/demo.json --compare generated_organisms/other.json
```

Self-validated by **Gate 15** (`scripts/check_topology_profile.py`).

---

## Repository layout

```
flybrain-connectome/
├── flybrain_cli.py                 ★ developer CLI (serve/query/motifs/generate/verify/info)
├── pyproject.toml                  zero deps, `flybrain` console script
├── LICENSE · CITATION.cff · CHANGELOG.md
├── flybrain-connectome-mcp/
│   ├── mcp_connectome/             query engine (core) + 47-tool MCP + HTTP API (:8799)
│   ├── motifs/                     drop-in client + derived motif snapshot
│   ├── synthetic_bio_topology.py   ★ C1 generator (motif → agent graph + config + PROV)
│   ├── _verify.py                  end-to-end smoke test (70/70)
│   └── flybrain-connectome-mcp/
│       ├── generated_organisms/     example artifacts (json/html + swarm configs)
│       └── swarmlabs/               swarm config exports
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
| `GET  /tools`  | key  | list the 47 tools + descriptions |
| `POST /query`  | key  | `{"tool": <name>, "args": {...}}` → `{"ok": true, "result": ...}` |

**Auth:** `Authorization: Bearer <key>` or `X-API-Key: <key>`. Keys come from
`config.json` (`api_keys`) or env `FLYBRAIN_API_KEY`. If none is configured the
server generates a temporary per-boot key and warns loudly — it never falls
back to a key committed to source.

**The 47 tools** (real names, do not invent — verified against `GET /tools`
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
`list_combination_rules` · `validate_combination` · `expand_organism` · `get_multiplier_metrics` · `profile_topology` · `profile_health`

*Functional-unit composition library — the composable layer above neuron types:*

`list_functional_units` · `get_functional_unit` ·
`list_connection_types` · `list_evidence_ledger` · `compose_from_units`

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

**25 blueprints** across three categories, composed from **270 modules**:
**10 cognitive-function modules** (sensory / memory / motor / integration / attention /
working_memory / reward / punishment / habit / metacognition) + **190 cross-species
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

+ **a second non-cortical batch: rhythm, state and error** (24 further types, v1.6.0):

- **segmental / peripheral oscillators (9)** — leech swim-CPG interneuron and body-wall
  motor neuron with its mechanosensory T cell, ascidian larval motor neuron and ocellus
  photoreceptor, Aplysia sensory / motor / serotonergic facilitating neurons, buccal
  ganglion CPG neuron
- **infrared and amphibian (5)** — trigeminal infrared afferent, infrared tectal map
  neuron, multimodal optic-tectum neuron, tectal T5-type prey detector, tongue motor neuron
- **error teaching and state (6)** — climbing fibre, cerebellar Golgi cell, vestibular
  nucleus neuron, pre-Bötzinger complex neuron, phrenic motor neuron, VLPO neuron
- **navigation and active sensing (4)** — head-direction cell, place cell, barrel cortex
  neuron, whisker motor neuron

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

- **116 functional units** — each is ONE function (phototransduction, action
  selection, theta pacing, gliotransmission, sparse mushroom-body coding, ring-attractor
  heading, song timing, Mauthner escape, active electrolocation, camouflage, leech swim
  rhythm, infrared thermal imaging, climbing-fibre error teaching, sleep/wake switching …)
  delivered by a **group** of neuron populations (1–6 of them, taken from the 254-module
  vocabulary) wired into an internal sub-circuit, and exposing **typed ports** (`light`
  in → `high_res` out; `candidates` + `value` in → `selected_action` out).
  Composition: 40 mammal-cortex-shaped + **16 cross-clade** (insect / bird / fish /
  cephalopod, v1.4.1) + **16 rhythm/state/error and active-sensing** (annelid, ascidian,
  mollusc, pit viper, frog, cerebellum, brainstem, hippocampus, barrel cortex, v1.6.0)
  + **10 Drosophila-shaped** (optic lobe, giant-fiber escape, male courtship & song,
  lateral horn, v1.8.0 — every one of them fully anchored, see below).
  + **5 Drosophila-shaped** (thermal preference, feeding circuit, leg motor, multimodal LAL, sleep memory, v1.10.0 — first batch anchored, see below).
  + **4 C. elegans connectome-derived** (forward locomotion command, touch-avoidance
  reflex, amphid chemosensory, nociceptive avoidance — v2.27.0, see below; each also
  carries a **L1 → L2 → L3 → adult** axis, v2.30.0).
  + **8 Drosophila larva connectome-derived** (`larv_olfactory_associative_learning_unit`,
  `larv_somatosensory_escape_unit`, `larv_gustatory_feeding_program_unit`,
  `larv_descending_motor_command_unit`, `larv_mushroom_body_feedback_unit` — v2.28.0,
  third connectome — plus `larv_thermosensory_relay_unit`, `larv_visual_relay_unit`,
  `larv_respiratory_relay_unit` — v2.29.0, one unit per traced sensory channel,
  see below).
- **66 connection types** — each is one connection FORM, constrained on the port
  types it may join, in six families:
  **micro** (axo-dendritic / axo-somatic / axo-axonic / dendro-dendritic …
  point-to-point contact sites) · **circuit** (feedforward / feedback / lateral /
  mutual / recurrent / disinhibition / winner-take-all / global inhibitory gain control /
  synfire chain / efference-copy cancellation / half-centre oscillation / grid phase
  precession …) · **modulatory**
  (diffuse / volume / retrograde / state gating) · **electrical** (gap junction /
  ephaptic / mixed electro-chemical / tripartite astrocyte / plateau-potential
  bistability) · **plasticity** (STDP / LTP-LTD / short-term / homeostatic scaling /
  modulator-gated / repeated-activation LTS / serotonergic presynaptic facilitation /
  short-term habituation / coincidence detection) ·
  **macro** (topographic mapping / divergent fan-out / convergent fan-in / corollary
  discharge / global broadcast / sparse expansion / command-neuron recruitment /
  bistable state switch / thermal cross-modal convergence).

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

Four canonical chains ship as fixtures and are re-validated by Gate 9 on every
run — `--demo mammal` (retina → thalamus → cortex → basal ganglia → motor
thalamus), `--demo insect` (antennal lobe → mushroom body sparse code → learned
valence → central complex heading/steering, clock-biased),
`--demo electrosensory` (EOD pacemaker → efference-copy cancellation →
electrolocation, plus a passive-electric cue into the Mauthner escape command)
and `--demo swim` (leech half-centre swim CPG → ascidian larval oscillator →
frog reticulospinal escape swim).
`--demo` with no argument runs all four.

### Developmental axis (v2.30.0) — the same four circuits at L1 / L2 / L3 / adult

The Witvliet 2020 series is **eight** reconstructions, not two: four L1 animals,
one L2, one L3 and two adults. The library used to carry only the two adults.
All eight are now loaded and measured per animal. Each of the four C. elegans
units above carries the result in `provenance.developmental_stages`; run
`flybrain stages` to print it.

| stage | dataset | cell classes | unique edges | synapses |
|---|---|---|---|---|
| L1 | 1 | 108 | 566 | 1,400 |
| L1 | 2 | 114 | 693 | 2,028 |
| L1 | 3 | 119 | 700 | 2,237 |
| L1 | 4 | 122 | 795 | 3,020 |
| L2 | 5 | 128 | 1,107 | 4,535 |
| L3 | 6 | 132 | 1,072 | 4,723 |
| adult | 7 | 135 | 1,565 | 7,867 |
| adult | 8 | 134 | 1,530 | 8,400 |

The four circuits, measured at every stage (synapses per animal):

| unit | L1 | L2 | L3 | adult |
|---|---|---|---|---|
| forward locomotion command | 26 / 34 / 41 / 66 | 92 | 87 | 125 / 179 |
| touch-avoidance reflex | 30 / 38 / 43 / 72 | 111 | 107 | 159 / 210 |
| amphid chemosensory | 97 / 127 / 150 / 199 | 301 | 267 | 433 / 495 |
| nociceptive avoidance | 21 / 22 / 31 / 64 | 76 | 69 | 110 / 144 |

**Those four rows do not add up (v2.34.0).** The circuits are not disjoint
cell-class sets — `AIA` sits in all four, `AIB`/`AIZ`/`AVB`/`PV` in two or three
— so an edge like `AIZ → AIB` is internal wiring for two circuits at once and
gets counted by both. Adding the column overstates the wiring that is actually
internal to these circuits by ~1.27×. Both figures are now reported per stage:

| stage | sum of the four circuits | union (counted once) | inflation |
|---|---|---|---|
| L1 | 1,061 | 849 | 1.25× |
| L2 | 580 | 455 | 1.27× |
| L3 | 530 | 421 | 1.26× |
| adult | 1,855 | 1,456 | 1.27× |

Use **union** for "how much of this animal's wiring sits inside these
circuits"; use the sum only when the circuits are counted individually. The
extractor now asserts that the per-circuit rows reconstruct the sum, and refuses
to write when they disagree.

**One circuit is measured wider than the unit it attaches to (v2.35.0).**
`PROFILES` declares 11 cell classes for the touch-avoidance circuit, `PLM`
among them, but `extract_cel_profiles.py` only emits a member profile for a
declared class that actually has an edge inside the module — and in the adult
reconstruction `PLM` has none, so the v2.27 unit ships **10** members and
`cel.plm` does not exist anywhere in this library. Merged across all eight
reconstructions `PLM` *does* have edges, so this series measures **11**. Both
are correct; the unit name is identical, which is exactly why the gap had no
name and no guard. The artifact now records it as `declared_vs_shipped` and
the extractor refuses to write if a unit ever ships a class the series cannot
measure. Practical consequence: compare the touch-avoidance stage numbers
against the unit by that one class, not directly.

Across all 16 measurements the four circuits are **present in every animal at
every stage** (6–37 edges at L1), so what development adds is synapse weight,
not new topology.

**The boundary that matters here.** A side result — 271 edge pairs appear in L1
and not in the adults — is **not** reported as transient developing synapses. A
single L1 file carries 566–795 distinct edges against 1,107 for a single L2
file, so "seen at L1" is confounded with reconstruction depth. Only the claim
that survives that confound is published; the `caveat` field of
`cel_development_stages.json` states this in the artifact itself. As of
v2.34.0 that 271 is **computed** (`stage_diffs.l1_only_keys`, alongside
`l1_union_keys` 1,188, `adult_union_keys` 1,980, `shared_keys` 917,
`adult_only_keys` 1,063) rather than written into the caveat as a literal that
could not be re-derived if the source changed.

### Larva cluster ledger (v2.31.0) — how much of the larva network the units cover

The eight larva units were built by aggregating nodes on
`(cell_type, annotations)`. That left one question unanswered: *how much of the
352,611-synapse larva network do they actually span?* `flybrain
larva-clusters` answers it by walking all 116,922 edges.

A synapse counts as **covered** only when **both** endpoints' `(cell_type,
modality bucket)` resolve to a `larv.*` profile that at least one unit declares
as a member. A synapse is **frontier** when neither endpoint does.

| measure | synapses | share |
|---|---|---|
| both endpoints traceable | 271,956 | **77.13%** |
| frontier (no unit declares either endpoint) | 12,415 | **3.52%** |

Per unit, at both-endpoint resolution:

| unit | synapses | share | cells reached |
|---|---|---|---|
| olfactory associative learning | 80,161 | 22.73% | 548 |
| mushroom body feedback | 74,960 | 21.26% | 530 |
| somatosensory escape | 57,262 | 16.24% | 942 |
| descending motor command | 53,824 | 15.26% | 910 |
| thermosensory relay | 22,981 | 6.52% | 361 |
| visual relay | 20,712 | 5.87% | 358 |
| gustatory feeding program | 6,428 | 1.82% | 525 |
| respiratory relay | 2,736 | 0.78% | 275 |

Three cell classes sit entirely outside every unit: the unlabelled class
(346 cells), `MB-FFN` and `pre-DN-SEZ`.

**`_unannotated` in a profile id does not mean "unannotated" (v2.36.0).** 15 of
the 43 profile classes carry that suffix, and it is `bucket()`'s
*modality-recognition* fallback, not an annotation verdict: a cell whose
`annotations` string is literally `KC` contains no modality keyword, so it
lands in the fallback bucket while being fully named. **13 of those 15 classes
hold annotated cells — 1,686 of them**, including `larv.kc_unannotated` (144
cells, all annotated `KC`), `larv.mb_fbn_unannotated` (100, all annotated like
`CN-10; FAN-2`) and `larv.mb_ffn_unannotated` (54, all `FFN-23` and
siblings). The earlier line in this README that read the frontier list as an
annotation verdict was wrong on exactly this point: `MB-FFN`'s 54 cells all
carry names.

The network-wide figure is unaffected — **1,560 cells (52.77%) genuinely have
no official annotation**, because it reads the `annotations` column directly
and never touches the bucket. What was wrong was the reading of the *names*.
The ids are unchanged (40 profile keys, gate 9 and every published artifact
index them by name); the two notions are now measured apart in
`annotation_identity` and carried on each unit as `member_id_caveat`.

**The per-unit rows are not additive either (v2.34.0).** Nineteen `larv.*`
profiles are declared by more than one unit — `larv.lhn_unannotated`,
`larv.lhn_mechano`, `larv.kc_unannotated` and friends — so one synapse
legitimately counts toward each of them. The eight rows sum to **319,064**
against a covered total of **271,956** (1.17×). Use the union figure for network
coverage and the per-unit rows only to compare units with one another; the
shared-profile list is in `unit_attribution` and `flybrain larva-clusters
--caveat` prints it. The extractor asserts that the sum can only exceed the
covered total, that the coverage partition closes, and that per-cluster
`internal + out` reconstructs the network.

**The headcount was the wrong measure.** The larva network has 1,560 cells with
no official annotation — 52.77% of its neurons, and the number that made the
network look mostly uncharacterised. They touch 212,542 synapses, 60.28% of the
total, because the units *do* declare the unannotated populations as filler
roles. Coverage and characterisation are different things, and the ledger holds
them apart on purpose: a unit can span three quarters of the larva synapses
while its unannotated members still have no known function. Cluster 0 — the
authors' unassigned bucket, 364 cells — is the single largest holder of
synapses in the whole network (51,211) and is *not* given a function here.

### Male dimorphic ledger (v2.32.0, audited v2.33.0) — 2,368 cells inside the male connectome

MaleCNS v1.0 is a *male* reconstruction, and its annotation table carries a
`dimorphism` column. Nobody in this library had ever read it: the 58 anchored
profiles were built from `superclass` / `type`, and `type` is not sex-aware.
`flybrain dimorphism` streams all 151,856,684 weight rows and asks, for every
edge, whether at least one endpoint is one of the 2,368 bodies the column
flags.

| quantity | value |
|---|---|
| bodies / cell types | **2,368 / 479** |
| edges touching the population | 5,875,648 pairs — **22.97%** |
| synapses touching the population | 13,376,848 — **10.77%** |
| edges with *both* endpoints dimorphic | 284,982 pairs — **1.11%** |
| synapses with both endpoints dimorphic | 1,589,267 — **1.28%** |

**The gap between those last two rows is the finding.** The male population is
not an island: it is a thin, widely-connected subset that mostly talks to
universal cells, and only about one in nine of the synapses it touches sits
*between* two of its own cells. A "male circuit" declared on these numbers
would have to be the 1.28% — which is smaller than the measurement noise of
the surrounding network. So no circuit is declared: FUNCTIONAL_UNITS stays at
115, and 29 units carry the population's distance in
`provenance.male_dimorphic`.

The heaviest type is `TmY21` (372 bodies, 732,527 synapses, 0.590% of the
network). The heaviest both-ends pair is `TmY21 → LoVP92` (442 edges / 2,721
synapses), then `AN09B017b → mAL_m1`, then `pC1_2a → mAL_m8`.

**How big is "big" here (v2.33.0).** v2.32.0 quoted those totals with nothing to
compare them against, which is how `oviIN`'s two bodies / 196,360 synapses came
to look like an error — it is 10× the "1k–10k per neuron" folk rule. It is not
an error. The per-body distribution in this connectome is heavy-tailed:

| per-body synapses (annotated bodies) | median | p90 | p99 | p99.9 | max |
|---|---|---|---|---|---|
| 191,696 bodies with synapses | 1,164 | 4,636 | 19,816 | 48,496 | 271,220 |

So `oviIN` sits at the **99.98th percentile** — the top of a long tail, not an
outlier — while `TmY21`, the heaviest type by total, sits at only the **72nd
percentile** per body. Cell count and per-cell strength are different things and
the ledger now carries both.

**Three things the type names will not tell you (v2.33.0).** First, the
annotation table carries **three independent type axes** — `type` (MaleCNS,
11,751 classes), `flywireType` (8,199) and `hemibrainType` (4,495) — and
`type` disagrees with `flywireType` on **33.08%** of bodies. `TmY21` in this
ledger is the class FlyWire calls **`Tm36`**; the alias travels with every top
type. All 5,413 anchored type names were checked to sit on the `type` axis, and
the script refuses to write if that ever stops being true. Second, each type now
carries the curator's own `matchingNotes` sentence behind the sex label
(`oviIN`: *"more extensive dendrites in male"*) plus its trace grade — **150 of
479** types have such a note and **327** are only `Roughly traced`. Third, the
per-type totals are now checked on every run: each pair is charged once per
dimorphic endpoint, so they must sum to touching + both-ends
(14,966,115), and the extractor refuses to write if they do not. They did not
in v2.32.0 — internal pairs were counted four times, which inflated every
per-type figure by 3× the internal total.

**What this ledger cannot say.** MaleCNS contains no female reconstruction, so
a `dimorphism` label is the curator's annotation, not a comparison made here.
Nothing in it supports "larger in males", and the artifact says so in its own
`caveat` field. Two counters are also kept separate on purpose: **194** dimorphic
types are *listed* in an anchored profile's own type list (someone looked at
them), while all **479** sit inside some anchored `^XXX` family rule — family
membership is not tracing.

### Connection cost axis (v2.38.0) — what each connection costs, and what we cannot say

`PROJECT_VISION.md` claims the generator can optimise *any* goal against the
biological library as prior. Phase 3 tested that and found the optimiser could
only win on structure (−84% wire cost) while the headline computation claim
measured **negative, 0/7 topologies beating random**.

The cause was in the vocabulary rather than in the optimiser. The 66 connection
types carried `delay_class` with three symbolic values — `immediate` / `short` /
`long` — and a `parameters` block with no units. With latency a category and
energy absent, the only axis left to trade was structure. `flybrain costs` adds
the numbers where a citation exists, and `unknown` where one does not.

| basis | latency | source |
|---|---|---|
| chemical synapse | **0.5–4 ms** | Guyton & Hall 2008 p.570 gives 0.5 ms as the minimum; 0.5–4 ms typical |
| electrical synapse | **0.05–0.2 ms** | quoted under 0.2 ms, often called instantaneous |
| volume transmission | 10–1000 ms | diffusion cloud; the spread *is* the mechanism |
| retrograde messenger | 1–60 ms | slower than forward release, faster than volume spread |
| circuit motif / macro geometry / plasticity rule | **none — `unknown`** | not a contact; a pattern whose cost is emergent |

**16 of 66 types carry a latency; 50 do not, and that split is the finding.**
Every type with a number is an actual contact site (micro 9/10, electrical 3/7,
modulatory 4/6). All 20 circuit motifs, 13 macro geometries and 10 plasticity
rules have none, because a single-contact delay is not a defined quantity for a
pattern — compose the members' delays and the motif's cost follows. **Energy is
present for all 66**, because energy composes over a motif while latency does
not. That asymmetry is the design.

**21 types carry no latency by rule.** They are flagged `abstraction_only` — a
winner-take-all or a half-centre oscillator is a design pattern, not a
biological contact, and an autapse is chemically a chemical synapse but as a
*design pattern* has no delay literature can supply. Their `delay_class` is
kept under `designed_cost` so an assumption is never summed with a measurement.
Latency is a **range, not a point**: the spread is the trade, since choosing a
fast synapse trades against reliability.

**Does the axis actually steer an optimiser? (v2.39.0)** Data nobody optimises
over is decoration, so `cost_aware_optimization_experiment.py` runs the same GA
twice — same space, same budget, same evaluation seed — changing only the
objective, and asks whether the latency penalty actually lowers latency.

**At unit granularity it cannot be tested, and that is a measured fact:** only
**14 of 115 units** have every connection type on the latency axis. The other 101
carry unknown-latency types with a **median unknown share of 100%**, so a
5–6 unit organism almost always contains one and has no latency figure at all.

**At connection-type granularity it works.** With a fixed 6-edge budget:

| | struct_only | cost_aware |
|---|---|---|
| edges | 6.00 | **6.00** (unchanged) |
| latency | 1536.62 ms | **16.40 ms (−98.9%)** |
| energy | 0.414 | **0.383 (−7.4%)** |

A 99% latency cut bought with **no extra wire and less energy** — a Pareto
improvement, because the fast types (electrical, 0.05–0.2 ms) are also the cheap
ones. Across four parameter settings: k=6 gives −98.9% twice identically, k=8
gives −51.2%, and **k=10 gives +73% — the axis stops working**, because 16
latency-bearing types cannot fill a 10-type candidate from the fast end. The
capacity boundary is in the artifact rather than averaged away.

Three measurement holes were found by the optimiser, all of them mine:
treating `unknown` as 0 ms (so the cheapest way to win was to select what cannot
be measured — reported as a bogus −99.9%); charging it the slowest latency
instead (GA learned to *add* unmeasured types, and latency rose 16–19% across
three runs); and a floating candidate size (GA shrank every candidate to one
type and reported a 99.9% win by deleting the topology). The fix in all three is
the same: an unmeasured type is **incomparable**, not cheap and not expensive,
so topologies containing one are left out of the latency ranking, and the
candidate size is asserted rather than assumed.

**GATE 12** enforces this. It fails when a design abstraction gains a latency,
when a range is malformed, when the fastest electrical is not strictly faster
than the slowest chemical (the trade the axis exists to express), when a graded
value cites nothing, or when any type loses its energy entry.

### Function axis (v2.37.0) — coverage by function, not by species

The library is organised by taxon. Its 116 units carry 48 distinct `system`
values and 60+ distinct `function` values, and their names are anatomical:
`cortical_`, `retinal_`, `larv_`, `cel_`, `frog_`, `birdsong_`. That is a
catalogue of species circuits, not a function library, and `PROJECT_VISION.md`
asks for the second kind — it names the set the generator grows toward.

`flybrain function` measures the distance. Every unit is tagged with the
function categories its **own** `capability` / `task_hint_pool` fields declare;
nothing is inferred from description prose, and no unit is added, renamed or
reclassified.

Of the 15 categories PROJECT_VISION requires:

| status | categories |
|---|---|
| **missing** | **none** (v2.41.0 closed the last one, `metacognition`; v2.42.0 closed the two non-vision ones, `homeostasis` and `neuromodulation`) |
| thin (<3 units) | `attention` (2) · `habit` (1) · `metacognition` (1) · `punishment` (1) · `working_memory` (1) · `motor_command` (2) · `motor_relay` (1) |
| covered | `integration` (4) · `prediction` (6) · `reward` (5) · `associative_learn` (9, 4 taxa) · `memory_encode` (11) · `memory_readout` (5) · `sensory_relay` (16) · `sensory_transduction` (6) |

**The honest measure is taxon breadth, and it is the library's biggest gap.**
`covered` counts units, so a category carried by a single species reads as
covered. Splitting it by how many taxa actually carry each required category:

> **Only 1 of the 15 required categories — `associative_learn` — spans 3 or more
> taxa. The other 14 are single-taxon implementations.**

GATE 11 derives that split from the matrix and fails if it is hand-written or
silently improves. The library can generate 115 circuits; it cannot yet
generalise a function across species, which is what a morphology generator
needs. Closing it means new units with real evidence — roughly 14 more, each
with literature verification, a JEV run and a profile registration.

### Metacognition, the last missing category (v2.41.0)

A sweep of all 116 units for `confidence`, `uncertainty`, `metacognit`,
`precision` and `attentional` in their name, function and description returned
**nothing** — the gap was real, and the 48 untagged units could not fill it
(their capabilities are mechanism verbs like `oscillate` and `reflex`). So it
needed a unit: `prefrontal_metacognitive_unit`, with six profiles.

The literature separates two networks rather than one "confidence centre":
dACC and insula carry objective uncertainty and correlate **negatively** with
reported confidence; VMPFC and pgACC carry the subjective sense and correlate
**positively**; and the lateral frontal pole maps a private estimate onto a
public report — a stage separable from confidence itself. JEV returned
**PARTIAL** (lit 0.76, model 0.56, score 4): well documented, not
computationally validated. Two fail-closed gates fired on the way in (no JEV
verdict, then members not in `MODULE_PROFILES`) and neither was bypassed.

**The honest summary of this axis: only 2 of 24 categories are carried by three
or more taxa** (`associative_learn`, `credit_assign`), and 41 of 116 units
belong to no category at all. Cross-taxon coverage is this library's weakest
dimension, and that is now a number rather than an impression. A tag means the
unit declares a mechanism implementing the category — it is a coverage label,
not a claim that the unit performs the function well.

### Keyword repair and match evidence (v2.42.0) — the matrix had to be believed

v2.42.0 caught two categories reporting **0 units** while the library already
declared them. `homeostasis`' keyword list was `homeostasis`,
`thermoregulation`, `circadian_rhythm`, `fluid_balance` — and the library writes
that concept as `circadian_pace`, `oscillate_circadian`, `circadian_track`,
`sleep_wake`, `metabolic_support`. Same story for `neuromodulation`, whose six
tokens matched nothing while twelve units declared it as `modulate`,
`modulation`, `peptide_release`, `calcium_wave`. Both read `missing`, so the
work queue said "build these" when the library already had them.

The fix was to add the library's actual words, not to loosen the matcher. Two
candidate tokens were **rejected after probing every capability string**, and
the rejections are recorded in `function_coverage.json` so they stay visible:

| token | would have gone to | why it was refused |
|---|---|---|
| `rhythm_generate` | homeostasis | matches every CP and pattern generator (`spinal_cpg_unit`, `respiratory_rhythm_cpg_unit`, `courtship_song_pattern_unit` …) — rhythm *generation*, a motor output, not keeping an internal variable in range |
| `broadcast` | neuromodulation | `value_broadcast` and `arousal_broadcast` are command broadcasts, not a diffusible signal changing the gain of many targets — the substring trap reappearing as a whole token |

Each tag now carries its firing token: `match_evidence[unit] = ["cap <- token", …]`.
GATE 11 re-derives all **213 pairs** from the units' own `capability` /
`task_hint_pool` fields and refuses to write any tag it cannot reproduce. A
fault-injection test that gave `spinal_cpg_unit` a fabricated
`rhythm_generate <- circadian` evidence entry made the gate fail with
`the tag was not earned`. That is the difference between a coverage matrix and
a coincidence report — the matrix had overstated itself three times before this
gate existed.

### Composition semantics (v2.40.0) — can the library be assembled?

`composable_with` decides which units may be wired together, and until
v2.40.0 nothing checked it. Gates 1–12 verified units are well formed, that
function coverage is measured, that latencies are cited — none of them asked
whether a declared combination can actually form.

Of **163** declarations across 115 units:

| state | count |
|---|---|
| reciprocal **and** port types meet | **28** |
| one-way, but the ports would meet | **38** |
| **declared while no port type can meet** | **97** |

**Usable combinations: 23 mutual pairs plus 28 one-way-but-reachable.** For
example `amygdala_fear_unit` exposes `out: limbic.fear` while
`hypothalamic_arousal_unit` accepts only `arousal.state` / `rhythm.circadian` —
no overlap, so that composition cannot be built.

**Fixed in v2.41.0.** The builder no longer takes a declaration at face
value: `suggest_composition` now emits an edge only when the other unit declared
it back **or** the port types actually meet, and records everything it dropped
in `skipped_edges` with the reason — so a discarded composition is visible
rather than silent. `strict=False` restores the old behaviour. On the `memory`
query: strict keeps 2 edges and drops 1 with
`reason: ports_cannot_meet_and_not_reciprocated`; legacy kept 3.

GATE 13 enforces it **behaviourally**, not by grepping source: it calls
`suggest_composition` and checks that strict never returns more edges than
legacy and that nothing appears in both the kept and skipped lists.

What *is* clean: `internal_wiring` has **0 dangling role references**, and
**115/115 units expose both an input and an output port**.

The gate also had to survive bad data: its first version crashed on a
`composable_with` entry naming a unit that does not exist, and a gate that dies
on one bad reference cannot report the rest. With that fixed, injecting both a
dangling role reference and a dangling target reports **both** and exits 1.

**GATE 11 keeps it honest.** It is the first gate that asks whether the library
covers what the vision requires. It does not fail for having gaps — the gap
list *is* the work queue. It fails when a gap becomes invisible: the summary
disagrees with the matrix, a category names a unit the library does not have,
tagged + untagged stops equalling the library size, or a `cross_species` claim
contradicts its own count.

### MaleCNS embodiment (v1.7.0, densified v1.8.0)

Everything above is literature-curated, which left the library unable to answer
the first question any reader asks: does any of this correspond to the fly brain
it is named after? `functional_units/malecns_anchors.json` (built by
`scripts/build_malecns_anchors.py`) answers it, for the part where an answer is
honest.

- **Presence.** **37 of 116 units** have member populations that resolve to real
  annotated MaleCNS v1.0 cell types. Across the whole library that is
  **58 of 204 neuron populations** covering **107,558 real cells**: the `kc` role of
  the mushroom-body unit is 4,064 real Kenyon cells over 15 real KC types
  (`KCg-m`, `KCab-m`, `KCa'b'-ap2` …), its `input` role is 583 real antennal-lobe
  projection neurons over 145 types (`DA1_lPN`, `VM5d_adPN` …), its `gaba` role is
  the 2 real APL cells. Matching is by an explicit name rule **plus** the
  dataset's own `superclass` — a name rule alone would have swallowed the clock
  neurons `DN1a`/`DN1pA` and the endocrine `DNES1-3` into the descending-neuron
  anchor — and the complete match list is written into the artifact, so a wrong
  rule is auditable by reading JSON rather than by trusting a script.
- **Measured structure instead of assumed structure.** A single pass over the
  real synapse table produces the complete 27×27 superclass matrix and the
  anchored-cell-type matrix, independently cross-checked against
  `connectivity_stats.json`: both agree on **124,177,617** synapses over
  25,582,938 edges. Each declared unit edge therefore carries the real measured
  synapse count between its two populations' actual cell types — antennal-lobe
  PN → Kenyon cell measures 378,315 synapses over 21,658 connected type pairs,
  Kenyon cell → mushroom-body output neuron measures 463,640, Kenyon cell → APL
  measures 210,352 — and in v1.8.0 the ten new Drosophila-shaped units went
  through the same test before their wiring was written: T4/T5 → lobula-plate
  tangential cell measures 296,217, medulla intrinsic → T4/T5 measures
  1,924,544, PN → lateral horn measures 391,155, giant fiber → TTMn measures
  the famous 90 (over the real mixed electrical-chemical synapse), pC1 → pIP
  measures 1,973, AMMC → pIP measures 90.
- **Support tier at type-pair resolution (v2.2.0).** The profile-level count is
  still the contradiction gate, but it is no longer the whole verdict: every
  declared edge is additionally walked across the **5,413×5,413 anchored
  type-pair matrix**, counting how many individual `(from_type, to_type)` pairs
  carry real synapses. That separates a pathway spread over many cell types from
  a profile-level non-zero carried by one lucky pair, and it surfaced **six
  FRAGILE edges** that the cell-type-set verdict had treated as fine: `giant_fiber_escape_unit`
  `GF → TTMn` (4 pairs, 1 live: `DNp01 → TTMn` = 90) and `GF → PSI` (1 pair:
  `DNp01 → PSI` = 16); `auditory_song_reception_unit` `AMMC → aSP` (240 pairs, 1
  live: `AMMC012 → aSP10A_b` = 19); `cb_efferent_command_unit` `PN → CB-efferent`
  (145 pairs, 1 live: `VP2+Z_lvPN → GNG656` = 2); and both edges of
  `buccal_efferent_feedback_unit` (`LN-DN2 → DNg28` = 16, `DNg28 → PhG3` = 3).
  **109 edges are SUPPORTED** (≥2 live pairs), **6 FRAGILE** (exactly 1),
  **1 CONTRADICTED**. FRAGILE is a *new honesty tier*, not a new contradiction —
  those edges do have measured support, they just should not be cited as strong
  evidence, and Gate 10 re-derives every tier from the raw matrix so a hand-written
  tier cannot survive.
- **Falsification, not confirmation.** A nonzero count means only that the
  declared edge is *not contradicted* at cell-type-set resolution; it says nothing
  about whether the declared connection FORM is the one the fly uses. A zero count
  is a real contradiction, and the library has exactly one:
  `central_complex_steering_unit`'s `nod -> fb` projection, which this release's
  Nod population (5 types, 12 cells, filed by the dataset under
  `visual_projection`) does not exhibit. It is kept and flagged **UNSUPPORTED**
  rather than quietly rewritten to something that passes — Gate 10 fails on any
  contradiction that is not registered in `ACKNOWLEDGED_CONTRADICTIONS` with a
  reason.
- **The other 146 populations are unanchored with a stated reason**, not silently
  skipped: 131 are non-Drosophila (bird song system, fish Mauthner and
  electroreception, cephalopod vertical lobe, mammalian cortical classes), 5 could
  not be resolved narrowly enough to defend, and 10 are abstract cognitive modules
  with no single cell class. Every unanchored **unit** now also carries a
  machine-checkable `provenance.unanchored_reason` from a three-value enum
  (`taxon_no_malecns_data` / `identity_not_in_drosophila` /
  `abstract_module_no_cell_type`), derived from the profile classification rather
  than asserted by hand, so a reader never has to guess why a unit has no anchor:
  all **66** currently fall under `identity_not_in_drosophila` — 58 of them
  reference only non-Drosophila cell classes, and 8 mix those with the 5
  profiles too broad to resolve (`interneuron_kcn`, `interneuron_lamp`,
  `interneuron_npf`, `interneuron_nph`, `olfactory_receptor`). No unanchored
  unit's members are all abstract modules or all in-species-without-data, which
  is why the other two enum values are present but currently unpopulated — Gate 10
  proves each unit's reason is what the classification would derive, so a
  hand-typed reason cannot survive.

**Honest boundary.** These units are curated from comparative-neuroscience
literature with a named reference each (`provenance.extracted_from_malecns` is
`false` for all 97) — they are NOT extracted from MaleCNS v1.0, unlike the three
original fly motifs. Member ratios are composition weights, not measured cell
counts. `provenance.embodied_in_malecns` marks the 31 units whose populations *do*
resolve to real annotated cells. Embodiment proves the parts exist and that a
declared edge is not contradicted; it does not prove the declared microcircuit or
its connection form. Treat the layer as a composable scaffold with literature
provenance, not as a measured cell assembly.

Machine-readable equivalents: `list_functional_units`, `get_functional_unit`,
`list_connection_types`, `compose_from_units`. Regenerate + verify with
`python scripts/gen_functional_units.py` and `scripts/check_functional_units.py`
(Gate 9, which fails the build if the artifacts drift from the generator, if a
member neuron does not exist in the vocabulary, or if the composer stops
rejecting malformed wiring). The embodiment layer is rebuilt with
`python scripts/build_malecns_anchors.py` and locked by `scripts/check_embodiment.py`
(Gate 10, which recomputes every measured count from the matrices, re-derives every
support tier from the raw type-pair matrix, re-injects nine defects every run, and
refuses to let an unacknowledged contradiction or a hand-typed reason ship).

---

## Science & paper

The methodology, the four moats, the six falsified mechanisms, and the two
negative results are written up in **[`docs/arxiv_paper.md`](docs/arxiv_paper.md)**
(preprint-ready).

### Research self-verification discipline (S6–S9)

This project follows four scientific self-verification disciplines that are
uncommon in open-source tooling but essential for research integrity:

- **S6 · Control group scoreability** — every control experiment must verify
  that the control arm has scoreable samples in *every* task category. If a
  category is structurally unscoreable for the control arm, it must be excluded
  or reported separately. (Caught a false +33.4pp result in P1.)

- **S7 · Resolution pre-check** — before starting a scan experiment, verify
  that the target resolution matches the parameter-space geometric limit
  (`clamp_density = n_nodes / (n * (n-1))`). (Caught a silent clamp in R2.)

- **S8 · Mechanism falsification as output** — when a mechanism hypothesis is
  falsified, the result must include a structured `falsified_mechanisms` list
  (mechanism, hypothesis, test, result, verdict). Six mechanisms have been
  tested and falsified (P1 feature addition, P2 task alignment, P3 edge
  density, P1 correction, R3 monotonic gain, H-A critical edge sparsity).

- **S9 · Perturbation analysis over correlation** — when correlation R² < 0.05,
  perturbation data must exist and contain boundary signals. Correlation alone
  is insufficient for mechanism claims.

These disciplines are enforced by **Gate 30** (`scripts/check_llm_orchestrator.py`),
which independently recomputes claim metadata from experiment data and refuses
to let an unverified claim pass.

### Reproducible negative results

The project maintains a public `research_claims.json` with six claims (R1–R6),
each containing: statement, quantitative prediction, falsification condition,
reproduction command, sample size, random seed, boundary statement, and
falsified mechanisms. Current status: 1 supported after metric fix, 3 complete,
2 at boundary (partial-falsification and anchor-gap, both terminal per PR-2b
precedent). The research claim system is itself gated (Gate 30) to prevent
silent drift.

Key references:

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
for client configs, the 47-tool reference, and troubleshooting.

---

## Development & testing

### One command runs every offline gate

The same set CI runs, so "green locally" and "green in CI" cannot diverge:

```bash
python scripts/run_gates.py              # 61 gates, no dataset needed
python scripts/run_gates.py --quick      # the 53 gates that don't need numpy / a server
python scripts/run_gates.py --with-data  # 61 gates: + `flybrain verify` (70 assertions)
```

### Makefile shortcuts (v2.43.0)

```bash
make help          # all targets
make setup         # create .venv, install [dev]
make lint          # ruff check + black --check
make format        # ruff --fix + black
make typecheck     # mypy on shipped code
make test          # pytest --cov
make gates         # = python scripts/run_gates.py
make gates-data    # + flybrain verify
make smoke         # generate a smoke organism
make build         # build dist/{sdist,wheel}
make publish       # twine upload
```

### Docker (v2.43.0)

Two flavors in one image. The dataset is never baked in — mount it:

```bash
docker build -t flybrain-connectome .

# MCP stdio server
docker run --rm flybrain-connectome

# HTTP API on :8799
docker run --rm -p 8799:8799 \
  -v "$(pwd)/male_cns:/data/male_cns:ro" \
  -e FLYBRAIN_DATA_DIR=/data/male_cns \
  flybrain-connectome serve-http
```

`docker-compose.yml` also ships a `dev` / `api` / `mcp` / `gates` service
matrix — one command per use case:

```bash
docker compose up --build dev      # shell into the dev container
docker compose run --rm gates      # offline CI-equivalent gates
```

### Dev container / Codespaces

Open in VS Code or Codespaces; `.devcontainer.json` installs everything and
runs `make gates` on entry.

### Pre-commit

```bash
pre-commit install       # one time
pre-commit run --all-files
```

Hooks: ruff + ruff-format + black + trailing-whitespace + end-of-file-fixer +
check-yaml/toml/json + check-merge-conflict + debug-statements +
detect-secrets (against `.secrets.baseline`).

### Individually: each gate

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

- **Code:** MIT — see [LICENSE](LICENSE). Repo is **PUBLIC** since 2026-10-18.
  See [LICENSE-CLAUSE.md](LICENSE-CLAUSE.md) for the 3-tier split and the
  re-publicization history.
- **Connectome data:** MaleCNS v1.0, CC-BY. The 5.63 GB dataset is **not**
  included in this repository. Obtain it from the original publication and set
  `FLYBRAIN_DATA_DIR`. All numbers in this project are derived from that real
  dataset; nothing is synthetically fabricated to look impressive.

> "Virtual organism" is a **software-layer analogy**: we reuse real topology
> *principles* (motif shapes, recurrence rates, inhibition patterns), not real
> cells. It is not a wet-lab construct and is not claimed to be one.
