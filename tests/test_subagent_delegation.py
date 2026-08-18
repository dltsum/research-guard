from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402
from llm_delegation_core import (  # noqa: E402
    LLMDelegationError,
    plan_llm_assistance,
    submit_llm_assistance,
    verify_llm_assistance,
)


class SubagentDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        (self.root / "result.md").write_text("bounded result\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _plan(self, **overrides):
        values = {
            "task_id": "draft-review-1",
            "task_type": "draft_review",
            "task_summary": "Review the draft with bounded evidence.",
            "selected_by": "main_agent",
            "subagent_available": True,
        }
        values.update(overrides)
        return plan_llm_assistance(self.root, **values)

    def test_round_1_default_is_one_low_entry_subagent_and_no_api(self) -> None:
        plan = self._plan()
        self.assertEqual(plan["status"], "SUBAGENT_REQUIRED")
        self.assertEqual(plan["execution_mode"], "native_subagent")
        self.assertEqual(plan["contract"]["subagent_count"], 1)
        self.assertEqual(plan["contract"]["reasoning_effort"], "low")
        self.assertEqual(plan["contract"]["model_tier"], "entry_or_lowest_capable")
        self.assertFalse(plan["contract"]["external_api_allowed"])
        receipt = submit_llm_assistance(
            self.root, task_id="draft-review-1", execution_mode="native_subagent",
            artifact_path="result.md", executor_id="subagent-1", model_tier="entry",
            reasoning_effort="low",
        )
        self.assertEqual(receipt["independence_status"], "NOT_CROSS_PROVIDER")
        self.assertEqual(verify_llm_assistance(self.root)["status"], "PASS")

    def test_round_2_no_subagent_falls_back_locally_not_to_api(self) -> None:
        plan = self._plan(subagent_available=False)
        self.assertEqual(plan["status"], "LOCAL_FALLBACK_REQUIRED")
        self.assertEqual(plan["execution_mode"], "main_agent_local")
        receipt = submit_llm_assistance(
            self.root, task_id="draft-review-1", execution_mode="main_agent_local",
            artifact_path="result.md", executor_id="main-agent",
        )
        self.assertEqual(receipt["independence_status"], "NOT_INDEPENDENT_REVIEW")
        self.assertEqual(verify_llm_assistance(self.root)["status"], "PASS")

    def test_round_3_external_api_requires_explicit_user_selection(self) -> None:
        plan = self._plan(
            external_requirement="user_requested_provider", requested_provider="named-provider",
            external_rationale="The user requested this exact external provider.",
        )
        self.assertEqual(plan["status"], "EXTERNAL_API_USER_DECISION_REQUIRED")
        with self.assertRaisesRegex(LLMDelegationError, "does not match|USER_DECISION_REQUIRED"):
            submit_llm_assistance(
                self.root, task_id="draft-review-1", execution_mode="external_api_exception",
                artifact_path="result.md", executor_id="api-call", provider_model_id="provider/model",
            )

    def test_round_4_user_authorized_external_exception_is_hash_bound(self) -> None:
        plan = self._plan(
            external_requirement="cross_provider_protocol", requested_provider="independent-provider",
            external_selected_by="user",
            external_rationale="The registered protocol needs a distinct provider identity.",
        )
        self.assertEqual(plan["status"], "EXTERNAL_API_AUTHORIZED")
        receipt = submit_llm_assistance(
            self.root, task_id="draft-review-1", execution_mode="external_api_exception",
            artifact_path="result.md", executor_id="external-run-1", provider_model_id="provider/model-v1",
        )
        self.assertEqual(receipt["independence_status"], "DECLARED_EXTERNAL_PROVIDER")
        (self.root / "result.md").write_text("changed\n", encoding="utf-8")
        self.assertEqual(verify_llm_assistance(self.root)["status"], "FAIL")

    def test_round_5_high_reasoning_and_unsafe_artifacts_are_rejected(self) -> None:
        self._plan()
        with self.assertRaisesRegex(LLMDelegationError, "cannot exceed medium"):
            submit_llm_assistance(
                self.root, task_id="draft-review-1", execution_mode="native_subagent",
                artifact_path="result.md", executor_id="subagent-1", model_tier="entry",
                reasoning_effort="high",
            )
        with self.assertRaisesRegex(LLMDelegationError, "Medium reasoning requires"):
            submit_llm_assistance(
                self.root, task_id="draft-review-1", execution_mode="native_subagent",
                artifact_path="result.md", executor_id="subagent-1", model_tier="entry",
                reasoning_effort="medium",
            )
        outside = self.root.parent / "outside-delegation-result.md"
        outside.write_text("outside\n", encoding="utf-8")
        try:
            with self.assertRaisesRegex(LLMDelegationError, "inside project_root"):
                submit_llm_assistance(
                    self.root, task_id="draft-review-1", execution_mode="native_subagent",
                    artifact_path=str(outside), executor_id="subagent-1", model_tier="entry",
                    reasoning_effort="low",
                )
        finally:
            outside.unlink(missing_ok=True)

    def test_mcp_subroute_preserves_seventeen_top_level_tools(self) -> None:
        self.assertEqual(len(mcp_server.TOOLS), 17)
        tool = next(item for item in mcp_server.TOOLS if item["name"] == "research_design")
        props = tool["inputSchema"]["properties"]
        self.assertIn("delegation_action", props)
        result = mcp_server.dispatch("research_design", {
            "action": "status", "project_root": str(self.root), "delegation_action": "plan",
            "delegation_task_id": "lit-1", "delegation_task_type": "literature_synthesis",
            "delegation_task_summary": "Synthesize a bounded literature set.",
            "delegation_selected_by": "main_agent", "subagent_available": True,
        })
        self.assertEqual(result["execution_mode"], "native_subagent")
        state = json.loads((self.root / ".research-guard" / "llm-assistance-delegation.json").read_text(encoding="utf-8"))
        self.assertIn("lit-1", state["tasks"])


if __name__ == "__main__":
    unittest.main()
