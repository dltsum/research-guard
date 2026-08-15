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

from intent_router_core import route_prompt  # noqa: E402
from mcp_server import TOOLS  # noqa: E402
from paper_audit_core import plan_paper_audit  # noqa: E402


class P10CycleDRouterTests(unittest.TestCase):
    CASES = {
        "深入探讨单细胞转录组分析方法": "domain_skill",
        "请润色这篇学术论文": "academic_language",
        "给 CVPR 论文设计章节和排版": "venue_evidence",
        "核验全文公式并用 Lean 检查": "formula_verification",
        "请做系统综述筛选账本": "research_artifact",
        "优化这个科研插件": "self_evolution",
        "run a literature review with DOI references": "citation_literature",
        "create a statistical research plot": "academic_figure",
        "audit this manuscript and its experiments": "paper_audit",
        "assess my research hypothesis and experiment design": "research_strategy",
    }

    def test_every_frozen_intent_has_an_owner(self):
        for prompt, owner in self.CASES.items():
            with self.subTest(prompt=prompt):
                routed = route_prompt(prompt)
                self.assertIn(owner, routed["selected_modules"])
                self.assertLessEqual(len(routed["selected_modules"]), 3)

    def test_mixed_prompt_never_selects_more_than_three(self):
        prompt = "Deep dive into a CVPR paper: literature review, formulas, experiments, plots, academic writing, and reviewer response"
        routed = route_prompt(prompt)
        self.assertEqual(len(routed["selected_modules"]), 3)
        self.assertTrue(any(item["suppressed_by"] == "module_budget" for item in routed["suppressed"]))

    def test_method_change_overlay_is_unskippable_and_outside_budget(self):
        routed = route_prompt("修改研究方法并增加一个损失项，同时润色论文并核验公式")
        self.assertTrue(routed["method_change_overlay"])
        self.assertLessEqual(len(routed["selected_modules"]), 3)
        self.assertIn("rerun the full collision search", routed["hard_overlay_instruction"])

    def test_nonresearch_prompt_does_not_trigger(self):
        self.assertEqual(route_prompt("Plan a weekend picnic")["status"], "NO_RESEARCH_MODULE")

    def test_hook_emits_domain_and_method_change_gates(self):
        with tempfile.TemporaryDirectory() as temporary:
            prompt = "深入探讨这个研究方法，然后修改其损失函数"
            payload = json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": temporary, "prompt": prompt}, ensure_ascii=False)
            run = subprocess.run(
                [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")], input=payload,
                text=True, capture_output=True, encoding="utf-8", check=True,
            )
        self.assertIn("domain_skill_action", run.stdout)
        self.assertIn("method adjustment", run.stdout)
        self.assertIn("prior receipt must not be reused", run.stdout)

    def test_chinese_formula_intent_reaches_lean_requirement(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = plan_paper_audit(temporary, "核验论文全文所有公式、方程、定理和参数")
        self.assertTrue(plan["requirements"]["lean_required"])
        self.assertIn("formal_math_lean", plan["selected_roles"])
        self.assertLessEqual(len(plan["selected_roles"]), 3)

    def test_method_change_message_precedes_large_mixed_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            prompt = "Modify this research method and loss, then deep dive into literature, CVPR layout, formulas, experiments, figures, writing, and reviewer response"
            payload = json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": temporary, "prompt": prompt})
            run = subprocess.run(
                [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")], input=payload,
                text=True, capture_output=True, encoding="utf-8", check=True,
            )
        context = json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(context.startswith("Research method adjustment detected."))
        self.assertIn("rerun the full collision search", context[:300])


class P10CycleDMCPTests(unittest.TestCase):
    def test_existing_15_tool_surface_is_preserved(self):
        self.assertEqual(len(TOOLS), 15)
        design = next(item for item in TOOLS if item["name"] == "research_design")
        props = design["inputSchema"]["properties"]
        self.assertIn("knowledge_action", props)
        self.assertIn("domain_skill_action", props)
        self.assertIn("artifact_action", props)
        self.assertIn("evolution_action", props)
        self.assertNotIn("apply", props["evolution_action"]["enum"])
        self.assertEqual(
            props["action"]["enum"],
            ["plan_ideation", "register_candidates", "commit_candidate", "plan_strategy", "register_strategy", "decide_strategy_branch", "register_hypothesis", "register_experiment", "status", "verify"],
        )
        paper = next(item for item in TOOLS if item["name"] == "paper_audit")
        self.assertEqual(paper["inputSchema"]["properties"]["citation_action"]["enum"], ["verify_format"])


if __name__ == "__main__":
    unittest.main()
