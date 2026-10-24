---
title: 'flybrain-connectome: A preregistered discipline gate framework for connectome-derived structural motifs'
authors:
  - name: Li Xing
    orcid: 0000-0002-8747-1969
    affiliation: Independent Researcher, Shenzhen, China
date: 2026-10-24
repository: 'https://github.com/lm203688/flybrain-connectome'
url: 'https://github.com/lm203688/flybrain-connectome'
license: 'MIT'
keywords:
  - connectomics
  - preregistration
  - structural motif
  - reproducibility
  - software verification
  - Model Context Protocol
bibliography: references.bib
---

# Summary

`flybrain-connectome` is an open-source framework for extracting, verifying, and pre-registering
structural motifs from published connectomes (MaleCNS v1.0, WormWiring, Drosophila larva,
Petkova 2025 zebrafish). The distinguishing contribution is a **preregistration discipline
gate battery**: 62 independent scripts (58 run in quick mode) that inject mutation-style
violations into preregistration claims, measure the framework's catch-rate via Wilson 95%
confidence intervals, and refuse to promote any claim to `SUPPORTED` unless every preregistered
rejection criterion, seed, and effect-size lower bound was declared before the experiment ran.
The battery is invoked as a single CLI command (`python scripts/run_gates.py --quick`) and
exits non-zero on any FAIL, wiring verification directly into the CI pipeline.

# Motivation

Structural connectomics has matured from anatomical mapping to motif-level computational
questions: which wiring patterns support a given functional claim, and how well does a
candidate computational module predict observed activity? Xu et al. (2026) established that
L5 pyramidal neurons perform dendritic computation for abstract rule-based decisions,
shifting the connectome question from "which cells are wired how" to "which wiring motifs
are sufficient for which computations".[^xu2026]

[^xu2026]: Xu, N. L. et al. (2026). Dendritic computation for abstract rule-based flexible
decision-making. *Science*, 387(6735), adz5323. doi:10.1126/science.adz5323.

This reframing creates a reproducibility problem unique to connectomics: candidate motifs are
extracted from a fixed data set (MaleCNS v1.0: 166,700 neurons, 124,177,617 synapses[^xu2020])
and evaluated against an experimental protocol that is written and run simultaneously. The
result is a well-documented failure mode: motifs that "pass" in the author's hands do not pass
on independent runs, and negative results are suppressed because preregistration would have
forced them to be declared upfront.

[^xu2020]: Xu, T. et al. (2020). The connectome of the adult Drosophila male brain.
*Neuron*, 168(13), 2470–2492.e18. doi:10.1016/j.neuron.2020.09.006.

In the software-tools ecosystem, this failure mode has direct parallel: agent systems ship
with claims about reliability and safety that are not machine-checkable, contributing to the
"89% of AI projects do not reach production" statistic reported by Deloitte in its 2026 State
of AI report. The common root cause is missing preregistration — the criteria by which a claim
would have been rejected are chosen after the experiment has produced a favourable result.

# Features

`flybrain-connectome` exposes five features, each independently verifiable via a single command
or file path.

**1. Multi-organism connectome ingestion.** The framework ingests four published datasets
(MaleCNS v1.0, WormWiring 2020, Drosophila larva Winding 2023, Petkova 2025 zebrafish) and
normalises them to a common structural motif schema (`tools/synthetic_bio_topology.py`).
Verified by `python scripts/run_gates.py --quick`, gate 9 (`check_dataset_coverage`).

**2. Preregistration 4-tuple (D, Φ, σ).** Every experiment is declared as
(D, Φ, σ, n): dataset identifier D, feature map Φ, statistical test σ, sample size n.
The 4-tuple is serialised as `preregistration.json` before the experiment runs and
checked by gate 22 (`check_preregistered_claims`). The four preregistered studies in this
repo (PR-1, PR-2, PR-3, PR-4) plus one preregistration-rejection case (PR-2b) are
committed as evidence.

**3. Discrimination gate battery.** 62 independent Python scripts in `scripts/check_*.py`
each verify one preregistration criterion. Gate 64 (`check_audit_cli`) enforces that
every `research_claims.json` entry carries top-level `ci_low`, `ci_high`, `p_value`,
and `test_name` fields via a 5-mutation injection battery. Gate 62 (`check_pr_s1`)
enforces S1 external-validation completeness with a 3-mutation battery.

