from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from paper_audit_core import AuditError, plan_paper_audit  # noqa: E402


class PaperAuditRouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, request_text, *, roles=None, features=None, effort="medium"):
        return plan_paper_audit(
            self.root,
            request_text,
            selected_roles=roles or ["methodology_statistics", "adversarial_logic"],
            audit_features=features or {},
            selected_by="main_agent",
            selection_rationale="The main agent selected the smallest reviewer set that covers this audit request.",
            effort=effort,
        )

    def test_router_selects_only_two_or_three_roles(self):
        plan = self.plan("Please audit this completed manuscript.")
        self.assertIn(len(plan["selected_roles"]), (2, 3))
        self.assertEqual(len(plan["selected_roles"]), len(set(plan["selected_roles"])))

    def test_formula_request_mandates_lean_role(self):
        plan = self.plan(
            "Help derive and verify the theorem and equations.",
            roles=["formal_math_lean", "methodology_statistics"],
            features={"formula": True},
        )
        self.assertIn("formal_math_lean", plan["selected_roles"])
        self.assertTrue(plan["requirements"]["lean_required"])

    def test_experiment_request_mandates_integrity_role(self):
        plan = self.plan(
            "Audit the code, experiments, metrics and results.",
            roles=["code_experiment_integrity", "methodology_statistics"],
            features={"experiment": True},
        )
        self.assertIn("code_experiment_integrity", plan["selected_roles"])
        self.assertTrue(plan["requirements"]["experiment_evidence_required"])

    def test_literature_request_mandates_domain_role_and_links(self):
        plan = self.plan(
            "Analyze prior literature and suggest citations.",
            roles=["domain_literature", "adversarial_logic"],
            features={"literature": True},
        )
        self.assertIn("domain_literature", plan["selected_roles"])
        self.assertTrue(plan["requirements"]["literature_https_links_required"])

    def test_effort_is_hard_capped_at_high(self):
        with self.assertRaises(AuditError):
            plan_paper_audit(self.root, "Audit the paper", effort="xhigh")
        for effort in ("low", "medium", "high"):
            self.assertEqual(self.plan("Audit the paper", effort=effort)["effort"], effort)

    def test_each_selected_role_embeds_numeric_checks(self):
        plan = self.plan(
            "Audit equations, numeric results, and experiments.",
            roles=["formal_math_lean", "methodology_statistics", "code_experiment_integrity"],
            features={"formula": True, "experiment": True, "constructive_numerical": True},
        )
        for role in plan["role_templates"]:
            self.assertTrue(role["numeric_checks"])


if __name__ == "__main__":
    unittest.main()
