"""Unit tests for selfverify.prerejection — PR-2b-style coupling rejection.

The rejection rule is the third-class outcome: "we did not run it because
running it would be uninformative." These tests verify:
  1. The coupling rule correctly computes |Pearson| across arms.
  2. The preregistered threshold is honoured.
  3. Unknown arms degrade gracefully (return error, do not crash).
  4. Missing or non-coupling rules are skipped.
"""
from __future__ import annotations

import unittest

from selfverify.protocol import Protocol
from selfverify.prerejection import evaluate_rejection, coupling


def _proto(rules):
    return Protocol(
        id="DEMO-1",
        hypothesis="test",
        metric="held_out_auc",
        success_criteria={},
        reject_rules=rules,
    )


class TestCoupling(unittest.TestCase):
    def test_perfect_coupling_is_one(self):
        self.assertAlmostEqual(coupling([1, 2, 3, 4], [2, 4, 6, 8]), 1.0, places=6)

    def test_perfect_anticoupling_is_one_absolute(self):
        # |Pearson| — sign is discarded, only magnitude matters
        self.assertAlmostEqual(coupling([1, 2, 3, 4], [8, 6, 4, 2]), 1.0, places=6)

    def test_uncoupled_is_zero(self):
        # Truly orthogonal-ish data: mean-0 patterns that don't correlate.
        # [1,-1,1,-1] vs [1,1,-1,-1] → Pearson = 0
        self.assertAlmostEqual(coupling([1, -1, 1, -1], [1, 1, -1, -1]), 0.0, places=6)

    def test_negative_correlation_is_anti_coupling(self):
        # Perfect negative correlation still counts as coupling in magnitude
        self.assertAlmostEqual(coupling([1, 2, 3, 4], [4, 3, 2, 1]), 1.0, places=6)

    def test_demo_protocol_coupling_is_below_threshold(self):
        # The demo protocol has arms that are permutations of the same values —
        # coupling should be low enough to NOT trigger rejection.
        a = [1, 2, 3, 4, 5]
        b = [5, 1, 4, 2, 3]
        c = coupling(a, b)
        self.assertLess(c, 0.5)  # below demo threshold


class TestEvaluateRejection(unittest.TestCase):
    def test_rejects_when_coupling_above_threshold(self):
        proto = _proto([{
            "type": "coupling", "arm_a": "A", "arm_b": "B", "corr_min": 0.5
        }])
        results = {"arms": [
            {"name": "A", "values": [1, 2, 3, 4, 5]},
            {"name": "B", "values": [2, 4, 6, 8, 10]},  # perfectly coupled
        ]}
        out = evaluate_rejection(proto, results)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["rejected"])
        self.assertAlmostEqual(out[0]["corr"], 1.0, places=6)

    def test_accepts_when_coupling_below_threshold(self):
        proto = _proto([{
            "type": "coupling", "arm_a": "A", "arm_b": "B", "corr_min": 0.5
        }])
        results = {"arms": [
            {"name": "A", "values": [1, 2, 3, 4, 5]},
            {"name": "B", "values": [5, 1, 4, 2, 3]},  # demo-style, low coupling
        ]}
        out = evaluate_rejection(proto, results)
        self.assertFalse(out[0]["rejected"])
        self.assertLess(out[0]["corr"], 0.5)

    def test_unknown_arm_returns_error_not_crash(self):
        proto = _proto([{
            "type": "coupling", "arm_a": "A", "arm_b": "MISSING", "corr_min": 0.5
        }])
        results = {"arms": [{"name": "A", "values": [1, 2, 3, 4]}]}
        out = evaluate_rejection(proto, results)
        self.assertFalse(out[0]["rejected"])
        self.assertEqual(out[0]["error"], "arm_not_found")

    def test_non_coupling_rule_is_skipped(self):
        proto = _proto([
            {"type": "threshold", "metric": "auc", "min": 0.7},  # not a coupling rule
            {"type": "coupling", "arm_a": "A", "arm_b": "B", "corr_min": 0.5},
        ])
        results = {"arms": [
            {"name": "A", "values": [1, 2, 3, 4]},
            {"name": "B", "values": [2, 4, 6, 8]},
        ]}
        out = evaluate_rejection(proto, results)
        # Only the coupling rule is evaluated
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["rejected"])

    def test_no_rules_returns_empty(self):
        proto = _proto([])
        out = evaluate_rejection(proto, {"arms": []})
        self.assertEqual(out, [])

    def test_custom_threshold_is_honoured(self):
        proto = _proto([{
            "type": "coupling", "arm_a": "A", "arm_b": "B", "corr_min": 0.9
        }])
        results = {"arms": [
            {"name": "A", "values": [1, 2, 3, 4, 5]},
            {"name": "B", "values": [1, 2, 3, 4, 6]},  # very high but not perfect
        ]}
        out = evaluate_rejection(proto, results)
        # Actual Pearson for [1,2,3,4,5] vs [1,2,3,4,6] ≈ 0.9864
        # Above the 0.9 threshold → rejected
        self.assertGreater(out[0]["corr"], 0.98)
        self.assertLess(out[0]["corr"], 1.0)
        self.assertTrue(out[0]["rejected"])

    def test_strict_threshold_rejects_weak_coupling(self):
        proto = _proto([{
            "type": "coupling", "arm_a": "A", "arm_b": "B", "corr_min": 0.99
        }])
        results = {"arms": [
            {"name": "A", "values": [1, 2, 3, 4, 5]},
            {"name": "B", "values": [5, 1, 4, 2, 3]},
        ]}
        out = evaluate_rejection(proto, results)
        self.assertLess(out[0]["corr"], 0.99)
        self.assertFalse(out[0]["rejected"])


if __name__ == "__main__":
    unittest.main()
