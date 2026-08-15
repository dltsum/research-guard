from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from evidence_kernel import digest as evidence_digest, verify_evidence_manifest  # noqa: E402
from mcp_server import TOOLS  # noqa: E402
from paper_audit_core import get_paper_audit_status, plan_paper_audit, submit_paper_audit  # noqa: E402
from research_design_core import DesignError, get_research_design_status, plan_ideation, register_candidates  # noqa: E402
from research_guard_core import GuardError, register_manual_evidence, register_method  # noqa: E402


class P4CycleEIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_evidence_manifest_rejects_non_array_attempts(self):
        relative = Path(".research-guard/evidence/runs/tampered/manifest.json")
        path = self.root / relative
        path.parent.mkdir(parents=True)
        manifest = {
            "schema_version": 1, "run_id": "tampered", "created_at": "2026-08-12T00:00:00Z",
            "method_version": 1, "method_hash": "m", "query_plan_hash": "p",
            "query_runs_hash": "q", "attempts": {},
        }
        manifest["manifest_hash"] = evidence_digest(manifest)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        errors = verify_evidence_manifest(self.root, relative.as_posix())
        self.assertTrue(any("attempts" in error for error in errors))

    def test_paper_receipt_payload_tampering_invalidates_pass(self):
        plan = plan_paper_audit(self.root, "Audit final manuscript")
        reports = [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "none", "status": "verified"}]}
            for role in plan["selected_roles"]
        ]
        submit_paper_audit(
            self.root,
            role_reports=reports,
            online_checks=[{
                "claim": "policy", "url": "https://example.org/policy", "accessed_at": "2026-08-12",
                "source_type": "official", "status": "verified",
            }],
        )
        state_path = self.root / ".research-guard" / "paper-audit-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["receipt"]["role_reports"][0]["findings"] = ["tampered"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        status = get_paper_audit_status(self.root)
        self.assertEqual(status["status"], "AUDIT_REQUIRED")
        self.assertIn("receipt", status["reason"])

    def test_manual_official_url_rejects_userinfo_credentials(self):
        register_method(
            self.root,
            {"title": "Directory", "problem": "software systems", "mechanism": "graph ranking", "required_sources": ["ccf"]},
        )
        (self.root / "capture.png").write_bytes(b"capture")
        with self.assertRaisesRegex(GuardError, "credentials"):
            register_manual_evidence(
                self.root, source="ccf", purpose="index_membership", query="Venue",
                status="index_verified", evidence_path="capture.png",
                evidence_url="https://user:secret@www.ccf.org.cn/Academic_Evaluation/By_category/",
                identifier="Venue",
            )

    def test_design_candidate_tampering_is_detected_before_status(self):
        plan = plan_ideation(self.root, request_text="brainstorm", problem="model failure")
        candidate = {
            "candidate_id": "c1", "title": "Candidate", "problem": "model failure",
            "mechanism": "boundary routing", "falsifier": "no effect",
            "minimum_viable_experiment": "comparison", "differentiator": "boundary",
            "feasibility": "small run", "lens_id": plan["selected_lens_ids"][0], "prior_work": [],
        }
        register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[candidate])
        state_path = self.root / ".research-guard" / "research-design.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["candidates"][0]["mechanism"] = "tampered mechanism"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(DesignError, "integrity"):
            get_research_design_status(self.root)

    def test_mcp_never_exposes_deterministic_fixture_bypass(self):
        novelty = next(tool for tool in TOOLS if tool["name"] == "run_novelty_search")
        self.assertNotIn("fixture_sources", novelty["inputSchema"]["properties"])
        self.assertFalse(novelty["inputSchema"].get("additionalProperties", True))

    def test_all_skill_entrypoints_remain_compact(self):
        for relative in (
            "skills/research-novelty-guard/SKILL.md",
            "skills/paper-audit-guard/SKILL.md",
            "skills/research-design-guard/SKILL.md",
        ):
            lines = (PLUGIN / relative).read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 60, relative)


if __name__ == "__main__":
    unittest.main()
