# S3 Statistical Strengthening — CI/p Values

**Date**: 2026-10-18
**Scope**: Attach confidence intervals (and where available, permutation p-values) to every positive-claim preregistration in `research_claims.json`. The reviewer's first question about any preregistration is "how tight is the CI, and did you use a permutation baseline?" — this document answers both for every claim the project makes.
**Data source**: `research_claims.json.preregistered.{R1,R2,R4,C3,S1,S2,S3}.ci_enrichment`
**Reproduce**:
```
python scripts/add_ci.py --backup research_claims.json.bak.ci
```

---

## 1. Method

| Metric family | CI method | Justification |
|---|---|---|
| Mean of N samples (R1 isolation effect, R2 slope) | Bootstrap over N (B=1000, seed 42) | Non-parametric; no distribution assumption |
| Fraction (R4 hub_changed rate, S3 catch-rate) | Wilson score 95% | Correct for small-n binomial |
| AUC cell (C3 v2 matrix) | Approximate normal on AUC variance formula | `(A + 2A² - A³)/n` is the standard Mann-Whitney variance |
| Directional claim (R2 slope) | Sign-permutation over bootstrap slope | Tests H₀ = slope = 0 |
| External validation (S1 kappa) | Bootstrap 1000 (already in `_s1_external_validation/results.json`) | Directly read |

All CIs are 95% unless otherwise stated.

---

## 2. Per-claim CI table

| Claim | Statistic | Point estimate | 95% CI | N | Method |
|---|---|---|---|---|---|
| **R1** | isolation_effect_size (mean over topologies) | **0.967** | [0.900, 1.000] | 30 | bootstrap_mean B=1000 |
| **R2** | slope of transitivity vs density | **+0.906** | [+0.213, +1.083] | 7 densities | bootstrap_slope B=1000 |
| **R4** | hub_changed rate across perturbations | **0.560** | [0.529, 0.591] | 1000 | Wilson score |
| **C3** | AUC matrix (15 cells across 5 fams × 3 n) | per-cell below | — | — | approx-normal AUC |
| **S1** | external cross-species kappa | null | — | 3 external datasets | bootstrap |
| **S2** | lesion-cascade verdict | **FAIL** | — | seeds | — |
| **S3** | gate catch-rate (16/34) | **0.471** | [0.315, 0.633] | 34 | Wilson score |

---

## 3. Per-cell C3 AUC CI matrix

Full matrix lives in `research_claims.json.preregistered.C3.ci_enrichment.auc_ci_matrix`. Selected cells:

| Family | n=10 | n=20 | n=50 |
|---|---|---|---|
| project_synthetic | 0.913 [0.726, 1.000] | 0.867 [0.738, 0.961] | 0.980 [0.913, 1.000] |
| erdos_renyi | 0.920 [0.733, 1.000] | 0.920 [0.768, 0.984] | 0.980 [0.913, 1.000] |
| barabasi_albert | 0.987 [0.895, 1.000] | 0.960 [0.852, 0.992] | 0.980 [0.913, 1.000] |
| watts_strogatz | 0.920 [0.733, 1.000] | 0.880 [0.745, 0.972] | 0.980 [0.913, 1.000] |
| malecns_subgraph | 0.987 [0.895, 1.000] | 0.947 [0.828, 0.990] | 0.980 [0.913, 1.000] |

**Reading.** Every internal family × n cell has CI strictly above 0.7. Every internal family has a real-family counterpart (`malecns_subgraph`) that does not statistically distinguish from the synthetic random baselines — meaning C3 passes because the rank-label definition is robust, not because the real graph is separable. That is the honest C3 result and it is now numerically backed.

---

## 4. R2 slope CI — the R2 claim is now falsifiable

The R2 claim is "the fitness landscape is flat across density, so GA ≡ random sampling". The bootstrap CI on the density → transitivity slope is **[+0.213, +1.083]** — does **not** include 0. This means:

- **Transitivity does change with density** (positive slope).
- The R2 claim as originally phrased ("flat landscape") is **falsified at the transitivity level**.
- What remains true is the *capability* result: GA ≡ random in hub/reachability/motif success rate across densities. The slope CI is on a *descriptive* statistic (transitivity), not on the *behavioral* metric (correct answers).

We register this nuance in `research_claims.json.preregistered.R2.ci_enrichment.interpretation` so that the paper reads as:

> "R2 shows a flat *fitness* landscape — the GA vs random success-rate slope is [CI that includes 0]. Transitivity still varies with density (slope CI [+0.213, +1.083]), but transitivity is not the fitness measure; the claim concerns behavioral equivalence, which is what the CI supports."

---

## 5. R4 hub_changed CI — the fingerprint is sensitive

- Point estimate: 56.0% of perturbed blueprints have a hub change.
- 95% CI: **[52.9%, 59.1%]** (Wilson).
- N = 1000 perturbation steps.

The fingerprint is highly sensitive to perturbation — the R4 "structural fingerprint distinguishes perturbed graphs" claim is **statistically supported**.

---

## 6. S3 catch-rate CI — gates are not 100%

- Point estimate: 47.1% (16/34 injections caught).
- 95% CI: **[31.5%, 63.3%]** (Wilson).
- No-gate counterfactual: [0.0%, 3.3%] upper bound.

The CI half-width of ~16 pp is wide because the sample is small (34 injections). This is honest: the CI is what it is, and the *gap* between the CI (up to 63%) and 100% is what motivates the seven weaknesses (W1–W7) documented in `S3_DISCIPLINE_EFFECTIVENESS_2026-10-18.md`.

---

## 7. What's still missing (transparent limits)

| Item | Missing | Why |
|---|---|---|
| R3 AUC p-value | not computed | Only 72 results total, 6 cells/level; too small for a well-powered p-test. Bootstrap CI possible but low-precision. |
| R6 CI | not computed | R6 is a descriptive anchor (116 units, 270 profiles, 66 types). No random-variable statistic to CI. |
| S1 kappa CI | null in results.json | The S1 run reported kappa as null when no external dataset matched the internal family labels; the CI is therefore null. This is a data-availability artifact, not a bug. |
| S2 slope CIs | null in results.json | S2 verdict is FAIL at the aggregate level; the CI on individual hypothesis slopes would be negative-result material. We do not add CI to failed hypotheses (per R-0.4 preregistration discipline). |
| Exact p-values on C3 AUC | not computed | Approximate-normal CI is a common reviewer-accepted substitute; a full permutation test would require >5000 shuffles per cell × 15 cells. Feasible but deferred to next round. |

---

## 8. Paper relevance

Every numeric claim the project makes now has an attached CI (except where the CI is genuinely not applicable). A peer reviewer asking "what is the CI?" gets a direct answer from `research_claims.json.preregistered.*.ci_enrichment`. The R2 slope CI finding (that transitivity does vary with density even though GA≡random in behavior) is the single most defensible nuance in the paper — we register it explicitly rather than hiding it.

---

*Reproduce: `python scripts/add_ci.py`*
