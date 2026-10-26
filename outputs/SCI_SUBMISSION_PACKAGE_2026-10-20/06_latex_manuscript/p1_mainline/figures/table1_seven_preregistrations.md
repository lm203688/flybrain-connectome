| Protocol | Focus | Design | Effect | CI | p-value | Verdict |
|---|---|---|---|---|---|---|
| PR-1 | Mechanism predictability | 200 permutations | 0.788 | z=1.5291 | p=0.1262 | WEAK |
| PR-2 | Intervention effect | n=10/50/100 | composite 38.9→71.4→59.1 | n/a | n/a | FAIL |
| PR-3 v1 | Generalization (n=10) | 5 families | 2/5 pass | n/a | n/a | FAIL |
| PR-3 v2 | Generalization w/ quantile labels | 5 families | n/a | n/a | n/a | FAIL |
| PR-4 | Recovery dynamics | n=1000 | 560/1000 | Wilson [0.5291, 0.5905] | p≈0.00015 | PASS |
| PR-2b | Pre-execution rejection | n/a (not run) | n/a | n/a | n/a | REJECT |
| PR_S1 | Cross-species external validation | 3 datasets | PARTIAL (mean AUC) | bootstrap CI | n/a | PARTIAL |
| PR_S2 | Lesion cascade w/ Xu 2026 bridge | 500 bootstrap | d=1.153, ρ=-0.1795 | bootstrap | p=0.0149 | FAIL |