# SCI Readiness Execution Report — 2026-10-18

**Version**: v2.98.0 (bumped from v2.97.0)
**Baseline**: `docs/SCI_READINESS_ASSESSMENT_2026-10-18.md`
**Scope**: Execute every S1–S4 task from the SCI readiness assessment, plus P3 follow-up. Reach arXiv-publishable level.

---

## 1. Task completion matrix

| # | Task | Deliverable | Verdict |
|---|---|---|---|
| P0 | Gate 60 AIBOM 门禁脱钩 | `scripts/check_supply_chain.py --regenerate` after bump | ✅ |
| P3 | P-4 决策 memo 引入 Xu 2026 引用 | `docs/PAPER_P4_CASE_STUDY.md` | ✅ |
| S1 | 外部验证队列预注册 PR-S1 | `docs/PR_S1_EXTERNAL_VALIDATION_2026-10-18.md` + `vault/S1.commit.json` | ✅ |
| S1 | 执行 C3/R6 到 3 个外部数据集 | `scripts/s1_external_validation.py` + `_s1_external_validation/results.json` | ✅ (PARTIAL) |
| S2 | 理论桥预注册 PR-S2 lesion cascade | `docs/PR_S2_LESION_CASCADE_2026-10-18.md` + `vault/S2.commit.json` | ✅ |
| S2 | 执行 lesion cascade 实验 | `scripts/s2_lesion_cascade.py` + `_s2_lesion_cascade/results.json` | ✅ (FAIL, honest) |
| S3 | 统计强化 — CI/p 值补齐 | `scripts/add_ci.py` + `research_claims.json.preregistered.*.ci_enrichment` | ✅ |
| S3 | P5 纪律有效性量化 | `scripts/s3_discipline_effectiveness.py` + `_s3_discipline_effectiveness/results.json` | ✅ |
| S4 | arXiv 投稿准备包（不真投） | `docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md` | ✅ |
| Final | 版本升级 + 门禁 + 推送 | v2.98.0, gates 58/58 PASS, 27 files pushed | ✅ |

---

## 2. Headline findings (all honest, no FAIL flipped to PASS)

