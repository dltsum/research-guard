from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from p7_fixtures import candidate, commit, plan_strategy, strategy


class P7CycleEIntegrityHeldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        commit(self.root)
        self.plan = plan_strategy(self.root)

    def tearDown(self):
        self.temp.cleanup()

    @property
    def state_path(self) -> Path:
        return self.root / ".research-guard" / "research-design.json"

    def register(self):
        from research_design_core import register_strategy

        return register_strategy(self.root, strategy_plan_hash=self.plan["strategy_plan_hash"], strategy=strategy())

    def test_plan_tampering_is_detected(self):
        from research_design_core import DesignError, get_research_design_status

        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["strategy_plan"]["selected_module_ids"][0] = "tampered"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(DesignError, "strategy plan hash"):
            get_research_design_status(self.root)

    def test_contract_tampering_is_detected(self):
        from research_design_core import DesignError, get_research_design_status

        self.register()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["strategy"]["strategy"]["objective"]["success_definition"] = "tampered"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(DesignError, "strategy hash"):
            get_research_design_status(self.root)

    def test_branch_decision_tampering_is_detected(self):
        from research_design_core import DesignError, decide_strategy_branch, get_research_design_status

        self.register()
        decide_strategy_branch(
            self.root, decision_id="D1", branch_id="B_continue", selected_by="user",
            rationale="The user reviewed the frozen evidence and chose the non-changing branch.",
        )
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["strategy_decisions"][0]["selected_by"] = "assistant"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(DesignError, "strategy decision"):
            get_research_design_status(self.root)

    def test_direct_method_change_makes_strategy_stale(self):
        from research_design_core import get_research_design_status
        from research_guard_core import register_method

        self.register()
        changed = {key: candidate()[key] for key in ("title", "problem", "mechanism")}
        changed["mechanism"] = "A new detector gates a sparse update under a changed schedule."
        register_method(self.root, changed)
        status = get_research_design_status(self.root)
        self.assertEqual(status["status"], "STALE_METHOD")
        self.assertFalse(status["ready"])

    def test_hook_routes_strategy_requests_without_copying_prompt_bundle(self):
        hook = (Path(__file__).resolve().parents[1] / "hooks" / "guard_hook.py").read_text(encoding="utf-8")
        self.assertIn("STRATEGY_TERMS", hook)
        self.assertIn("plan_strategy", hook)
        self.assertNotIn("Fischbach", hook)

    def test_hook_actual_prompt_emits_strategy_contract_and_collision_warning(self):
        hook = Path(__file__).resolve().parents[1] / "hooks" / "guard_hook.py"
        payload = {
            "hook_event_name": "UserPromptSubmit", "cwd": str(self.root),
            "prompt": "项目卡住了，请做风险评估和问题反转，并调整方法",
        }
        proc = subprocess.run(
            [sys.executable, str(hook)], input=json.dumps(payload, ensure_ascii=True),
            text=True, capture_output=True, encoding="utf-8", check=True,
        )
        output = json.loads(proc.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("plan_strategy", context)
        self.assertIn("rerun the novelty search", context)
        self.assertIn("method adjustment detected", context.lower())


if __name__ == "__main__":
    unittest.main()
