"""Unit tests for selfverify.gate — the core verdict logic.

Deliberately pytest-free: these can run as `python -m unittest discover -s tests`
on any Python 3.9+ interpreter with zero install. The point of selfverify is
zero-dependency deployment; the tests should honour that.
"""
from __future__ import annotations

import unittest

from selfverify.protocol import Protocol
from selfverify.gate import auc, independent_recompute, check, pearson


def _demo_protocol(**overrides):
    base = {
        "id": "DEMO-1",
        "hypothesis": "A structural feature predicts held-out isolation.",
        "metric": "held_out_auc",
        "features": ["n_bridges", "bridge_fraction"],
        "success_criteria": {
            "held_out_auc_min": 0.7,
            "min_positive_held_out": 3,
        },
        "held_out_slice": "6:12",
    }
    base.update(overrides)
    return Protocol(**base)


def _held_out(scores_labels):
    """Build a results dict with only held-out samples."""
    return {"samples": [
        {"id": i, "split": "held_out", "score": s, "label": l}
        for i, (s, l) in enumerate(scores_labels)
    ]}


class TestAUC(unittest.TestCase):
    """AUC helpers — verify the rank-based computation matches expectation."""

    def test_perfect_separation_is_one(self):
        # All positives score above all negatives → AUC = 1.0 exactly.
        # (K5 kernel convergence: previously used "pairwise ties = 0.5" so
        # this returned 0.999; the Manna-Kendall rank-average formula gives
        # the mathematically exact 1.0, which is what the audit §K5
        # converged the codebase to.)
        self.assertAlmostEqual(auc([0.9, 0.8, 0.7, 0.4, 0.3], [1, 1, 1, 0, 0]), 1.0, places=6)

    def test_perfect_inversion_is_zero(self):
        # All positives score below all negatives → AUC = 0.0
        self.assertEqual(auc([0.3, 0.2, 0.1, 0.6, 0.5], [1, 1, 1, 0, 0]), 0.0)

    def test_all_one_class_returns_half(self):
        # Degenerate: no negatives → AUC undefined, we return 0.5 by convention.
        # This is intentional — a gate with only positives (or only negatives)
        # is under-specified and should not overclaim.
        self.assertEqual(auc([0.9, 0.8, 0.7], [1, 1, 1]), 0.5)
        self.assertEqual(auc([0.9, 0.8, 0.7], [0, 0, 0]), 0.5)

    def test_ties_are_averaged(self):
        # Two positives tied with one negative:
        # scores [0.5, 0.5, 0.5], labels [1, 0, 1]
        # AUC = 0.5 (all tied → half-rank)
        self.assertAlmostEqual(auc([0.5, 0.5, 0.5], [1, 0, 1]), 0.5, places=4)

    def test_empty_or_unary_returns_half(self):
        # Guard against degenerate inputs
        self.assertEqual(auc([], []), 0.5)
        self.assertEqual(auc([0.5], [1]), 0.5)  # no negatives
        self.assertEqual(auc([0.5], [0]), 0.5)  # no positives

    def test_known_small_case(self):
        # From standard textbook: 3 pos above 2 neg → AUC = 1.0 exactly
        # (Manna-Kendall rank-average formula).
        self.assertAlmostEqual(auc([0.9, 0.8, 0.7, 0.4, 0.3], [1, 1, 1, 0, 0]), 1.0, places=6)


class TestPearson(unittest.TestCase):
    """Pearson correlation — used by the rejection rule."""

    def test_perfect_positive(self):
        self.assertAlmostEqual(pearson([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]), 1.0, places=6)

    def test_perfect_negative(self):
        self.assertAlmostEqual(pearson([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]), -1.0, places=6)

    def test_zero_variance_returns_zero(self):
        # Zero variance in one arm → correlation undefined; we return 0.0
        self.assertEqual(pearson([1, 1, 1, 1], [1, 2, 3, 4]), 0.0)


class TestIndependentRecompute(unittest.TestCase):
    """The gate recomputes from raw samples, ignoring any summary field."""

    def test_reads_held_out_only(self):
        results = {
            "samples": [
                {"id": 0, "split": "train", "score": 0.99, "label": 0},   # ignore
                {"id": 1, "split": "train", "score": 0.99, "label": 0},   # ignore
                {"id": 2, "split": "held_out", "score": 0.8, "label": 1},
                {"id": 3, "split": "held_out", "score": 0.2, "label": 0},
            ]
        }
        ev = independent_recompute(_demo_protocol(), results)
        self.assertEqual(ev["n_held_out"], 2)
        self.assertEqual(ev["n_positive"], 1)
        self.assertEqual(ev["source"], "recomputed_from_raw_samples")

    def test_summary_field_is_ignored(self):
        # Analyst tries to smuggle in a good-looking AUC summary — gate ignores it.
        results = {
            "samples": [
                {"id": 0, "split": "held_out", "score": 0.3, "label": 1},
                {"id": 1, "split": "held_out", "score": 0.2, "label": 1},
                {"id": 2, "split": "held_out", "score": 0.9, "label": 0},
                {"id": 3, "split": "held_out", "score": 0.8, "label": 0},
            ],
            "summary": {"held_out_auc": 0.99},  # bogus, must be ignored
        }
        ev = independent_recompute(_demo_protocol(), results)
        # Actual AUC: 2 pos at bottom, 2 neg at top → 0.0
        self.assertEqual(ev["held_out_auc"], 0.0)

    def test_falls_back_to_all_samples_when_no_split(self):
        results = {"samples": [
            {"id": 0, "score": 0.9, "label": 1},
            {"id": 1, "score": 0.4, "label": 0},
        ]}
        ev = independent_recompute(_demo_protocol(), results)
        self.assertEqual(ev["n_held_out"], 2)


