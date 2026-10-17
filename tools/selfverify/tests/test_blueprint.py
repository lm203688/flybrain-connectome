"""Unit tests for selfverify.blueprint — S1 typed claim graph builder.

Zero-dependency: unittest only, runs via
    python -m unittest discover -s tests

Covers:
  - verification_level mapping across the V0..V5 ladder
  - build() turns a minimal research_claims.json into nodes/edges
  - status normalization via STATUS_MAP (complete → verified, etc.)
  - preregistered protocol block becomes evidence + tests edge
  - pre-execution-rejection protocol is treated as ACCEPT → rejected
  - validate() catches illegal node/edge types and unsupported claims
  - stats counters match the actual node/edge counts
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from selfverify.blueprint import (
    ALLOWED_NODE_TYPES,
    ALLOWED_EDGE_TYPES,
    STATUS_MAP,
    PROTOCOL_VERDICT_MAP,
    verification_level,
    build,
    validate,
)


def _write_tmp_claims(rc: dict) -> str:
    d = tempfile.mkdtemp(prefix="blueprint_test_")
    path = os.path.join(d, "research_claims.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rc, f, ensure_ascii=False)
    return path


class TestVerificationLevel(unittest.TestCase):
    def test_verified_with_evidence_and_repro_is_v3(self):
        self.assertEqual(verification_level("verified", n_evidence=1, has_repro=True), "V3")

    def test_supported_with_evidence_is_v2(self):
        self.assertEqual(verification_level("supported", n_evidence=1, has_repro=False), "V2")

    def test_boundary_is_v1(self):
        self.assertEqual(verification_level("boundary", n_evidence=0, has_repro=False), "V1")

    def test_refuted_is_v1(self):
        self.assertEqual(verification_level("refuted", n_evidence=1, has_repro=True), "V1")

    def test_rejected_is_v1(self):
        self.assertEqual(verification_level("rejected", n_evidence=0, has_repro=False), "V1")

    def test_draft_with_no_evidence_is_v0(self):
        self.assertEqual(verification_level("draft", n_evidence=0, has_repro=False), "V0")

    def test_verified_without_repro_falls_back_to_v0(self):
        # "verified" without has_repro does NOT match any positive ladder rung
        # (V3 requires both, V2 requires status="supported", V1 requires boundary
        # / refuted / rejected). It therefore falls through to the V0 default —
        # which is the honest answer: a claim cannot self-claim V3 without
        # reproduction evidence, and it is not the same as "supported".
        self.assertEqual(verification_level("verified", n_evidence=1, has_repro=False), "V0")

    def test_verified_with_zero_evidence_falls_back_to_v0(self):
        self.assertEqual(verification_level("verified", n_evidence=0, has_repro=True), "V0")


class TestStatusMap(unittest.TestCase):
    def test_complete_maps_to_verified(self):
        self.assertEqual(STATUS_MAP["complete"], "verified")

    def test_boundary_partial_maps_to_boundary(self):
        self.assertEqual(STATUS_MAP["boundary_partial_falsification"], "boundary")

    def test_negative_result_maps_to_refuted(self):
        self.assertEqual(STATUS_MAP["negative_result"], "refuted")

    def test_protocol_verdict_pass_maps_to_verified(self):
        self.assertEqual(PROTOCOL_VERDICT_MAP["PASS"], "verified")

    def test_protocol_verdict_accept_maps_to_rejected(self):
        # ACCEPT on a pre-execution rejection means "we refused to run"
        self.assertEqual(PROTOCOL_VERDICT_MAP["ACCEPT"], "rejected")


class TestBuild(unittest.TestCase):
    def test_minimal_claim_with_evidence_creates_claim_and_evidence_nodes(self):
        rc = {
            "claims": [{
                "id": "C1",
                "title": "demo claim",
                "statement": "some statement",
                "status": "complete",
                "supporting_evidence": [{"artifact": "a1.json", "claim": "text"}],
                "reproduction_command": "python x.py",
            }]
        }
        graph = build(_write_tmp_claims(rc))
        ids = {n["id"] for n in graph["nodes"]}
        self.assertIn("claim:C1", ids)
        self.assertIn("evidence:C1:a1.json", ids)
        self.assertEqual(graph["stats"]["n_claims"], 1)
        self.assertEqual(graph["stats"]["n_evidence"], 1)

    def test_preregistered_block_creates_protocol_node_and_tests_edge(self):
        rc = {
            "claims": [{"id": "C1", "title": "t", "status": "stated"}],
            "preregistered": {
                "PR1": {
                    "claim_id": "C1",
                    "protocol_ref": "PR-1.md",
                    "verification": {"verdict": "PASS"},
                }
            },
        }
        graph = build(_write_tmp_claims(rc))
        ids = {n["id"] for n in graph["nodes"]}
        self.assertIn("protocol:PR1", ids)
        tests_edges = [e for e in graph["edges"] if e["type"] == "tests"]
        self.assertTrue(any(e["from"] == "protocol:PR1" and e["to"] == "claim:C1"
                            for e in tests_edges))

    def test_pre_execution_rejection_uses_accept_verdict(self):
        rc = {
            "claims": [{"id": "C1", "title": "t", "status": "stated"}],
            "preregistered": {
                "PR2b": {
                    "claim_id": "C1",
                    "kind": "pre_execution_rejection",
                    "decision": "REFUSE",
                }
            },
        }
        graph = build(_write_tmp_claims(rc))
        pnode = next(n for n in graph["nodes"] if n["id"] == "protocol:PR2b")
        self.assertEqual(pnode["verdict"], "ACCEPT")
        self.assertEqual(pnode["status"], "rejected")

    def test_unknown_preregistered_key_for_absent_claim_is_ignored(self):
        # If a preregistered block references a claim_id that is not in claims[],
        # the protocol node must NOT be created (R-0.2 integrity).
        rc = {
            "claims": [{"id": "C1", "title": "t", "status": "stated"}],
            "preregistered": {
                "PRX": {
                    "claim_id": "C999",  # does not exist
                    "verification": {"verdict": "PASS"},
                }
            },
        }
        graph = build(_write_tmp_claims(rc))
        ids = {n["id"] for n in graph["nodes"]}
        self.assertNotIn("protocol:PRX", ids)

    def test_preregistered_metadata_keys_are_skipped(self):
        # The top-level "protocol" / "frozen_at" / "freeze_rules" keys are
        # metadata, not per-study blocks. They must not spawn nodes.
        rc = {
            "claims": [{"id": "C1", "title": "t", "status": "stated"}],
            "preregistered": {
                "protocol": "PR-v1",
                "frozen_at": "2026-10-01T00:00:00Z",
                "freeze_rules": ["R-0.1"],
                "PR1": {"claim_id": "C1", "verification": {"verdict": "PASS"}},
            },
        }
        graph = build(_write_tmp_claims(rc))
        protocol_nodes = [n for n in graph["nodes"] if n["id"].startswith("protocol:")]
        self.assertEqual(len(protocol_nodes), 1)
        self.assertEqual(protocol_nodes[0]["id"], "protocol:PR1")

    def test_weak_pass_verdict_maps_to_boundary(self):
        rc = {
            "claims": [{"id": "C1", "title": "t", "status": "stated"}],
            "preregistered": {
                "PR1": {"claim_id": "C1", "verification": {"verdict": "WEAK_PASS"}}
            },
        }
        graph = build(_write_tmp_claims(rc))
        pnode = next(n for n in graph["nodes"] if n["id"] == "protocol:PR1")
        self.assertEqual(pnode["status"], "boundary")

    def test_stats_counters_match_node_and_edge_counts(self):
        rc = {
            "claims": [
                {
                    "id": "C1", "title": "t", "status": "complete",
                    "supporting_evidence": [
                        {"artifact": "a1"}, {"artifact": "a2"}, {"artifact": "a3"}
                    ],
                    "reproduction_command": "python x.py",
                    "boundary_statement": "boundary text",
                    "quantitative_prediction": "target=0.7",
                    "falsified_mechanisms": [
                        {"mechanism": "P1", "hypothesis": "h", "verdict": "falsified"}
                    ],
                }
            ]
        }
        graph = build(_write_tmp_claims(rc))
        nodes = graph["nodes"]
        stats = graph["stats"]
        self.assertEqual(stats["n_nodes"], len(nodes))
        self.assertEqual(stats["n_edges"], len(graph["edges"]))
        self.assertEqual(stats["n_claims"], sum(1 for n in nodes if n["type"] == "claim"))
        self.assertEqual(stats["n_evidence"], sum(1 for n in nodes if n["type"] == "evidence"))
        self.assertEqual(stats["n_risks"], sum(1 for n in nodes if n["type"] == "risk"))
        self.assertEqual(stats["n_definitions"], sum(1 for n in nodes if n["type"] == "definition"))
        self.assertEqual(stats["n_assumptions"], sum(1 for n in nodes if n["type"] == "assumption"))


class TestValidate(unittest.TestCase):
    def test_illegal_node_type_is_reported(self):
        graph = {
            "nodes": [{"id": "bad:1", "type": "bogus"}],
            "edges": [],
        }
        errors = validate(graph)
        self.assertTrue(any("类型无效" in e for e in errors))

    def test_illegal_edge_type_is_reported(self):
        graph = {
            "nodes": [{"id": "a", "type": "claim"}, {"id": "b", "type": "evidence"}],
            "edges": [{"from": "a", "to": "b", "type": "nonsense"}],
        }
        errors = validate(graph)
        self.assertTrue(any("类型无效" in e for e in errors))

    def test_claim_without_evidence_and_without_boundary_is_flagged(self):
        graph = {
            "nodes": [{"id": "claim:X", "type": "claim", "status": "stated"}],
            "edges": [],
        }
        errors = validate(graph)
        self.assertTrue(any("无证据且无 boundary 状态" in e for e in errors))

    def test_claim_with_evidence_support_is_clean(self):
        graph = {
            "nodes": [
                {"id": "claim:X", "type": "claim", "status": "supported"},
                {"id": "evidence:E1", "type": "evidence"},
            ],
            "edges": [{"from": "evidence:E1", "to": "claim:X", "type": "supports"}],
        }
        self.assertEqual(validate(graph), [])

    def test_boundary_status_claim_without_evidence_is_clean(self):
        graph = {
            "nodes": [{"id": "claim:X", "type": "claim", "status": "boundary"}],
            "edges": [],
        }
        self.assertEqual(validate(graph), [])

    def test_empty_graph_is_clean(self):
        self.assertEqual(validate({"nodes": [], "edges": []}), [])


class TestAllowedVocabularies(unittest.TestCase):
    def test_node_types_are_the_documented_five(self):
        self.assertEqual(
            ALLOWED_NODE_TYPES,
            {"claim", "evidence", "assumption", "definition", "risk"},
        )

    def test_edge_types_are_the_documented_four(self):
        self.assertEqual(
            ALLOWED_EDGE_TYPES,
            {"supports", "contradicts", "depends_on", "tests"},
        )


if __name__ == "__main__":
    unittest.main()
