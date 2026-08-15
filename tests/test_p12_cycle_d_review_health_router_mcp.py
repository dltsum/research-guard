from __future__ import annotations

import json
import hashlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from intent_router_core import route_prompt  # noqa: E402
from mcp_server import TOOLS  # noqa: E402
from research_guard_core import register_method  # noqa: E402
from research_integrity_core import IntegrityError, monitor_record_health, rank_systematic_review  # noqa: E402
from skillopt_p12 import TRAIN as SKILLOPT_TRAIN, _rounds_pass_gate, _routing_score  # noqa: E402


class P12CycleDReviewHealthRouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        register_method(self.root, {"title": "Review", "problem": "evidence", "mechanism": "human screening"})

    def tearDown(self):
        self.temp.cleanup()

    def test_review_prioritizes_but_never_decides(self):
        records = [
            {"record_id": "i1", "title": "Graph therapy works", "abstract": "random trial", "primary_record_url": "https://doi.org/10.1000/i1", "decision": "include", "selected_by": "user"},
            {"record_id": "e1", "title": "Editorial", "abstract": "opinion only", "primary_record_url": "https://doi.org/10.1000/e1", "decision": "exclude", "selected_by": "user"},
            {"record_id": "u1", "title": "Graph therapy trial", "abstract": "random evaluation", "primary_record_url": "https://doi.org/10.1000/u1"},
        ]
        result = rank_systematic_review(self.root, "review-v1", records)
        self.assertEqual(result["ranking"][0]["record_id"], "u1")
        self.assertNotIn("decision", result["ranking"][0])
        with self.assertRaises(IntegrityError):
            rank_systematic_review(self.root, "review-v2", [{**records[0], "selected_by": "agent"}])
        with self.assertRaisesRegex(IntegrityError, "include and exclude"):
            rank_systematic_review(self.root, "review-v3", [records[0], records[2]])
        with self.assertRaisesRegex(IntegrityError, "title or abstract"):
            rank_systematic_review(self.root, "review-empty", [records[0], records[1], {
                "record_id": "empty", "primary_record_url": "https://doi.org/10.1000/empty",
            }])

    def test_record_health_exposes_links_and_material_updates(self):
        audit_state = self.root / ".research-guard" / "paper-audit-state.json"
        audit_state.write_text('{"status":"PASS","receipt":{"receipt_sha256":"old"}}', encoding="utf-8")
        result = monitor_record_health(self.root, "watch-v1", "10.1000/base", fixture_record={
            "DOI": "10.1000/base", "title": ["Base"],
            "update-to": [{"type": "retraction", "DOI": "10.1000/retract", "source": "publisher"}],
        })
        self.assertEqual(result["status"], "ACTION_REQUIRED")
        self.assertTrue(result["dependent_receipts_invalidated"])
        self.assertEqual(result["current"]["doi_url"], "https://doi.org/10.1000/base")
        self.assertEqual(result["current"]["updates"][0]["primary_record_url"], "https://doi.org/10.1000/retract")
        self.assertIn("scholarly record health changed", audit_state.read_text(encoding="utf-8"))

    def test_nonmaterial_record_change_requires_review(self):
        baseline = monitor_record_health(self.root, "watch-change", "10.1000/base", fixture_record={
            "DOI": "10.1000/base", "title": ["Original title"],
        })
        self.assertEqual(baseline["status"], "PASS")
        changed = monitor_record_health(self.root, "watch-change", "10.1000/base", fixture_record={
            "DOI": "10.1000/base", "title": ["Corrected metadata title"],
        })
        self.assertEqual(changed["status"], "REVIEW_REQUIRED")
        self.assertTrue(changed["dependent_receipts_invalidated"])

    def test_crossref_indexing_timestamp_alone_is_not_scholarly_drift(self):
        first = monitor_record_health(self.root, "watch-index", "10.1000/base", fixture_record={
            "DOI": "10.1000/base", "title": ["Stable title"], "indexed": {"timestamp": 1},
        })
        self.assertEqual(first["status"], "PASS")
        second = monitor_record_health(self.root, "watch-index", "10.1000/base", fixture_record={
            "DOI": "10.1000/base", "title": ["Stable title"], "indexed": {"timestamp": 2},
        })
        self.assertEqual(second["status"], "PASS")
        self.assertFalse(second["changed"])

    def test_router_and_mcp_stay_bounded(self):
        routed = route_prompt("Parse this paper into a claim-evidence graph and audit statistical consistency")
        self.assertEqual(routed["primary_module"], "structured_evidence")
        self.assertIn("research_integrity", routed["selected_modules"])
        self.assertLessEqual(len(routed["selected_modules"]), 3)
        self.assertEqual(len(TOOLS), 15)
        paper = next(item for item in TOOLS if item["name"] == "paper_audit")
        design = next(item for item in TOOLS if item["name"] == "research_design")
        self.assertIn("integrity_action", paper["inputSchema"]["properties"])
        self.assertIn("integrity_action", design["inputSchema"]["properties"])
        self.assertEqual(design["inputSchema"]["properties"]["rounds"]["maximum"], 3)

    def test_skillopt_routing_cases_include_priority_sensitive_mixed_intents(self):
        mixed = [case for case in SKILLOPT_TRAIN if "statistical consistency" in case[0] and "claim-evidence" in case[0]]
        self.assertEqual(len(mixed), 1)
        baseline, baseline_results = _routing_score(mixed, {
            "structured_evidence": 93, "research_integrity": 89,
        })
        inverted, inverted_results = _routing_score(mixed, {
            "structured_evidence": 86, "research_integrity": 98,
        })
        self.assertTrue(baseline_results[0]["passed"])
        self.assertFalse(inverted_results[0]["passed"])
        self.assertGreater(baseline, inverted)

    def test_skillopt_candidate_config_is_hash_bound_and_changes_runtime_routing(self):
        evidence_root = PLUGIN / "evals" / "p12-skillopt"
        evidence_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=evidence_root) as temporary:
            candidate = Path(temporary) / "candidate.json"
            candidate.write_text(json.dumps({
                "routing_priorities": {
                    "structured_evidence": 86,
                    "research_integrity": 98,
                },
                "active_review": {"smoothing": 1.0, "prior_weight": 1.0},
            }), encoding="utf-8")
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            environment = {
                "RESEARCH_GUARD_SKILLOPT_CONFIG": str(candidate),
                "RESEARCH_GUARD_SKILLOPT_CONFIG_SHA256": digest,
            }
            with patch.dict(os.environ, environment, clear=False):
                routed = route_prompt(
                    "Parse this paper into a claim-evidence graph and audit statistical consistency"
                )
            self.assertEqual(routed["primary_module"], "research_integrity")
            with patch.dict(os.environ, {**environment, "RESEARCH_GUARD_SKILLOPT_CONFIG_SHA256": "0" * 64}, clear=False):
                with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                    route_prompt("Parse this PDF into structured sections")

    def test_skillopt_report_accepts_correctly_rejected_regression_clean_round(self):
        passing_case = {"passed": True}
        review_case = {"pair_correct": True}
        accepted = {
            "accepted": True, "candidate_gate_passed": True,
            "regression": {"status": "PASS"},
            "train": [passing_case], "validation": [passing_case],
            "heldout": [passing_case], "review_heldout": [review_case],
        }
        rejected = {
            **accepted,
            "accepted": False,
            "candidate_gate_passed": False,
        }
        self.assertTrue(_rounds_pass_gate([accepted, rejected], 2, 1.1, 1.0))
        self.assertFalse(_rounds_pass_gate([{**rejected, "accepted": True}], 1, 1.0, 1.0))

    def test_structured_extraction_and_plural_retraction_prompts_route(self):
        extraction = route_prompt("Extract this paper with exact page locators")
        self.assertEqual(extraction["primary_module"], "structured_evidence")
        health = route_prompt("Monitor retractions while auditing the manuscript")
        self.assertEqual(health["primary_module"], "research_integrity")
        preregister = route_prompt("Preregister this analysis and freeze the stopping rule")
        self.assertEqual(preregister["primary_module"], "research_integrity")
        mixed = route_prompt("Extract exact paper locators and monitor its DOI for retraction")
        self.assertEqual(mixed["primary_module"], "structured_evidence")

    def test_each_p12_component_compares_three_pinned_upstreams(self):
        registry = json.loads(
            (PLUGIN / "docs" / "provenance" / "P12_COMPONENT_REGISTRY.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(registry["components"]), 8)
        self.assertGreaterEqual(sum(len(item["upstreams"]) for item in registry["components"]), 24)
        required = {"name", "url", "revision", "forks", "license", "architecture", "resource", "decision"}
        for component in registry["components"]:
            self.assertTrue(component["owner"])
            self.assertGreaterEqual(len(component["upstreams"]), 3, component["id"])
            for upstream in component["upstreams"]:
                self.assertTrue(required <= upstream.keys(), (component["id"], upstream.get("name")))
                self.assertRegex(upstream["url"], r"^https://github\.com/[^/]+/[^/]+$")
                self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", upstream["revision"]))
                self.assertIsInstance(upstream["forks"], int)
                self.assertGreaterEqual(upstream["forks"], 0)


if __name__ == "__main__":
    unittest.main()
