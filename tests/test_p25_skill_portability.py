from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import mcp_server  # noqa: E402
from frontier_skill_research_core import (  # noqa: E402
    finalize_frontier_skill_research,
    plan_frontier_skill_research,
    record_frontier_skill_source,
    record_frontier_skill_trial,
    register_frontier_skill_hypothesis,
)
from skill_portability_core import (  # noqa: E402
    SkillPortabilityError,
    finalize_skill_portability,
    plan_skill_portability,
    record_skill_portability_source,
    record_skill_portability_trial,
    skill_portability_status,
    verify_skill_portability,
)


class SkillPortabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.candidate_hash = "b" * 64
        self.candidate_commit = "c5ee10f6b566cd2ccf96f7cef115eba59606b01b"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _sha(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _frontier_trial(self, protocol_id: str, split: str, round_number: int) -> Path:
        directory = self.root / "frontier-trials"
        directory.mkdir(exist_ok=True)
        path = directory / f"{split}-{round_number}.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "protocol_id": protocol_id,
            "hypothesis_id": "target-evaluation",
            "split": split,
            "round": round_number,
            "run_id": f"frontier-{split}-{round_number}",
            "case_ids": [f"{split}-1", f"{split}-2"],
            "baseline_artifact_sha256": "a" * 64,
            "candidate_artifact_sha256": self.candidate_hash,
            "metrics": {
                "utility": {"baseline": 0.5, "candidate": 0.7},
                "unsafe_rate": {"baseline": 0.1, "candidate": 0.1},
            },
            "producer": "deterministic P25 frontier fixture",
        }), encoding="utf-8")
        return path

    def _frontier(self, protocol_id: str = "frontier-for-portability-v1") -> dict[str, str]:
        plan_frontier_skill_research(
            self.root,
            protocol_id=protocol_id,
            protocol={
                "research_question": "Does the candidate improve its frozen source target before portability testing?",
                "target_agent": "source target agent",
                "target_harness": "source target harness",
                "baseline_artifact_sha256": "a" * 64,
                "candidate_identity": {
                    "skill_id": "skilllens-candidate",
                    "repository": "microsoft/SkillLens",
                    "commit": self.candidate_commit,
                },
                "splits": {
                    "train": ["train-1", "train-2"],
                    "validation": ["validation-1", "validation-2"],
                    "heldout": ["heldout-1", "heldout-2"],
                },
                "metrics": [
                    {"name": "utility", "direction": "maximize", "kind": "utility", "tolerance": 0.0},
                    {"name": "unsafe_rate", "direction": "minimize", "kind": "safety", "tolerance": 0.0},
                ],
                "validation_rounds": 2,
            },
            selected_by="main_agent",
            selection_rationale="The main agent selected an exact source target and immutable candidate for portability testing.",
        )
        record_frontier_skill_source(self.root, protocol_id=protocol_id, source={
            "source_id": "skilllens-paper",
            "source_type": "primary_paper",
            "title": "From Raw Experience to Skill Consumption",
            "url": "https://arxiv.org/abs/2605.23899",
            "immutable_id": "2605.23899v1",
            "mechanism": "Separates Skill extraction from target-agent consumption and transfer behavior.",
            "limitations": "One target cell does not establish transfer to another model or harness.",
        })
        record_frontier_skill_source(self.root, protocol_id=protocol_id, source={
            "source_id": "skilllens-code",
            "source_type": "repository",
            "title": "SkillLens repository",
            "url": "https://github.com/microsoft/SkillLens",
            "immutable_id": self.candidate_commit,
            "mechanism": "Provides the exact inspectable candidate implementation identity.",
            "limitations": "The repository is source evidence and is not executed by this fixture.",
        })
        register_frontier_skill_hypothesis(self.root, protocol_id=protocol_id, hypothesis={
            "hypothesis_id": "target-evaluation",
            "statement": "The candidate improves its exact source target without a safety regression.",
            "mechanism": "Paired validation and heldout metrics bind the retained candidate artifact.",
            "expected_effect": "Utility improves and safety remains non-regressive.",
            "failure_condition": "Utility fails to improve or safety regresses.",
            "canonical_owner": "domain-skill",
            "overlap_decision": "fuse_narrow_adapter",
            "source_ids": ["skilllens-paper", "skilllens-code"],
        })
        for round_number in (1, 2):
            record_frontier_skill_trial(
                self.root, protocol_id=protocol_id,
                trial_path=str(self._frontier_trial(protocol_id, "validation", round_number)),
            )
        record_frontier_skill_trial(
            self.root, protocol_id=protocol_id,
            trial_path=str(self._frontier_trial(protocol_id, "heldout", 1)),
        )
        finalize_frontier_skill_research(self.root, protocol_id=protocol_id)
        return {
            "artifact_sha256": self.candidate_hash,
            "skill_id": "skilllens-candidate",
            "repository": "microsoft/SkillLens",
            "commit": self.candidate_commit,
            "canonical_owner": "domain-skill",
            "overlap_decision": "fuse_narrow_adapter",
        }

    def _cells(self, *, same_evidence_family: bool = False) -> list[dict[str, object]]:
        second_family = "shared-family" if same_evidence_family else "claude-independent"
        return [
            {
                "cell_id": "codex-cell",
                "agent_id": "codex-entry",
                "model_family": "gpt-5",
                "model_version": "gpt-5.5",
                "harness": "codex-cli",
                "harness_version": "2026-08",
                "task_scope": "transfer-benchmark-a",
                "executor_group": "host-a",
                "evidence_family": "shared-family" if same_evidence_family else "codex-independent",
                "case_ids": ["transfer-a-1", "transfer-a-2"],
            },
            {
                "cell_id": "claude-cell",
                "agent_id": "claude-entry",
                "model_family": "claude-4",
                "model_version": "claude-4.5",
                "harness": "claude-code",
                "harness_version": "2026-08",
                "task_scope": "transfer-benchmark-b",
                "executor_group": "host-b",
                "evidence_family": second_family,
                "case_ids": ["transfer-b-1", "transfer-b-2"],
            },
        ]

    def _plan(
        self,
        portability_id: str = "portability-v1",
        *,
        cells: list[dict[str, object]] | None = None,
        binding: dict[str, str] | None = None,
        replicates: int = 2,
    ) -> str:
        binding = binding or self._frontier()
        plan_skill_portability(
            self.root,
            portability_id=portability_id,
            protocol={
                "research_question": "Where does the retained Skill transfer without utility or safety regression?",
                "frontier_protocol_id": "frontier-for-portability-v1",
                "source_binding": binding,
                "replicates": replicates,
                "cells": cells or self._cells(),
            },
            selected_by="main_agent",
            selection_rationale="The main agent selected explicit target cells to test a scoped portability claim without universal extrapolation.",
        )
        return portability_id

    def _sources(self, portability_id: str) -> None:
        record_skill_portability_source(self.root, portability_id=portability_id, source={
            "source_id": "skilllens-transfer-paper",
            "source_type": "primary_paper",
            "title": "From Raw Experience to Skill Consumption",
            "url": "https://arxiv.org/abs/2605.23899",
            "immutable_id": "2605.23899v1",
            "mechanism": "Requires evaluation on the actual consuming target because transfer can be negative.",
            "limitations": "Measured target cells do not justify universal transfer claims.",
        })
        record_skill_portability_source(self.root, portability_id=portability_id, source={
            "source_id": "skillopt-transfer-code",
            "source_type": "repository",
            "title": "SkillOpt exact transfer implementation",
            "url": "https://github.com/microsoft/SkillOpt",
            "immutable_id": "bdfdc30a8e17309c06cdbe8449f01bdecc120203",
            "mechanism": "Evaluates a frozen Skill artifact across source and target model or harness cells.",
            "limitations": "Its reported cells are examples, not evidence for untested agents or tasks.",
        })

    def _trial(
        self,
        portability_id: str,
        cell_id: str,
        replicate: int,
        *,
        utility: float = 0.7,
        unsafe_rate: float = 0.1,
        run_id: str | None = None,
    ) -> Path:
        cells = {item["cell_id"]: item for item in self._cells()}
        directory = self.root / "portability-trials"
        directory.mkdir(exist_ok=True)
        path = directory / f"{cell_id}-{replicate}.json"
        key = f"{cell_id}-{replicate}"
        path.write_text(json.dumps({
            "schema_version": 1,
            "portability_id": portability_id,
            "cell_id": cell_id,
            "replicate": replicate,
            "run_id": run_id or f"transfer-{key}",
            "case_ids": cells[cell_id]["case_ids"],
            "frontier_protocol_id": "frontier-for-portability-v1",
            "candidate_artifact_sha256": self.candidate_hash,
            "baseline_run_sha256": self._sha(f"baseline-{key}"),
            "candidate_run_sha256": self._sha(f"candidate-{key}"),
            "execution_receipt_sha256": self._sha(f"receipt-{key}"),
            "metrics": {
                "utility": {"baseline": 0.5, "candidate": utility},
                "unsafe_rate": {"baseline": 0.1, "candidate": unsafe_rate},
            },
            "producer": "deterministic P25 portability fixture",
        }), encoding="utf-8")
        return path

    def _complete(
        self,
        portability_id: str = "portability-v1",
        *,
        second_utility: float = 0.7,
        second_unsafe_rate: float = 0.1,
        same_evidence_family: bool = False,
    ) -> str:
        self._plan(portability_id, cells=self._cells(same_evidence_family=same_evidence_family))
        self._sources(portability_id)
        for cell_id in ("codex-cell", "claude-cell"):
            for replicate in (1, 2):
                result = record_skill_portability_trial(
                    self.root,
                    portability_id=portability_id,
                    trial_path=str(self._trial(
                        portability_id,
                        cell_id,
                        replicate,
                        utility=second_utility if cell_id == "claude-cell" else 0.7,
                        unsafe_rate=second_unsafe_rate if cell_id == "claude-cell" else 0.1,
                    )),
                )
                self.assertEqual(result["status"], "RECORDED_NOT_EXPOSED")
                self.assertNotIn("classification", result)
                self.assertNotIn("metrics", result)
        return portability_id

    def test_positive_portability_is_scoped_and_never_universal(self) -> None:
        portability_id = self._complete()
        before = skill_portability_status(self.root, portability_id)
        self.assertTrue(all(item["status"] == "RECORDED_NOT_EXPOSED" for item in before["trials"]))
        final = finalize_skill_portability(self.root, portability_id=portability_id)
        self.assertEqual(final["status"], "HUMAN_REVIEW_REQUIRED")
        self.assertTrue(final["finalization"]["scoped_claim_allowed"])
        self.assertFalse(final["finalization"]["universal_claim_allowed"])
        self.assertEqual(final["finalization"]["support_status"], "SUPPORTED_ON_RECORDED_CELLS")
        self.assertEqual({item["classification"] for item in final["finalization"]["cells"]}, {"POSITIVE_TRANSFER"})
        self.assertEqual(
            {item["executor_group"] for item in final["finalization"]["cells"]},
            {"host-a", "host-b"},
        )
        self.assertTrue(final["finalization"]["independent_corroboration"])
        self.assertEqual(verify_skill_portability(self.root, portability_id)["status"], "PASS")

    def test_three_replicates_complete_in_frozen_order(self) -> None:
        portability_id = self._plan("three-replicates-v1", replicates=3)
        self._sources(portability_id)
        for cell_id in ("codex-cell", "claude-cell"):
            for replicate in (1, 2, 3):
                record_skill_portability_trial(
                    self.root,
                    portability_id=portability_id,
                    trial_path=str(self._trial(portability_id, cell_id, replicate)),
                )
        final = finalize_skill_portability(self.root, portability_id=portability_id)["finalization"]
        self.assertEqual(final["support_status"], "SUPPORTED_ON_RECORDED_CELLS")
        self.assertTrue(all(len(cell["replicates"]) == 3 for cell in final["cells"]))

    def test_negative_transfer_is_preserved_and_not_averaged_away(self) -> None:
        portability_id = self._complete("negative-v1", second_utility=0.4)
        final = finalize_skill_portability(self.root, portability_id=portability_id)["finalization"]
        outcomes = {item["cell_id"]: item["classification"] for item in final["cells"]}
        self.assertEqual(outcomes["codex-cell"], "POSITIVE_TRANSFER")
        self.assertEqual(outcomes["claude-cell"], "NEGATIVE_TRANSFER")
        self.assertEqual(final["support_status"], "PARTIAL_OR_NOT_SUPPORTED")
        self.assertFalse(final["scoped_claim_allowed"])
        self.assertFalse(final["independent_corroboration"])
        self.assertNotIn("aggregate_mean", final)

    def test_no_measured_gain_does_not_become_portability_support(self) -> None:
        portability_id = self._plan("no-gain-v1")
        self._sources(portability_id)
        for cell_id in ("codex-cell", "claude-cell"):
            for replicate in (1, 2):
                record_skill_portability_trial(
                    self.root,
                    portability_id=portability_id,
                    trial_path=str(self._trial(portability_id, cell_id, replicate, utility=0.5)),
                )
        final = finalize_skill_portability(self.root, portability_id=portability_id)["finalization"]
        self.assertEqual(final["support_status"], "NOT_DEMONSTRATED")
        self.assertEqual({item["classification"] for item in final["cells"]}, {"NO_MEASURED_GAIN"})
        self.assertFalse(final["scoped_claim_allowed"])
        self.assertFalse(final["independent_corroboration"])

    def test_safety_regression_dominates_the_claim_boundary(self) -> None:
        portability_id = self._complete("safety-v1", second_unsafe_rate=0.2)
        final = finalize_skill_portability(self.root, portability_id=portability_id)["finalization"]
        self.assertEqual(final["support_status"], "NOT_SUPPORTED_SAFETY_REGRESSION")
        self.assertFalse(final["scoped_claim_allowed"])
        self.assertIn("SAFETY_REGRESSION", {item["classification"] for item in final["cells"]})

    def test_same_model_or_executor_cannot_masquerade_as_independent(self) -> None:
        binding = self._frontier()
        cells = self._cells()
        cells[1]["model_family"] = cells[0]["model_family"]
        cells[1]["evidence_family"] = "falsely-independent"
        with self.assertRaisesRegex(SkillPortabilityError, "evidence family"):
            self._plan("false-independence-v1", cells=cells, binding=binding)

        portability_id = "same-family-v1"
        self._plan(portability_id, cells=self._cells(same_evidence_family=True), binding=binding)
        self._sources(portability_id)
        for cell_id in ("codex-cell", "claude-cell"):
            for replicate in (1, 2):
                record_skill_portability_trial(
                    self.root, portability_id=portability_id,
                    trial_path=str(self._trial(portability_id, cell_id, replicate)),
                )
        final = finalize_skill_portability(self.root, portability_id=portability_id)["finalization"]
        self.assertFalse(final["independent_corroboration"])

    def test_transfer_cases_must_not_reuse_p24_splits(self) -> None:
        binding = self._frontier()
        cells = self._cells()
        cells[0]["case_ids"] = ["heldout-1", "new-case"]
        with self.assertRaisesRegex(SkillPortabilityError, "source protocol"):
            self._plan("leakage-v1", cells=cells, binding=binding)

    def test_matrix_requires_real_variation_and_exact_p24_binding(self) -> None:
        binding = self._frontier()
        cells = self._cells()
        for field in ("model_family", "model_version", "harness", "harness_version", "task_scope"):
            cells[1][field] = cells[0][field]
        with self.assertRaisesRegex(SkillPortabilityError, "vary"):
            self._plan("no-variation-v1", cells=cells, binding=binding)

        wrong = dict(binding)
        wrong["artifact_sha256"] = "d" * 64
        with self.assertRaisesRegex(SkillPortabilityError, "frontier"):
            self._plan("wrong-binding-v1", binding=wrong)

    def test_replicates_are_ordered_and_run_ids_are_unique(self) -> None:
        portability_id = self._plan("ordered-v1")
        self._sources(portability_id)
        with self.assertRaisesRegex(SkillPortabilityError, "replicate order"):
            record_skill_portability_trial(
                self.root, portability_id=portability_id,
                trial_path=str(self._trial(portability_id, "codex-cell", 2)),
            )
        record_skill_portability_trial(
            self.root, portability_id=portability_id,
            trial_path=str(self._trial(portability_id, "codex-cell", 1, run_id="unique-transfer-run")),
        )
        with self.assertRaisesRegex(SkillPortabilityError, "run_id"):
            record_skill_portability_trial(
                self.root, portability_id=portability_id,
                trial_path=str(self._trial(portability_id, "claude-cell", 1, run_id="unique-transfer-run")),
            )
        replayed_receipt = self._trial(
            portability_id, "claude-cell", 1, run_id="new-transfer-run",
        )
        replayed_document = json.loads(replayed_receipt.read_text(encoding="utf-8"))
        replayed_document["execution_receipt_sha256"] = self._sha("receipt-codex-cell-1")
        replayed_receipt.write_text(json.dumps(replayed_document), encoding="utf-8")
        with self.assertRaisesRegex(SkillPortabilityError, "execution receipt"):
            record_skill_portability_trial(
                self.root, portability_id=portability_id, trial_path=str(replayed_receipt),
            )

    def test_missing_cell_blocks_finalization(self) -> None:
        portability_id = self._plan("missing-v1")
        self._sources(portability_id)
        for replicate in (1, 2):
            record_skill_portability_trial(
                self.root, portability_id=portability_id,
                trial_path=str(self._trial(portability_id, "codex-cell", replicate)),
            )
        with self.assertRaisesRegex(SkillPortabilityError, "complete matrix"):
            finalize_skill_portability(self.root, portability_id=portability_id)

    def test_trial_and_state_tampering_are_detected(self) -> None:
        portability_id = self._complete("tamper-v1")
        status = skill_portability_status(self.root, portability_id)
        artifact = self.root / status["trials"][0]["artifact_path"]
        artifact.write_text("{}", encoding="utf-8")
        self.assertEqual(verify_skill_portability(self.root, portability_id)["status"], "FAIL")

        state_path = self.root / ".research-guard" / "domain-skills" / "frontier-portability" / portability_id / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["protocol"]["research_question"] = "tampered"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(SkillPortabilityError):
            skill_portability_status(self.root, portability_id)

    def test_mcp_reuses_research_design_and_preserves_seventeen_tools(self) -> None:
        self.assertEqual(len(mcp_server.TOOLS), 17)
        design = next(item for item in mcp_server.TOOLS if item["name"] == "research_design")
        properties = design["inputSchema"]["properties"]
        self.assertIn("skill_portability_action", properties)
        self.assertEqual(
            properties["skill_portability_action"]["enum"],
            ["plan", "record_source", "record_trial", "finalize", "status", "verify"],
        )
        binding = self._frontier()
        routed = mcp_server.dispatch("research_design", {
            "action": "status",
            "project_root": str(self.root),
            "skill_portability_action": "plan",
            "skill_portability_id": "mcp-portability-v1",
            "skill_portability_protocol": {
                "research_question": "Does MCP preserve the exact target-cell portability boundary?",
                "frontier_protocol_id": "frontier-for-portability-v1",
                "source_binding": binding,
                "replicates": 2,
                "cells": self._cells(),
            },
            "skill_portability_selected_by": "main_agent",
            "skill_portability_selection_rationale": (
                "The main agent selected explicit cells to verify the existing research-design dispatch path."
            ),
        })
        self.assertEqual(routed["status"], "ACTION_REQUIRED")
        self.assertFalse(routed["execution_allowed_by_core"])


if __name__ == "__main__":
    unittest.main()
