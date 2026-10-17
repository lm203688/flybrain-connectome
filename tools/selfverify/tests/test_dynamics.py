"""Unit tests for selfverify.dynamics — S3 minimum dynamics readout.

Zero-dependency: unittest only, runs via
    python -m unittest discover -s tests

Covers:
  - recovery_trajectory shape and monotonicity
  - recovery_fraction in [0, 1] and degenerate inputs
  - t_half and tau_recovery consistency (tau ≈ t_half / ln 2)
  - oscillation_frequency on a known sine-like signal
  - decay_rate sign convention (decay > 0, growth < 0)
  - steady_state_bias direction
  - compute_all returns every documented key
  - variance_over_trajectories non-degenerate detection
  - zero_ratio on an all-zero curve
"""
from __future__ import annotations

import math
import unittest

from selfverify.dynamics import (
    TAU_A, TAU_B, TAU_C,
    recovery_trajectory,
    recovery_fraction,
    t_half,
    tau_recovery,
    oscillation_frequency,
    decay_rate,
    steady_state_bias,
    compute_all,
    variance_over_trajectories,
    zero_ratio,
)


class TestRecoveryTrajectory(unittest.TestCase):
    def test_returns_T_plus_one_points(self):
        mods = {"R_a": 1.0, "R_b": 1.0, "R_c": 1.0}
        curve = recovery_trajectory(mods, drop_magnitude=0.5, T=20)
        self.assertEqual(len(curve), 21)  # indices 0..20

    def test_starts_at_zero(self):
        mods = {"R_a": 0.5, "R_b": 0.5, "R_c": 0.5}
        curve = recovery_trajectory(mods, drop_magnitude=0.8, T=10)
        self.assertEqual(curve[0], 0.0)

    def test_monotone_increasing_when_all_modulators_positive(self):
        mods = {"R_a": 0.6, "R_b": 0.4, "R_c": 0.2}
        curve = recovery_trajectory(mods, drop_magnitude=1.0, T=30)
        # The trajectory is a sum of concave-increasing exponentials
        # scaled by drop_magnitude; it must be non-decreasing.
        for i in range(1, len(curve)):
            self.assertGreaterEqual(curve[i], curve[i - 1],
                                    f"non-monotone at index {i}")

    def test_disabled_mechanism_contributes_nothing(self):
        mods = {"R_a": 1.0, "R_b": 1.0, "R_c": 1.0}
        full = recovery_trajectory(mods, drop_magnitude=0.5, T=15,
                                    enabled={"R_a", "R_b", "R_c"})
        only_a = recovery_trajectory(mods, drop_magnitude=0.5, T=15,
                                      enabled={"R_a"})
        # The full curve must be >= the single-mechanism curve at every point.
        for i, (f, s) in enumerate(zip(full, only_a)):
            self.assertGreaterEqual(f, s, f"full < only_a at t={i}")

    def test_zero_modulators_give_flat_zero(self):
        mods = {"R_a": 0.0, "R_b": 0.0, "R_c": 0.0}
        curve = recovery_trajectory(mods, drop_magnitude=0.9, T=10)
        self.assertTrue(all(v == 0.0 for v in curve))


class TestRecoveryFraction(unittest.TestCase):
    def test_zero_drop_magnitude_returns_zero(self):
        self.assertEqual(recovery_fraction([0.0, 0.5, 1.0], 0.0), 0.0)

    def test_empty_or_singleton_curve_returns_zero(self):
        self.assertEqual(recovery_fraction([0.5], 0.5), 0.0)
        self.assertEqual(recovery_fraction([], 0.5), 0.0)

    def test_result_clamped_to_unit_interval(self):
        # Very large drop_magnitude → fraction must stay <= 1
        big = [0.9, 1.0, 1.0]
        self.assertLessEqual(recovery_fraction(big, 0.1), 1.0)

    def test_known_small_case(self):
        # curve = [0, 0.25, 0.5, 0.75], drop=0.5
        # mean of curve[1:] = (0.25 + 0.5 + 0.75) / 3 = 0.5
        # fraction = 0.5 / 0.5 = 1.0
        self.assertAlmostEqual(recovery_fraction([0.0, 0.25, 0.5, 0.75], 0.5),
                               1.0, places=6)


