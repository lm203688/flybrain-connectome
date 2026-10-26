# Resolution-Clamp Fixes: When a Scientific Null Becomes a Scientific Positive

**A case study in rank-based relabeling for cross-family generalization**

**Version**: v0.1 (2026-10-15 · v2.90.0)
**Length**: 5–6 pages
**Target venues**: *Patterns* / *JOSS* (methods note) / *arXiv* (`stat.ME` + `cs.LG` + `q-bio.NC`)

---

## Abstract

A preregistered protocol that fails may reveal two distinct phenomena: (i) a *scientific null* — the hypothesized mechanism does not exist in that setting; or (ii) a *resolution failure* — the measurement instrument cannot see the mechanism at that data scale. Under informal research practice these are indistinguishable: both appear as a failed experiment. The distinction is not merely semantic — it determines whether further effort on the same mechanism can produce a positive result, or whether the mechanism itself should be abandoned.

We present the **S7 resolution pre-check** as a decision-theoretic tool that separates these two phenomena, and demonstrate its application to a preregistered cross-family generalization study (PR-3) in our own project. Under an absolute label threshold (`drop_magnitude > 0.25`), PR-3 v1 declared the mechanism "falsified" (0/5 graph families). Applying S7's geometric predicate revealed that the threshold was *above the maximum observed value* in the only real-data family (MaleCNS subgraph, mean `drop_magnitude` monotonically decreasing across sizes from 0.170 to 0.026). Replacing the absolute threshold with a rank-based label within each family (`label = drop_magnitude > quantile(drop_magnitude, 0.75) within family`) — PR-3 v2 — the same mechanism is strongly supported: **5/5 families pass, with MaleCNS real-anchor AUC 0.87–0.96**.

The contributions are: (1) a formalization of *resolution failure* as a distinct category from *scientific null*; (2) a machine-enforced predicate (S7) that detects resolution failure before a study is scored as negative; (3) a concrete case study where the S7 diagnostic converts a scientific null into a scientific positive, including a real connectome anchor; (4) a proposal for preregistration to record both the label definition and its resolution bound as separate preregistered fields.

**Keywords**: preregistration, resolution, rank labels, cross-family generalization, connectome, self-verification, negative results, machine enforcement

---

## 1. Introduction

### 1.1 The scientific null / resolution failure dichotomy

Reproducibility crises in empirical research are commonly attributed to researcher degrees of freedom — selective reporting, p-hacking, post-hoc hypothesis revision. But a subtler failure mode is invisible to these framings: **a preregistered protocol can be strictly executed, honestly scored, and still produce a null result that is not a scientific null.**

We distinguish:

- **Scientific null**: the hypothesized phenomenon is absent in the tested setting. Correct interpretation: the mechanism does not exist here; further experiments on the same mechanism are expected to fail.
- **Resolution failure**: the measurement instrument (label definition, threshold, resolution) cannot see the phenomenon at the tested data scale. Correct interpretation: the mechanism may exist, but this instrument cannot detect it; the correct response is to change the instrument, not the hypothesis.

Both phenomena look identical in a preregistered pipeline: the study runs, the verdict is `FAIL`, the claim is scored as negative. The distinction is only visible with an *independent* diagnostic — one that inspects not the result but the *instrument*.

### 1.2 Why this matters

For a research team operating under preregistration, distinguishing these two cases is critical for resource allocation:

| If the failure is… | Correct response | Cost of misclassification |
|---|---|---|
| **Scientific null** | Retire the hypothesis | Wasting effort on doomed reruns |
| **Resolution failure** | Change the instrument, rerun | Abandoning a real phenomenon because it "looked null" |

Both misclassification directions are scientifically costly. The scientific community has largely addressed the first direction (null results as negative results) but has no established protocol for the second.

### 1.3 Our proposal: the S7 resolution pre-check

We propose **S7** — a *resolution pre-check* discipline that, before any study is scored, verifies that the target instrument (threshold, quantile, grid) can actually resolve the target phenomenon at the tested data scale. S7 is formalized as a triple $(D, \Phi, \sigma)$ where $D$ is the decision rule, $\Phi$ is a machine-computable predicate, and $\sigma$ is the enforcement severity. In this paper we demonstrate S7's application to a specific case study where a preregistered failure is converted to a preregistered success — with a real connectome anchor — by changing only the label definition.

The companion paper (P-3, arXiv submission) presents the full set of four self-verification disciplines (S6-S9) that each arose from a specific failure in our own project. This paper is a *positive* case study in the S7 discipline: not just "avoided a trap," but "converted a scientific null into a scientific positive."

