from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from p8_fixtures import plan_statistical, statistical_spec


class P8CycleDLifecycleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        plan_statistical(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def render_and_audit(self):
        from academic_figure_core import audit_academic_figure, render_academic_figure

        rendered = render_academic_figure(self.root, "training", statistical_spec())
        audited = audit_academic_figure(self.root, "training")
        return rendered, audited

    def test_programmatic_audit_then_visual_review_is_required(self):
        from academic_figure_core import get_academic_figure_status, record_visual_review, verify_academic_figure

        rendered, audited = self.render_and_audit()
        self.assertEqual(audited["status"], "VISUAL_REVIEW_REQUIRED")
        self.assertEqual(get_academic_figure_status(self.root, "training")["status"], "VISUAL_REVIEW_REQUIRED")
        with self.assertRaisesRegex(Exception, "visual review"):
            verify_academic_figure(self.root, "training")
        reviewed = record_visual_review(
            self.root, "training", rendered_png_sha256=rendered["outputs"]["png"]["sha256"],
            review_method="actual_png_at_final_size", checks={
                "labels_readable": True, "no_clipping": True, "legend_clear": True,
                "uncertainty_clear": True, "color_redundant": True,
                "semantic_accuracy": True, "panel_hierarchy": True,
            }, issues=[],
        )
        self.assertEqual(reviewed["status"], "PASS")
        self.assertEqual(verify_academic_figure(self.root, "training")["status"], "PASS")

    def test_source_or_output_change_invalidates_receipt(self):
        from academic_figure_core import FigureError, audit_academic_figure, get_academic_figure_status

        rendered, _ = self.render_and_audit()
        svg = self.root / rendered["outputs"]["svg"]["path"]
        svg.write_text(svg.read_text(encoding="utf-8") + "\n<!-- tamper -->\n", encoding="utf-8")
        with self.assertRaisesRegex(FigureError, "changed"):
            audit_academic_figure(self.root, "training")
        self.assertNotEqual(get_academic_figure_status(self.root, "training")["status"], "PASS")

    def test_mcp_and_hook_expose_one_compact_owner(self):
        import mcp_server

        tools = [item for item in mcp_server.TOOLS if item["name"] == "paper_audit"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(len(mcp_server.TOOLS), 15)
        actions = set(tools[0]["inputSchema"]["properties"]["action"]["enum"])
        self.assertEqual(actions, {"plan", "lean_check", "submit", "status", "verify"})
        figure_actions = set(tools[0]["inputSchema"]["properties"]["figure_action"]["enum"])
        self.assertEqual(figure_actions, {"plan", "render", "audit", "visual_review", "status", "verify"})
        hook = Path(__file__).resolve().parents[1] / "hooks" / "guard_hook.py"
        payload = {"hook_event_name": "UserPromptSubmit", "cwd": str(self.root), "prompt": "请制作一张科研统计图和向量架构图"}
        proc = subprocess.run(
            [sys.executable, str(hook)], input=json.dumps(payload, ensure_ascii=True), text=True,
            capture_output=True, encoding="utf-8", check=True,
        )
        context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("figure_action", context)

    def test_paper_audit_consumes_verified_figure_receipt_and_detects_later_change(self):
        from academic_figure_core import audit_academic_figure, record_visual_review, render_academic_figure
        from paper_audit_core import AuditError, get_paper_audit_status, plan_paper_audit, submit_paper_audit

        rendered = render_academic_figure(self.root, "training", statistical_spec())
        audit_academic_figure(self.root, "training")
        record_visual_review(
            self.root, "training", rendered_png_sha256=rendered["outputs"]["png"]["sha256"],
            review_method="actual_png_at_final_size", checks={
                "labels_readable": True, "no_clipping": True, "legend_clear": True,
                "uncertainty_clear": True, "color_redundant": True,
                "semantic_accuracy": True, "panel_hierarchy": True,
            }, issues=[],
        )
        plan = plan_paper_audit(self.root, "Audit this paper figure", figure_ids=["training"])
        reports = [{"role": role, "findings": ["checked"], "numeric_checks": ["checked"]} for role in plan["selected_roles"]]
        result = submit_paper_audit(
            self.root, role_reports=reports,
            online_checks=[{"claim": "current figure policy", "url": "https://example.org/policy", "accessed_at": "2026-08-12", "source_type": "official", "status": "verified"}],
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["figure_receipts"][0]["figure_id"], "training")
        svg = self.root / rendered["outputs"]["svg"]["path"]
        svg.write_text(svg.read_text(encoding="utf-8") + "\n<!-- changed -->", encoding="utf-8")
        status = get_paper_audit_status(self.root)
        self.assertEqual(status["status"], "AUDIT_REQUIRED")
        self.assertIn("figure", status["reason"])

    def test_figure_audit_request_without_ids_requires_replanning_before_submit(self):
        from paper_audit_core import AuditError, plan_paper_audit, submit_paper_audit

        plan = plan_paper_audit(self.root, "Audit the manuscript figure")
        reports = [{"role": role, "findings": ["checked"], "numeric_checks": ["checked"]} for role in plan["selected_roles"]]
        with self.assertRaisesRegex(AuditError, "figure_ids"):
            submit_paper_audit(
                self.root, role_reports=reports,
                online_checks=[{"claim": "current figure policy", "url": "https://example.org/policy", "accessed_at": "2026-08-12", "source_type": "official", "status": "verified"}],
            )


if __name__ == "__main__":
    unittest.main()
