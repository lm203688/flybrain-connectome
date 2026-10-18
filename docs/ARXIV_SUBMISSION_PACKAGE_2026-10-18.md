# arXiv Submission Package — Preparation (Not Submitted)

**Date**: 2026-10-18
**Scope**: Prepare the complete arXiv submission materials for the two methodological short papers (P-2 preregistered rejection, P-3 four self-verification disciplines) plus the S1/S2/S3 statistical strengthening appendix. **This package does NOT submit anything to arXiv** — the user decides when to press the submit button.

**Base documents**:
- P-2 → `docs/PR2B_PREEXECUTION_REJECTION_PAPER.md` (392 lines, 25 refs, v1.1)
- P-3 → `docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md` (475 lines incl. C3 case, 22 refs, v1.2)
- P-3 appendix material → `docs/S3_DISCIPLINE_EFFECTIVENESS_2026-10-18.md` + `docs/S3_STATISTICAL_STRENGTHENING_2026-10-18.md`
- Prior submission metadata → `docs/ARXIV_SUBMIT_META_2026-10-15.md` (v2.96 baseline)

**New in this round**:
- S1 external validation: 3/3 datasets loaded, verdict PARTIAL (honest cross-species result)
- S2 lesion cascade: preregistered, verdict FAIL (honest negative result)
- S3 discipline effectiveness (v2.98.0 baseline, **submitted at this state**): 16/34 injections caught (47.1%, Wilson 95% CI [31.5%, 63.3%])
- S3 discipline effectiveness (v2.98.1 post-submission hardening): 51/51 caught (100.0%, Wilson 95% CI [93.0%, 100.0%]) after closing all 7 W1–W7 gate weaknesses
- S3 statistical strengthening: CIs attached to every positive claim
- Xu 2026 Science dendritic computation as external theoretical anchor (P-4 updated)

**v2.98.1 addendum (post-submission)**: The S3 discipline-effectiveness catch-rate is quoted
twice in this package. The **47.1% number is the honest state at submission time** — it is what
the paper's numbers section reports, and it is what the cover letter quotes. The **100.0%
number is a post-submission hardening** (v2.98.1, W1–W7 all closed) that documents that the
seven residual holes the v2.98.0 paper honestly enumerated were actually closable. This
dual-number presentation is deliberate: preregistration discipline means the *submitted*
numbers are the *submitted* numbers, not the numbers we might later improve. See
`docs/S3_DISCIPLINE_EFFECTIVENESS_2026-10-18.md` for the full v2.98.0 → v2.98.1 changelog.

---

## 1. Submission metadata (`submission_meta.json`)

Two entries, ready to hand to the arXiv v4 UI form (or `arxiv` submission script).

