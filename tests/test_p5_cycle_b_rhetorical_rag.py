from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

try:
    from language_guard_core import LanguageError, register_rhetorical_card, retrieve_rhetorical_cards
    IMPORT_ERROR = None
except ImportError as exc:
    LanguageError = ValueError
    register_rhetorical_card = retrieve_rhetorical_cards = None
    IMPORT_ERROR = exc


def card(card_id="c1", **overrides):
    value = {
        "card_id": card_id,
        "title": "Evidence-calibrated introduction",
        "source_url": "https://doi.org/10.1000/example",
        "source_locator": "Introduction, paragraph 2",
        "section": "introduction",
        "rhetorical_move": "establish_gap",
        "paragraph_role": "gap",
        "evidence_pattern": "two prior results followed by one bounded gap",
        "reusable_technique": "state the unresolved boundary after concrete evidence",
        "discipline": "machine learning",
        "venue": "conference",
        "evidence_type": "primary_study",
        "transition_relation": "known_to_unknown",
        "verification_excerpt": "Prior systems cover the common case, while the boundary remains unresolved.",
    }
    value.update(overrides)
    return value


class P5CycleBRhetoricalRagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def require_component(self):
        self.assertIsNone(IMPORT_ERROR, f"language component missing: {IMPORT_ERROR}")

    def test_registers_structured_card_with_hash(self):
        self.require_component()
        result = register_rhetorical_card(self.root, card())
        self.assertRegex(result["card_sha256"], r"^[0-9a-f]{64}$")

    def test_rejects_non_https_and_credential_urls(self):
        self.require_component()
        for url in ("http://example.org/paper", "https://user:secret@example.org/paper"):
            with self.subTest(url=url), self.assertRaises(LanguageError):
                register_rhetorical_card(self.root, card(source_url=url))

    def test_rejects_raw_body_fields(self):
        self.require_component()
        for field in ("body", "full_text", "paragraph", "raw_text", "template"):
            with self.subTest(field=field), self.assertRaises(LanguageError):
                register_rhetorical_card(self.root, card(**{field: "copied prose"}))

    def test_rejects_oversized_verification_excerpt(self):
        self.require_component()
        with self.assertRaises(LanguageError):
            register_rhetorical_card(self.root, card(verification_excerpt="x" * 241))

    def test_duplicate_identifier_is_rejected(self):
        self.require_component()
        register_rhetorical_card(self.root, card())
        with self.assertRaises(LanguageError):
            register_rhetorical_card(self.root, card())

    def test_retrieval_is_deterministic_linked_and_non_copying(self):
        self.require_component()
        register_rhetorical_card(self.root, card())
        first = retrieve_rhetorical_cards(self.root, "evidence bounded gap", limit=3)
        second = retrieve_rhetorical_cards(self.root, "evidence bounded gap", limit=3)
        self.assertEqual(first, second)
        self.assertTrue(first["results"][0]["source_url"].startswith("https://"))
        self.assertIn("do not copy", first["usage_boundary"].lower())
        self.assertNotIn("verification_excerpt", first["results"][0])

    def test_retrieval_filters_section_and_role(self):
        self.require_component()
        register_rhetorical_card(self.root, card("intro"))
        register_rhetorical_card(self.root, card(
            "methods", section="methods", paragraph_role="procedure",
            rhetorical_move="describe_procedure", reusable_technique="bind each operation to a parameter",
        ))
        result = retrieve_rhetorical_cards(self.root, "parameter operation", section="methods", paragraph_role="procedure")
        self.assertEqual([item["card_id"] for item in result["results"]], ["methods"])

    def test_retrieval_never_returns_more_than_four(self):
        self.require_component()
        for index in range(6):
            register_rhetorical_card(self.root, card(f"c{index}", title=f"Card {index}"))
        self.assertLessEqual(len(retrieve_rhetorical_cards(self.root, "gap", limit=4)["results"]), 4)
        with self.assertRaises(LanguageError):
            retrieve_rhetorical_cards(self.root, "gap", limit=5)


if __name__ == "__main__":
    unittest.main()
