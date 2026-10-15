# Preregistered Rejection as a First-Class Negative Result

**A methodological note on pre-execution refusal in preregistered research**

Lexing (厉兴)  
Independent researcher  
`lm203688/flybrain-connectome` · MIT License

**Version 0.1 (2026-10-15)** — Draft skeleton for arXiv submission. Data and code are available at `lm203688/flybrain-connectome`.

---

## Abstract

Pre-registration has become a standard practice for reducing researcher degrees of freedom, and negative results from preregistered protocols are increasingly valued. But preregistration discourse is asymmetric: it tells researchers *when* to run an experiment and *how* to interpret its result, but is silent on *whether* to run it at all. In particular, when an analyst realizes — before execution — that the proposed consequence measure is analytically coupled to the structural variable it is supposed to measure independently, the standard workflow offers no formal category for this refusal.

We propose **preregistered rejection** as a third category of preregistered output, alongside preregistered *success* and preregistered *failure*. A preregistered rejection consists of (i) a proposed experiment with its full four-tuple specification, (ii) a *pre-execution* decision to refuse, (iii) an analytic or empirical justification that the refusal can be verified independently of the analyst's later beliefs, and (iv) a set of *unexplored alternatives* the analyst considered but declined to pursue.

We illustrate the category with a case from our own project: an intervention study (PR-2) that FAILed at three sample sizes, motivated by its own diagnosis, proposed a substitution (PR-2b) — replacing `drop_magnitude` with `recovery_AUC` as the consequence variable. A pre-execution analysis showed that `modulator_Ra = 1 − bridge_fraction − 0.5·ap_fraction` and `recovery_AUC = mean_t(r(t)) / drop_magnitude` share a component: `bridge_fraction` appears in the modulator, and `drop_magnitude` is the normalizer. Because deleting a bridge edge decreases both the numerator and the denominator of `bridge_fraction`, the modulator's penalty decreases, R-a inflates, and `recovery_AUC` inflates — the intervention that "broke" the system is *predicted by construction* to raise the proposed recovery metric. The pre-execution analysis recorded an artifact rate of 95.2% on the intervention arm with 85.7% reverse separation on the control arm, and a merged-arm correlation |corr| = 0.902. The proposed experiment was not run.

We argue that preregistered rejection is a genuine scientific contribution — not a "failed attempt" but a distinct category of negative result whose value is comparable to preregistered failure. We formalize the category, describe its machine-enforcement (Gate 47 in our project), and discuss the substrate limits it reveals: when no independent second read-out exists in the current metric family, the boundary is a **scope boundary** — a call for a new instrument — not a sample-size failure.

**Keywords**: preregistration, negative results, pre-execution refusal, measurement redundancy, causal inference, self-verification, computational experiments

---

## 1. Introduction

### 1.1 The asymmetry in preregistration

Pre-registration has been adopted as a standard practice to reduce researcher degrees of freedom and to protect the interpretive value of null and negative findings. It has generated a rich literature on:

- *When* to run an experiment (e.g., power calculations, sample size justification);
- *How* to specify success and failure criteria in advance (e.g., preregistered thresholds, equivalence tests);
- *How* to interpret negative results (e.g., equivalence vs. absence-of-evidence; replication registries).

But preregistration discourse is silent on a third question: **whether to run the experiment at all**, when pre-execution analysis reveals that the proposed measurement is analytically redundant with the intervention. This is a distinct case from underpowered studies, under-specified hypotheses, or ill-designed controls: the failure mode is not statistical, it is *definitional*.

### 1.2 The gap

Consider a scenario common in computational and networked research:

1. An initial experiment (E1) is preregistered and FAILS at three sample sizes.
2. E1's own diagnostic points to a candidate substitute measurement M'.
3. E1's FAIL is thus reframed: perhaps E1 was measuring the wrong thing, and re-running with M' would succeed.
4. The analyst proposes E2 = E1 with M' as the outcome variable.

The standard workflow has no formal category for E2 being *refused* before execution. The analyst is effectively forced to choose between two dishonest options:

- **Run E2 anyway**, publish "another failure," and let the pattern itself be discovered by readers; or
- **Refuse E2 without documentation**, effectively hiding an important methodological decision.

Both options hide the *decision process* from future readers. The first hides it by noise; the second hides it by silence.

