from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from mcp_server import handle  # noqa: E402
from research_guard_core import (  # noqa: E402
    classify_domain,
    list_sources,
    load_state,
    register_method,
    refresh_domain,
    run_novelty_search,
    search_clinicaltrials,
    search_openaire,
    search_zenodo,
)


def sample_method():
    return {
        "title": "Graph retrieval for long horizon language model agents",
        "problem": "Language model agents retrieve irrelevant memory during long tasks",
        "mechanism": "A confidence gate selects graph connected episodic memory",
        "contributions": "adaptive graph memory retrieval",
    }


class OpenSourceCatalogRoundFiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.key = Path(self.temp.name) / "key.bin"
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.key)

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def select_computer_science(self):
        return refresh_domain(
            self.root,
            primary_domain="computer_science",
            secondary_domains=[],
            selected_by="main_agent",
            selection_rationale=(
                "The main agent selected computer science because the registered method concerns "
                "language-model agents, graph retrieval, and long-horizon memory."
            ),
        )

    def test_catalog_has_unique_ids_and_direct_urls(self):
        sources = list_sources()
        ids = [source["id"] for source in sources]
        self.assertGreaterEqual(len(sources), 30)
        self.assertEqual(len(ids), len(set(ids)))
        for source in sources:
            self.assertTrue(str(source["search_url"]).startswith(("http://", "https://")))
            self.assertTrue(str(source["docs_url"]).startswith(("http://", "https://")))

    def test_no_registration_api_filter_includes_current_openalex_and_doaj_routes(self):
        sources = list_sources(access="no_registration", automation="public_api")
        ids = {source["id"] for source in sources}
        self.assertTrue({"crossref", "arxiv", "pubmed", "europe_pmc", "datacite", "dblp", "hal", "openaire"} <= ids)
        self.assertTrue({"openalex", "doaj"} <= ids)

    def test_domain_route_separates_required_supplemental_and_manual(self):
        profile = classify_domain(
            primary_domain="social_science",
            secondary_domains=[],
            selected_by="main_agent",
            selection_rationale=(
                "The main agent selected social science because the topic concerns education policy, "
                "social governance, and communication outcomes."
            ),
        )
        self.assertFalse(set(profile["required_sources"]) & set(profile["supplemental_sources"]))
        self.assertIn("ncpssd", profile["manual_sources"])
        self.assertIn("cssci", profile["manual_sources"])

    def test_supplemental_gap_is_recorded_without_claiming_it_was_searched(self):
        register_method(self.root, sample_method())
        self.select_computer_science()
        state = load_state(self.root)
        fixtures = {source: [] for source in state["search_plan"]["required_sources"]}
        result = run_novelty_search(self.root, fixture_sources=fixtures)
        report = result["report"]
        self.assertEqual(report["gate_status"], "PASS")
        self.assertTrue(report["supplemental_gaps"])
        for source in report["supplemental_gaps"]:
            self.assertEqual(report["coverage"][source]["status"], "not_tested")
            self.assertEqual(report["coverage"][source]["tier"], "supplemental")
        self.assertIn("Supplemental gaps recorded", report["gate_reason"])

    def test_user_named_indexes_are_promoted_to_hard_coverage(self):
        method = sample_method()
        method["required_sources"] = ["SCI", "SSCI", "CCF", "IEEE", "CSSCI", "C刊"]
        register_method(self.root, method)
        self.select_computer_science()
        plan = load_state(self.root)["search_plan"]
        expected = {"wos_sci", "wos_ssci", "ccf", "ieee", "cssci", "c_journal"}
        self.assertTrue(expected <= set(plan["user_required_sources"]))
        fixtures = {source: [] for source in plan["required_sources"] if source != "ccf"}
        result = run_novelty_search(self.root, fixture_sources=fixtures)
        self.assertEqual(result["status"], "ACTION_REQUIRED")
        self.assertTrue(result["required_failed_units"])
        self.assertTrue(
            any(item["source"] == "ccf" and item["status"] == "error" for item in result["stage_results"])
        )

    def test_mcp_and_cli_expose_catalog_filters(self):
        response = handle({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "list_sources", "arguments": {"domain": "computer_science"}},
        })
        self.assertFalse(response["result"]["isError"])
        self.assertTrue(response["result"]["structuredContent"])
        completed = subprocess.run(
            [sys.executable, str(PLUGIN / "scripts" / "researchctl.py"), "sources", "--access", "no_registration"],
            text=True, encoding="utf-8", capture_output=True, timeout=15,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"crossref"', completed.stdout)

    def test_live_open_apis_cover_graph_repository_and_registry(self):
        checks = (
            (search_openaire, "transformer", "openaire"),
            (search_zenodo, "transformer", "zenodo"),
            (search_clinicaltrials, "Alzheimer", "clinicaltrials"),
        )
        for searcher, query, source in checks:
            with self.subTest(source=source):
                works = searcher(query, 1, 40)
                self.assertTrue(works)
                self.assertIn(source, works[0]["sources"])
                self.assertTrue(works[0]["title"])


if __name__ == "__main__":
    unittest.main()
