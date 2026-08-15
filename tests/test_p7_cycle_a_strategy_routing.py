from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from p7_fixtures import PLUGIN, commit, plan_strategy, strategy


class P7CycleAStrategyRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        commit(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_router_is_deterministic_bounded_and_high_capped(self):
        first = plan_strategy(self.root)
        second = plan_strategy(self.root)
        self.assertEqual(first["strategy_plan_hash"], second["strategy_plan_hash"])
        self.assertIn(len(first["selected_modules"]), {2, 3})
        self.assertEqual(first["effort_cap"], "high")
        self.assertTrue(first["human_decision_required"])

    def test_objective_and_priorities_are_user_owned(self):
        from research_design_core import DesignError, register_strategy

        plan = plan_strategy(self.root)
        invalid = strategy()
        invalid["defined_by"] = "assistant"
        with self.assertRaisesRegex(DesignError, "defined_by"):
            register_strategy(self.root, strategy_plan_hash=plan["strategy_plan_hash"], strategy=invalid)
        invalid = strategy()
        invalid["objective"]["criteria"][0]["priority_source"] = "model"
        with self.assertRaisesRegex(DesignError, "priority_source"):
            register_strategy(self.root, strategy_plan_hash=plan["strategy_plan_hash"], strategy=invalid)

    def test_hidden_automatic_choice_fields_are_rejected(self):
        from research_design_core import DesignError, register_strategy

        plan = plan_strategy(self.root)
        invalid = strategy()
        invalid["decisions"][0]["recommended_branch"] = "B_continue"
        with self.assertRaisesRegex(DesignError, "automatic-choice"):
            register_strategy(self.root, strategy_plan_hash=plan["strategy_plan_hash"], strategy=invalid)
        invalid = strategy()
        invalid["decisions"][0]["recommendedBranch"] = "B_continue"
        with self.assertRaisesRegex(DesignError, "automatic-choice"):
            register_strategy(self.root, strategy_plan_hash=plan["strategy_plan_hash"], strategy=invalid)

    def test_no_new_tool_and_skill_stays_compact(self):
        import mcp_server

        tools = [item for item in mcp_server.TOOLS if item["name"] == "research_design"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(len(mcp_server.TOOLS), 17)
        actions = set(tools[0]["inputSchema"]["properties"]["action"]["enum"])
        self.assertTrue({"plan_strategy", "register_strategy", "decide_strategy_branch"} <= actions)
        skill = (PLUGIN / "skills" / "research-design-guard" / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(len(skill.split()), 320)
        self.assertIn("strategy", skill.lower())


if __name__ == "__main__":
    unittest.main()