### 1.3 Our proposal

We propose **preregistered rejection** as a formal category for this third case. A preregistered rejection records:

- The proposed experiment (E2) with its full preregistered specification;
- The pre-execution decision to refuse;
- A justification that is verifiable independently of the analyst's later beliefs;
- A set of *unexplored alternatives* the analyst considered but declined to pursue;
- An explicit statement of what condition would need to be satisfied to lift the refusal.

This category sits alongside preregistered success and preregistered failure as a **third class of preregistered output**, with its own interpretive value.

### 1.4 Roadmap

Section 2 formalizes the category. Section 3 introduces Gate 47, our machine-enforced integrity checker. Section 4 presents the case study. Section 5 discusses the implications for preregistration discourse and the substrate limits this case reveals. Section 6 concludes.

---

## 2. Formalization: preregistered rejection

### 2.1 Definition

**Definition 1 (Preregistered experiment).** A *preregistered experiment* is a tuple
$$E = \langle S, I, M, C, \Theta \rangle$$
where $S$ is the target system, $I$ is the intervention (a set of structural actions), $M$ is the consequence measure, $C$ is the control, and $\Theta$ is the tuple of preregistered success criteria.

**Definition 2 (Preregistered rejection).** A *preregistered rejection* of $E$ is a tuple
$$R_E = \langle E, D, J, A, U, T \rangle$$
where:

- $D = \texttt{REJECT}$ is the pre-execution decision;
- $J = (J_{\text{analytic}}, J_{\text{empirical}})$ is a justification that is (a) analytically derivable from the definitions of $M$ and $I$ alone, or (b) empirically detectable on a sample that is independent of $E$'s intended sample;
- $A = \texttt{criteria\_modified\_after\_results = False}$ is an explicit declaration that $\Theta$ was not revised in response to $R_E$'s evidence;
- $U$ is the set of *unexplored alternatives* — substitutes, follow-ups, and scope changes the analyst considered but declined to pursue;
- $T$ is a *lift condition* — the condition under which $R_E$ would be lifted and $E$ reconsidered.

### 2.2 Independence of justification

A critical property of a preregistered rejection is that its justification must be **independent of the analyst's later beliefs**. If $J$ requires the analyst to know the outcome of $E$ in order to justify $R_E$, then $R_E$ is not a refusal — it is post-hoc rationalization.

Two forms of independence:

- **Analytic independence**: $J_{\text{analytic}}$ is derivable by reading the definitions of $M$ and $I$, without any data. In this case, refusal is unambiguous: the analyst can prove that running $E$ is definitionally redundant before any data is collected.

- **Empirical independence**: $J_{\text{empirical}}$ uses a sample that is *provably independent* of $E$'s intended sample. In this case, refusal is justified only if the sample was selected before the analyst knew whether $E$ would succeed; if the sample is drawn after $E$ is proposed but before $E$ is executed, the analyst must document the selection rule and show that it does not depend on $E$'s predicted outcome.

### 2.3 The unexplored alternatives field

A preregistered rejection is *incomplete* without its $U$ field. The $U$ field has three purposes:

1. **Reproducibility**: future readers can reconstruct not just what the analyst did but what she considered and declined;
2. **Auditability**: an $R_E$ with an empty $U$ field is a red flag — it suggests the analyst did not actually consider alternatives;
3. **Boundary communication**: the $U$ field implicitly specifies the scope boundary of the current measurement family, i.e., what conditions would need to change for the refusal to be lifted.

### 2.4 Interpretive value

We claim that preregistered rejection has **comparable interpretive value** to preregistered success and failure. Its value lies in three places:

1. **Documentation of decisions not taken** — every refusal has a cost; documenting it prevents silent abandonment of a methodological branch;
2. **Boundary identification** — a preregistered rejection pinpoints the substrate limits of the current measurement family, which is itself a scientific finding;
3. **Anti-rationalization** — by requiring $U$ and $T$ to be documented *before* execution, the format prevents post-hoc rationalization of why the experiment was not run.

---

## 3. Machine enforcement: Gate 47

### 3.1 Rationale

A preregistered rejection is a *claim about a decision not taken*. Such a claim has no empirical data on which to fall back: it must be verified through its own specification. This makes it vulnerable to a class of abuse — post-hoc rationalization — that preregistered success and failure are immune to (they have data to check against).

