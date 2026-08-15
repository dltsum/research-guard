from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import dependency_manager  # noqa: E402
from math_verification_worker import run as run_worker  # noqa: E402
from mcp_server import TOOLS  # noqa: E402
from paper_audit_core import AuditError, plan_paper_audit, submit_paper_audit  # noqa: E402


class P13AdversarialContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def applicability(self, required: str) -> dict:
        return {
            channel: ({"status": "required"} if channel == required else {
                "status": "not_applicable", "reason": f"This channel is outside the stated {required} verification target.", "source": "Methods p. 2",
            })
            for channel in ("lean", "dimensional", "symbolic", "constraints", "numerical_protocol")
        }

    def test_sympy_does_not_execute_arbitrary_python(self):
        marker = self.root / "owned.txt"
        manifest = {
            "applicability": self.applicability("symbolic"),
            "symbolic_checks": [{
                "id": "S1", "source": "Eq. 1", "lhs": f"__import__('pathlib').Path('{marker}').write_text('x')",
                "rhs": "x", "symbols": [{"name": "x", "assumptions": {"real": True}}],
            }],
        }
        result = run_worker({"project_root": str(self.root), "manifest": manifest})
        self.assertEqual(result["results"]["symbolic"]["status"], "FAIL")
        self.assertFalse(marker.exists())

    def test_z3_requires_structured_constraints(self):
        manifest = {
            "applicability": self.applicability("constraints"),
            "constraint_checks": [{
                "id": "C1", "source": "Methods", "parameters": [{"name": "x", "type": "real"}],
                "constraints": ["x > 0"],
            }],
        }
        result = run_worker({"project_root": str(self.root), "manifest": manifest})
        self.assertEqual(result["results"]["constraints"]["status"], "FAIL")

    def test_formula_submit_cannot_hide_missing_cross_channels(self):
        plan = plan_paper_audit(
            self.root, "Audit this equation and theorem",
            selected_roles=["formal_math_lean", "adversarial_logic"],
            audit_features={"formula": True}, selected_by="main_agent",
            selection_rationale="The main agent selected formal and adversarial roles for the equation audit.",
        )
        state_path = self.root / ".research-guard" / "paper-audit-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["lean_check"] = {"status": "PASS"}
        state["verification_results"] = {"lean": {"status": "PASS"}}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        reports = [{"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "x", "status": "verified"}]} for role in plan["selected_roles"]]
        online = [{"claim": "current definition", "url": "https://example.org", "accessed_at": "2026-08-14", "source_type": "official", "status": "verified"}]
        with self.assertRaisesRegex(AuditError, "all five"):
            submit_paper_audit(self.root, role_reports=reports, online_checks=online)

    def test_mcp_surface_has_subroutes_and_explicit_selection_tools(self):
        self.assertEqual(len(TOOLS), 17)
        paper = next(item for item in TOOLS if item["name"] == "paper_audit")
        props = paper["inputSchema"]["properties"]
        self.assertEqual(props["verification_action"]["enum"], ["cross_verify"])
        self.assertEqual(props["review_action"]["enum"], ["calibrate", "status"])
        self.assertEqual(props["image_action"]["enum"], ["audit", "review", "status"])
        self.assertIn("verification_manifest", props)


if __name__ == "__main__":
    unittest.main()
