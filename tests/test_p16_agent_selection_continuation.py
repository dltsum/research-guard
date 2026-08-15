from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from discipline_profile_core import analyze_discipline  # noqa: E402
from intent_router_core import route_prompt, select_research_modules  # noqa: E402
from paper_audit_core import AuditError, plan_paper_audit  # noqa: E402
from research_guard_core import (  # noqa: E402
    GuardError,
    refresh_domain,
    register_method,
    run_novelty_search,
)


METHOD = {
    "title": "Historical graph evidence retrieval",
    "problem": "Researchers need traceable evidence for graph retrieval failures",
    "mechanism": "A provenance-bound graph traversal selects evidence records",
    "contributions": "Version-bound traversal and collision auditing",
}


class AgentSelectionContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _select_domain(self) -> dict:
        return refresh_domain(
            self.root,
            primary_domain="computer_science",
            secondary_domains=[],
            selected_by="main_agent",
            selection_rationale="The method implements graph retrieval software and database evidence traversal.",
        )

    def test_history_text_is_not_classified_automatically(self) -> None:
        routed = route_prompt("history")
        self.assertEqual(routed["status"], "MAIN_AGENT_SELECTION_REQUIRED")
        self.assertEqual(routed["selected_modules"], [])
        self.assertIsNone(routed["method_change_overlay"])

    def test_method_requires_explicit_domain_selection(self) -> None:
        registered = register_method(self.root, METHOD)
        self.assertEqual(registered["state"]["gate"]["status"], "DOMAIN_SELECTION_REQUIRED")
        with self.assertRaisesRegex(GuardError, "MAIN_AGENT_SELECTION_REQUIRED"):
            run_novelty_search(self.root, fixture_sources={})
        profile = self._select_domain()
        self.assertEqual(profile["selected_by"], "main_agent")
        self.assertFalse(profile["automatic_classification"])
        self.assertEqual(profile["primary"], "computer_science")

    def test_search_persists_stage_and_resumes_without_research_deadline(self) -> None:
        register_method(self.root, METHOD)
        self._select_domain()
        state = json.loads((self.root / ".research-guard" / "state.json").read_text(encoding="utf-8"))
        plan = state["search_plan"]
        sources = [*plan["required_sources"], *plan["supplemental_sources"]]
        fixture = {
            source: [{
                "title": f"Evidence record from {source}",
                "doi": f"10.9999/{source.replace('_', '-')}",
                "url": f"https://example.org/{source}",
                "abstract": "A provenance graph retrieves traceable evidence records.",
            }]
            for source in sources
        }
        first = run_novelty_search(self.root, fixture_sources=fixture, work_units_per_call=1)
        self.assertEqual(first["status"], "IN_PROGRESS")
        self.assertTrue(first["continue_required"])
        self.assertFalse(first["stop_allowed"])
        self.assertIsNone(first["research_deadline"])
        self.assertFalse(first["transport_timeout_is_stop_condition"])
        checkpoint = self.root / first["checkpoint"]
        self.assertTrue(checkpoint.is_file())
        self.assertTrue(first["stage_results"][0]["results"][0]["url"].startswith("https://"))

        final = run_novelty_search(self.root, fixture_sources=fixture)
        self.assertEqual(final["status"], "COMPLETE")
        self.assertFalse(final["continue_required"])
        self.assertEqual(final["remaining_units"], 0)
        self.assertIsNone(final["report"]["search_protocol"]["research_deadline"])
        self.assertFalse(final["report"]["search_protocol"]["transport_timeout_is_stop_condition"])

    def test_failed_required_units_need_main_agent_retry_or_explicit_blocker(self) -> None:
        register_method(self.root, METHOD)
        self._select_domain()
        state = json.loads((self.root / ".research-guard" / "state.json").read_text(encoding="utf-8"))
        plan = state["search_plan"]
        sources = [*plan["required_sources"], *plan["supplemental_sources"]]
        failed_source = plan["required_sources"][0]
        fixture = {
            source: (
                {"error_type": "TimeoutError", "message": "single transport attempt expired"}
                if source == failed_source else [{
                    "title": f"Evidence record from {source}",
                    "doi": f"10.9998/{source.replace('_', '-')}",
                    "url": f"https://example.org/{source}",
                    "abstract": "A provenance graph retrieves traceable evidence records.",
                }]
            )
            for source in sources
        }
        action = run_novelty_search(self.root, fixture_sources=fixture)
        self.assertEqual(action["status"], "ACTION_REQUIRED")
        self.assertTrue(action["continue_required"])
        self.assertFalse(action["stop_allowed"])
        self.assertIn("retry_unit_ids", action["available_actions"])
        self.assertTrue(action["required_failed_units"])

        blocked = run_novelty_search(self.root, fixture_sources=fixture, blocker_decision={
            "decision": "stop_with_factual_blocker",
            "selected_by": "main_agent",
            "unit_ids": action["required_failed_units"],
            "rationale": "The required endpoint remains unavailable and every failed unit is preserved in the checkpoint.",
            "evidence_urls": ["https://example.org/service-status"],
        })
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertFalse(blocked["continue_required"])
        self.assertTrue(blocked["stop_allowed"])
        self.assertEqual(blocked["factual_blocker"]["selected_by"], "main_agent")

    def test_main_agent_module_selection_invalidates_method(self) -> None:
        register_method(self.root, METHOD)
        self._select_domain()
        selected = select_research_modules(
            self.root,
            request_text="Change the graph traversal scoring rule.",
            selected_modules=["research_strategy", "research_novelty"],
            selection_rationale="The request changes the canonical retrieval mechanism and requires a new collision search.",
            selected_by="main_agent",
            method_change=True,
        )
        self.assertEqual(selected["status"], "SELECTED")
        self.assertTrue(selected["method_change_invalidation"]["changed"])

    def test_paper_roles_are_explicit(self) -> None:
        with self.assertRaisesRegex(AuditError, "selected_by=main_agent"):
            plan_paper_audit(self.root, "Audit this equation")
        planned = plan_paper_audit(
            self.root,
            "Audit this equation",
            selected_roles=["formal_math_lean", "adversarial_logic"],
            audit_features={"formula": True},
            selected_by="main_agent",
            selection_rationale="The manuscript request contains a formal equation and needs adversarial logical review.",
        )
        self.assertEqual(planned["selected_by"], "main_agent")
        self.assertFalse(planned["automatic_role_selection"])

    def test_unregistered_discipline_analysis_does_not_auto_initialize(self) -> None:
        result = analyze_discipline(
            self.root,
            request_text="Explore chronofabric studies",
            discipline="chronofabric studies",
            broad_domain="humanities",
            selected_by="main_agent",
            selection_rationale="The main agent treats this named field as a humanities profile pending live initialization.",
        )
        self.assertEqual(result["status"], "INITIALIZATION_REQUIRED")
        self.assertFalse(result["automatic_initialization"])
        self.assertNotIn("profile", result)

    def test_mcp_contract_has_no_120_second_research_cap(self) -> None:
        from mcp_server import TOOLS

        novelty = next(item for item in TOOLS if item["name"] == "run_novelty_search")
        properties = novelty["inputSchema"]["properties"]
        self.assertNotIn("timeout", properties)
        self.assertEqual(properties["attempt_timeout_seconds"]["maximum"], 900)
        self.assertIn("work_units_per_call", properties)
        self.assertIn("blocker_decision", properties)
        for tool in TOOLS:
            self.assertNotIn("timeout", tool["inputSchema"].get("properties", {}), tool["name"])


if __name__ == "__main__":
    unittest.main()
