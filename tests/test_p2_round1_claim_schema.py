from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from paper_audit_core import AuditError, plan_paper_audit, submit_paper_audit  # noqa: E402


class ClaimEvidenceSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "paper.tex").write_text(
            "Prior work reports this effect \\cite{Smith2025}.\n"
            "Our measured accuracy is 91.2%.\n",
            encoding="utf-8",
        )
        self.plan = plan_paper_audit(
            self.root,
            "Audit the completed manuscript and its citations.",
            paper_files=["paper.tex"],
        )

    def tearDown(self):
        self.temp.cleanup()

    def reports(self):
        return [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "checked", "status": "verified"}]}
            for role in self.plan["selected_roles"]
        ]

    def online(self):
        return [{
            "claim": "current source status",
            "url": "https://example.org/current",
            "accessed_at": "2026-08-12T00:00:00Z",
            "source_type": "official",
            "status": "verified",
        }]

    def item(self, claim):
        value = {
            "claim_id": claim["claim_id"],
            "claim_type": claim["claim_type"],
            "support_status": "supports",
            "support_basis": "The cited primary record directly supports the manuscript statement.",
            "evidence_locator": "abstract and results",
            "source_kind": "literature",
            "source_title": "Primary evidence",
            "source_url": "https://doi.org/10.1000/example",
            "metadata_status": "verified",
        }
        if claim["claim_type"] == "bibliographic":
            value["citation_keys"] = claim["citation_keys"]
        if claim["claim_type"] == "quantitative":
            value["numeric_check"] = {
                "paper_value": "91.2%",
                "evidence_value": "91.2%",
                "method": "direct value comparison",
                "status": "exact_match",
            }
        return value

    def test_plan_inventories_citation_and_quantitative_claims(self):
        inventory = self.plan["claim_inventory"]
        self.assertEqual(inventory["status"], "REQUIRED")
        self.assertEqual({item["claim_type"] for item in inventory["claims"]}, {"bibliographic", "quantitative"})
        self.assertTrue(self.plan["requirements"]["claim_evidence_required"])
        self.assertIn("domain_literature", self.plan["selected_roles"])

    def test_missing_claim_evidence_fails_closed(self):
        with self.assertRaisesRegex(AuditError, "claim evidence"):
            submit_paper_audit(self.root, role_reports=self.reports(), online_checks=self.online())

    def test_duplicate_or_unknown_claim_ids_are_rejected(self):
        items = [self.item(claim) for claim in self.plan["claim_inventory"]["claims"]]
        with self.assertRaisesRegex(AuditError, "duplicate claim"):
            submit_paper_audit(
                self.root, role_reports=self.reports(), online_checks=self.online(),
                claim_evidence_items=items + [dict(items[0])],
            )
        items[0]["claim_id"] = "claim-unknown"
        with self.assertRaisesRegex(AuditError, "claim coverage"):
            submit_paper_audit(
                self.root, role_reports=self.reports(), online_checks=self.online(), claim_evidence_items=items,
            )

    def test_literature_claim_requires_https_and_verified_metadata(self):
        items = [self.item(claim) for claim in self.plan["claim_inventory"]["claims"]]
        citation = next(item for item in items if item["claim_type"] == "bibliographic")
        citation["source_url"] = "http://example.org/paper"
        with self.assertRaisesRegex(AuditError, "https"):
            submit_paper_audit(
                self.root, role_reports=self.reports(), online_checks=self.online(), claim_evidence_items=items,
            )
        citation["source_url"] = "https://example.org/paper"
        citation["metadata_status"] = "unverified"
        with self.assertRaisesRegex(AuditError, "metadata"):
            submit_paper_audit(
                self.root, role_reports=self.reports(), online_checks=self.online(), claim_evidence_items=items,
            )


if __name__ == "__main__":
    unittest.main()
