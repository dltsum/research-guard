from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ADDON = Path(__file__).resolve().parents[1]
PLUGIN = ADDON.parents[1]
FAKE_CODEX = Path(__file__).resolve().parent / "fake_codex.py"
sys.path.insert(0, str(ADDON))

from research_console.codex_bridge import BridgeError, CodexBridge, discover_preflight  # noqa: E402
from research_console.contracts import normalize_chat_request  # noqa: E402


def bridge() -> CodexBridge:
    with patch.dict(os.environ, {"FAKE_RESEARCH_GUARD_PLUGIN_ROOT": str(PLUGIN)}):
        return CodexBridge(discover_preflight((sys.executable, str(FAKE_CODEX))))


class BridgeTests(unittest.TestCase):
    def test_preflight_uses_machine_readable_codex_and_plugin_status(self) -> None:
        value = bridge().preflight
        self.assertEqual(value.codex_version, "codex-cli 0.test")
        self.assertEqual(value.plugin_version, "0.7.0+codex.test")
        self.assertEqual(value.plugin_root, PLUGIN.resolve())
        self.assertEqual(value.disabled_mcp_servers, ("unrelated-test-server",))
        self.assertTrue(value.mcp_args[-1].endswith("scripts\\mcp_launcher.py") or value.mcp_args[-1].endswith("scripts/mcp_launcher.py"))
        self.assertEqual(value.resource_policy["owned_task_budget_bytes"], 512 * 1024**2)

    def test_preflight_rejects_an_older_core_plugin(self) -> None:
        environment = {
            "FAKE_RESEARCH_GUARD_PLUGIN_ROOT": str(PLUGIN),
            "FAKE_PLUGIN_VERSION": "0.6.9",
        }
        with patch.dict(os.environ, environment):
            with self.assertRaises(BridgeError) as raised:
                discover_preflight((sys.executable, str(FAKE_CODEX)))
        self.assertEqual(raised.exception.code, "RESEARCH_GUARD_VERSION_UNSUPPORTED")

    def test_preflight_rejects_an_mcp_name_that_cannot_be_safely_overridden(self) -> None:
        environment = {
            "FAKE_RESEARCH_GUARD_PLUGIN_ROOT": str(PLUGIN),
            "FAKE_MCP_NAME": "unsafe.dotted-name",
        }
        with patch.dict(os.environ, environment):
            with self.assertRaises(BridgeError) as raised:
                discover_preflight((sys.executable, str(FAKE_CODEX)))
        self.assertEqual(raised.exception.code, "MCP_LIST_INVALID")

    def test_new_and_resumed_commands_keep_prompt_out_of_process_arguments(self) -> None:
        value = bridge()
        with tempfile.TemporaryDirectory() as temporary:
            request = normalize_chat_request({"message": "secret research prompt"}, Path(temporary))
            command = value._command(request)
            self.assertEqual(command[-1], "-")
            self.assertNotIn("--ignore-user-config", command)
            joined = " ".join(command)
            self.assertIn("mcp_servers.unrelated-test-server.enabled=false", joined)
            self.assertIn('mcp_servers.research-guard.default_tools_approval_mode="approve"', joined)
            self.assertIn("mcp_servers.research-guard.required=true", joined)
            self.assertNotIn(request.message, command)
            resumed = normalize_chat_request({
                "message": "continue",
                "thread_id": "11111111-2222-4333-8444-555555555555",
            }, Path(temporary))
            resumed_command = value._command(resumed)
            self.assertIn("resume", resumed_command)
            self.assertNotIn("--ignore-user-config", resumed_command)
            self.assertLess(resumed_command.index("-c"), resumed_command.index("resume"))
            self.assertNotIn("--sandbox", resumed_command)
            self.assertNotIn("--cd", resumed_command)

    def test_jsonl_stream_normalizes_messages_links_diagnostics_and_resources(self) -> None:
        value = bridge()
        with tempfile.TemporaryDirectory() as temporary:
            request = normalize_chat_request({"message": "Find evidence."}, Path(temporary))
            with patch.dict(os.environ, {"FAKE_RESEARCH_GUARD_PLUGIN_ROOT": str(PLUGIN)}):
                events = list(value.stream(request))
        kinds = [item["kind"] for item in events]
        self.assertEqual(kinds[0], "run")
        self.assertIn("thread", kinds)
        self.assertIn("assistant", kinds)
        self.assertTrue(any(
            item.get("kind") == "activity"
            and item.get("event", {}).get("item_type") == "mcp_tool_call"
            and item.get("event", {}).get("server") == "research-guard"
            and item.get("event", {}).get("status") == "completed"
            for item in events
        ))
        self.assertIn("resource", kinds)
        self.assertEqual(kinds[-1], "done")
        self.assertTrue(events[-1]["success"])
        self.assertLessEqual(events[-1]["peak_owned_bytes"], 512 * 1024**2)
        assistant = next(item for item in events if item["kind"] == "assistant")
        self.assertIn("https://doi.org/10.1234/example", assistant["text"])
        serialized = repr(events)
        self.assertNotIn("test-secret-value", serialized)
        self.assertNotIn("unsafe-test-token", serialized)
        self.assertNotIn(str(Path.home()), serialized)

    def test_start_reservation_rejects_a_second_turn(self) -> None:
        value = bridge()
        value._starting_run_id = "reserved-run"
        with tempfile.TemporaryDirectory() as temporary:
            request = normalize_chat_request({"message": "Second turn."}, Path(temporary))
            with self.assertRaises(BridgeError) as raised:
                next(value.stream(request))
        self.assertEqual(raised.exception.code, "RUN_BUSY")

    def test_resource_breach_stops_owned_codex_tree_and_never_passes(self) -> None:
        value = bridge()
        limit = int(value.preflight.resource_policy["owned_task_budget_bytes"])
        with tempfile.TemporaryDirectory() as temporary:
            request = normalize_chat_request({"message": "Bounded turn."}, Path(temporary))
            environment = {
                "FAKE_RESEARCH_GUARD_PLUGIN_ROOT": str(PLUGIN),
                "FAKE_CODEX_DELAY_SECONDS": "0.2",
            }
            with patch.dict(os.environ, environment), patch.object(
                value, "_owned_snapshot", return_value=(limit + 1, 2 * 1024**3)
            ):
                events = list(value.stream(request))
        final = events[-1]
        self.assertEqual(final["kind"], "done")
        self.assertFalse(final["success"])
        self.assertEqual(final["resource_breach"], "RESOURCE_WORKING_SET_ABORT")


if __name__ == "__main__":
    unittest.main()
