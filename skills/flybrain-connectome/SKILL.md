---
name: flybrain-connectome
description: >-
  Generate auditable agent topologies grounded in the real Drosophila male-brain
  connectome, with W3C PROV-JSON provenance on every edge, and audit the result
  for structural integrity. Use when a user wants an agent swarm whose wiring can
  be traced back to real neurons/synapse classes, when they need provenance that
  satisfies EU AI Act auditing, or when they want to convert a topology into
  LangGraph/CrewAI/AutoGen format.
homepage: https://github.com/lm203688/flybrain-connectome
license: MIT
version: 3.01.3
triggers:
  - "auditable agent topology"
  - "生物可溯源的 agent 拓扑"
  - "connectome provenance"
  - "可审计的智能体拓扑"
---

# flybrain-connectome

Turn a real, published brain wiring diagram (Drosophila MaleCNS v1.0 — 166,700
neurons / 124,177,617 synapses) into task-tailored multi-agent topologies you can
instantiate as agent swarms — and prove, for every edge, **which real neuron /
synapse class it came from**. The motif provenance is serialized as **W3C
PROV-JSON**, the same standard EU AI Act auditors expect.

This addresses the "查不清" (unauditable) half of the 89% enterprise-agent-pilot
failure problem (Deloitte 2026): your agent swarm isn't a black box; it's a
verifiable structure with biological provenance.

## Capabilities

1. **Generate a topology** — compose a synthetic bio-topology from a biological
   motif blueprint (`flybrain generate`) or produce a showcase organism with an
   interactive HTML visualization (`flybrain demo`).
2. **Provenance** — every edge traces back to a real neuron/synapse class via
   W3C PROV-JSON (`flybrain motifs` / MCP `query`).
3. **Audit** — check a generated organism or swarmlabs JSON for structural
   integrity (`flybrain audit`).
4. **Export** — convert topology JSON into mainstream agent framework format
   (`flybrain export --format langgraph|crewai|autogen`).

## Prerequisites

- Python 3.10+
- `pip install flybrain-connectome` (or clone the repo and run `flybrain_cli.py`)
- Data: real connectome files under `FLYBRAIN_DATA_DIR` (offline motif build is
  the primary path; no running server required for `generate`/`demo`)

## Workflow

### 1. Generate an auditable topology

```bash
# Showcase: generates a 5-module x 8-agent predictive_coding_v2 topology
# and opens its interactive D3 HTML visualization
flybrain demo

# Or target a specific biological blueprint
flybrain generate --blueprint predictive_coding_v2 --name my_swarm
```

Output: a JSON topology + HTML visualization in `generated_organisms/`.

### 2. Trace provenance

```bash
# Export / pull the derived motifs (each carrying its neuron/synapse anchor)
flybrain motifs --output provenance.json

# Query the connectome over HTTP (requires `flybrain serve` running)
flybrain query --tool get_neuron --args '{"query": "APL"}'
```

Every edge in the topology maps back to a real neuron or synapse class. The
provenance is W3C PROV-JSON, ingestible by any PROV tool (yProv4ML, MLflow2PROV,
PROV-O SPARQL).

### 3. Audit for structural integrity

```bash
flybrain audit generated_organisms/my_swarm.json
```

Checks: schema_version, node/edge reference integrity, module_id consistency,
role binding, W3C PROV-JSON @context compliance, metrics completeness,
topology_profile validation. Exit code 0 = PASS (may have WARN), 1 = ERROR.

### 4. Export to an agent framework

```bash
flybrain export --format langgraph --input my_swarm.json
flybrain export --format crewai --input my_swarm.json
flybrain export --format autogen --input my_swarm.json
```

## Inputs / Outputs

- **Input**: a blueprint name (e.g. `predictive_coding_v2`, `inhibitory_hub`,
  `reservoir_smallworld`, `recurrent_feedback`) or an existing topology JSON.
- **Output**: JSON topology + optional interactive D3 HTML + W3C PROV-JSON
  provenance + framework-ready YAML/JSON (LangGraph/CrewAI/AutoGen).

## Honest boundaries

- This is a **developer toolkit and research artifact**, not a trained model and
  not a simulation of a fly.
- **Verified advantages**: structural simplification (GA -84% edge cost),
  module-level fault isolation (92.6% of 27 topologies), provenance
  traceability.
- **Measured as NOT an advantage** (do not claim): compute power (0/7 better
  than random), energy efficiency (0/24). These were honestly tested and found
  negative.
- Cross-species motif conservation is **PARTIAL** (2/4 robust clades) — a real
  scale/lineage-dependent boundary, not a claim of universality.

## References

- README: https://github.com/lm203688/flybrain-connectome
- Live demo: https://lm203688.github.io/flybrain-connectome/demo/
- Quickstart: `docs/QUICKSTART_5MIN.md`
- Gate battery: `scripts/run_gates.py --quick` (64 gates, fail-loud)