class TestTHalfAndTau(unittest.TestCase):
    def test_t_half_finds_first_half_recovery(self):
        curve = [0.0, 0.1, 0.2, 0.25, 0.3, 0.5, 0.6]
        # drop=0.5 → 50% threshold is 0.25, first hit at index 3
        self.assertEqual(t_half(curve, 0.5), 3.0)

    def test_t_half_returns_none_when_never_reached(self):
        curve = [0.0, 0.05, 0.1, 0.15]
        self.assertIsNone(t_half(curve, 1.0))

    def test_tau_recovery_matches_half_time_formula(self):
        # If t_half = 2, tau = 2 / ln(2)
        curve = [0.0, 0.4, 0.5, 0.6, 0.7]
        # drop=0.5 → 50% threshold is 0.25, first hit at index 1
        t_h = t_half(curve, 0.5)
        self.assertEqual(t_h, 1.0)
        tau = tau_recovery(curve, 0.5)
        self.assertAlmostEqual(tau, 1.0 / math.log(2), places=6)

    def test_tau_returns_none_when_t_half_none(self):
        curve = [0.0, 0.01, 0.02]
        self.assertIsNone(tau_recovery(curve, 1.0))


class TestOscillationFrequency(unittest.TestCase):
    def test_short_curve_returns_none(self):
        self.assertIsNone(oscillation_frequency([1.0, 2.0]))

    def test_constant_signal_has_zero_frequency(self):
        curve = [1.0, 1.0, 1.0, 1.0, 1.0]
        self.assertEqual(oscillation_frequency(curve), 0.0)

    def test_known_crossing_count_gives_expected_frequency(self):
        # curve = [1.0, 2.0, 1.0, 0.0, 1.0, 2.0]  baseline = 1.0
        # diffs from baseline:  [0, +1, 0, -1, 0, +1]
        # crossings:
        #   i=1: prev=0 (<=0) curr=+1 (>0)  -> +1
        #   i=2: prev=+1 (>0) curr=0 (<=0)  -> +1
        #   i=3: prev=0 (<=0) curr=-1 (<=0) -> no
        #   i=4: prev=-1 (<=0) curr=0 (<=0) -> no
        #   i=5: prev=0 (<=0) curr=+1 (>0)  -> +1
        # n_crossings = 3, T = len(curve) - 1 = 5
        # freq = 3 / (2 * 5) = 0.3
        curve = [1.0, 2.0, 1.0, 0.0, 1.0, 2.0]
        f = oscillation_frequency(curve, baseline=1.0)
        self.assertAlmostEqual(f, 3 / (2 * 5), places=6)


class TestDecayRate(unittest.TestCase):
    def test_too_short_returns_none(self):
        self.assertIsNone(decay_rate([1.0, 0.5]))

    def test_decaying_signal_has_positive_rate(self):
        # 1.0, 0.8, 0.6, 0.4 → first half mean 0.9, second half mean 0.5
        rate = decay_rate([1.0, 0.8, 0.6, 0.4])
        self.assertGreater(rate, 0.0)

    def test_growing_signal_has_negative_rate(self):
        rate = decay_rate([0.4, 0.6, 0.8, 1.0])
        self.assertLess(rate, 0.0)

    def test_all_zero_returns_none(self):
        self.assertIsNone(decay_rate([0.0, 0.0, 0.0, 0.0]))


