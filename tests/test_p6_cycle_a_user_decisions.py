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
    plan_language_review,
    resolve_language_issues,
)


class P6CycleAUserDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def analyze(self, text: str):
        plan_language_review(self.root, "Audit the wording", draft_text=text)
        return analyze_language(self.root, draft_text=text)

    def test_limitation_creates_an_advisory_checklist_and_stays_protected(self):
        result = self.analyze("A limitation is that the sample contains only 18 participants.")
        self.assertEqual(result["status"], "USER_DECISION_REQUIRED")
        item = next(item for item in result["decision_checklist"] if item["kind"] == "material_limitation")
        self.assertEqual(item["selected_by"], "user")
        self.assertIn("retain_as_written", [choice["action"] for choice in item["choices"]])
        finding = next(item for item in result["findings"] if item["category"] == "material_limitation")
        self.assertFalse(finding["blocking"])
        self.assertEqual(finding["recommended_action"], "preserve")
        receipt = finalize_language_review(self.root)
        self.assertEqual(receipt["status"], "PASS")

    def test_human_study_without_disclosure_creates_candidate_not_accusation(self):
        result = self.analyze("We interviewed 24 participants about their medical records.")
        ethics = [item for item in result["decision_checklist"] if item["kind"] == "potential_ethics_omission"]
        self.assertTrue(ethics)
        self.assertTrue(all(item["epistemic_status"] == "candidate_for_user_review" for item in ethics))
        self.assertTrue(all("omission is proven" not in item["rationale"].lower() for item in ethics))

    def test_existing_disclosure_avoids_ethics_omission_candidate(self):
        result = self.analyze(
            "The institutional review board approved the interview study, and all 24 participants gave informed consent."
        )
        self.assertFalse(any(item["kind"] == "potential_ethics_omission" for item in result["decision_checklist"]))
        self.assertTrue(any(item["category"] == "required_disclosure" for item in result["findings"]))

    def test_reviewer_can_record_retention_without_impersonating_the_user(self):
        result = self.analyze("This study is limited to one hospital.")
        decision_id = result["decision_checklist"][0]["decision_id"]
        resolved = resolve_language_issues(self.root, [], decisions=[{
            "decision_id": decision_id,
            "action": "retain_as_written",
            "selected_by": "assistant",
            "rationale": "The scope boundary is materially necessary and should stay visible.",
        }])
        self.assertEqual(resolved["status"], "READY_TO_FINALIZE")
        state = json.loads((self.root / ".research-guard/language-state.json").read_text("utf-8"))
        self.assertEqual(state["decisions"][0]["selected_by"], "assistant")

    def test_retention_choice_records_current_actor_without_signature_gate(self):
        result = self.analyze("This study is limited to one hospital.")
        decision_id = result["decision_checklist"][0]["decision_id"]
        resolved = resolve_language_issues(self.root, [], decisions=[{
            "decision_id": decision_id,
            "action": "retain_as_written",
            "selected_by": "user",
            "rationale": "The user chose to retain this real external-validity boundary unchanged.",
        }])
        self.assertEqual(resolved["status"], "READY_TO_FINALIZE")
        receipt = finalize_language_review(self.root)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["decided_item_ids"], [decision_id])

        path = self.root / ".research-guard" / "language-state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["decisions"][0]["selected_by"] = "assistant"
        path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(finalize_language_review(self.root)["status"], "PASS")
        updated = json.loads(path.read_text("utf-8"))
        self.assertEqual(updated["decisions"][0]["selected_by"], "assistant")

    def test_requested_edit_can_be_analyzed_with_the_same_plan(self):
        result = self.analyze("This study is limited to one hospital.")
        decision_id = result["decision_checklist"][0]["decision_id"]
        resolved = resolve_language_issues(self.root, [], decisions=[{
            "decision_id": decision_id,
            "action": "revise_preserving_substance",
            "selected_by": "user",
            "rationale": "The user requested a clearer boundary while preserving its full scientific substance.",
        }])
        self.assertEqual(resolved["status"], "EDIT_REQUIRED")
        updated_text = "The study covers one hospital; this limitation constrains external validity."
        analyzed = analyze_language(self.root, draft_text=updated_text)
        self.assertTrue(any(item["category"] == "material_limitation" for item in analyzed["findings"]))
        self.assertEqual(finalize_language_review(self.root)["status"], "PASS")
        stored = json.loads((self.root / ".research-guard/language-state.json").read_text("utf-8"))
        self.assertEqual(stored["inline_text"], updated_text)

    def test_existing_disclosure_locator_choice_requires_locator(self):
        result = self.analyze("We interviewed 24 participants about their medical records.")
        decision_id = result["decision_checklist"][0]["decision_id"]
        with self.assertRaises(LanguageError):
            resolve_language_issues(self.root, [], decisions=[{
                "decision_id": decision_id,
                "action": "already_disclosed_at_locator",
                "selected_by": "user",
                "rationale": "The user states that the disclosure exists elsewhere in the complete manuscript.",
            }])

    def test_disclosure_in_another_file_avoids_false_omission(self):
        (self.root / "methods.md").write_text("We interviewed 24 participants about their medical records.\n", encoding="utf-8")
        (self.root / "ethics.md").write_text("The institutional review board approved the study; all participants gave informed consent.\n", encoding="utf-8")
        plan_language_review(self.root, "Audit", manuscript_files=["methods.md", "ethics.md"])
        result = analyze_language(self.root)
        self.assertFalse(any(item["kind"] == "potential_ethics_omission" for item in result["decision_checklist"]))


if __name__ == "__main__":
    unittest.main()
