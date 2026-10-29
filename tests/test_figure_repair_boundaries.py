"""Synthetic repair/resampling behavior, not image-quality or live-run evidence.

Exercise existing reusable pixel/geometry primitives on actual PNGs. These
fixtures do not prescribe a resize ratio, infer artistic intent or render the
user's figure. All masks are declared from geometry before reading pixel color.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from figure_pixel_audit import compare, flat_fill_metrics


class FigureRepairBoundariesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def surface(self, bounds, exclusions=()):
        return {"flat_regions": [{
            "id": "declared-interior", "bbox": bounds,
            "expected_rgba": [255, 255, 255, 255], "max_channel_range": 0,
            "exclude_boxes": list(exclusions),
            "exclusion_reason": "Known foreground geometry, not detected defect pixels.",
        }]}

    def audit(self, reference, candidate, geometry, name):
        ref_path, candidate_path = self.root / "reference.png", self.root / "candidate.png"
        reference.save(ref_path)
        candidate.save(candidate_path)
        return compare(ref_path, candidate_path, self.root / name, geometry=geometry)

    def test_resampling_fringe_requires_fresh_final_pixel_audit(self):
        before = Image.new("RGBA", (64, 48), "white")
        ImageDraw.Draw(before).rectangle((0, 12, 63, 15), fill="black")
        original = self.audit(before, before,
                              self.surface([0, 0, 64, 48], [[0, 12, 64, 16]]), "before")
        self.assertEqual(original["flat_fill_audit"]["status"], "PASS")
        self.assertEqual(original["flat_fill_audit"]["pixels_examined"], 2816)

        # Nominal geometry scales exactly by 3/4, but Lanczos spreads the edge.
        compact = before.resize((64, 36), Image.Resampling.LANCZOS)
        final_geometry = self.surface([0, 0, 64, 36], [[0, 9, 64, 12]])
        current = self.audit(before, compact, final_geometry, "resampled")
        self.assertEqual(current["candidate_size"], [64, 36])
        self.assertFalse(current["resized"])  # Checker performs no implicit resize.
        self.assertEqual(current["pixel_comparison"]["status"], "SIZE_MISMATCH")
        self.assertEqual(current["flat_fill_audit"]["status"], "FAIL")
        self.assertEqual(current["flat_fill_audit"]["pixels_examined"], 2112)
        self.assertGreater(current["flat_fill_audit"]["regions"][0]["violating_pixels"], 0)

        # Positive control: exact final-size foreground, unchanged expectations.
        repaired = Image.new("RGBA", (64, 36), "white")
        ImageDraw.Draw(repaired).rectangle((0, 9, 63, 11), fill="black")
        result = self.audit(before, repaired, final_geometry, "repaired")
        self.assertEqual(result["flat_fill_audit"]["status"], "PASS")
        failed = json.loads((self.root / "resampled/pixel-audit.json").read_text("utf-8"))
        self.assertEqual(failed["flat_fill_audit"]["status"], "FAIL")

    def test_old_full_height_mask_is_not_accepted_on_shorter_export(self):
        final = Image.new("RGBA", (64, 36), "white")
        with self.assertRaises(ValueError):
            flat_fill_metrics(final, self.surface([0, 0, 64, 48]))

    def test_flat_pass_does_not_excuse_text_overflow_after_compaction(self):
        image = Image.new("RGBA", (64, 48), "white")
        before_geometry = self.surface([0, 0, 64, 48])
        before_geometry["boxes"] = [{"id": "card", "bbox": [4, 4, 60, 44],
                                     "text_bbox": [8, 16, 56, 32]}]
        self.assertEqual(self.audit(image, image, before_geometry, "before")["geometry_findings"], [])
        final = image.resize((64, 36), Image.Resampling.NEAREST)
        geometry = self.surface([0, 0, 64, 36])
        # Keep the declared text size readable; squeezing only the card clips it.
        geometry["boxes"] = [{"id": "card", "bbox": [4, 4, 60, 28],
                              "text_bbox": [8, 16, 56, 32]}]
        report = self.audit(image, final, geometry, "compact")
        self.assertEqual(report["flat_fill_audit"]["status"], "PASS")
        self.assertIn("text_outside_box", {row["type"] for row in report["geometry_findings"]})

    def test_compaction_rechecks_collisions_and_anchor_coordinates(self):
        image = Image.new("RGB", (64, 36), "white")
        geometry = self.surface([0, 0, 64, 36])
        geometry["boxes"] = [{"id": "title", "bbox": [8, 4, 56, 16]},
                             {"id": "control", "bbox": [44, 12, 60, 20]}]
        geometry["edges"] = [{"id": "crossing", "points": [[4, 24], [60, 24]],
                              "source_anchor": [4, 32], "target_anchor": [60, 24]}]
        report = self.audit(image, image, geometry, "compact")
        findings = {row["type"]: row for row in report["geometry_findings"]}
        self.assertEqual(findings["box_overlap"]["area_px"], 48)
        self.assertEqual(findings["disconnected_anchor"]["distance_px"], 8)

    def test_complete_text_footprint_cleared_without_clipping_icon(self):
        image = Image.new("RGBA", (40, 24), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((2, 6, 8, 17), fill=(20, 60, 120, 255))  # Preserved icon.
        draw.rectangle((12, 6, 27, 13), fill="black")  # Nominal old label.
        image.putpixel((28, 15), (220, 220, 220, 255))  # Descender/fringe remnant.
        icon = image.crop((2, 6, 9, 18)).tobytes()
        scope = self.surface([0, 0, 40, 24], [[2, 6, 9, 18]])
        draw.rectangle((12, 6, 27, 13), fill="white")
        partial = flat_fill_metrics(image, scope)
        self.assertEqual(partial["status"], "FAIL")
        self.assertEqual(partial["regions"][0]["violation_bbox"], [28, 15, 29, 16])
        draw.rectangle((12, 6, 28, 15), fill="white")
        self.assertEqual(flat_fill_metrics(image, scope)["status"], "PASS")
        self.assertEqual(image.crop((2, 6, 9, 18)).tobytes(), icon)

    def test_accidental_ring_measured_separately_from_declared_glass(self):
        image = Image.new("RGBA", (40, 24), "white")
        draw = ImageDraw.Draw(image)
        # Intent supplied by fixture geometry, never inferred from pale colors.
        draw.arc((2, 2, 14, 14), 180, 270, fill=(240, 246, 252, 255), width=2)
        glass = image.crop((2, 2, 15, 15)).tobytes()
        draw.ellipse((24, 2, 36, 14), outline=(250, 250, 250, 255))
        scope = self.surface([0, 0, 40, 24], [[2, 2, 15, 15]])
        self.assertEqual(flat_fill_metrics(image, scope)["status"], "FAIL")
        draw.rectangle((24, 2, 36, 14), fill="white")
        self.assertEqual(flat_fill_metrics(image, scope)["status"], "PASS")
        self.assertEqual(image.crop((2, 2, 15, 15)).tobytes(), glass)

    def test_chrome_fill_pass_cannot_certify_foreground_layer_preservation(self):
        before = Image.new("RGBA", (40, 24), "white")
        draw = ImageDraw.Draw(before)
        title, arrow = (4, 4, 12, 8), (20, 0, 22, 16)
        draw.rectangle((4, 4, 11, 7), fill="black")
        draw.rectangle((20, 0, 21, 15), fill=(20, 60, 120, 255))
        scope = self.surface([0, 0, 40, 24], [list(title), list(arrow)])
        bad = before.copy()
        ImageDraw.Draw(bad).rectangle((0, 2, 39, 10), fill="white")
        self.assertEqual(flat_fill_metrics(bad, scope)["status"], "PASS")
        # The excluded title/arrow are damaged despite that legitimate scoped PASS.
        for bounds in (title, arrow):
            self.assertNotEqual(bad.crop(bounds).tobytes(), before.crop(bounds).tobytes())
        for bounds in (title, arrow):
            bad.paste(before.crop(bounds), bounds[:2])  # Restore original layer order.
        self.assertEqual(flat_fill_metrics(bad, scope)["status"], "PASS")
        for bounds in (title, arrow):
            self.assertEqual(bad.crop(bounds).tobytes(), before.crop(bounds).tobytes())


if __name__ == "__main__":
    unittest.main()