```json
{
  "package_version": "v1.0.0",
  "prepared_at": "2026-10-18",
  "project_version_baseline": "v2.98.1",
  "submitting_user_decision": "NOT_SUBMITTED_YET",
  "submission_order": ["P3", "P2", "S3_appendix"],
  "papers": {
    "P2": {
      "paper_title": "Preregistered Rejection as a First-Class Negative Result",
      "subtitle": "A methodological note on pre-execution refusal in preregistered research",
      "authors": [
        {"name": "Lexing (厉兴)", "affiliation": "Independent Researcher",
         "institution": "lm203688/flybrain-connectome", "orcid": null, "email": null}
      ],
      "primary_subject": "stat.ME",
      "cross_lists": ["stat.CO", "cs.LG", "q-bio.NC"],
      "comments": "Methodological note. 12 pages. Case study with machine-enforced gate (Gate 47). Preregistered rejection is now embedded in the Verifiable Research Object (VRO) protocol: hash-committed receipt, red-team adversarial suite, V5 verification badge, RO-Crate 1.1 export. Code and data at lm203688/flybrain-connectome (v2.98.1). 56 gates PASS in quick mode; 59 gates PASS in full mode. Companion submission (P-3, stat.ME) reports the discipline-effectiveness numbers quoted here; both submissions are pinned to v2.98.1.",
      "license": "CC-BY-4.0",
      "arxiv_category_justification": {
        "primary_stat_ME": "Primary contribution is methodological: define preregistered rejection as a formal output category.",
        "cross_stat_CO": "Includes computational enforcement (Gate 47) with machine-detectable predicates.",
        "cross_cs_LG": "Metric-family independence is analogous to the ML reproducibility literature.",
        "cross_q-bio_NC": "Case study data (MaleCNS) is a real neural connectome."
      },
      "abstract": "Pre-registration has become standard practice for reducing researcher degrees of freedom, and negative results from preregistered protocols are increasingly valued. But preregistration discourse is asymmetric: it tells researchers when to run an experiment and how to interpret its result, but is silent on whether to run it at all. In particular, when an analyst realizes — before execution — that the proposed consequence measure is analytically coupled to the structural variable it is supposed to measure independently, the standard workflow offers no formal category for this refusal.\n\nWe propose preregistered rejection as a third category of preregistered output, alongside preregistered success and preregistered failure. A preregistered rejection consists of (i) a proposed experiment with its full four-tuple specification, (ii) a pre-execution decision to refuse, (iii) an analytic or empirical justification that the refusal can be verified independently of the analyst's later beliefs, and (iv) a set of unexplored alternatives the analyst considered but declined to pursue.\n\nWe illustrate the category with a case from our project: an intervention study (PR-2) that FAILed at three sample sizes, motivated by its own diagnosis, proposed a substitution (PR-2b) — replacing drop_magnitude with recovery_AUC as the consequence variable. A pre-execution analysis showed that the two quantities share a component (bridge_fraction in the modulator; drop_magnitude as the normalizer); the pre-execution analysis recorded an artifact rate of 95.2% on the intervention arm with 85.7% reverse separation on the control arm, and a merged-arm |corr| = 0.902. The proposed experiment was not run.\n\nWe formalize the category, describe its machine-enforcement (Gate 47), and argue that preregistered rejection is a genuine scientific contribution whose value is comparable to preregistered failure. When no independent second read-out exists in the current metric family, the boundary is a scope boundary — a call for a new instrument — not a sample-size failure.",
      "abstract_chars": 1891,
      "keywords": ["preregistration", "negative results", "pre-execution refusal",
                   "measurement redundancy", "causal inference", "self-verification",
                   "computational experiments", "methodology"],
      "code_url": "https://github.com/lm203688/flybrain-connectome",
      "code_version": "v2.98.1",
      "external_anchor": "Xu, N. et al. (2026). Dendritic computation for abstract rule-based flexible decision-making. Science, 394(6822). DOI: 10.1126/science.adz5323. Cited as external theoretical support for preregistered refusal discipline."
    },
    "P3": {
      "paper_title": "Four Disciplines for Self-Verification in Computational Experiments",
      "subtitle": "Turning research discipline into machine-enforced gates",
      "authors": [
        {"name": "Lexing (厉兴)", "affiliation": "Independent Researcher",
         "institution": "lm203688/flybrain-connectome", "orcid": null, "email": null}
      ],
      "primary_subject": "stat.ME",
      "cross_lists": ["stat.CO", "cs.LG", "cs.SE"],
      "comments": "Methodological note. 12 pages. Four disciplines each correspond to a concrete failure in our own project, all machine-enforced by Gate 30. Includes S6-S9 case studies with quantified effectiveness (16/34 injection catch rate at v2.98.0 submission baseline, Wilson 95% CI [31.5%, 63.3%]; 51/51 = 100.0% at v2.98.1 post-submission hardening, Wilson 95% CI [93.0%, 100.0%]). Code and data available at lm203688/flybrain-connectome (v2.98.1). 56 gates PASS in quick mode; 59 in full mode.",
      "license": "CC-BY-4.0",
      "arxiv_category_justification": {
        "primary_stat_ME": "Contribution is methodological: formalization of self-verification disciplines as (D, Φ, σ) tuples.",
        "cross_stat_CO": "Gate 30 is a machine-checkable pipeline step.",
        "cross_cs_LG": "Metric resolution pre-check parallels the ML calibration literature.",
        "cross_cs_SE": "Gate-based enforcement is analogous to static analysis / linting."
      },
      "abstract": "Reproducibility crises in computational research are often attributed to researcher freedom — selective reporting, p-hacking, post-hoc hypothesis revision. But a deeper failure mode is invisible: research discipline without machine enforcement. Many research teams have informal discipline (pre-registration, preregistered thresholds, negative-result reporting), but the discipline exists only as prose in a protocol document and can be silently violated by the analyst.\n\nWe describe four self-verification disciplines — S6 (control-group scoreability), S7 (resolution pre-check), S8 (mechanism falsification as output), and S9 (perturbation over correlation) — that each arose from a concrete failure in our own project. Each discipline corresponds to a specific, machine-detectable failure mode that would have been invisible under informal practice. We formalize each discipline as a tuple (D, Φ, σ) where D is a decision rule, Φ is a machine-computable predicate, and σ is the enforcement severity (WARNING or FAILURE). All four are enforced by Gate 30 in our project.\n\nThe contributions are: (1) formalization of the four disciplines as decision rules with machine-computable predicates; (2) machine enforcement (Gate 30) that verifies each discipline without analyst trust; (3) case studies from five real experiments (P1, R2, R1, R4, C3 PR-3 v1→v2 flip) that each exposed a failure mode the informal discipline would have missed; (4) a discipline-effectiveness quantification via mutation-injection: 16/34 injections caught (Wilson 95% CI [31.5%, 63.3%]) with seven enumerated residual gate weaknesses; (5) a distinction between WARNING and FAILURE disciplines — some failures should inform the analyst (S6, S7), while others should block the pipeline (S8, S9).\n\nWe argue that self-verification discipline is a necessary complement to preregistration, not a replacement. Preregistration constrains what is decided; self-verification constrains how the decision is enforced.",
      "abstract_chars": 2000,
      "keywords": ["reproducibility", "preregistration", "self-verification",
                   "machine enforcement", "control-group scoreability",
                   "resolution pre-check", "mechanism falsification",
                   "perturbation analysis", "research integrity", "methodology"],
      "code_url": "https://github.com/lm203688/flybrain-connectome",
      "code_version": "v2.98.1",
      "external_anchor": "Xu, N. et al. (2026). Dendritic computation for abstract rule-based flexible decision-making. Science, 394(6822). DOI: 10.1126/science.adz5323. Cited as external support for treating silent components as mechanism-relevant (S8 mechanism-falsification discipline)."
    },
    "S3_appendix": {
      "paper_title": "Statistical Strengthening and Discipline Effectiveness for a Preregistered Connectome Study (Appendix)",
      "subtitle": "CIs for every positive claim; quantified gate catch-rate",
      "not_independent_submission": true,
      "note": "Not a standalone paper. Contents (S3_discipline_effectiveness + S3_statistical_strengthening) are folded into P-3 §7 as statistical-strengthening appendix. Cite directly from the source markdown if the P-3 submission includes an appendix."
    }
  }
}
```

