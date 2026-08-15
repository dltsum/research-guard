from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

try:
    from language_guard_core import LanguageError, analyze_language, plan_language_review
    IMPORT_ERROR = None
except ImportError as exc:  # frozen zero-baseline path
    LanguageError = ValueError
    analyze_language = plan_language_review = None
    IMPORT_ERROR = exc


class P5CycleADefensiveLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def require_component(self):
        self.assertIsNone(IMPORT_ERROR, f"language component missing: {IMPORT_ERROR}")

    def analyze(self, text, **kwargs):
        self.require_component()
        plan_language_review(self.root, "Polish this manuscript", draft_text=text, **kwargs)
        return analyze_language(self.root, draft_text=text)

    def test_explicit_epistemic_qualifier_is_protected(self):
        result = self.analyze(
            "The intervention may reduce variance.",
            protected_spans=[{"text": "may", "reason": "The evidence is correlational."}],
        )
        finding = next(item for item in result["findings"] if item["category"] == "protected_epistemic_qualifier")
        self.assertEqual(finding["recommended_action"], "preserve")
        self.assertFalse(finding["blocking"])

    def test_single_unregistered_may_is_not_blanket_deletion(self):
        result = self.analyze("The intervention may reduce variance.")
        self.assertFalse(any(item.get("recommended_action") == "delete" and "may" in item["excerpt"] for item in result["findings"]))

    def test_material_limitation_is_protected(self):
        result = self.analyze("A limitation is that the sample contains only 18 participants.")
        finding = next(item for item in result["findings"] if item["category"] == "material_limitation")
        self.assertEqual(finding["recommended_action"], "preserve")
        self.assertFalse(finding["blocking"])

    def test_required_disclosure_is_protected(self):
        result = self.analyze("The institutional review board approved the study and all participants gave consent.")
        self.assertTrue(any(item["category"] == "required_disclosure" for item in result["findings"]))

    def test_unsupported_hedge_stack_is_blocking_meaning_risk(self):
        result = self.analyze("This result may perhaps possibly indicate a weak association.")
        finding = next(item for item in result["findings"] if item["category"] == "unsupported_hedge_stack")
        self.assertTrue(finding["blocking"])
        self.assertTrue(finding["meaning_risk"])

    def test_imagined_critic_disclaimer_is_detected(self):
        result = self.analyze("To avoid misunderstanding, we do not claim that the method is universally optimal.")
        self.assertTrue(any(item["category"] == "imagined_critic_disclaimer" for item in result["findings"]))

    def test_disclaimer_first_framing_is_detected_in_chinese(self):
        result = self.analyze("需要指出的是，我们的方法在该数据集上有效。")
        self.assertTrue(any(item["category"] == "disclaimer_first_framing" for item in result["findings"]))

    def test_missing_protected_span_fails_explicitly(self):
        self.require_component()
        with self.assertRaises(LanguageError):
            plan_language_review(
                self.root, "Polish", draft_text="Observed effect.",
                protected_spans=[{"text": "may", "reason": "Keep uncertainty."}],
            )


if __name__ == "__main__":
    unittest.main()
