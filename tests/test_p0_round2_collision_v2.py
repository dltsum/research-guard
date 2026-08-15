from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import deduplicate, load_state, register_method, run_novelty_search, score_collisions  # noqa: E402


def method(**changes):
    value = {
        "title": "Counterfactual routing for medical retrieval agents",
        "problem": "Clinical agents retrieve stale evidence during longitudinal diagnosis",
        "mechanism": "A counterfactual confidence router selects temporal evidence graphs",
        "contributions": ["counterfactual router", "temporal evidence graph"],
        "datasets": ["longitudinal clinical records"],
        "evaluation": ["diagnostic calibration", "evidence freshness"],
        "aliases": ["causal routing", "time aware evidence selection"],
    }
    value.update(changes)
    return value


class CollisionV2RoundTwoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(Path(self.temp.name) / "key.bin")
        register_method(self.root, method())

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def test_aliases_and_components_enter_query_compiler(self):
        specs = load_state(self.root)["search_plan"]["query_specs"]
        text = " ".join(item["text"] for item in specs).lower()
        self.assertIn("causal routing", text)
        self.assertIn("longitudinal clinical records", text)
        self.assertIn("diagnostic calibration", text)

    def test_component_reordered_collision_exposes_deterministic_features(self):
        work = {
            "title": "Temporal evidence graphs with confidence based counterfactual routing",
            "abstract": "We select fresh longitudinal clinical evidence for calibrated diagnosis.",
            "sources": ["fixture"],
            "matched_query_ids": ["q-problem-mechanism", "q-mechanism-dataset"],
        }
        scored = score_collisions(method(), [work], {"potential": 0.28, "high": 0.58})[0]
        self.assertIn(scored["collision_level"], {"POTENTIAL", "HIGH"})
        features = scored["collision_features"]
        self.assertGreater(features["component_coverage"], 0)
        self.assertGreater(features["text_vector_similarity"], 0)
        self.assertGreater(features["query_diversity"], 0)
        self.assertTrue(scored["collision_id"])

    def test_citation_neighbor_titles_contribute_graph_signal(self):
        work = {
            "title": "A broad survey of retrieval systems",
            "abstract": "Background review.",
            "sources": ["semantic_scholar"],
            "citation_neighbors": [
                {"paper_id": "n1", "title": "Counterfactual confidence routing over temporal clinical evidence graphs"}
            ],
        }
        scored = score_collisions(method(), [work], {"potential": 0.2, "high": 0.65})[0]
        self.assertGreater(scored["collision_features"]["citation_neighbor_similarity"], 0.45)

    def test_dedup_merges_identifiers_queries_evidence_and_graph(self):
        works = deduplicate([
            {
                "title": "Same work", "doi": "10.1000/same", "sources": ["a"],
                "identifiers": {"pmid": "123"}, "matched_query_ids": ["q1"],
                "evidence_refs": ["e1"], "citation_neighbors": [{"paper_id": "n1", "title": "N1"}],
            },
            {
                "title": "Same work expanded", "doi": "10.1000/same", "sources": ["b"],
                "identifiers": {"semantic_scholar": "s2"}, "matched_query_ids": ["q2"],
                "evidence_refs": ["e2"], "citation_neighbors": [{"paper_id": "n2", "title": "N2"}],
            },
        ])
        self.assertEqual(len(works), 1)
        self.assertEqual(works[0]["sources"], ["a", "b"])
        self.assertEqual(works[0]["matched_query_ids"], ["q1", "q2"])
        self.assertEqual(works[0]["evidence_refs"], ["e1", "e2"])
        self.assertEqual(set(works[0]["identifiers"]), {"doi", "pmid", "semantic_scholar"})
        self.assertEqual(len(works[0]["citation_neighbors"]), 2)

    def test_report_preserves_all_query_specs_and_matches(self):
        state = load_state(self.root)
        fixtures = {source: [] for source in state["search_plan"]["required_sources"]}
        source = next(iter(fixtures))
        fixtures[source] = [{
            "title": "Counterfactual routing for temporal clinical evidence graphs",
            "abstract": "Confidence selection for stale longitudinal evidence.",
        }]
        report = run_novelty_search(self.root, fixture_sources=fixtures)["report"]
        self.assertEqual(report["queries"], [item["text"] for item in report["query_specs"]])
        candidate = report["collision_candidates"][0]
        self.assertEqual(set(candidate["matched_query_ids"]), {item["query_id"] for item in report["query_specs"]})


if __name__ == "__main__":
    unittest.main()
