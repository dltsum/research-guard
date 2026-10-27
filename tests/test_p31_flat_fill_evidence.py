"""Pixel and integration behavior, not synthetic reviewer-quality evidence."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from PIL import Image, ImageDraw
import figure_pixel_audit as pixels
from academic_figure_core import FigureError, audit_reference_figure
from test_reference_figure_contract import ReferenceFigureContractTests


class FlatFillEvidenceTests(unittest.TestCase):
    def geometry(self, size=8, **updates):
        return {"flat_regions": [{"id": "surface", "bbox": [0, 0, size, size],
                                  "max_channel_range": 0, **updates}]}

    def test_missing_scope_is_not_run_not_a_pass(self):
        report = pixels.flat_fill_metrics(Image.new("RGB", (8, 8), "white"))
        self.assertEqual(report["status"], "NOT_RUN")
        self.assertEqual(report["pixels_examined"], 0)

    def test_uniform_surface_examines_every_pixel(self):
        report = pixels.flat_fill_metrics(Image.new("RGB", (8, 8), (240, 241, 242)), self.geometry())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["pixels_examined"], 64)
        self.assertEqual(report["regions"][0]["channel_ranges"], [0, 0, 0, 0])

    def test_single_pixel_defect_not_lost_to_sampling(self):
        image = Image.new("RGB", (8, 8), (100, 100, 100))
        image.putpixel((7, 6), (101, 100, 100))
        report = pixels.flat_fill_metrics(image, self.geometry())
        region = report["regions"][0]
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(region["pixels_examined"], 64)
        self.assertEqual(region["violating_pixels"], 1)
        self.assertEqual(region["first_violations"][0]["xy"], [7, 6])
        self.assertEqual(region["violation_bbox"], [7, 6, 8, 7])

    def test_smooth_gradient_fails_even_without_spots(self):
        image = Image.new("RGB", (8, 8))
        for y in range(8):
            for x in range(8):
                image.putpixel((x, y), (220 + x, 230, 240))
        region = pixels.flat_fill_metrics(image, self.geometry())["regions"][0]
        self.assertEqual(region["status"], "FAIL")
        self.assertEqual(region["channel_ranges"], [7, 0, 0, 0])
        self.assertEqual(region["violating_pixels"], 56)

    def test_text_exclusion_preserves_exact_coverage(self):
        image = Image.new("RGB", (8, 8), "white")
        ImageDraw.Draw(image).rectangle((2, 2, 4, 4), fill="black")
        report = pixels.flat_fill_metrics(image, self.geometry(exclude_boxes=[[2, 2, 5, 5]], exclusion_reason="Known text foreground."))
        region = report["regions"][0]
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(region["pixels_examined"], 55)
        self.assertEqual(region["pixels_excluded"], 9)

    def test_alpha_only_nonuniformity_is_detected(self):
        image = Image.new("RGBA", (8, 8), (20, 30, 40, 200))
        image.putpixel((3, 4), (20, 30, 40, 201))
        report = pixels.flat_fill_metrics(image, self.geometry())
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["regions"][0]["channel_ranges"], [0, 0, 0, 1])

    def test_expected_color_and_declared_tolerance(self):
        image = Image.new("RGBA", (8, 8), (11, 20, 30, 255))
        self.assertEqual(pixels.flat_fill_metrics(image, self.geometry(expected_rgba=[10, 20, 30, 255]))["status"], "FAIL")
        self.assertEqual(pixels.flat_fill_metrics(image, self.geometry(expected_rgba=[10, 20, 30, 255], max_channel_range=1))["status"], "PASS")

    def test_invalid_or_empty_scope_cannot_silently_pass(self):
        image = Image.new("RGB", (8, 8), "white")
        cases = [self.geometry(max_channel_range=-1), self.geometry(max_channel_range=True),
                 self.geometry(exclude_boxes=[[0, 0, 8, 8]], exclusion_reason="Everything"),
                 self.geometry(exclude_boxes=[[1, 1, 2, 2]]),
                 self.geometry(expected_rgba=[256, 0, 0, 255])]
        for geometry in cases:
            with self.subTest(geometry=geometry), self.assertRaises(ValueError):
                pixels.flat_fill_metrics(image, geometry)

    def fixture(self):
        case = ReferenceFigureContractTests("runTest")
        case.setUp()
        self.addCleanup(case.tearDown)
        return case

    def test_missing_fill_scope_blocks_all_true_review_booleans(self):
        case = self.fixture()
        bundle = case.bundle()
        pixels.compare(case.root / "reference.png", case.root / "candidate.png", case.root / "pixels",
                       regions=[{"id":"module", "reference":[20,20,80,80], "candidate":[20,20,80,80]}])
        result = audit_reference_figure(case.root, "toy", bundle)
        self.assertEqual(result["status"], "CORRECTION_REQUIRED")
        self.assertTrue(any("flat_fill" in entry for entry in result["unresolved"]))

    def test_uneven_fill_blocks_even_when_findings_list_cleared(self):
        case = self.fixture()
        bundle = case.bundle()
        pixels.compare(case.root / "reference.png", case.root / "candidate.png", case.root / "pixels",
                       regions=[{"id":"module", "reference":[20,20,80,80], "candidate":[20,20,80,80]}],
                       geometry={"flat_regions":[{"id":"bad", "bbox":[20,20,80,80]}]})
        path = case.root / "pixels/pixel-audit.json"
        report = json.loads(path.read_text("utf-8"))
        report["geometry_findings"] = []
        path.write_text(json.dumps(report), encoding="utf-8")
        self.assertEqual(audit_reference_figure(case.root, "toy", bundle)["status"], "CORRECTION_REQUIRED")
        report["flat_fill_audit"]["status"] = "PASS"
        path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(FigureError, "flat-fill recomputation"):
            audit_reference_figure(case.root, "toy", bundle)

    def test_cli_required_fill_missing_or_failed_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGB", (8, 8), "white").save(root / "image.png")
            command = [sys.executable, str(ROOT / "scripts/figure_pixel_audit.py"), str(root / "image.png"),
                       str(root / "image.png"), "--output", str(root / "audit"), "--require-flat-fills"]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(json.loads(run.stdout)["flat_fill_audit"]["status"], "NOT_RUN")
            (root / "geometry.json").write_text(json.dumps(self.geometry()), encoding="utf-8")
            run = subprocess.run(command + ["--geometry", str(root / "geometry.json")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["flat_fill_audit"]["status"], "PASS")
            image = Image.new("RGB", (8, 8), "white")
            image.putpixel((7, 7), (250, 255, 255))
            image.save(root / "image.png")
            run = subprocess.run(command + ["--geometry", str(root / "geometry.json")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(json.loads(run.stdout)["flat_fill_audit"]["status"], "FAIL")

    def test_excluded_foreground_does_not_hide_nearby_defect(self):
        image = Image.new("RGB", (8, 8), "white")
        ImageDraw.Draw(image).rectangle((2, 2, 4, 4), fill="black")
        image.putpixel((7, 7), (254, 255, 255))
        report = pixels.flat_fill_metrics(image, self.geometry(exclude_boxes=[[2, 2, 5, 5]],
                                                               exclusion_reason="Known text foreground."))
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["pixels_examined"], 55)

    def test_size_mismatch_does_not_skip_candidate_fill_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGB", (12, 12), "white").save(root / "ref.png")
            image = Image.new("RGB", (8, 8), "white")
            image.putpixel((7, 7), (254, 255, 255))
            image.save(root / "candidate.png")
            report = pixels.compare(root / "ref.png", root / "candidate.png", root / "audit", geometry=self.geometry())
            self.assertEqual(report["pixel_comparison"]["status"], "SIZE_MISMATCH")
            self.assertEqual(report["flat_fill_audit"]["status"], "FAIL")
            self.assertEqual(report["flat_fill_audit"]["pixels_examined"], 64)

    def test_real_mcp_dispatch_cannot_upgrade_missing_fill_evidence(self):
        import mcp_server
        case = self.fixture()
        bundle = case.bundle()
        pixels.compare(case.root / "reference.png", case.root / "candidate.png", case.root / "pixels",
                       regions=[{"id":"module", "reference":[20,20,80,80], "candidate":[20,20,80,80]}])
        result = mcp_server.dispatch("paper_audit", {"action":"status", "project_root":str(case.root),
            "figure_action":"reference_audit", "figure_id":"toy", "reference_bundle":bundle})
        self.assertEqual(result["status"], "CORRECTION_REQUIRED")
        saved = mcp_server.dispatch("paper_audit", {"action":"status", "project_root":str(case.root),
            "figure_action":"reference_status", "figure_id":"toy"})
        self.assertEqual(saved["status"], "CORRECTION_REQUIRED")

    def test_selected_figures_install_contains_rules_and_runs_strict_checker(self):
        from component_install import install_components
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "figures"
            installed = install_components(ROOT, target, ["figures"])
            self.assertEqual(installed["network_operations"], 0)
            self.assertTrue((target / "docs/FIGURE_FLAT_FILL_AUDIT.md").is_file())
            self.assertTrue((target / "docs/FIGURE_FLAT_FILL_AUDIT.zh-CN.md").is_file())
            Image.new("RGB", (8, 8), "white").save(target / "image.png")
            run = subprocess.run([sys.executable, str(target / "scripts/figure_pixel_audit.py"),
                str(target / "image.png"), str(target / "image.png"), "--output", str(target / "audit"),
                "--require-flat-fills"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(json.loads(run.stdout)["flat_fill_audit"]["status"], "NOT_RUN")

    def test_repair_cycle_rescans_current_pixels_without_reusing_pass(self):
        case = self.fixture()
        bundle = case.bundle()
        report_path = case.root / "pixels/pixel-audit.json"
        original = json.loads(report_path.read_text("utf-8"))
        kwargs = {"regions": [{"id": "module", "reference": [20, 20, 80, 80],
                               "candidate": [20, 20, 80, 80]}],
                  "geometry": original["geometry"]}
        with Image.open(case.root / "candidate.png") as source:
            image = source.copy()
        for color, expected in (((254, 255, 255), "CORRECTION_REQUIRED"),
                                ((255, 255, 255), "PASS"),
                                ((255, 254, 255), "CORRECTION_REQUIRED")):
            image.putpixel((5, 5), color)
            image.save(case.root / "candidate.png")
            current = pixels.compare(case.root / "reference.png", case.root / "candidate.png",
                                     case.root / "pixels", **kwargs)
            self.assertEqual(current["flat_fill_audit"]["pixels_examined"], 16224)
            self.assertEqual(audit_reference_figure(case.root, "toy", bundle)["status"], expected)


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromTestCase(FlatFillEvidenceTests)


if __name__ == "__main__":
    unittest.main()
