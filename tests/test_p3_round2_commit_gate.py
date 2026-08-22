from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]


def api():
    import sys

    sys.path.insert(0, str(PLUGIN / "scripts"))
    from research_design_core import DesignError, commit_candidate, get_research_design_status, plan_ideation, register_candidates
    from research_guard_core import load_state, save_state

    return DesignError, commit_candidate, get_research_design_status, plan_ideation, register_candidates, load_state, save_state


def candidate(candidate_id: str, mechanism: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "title": f"Selected method {candidate_id}",
        "problem": "Existing methods confound boundary detection with adaptation.",
        "mechanism": mechanism,
        "falsifier": "Matched controls show no boundary-specific effect.",
        "minimum_viable_experiment": "Run a matched two-boundary comparison.",
        "differentiator": "Separates boundary detection from the update.",
        "feasibility": "Fits the declared resource budget.",
        "lens_id": "boundary_probe",
        "prior_work": [{"title": "Primary prior work", "url": "https://doi.org/10.1000/prior"}],
    }


def method(item: dict) -> dict:
    return {key: item[key] for key in ("title", "problem", "mechanism")}


class CommitGateRoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        _, _, _, plan_ideation, register_candidates, _, _ = api()
        self.plan = plan_ideation(
            self.root,
            request_text="Develop a boundary-specific update",
            problem="Existing methods confound boundary detection with adaptation.",
        )
        self.c1 = candidate("I1", "Detect the boundary, then apply a separated low-rank update.")
        self.c2 = candidate("I2", "Detect the boundary, then apply a separated sparse update.")
        register_candidates(self.root, plan_hash=self.plan["plan_hash"], candidates=[self.c1, self.c2])

    def tearDown(self):
        self.temp.cleanup()

    def test_commit_requires_explicit_user_selection(self):
        DesignError, commit_candidate, *_ = api()
        with self.assertRaisesRegex(DesignError, "selected_by"):
            commit_candidate(self.root, candidate_id="I1", selected_by="assistant", method=method(self.c1))

    def test_first_commit_enters_the_existing_novelty_gate(self):
        _, commit_candidate, _, _, _, load_state, _ = api()
        result = commit_candidate(self.root, candidate_id="I1", selected_by="user", method=method(self.c1))
        state = load_state(self.root)
        self.assertEqual(state["gate"]["status"], "DOMAIN_SELECTION_REQUIRED")
        self.assertEqual(result["method_hash"], state["active_method"]["hash"])
        self.assertEqual(state["active_method"]["payload"]["design_candidate_id"], "I1")
        self.assertEqual(state["active_method"]["payload"]["design_candidate_hash"], result["candidate_hash"])

    def test_changed_commit_invalidates_prior_report_and_receipt(self):
        _, commit_candidate, _, _, _, load_state, save_state = api()
        first = commit_candidate(self.root, candidate_id="I1", selected_by="user", method=method(self.c1))
        state = load_state(self.root)
        state["gate"] = {"status": "PASS", "reason": "fixture", "updated_at": "2026-08-12T00:00:00Z"}
        state["latest_report"] = ".research-guard/reports/old.json"
        state["current_receipt"] = ".research-guard/receipts/old.json"
        save_state(self.root, state)
        second = commit_candidate(self.root, candidate_id="I2", selected_by="user", method=method(self.c2))
        changed = load_state(self.root)
        self.assertNotEqual(first["method_hash"], second["method_hash"])
        self.assertEqual(changed["active_method"]["version"], 2)
        self.assertEqual(changed["gate"]["status"], "DOMAIN_SELECTION_REQUIRED")
        self.assertIsNone(changed["latest_report"])
        self.assertIsNone(changed["current_receipt"])

    def test_unknown_candidate_cannot_be_committed(self):
        DesignError, commit_candidate, *_ = api()
        with self.assertRaisesRegex(DesignError, "Unknown candidate"):
            commit_candidate(self.root, candidate_id="missing", selected_by="user", method=method(self.c1))


if __name__ == "__main__":
    unittest.main()
