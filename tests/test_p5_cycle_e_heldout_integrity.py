from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

try:
    from language_guard_core import (
        LanguageError, analyze_language, finalize_language_review, get_language_status,
        plan_language_review, register_rhetorical_card, resolve_language_issues, retrieve_rhetorical_cards,
    )
    IMPORT_ERROR = None
except ImportError as exc:
    LanguageError = ValueError
    analyze_language = finalize_language_review = get_language_status = None
    plan_language_review = register_rhetorical_card = resolve_language_issues = retrieve_rhetorical_cards = None
    IMPORT_ERROR = exc

from mcp_server import TOOLS
from paper_audit_core import get_paper_audit_status, plan_paper_audit, submit_paper_audit


class P5CycleEHeldoutIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def require_component(self):
        self.assertIsNone(IMPORT_ERROR, f"language component missing: {IMPORT_ERROR}")

    def test_bilingual_case_preserves_uncertainty_and_flags_framing(self):
        self.require_component()
        text = "为避免误解，需要指出的是，该关联可能不适用于样本外人群。"
        plan_language_review(
            self.root, "润色论述", draft_text=text,
            protected_spans=[{"text": "可能", "reason": "外部有效性尚未建立。"}],
        )
        result = analyze_language(self.root, draft_text=text)
        categories = {item["category"] for item in result["findings"]}
        self.assertIn("protected_epistemic_qualifier", categories)
        self.assertTrue({"imagined_critic_disclaimer", "disclaimer_first_framing"} & categories)
        self.assertIn("material_limitation", categories)

    def test_generic_throat_clearing_is_detected(self):
        self.require_component()
        text = "It is well known that artificial intelligence has attracted extensive attention."
        plan_language_review(self.root, "Polish", draft_text=text)
        result = analyze_language(self.root, draft_text=text)
        self.assertTrue(any(item["category"] == "generic_throat_clearing" for item in result["findings"]))

    def test_path_escape_is_rejected(self):
        self.require_component()
        outside = self.root.parent / "outside.md"
        outside.write_text("text", encoding="utf-8")
        try:
            with self.assertRaises(LanguageError):
                plan_language_review(self.root, "Polish", manuscript_files=[str(outside)])
        finally:
            outside.unlink(missing_ok=True)

    def test_card_store_tampering_fails_closed(self):
        self.require_component()
        register_rhetorical_card(self.root, {
            "card_id": "c1", "title": "Card", "source_url": "https://example.org/paper",
            "source_locator": "p. 1", "section": "discussion", "rhetorical_move": "bound_claim",
            "paragraph_role": "boundary", "evidence_pattern": "claim then limitation",
            "reusable_technique": "place the verified boundary next to the claim",
        })
        path = self.root / ".research-guard" / "rhetorical-cards.json"
        store = json.loads(path.read_text(encoding="utf-8"))
        store["cards"][0]["title"] = "tampered"
        path.write_text(json.dumps(store), encoding="utf-8")
        with self.assertRaises(LanguageError):
            retrieve_rhetorical_cards(self.root, "boundary")

    def test_receipt_cannot_be_replayed_in_another_project(self):
        self.require_component()
        text = "Direct claim."
        plan_language_review(self.root, "Polish", draft_text=text)
        analyze_language(self.root, draft_text=text)
        finalize_language_review(self.root)
        other = Path(tempfile.mkdtemp())
        try:
            (other / ".research-guard").mkdir()
            shutil.copy2(self.root / ".research-guard" / "language-state.json", other / ".research-guard" / "language-state.json")
            self.assertEqual(get_language_status(other)["status"], "REVIEW_REQUIRED")
        finally:
            shutil.rmtree(other)

    def test_protected_finding_cannot_be_resolved_as_deletion(self):
        self.require_component()
        text = "The effect may be conditional."
        plan_language_review(self.root, "Polish", draft_text=text, protected_spans=[{"text": "may", "reason": "Uncertainty is required."}])
        result = analyze_language(self.root, draft_text=text)
        issue_id = next(item["issue_id"] for item in result["findings"] if item["category"] == "protected_epistemic_qualifier")
        with self.assertRaises(LanguageError):
            resolve_language_issues(self.root, [{
                "issue_id": issue_id, "action": "delete",
                "rationale": "This text is intentionally long enough to exercise the deletion safeguard.",
            }])

    def test_language_tool_schema_is_closed(self):
        tool = next(item for item in TOOLS if item["name"] == "language_assist")
        self.assertFalse(tool["inputSchema"].get("additionalProperties", True))

    def test_language_skill_entrypoint_is_compact(self):
        path = PLUGIN / "skills" / "academic-language-guard" / "SKILL.md"
        self.assertTrue(path.is_file())
        self.assertLessEqual(len(path.read_text(encoding="utf-8").splitlines()), 60)

    def test_paper_pass_is_invalidated_when_language_receipt_is_tampered(self):
        self.require_component()
        (self.root / "paper.md").write_text("The bounded result follows from the observed data.\n", encoding="utf-8")
        plan = plan_paper_audit(self.root, "Audit the manuscript", paper_files=["paper.md"])
        reports = [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "none", "status": "verified"}]}
            for role in plan["selected_roles"]
        ]
        submit_paper_audit(
            self.root,
            role_reports=reports,
            online_checks=[{
                "claim": "policy", "url": "https://example.org/policy", "accessed_at": "2026-08-12",
                "source_type": "official", "status": "verified",
            }],
        )
        language_path = self.root / ".research-guard" / "language-state.json"
        language_state = json.loads(language_path.read_text(encoding="utf-8"))
        language_state["receipt"]["finding_ids"] = ["tampered"]
        language_path.write_text(json.dumps(language_state), encoding="utf-8")
        status = get_paper_audit_status(self.root)
        self.assertEqual(status["status"], "AUDIT_REQUIRED")
        self.assertIn("language receipt", status["reason"])


if __name__ == "__main__":
    unittest.main()