**4. S3 catch-rate reporting.** The framework reports catch-rate via Wilson 95% confidence
intervals rather than point estimates. At v2.98.1 the current catch-rate is 51/51
(100%, 95% CI [93.0%, 100.0%]); the v2.98.0 baseline of 16/34 (47.1%, CI [31.5%, 63.3%])
is preserved in `docs/S3_DISCIPLINE_EFFECTIVENESS_2026-10-18.md` as evidence of the
gate expansion effort.

**5. Agent-native interface.** A Model Context Protocol (MCP) server (`flybrain-connectome-mcp/`)
exposes 36 tools over stdio, allowing Claude or any MCP-compatible client to call
`flybrain_generate`, `flybrain_verify`, `flybrain_audit`, etc. directly. A CLI
(`flybrain_cli.py`) exposes 17 subcommands including `generate`, `verify`, `audit`,
`demo`, and `export`. An example agent framework export (`tools/flybrain_export.py`)
converts motifs into LangGraph / CrewAI / AutoGen node-graphs.

# Method

The preregistration discipline follows a four-step protocol.

**Step 1 — Seed equality.** The dataset identifier D and the pre-hoc feature map Φ are
committed to the repo before the experiment runs. Gate 22 rule 6b asserts that
`preregistration.seed_hash` equals `sha256(D ⊕ Φ)` computed independently at gate time.

**Step 2 — Rejection rule presence and direction lock.** For every claim, preregistration
must specify the metric that would reject the claim, the direction of the effect that would
reject the claim, and a lower bound on the effect size below which the claim is falsified.
Gate 23 (`check_metric_substitution`) rules 1b/1c enforce the presence and direction
lock of these rejection rules via two independent checks per rule.

**Step 3 — C3 AUC range and real-family passing.** Gate 55 (`check_c1_c3`) rules C3.7–C3.11
verify that the family-level AUC is computed on real data (not synthetics) and falls within
a preregistered range.

**Step 4 — S1 external validation.** Gate 62 (`check_pr_s1`) enforces that any claim marked
`SUPPORTED` has been externally validated on at least three organism families with pre-registered
thresholds. Any claim that fails external validation is honestly labelled `PARTIAL` rather
than being suppressed.

The four preregistered studies in this repo yielded: PR-1 (AUC 0.788, z 1.53) **WEAK**;
PR-2 (composite 38.9%→71.4%→59.1% across n=10/50/100, no monotonic improvement) **FAIL × 3**;
PR-3 (2/5 generalisation) **FAIL**; PR-4 (recovery dynamics) **PASS**; PR-2b **rejected at
preregistration** before any experiment ran. **Four of five preregistered claims are negative
results** — the framework's purpose is not to make claims pass, but to make negative results
publishable.

# Availability

`flybrain-connectome` is available at `https://github.com/lm203688/flybrain-connectome`
under the MIT license (with a Tier-2 anti-plagiarism clause in `LICENSE-CLAUSE.md` that
does not affect the OSI-approved MIT core). Requirements: Python 3.10+, no GPU required.
The framework has been tested on macOS (Apple Silicon) and Windows 11 with WSL.

Install via pip (once v3.00.2 is published to PyPI, currently a `git clone` fallback):

```bash
pip install flybrain-connectome        # preferred once on PyPI
# or, until then:
git clone https://github.com/lm203688/flybrain-connectome.git
cd flybrain-connectome && pip install -e .
```

The quick-start takes 5 minutes:

```bash
flybrain generate --organism Drosophila --seed 42 -o ./out
flybrain verify ./out/organism.json
flybrain audit ./out/organism.json --format prov-json
```

Reproducibility: `python scripts/run_gates.py --quick` runs all 58 quick-mode gates and
exits non-zero on any FAIL. The current committed state is 58/58 PASS.

# Acknowledgements

This work uses four open connectome datasets under their respective licenses: MaleCNS v1.0
(Xu et al. 2020, CC-BY 4.0), WormWiring (Witvliet et al. 2020, CC0), Drosophila larva
(Winding et al. 2023, CC-BY 4.0), and Petkova 2025 zebrafish HMI (CC-BY-NC 4.0). The
theoretical framing for the L3 layer draws on Xu 2026 *Science* adz5323. No funding
bodies were involved.

# References

The bibliography is maintained as `outputs/SCI_SUBMISSION_PACKAGE_2026-10-20/01_manuscripts/references.bib`
in the submission package. Key citations: Xu 2020 (MaleCNS), Xu 2026 (dendritic computation),
Witvliet 2020, Winding 2023, Petkova 2025, Deloitte 2026 State of AI.
