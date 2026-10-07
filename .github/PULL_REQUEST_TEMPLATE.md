---
name: Pull request
about: Submit a change
labels: ["needs-review"]
---

## What this PR does

<!-- One paragraph. Not the commit log; the intent. -->

## Which gate(s) this proves

<!-- Pick at least one. This repo has 10+ gates; the CHANGELOG explains each. -->

- [ ] Gate 1 — no hardcoded credentials
- [ ] Gate 2 — docs match code
- [ ] Gate 3 — every advertised MCP tool responds
- [ ] Gate 4 — optional dependency absent degrades honestly
- [ ] Gate 5 — generated artifact is structurally real
- [ ] Gate 6 — Phase 4/5/6 features (variants + SwarmLabs + market)
- [ ] Gate 7 — module architecture (neuropil + worm + combinator + HMAC)
- [ ] Gate 8 — physical tiering (public MIT vs private Tier-2)
- [ ] Gate 9 — unit library (units + connection types + composer)
- [ ] Gate 10 — embodiment (anchors + matrices + contradictions)
- [ ] Gate 11 — function coverage axis
- [ ] Gate 12 — connection cost axis
- [ ] Gate 13 — composition semantics

## Verification

```bash
# Paste the exact commands you ran locally.
python scripts/run_gates.py
# or, with a MaleCNS checkout:
python scripts/run_gates.py --with-data
```

## Version bump

- [ ] `pyproject.toml` version bumped
- [ ] `CHANGELOG.md` updated
- [ ] README counts updated (if the shipped library size changed)

## Honesty check

- [ ] I have not added a claim that a gate cannot reproduce
- [ ] Any new number in the CHANGELOG is measured, not estimated
- [ ] I have not introduced a new runtime dependency
