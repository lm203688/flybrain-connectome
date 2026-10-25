# MCP Ecosystem Submission Package — flybrain-connectome v3.00.2

> **Goal**: Get flybrain-connectome listed in MCP ecosystem directories, enabling
> discovery by the 2026 AI developer community that is migrating to MCP as the
> standard tool-calling protocol.
> **Estimated time**: 60 min active work across 4 targets.
> **Cost**: $0 (all open-source directories).
>
> **🎉 2026-10-25 UPDATE**: MCP Registry publication COMPLETE. Published at
> https://registry.modelcontextprotocol.io/v0.1/servers/io.github.lm203688%2Fflybrain-connectome/versions/3.0.2
> Status: active, isLatest: true. This is the official MCP server registry (7.4k stars).

---

## 0. Target List (priority order)

| # | Directory | URL | Stars | Acceptance | Status |
|---|---|---|---|---|---|
| 1 | **punkpeye/awesome-mcp-servers** | https://github.com/punkpeye/awesome-mcp-servers | 86k+ | PR #17478 | 🟡 open (needs Glama badge) |
| 2 | **MCP Registry** | https://registry.modelcontextprotocol.io/ | 7.4k | `mcp-publisher publish` | ✅ **PUBLISHED** |
| 3 | **MobinX/awesome-mcp-list** | https://github.com/MobinX/awesome-mcp-list | 893 | PR #928 | 🟡 open |
| 4 | **ceesem/awesome-connectomics** | https://github.com/ceesem/awesome-connectomics | new | PR #1 | 🟡 open |
| 5 | **cobanov/awesome-fly** | https://github.com/cobanov/awesome-fly | 684 | PR #26 | 🟡 open |
| 6 | **cryptotaxi247/awesome-mcp-servers** | https://github.com/CryptoTaxi247/awesome-mcp-servers | large | PR #1 | 🟡 open |
| 7 | **yzfly/Awesome-MCP-ZH** | https://github.com/yzfly/Awesome-MCP-ZH | 7.7k | PR #834 | 🟡 open |
| 8 | **rohitg00/awesome-devops-mcp-servers** | https://github.com/rohitg00/awesome-devops-mcp-servers | 1k | PR #380 | 🟡 open (CodeRabbit 4 fixes applied) |
| 9 | **punkpeye/awesome-remote-mcp-servers** | https://github.com/punkpeye/awesome-remote-mcp-servers | 1.8k | PR #2801 | ⚫ **Closed** (no hosted endpoint) |

---

## 9. cryptotaxi247/awesome-mcp-servers PR (target #7, biology section)

### 9.1 Fork + branch

```bash
git clone https://github.com/cryptotaxi247/awesome-mcp-servers.git
cd awesome-mcp-servers
git checkout -b add-flybrain-connectome
```

### 9.2 Add to README.md

Under "Biology, Medicine and Bioinformatics" section:

```markdown
- **[flybrain-connectome](https://github.com/lm203688/flybrain-connectome)** 🧠 🐍 🏠 —
  Preregistered discipline gate framework for connectome-derived structural motifs.
  36 MCP tools. 62-gate verification battery. 4 organism datasets (Drosophila,
  C. elegans, zebrafish). EU AI Act PROV-JSON provenance. Exports to LangGraph /
  CrewAI / AutoGen. MIT license.
```

### 9.3 PR title

```
Add flybrain-connectome to Biology, Medicine and Bioinformatics section
```

### 9.4 PR description

```markdown
## What is flybrain-connectome?

An open-source MCP server for extracting, verifying, and preregistering structural
motifs from published connectomes. It's the first tool that enforces preregistration
discipline via machine-enforced gate scripts.

## Why it fits this section

- **Biology**: uses real connectome datasets (Drosophila, C. elegans, zebrafish)
- **Bioinformatics**: performs graph-theoretic motif analysis on biological data
- **MCP server**: 36 MCP tools for AI assistant integration
- **Reproducibility**: 62-gate verification battery with 100% catch-rate

## Key features

- 4 organism datasets: MaleCNS v1.0 (166,700 neurons), WormWiring 2020, Drosophila larva 2023, zebrafish 2025
- 36 MCP tools over stdio
- 62-gate verification battery (58 quick + 4 full)
- 100% catch-rate (Wilson 95% CI [93.0%, 100.0%])
- EU AI Act PROV-JSON provenance
- Agent framework exports: LangGraph, CrewAI, AutoGen

## Repository

https://github.com/lm203688/flybrain-connectome
```

---

## 10. LobeHub MCP Marketplace submission (target #8)

### 10.1 Submit at https://lobehub.com/mcp

Fill in the submission form:

