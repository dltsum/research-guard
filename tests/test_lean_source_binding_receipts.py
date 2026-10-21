"""Regression units, not substitutes for installed native Lean acceptance traces."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import paper_audit_core as audit

VALID = "import Init\nset_option autoImplicit false\n-- FORMULA_ID: COUNT\ntheorem count_zero (count : Nat) : count + 0 = count := by rfl\n"
FORMULAS = {"formulas": [{"id": "COUNT", "source": "Regression mechanism", "parameters": ["count"]}],
            "parameters": [{"name": "count", "purpose": "mechanism episode count", "used_by": ["COUNT"]}]}


class LeanSourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "Checked.lean"
        self.source.write_text(VALID, encoding="utf-8")
        audit.plan_paper_audit(
            self.root, "Regression checks for source binding and compiler output receipts",
            selected_roles=["formal_math_lean", "adversarial_logic"], audit_features={"formula": True},
            selected_by="main_agent", selection_rationale="Test deterministic source binding before old proof evidence is reused.")
        self.path = self.root / ".research-guard/paper-audit-state.json"
        self.saved = {"status": "PASS", "lean_file": "Checked.lean",
                      "lean_sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}
        state = json.loads(self.path.read_text(encoding="utf-8"))
        state["lean_check"] = self.saved
        self.path.write_text(json.dumps(state), encoding="utf-8")
        self.manifest = {"applicability": {
            "lean": {"status": "required"},
            **{name: {"status": "not_applicable", "source": "Source binding regression",
                      "reason": "This isolated regression tests source binding only, not mathematical correctness."}
               for name in audit.VERIFICATION_CHANNELS[1:]}}}

    def tearDown(self):
        self.temporary.cleanup()

    def cross(self):
        # Four-route worker is a real subprocess. N/A routes intentionally test
        # only source-reuse behavior; these units never establish native proof.
        with patch("component_runtime.selected_component_python", return_value=Path(sys.executable)):
            return audit.run_formula_cross_verification(self.root, self.manifest, timeout=30)

    def test_recorded_lean_result_needs_no_source_digest(self):
        state = json.loads(self.path.read_text(encoding="utf-8"))
        state['lean_check'].pop('lean_sha256')
        self.path.write_text(json.dumps(state), encoding='utf-8')
        result = self.cross()
        self.assertEqual(result['status'], 'PASS')
        self.assertIn('Recorded compiler run', result['results']['lean']['execution_scope'])

    def test_source_edit_does_not_destroy_recorded_compilation(self):
        self.source.write_text(VALID + '-- ordinary edit\n', encoding='utf-8')
        result = self.cross()
        self.assertEqual(result['status'], 'PASS')
        self.assertIn('subsequent edits', result['results']['lean']['execution_scope'])

    def test_missing_and_outside_sources_are_still_reported(self):
        self.source.unlink()
        self.assertEqual(audit._current_lean_result(self.root, self.saved)['status'], 'INPUT_REQUIRED')
        for value in ['../Checked.lean', '']:
            self.assertEqual(audit._current_lean_result(self.root, {**self.saved, 'lean_file': value})['status'], 'INPUT_REQUIRED')

    def test_worker_failure_is_reported_without_hash_related_state_rewrites(self):
        from resource_guard import ResourceGuardError
        self.assertEqual(self.cross()['status'], 'PASS')
        self.source.write_text(VALID + '-- revised source\n', encoding='utf-8')
        with patch('component_runtime.selected_component_python', return_value=Path(sys.executable)), \
                patch('resource_guard.run_managed', side_effect=ResourceGuardError('FAULT_INJECTION worker denied')), \
                self.assertRaises(audit.AuditError):
            audit.run_formula_cross_verification(self.root, self.manifest, timeout=30)
        state = json.loads(self.path.read_text('utf-8'))
        self.assertEqual(state['lean_check']['status'], 'PASS')
        self.assertEqual(self.source.read_text('utf-8'), VALID + '-- revised source\n')

    def seed_untracked_legacy_receipt(self, mutation):
        """Real source files plus explicit legacy-state unit fixtures, not proof evidence."""
        self.source.write_text(VALID, encoding="utf-8")
        lean = dict(self.saved)
        if mutation == "missing_file_field":
            lean.pop("lean_file")
        elif mutation == "missing_hash_field":
            lean.pop("lean_sha256")
        state = json.loads(self.path.read_text(encoding="utf-8"))
        state["tracked_files"] = []  # Older receipts need not have tracked Lean.
        state["lean_check"] = lean
        state["verification_results"] = {"lean": lean, **{
            key: {"status": "PASS", "scope": "legacy unit fixture only"}
            for key in audit.VERIFICATION_CHANNELS[1:]}}
        state["verification_receipt"] = {"status": "PASS", "results": state["verification_results"],
                                         "receipt_sha256": "legacy-unit-fixture"}
        receipt = {"scope": "legacy final receipt unit fixture, never scientific evidence"}
        receipt["receipt_sha256"] = hashlib.sha256(json.dumps(
            receipt, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        state["receipt"] = receipt
        state["status"] = "PASS"
        self.path.write_text(json.dumps(state), encoding="utf-8")
        if mutation == "changed":
            self.source.write_text(VALID.replace("count + 0", "count + 1"), encoding="utf-8")
        elif mutation == "deleted":
            self.source.unlink()


    def test_status_reads_legacy_record_without_source_checksum(self):
        self.seed_untracked_legacy_receipt('missing_hash_field')
        self.assertEqual(audit.get_paper_audit_status(self.root)['status'], 'PASS')
        self.source.write_text(VALID + '-- current revision\n', encoding='utf-8')
        self.assertEqual(audit.get_paper_audit_status(self.root)['status'], 'PASS')

    def test_submit_reports_actual_role_errors_without_requiring_digest(self):
        self.seed_untracked_legacy_receipt('missing_hash_field')
        with self.assertRaises(audit.AuditError):
            audit.submit_paper_audit(self.root, role_reports=[], online_checks=[])
        state = json.loads(self.path.read_text('utf-8'))
        self.assertNotIn('lean_sha256', state['lean_check'])
        self.assertEqual(state['lean_check']['status'], 'PASS')

    def compile_fixture(self, returncode, stdout, stderr):
        # Injected compiler return is explicitly a unit fixture. Real Lean
        # success/failure is tested through installed MCP by run_formal.py.
        completed = subprocess.CompletedProcess(["unit-fixture"], returncode, stdout, stderr)
        with patch.object(audit, "_lean_runtime", return_value=self.root), \
                patch('reproduction_helpers.lean_basic_profile', return_value={'lean_executable': str(self.root / 'bin/lean.exe')}), \
                patch("resource_guard.run_managed_lean", return_value=completed):
            return audit.run_lean_formula_audit(self.root, "Checked.lean", FORMULAS,
                                              runtime_root=self.root, lean_profile="lean-basic")

    def test_success_receipt_preserves_command_exit_and_output(self):
        result = self.compile_fixture(0, "unit-fixture stdout\n", "unit-fixture warning\n")
        execution = result["execution"]
        self.assertEqual(execution["returncode"], 0)
        self.assertEqual(execution["stdout"], "unit-fixture stdout\n")
        self.assertEqual(execution["stderr"], "unit-fixture warning\n")
        self.assertEqual(execution["command"], [str(self.root / "bin/lean.exe"), str(self.source)])
        self.assertEqual(json.loads((self.root / result["execution_record"]).read_text(encoding="utf-8")), execution)

    def test_failure_preserves_full_managed_output_and_does_not_return_pass(self):
        output = "compiler-fixture-begin\n" + "x" * 5000 + "\ncompiler-fixture-end"
        with self.assertRaises(audit.AuditError) as caught:
            self.compile_fixture(7, output, "fixture failure")
        records = list((self.root / ".research-guard/lean-executions").glob("*.json"))
        self.assertEqual(len(records), 1)
        execution = json.loads(records[0].read_text(encoding="utf-8"))
        self.assertEqual(execution["returncode"], 7)
        self.assertEqual(execution["stdout"], output)
        self.assertIn("compiler-fixture-begin", str(caught.exception))
        self.assertIn("execution_record=", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