class TestSteadyStateBias(unittest.TestCase):
    def test_perfect_target_has_zero_bias(self):
        curve = [0.0, 0.5, 1.0, 1.0, 1.0, 1.0]
        self.assertAlmostEqual(steady_state_bias(curve, target=1.0), 0.0)

    def test_short_curve_uses_last_value(self):
        curve = [0.0, 0.4]
        self.assertAlmostEqual(steady_state_bias(curve, target=1.0), 0.6)

    def test_underrecovery_is_positive(self):
        curve = [0.0, 0.1, 0.2, 0.3, 0.4]
        bias = steady_state_bias(curve, target=1.0)
        self.assertGreater(bias, 0.0)

    def test_overrecovery_is_negative(self):
        curve = [0.0, 1.2, 1.3, 1.4, 1.5]
        bias = steady_state_bias(curve, target=1.0)
        self.assertLess(bias, 0.0)


class TestComputeAll(unittest.TestCase):
    def test_returns_all_documented_keys(self):
        out = compute_all({"R_a": 0.8, "R_b": 0.6, "R_c": 0.4},
                          drop_magnitude=0.5, T=20)
        expected = {"curve", "recovery_fraction", "t_half", "tau_recovery",
                    "oscillation_frequency", "decay_rate", "steady_state_bias",
                    "modulators", "drop_magnitude", "T", "enabled"}
        self.assertEqual(set(out.keys()), expected)

    def test_curve_length_matches_T(self):
        out = compute_all({"R_a": 1.0, "R_b": 1.0, "R_c": 1.0},
                          drop_magnitude=0.5, T=15)
        self.assertEqual(len(out["curve"]), 16)

    def test_disabled_mechanism_is_recorded(self):
        out = compute_all({"R_a": 1.0, "R_b": 1.0, "R_c": 1.0},
                          drop_magnitude=0.5, T=10, enabled={"R_a"})
        self.assertEqual(out["enabled"], ["R_a"])

    def test_recovery_fraction_matches_standalone(self):
        mods = {"R_a": 0.7, "R_b": 0.5, "R_c": 0.3}
        out = compute_all(mods, drop_magnitude=0.4, T=20)
        standalone = recovery_fraction(out["curve"], 0.4)
        self.assertAlmostEqual(out["recovery_fraction"], standalone, places=8)


class TestVarianceAndZeroRatio(unittest.TestCase):
    def test_variance_over_trajectories_zero_when_uniform(self):
        trajectories = [
            {"recovery_fraction": 0.5},
            {"recovery_fraction": 0.5},
            {"recovery_fraction": 0.5},
        ]
        self.assertEqual(variance_over_trajectories(trajectories), 0.0)

    def test_variance_over_trajectories_nonzero_when_spread(self):
        trajectories = [
            {"recovery_fraction": 0.2},
            {"recovery_fraction": 0.5},
            {"recovery_fraction": 0.8},
        ]
        self.assertGreater(variance_over_trajectories(trajectories), 0.0)

    def test_variance_ignores_none_entries(self):
        trajectories = [
            {"recovery_fraction": 0.5},
            {"recovery_fraction": None},
            {"recovery_fraction": 0.5},
        ]
        self.assertEqual(variance_over_trajectories(trajectories), 0.0)

    def test_variance_needs_at_least_two_values(self):
        trajectories = [{"recovery_fraction": 0.5}]
        self.assertEqual(variance_over_trajectories(trajectories), 0.0)

    def test_zero_ratio_all_zeros(self):
        self.assertEqual(zero_ratio([0.0, 0.0, 0.0]), 1.0)

    def test_zero_ratio_mixed(self):
        self.assertAlmostEqual(zero_ratio([0.0, 0.5, 0.0, 1.0]), 0.5)

    def test_zero_ratio_empty(self):
        self.assertEqual(zero_ratio([]), 0.0)


class TestTimeConstantConstants(unittest.TestCase):
    def test_taus_are_ordered(self):
        # R_a fast < R_b medium < R_c slow
        self.assertLess(TAU_A, TAU_B)
        self.assertLess(TAU_B, TAU_C)


if __name__ == "__main__":
    unittest.main()