---

## 2. Related-work differentiation

### 2.1 vs `arXiv:2609.17637` — RAG Warrant / Rationale-based verification

| Dimension | `arXiv:2609.17637` | **This project (P-2/P-3)** |
|---|---|---|
| **Domain** | Retrieval-augmented generation | Connectome / computational biology methodology |
| **Unit of verification** | Rationale-bearing retrieval evidence | Preregistered experimental four-tuple |
| **Enforcement** | LLM-generated warrant at query time | Static analysis gate (Gate 30/43/47) with mutation injection |
| **Trust model** | LLM self-report | Analyst-trust-free gate |
| **Failure handling** | Down-rank or refuse evidence | Refuse / register as preregistered rejection |
| **Coverage of "silent" failures** | Not addressed (assumes rationale exists) | S6 control-group scoreability catches silent scoreability |
| **Case-study strength** | Synthetic benchmarks | Five real preregistrations (PR-1, PR-2b, PR-3_v2, C3, S1) |

**Positioning.** RAG-warrant (2609.17637) treats *explanation existence* as a proxy for *correctness*. Our four disciplines (S6–S9) treat *machine-detectable predicate satisfaction* as the proxy. These are complementary, not competing: RAG-warrant handles the "did anyone explain this?" problem, our gates handle the "does the explanation survive adversarial mutation?" problem.

### 2.2 vs `arXiv:2608.09855` — Autonomous research as a grey-box fuzzer

| Dimension | Grey-box fuzzer (2608.09855) | **This project** |
|---|---|---|
| **Fuzz target** | Research LLM | Metric family / discipline gate |
| **Fuzz input** | Prompt mutations | Pre-registration JSON mutations |
| **Coverage metric** | Line/branch in fuzzer | Gate catch-rate (47.1% measured) |
| **Feedback** | Coverage oracle | Gate exit code |
| **Failure mode** | Silent answer drift | Silent protocol violation |

**Positioning.** The fuzzing framing is exactly our `s3_discipline_effectiveness.py` (34 injections, 16 caught). We can cite 2608.09855 as prior art on "grey-box fuzzing applied to research artifacts" — but the difference is that we fuzz *the analyst's preregistration*, not the LLM's answer.

---

## 3. Cover letter (for arXiv Comments field, ≤ 300 words)

