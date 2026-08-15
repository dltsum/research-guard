from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

try:
    from language_guard_core import (
        LanguageError, analyze_language, finalize_language_review, get_language_status,
        plan_language_review, resolve_language_issues,
    )
    IMPORT_ERROR = None
except ImportError as exc:
    LanguageError = ValueError
    analyze_language = finalize_language_review = get_language_status = None
    plan_language_review = resolve_language_issues = None
    IMPORT_ERROR = exc


class P5CycleCLanguageLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "paper.md").write_text("It should be noted that the result is bounded.\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def require_component(self):
        self.assertIsNone(IMPORT_ERROR, f"language component missing: {IMPORT_ERROR}")

    def planned(self):
        self.require_component()
        plan = plan_language_review(self.root, "Polish the paper", manuscript_files=["paper.md"])
        analysis = analyze_language(self.root)
        return plan, analysis

    def test_plan_hash_binds_manuscript(self):
        plan, _ = self.planned()
        self.assertEqual(plan["tracked_files"][0]["path"], "paper.md")
        self.assertRegex(plan["tracked_files"][0]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(plan["plan_hash"], r"^[0-9a-f]{64}$")

    def test_unresolved_blocker_cannot_finalize(self):
        _, analysis = self.planned()
        self.assertGreater(analysis["blocking_count"], 0)
        with self.assertRaises(LanguageError):
            finalize_language_review(self.root)

    def test_short_resolution_rationale_is_rejected(self):
        _, analysis = self.planned()
        issue_id = next(item["issue_id"] for item in analysis["findings"] if item["blocking"])
        with self.assertRaises(LanguageError):
            resolve_language_issues(self.root, [{"issue_id": issue_id, "action": "retain_with_justification", "rationale": "fine"}])

    def test_explicit_retention_resolution_can_finalize(self):
        _, analysis = self.planned()
        blockers = [item for item in analysis["findings"] if item["blocking"]]
        resolve_language_issues(self.root, [{
            "issue_id": item["issue_id"], "action": "retain_with_justification",
            "rationale": "The wording marks a deliberate scope boundary required by the argument.",
        } for item in blockers])
        receipt = finalize_language_review(self.root)
        self.assertEqual(receipt["status"], "PASS")
        self.assertRegex(receipt["receipt_sha256"], r"^[0-9a-f]{64}$")

    def test_rewrite_resolution_requires_file_edit_and_replan(self):
        _, analysis = self.planned()
        issue_id = next(item["issue_id"] for item in analysis["findings"] if item["blocking"])
        with self.assertRaises(LanguageError):
            resolve_language_issues(self.root, [{
                "issue_id": issue_id, "action": "rewrite_preserving_meaning",
                "rationale": "Move the claim first while preserving the exact scientific boundary.",
            }])

    def test_file_change_invalidates_pass(self):
        _, analysis = self.planned()
        blockers = [item for item in analysis["findings"] if item["blocking"]]
        resolve_language_issues(self.root, [{
            "issue_id": item["issue_id"], "action": "retain_with_justification",
            "rationale": "This exact limitation is intentionally retained as a necessary boundary.",
        } for item in blockers])
        finalize_language_review(self.root)
        (self.root / "paper.md").write_text("Changed.\n", encoding="utf-8")
        self.assertEqual(get_language_status(self.root)["status"], "REVIEW_REQUIRED")

    def test_receipt_tampering_invalidates_pass(self):
        _, analysis = self.planned()
        blockers = [item for item in analysis["findings"] if item["blocking"]]
        resolve_language_issues(self.root, [{
            "issue_id": item["issue_id"], "action": "retain_with_justification",
            "rationale": "The boundary is scientifically necessary and remains visible to readers.",
        } for item in blockers])
        finalize_language_review(self.root)
        path = self.root / ".research-guard" / "language-state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["receipt"]["resolved_issue_ids"] = []
        path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(get_language_status(self.root)["status"], "REVIEW_REQUIRED")

    def test_unknown_issue_and_duplicate_claim_ids_fail(self):
        self.require_component()
        with self.assertRaises(LanguageError):
            plan_language_review(self.root, "Polish", manuscript_files=["paper.md"], claim_ids=["c1", "c1"])
        self.planned()
        with self.assertRaises(LanguageError):
            resolve_language_issues(self.root, [{
                "issue_id": "unknown", "action": "retain_with_justification",
                "rationale": "This rationale is long enough but the issue identifier is invalid.",
            }])


if __name__ == "__main__":
    unittest.main()
