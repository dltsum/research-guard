from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dependency_manager  # noqa: E402
import mcp_server  # noqa: E402
from instruction_adherence_core import (  # noqa: E402
    InstructionAdherenceError,
    instruction_adherence_status,
    record_instruction_requirement,
    register_instruction_contract,
    verify_instruction_contract,
    waive_instruction_requirement,
)


def requirements() -> list[dict]:
    return [
        {
            "id": "implement",
            "text": "Implement the requested executable feature.",
            "kind": "deliverable",
            "mandatory": True,
            "acceptance_criteria": ["A project-local implementation artifact exists."],
            "required_evidence_kinds": ["file"],
            "forbidden_substitutions": ["Do not replace executable code with prompt text."],
            "depends_on": [],
        },
        {
            "id": "verify",
            "text": "Run the focused correctness regression.",
            "kind": "verification",
            "mandatory": True,
            "acceptance_criteria": ["The registered JSON test receipt reports PASS."],
            "required_evidence_kinds": ["json_receipt", "manual_review"],
            "forbidden_substitutions": ["Do not treat a zero exit code alone as scientific proof."],
            "depends_on": ["implement"],
        },
    ]


class InstructionAdherenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.old_home = os.environ.get("RESEARCH_GUARD_HOME")
        os.environ["RESEARCH_GUARD_HOME"] = str(self.root / "dependency-home")
        dependency_manager.decide([], [])
        (self.root / "implementation.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "test-receipt.json").write_text(
            json.dumps({"result": {"status": "PASS"}}) + "\n", encoding="utf-8",
        )

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = self.old_home
        self.temporary.cleanup()

    def register(self, identifier: str = "task-1") -> dict:
        return register_instruction_contract(
            self.root,
            contract_id=identifier,
            request_text="Implement two executable requirements and prove both.",
            scope="This multistep project change and its focused regression.",
            requirements=requirements(),
            selected_by="main_agent",
            selection_rationale="The main agent decomposed the complete user request into two atomic deliverables.",
        )

    def record_implementation(self, identifier: str = "task-1") -> dict:
        return record_instruction_requirement(
            self.root,
            contract_id=identifier,
            requirement_id="implement",
            outcome="satisfied",
            evidence=[{"kind": "file", "path": "implementation.py"}],
            note="The executable implementation artifact now exists.",
            blocker_code=None,
            selected_by="main_agent",
        )

    def record_verification(self, identifier: str = "task-1") -> dict:
        return record_instruction_requirement(
            self.root,
            contract_id=identifier,
            requirement_id="verify",
            outcome="satisfied",
            evidence=[
                {
                    "kind": "json_receipt",
                    "path": "test-receipt.json",
                    "status_path": "result.status",
                    "expected": "PASS",
                },
                {
                    "kind": "manual_review",
                    "reviewer": "main-agent",
                    "status": "PASS",
                    "checklist": ["Data flow and acceptance intent were reviewed."],
                },
            ],
            note="The focused regression and its data-flow intent both passed.",
            blocker_code=None,
            selected_by="main_agent",
        )

    def hook(self, payload: dict) -> dict:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "hooks" / "guard_hook.py")],
            input=json.dumps(payload), text=True, capture_output=True, cwd=self.root,
            env={**os.environ, "PYTHONUTF8": "1"}, timeout=20,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout) if completed.stdout.strip() else {}

    def test_round_1_pending_contract_blocks_stop_and_completion(self) -> None:
        status = self.register()
        self.assertEqual(status["status"], "ACTION_REQUIRED")
        self.assertFalse(status["stop_allowed"])
        stopped = self.hook({"hook_event_name": "Stop", "cwd": str(self.root), "stop_hook_active": False})
        self.assertEqual(stopped["decision"], "block")
        self.assertIn("task-1=ACTION_REQUIRED", stopped["reason"])

    def test_round_2_dependencies_and_evidence_are_enforced(self) -> None:
        self.register()
        with self.assertRaisesRegex(InstructionAdherenceError, "dependencies are incomplete"):
            self.record_verification()
        self.record_implementation()
        (self.root / "implementation.py").write_text("VALUE = 2\n", encoding="utf-8")
        with self.assertRaisesRegex(InstructionAdherenceError, "dependencies are incomplete"):
            self.record_verification()
        renewed = self.record_implementation()
        self.assertEqual(renewed["contracts"][0]["requirements"][0]["state"], "satisfied")
        with self.assertRaisesRegex(InstructionAdherenceError, "Required evidence kinds are missing"):
            record_instruction_requirement(
                self.root,
                contract_id="task-1",
                requirement_id="verify",
                outcome="satisfied",
                evidence=[{"kind": "file", "path": "test-receipt.json"}],
                note="A weaker artifact was supplied instead of the required receipt.",
                blocker_code=None,
                selected_by="main_agent",
            )
        self.record_verification()
        result = verify_instruction_contract(self.root, "task-1")
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["completion_claim_allowed"])
        self.assertRegex(result["receipts"][0]["receipt_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.hook({"hook_event_name": "Stop", "cwd": str(self.root)}), {})

    def test_round_3_changed_evidence_invalidates_pass_and_stop(self) -> None:
        self.register()
        self.record_implementation()
        self.record_verification()
        self.assertEqual(verify_instruction_contract(self.root)["status"], "PASS")
        (self.root / "implementation.py").write_text("VALUE = 2\n", encoding="utf-8")
        status = instruction_adherence_status(self.root)
        self.assertEqual(status["status"], "ACTION_REQUIRED")
        implementation = status["contracts"][0]["requirements"][0]
        self.assertEqual(implementation["state"], "evidence_invalid")
        self.assertFalse(status["stop_allowed"])
        repaired = self.record_implementation()
        self.assertEqual(repaired["status"], "PASS")
        self.assertEqual(verify_instruction_contract(self.root)["status"], "PASS")

    def test_round_4_user_waiver_and_blocked_handoff_are_not_completion(self) -> None:
        self.register()
        self.record_implementation()
        with self.assertRaisesRegex(InstructionAdherenceError, "selected_by=user"):
            waive_instruction_requirement(
                self.root,
                contract_id="task-1",
                requirement_id="verify",
                rationale="The user explicitly removed this verification requirement.",
                user_message_sha256=hashlib.sha256(b"waive verify").hexdigest(),
                selected_by="main_agent",
            )
        waived = waive_instruction_requirement(
            self.root,
            contract_id="task-1",
            requirement_id="verify",
            rationale="The user explicitly removed this verification requirement.",
            user_message_sha256=hashlib.sha256(b"waive verify").hexdigest(),
            selected_by="user",
        )
        self.assertEqual(waived["status"], "PASS")

        self.register("blocked-task")
        record_instruction_requirement(
            self.root,
            contract_id="blocked-task",
            requirement_id="implement",
            outcome="blocked",
            evidence=[],
            note="The required external authority is unavailable after all safe in-scope checks.",
            blocker_code="EXTERNAL_AUTHORITY_REQUIRED",
            selected_by="main_agent",
        )
        record_instruction_requirement(
            self.root,
            contract_id="blocked-task",
            requirement_id="verify",
            outcome="blocked",
            evidence=[],
            note="Verification cannot start because the prerequisite implementation remains blocked.",
            blocker_code="PREREQUISITE_BLOCKED",
            selected_by="main_agent",
        )
        blocked = instruction_adherence_status(self.root, "blocked-task")
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertTrue(blocked["stop_allowed"])
        self.assertFalse(blocked["completion_claim_allowed"])
        self.assertIsNone(verify_instruction_contract(self.root, "blocked-task")["receipt"])

    def test_round_5_mcp_route_and_integrity_checks_preserve_surface(self) -> None:
        self.assertEqual(len(mcp_server.TOOLS), 17)
        design = next(item for item in mcp_server.TOOLS if item["name"] == "research_design")
        self.assertIn("instruction_action", design["inputSchema"]["properties"])
        result = mcp_server.dispatch("research_design", {
            "action": "status",
            "project_root": str(self.root),
            "instruction_action": "register",
            "instruction_contract_id": "mcp-task",
            "instruction_request_text": "Build and verify the executable feature.",
            "instruction_scope": "The complete MCP-routed feature implementation.",
            "instruction_requirements": requirements(),
            "instruction_selected_by": "main_agent",
            "instruction_selection_rationale": "The main agent preserved every atomic user requirement before mutation.",
        })
        self.assertEqual(result["status"], "ACTION_REQUIRED")
        path = self.root / ".research-guard" / "instruction-adherence.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["contracts"]["mcp-task"]["contract"]["scope"] = "tampered"
        path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(InstructionAdherenceError, "INTEGRITY_FAILURE"):
            instruction_adherence_status(self.root)


if __name__ == "__main__":
    unittest.main()
