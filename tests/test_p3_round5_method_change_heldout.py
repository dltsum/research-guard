from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


def api():
    import sys

    sys.path.insert(0, str(PLUGIN / "scripts"))
    from research_design_core import DesignError, commit_candidate, plan_ideation, register_candidates, register_hypothesis
    from research_guard_core import declare_method_change

    return DesignError, commit_candidate, plan_ideation, register_candidates, register_hypothesis, declare_method_change


def candidate() -> dict:
    return {
        "candidate_id": "I1", "title": "Tracked boundary method",
        "problem": "Existing methods fail at a declared boundary.",
        "mechanism": "A detector gates a separate update.",
        "falsifier": "Matched controls show no boundary-specific gain.",
        "minimum_viable_experiment": "Compare gated and ungated updates.",
        "differentiator": "Separates boundary detection from adaptation.",
        "feasibility": "Uses existing data and bounded compute.",
        "lens_id": "boundary_probe", "prior_work": [],
    }


def hypothesis() -> dict:
    return {
        "hypothesis_id": "H1", "status": "candidate",
        "observation": {"statement": "A boundary failure was observed.", "provenance": "Frozen local log."},
        "research_question": "Does gating reduce the boundary failure?",
        "statement": "Gating reduces boundary interference.",
        "mechanism": "The gate isolates the update.",
        "rivals": [{"rival_id": "H2", "statement": "Only update magnitude matters.", "mechanism": "Gating lowers update norm."}],
        "predictions": [{
            "prediction_id": "P1", "statement": "Gating wins at matched norm.", "observable": "held-out loss",
            "expected_pattern": "lower loss", "falsifier": "no matched-norm difference", "discriminates_against": ["H2"],
        }],
        "operationalizations": [{
            "construct": "interference", "variable": "delta_loss", "role": "outcome",
            "definition": "held-out loss change", "measurement_method": "frozen evaluator",
            "unit": "loss units", "timing": "after the update",
        }],
        "evidence_boundary": "The observation motivates but does not establish the mechanism.",
        "literature_items": [],
    }


class MethodChangeHeldOutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.method_file = self.root / "method.md"
        self.method_file.write_text("version one", encoding="utf-8")
        _, commit_candidate, plan_ideation, register_candidates, _, _ = api()
        plan = plan_ideation(self.root, request_text="Design a boundary mechanism", problem="Methods fail at a boundary.")
        item = candidate()
        register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[item])
        method = {key: item[key] for key in ("title", "problem", "mechanism")}
        method["method_files"] = ["method.md"]
        commit_candidate(self.root, candidate_id="I1", selected_by="user", method=method)

    def tearDown(self):
        self.temp.cleanup()

    def test_tracked_method_file_change_blocks_hypothesis_registration(self):
        DesignError, _, _, _, register_hypothesis, _ = api()
        self.method_file.write_text("version two", encoding="utf-8")
        with self.assertRaisesRegex(DesignError, "tracked method file"):
            register_hypothesis(self.root, hypothesis())

    def test_declared_method_adjustment_blocks_hypothesis_registration(self):
        DesignError, _, _, _, register_hypothesis, declare_method_change = api()
        declare_method_change(self.root, "Change the gating schedule and update rule")
        with self.assertRaisesRegex(DesignError, "declared method adjustment"):
            register_hypothesis(self.root, hypothesis())


if __name__ == "__main__":
    unittest.main()
