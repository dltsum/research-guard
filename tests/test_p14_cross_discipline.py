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

from discipline_profile_core import analyze_discipline, initialize_discipline, load_registry  # noqa: E402
from intent_router_core import route_prompt  # noqa: E402
from mcp_server import TOOLS  # noqa: E402
from research_guard_core import (  # noqa: E402
    GuardError, get_gate_status, load_state, refresh_domain, register_method, run_novelty_search,
)


def _live_payload(url: str, _attempt_timeout_seconds: float):
    if "api.openalex.org" in url:
        payload = {"results": [{
            "id": "https://openalex.org/W123", "doi": "https://doi.org/10.1234/example",
            "primary_location": {"source": {
                "id": "https://openalex.org/S123", "display_name": "Journal of Chronofabric Studies",
                "issn": ["1234-5678"],
            }},
        }]}
    elif "api.crossref.org" in url:
        payload = {"message": {"items": [{
            "container-title": ["Journal of Chronofabric Studies"], "ISSN": ["1234-5678"],
            "DOI": "10.1234/example",
        }]}}
    elif "doaj.org" in url:
        payload = {"results": [{
            "id": "journal-123", "bibjson": {"title": "Journal of Chronofabric Studies", "pissn": "1234-5678"},
        }]}
    elif "openlibrary.org" in url:
        payload = {"docs": []}
    elif "loc.gov" in url:
        payload = {"results": []}
    else:
        raise AssertionError(f"unexpected live initializer URL: {url}")
    return payload, json.dumps(payload, sort_keys=True).encode("utf-8")


def _method() -> dict:
    return {
        "title": "Phase-aware records for chronofabric entities",
        "problem": "Chronofabric entities lose phase relations between observations",
        "mechanism": "A phase-aware linkage operator preserves relations",
        "contributions": "Versioned chronofabric relation analysis",
    }


class CrossDisciplineP14Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.key = Path(self.temp.name) / "signing.key"
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.key)

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def _initialize_chronofabric(self) -> None:
        with patch("discipline_profile_core._fetch_json", side_effect=_live_payload):
            initialized = initialize_discipline(
                self.root, discipline="chronofabric studies", request_text="Deep research in chronofabric studies",
                broad_domain="humanities", selected_by="main_agent",
                selection_rationale="The main agent selected this unregistered field as a humanities profile.",
                attempt_timeout_seconds=2,
            )
        self.assertEqual(initialized["status"], "PASS")

    def _bind_chronofabric(self) -> None:
        refresh_domain(
            self.root, primary_domain="humanities", secondary_domains=[], selected_by="main_agent",
            selection_rationale="The main agent bound the initialized chronofabric humanities profile.",
            discipline_profile_id="chronofabric-studies",
        )

    def test_registry_covers_broad_and_specialized_fields_with_history_boundaries(self):
        registry = load_registry()
        profiles = {item["id"]: item for item in registry["disciplines"]}
        self.assertGreaterEqual(len(profiles), 21)
        self.assertTrue({
            "computer_science", "engineering", "mathematics_statistics", "natural_science",
            "medicine_life_science", "social_science", "humanities", "history",
        } <= set(profiles))
        history = profiles["history"]
        self.assertTrue({"book", "book_chapter", "critical_edition", "primary_source"} <= set(history["literature_forms"]))
        self.assertTrue(any("archive" in boundary.casefold() for boundary in history["boundaries"]))
        self.assertTrue(all(item["url"].startswith("https://") for item in registry["public_catalogs"].values()))

    def test_unknown_field_requires_explicit_selection_and_initialization(self):
        register_method(self.root, _method())
        with self.assertRaisesRegex(GuardError, "MAIN_AGENT_SELECTION_REQUIRED"):
            run_novelty_search(self.root, fixture_sources={})
        analysis = analyze_discipline(
            self.root, request_text="Deep research in chronofabric studies",
            discipline="chronofabric studies", broad_domain="humanities",
            selected_by="main_agent",
            selection_rationale="The main agent selected this unregistered field as a humanities profile.",
        )
        self.assertEqual(analysis["status"], "INITIALIZATION_REQUIRED")
        self.assertFalse(analysis["automatic_initialization"])
        self._initialize_chronofabric()
        self._bind_chronofabric()
        state = load_state(self.root)
        binding = state["search_plan"]["discipline_profile"]
        self.assertFalse(binding["initialization_required"])
        self.assertEqual(binding["live_profile_status"], "PASS")
        fixtures = {source: [] for source in state["search_plan"]["required_sources"]}
        searched = run_novelty_search(self.root, fixture_sources=fixtures)
        self.assertEqual(searched["report"]["gate_status"], "PASS")
        self.assertTrue(searched["report"]["discipline_journal_watchlist"])

    def test_bound_discipline_evidence_tamper_invalidates_collision_receipt(self):
        register_method(self.root, _method())
        self._initialize_chronofabric()
        self._bind_chronofabric()
        state = load_state(self.root)
        run_novelty_search(
            self.root, fixture_sources={source: [] for source in state["search_plan"]["required_sources"]},
        )
        profile_path = self.root / state["search_plan"]["discipline_profile"]["live_profile_path"]
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        evidence_path = self.root / profile["source_runs"][0]["evidence_path"]
        evidence_path.write_text("{}\n", encoding="utf-8")
        gate = get_gate_status(self.root)
        self.assertEqual(gate["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        self.assertTrue(gate["discipline_profile_errors"])
        self.assertIsNone(gate["current_receipt"])

    def test_history_fixture_extracts_books_and_primary_sources_without_claiming_live_pass(self):
        fixtures = {
            "openalex": _live_payload("https://api.openalex.org", 1)[0],
            "crossref": _live_payload("https://api.crossref.org", 1)[0],
            "doaj": _live_payload("https://doaj.org", 1)[0],
            "openlibrary": {"docs": [{
                "key": "/works/OL1W", "title": "A History of Archives",
                "author_name": ["A. Historian"], "first_publish_year": 1990,
            }]},
            "library_of_congress": {"results": [{
                "id": "https://www.loc.gov/item/123/", "title": "Archive collection",
                "date": "1901", "original_format": ["manuscript/mixed material"],
            }]},
        }
        result = initialize_discipline(
            self.root, discipline="history", request_text="modern history", selected_by="main_agent",
            selection_rationale="The main agent explicitly selected the registered history profile.",
            fixture_sources=fixtures,
        )
        self.assertEqual(result["status"], "FIXTURE_ONLY")
        self.assertFalse(result["profile"]["admissible_for_novelty"])
        self.assertTrue(result["profile"]["book_candidates"])
        self.assertTrue(result["profile"]["primary_source_candidates"])

    def test_existing_mcp_surface_has_typed_explicit_discipline_subroute(self):
        self.assertEqual(len(TOOLS), 17)
        tool = next(item for item in TOOLS if item["name"] == "research_design")
        properties = tool["inputSchema"]["properties"]
        self.assertEqual(properties["discipline_action"]["enum"], ["analyze", "initialize", "status", "verify"])
        self.assertIn("discipline", properties)
        self.assertIn("discipline_selected_by", properties)

    def test_router_never_classifies_history_text(self):
        for prompt in (
            "I want to research history and search literature", "I like history games",
            "Write a family history story", "历史游戏里哪个角色最好？",
        ):
            with self.subTest(prompt=prompt):
                routed = route_prompt(prompt)
                self.assertEqual(routed["status"], "MAIN_AGENT_SELECTION_REQUIRED")
                self.assertEqual(routed["selected_modules"], [])


if __name__ == "__main__":
    unittest.main()
