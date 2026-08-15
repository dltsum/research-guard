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

    def test_router_selects_only_two_or_three_roles(self):
        plan = plan_paper_audit(self.root, "Please audit this completed manuscript.")
        self.assertIn(len(plan["selected_roles"]), (2, 3))
        self.assertEqual(len(plan["selected_roles"]), len(set(plan["selected_roles"])))

    def test_formula_request_mandates_lean_role(self):
        plan = plan_paper_audit(self.root, "Help derive and verify the theorem and equations.")
        self.assertIn("formal_math_lean", plan["selected_roles"])
        self.assertTrue(plan["requirements"]["lean_required"])

    def test_experiment_request_mandates_integrity_role(self):
        plan = plan_paper_audit(self.root, "Audit the code, experiments, metrics and results.")
        self.assertIn("code_experiment_integrity", plan["selected_roles"])
        self.assertTrue(plan["requirements"]["experiment_evidence_required"])

    def test_literature_request_mandates_domain_role_and_links(self):
        plan = plan_paper_audit(self.root, "Analyze prior literature and suggest citations.")
        self.assertIn("domain_literature", plan["selected_roles"])
        self.assertTrue(plan["requirements"]["literature_https_links_required"])

    def test_effort_is_hard_capped_at_high(self):
        with self.assertRaises(AuditError):
            plan_paper_audit(self.root, "Audit the paper", effort="xhigh")
        for effort in ("low", "medium", "high"):
            self.assertEqual(plan_paper_audit(self.root, "Audit the paper", effort=effort)["effort"], effort)

    def test_each_selected_role_embeds_numeric_checks(self):
        plan = plan_paper_audit(self.root, "Audit equations, numeric results, and experiments.")
        for role in plan["role_templates"]:
            self.assertTrue(role["numeric_checks"])


if __name__ == "__main__":
    unittest.main()
