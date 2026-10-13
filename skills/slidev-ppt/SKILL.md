---
name: slidev-ppt
description: "Create and export beautiful HTML slides with Slidev. Works with existing repo files OR by initializing a new Slidev project from scratch; exports to PDF and/or PPTX."
homepage: https://sli.dev/
install:
  npm: ["playwright"]
  python: ["PyMuPDF"]
---

# Slidev

Create, run, and export HTML presentations with Slidev (https://sli.dev/).

## Capabilities

1. **Existing project** — when the user already has a Slidev repo (`package.json` + `slides.md`): edit `.md` slides, then export.
2. **New project from scratch** — when there is no repo, init a fresh Slidev project locally (`npx degit antfu/slidev`) and create the slides there.
3. **Export** — from Markdown / HTML to **PDF** and **PPTX**.

## Quick start

### Existing project

```bash
nvm use          # if available
npm install
npx slidev --port 3000
npx slidev export -p 3000 -f pdf
npx slidev export -p 3000 -f pptx
```

### New project (no existing repo)

```bash
npx degit antfu/slidev my-presentation   # interactive scaffold
cd my-presentation
npm install
# create slides.md, then:
npx slidev --port 3000
npx slidev export -p 3000 -f pdf
npx slidev export -p 3000 -f pptx
```

If `degit` is blocked, fetch the template files directly from GitHub (`main` branch) and place them in the new directory.

## Markdown workflow

1. Ensure dependencies (`npm install`).
2. Check `package.json`, `slides.md`, `netlify.toml`.
3. Start dev server (`npx slidev --port 3000`) and check the page title.
4. Read current slides, edit/insert, run checks: `node scripts/check.mjs` and `npm run typecheck`.
5. Re-render, verify visual changes, update `netlify.toml` title.
6. Commit and push if a repo is configured.

## Key reference

- CLI: https://sli.dev/reference/cli
- Export: https://sli.dev/guide/exporting
- Config: https://sli.dev/reference/config
- Slides/Markdown: https://sli.dev/guide/syntax/slides
- Layouts: https://sli.dev/guide/syntax/layouts
- Animations: https://sli.dev/guide/animations
- Theme dev: https://sli.dev/wondering/how-to-develop-my-own-theme