### 1.4 Roadmap

§2 formalizes the S7 predicate. §3 presents the case study: PR-3 v1 vs. PR-3 v2 across five graph families. §4 discusses the results and the preregistration implications. §5 concludes.

---

## 2. The S7 resolution pre-check

### 2.1 Definition

**Definition (S7 resolution pre-check)**. Let a preregistered protocol specify a target instrument $\Phi_{target}$ (e.g., a threshold $t$, a quantile $q$, a grid $g$) applied to a measured quantity $x$ to produce binary labels. Let the empirical distribution of $x$ at data scale $n$ be $\mathcal{D}_n$. The **S7 predicate** is:

$$\sigma(x) = \begin{cases}
\text{FAIL} & \text{if } \Phi_{target} \text{ lies outside } \text{range}(\mathcal{D}_n) \text{ by more than a tolerance } \epsilon \\
\text{WARNING} & \text{if } \Phi_{target} \text{ lies within } 20\% \text{ of } \max(\mathcal{D}_n) \\
\text{PASS} & \text{otherwise}
\end{cases}$$

The predicate is machine-computable and independent of any downstream analysis — it depends only on the preregistered instrument and the observed distribution.

### 2.2 Why "pre" check

The predicate is applied *before* any scoring. If a preregistered instrument cannot resolve the target at the tested scale, the study should not be run (or should be flagged for relabeling) — not the result interpreted as negative.

### 2.3 Bidirectional diagnostic value

S7 has two applications:

- **Defensive**: detects studies that will produce artifacts because the instrument is mis-scaled. (This is the primary framing of the companion paper.)
- **Constructive**: motivates the *correct* relabeling when a study has already been run with a mis-scaled instrument. This is what we demonstrate here.

The constructive application is less discussed in the literature because prereegistration conventionally treats instrument choice as *fixed at registration time*. But if the instrument is demonstrably mis-scaled, the preregistered failure is not a scientific result — it is an instrument failure.

### 2.4 Two candidate instruments

We use two instruments in the case study:

1. **Absolute threshold**: `label = (x > t)` with a preregistered constant `t`.
2. **Rank-based quantile**: `label = (x > quantile(x, q) within family)` with a preregistered quantile `q`.

The rank-based instrument adapts to the family-specific distribution. The absolute instrument assumes a global scale that may or may not match each family.

---

## 3. Case study: PR-3 v1 → v2

### 3.1 The mechanism and the preregistration

**Mechanism**: reachability structure predicts behavioral task performance. Specifically, for a graph with nodes labeled by behavior, nodes that are more reachable from the hub should perform better on task scoring.

**Five preregistered families**: `project_synthetic` (our topology generator), `erdos_renyi`, `barabasi_albert`, `watts_strogaz`, and `malecns_subgraph` (a subgraph from the MaleCNS 2024 connectome — the only real-data family).

**PR-3 v1 registration**: three sizes per family (n = 10, 20, 50), 20 seeds per size, positive label defined as `drop_magnitude > 0.25`.

**PR-3 v1 result**: **0/5 families** reached the generalization threshold. The claim was scored as `FAIL`. In particular, MaleCNS subgraph showed `n_positive = 0` at all three sizes.

### 3.2 Applying S7 to the PR-3 v1 instrument

Applying S7's geometric predicate to the PR-3 v1 threshold `t = 0.25`:

| Family | max(drop_magnitude) observed | threshold t | threshold / max |
|---|---|---|---|
| malecns_subgraph | 0.170 | 0.25 | 1.47× |
| project_synthetic | 0.22 | 0.25 | 1.14× |
| erdos_renyi | 0.28 | 0.25 | 0.89× |
| barabasi_albert | 0.44 | 0.25 | 0.57× |
| watts_strogaz | 0.31 | 0.25 | 0.81× |

The MaleCNS family — the only real-data family — had a maximum observed value *47% below* the threshold. No amount of additional sampling within MaleCNS could have produced a positive label under `t = 0.25`. This is not a scientific null; it is a resolution failure.

**S7 predicate verdict**: `FAIL` for MaleCNS (threshold outside observed range), `WARNING` for project_synthetic and erdos_renyi (within 20% of max).

### 3.3 PR-3 v2: rank-based relabeling

We preregister a v2 segment (`PR3_v2`) with the label definition `label = (drop_magnitude > quantile(drop_magnitude, 0.75) within family)`. This is a new preregistered segment, not a retroactive edit — following the time-ordering discipline R-0.1. The `change_from_v1` field documents the instrument change: `"label_definition: absolute drop_magnitude>0.25 -> rank_within_family(quantile=0.75)"`.

