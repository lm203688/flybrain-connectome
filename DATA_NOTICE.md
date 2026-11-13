# Data Notice — MaleCNS Connectome Dataset

This repository **does not contain** the MaleCNS raw dataset. It is fetched
externally via the documented data pipeline and queried through the MCP/HTTP API.
This notice documents its provenance, license, and modifications for the
benefit of anyone reusing or redistributing project artifacts derived from it.

## Provenance

- **Dataset:** MaleCNS v1.0 — male *Drosophila* central nervous system connectome
- **Primary publication:** Berg, S. et al. (2026). *Sexual dimorphism in the complete
  Drosophila male central nervous system connectome.* **Cell**, 189(18), 5504–5526.e15.
  DOI: [10.1016/j.cell.2026.08.015](https://doi.org/10.1016/j.cell.2026.08.015)
  (published 2026-09-03; PII S0092867426009426).
- **Preprint:** Berg, S. et al. (2025). *Sexual dimorphism in the complete connectome of
  the Drosophila male central nervous system.* bioRxiv.
  DOI: [10.1101/2025.10.09.680999](https://doi.org/10.1101/2025.10.09.680999)
  (posted 2025-10-09; no `v2` suffix — the `v2` DOI resolves to HTTP 404).
- **Source:** male-cns.janelia.org (Janelia Research Campus).

## License

The MaleCNS dataset is released under **CC-BY 4.0** (© 2026 MRC Laboratory of
Molecular Biology). The license text and attribution requirements are the
responsibility of the upstream release; this notice does not replace them.

## Modification notice

`DATA_MANIFEST.json` in this repository is a **derived, project-generated** file
that records the sha256 checksums and byte counts of the fetched MaleCNS files as
they were **after** any project-side transformation (see "Changes" below). It is
**not** part of the upstream MaleCNS release and does **not** re-license the
underlying data.

**Changes made to the dataset by this project (if any):**

- The dataset is consumed **read-only** for topology extraction (motifs, recurrence
  rates, inhibition patterns). No cell annotations or connectivity records are
  modified in place.
- `DATA_MANIFEST.json` (211,604 files, `total_bytes` = 37,418,478,413) was generated
  by this project on 2026-09-20 for integrity verification (sha256) and size
  accounting. It is an additional artifact, not an upstream file.

**Size (two unit conventions, same byte count):**

| Unit | Value | Note |
|------|-------|------|
| Bytes (decimal) | 37,418,478,413 B | `DATA_MANIFEST.json` `total_bytes` |
| GB (10^9) | 37.42 GB | decimal units |
| GiB (2^30) | 34.85 GiB | binary units |

The compressed download is ~5.63 GB (as delivered by male-cns.janelia.org).

## Attribution when reusing derived artifacts

Any artifact in this project derived from MaleCNS (motif documents, connectivity
statistics, generated topologies) should cite:

> Berg, S. et al. (2026). Sexual dimorphism in the complete Drosophila male central
> nervous system connectome. *Cell*, 189(18), 5504–5526.e15.
> doi:10.1016/j.cell.2026.08.015.

and note that the underlying data is CC-BY 4.0 and **not** created by this project.
