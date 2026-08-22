from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from paper_audit_core import AuditError, plan_paper_audit, submit_paper_audit  # noqa: E402
from research_guard_core import _normalize_work, verify_publication  # noqa: E402


class LiteratureHyperlinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def reports(self, plan):
        return [{"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "1 = 1", "status": "verified"}]} for role in plan["selected_roles"]]

    def plan(self, request_text, *, literature=False):
        return plan_paper_audit(
            self.root,
            request_text,
            selected_roles=(
                ["domain_literature", "adversarial_logic"]
                if literature else ["methodology_statistics", "adversarial_logic"]
            ),
            audit_features={"literature": literature},
            selected_by="main_agent",
            selection_rationale="The main agent selected two roles that cover the requested evidence and link checks.",
        )

    def test_doi_normalization_emits_clickable_https_link(self):
        work = _normalize_work({"title": "A paper", "doi": "10.1000/example"}, "crossref")
        self.assertEqual(work["citation_url"], "https://doi.org/10.1000/example")
        self.assertTrue(all(item["url"].startswith("https://") for item in work["citation_links"]))

    def test_title_only_work_emits_clickable_search_link(self):
        work = _normalize_work({"title": "A title only record"}, "manual")
        self.assertTrue(work["citation_url"].startswith("https://"))
        self.assertIsNone(work["primary_record_url"])
        self.assertEqual(work["link_scope"], "search_fallback")
        self.assertIn("citation_links", work)

    def test_publication_verifier_always_returns_clickable_lookup_link(self):
        result = verify_publication("not-a-doi")
        self.assertTrue(result["citation_url"].startswith("https://"))
        self.assertTrue(result["citation_links"])

    def test_literature_output_without_link_fails_closed(self):
        plan = self.plan("Analyze literature and citations", literature=True)
        with self.assertRaises(AuditError):
            submit_paper_audit(
                self.root,
                role_reports=self.reports(plan),
                online_checks=[{"claim": "venue policy", "url": "https://example.org/policy", "accessed_at": "2026-08-11T00:00:00Z", "source_type": "official", "status": "verified"}],
                literature_items=[{"title": "Unlinked prior work"}],
            )

    def test_non_https_online_check_fails_closed(self):
        plan = self.plan("Audit the manuscript")
        with self.assertRaises(AuditError):
            submit_paper_audit(
                self.root,
                role_reports=self.reports(plan),
                online_checks=[{"claim": "current rule", "url": "http://example.org", "accessed_at": "2026-08-11", "source_type": "official", "status": "verified"}],
            )

    def test_linked_literature_is_preserved_in_receipt(self):
        plan = self.plan("Analyze literature and citations", literature=True)
        result = submit_paper_audit(
            self.root,
            role_reports=self.reports(plan),
            online_checks=[{"claim": "current source", "url": "https://example.org/current", "accessed_at": "2026-08-11T00:00:00Z", "source_type": "official", "status": "verified"}],
            literature_items=[{"title": "Linked work", "citation_url": "https://doi.org/10.1000/linked"}],
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["literature_items"][0]["citation_url"], "https://doi.org/10.1000/linked")


if __name__ == "__main__":
    unittest.main()
