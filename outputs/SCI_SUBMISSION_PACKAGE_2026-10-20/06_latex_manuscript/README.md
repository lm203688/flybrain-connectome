# LaTeX submission sources (Pandoc-generated)

Pandoc-generated LaTeX source files for the three manuscripts in the SCI
submission package. Compile locally with Tectonic or MiKTeX.

| Manuscript | Directory | .tex |
|---|---|---|
| P-1 Mainline (P-3+P-4 merged, 8000+ words) | `p1_mainline/` | `p1_mainline.tex` |
| P-3 Methodological short: Four Disciplines for Self-Verification | `p3_selfverification/` | `p3_selfverification.tex` |
| P-4 Methodological short: Preregistered Rejection | `p4_prereject/` | `p4_prereject.tex` |

Each directory also contains:
- `references.bib` — auto-extracted citations (verify metadata before submission)
- `COMPILE.md` — Tectonic / MiKTeX commands + journal template swap table
- `figures/` — empty; add real figures before submission

## What's missing
- **Real figures**: the .md sources use ASCII schematic diagrams. Convert to PNG/PDF
  and place under `figures/`.
- **Curated bibliography**: the auto-extracted bib has stub metadata. Before
  submission, verify each DOI / arXiv entry in a bibliography manager (Zotero,
  JabRef) and re-export.
- **Journal template**: swap `\documentclass{article}` for the target journal's
  template class file (see `COMPILE.md`).

## Regenerate
```bash
python scripts/build_latex_papers.py
```
