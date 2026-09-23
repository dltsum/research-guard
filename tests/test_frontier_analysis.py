from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from frontier_analysis_core import (  # noqa: E402
    FrontierAnalysisError,
    frontier_status,
    run_frontier_analysis,
)


def work(work_id: str, year: int, keywords: list[str], references: list[str] | None = None) -> dict:
    return {"work_id": work_id, "year": year, "title": work_id, "keywords": keywords, "references": references or []}


def corpus() -> list[dict]:
    works = []
    # Background works in every year keep per-year denominators comparable.
    for year in range(2018, 2025):
        for index in range(6):
            works.append(work(f"W-bg-{year}-{index}", year, ["pedagogy" if index % 2 == 0 else "assessment"]))
    # Established topic: learning analytics at a steady background rate.
    for year in range(2018, 2025):
        works.append(work(f"W-la-{year}", year, ["learning analytics", "education"]))
    # Burst topic: generative ai concentrated in the most recent years.
    for index in range(20):
        works.append(work(f"W-new-{index}", 2023 + index % 2, ["generative ai", "education", "llm feedback"]))
    # Bridge works so "education" connects both clusters structurally.
    works.append(work("W-bridge-1", 2022, ["learning analytics", "generative ai", "education"],
                      references=["R1", "R2"]))
    works.append(work("W-bridge-2", 2024, ["learning analytics", "llm feedback"], references=["R1", "R3"]))
    works.append(work("W-bridge-3", 2024, ["generative ai", "llm feedback"], references=["R1", "R2"]))
    return works


class FrontierAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_cooccurrence_burst_and_centrality_pipeline(self) -> None:
        result = run_frontier_analysis(
            self.root, corpus(), analysis_id="A1", min_cooccurrence=2, burst_window_years=3,
        )
        self.assertEqual(result["work_count"], len(corpus()))
        self.assertEqual(result["year_range"], [2018, 2024])
        self.assertTrue(result["analysis_hash"])

        graph = result["keyword_graph"]
        self.assertGreater(graph["node_count"], 0)
        weights = {(tuple(edge["pair"])): edge["weight"] for edge in graph["top_edges"]}
        # "generative ai" co-occurs with "education" in every W-new work.
        self.assertTrue(
            weights.get(("education", "generative ai"), 0) >= 8,
            f"expected strong education x generative ai edge, got {weights}",
        )

        recent_bursts = [b for b in result["bursts"] if b["recent"]]
        burst_keywords = {b["keyword"] for b in recent_bursts}
        self.assertIn("generative ai", burst_keywords)
        self.assertNotIn("learning analytics", burst_keywords)

        frontier_keywords = [item["keyword"] for item in result["frontier"]]
        # Both burst topics must lead the frontier; background terms must not.
        self.assertIn("generative ai", frontier_keywords[:3])
        self.assertIn("llm feedback", frontier_keywords[:3])
        self.assertNotIn("pedagogy", frontier_keywords[:3])
        frontier_map = {item["keyword"]: item for item in result["frontier"]}
        # The bridge keyword "education" must carry structural centrality.
        self.assertGreater(frontier_map["education"]["betweenness"], 0.0)

        cocitation_pairs = {tuple(pair["pair"]) for pair in result["cocitation_graph"]["top_pairs"]}
        self.assertIn(("R1", "R2"), cocitation_pairs)

        status = frontier_status(self.root)
        self.assertEqual(status["status"], "PASS")
        self.assertEqual(status["analysis_hash"], result["analysis_hash"])

    def test_deterministic_repeated_runs_match_hash(self) -> None:
        first = run_frontier_analysis(self.root, corpus(), analysis_id="A1")
        second = run_frontier_analysis(self.root, corpus(), analysis_id="A1")
        self.assertEqual(first["analysis_hash"], second["analysis_hash"])

    def test_mcp_exposes_frontier_analysis_on_research_design(self) -> None:
        import mcp_server

        tools = [item for item in mcp_server.TOOLS if item["name"] == "research_design"]
        self.assertEqual(len(tools), 1)
        properties = tools[0]["inputSchema"]["properties"]
        self.assertEqual(properties["frontier_analysis_action"]["enum"], ["analyze", "status"])
        result = mcp_server.dispatch("research_design", {
            "action": "status",
            "project_root": str(self.root),
            "frontier_analysis_action": "analyze",
            "frontier_analysis_id": "A1",
            "frontier_works": corpus(),
        })
        self.assertEqual(result["analysis_id"], "A1")
        self.assertEqual(result["work_count"], len(corpus()))

    def test_status_without_analysis_fails_closed(self) -> None:
        self.assertEqual(frontier_status(self.root)["status"], "FRONTIER_ANALYSIS_REQUIRED")

    def test_malformed_works_rejected(self) -> None:
        with self.assertRaises(FrontierAnalysisError):
            run_frontier_analysis(self.root, [], analysis_id="A1")
        with self.assertRaisesRegex(FrontierAnalysisError, "work_id"):
            run_frontier_analysis(self.root, [{"year": 2020}], analysis_id="A1")
        with self.assertRaisesRegex(FrontierAnalysisError, "year"):
            run_frontier_analysis(self.root, [work("W1", 1800, ["a"])], analysis_id="A1")
        with self.assertRaisesRegex(FrontierAnalysisError, "duplicates"):
            run_frontier_analysis(self.root, [work("W1", 2020, ["a"]), work("W1", 2021, ["b"])], analysis_id="A1")
        with self.assertRaisesRegex(FrontierAnalysisError, "keywords"):
            run_frontier_analysis(self.root, [work("W1", 2020, ["  "])], analysis_id="A1")


if __name__ == "__main__":
    unittest.main()
