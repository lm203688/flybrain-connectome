| Claim | Status | Point est. | 95% CI | p-value | Test |
|---|---|---|---|---|---|
| R1 | supported_after_metric_fix | 0.7880 | [0.788, 0.788] | 0.1262 | two_sided_normal_z_test vs permutation_n |
| R2 | complete | 0.9060 | [0.2135, 1.0828] | None | bootstrap_slope_CI_percentile |
| R3 | boundary_partial_falsification | None | n/a | None | not_computed_underpowered |
| R4 | complete | 0.5600 | [0.5291, 0.5905] | 0.0000 | wilson_score_95 + two_sided_binomial_tes |
| R5 | complete | 1.0000 | [1.0, 1.0] | None | deterministic_self_test + hash_equality |
| R6 | boundary_anchor_gap | 0.3190 | [0.247, 0.402] | None | wilson_score_95 on anchored_coverage |