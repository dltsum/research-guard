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

from mcp_server import TOOLS, handle  # noqa: E402
from research_guard_core import load_state, refresh_domain, register_method, run_novelty_search  # noqa: E402
import dependency_manager  # noqa: E402


def sample_method(**changes):
    value = {
        "title": "Graph retrieval for long horizon language model agents",
        "problem": "Language model agents retrieve irrelevant memory during long tasks",
        "mechanism": "A confidence gate selects graph connected episodic memory",
        "contributions": "adaptive graph memory retrieval",
    }
    value.update(changes)
    return value


class EnforcementRoundTwoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.key = Path(self.temp.name) / "key.bin"
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        self.old_dependency_home = os.environ.get("RESEARCH_GUARD_HOME")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.key)
        os.environ["RESEARCH_GUARD_HOME"] = str(Path(self.temp.name) / "dependency-home")
        dependency_manager.decide([], [])

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        if self.old_dependency_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = self.old_dependency_home
        self.temp.cleanup()

    def fixtures(self):
        state = load_state(self.root)
        if not state.get("search_plan"):
            refresh_domain(
                self.root,
                primary_domain="computer_science",
                secondary_domains=[],
                selected_by="main_agent",
                selection_rationale="The main agent selected computer science for this graph-memory retrieval method.",
            )
            state = load_state(self.root)
        return {source: [] for source in state["search_plan"]["required_sources"]}

    def hook(self, payload):
        completed = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")],
            input=json.dumps(payload), text=True, capture_output=True, cwd=self.root,
            env={**os.environ, "PYTHONUTF8": "1"}, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout) if completed.stdout.strip() else {}

    def test_mcp_exposes_all_required_tools(self):
        names = {tool["name"] for tool in TOOLS}
        self.assertEqual(names, {
            "select_research_modules", "list_research_modules",
            "register_method", "classify_domain", "build_search_plan", "run_novelty_search",
            "list_sources", "request_manual_evidence", "register_manual_evidence",
            "verify_publication", "verify_index_membership", "record_collision_resolution",
            "get_collision_report", "get_gate_status",
            "paper_audit", "research_design", "language_assist",
        })

    def test_mcp_initialize_and_call_register_method(self):
        initialized = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "research-guard")
        called = handle({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "register_method", "arguments": {"project_root": str(self.root), "method": sample_method()}},
        })
        self.assertFalse(called["result"]["isError"])
        self.assertEqual(called["result"]["structuredContent"]["state"]["gate"]["status"], "DOMAIN_SELECTION_REQUIRED")

    def test_mcp_stdio_transport_is_line_delimited_json_rpc(self):
        messages = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        ]) + "\n"
        completed = subprocess.run(
            [sys.executable, str(PLUGIN / "scripts" / "mcp_server.py")], input=messages,
            text=True, capture_output=True, timeout=10, env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual([item["id"] for item in responses], [1, 2])
        self.assertEqual(len(responses[1]["result"]["tools"]), 17)

    def test_prompt_method_change_adds_mandatory_context(self):
        output = self.hook({
            "hook_event_name": "UserPromptSubmit", "cwd": str(self.root),
            "prompt": "把论文方法中的 graph gate 改为 causal gate",
        })
        text = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Register the method first", text)
        self.assertIn("method_change=true exactly when", text)

    def test_pending_gate_blocks_paper_write(self):
        register_method(self.root, sample_method())
        output = self.hook({
            "hook_event_name": "PreToolUse", "cwd": str(self.root), "tool_name": "apply_patch",
            "tool_input": {"command": "*** Add File: paper.tex\n+draft"},
        })
        decision = output["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("DOMAIN_SELECTION_REQUIRED", decision["permissionDecisionReason"])

    def test_pass_gate_allows_paper_write(self):
        register_method(self.root, sample_method())
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        output = self.hook({
            "hook_event_name": "PreToolUse", "cwd": str(self.root), "tool_name": "apply_patch",
            "tool_input": {"command": "*** Add File: paper.tex\n+draft"},
        })
        self.assertEqual(output, {})

    def test_method_file_edit_is_allowed_then_post_hook_invalidates(self):
        tracked = self.root / "method.md"
        tracked.write_text("confidence gate", encoding="utf-8")
        register_method(self.root, sample_method(method_files=["method.md"]))
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        pre = self.hook({
            "hook_event_name": "PreToolUse", "cwd": str(self.root), "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: method.md\n-confidence\n+causal"},
        })
        self.assertIn("tracked method file", pre["hookSpecificOutput"]["additionalContext"].lower())
        tracked.write_text("causal gate", encoding="utf-8")
        post = self.hook({
            "hook_event_name": "PostToolUse", "cwd": str(self.root), "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: method.md"}, "tool_response": {"ok": True},
        })
        self.assertIn("invalid", post["hookSpecificOutput"]["additionalContext"].lower())
        self.assertEqual(load_state(self.root)["gate"]["status"], "NOVELTY_CHECK_REQUIRED")

    def test_stop_blocks_once_then_exits_explicitly(self):
        register_method(self.root, sample_method())
        first = self.hook({"hook_event_name": "Stop", "cwd": str(self.root), "stop_hook_active": False})
        self.assertEqual(first["decision"], "block")
        second = self.hook({"hook_event_name": "Stop", "cwd": str(self.root), "stop_hook_active": True})
        self.assertFalse(second["continue"])
        self.assertIn("DOMAIN_SELECTION_REQUIRED", second["stopReason"])

    def test_cli_strict_returns_two_before_pass_and_zero_after_pass(self):
        register_method(self.root, sample_method())
        command = [sys.executable, str(PLUGIN / "scripts" / "researchctl.py"), "verify", "--project-root", str(self.root), "--strict"]
        before = subprocess.run(command, text=True, capture_output=True, env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(before.returncode, 2)
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        after = subprocess.run(command, text=True, capture_output=True, env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(after.returncode, 0, after.stderr)

    def test_unknown_index_fails_closed(self):
        result = handle({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "verify_index_membership", "arguments": {"identifier": "venue", "index": "invented"}},
        })
        structured = result["result"]["structuredContent"]
        self.assertFalse(structured["verified"])
        self.assertIn("unsupported", structured["reason"])


if __name__ == "__main__":
    unittest.main()
