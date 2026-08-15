from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import (  # noqa: E402
    GuardError,
    SourceAccessError,
    deduplicate,
    load_state,
    register_method,
    run_novelty_search,
    search_arxiv,
    search_crossref,
    search_datacite,
    search_dblp,
    search_europe_pmc,
    search_hal,
    search_ieee,
    search_manual_only,
    search_openalex,
    search_pubmed,
    search_wos,
    verify_publication,
)


def cs_method(**changes):
    value = {
        "title": "Sparse attention for efficient transformer inference",
        "problem": "Transformer inference has quadratic attention cost",
        "mechanism": "A learned sparse attention mask selects tokens before decoding",
        "contributions": "adaptive token selection for efficient inference",
    }
    value.update(changes)
    return value


class LiveAndAdversarialRoundThreeTests(unittest.TestCase):
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

    def fixtures(self):
        return {source: [] for source in load_state(self.root)["search_plan"]["required_sources"]}

    def test_live_crossref_returns_attributed_metadata(self):
        works = search_crossref("attention is all you need", 3, 30)
        self.assertTrue(works)
        self.assertIn("crossref", works[0]["sources"])
        self.assertTrue(works[0]["title"])

    def test_live_arxiv_returns_attributed_preprints(self):
        try:
            works = search_arxiv("transformer attention", 3, 20)
        except SourceAccessError as exc:
            self.assertIn("export.arxiv.org", str(exc))
            self.assertRegex(str(exc), r"HTTP \d+|transport failure")
        else:
            self.assertTrue(works)
            self.assertIn("arxiv", works[0]["sources"])
            self.assertEqual(works[0]["venue"], "arXiv")

    def test_live_pubmed_returns_attributed_biomedical_records(self):
        works = search_pubmed("CRISPR genome editing", 3, 30)
        self.assertTrue(works)
        self.assertIn("pubmed", works[0]["sources"])
        self.assertTrue(works[0]["url"].startswith("https://pubmed.ncbi.nlm.nih.gov/"))

    def test_live_anonymous_open_sources_return_attributed_records(self):
        checks = (
            (search_europe_pmc, "CRISPR genome editing", "europe_pmc"),
            (search_datacite, "transformer", "datacite"),
            (search_dblp, "transformer", "dblp"),
            (search_hal, "transformer", "hal"),
        )
        for searcher, query, source in checks:
            with self.subTest(source=source):
                works = searcher(query, 2, 30)
                self.assertTrue(works)
                self.assertIn(source, works[0]["sources"])
                self.assertTrue(works[0]["title"])

    def test_openalex_supports_current_keyless_free_route(self):
        old = os.environ.pop("OPENALEX_API_KEY", None)
        try:
            works = search_openalex("retrieval augmented generation", 3, 30)
            self.assertTrue(works)
            self.assertIn("openalex", works[0]["sources"])
            self.assertTrue(works[0]["citation_url"].startswith("https://"))
        finally:
            if old is not None:
                os.environ["OPENALEX_API_KEY"] = old

    def test_real_doi_resolves_and_fake_doi_syntax_fails(self):
        real = verify_publication("10.1038/nphys1170", timeout=30)
        fake = verify_publication("not-a-doi", timeout=30)
        self.assertTrue(real["verified"], real)
        self.assertEqual(real["source"], "crossref")
        self.assertFalse(fake["verified"])
        self.assertIn("syntax", fake["reason"])

    def test_missing_ieee_key_is_explicit_failure(self):
        old = os.environ.pop("IEEE_API_KEY", None)
        try:
            with self.assertRaisesRegex(GuardError, "IEEE_API_KEY"):
                search_ieee("graph retrieval", 2, 5)
        finally:
            if old is not None:
                os.environ["IEEE_API_KEY"] = old

    def test_missing_wos_key_is_explicit_failure(self):
        old = os.environ.pop("CLARIVATE_WOS_API_KEY", None)
        try:
            with self.assertRaisesRegex(GuardError, "CLARIVATE_WOS_API_KEY"):
                search_wos("graph retrieval", 2, 5, "wos_sci")
        finally:
            if old is not None:
                os.environ["CLARIVATE_WOS_API_KEY"] = old

    def test_cssci_manual_only_route_fails_closed(self):
        with self.assertRaisesRegex(GuardError, "verified export evidence"):
            search_manual_only("cssci")

    def test_cross_source_dedup_merges_provenance(self):
        merged = deduplicate([
            {"title": "Same Work", "doi": "10.1000/ABC", "sources": ["crossref"], "venue": "V1"},
            {"title": "Same work", "doi": "https://doi.org/10.1000/abc", "sources": ["openalex"], "abstract": "details"},
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["sources"], ["crossref", "openalex"])
        self.assertEqual(merged[0]["abstract"], "details")

    def test_source_outage_is_recorded_and_blocks_gate(self):
        register_method(self.root, cs_method())
        fixtures = self.fixtures()
        failed = next(iter(fixtures))
        fixtures[failed] = {"error": "simulated timeout"}
        result = run_novelty_search(self.root, fixture_sources=fixtures)
        self.assertEqual(result["report"]["coverage"][failed]["status"], "error")
        self.assertIn("simulated timeout", result["report"]["coverage"][failed]["message"])
        self.assertEqual(result["report"]["gate_status"], "COVERAGE_INCOMPLETE")

    def test_method_file_path_escape_is_rejected(self):
        with self.assertRaisesRegex(GuardError, "escapes project root"):
            register_method(self.root, cs_method(method_files=["../outside.md"]))

    def test_signing_secret_is_not_written_inside_project(self):
        register_method(self.root, cs_method())
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.assertTrue(self.key.exists())
        project_files = [path.resolve() for path in self.root.rglob("*") if path.is_file()]
        self.assertNotIn(self.key.resolve(), project_files)
        secret = self.key.read_bytes()
        for path in project_files:
            self.assertNotIn(secret, path.read_bytes())

    def test_whitespace_only_method_change_is_idempotent(self):
        first = register_method(self.root, cs_method())
        second = register_method(self.root, cs_method(problem="  Transformer   inference has quadratic attention cost  "))
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])


if __name__ == "__main__":
    unittest.main()