We therefore introduced **Gate 47** — a machine-enforced integrity checker that verifies:

- The preregistered rejection's specification matches the executed pre-execution analysis;
- The `criteria_modified_after_results` field is `False`;
- The `unexplored_alternatives` field is populated and non-trivial;
- The decision is derived from an independently-computable quantity (not the analyst's summary field);
- The rule used to make the decision is itself under-documented (i.e., `rule_underpowered = True` is explicitly recorded if applicable).

### 3.2 The independent recomputation principle

Gate 47 follows a general principle: **the checker should recompute the decision from the raw sample, not from the analyst's summary**. This means that if the analyst's summary field is tampered with, the checker will catch the mismatch.

Formally: given a preregistered rejection $R_E = \langle E, D, J, A, U, T \rangle$ and a raw sample $X$:

- The checker recomputes $J' = \texttt{compute}(X, E)$ from the raw sample;
- It compares $J'$ to $J$;
- If they differ, it fails the integrity check.

This principle — **independent recomputation > analyst trust** — generalizes beyond Gate 47 to all preregistered experiment integrity checks.

### 3.3 Implementation

Gate 47 is implemented as `scripts/check_metric_substitution.py` in the `flybrain-connectome` project. The pre-execution analysis script is `scripts/f4b_metric_substitution_check.py`. The full protocol is at `docs/PREREGISTRATION_PROTOCOL_v1.md#PR-2b`.

---

## 4. Case study: PR-2b

### 4.1 Background: PR-2 and its FAIL

In the same project, we ran a preregistered intervention experiment (PR-2) testing the hypothesis: "deleting a bridge edge of a network increases its `drop_magnitude` (a measure of fault isolation)". The experiment was run at three sample sizes — n = 10, 50, 100 topologies — and FAILed at all three: composite pass rates of 38.9%, 71.4%, and 59.1% respectively; effect sizes |mean_delta| ≤ 0.0005.

**Diagnosis**: PR-2's own result analysis suggested that `drop_magnitude` was saturated at small n (i.e., it hit its upper bound for many topologies), limiting the measurable effect. A natural substitute was `recovery_AUC` — a measure of recovery dynamics — which was already part of the project's metric family (see PR-4, which PASSed).

### 4.2 The proposed substitute: PR-2b

PR-2b was proposed as: re-run PR-2 with `recovery_AUC` substituting `drop_magnitude` as the consequence variable. The proposition had all the surface qualities of a legitimate preregistration extension: same intervention, same control, updated metric with a clear motivation from the previous experiment's own diagnosis.

### 4.3 The pre-execution analysis

Before running PR-2b, we performed an analytic and empirical analysis of whether `recovery_AUC` is *independent* of `drop_magnitude`. Reading `compute_ablation` line by line revealed the following definitions:

$$\texttt{modulator\_Ra} = 1 - \texttt{bridge\_fraction} - 0.5 \cdot \texttt{ap\_fraction}$$
$$\texttt{recovery\_AUC} = \frac{\text{mean}_t(r(t))}{\texttt{drop\_magnitude}}$$

Two observations follow:

**Observation 1 (analytic coupling)**: `modulator_Ra` contains `bridge_fraction` in its numerator (as a subtracted penalty term). When a bridge edge is deleted, `n_edges` and `n_bridges` both decrease by 1, so `bridge_fraction = (B-1)/(E-1) < B/E` — the bridge fraction *decreases*. That lowers `modulator_Ra`'s penalty term, which *raises* `R-a`, which (via the recovery dynamics) *raises* `recovery_AUC`. In other words: the intervention that "broke" the system is *predicted by construction* to *raise* the proposed recovery metric.

**Observation 2 (normalizer coupling)**: `recovery_AUC` is normalised by `drop_magnitude` — the very quantity PR-2 measures. This means `recovery_AUC` and `drop_magnitude` are coupled at the definitional level: they cannot vary independently.

Both observations are derivable from the definitions alone; no empirical data is required.

### 4.4 The empirical verification

We ran a pre-execution empirical check (`scripts/f4b_metric_substitution_check.py`) on a fresh sample of 30 topologies (independent of PR-2's intended sample) with 50 nodes each. The check computed:

- **Artifact rate on the intervention arm**: 20/21 = **95.2%** — i.e., in 20 of 21 bridge-edge deletions, `recovery_AUC` *rose* after the "damage";
- **Reverse artifact rate on the control arm**: 18/21 = **85.7%** — i.e., in 18 of 21 non-bridge-edge deletions, `recovery_AUC` *fell* after the "control" intervention;
- **Merged-arm correlation**: |corr(Δbridge_fraction, Δrecovery_AUC)| = **0.902**;
- **Single-arm (non-bridge) correlation**: |corr| = **0.906**;
- **Intervention-arm correlation alone**: |corr| = 0.354 (below the pre-registered rejection threshold of 0.5).

### 4.5 The rule's own insufficiency

The preregistered rejection rule (|corr| > 0.5) flagged only the merged-arm sample. On the intervention arm alone, the variance of Δbridge_fraction was compressed to 4.82 × 10⁻⁵ by the intervention itself (all bridges were deleted), so |corr| = 0.354 fell below the rejection threshold — a spurious "ACCEPT" verdict.

The analyst explicitly recorded `rule_underpowered = true` on the intervention arm and did **not** modify the threshold. The rejection stood on:

- The analytic proof (Observations 1 and 2);
- The merged-arm correlation of 0.902 (far above threshold);
- The artifact rate of 95.2% on the intervention arm with 85.7% reverse separation on the control arm.

### 4.6 The unexplored alternatives

The preregistered rejection record also documented three alternatives that were considered but not pursued:

1. **Larger n**: rejected because changing n affects effect size, not the denominator artifact;
2. **Half-life of recovery (t½)**: rejected because t½ is derived from the same trajectory, so it carries the same coupling;
3. **An independent second read-out under real dynamics**: identified as the *only* path forward, but noted to be outside the project's current compute substrate.

### 4.7 The boundary conclusion

With `drop_magnitude` effect size ≤ 0.001 at n ≤ 100, and no independent second read-out in the current metric family, **L4 (causal) evidence for the bridge → isolation link is not attainable within the current substrate**.

This is a **scope boundary** — a call for a new instrument — not a sample-size failure. Framing it as the latter would prescribe more runs of the same instrument; framing it as the former prescribes a new measurement. The distinction matters: it changes the follow-up work from "run more" to "build something different."

---

## 5. Discussion

### 5.1 The interpretive value of preregistered rejection

Preregistered rejection is not merely "another failure." It has a distinct interpretive value:

- **Documentation of decisions not taken** — every refusal has a cost; documenting it prevents silent abandonment;
- **Boundary identification** — a preregistered rejection pinpoints the substrate limits of the current measurement family;
- **Anti-rationalization** — by requiring $U$ and $T$ to be documented before execution, the format prevents post-hoc rationalization.

### 5.2 Substrate limits vs. sample-size limits

The PR-2b case is a canonical example of a **substrate limit**: a limitation that cannot be resolved by gathering more data, only by changing the instrument. The two framings prescribe different actions:

| | Sample-size limit | Substrate limit |
|---|---|---|
| **Nature** | Underpowered study | Missing measurement |
| **Diagnosis** | Effect size ≤ detection threshold | No independent read-out exists |
| **Prescription** | Run more samples | Build a new instrument |
| **Failure mode** | Not enough data | Wrong instrument |

A preregistered rejection that identifies a substrate limit is thus scientifically more informative than a preregistered failure at any sample size: it tells future researchers *not* to run more of the same.

### 5.3 The R-0.4 extension

The R-0.4 discipline from our project's preregistration protocol states: *"failed experiments are reported, not adjusted."* PR-2b extends this to: *"not-run experiments are also reported, with their reason."* This is a small but important extension:

- **Without R-0.4**: the analyst is free to abandon E2 without documentation.
- **With R-0.4 (extended)**: the analyst must record the refusal, its justification, and its unexplored alternatives.

This extension closes a small loophole: the space of *experiments that could have been run but were not*, together with the decision process that ruled them out. In practice, the preregistration record now contains `unexplored_alternatives` alongside the primary decision basis, so future readers can reconstruct not just what the analyst did but what she chose not to do and why.

### 5.4 Relation to existing literature

Preregistered rejection is related to but distinct from:

- **Pre-registration registries** (OSF, AsPredicted, PRISMA): these register *when* and *how* an experiment is run; they do not register *refusal to run*;
- **Retraction and correction**: these apply after publication; preregistered rejection applies before execution;
- **Replication registries**: these register *replications*; preregistered rejection registers *non-executions*;
- **Pre-registration of null hypotheses**: these register the *intent* to test null hypotheses; preregistered rejection registers the *decision not to test*.

To the best of our knowledge, preregistered rejection as a formal category is not covered by any of these frameworks.

### 5.5 Machine enforcement and the anti-rationalization property

Gate 47 enforces preregistered rejection integrity by:

- Independent recomputation from raw samples (not the analyst's summary);
- Explicit declaration of `criteria_modified_after_results = False`;
- Population of `unexplored_alternatives` as a non-trivial field;
- Recording of `rule_underpowered` when applicable (preventing silent threshold changes).

This anti-rationalization property is what makes preregistered rejection *credible*. Without machine enforcement, an analyst could easily rationalize a refusal post-hoc; with it, the refusal must be justified before execution and any post-hoc adjustment is detected.

---

## 6. Conclusion

We proposed **preregistered rejection** as a third category of preregistered output, alongside preregistered success and failure. We formalized it as a tuple that includes the proposed experiment, the pre-execution decision, an independent justification, unexplored alternatives, and a lift condition. We described Gate 47, a machine-enforced integrity checker that verifies the anti-rationalization property. We illustrated the category with PR-2b — a case in which the pre-execution analysis proved analytically (and confirmed empirically at |corr| = 0.902) that the proposed substitute metric was redundant with the intervention.

The interpretive value of preregistered rejection is threefold:

1. **Documentation of decisions not taken** — the space of refused experiments is a scientific record in its own right;
2. **Boundary identification** — preregistered rejection pinpoints substrate limits that cannot be resolved by more data;
3. **Anti-rationalization** — machine enforcement prevents post-hoc rationalization of why an experiment was not run.

We argue that preregistered rejection is scientifically *more informative* than preregistered failure at any sample size, when the failure mode is a substrate limit rather than a sample-size limit. It tells future researchers not to run more of the same — a message that preregistered failure alone cannot convey.

**Future work**: (i) apply preregistered rejection to a second domain to test its generality; (ii) develop a public registry for preregistered rejections; (iii) investigate whether other preregistered categories (e.g., preregistered abandonment, preregistered scope change) deserve formal treatment.

---

## Data and code availability

- Preregistered rejection record: `research_claims.json.preregistered.PR2b`
- Pre-execution analysis script: `scripts/f4b_metric_substitution_check.py`
- Integrity checker (Gate 47): `scripts/check_metric_substitution.py`
- Full preregistration protocol: `docs/PREREGISTRATION_PROTOCOL_v1.md#PR-2b`
- Main paper (§4.8 discusses PR-2b in context): `docs/arxiv_paper.md`

Repository: `lm203688/flybrain-connectome` (MIT). The 5.63 GB raw connectome is not redistributed; obtain MaleCNS v1.0 from the original publication.

---

## Acknowledgments

The preregistration protocol (R-0.1 time-ordering, R-0.2 machine fixation, R-0.3 one-shot verification, R-0.4 failed-experiment publication) and its extension to preregistered rejection (R-0.4′ not-run-experiment publication) were developed as part of the `flybrain-connectome` project. The case study draws on a series of preregistered experiments (PR-1, PR-2, PR-3, PR-4) conducted over the period 2026-10-09 to 2026-10-15.

---

## References

1. MaleCNS v1.0 — whole-brain connectome of the male *Drosophila*, *Cell*, 2026 (CC-BY).
2. Preregistration Protocol v1 (`docs/PREREGISTRATION_PROTOCOL_v1.md`) — this project's preregistration standard.
3. Gate 47 (`scripts/check_metric_substitution.py`) — machine-enforced preregistered rejection integrity.
4. Preregistration Registry — Open Science Framework (OSF).
5. AsPredicted — preregistration service for social and behavioral research.
6. PRISMA — Preferred Reporting Items for Systematic Reviews and Meta-Analyses.

---

*Preprint — under review. Contact: `lm203688@...`*
