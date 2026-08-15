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

from intent_router_core import route_prompt, select_research_modules  # noqa: E402
from mcp_server import TOOLS  # noqa: E402
from research_guard_core import register_method  # noqa: E402
from research_integrity_core import IntegrityError, monitor_record_health, rank_systematic_review  # noqa: E402
from skillopt_p12 import _rounds_pass_gate  # noqa: E402


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
        self.assertEqual(routed["status"], "MAIN_AGENT_SELECTION_REQUIRED")
        self.assertEqual(routed["selected_modules"], [])
        with tempfile.TemporaryDirectory() as temporary:
            selected = select_research_modules(
                temporary, request_text="Parse this paper into a claim-evidence graph and audit statistical consistency",
                selected_modules=["structured_evidence", "research_integrity"],
                selection_rationale="The main agent selected structured evidence and integrity as non-overlapping owners.",
                selected_by="main_agent", method_change=False,
            )
        self.assertEqual(len(selected["selection"]["selected_modules"]), 2)
        self.assertEqual(len(TOOLS), 17)
        paper = next(item for item in TOOLS if item["name"] == "paper_audit")
        design = next(item for item in TOOLS if item["name"] == "research_design")
        self.assertIn("integrity_action", paper["inputSchema"]["properties"])
        self.assertIn("integrity_action", design["inputSchema"]["properties"])
        self.assertEqual(design["inputSchema"]["properties"]["rounds"]["maximum"], 3)

    def test_skillopt_does_not_optimize_semantic_routing(self):
        source = (PLUGIN / "scripts" / "skillopt_p12.py").read_text(encoding="utf-8")
        self.assertNotIn("route_prompt", source)
        self.assertIn('"automatic_semantic_routing": False', source)

    def test_skillopt_priority_config_cannot_override_main_agent_selection(self):
        with patch.dict(os.environ, {"RESEARCH_GUARD_SKILLOPT_CONFIG": "invalid"}, clear=False):
            routed = route_prompt("Parse this paper into a claim-evidence graph")
        self.assertEqual(routed["status"], "MAIN_AGENT_SELECTION_REQUIRED")
        self.assertEqual(routed["selected_modules"], [])

    def test_skillopt_report_accepts_correctly_rejected_regression_clean_round(self):
        review_case = {"pair_correct": True}
        accepted = {
            "accepted": True, "candidate_gate_passed": True,
            "regression": {"status": "PASS"},
            "review_heldout": [review_case],
        }
        rejected = {
            **accepted,
            "accepted": False,
            "candidate_gate_passed": False,
        }
        self.assertTrue(_rounds_pass_gate([accepted, rejected], 2, 1.1, 1.0))
        self.assertFalse(_rounds_pass_gate([{**rejected, "accepted": True}], 1, 1.0, 1.0))

    def test_structured_extraction_and_plural_retraction_prompts_route(self):
        for prompt in (
            "Extract this paper with exact page locators",
            "Monitor retractions while auditing the manuscript",
            "Preregister this analysis and freeze the stopping rule",
            "Extract exact paper locators and monitor its DOI for retraction",
        ):
            self.assertEqual(route_prompt(prompt)["status"], "MAIN_AGENT_SELECTION_REQUIRED")

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
