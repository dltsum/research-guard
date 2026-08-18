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
from paper_audit_core import AuditError, plan_paper_audit, run_formula_cross_verification  # noqa: E402


def manifest(model_hash: str) -> dict:
    return {
        "applicability": {
            "lean": {"status": "required"},
            "dimensional": {"status": "required"},
            "symbolic": {"status": "required"},
            "constraints": {"status": "required"},
            "numerical_protocol": {"status": "required"},
        },
        "dimensional_checks": [{"id": "D1", "source": "Eq. 1", "lhs_units": "meter / second", "rhs_units": "kilometer / hour"}],
        "symbolic_checks": [{
            "id": "S1", "source": "Eq. 1", "lhs": "(x + 1)^2", "rhs": "x^2 + 2*x + 1",
            "symbols": [{"name": "x", "assumptions": {"real": True}}],
        }],
        "constraint_checks": [{
            "id": "C1", "source": "Protocol p. 3",
            "parameters": [{"name": "x", "type": "real"}],
            "constraints": [
                {"op": ">=", "args": [{"var": "x"}, 0]},
                {"op": "<=", "args": [{"var": "x"}, 1]},
            ],
        }],
        "numerical_protocol": {
            "protocol_id": "paper-protocol-v1", "source": "Methods p. 3", "model_script": "model.py",
            "model_sha256": model_hash, "entrypoint": "evaluate",
            "parameters": {"x": {"type": "number", "minimum": 0, "maximum": 1}},
            "constraints": [{"op": ">=", "args": [{"var": "x"}, 0]}],
            "cases": [
                {"id": "lower", "kind": "boundary", "parameters": {"x": 0}, "expected": {"finite": True, "value": 0, "abs_tolerance": 0}},
                {"id": "limit", "kind": "limit", "sequence": [{"x": 0.9}, {"x": 0.99}, {"x": 1.0}], "expected": {"target": 1, "abs_tolerance": 0}},
                {"id": "overflow", "kind": "overflow", "parameters": {"x": 1}, "expected": {"finite": True, "maximum": 1}},
            ],
        },
    }


class P13CrossVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        # register_core accepts a runtime root containing python.exe on Windows
        # or bin/python on POSIX. sys.prefix is that cross-platform root;
        # sys.executable.parent is only the root on Windows.
        self.runtime = Path(sys.prefix).resolve()
        self.old_home = os.environ.get("RESEARCH_GUARD_HOME")
        os.environ["RESEARCH_GUARD_HOME"] = str(self.home)
        dependency_manager.register_core(self.runtime)
        dependency_manager.decide([], [])
        model = self.root / "model.py"
        model.write_text("def evaluate(parameters):\n    return float(parameters['x'])\n", encoding="utf-8")
        self.model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
        plan_paper_audit(
            self.root, "Verify the theorem, units, algebra, constraints, limits and overflow",
            selected_roles=["formal_math_lean", "adversarial_logic"],
            audit_features={"formula": True}, selected_by="main_agent",
            selection_rationale="The main agent selected formal and adversarial roles for all five formula channels.",
        )
        state_path = self.root / ".research-guard" / "paper-audit-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["lean_check"] = {"status": "PASS", "lean_file": "PaperFormulaAudit.lean", "lean_sha256": "f" * 64}
        state["verification_results"] = {"lean": state["lean_check"]}
        state_path.write_text(json.dumps(state), encoding="utf-8")

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = self.old_home
        self.temp.cleanup()

    def test_five_channels_are_separate_and_pass(self):
        payload = manifest(self.model_hash)
        result = run_formula_cross_verification(self.root, payload, timeout=120)
        self.assertEqual(set(result["results"]), {"lean", "dimensional", "symbolic", "constraints", "numerical_protocol"})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["results"]["constraints"]["checks"][0]["satisfiability"], "SAT")
        self.assertTrue(all(item["status"] == "ADMITTED" for check in result["results"]["numerical_protocol"]["checks"] for item in check["protocol_legality"]))

    def test_out_of_protocol_boundary_is_explicit_failure(self):
        payload = manifest(self.model_hash)
        payload["numerical_protocol"]["cases"][0]["parameters"]["x"] = -1
        result = run_formula_cross_verification(self.root, payload, timeout=120)
        numerical = result["results"]["numerical_protocol"]
        self.assertEqual(numerical["status"], "FAIL")
        self.assertEqual(numerical["checks"][0]["protocol_legality"][0]["status"], "PROTOCOL_VIOLATION")

    def test_declined_lean_runs_four_channels_but_cannot_pass(self):
        state_path = self.root / ".research-guard" / "paper-audit-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["lean_check"] = None
        state["verification_results"] = None
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = run_formula_cross_verification(self.root, manifest(self.model_hash), timeout=120)
        self.assertEqual(result["status"], "DEGRADED")
        self.assertEqual(result["results"]["lean"]["status"], "NOT_RUN_BY_USER")
        self.assertTrue(all(
            result["results"][name]["status"] in {"PASS", "NOT_APPLICABLE"}
            for name in ("dimensional", "symbolic", "constraints", "numerical_protocol")
        ))

    def test_missing_channel_and_lean_na_are_rejected(self):
        payload = manifest(self.model_hash)
        del payload["applicability"]["constraints"]
        with self.assertRaises(AuditError):
            run_formula_cross_verification(self.root, payload)
        payload = manifest(self.model_hash)
        payload["applicability"]["lean"] = {"status": "not_applicable", "reason": "There is no proposition in this section.", "source": "Methods"}
        with self.assertRaises(AuditError):
            run_formula_cross_verification(self.root, payload)


if __name__ == "__main__":
    unittest.main()
