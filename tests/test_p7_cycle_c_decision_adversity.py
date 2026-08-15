from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from p7_fixtures import commit, plan_strategy, strategy


class P7CycleCDecisionAdversityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        commit(self.root)
        self.plan = plan_strategy(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def register(self, value: dict):
        from research_design_core import register_strategy

        return register_strategy(self.root, strategy_plan_hash=self.plan["strategy_plan_hash"], strategy=value)

    def test_decision_requires_two_branches(self):
        from research_design_core import DesignError

        value = strategy()
        value["decisions"][0]["branches"] = value["decisions"][0]["branches"][:1]
        with self.assertRaisesRegex(DesignError, "at least two branches"):
            self.register(value)

    def test_dangling_and_cyclic_decision_edges_are_rejected(self):
        from research_design_core import DesignError

        dangling = strategy()
        dangling["decisions"][0]["branches"][0]["next_decision_id"] = "missing"
        with self.assertRaisesRegex(DesignError, "unknown next decision"):
            self.register(dangling)

        cyclic = strategy()
        second = copy.deepcopy(cyclic["decisions"][0])
        second["decision_id"] = "D2"
        second["requires_current_choice"] = False
        for index, branch in enumerate(second["branches"]):
            branch["branch_id"] = f"B2_{index}"
            branch.pop("next_decision_id", None)
        cyclic["decisions"][0]["branches"][0]["next_decision_id"] = "D2"
        second["branches"][0]["next_decision_id"] = "D1"
        cyclic["decisions"].append(second)
        with self.assertRaisesRegex(DesignError, "cycle"):
            self.register(cyclic)

    def test_adversity_and_inversion_references_fail_closed(self):
        from research_design_core import DesignError

        adversity = strategy()
        adversity["adversities"][0]["fallback_branch_id"] = "missing"
        with self.assertRaisesRegex(DesignError, "fallback_branch_id"):
            self.register(adversity)
        inversion = strategy()
        inversion["inversions"][0]["parameter_ids"] = ["missing"]
        with self.assertRaisesRegex(DesignError, "parameter"):
            self.register(inversion)

    def test_no_model_selected_best_path_appears(self):
        result = self.register(strategy())
        text = repr(result).lower()
        self.assertNotIn("recommended_branch", text)
        self.assertNotIn("best_option", text)
        self.assertFalse(result["automatic_selection"])


if __name__ == "__main__":
    unittest.main()
