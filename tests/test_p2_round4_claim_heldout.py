from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from paper_audit_core import AuditError, plan_paper_audit, submit_paper_audit  # noqa: E402


class ClaimEvidenceHeldOutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def reports(plan):
        return [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "checked", "status": "verified"}]}
            for role in plan["selected_roles"]
        ]

    @staticmethod
    def online():
        return [{
            "claim": "current check", "url": "https://example.org/current",
            "accessed_at": "2026-08-12T00:00:00Z", "source_type": "official", "status": "verified",
        }]

    def plan(self, request_text, paper_file, *, literature=False):
        return plan_paper_audit(
            self.root,
            request_text,
            paper_files=[paper_file],
            selected_roles=(
                ["domain_literature", "methodology_statistics"]
                if literature else ["methodology_statistics", "adversarial_logic"]
            ),
            audit_features={"literature": literature},
            selected_by="main_agent",
            selection_rationale="The main agent selected two roles that cover this held-out manuscript audit.",
        )

    def test_chinese_claims_and_citations_are_detected(self):
        (self.root / "paper.md").write_text(
            "相关工作证明该机制有效 [@Zhang2025]。\n本方法准确率提高 8.4%，显著优于基线。\n",
            encoding="utf-8",
        )
        plan = self.plan("请审计这篇论文并核验引用", "paper.md", literature=True)
        kinds = {claim["claim_type"] for claim in plan["claim_inventory"]["claims"]}
        self.assertTrue({"bibliographic", "quantitative", "comparative"} <= kinds)
        self.assertIn("domain_literature", plan["selected_roles"])

    def test_binary_only_manuscript_blocks_claim_audit(self):
        (self.root / "paper.pdf").write_bytes(b"%PDF-1.7\x00binary")
        plan = self.plan("Audit the completed paper", "paper.pdf")
        self.assertEqual(plan["claim_inventory"]["status"], "BLOCKED")
        with self.assertRaisesRegex(AuditError, "text manuscript"):
            submit_paper_audit(self.root, role_reports=self.reports(plan), online_checks=self.online())

    def test_text_without_auditable_claims_is_not_applicable(self):
        (self.root / "note.md").write_text("Acknowledgements\n", encoding="utf-8")
        plan = self.plan("Audit this note", "note.md")
        self.assertEqual(plan["claim_inventory"]["status"], "NOT_APPLICABLE")
        result = submit_paper_audit(self.root, role_reports=self.reports(plan), online_checks=self.online())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["claim_evidence_items"], [])

    def test_skill_prompt_stays_compact_and_names_claim_gate(self):
        skill = (PLUGIN / "skills" / "paper-audit-guard" / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(len(skill.split()), 350)
        self.assertIn("claim_evidence_items", skill)


if __name__ == "__main__":
    unittest.main()