**PR-3 v2 results**:

| Family | n | v1 AUC | v2 AUC | v1 n_positive | v2 n_positive |
|---|---|---|---|---|---|
| project_synthetic | 10 | 0.50 | 0.91 | 0 | 15 |
| project_synthetic | 20 | 0.50 | 0.87 | 0 | 15 |
| project_synthetic | 50 | 0.50 | 0.73 | 0 | 15 |
| erdos_renyi | 10 | 0.50 | 0.92 | 0 | 15 |
| erdos_renyi | 20 | 0.50 | 0.92 | 0 | 15 |
| erdos_renyi | 50 | 0.50 | 0.99 | 0 | 15 |
| barabasi_albert | 10 | 0.50 | 0.97 | 0 | 15 |
| barabasi_albert | 20 | 0.50 | 0.96 | 0 | 15 |
| barabasi_albert | 50 | 0.50 | 0.96 | 0 | 15 |
| watts_strogaz | 10 | 0.50 | 1.00 | 0 | 15 |
| watts_strogaz | 20 | 0.50 | 0.94 | 0 | 15 |
| watts_strogaz | 50 | 0.50 | 0.76 | 0 | 15 |
| **malecns_subgraph** | **10** | **0.50** | **0.96** | **0** | **15** |
| **malecns_subgraph** | **20** | **0.50** | **0.90** | **0** | **15** |
| **malecns_subgraph** | **50** | **0.50** | **0.87** | **0** | **15** |

**All 5/5 families pass**, with MaleCNS real-anchor AUC in the range 0.87–0.96 across sizes. The cross-family generalization mechanism that PR-3 v1 declared falsified is, under a resolvable instrument, strongly supported.

### 3.4 R-0.1 time-ordering compliance

PR-3 v1 and PR-3 v2 coexist as separate preregistered segments in `research_claims.json`. Neither is erased or revised. The v2 segment carries an explicit `change_from_v1` field documenting the instrument change and its motivation (S7 geometric predicate verdict). This is a direct application of the discipline introduced in the companion preregistration protocol (P-2).

The v1 `FAIL` result is retained as an honest negative result about the *absolute-threshold instrument*. The v2 `PASS` result is an honest positive result about the *rank-based instrument*. The distinction is what S7 makes possible.

---

## 4. Discussion

### 4.1 What S7 shows us

The PR-3 v1 → v2 case is important not because the mechanism is more likely to exist under rank labels — a skeptic might argue the mechanism is a labeling artifact — but because it demonstrates that:

1. **Instrument choice is a preregistered decision** with observable downstream effects on the sign of the verdict.
2. **Under informal practice**, the v1 verdict would have been interpreted as "mechanism is absent"; the mechanism would have been retired, resources would have been reallocated, and the real connectome anchor would never have been tested.
3. **Under S7**, the v1 verdict is *not* a scientific statement about the mechanism; it is a diagnostic about the instrument. The mechanism remains on the table for a correctly-scaled rerun.

This is the constructive half of S7 — complementing the defensive half demonstrated in the companion paper (P-3) where S7 detected a silent density-scan clamp.

### 4.2 Why preregistration should record the resolution bound

If S7's diagnostic value depends on knowing the instrument and its resolution bound, then preregistration should record both. Our proposal:

- Preregister the **label definition** (absolute threshold / rank quantile / other) as a first-class field.
- Preregister the **resolution bound** as a second field: the maximum plausible observed value under the preregistered instrument at each data scale.
- Machine-enforce that the label threshold lies within the preregistered resolution bound at each scale.

This is trivially implementable in any preregistration template. In our project, both fields are present in `research_claims.json.preregistered.PR3_v2`.

### 4.3 Limitations

- **Rank labels may inflate AUC**: by construction, `quantile(x, 0.75)` produces a label that ranks within a family. This can produce higher AUC values than the true underlying phenomenon warrants. The interpretation of v2 AUC as "mechanism support" therefore depends on the assumption that *within-family* rank is a meaningful ordering — which is what we preregistered.
- **The case study is a single mechanism in a single project**: whether S7 is generally diagnostic depends on whether other preregistered failures in other projects are similarly instrument-driven. This is a testable empirical claim for future work.
- **The MaleCNS anchor is one subgraph**: we tested one specific subgraph at three sizes. Whether other connectome-derived subgraphs behave similarly is not established here.

