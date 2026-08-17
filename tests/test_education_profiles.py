from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from discipline_profile_core import analyze_discipline, load_registry, resolve_discipline_overlay  # noqa: E402
from research_guard_core import DOMAIN_ROUTES, make_search_plan, search_eric  # noqa: E402


class EducationProfileTests(unittest.TestCase):
    def test_education_and_educational_technology_have_distinct_contracts(self) -> None:
        registry = load_registry()
        profiles = {item["id"]: item for item in registry["disciplines"]}
        self.assertIn("education", profiles)
        self.assertIn("educational_technology", profiles)
        education = profiles["education"]
        technology = profiles["educational_technology"]
        self.assertIn("psychometrics classical test theory and IRT", education["method_families"])
        self.assertIn("learning analytics and process mining", technology["method_families"])
        self.assertIn("isls", technology["venue_families"])
        self.assertIn("aera_annual_meeting", education["venue_families"])
        self.assertTrue(all(item["url"].startswith("https://") for item in registry["venue_resources"].values()))

    def test_main_agent_selection_exposes_official_resources_without_auto_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = analyze_discipline(
                temporary, request_text="analyze a learning analytics intervention",
                discipline="educational technology", selected_by="main_agent",
                selection_rationale="The main agent selected educational technology because the claim concerns a learning platform.",
            )
            self.assertEqual(result["detected"]["profile_id"], "educational_technology")
            overlay = resolve_discipline_overlay(temporary, profile_id="educational_technology")
            self.assertGreaterEqual(len(overlay["venue_families"]), 10)
            self.assertGreaterEqual(len(overlay["research_methods"]), 3)
            self.assertGreaterEqual(len(overlay["data_sources"]), 4)
            self.assertIn("learning analytics and process mining", overlay["method_families"])
            self.assertTrue(all(item["url"].startswith("https://") for item in overlay["venue_families"]))
            self.assertTrue(all("exact current venue requirements" in item["interpretation"] for item in overlay["venue_families"]))

    def test_education_overlay_extends_collision_plan_and_eric_records_keep_official_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            overlay = resolve_discipline_overlay(temporary, profile_id="education")
            profile = {
                "primary": "social_science", "secondary": [],
                **DOMAIN_ROUTES["social_science"],
            }
            plan = make_search_plan({
                "title": "Scaffold timing", "problem": "Learners receive mistimed scaffolds",
                "mechanism": "A mastery-sensitive policy changes scaffold timing",
            }, profile, overlay)
            self.assertIn("eric", plan["required_sources"])
            self.assertTrue(plan["discipline_venue_families"])
            self.assertIn("psychometrics classical test theory and IRT", plan["discipline_method_families"])
        payload = {"response": {"docs": [{
            "id": "EJ1234567", "title": "Adaptive Scaffolding in Classrooms",
            "publicationdateyear": 2025, "source": "Journal of Learning Research",
            "description": "A cluster-aware classroom study.", "author": ["A. Author"],
            "publicationtype": ["Journal Articles"],
        }]}}
        with patch("research_guard_core._json_request", return_value=payload):
            records = search_eric("adaptive scaffolding", 10, 2)
        self.assertEqual(records[0]["primary_record_url"], "https://eric.ed.gov/?id=EJ1234567")
        self.assertEqual(records[0]["sources"], ["eric"])


if __name__ == "__main__":
    unittest.main()
