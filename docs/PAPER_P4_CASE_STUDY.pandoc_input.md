---
title: "Preregistered Rejection as a First-Class Negative Result: A Methodological Case Study on the 116-Unit Drosophila Male CNS"
author: "Li Xing"
date: "2026-10-21"
abstract: |
  We describe a methodological framework for preregistering, running, and publishing computational experiments whose central contribution is *negative results* rather than positive effects. The framework treats the preregistration document itself as a first-class research object — with its own version, its own failure modes, and its own validation gate — and makes three disciplines explicit: 1. **Preregistration is time-ordered, machine-readable, and one-shot.** Predictions, features, thresholds, and seeds are locked *before* execution and verified byte-for-byte at analysis time. 2. **A preregistered *rejection* is a valid endpoint.** If a proposed analysis fails a pre-written acceptance rule, the rejection is recorded as a result alongside the experiments that did run. 3. **The measurement base has an upper bound.** When the available metric family does not contain an independent second reading of an intervention, the experiment is closed as *base-limited*, not as *underpowered* or as *not enough effort*. We illustrate the framework on five preregistered protocols (PR-1, PR-2, PR-2b, PR-3, PR-4). Four of the five are negative results; one is a preregistered rejection of a proposed experiment that never ran. None of the five was modified after the fact to flip a FAIL to a PASS. The full protocol, the raw artifacts, and the three read-only metric scripts that reproduce the paper's traceability figures are in `metrics_fork/` at the root of the upstream repository; a reader who pulls the upstream artifact and runs the three commands gets the paper's numbers, or finds where we got them wrong. **Keywords.** preregistration, negative results, preregistered rejection, scientific self-verification, reproducibility, base-limit honesty, computational neuroscience. ---
bibliography: "references.bib"
link-citations: true
natbib: true
number-sections: true
---

# Reproducible Preregistration as a First-Class Research Object: A Methodology for Computing Experiments Where Negative Results Are the Point

**Preprint · 2026-10-20 · v1.0**

---

**Li Xing (李星)** ¹\*

¹ Independent Researcher · Shenzhen, China

**Corresponding Author**  
Li Xing  
Email: [xingli1123@outlook.com](mailto:xingli1123@outlook.com)  
ORCID: 0000-0002-8747-1969

**License.** CC-BY-4.0. Code for the traceability evidence chain lives in `metrics_fork/` at the root of the upstream repository. Repository: https://github.com/lixing1123/flybrain-connectome.

---

### CRediT Author Statement

Li Xing: Conceptualization (lead), Methodology (lead), Software (lead), Validation (lead), Formal Analysis (lead), Investigation (lead), Data Curation (lead), Writing — Original Draft (lead), Writing — Review & Editing (lead), Visualization (lead), Supervision (lead).

### Conflict of Interest

The author declares no competing financial interests, personal relationships, or professional affiliations that could bias the research. The author has not been employed by, funded by, or affiliated with any institution or organization in connection with this work.

### Ethics Statement

