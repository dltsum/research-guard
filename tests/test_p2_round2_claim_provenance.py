from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from paper_audit_core import AuditError, get_paper_audit_status, plan_paper_audit, submit_paper_audit  # noqa: E402


class ClaimEvidenceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "paper.md").write_text(
            "Our method improves accuracy by 12.8% compared with the baseline.\n",
            encoding="utf-8",
        )
        (self.root / "results.json").write_text('{"baseline": 0.700, "ours": 0.828}\n', encoding="utf-8")
        self.plan = plan_paper_audit(
            self.root,
            "Audit the manuscript results and comparisons.",
            paper_files=["paper.md"],
            evidence_files=["results.json"],
        )

    def tearDown(self):
        self.temp.cleanup()

    def reports(self):
        return [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "12.8%", "status": "verified"}]}
            for role in self.plan["selected_roles"]
        ]

    def online(self):
        return [{
            "claim": "benchmark protocol",
            "url": "https://example.org/benchmark",
            "accessed_at": "2026-08-12T00:00:00Z",
            "source_type": "official",
            "status": "verified",
        }]

    def items(self):
        result = []
        for claim in self.plan["claim_inventory"]["claims"]:
            item = {
                "claim_id": claim["claim_id"],
                "claim_type": claim["claim_type"],
                "support_status": "supports",
                "support_basis": "The raw result values and configuration reproduce this claim.",
                "evidence_locator": "$.baseline and $.ours",
                "source_kind": "raw_result",
                "evidence_files": ["results.json"],
            }
            if claim["claim_type"] == "quantitative":
                item["numeric_check"] = {
                    "paper_value": "12.8%",
                    "evidence_value": "12.8%",
                    "method": "0.828 - 0.700",
                    "status": "exact_match",
                }
            result.append(item)
        return result

    def test_numeric_mismatch_and_weak_support_cannot_pass(self):
        items = self.items()
        numeric = next(item for item in items if item["claim_type"] == "quantitative")
        numeric["numeric_check"]["status"] = "mismatch"
        with self.assertRaisesRegex(AuditError, "numeric"):
            submit_paper_audit(
                self.root, role_reports=self.reports(), online_checks=self.online(),
                claim_evidence_items=items, experiment_check=self.experiment_check(),
            )
        numeric["numeric_check"]["status"] = "exact_match"
        numeric["support_status"] = "weak"
        with self.assertRaisesRegex(AuditError, "support"):
            submit_paper_audit(
                self.root, role_reports=self.reports(), online_checks=self.online(),
                claim_evidence_items=items, experiment_check=self.experiment_check(),
            )

    def experiment_check(self):
        return {
            "evidence_files": ["results.json"],
            "data_provenance": "recorded raw fixture",
            "configuration": "fixed fixture configuration",
            "seeds": [1],
            "numeric_recomputation": "0.828 - 0.700 = 0.128",
            "dead_code": "not present in fixture",
            "evaluation_scope": "single held-out fixture",
        }

    def test_unbound_raw_evidence_is_rejected(self):
        items = self.items()
        items[0]["evidence_files"] = ["untracked.json"]
        with self.assertRaisesRegex(AuditError, "hash-bound"):
            submit_paper_audit(
                self.root, role_reports=self.reports(), online_checks=self.online(),
                claim_evidence_items=items, experiment_check=self.experiment_check(),
            )

    def test_claim_receipt_is_invalidated_by_manuscript_change(self):
        submit_paper_audit(
            self.root, role_reports=self.reports(), online_checks=self.online(),
            claim_evidence_items=self.items(), experiment_check=self.experiment_check(),
        )
        (self.root / "paper.md").write_text("Changed claim: improvement is 13.1%.\n", encoding="utf-8")
        status = get_paper_audit_status(self.root)
        self.assertEqual(status["status"], "AUDIT_REQUIRED")
        self.assertIsNone(status["receipt"])


if __name__ == "__main__":
    unittest.main()
