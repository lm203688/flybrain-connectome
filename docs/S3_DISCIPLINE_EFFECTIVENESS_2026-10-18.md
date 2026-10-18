# S3 Discipline Effectiveness — Quantified Gate Coverage

**Date**: 2026-10-18
**Scope**: Quantify the violation-catch rate of every preregistration gate in the project. This is the "what if there were no gate" counterfactual — the single most defensible number we can produce for a methodological paper about preregistration.
**Data**: `_s3_discipline_effectiveness/results.json`
**Reproduce**:
```
python scripts/s3_discipline_effectiveness.py --repeats 3 --seed 42
```

---

## 1. Setup

For each preregistration protocol we mutated a copy of `research_claims.json` with a class of violation (threshold drift, dropped feature, seed flip, etc.), then ran the corresponding gate and counted whether the injected defect was flagged.

**Mutation → Gate matrix**

| Protocol | Injection target | Gate that owns it |
|---|---|---|
| PR1 | Manifest↔execution integrity (threshold, features, slice, seed, perm) | `check_preregistered_claims.py` |
| PR2b | Rejection rule fields | `check_metric_substitution.py` |
| PR3_v2 | Label definition, change_from_v1, family list | `check_c1_c3.py` |
| C3 | Verdict, real-family passing, AUC matrix | `check_c1_c3.py` |
| PR_S1 | Success criteria (new protocol, no gate yet) | **none** |

34 total injections (5 protocols × 3–5 mutation classes × 2 repeats), seed 42.

---

## 2. Headline numbers

| Metric | Value |
|---|---|
| Total injections | 34 |
| Caught by gates | **16 (47.1%)** |
| Missed by gates | 18 (52.9%) |
| Counterfactual (no gates) | 0/34 caught |
| Miss-rate reduction | 100% → 52.9% |
| Protocols with **no dedicated gate** | 1 of 5 (`PR_S1`) |

**One-line interpretation.** Preregistration gates catch slightly less than half of the violations we can think of injecting. The remaining half are (a) silent-field mutations, (b) verdict-only flips that the gate cannot see, and (c) coverage gaps where the protocol has not yet been gated.

---

## 3. Per-protocol results

| Protocol | Catch-rate | Mutation coverage | Interpretation |
|---|---|---|---|
| **PR1** | **80.0%** (8/10) | 4/5 mutations caught; `seed_mismatch` escapes | Strong; only structural seed check is missing |
| **PR3_v2** | **66.7%** (4/6) | 2/3 caught; dropping `malecns_subgraph` from `families` escapes | Good; family-membership not gated |
| **PR2b** | **33.3%** (2/6) | Only threshold changes caught; rule removal & direction flip miss | **Weak** — reject-rule structure is not validated |
| **C3** | **33.3%** (2/6) | Only verdict flip caught; AUC drop and real-family removal miss | **Weak** — AUC monotonicity not enforced |
| **PR_S1** | **0.0%** (0/6) | No gate exists | **Coverage gap** — new protocol, pending gate |

---

## 4. Concrete gate weaknesses (from missed injections)

These are the actionable findings — each is a place where the gate is either silent or too lax.

| # | Protocol | Missed mutation | What the gate should check |
|---|---|---|---|
| W1 | PR1 | `seed_mismatch` — flip `preregistered.PR1.seed` | Manifest↔execution seed equality |
| W2 | PR2b | `remove_reject_rule` — delete `preregistered.PR2b.reject_rules` | `reject_rules` non-empty and non-null |
| W3 | PR2b | `wrong_direction` — flip `declared_direction_for_recovery_auc` to `increase` | Direction must be `"decrease"` for PR2b recovery test |
| W4 | PR3_v2 | `no_real_family` — remove `malecns_subgraph` from `families` | `malecns_subgraph ∈ families` is mandatory |
| W5 | C3 | `lower_auc` — subtract 0.2 from every cell in `auc_matrix_summary` | Monotone AUC bounds or per-cell sanity range |
| W6 | C3 | `remove_real_family_passing` — flip `real_family_passing` to `false` | `real_family_passing == true` for C3 PASS |
| W7 | PR_S1 | Any mutation | No gate exists; `check_pr_s1.py` is a first-order gap |

These are the exact items a follow-up round would fix. We register them honestly rather than inflating the catch-rate.

---

## 5. Paper relevance

This is the number that a peer reviewer would demand to see before believing "we have disciplined preregistration":

> *"Our preregistration gates catch 47.1% of the injected defects (16/34). We enumerate the seven residual holes (W1–W7) and the two protocols for which no gate yet exists."*

Every number above is reproducible from a single command. The `seed_mismatch` miss, in particular, is the strongest evidence that "gates are not free": they only catch the violations we taught them to catch.

---

## 6. Counterfactual sanity check

The `counterfactual_miss_rate_without_gate = 1.0` baseline is a strict assumption: without gates, a preregistration violation would not be flagged by any external check. That is a generous upper bound for the value of gates, because real-world review still catches some silent defects (e.g., an external reviewer noticing a suspicious seed flip).

Even under this generous baseline, the observed 47.1% catch-rate is the honest, published number.

---

## 7. Follow-up (H2)

The seven weaknesses W1–W7 above are the natural next-round preregistration hardening targets. Priority order:

1. **W2 + W3** (PR2b structure): one small schema check.
2. **W7** (PR_S1): new gate `check_pr_s1.py`.
3. **W4 + W5 + W6** (C3 monotonicity): one assertion per cell.
4. **W1** (PR1 seed): one equality check.

Each is <50 LOC and would raise the catch-rate toward 90%. We **do not** do this in this round; the current 47.1% is the honest published state and the seven holes are the paper's "what we didn't do" section.

---

*Reproduce: `python scripts/s3_discipline_effectiveness.py --repeats 3`*
