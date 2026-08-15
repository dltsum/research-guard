from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from language_guard_core import LanguageError, analyze_language, finalize_language_review, plan_language_review  # noqa: E402


class P6CycleBTranslationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = (
            "We processed 18 samples (5%) using `model_id` [12]. "
            "See https://example.org/data and Eq. \\ref{eq:loss}."
        )

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, target: str, **kwargs):
        return plan_language_review(
            self.root,
            "Translate faithfully",
            task_mode="translation",
            source_text=self.source,
            draft_text=target,
            source_language="English",
            target_language="Chinese",
            **kwargs,
        )

    def test_translation_requires_source_text(self):
        with self.assertRaises(LanguageError):
            plan_language_review(
                self.root, "Translate", task_mode="translation", draft_text="译文",
                source_language="English", target_language="Chinese",
            )

    def test_exact_invariants_pass(self):
        target = "我们处理了18个样本（5%），使用`model_id` [12]。参见 https://example.org/data 和公式 \\ref{eq:loss}。"
        self.plan(target)
        result = analyze_language(self.root, draft_text=target, source_text=self.source)
        self.assertEqual(result["translation_check"]["status"], "PASS")
        self.assertEqual(result["translation_check"]["missing"], [])
        self.assertEqual(finalize_language_review(self.root)["status"], "PASS")

    def test_changed_number_and_dropped_citation_fail(self):
        target = "我们处理了80个样本（5%），使用`model_id`。参见 https://example.org/data 和公式 \\ref{eq:loss}。"
        self.plan(target)
        result = analyze_language(self.root, draft_text=target, source_text=self.source)
        self.assertEqual(result["translation_check"]["status"], "BLOCKED")
        kinds = {item["kind"] for item in result["translation_check"]["missing"]}
        self.assertIn("number", kinds)
        self.assertIn("citation", kinds)
        with self.assertRaises(LanguageError):
            finalize_language_review(self.root)

    def test_registered_terminology_is_enforced(self):
        target = "我们处理了18个实例（5%），使用`model_id` [12]。参见 https://example.org/data 和公式 \\ref{eq:loss}。"
        self.plan(target, terminology=[{"source_term": "samples", "target_term": "样本"}])
        result = analyze_language(self.root, draft_text=target, source_text=self.source)
        self.assertTrue(any(item["kind"] == "terminology" for item in result["translation_check"]["missing"]))

    def test_translation_source_hash_is_bound(self):
        target = "我们处理了18个样本（5%），使用`model_id` [12]。参见 https://example.org/data 和公式 \\ref{eq:loss}。"
        self.plan(target)
        with self.assertRaises(LanguageError):
            analyze_language(self.root, draft_text=target, source_text=self.source + " changed")

    def test_translation_preserves_negation_causality_and_uncertainty(self):
        source = "The treatment may not improve accuracy because the sample is small."
        target = "由于样本较小，该处理可能不会提高准确率。"
        plan_language_review(
            self.root, "Translate", task_mode="translation", source_text=source, draft_text=target,
            source_language="English", target_language="Chinese",
        )
        result = analyze_language(self.root, draft_text=target, source_text=source)
        self.assertEqual(result["translation_check"]["status"], "PASS")

    def test_translation_dropped_negation_fails(self):
        source = "The treatment may not improve accuracy because the sample is small."
        target = "由于样本较小，该处理可能提高准确率。"
        plan_language_review(
            self.root, "Translate", task_mode="translation", source_text=source, draft_text=target,
            source_language="English", target_language="Chinese",
        )
        result = analyze_language(self.root, draft_text=target, source_text=source)
        self.assertIn(
            {"kind": "semantic_boundary", "value": "negation"},
            result["translation_check"]["missing"],
        )


if __name__ == "__main__":
    unittest.main()
