from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from intent_router_core import (  # noqa: E402
    WORK_DISCIPLINE_CONTEXT,
    list_research_modules,
    research_work_discipline,
    route_prompt,
    select_research_modules,
)
from mcp_server import dispatch, TOOLS  # noqa: E402


class WorkDisciplineTests(unittest.TestCase):
    def test_catalog_and_mcp_expose_the_same_advisory_contract(self):
        catalog = list_research_modules()
        self.assertEqual(dispatch("list_research_modules", {})["work_discipline"], catalog["work_discipline"])
        self.assertEqual(catalog["selected_modules"], [])
        self.assertFalse(catalog["selection_contract"]["automatic_keyword_routing"])
        self.assertEqual(len(TOOLS), 17)
        self.assertFalse(catalog["work_discipline"]["runtime_write_blocking"])
        self.assertEqual(catalog["work_discipline"]["enforcement"], "main_agent_guidance")

    def test_contract_calls_do_not_share_mutable_lists(self):
        first = research_work_discipline()
        first["verification"]["rerun_for"].clear()
        self.assertEqual(len(research_work_discipline()["verification"]["rerun_for"]), 6)

    def test_selection_persists_guidance_without_widening_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = select_research_modules(
                temporary, request_text="Review this paragraph without changing source files.",
                selected_modules=["academic_language"], selected_by="main_agent",
                selection_rationale="The request is a language review, not a method revision.",
                method_change=False,
            )
            saved = json.loads((Path(temporary) / result["selection_path"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["work_discipline"], research_work_discipline())
            self.assertFalse(saved["method_change"])
            self.assertIsNone(result["method_change_invalidation"])
            self.assertFalse((Path(temporary) / "paper.md").exists())

    def test_request_words_do_not_select_or_create_permission_modes(self):
        for request in ("review change hash allow", "请审查论文，不改文件", "$stop-that-shit change -- fix"):
            with self.subTest(request=request):
                result = route_prompt(request)
                self.assertIsNone(result["primary_module"])
                self.assertEqual(result["selected_modules"], [])
                self.assertEqual(result["work_discipline"], research_work_discipline())

    def test_prompt_hook_returns_guidance_without_denial_or_project_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = {"hook_event_name": "UserPromptSubmit", "cwd": temporary,
                       "prompt": "Review the writing; keep necessary uncertainty."}
            run = subprocess.run(
                [sys.executable, str(ROOT / "hooks" / "guard_hook.py")],
                input=json.dumps(payload), encoding="utf-8", capture_output=True, check=True,
            )
            result = json.loads(run.stdout)
            context = result["hookSpecificOutput"]["additionalContext"]
            self.assertIn(WORK_DISCIPLINE_CONTEXT, context[:800])
            self.assertNotIn("permissionDecision", result["hookSpecificOutput"])
            self.assertEqual(list(Path(temporary).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
