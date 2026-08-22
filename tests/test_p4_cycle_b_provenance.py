from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from evidence_kernel import EvidenceRecorder, digest as evidence_digest, verify_evidence_manifest  # noqa: E402
from paper_audit_core import (  # noqa: E402
    AuditError,
    _formula_contract,
    _validate_online_checks,
    plan_paper_audit,
    submit_paper_audit,
)
from research_design_core import DesignError, _normalize_ethics, _normalize_power  # noqa: E402
from research_guard_core import (  # noqa: E402
    GuardError,
    SourcePayloadError,
    deduplicate,
    refresh_domain,
    register_manual_evidence,
    register_method,
)


class P4CycleBProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_conflicting_titles_for_same_doi_fail_closed(self):
        with self.assertRaisesRegex(SourcePayloadError, "conflicting"):
            deduplicate([
                {"title": "First scientific result", "doi": "10.1000/shared", "sources": ["crossref"]},
                {"title": "Unrelated second result", "doi": "10.1000/shared", "sources": ["datacite"]},
            ])

    def test_compatible_duplicate_keeps_all_links_and_provenance(self):
        merged = deduplicate([
            {
                "title": "A shared result",
                "doi": "10.1000/shared",
                "url": "https://example.org/record-a",
                "sources": ["crossref"],
                "evidence_refs": ["a1"],
            },
            {
                "title": "A shared result",
                "doi": "10.1000/shared",
                "url": "https://example.net/record-b",
                "sources": ["datacite"],
                "evidence_refs": ["a2"],
            },
        ])[0]
        self.assertEqual(merged["sources"], ["crossref", "datacite"])
        self.assertEqual(merged["evidence_refs"], ["a1", "a2"])
        urls = {item["url"] for item in merged["citation_links"]}
        self.assertTrue({"https://example.org/record-a", "https://example.net/record-b"} <= urls)

    def test_evidence_manifest_cannot_replay_raw_path_outside_project(self):
        outside = self.root.parent / f"{self.root.name}-outside.bin"
        outside.write_bytes(b"outside")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        recorder = EvidenceRecorder(self.root, "path-boundary")
        recorder.record_fixture(source="crossref", query_id="q1", query="x", payload=[])
        relative, manifest = recorder.finalize(method_version=1, method_hash="m", query_plan_hash="p", query_runs=[])
        manifest["attempts"][0]["raw_path"] = str(outside)
        unsigned = {key: value for key, value in manifest.items() if key != "manifest_hash"}
        manifest["manifest_hash"] = evidence_digest(unsigned)
        (self.root / relative).write_text(json.dumps(manifest), encoding="utf-8")
        errors = verify_evidence_manifest(self.root, relative)
        self.assertTrue(any("unreadable" in error for error in errors))

    def test_manual_evidence_rejects_plain_http_even_on_official_host(self):
        register_method(
            self.root,
            {"title": "CCF study", "problem": "software systems", "mechanism": "graph ranking", "required_sources": ["ccf"]},
        )
        refresh_domain(
            self.root,
            primary_domain="computer_science",
            secondary_domains=[],
            selected_by="main_agent",
            selection_rationale="The main agent selected computer science for this CCF software-systems study.",
        )
        (self.root / "ccf.png").write_bytes(b"capture")
        with self.assertRaisesRegex(GuardError, "HTTPS"):
            register_manual_evidence(
                self.root,
                source="ccf",
                purpose="index_membership",
                query="Example Conference",
                status="index_verified",
                evidence_path="ccf.png",
                evidence_url="http://www.ccf.org.cn/Academic_Evaluation/By_category/",
                identifier="Example Conference",
            )

    def test_online_check_rejects_invalid_timestamp_and_unresolved_status(self):
        with self.assertRaisesRegex(AuditError, "accessed_at"):
            _validate_online_checks([{
                "claim": "current policy", "url": "https://example.org/policy",
                "accessed_at": "yesterday", "source_type": "official", "status": "verified",
            }])
        with self.assertRaisesRegex(AuditError, "status"):
            _validate_online_checks([{
                "claim": "current policy", "url": "https://example.org/policy",
                "accessed_at": "2026-08-12T00:00:00Z", "source_type": "official", "status": "unknown",
            }])

    def test_numeric_status_cannot_override_mismatching_values(self):
        (self.root / "paper.md").write_text("Accuracy improved by 12.8%.\n", encoding="utf-8")
        plan = plan_paper_audit(
            self.root,
            "Audit the numeric manuscript",
            paper_files=["paper.md"],
            selected_roles=["methodology_statistics", "adversarial_logic"],
            audit_features={},
            selected_by="main_agent",
            selection_rationale="The main agent selected methodology and adversarial roles for the numeric claim audit.",
        )
        reports = [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "12.8%", "status": "verified"}]}
            for role in plan["selected_roles"]
        ]
        evidence = []
        for claim in plan["claim_inventory"]["claims"]:
            item = {
                "claim_id": claim["claim_id"], "claim_type": claim["claim_type"],
                "support_status": "supports", "support_basis": "The linked source directly supports the stated claim.",
                "evidence_locator": "table 1", "source_kind": "official_standard",
                "source_title": "Official result", "source_url": "https://example.org/result",
                "metadata_status": "verified",
            }
            if claim["claim_type"] == "quantitative":
                item["numeric_check"] = {
                    "paper_value": "12.8%", "evidence_value": "99%",
                    "method": "direct percentage comparison", "status": "exact_match",
                }
            evidence.append(item)
        with self.assertRaisesRegex(AuditError, "numeric"):
            submit_paper_audit(
                self.root,
                role_reports=reports,
                online_checks=[{
                    "claim": "current result", "url": "https://example.org/result",
                    "accessed_at": "2026-08-12T00:00:00Z", "source_type": "official", "status": "verified",
                }],
                claim_evidence_items=evidence,
            )

    def test_formula_parameter_mentions_in_comments_do_not_count_as_use(self):
        text = """import Mathlib
set_option autoImplicit false
-- FORMULA_ID: f
-- x x appears only in this comment
theorem f (x : Nat) : True := by trivial
"""
        manifest = {
            "formulas": [{"id": "f", "source": "paper.tex:1", "parameters": ["x"]}],
            "parameters": [{"name": "x", "purpose": "input value", "used_by": ["f"]}],
        }
        with self.assertRaisesRegex(AuditError, "not actually used"):
            _formula_contract(text, manifest)

    def test_power_contract_rejects_placeholder_sample_size(self):
        with self.assertRaisesRegex(DesignError, "placeholder"):
            _normalize_power({
                "mode": "analytic", "basis": "two-sided test",
                "target_power_or_precision": "0.8", "sample_size": "TBD",
                "sensitivity_plan": "vary the assumed effect size",
            })

    def test_cleared_ethics_cannot_keep_unresolved_blocks(self):
        with self.assertRaisesRegex(DesignError, "unresolved"):
            _normalize_ethics({
                "status": "cleared", "required_reviews": ["IRB"],
                "unresolved_blocks": ["consent language pending"],
            })


if __name__ == "__main__":
    unittest.main()