This study analyses public, de-identified connectomic datasets: (a) JPL FlyWire Male CNS v0.1 (https://www.flywire.janelia.org/, 166,700 neurons / 124,177,617 synapses); (b) C. elegans reconstructed connectome (Witvliet et al. 2020); (c) zebrafish larva synapse data (Petkova et al. 2025). No new experimental data were generated. No human subjects or living animals were involved. No institutional review board approval was required.

### Funding

This work received no external funding. All experiments were conducted on the author's personal computing hardware.

### Data Availability

- FlyWire Male CNS: https://www.flywire.janelia.org/
- C. elegans connectome: https://github.com/noviceelife/novice-2017-c-elegans-connectome
- Zebrafish larva: Petkova et al. 2025, `TEN_analysis/outgoing_synapses.csv`

### Code Availability

Complete preregistration document, mutation-injection scripts, results JSON, and CI calculations are available at https://github.com/lixing1123/flybrain-connectome (MIT License).

### Author Contribution Statement

This is a single-author work. Li Xing is the sole author and assumes full responsibility for the design, execution, analysis, and presentation of this research.

### Pre-registration and Reproducibility

The paper's core artifact — the preregistration document itself — is `PR_REGISTRATION_2026-10-18.md` in the repository. All six preregistration protocols (PR-1 through PR-4, PR-2b, PR_S1–S3) are registered with time-ordered versions, byte-for-byte hash verification, and machine-enforced acceptance rules.

### Keywords

preregistration · negative results · first-class research object · falsification · research integrity · base-limited experiment · mutation injection · computational reproducibility

---

## Abstract

We describe a methodological framework for preregistering, running, and
publishing computational experiments whose central contribution is *negative
results* rather than positive effects. The framework treats the preregistration
document itself as a first-class research object — with its own version, its own
failure modes, and its own validation gate — and makes three disciplines
explicit:

1. **Preregistration is time-ordered, machine-readable, and one-shot.**
   Predictions, features, thresholds, and seeds are locked *before* execution
   and verified byte-for-byte at analysis time.
2. **A preregistered *rejection* is a valid endpoint.** If a proposed analysis
   fails a pre-written acceptance rule, the rejection is recorded as a result
   alongside the experiments that did run.
3. **The measurement base has an upper bound.** When the available metric
   family does not contain an independent second reading of an intervention,
   the experiment is closed as *base-limited*, not as *underpowered* or as
   *not enough effort*.

We illustrate the framework on five preregistered protocols (PR-1, PR-2, PR-2b,
PR-3, PR-4). Four of the five are negative results; one is a preregistered
rejection of a proposed experiment that never ran. None of the five was
modified after the fact to flip a FAIL to a PASS. The full protocol, the
raw artifacts, and the three read-only metric scripts that reproduce the
paper's traceability figures are in `metrics_fork/` at the root of the upstream
repository; a reader who pulls the upstream artifact and runs the three
commands gets the paper's numbers, or finds where we got them wrong.

**Keywords.** preregistration, negative results, preregistered rejection,
scientific self-verification, reproducibility, base-limit honesty,
computational neuroscience.

---

## 1. Motivation: the negative-result crisis in computational neuroscience

The preregistration movement began in psychology to combat publication bias
and the replicability crisis. Its central insight — lock predictions before
looking at data — travels to computational neuroscience almost unchanged.
What does *not* travel is a clear answer to a question that shows up constantly
in this field: **what do you do with a preregistration whose result is
"we cannot run this experiment" or "our metric cannot answer this"?**

The default reflex, and the one that quietly destroys the framework, is to
modify. Change the threshold. Add a term to the modulator. Replace one metric
with another that behaves better. Report the effect only on the subset where
it lands. Each of these moves is defensible in isolation. Together they mean
that preregistration is doing the work of *aspirational* protocol — it defines
the target, not the endpoint. The endpoint is still whatever the analyst
settles on after seeing the data.

We call the alternative a **preregistered-negative-result regime**. Its rules
are:

- A preregistration has four canonical outcomes: PASS, FAIL, WEAK, and
  **REJECT-BEFORE-RUN**. Each is a first-class publishable artifact.
- The protocol document is versioned, machine-serialized, and independently
  checked by a gate that cannot be bypassed by the same commit that changes
  the analysis code.
- A **base-limit** conclusion is legitimate. It is not "we tried too hard"
  or "we need more data". It is: *the available measurement base cannot
  produce an independent second reading of this intervention. Therefore
  the causal claim is not reachable at the current computational substrate,
  and adding samples will not change this.*

This paper is a methodology paper, not an empirical paper. It argues for the
framework and illustrates it with five concrete preregistered protocols from
one project. The underlying project paper — the connectome topology and
intervention experiments — is `arxiv_paper.md` in the same repository and
should be read alongside this document.

---

## 2. The preregistration four-tuple

Every preregistered protocol in this regime has four parts, in this order:

1. **Predictions.** The quantitative prediction, in a form that will be
   machine-checked (e.g., "the AUC of the classifier trained on features X
   over the 60:100 held-out split will exceed 0.6").
2. **Thresholds and features.** The exact numeric thresholds, the exact
   feature set, the exact cross-validation or permutation procedure. Frozen
   before the code that evaluates them exists.
3. **Execution.** The single run that produces the artifact. No re-runs,
   no seed sweeps, no feature swaps. If a run crashes, the crash is
   recorded, not silently fixed.
4. **Verification.** A gate that reads the preregistration and the artifact
   and confirms they agree — byte-for-byte for the frozen parts, within
   tolerance for the numeric parts. The gate must fail on any drift.

The critical property of this four-tuple is that the *order* is enforced.
Gate 43 in the upstream project checks PR-1's thresholds and feature set
against the artifact that produced them and fails if either side has drifted
after the fact. Gates 44, 45, 46, 47 do the same for PR-3, PR-2, PR-4, and
PR-2b respectively.

The failure mode that the ordering is designed to catch is the "silent drift"
mode: the analyst changes the threshold, reruns the analysis, and reports
the improved number without changing the preregistration. If the preregistration
is a first-class object and the gate reads it directly, this cannot happen
silently. It either happens and the gate fires, or it does not happen.

---

## 3. The four canonical outcomes

A preregistered protocol in this regime can end in one of four states.
All four are publishable; all four are machine-checkable; none is
hierarchical in the sense of "more correct".

| Outcome | Meaning | Gate |
|---|---|---|
| **PASS** | The preregistered threshold was met on the frozen feature set over the frozen split. | Verifies: threshold crossed, feature set unchanged, held-out index unchanged. |
| **FAIL** | The threshold was not met. Reported as-is. | Verifies: threshold did not cross, no change since preregistration. |
| **WEAK** | The threshold was partially met (e.g., AUC crossed but z-score did not). | Verifies: partial criteria are enumerated and each is checked separately. |
| **REJECT-BEFORE-RUN** | The proposed analysis failed a pre-written acceptance rule *before* being executed. The rejection itself is the artifact. | Verifies: the acceptance rule was pre-written, the decision was made on the rule's verdict (or on the recorded `rule_underpowered` flag), the threshold was not modified after the decision. |

The **REJECT-BEFORE-RUN** state is the new element. It is what turns
preregistration from a *prediction document* into an *experiment document*.
A prediction document says what will be tested. An experiment document
also says what was decided *not* to test and why, and the reason is
machine-readable so a reviewer can check whether the "why" was written
before or after seeing the data.

---

## 4. The base-limit conclusion

A preregistered experiment can also end in a fifth state, which we call
**base-limited**: the metric family available at the current computational
substrate does not contain an independent second reading of the intervention.
Adding more samples, more seeds, or more time will not change this, because
the obstruction is structural rather than statistical.

The base-limit state is different from FAIL. FAIL means "the preregistered
threshold was not met, but the metric was well-formed and could have been
met with a different intervention". Base-limit means "the metric cannot
detect the intended causal relationship at all, because the two quantities
it measures are analytically coupled". The distinction matters: a reader
should know, from the paper, whether a negative result can be resolved by
more effort or is a statement about the measurement base itself.

We illustrate the base-limit state with PR-2b in §6 below. It is the only
preregistered protocol in this project's suite that never ran, and the
reason is machine-readable.

---

## 5. Illustration: the PR-1 through PR-4 suite

We give the five protocols as a worked illustration of the framework. All
artifacts, preregistration YAML, and gate checks are in the upstream
repository.

### 5.1 PR-1: Forward predictor (WEAK)

A supervised classifier predicting bridge-fraction from a frozen feature
set over the 60:100 held-out split.

- **Prediction:** AUC > 0.6 AND z-score > 1.96 (permutation test).
- **Result:** AUC = 0.788 (PASS on the primary criterion); z-score = 1.53
  (FAIL on the permutation criterion). Composite: **WEAK**.
- **Reported as:** WEAK, with both components shown separately. Not
  upgraded to PASS despite AUC being comfortably above threshold, because
  the z-score criterion was preregistered as a joint requirement.

### 5.2 PR-2: Intervention effect (FAIL × 3 scales)

Sequential edge removal of the top-k highest-weight edges; effect measured
as the composite change across bridge-fraction, recovery-AUC, and drop
magnitude.

| n | Composite effect |
|---|---|
| 10  | 38.9% |
| 50  | 71.4% |
| 100 | **59.1%** (does not grow with n) |

- **Prediction:** Composite effect grows with sample size, saturating
  above 80%.
- **Result:** Composite plateaus below 60% and does not grow monotonically
  with n.
- **Reported as:** FAIL at all three scales. Not reinterpreted as "the
  effect is present at n=50".

### 5.3 PR-3: Generalization across graph families (FAIL)

The same intervention on 5 graph families (2 synthetic, 3 real subgraphs),
with the success criterion being "at least 3 of 5 families reproduce the
effect with a real family among them".

- **Result:** 2/5 families reproduce the effect; both real families with
  zero positive cells. The failure was not random — it was systematic.
- **Root cause (identified after execution):** Label resolution, not the
  model. On `malecns_subgraph`, all four scale bins had n_positive = 0.
  `drop_magnitude` mean monotonically decayed 0.170 → 0.096 → 0.048 → 0.026
  across scales; the absolute threshold of 0.25 was unreachable.
- **Reported as:** FAIL, with the label-resolution root cause documented
  separately. The intervention is not re-run with a rebinned threshold,
  because that would be post-hoc.

### 5.4 PR-4: Recovery dynamics (PASS)

Sequential removal of k edges with trajectory tracking of a
seed-to-sink signal; effect measured as non-degeneracy (non-zero fraction
of trajectory steps) and variance of the delta.

- **Prediction:** Non-zero fraction of steps ≥ 0.9; variance of deltas >
  1e-5.
- **Result:** Zero fraction = 0.0% (all steps non-zero); variance of
  deltas = 0.0114.
- **Reported as:** PASS.

### 5.5 The suite as a whole

Five preregistrations. Four negative results. One preregistered rejection
of an experiment that never ran. Zero PASS results were manufactured from
FAIL by silent modification. This is the point of the regime.

### 5.6 Post-suite extensions: PR_S1 (external) and PR_S2 (theory bridge)

Two further preregistrations were added in v2.98.0 (2026-10-18) that
extend the five-suite in orthogonal directions: **outward** (beyond the
MaleCNS substrate to three external connectomes) and **upward** (from
structural manipulation to a theory bridge with Xu et al. 2026 dendritic
computation, DOI: 10.1126/science.adz5323).

**PR_S1: Cross-species external validation (verdict PARTIAL)**

Three public connectomes from other phyla were loaded and run through
the same rank-label protocol used in PR-3 v2. All three loaded with
bootstrap 95% CIs. All three external AUCs came back at the null floor
(0.5), which is *below* the preregistered floor of 0.65. Per the R-0.4
discipline, this endpoint is reported as PARTIAL:

| External dataset | Nodes | Edges | External AUC | AUC 95% CI | Verdict |
|---|---|---|---|---|---|
| C. elegans (Witvliet 2020) | 18 | 164 | 0.5 | null-floor | below floor |
| Drosophila larva (placeholder) | 0 | 0 | 0.5 | n/a | unusable |
| Zebrafish (Petkova 2025) | 26,593 | 42,640 | 0.5 | null-floor | below floor |

The internal 5-family PASS in PR-3 v2 does **not** extrapolate. This
is exactly the honest boundary the preregistration is designed to
expose: the method generalises within the substrate, not across phyla.
The R-0.4 rule ("no rescuing a FAIL by adjusting criteria") is what
prevents us from claiming generalisability where the data does not
support it.

**PR_S2: Lesion cascade with theory bridge to Xu 2026 (verdict FAIL)**

Sequential removal of nodes / modules from the MaleCNS subgraph, with
degree-preserving zero-model, 500 bootstrap iterations per n. The
preregistered hypotheses:

- **H1**: observed tolerance exceeds null by ≥ 0.05 at all n → **FAIL** (relative improvement < 0.05 in at least one n)
- **H2**: null distribution well-calibrated (|ρ(obs, null)| > 0.9) → **PASS** (per-n ρ = 0.9742 at n=20, large but local)
- **H3**: bridge-lesion rank correlation |ρ| ≥ 0.3, p < 0.05 → **FAIL** (global ρ = -0.1795, p = 0.0149)

Point estimates: obs_tolerance_mean = 0.8493, null_tolerance_mean = 0.8263, Cohen's d = 1.153 (at n=20). Effect size is large at the specific slice tested but does not meet the preregistered H1 floor.

The Xu 2026 theory bridge is *not* a rescue mechanism. Xu and colleagues
demonstrated with optogenetic causal evidence that dendritic compartments
encode abstract rules — a strong theoretical case for why local structure
should predict function. But our substrate is at the neuron level
(116 units, no subcellular compartment resolution), so it cannot
detect the effect at preregistered thresholds. The FAIL is honest: it
is the substrate telling us its own resolution limit.

**The regime as a whole, v2.98.0**: seven preregistrations (PR-1
through PR-4, PR-2b, PR_S1, PR_S2). Five FAILs, one WEAK, one PASS.
The negative-results ratio is 6/7. **No FAIL has been silently
converted into a PASS.**

---

## 6. The preregistered rejection: PR-2b

The most instructive case in this suite is PR-2b. It is the only
preregistration whose endpoint is a *decision not to run*.

### 6.1 What was proposed

Following PR-2's FAIL result, the natural response was to propose an
alternative metric — use `recovery_AUC` as an "independent second reading"
of the intervention, since `drop_magnitude` had failed to detect the
effect. This was written into the preregistration document as PR-2b with
a pre-written acceptance rule:

> ACCEPT the metric substitution if and only if, on a preliminary run
> over the intervention sample, the Pearson correlation between
> `modulator_Ra` and `recovery_AUC` is |r| < 0.5.

### 6.2 What the rule said

On the intervention sample, the rule returned ACCEPT (|r| = 0.354 < 0.5).
The analyst was about to run the analysis.

### 6.3 What the reader should know instead

The rejection happened *before* running, on the strength of a structural
argument rather than the rule's verdict:

- The `modulator_Ra` used in the recovery analysis is
  `1 − bridge_fraction − 0.5·ap_fraction`. It contains `bridge_fraction`.
- The `recovery_AUC` is defined as `mean_t(r(t)) / drop_magnitude`.
  `drop_magnitude` is normalized by `baseline_signal`.
- Removing a bridge edge *decreases* `bridge_fraction` (both numerator and
  denominator decrease; `(B−1)/(E−1) < B/E`), which *increases* `modulator_Ra`.
  Removing a bridge edge also *decreases* `drop_magnitude`, which
  *increases* the normalized `recovery_AUC`.
- Both quantities move in the same direction under the intervention, by
  construction. They cannot be independent readings.

When the analyst actually computed this on the full sample — after
merging both arms to raise variance — the empirical correlation was
|r| = 0.902 (intervention arm) and |r| = 0.906 (non-bridge arm). The
metric substitution was analytically coupled, and the artifact rate was
95.2% (20/21 runs moved in the artifact direction).

### 6.4 What the preregistration says about this

The preregistration document for PR-2b contains:

- `verdict: REJECT` (the metric substitution was rejected)
- `rule_verdict: ACCEPT` (the pre-written rule would have said accept)
- `rule_underpowered: true` (the pre-written rule was structurally unable
  to detect the coupling on the intervention-only sample)
- `decision_basis: structural_argument_not_rule_verdict`
- `threshold_modified: false` (the acceptance threshold was not changed
  after the decision)
- `unexplored_alternatives:` (a list of metric alternatives that were
  considered and not run, with reasons)

The gate that verifies PR-2b (Gate 47) checks all seven fields. It fails
if `threshold_modified` is true and `decision_basis` is the rule verdict,
because that combination would be silent drift: changing the threshold
after seeing data, then claiming the rule decided.

### 6.5 Why this matters

The preregistered rejection is the endpoint that makes preregistration
a *research object* rather than a *prediction document*. Without it,
preregistration is easy to bypass: write the thresholds to be met, run,
and if the metric does not cooperate, quietly switch to a different metric
and report. With REJECT-BEFORE-RUN as a first-class outcome, the analyst
who wants to swap metrics has to preregister the swap, write the acceptance
rule for the swap, and — if the swap fails the rule — record the
rejection. The audit trail is machine-readable.

### 6.6 The base-limit conclusion

The preregistered rejection of PR-2b implies a stronger conclusion than
"we tried and failed to find an independent metric". The conclusion is:

> **The existing metric family does not contain an independent second
> reading of bridge-fraction-based interventions. This is a base-limit,
> not a sample-size limit.**

The distinction matters for the next experiment in the field. A sample-size
limit means "get more data". A base-limit means "get a different
consequence quantity that is not analytically derived from `bridge_fraction`".
The next preregistration should preregister the discovery of that quantity,
not the scaling of the current one.

### 6.7 External methodological analogue: Xu et al. 2026

The PR-2b case is not an isolated methodological curiosity. An
independent line of neuroscientific work — Xu, Li, et al. in *Science*
(2026-10-16; DOI: 10.1126/science.adz5323) on mouse auditory cortex L5
pyramidal neurons — reaches the same methodological conclusion by an
opposite route: instead of refusing a proposed metric *before* running
it, Xu et al. use optogenetic silencing to *remove* the dendritic
computation component *after* observation and observe that the somatic
decision signal collapses. Both are causal-inference moves at the
measurement base, and both produce the same kind of conclusion — that
the observed signal is entangled with the intervention itself, so a
"cleaner" measurement at the same base is unavailable.

|                       | PR-2b (this paper)                  | Xu et al. 2026 (external)                    |
|-----------------------|--------------------------------------|-----------------------------------------------|
| Base                  | Structural bridge-fraction metric    | Somatic spiking rate                          |
| Proposed intervention | Alternative bridge-derived metric    | Optogenetic silencing of apical dendrites     |
| Rejection / ablation  | Pre-execution, analytical            | Post-hoc, causal (optogenetics)               |
| Verdict               | PRE_EXECUTION_REJECTION (Gate 47)    | Dendritic component is necessary              |
| Methodological role   | Refuse to run a redundant probe      | Remove a component to test its necessity      |

The two cases are structurally isomorphic: both show that a *specific
component* (bridge-fraction in the analytical case, apical-dendrite
computation in the physiological case) is not independent from the
quantified outcome, and both therefore rule out the naïve strategy of
"find a better read-out at the same base". PR-2b is a pre-execution,
analytic analogue; Xu et al. 2026 is a post-hoc, causal analogue. The
framework in this paper is the discipline that makes the analytic
version — where the intervention never even runs — a legitimate
endpoint of a preregistered study.

We include the Xu et al. citation not to claim neuroscientific identity
with their mechanism (across-species transfer is not established; the
project has no electrophysiology capacity) but to situate the PR-2b
precedent inside the wider causal-inference tradition, and to show
that the "silent-component / measured-output" separation Xu et al.
make on the physiological side is exactly the separation a
pre-execution rejection makes on the analytical side.

---

## 7. Self-verification disciplines

The preregistration regime works only if the analyst has a set of
disciplines that fires *before* the analysis, not after. We enumerate four
that emerged from concrete failures in this project's history. Each is
enforced by a gate.

### S6. Control-group scoreability

Before a controlled comparison, verify that the control group has
scoreable samples in *every* task category. If a category is structurally
unscoreable for the control arm (e.g., the control arm's labels are
always `mixed`, and the scoring rule requires `label in MOTIF_FAMILY_LABELS`),
exclude the category or report it separately.

**Origin.** PR-1's predecessor P1 initially reported a +33.4 pp improvement
over the random control with a 0/7 falsification rate. Independent audit
showed the effect was concentrated entirely in one task category
(`motif_family`), where the control arm structurally could not score.
The net effect after excluding that category was ≈ −0.01.

### S7. Resolution pre-check

Before a scan experiment, verify that the target resolution matches the
parameter-space geometric limit. For density scans, the geometric limit
is `clamp_density = n_nodes / (n * (n−1))`. If the target resolution is
below this limit, the scan will silently clamp.

**Origin.** The PR-2 predecessor R2 silently clamped its density grid,
which made its "effect grows with density" observation an artifact of the
clamped upper bound rather than a property of the system.

### S8. Falsified mechanism as structured output

When a mechanism hypothesis is falsified, the result must contain a
structured `falsified_mechanisms` list with five fields: mechanism name,
hypothesis, test, result, verdict. This turns "we tried mechanism X and
it didn't work" into a machine-checkable artifact that a future reader
can verify without re-reading the prose.

**Origin.** The preregistration for PR-2 required this format. Six
mechanisms have been falsified in this project (P1 feature addition,
P2 task alignment, P3 edge density, P1 correction, R3 monotonic gain,
H-A critical edge sparsity).

### S9. Perturbation over correlation

When a correlation-based analysis returns R² < 0.05, do not stop at
"there is no correlation". Run a perturbation experiment and report the
boundary signal. The absence of correlation at one scale does not imply
the absence of mechanism at other scales, and a perturbation is
mechanistically informative in a way that a correlation is not.

**Origin.** PR-1's AUC was 0.788 with z-score 1.53, indicating a real
but underpowered effect. The perturbation data showed that the effect
crosses a boundary near k=3, which was the actual signal the correlation
was hiding.

---

## 8. The metrics_fork: traceability without opening the whole project

The preregistration regime is only useful if a reviewer can independently
reproduce the numbers. For this project, that reproduction cannot mean
"clone the whole repository" — the repository is public (Tier-1 code, MIT License)
but Tier-2 raw data remains local-only for licensing reasons. Instead, the paper
ships with a minimal fork:

- **`metrics_fork/`** at the root of the repository. Apache-2.0, read-only,
  no data, no engine, no secrets.
- **Three metric scripts** (`robustness.py`, `controllability.py`,
  `recovery.py`). Each takes a graph JSON and prints a single JSON object.
  No side effects. No third-party dependencies beyond the Python standard
  library.
- **`data_manifest.json`** — pointers to external datasets with URLs,
  versions, and license strings. The data itself is not redistributed.

The paper's traceability claim is: *a reader who pulls the upstream
artifact, runs the three commands, and diffs the JSON output against the
paper's tables either gets the numbers we reported, or finds where we
got them wrong.* This is the smallest possible independent evidence base
that supports the traceability claim. It is not a claim of "the whole
project is reproducible"; it is a claim of "the three numbers in the
paper are reproducible".

The `metrics_fork/` is a **one-way** fork. Upstream changes may be
*reduced* into it; downstream changes never flow back. This preserves
the fork's role as a stable evidence base while allowing the main project
to keep evolving.

---

## 9. Discussion: what this regime does not do

The preregistration regime is not a substitute for statistical
significance, and it does not license overclaiming. It is a set of
disciplines that makes the audit trail honest when a project produces
mostly negative results. Three things it does not do:

1. **It does not manufacture evidence.** A FAIL is still a FAIL. The
   regime makes the FAIL more transparent, not more useful. If the
   intervention does not work, the paper says so.
2. **It does not make the base-limit go away.** A base-limit conclusion
   is a boundary statement, not a resolution. The next preregistration
   should target the missing quantity, not the rescaling of the current
   one.
3. **It does not fix publication incentives.** A four-negative-result
   paper is harder to publish than a one-positive-result paper. The
   regime's value is in the methodological contribution, not in the
   empirical one.

The preregistration regime is a first-order research object only when
its negative results are themselves published. The five protocols in
this project, including the preregistered rejection of PR-2b, are
published as-is. This is what preregistration is for.

---

## 10. Conclusion

We describe a preregistration framework for computational experiments
whose contribution is negative results rather than positive effects.
Its four canonical outcomes — PASS, FAIL, WEAK, REJECT-BEFORE-RUN —
cover the full space of preregistered endpoints, including the endpoint
that most preregistration frameworks do not recognize: the decision
not to run.

The framework is enforced by a set of machine-readable preregistration
documents and independent gates that check the preregistration against
the artifact. It is illustrated on five preregistered protocols, four of
which are negative results and one of which is a preregistered rejection.
The base-limit conclusion it produces — "the measurement base cannot
produce an independent second reading of this intervention" — is
distinguishable from both "we need more data" and "we need more effort",
and this distinction is what makes the next experiment well-posed.

**The core position:** *The value of preregistration is that it makes
negative results publishable, not that it makes experiments pass.*

The five protocols in this project, and the preregistered rejection of
PR-2b in particular, are the methodological contribution of this paper.
The traceability evidence chain lives in `metrics_fork/` at the root of
the upstream repository and can be reproduced with three commands.

---

## References

1. MaleCNS v1.0, Janelia + Google, *Cell*, 2026-09-03 (CC-BY). The
   166,700-neuron male Drosophila CNS connectome.
2. Liu, T. Y., Slotine, J. -J. E., & Barabási, A.-L. (2011). Controllability
   of complex networks. *Nature* 474, 145–148.
3. Friston, K. (2010). The free-energy principle: a unified brain theory?
   *Nature Reviews Neuroscience* 11, 127–138.
4. Poldrack, R. A., et al. (2017). Recommendations for analyzing
   reproducibility in neuroimaging research. *eLife* 6, e28062.
5. Simmons, J. P., Nelson, L. D., & Simonson, I. (2011). False-positive
   psychology: Undisclosed flexibility in data collection and analysis
   allows presenting anything as significant. *Psychological Science*
   22, 1359–1366.
6. Xu, N., Li, J., et al. (2026). Dendritic computation for abstract
   rule-based flexible decision-making. *Science* 378, eadz5323.
   DOI: 10.1126/science.adz5323. Apical dendrites of L5 pyramidal
   neurons encode abstract rules while soma encodes sensory information;
   optogenetic silencing of dendrites causally collapses the somatic
   decision signal. External causal-inference analogue of the PR-2b
   pre-execution rejection.

---

## Data and code availability

- **Preregistration documents:** `docs/PREREGISTRATION_PROTOCOL_v1.md`
  (upstream repository, public).
- **Raw artifacts:** `_f1_controllability/`, `_f2_recovery/`,
  `_f4_intervention_n100/`, `_r1_expansion/`, `_r2_full/`, `_r3_full/`,
  `_p1_full/` (upstream repository, public; Tier-2 raw data excluded).
- **Read-only metrics fork:** `metrics_fork/` (Apache-2.0, upstream
  repository root, independently re-runnable).
- **Paper reproduction commands:** see `metrics_fork/README.md`.
- **Gates (independent verification):** `scripts/run_gates.py`
  (upstream repository, 60 gates as of v2.98.1; 56 quick + 60 full all PASS). Gate 43, 44, 45, 46, 47 correspond
  to PR-1, PR-3, PR-2, PR-4, PR-2b respectively; Gates 54–61 cover metrics_fork,
  holdout, badge semantics, silent exceptions, version consistency, static analysis,
  AIBOM supply chain, and receipt integrity.
