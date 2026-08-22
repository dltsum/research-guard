from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import (  # noqa: E402
    GuardError,
    get_gate_status,
    load_state,
    refresh_domain,
    register_method,
    run_novelty_search,
    verify_receipt,
)


def tracked_method():
    return {
        "title": "Adaptive memory retrieval for agents",
        "problem": "Agents retrieve irrelevant episodic memories",
        "mechanism": "A confidence gate selects graph connected memory",
        "method_files": ["method.md"],
    }


class MethodFileBindingRoundFourTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.method_file = self.root / "method.md"
        self.method_file.write_text("confidence gate", encoding="utf-8")
        self.key = Path(self.temp.name) / "key.bin"
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.key)

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def fixtures(self):
        state = load_state(self.root)
        if not state.get("search_plan"):
            refresh_domain(
                self.root,
                primary_domain="computer_science",
                secondary_domains=[],
                selected_by="main_agent",
                selection_rationale="The main agent selected computer science for this adaptive-memory method.",
            )
            state = load_state(self.root)
        return {source: [] for source in state["search_plan"]["required_sources"]}

    def test_direct_search_after_file_edit_requires_registration(self):
        register_method(self.root, tracked_method())
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.method_file.write_text("causal gate", encoding="utf-8")
        with self.assertRaisesRegex(GuardError, "register the complete adjusted method"):
            run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.assertEqual(load_state(self.root)["gate"]["status"], "NOVELTY_CHECK_REQUIRED")

    def test_prior_status_sync_cannot_bypass_registration_requirement(self):
        register_method(self.root, tracked_method())
        self.method_file.write_text("causal gate", encoding="utf-8")
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        with self.assertRaisesRegex(GuardError, "register the complete adjusted method"):
            run_novelty_search(self.root, fixture_sources=self.fixtures())

    def test_same_structured_payload_with_new_file_content_gets_new_version_and_hash(self):
        first = register_method(self.root, tracked_method())["state"]
        old_hash = first["active_method"]["hash"]
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.method_file.write_text("causal confidence gate", encoding="utf-8")
        second = register_method(self.root, tracked_method())
        self.assertTrue(second["changed"])
        self.assertEqual(second["state"]["active_method"]["version"], 2)
        self.assertNotEqual(second["state"]["active_method"]["hash"], old_hash)
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.assertTrue(verify_receipt(self.root, strict=True)["valid"])


if __name__ == "__main__":
    unittest.main()
