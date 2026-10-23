# flybrain-connectome: 5-Minute Quickstart

> From zero to an interactive D3 topology graph in five minutes. No data download, no server setup, no credentials. Just Python 3.10+.

## Why this project exists (30 seconds)

Deloitte's 2026 agent-pilot survey found **89% of enterprise agent pilots never reach production**. The failure pattern isn't intelligence — it's three words repeated across industries: **"跑不稳、管不住、查不清"** (unstable, ungovernable, unauditable).

`flybrain-connectome` addresses the third word directly: every agent edge in a generated topology traces back to a real neuron or synapse class in the *Drosophila* male brain connectome, serialized as **W3C PROV-JSON** — the same format EU AI Act auditors expect.

You don't need neuroscience expertise to use this. You need Python.

---

## Minute 1 — Clone and check

```bash
git clone https://github.com/lm203688/flybrain-connectome.git
cd flybrain-connectome
python flybrain_cli.py --help
```

You should see 14 commands including `demo`, `generate`, `serve`, `query`, `profile`, and `verify`.

**One runtime dependency:** `numpy`. That's it. No GPU, no CUDA, no Docker required.

---

## Minute 2 — Generate a topology (one command)

```bash
python flybrain_cli.py demo --no-open
```

Output:
```
[demo] Generating showcase organism...
  blueprint : predictive_coding_v2
  modules   : 5
  agents/module: 8

[demo] Outputs written to:
  [json] .../generated_organisms/demo_predictive_coding_v2_m5_a8.json
  [html] .../generated_organisms/demo_predictive_coding_v2_m5_a8.html
  [swarm] .../swarmlabs/demo_predictive_coding_v2_m5_a8.swarm.json

[demo] Done.
```

That's it. You now have a **40-agent multi-module topology** with:
- **40 agents** (8 per module, 5 modules)
- **W3C PROV-JSON provenance** on every edge
- **SwarmLabs config** ready to import into CrewAI / AutoGen / LangGraph
- **D3 interactive HTML** visualization (open in browser)

**No data download.** The generator composes topologies from a 7 KB derived motif snapshot bundled in the repo.

---

## Minute 3 — Open the interactive visualization

```bash
# On macOS
open flybrain-connectome-mcp/generated_organisms/demo_predictive_coding_v2_m5_a8.html

# On Windows
start flybrain-connectome-mcp/generated_organisms/demo_predictive_coding_v2_m5_a8.html

# On Linux
xdg-open flybrain-connectome-mcp/generated_organisms/demo_predictive_coding_v2_m5_a8.html
```

You'll see a **force-directed D3 graph** with:
- **Draggable nodes** — drag any agent to reposition it
- **Hover tooltips** — mouse over a node to see its role, module, and motif source
- **Dark theme** — designed for sustained reading
- **Fully offline** — no CDN dependencies, works in an air-gapped lab
- **RequestAnimationFrame animation** — smooth node physics

The graph shows 5 modules (color-coded) with inhibitory coordinators (red hub) and reservoir buffers (blue) connecting them. This topology is grounded in real Drosophila circuit motifs: the antennal lobe's inhibitory architecture, the mushroom body's memory structure, and the central complex's recurrent processing.

---

## Minute 4 — Profile the topology

```bash
python flybrain_cli.py profile flybrain-connectome-mcp/generated_organisms/demo_predictive_coding_v2_m5_a8.json
```

Output includes:
- **Module count** and agent distribution
- **Edge density** and clustering coefficient
- **Spectral radius** (stability indicator — should be < 1.0)
- **Provenance coverage** (what % of edges trace to real neurons)

For JSON output:
```bash
python flybrain_cli.py profile flybrain-connectome-mcp/generated_organisms/demo_predictive_coding_v2_m5_a8.json --json
```

For comparing two topologies:
```bash
python flybrain_cli.py profile a.json --compare b.json
```

---

## Minute 5 — Run the gates

```bash
python scripts/run_gates.py --quick
```

Expected output:
```
========================================================================
GATES: PASS — 57/57
```

57 gates check:
- **Version consistency** across 7 files
- **Gate-to-metric mapping** (no orphaned checks)
- **Provenance integrity** (W3C PROV-JSON schema v1.2.1)
- **Preregistration completeness** (all 7 PRs have hash-committed vaults)
- **Statistical rigor** (Wilson CIs, bootstrap intervals, permutation tests)
- **Supply chain** (AIBOM disclosure, dependency audit)

**If you see any FAIL, you're doing it right** — the gates are designed to be loud about problems.

---

## What to try next

### For agent framework developers
```bash
# Start the HTTP API server
python flybrain_cli.py serve --port 8080

# Query a connectome tool
python flybrain_cli.py query --tool units --json

# Generate with a different blueprint
python flybrain_cli.py demo --blueprint swim_resonance --modules 3 --agents-per-module 12
```

### For researchers
```bash
# Read the C. elegans developmental axis
python flybrain_cli.py stages

# Read the larva connectome cluster ledger
python flybrain_cli.py larva-clusters --top 20

# Read the MaleCNS male-dimorphic ledger
python flybrain_cli.py dimorphism
```

### For auditors
```bash
# Verify the full pipeline end-to-end
python flybrain_cli.py verify

# Check the full structural profile as JSON
python flybrain_cli.py profile generated_organisms/demo.json --json
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ImportError: numpy` | numpy not installed | `pip install numpy` |
| `[demo] Error: ...` | Running outside a checkout | `export FLYBRAIN_HOME=/path/to/flybrain-connectome` |
| `Toolkit missing` in `flybrain info` | FLYBRAIN_HOME not set | `export FLYBRAIN_HOME=$(pwd)` |
| HTML won't open | Minimal renderer fallback | Run `flybrain generate` for full D3 visualization |
| `flybrain demo` shows "[warn] Full HTML renderer not available" | Normal in minimal installs | The JSON output is complete; HTML is a nice-to-have |

---

## Honest boundaries

- **This is a topology generator, not a neuron simulator.** The topology is grounded in real brain circuit motifs, but the agents are software entities — not spiking neurons.
- **68% of the 116 functional units are cross-species declarations** without MaleCNS anchoring. They are comparative-neuroscience scaffolds, not measured circuits.
- **Phase 3 experiments measured negative** — the synthetic topology does not beat random structure on raw compute or energy efficiency. The value is in **traceability**, not performance.
- **The project is a single-author independent-researcher work** (Li Xing, Shenzhen). It is not affiliated with any institution and has no external funding.

---

## Next steps

1. **Read the full README** for the 13-command reference, Docker setup, and swarm config examples
2. **Run the notebooks** in `examples/` for guided exploration
3. **Check out the methodological papers** in `docs/` — the preregistered-negative-result regime is the most interesting thing in this repo
4. **File an issue** if you find a bug or want to suggest a feature — the project is publicly invited to contributions

---

*Five minutes ago you didn't know this project existed. Now you have a 40-agent topology with full provenance traceability, ready to plug into CrewAI, AutoGen, or LangGraph. That's the pitch.*
