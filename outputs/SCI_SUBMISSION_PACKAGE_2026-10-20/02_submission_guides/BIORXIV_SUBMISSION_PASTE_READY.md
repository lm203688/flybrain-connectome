# bioRxiv Submission — Paste-Ready Metadata

**Prepared for user manual submission on 2026-10-20 (updated 2026-10-24)**

Two papers to submit in order: **P-3 first**, then P-2.

- P-3 PDF: `P3_submit.pdf` (523 KB, 18 pages)
- P-2 PDF: `P2_submit.pdf` (434 KB, 16 pages)

Instructions in `docs/A_LEG_ARXIV_SUBMISSION_GUIDE_2026-10-19.md` (§ adapted below).

---

## Pre-submission 5-Step Checklist

**Tick all 5 before clicking "Submit".** Estimated total: 20 minutes.

- [ ] **1. Compile the PDFs locally**
  - Install Tectonic: `winget install tactiq.Tectonic`
  - Build P-3: `cd outputs/SCI_SUBMISSION_PACKAGE_2026-10-20/06_latex_manuscript/p3_selfverification && tectonic p3_selfverification.tex`
  - Build P-2 (P4 in our internal naming): `cd .../p4_prereject && tectonic p4_prereject.tex`
  - Verify PDFs look correct (open both, check figures render, references list is populated)
  - Copy the resulting `.pdf` files to `P3_submit.pdf` and `P2_submit.pdf` at the repo root
- [ ] **2. Verify author identity consistency**
  - ORCID: `0000-0002-8747-1969` (Li Xing / 李星)
  - Given name: `Xing` · Family name: `Li`
  - Email: `xingli1123@outlook.com`
  - Affiliation: `Independent Researcher, Shenzhen, China`
  - Confirm PDF front matter matches (open the PDFs, first page)
- [ ] **3. Verify repository URL is public**
  - Visit https://github.com/lm203688/flybrain-connectome
  - Should load without login (verify by opening in incognito)
  - The README should show "PUBLIC since 2026-10-18"
- [ ] **4. Log into bioRxiv**
  - Homepage https://www.biorxiv.org/ → click `SIGN UP` in top-right
  - (Or SIGN IN if you already have an account)
  - Confirm you see your profile name after login
- [ ] **5. Sanity check the PDFs one more time**
  - Open P3_submit.pdf → verify title, author, abstract all correct
  - Open P2_submit.pdf → verify title, author, abstract all correct
  - Verify no placeholder text like `TODO`, `<insert>`, `XXX`
  - Verify all citations resolve (no `[?]` or empty reference numbers)

**If any checkbox fails, fix it before proceeding. bioRxiv keeps ALL versions public — you can only mark as "withdrawn", not delete.**

---

## Step 0 — Account

**Do NOT go to `/login` directly** — the signup link is not there.

- Go to the **homepage**: https://www.biorxiv.org/
- Click **`SIGN UP`** in the top-right corner (next to SIGN IN).
- Alternative URL if the button is not visible: https://www.biorxiv.org/registration
- Registration takes ~1 minute: name + email + password + affiliation + reCAPTCHA.
- No endorsement required. No institutional email needed (independent researcher is fine).
- After signup you are logged in and can click "Submit Manuscript" immediately.

Common gotchas:
- Google reCAPTCHA blocked → use Chrome incognito or a different browser
- Country field → select "China" or "Hong Kong SAR"
- If you already have a bioRxiv account → just SIGN IN, skip signup

---

## Step 1 — Submit P-3

After logging in, click **"Submit Manuscript"** → follow the 8-page wizard.

### 1.1 Title

```
Four Disciplines for Self-Verification in Computational Experiments
```

### 1.2 Authors

Only you. Fill in:
- **Given name**: Xing
- **Family name**: Li
- **Affiliation**: Independent Researcher, Shenzhen, China
- **Email**: xingli1123@outlook.com
- **ORCID**: 0000-0002-8747-1969

### 1.3 Abstract (paste this exactly)

