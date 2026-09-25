from __future__ import annotations

import json
import os
import subprocess
import sys
import types
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop")


class ManifestTests(unittest.TestCase):
    def test_claude_plugin_manifest(self) -> None:
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "research-guard")
        for field in ("version", "description", "author"):
            self.assertIn(field, manifest)
        # Default component layout must exist at the plugin root.
        for relative in ("skills", "hooks/hooks.json", ".mcp.json"):
            self.assertTrue((ROOT / relative).exists(), relative)

    def test_kimi_plugin_manifest(self) -> None:
        manifest = json.loads((ROOT / "kimi.plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "research-guard")
        self.assertEqual(manifest["skills"], "./skills/")
        server = manifest["mcpServers"]["research-guard"]
        self.assertEqual(server["command"], "python")
        launcher = server["args"][-1]
        self.assertTrue(launcher.startswith("./"), launcher)
        self.assertTrue((ROOT / launcher).is_file(), launcher)

    def test_manifest_versions_match_codex(self) -> None:
        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        for relative in (".claude-plugin/plugin.json", "kimi.plugin.json"):
            manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], codex["version"], relative)


class McpConfigTests(unittest.TestCase):
    def _resolver_code(self) -> str:
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        args = config["mcpServers"]["research-guard"]["args"]
        self.assertEqual(args[:3], ["-X", "utf8", "-c"])
        return args[3]

    def _run_resolver(self, code: str, env: dict[str, str]) -> str:
        captured: dict[str, str] = {}
        fake_runpy = types.ModuleType("runpy")
        fake_runpy.run_path = lambda path, run_name=None: captured.setdefault("path", path)
        with unittest.mock.patch.dict(sys.modules, {"runpy": fake_runpy}):
            with unittest.mock.patch.dict(os.environ, env, clear=False):
                exec(compile(code, ".mcp.json", "exec"), {})  # noqa: S102
        return captured["path"]

    def test_resolver_mentions_both_plugin_root_variables(self) -> None:
        code = self._resolver_code()
        self.assertIn("${PLUGIN_ROOT}", code)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", code)
        self.assertIn("mcp_launcher.py", code)

    def test_resolver_leaves_no_variable_after_bridge_substitution(self) -> None:
        code = self._resolver_code()
        resolved = code.replace("${PLUGIN_ROOT}", "/plugin").replace("${CLAUDE_PLUGIN_ROOT}", "/plugin")
        self.assertNotIn("${", resolved)

    def test_resolver_prefers_environment(self) -> None:
        code = self._resolver_code()
        path = self._run_resolver(code, {"PLUGIN_ROOT": "/env/plugin"})
        self.assertEqual(path, os.path.join("/env/plugin", "scripts", "mcp_launcher.py"))

    def test_resolver_uses_expanded_placeholder(self) -> None:
        code = self._resolver_code().replace("${CLAUDE_PLUGIN_ROOT}", "/harness/plugin")
        env = {key: "" for key in ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")}
        path = self._run_resolver(code, env)
        self.assertEqual(path, os.path.join("/harness/plugin", "scripts", "mcp_launcher.py"))

    def test_resolver_fails_closed_without_root(self) -> None:
        code = self._resolver_code()
        env = {key: "" for key in ("PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT")}
        with unittest.mock.patch.dict(os.environ, env, clear=False):
            with self.assertRaises(SystemExit):
                exec(compile(code, ".mcp.json", "exec"), {})  # noqa: S102


class HookConfigTests(unittest.TestCase):
    def _hooks(self) -> dict:
        return json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]

    def test_all_five_events_present(self) -> None:
        hooks = self._hooks()
        for event in HOOK_EVENTS:
            self.assertIn(event, hooks)

    def test_posix_commands_resolve_plugin_root_with_claude_fallback(self) -> None:
        for event, entries in self._hooks().items():
            for entry in entries:
                for hook in entry["hooks"]:
                    command = hook["command"]
                    self.assertIn("${PLUGIN_ROOT}", command, event)
                    self.assertIn("CLAUDE_PLUGIN_ROOT", command, event)
                    self.assertIn("hooks/hook.sh", command, event)
                    self.assertEqual(hook.get("commandWindows"), '"%PLUGIN_ROOT%\\scripts\\hook.cmd"', event)

    def test_posix_command_accepts_claude_plugin_root(self) -> None:
        import shutil

        sh = shutil.which("sh")
        if not sh:
            self.skipTest("POSIX sh not available on this host")
        hooks = self._hooks()
        command = hooks["UserPromptSubmit"][0]["hooks"][0]["command"]
        # Unexpanded ${PLUGIN_ROOT} must fall back to CLAUDE_PLUGIN_ROOT; point the
        # fallback at a scratch tree whose hook.sh records that it ran.
        scratch = ROOT / ".research-guard" / "test-harness-hook"
        (scratch / "hooks").mkdir(parents=True, exist_ok=True)
        marker = scratch / "ran"
        (scratch / "hooks" / "hook.sh").write_text(f'#!/usr/bin/env sh\ntouch "{marker}"\n', encoding="utf-8")
        try:
            env = {key: value for key, value in os.environ.items() if key != "PLUGIN_ROOT"}
            env["CLAUDE_PLUGIN_ROOT"] = str(scratch)
            subprocess.run([sh, "-c", command], env=env, check=True, capture_output=True, timeout=30)
            self.assertTrue(marker.is_file())
        finally:
            marker.unlink(missing_ok=True)
            (scratch / "hooks" / "hook.sh").unlink(missing_ok=True)


class DocumentationTests(unittest.TestCase):
    def test_compatibility_guide_pair_and_links(self) -> None:
        en = (ROOT / "docs" / "HARNESS_COMPATIBILITY.md").read_text(encoding="utf-8")
        zh = (ROOT / "docs" / "HARNESS_COMPATIBILITY.zh-CN.md").read_text(encoding="utf-8")
        for text in (en, zh):
            self.assertIn("research-guard-doc-pair: harness-compatibility", text)
        for harness in ("Claude Code", "Codex", "Kimi", "ZCode", "WorkBuddy", "OpenClaw", "DSH"):
            self.assertIn(harness, en)
        self.assertIn("docs/HARNESS_COMPATIBILITY.md", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("docs/HARNESS_COMPATIBILITY.zh-CN.md", (ROOT / "README.zh-CN.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
