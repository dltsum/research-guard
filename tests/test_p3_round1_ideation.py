from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


def api():
    import sys

    plugin = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(plugin / "scripts"))
    from research_design_core import DesignError, plan_ideation, register_candidates

    return DesignError, plan_ideation, register_candidates


def candidate(candidate_id: str, *, title: str | None = None, mechanism: str | None = None) -> dict:
    return {
        "candidate_id": candidate_id,
        "title": title or f"Boundary-aware model {candidate_id}",
        "problem": "Current models fail when the deployment distribution crosses a known boundary.",
        "mechanism": mechanism or f"Use a boundary-conditioned update mechanism {candidate_id}.",
        "falsifier": "No gain appears at the boundary under matched compute and data.",
        "minimum_viable_experiment": "Compare the mechanism with a matched baseline on two boundary shifts.",
        "differentiator": "The update is conditioned on an explicit boundary variable.",
        "feasibility": "Uses the existing dataset and one small controlled run.",
        "lens_id": "boundary_probe",
        "prior_work": [{"title": "Related primary record", "url": "https://doi.org/10.1000/example"}],
    }


class IdeationRoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def plan(self):
        _, plan_ideation, _ = api()
        return plan_ideation(
            self.root,
            request_text="Explore a simpler boundary-robust mechanism under a strict compute constraint",
            problem="Models fail at distribution boundaries and the mechanism may be over-complex.",
            constraints=["one GPU-equivalent run", "no new private data"],
        )

    def test_router_is_deterministic_and_selects_only_two_or_three_lenses(self):
        first = self.plan()
        second = self.plan()
        self.assertEqual(first["plan_hash"], second["plan_hash"])
        self.assertIn(len(first["selected_lenses"]), {2, 3})
        self.assertEqual(len({item["lens_id"] for item in first["selected_lenses"]}), len(first["selected_lenses"]))
        self.assertEqual(first["effort_cap"], "high")

    def test_candidate_contract_fails_closed(self):
        DesignError, _, register_candidates = api()
        plan = self.plan()
        invalid = candidate("I1")
        invalid.pop("falsifier")
        with self.assertRaisesRegex(DesignError, "falsifier"):
            register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[invalid])

    def test_mechanical_duplicates_are_removed_without_ranking(self):
        _, _, register_candidates = api()
        plan = self.plan()
        first = candidate("I1", title="Boundary Model!", mechanism="Use boundary-conditioned updates.")
        duplicate = candidate("I2", title="boundary model", mechanism="use boundary conditioned updates")
        third = candidate("I3")
        result = register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[first, duplicate, third])
        self.assertEqual([item["candidate_id"] for item in result["candidates"]], ["I1", "I3"])
        self.assertEqual(result["duplicates"], [{"duplicate_id": "I2", "kept_id": "I1"}])
        self.assertNotIn("winner", result)
        self.assertNotIn("ranking", result)
        self.assertFalse(any("score" in item or "rank" in item for item in result["candidates"]))

    def test_every_prior_work_item_requires_clickable_https(self):
        DesignError, _, register_candidates = api()
        plan = self.plan()
        invalid = candidate("I1")
        invalid["prior_work"] = [{"title": "Unlinked title", "url": "http://example.org/paper"}]
        with self.assertRaisesRegex(DesignError, "HTTPS"):
            register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[invalid])
        valid = candidate("I1")
        result = register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[valid])
        self.assertTrue(result["candidates"][0]["prior_work"][0]["url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
