from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from intent_router_core import route_prompt, select_research_modules  # noqa: E402
from mcp_server import TOOLS  # noqa: E402
from paper_audit_core import plan_paper_audit  # noqa: E402


class P10CycleDRouterTests(unittest.TestCase):
    EXPECTED_MODULES = {
        "domain_skill", "academic_language", "venue_evidence", "formula_verification",
        "research_artifact", "self_evolution", "citation_literature", "academic_figure",
        "paper_audit", "research_strategy",
    }

    def test_router_returns_catalog_without_automatic_semantic_choice(self):
        for prompt in (
            "深入探讨单细胞转录组分析方法", "请润色这篇学术论文", "给 CVPR 论文设计章节和排版",
            "核验全文公式并用 Lean 检查", "run a literature review with DOI references",
            "audit this manuscript and its experiments", "Plan a weekend picnic",
        ):
            with self.subTest(prompt=prompt):
                routed = route_prompt(prompt)
                self.assertEqual(routed["status"], "MAIN_AGENT_SELECTION_REQUIRED")
                self.assertEqual(routed["selected_modules"], [])
                self.assertIsNone(routed["method_change_overlay"])
        catalog = {item["id"] for item in route_prompt("anything")["modules"]}
        self.assertTrue(self.EXPECTED_MODULES.issubset(catalog))

    def test_main_agent_can_select_at_most_three_nonoverlapping_modules(self):
        prompt = "Deep dive into a CVPR paper with formulas, plots, and language revision"
        with tempfile.TemporaryDirectory() as temporary:
            routed = select_research_modules(
                temporary, request_text=prompt,
                selected_modules=["formula_verification", "academic_figure", "academic_language"],
                selection_rationale="The main agent selected three non-overlapping owners for this mixed request.",
                selected_by="main_agent", method_change=False,
            )
        self.assertEqual(routed["status"], "SELECTED")
        self.assertEqual(len(routed["selection"]["selected_modules"]), 3)

    def test_method_change_is_a_main_agent_declaration(self):
        routed = route_prompt("Modify the research method and loss")
        self.assertIsNone(routed["method_change_overlay"])
        self.assertIn("main agent must decide", routed["hard_overlay_instruction"])

    def test_hook_emits_explicit_selection_and_continuation_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = json.dumps({
                "hook_event_name": "UserPromptSubmit", "cwd": temporary,
                "prompt": "深入探讨这个研究方法，然后修改其损失函数",
            }, ensure_ascii=False)
            run = subprocess.run(
                [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")], input=payload,
                text=True, capture_output=True, encoding="utf-8", check=True,
            )
        context = json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(context.startswith("Research Guard does not run keyword domain classifiers"))
        self.assertIn("select_research_modules", context)
        self.assertIn("method_change=true", context)
        self.assertIn("status=IN_PROGRESS", context)
        self.assertIn("not a stopping condition", context)

    def test_explicit_formula_audit_reaches_lean_requirement(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = plan_paper_audit(
                temporary, "核验论文全文所有公式、方程、定理和参数",
                selected_roles=["formal_math_lean", "adversarial_logic"],
                audit_features={"formula": True}, selected_by="main_agent",
                selection_rationale="The main agent selected formal and adversarial roles for the equation audit.",
            )
        self.assertTrue(plan["requirements"]["lean_required"])
        self.assertIn("formal_math_lean", plan["selected_roles"])
        self.assertFalse(plan["automatic_role_selection"])


class P10CycleDMCPTests(unittest.TestCase):
    def test_tool_surface_adds_explicit_selection_without_removing_existing_tools(self):
        self.assertEqual(len(TOOLS), 17)
        names = {item["name"] for item in TOOLS}
        self.assertIn("select_research_modules", names)
        self.assertIn("list_research_modules", names)
        design = next(item for item in TOOLS if item["name"] == "research_design")
        props = design["inputSchema"]["properties"]
        self.assertIn("knowledge_action", props)
        self.assertIn("domain_skill_action", props)
        self.assertIn("frontier_skill_action", props)
        self.assertIn("artifact_action", props)
        self.assertIn("evolution_action", props)
        self.assertNotIn("apply", props["evolution_action"]["enum"])
        paper = next(item for item in TOOLS if item["name"] == "paper_audit")
        self.assertEqual(paper["inputSchema"]["properties"]["citation_action"]["enum"], ["verify_format"])


if __name__ == "__main__":
    unittest.main()
