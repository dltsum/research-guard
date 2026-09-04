from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch
from urllib.response import addinfourl
from io import BytesIO


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import (  # noqa: E402
    GuardError, SourcePayloadError, _foreign_proxy_for, declare_method_change, register_manual_evidence,
    refresh_domain, register_method, run_novelty_search, search_clinicaltrials, search_datacite,
    search_dblp, search_github, search_nih_reporter, search_openaire, search_openaire_projects,
    search_osf,
)
from research_integrity_core import IntegrityError, audit_statistics, ingest_document, register_preregistration  # noqa: E402
from research_guard_core import sync_tracked_method_files  # noqa: E402
from intent_router_core import route_prompt, select_research_modules  # noqa: E402


METHOD = {
    "title": "Graph collision test", "problem": "graph learning",
    "mechanism": "adaptive graph sampler", "contributions": "sampling mechanism",
}


def fixtures(plan: dict) -> dict:
    output = {}
    for source in plan["required_sources"]:
        output[source] = [{
            "title": f"Distinct result from {source}", "url": f"https://example.org/{source}",
            "record_family": next((family for family, sources in plan["source_families"].items() if source in sources), "publications"),
        }]
    return output


class P12CycleBExtendedCollisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self._register(METHOD)

    def _register(self, method: dict, domain: str = "computer_science") -> dict:
        register_method(self.root, method)
        refresh_domain(
            self.root, primary_domain=domain, secondary_domains=[], selected_by="main_agent",
            selection_rationale=f"The main agent selected {domain} for this deterministic collision test.",
        )
        return json.loads((self.root / ".research-guard" / "state.json").read_text(encoding="utf-8"))

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_and_receipt_cover_extended_families(self):
        plan = self.state["search_plan"]
        for family in ("publications", "grants", "datasets", "software", "preregistrations"):
            self.assertTrue(plan["source_families"][family])
        self.assertTrue(plan["source_families"]["patents"])
        self.assertEqual(plan["source_families"]["trials"], [])
        report = run_novelty_search(self.root, fixture_sources=fixtures(plan))["report"]
        self.assertEqual(report["gate_status"], "PASS")
        for family, value in report["family_coverage"].items():
            if plan["source_families"][family]:
                self.assertEqual(value["status"], "success")
        for work in report["works"]:
            self.assertTrue(work["citation_url"].startswith("https://"))

    def test_foreign_proxy_and_domestic_direct_routes_are_deterministic(self):
        with patch.dict("os.environ", {"RESEARCH_GUARD_FOREIGN_PROXY": "http://127.0.0.1:7897"}):
            self.assertEqual(_foreign_proxy_for("https://api.github.com/search/repositories"), "http://127.0.0.1:7897")
        self.assertIsNone(_foreign_proxy_for("https://www.ccf.org.cn/Academic_Evaluation/By_category/"))

    def test_domestic_request_explicitly_bypasses_inherited_proxy(self):
        class Response(BytesIO):
            status = 200
            headers = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.close()

        opener = unittest.mock.Mock()
        opener.open.return_value = Response(b"{}")
        with patch.dict("os.environ", {"HTTP_PROXY": "http://127.0.0.1:7897", "HTTPS_PROXY": "http://127.0.0.1:7897"}), \
             patch("research_guard_core.urllib.request.build_opener", return_value=opener) as builder, \
             patch("research_guard_core.urllib.request.urlopen", side_effect=AssertionError("domestic request used ambient proxy")):
            from research_guard_core import _request
            self.assertEqual(_request("https://www.ccf.org.cn/test", timeout=1), b"{}")
        builder.assert_called_once()
        proxy_handler = builder.call_args.args[0]
        self.assertEqual(proxy_handler.proxies, {})

    def test_foreign_request_uses_proxy_handler_for_https_connect(self):
        class Response(BytesIO):
            status = 200
            headers = None

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.close()

        opener = unittest.mock.Mock()
        opener.open.return_value = Response(b"{}")
        with patch.dict("os.environ", {"RESEARCH_GUARD_FOREIGN_PROXY": "http://127.0.0.1:7897"}), \
             patch("research_guard_core.urllib.request.build_opener", return_value=opener) as builder, \
             patch("research_guard_core.urllib.request.urlopen", side_effect=AssertionError("foreign route bypassed ProxyHandler")):
            from research_guard_core import _request
            self.assertEqual(_request("https://api.github.com/test", timeout=1), b"{}")
        proxy_handler = builder.call_args.args[0]
        self.assertEqual(proxy_handler.proxies["https"], "http://127.0.0.1:7897")

    def test_every_extended_adapter_has_a_clickable_catalog_entry(self):
        catalog = json.loads((PLUGIN / "skills" / "research-novelty-guard" / "references" / "source-catalog.json").read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in catalog}
        required = {source for sources in self.state["search_plan"]["source_families"].values() for source in sources}
        for source in required:
            self.assertIn(source, by_id)
            entry = by_id[source]
            self.assertTrue(entry["search_url"].startswith("https://"))
            self.assertTrue(entry["docs_url"].startswith("https://"))

    def test_registration_free_adapters_parse_primary_records(self):
        fixtures_and_searches = [
            ({"data": [{"attributes": {
                "titles": [{"title": "Dataset"}], "doi": "10.1000/data", "publicationYear": 2026,
                "publisher": "Repository", "descriptions": [{"description": "data"}],
                "url": "https://doi.org/10.1000/data", "types": {"resourceTypeGeneral": "Dataset"},
            }}]}, search_datacite, "datasets"),
            ({"studies": [{"protocolSection": {
                "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Trial"},
                "descriptionModule": {"briefSummary": "summary"},
                "statusModule": {"studyFirstPostDateStruct": {"date": "2026-01-01"}},
            }}]}, search_clinicaltrials, "trials"),
            ({"items": [{"full_name": "org/tool", "description": "software", "created_at": "2025-01-01", "html_url": "https://github.com/org/tool"}]}, search_github, "software"),
            ({"data": [{"attributes": {"title": "Registration", "description": "protocol", "date_registered": "2026-01-01"}, "links": {"html": "https://osf.io/abcd1"}}]}, search_osf, "preregistrations"),
            ({"results": [{"appl_id": 123, "project_title": "Grant", "abstract_text": "funded", "fiscal_year": 2026}]}, search_nih_reporter, "grants"),
            ({"header": {"numFound": 1}, "results": [{
                "id": "corda__h2020::project-1", "title": "Project", "summary": "funded",
                "startDate": "2026-01-01", "code": "P1", "fundings": [],
            }]}, search_openaire_projects, "grants"),
        ]
        for payload, search, family in fixtures_and_searches:
            with self.subTest(search=search.__name__), patch("research_guard_core._json_request", return_value=payload) as request:
                works = search("query", 2, 1.0)
                self.assertEqual(len(works), 1)
                self.assertEqual(works[0]["record_family"], family)
                self.assertTrue(works[0]["citation_url"].startswith("https://"))
                self.assertTrue(works[0]["primary_record_url"].startswith("https://"))
                self.assertEqual(works[0]["link_scope"], "primary_record")
                if search is search_datacite:
                    self.assertIn("resource-type-id=dataset", request.call_args.args[0])
                if search is search_osf:
                    self.assertIn("/registrations/", request.call_args.args[0])

    def test_openaire_graph_v3_adapters_parse_results_and_valid_empty_arrays(self):
        publication_payload = {
            "header": {"numFound": 1, "page": 1, "pageSize": 2},
            "results": [{
                "id": "doi_dedup___::publication-1",
                "type": "publication",
                "mainTitle": "Publication",
                "descriptions": ["First abstract", "Second abstract"],
                "publicationDate": "2026-01-15",
                "publisher": "Publisher",
                "container": {"name": "Journal"},
                "pids": [{"scheme": "doi", "value": "10.1000/publication"}],
                "authors": [{"fullName": "Ada Lovelace"}],
            }],
        }
        project_payload = {
            "header": {"numFound": 1, "page": 1, "pageSize": 2},
            "results": [{
                "id": "corda__h2020::project-1",
                "code": "P1",
                "title": "Project",
                "summary": "Funded work",
                "startDate": "2025-02-01",
                "fundings": [{"shortName": "EC", "name": "European Commission"}],
            }],
        }
        cases = (
            (search_openaire, publication_payload, "/graph/v3/research-products?", "publications"),
            (search_openaire_projects, project_payload, "/graph/v3/projects?", "grants"),
        )
        for searcher, payload, endpoint, family in cases:
            with self.subTest(searcher=searcher.__name__), patch(
                "research_guard_core._json_request", return_value=payload
            ) as request:
                [work] = searcher("query", 2, 1.0)
                request_url = request.call_args.args[0]
                self.assertIn(endpoint, request_url)
                self.assertIn("search=query", request_url)
                self.assertIn("pageSize=2", request_url)
                self.assertEqual(work["record_family"], family)
                self.assertEqual(work["identifiers"]["openaire"], payload["results"][0]["id"])
                self.assertTrue(work["primary_record_url"].startswith("https://"))
                if searcher is search_openaire:
                    self.assertIn("type=publication", request_url)
                    self.assertEqual(work["doi"], "10.1000/publication")
                    self.assertEqual(work["authors"], ["Ada Lovelace"])
                    self.assertEqual(work["venue"], "Journal")
                else:
                    self.assertEqual(work["venue"], "European Commission")

        valid_empty = {"header": {"numFound": 0, "page": 1, "pageSize": 2}, "results": []}
        for searcher in (search_openaire, search_openaire_projects):
            with self.subTest(empty=searcher.__name__), patch(
                "research_guard_core._json_request", return_value=valid_empty
            ):
                self.assertEqual(searcher("no matches", 2, 1.0), [])

        for malformed in ({"header": {}}, {"header": {}, "results": {}}):
            with self.subTest(malformed=malformed), patch(
                "research_guard_core._json_request", return_value=malformed
            ):
                with self.assertRaises(SourcePayloadError):
                    search_openaire("query", 2, 1.0)
    def test_github_search_bounds_encoded_parameters_without_changing_short_queries(self):
        short_query = "selective legal fact checking"
        long_query = (
            "shared CaseFacts retrieval and verdict pipeline with selective accept-or-abstain scores "
            "compare generic retrieval confidence Recall and MRR for retrieval shared verdict accuracy "
            "and evidence score risk-coverage and CA-AURC"
        )
        with patch("research_guard_core._json_request", return_value={"items": []}) as request:
            search_github(short_query, 5, 1.0)
            short_url = request.call_args.args[0]
            short_parameters = urllib.parse.urlsplit(short_url).query
            self.assertEqual(urllib.parse.parse_qs(short_parameters)["q"], [short_query])

            search_github(long_query, 5, 1.0)
            long_url = request.call_args.args[0]
            long_parameters = urllib.parse.urlsplit(long_url).query
            bounded_query = urllib.parse.parse_qs(long_parameters)["q"][0]
            self.assertLessEqual(len(bounded_query), 200)
            self.assertLessEqual(len(long_parameters), 240)
            self.assertNotEqual(bounded_query, long_query)
            self.assertTrue(long_query.startswith(f"{bounded_query} "))
            self.assertTrue(bounded_query.split())
    def test_dblp_zero_result_envelope_is_empty_but_missing_hits_fail_closed(self):
        zero_result = {
            "result": {
                "status": {"@code": "200", "text": "OK"},
                "hits": {"@total": "0", "@computed": "0", "@sent": "0", "@first": "0"},
            },
        }
        with patch("research_guard_core._json_request", return_value=zero_result):
            self.assertEqual(search_dblp("no matching publication", 5, 1.0), [])

        for malformed in (
            {"result": {"hits": {"@total": "1", "@sent": "0"}}},
            {"result": {"hits": {"@total": "0"}}},
            {"result": {"hits": {"@sent": "0"}}},
        ):
            with self.subTest(payload=malformed), \
                 patch("research_guard_core._json_request", return_value=malformed), \
                 self.assertRaisesRegex(SourcePayloadError, "missing required field hit"):
                search_dblp("malformed response", 5, 1.0)

    def test_manual_patent_capture_must_cover_every_planned_query(self):
        patent_method = dict(METHOD)
        patent_method["required_sources"] = ["google_patents"]
        self.state = self._register(patent_method)
        capture = self.root / "patents.txt"
        capture.write_text("Google Patents result export for complete query plan", encoding="utf-8")
        query_ids = [item["query_id"] for item in self.state["search_plan"]["query_specs"]]
        with self.assertRaises(GuardError):
            register_manual_evidence(
                self.root, source="google_patents", purpose="literature_search",
                query="all frozen method queries", status="zero_results", evidence_path="patents.txt",
                evidence_url="https://patents.google.com/", query_ids=query_ids[:-1],
            )
        result = register_manual_evidence(
            self.root, source="google_patents", purpose="literature_search",
            query="all frozen method queries", status="zero_results", evidence_path="patents.txt",
            evidence_url="https://patents.google.com/", query_ids=query_ids,
        )
        self.assertTrue(result["registered"])

    def test_manual_hits_cannot_use_a_search_fallback_as_primary_record(self):
        method = dict(METHOD, required_sources=["google_patents"])
        self.state = self._register(method)
        capture = self.root / "patents.txt"
        capture.write_text("complete Google Patents export", encoding="utf-8")
        query_ids = [item["query_id"] for item in self.state["search_plan"]["query_specs"]]
        with self.assertRaisesRegex(GuardError, "search page is not a primary record"):
            register_manual_evidence(
                self.root, source="google_patents", purpose="literature_search",
                query="complete frozen queries", status="hits_present", evidence_path="patents.txt",
                evidence_url="https://patents.google.com/", query_ids=query_ids,
                records=[{"title": "Unlinked patent"}],
            )
        with self.assertRaisesRegex(GuardError, "official host"):
            register_manual_evidence(
                self.root, source="google_patents", purpose="literature_search",
                query="complete frozen queries", status="hits_present", evidence_path="patents.txt",
                evidence_url="https://patents.google.com/", query_ids=query_ids,
                records=[{"title": "Mislabelled patent", "url": "https://example.org/not-a-patent"}],
            )

    def test_declared_and_registered_changes_invalidate_derived_records(self):
        protocol = {
            "research_questions": ["RQ1"], "hypotheses": ["H1"], "outcomes": ["Y"],
            "exclusions": ["invalid"], "sample_size_basis": "power analysis", "analysis_plan": "linear model",
            "missing_data": "multiple imputation", "multiplicity": "Holm", "stopping_rule": "fixed N",
            "random_seed_policy": "record all seeds",
        }
        register_preregistration(self.root, "pre-v1", protocol, selected_by="user")
        (self.root / "paper.md").write_text("# Method\nold method", encoding="utf-8")
        ingest_document(self.root, "paper.md", "paper-old")
        declare_method_change(self.root, "Adjust the adaptive graph sampler")
        with self.assertRaisesRegex(IntegrityError, "adjustment is pending"):
            audit_statistics(self.root, "old-method-stats", text="t(10)=2.228, p=.050")
        integrity = json.loads((self.root / ".research-guard" / "research-integrity.json").read_text(encoding="utf-8"))
        self.assertEqual(integrity["preregistrations"]["pre-v1"]["status"], "INVALIDATED")
        self.assertEqual(integrity["ingestions"]["paper-old"]["status"], "INVALIDATED")
        changed = dict(METHOD)
        changed["mechanism"] = "adaptive graph sampler with uncertainty"
        register_method(self.root, changed)
        integrity = json.loads((self.root / ".research-guard" / "research-integrity.json").read_text(encoding="utf-8"))
        self.assertTrue(integrity["invalidations"][-1]["full_collision_rerun_required"])

    def test_domain_specific_families_are_required(self):
        medical = self._register({
            "title": "Randomized cancer therapy trial", "problem": "clinical survival",
            "mechanism": "drug intervention", "contributions": "prospective outcome analysis",
        }, domain="medicine_life_science")["search_plan"]
        self.assertTrue(medical["source_families"]["trials"])
        self.assertTrue(medical["source_families"]["grants"])
        computer = self._register({
            "title": "Neural network compiler acceleration", "problem": "computer systems performance",
            "mechanism": "GPU kernel scheduling algorithm", "contributions": "software optimization method",
        }, domain="computer_science")["search_plan"]
        self.assertTrue(computer["source_families"]["patents"])
        self.assertTrue(computer["source_families"]["software"])

    def test_real_chinese_method_change_triggers_unskippable_collision_overlay(self):
        for prompt in ("请修改研究方法，增加不确定性采样", "调整一下研究机制"):
            with self.subTest(prompt=prompt):
                self.assertIsNone(route_prompt(prompt)["method_change_overlay"])
                routed = select_research_modules(
                    self.root, request_text=prompt,
                    selected_modules=["research_strategy", "research_novelty"],
                    selection_rationale="The main agent judged this request to change the canonical research method.",
                    selected_by="main_agent", method_change=True,
                )
                self.assertTrue(routed["selection"]["method_change"])
                self.assertIsNotNone(routed["method_change_invalidation"])

    def test_malformed_paper_audit_cannot_leave_integrity_receipts_passed(self):
        protocol = {
            "research_questions": ["RQ1"], "hypotheses": ["H1"], "outcomes": ["Y"],
            "exclusions": ["invalid"], "sample_size_basis": "power analysis", "analysis_plan": "linear model",
            "missing_data": "multiple imputation", "multiplicity": "Holm", "stopping_rule": "fixed N",
            "random_seed_policy": "record all seeds",
        }
        register_preregistration(self.root, "pre-malformed", protocol, selected_by="user")
        audit = self.root / ".research-guard" / "paper-audit-state.json"
        audit.write_text("{malformed", encoding="utf-8")
        with self.assertRaises(GuardError):
            declare_method_change(self.root, "Adjust after malformed audit state")
        integrity = json.loads((self.root / ".research-guard" / "research-integrity.json").read_text(encoding="utf-8"))
        self.assertEqual(integrity["preregistrations"]["pre-malformed"]["status"], "INVALIDATED")

    def test_tracked_method_file_drift_invalidates_derived_records(self):
        tracked = dict(METHOD)
        (self.root / "method.yaml").write_text("mechanism: adaptive graph sampler\n", encoding="utf-8")
        tracked["method_files"] = ["method.yaml"]
        register_method(self.root, tracked)
        protocol = {
            "research_questions": ["RQ1"], "hypotheses": ["H1"], "outcomes": ["Y"],
            "exclusions": ["invalid"], "sample_size_basis": "power analysis", "analysis_plan": "linear model",
            "missing_data": "multiple imputation", "multiplicity": "Holm", "stopping_rule": "fixed N",
            "random_seed_policy": "record all seeds",
        }
        register_preregistration(self.root, "pre-file-v1", protocol, selected_by="user")
        (self.root / "method.yaml").write_text("mechanism: uncertainty sampler\n", encoding="utf-8")
        self.assertTrue(sync_tracked_method_files(self.root)["requires_registration"])
        integrity = json.loads((self.root / ".research-guard" / "research-integrity.json").read_text(encoding="utf-8"))
        self.assertEqual(integrity["preregistrations"]["pre-file-v1"]["status"], "INVALIDATED")


if __name__ == "__main__":
    unittest.main()
