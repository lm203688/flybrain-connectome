# MCP Ecosystem Submission Package — flybrain-connectome v3.00.2

> **Goal**: Get flybrain-connectome listed in MCP ecosystem directories, enabling
> discovery by the 2026 AI developer community that is migrating to MCP as the
> standard tool-calling protocol.
> **Estimated time**: 60 min active work across 4 targets.
> **Cost**: $0 (all open-source directories).

---

## 0. Target List (priority order)

| # | Directory | URL | Acceptance | Time |
|---|---|---|---|---|
| 1 | **awesome-mcp-servers** | https://github.com/purpleailab/awesome-mcp-servers | PR + review | 15 min |
| 2 | **mcp-servers** (official list) | https://github.com/modelcontextprotocol/servers | PR + admin review | 15 min |
| 3 | **awesome-mcp-servers** (alt) | https://github.com/garybrail/awesome-mcp-servers | PR | 5 min |
| 4 | **MCP Registry** (if open) | https://registry.modelcontextprotocol.io/ | Submit form | 10 min |

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
