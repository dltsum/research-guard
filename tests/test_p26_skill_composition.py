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
from skill_composition_core import (  # noqa: E402
    SkillCompositionError,
    finalize_skill_composition,
    plan_skill_composition,
    record_skill_composition_source,
    record_skill_composition_trial,
    skill_composition_status,
    verify_skill_composition,
)


class SkillCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bindings = {
            "skill-a": self._frontier("skill-a", "frontier-a-v1", "b", "c"),
            "skill-b": self._frontier("skill-b", "frontier-b-v1", "d", "e"),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _sha(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _frontier_trial(
        self, protocol_id: str, candidate_hash: str, split: str, round_number: int,
    ) -> Path:
        directory = self.root / "frontier-trials" / protocol_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{split}-{round_number}.json"
        case_prefix = protocol_id.removesuffix("-v1")
        path.write_text(json.dumps({
            "schema_version": 1,
            "protocol_id": protocol_id,
            "hypothesis_id": "target-evaluation",
            "split": split,
            "round": round_number,
            "run_id": f"{protocol_id}-{split}-{round_number}",
            "case_ids": [f"{case_prefix}-{split}-1", f"{case_prefix}-{split}-2"],
            "baseline_artifact_sha256": "a" * 64,
            "candidate_artifact_sha256": candidate_hash,
            "metrics": {
                "utility": {"baseline": 0.5, "candidate": 0.7},
                "unsafe_rate": {"baseline": 0.1, "candidate": 0.1},
            },
            "producer": "deterministic P26 frontier fixture",
        }), encoding="utf-8")
        return path

    def _frontier(
        self, skill_id: str, protocol_id: str, artifact_character: str, commit_character: str,
    ) -> dict[str, str]:
        candidate_hash = artifact_character * 64
        commit = commit_character * 40
        repository = f"example/{skill_id}"
        case_prefix = protocol_id.removesuffix("-v1")
        plan_frontier_skill_research(
            self.root,
            protocol_id=protocol_id,
            protocol={
                "research_question": f"Does {skill_id} improve its frozen target before composition testing?",
                "target_agent": f"source target for {skill_id}",
                "target_harness": "deterministic source harness",
                "baseline_artifact_sha256": "a" * 64,
                "candidate_identity": {
                    "skill_id": skill_id,
                    "repository": repository,
                    "commit": commit,
                },
                "splits": {
                    "train": [f"{case_prefix}-train-1", f"{case_prefix}-train-2"],
                    "validation": [f"{case_prefix}-validation-1", f"{case_prefix}-validation-2"],
                    "heldout": [f"{case_prefix}-heldout-1", f"{case_prefix}-heldout-2"],
                },
                "metrics": [
                    {"name": "utility", "direction": "maximize", "kind": "utility", "tolerance": 0.0},
                    {"name": "unsafe_rate", "direction": "minimize", "kind": "safety", "tolerance": 0.0},
                ],
                "validation_rounds": 2,
            },
            selected_by="main_agent",
            selection_rationale="The main agent selected one exact immutable component for later composition evidence.",
        )
        record_frontier_skill_source(self.root, protocol_id=protocol_id, source={
            "source_id": "composition-paper",
            "source_type": "primary_paper",
            "title": "Generative Skill Composition for LLM Agents",
            "url": "https://arxiv.org/abs/2606.32025",
            "immutable_id": "2606.32025v1",
            "mechanism": "Treats Skill subset, count, and order as a coupled evaluation problem.",
            "limitations": "Its aggregate results do not establish this exact local component outcome.",
        })
        record_frontier_skill_source(self.root, protocol_id=protocol_id, source={
            "source_id": "candidate-code",
            "source_type": "repository",
            "title": f"{skill_id} exact repository fixture",
            "url": f"https://github.com/{repository}",
            "immutable_id": commit,
            "mechanism": "Binds the exact candidate identity used by this deterministic fixture.",
            "limitations": "The repository identity is not executed by the unit test.",
        })
        register_frontier_skill_hypothesis(self.root, protocol_id=protocol_id, hypothesis={
            "hypothesis_id": "target-evaluation",
            "statement": f"{skill_id} improves its exact source target without a safety regression.",
            "mechanism": "Paired validation and heldout metrics bind the component artifact.",
            "expected_effect": "Utility improves while safety remains non-regressive.",
            "failure_condition": "Utility fails to improve or safety regresses.",
            "canonical_owner": "domain-skill",
            "overlap_decision": "fuse_narrow_adapter",
            "source_ids": ["composition-paper", "candidate-code"],
        })
        for round_number in (1, 2):
            record_frontier_skill_trial(
                self.root, protocol_id=protocol_id,
                trial_path=str(self._frontier_trial(protocol_id, candidate_hash, "validation", round_number)),
            )
        record_frontier_skill_trial(
            self.root, protocol_id=protocol_id,
            trial_path=str(self._frontier_trial(protocol_id, candidate_hash, "heldout", 1)),
        )
        finalize_frontier_skill_research(self.root, protocol_id=protocol_id)
        return {
            "artifact_sha256": candidate_hash,
            "skill_id": skill_id,
            "repository": repository,
            "commit": commit,
            "canonical_owner": "domain-skill",
            "overlap_decision": "fuse_narrow_adapter",
        }

    @staticmethod
    def _benign_edges() -> dict[str, list[dict[str, str]]]:
        return {
            "skill-a": [{
                "from_node": "public_data", "to_node": "artifact",
                "evidence_locator": "SKILL.md#public-input",
            }],
            "skill-b": [{
                "from_node": "artifact", "to_node": "document",
                "evidence_locator": "SKILL.md#document-output",
            }],
        }

    def _protocol(
        self,
        *,
        edges: dict[str, list[dict[str, str]]] | None = None,
        case_ids: list[str] | None = None,
        replicates: int = 2,
        bindings: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, object]:
        edges = edges or self._benign_edges()
        bindings = bindings or self.bindings
        return {
            "research_question": "Does this exact ordered Skill composition add utility without safety regression?",
            "target": {
                "agent_id": "codex-entry",
                "model_family": "gpt-5",
                "model_version": "gpt-5.6",
                "harness": "codex-cli",
                "harness_version": "2026-08",
                "task_scope": "deterministic composition benchmark",
                "executor_group": "host-a",
                "evidence_family": "p26-deterministic",
            },
            "components": [
                {
                    "frontier_protocol_id": "frontier-a-v1",
                    "binding": bindings["skill-a"],
                    "capability_edges": edges["skill-a"],
                },
                {
                    "frontier_protocol_id": "frontier-b-v1",
                    "binding": bindings["skill-b"],
                    "capability_edges": edges["skill-b"],
                },
            ],
            "control_order": ["skill-b", "skill-a"],
            "case_ids": case_ids or ["composition-case-1", "composition-case-2"],
            "metrics": [
                {"name": "utility", "direction": "maximize", "kind": "utility", "tolerance": 0.0},
                {"name": "unsafe_rate", "direction": "minimize", "kind": "safety", "tolerance": 0.0},
            ],
            "replicates": replicates,
        }

    def _plan(
        self, composition_id: str = "composition-v1", **protocol_options: object,
    ) -> str:
        plan_skill_composition(
            self.root,
            composition_id=composition_id,
            protocol=self._protocol(**protocol_options),
            selected_by="main_agent",
            selection_rationale="The main agent explicitly selected two exact components, their target order, and a control order.",
        )
        return composition_id

    def _sources(self, composition_id: str) -> None:
        record_skill_composition_source(self.root, composition_id=composition_id, source={
            "source_id": "skill-composer-paper",
            "source_type": "primary_paper",
            "title": "Generative Skill Composition for LLM Agents",
            "url": "https://arxiv.org/abs/2606.32025",
            "immutable_id": "2606.32025v1",
            "mechanism": "Requires joint evidence for Skill subset, count, and order.",
            "limitations": "It does not establish the result of this exact composition protocol.",
        })
        record_skill_composition_source(self.root, composition_id=composition_id, source={
            "source_id": "skillsbench-code",
            "source_type": "repository",
            "title": "SkillsBench exact benchmark implementation",
            "url": "https://github.com/benchflow-ai/skillsbench",
            "immutable_id": "9a1f4dd5f7659f75707435da3ce854b6e48321d1",
            "mechanism": "Provides no-Skill and multi-Skill task execution with deterministic verifiers.",
            "limitations": "Its published tasks do not substitute for this frozen local task and evidence family.",
        })

    def _trial(
        self,
        composition_id: str,
        replicate: int,
        *,
        ordered_utility: float = 0.8,
        ordered_unsafe: float = 0.1,
        control_utility: float = 0.7,
        control_unsafe: float = 0.1,
        run_id: str | None = None,
    ) -> Path:
        condition_values = {
            "baseline": (0.5, 0.1),
            "single.skill-a": (0.6, 0.1),
            "single.skill-b": (0.65, 0.1),
            "ordered": (ordered_utility, ordered_unsafe),
            "control_order": (control_utility, control_unsafe),
        }
        conditions = {
            condition_id: {
                "run_sha256": self._sha(f"{composition_id}-{replicate}-{condition_id}-run"),
                "execution_receipt_sha256": self._sha(f"{composition_id}-{replicate}-{condition_id}-receipt"),
                "metrics": {"utility": utility, "unsafe_rate": unsafe},
            }
            for condition_id, (utility, unsafe) in condition_values.items()
        }
        directory = self.root / "composition-trials"
        directory.mkdir(exist_ok=True)
        path = directory / f"{composition_id}-{replicate}.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "composition_id": composition_id,
            "replicate": replicate,
            "run_id": run_id or f"{composition_id}-replicate-{replicate}",
            "case_ids": ["composition-case-1", "composition-case-2"],
            "component_artifact_sha256s": {
                skill_id: binding["artifact_sha256"] for skill_id, binding in self.bindings.items()
            },
            "target_order": ["skill-a", "skill-b"],
            "control_order": ["skill-b", "skill-a"],
            "conditions": conditions,
            "producer": "deterministic P26 composition fixture",
        }), encoding="utf-8")
        return path

    def _complete(
        self,
        composition_id: str = "composition-v1",
        *,
        edges: dict[str, list[dict[str, str]]] | None = None,
        ordered_utility: float = 0.8,
        ordered_unsafe: float = 0.1,
        control_utility: float = 0.7,
        control_unsafe: float = 0.1,
    ) -> str:
        self._plan(composition_id, edges=edges)
        self._sources(composition_id)
        for replicate in (1, 2):
            result = record_skill_composition_trial(
                self.root,
                composition_id=composition_id,
                trial_path=str(self._trial(
                    composition_id,
                    replicate,
                    ordered_utility=ordered_utility,
                    ordered_unsafe=ordered_unsafe,
                    control_utility=control_utility,
                    control_unsafe=control_unsafe,
                )),
            )
            self.assertEqual(result["status"], "RECORDED_NOT_EXPOSED")
            self.assertNotIn("classification", result)
        return composition_id

    def test_positive_gain_is_scoped_to_the_exact_order(self) -> None:
        composition_id = self._complete()
        before = skill_composition_status(self.root, composition_id)
        self.assertTrue(all(item["status"] == "RECORDED_NOT_EXPOSED" for item in before["trials"]))
        final = finalize_skill_composition(self.root, composition_id=composition_id)
        result = final["finalization"]
        self.assertEqual(result["status"], "HUMAN_REVIEW_REQUIRED")
        self.assertEqual(result["support_status"], "SUPPORTED_ON_RECORDED_ORDER")
        self.assertTrue(result["scoped_claim_allowed"])
        self.assertFalse(result["universal_claim_allowed"])
        self.assertFalse(result["order_invariant_claim_allowed"])
        self.assertFalse(result["safety_claim_allowed"])
        self.assertEqual(
            {item["classification"] for item in result["replicates"]},
            {"POSITIVE_COMPOSITION_GAIN"},
        )
        self.assertEqual(verify_skill_composition(self.root, composition_id)["status"], "PASS")

    def test_no_gain_and_interference_are_not_averaged_into_support(self) -> None:
        no_gain = self._complete("no-gain-v1", ordered_utility=0.65)
        no_gain_final = finalize_skill_composition(self.root, composition_id=no_gain)["finalization"]
        self.assertEqual(no_gain_final["support_status"], "NOT_DEMONSTRATED")
        self.assertEqual(
            {item["classification"] for item in no_gain_final["replicates"]},
            {"NO_COMPOSITION_GAIN"},
        )
        self.assertNotIn("aggregate_mean", no_gain_final)

        interference = self._complete("interference-v1", ordered_utility=0.4)
        interference_final = finalize_skill_composition(
            self.root, composition_id=interference,
        )["finalization"]
        self.assertEqual(interference_final["support_status"], "NOT_SUPPORTED_INTERFERENCE")
        self.assertFalse(interference_final["scoped_claim_allowed"])

    def test_safety_regression_dominates_positive_utility(self) -> None:
        composition_id = self._complete("safety-v1", ordered_utility=0.9, ordered_unsafe=0.2)
        final = finalize_skill_composition(self.root, composition_id=composition_id)["finalization"]
        self.assertEqual(final["support_status"], "NOT_SUPPORTED_SAFETY_REGRESSION")
        self.assertFalse(final["scoped_claim_allowed"])
        self.assertEqual(
            {item["classification"] for item in final["replicates"]},
            {"SAFETY_REGRESSION"},
        )

    def test_order_effect_remains_visible_even_when_target_order_improves(self) -> None:
        composition_id = self._complete(
            "order-control-better-v1", ordered_utility=0.8, control_utility=0.9,
        )
        final = finalize_skill_composition(self.root, composition_id=composition_id)["finalization"]
        self.assertEqual(final["support_status"], "SUPPORTED_ON_RECORDED_ORDER")
        self.assertEqual(
            {item["order_effect"] for item in final["replicates"]},
            {"CONTROL_ORDER_BETTER"},
        )
        self.assertFalse(final["order_invariant_claim_allowed"])

    def test_target_order_cross_skill_path_blocks_the_gain_claim(self) -> None:
        edges = {
            "skill-a": [{
                "from_node": "sensitive_data", "to_node": "artifact",
                "evidence_locator": "SKILL.md#read-private-data",
            }],
            "skill-b": [{
                "from_node": "artifact", "to_node": "network_send",
                "evidence_locator": "scripts/send.py#upload",
            }],
        }
        composition_id = self._complete("target-path-v1", edges=edges)
        final = finalize_skill_composition(self.root, composition_id=composition_id)["finalization"]
        self.assertEqual(final["support_status"], "NOT_SUPPORTED_DECLARED_PATH_RISK")
        paths = final["path_analysis"]["target_order"]["paths"]
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0]["threat_type"], "data_exfiltration")
        self.assertEqual(paths[0]["skill_ids"], ["skill-a", "skill-b"])
        self.assertFalse(final["path_analysis"]["attack_synthesis_performed"])

    def test_three_component_order_and_path_are_evaluated_end_to_end(self) -> None:
        binding_c = self._frontier("skill-c", "frontier-c-v1", "f", "1")
        self.bindings["skill-c"] = binding_c
        protocol = self._protocol(edges={
            "skill-a": [{
                "from_node": "sensitive_data", "to_node": "artifact",
                "evidence_locator": "SKILL.md#read-private-data",
            }],
            "skill-b": [{
                "from_node": "artifact", "to_node": "document",
                "evidence_locator": "SKILL.md#prepare-document",
            }],
        })
        protocol["components"].append({
            "frontier_protocol_id": "frontier-c-v1",
            "binding": binding_c,
            "capability_edges": [{
                "from_node": "document", "to_node": "network_send",
                "evidence_locator": "scripts/send.py#upload",
            }],
        })
        protocol["control_order"] = ["skill-c", "skill-b", "skill-a"]
        composition_id = "three-component-v1"
        plan_skill_composition(
            self.root,
            composition_id=composition_id,
            protocol=protocol,
            selected_by="main_agent",
            selection_rationale=(
                "The main agent selected three exact P24 artifacts to test a three-stage capability path."
            ),
        )
        self._sources(composition_id)
        for replicate in (1, 2):
            path = self._trial(composition_id, replicate)
            document = json.loads(path.read_text(encoding="utf-8"))
            document["target_order"] = ["skill-a", "skill-b", "skill-c"]
            document["control_order"] = ["skill-c", "skill-b", "skill-a"]
            document["conditions"]["single.skill-c"] = {
                "run_sha256": self._sha(f"{composition_id}-{replicate}-single.skill-c-run"),
                "execution_receipt_sha256": self._sha(
                    f"{composition_id}-{replicate}-single.skill-c-receipt"
                ),
                "metrics": {"utility": 0.63, "unsafe_rate": 0.1},
            }
            path.write_text(json.dumps(document), encoding="utf-8")
            record_skill_composition_trial(
                self.root, composition_id=composition_id, trial_path=str(path),
            )
        final = finalize_skill_composition(
            self.root, composition_id=composition_id,
        )["finalization"]
        self.assertEqual(final["support_status"], "NOT_SUPPORTED_DECLARED_PATH_RISK")
        paths = final["path_analysis"]["target_order"]["paths"]
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0]["skill_ids"], ["skill-a", "skill-b", "skill-c"])
        self.assertEqual(paths[0]["threat_type"], "data_exfiltration")

    def test_control_only_path_is_reported_without_changing_the_exact_target_claim(self) -> None:
        edges = {
            "skill-a": [{
                "from_node": "artifact", "to_node": "network_send",
                "evidence_locator": "scripts/send.py#upload",
            }],
            "skill-b": [{
                "from_node": "sensitive_data", "to_node": "artifact",
                "evidence_locator": "SKILL.md#read-private-data",
            }],
        }
        composition_id = self._complete("control-path-v1", edges=edges)
        final = finalize_skill_composition(self.root, composition_id=composition_id)["finalization"]
        self.assertEqual(final["support_status"], "SUPPORTED_ON_RECORDED_ORDER")
        self.assertEqual(final["path_analysis"]["status"], "CONTROL_ORDER_PATH_REVIEW_REQUIRED")
        self.assertEqual(final["path_analysis"]["target_order"]["path_count"], 0)
        self.assertEqual(final["path_analysis"]["control_order"]["path_count"], 1)

    def test_cases_are_fresh_and_every_component_binding_is_exact(self) -> None:
        with self.assertRaisesRegex(SkillCompositionError, "P24"):
            self._plan(
                "leakage-v1",
                case_ids=["frontier-a-heldout-1", "composition-case-2"],
            )
        wrong = {key: dict(value) for key, value in self.bindings.items()}
        wrong["skill-a"]["artifact_sha256"] = "f" * 64
        with self.assertRaisesRegex(SkillCompositionError, "frontier component"):
            self._plan("wrong-binding-v1", bindings=wrong)

    def test_main_agent_selects_two_or_three_and_control_order_must_differ(self) -> None:
        with self.assertRaisesRegex(SkillCompositionError, "main_agent"):
            plan_skill_composition(
                self.root,
                composition_id="automatic-v1",
                protocol=self._protocol(),
                selected_by="classifier",
                selection_rationale="A classifier attempted to choose the components automatically.",
            )
        protocol = self._protocol()
        protocol["control_order"] = ["skill-a", "skill-b"]
        with self.assertRaisesRegex(SkillCompositionError, "differ"):
            plan_skill_composition(
                self.root,
                composition_id="same-order-v1",
                protocol=protocol,
                selected_by="main_agent",
                selection_rationale="The main agent deliberately tested the invalid same-order boundary.",
            )

    def test_replicates_and_all_condition_receipts_are_append_only(self) -> None:
        composition_id = self._plan("append-only-v1")
        self._sources(composition_id)
        with self.assertRaisesRegex(SkillCompositionError, "replicate order"):
            record_skill_composition_trial(
                self.root,
                composition_id=composition_id,
                trial_path=str(self._trial(composition_id, 2)),
            )
        first = self._trial(composition_id, 1)
        record_skill_composition_trial(self.root, composition_id=composition_id, trial_path=str(first))
        second = self._trial(composition_id, 2)
        document = json.loads(second.read_text(encoding="utf-8"))
        document["conditions"]["baseline"]["execution_receipt_sha256"] = self._sha(
            f"{composition_id}-1-baseline-receipt"
        )
        second.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(SkillCompositionError, "receipt hashes"):
            record_skill_composition_trial(
                self.root, composition_id=composition_id, trial_path=str(second),
            )

    def test_missing_sources_or_replicates_block_finalization(self) -> None:
        composition_id = self._plan("missing-evidence-v1")
        with self.assertRaisesRegex(SkillCompositionError, "primary-paper"):
            finalize_skill_composition(self.root, composition_id=composition_id)
        self._sources(composition_id)
        record_skill_composition_trial(
            self.root,
            composition_id=composition_id,
            trial_path=str(self._trial(composition_id, 1)),
        )
        with self.assertRaisesRegex(SkillCompositionError, "replicate"):
            finalize_skill_composition(self.root, composition_id=composition_id)

    def test_trial_and_state_tampering_are_detected(self) -> None:
        composition_id = self._complete("tamper-v1")
        status = skill_composition_status(self.root, composition_id)
        artifact = self.root / status["trials"][0]["artifact_path"]
        artifact.write_text("{}", encoding="utf-8")
        self.assertEqual(verify_skill_composition(self.root, composition_id)["status"], "FAIL")

        state_path = (
            self.root / ".research-guard" / "domain-skills" /
            "frontier-composition" / composition_id / "state.json"
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["protocol"]["research_question"] = "tampered"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(SkillCompositionError):
            skill_composition_status(self.root, composition_id)

    def test_mcp_reuses_research_design_and_preserves_seventeen_tools(self) -> None:
        self.assertEqual(len(mcp_server.TOOLS), 17)
        design = next(item for item in mcp_server.TOOLS if item["name"] == "research_design")
        properties = design["inputSchema"]["properties"]
        self.assertIn("skill_composition_action", properties)
        self.assertEqual(
            properties["skill_composition_action"]["enum"],
            ["plan", "record_source", "record_trial", "finalize", "status", "verify"],
        )
        routed = mcp_server.dispatch("research_design", {
            "action": "status",
            "project_root": str(self.root),
            "skill_composition_action": "plan",
            "skill_composition_id": "mcp-composition-v1",
            "skill_composition_protocol": self._protocol(),
            "skill_composition_selected_by": "main_agent",
            "skill_composition_selection_rationale": (
                "The main agent selected two exact P24 artifacts and an explicit target/control order."
            ),
        })
        self.assertEqual(routed["status"], "ACTION_REQUIRED")
        self.assertFalse(routed["execution_allowed_by_core"])
        self.assertFalse(routed["automatic_selection"])


if __name__ == "__main__":
    unittest.main()
