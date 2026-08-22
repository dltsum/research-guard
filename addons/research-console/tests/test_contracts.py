from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


ADDON = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ADDON))

from research_console.contracts import (  # noqa: E402
    ContractError,
    compose_codex_prompt,
    normalize_chat_request,
    public_focus_options,
)


class ContractTests(unittest.TestCase):
    def test_main_agent_auto_selection_is_default_and_prompt_is_compact(self) -> None:
        plugin_skill = ADDON.parents[1] / "SKILL.md"
        with tempfile.TemporaryDirectory() as temporary:
            request = normalize_chat_request({"message": "Audit this paper."}, Path(temporary))
        self.assertEqual(request.focus, ("auto",))
        prompt = compose_codex_prompt(request, plugin_skill)
        self.assertIn(str(plugin_skill), prompt)
        self.assertNotIn("RESEARCH_GUARD_PLUGIN_ROOT", prompt)
        self.assertIn("User request:\nAudit this paper.", prompt)
        self.assertIn("not keyword classification", prompt)
        self.assertLess(len(prompt), 1000)

    def test_explicit_focus_is_bounded_and_auto_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = normalize_chat_request({
                "message": "Plan the study.",
                "focus": ["study-experiments", "formulas-numbers", "writing-review"],
                "workspace": str(root),
            }, root)
            self.assertEqual(len(request.focus), 3)
            for invalid in (
                ["auto", "writing-review"],
                ["ideas-novelty", "literature-citations", "study-experiments", "writing-review"],
                ["unknown"],
            ):
                with self.subTest(invalid=invalid), self.assertRaises(ContractError):
                    normalize_chat_request({"message": "x", "focus": invalid}, root)

    def test_resume_id_and_workspace_are_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ContractError, "UUID"):
                normalize_chat_request({"message": "continue", "thread_id": "--last"}, root)
            with self.assertRaisesRegex(ContractError, "does not exist"):
                normalize_chat_request({"message": "continue", "workspace": str(root / "missing")}, root)

    def test_unsafe_sandbox_and_unknown_fields_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ContractError, "unsafe bypass"):
                normalize_chat_request({"message": "run", "sandbox": "danger-full-access"}, root)
            with self.assertRaisesRegex(ContractError, "Unknown request fields"):
                normalize_chat_request({"message": "run", "model": "hidden"}, root)

    def test_focus_catalog_is_human_visible_not_a_classifier(self) -> None:
        catalog = public_focus_options()
        self.assertGreaterEqual(len(catalog), 8)
        self.assertEqual(catalog[0]["id"], "auto")
        for item in catalog:
            self.assertTrue(item["label_en"])
            self.assertTrue(item["label_zh"])
            self.assertTrue(item["description_en"])
            self.assertTrue(item["description_zh"])


if __name__ == "__main__":
    unittest.main()
