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
from paper_audit_core import AuditError, plan_paper_audit, submit_paper_audit  # noqa: E402
import dependency_manager  # noqa: E402


class P6CycleDIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_dependency_home = os.environ.get("RESEARCH_GUARD_HOME")
        os.environ["RESEARCH_GUARD_HOME"] = str(self.root / "dependency-home")
        dependency_manager.decide([], [])

    def tearDown(self):
        if self.old_dependency_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = self.old_dependency_home
        self.temp.cleanup()

    def hook(self, prompt: str):
        done = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")],
            input=json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": str(self.root), "prompt": prompt}),
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONUTF8": "1"},
            timeout=20,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_single_tool_surface_adds_configuration_and_decisions_not_new_tool(self):
        names = [item["name"] for item in TOOLS]
        self.assertEqual(len(names), 15)
        self.assertEqual(names.count("language_assist"), 1)
        props = next(item for item in TOOLS if item["name"] == "language_assist")["inputSchema"]["properties"]
        for name in ("task_mode", "source_text", "source_language", "target_language", "terminology", "venue_contract", "decisions"):
            self.assertIn(name, props)

    def test_mcp_user_decision_roundtrip(self):
        text = "This study is limited to one hospital."
        planned = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "language_assist", "arguments": {
            "action": "plan", "project_root": str(self.root), "request_text": "Polish", "draft_text": text,
        }}})
        self.assertFalse(planned["result"]["isError"])
        analyzed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "language_assist", "arguments": {
            "action": "analyze", "project_root": str(self.root), "draft_text": text,
        }}})
        payload = analyzed["result"]["structuredContent"]
        decision_id = payload["decision_checklist"][0]["decision_id"]
        resolved = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "language_assist", "arguments": {
            "action": "resolve", "project_root": str(self.root), "decisions": [{
                "decision_id": decision_id, "action": "retain_as_written", "selected_by": "user",
                "rationale": "The user explicitly retained the actual single-site limitation for readers.",
            }],
        }}})
        self.assertFalse(resolved["result"]["isError"])

    def test_translation_and_conference_prompts_route_to_language_contract(self):
        for prompt in ("把这篇论文翻译成英文并保持数字引用", "Help draft this conference manuscript using the official template"):
            text = self.hook(prompt)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("language_assist", text)
            self.assertIn("user decision", text.lower())

    def test_paper_audit_does_not_pass_before_limitation_decision(self):
        (self.root / "paper.md").write_text("This study is limited to one hospital.\n", encoding="utf-8")
        plan = plan_paper_audit(self.root, "Audit this manuscript", paper_files=["paper.md"])
        self.assertEqual(plan["language_review"]["status"], "USER_DECISION_REQUIRED")
        reports = [{
            "role": role,
            "findings": ["checked"],
            "numeric_checks": [{"claim": "none", "status": "verified"}],
        } for role in plan["selected_roles"]]
        with self.assertRaises(AuditError):
            submit_paper_audit(
                self.root,
                role_reports=reports,
                online_checks=[{
                    "claim": "policy", "url": "https://example.org/policy", "accessed_at": "2026-08-12",
                    "source_type": "official", "status": "verified",
                }],
            )


if __name__ == "__main__":
    unittest.main()