- **Name**: flybrain-connectome
- **Description**: Preregistered discipline gate framework for connectome-derived structural motifs. 36 MCP tools. 62-gate verification battery. 4 organism datasets. EU AI Act PROV-JSON provenance.
- **Category**: Science & Education
- **Type**: Local Service
- **Repository**: https://github.com/lm203688/flybrain-connectome
- **Language**: Python
- **Installation**: `pip install flybrain-connectome` or `git clone https://github.com/lm203688/flybrain-connectome.git && cd flybrain-connectome && pip install -e .`
- **Configuration**: No API key required. Uses local connectome data files.
- **License**: MIT

---

## 7. awesome-connectomics PR (target #5, best fit)

### 7.1 Fork + branch

```bash
git clone https://github.com/ceesem/awesome-connectomics.git
cd awesome-connectomics
git checkout -b add-flybrain-connectome
```

### 7.2 Add to readme.md

Under "Network Analysis and Statistics" section:

```markdown
- **[flybrain-connectome](https://github.com/lm203688/flybrain-connectome)** —
  Preregistered discipline gate framework for connectome-derived structural motifs.
  Extracts motifs from MaleCNS v1.0, WormWiring, Drosophila larva, and zebrafish.
  62-gate verification battery with 100% catch-rate. 36 MCP tools. Exports to
  LangGraph / CrewAI / AutoGen. EU AI Act PROV-JSON provenance. MIT license.
```

### 7.3 PR title

```
Add flybrain-connectome to Network Analysis and Statistics section
```

### 7.4 PR description

```markdown
## What is flybrain-connectome?

An open-source framework for extracting, verifying, and preregistering structural
motifs from published connectomes. It's the first tool that enforces preregistration
discipline via machine-enforced gate scripts.

## Why it fits this list

- **Connectomics tool**: extracts structural motifs from EM connectome datasets
- **Network analysis**: performs graph-theoretic motif analysis on connectome data
- **Reproducibility**: 62-gate verification battery ensures results are reproducible
- **Multi-organism**: supports Drosophila, C. elegans, and zebrafish datasets
- **MCP-native**: 36 MCP tools for AI agent integration

## Key features

- 4 organism datasets: MaleCNS v1.0 (166,700 neurons), WormWiring 2020, Drosophila larva 2023, zebrafish 2025
- 62 independent gate scripts for preregistration verification
- 100% catch-rate (Wilson 95% CI [93.0%, 100.0%])
- EU AI Act PROV-JSON provenance
- Agent framework exports: LangGraph, CrewAI, AutoGen

## Repository

https://github.com/lm203688/flybrain-connectome
```

---

## 8. awesome-fly PR (target #6)

### 8.1 Fork + branch

```bash
git clone https://github.com/cobanov/awesome-fly.git
cd awesome-fly
git checkout -b add-flybrain-connectome
```

### 8.2 Add to README.md

Under "Analysis Tools" or create a new section:

```markdown
- **[flybrain-connectome](https://github.com/lm203688/flybrain-connectome)** —
  Preregistered discipline gate framework for connectome-derived structural motifs.
  Uses MaleCNS v1.0 (Drosophila male brain, 166,700 neurons, 124M synapses).
  62-gate verification. 36 MCP tools. Exports to agent frameworks.
```

### 8.3 PR title

```
Add flybrain-connectome to Analysis Tools section
```

### 8.4 PR description

```markdown
## What is flybrain-connectome?

An open-source framework for extracting structural motifs from the MaleCNS v1.0
Drosophila connectome and verifying them with a 62-gate preregistration battery.

## Why it fits this list

- **Drosophila focus**: primary dataset is MaleCNS v1.0 (Drosophila male brain)
- **Analysis tool**: extracts and verifies structural motifs from connectome data
- **Reproducibility**: machine-enforced preregistration discipline
- **Active development**: v3.00.2, 62 gates, JOSS submission candidate

## Key stats

- Dataset: MaleCNS v1.0 (166,700 neurons, 124,177,617 synapses)
- Gates: 62 (58 quick + 4 full), 100% catch-rate
- Tools: 36 MCP tools, 17 CLI commands
- License: MIT
- Python: 3.10+

## Repository

https://github.com/lm203688/flybrain-connectome
```

---

## 1. awesome-mcp-servers PR (target #1)

### 1.1 Fork + branch

```bash
git clone https://github.com/purpleailab/awesome-mcp-servers.git
cd awesome-mcp-servers
git checkout -b add-flybrain-connectome
```

### 1.2 Add entry to README.md

