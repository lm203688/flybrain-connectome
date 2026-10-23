# LaTeX Compilation Guide

## Quick Start (compile locally)

```bash
# Option 1: Tectonic (recommended, single binary)
winget install tactiq.Tectonic
cd p1_mainline
tectonic p1_mainline.tex

# Option 2: MiKTeX or TeX Live
pdflatex p1_mainline.tex
bibtex p1_mainline
pdflatex p1_mainline.tex
pdflatex p1_mainline.tex
```

## Directory structure

Each paper directory contains:
```
pN_<name>/
├── pN_<name>.tex       # Main source (pandoc-generated, hand-touched for compile)
├── references.bib      # BibTeX entries (38+ entries, some stubs)
├── figures/            # Real PNG figures (3 figures + 4 table markdowns)
├── COMPILE.md          # This file
└── refs/               # (may contain additional reference materials)
```

## Journal template swap

The pandoc-generated `.tex` uses `\documentclass{article}` as a **fallback**.
For final journal submission, replace the top line with the target journal's class.

| Target journal | Template class | Download |
|---|---|---|
| **Scientific Reports** (Nature, Q1) | `sn-jnl.cls` | https://www.nature.com/sn-journal/submission-guidelines/preparing-your-article |
| **Frontiers in Computational Neuroscience** | `frontiersin.cls` | https://www.frontiersin.org/journals/computational-neuroscience |
| **PLOS Computational Biology** | `plos.bst` + standard | https://journals.plos.org/ploscompbiol/submissions |
| **Bioinformatics (Oxford)** | `bmolatex` | https://academic.oup.com/bioinformatics/pages/author-guidance |

### Swap procedure

1. Download the target journal's `.cls` file into the paper directory
2. Change line 23 in `pN_<name>.tex` from:
   ```latex
   \documentclass[
   ]{article}
   ```
   to:
   ```latex
   \documentclass{sn-jnl}        % Scientific Reports
   % or
   \documentclass{frontiersin}   % Frontiers in Computational Neuroscience
   ```
3. Delete or comment out lines that conflict with the new template (often `\usepackage{geometry}`, `\usepackage{graphicx}`, or `\usepackage{hyperref}` — the template provides these)
4. Replace `\bibliographystyle{plainnat}` with the journal's required style:
   - Scientific Reports: `\bibliographystyle{sn-nature}`
   - Frontiers: `\bibliographystyle{frontiersin}`
   - PLOS Comp Biol: `\bibliographystyle{plos}`
5. Follow the journal's cover page / running title / corresponding author block

## Reference style

- **Current**: `plainnat` (numbered, author-year in bibliography). Text citations use `\citet{}` (e.g., `(Xu et al. 2026)`).
- **To switch**: change `\bibliographystyle{}` in the preamble and any citation commands as required by the journal.
- **Note**: Some references in `references.bib` are stubs (extracted from markdown). Verify each DOI/title/journal in Zotero or JabRef before submission — journals reject submissions with broken metadata.

## Figures

The `figures/` directory contains 3 real PNG figures plus 4 table markdown files.
- `fig1_endpoint_distribution.png` — PR endpoint distribution
- `fig2_s3_catch_rate.png` — S3 mutation-injection catch rate
- `fig3_s1_external_auc.png` — S1 cross-species AUC contrast
- `table*.md` — table content (render as text in current form; consider converting to PDF)

For journal submission, convert figures to the journal's preferred format (usually PDF or TIFF at 300+ dpi).

## Compilation troubleshooting

### "I can't find file references.bib"
- Ensure the `.bib` file is in the same directory as the `.tex` file (or a path relative to it)

### "Undefined control sequence: \pandocbounded"
- The preamble defines `\providecommand{\pandocbounded}[1]{#1}`; if you stripped the preamble, add this line manually

### "Overfull hbox"
- Add `\emergencystretch{3em}` (already present in the preamble) or increase the margins

### Bib entries with malformed fields
- Some `references.bib` entries have stub metadata. Use JabRef to normalize.

## Final checklist before submission

- [ ] Swap `\documentclass` to the target journal's class
- [ ] Verify all 38+ references in Zotero/JabRef (DOI, journal, year)
- [ ] Convert figures to journal's required format (PDF or TIFF)
- [ ] Add cover page / running title per journal
- [ ] Compile twice (or three times) so that citations resolve
- [ ] Upload PDF + source files as required by the journal's submission system
