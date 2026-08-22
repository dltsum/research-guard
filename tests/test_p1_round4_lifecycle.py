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
from paper_audit_core import get_paper_audit_status, plan_paper_audit, submit_paper_audit  # noqa: E402
import dependency_manager  # noqa: E402


class PaperAuditLifecycleTests(unittest.TestCase):
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

    def hook(self, payload):
        done = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")],
            input=json.dumps(payload), text=True, capture_output=True, cwd=self.root,
            env={**os.environ, "PYTHONUTF8": "1"}, timeout=20,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout) if done.stdout.strip() else {}

    def plan(self, request_text, *, roles=None, features=None, paper_files=None):
        return plan_paper_audit(
            self.root,
            request_text,
            paper_files=paper_files,
            selected_roles=roles or ["methodology_statistics", "adversarial_logic"],
            audit_features=features or {},
            selected_by="main_agent",
            selection_rationale="The main agent selected the smallest reviewer set that covers this lifecycle test.",
        )

    def test_mcp_exposes_single_paper_audit_multiplexer(self):
        names = [tool["name"] for tool in TOOLS]
        self.assertEqual(names.count("paper_audit"), 1)
        self.assertEqual(len(names), 17)
        called = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "paper_audit", "arguments": {
            "action": "plan", "project_root": str(self.root), "request_text": "audit the manuscript",
            "selected_roles": ["methodology_statistics", "adversarial_logic"],
            "audit_features": {}, "selected_by": "main_agent",
            "selection_rationale": "The main agent selected two complementary manuscript audit roles.",
        }}})
        self.assertFalse(called["result"]["isError"])

    def test_writing_prompt_triggers_audit_and_link_rule(self):
        output = self.hook({"hook_event_name": "UserPromptSubmit", "cwd": str(self.root), "prompt": "Help write the related work and citations."})
        text = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Paper audits likewise require 2-3 roles", text)
        self.assertEqual(get_paper_audit_status(self.root)["status"], "NOT_PLANNED")
        planned = self.plan(
            "Help write the related work and citations.",
            roles=["domain_literature", "adversarial_logic"],
            features={"literature": True},
        )
        self.assertTrue(planned["requirements"]["literature_https_links_required"])

    def test_formula_prompt_mandates_lean(self):
        output = self.hook({"hook_event_name": "UserPromptSubmit", "cwd": str(self.root), "prompt": "请协助检查全文公式与参数"})
        self.assertIn("explicit audit_features", output["hookSpecificOutput"]["additionalContext"])
        planned = self.plan(
            "Please inspect all formulas and parameters.",
            roles=["formal_math_lean", "methodology_statistics"],
            features={"formula": True},
        )
        self.assertTrue(planned["requirements"]["lean_required"])

    def test_code_experiment_plan_requires_evidence(self):
        plan = self.plan(
            "Audit experiment code, datasets, seeds and results",
            roles=["code_experiment_integrity", "methodology_statistics"],
            features={"experiment": True},
        )
        reports = [{"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "metric", "status": "verified"}]} for role in plan["selected_roles"]]
        with self.assertRaises(Exception):
            submit_paper_audit(self.root, role_reports=reports, online_checks=[{"claim": "benchmark", "url": "https://example.org/benchmark", "accessed_at": "2026-08-11", "source_type": "official", "status": "verified"}])

    def test_tracked_input_change_invalidates_receipt(self):
        paper = self.root / "paper.md"
        paper.write_text("v1", encoding="utf-8")
        plan = self.plan("Audit final manuscript", paper_files=["paper.md"])
        reports = [{"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "number", "status": "verified"}]} for role in plan["selected_roles"]]
        submit_paper_audit(self.root, role_reports=reports, online_checks=[{"claim": "current policy", "url": "https://example.org/policy", "accessed_at": "2026-08-11", "source_type": "official", "status": "verified"}])
        paper.write_text("v2", encoding="utf-8")
        self.assertEqual(get_paper_audit_status(self.root)["status"], "AUDIT_REQUIRED")


if __name__ == "__main__":
    unittest.main()
