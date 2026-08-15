from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from language_guard_core import (  # noqa: E402
    LanguageError,
    analyze_language,
    finalize_language_review,
    get_language_status,
    plan_language_review,
    resolve_language_issues,
)


class P6CycleEHeldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_translation_url_sentence_punctuation_is_not_part_of_url(self):
        source = "See https://example.org/data."
        target = "参见 https://example.org/data。"
        plan_language_review(
            self.root, "Translate", task_mode="translation", source_text=source, draft_text=target,
            source_language="English", target_language="Chinese",
        )
        result = analyze_language(self.root, draft_text=target, source_text=source)
        self.assertEqual(result["translation_check"]["status"], "PASS")

    def test_translation_ethics_context_still_creates_user_checklist(self):
        source = "We interviewed 24 participants."
        target = "我们访谈了24名参与者。"
        plan_language_review(
            self.root, "Translate", task_mode="translation", source_text=source, draft_text=target,
            source_language="English", target_language="Chinese",
        )
        result = analyze_language(self.root, draft_text=target, source_text=source)
        self.assertEqual(result["status"], "USER_DECISION_REQUIRED")
        self.assertTrue(any(item["kind"] == "potential_ethics_omission" for item in result["decision_checklist"]))

    def test_http_and_stale_venue_contracts_fail_closed(self):
        base = {
            "venue_name": "ExampleConf", "template_url": "https://example.org/template",
            "verified_at": "2026-08-12", "source_type": "official", "status": "verified",
        }
        with self.assertRaises(LanguageError):
            plan_language_review(
                self.root, "Conference", task_mode="conference_writing", draft_text="Draft",
                venue_contract={**base, "policy_url": "http://example.org/policy"},
            )
        with self.assertRaises(LanguageError):
            plan_language_review(
                self.root, "Conference", task_mode="conference_writing", draft_text="Draft",
                venue_contract={**base, "policy_url": "https://example.org/policy", "verified_at": "2025-01-01"},
            )

    def test_limitation_decision_state_tampering_invalidates_pass(self):
        text = "This study is limited to one hospital."
        plan_language_review(self.root, "Polish", draft_text=text)
        result = analyze_language(self.root, draft_text=text)
        decision_id = result["decision_checklist"][0]["decision_id"]
        resolve_language_issues(self.root, [], decisions=[{
            "decision_id": decision_id, "action": "retain_as_written", "selected_by": "user",
            "rationale": "The user retained the exact external-validity boundary for the final manuscript.",
        }])
        finalize_language_review(self.root)
        path = self.root / ".research-guard" / "language-state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["decisions"][0]["rationale"] = "tampered"
        path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(get_language_status(self.root)["status"], "REVIEW_REQUIRED")

    def test_conference_contract_checks_only_registered_sections(self):
        text = "\\section{Introduction}\n\\section{Methods}\n"
        plan_language_review(
            self.root, "Conference", task_mode="conference_writing", draft_text=text,
            venue_contract={
                "venue_name": "ExampleConf", "policy_url": "https://example.org/policy",
                "template_url": "https://example.org/template", "verified_at": "2026-08-12",
                "source_type": "official", "status": "verified", "required_sections": ["Introduction"],
            },
        )
        result = analyze_language(self.root, draft_text=text)
        self.assertEqual(result["document_check"]["status"], "PASS")
        self.assertNotIn("Conclusion", json.dumps(result["document_check"]))

    def test_blocker_resolution_tampering_invalidates_pass(self):
        text = "It should be noted that the result is bounded."
        plan_language_review(self.root, "Polish", draft_text=text)
        result = analyze_language(self.root, draft_text=text)
        issue_id = next(item["issue_id"] for item in result["findings"] if item["blocking"])
        resolve_language_issues(self.root, [{
            "issue_id": issue_id, "action": "retain_with_justification",
            "rationale": "The user deliberately retains this exact framing as part of the registered argument.",
        }])
        finalize_language_review(self.root)
        path = self.root / ".research-guard" / "language-state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["resolutions"][0]["rationale"] = "tampered"
        path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(get_language_status(self.root)["status"], "REVIEW_REQUIRED")

    def test_pre_finalize_decision_tampering_cannot_be_signed(self):
        text = "This study is limited to one hospital."
        plan_language_review(self.root, "Polish", draft_text=text)
        result = analyze_language(self.root, draft_text=text)
        decision_id = result["decision_checklist"][0]["decision_id"]
        resolve_language_issues(self.root, [], decisions=[{
            "decision_id": decision_id, "action": "retain_as_written", "selected_by": "user",
            "rationale": "The user retained the exact external-validity boundary for the manuscript.",
        }])
        path = self.root / ".research-guard" / "language-state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["decisions"][0]["rationale"] = "tampered"
        path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(LanguageError):
            finalize_language_review(self.root)


if __name__ == "__main__":
    unittest.main()