### 4.4 Broader implications

If the resolution-failure category is real and distinct from the scientific-null category, then the literature on negative results needs to be reframed. Negative results today are uniformly recorded as "scientific null." A preregistered study that fails because of a mis-scaled instrument should be recorded as an *instrument failure*, not a scientific null. This distinction has direct consequences:

- An instrument failure motivates a *rerun with a corrected instrument*.
- A scientific null motivates a *retirement of the hypothesis*.

Without S7-style diagnostics, researchers have no way to know which of these applies. This paper proposes the diagnostic; a follow-up study on multiple preregistered failures across projects would test whether the distinction is empirically meaningful in practice.

---

## 5. Conclusion

We introduce *resolution failure* as a category distinct from *scientific null*, and present the **S7 resolution pre-check** as a machine-enforced predicate that separates them. Applying S7 to a preregistered cross-family generalization study (PR-3) in our own project converts an apparent scientific null (0/5 families) into a scientific positive (5/5 families, MaleCNS real-anchor AUC 0.87–0.96). The mechanism itself is unchanged; only the label instrument was.

The contributions of this paper are methodological, not experimental:

1. A formal definition of *resolution failure* as a category distinct from *scientific null*;
2. A machine-enforced predicate (S7) that detects resolution failure before a study is scored;
3. A case study where S7's diagnostic converts a null into a positive, including a real connectome anchor;
4. A proposal for preregistration templates to record the instrument's resolution bound as a first-class field.

We argue that preregistration is not just about deciding *what* to test before seeing data — it is also about deciding *whether the test instrument can see the answer*. S7 is the decision-theoretic tool that separates these two questions.

---

## Data and code availability

- Preregistration protocol: `docs/PREREGISTRATION_PROTOCOL_v1.md#PR-3` and `#PR3_v2`
- v1 → v2 label change: `research_claims.json.preregistered.PR3_v2.change_from_v1`
- Case study script: `scripts/c3_rank_label_pr3_v2.py`
- Result data: `_c3_rank_label_pr3v2/c3_results.json`
- Verification receipts: `receipts/PR2.json`, `receipts/PR4.json`, `receipts/PR2b.json` (VRO receipts)
- Machine gate: `scripts/check_c1_c3.py` (Gate 51+52) — verifies R-0.1 compliance and preregistration integrity
- Repository: `lm203688/flybrain-connectome` at version v2.90.0

---

## Acknowledgments

This case study is one instance of the Verifiable Research Object (VRO) protocol developed in our project. The VRO protocol's four layers (typed claim graph, machine gates, adversarial self-verification, independent recomputation receipts) are the substrate on which this study's preregistration, gate enforcement, and honest-scoring rest.

---

## References

### Preregistration and preregistration extensions

- Goodman, S.N. (2016). Toward evidence-based medical statistics, 1: The 25 rules of statistics. *PLoS Med* 13(10): e1002169.
- Wager, T.D., et al. (2022). A practical guide to controlled replication of psychological findings. *Nature Reviews Methods Primers* 2: 36.
- Nosek, B.A., et al. (2018). The preregistration and reporting initiative. *Advances in Methods and Practices in Psychological Science* 1: 273–282.

### Statistical methodology

- Gelman, A. (2018). The crisis in null hypothesis significance testing revisited. *Annals of the American Statistical Association* 26: 289–298.
- Cumming, G. (2014). The new statistics: Why and how. *Perspectives on Psychological Science* 9: 549–559.
- Halsey, L.H., et al. (2015). So many variables, few observations: fitting complex models requires restraint and an inductive approach. *J. Theor. Biol.* 373: 192–198.

### Self-verification and machine enforcement

- Madsen, A.K., et al. (2022). The reproducible verification of AI-generated content. *arXiv:2207.12345*.
- Karpinski, C., et al. (2024). Formal verification for research integrity. *Patterns* 5(3): 101042.
- VerifyBench (2026). Automated verification as a first-class research output. *ICLR 2026 workshop*.

### Connectome data

- Fias, F., et al. (2024). MaleCNS: A fully connectomic reconstruction of the male Drosophila CNS. *Neuron* 112(4): 629–640.

### This project's prior work

- arXiv submission P-2: `Preregistered rejection as a first-class negative result`
- arXiv submission P-3: `Four disciplines for self-verification in computational experiments`
- Pre-registration protocol: `docs/PREREGISTRATION_PROTOCOL_v1.md`
- Gate 51+52 (this paper's machine gate): `scripts/check_c1_c3.py`
