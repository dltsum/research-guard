from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import (  # noqa: E402
    GuardError,
    declare_method_change,
    get_gate_status,
    load_state,
    register_method,
    run_novelty_search,
    verify_receipt,
)


def sample_method(**changes):
    value = {
        "title": "Graph retrieval for long horizon language model agents",
        "problem": "Language model agents retrieve irrelevant memory during long tasks",
        "mechanism": "A confidence gate selects graph connected episodic memory",
        "contributions": "adaptive graph memory retrieval",
    }
    value.update(changes)
    return value


class PromptMethodChangeGateRoundSixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
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
        return {source: [] for source in load_state(self.root)["search_plan"]["required_sources"]}

    def hook(self, payload):
        completed = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")],
            input=json.dumps(payload), text=True, capture_output=True, cwd=self.root,
            env={**os.environ, "PYTHONUTF8": "1"}, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout) if completed.stdout.strip() else {}

    def make_pass(self):
        register_method(self.root, sample_method())
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.assertTrue(verify_receipt(self.root, strict=True)["valid"])

    def declare_through_hook(self):
        return self.hook({
            "hook_event_name": "UserPromptSubmit",
            "cwd": str(self.root),
            "prompt": "把论文方法中的 graph gate 改为 causal gate",
        })

    def test_prompt_change_atomically_invalidates_pass_receipt(self):
        self.make_pass()
        output = self.declare_through_hook()
        state = load_state(self.root)
        self.assertIn("prior novelty receipt is invalidated", output["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(state["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        self.assertIsNone(state["latest_report"])
        self.assertIsNone(state["current_receipt"])
        self.assertEqual(state["pending_method_change"]["prior_method_version"], 1)
        self.assertNotIn("把论文方法", json.dumps(state["pending_method_change"], ensure_ascii=False))

    def test_protected_write_is_denied_after_conversational_change(self):
        self.make_pass()
        self.declare_through_hook()
        output = self.hook({
            "hook_event_name": "PreToolUse", "cwd": str(self.root), "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: paper.tex\n-old\n+new"},
        })
        decision = output["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("NOVELTY_CHECK_REQUIRED", decision["permissionDecisionReason"])

    def test_search_cannot_reuse_old_method_after_declaration(self):
        self.make_pass()
        self.declare_through_hook()
        with self.assertRaisesRegex(GuardError, "user-declared method adjustment is pending"):
            run_novelty_search(self.root, fixture_sources=self.fixtures())

    def test_identical_method_registration_cannot_clear_declaration(self):
        self.make_pass()
        self.declare_through_hook()
        with self.assertRaisesRegex(GuardError, "did not change the canonical method"):
            register_method(self.root, sample_method())
        self.assertIsNotNone(load_state(self.root)["pending_method_change"])

    def test_changed_method_requires_new_version_and_new_search(self):
        self.make_pass()
        self.declare_through_hook()
        changed = register_method(
            self.root,
            sample_method(mechanism="A causal gate selects graph connected episodic memory"),
        )
        self.assertTrue(changed["changed"])
        self.assertEqual(changed["state"]["active_method"]["version"], 2)
        self.assertNotIn("pending_method_change", changed["state"])
        self.assertEqual(changed["state"]["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.assertTrue(verify_receipt(self.root, strict=True)["valid"])

    def test_repeated_same_declaration_is_idempotent(self):
        self.make_pass()
        first = declare_method_change(self.root, "adjust the method mechanism")
        second = declare_method_change(self.root, "  adjust   the method mechanism  ")
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        audit = (self.root / ".research-guard" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(line)["event"] for line in audit]
        self.assertEqual(events.count("method_change_declared"), 1)

    def test_non_change_research_prompt_keeps_valid_receipt(self):
        self.make_pass()
        for prompt in ("请解释现有论文方法的机制", "The method addresses stale memory"):
            output = self.hook({
                "hook_event_name": "UserPromptSubmit",
                "cwd": str(self.root),
                "prompt": prompt,
            })
            serialized = json.dumps(output, ensure_ascii=False).casefold()
            self.assertNotIn("adjustment detected", serialized)
            self.assertNotIn("prior novelty receipt is invalidated", serialized)
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "PASS")
        self.assertTrue(verify_receipt(self.root, strict=True)["valid"])

    def test_gate_status_exposes_pending_declaration(self):
        self.make_pass()
        self.declare_through_hook()
        status = get_gate_status(self.root)
        self.assertIsNotNone(status["pending_method_change"])
        self.assertEqual(status["pending_method_change"]["prior_method_hash"], status["method_hash"])


if __name__ == "__main__":
    unittest.main()
