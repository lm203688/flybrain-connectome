**Table 1.** Summary of the seven preregistrations instantiated against the 116-unit Male CNS substrate. All protocols were hash-committed before execution; the vaults are at `vault/` and `registry/preregistered_rejections.json`. Endpoint labels are assigned by the preregistered acceptance rule (not by post-hoc judgement). CI denotes 95% confidence interval where applicable.

| ID | Protocol | Target metric | Observed | CI | Test | Endpoint |
|---|---|---|---:|---|---|---|
| PR-4 | Recovery dynamics | Hub-change rate on 1000 seeds | 0.560 | Wilson [0.529, 0.591] | z-test | **PASS** |
| PR_S1 | External validation (3 datasets) | Internal/external AUC split | 5/5 vs 0/3 above 0.8 | — | Family threshold | **PARTIAL** |
| PR-1 | Mechanism (label resolution) | Held-out AUC (n=40) | 0.788 | null mean 0.497, z=1.529, p=0.126 | 200-perm null | **WEAK** |
| PR-2 | Intervention (n-scan) | Composite score across n=10/50/100 | 38.9% / 71.4% / 59.1% | — | Preregistered monotonicity | **FAIL** |
| PR-3 | Cross-family generalisation | Families passing AUC>0.8 | 2/5 | — | Family threshold | **FAIL** |
| PR_S2 | Lesion cascade (MaleCNS subgraph) | Cohen's d on obs vs null tolerance | 1.153 | bootstrap 500 iters, ρ=−0.18, p=0.015 | One-sided bootstrap | **FAIL** |
| PR-2b | Pre-execution rejection | Artifact 95.2% reverse, |corr|=0.902 | — | Preregistered rejection rule | **REJECT-BEFORE-RUN** |

**Interpretation.** Four of the six executed preregistrations (PR-1, PR-2, PR-3, PR_S2) end in FAIL or WEAK, and the seventh is a preregistered refusal to execute at all. Only PR-4 is PASS and PR_S1 is honest PARTIAL. This is the endpoint distribution that a preregistered-negative-result regime is designed to produce; no FAIL has been silently re-scoped into PASS.
