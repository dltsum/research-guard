"""Real paper_audit dispatch tests; no mocked figure implementations."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mcp_server
from academic_figure_core import FigureError
import test_reference_figure_contract as fixtures


class MCPReferenceDispatchTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReferenceFigureContractTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        self.bundle = self.fixture.bundle()
        # The fixture constructs materials, but the route under test must create
        # its own state. This is an exact known temporary state file, not cleanup
        # of any user project or recursively computed directory.
        (self.root / ".research-guard/reference-figures/toy.json").unlink()

    def tearDown(self):
        self.fixture.tearDown()

    def dispatch(self, action, **kwargs):
        return mcp_server.dispatch("paper_audit", {
            "action": "status", "project_root": str(self.root),
            "figure_action": action, "figure_id": "toy", **kwargs,
        })

    def rpc(self, action, **kwargs):
        return mcp_server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {
            "name": "paper_audit", "arguments": {"action": "status", "project_root": str(self.root), "figure_action": action, "figure_id": "toy", **kwargs},
        }})["result"]

    def test_all_three_actions_execute_real_lifecycle_through_paper_audit(self):
        self.assertEqual(self.dispatch("reference_status")["status"], "NOT_PLANNED")
        plan = self.dispatch("reference_plan", reference_contract=self.fixture.contract)
        self.assertEqual(plan["plan_sha256"], self.bundle["plan_sha256"])
        self.assertEqual(self.dispatch("reference_status")["status"], "DELIVERABLES_REQUIRED")
        receipt = self.dispatch("reference_audit", reference_bundle=self.bundle)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(self.dispatch("reference_status")["receipt"]["audit_sha256"], receipt["audit_sha256"])
        self.fixture.write("comparison.md", "Changed after dispatch-issued receipt.")
        self.assertEqual(self.dispatch("reference_status")["status"], "AUDIT_REQUIRED")

    def test_invalid_contract_is_rejected_by_plan_route(self):
        with self.assertRaises(FigureError):
            self.dispatch("reference_plan", reference_contract={})
        result = self.rpc("reference_plan", reference_contract={"figure_id": "toy"})
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"], "FigureError")
        self.assertEqual(self.dispatch("reference_status")["status"], "NOT_PLANNED")

    def test_audit_route_rejects_wrong_plan_and_one_reviewer_identity(self):
        self.dispatch("reference_plan", reference_contract=self.fixture.contract)
        wrong = copy.deepcopy(self.bundle)
        wrong["plan_sha256"] = "0" * 64
        result = self.rpc("reference_audit", reference_bundle=wrong)
        self.assertTrue(result["isError"])
        self.assertIn("plan_sha256", result["structuredContent"]["message"])
        same_agent = copy.deepcopy(self.bundle)
        for review in same_agent["outputs"][0]["rounds"][-1]["reviews"]:
            review["agent_id"] = "one-agent"
        with self.assertRaisesRegex(FigureError, "three distinct"):
            self.dispatch("reference_audit", reference_bundle=same_agent)

    def test_status_route_rejects_path_escape_as_mcp_error(self):
        result = self.rpc("reference_status", figure_id="../../escape")
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"], "FigureError")

    def test_actual_tools_call_envelope_carries_successful_reference_actions(self):
        planned = self.rpc("reference_plan", reference_contract=self.fixture.contract)
        self.assertFalse(planned["isError"])
        audited = self.rpc("reference_audit", reference_bundle=self.bundle)
        self.assertFalse(audited["isError"])
        self.assertEqual(audited["structuredContent"]["status"], "PASS")
        status = self.rpc("reference_status")
        self.assertFalse(status["isError"])
        self.assertEqual(status["structuredContent"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
