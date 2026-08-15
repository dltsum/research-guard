from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path


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
        register_hypothesis,
    )
    from research_guard_core import register_method

    return DesignError, commit_candidate, get_research_design_status, plan_ideation, register_candidates, register_hypothesis, register_method


def candidate() -> dict:
    return {
        "candidate_id": "I1",
        "title": "Boundary-separated adaptation",
        "problem": "Boundary detection and adaptation are confounded.",
        "mechanism": "A detector gates a separate low-rank update.",
        "falsifier": "A matched ungated update has the same boundary-specific effect.",
        "minimum_viable_experiment": "Compare gated and ungated updates on two shifts.",
        "differentiator": "Explicitly separates detection and adaptation.",
        "feasibility": "Uses existing data and bounded compute.",
        "lens_id": "boundary_probe",
        "prior_work": [{"title": "Primary related work", "url": "https://doi.org/10.1000/related"}],
    }


def hypothesis() -> dict:
    return {
        "hypothesis_id": "H1",
        "status": "candidate",
        "observation": {
            "statement": "Ungated updates degrade after a detected shift.",
            "provenance": "Pilot log with fixed preprocessing; pattern is descriptive, not causal evidence.",
        },
        "research_question": "Does separating boundary detection from adaptation improve shifted performance?",
        "statement": "A detector-gated update improves shifted performance through reduced cross-regime interference.",
        "mechanism": "The gate prevents gradients from one regime changing the other regime's update.",
        "rivals": [{
            "rival_id": "H2",
            "statement": "Any gain is caused only by a lower effective learning rate.",
            "mechanism": "Gating reduces total update magnitude without boundary-specific action.",
        }],
        "predictions": [{
            "prediction_id": "P1",
            "statement": "Matched-norm gated updates reduce cross-regime interference more than ungated updates.",
            "observable": "Cross-regime loss change under matched update norm.",
            "expected_pattern": "Lower interference for gated updates at equal norm.",
            "falsifier": "No difference remains after matching update norm and data order.",
            "discriminates_against": ["H2"],
        }],
        "operationalizations": [{
            "construct": "cross-regime interference",
            "variable": "delta_other_regime_loss",
            "role": "primary_outcome",
            "definition": "Change in held-out loss of the non-updated regime after one update block.",
            "measurement_method": "Frozen evaluation script on the held-out regime.",
            "unit": "loss units",
            "timing": "After each prespecified update block.",
        }],
        "evidence_boundary": "The pilot motivates the candidate but does not establish the mechanism.",
        "literature_items": [{"title": "Mechanistic precedent", "url": "https://doi.org/10.1000/mechanism"}],
    }


class HypothesisRoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        _, commit_candidate, _, plan_ideation, register_candidates, _, _ = api()
        plan = plan_ideation(self.root, request_text="Develop and test the mechanism", problem="Boundary adaptation is confounded.")
        item = candidate()
        register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[item])
        method = {key: item[key] for key in ("title", "problem", "mechanism")}
        commit_candidate(self.root, candidate_id="I1", selected_by="user", method=method)

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_hypothesis_preserves_rivals_and_candidate_status(self):
        _, _, _, _, _, register_hypothesis, _ = api()
        result = register_hypothesis(self.root, hypothesis())
        self.assertEqual(result["hypothesis"]["status"], "candidate")
        self.assertEqual(result["hypothesis"]["rivals"][0]["rival_id"], "H2")
        self.assertTrue(result["hypothesis_hash"])
        self.assertNotIn("winner", result)

    def test_rival_prediction_and_falsifier_are_mandatory(self):
        DesignError, _, _, _, _, register_hypothesis, _ = api()
        cases = []
        no_rival = hypothesis(); no_rival["rivals"] = []; cases.append((no_rival, "rival"))
        no_prediction = hypothesis(); no_prediction["predictions"] = []; cases.append((no_prediction, "prediction"))
        no_falsifier = hypothesis(); no_falsifier["predictions"][0].pop("falsifier"); cases.append((no_falsifier, "falsifier"))
        for value, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(DesignError, message):
                register_hypothesis(self.root, value)

    def test_literature_evidence_requires_https_links(self):
        DesignError, _, _, _, _, register_hypothesis, _ = api()
        invalid = hypothesis()
        invalid["literature_items"][0]["url"] = "http://example.org/unlinked"
        with self.assertRaisesRegex(DesignError, "HTTPS"):
            register_hypothesis(self.root, invalid)
        valid = register_hypothesis(self.root, hypothesis())
        self.assertTrue(valid["hypothesis"]["literature_items"][0]["url"].startswith("https://"))

    def test_direct_method_change_makes_hypothesis_stale(self):
        _, _, get_status, _, _, register_hypothesis, register_method = api()
        register_hypothesis(self.root, hypothesis())
        changed = {key: candidate()[key] for key in ("title", "problem", "mechanism")}
        changed["mechanism"] = "A detector gates a separate sparse update with a new schedule."
        register_method(self.root, changed)
        status = get_status(self.root)
        self.assertEqual(status["status"], "STALE_METHOD")
        self.assertFalse(status["ready"])


if __name__ == "__main__":
    unittest.main()
