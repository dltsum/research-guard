from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from p7_fixtures import commit, plan_strategy, strategy


class P7CycleBAssumptionParameterTests(unittest.TestCase):
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

    def test_valid_contract_preserves_provenance_and_parameter_status(self):
        result = self.register(strategy())
        assumption = result["strategy"]["assumptions"][0]
        self.assertEqual(assumption["likelihood"]["selected_by"], "user")
        self.assertTrue(assumption["evidence_items"][0]["url"].startswith("https://"))
        self.assertEqual(result["strategy"]["parameters"][0]["status"], "fixed")
        self.assertNotIn("parameter_count_verdict", result)

    def test_likelihood_cannot_be_attributed_to_model(self):
        from research_design_core import DesignError

        value = strategy()
        value["assumptions"][0]["likelihood"]["selected_by"] = "assistant"
        with self.assertRaisesRegex(DesignError, "likelihood.*selected_by"):
            self.register(value)

    def test_evidence_supported_assumption_requires_https_primary_record(self):
        from research_design_core import DesignError

        value = strategy()
        value["assumptions"][0]["evidence_items"][0]["url"] = "http://example.org/paper"
        with self.assertRaisesRegex(DesignError, "HTTPS"):
            self.register(value)
        value = strategy()
        value["assumptions"][0]["evidence_items"] = []
        with self.assertRaisesRegex(DesignError, "evidence_supported"):
            self.register(value)

    def test_assumption_dependency_cycle_is_rejected(self):
        from research_design_core import DesignError

        value = strategy()
        second = dict(value["assumptions"][0])
        second["assumption_id"] = "A2"
        second["depends_on"] = ["A1"]
        value["assumptions"][0]["depends_on"] = ["A2"]
        value["assumptions"].append(second)
        with self.assertRaisesRegex(DesignError, "cycle"):
            self.register(value)

    def test_all_parameter_statuses_are_accepted_without_count_heuristic(self):
        for status in ("fixed", "floating", "conditional"):
            with self.subTest(status=status):
                value = strategy()
                value["parameters"][0]["status"] = status
                self.assertEqual(self.register(value)["strategy"]["parameters"][0]["status"], status)


if __name__ == "__main__":
    unittest.main()
