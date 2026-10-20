from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_guard_core import GuardError, get_search_plan, load_state, refresh_domain, register_method, save_state


QUERIES = [
    {"text": "robot imitation learning evaluation reproducibility", "components": ["problem"],
     "rationale": "Retrieve prior work on reproducibility of robot policy evaluation."},
    {"text": "paired checkpoint comparison matched initial states", "components": ["mechanism", "evaluation"],
     "rationale": "Retrieve the paired comparison mechanism without local file names."},
    {"text": "robot policy training seed evaluation coverage", "components": ["contributions"],
     "rationale": "Retrieve work on seed and evaluation coverage as an audit contribution."},
]


class CuratedSearchPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        register_method(self.root, {"title": "Historical robot checkpoint audit", "problem": "Robot policy reproducibility",
                                   "mechanism": "Use inputs/experiment-cells.csv then compare paired checkpoints"})
        refresh_domain(self.root, primary_domain="computer_science", secondary_domains=[], selected_by="main_agent",
                       selection_rationale="Main agent chose computing for this robot evaluation audit.")

    def tearDown(self):
        self.temp.cleanup()

    def test_semantic_queries_persist_with_method_binding_and_original_unchanged(self):
        before = load_state(self.root)
        plan = get_search_plan(self.root, query_specs=QUERIES)
        self.assertEqual(plan["queries"], [q["text"] for q in QUERIES])
        self.assertEqual(get_search_plan(self.root), plan)
        self.assertEqual(plan["method_hash"], before["active_method"]["hash"])
        self.assertEqual(load_state(self.root)["active_method"], before["active_method"])
        self.assertEqual(plan["query_generation"], "agent_curated")

    def test_changed_queries_invalidate_previous_search_and_manual_evidence(self):
        state = load_state(self.root)
        for key in ("manual_evidence", "collision_resolutions", "latest_report", "current_receipt", "current_search"):
            state[key] = {"old": "must be invalidated"}
        save_state(self.root, state)
        get_search_plan(self.root, query_specs=QUERIES)
        changed = load_state(self.root)
        self.assertEqual(changed["manual_evidence"], {})
        self.assertEqual(changed["collision_resolutions"], {})
        for key in ("latest_report", "current_receipt", "current_search"):
            self.assertIsNone(changed[key])
        self.assertEqual(changed["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        changed["manual_evidence"] = {"new": "keep for identical plan"}
        save_state(self.root, changed)
        get_search_plan(self.root, query_specs=QUERIES)
        self.assertEqual(load_state(self.root)["manual_evidence"], changed["manual_evidence"])

    def test_bad_or_unmapped_queries_are_rejected_without_state_mutation(self):
        baseline = load_state(self.root)
        bad_sets = [QUERIES[:1], [QUERIES[0]] * 3,
                    [{**q, "components": ["invented"]} for q in QUERIES],
                    [{**q, "text": "inputs/experiment-cells.csv"} for q in QUERIES],
                    [{**q, "rationale": ""} for q in QUERIES]]
        for queries in bad_sets:
            with self.subTest(queries=queries), self.assertRaises(GuardError):
                get_search_plan(self.root, query_specs=queries)
            self.assertEqual(load_state(self.root), baseline)


if __name__ == "__main__":
    unittest.main()
