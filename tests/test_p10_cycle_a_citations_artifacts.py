from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from citation_guard_core import CitationGuardError, verify_and_format_citation  # noqa: E402
from research_artifact_core import (  # noqa: E402
    ArtifactError,
    plan_research_artifact,
    research_artifact_status,
    submit_research_artifact,
)


CROSSREF_ITEM = {
    "DOI": "10.1000/test-doi",
    "type": "journal-article",
    "author": [{"family": "Doe", "given": "Jane"}, {"family": "Li", "given": "Ming"}],
    "title": ["A verified research record"],
    "container-title": ["Journal of Tests"],
    "published": {"date-parts": [[2026]]},
    "volume": "12", "issue": "3", "page": "1-9",
}


class P10CycleACitationTests(unittest.TestCase):
    def test_crossref_verification_precedes_all_four_formatters(self):
        for style in ("apa", "mla", "ieee", "harvard"):
            with self.subTest(style=style), patch("citation_guard_core._crossref", return_value=CROSSREF_ITEM):
                result = verify_and_format_citation("https://doi.org/10.1000/TEST-DOI", style)
                self.assertEqual(result["status"], "PASS")
                self.assertTrue(result["verified"])
                self.assertEqual(result["citation_url"], "https://doi.org/10.1000/test-doi")
                self.assertIn("A verified research record", result["formatted"])

    def test_unverified_or_invalid_records_fail_closed(self):
        with self.assertRaises(CitationGuardError):
            verify_and_format_citation("not-a-doi", "apa")
        with self.assertRaises(CitationGuardError):
            verify_and_format_citation("10.1000/test-doi", "vancouver")

    def test_repository_registry_is_pinned_and_clickable(self):
        registry = json.loads((PLUGIN / "assets" / "research-repositories" / "registry.json").read_text(encoding="utf-8"))
        entries = registry["repositories"]
        self.assertGreaterEqual(len(entries), 18)
        self.assertEqual(len({item["id"] for item in entries}), len(entries))
        for item in entries:
            self.assertTrue(item["url"].startswith("https://"))
            self.assertRegex(item["commit"], r"^[0-9a-f]{40}$")
            self.assertTrue(item["license"])
            self.assertTrue(item["verdict"])


class P10CycleAArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "paper.md").write_text("source paper", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_paper_card_requires_fixed_16_sections_and_https_source(self):
        plan = plan_research_artifact(self.root, "paper_card", "card-v1", ["paper.md"])
        artifact = {
            "source_record": {
                "title": "Paper", "primary_record_url": "https://doi.org/10.1000/test-doi", "verified_metadata": True,
            },
            "locator_mode": "structure-grounded",
            "sections": [
                {"section_id": f"{index:02d}", "heading": f"Section {index}", "content": "Supported or not assessable.", "locators": ["paper.md:section"]}
                for index in range(1, 17)
            ],
        }
        result = submit_research_artifact(self.root, "card-v1", plan["plan_hash"], artifact)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checks"]["section_count"], 16)
        self.assertEqual(research_artifact_status(self.root, "card-v1", verify=True)["status"], "PASS")
        changed = dict(artifact)
        changed["locator_mode"] = "source-limited"
        with self.assertRaises(ArtifactError):
            submit_research_artifact(self.root, "card-v1", plan["plan_hash"], changed)

    def test_systematic_review_keeps_screening_decisions_human_owned(self):
        protocol = {
            "research_question": "What works?", "databases": ["OpenAlex"], "search_strings": ["test"],
            "date_range": "2020-2026", "inclusion_criteria": ["primary study"], "exclusion_criteria": ["duplicate"],
            "deduplication_keys": ["doi"], "screening_stages": ["title", "full text"],
            "reviewer_policy": "two reviewers", "conflict_resolution": "user adjudication",
        }
        plan = plan_research_artifact(self.root, "systematic_review", "review-v1", ["paper.md"], protocol)
        artifact = {
            "records": [{
                "record_id": "r1", "title": "Study", "primary_record_url": "https://doi.org/10.1000/test-doi",
                "decision": "include", "selected_by": "user", "reason": "Meets frozen criteria",
            }],
            "flow_counts": {"include": 1, "exclude": 0, "maybe": 0},
        }
        self.assertEqual(submit_research_artifact(self.root, "review-v1", plan["plan_hash"], artifact)["status"], "PASS")

    def test_source_change_invalidates_artifact(self):
        plan_research_artifact(self.root, "paper_card", "card-change", ["paper.md"])
        (self.root / "paper.md").write_text("changed source paper", encoding="utf-8")
        self.assertEqual(research_artifact_status(self.root, "card-change")["status"], "INVALIDATED")

    def test_experiment_log_separates_raw_measurements_from_interpretation(self):
        plan = plan_research_artifact(
            self.root, "experiment_log", "experiment-v1", ["paper.md"],
            {"experiment_id": "E-001", "objective": "Measure response", "started_at": "2026-08-13T00:00:00Z", "operator": "researcher"},
        )
        artifact = {
            "materials": ["sample-a"], "parameters": {"temperature_c": 25},
            "measurements": [{"name": "response", "value": 1.2, "unit": "a.u.", "recorded_at": "2026-08-13T00:01:00Z", "source_file": "paper.md"}],
            "observations": ["Signal recorded"], "anomalies": [], "interpretations": ["Candidate explanation; not a raw result"],
        }
        result = submit_research_artifact(self.root, "experiment-v1", plan["plan_hash"], artifact)
        self.assertTrue(result["checks"]["raw_interpretation_separated"])

    def test_reviewer_response_cannot_hide_unresolved_user_input(self):
        protocol = {"venue": "ExampleConf", "decision_type": "major revision", "response_mode": "per_reviewer", "length_limit": 5000}
        plan = plan_research_artifact(self.root, "reviewer_response", "response-v1", ["paper.md"], protocol)
        artifact = {"issues": [{
            "issue_id": "R1-C1", "reviewer": "R1", "raw_anchor": "Need another baseline",
            "status": "needs_user_input", "response": "Awaiting a user-confirmed experiment.", "evidence": [],
        }]}
        result = submit_research_artifact(self.root, "response-v1", plan["plan_hash"], artifact)
        self.assertEqual(result["status"], "USER_INPUT_REQUIRED")
        self.assertTrue(result["checks"]["coverage_complete"])
        self.assertFalse(result["checks"]["delivery_ready"])


if __name__ == "__main__":
    unittest.main()
