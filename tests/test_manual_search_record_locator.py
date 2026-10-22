"""Regression from an actual manual-evidence acceptance failure; local inputs only."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from research_guard_core import (GuardError, _normalize_work, register_method,
    refresh_domain, get_search_plan, register_manual_evidence)


class ManualRecordLocatorTests(unittest.TestCase):
    def test_search_urls_never_become_primary_records_without_identifiers(self):
        for url in ["https://dblp.org/search?q=residual", "https://dblp.org/search/publ/api", "https://search.crossref.org/?q=residual", "https://api.crossref.org/works?query=residual"]:
            with self.subTest(url=url):
                result = _normalize_work({"title": "Residual learning", "url": url}, "dblp")
                self.assertEqual(result["link_scope"], "search_fallback")
                self.assertIsNone(result["primary_record_url"])

    def test_record_locators_and_portable_identifiers_remain_primary(self):
        cases = [
            {"primary_record_url": "https://dblp.org/rec/conf/cvpr/HeZRS16"},
            {"url": "https://dblp.org/search?q=residual", "doi": "10.1109/CVPR.2016.90"},
            {"url": "https://arxiv.org/search/?query=residual", "arxiv": "1512.03385"},
            {"url": "https://explore.openaire.eu/search/project?projectId=corda__h2020::example"},
        ]
        for record in cases:
            with self.subTest(record=record):
                self.assertEqual(_normalize_work({"title": "Residual learning", **record}, "dblp")["link_scope"], "primary_record")

    def test_manual_search_page_rejected_record_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            register_method(root, {"title": "Residual learning", "problem": "image recognition", "mechanism": "identity shortcuts"})
            refresh_domain(root, secondary_domains=None, primary_domain="computer_science", selected_by="main_agent", selection_rationale="An explicit computational image-recognition test method.")
            plan = get_search_plan(root)
            (root / "capture.txt").write_text("Explicit local regression capture; no online verification asserted.")
            args = dict(source="dblp", purpose="literature_search", query="Complete test plan", status="hits_present", evidence_path="capture.txt", evidence_url="https://dblp.org/search/publ/api", query_ids=[q["query_id"] for q in plan["query_specs"]])
            with self.assertRaisesRegex(GuardError, "search page is not a primary record"):
                register_manual_evidence(root, **args, records=[{"title": "Residual learning", "url": "https://dblp.org/search?q=residual"}])
            with patch.object(Path, "read_bytes", side_effect=AssertionError("Do not scan captures for hashes")):
                result = register_manual_evidence(root, **args, records=[{"title": "Residual learning", "primary_record_url": "https://dblp.org/rec/conf/cvpr/HeZRS16"}])
            self.assertTrue(result["registered"])
            self.assertEqual(result["evidence"]["records"][0]["link_scope"], "primary_record")


if __name__ == "__main__":
    unittest.main()