```
Reproducibility crises in computational research are often attributed to researcher freedom — selective reporting, p-hacking, post-hoc hypothesis revision. But a deeper failure mode is invisible: research discipline without machine enforcement. Many research teams have informal discipline (pre-registration, preregistered thresholds, negative-result reporting), but the discipline exists only as prose in a protocol document and can be silently violated by the analyst.

We describe four self-verification disciplines — S6 (control-group scoreability), S7 (resolution pre-check), S8 (mechanism falsification as output), and S9 (perturbation over correlation) — that each arose from a concrete failure in our own project. Each discipline corresponds to a specific, machine-detectable failure mode that would have been invisible under informal practice. We formalize each discipline as a tuple (D, Φ, σ) where D is a decision rule, Φ is a machine-computable predicate, and σ is the enforcement severity (WARNING or FAILURE). All four are enforced by Gate 30 in our project.

The contributions are: (1) formalization of the four disciplines as decision rules with machine-computable predicates; (2) machine enforcement (Gate 30) that verifies each discipline without analyst trust; (3) case studies from five real experiments (P1, R2, R1, R4, C3 PR-3 v1→v2 flip) that each exposed a failure mode the informal discipline would have missed; (4) a discipline-effectiveness quantification via mutation-injection: 16/34 injections caught at the v2.98.0 submission baseline (Wilson 95% CI [31.5%, 63.3%]), with seven enumerated residual gate weaknesses closed in v2.98.1 (51/51 = 100.0%, Wilson 95% CI [93.0%, 100.0%]); (5) a distinction between WARNING and FAILURE disciplines — some failures should inform the analyst (S6, S7), while others should block the pipeline (S8, S9).

We argue that self-verification discipline is a necessary complement to preregistration, not a replacement. Preregistration constrains what is decided; self-verification constrains how the decision is enforced. The two together form the operational backbone of a verifiable research object. Code and preregistration data are publicly available at github.com/lm203688/flybrain-connectome (v2.98.1).
```

**Character count**: ~2050 (bioRxiv limit: 2000 chars — if it complains, remove the last sentence "Code and preregistration data..." — saves 130 chars).

### 1.4 Subject Areas

Select **one primary** + up to 3 cross-lists.

**Primary** (required):
- ✓ **Scientific Communication and Education** — the paper is about research methodology / integrity

**Cross-lists** (optional, pick up to 3):
- ✓ **Neuroscience** (case studies use a real Drosophila connectome)
- ✓ **Bioinformatics** (method is applied to connectomics)
- ✓ **Systems Biology** (methodology for computational experiments)

If only ONE is allowed, choose **Scientific Communication and Education** — that's where methodology/integrity papers live (see https://www.biorxiv.org/collection/scientific-communication-and-education for similar papers).

### 1.5 Keywords (up to 5)

```
self-verification, preregistration, machine enforcement, research integrity, computational experiments
```

### 1.6 License

- ✓ **CC-BY 4.0** (Creative Commons Attribution 4.0)

### 1.7 Author Statement

bioRxiv will ask:
- **Data availability statement** → paste:
  ```
  All code and data are available at https://github.com/lm203688/flybrain-connectome (v2.98.1). License: MIT. The 5.63 GB Drosophila Male CNS connectome is not redistributed; obtain v1.0 from the original publication (Xu et al. 2020, Neuron; https://www.flywire.janelia.org/).
  ```
- **Ethics statement** → paste:
  ```
  No human or animal subjects were studied. All data are public connectomics datasets. No IRB approval was required.
  ```
- **Competing interests** → paste:
  ```
  The author declares no competing financial interests, personal relationships, or professional affiliations that could bias this research. The author is not employed by, funded by, or affiliated with any institution or organization in connection with this work.
  ```
- **Funding** → paste:
  ```
  This work received no external funding. All experiments were conducted on the author's personal computing hardware.
  ```
- **Acknowledgments** → paste (or leave blank):
  ```
  The author thanks the arXiv and open-source connectomics community.
  ```

### 1.8 Upload PDF

- File: **P3_submit.pdf** (located at `C:\Users\xing\Desktop\flybrain-connectome\P3_submit.pdf`)
- bioRxiv accepts PDF. No LaTeX required.

### 1.9 Final screen — Author Consent

Read the Author Terms. **Check the consent box** and click **Submit**.

---

## Step 2 — Submit P-2 (repeat same flow)

Same PDF path but for P-2. Metadata:

### 2.1 Title
```
Preregistered Rejection as a First-Class Negative Result
```

