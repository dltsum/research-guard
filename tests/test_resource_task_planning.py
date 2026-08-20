from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import mcp_server  # noqa: E402
from llm_delegation_core import plan_llm_assistance, submit_llm_assistance  # noqa: E402
from resource_task_planner_core import (  # noqa: E402
    ResourcePlanError,
    inventory_resources,
    plan_resource_tasks,
    record_resource_task,
    resource_task_plan_status,
    verify_resource_task_plan,
)


class ResourceTaskPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def task(task_id: str, **overrides):
        value = {
            "task_id": task_id,
            "summary": f"Bounded stage {task_id}",
            "resource_class": "inline_light",
            "depends_on": [],
            "expected_artifacts": [],
            "completion_semantics": "read_only",
            "network_required": False,
            "gpu_required": False,
            "cpu_threads": 1,
        }
        value.update(overrides)
        return value

    def plan(self, tasks=None, constraints=None, plan_id="plan-1"):
        return plan_resource_tasks(
            self.root, plan_id=plan_id, task_goal="Finish a resource-bounded research workflow.",
            tasks=tasks or [self.task("stage-a")], constraints=constraints,
            selected_by="main_agent",
        )

    def test_round_1_inventory_separates_host_facts_from_plugin_entitlement(self) -> None:
        snapshot = inventory_resources(self.root)
        self.assertEqual(snapshot["memory"]["owned_task_budget_bytes"], 512 * 1024 * 1024)
        self.assertEqual(snapshot["cpu"]["admitted_parallel_tasks"], 1)
        self.assertFalse(snapshot["accelerators"]["policy_allowed"])
        self.assertIsNone(snapshot["accelerators"]["runtime_usable_devices"])
        self.assertEqual(snapshot["network"]["connectivity"], "not_tested")
        rendered = json.dumps(snapshot, ensure_ascii=False)
        self.assertNotIn(str(self.root), rendered)
        self.assertTrue(snapshot["privacy"]["hostname_redacted"])

    def test_round_2_dag_is_topological_but_execution_is_serial(self) -> None:
        tasks = [
            self.task("discover"),
            self.task(
                "analyze", resource_class="managed_standard", depends_on=["discover"],
                expected_artifacts=["checkpoints/analyze.json"], completion_semantics="idempotent",
                estimated_peak_memory_bytes=64 * 1024 * 1024,
            ),
            self.task("report", depends_on=["analyze"]),
        ]
        plan = self.plan(tasks)
        self.assertEqual(plan["dependency_waves"], [["discover"], ["analyze"], ["report"]])
        self.assertEqual(plan["serial_execution_order"], ["discover", "analyze", "report"])
        self.assertEqual(plan["next_ready_task_ids"], ["discover"])
        first = record_resource_task(
            self.root, plan_id="plan-1", task_id="discover", task_status="completed",
        )
        self.assertEqual(first["next_ready_task_ids"], ["analyze"])
        artifact = self.root / "checkpoints" / "analyze.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text('{"status":"PASS"}\n', encoding="utf-8")
        second = record_resource_task(
            self.root, plan_id="plan-1", task_id="analyze", task_status="completed",
            artifacts=["checkpoints/analyze.json"], observation={
                "peak_worker_bytes": 32 * 1024 * 1024,
                "peak_orchestrator_bytes": 16 * 1024 * 1024,
                "peak_owned_bytes": 48 * 1024 * 1024,
            },
        )
        self.assertEqual(second["next_ready_task_ids"], ["report"])

    def test_round_2_cycles_missing_dependencies_and_oversized_profiles_fail_closed(self) -> None:
        with self.assertRaisesRegex(ResourcePlanError, "cycle"):
            self.plan([
                self.task("a", depends_on=["b"]),
                self.task("b", depends_on=["a"]),
            ])
        with self.assertRaisesRegex(ResourcePlanError, "unknown dependencies"):
            self.plan([self.task("a", depends_on=["missing"])])
        blocked = self.plan([
            self.task(
                "large", resource_class="managed_standard",
                estimated_peak_memory_bytes=385 * 1024 * 1024,
            )
        ], plan_id="large-plan")
        self.assertEqual(blocked["status"], "ACTION_REQUIRED")
        self.assertIn("MEMORY_PROFILE_EXCEEDED", {item["code"] for item in blocked["static_issues"]})

    def test_round_3_network_gpu_and_explicit_budget_unknowns_are_visible(self) -> None:
        plan = self.plan([
            self.task("online", network_required=True),
            self.task("gpu", gpu_required=True),
        ], constraints={
            "network_allowed": None,
            "max_download_bytes": 1024,
            "max_disk_write_bytes": 2048,
            "budget_selected_by": "user",
        })
        codes = {item["code"] for item in plan["static_issues"]}
        self.assertTrue({"NETWORK_DECISION_REQUIRED", "DOWNLOAD_ESTIMATE_REQUIRED", "GPU_NOT_ADMITTED", "DISK_ESTIMATE_REQUIRED"} <= codes)
        self.assertEqual(plan["status"], "ACTION_REQUIRED")

    def test_round_3_aggregate_budget_is_checked_only_for_consuming_tasks(self) -> None:
        plan = self.plan([
            self.task("offline", estimated_disk_write_bytes=0),
            self.task(
                "online-a", network_required=True, estimated_download_bytes=600,
                estimated_disk_write_bytes=0,
            ),
            self.task(
                "online-b", network_required=True, estimated_download_bytes=600,
                estimated_disk_write_bytes=0,
            ),
        ], constraints={
            "network_allowed": True,
            "max_download_bytes": 1000,
            "max_disk_write_bytes": 100,
            "budget_selected_by": "user",
        }, plan_id="budget-plan")
        self.assertIn("DOWNLOAD_BUDGET_EXCEEDED", {item["code"] for item in plan["static_issues"]})

    def test_round_3_unknown_completion_requires_receipt_inspection(self) -> None:
        self.plan([
            self.task(
                "remote", resource_class="external_wait", expected_artifacts=["receipts/remote.json"],
                completion_semantics="stateful", network_required=True,
            )
        ], constraints={"network_allowed": True})
        unknown = record_resource_task(
            self.root, plan_id="plan-1", task_id="remote", task_status="unknown",
            note="The transport ended without a final receipt.",
        )
        self.assertEqual(unknown["status"], "RECEIPT_INSPECTION_REQUIRED")
        receipt = self.root / "receipts" / "remote.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{"status":"complete"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ResourcePlanError, "RECEIPT_INSPECTION_REQUIRED"):
            record_resource_task(
                self.root, plan_id="plan-1", task_id="remote", task_status="completed",
                artifacts=["receipts/remote.json"],
            )
        completed = record_resource_task(
            self.root, plan_id="plan-1", task_id="remote", task_status="completed",
            artifacts=["receipts/remote.json"], observation={"receipt_inspected": True},
        )
        self.assertEqual(completed["status"], "COMPLETE")

    def test_round_4_llm_stage_requires_the_existing_delegation_contract(self) -> None:
        task = self.task(
            "review", resource_class="llm_assistance", expected_artifacts=["review.md"],
            completion_semantics="idempotent", delegation_task_id="review-help",
        )
        blocked = self.plan([task], plan_id="llm-blocked")
        self.assertIn("LLM_DELEGATION_PLAN_REQUIRED", {item["code"] for item in blocked["static_issues"]})
        plan_llm_assistance(
            self.root, task_id="review-help", task_type="draft_review",
            task_summary="Review the bounded manuscript stage.", selected_by="main_agent",
            subagent_available=True,
        )
        admitted = self.plan([task], plan_id="llm-ready")
        self.assertEqual(admitted["status"], "READY")
        (self.root / "review.md").write_text("reviewed\n", encoding="utf-8")
        submit_llm_assistance(
            self.root, task_id="review-help", execution_mode="native_subagent",
            artifact_path="review.md", executor_id="subagent-1", model_tier="entry",
            reasoning_effort="low",
        )
        completed = record_resource_task(
            self.root, plan_id="llm-ready", task_id="review", task_status="completed",
            artifacts=["review.md"],
        )
        self.assertEqual(completed["status"], "COMPLETE")

    def test_round_4_artifact_and_state_tampering_are_detected(self) -> None:
        self.plan([
            self.task(
                "save", expected_artifacts=["checkpoint.json"], completion_semantics="idempotent",
            )
        ])
        artifact = self.root / "checkpoint.json"
        artifact.write_text('{"value":1}\n', encoding="utf-8")
        record_resource_task(
            self.root, plan_id="plan-1", task_id="save", task_status="completed",
            artifacts=["checkpoint.json"],
        )
        self.assertEqual(verify_resource_task_plan(self.root, "plan-1")["status"], "PASS")
        artifact.write_text('{"value":2}\n', encoding="utf-8")
        report = verify_resource_task_plan(self.root, "plan-1")
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(item.startswith("ARTIFACT_HASH_MISMATCH") for item in report["errors"]))

    def test_round_5_replanning_preserves_prior_revision_and_mcp_surface(self) -> None:
        first = self.plan(plan_id="replan")
        second = self.plan([self.task("stage-b")], plan_id="replan")
        self.assertEqual(first["revision"], 1)
        self.assertEqual(second["revision"], 2)
        state = json.loads((self.root / ".research-guard" / "resource-task-plans" / "replan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(state["revisions"]), 2)
        self.assertIsNotNone(state["revisions"][0]["superseded_at"])
        self.assertEqual(len(mcp_server.TOOLS), 17)
        design = next(item for item in mcp_server.TOOLS if item["name"] == "research_design")
        self.assertIn("resource_plan_action", design["inputSchema"]["properties"])
        result = mcp_server.dispatch("research_design", {
            "action": "status", "project_root": str(self.root),
            "resource_plan_action": "status", "resource_plan_id": "replan",
        })
        self.assertEqual(result["revision"], 2)
        self.assertEqual(resource_task_plan_status(self.root, "replan")["status"], "READY")

    def test_managed_lean_implicitly_checks_the_registered_lean_component(self) -> None:
        with patch("resource_task_planner_core.component_need", return_value={"status": "USER_DECISION_REQUIRED"}):
            plan = self.plan([
                self.task(
                    "lean", resource_class="managed_lean", expected_artifacts=["proof.json"],
                    completion_semantics="idempotent",
                )
            ], plan_id="lean-plan")
        self.assertIn("DEPENDENCY_DECISION_REQUIRED", {item["code"] for item in plan["static_issues"]})

    def test_install_profile_uses_the_full_budget_without_exceeding_it(self) -> None:
        plan = self.plan([
            self.task(
                "install", resource_class="managed_install",
                estimated_peak_memory_bytes=420 * 1024 * 1024,
                expected_artifacts=["receipts/install.json"], completion_semantics="idempotent",
            )
        ], plan_id="install-plan")
        self.assertEqual(plan["status"], "READY")
        profile = inventory_resources(self.root)["task_profiles"]["managed_install"]
        self.assertEqual(profile["worker_limit_bytes"], 448 * 1024 * 1024)
        self.assertEqual(profile["orchestrator_limit_bytes"], 64 * 1024 * 1024)
        self.assertEqual(
            profile["worker_limit_bytes"] + profile["orchestrator_limit_bytes"],
            512 * 1024 * 1024,
        )


if __name__ == "__main__":
    unittest.main()
