"""Unit tests for selfverify.receipt — S2 verification receipt issuer.

Zero-dependency: unittest only, runs via
    python -m unittest discover -s tests

Covers:
  - sha256_file on a known file (matches hashlib reference)
  - env_hash determinism within a process
  - issue_one produces all documented fields
  - missing artifact/script is flagged status=missing rather than crashing
  - raw_sample_sha256 is stable across identical artifacts
  - verify_one catches a tampered raw_sample hash
  - verify_one runs recompute_fn and reports MISMATCH on disagreement
  - verify_many detects a missing artifact on disk
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from selfverify.receipt import (
    sha256_file,
    env_hash,
    issue_one,
    issue_many,
    verify_one,
    verify_many,
)


class TestSha256File(unittest.TestCase):
    def test_matches_hashlib_reference(self):
        d = tempfile.mkdtemp(prefix="receipt_hash_")
        p = Path(d) / "sample.bin"
        p.write_bytes(b"flybrain test payload")
        expected = hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(sha256_file(p), expected)

    def test_changes_when_content_changes(self):
        d = tempfile.mkdtemp(prefix="receipt_hash_")
        p = Path(d) / "sample.bin"
        p.write_bytes(b"aaa")
        h1 = sha256_file(p)
        p.write_bytes(b"bbb")
        h2 = sha256_file(p)
        self.assertNotEqual(h1, h2)


class TestEnvHash(unittest.TestCase):
    def test_is_stable_within_a_process(self):
        # env_hash reads the same runtime facts twice in the same process,
        # so two consecutive calls must return the identical digest.
        h1 = env_hash()
        h2 = env_hash()
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex digest length


class TestIssueOne(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="receipt_root_"))
        self.artifact = self.root / "data" / "sample.json"
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_text(json.dumps({"a": 1}), encoding="utf-8")
        self.script = self.root / "scripts" / "recompute.py"
        self.script.parent.mkdir(parents=True)
        self.script.write_text("print(42)", encoding="utf-8")

    def _spec(self, **overrides):
        base = {
            "claim_id": "C1",
            "statement": "demo statement",
            "protocol_ref": "PR-1.md",
            "expected_verdict": "PASS",
            "artifacts": ["data/sample.json"],
            "scripts": ["scripts/recompute.py"],
            "notes": "test note",
        }
        base.update(overrides)
        return base

    def test_receipt_contains_all_documented_fields(self):
        receipt = issue_one(self._spec(), self.root)
        for field in (
            "schema", "claim_id", "statement", "protocol_ref",
            "expected_verdict", "raw_sample_sha256", "recompute_script_sha256",
            "artifacts", "scripts", "env_hash", "timestamp",
            "issued_by", "notes",
        ):
            self.assertIn(field, receipt, f"missing field: {field}")

    def test_schema_is_vro_receipt_v1(self):
        receipt = issue_one(self._spec(), self.root)
        self.assertEqual(receipt["schema"], "vro_receipt_v1")

    def test_present_artifact_carries_real_hash_and_size(self):
        receipt = issue_one(self._spec(), self.root)
        self.assertEqual(len(receipt["artifacts"]), 1)
        a = receipt["artifacts"][0]
        self.assertEqual(a["path"], "data/sample.json")
        self.assertEqual(a["sha256"], hashlib.sha256(self.artifact.read_bytes()).hexdigest())
        self.assertGreater(a["size"], 0)

    def test_missing_artifact_is_marked_missing(self):
        receipt = issue_one(self._spec(artifacts=["data/nope.json"]), self.root)
        a = receipt["artifacts"][0]
        self.assertIsNone(a["sha256"])
        self.assertEqual(a["status"], "missing")

    def test_missing_script_is_marked_missing(self):
        receipt = issue_one(self._spec(scripts=["scripts/nope.py"]), self.root)
        s = receipt["scripts"][0]
        self.assertIsNone(s["sha256"])
        self.assertEqual(s["status"], "missing")

    def test_raw_sample_sha256_is_stable_for_identical_inputs(self):
        r1 = issue_one(self._spec(), self.root)
        r2 = issue_one(self._spec(), self.root)
        self.assertEqual(r1["raw_sample_sha256"], r2["raw_sample_sha256"])
        self.assertEqual(r1["recompute_script_sha256"], r2["recompute_script_sha256"])

    def test_raw_sample_sha256_changes_when_artifact_changes(self):
        r1 = issue_one(self._spec(), self.root)
        self.artifact.write_text(json.dumps({"a": 2}), encoding="utf-8")
        r2 = issue_one(self._spec(), self.root)
        self.assertNotEqual(r1["raw_sample_sha256"], r2["raw_sample_sha256"])

    def test_missing_artifacts_give_none_raw_hash(self):
        receipt = issue_one(self._spec(artifacts=["missing/x.json"]), self.root)
        self.assertIsNone(receipt["raw_sample_sha256"])


class TestIssueMany(unittest.TestCase):
    def test_writes_one_json_per_claim(self):
        root = Path(tempfile.mkdtemp(prefix="receipt_many_"))
        out = Path(tempfile.mkdtemp(prefix="receipt_many_out_"))
        specs = [
            {"claim_id": "C1", "expected_verdict": "PASS", "artifacts": [], "scripts": []},
            {"claim_id": "C2", "expected_verdict": "FAIL", "artifacts": [], "scripts": []},
        ]
        written = issue_many(specs, root, out)
        self.assertEqual(len(written), 2)
        for p in written:
            self.assertTrue(p.exists())
            self.assertEqual(p.suffix, ".json")


class TestVerifyOne(unittest.TestCase):
    def test_correct_hash_verifies(self):
        receipt = {
            "claim_id": "C1",
            "raw_sample_sha256": hashlib.sha256(b"payload").hexdigest(),
        }
        result = verify_one(receipt, b"payload")
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["checks"]["raw_sample_sha256"], "OK")

    def test_tampered_hash_fails(self):
        receipt = {
            "claim_id": "C1",
            "raw_sample_sha256": hashlib.sha256(b"original").hexdigest(),
        }
        result = verify_one(receipt, b"tampered")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["checks"]["raw_sample_sha256"], "MISMATCH")
        self.assertTrue(result["errors"])

    def test_recompute_fn_match_verifies(self):
        receipt = {
            "claim_id": "C1",
            "expected_verdict": "PASS",
            "recompute_script_sha256": "abc",
        }
        result = verify_one(receipt, b"x", recompute_fn=lambda _r: "PASS")
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["checks"]["recompute_verdict"], "OK")

    def test_recompute_fn_mismatch_fails(self):
        receipt = {
            "claim_id": "C1",
            "expected_verdict": "PASS",
            "recompute_script_sha256": "abc",
        }
        result = verify_one(receipt, b"x", recompute_fn=lambda _r: "FAIL")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["checks"]["recompute_verdict"], "MISMATCH")

    def test_recompute_fn_exception_fails(self):
        receipt = {
            "claim_id": "C1",
            "expected_verdict": "PASS",
            "recompute_script_sha256": "abc",
        }

        def boom(_r):
            raise RuntimeError("kaboom")

        result = verify_one(receipt, b"x", recompute_fn=boom)
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("recompute_fn raised", result["errors"][-1])

    def test_receipt_without_hashes_and_without_fn_stays_verified(self):
        receipt = {"claim_id": "C1"}
        result = verify_one(receipt, b"anything")
        self.assertEqual(result["status"], "VERIFIED")


class TestVerifyMany(unittest.TestCase):
    def test_missing_artifact_is_reported(self):
        root = Path(tempfile.mkdtemp(prefix="verify_many_root_"))
        receipts_dir = Path(tempfile.mkdtemp(prefix="verify_many_dir_"))
        receipt = {
            "claim_id": "C1",
            "artifacts": [{"path": "data/nope.json", "sha256": "deadbeef"}],
            "scripts": [],
        }
        (receipts_dir / "C1.json").write_text(json.dumps(receipt), encoding="utf-8")
        results = verify_many(receipts_dir, root)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "FAILED")
        self.assertFalse(results[0]["checks"]["artifacts_present"])

    def test_present_artifacts_verify(self):
        root = Path(tempfile.mkdtemp(prefix="verify_many_root_"))
        receipts_dir = Path(tempfile.mkdtemp(prefix="verify_many_dir_"))
        # Create the artifact on disk first
        art_path = root / "data" / "sample.json"
        art_path.parent.mkdir(parents=True)
        art_path.write_text("payload", encoding="utf-8")
        receipt = {
            "claim_id": "C1",
            "artifacts": [{"path": "data/sample.json", "sha256": "abc123"}],
            "scripts": [],
        }
        (receipts_dir / "C1.json").write_text(json.dumps(receipt), encoding="utf-8")
        results = verify_many(receipts_dir, root)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "VERIFIED")
        self.assertTrue(results[0]["checks"]["artifacts_present"])

    def test_empty_directory_returns_empty(self):
        receipts_dir = Path(tempfile.mkdtemp(prefix="verify_many_empty_"))
        root = Path(receipts_dir)
        self.assertEqual(verify_many(receipts_dir, root), [])


if __name__ == "__main__":
    unittest.main()
