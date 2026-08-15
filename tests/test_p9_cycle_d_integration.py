from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from language_guard_core import LanguageError, plan_language_review  # noqa: E402
from mcp_server import TOOLS, handle  # noqa: E402
from venue_evidence_core import resolve_venue_profile  # noqa: E402
import dependency_manager  # noqa: E402


class P9CycleDIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_dependency_home = os.environ.get("RESEARCH_GUARD_HOME")
        os.environ["RESEARCH_GUARD_HOME"] = str(self.root / "dependency-home")
        dependency_manager.decide([], [])

    def tearDown(self):
        if self.old_dependency_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = self.old_dependency_home
        self.temp.cleanup()

    def test_mcp_surface_reuses_language_multiplexer(self):
        self.assertEqual(len(TOOLS), 15)
        tool = next(item for item in TOOLS if item["name"] == "language_assist")
        props = tool["inputSchema"]["properties"]
        self.assertEqual(
            props["action"]["enum"],
            ["plan", "analyze", "register_card", "retrieve", "resolve", "finalize", "status", "verify"],
        )
        self.assertIn("venue_action", props)
        self.assertIn("venue_year", props)
        self.assertIn("venue_receipt_sha256", props)

    def test_legacy_free_form_contract_cannot_authorize_structure(self):
        with self.assertRaises(LanguageError):
            plan_language_review(
                self.root, "Write a conference outline", task_mode="conference_writing", draft_text="Draft",
                venue_contract={
                    "venue_name": "MadeUpConf", "policy_url": "https://example.org/policy",
                    "template_url": "https://example.org/template", "verified_at": "2026-08-13",
                    "source_type": "official", "status": "verified",
                    "required_sections": ["Invented Mandatory Chapter"],
                },
            )

    def test_resolve_then_plan_binds_exact_profile(self):
        venue = resolve_venue_profile(self.root, "NeurIPS", 2025, "main", "submission")
        planned = plan_language_review(
            self.root, "Write a NeurIPS conference outline", task_mode="conference_writing",
            draft_text="\\section{Introduction}\nDraft",
            venue="NeurIPS", venue_year=2025, venue_track="main", venue_stage="submission",
            venue_receipt_sha256=venue["receipt_sha256"],
        )
        self.assertEqual(planned["status"], "REVIEW_REQUIRED")
        self.assertEqual(planned["reason"], "language analysis has not been completed")
        self.assertEqual(planned["venue_profile"]["year"], 2025)

    def test_mcp_missing_profile_returns_search_instead_of_outline(self):
        response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "language_assist", "arguments": {
                "action": "status", "venue_action": "resolve", "project_root": str(self.root),
                "venue": "UnknownConf", "venue_year": 2026, "venue_track": "main", "venue_stage": "submission",
            },
        }})
        data = response["result"]["structuredContent"]
        self.assertEqual(data["status"], "ONLINE_ACQUISITION_REQUIRED")
        self.assertNotIn("suggested_sections", data)


if __name__ == "__main__":
    unittest.main()