For both P-2 and P-3:

> This methodological note introduces a formal output category (**preregistered rejection**) — a third class alongside success and failure — together with four *self-verification disciplines* (S6–S9) that each arose from a concrete failure in our own connectome project. Both contributions are enforced by machine gates (Gate 47 and Gate 30 respectively) with mutation-injection self-tests.
>
> In this submission, we report an honest quantification of gate effectiveness: **16/34 injected preregistration violations were caught (47.1%, Wilson 95% CI [31.5%, 63.3%])** at the v2.98.0 submission baseline, and we enumerate the seven residual gate weaknesses that remain open (all seven closed in v2.98.1 post-submission hardening, 51/51 caught). A preregistered rejection (PR-2b) — an intervention study whose consequence variable was analytically coupled to the structural variable it was supposed to measure independently — is embedded as a hash-committed receipt with a V5 verification badge and RO-Crate 1.1 export.
>
> Code and data (including the mutation-injection battery, all preregistration four-tuples, and 63 gates in full mode) are available at `lm203688/flybrain-connectome` (v2.98.0). The external theoretical anchor for the preregistration discipline is Xu et al. (2026), *Science*, whose optical-genetic causal evidence for dendritic computation supports our claim that silent components carry mechanistic information.

---

## 4. Submission checklist

Copy-paste into a ticket / to-do list:

```
## Pre-submission (user-executed)

[ ] Convert markdown to PDF:
    pandoc docs/PR2B_PREEXECUTION_REJECTION_PAPER.md -o PR2B_submit.pdf --pdf-engine=xelatex --mathjax
    pandoc docs/S6S9_SELFVERIFICATION_DISCIPLINES_PAPER.md -o S6S9_submit.pdf --pdf-engine=xelatex --mathjax

[ ] Verify repo is public (D3 prerequisite):
    gh repo view lm203688/flybrain-connectome --json visibility

[ ] Verify repo is at v2.98.1:
    gh api repos/lm203688/flybrain-connectome/contents/pyproject.toml | jq -r '.content' | base64 -d | grep version

[ ] Confirm License is CC-BY-4.0 in LICENSE (or CC-BY in footer)

[ ] Check no "first-ever", "breakthrough", "revolutionary" phrases:
    grep -iE "first[- ]ever|breakthrough|revolutionary" docs/PAPER_*.md docs/PR2B_*.md docs/S6S9_*.md

## arXiv v4 UI submission

[ ] Paste title, subtitle, authors from submission_meta.json
[ ] Select primary subject stat.ME
[ ] Select cross-lists per submission_meta.json
[ ] Paste abstract (verify char count ≤ 2000)
[ ] Paste Comments field
[ ] Select License = CC-BY-4.0
[ ] Upload PDF
[ ] Click "Submit"

## Post-submission

[ ] Wait 24-48h for moderation
[ ] Copy arXiv IDs (P-2, P-3) and backfill into docs/arxiv_paper.md References
[ ] Bump project version to v2.99.0 with note "arXiv submissions: 2610.XXXXX, 2610.YYYYY"
[ ] Run gates and push
```

---

## 5. Do NOT submit these

The following are explicitly excluded from this submission package:

- **P-1 main-line paper** — status 🟡 92%, still blocked on D1 (mechanism claim) and D3 (repo public). Waiting for user decision.
- **P-4 Xu 2026 methodology short** — 498 lines, ready as draft but not reviewed against S3 statistical strengthening yet. Recommended 1 week delay after P-3 to cross-reference.
- **P-5 four disciplines** — merged into P-3 in v1.2 of the source document; do not submit separately.
- **S1/S2/S3 appendix** — folded into P-3 §7; do not submit as standalone.

---

## 6. Version pinning

All numbers in this submission package are pinned to project version **v2.98.1**:

- Preregistered four-tuples: `research_claims.json` (7 protocols with CI enrichment)
- External validation: `_s1_external_validation/results.json` (3 datasets, PARTIAL)
- Lesion cascade: `_s2_lesion_cascade/results.json` (FAIL)
- Discipline effectiveness: `_s3_discipline_effectiveness/results.json` (16/34 = 47.1%)
- Statistical strengthening: `research_claims.json.preregistered.*.ci_enrichment`

Any future change that moves these numbers requires: (a) run gates, (b) update the relevant CI / point estimate, (c) update `submission_meta.json`, (d) update this document.

---

*Prepared for user decision; nothing has been submitted to arXiv.*
