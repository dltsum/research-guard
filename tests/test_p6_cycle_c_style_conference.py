from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from language_guard_core import LanguageError, analyze_language, plan_language_review  # noqa: E402


class P6CycleCStyleConferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def analyze(self, text: str):
        plan_language_review(self.root, "Polish", draft_text=text)
        return analyze_language(self.root, draft_text=text)

    def test_chat_residue_and_knowledge_cutoff_are_high_precision_signals(self):
        result = self.analyze("As of my knowledge cutoff, the benchmark is current. I hope this helps.")
        categories = {item["category"] for item in result["findings"]}
        self.assertIn("assistant_process_residue", categories)

    def test_style_signal_never_claims_ai_authorship(self):
        result = self.analyze("Some researchers say this marks a pivotal moment for the field.")
        finding = next(item for item in result["findings"] if item["category"] == "vague_promotional_attribution")
        self.assertEqual(finding["epistemic_status"], "textual_pattern_only")
        self.assertNotIn("authored by ai", finding["rationale"].lower())

    def test_quoted_meta_example_and_code_fence_are_not_flagged(self):
        text = (
            "The phrase \"It should be noted that\" is a negative example.\n\n"
            "```text\nAs of my knowledge cutoff, I hope this helps.\n```\n"
            "> To avoid misunderstanding, this quotation is retained verbatim."
        )
        result = self.analyze(text)
        blocked = {item["category"] for item in result["findings"] if item["blocking"]}
        self.assertFalse(blocked & {"disclaimer_first_framing", "imagined_critic_disclaimer", "assistant_process_residue"})

    def test_conference_mode_requires_current_official_https_contract(self):
        with self.assertRaises(LanguageError):
            plan_language_review(
                self.root, "Prepare conference paper", task_mode="conference_writing",
                draft_text="Draft", venue_contract={"venue_name": "ExampleConf"},
            )

    def test_registered_structure_and_latex_references_are_checked(self):
        paper = self.root / "paper.tex"
        paper.write_text(
            "\\section{Introduction}\n"
            "See Figure~\\ref{fig:missing}.\n"
            "\\begin{figure}content\\end{figure}\n",
            encoding="utf-8",
        )
        plan_language_review(
            self.root,
            "Prepare conference paper",
            task_mode="conference_writing",
            manuscript_files=["paper.tex"],
            venue_contract={
                "venue_name": "ExampleConf",
                "policy_url": "https://example.org/official/policy",
                "template_url": "https://example.org/official/template",
                "verified_at": "2026-08-12",
                "source_type": "official",
                "status": "verified",
                "required_sections": ["Introduction", "Conclusion"],
            },
        )
        result = analyze_language(self.root)
        self.assertEqual(result["document_check"]["status"], "BLOCKED")
        codes = {item["code"] for item in result["document_check"]["issues"]}
        self.assertIn("missing_required_section", codes)
        self.assertIn("undefined_reference", codes)
        self.assertIn("figure_missing_caption", codes)
        self.assertIn("figure_missing_label", codes)


if __name__ == "__main__":
    unittest.main()
