from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.response import addinfourl
from io import BytesIO


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import (  # noqa: E402
    GuardError, _foreign_proxy_for, declare_method_change, register_manual_evidence,
    register_method, run_novelty_search, search_clinicaltrials, search_datacite,
    search_github, search_nih_reporter, search_openaire_projects, search_osf,
)
from research_integrity_core import IntegrityError, audit_statistics, ingest_document, register_preregistration  # noqa: E402
from research_guard_core import sync_tracked_method_files  # noqa: E402
from intent_router_core import route_prompt  # noqa: E402


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
        self.state = register_method(self.root, METHOD)["state"]

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_and_receipt_cover_extended_families(self):
        plan = self.state["search_plan"]
        for family in ("publications", "grants", "datasets", "software", "preregistrations"):
            self.assertTrue(plan["source_families"][family])
        self.assertEqual(plan["source_families"]["patents"], [])
        self.assertEqual(plan["source_families"]["trials"], [])
        report = run_novelty_search(self.root, fixture_sources=fixtures(plan))["report"]
        self.assertEqual(report["gate_status"], "PASS")
        for family, value in report["family_coverage"].items():
            if plan["source_families"][family]:
                self.assertEqual(value["status"], "success")
        for work in report["works"]:
            self.assertTrue(work["citation_url"].startswith("https://"))

    def test_foreign_proxy_and_domestic_direct_routes_are_deterministic(self):
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
        with patch("research_guard_core.urllib.request.build_opener", return_value=opener) as builder, \
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
            ({"response": {"results": {"result": [{"metadata": {"oaf:entity": {"oaf:project": {
                "title": {"$": "Project"}, "summary": {"$": "funded"}, "startdate": {"$": "2026-01-01"}, "code": {"$": "P1"},
            }}}}]}}}, search_openaire_projects, "grants"),
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

    def test_manual_patent_capture_must_cover_every_planned_query(self):
        patent_method = dict(METHOD)
        patent_method["required_sources"] = ["google_patents"]
        self.state = register_method(self.root, patent_method)["state"]
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
        self.state = register_method(self.root, method)["state"]
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
        medical = register_method(self.root, {
            "title": "Randomized cancer therapy trial", "problem": "clinical survival",
            "mechanism": "drug intervention", "contributions": "prospective outcome analysis",
        })["state"]["search_plan"]
        self.assertTrue(medical["source_families"]["trials"])
        self.assertTrue(medical["source_families"]["grants"])
        computer = register_method(self.root, {
            "title": "Neural network compiler acceleration", "problem": "computer systems performance",
            "mechanism": "GPU kernel scheduling algorithm", "contributions": "software optimization method",
        })["state"]["search_plan"]
        self.assertTrue(computer["source_families"]["patents"])
        self.assertTrue(computer["source_families"]["software"])

    def test_real_chinese_method_change_triggers_unskippable_collision_overlay(self):
        for prompt in ("请修改研究方法，增加不确定性采样", "调整一下研究机制"):
            with self.subTest(prompt=prompt):
                routed = route_prompt(prompt)
                self.assertTrue(routed["method_change_overlay"])
                self.assertIn("research_novelty", routed["selected_modules"])
                self.assertIn("rerun the full collision search", routed["hard_overlay_instruction"])

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
