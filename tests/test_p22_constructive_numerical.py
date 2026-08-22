from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dependency_manager  # noqa: E402
import mcp_server  # noqa: E402
from constructive_numerical_core import (  # noqa: E402
    ConstructiveNumericalError,
    get_constructive_numerical_audit,
    run_constructive_numerical_audit,
    verify_constructive_numerical_audit,
)
from paper_audit_core import AuditError, plan_paper_audit, submit_paper_audit  # noqa: E402


def feasible_manifest(audit_id: str = "numeric-v1") -> dict:
    return {
        "audit_id": audit_id,
        "protocol_id": "paper-protocol-v1",
        "source": "Methods pp. 3-4",
        "anchor_count": 3,
        "variables": [
            {
                "name": "duration",
                "type": "real",
                "unit": "second",
                "minimum": 0,
                "minimum_inclusive": False,
                "maximum": 10,
                "source": "Methods p. 3",
                "purpose": "duration allocated to one protocol run",
            },
            {
                "name": "batch",
                "type": "integer",
                "unit": "count",
                "minimum": 1,
                "maximum": 8,
                "source": "Methods p. 3",
                "purpose": "number of independent items in one batch",
            },
        ],
        "constraints": [
            {
                "id": "budget",
                "source": "Methods Eq. 2",
                "relation": "<=",
                "terms": [
                    {"variable": "duration", "coefficient": 1},
                    {"variable": "batch", "coefficient": "1/2", "coefficient_unit": "second / count"},
                ],
                "rhs": {"value": 10, "unit": "second"},
            },
            {
                "id": "coupling",
                "source": "Methods Eq. 3",
                "relation": ">=",
                "terms": [
                    {"variable": "duration", "coefficient": 1},
                    {"variable": "batch", "coefficient": "-1/2", "coefficient_unit": "second / count"},
                ],
                "rhs": {"value": 0, "unit": "second"},
            },
        ],
    }


class ConstructiveNumericalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.old_home = os.environ.get("RESEARCH_GUARD_HOME")
        os.environ["RESEARCH_GUARD_HOME"] = str(self.root / "dependency-home")
        dependency_manager.register_core(Path(sys.prefix).resolve())
        dependency_manager.decide([], [])

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = self.old_home
        self.temporary.cleanup()

    def test_round_1_feasible_ranges_and_anchors_are_exact_and_joint(self) -> None:
        result = run_constructive_numerical_audit(self.root, feasible_manifest(), timeout=120)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(set(result["results"]), {"dimensional", "symbolic", "constraints", "numerical_protocol"})
        self.assertEqual(result["results"]["constraints"]["satisfiability"], "SAT")
        self.assertTrue(result["marginal_intervals"])
        self.assertEqual(len(result["joint_anchors"]), 3)
        self.assertTrue(all(anchor["status"] == "PASS" for anchor in result["joint_anchors"]))
        self.assertTrue(all(
            check["status"] == "PASS"
            for anchor in result["joint_anchors"]
            for check in anchor["constraint_checks"]
        ))
        self.assertIn("Cartesian product is not guaranteed feasible", " ".join(result["warnings"]))
        self.assertLessEqual(result["resource_usage"]["peak_owned_bytes"], 512 * 1024 * 1024)

    def test_round_2_dimension_mismatch_and_unsat_fail_without_anchors(self) -> None:
        mismatch = feasible_manifest("dimension-fail")
        mismatch["constraints"][0]["rhs"]["unit"] = "meter"
        dimensional = run_constructive_numerical_audit(self.root, mismatch, timeout=120)
        self.assertEqual(dimensional["status"], "BLOCKED")
        self.assertEqual(dimensional["results"]["dimensional"]["status"], "FAIL")
        self.assertEqual(dimensional["joint_anchors"], [])

        offset = {
            "audit_id": "offset-fail",
            "protocol_id": "temperature-v1",
            "source": "Methods p. 6",
            "anchor_count": 1,
            "variables": [{
                "name": "temperature", "type": "real", "unit": "degree_Celsius",
                "minimum": 0, "maximum": 100, "source": "Methods p. 6",
                "purpose": "registered experimental temperature",
            }],
            "constraints": [{
                "id": "temperature-cap", "source": "Methods Eq. 6", "relation": "<=",
                "terms": [{"variable": "temperature", "coefficient": 1}],
                "rhs": {"value": 37315, "unit": "centikelvin"},
            }],
        }
        offset_result = run_constructive_numerical_audit(self.root, offset, timeout=120)
        self.assertEqual(offset_result["status"], "BLOCKED")
        self.assertIn("offset unit", " ".join(offset_result["results"]["dimensional"]["checks"][0]["issues"]))

        unsat = feasible_manifest("unsat-v1")
        unsat["constraints"].append({
            "id": "impossible",
            "source": "Methods Eq. 4",
            "relation": ">=",
            "terms": [{"variable": "duration", "coefficient": 1}],
            "rhs": {"value": 20, "unit": "second"},
        })
        impossible = run_constructive_numerical_audit(self.root, unsat, timeout=120)
        self.assertEqual(impossible["status"], "BLOCKED")
        self.assertEqual(impossible["results"]["constraints"]["satisfiability"], "UNSAT")
        self.assertTrue(impossible["results"]["constraints"]["unsat_core"])
        self.assertEqual(impossible["joint_anchors"], [])

    def test_round_3_strict_and_integer_bound_semantics_are_preserved(self) -> None:
        result = run_constructive_numerical_audit(self.root, feasible_manifest("bounds-v1"), timeout=120)
        intervals = {item["variable"]: item for item in result["marginal_intervals"]}
        self.assertEqual(intervals["duration"]["lower"]["value"], "1/2")
        self.assertTrue(intervals["duration"]["lower"]["inclusive"])
        self.assertEqual(intervals["batch"]["lower"]["value"], "1")
        self.assertEqual(intervals["batch"]["upper"]["value"], "8")
        self.assertTrue(intervals["batch"]["lower"]["inclusive"])
        self.assertTrue(all(
            value["exact"].lstrip("-").isdigit()
            for anchor in result["joint_anchors"]
            for name, value in anchor["joint_assignment"].items()
            if name == "batch"
        ))
        open_manifest = {
            "audit_id": "open-v1",
            "protocol_id": "open-protocol-v1",
            "source": "Methods p. 5",
            "anchor_count": 1,
            "variables": [{
                "name": "x", "type": "real", "unit": "dimensionless",
                "minimum": 0, "minimum_inclusive": False,
                "maximum": 1, "maximum_inclusive": False,
                "source": "Methods p. 5", "purpose": "strictly interior mixing weight",
            }],
            "constraints": [{
                "id": "positive", "source": "Methods Eq. 5", "relation": ">",
                "terms": [{"variable": "x", "coefficient": 1}],
                "rhs": {"value": 0, "unit": "dimensionless"},
            }],
        }
        opened = run_constructive_numerical_audit(self.root, open_manifest, timeout=120)
        interval = opened["marginal_intervals"][0]
        self.assertEqual(interval["lower"]["value"], "0")
        self.assertFalse(interval["lower"]["inclusive"])
        self.assertEqual(interval["upper"]["value"], "1")
        self.assertFalse(interval["upper"]["inclusive"])

    def test_round_4_id_reuse_and_record_tampering_fail_closed(self) -> None:
        first = run_constructive_numerical_audit(self.root, feasible_manifest("immutable-v1"), timeout=120)
        again = run_constructive_numerical_audit(self.root, feasible_manifest("immutable-v1"), timeout=120)
        self.assertEqual(first["receipt_sha256"], again["receipt_sha256"])
        changed = feasible_manifest("immutable-v1")
        changed["anchor_count"] = 2
        with self.assertRaisesRegex(ConstructiveNumericalError, "different manifest"):
            run_constructive_numerical_audit(self.root, changed, timeout=120)
        path = self.root / ".research-guard" / "constructive-numerical" / "immutable-v1.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["result"]["status"] = "BLOCKED"
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(ConstructiveNumericalError, "INTEGRITY_FAILURE"):
            get_constructive_numerical_audit(self.root, "immutable-v1")

    def test_round_5_paper_audit_route_and_role_gate_are_integrated(self) -> None:
        with self.assertRaisesRegex(AuditError, "methodology_statistics or formal_math_lean"):
            plan_paper_audit(
                self.root,
                "Construct legal parameter intervals and jointly feasible anchors.",
                selected_roles=["adversarial_logic", "interdisciplinary_impact"],
                audit_features={"constructive_numerical": True},
                selected_by="main_agent",
                selection_rationale="The main agent selected two general roles but omitted numerical expertise.",
            )
        plan_paper_audit(
            self.root,
            "Construct legal parameter intervals and jointly feasible anchors.",
            selected_roles=["methodology_statistics", "adversarial_logic"],
            audit_features={"constructive_numerical": True},
            selected_by="main_agent",
            selection_rationale="The main agent selected methodology and adversarial roles for constructive numerical audit.",
        )
        result = mcp_server.dispatch("paper_audit", {
            "action": "status",
            "project_root": str(self.root),
            "numerical_action": "construct",
            "numeric_constraint_manifest": feasible_manifest("paper-numeric-v1"),
            "process_timeout_seconds": 120,
        })
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(verify_constructive_numerical_audit(self.root, "paper-numeric-v1")["verification"], "PASS")
        submitted = submit_paper_audit(
            self.root,
            role_reports=[
                {"role": "methodology_statistics", "findings": ["constraints checked"], "numeric_checks": ["anchors checked"]},
                {"role": "adversarial_logic", "findings": ["marginal/joint distinction checked"], "numeric_checks": ["boundary checked"]},
            ],
            online_checks=[{
                "claim": "The protocol source locator was reviewed against its current official context.",
                "url": "https://example.org/protocol",
                "accessed_at": "2026-08-22T00:00:00+00:00",
                "source_type": "official protocol",
                "status": "verified",
            }],
        )
        self.assertEqual(submitted["status"], "PASS")
        self.assertEqual(submitted["constructive_numerical_audit"]["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(len(mcp_server.TOOLS), 17)


if __name__ == "__main__":
    unittest.main()
