# Contributing to flybrain-connectome

Thank you. The bar is deliberately high on this repo — this is a scientific
artifact, not a demo — so a well-scoped contribution matters more than volume.

## Scope of contributions welcome

- **Bugs** — reproducible, minimal, with a failing assertion.
- **New connectome-derived units** — following the extraction contract in
  `scripts/extract_cel_profiles.py` / `scripts/extract_larva_profiles.py`.
- **New functional units** — must earn their `jev_verdict` and their
  evidence-weight axis (see `PROJECT_VISION.md`).
- **Documentation** — honest boundaries, method caveats, worked examples.
- **Tests and gate additions** — one gate per claim.

## What we will not accept

- **Silent numerical changes** in a shipped metric without a documented audit
  (see the CHANGELOG convention in `CHANGELOG.md`).
- **New third-party runtime dependencies** without justification. The toolkit
  is deliberately standard-library-first.
- **Data commits** — the MaleCNS / worm / larva datasets are never committed.
  Only derived JSON artifacts are, and only small enough to review in a PR.
- **Secrets, tokens, or credentials** — enforced by Gate 1 and detect-secrets.

## Getting started

```bash
git clone https://github.com/lm203688/flybrain-connectome.git
cd flybrain-connectome
make setup          # creates .venv, installs dev deps
make gates          # offline gates, CI-equivalent
```

If you have a local MaleCNS v1.0 checkout (~5.63 GB):

```bash
export FLYBRAIN_DATA_DIR=/path/to/male_cns
make gates-data
```

## Branching and commits

- Branch from `main`. One branch per logical change.
- Commit messages follow the pattern in the recent history:
  `vX.Y.Z: <short summary> — <measured outcome>` (see `CHANGELOG.md`).
- Every version bump must update the version string in:
  1. `pyproject.toml`
  2. `CHANGELOG.md` (prepend a new section)
  3. The README version banner if shown
  4. Any hardcoded count (Gate 9 count, module count, etc.)

## Versioning

Follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).
Schema versions are tracked separately in the CHANGELOG header table.

## The four moats are measured, not marketed

Before adding a claim to `README.md` or `PROJECT_VISION.md`, ask: is there a
script under `scripts/` that reproduces it end-to-end? If not, either build
the script first, or don't claim it. This has been the maintainer's default
for four consecutive versions — two "obvious" advantages were dropped after
experiments showed 0/7 and 0/24.

## Code style

- Python 3.10+. `ruff` and `black` run on every commit via pre-commit.
- Type hints where cheap; no strict mode yet (see `pyproject.toml`).
- Docstrings in English, matching the existing style.
- Every new gate must fail-closed and have a documented mutation test.

## Submitting a PR

1. Update `CHANGELOG.md` with your version bump.
2. Update README counts if you changed the shipped library size.
3. `make gates` must be green before you open the PR.
4. If you added a gate, add a CHANGELOG entry that explains why the gate
   exists (what defect would it have caught?) — every gate in this repo
   has one.

## Communication

- **Issues** — bug reports, feature proposals, questions.
- **PRs** — changes. Please keep PR descriptions short but include a
  reproduction for any behavior change.

## License

By contributing you agree your contributions are MIT-licensed and that any
dataset-derived artifact you add is provenance-tagged per the license clause
in `LICENSE-CLAUSE.md`.
