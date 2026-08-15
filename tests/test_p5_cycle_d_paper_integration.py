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

try:
    from language_guard_core import analyze_language, finalize_language_review, resolve_language_issues
    IMPORT_ERROR = None
except ImportError as exc:
    analyze_language = finalize_language_review = resolve_language_issues = None
    IMPORT_ERROR = exc

from mcp_server import TOOLS, handle
from paper_audit_core import AuditError, plan_paper_audit, submit_paper_audit
import dependency_manager


class P5CycleDPaperIntegrationTests(unittest.TestCase):
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

    def require_component(self):
        self.assertIsNone(IMPORT_ERROR, f"language component missing: {IMPORT_ERROR}")

    def hook(self, prompt):
        done = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")],
            input=json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": str(self.root), "prompt": prompt}),
            text=True, capture_output=True, cwd=self.root, env={**os.environ, "PYTHONUTF8": "1"}, timeout=20,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout) if done.stdout.strip() else {}

    def reports(self, plan):
        return [{"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "none", "status": "verified"}]} for role in plan["selected_roles"]]

    def online(self):
        return [{"claim": "policy", "url": "https://example.org/policy", "accessed_at": "2026-08-12", "source_type": "official", "status": "verified"}]

    def test_one_new_mcp_multiplexer_and_fifteen_tools(self):
        names = [tool["name"] for tool in TOOLS]
        self.assertEqual(len(names), 15)
        self.assertEqual(names.count("language_assist"), 1)
        tool = next(item for item in TOOLS if item["name"] == "language_assist")
        self.assertEqual(tool["inputSchema"]["properties"]["action"]["enum"], [
            "plan", "analyze", "register_card", "retrieve", "resolve", "finalize", "status", "verify",
        ])

    def test_mcp_language_plan_and_analyze(self):
        self.require_component()
        planned = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "language_assist", "arguments": {
            "action": "plan", "project_root": str(self.root), "request_text": "Polish",
            "draft_text": "It should be noted that the result is bounded.",
        }}})
        self.assertFalse(planned["result"]["isError"])
        analyzed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "language_assist", "arguments": {
            "action": "analyze", "project_root": str(self.root),
            "draft_text": "It should be noted that the result is bounded.",
        }}})
        self.assertFalse(analyzed["result"]["isError"])

    def test_paper_plan_auto_runs_language_review_on_manuscript(self):
        self.require_component()
        (self.root / "paper.md").write_text("The result is bounded.\n", encoding="utf-8")
        plan = plan_paper_audit(self.root, "Audit the manuscript", paper_files=["paper.md"])
        self.assertTrue(plan["requirements"]["language_review_required"])
        self.assertEqual(plan["language_review"]["status"], "PASS")

    def test_paper_submit_blocks_unresolved_language_issue(self):
        self.require_component()
        (self.root / "paper.md").write_text("It should be noted that the result is bounded.\n", encoding="utf-8")
        plan = plan_paper_audit(self.root, "Audit the manuscript", paper_files=["paper.md"])
        self.assertEqual(plan["language_review"]["status"], "REVIEW_REQUIRED")
        with self.assertRaises(AuditError):
            submit_paper_audit(self.root, role_reports=self.reports(plan), online_checks=self.online())

    def test_resolved_language_receipt_is_embedded_in_paper_receipt(self):
        self.require_component()
        (self.root / "paper.md").write_text("It should be noted that the result is bounded.\n", encoding="utf-8")
        plan = plan_paper_audit(self.root, "Audit the manuscript", paper_files=["paper.md"])
        analysis = analyze_language(self.root)
        blockers = [item for item in analysis["findings"] if item["blocking"]]
        resolve_language_issues(self.root, [{
            "issue_id": item["issue_id"], "action": "retain_with_justification",
            "rationale": "The statement is an intentional scope boundary and must remain explicit.",
        } for item in blockers])
        language_receipt = finalize_language_review(self.root)
        result = submit_paper_audit(self.root, role_reports=self.reports(plan), online_checks=self.online())
        self.assertEqual(result["language_receipt_sha256"], language_receipt["receipt_sha256"])

    def test_prompt_hook_names_language_tool_and_link_rule(self):
        self.require_component()
        output = self.hook("Help polish the defensive writing in my related work and citations.")
        text = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("language_assist", text)
        self.assertIn("https://", text)

    def test_method_change_and_language_triggers_coexist(self):
        self.require_component()
        output = self.hook("Revise the manuscript and change the method mechanism.")
        text = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("language_assist", text)
        self.assertIn("register_method", text)

    def test_no_manuscript_source_is_explicitly_not_applicable(self):
        self.require_component()
        plan = plan_paper_audit(self.root, "Audit the manuscript")
        self.assertFalse(plan["requirements"]["language_review_required"])
        self.assertEqual(plan["language_review"]["status"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
