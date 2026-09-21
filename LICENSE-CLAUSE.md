# License & Anti-Plagiarism Tiering

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

- All Python source code under `flybrain-connectome-mcp/` (except closed-tier configs listed below)
- All shell scripts under `scripts/`
- All markdown documentation under `docs/`
- CI configuration (`.github/workflows/ci.yml`)
- `pyproject.toml` and packaging metadata
- The module architecture documentation (`docs/module_architecture_*.md`)

Tier 1 includes:

1. **The MCP server** (`mcp_connectome/server.py`) — full source, 40 tools
2. **The module registry** (`module_registry.py`) — module definitions, presets, market APIs
3. **The combinator middleware** (`module_combinator.py`) — validation/expansion API
4. **The synthetic topology generator** (`synthetic_bio_topology.py`) — C1 motif composition
5. **The CLI** (`flybrain_cli.py`) — `flybrain serve/query/motifs/generate/verify/info`
6. **The HTTP API** (`api_server.py`) — the REST wrapper around the MCP core
7. **All discovery scripts** (`scripts/module_discovery/*.py`) — reproducible pipelines

## Tier 2 — Closed (Proprietary)

The following artifacts are **derived from** MaleCNS v1.0 (CC-BY) and other proprietary
or semi-proprietary sources. They are NOT redistributed under MIT:

- `male_cns/connectome_cache/*.npy` — raw connectome tensor payloads
- `male_cns/flat-connectome/*.feather` — the 6.7 GB syn-partners source
- `data/worm/raw/*.zip` — Cook et al. 2019 raw data (Emmons Lab / Netzschleuder mirror)
- `male_cns/virtual_organisms/` — user-generated organism instances
- `male_cns/generated_organisms/` — batch-generated topology outputs
- `mcp_connectome/config.json` — API-key-gated runtime config

The **canonical, authoritative copy** of every Tier-2 artifact lives in the
**private repository `flybrain-connectome-core`** (`lm203688/flybrain-connectome-core`).
The public repo (`lm203688/flybrain-connectome`, MIT) ships only the Tier-1 code and
the tiering *mechanism* (`flybrain-connectome-mcp/core_bridge.py`): public code prefers
the private package when installed and degrades gracefully (9 tools return a
"Tier-2 required" envelope) when it is absent. This keeps the MIT surface auditable
while the closed IP never ships in the open package.

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
- **Enable open-source reach.** The MIT Tier 1 layer lets the community fork, extend,
  and audit the code freely.
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
