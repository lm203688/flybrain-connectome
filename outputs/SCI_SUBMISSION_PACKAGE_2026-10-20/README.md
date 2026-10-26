# SCI Submission Package · 2026-10-20

**Project**: FlyBrain Connectome · Verifiable Structure Layer
**Version**: v2.98.1 · 56/56 gates PASS · 116 units / 157 edges / 149 supported

## Package Contents

| Folder | Files | Purpose |
|---|---|---|
| `01_manuscripts/` | 6 files | Paper main texts (P-3, P-4, P-5, arXiv primary + methodology short) |
| `02_submission_guides/` | 4 files | Platform submission workflows (bioRxiv paste-ready + arXiv guides) |
| `03_evidence_reports/` | 4 files | Underlying execution + prereg reports (S1/S2/S3/C3) |
| `04_readiness/` | 4 files | SCI readiness assessments & execution plans |
| `05_scripts/` | 1 file | `post_biorxiv_backfill.py` — backfill DOIs after submission |
| `06_meta/` | — | (placeholder) |

## Two Papers to Submit Now (bioRxiv primary target)

### **P-3: Science Preprint on BioRxiv** (5-section, ~500 lines)
- **Target**: https://www.biorxiv.org/
- **Manuscript**: `01_manuscripts/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md`
  - Alt: `01_manuscripts/arxiv_methodology_short_paper_2026-10-16.md`
- **Guide**: `02_submission_guides/BIORXIV_SUBMISSION_PASTE_READY.md` §1
- **Prereg IDs**: PR-1 (WEAK) · PR-2 (FAIL×3) · PR-3 (FAIL) · PR-2b (REJECTED)
- **Category**: q-bio.QM / bio-systems (secondary: stat.ME / cs.LG)

### **P-4: PR-2b Pre-execution Rejection Paper** (3-section, ~200 lines)
- **Target**: https://www.biorxiv.org/ (submit after P-3 lands)
- **Manuscript**: `01_manuscripts/PAPER_P4_CASE_STUDY.md`
  - Alt: `01_manuscripts/PR2B_PREEXECUTION_REJECTION_PAPER.md`
- **Guide**: `02_submission_guides/BIORXIV_SUBMISSION_PASTE_READY.md` §2
- **Prereg ID**: PR-2b
- **Category**: q-bio.QM / stat.ME

## Submission Flow (bioRxiv)

```
1. Register    → https://www.biorxiv.org/ (SIGN UP top-right, NOT /login)
2. Submit P-3  → Copy PASTE_READY.md §1 → Submit
3. Submit P-4  → Copy PASTE_READY.md §2 → Submit
4. Receive DOIs → Paste DOIs back to me → I run post_biorxiv_backfill.py --apply
```

## Fallback Target: arXiv

If bioRxiv blocks: use `02_submission_guides/A_LEG_ARXIV_SUBMISSION_GUIDE_2026-10-19.md`.
arXiv requires **LaTeX PDF** upload (not MD) — use `publish_arxiv_ready.sh` locally to convert.

## Key Numbers (all verified)

| Metric | Value |
|---|---|
| Library scale | 116 units · 270 profiles · 157 edges |
| Supported edges | 149 SUPPORTED + 7 FRAGILE + 1 CONTRADICTED |
| Three connectome sets | MaleCNS · C. elegans Witvliet · Drosophila larva |
| Gates | 56/56 quick + data PASS |
| Pre-reg verdicts | PR-1 WEAK · PR-2 FAIL×3 · PR-3 FAIL · PR-2b REJECTED · PR-4 PASS |
| Discipline injection catch-rate | 51/51 (100%, Wilson 95% CI [93.0, 100.0]) |

## Related Project Files (NOT in package, in repo)

- `engine/` — 4-stage engine + 56 gates
- `connectome/` — 3 connectome datasets (MaleCNS / C. elegans / Drosophila larva)
- `vault/` — typed structure evidence library (149 SUPPORTED)
- `.workbuddy/skills/` — skill workflows
