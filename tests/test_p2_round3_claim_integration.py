from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from mcp_server import TOOLS, handle  # noqa: E402
from paper_audit_core import plan_paper_audit, submit_paper_audit  # noqa: E402
import dependency_manager  # noqa: E402


class ClaimEvidenceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_dependency_home = os.environ.get("RESEARCH_GUARD_HOME")
        os.environ["RESEARCH_GUARD_HOME"] = str(self.root / "dependency-home")
        dependency_manager.decide([], [])
        (self.root / "paper.tex").write_text("This mechanism follows prior work \\cite{Doe2026}.\n", encoding="utf-8")

    def tearDown(self):
        if self.old_dependency_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = self.old_dependency_home
        self.temp.cleanup()

    def test_existing_multiplexer_owns_claim_evidence_without_surface_growth(self):
        names = [tool["name"] for tool in TOOLS]
        self.assertEqual(len(names), 17)
        self.assertEqual(names.count("paper_audit"), 1)
        tool = next(item for item in TOOLS if item["name"] == "paper_audit")
        self.assertEqual(tool["inputSchema"]["properties"]["action"]["enum"], ["plan", "lean_check", "submit", "status", "verify"])
        self.assertIn("claim_evidence_items", tool["inputSchema"]["properties"])

    def test_mcp_plan_exposes_inventory_and_domain_owner(self):
        reply = handle({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "paper_audit", "arguments": {
                "action": "plan", "project_root": str(self.root),
                "request_text": "Audit this manuscript.", "paper_files": ["paper.tex"],
                "selected_roles": ["domain_literature", "methodology_statistics"],
                "audit_features": {"literature": True}, "selected_by": "main_agent",
                "selection_rationale": "The main agent selected literature and methodology roles for citation evidence.",
            }},
        })
        self.assertFalse(reply["result"]["isError"])
        plan = reply["result"]["structuredContent"]
        self.assertEqual(plan["claim_inventory"]["status"], "REQUIRED")
        self.assertIn("domain_literature", plan["selected_roles"])

    def test_receipt_preserves_complete_claim_coverage(self):
        plan = plan_paper_audit(
            self.root,
            "Audit this manuscript.",
            paper_files=["paper.tex"],
            selected_roles=["domain_literature", "methodology_statistics"],
            audit_features={"literature": True},
            selected_by="main_agent",
            selection_rationale="The main agent selected literature and methodology roles for complete claim coverage.",
        )
        reports = [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "citation", "status": "verified"}]}
            for role in plan["selected_roles"]
        ]
        claim = plan["claim_inventory"]["claims"][0]
        items = [{
            "claim_id": claim["claim_id"],
            "claim_type": "bibliographic",
            "citation_keys": claim["citation_keys"],
            "support_status": "supports",
            "support_basis": "The primary article supports the exact statement at this location.",
            "evidence_locator": "abstract",
            "source_kind": "literature",
            "source_title": "Primary article",
            "source_url": "https://doi.org/10.1000/example",
            "metadata_status": "verified",
        }]
        result = submit_paper_audit(
            self.root,
            role_reports=reports,
            online_checks=[{
                "claim": "publication status", "url": "https://doi.org/10.1000/example",
                "accessed_at": "2026-08-12T00:00:00Z", "source_type": "primary", "status": "verified",
            }],
            literature_items=[{"title": "Primary article", "citation_url": "https://doi.org/10.1000/example"}],
            claim_evidence_items=items,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["claim_evidence_items"], items)
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
