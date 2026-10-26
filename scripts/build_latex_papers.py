#!/usr/bin/env python3
"""Generate LaTeX + BibTeX submission sources for P-1, P-3, P-4 via pandoc.

Target journals:
  - Frontiers in Computational Neuroscience (primary LaTeX template)
  - Scientific Reports (Springer Nature template)
  - IEEE / Elsevier (as fallback)

Note: pandoc emits a compilable .tex that uses the standard article class.
For final journal submission, users can swap the documentclass line to the
specific journal template (e.g. \\documentclass[oneside]{article} ->
\\documentclass{frontiersin}). Everything else (sections, references, tables)
is preserved verbatim.

Usage:
  python scripts/build_latex_papers.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PANDOC = r"C:\Users\xing\AppData\Local\Pandoc\pandoc.exe"

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "outputs" / "SCI_SUBMISSION_PACKAGE_2026-10-20" / "06_latex_manuscript"

# Three manuscripts to convert
PAPERS = [
    {
        "slug": "p1_mainline",
        "src": DOCS / "PAPER_P1_MAINLINE_MERGED.md",
        "title": "A Preregistered-Negative-Result Regime with Machine-Enforced "
                 "Self-Verification: The 116-Unit Drosophila Male CNS Substrate "
                 "as Test Case",
        "author": "Li Xing",
        "abstract_hint": "The preregistered-negative-result regime",
    },
    {
        "slug": "p3_selfverification",
        "src": DOCS / "S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md",
        "title": "Four Disciplines for Self-Verification in Computational Experiments",
        "author": "Li Xing",
        "abstract_hint": "Four disciplines for self-verification",
    },
    {
        "slug": "p4_prereject",
        "src": DOCS / "PAPER_P4_CASE_STUDY.md",
        "title": "Preregistered Rejection as a First-Class Negative Result: "
                 "A Methodological Case Study on the 116-Unit Drosophila Male CNS",
        "author": "Li Xing",
        "abstract_hint": "Preregistered rejection as a first-class negative result",
    },
]


def extract_abstract(md_text: str) -> str:
    """Pull the first ~150-word abstract from an MD manuscript."""
    # Look for explicit Abstract heading first
    m = re.search(r"(?ims)^#{1,3}\s*Abstract\s*\n(.*?)(?=\n#{1,3}\s|\Z)", md_text)
    if m:
        body = m.group(1).strip()
        # strip bullets, blockquotes
        body = re.sub(r"^[-*>]\s+", "", body, flags=re.M)
        body = re.sub(r"\s+", " ", body).strip()
        if len(body.split()) >= 60:
            return body[:2400]
    # Fallback: first non-heading paragraph after title/author block
    lines = md_text.split("\n")
    buf = []
    started = False
    for line in lines:
        if re.match(r"^#{1,6}\s", line):
            if started:
                break
            if re.search(r"Abstract", line, re.I):
                started = True
            continue
        if line.startswith("**") or line.startswith("*"):
            continue
        if line.strip().startswith("https://") or line.strip().startswith("`"):
            continue
        if not line.strip():
            if started and buf:
                continue
            continue
        if line.strip().startswith("---") or line.strip().startswith("|"):
            continue
        buf.append(line.strip())
    return re.sub(r"\s+", " ", " ".join(buf)).strip()[:2400]


PANDOC_HEADER = r"""% Pandoc-generated LaTeX source
% Target journal template: swap \documentclass line to the specific template
%   e.g. \documentclass[oneside]{article} -> \documentclass{frontiersin}
% Compile with:
%   pdflatex paper && bibtex paper && pdflatex paper && pdflatex paper
% or with tectonic: tectonic paper.tex

\documentclass[11pt,letterpaper]{article}

% Standard packages
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{geometry}
\usepackage{hyperref}
\usepackage{natbib}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{multirow}
\usepackage{fancyhdr}
\usepackage{fcolorbox}
\usepackage{caption}
\usepackage{float}
\usepackage{microtype}
\usepackage{enumitem}
\usepackage{listings}
\usepackage{url}

\geometry{a4paper, margin=1in}

% Hyperref setup
\hypersetup{
  colorlinks=true,
  linkcolor=blue,
  citecolor=green!50!black,
  urlcolor=blue,
}