| Item | Point estimate | CI / verdict |
|---|---|---|
| **S1 cross-species kappa** | n/a (dataset labels don't match internal) | verdict PARTIAL |
| **S2 lesion-cascade verdict** | FAIL | H1 relative improvement not met; H3 bridge prediction fails |
| **S3 gate catch-rate** | **47.1%** (16/34 injections) | Wilson 95% CI **[31.5%, 63.3%]** |
| **S3 gate coverage gaps** | 1 of 5 protocols ungated | `PR_S1` |
| **R1 isolation effect size** | 0.967 | Bootstrap 95% CI [0.900, 1.000] |
| **R2 transitivity-vs-density slope** | +0.906 | Bootstrap 95% CI [+0.213, +1.083] — **excludes 0** |
| **R4 hub_changed rate** | 0.560 | Wilson 95% CI [0.529, 0.591] |
| **C3 v2 AUC cells (all 15)** | 0.87–1.00 | Approx-normal CI [0.73–0.91, 1.00] |

**Two most defensible nuances**:
1. **R2 slope CI excludes 0** — transitivity does change with density, but the *behavioral* claim (GA≡random) still holds. The CI is on the *descriptive* statistic, not the *behavioral* metric.
2. **S3 catch-rate CI up to 63%** — 7 concrete gate weaknesses (W1–W7) enumerated. This is the "what we didn't do" section of the paper.

---

## 3. Files added/modified

### New (14 files)
- `scripts/s1_external_validation.py` — cross-species C3/R6 runner
- `scripts/s2_lesion_cascade.py` — MaleCNS subgraph progressive deletion
- `scripts/s3_discipline_effectiveness.py` — gate violation catch-rate
- `scripts/add_ci.py` — CI enrichment across all preregs
- `vault/S1.commit.json`, `vault/S2.commit.json` — E3 vault commits
- `_s1_external_validation/results.json`, `_s2_lesion_cascade/results.json`, `_s3_discipline_effectiveness/results.json`
- `docs/PR_S1_EXTERNAL_VALIDATION_2026-10-18.md`
- `docs/PR_S2_LESION_CASCADE_2026-10-18.md`
- `docs/S1_EXTERNAL_VALIDATION_2026-10-18.md`
- `docs/S2_LESION_CASCADE_2026-10-18.md`
- `docs/S3_DISCIPLINE_EFFECTIVENESS_2026-10-18.md`
- `docs/S3_STATISTICAL_STRENGTHENING_2026-10-18.md`
- `docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md`

### Modified (8 files)
- `pyproject.toml` (v2.98.0)
- `flybrain_cli.py` (`__version__ = "2.98.0"`)
- `flybrain-connectome-mcp/mcp_connectome/api_server.py` (version)
- `flybrain-connectome-mcp/mcp_connectome/server.py` (version)
- `README.md` (v2.98.0 features)
- `CHANGELOG.md` (v2.98.0 entry)
- `aibom.json` (regenerated)
- `research_claims.json` (CI enrichment + `meta.ci_enrichment_run_at`)
- `docs/PAPER_P4_CASE_STUDY.md` (Xu 2026 references + preregistered refusal paragraph)
- `registry/preregistered_rejections.json` (regenerated)

---

## 4. Gate results

```
Quick:         55/55 PASS
Quick+data:    56/56 PASS
Full:          58/58 PASS
```

Full gate battery includes:
- Gate 53 (preregistered rejection registry): PASS after `export_preregistration_registry.py` regen
- Gate 55 (holdout integrity): PASS after renaming vault PR_S1/PR_S2 → S1/S2 to match `research_claims.preregistered` keys
- Gate 58 (version consistency): PASS (7 places bumped)
- Gate 59 (static analysis): PASS
- Gate 60 (supply chain AIBOM): PASS after `check_supply_chain.py --regenerate`

---

## 5. What this round proves

1. **S1: cross-species generalization is not automatic.** 3/3 external datasets load, internal 5 families pass C3, but external 3 families AUC are low → honest PARTIAL verdict. The project does not overclaim cross-species.

2. **S2: preregistration has real value.** The lesion-cascade verdict is FAIL. Under informal practice, "we got some local improvement on some subgraph" would be a positive result. Pre-registration with three explicit hypotheses (H1 relative improvement, H2 bootstrap p, H3 bridge lesion correlation) made the negative result undeniable.

3. **S3: gates are not free.** 47.1% catch-rate on 34 injections. The gate catches what we taught it to catch and misses silent-field mutations and verdict-only flips. Seven concrete weaknesses are enumerated. This is publishable honesty, not marketing.

4. **S3 statistical strengthening: every positive claim now has a CI.** R1/R2/R4/C3/S1/S2/S3 all carry `ci_enrichment` in `research_claims.json`. The R2 slope CI excludes zero — a small honest nuance that the paper registers explicitly rather than hiding.

5. **Xu 2026 provides external theoretical anchor.** P-4 updated to cite Xu et al. (2026) *Science* as the external support for the preregistration discipline (silent components carry mechanistic information → treating silence as mechanism-relevant is the S8 discipline).

---

## 6. Publication readiness (post-execution)

| Paper | Status | Ready to submit? |
|---|---|---|
| **P-2** Preregistered Rejection | v1.2 (PAPER_P4 updated with Xu 2026) | ✅ Yes, with submission package |
| **P-3** Four Disciplines | v1.3 (S3 statistical strengthening + discipline effectiveness folded into §7) | ✅ Yes, with submission package |
| **P-1** Main line | v1.2 (unchanged) | ❌ Still blocked on D1 mechanism + D3 repo public |
| **S3 appendix** | Folded into P-3 §7 | Folded, not standalone |

`docs/ARXIV_SUBMISSION_PACKAGE_2026-10-18.md` contains the complete `submission_meta.json` (title, subtitle, authors, abstract ≤2000 chars, primary subject, cross-lists, comments, license, code URL, category justification, related-work differentiation vs `arXiv:2609.17637` RAGWarrant and `arXiv:2608.09855` grey-box fuzzer, cover letter, submission checklist).

**The user decides when to press submit.** Nothing has been pushed to arXiv.

---

## 7. Known limitations (transparent)

- **S1 external kappa is null** — the internal family labels don't match external dataset labels; kappa could not be computed. Registered honestly as `n/a`.
- **S2 individual-hypothesis slope CIs not computed** — S2 is FAIL at the aggregate level; per-hypothesis CIs would be negative-result material. Deferred.
- **C3 AUC p-values not computed** — approximate-normal CI used instead; full permutation test deferred (would require >5000 shuffles × 15 cells).
- **7 gate weaknesses (W1–W7) not fixed in this round** — enumerated in `S3_DISCIPLINE_EFFECTIVENESS_2026-10-18.md`. Priority order documented for next round.
- **D3 repo public still pending** — arXiv submission package uses `Code available at lm203688/flybrain-connectome` (assumes public). If not yet public, substitute `Code will be made publicly available upon acceptance`.

---

## 8. Reproduce commands

```bash
# Version
python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"

# Gates
python scripts/run_gates.py --quick                    # 55/55
python scripts/run_gates.py --quick --with-data        # 56/56
python scripts/run_gates.py                            # 58/58

# S1 external validation
python scripts/s1_external_validation.py --datasets cel,larva,zebrafish --n-nodes 10,20 --seeds 15 --bootstrap 200

# S2 lesion cascade
python scripts/s2_lesion_cascade.py --n-nodes 20,50,100 --seeds 60 --bootstrap 500

# S3 discipline effectiveness
python scripts/s3_discipline_effectiveness.py --repeats 3 --seed 42

# S3 CI enrichment
python scripts/add_ci.py

# AIBOM regen (after version bump)
python scripts/check_supply_chain.py --regenerate

# Registry regen (after research_claims change)
python scripts/export_preregistration_registry.py
```

---

## 9. Final status

- Version: **v2.98.0**
- Git commit: `07236bd feat(v2.98.0): S1/S2/S3 statistical strengthening + arXiv submission package`
- Files pushed to `lm203688/flybrain-connectome` master: 27 (via Contents API, individual per-file)
- Gates: 58/58 PASS
- Publication ready: P-2 ✅, P-3 ✅ (both with submission_meta.json + related-work + cover letter)
- Still pending (user decision): press submit on arXiv, and D3 repo-public decision for P-1

---

*Execution completed 2026-10-18. All S1–S4 tasks done; P3 done; final packaging done.*
