# License & Anti-Plagiarism Tiering

> **Current status (2026-09-22):** this repository is **private**. It was
> made private as an immediate mitigation after Tier-2 IP was found in the
> public git history (v1.2.0 / v1.2.1). The Tier-1 MIT license below is
> still in force for anyone who receives access; a history rewrite is
> planned to re-publicize the Tier-1 layer. See [CHANGELOG v1.3.0](CHANGELOG.md)
> for details.

This repository uses a **three-tier license split** to maximize open-source reach while
protecting the data-driven intellectual property that is the actual moat.

## Overview

| Tier | What is shared | What is NOT shared | License |
|------|---------------|-------------------|---------|
| **Tier 1 — Open thin layer** | Code interfaces, schemas, API contract, documentation | — | MIT (`LICENSE`) |
| **Tier 2 — Closed thick layer** | Module parameter tables, clustering configs, module fingerprint database | `male_cns/connectome_cache/*`, `data/worm/raw/*.zip`, closed-tier configs | Proprietary |
| **Tier 3 — Service-side** | Signed fingerprints (sha256) delivered per-organism | Raw connectome payloads, complete clustering artifacts | API-key gated |

## Tier 1 — Open (MIT)

The following files are fully open under the MIT license in the root `LICENSE` file:

- All Python source code under `flybrain-connectome-mcp/` (the combinator file ships as a
  thin seam; see Tier 2)
- All scripts under `scripts/` except the Tier-2 discovery pipelines listed below
- All markdown documentation under `docs/`
- CI configuration (`.github/workflows/ci.yml`)
- `pyproject.toml` and packaging metadata
- The module architecture documentation (`docs/module_architecture_*.md`)

Tier 1 includes:

1. **The MCP server** (`mcp_connectome/server.py`) — full source, 40 tools registered
2. **The module registry** (`module_registry.py`) — module definitions, presets, market APIs
3. **The combinator seam** (`module_combinator.py`) — interface only, ~5.5 KB. Delegates to
   the private `flybrain_core.module_combinator` when installed; otherwise returns a
   `tier2_required` envelope. Carries **no rule payload**.
4. **The tiering bridge** (`core_bridge.py`) — graceful-degradation contract and the
   Tier-2 artifact manifest (single source of truth for Gate 8)
5. **The synthetic topology generator** (`synthetic_bio_topology.py`) — C1 motif composition
6. **The CLI** (`flybrain_cli.py`) — `flybrain serve/query/motifs/generate/verify/info`
7. **The HTTP API** (`api_server.py`) — the REST wrapper around the MCP core
8. **Fingerprint tooling** (`scripts/fingerprint_organism.py`) — format + generic key
   loader. The *implementation* is open; the signing *key* is not (Tier 3).
9. **All quality gates** (`scripts/check_*.py`, `scripts/run_gates.py`)

## Tier 2 — Closed (Proprietary)

The following artifacts are **derived from** MaleCNS v1.0 (CC-BY) and other proprietary
or semi-proprietary sources. They are NOT redistributed under MIT:

**Physical isolation (since v1.3.0).** The Tier-2 payload is *absent* from this
repository — it is not merely license-restricted. Every artifact below has been deleted
from the public tree and lives only in the private
**`lm203688/flybrain-connectome-core`**:

| Artifact | What it is |
|----------|-----------|
| `flybrain-connectome-mcp/module_combinator.py` | COMBINATION_RULES / NESTING_RULES / MULTIPLIER_SEMANTICS (7+4+3) plus the organism unit libraries. The only Tier-2 path with a public stand-in: a 5.5 KB seam |
| `male_cns/superclass_matrix.json` | 27×27 superclass projection matrix |
| `male_cns/superclass_neuropil_matrix.json` | superclass × neuropil cross-matrix |
| `male_cns/candidate_combination_rules.json` | data-mined rule candidates with enrichment z-scores |
| `male_cns/discovered_modules.json` | 8 superclass-derived module units |
| `male_cns/discovered_modules_neuropil.json` | 10 neuropil-derived module units |
| `data/worm/worm_modules.json` | 12 C. elegans (Cook 2019) module units |
| `scripts/module_discovery/*.py` (6 files) | matrix build → clustering → library → cross-species pipelines, including clustering parameters |
| `scripts/data_driven_rules.py` | rule mining from the matrix (independence null model) |

Still gated, but not relocated (large binary payloads that are never committed):

