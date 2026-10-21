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

    def test_direct_search_after_file_edit_allows_direct_rerun(self):
        register_method(self.root,tracked_method())
        self.method_file.write_text("edited method file",encoding="utf-8")
        result=run_novelty_search(self.root,fixture_sources=self.fixtures())
        self.assertEqual(result["report"]["gate_status"],"PASS")
        self.assertEqual(get_gate_status(self.root)["gate"]["status"],"PASS")

    def test_prior_status_sync_does_not_block_rerun(self):
        register_method(self.root,tracked_method())
        self.method_file.write_text("edited method file",encoding="utf-8")
        result=run_novelty_search(self.root,fixture_sources=self.fixtures())
        self.assertEqual(result["report"]["gate_status"],"PASS")
        self.assertEqual(get_gate_status(self.root)["gate"]["status"],"PASS")

    def test_file_edit_does_not_create_a_new_method_version(self):
        first = register_method(self.root, tracked_method())["state"]
        old_hash = first["active_method"]["hash"]
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.method_file.write_text("causal confidence gate", encoding="utf-8")
        second = register_method(self.root, tracked_method())
        self.assertFalse(second["changed"])
        self.assertEqual(second["state"]["active_method"]["version"], 1)
        self.assertEqual(second["state"]["active_method"]["hash"], old_hash)
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.assertTrue(verify_receipt(self.root, strict=True)["valid"])

    def test_registration_rejects_nonexistent_declared_file_without_creating_state(self):
        missing = {**tracked_method(), "method_files": ["inputs/not-present.csv"]}
        with self.assertRaisesRegex(GuardError, "must exist and be a regular file"):
            register_method(self.root, missing)
        self.assertIsNone(load_state(self.root, required=False))

    def test_registration_rejects_directory_instead_of_hashing_it_as_missing(self):
        (self.root / "inputs").mkdir()
        directory = {**tracked_method(), "method_files": ["inputs"]}
        with self.assertRaisesRegex(GuardError, "must exist and be a regular file"):
            register_method(self.root, directory)
        self.assertIsNone(load_state(self.root, required=False))

    def test_deleted_tracked_file_still_invalidates_existing_registration(self):
        register_method(self.root, tracked_method())
        self.method_file.unlink()
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "DOMAIN_SELECTION_REQUIRED")
        with self.assertRaisesRegex(GuardError, "must exist and be a regular file"):
            register_method(self.root, tracked_method())


if __name__ == "__main__":
    unittest.main()