\renewcommand{\textcolor}[1]{}  % avoid \textcolor inside \hyperref if needed

\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{Li Xing \textemdash Independent Researcher}
\fancyhead[R]{Preprint \textemdash submitted 2026-10-21}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}

% Math helpers
\newcommand{\ci}[2]{[\,#\textit{95\%}\ CI\ \ensuremath{[}\,#\mathit{#1}\,{-}\,\mathit{#2}\,]\,\textcolor{gray}{\scriptsize (bootstrap)}}]
\newcommand{\citekey}[1]{\texttt{#1}}

% Bibliography style
\bibliographystyle{plainnat}
\nobibliography*

\begin{document}
"""


def convert(md_path: Path, slug: str, title: str, author: str) -> dict:
    """Convert one Markdown manuscript to a submission-ready LaTeX source."""
    out_dir = OUT / slug
    fig_dir = out_dir / "figures"
    bib_dir = out_dir / "refs"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    bib_dir.mkdir(parents=True, exist_ok=True)

    md_text = md_path.read_text(encoding="utf-8")
    abstract = extract_abstract(md_text)

    tex_path = out_dir / f"{slug}.tex"
    bib_path = out_dir / "references.bib"

    # Prepend pandoc YAML-ish frontmatter so pandoc handles title/author/abstract cleanly
    # Write bib FIRST (pandoc needs it to exist before --citeproc runs)
    bib_text = extract_bib_from_md(md_text, slug)
    bib_path.write_text(bib_text, encoding="utf-8")

    pandoc_input = md_path.with_suffix(".pandoc_input.md")
    safe_title = title.replace('"', '\\\\')  # double-escape for YAML frontmatter
    frontmatter = f"""---
title: "{safe_title}"
author: "{author}"
date: "2026-10-21"
abstract: |
  {abstract}
bibliography: "references.bib"
link-citations: true
natbib: true
number-sections: true
---

"""
    pandoc_input.write_text(frontmatter + md_text, encoding="utf-8")

    cmd = [
        PANDOC,
        str(pandoc_input),
        "-o", str(tex_path),
        "--standalone",
        "--section-divs",
        "--number-sections",
        "--toc",
        "--toc-depth=3",
        f"--bibliography={bib_path}",
        "--citeproc",
        f"--resource-path={out_dir}",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[FAIL] pandoc {slug}: {r.stderr.strip()}")
        return {"slug": slug, "ok": False, "stderr": r.stderr}

    # Post-process: prepend a top-of-file journal-template comment so users know
    # where to swap documentclass. Pandoc's default template already emits a
    # complete, compilable preamble, so we do NOT insert additional packages —
    # that would cause duplicate \usepackage errors.
    tex_text = tex_path.read_text(encoding="utf-8")

    # Insert the swap hint BEFORE the \documentclass block (which may span lines)
    preamble_hint = r"""% ===========================================================================
% LaTeX source generated by scripts/build_latex_papers.py (pandoc)
%
% JOURNAL TEMPLATE SWAP:
%   The default documentclass is "article". For final submission, replace the
%   \documentclass[...] line with the target journal's class. See COMPILE.md
%   for a per-journal template swap table and download instructions.
%
% COMPILE:
%   tectonic pN.tex              (single-binary, recommended)
%   OR: pdflatex pN.tex && bibtex pN && pdflatex pN.tex && pdflatex pN.tex
%
% REFERENCES:
%   references.bib is auto-extracted from the markdown References section.
%   Verify all metadata (author, title, journal, volume, pages, DOI) in
%   Zotero/JabRef before submission — stub entries contain the raw citation
%   text so nothing is lost.
%
% FIGURES:
%   Add real PNG/PDF figures under figures/ and update \includegraphics paths.
% ===========================================================================

"""
    # Find the first \documentclass (may be multi-line \documentclass[...])
    match = re.search(r"^\\documentclass", tex_text, re.M)
    if match:
        insert_at = match.start()
        tex_text = preamble_hint + tex_text[insert_at:]
        tex_path.write_text(tex_text, encoding="utf-8")
    else:
        print(f"[WARN] no \\documentclass found in {tex_path}")

    # Write references.bib
    bib_text = extract_bib_from_md(md_text, slug)
    bib_path.write_text(bib_text, encoding="utf-8")

    # Compile instructions
    compile_md = """# Compile {slug}.tex

## Prerequisites
- Install [Tectonic](https://tectonic.net/) (recommended, single-binary):
  ```powershell
  winget install tactiq.Tectonic
  ```
- Or install MiKTeX: `winget install MiKTeX.MiKTeX`

## Compile commands
```powershell
cd outputs/SCI_SUBMISSION_PACKAGE_2026-10-20/06_latex_manuscript/{slug}
tectonic {slug}.tex
```
Or with pdflatex + bibtex:
```powershell
pdflatex {slug}.tex
bibtex {slug}
pdflatex {slug}.tex
pdflatex {slug}.tex
```

## Journal template swap
The current documentclass is `article` (generic). For target journals:

| Journal | Template file | Swap line |
|---|---|---|
| Frontiers in Computational Neuroscience | `frontiersin.cls` | `\\documentclass[running]{{frontiersin}}` |
| Scientific Reports | `sn-jnl.cls` | `\\documentclass[script,sn-nature]{{sn-jnl}}` |
| PLOS ONE | `plosone.cls` | `\\documentclass[sn-nature]{{sn-jnl}}` |
| Neural Computation (MIT Press) | `mtp.cls` | `\\documentclass[prelim]{{mtp}}` |

The template files are downloadable from each journal's author kit and should be
placed in this directory.

## Content checks
- Sections 1–7 (Introduction through Conclusion) are present.
- References resolve via `references.bib`; missing keys should log as warnings.
- All figures referenced in text are placeholders — add real PNGs/PDFs under
  `figures/` and update `\\includegraphics` paths before submission.

## Data / Code availability
- Repository: https://github.com/lixing1123/flybrain-connectome
- License: MIT
- Pre-registration vault: `vault/` and `registry/preregistered_rejections.json`
""".format(slug=slug)
    (out_dir / "COMPILE.md").write_text(compile_md, encoding="utf-8")

    return {"slug": slug, "ok": True, "tex": str(tex_path), "bib": str(bib_path)}


def extract_bib_from_md(md_text: str, slug: str) -> str:
    """Best-effort extraction of references into a bib file.

    Strategy:
      1. Find the References / Bibliography section (markdown numbered list).
      2. Parse each numbered entry as a single line of citation metadata.
      3. Emit an @article entry with the best-available fields (title, author,
         journal, year, volume, pages, doi). Fields we cannot parse are
         emitted as verbatim "note" lines so the citation is still locatable
         and a human can finish it in Zotero / JabRef.

    Real bibliographies should be manually curated before journal submission.
    """
    refs = []
    seen_keys = set()

    # ---- Parse the References section (numbered markdown list) ----
    m = re.search(r"#{1,4}\s*(?:References|Bibliography|References list)\b[\s\n]*(.*?)(?:\n#{1,3}\s|\Z)",
                  md_text, re.I | re.DOTALL)
    ref_section = m.group(1) if m else ""

    if ref_section:
        # Split on leading "N." markers
        entries = re.split(r"\n\s*(\d{1,2})[.)]\s+", "\n" + ref_section)
        # entries = ['', '1', 'content1', '2', 'content2', ...]
        idx = 1
        while idx + 1 < len(entries):
            raw = entries[idx + 1].strip()
            raw = re.sub(r"\s+", " ", raw)
            entry_key = f"ref{idx:02d}"
            while entry_key in seen_keys:
                idx += 1
                entry_key = f"ref{idx:02d}"
            seen_keys.add(entry_key)

            # Try to detect DOI inline
            doi_m = re.search(r"DOI:\s*([0-9A-Za-z\.\-/]+)", raw, re.I)
            doi = doi_m.group(1).rstrip(".,;)\"' ") if doi_m else None

            # Heuristic author extract: first chunk before " (" or " (" or " - "
            author_m = re.match(r"^([A-Z][A-Za-z\.\-\,\& ]{1,80}?)\s*[\(,]\s*(?:\d{4}|\d{4}-\d{4})", raw)
            author = author_m.group(1).strip().rstrip(",") if author_m else ""
            # Fallback for "Name et al." or single-author patterns
            if not author:
                first_dot = raw.find(".")
                if first_dot > 20:
                    author = raw[:first_dot].strip()

            # Year
            year_m = re.search(r"\((\d{4})\)", raw) or re.search(r"\b(\d{4})\b", raw)
            year = year_m.group(1) if year_m else ""

            # Journal / book-ish: text between italic markers *...*
            journal_m = re.search(r"\*([^*]{3,80})\*", raw)
            journal = journal_m.group(1) if journal_m else ""

            # Title: text before " *Journal*" or before " (year) . "
            title_m = re.search(r"(?:\(\d{4}\)\.\s*|(\d{4}),\s*)([^*]{10,200})", raw)
            title = ""
            if journal_m:
                pre = raw[:journal_m.start()].strip()
                # strip trailing year and comma
                title = re.sub(r"\((\d{4})\)\.?\s*$", "", pre).rstrip("., ")
            if not title and author:
                tail = raw.split(author, 1)[1].strip()
                title = re.sub(r"^\s*\(\d{4}\)\.?\s*", "", tail).split(" *")[0].strip().rstrip("., ")
                if not title:
                    title = raw[:200]

            entry_lines = ["@article{" + entry_key + ","]
            if author:
                entry_lines.append("  author  = {" + author + "},")
            if title:
                entry_lines.append("  title   = {" + title[:220] + "},")
            if journal:
                entry_lines.append("  journal = {" + journal + "},")
            if year:
                entry_lines.append("  year    = {" + year + "},")
            if doi:
                entry_lines.append("  doi     = {" + doi + "},")
            entry_lines.append("  note    = {extracted from manuscript body; verify full metadata before submission},")
            entry_lines.append("}")
            refs.append("\n".join(entry_lines))

    # ---- Also catch inline arXiv / DOI citations scattered elsewhere ----
    for m in re.finditer(r"arXiv:(\d{4}\.\d{4,5})", md_text):
        aid = m.group(1)
        key = "arxiv" + aid.replace(".", "")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        refs.append(
            "@article{" + key + ",\n"
            "  title = {arXiv preprint " + aid + "},\n"
            "  eprint = {" + aid + "},\n"
            "  archiveprefix = {arXiv},\n"
            "}"
        )

    for m in re.finditer(r"(?:doi[:/]|https?://(?:dx\.)?doi\.org/)([0-9]\.[0-9]{4,}/[A-Za-z0-9\.\-]+)", md_text, re.I):
        doi = m.group(1).rstrip(".,;)\"' ")
        key = "doi_" + doi.replace("/", "_").replace(":", "_")[:40]
        if key in seen_keys or any(r.split("=", 1)[1].strip().strip("{}") == doi for r in refs for _ in [0] if "@" not in r.split("=",1)[0]):
            continue
        if any(doi in r for r in refs):
            continue
        seen_keys.add(key)
        refs.append(
            "@article{" + key + ",\n"
            "  title = {verify via DOI},\n"
            "  doi = {" + doi + "},\n"
            "}"
        )

    header = (
        "% references.bib — auto-generated by scripts/build_latex_papers.py\n"
        "% Verify metadata (title, author, journal, volume, pages) in Zotero/JabRef\n"
        "% before final journal submission. Stub entries preserve the original\n"
        "% citation text as `note` so nothing is lost.\n\n"
    )
    if not refs:
        return header + "% Empty bib; author should curate references.bib manually before submission.\n"
    return header + "\n\n".join(refs) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for p in PAPERS:
        src = p["src"]
        if not src.exists():
            print(f"[SKIP] missing {src}")
            continue
        r = convert(src, p["slug"], p["title"], p["author"])
        results.append(r)
        status = "OK" if r["ok"] else "FAIL"
        print(f"[{status}] {p['slug']}: tex={r.get('tex')} bib={r.get('bib')}")

    # Write README
    (OUT / "README.md").write_text(
        """# LaTeX submission sources (Pandoc-generated)

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
- **Journal template**: swap `\\documentclass{article}` for the target journal's
  template class file (see `COMPILE.md`).

## Regenerate
```bash
python scripts/build_latex_papers.py
```
""",
        encoding="utf-8",
    )
    print(f"[OK] wrote {OUT}/README.md")


if __name__ == "__main__":
    main()
