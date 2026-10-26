"""Post-bioRxiv backfill script.

Usage:
    python scripts/post_biorxiv_backfill.py <P3_DOI> <P2_DOI>

Example:
    python scripts/post_biorxiv_backfill.py 10.1101/2610.876543 10.1101/2610.876544

What this does:
    1. Verifies both DOIs resolve on https://doi.org/<DOI>
    2. Backfills DOIs into docs/arxiv_paper.md References
    3. Bumps version v2.98.1 -> v2.99.0 in 7 files (pyproject.toml, flybrain_cli.py,
       api_server.py, server.py, README.md x2 badges)
    4. Appends CHANGELOG entry
    5. Updates docs/SCI_VERDICT_2026-10-19.md with submission status
    6. Prints exact Commands to run: gate check + gh_publish.py push

Runs in DRY-RUN mode by default. Pass --apply to actually modify files.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Files that contain the version string (all must be bumped together).
# Grep-verified 2026-10-19: 7 files.
VERSION_FILES = [
    "pyproject.toml",
    "flybrain_cli.py",
    "api_server.py",
    "server.py",
    "README.md",
    "flybrain-connectome-mcp/mcp_connectome/api_server.py",
    "flybrain-connectome-mcp/mcp_connectome/server.py",
]

OLD_VERSION = "2.98.1"
NEW_VERSION = "2.99.0"

REFS_BLOCK_TEMPLATE = """
### 15. Companion preprints (bioRxiv, 2026-10-20)

{p3_cite}

{p2_cite}

These two methodological preprints form the A-leg of this project's publication
plan. The main-line paper (this document) is the B-leg; they share data, code,
and the preregistration protocol but address different questions.
"""


def doi_resolves(doi: str) -> bool:
    url = f"https://doi.org/{doi}"
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "flybrain-backfill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            # 302 to biorxiv.org is fine — it means the DOI resolves.
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as e:
        return 300 <= e.code < 400
    except Exception:
        return False


def format_cite(paper_id: str, title: str, doi: str) -> str:
    return (
        f"[{paper_id}] *{title}*. bioRxiv, 2026. DOI: {doi}. "
        f"Preprint (not peer-reviewed). "
        f"Available at https://www.biorxiv.org/content/10.1101/{doi.split('/', 1)[1]}"
    )


def backfill_arxiv_paper(p3_doi: str, p2_doi: str) -> None:
    path = REPO / "docs" / "arxiv_paper.md"
    text = path.read_text(encoding="utf-8")
    block = REFS_BLOCK_TEMPLATE.format(
        p3_cite=format_cite("P-3", "Four Disciplines for Self-Verification in Computational Experiments", p3_doi),
        p2_cite=format_cite("P-2", "Preregistered Rejection as a First-Class Negative Result", p2_doi),
    )
    # Anchor: insert just before the horizontal rule preceding any future section.
    marker = "\n\n---\n\n"
    if marker in text:
        text = text.replace(marker, "\n" + block + marker, 1)
    else:
        text = text.rstrip() + "\n\n" + block
    path.write_text(text, encoding="utf-8")


def bump_versions() -> list[str]:
    changed = []
    for rel in VERSION_FILES:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if OLD_VERSION not in text:
            continue
        # Only touch version-shaped matches, not prose references.
        new_text = re.sub(
            rf'(?<![A-Za-z0-9]){re.escape(OLD_VERSION)}(?![A-Za-z0-9])',
            NEW_VERSION,
            text,
        )
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(str(rel))
    return changed


def append_changelog(p3_doi: str, p2_doi: str) -> None:
    path = REPO / "CHANGELOG.md"
    entry = f"""## v{NEW_VERSION} — {date.today().isoformat()}

**A-leg preprints published on bioRxiv** (post-arXiv-endorsement-block fallback).

- P-3 "Four Disciplines for Self-Verification in Computational Experiments"
  → bioRxiv DOI: {p3_doi}
- P-2 "Preregistered Rejection as a First-Class Negative Result"
  → bioRxiv DOI: {p2_doi}

**Context**: arXiv's 2026-01-21 endorsement-policy tightening made all categories
endorsement-gated for first-time submitters. bioRxiv (same 0-yuan, no-endorsement,
24-72h DOI pipeline) was used as the fallback preprint venue. Repository, gates,
and catch-rate numbers are unchanged from v{OLD_VERSION}.

"""
    text = path.read_text(encoding="utf-8")
    # Insert after the "# Changelog" or "## ..." header
    for anchor in ("# Changelog\n", "# CHANGELOG\n"):
        if text.startswith(anchor):
            text = text.replace(anchor, anchor + "\n" + entry, 1)
            break
    else:
        text = entry + "\n" + text
    path.write_text(text, encoding="utf-8")


def update_sci_verdict(p3_doi: str, p2_doi: str) -> None:
    path = REPO / "docs" / "SCI_VERDICT_2026-10-19.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    stamp = f"""

---

## Post-submission update ({date.today().isoformat()})

A-leg preprints now have public DOIs:

- P-3: {p3_doi}
- P-2: {p2_doi}

Both are on bioRxiv (arXiv blocked by 2026-01-21 endorsement policy).
G-NOW-2 (arXiv submit) is closed via bioRxiv fallback. Repository, gates,
versioning, and code availability unchanged at v{NEW_VERSION}.
"""
    text = text.rstrip() + stamp
    path.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("p3_doi", help="P-3 bioRxiv DOI (e.g. 10.1101/2610.123456)")
    ap.add_argument("p2_doi", help="P-2 bioRxiv DOI")
    ap.add_argument("--apply", action="store_true", help="Actually modify files (default: dry-run)")
    args = ap.parse_args()

    # Normalize: strip any leading "https://doi.org/" or "http://"
    for attr in ("p3_doi", "p2_doi"):
        v = getattr(args, attr)
        v = v.replace("https://doi.org/", "").replace("http://doi.org/", "")
        setattr(args, attr, v)

    print("=" * 60)
    print(f"Post-bioRxiv backfill — mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    print("=" * 60)
    print(f"P-3 DOI: {args.p3_doi}")
    print(f"P-2 DOI: {args.p2_doi}")

    for label, doi in (("P-3", args.p3_doi), ("P-2", args.p2_doi)):
        ok = doi_resolves(doi)
        mark = "OK " if ok else "WARN"
        print(f"  [{mark}] {label} resolves on doi.org: {ok}")
        if not ok:
            print(f"  NOTE: bioRxiv moderation may still be processing. DOI may not resolve for 24-72h after acceptance.")

    if not args.apply:
        print("\nDRY-RUN — no files modified. Re-run with --apply to write.")
        return 0

    # Actual changes
    backfill_arxiv_paper(args.p3_doi, args.p2_doi)
    changed = bump_versions()
    append_changelog(args.p3_doi, args.p2_doi)
    update_sci_verdict(args.p3_doi, args.p2_doi)

    print(f"\nModified files ({len(changed) + 3}):")
    for f in changed:
        print(f"  {f} (version bump {OLD_VERSION} → {NEW_VERSION})")
    print("  docs/arxiv_paper.md (added References §15)")
    print("  CHANGELOG.md (v" + NEW_VERSION + " entry)")
    print("  docs/SCI_VERDICT_2026-10-19.md (post-submission update)")

    print("\nNext steps (run these yourself):")
    print(f"  cd {REPO}")
    print("  python scripts/run_gates.py --quick")
    print("  python scripts/run_gates.py --with-data")
    print("  python scripts/gh_publish.py --all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