class TestCheckVerdicts(unittest.TestCase):
    """The four verdict paths — SUCCESS, FAILURE, WEAK, PRE_EXECUTION_REJECTION."""

    def test_success(self):
        protocol = _demo_protocol()
        results = _held_out([
            (0.9, 1), (0.8, 1), (0.7, 1),
            (0.4, 0), (0.3, 0), (0.2, 0),
        ])
        out = check(protocol, results)
        self.assertEqual(out["verdict"], "SUCCESS")
        self.assertGreaterEqual(out["evidence"]["held_out_auc"], 0.7)

    def test_failure_signal_below_threshold(self):
        # All positives below all negatives → AUC 0.0 < 0.7
        protocol = _demo_protocol()
        results = _held_out([
            (0.3, 1), (0.2, 1), (0.1, 1),
            (0.8, 0), (0.7, 0), (0.9, 0),
        ])
        out = check(protocol, results)
        self.assertEqual(out["verdict"], "FAILURE")

    def test_failure_zero_auc_random(self):
        # Perfect inversion: all pos scores at bottom
        protocol = _demo_protocol()
        results = _held_out([
            (0.1, 1), (0.2, 1), (0.3, 1),
            (0.6, 0), (0.7, 0), (0.8, 0),
        ])
        out = check(protocol, results)
        self.assertEqual(out["verdict"], "FAILURE")
        self.assertEqual(out["evidence"]["held_out_auc"], 0.0)

    def test_weak_signal_present_but_underpowered(self):
        # High AUC but only 2 positives when min_positive=3
        protocol = _demo_protocol()
        results = _held_out([
            (0.9, 1), (0.85, 1),
            (0.4, 0), (0.3, 0), (0.2, 0), (0.1, 0),
        ])
        out = check(protocol, results)
        self.assertEqual(out["verdict"], "WEAK")
        self.assertEqual(out["evidence"]["n_positive"], 2)

    def test_pre_execution_rejection_takes_priority(self):
        # Even with strong signal, a recorded rejection overrides.
        protocol = _demo_protocol()
        results = _held_out([
            (0.9, 1), (0.8, 1), (0.7, 1),
            (0.4, 0), (0.3, 0), (0.2, 0),
        ])
        results["rejection"] = {
            "protocol_id": "DEMO-1",
            "decision": "REFUSE",
            "reason": "proposed substitute metric analytically redundant",
            "coupling": 0.902,
            "threshold": 0.5,
        }
        out = check(protocol, results)
        self.assertEqual(out["verdict"], "PRE_EXECUTION_REJECTION")
        # Evidence is the rejection record itself, not AUC
        self.assertEqual(out["evidence"]["decision"], "REFUSE")
        self.assertAlmostEqual(out["evidence"]["coupling"], 0.902, places=3)

    def test_failure_exit_code_only_on_true_failure(self):
        # WEAK and PRE_EXECUTION_REJECTION do NOT exit non-zero.
        # (The CLI checks this; here we just verify verdicts are distinguishable.)
        protocol = _demo_protocol()

        weak = check(protocol, _held_out([
            (0.9, 1), (0.85, 1), (0.4, 0), (0.3, 0), (0.2, 0), (0.1, 0),
        ]))
        failure = check(protocol, _held_out([
            (0.1, 1), (0.2, 1), (0.3, 1), (0.6, 0), (0.7, 0), (0.8, 0),
        ]))
        self.assertNotEqual(weak["verdict"], failure["verdict"])


class TestEdgeCases(unittest.TestCase):
    """Degenerate inputs must not crash the gate."""

    def test_empty_samples_does_not_crash(self):
        out = check(_demo_protocol(), {"samples": []})
        self.assertIn(out["verdict"], {"FAILURE", "WEAK", "SUCCESS"})

    def test_all_same_score_is_random(self):
        results = _held_out([(0.5, 1), (0.5, 1), (0.5, 0), (0.5, 0)])
        out = check(_demo_protocol(), results)
        # Ties everywhere → AUC = 0.5, below 0.7 threshold → FAILURE
        self.assertEqual(out["verdict"], "FAILURE")


if __name__ == "__main__":
    unittest.main()
