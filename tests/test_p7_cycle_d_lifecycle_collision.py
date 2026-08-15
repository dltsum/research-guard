from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from p7_fixtures import commit, experiment, hypothesis, plan_strategy, strategy


class P7CycleDLifecycleCollisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        commit(self.root)
        self.plan = plan_strategy(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def register(self):
        from research_design_core import register_strategy

        return register_strategy(self.root, strategy_plan_hash=self.plan["strategy_plan_hash"], strategy=strategy())

    def test_planned_strategy_blocks_readiness_until_registered(self):
        from research_design_core import get_research_design_status

        status = get_research_design_status(self.root)
        self.assertEqual(status["status"], "STRATEGY_REQUIRED")
        self.assertFalse(status["ready"])

    def test_required_branch_choice_is_user_only(self):
        from research_design_core import DesignError, decide_strategy_branch, get_research_design_status

        self.register()
        self.assertEqual(get_research_design_status(self.root)["status"], "STRATEGY_DECISION_REQUIRED")
        with self.assertRaisesRegex(DesignError, "selected_by"):
            decide_strategy_branch(
                self.root, decision_id="D1", branch_id="B_continue",
                selected_by="assistant", rationale="The model prefers continuing because the validation output looks favourable.",
            )

    def test_non_method_branch_preserves_novelty_state(self):
        from research_design_core import decide_strategy_branch
        from research_guard_core import load_state

        self.register()
        before = load_state(self.root)["gate"]
        result = decide_strategy_branch(
            self.root, decision_id="D1", branch_id="B_continue", selected_by="user",
            rationale="The user reviewed the frozen detector evidence and chose the continue branch.",
        )
        after = load_state(self.root)["gate"]
        self.assertFalse(result["changes_method"])
        self.assertEqual(after, before)

    def test_method_changing_branch_invalidates_old_novelty_evidence(self):
        from research_design_core import decide_strategy_branch
        from research_guard_core import load_state, save_state

        self.register()
        state = load_state(self.root)
        state["gate"] = {"status": "PASS", "reason": "fixture", "updated_at": "2026-08-12T00:00:00Z"}
        state["latest_report"] = ".research-guard/reports/old.json"
        state["current_receipt"] = ".research-guard/receipts/old.json"
        save_state(self.root, state)
        result = decide_strategy_branch(
            self.root, decision_id="D1", branch_id="B_change", selected_by="user",
            rationale="The user judged the detector criterion unmet and chose to replace the detector.",
        )
        changed = load_state(self.root)
        self.assertTrue(result["changes_method"])
        self.assertEqual(changed["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        self.assertIsNone(changed["latest_report"])
        self.assertIsNone(changed["current_receipt"])
        self.assertIsNotNone(changed["pending_method_change"])

    def test_failed_method_invalidation_cannot_record_changing_branch(self):
        from research_design_core import decide_strategy_branch, get_research_design_status
        from research_guard_core import GuardError

        self.register()
        with patch("research_design_core.declare_method_change", side_effect=GuardError("invalidation failed")):
            with self.assertRaisesRegex(GuardError, "invalidation failed"):
                decide_strategy_branch(
                    self.root, decision_id="D1", branch_id="B_change", selected_by="user",
                    rationale="The user chose the changing branch after reviewing the frozen evidence.",
                )
        status = get_research_design_status(self.root)
        self.assertEqual(status["status"], "STRATEGY_DECISION_REQUIRED")

    def test_changed_strategy_invalidates_downstream_experiment(self):
        from research_design_core import register_experiment, register_hypothesis, register_strategy

        self.register()
        register_hypothesis(self.root, hypothesis())
        register_experiment(self.root, experiment())
        changed = strategy()
        changed["objective"]["success_definition"] += " The registered resource cap also remains satisfied."
        result = register_strategy(self.root, strategy_plan_hash=self.plan["strategy_plan_hash"], strategy=changed)
        self.assertTrue(result["changed"])
        import json
        state = json.loads((self.root / ".research-guard" / "research-design.json").read_text(encoding="utf-8"))
        self.assertIsNone(state["experiment"])

    def test_mcp_strategy_roundtrip_uses_existing_multiplexer(self):
        import mcp_server

        planned = mcp_server.dispatch("research_design", {
            "action": "plan_strategy", "project_root": str(self.root),
            "request_text": "Audit assumptions, decision branches, adversity, and inversion",
        })
        registered = mcp_server.dispatch("research_design", {
            "action": "register_strategy", "project_root": str(self.root),
            "strategy_plan_hash": planned["strategy_plan_hash"], "strategy": strategy(),
        })
        decided = mcp_server.dispatch("research_design", {
            "action": "decide_strategy_branch", "project_root": str(self.root),
            "decision_id": "D1", "branch_id": "B_continue", "selected_by": "user",
            "rationale": "The user reviewed the registered criterion and selected the continuing branch.",
        })
        self.assertTrue(registered["strategy_hash"])
        self.assertEqual(decided["selected_by"], "user")


if __name__ == "__main__":
    unittest.main()