### 2.2 Abstract (paste this exactly)

```
Pre-registration has become standard practice for reducing researcher degrees of freedom, and negative results from preregistered protocols are increasingly valued. But preregistration discourse is asymmetric: it tells researchers when to run an experiment and how to interpret its result, but is silent on whether to run it at all. In particular, when an analyst realizes — before execution — that the proposed consequence measure is analytically coupled to the structural variable it is supposed to measure independently, the standard workflow offers no formal category for this refusal.

We propose preregistered rejection as a third category of preregistered output, alongside preregistered success and preregistered failure. A preregistered rejection consists of (i) a proposed experiment with its full four-tuple specification, (ii) a pre-execution decision to refuse, (iii) an analytic or empirical justification that the refusal can be verified independently of the analyst's later beliefs, and (iv) a set of unexplored alternatives the analyst considered but declined to pursue.

We illustrate the category with a case from our project: an intervention study (PR-2) that FAILed at three sample sizes, motivated by its own diagnosis, proposed a substitution (PR-2b) — replacing drop_magnitude with recovery_AUC as the consequence variable. A pre-execution analysis showed that the two quantities share a component (bridge_fraction in the modulator; drop_magnitude as the normalizer); the pre-execution analysis recorded an artifact rate of 95.2% on the intervention arm with 85.7% reverse separation on the control arm, and a merged-arm |corr| = 0.902. The proposed experiment was not run.

We formalize the category, describe its machine-enforcement (Gate 47), and argue that preregistered rejection is a genuine scientific contribution whose value is comparable to preregistered failure. When no independent second read-out exists in the current metric family, the analytically-coupled substitution is best reported as a preregistered rejection rather than as either success or failure.

We contribute (1) a formal definition of preregistered rejection as a preregistered output category, (2) a machine-enforced integrity gate (Gate 47) that verifies preregistered rejections are not fabricated after the fact, (3) a case study of PR-2b in our Drosophila connectome analysis project, (4) a hash-committed receipt and V5 verification badge for the PR-2b case, and (5) a RO-Crate 1.1 export of the full preregistration protocol. Code and preregistration data are publicly available at github.com/lm203688/flybrain-connectome (v2.98.1).
```

**Character count**: ~2150 — **if bioRxiv complains about length, cut the final paragraph** ("We contribute (1)...") — the case-study details stand on their own.

### 2.3 Subject Areas

**Primary**:
- ✓ **Scientific Communication and Education**

**Cross-lists**:
- ✓ **Neuroscience** (case study is a connectome)
- ✓ **Systems Biology** (statistical methodology for computational experiments)

### 2.4 Keywords

```
preregistration, negative results, pre-execution refusal, causal inference, computational experiments
```

### 2.5 Upload PDF

- File: **P2_submit.pdf** (located at `C:\Users\xing\Desktop\flybrain-connectome\P2_submit.pdf`)

### 2.6 Statements

Same as Step 1.7 — copy the same Data/Ethics/Competing/Funding statements.

---

## After Submitting Both

bioRxiv's moderation is 24-72 hours. You will receive an email with:
- A bioRxiv ID (format: `10.1101/2610.XXXXXX`)
- A DOI

**Immediately after receiving both DOIs, tell me and I will:**
1. Update `docs/arxiv_paper.md` References with bioRxiv DOIs
2. Update `docs/PAPER_P1_MAINLINE_MERGED.md` with bioRxiv citations
3. Update the 3 LaTeX `references.bib` files in `06_latex_manuscript/`
4. Bump project version (currently v3.00.1)
5. Update CHANGELOG.md
6. Rebuild dist/ (sdist + wheel) if version changed
7. Push via `gh_publish.py`
8. Run gates to verify 58/58 quick PASS
9. Add `data_availability` and `code_availability` fields to CITATION.cff with bioRxiv URLs

---

## What NOT to Do

- ❌ Don't click "Submit" until you've read the Author Terms on the final screen
- ❌ Don't add false affiliations — bioRxiv verifies via email domain
- ❌ Don't submit both papers simultaneously (do P-3 first, wait for confirmation, then P-2)
- ❌ Don't submit before the PDF is finalized — bioRxiv keeps ALL versions public, you can only mark as "withdrawn"
