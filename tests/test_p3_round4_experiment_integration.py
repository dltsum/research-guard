from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]


def api():
    import sys

    sys.path.insert(0, str(PLUGIN / "scripts"))
    from research_design_core import (
        DesignError,
        commit_candidate,
        get_research_design_status,
        plan_ideation,
        register_candidates,
        register_experiment,
        register_hypothesis,
    )
    from research_guard_core import load_state, save_state

    return DesignError, commit_candidate, get_research_design_status, plan_ideation, register_candidates, register_experiment, register_hypothesis, load_state, save_state


def candidate() -> dict:
    return {
        "candidate_id": "I1", "title": "Boundary-separated adaptation",
        "problem": "Boundary detection and adaptation are confounded.",
        "mechanism": "A detector gates a separate low-rank update.",
        "falsifier": "Matched controls show no boundary-specific effect.",
        "minimum_viable_experiment": "Compare gated and ungated updates on two shifts.",
        "differentiator": "Separates detection and adaptation.",
        "feasibility": "Uses existing data and bounded compute.",
        "lens_id": "boundary_probe", "prior_work": [],
    }


def hypothesis() -> dict:
    return {
        "hypothesis_id": "H1", "status": "candidate",
        "observation": {"statement": "Ungated updates degrade after a shift.", "provenance": "Frozen pilot log."},
        "research_question": "Does gated adaptation reduce interference?",
        "statement": "Gating reduces cross-regime interference.",
        "mechanism": "The gate isolates regime-specific gradients.",
        "rivals": [{"rival_id": "H2", "statement": "Only update magnitude matters.", "mechanism": "The gate merely lowers update norm."}],
        "predictions": [{
            "prediction_id": "P1", "statement": "Gating wins at matched update norm.",
            "observable": "Cross-regime loss", "expected_pattern": "Lower loss change",
            "falsifier": "No difference at matched norm", "discriminates_against": ["H2"],
        }],
        "operationalizations": [{
            "construct": "interference", "variable": "delta_loss", "role": "primary_outcome",
            "definition": "Held-out loss change", "measurement_method": "Frozen evaluation script",
            "unit": "loss units", "timing": "After each update block",
        }],
        "evidence_boundary": "Pilot evidence is motivating only.", "literature_items": [],
    }


def experiment() -> dict:
    return {
        "experiment_id": "E1",
        "design_type": "randomized controlled computational experiment",
        "claims_tested": ["P1"],
        "experimental_unit": "independently seeded training run",
        "analysis_unit": "independently seeded training run",
        "independence_justification": "Seeds, initialization, and data-order streams are independent; checkpoints within a run are repeated measures.",
        "assignment": "Pre-generate a seeded balanced schedule assigning each independent run to gated or ungated update.",
        "controls": ["matched update norm", "matched data order", "same checkpoint and evaluation code"],
        "blocking": "Block by starting checkpoint and shift family.",
        "primary_outcomes": ["delta_loss"],
        "estimand": "Mean gated-minus-ungated cross-regime loss change at matched update norm.",
        "power": {
            "mode": "simulation",
            "basis": "Minimum relevant loss difference declared before results are viewed.",
            "target_power_or_precision": "At least 0.8 power for the declared minimum difference.",
            "sample_size": "Number of independent seeds selected by blinded simulation.",
            "sensitivity_plan": "Report power across plausible variance and attrition values.",
        },
        "missing_data_plan": "Retain failed runs as failures; report exclusions by prespecified reason.",
        "multiplicity_plan": "One confirmatory outcome; all additional outcomes are exploratory.",
        "stopping_rule": "Stop only at the frozen run count or a documented safety/resource block.",
        "success_criteria": "Interval estimate excludes zero in the predicted direction and the effect exceeds the minimum relevant difference.",
        "failure_interpretation": "Distinguish evidence against the mechanism from imprecision, implementation failure, and invalid measurement.",
        "run_order": [{"run_id": "R1", "purpose": "Primary gated versus ungated comparison", "priority": "must_run", "stop_go": "Proceed to ablations only after implementation checks pass."}],
        "ablations": [{
            "ablation_id": "A1", "component": "boundary gate", "what_it_tests": "Whether boundary-specific gating causes the effect",
            "expected_if_matters": "Removing the gate increases interference at matched update norm.",
            "failure_interpretation": "The gate is unnecessary or the test lacks sensitivity.",
            "priority": "must_run", "compute": "One matched arm per independent seed.",
        }],
        "ethics_and_feasibility": {"status": "cleared", "required_reviews": [], "unresolved_blocks": []},
    }


class ExperimentIntegrationRoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        _, commit_candidate, _, plan_ideation, register_candidates, _, register_hypothesis, _, _ = api()
        plan = plan_ideation(self.root, request_text="Design the smallest rigorous test", problem="Boundary adaptation is confounded.")
        item = candidate()
        register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[item])
        commit_candidate(
            self.root, candidate_id="I1", selected_by="user",
            method={key: item[key] for key in ("title", "problem", "mechanism")},
        )
        register_hypothesis(self.root, hypothesis())

    def tearDown(self):
        self.temp.cleanup()

    def test_experiment_binds_units_power_run_order_and_ablations(self):
        _, _, _, _, _, register_experiment, _, _, _ = api()
        result = register_experiment(self.root, experiment())
        self.assertTrue(result["experiment_hash"])
        self.assertEqual(result["experiment"]["analysis_unit"], result["experiment"]["experimental_unit"])
        self.assertEqual(result["experiment"]["ablations"][0]["what_it_tests"], "Whether boundary-specific gating causes the effect")

    def test_independence_and_power_basis_fail_closed(self):
        DesignError, _, _, _, _, register_experiment, _, _, _ = api()
        no_independence = experiment(); no_independence.pop("independence_justification")
        no_power_basis = experiment(); no_power_basis["power"].pop("basis")
        for value, message in ((no_independence, "independence"), (no_power_basis, "basis")):
            with self.subTest(message=message), self.assertRaisesRegex(DesignError, message):
                register_experiment(self.root, value)

    def test_ablations_need_a_question_or_an_explicit_not_applicable_reason(self):
        DesignError, _, _, _, _, register_experiment, _, _, _ = api()
        invalid = experiment(); invalid["ablations"] = []
        with self.assertRaisesRegex(DesignError, "ablation"):
            register_experiment(self.root, invalid)
        valid = experiment(); valid["ablations"] = []; valid["ablation_not_applicable_reason"] = "No separable component exists in this registered method."
        self.assertEqual(register_experiment(self.root, valid)["experiment"]["ablations"], [])

    def test_readiness_requires_current_valid_novelty_pass(self):
        _, _, get_status, _, _, register_experiment, _, load_state, save_state = api()
        register_experiment(self.root, experiment())
        before = get_status(self.root, verify=True)
        self.assertEqual(before["status"], "NOVELTY_CHECK_REQUIRED")
        self.assertFalse(before["ready"])
        state = load_state(self.root)
        state["gate"] = {"status": "PASS", "reason": "fixture", "updated_at": "2026-08-12T00:00:00Z"}
        state["latest_report"] = ".research-guard/reports/current.json"
        state["current_receipt"] = ".research-guard/receipts/current.json"
        save_state(self.root, state)
        with patch("research_design_core.verify_receipt", return_value={"valid": True, "gate_status": "PASS", "errors": []}):
            after = get_status(self.root, verify=True)
        self.assertEqual(after["status"], "PASS")
        self.assertTrue(after["ready"])

    def test_mcp_uses_one_multiplexer_and_skill_stays_compact(self):
        import sys

        sys.path.insert(0, str(PLUGIN / "scripts"))
        import mcp_server

        tools = [item for item in mcp_server.TOOLS if item["name"] == "research_design"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(len(mcp_server.TOOLS), 17)
        actions = set(tools[0]["inputSchema"]["properties"]["action"]["enum"])
        self.assertTrue({
            "plan_ideation", "register_candidates", "commit_candidate", "register_hypothesis",
            "register_experiment", "status", "verify",
        } <= actions)
        skill = (PLUGIN / "skills" / "research-design-guard" / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(len(skill.split()), 320)
        self.assertIn("NOVELTY_CHECK_REQUIRED", skill)
        self.assertIn("https://", skill)


if __name__ == "__main__":
    unittest.main()