Add the following entry to the "Biology / Life Sciences" or "Connectomics" section
(create the section if it doesn't exist). Follow the existing entry format:

```markdown
- **[flybrain-connectome](https://github.com/lm203688/flybrain-connectome)** — 🧠
  Preregistered discipline gate framework for connectome-derived structural motifs.
  36 MCP tools over stdio. Exports to LangGraph / CrewAI / AutoGen. EU AI Act
  PROV-JSON provenance. 62-gate verification battery with 100% catch-rate.
  MIT license. Python 3.10+.
```

### 1.3 PR title

```
Add flybrain-connectome to Biology/Connectomics section
```

### 1.4 PR description

```markdown
## Summary

Adding flybrain-connectome — an open-source framework for extracting, verifying,
and preregistering structural motifs from published connectomes (MaleCNS v1.0,
WormWiring, Drosophila larva, Petkova 2025 zebrafish).

## What it does

- Extracts structural motifs from 4 published connectome datasets
- Enforces preregistration discipline via 62 independent gate scripts
- Exports motifs to LangGraph / CrewAI / AutoGen agent frameworks
- Provides EU AI Act PROV-JSON provenance for every claim
- 36 MCP tools over stdio for Claude/IDE integration

## Stats

- Stars: growing
- Gate battery: 58/58 quick PASS, 62 total
- Dataset: MaleCNS v1.0 (166,700 neurons, 124M synapses)
- License: MIT
- Python: 3.10+

## Reference

The project is a JOSS submission candidate (paper.md at repo root).
See https://github.com/lm203688/flybrain-connectome for details.
```

---

## 2. Official MCP Servers list PR (target #2)

### 2.1 Fork + branch

```bash
git clone https://github.com/modelcontextprotocol/servers.git
cd servers
git checkout -b add-flybrain-connectome
```

### 2.2 Add to README.md

Find the "Science" or "Other" section and add:

```markdown
### [flybrain-connectome](https://github.com/lm203688/flybrain-connectome)

🧠 **Connectome-derived structural motif extraction with preregistered
discipline gate verification.** 36 MCP tools. 62-gate verification battery.
EU AI Act PROV-JSON provenance. Exports to LangGraph / CrewAI / AutoGen.

```

### 2.3 PR title

```
Add flybrain-connectome MCP server
```

### 2.4 PR description

```markdown
## What is flybrain-connectome?

An open-source MCP server that extracts, verifies, and preregisters structural
motifs from published connectomes. It exposes 36 MCP tools over stdio.

## Key features

- **36 MCP tools** for connectome motif extraction, verification, and export
- **62-gate verification battery** with 100% catch-rate (Wilson 95% CI [93.0%, 100.0%])
- **4 organism datasets**: MaleCNS v1.0, WormWiring 2020, Drosophila larva 2023, zebrafish 2025
- **EU AI Act PROV-JSON** provenance for every structural claim
- **Agent framework exports**: LangGraph, CrewAI, AutoGen
- **License**: MIT
- **Python**: 3.10+
- **Installation**: `pip install flybrain-connectome` (or `git clone`)

## MCP tools exposed

- `flybrain_generate` — generate organism topology
- `flybrain_verify` — verify structural integrity
- `flybrain_audit` — PROV-JSON + integrity audit
- `flybrain_query` — query topology properties
- `flybrain_export` — export to agent frameworks
- + 31 more tools

## Repository

https://github.com/lm203688/flybrain-connectome
```

---

## 3. MCP Registry submission (target #4)

If the registry at https://registry.modelcontextprotocol.io/ is open:

1. Click "Submit a server"
2. Fill in:
   - **Name**: flybrain-connectome
   - **Description**: Preregistered discipline gate framework for connectome-derived structural motifs
   - **Repository**: https://github.com/lm203688/flybrain-connectome
   - **License**: MIT
   - **Category**: Science / Biology
   - **Transport**: stdio
   - **Tools**: 36
   - **Language**: Python
   - **Tags**: connectomics, preregistration, reproducibility, AI-Act, PROV-JSON

---

## 4. Additional ecosystem targets (optional, 30 min)

| Target | URL | Notes |
|---|---|---|
| **awesome-ai-agents** | github.com/e2b-dev/awesome-ai-agents | Add under "Connectomics" or "Science" |
| **awesome-connectomics** | github.com/ | Search for connectomics directories |
| **Hugging Face Datasets** | huggingface.co/datasets | If MaleCNS is mirrored, add link |
| **Papers with Code** | paperswithcode.com | If P1 mainline paper is published |

---

## 5. Submission Checklist

- [ ] **Fork** awesome-mcp-servers and add entry
- [ ] **Fork** modelcontextprotocol/servers and add entry
- [ ] **Submit** to MCP Registry (if open)
- [ ] **Search** for 2-3 more ecosystem directories and add entries
- [ ] **Tag** the repo with `v3.00.2` (or latest) so listings show a version
- [ ] **Wait** for PR reviews (typically 1-7 days for each)

---

## 6. Expected outcome

- **Week 1**: 2-3 PRs submitted, 1-2 accepted
- **Week 2**: PRs merged, project visible in MCP ecosystem
- **Month 1**: First organic star/fork from MCP ecosystem traffic
- **Month 3**: Discoverability improves 5-10x via ecosystem directories

**Key insight**: MCP ecosystem directories have low competition in the biology/
connectomics category (unlike the LLM/tools category which is saturated). The
first project to get listed gets disproportionate visibility.
