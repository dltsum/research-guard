"""A selected role's explicit nonapproval must never produce a PASS receipt."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paper_audit_core import AuditError, get_paper_audit_status, plan_paper_audit, submit_paper_audit


class ExplicitRoleOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        plan_paper_audit(
            self.root, "Interface regression, not a scientific paper approval",
            selected_roles=["methodology_statistics", "adversarial_logic"],
            audit_features={}, selected_by="main_agent",
            selection_rationale="Two roles cover explicit outcome and receipt lifecycle regression.",
        )

    def reports(self):
        return [{"role": role, "findings": ["Test-only interface finding"],
                 "numeric_checks": [{"claim": "Test fixture identity 1=1", "status": "verified"}]}
                for role in ["methodology_statistics", "adversarial_logic"]]

    def submit(self, reports):
        return submit_paper_audit(self.root, role_reports=reports, online_checks=[{
            "claim": "Test-only URL validation fixture, no external scholarly claim",
            "url": "https://example.org/test-only", "accessed_at": "2026-10-20T00:00:00Z",
            "source_type": "test fixture", "status": "verified"}])

    def test_negative_pending_unknown_or_malformed_outcomes_are_rejected(self):
        for field, values in {
            "status": ["FAIL", "failed", "CORRECTION_REQUIRED", "PENDING", "UNKNOWN", "", None, True],
            "verdict": ["FAIL", "REJECT", "NOT_RUN", "", None, ["PASS"]],
            "passed": [False, 0, 1, "true", None],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    reports = self.reports()
                    reports[0][field] = value
                    with self.assertRaisesRegex(AuditError, "explicit.*(approval|PASS|true)"):
                        self.submit(reports)
                    self.assertIsNone(get_paper_audit_status(self.root).get("receipt"))

    def test_contradictory_outcome_fields_cannot_override_failure(self):
        reports = self.reports()
        reports[0].update(status="PASS", verdict="FAIL", passed=True)
        with self.assertRaises(AuditError):
            self.submit(reports)

    def test_positive_explicit_and_legacy_reports_remain_supported(self):
        legacy = self.submit(self.reports())
        self.assertEqual(legacy["status"], "PASS")
        reports = self.reports()
        for report in reports:
            report.update(status="PASS", verdict="PASS", passed=True)
        self.assertEqual(self.submit(reports)["status"], "PASS")
        self.assertEqual(get_paper_audit_status(self.root)["status"], "PASS")

    def test_recorded_explicit_failure_cannot_be_reported_as_pass(self):
        self.submit(self.reports())
        state_path = self.root / ".research-guard/paper-audit-state.json"
        state = json.loads(state_path.read_text("utf8"))
        state["receipt"]["role_reports"][0]["status"] = "FAIL"
        state["receipt"].pop("receipt_sha256", None)
        state_path.write_text(json.dumps(state), encoding="utf8")
        current = get_paper_audit_status(self.root)
        self.assertEqual(current["status"], "AUDIT_REQUIRED")
        self.assertIsNone(current["receipt"])
        self.assertIn("role", current["reason"])


if __name__ == "__main__":
    unittest.main()
