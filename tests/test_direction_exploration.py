from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import mcp_server  # noqa: E402
import resource_guard  # noqa: E402
from direction_exploration_core import (  # noqa: E402
    DirectionExplorationError,
    activate_direction_candidate,
    bind_direction_collision,
    direction_exploration_status,
    finalize_direction_choices,
    plan_direction_exploration,
    record_direction_iteration,
    register_direction_candidates,
    revise_direction_candidate,
    verify_direction_exploration,
)
from research_guard_core import load_state, refresh_domain, run_novelty_search  # noqa: E402
from research_integrity_core import execute_reproducibility, register_reproducibility_plan  # noqa: E402


class DirectionExplorationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.root / "signing-key.bin")

    def tearDown(self) -> None:
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temporary.cleanup()

    @staticmethod
    def candidate(index: int, **overrides):
        method = {
            "title": f"Resource-bounded direction {index}",
            "problem": "Find a feasible local research direction without reusing stale novelty evidence",
            "mechanism": f"Candidate mechanism {index} applies a distinct frozen transformation to pilot evidence",
            "contributions": [f"direction-{index}", "resource-bounded pilot"],
            "datasets": ["local pilot fixture"],
            "evaluation": ["bounded validation signal"],
        }
        value = {
            "candidate_id": f"direction-{index}",
            "title": method["title"],
            "problem": method["problem"],
            "mechanism": method["mechanism"],
            "falsifier": "The frozen pilot metric does not improve by the predeclared minimum effect.",
            "minimum_viable_experiment": "Run a serial managed pilot against the frozen baseline and retain every attempt.",
            "differentiator": f"Uses transformation family {index} rather than the linked prior-work mechanism.",
            "feasibility": "Runs on one CPU thread inside the registered managed-standard memory profile.",
            "method": method,
            "prior_work": [{
                "title": f"Prior work anchor {index}",
                "url": f"https://doi.org/10.1000/direction-{index}",
                "relationship": "nearest initial literature anchor",
            }],
            "coarse_test_protocol": {
                "evidence_mode": "quantitative_delta",
                "data_role": "pilot",
                "iteration_limit": 2,
                "resource_profile": "managed_standard",
                "estimated_peak_memory_bytes": 32 * 1024 * 1024,
                "protocol_checks": [
                    {"check_id": "frozen-split", "description": "Use only the frozen pilot split."},
                    {"check_id": "parameter-range", "description": "Keep parameters inside the registered range."},
                ],
                "scope_note": "This is a direction-screening signal, not a confirmatory study.",
                "metric_id": "pilot-quality",
                "metric_label": "Pilot quality",
                "unit": "proportion",
                "direction": "maximize",
                "minimum_effect": 0.05,
                "legal_range": [0.0, 1.0],
                "minimum_observations": 2,
                "baseline_source": "Frozen local baseline fixture.",
            },
        }
        value.update(overrides)
        return value

    def plan_and_register(self, count: int = 6):
        plan_direction_exploration(
            self.root,
            exploration_id="local-directions-v1",
            authorization_scope="The user explicitly authorized local resource exploration and coarse direction testing.",
            problem="Identify five feasible and collision-checked directions from local pilot evidence.",
            constraints=["CPU only", "retain failed attempts", "final choice belongs to the user"],
            authorized_by="user",
        )
        return register_direction_candidates(
            self.root,
            exploration_id="local-directions-v1",
            candidates=[self.candidate(index) for index in range(1, count + 1)],
            selected_by="main_agent",
            selection_rationale="The pool spans distinct frozen mechanisms while preserving one problem anchor and resource profile.",
        )

    def activate_and_search(self, candidate_id: str) -> dict:
        activated = activate_direction_candidate(
            self.root, exploration_id="local-directions-v1", candidate_id=candidate_id,
        )
        refresh_domain(
            self.root,
            primary_domain="computer_science",
            secondary_domains=[],
            selected_by="main_agent",
            selection_rationale="The methods are computational pilot transformations evaluated with software experiments.",
        )
        novelty = load_state(self.root)
        sources = novelty["search_plan"]["required_sources"] + novelty["search_plan"]["supplemental_sources"]
        fixtures = {source: [] for source in sources}
        result = run_novelty_search(self.root, fixture_sources=fixtures)
        self.assertEqual(result["report"]["gate_status"], "PASS")
        collision = bind_direction_collision(
            self.root, exploration_id="local-directions-v1", candidate_id=candidate_id,
        )
        self.assertTrue(collision["literature_links"][0]["url"].startswith("https://"))
        return activated

    def run_iteration(self, candidate_id: str, *, candidate_value: float, iteration: int) -> dict:
        status = direction_exploration_status(self.root, "local-directions-v1")
        candidate = next(item for item in status["candidates"] if item["candidate_id"] == candidate_id)
        direction_state = json.loads(
            (self.root / ".research-guard" / "direction-explorations" / "local-directions-v1.json").read_text(encoding="utf-8")
        )
        revision = direction_state["candidates"][candidate_id]["revisions"][-1]
        run_id = f"{candidate_id}-r{revision['revision']}-i{iteration}"
        output = f"pilot-results/{run_id}.json"
        script = self.root / f"write-{run_id}.py"
        payload = {
            "schema_version": 1,
            "candidate_id": candidate_id,
            "revision": revision["revision"],
            "candidate_revision_hash": candidate["candidate_revision_hash"],
            "method_hash": candidate["method_hash"],
            "protocol_hash": revision["coarse_test_protocol"]["protocol_hash"],
            "iteration": iteration,
            "configuration_id": f"config-{iteration}",
            "data_role": "pilot",
            "result_claim_scope": "local_coarse_signal_only",
            "protocol_checks": {"frozen-split": True, "parameter-range": True},
            "evidence_urls": [],
            "metric_id": "pilot-quality",
            "unit": "proportion",
            "baseline_value": 0.5,
            "candidate_value": candidate_value,
            "observation_count": 3,
        }
        script.write_text(
            "import json\n"
            "from pathlib import Path\n"
            f"output = Path({output!r})\n"
            "output.parent.mkdir(parents=True, exist_ok=True)\n"
            f"output.write_text(json.dumps({payload!r}, sort_keys=True) + '\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        plan = register_reproducibility_plan(
            self.root,
            run_id,
            {
                "command": [sys.executable, script.name],
                "working_directory": ".",
                "inputs": [script.name],
                "outputs": [output],
                "parameters": {"candidate_id": candidate_id, "iteration": iteration},
                "seeds": [11],
                "environment": {"python": sys.version.split()[0]},
                "expected_checks": [{"kind": "output_exists", "path": output}],
            },
            selected_by="user",
        )
        self.assertEqual(plan["method_hash"], candidate["method_hash"])
        execution = execute_reproducibility(self.root, run_id, timeout=60)
        self.assertEqual(execution["status"], "PASS")
        return record_direction_iteration(
            self.root,
            exploration_id="local-directions-v1",
            candidate_id=candidate_id,
            run_id=run_id,
            result_path=output,
        )

    def test_round_1_requires_user_authorization_and_rejects_ranking(self) -> None:
        with self.assertRaisesRegex(DirectionExplorationError, "USER_AUTHORIZATION_REQUIRED"):
            plan_direction_exploration(
                self.root,
                exploration_id="not-authorized",
                authorization_scope="The agent inferred authorization.",
                problem="Find directions.",
                constraints=[],
                authorized_by="main_agent",
            )
        planned = plan_direction_exploration(
            self.root,
            exploration_id="local-directions-v1",
            authorization_scope="The user explicitly authorized local resource exploration.",
            problem="Find five directions.",
            constraints=[],
            authorized_by="user",
        )
        snapshot = planned["resource_snapshot"]
        self.assertFalse(snapshot["accelerators"]["policy_allowed"])
        self.assertIsNone(snapshot["accelerators"]["runtime_usable_devices"])
        self.assertTrue(snapshot["privacy"]["hostname_redacted"])
        with self.assertRaisesRegex(DirectionExplorationError, "5-15"):
            register_direction_candidates(
                self.root,
                exploration_id="local-directions-v1",
                candidates=[self.candidate(index) for index in range(1, 5)],
                selected_by="main_agent",
                selection_rationale="Four items are intentionally insufficient for the five-choice contract.",
            )
        ranked = self.candidate(1)
        ranked["score"] = 0.99
        with self.assertRaisesRegex(DirectionExplorationError, "cannot rank"):
            register_direction_candidates(
                self.root,
                exploration_id="local-directions-v1",
                candidates=[ranked, *[self.candidate(index) for index in range(2, 6)]],
                selected_by="main_agent",
                selection_rationale="The fixture intentionally contains a forbidden automatic score.",
            )

    def test_nested_managed_worker_reuses_run_low_water_for_admission(self) -> None:
        with patch.dict(os.environ, {"RESEARCH_GUARD_MANAGED_WORKER": "1"}), \
                patch.object(resource_guard, "current_process_in_job", return_value=True), \
                patch.object(
                    resource_guard,
                    "require_start_headroom",
                    side_effect=resource_guard.ResourceGuardError("TEST_STOP_AFTER_ADMISSION"),
                ) as headroom:
            with self.assertRaisesRegex(resource_guard.ResourceGuardError, "TEST_STOP_AFTER_ADMISSION"):
                resource_guard.run_managed([sys.executable, "--version"], timeout=1)
        headroom.assert_called_once_with(resource_guard.RUN_MIN_FREE_BYTES)

    def test_rounds_2_to_5_managed_iteration_collision_exact_five_revision_and_tamper(self) -> None:
        registered = self.plan_and_register()
        self.assertEqual(registered["candidate_count"], 6)
        self.assertFalse(registered["automatic_ranking"])

        for index in range(1, 6):
            candidate_id = f"direction-{index}"
            self.activate_and_search(candidate_id)
            if index == 1:
                negative = self.run_iteration(candidate_id, candidate_value=0.52, iteration=1)
                self.assertEqual(negative["computed_evidence"]["outcome"], "NON_POSITIVE")
                positive = self.run_iteration(candidate_id, candidate_value=0.60, iteration=2)
            else:
                positive = self.run_iteration(candidate_id, candidate_value=0.60 + index / 1000, iteration=1)
            self.assertEqual(positive["computed_evidence"]["outcome"], "POSITIVE")
            self.assertTrue(positive["computed_evidence"]["protocol_legal"])

        self.activate_and_search("direction-6")
        illegal = self.run_iteration("direction-6", candidate_value=1.2, iteration=1)
        self.assertEqual(illegal["computed_evidence"]["outcome"], "NON_POSITIVE")
        self.assertFalse(illegal["computed_evidence"]["protocol_legal"])

        with self.assertRaisesRegex(DirectionExplorationError, "Exactly 5"):
            finalize_direction_choices(
                self.root,
                exploration_id="local-directions-v1",
                choice_ids=["direction-1", "direction-2", "direction-3", "direction-4"],
                selected_by="main_agent",
                selection_rationale="The fixture intentionally supplies too few choices.",
            )
        with self.assertRaisesRegex(DirectionExplorationError, "POSITIVE_COARSE_TEST_REQUIRED"):
            finalize_direction_choices(
                self.root,
                exploration_id="local-directions-v1",
                choice_ids=["direction-1", "direction-2", "direction-3", "direction-4", "direction-6"],
                selected_by="main_agent",
                selection_rationale="The fixture intentionally includes a direction with no positive signal.",
            )

        choice_set = finalize_direction_choices(
            self.root,
            exploration_id="local-directions-v1",
            choice_ids=["direction-5", "direction-4", "direction-3", "direction-2", "direction-1"],
            selected_by="main_agent",
            selection_rationale="These five retain positive pilot evidence and complete collision receipts across distinct mechanisms.",
        )
        self.assertEqual(choice_set["status"], "USER_SELECTION_REQUIRED")
        self.assertEqual(choice_set["choice_ids"], [f"direction-{index}" for index in range(1, 6)])
        self.assertEqual(len(choice_set["choices"]), 5)
        self.assertNotIn("winner", choice_set)
        for choice in choice_set["choices"]:
            self.assertTrue(choice["collision_check"]["literature_links"])
            self.assertTrue(all(item["url"].startswith("https://") for item in choice["collision_check"]["literature_links"]))
        self.assertEqual(verify_direction_exploration(self.root, "local-directions-v1")["status"], "PASS")

        revised = self.candidate(1)
        revised["method"] = dict(revised["method"])
        revised["method"]["mechanism"] += " with a preregistered calibration stage"
        revised["mechanism"] = revised["method"]["mechanism"]
        revision = revise_direction_candidate(
            self.root,
            exploration_id="local-directions-v1",
            candidate_id="direction-1",
            candidate=revised,
            selected_by="main_agent",
            change_summary="Added a calibration stage, which changes the canonical method and requires both checks again.",
        )
        self.assertEqual(revision["status"], "NOVELTY_AND_COARSE_TEST_REQUIRED")
        self.assertEqual(
            set(revision["invalidated"]),
            {"positive_coarse_test_evidence", "collision_search_evidence", "active_five-choice_set"},
        )
        status = direction_exploration_status(self.root, "local-directions-v1")
        current = next(item for item in status["candidates"] if item["candidate_id"] == "direction-1")
        self.assertIn("POSITIVE_COARSE_TEST_REQUIRED", current["errors"])
        self.assertIn("COLLISION_SEARCH_REQUIRED", current["errors"])
        self.assertIsNone(status["active_choice_set_sha256"])

        result_path = self.root / "pilot-results" / "direction-2-r1-i1.json"
        result_path.write_text('{"tampered":true}\n', encoding="utf-8")
        verification = verify_direction_exploration(self.root, "local-directions-v1")
        self.assertEqual(verification["status"], "FAIL")
        self.assertTrue(any("ARTIFACT_HASH_MISMATCH" in item for item in verification["errors"]))

        self.assertEqual(len(mcp_server.TOOLS), 17)
        design = next(item for item in mcp_server.TOOLS if item["name"] == "research_design")
        direction_actions = design["inputSchema"]["properties"]["direction_action"]["enum"]
        self.assertEqual(
            direction_actions,
            ["plan", "register", "activate", "record_iteration", "bind_collision", "revise", "finalize", "status", "verify"],
        )


if __name__ == "__main__":
    unittest.main()
