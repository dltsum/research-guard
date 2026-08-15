from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from academic_figure_core import (  # noqa: E402
    audit_scientific_image_integrity,
    get_scientific_image_integrity_status,
    record_scientific_image_review,
)
from openreview_calibration_core import calibrate_openreview, get_openreview_calibration  # noqa: E402
from paper_audit_core import plan_paper_audit  # noqa: E402
from paper_audit_core import attach_paper_auxiliary_audit, get_paper_audit_status  # noqa: E402


class P13ReviewImageRouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_mixed_request_selects_exactly_three_specialist_roles(self):
        plan = plan_paper_audit(
            self.root,
            "Verify the equations with SymPy and Z3, calibrate OpenReview reviews, and audit scientific image integrity.",
        )
        self.assertEqual(plan["selected_roles"], ["formal_math_lean", "openreview_calibration", "scientific_image_integrity"])
        self.assertEqual(len(plan["selected_roles"]), 3)

    def test_openreview_fixture_is_hash_bound_calibration_not_prediction(self):
        forum = "forum123"
        fixture = {"notes": [{
            "id": "review1", "forum": forum, "invitation": "ICLR.cc/2026/Conference/-/Official_Review",
            "content": {
                "summary": {"value": "The experiments and ablation are clear."},
                "weaknesses": {"value": "Novelty and reproducibility need discussion."},
                "rating": {"value": "6: marginally above"},
            },
        }]}
        result = calibrate_openreview(self.root, "calibration-a", forum_ids=[forum], fixture_payload=fixture)
        self.assertEqual(result["status"], "FIXTURE_ONLY")
        self.assertTrue(result["calibration_only"])
        self.assertFalse(result["acceptance_prediction"])
        self.assertEqual(result["forum_urls"], ["https://openreview.net/forum?id=forum123"])
        self.assertEqual(get_openreview_calibration(self.root, "calibration-a")["receipt_sha256"], result["receipt_sha256"])

    def test_image_audit_flags_duplicates_without_fraud_claim(self):
        from PIL import Image, ImageDraw

        for name in ("original.png", "processed.png"):
            image = Image.new("RGB", (128, 128), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((16, 16, 112, 112), fill="navy")
            draw.ellipse((40, 40, 88, 88), fill="orange")
            image.save(self.root / name, pnginfo=(lambda info: (info.add_text("Software", "Adobe Photoshop export"), info)[1])(__import__("PIL.PngImagePlugin", fromlist=["PngInfo"]).PngInfo()))
        result = audit_scientific_image_integrity(
            self.root,
            "image-audit-a",
            images=[
                {"id": "original", "role": "original", "path": "original.png"},
                {"id": "processed", "role": "processed", "path": "processed.png", "source_id": "original", "transformation_ids": ["T1"]},
            ],
            transformations=[{"id": "T1", "operation": "format_conversion", "parameters": {}, "applies_to": ["processed"], "justification": "Lossless export for the manuscript."}],
        )
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertTrue(any(item["type"] == "exact_duplicate_image" for item in result["review_flags"]))
        self.assertTrue(any(item["type"] == "editing_software_metadata" for item in result["review_flags"]))
        self.assertIn("not findings", result["conclusion_boundary"])
        self.assertEqual(get_scientific_image_integrity_status(self.root, "image-audit-a")["audit_sha256"], result["audit_sha256"])
        decisions = [
            {"flag_id": f"flag-{index + 1}", "outcome": "explained_expected_relation", "rationale": "The processed file is the declared lossless export of this original."}
            for index, _flag in enumerate(result["review_flags"])
        ]
        reviewed = record_scientific_image_review(
            self.root, "image-audit-a", audit_sha256=result["audit_sha256"],
            review_method="expert_original_resolution", decisions=decisions, reviewer="image integrity reviewer",
        )
        self.assertEqual(reviewed["status"], "PASS")
        plan_paper_audit(self.root, "Audit scientific image integrity")
        attach_paper_auxiliary_audit(self.root, "scientific_image_integrity", reviewed)
        Image.new("RGB", (128, 128), "black").save(self.root / "processed.png")
        status = get_paper_audit_status(self.root)
        self.assertEqual(status["status"], "AUDIT_REQUIRED")
        self.assertIn("scientific image integrity evidence", status["reason"])

    def test_prohibited_image_transformation_is_hard_failure(self):
        from PIL import Image

        Image.new("RGB", (32, 32), "gray").save(self.root / "a.png")
        result = audit_scientific_image_integrity(
            self.root, "image-audit-b",
            images=[{"id": "a", "role": "original", "path": "a.png"}],
            transformations=[{"id": "T1", "operation": "generative_fill", "parameters": {}, "applies_to": ["a"], "justification": "Fill missing content for a cleaner image."}],
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(item["type"] == "prohibited_transformation" for item in result["hard_failures"]))


if __name__ == "__main__":
    unittest.main()