- `male_cns/connectome_cache/*.npy` — raw connectome tensor payloads (gitignored)
- `male_cns/flat-connectome/*.feather` — the 6.7 GB syn-partners source
- `data/worm/raw/*.zip` — Cook et al. 2019 raw data (Emmons Lab / Netzschleuder mirror)
- `male_cns/virtual_organisms/`, `male_cns/generated_organisms/` — generated instances
- `mcp_connectome/config.json` — API-key-gated runtime config

The public repo ships the tiering *mechanism* (`flybrain-connectome-mcp/core_bridge.py`)
and, for the combinator, the thin seam. A bare MIT install exposes **36 of the 40 MCP
tools**; the 4 combinator tools (`list_combination_rules`, `validate_combination`,
`expand_organism`, `get_multiplier_metrics`) return a `tier2_required` envelope until the
private package is installed, which restores all 40. Gate 8
(`scripts/check_physical_tiering.py`) fails the build if any Tier-2 payload reappears in
this tree, if the seam regrows into an implementation, or if the private repo stops
holding the complete set.

The **schemas and interfaces** for these artifacts are open; only the payloads are gated.

## Tier 3 — Service-side (API-key)

When the HTTP API is deployed at scale:

- All organism downloads are fingerprinted and delivered as signed JSON
- Raw connectome queries are served only through authenticated endpoints
- Every organism instance is watermarked with the fingerprint on save

**Two signature schemes** (see `scripts/fingerprint_organism.py`):

- **SHA-256 (unsigned)** — local-dev default. Deterministic and change-sensitive,
  but *forgeable*: anyone holding the organism payload can recompute it.
- **HMAC-SHA-256 (signed)** — service-side. Keyed with the server-side signing key
  (`FLYBRAIN_HMAC_KEY` env or `mcp_connectome/config.json:organism_signing_key`),
  which is **never shipped in the public repo**. Without that key an attacker cannot
  produce a valid fingerprint, so a stolen organism cannot be re-signed as authentic.

The output prefix is identical (`flybrain:organism-v1:`) in both cases, so downstream
consumers need no change. The `sign_organism()` result reports `signed` and `scheme`
explicitly, so a consumer can never mistake an unsigned organism for an authenticated one.

## Additional License Conditions

By using this software or any data-derived artifact from it, you agree:

1. **Attribution.** You must credit "flybrain-connectome" and the FlyWire consortium
   in any publication, commercial product, or downstream service built on this codebase.

2. **No reverse-engineered data redistribution.** You may use our API to query the
   connectome, but you may not attempt to reconstruct or redistribute the underlying
   raw payloads (MaleCNS v1.0 tensors, Cook 2019 worm data) in any form.

3. **No plagiarism of module fingerprints.** The data-driven module classifications
   produced by `scripts/module_discovery/*.py` (8 superclass units, 10 neuropil units,
   12 worm units) are protected by the fingerprint system described in Tier 3. Any
   re-distribution of a full module library, whether in original or paraphrased form,
   requires prior written permission.

4. **Cross-species validation artifacts.** The `data/worm/worm_modules.json` output
   references Cook et al. 2019 data. Reproduction of that analysis is permitted under
   CC-BY-4.0 (per the upstream license), but redistribution of our clustering
   assignments is covered by Tier 3.

5. **Research use.** Academic research use is encouraged without restriction, subject
   to the upstream data licenses (MaleCNS v1.0 is CC-BY; Cook 2019 is per Emmons Lab terms).

## Rationale

The three-tier split exists to:

- **Protect the moat.** The data-driven module classifications (which are the actual
  IP) are not easily recreated without running the full discovery pipeline on the
  raw payloads, and the fingerprint system provides additional attribution.
- **Enable open-source reach.** The MIT Tier 1 layer is intended to let the community
  fork, extend, and audit the code freely. *Currently paused* (repo is private since
  2026-09-22) — a history rewrite is planned to re-publicize Tier 1.
- **Preserve data sovereignty.** The raw connectome payloads remain with the original
  data owners; we only redistribute schemas, interfaces, and derived summaries.

## Fingerprint format

Fingerprints are 64-character SHA-256 hex digests, prefixed with `flybrain:` and the
organism version:

```
flybrain:organism-v1:3f9a2b1c4d5e6f708192a3b4c5d6e7f89a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4
```

A fingerprint certifies:

- The exact set of modules and their categories
- The combination rules applied
- The version of the discovery pipeline used
- The source data version (MaleCNS v1.0 / Cook 2019)

Two organisms with the same fingerprint are bit-identical.

---

MIT License (Tier 1) is at `LICENSE`. See `CITATION.cff` for academic attribution.
