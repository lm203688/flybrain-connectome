**Table 2.** Top-level statistical summary of the six research_claims.json entries. All positive claims now carry CI, test name, and effect-size metric at the top level of the JSON — enforced by Gate 63 (`scripts/check_claim_stats.py`). Wilson intervals are used for binary proportions; bootstrap percentile intervals for continuous slopes.

| ID | Claim focus | Point estimate | 95% CI | Test / metric | Verdict |
|---|---|---:|---|---|---|
| R1 | Fault isolation: structure×task alignment | AUC 0.788 | null mean 0.497, z=1.529, p=0.126 | 200-perm null, one-shot held-out | supported_after_metric_fix (WEAK) |
| R2 | Searchability condition (GA vs random) | slope 0.906 | bootstrap [0.214, 1.083] | Density scan, ≥20 seeds | complete |
| R3 | Structure-value × substrate alignment | 2/5 families | — | Family-generalisation threshold | boundary_partial_falsification |
| R4 | Structural fingerprint reproducibility | 560/1000 (0.560) | Wilson [0.529, 0.591] | Hub-change on 1000 seeds, p≈1.5e-4 | complete |
| R5 | Structural-level digital-life closed loop | didactic test | — | Deterministic assertion suite | complete |
| R6 | Cross-clade motif conservation | 37/116 anchored | Wilson [0.247, 0.402] | Anchored-coverage rate on 116 units | boundary_anchor_gap |
| — | S3 discipline-effectiveness | 51/51 caught | Wilson [93.0%, 100.0%] | Mutation-injection battery | hardened (v2.98.1) |

**Statistical notes.** R1's p=0.126 is reported as WEAK per preregistration; we do not adjust α to reach significance. R2's bootstrap CI is wide but brackets 1.0, consistent with GA ≡ random on this substrate. R3/R6 are boundary reports (partial falsification, anchor gap), not PASS/FAIL — they describe what the substrate can and cannot support.
