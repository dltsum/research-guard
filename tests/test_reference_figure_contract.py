from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from PIL import Image, ImageDraw
from academic_figure_core import (
    FigureError, REFERENCE_REVIEW_CHECKS, REFERENCE_STYLE_FIELDS,
    audit_reference_figure, get_reference_figure_status, plan_reference_figure,
)
from figure_pixel_audit import compare


class ReferenceFigureContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.write("paper.md", "# Toy mechanism\nInput A produces output B through module M.\n")
        Image.new("RGB", (128, 128), "white").save(self.root / "reference.png")
        image = Image.new("RGB", (128, 128), "white")
        ImageDraw.Draw(image).rectangle((30, 30, 70, 70), fill="#123456")
        image.save(self.root / "candidate.png")
        self.contract = {
            "figure_id": "toy", "request_text": "Preserve module and edge semantics in reference style.",
            "paper_logic_summary": "A -> M -> B; no measured results are pictured.",
            "manuscript_files": ["paper.md"], "reference_files": ["reference.png"],
            "width_mm": 10, "height_mm": 10, "minimum_dpi": 300,
            "requirements": [{"id": "r1", "text": "Show A -> M -> B.", "paper_anchor": "Methods paragraph 1"}],
            "styles": [{"id": "toy-style", "reference_file": "reference.png", "design_contract": {key: "Preserve the declared reference " + key for key in REFERENCE_STYLE_FIELDS}}],
        }

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value, dict) else value, encoding="utf-8")
        return name

    def bundle(self):
        plan = plan_reference_figure(self.root, self.contract)
        compare(self.root / "reference.png", self.root / "candidate.png", self.root / "pixels",
                regions=[{"id": "module", "reference": [20, 20, 80, 80], "candidate": [20, 20, 80, 80]}],
                geometry={"flat_regions": [
                    {"id": "background", "bbox": [0, 0, 128, 128], "exclude_boxes": [[30, 30, 71, 71]],
                     "exclusion_reason": "The separate solid module, including its border."},
                    {"id": "module", "bbox": [31, 31, 70, 70]}]})
        artifacts = {
            "comparison_audit": self.write("comparison.md", "Native reference versus adapted module: preserved composition; distinct content."),
            "pixel_script": "figure_pixel_audit.py", "pixel_report": "pixels/pixel-audit.json",
            "components_manifest": self.write("components.json", {"items": [{"id": "m", "file": "candidate.png", "meaning": "Module M and its semantic anchors"}]}),
            "internet_assets_manifest": self.write("internet.json", {"items": [], "empty_reason": "Synthetic fixture uses no external assets."}),
            "logic_mapping": self.write("logic.json", {"items": [{"id": "r1", "component_ids": ["m"], "present": True, "explanation": "A -> M -> B matches Methods paragraph 1."}]}),
            "component_audit": self.write("component-audit.json", {"items": [{"id": "r1", "component_ids": ["m"], "present": True, "explanation": "The complete requirement is represented by module m."}]}),
        }
        shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts/figure_pixel_audit.py", self.root / "figure_pixel_audit.py")
        self.write("tool.txt", "Synthetic unit-test record, not an actual image generation call.")
        self.write("prompt.txt", "Synthetic fixture prompt.")
        rounds = []
        for index in (1, 2):
            reviews = []
            for role, checks in REFERENCE_REVIEW_CHECKS.items():
                dialogue = self.write(f"round-{index}-{role}.txt", f"Synthetic {role} test attestation, not a live agent review.")
                reviews.append({
                    "agent_id": role + "-agent", "role": role,
                    "method": "native_resolution_and_paired_crops", "dialogue_file": dialogue,
                    "checks": {key: True for key in checks}, "issues": [],
                })
            rounds.append({"round_id": "round-" + str(index), "image_file": "candidate.png", "reviews": reviews})
        return {"outputs": [{
            "style_id": "toy-style", "final_image": "candidate.png", "artifacts": artifacts,
            "generation_record": {"tool": "image_gen.imagegen", "availability_checked_at": "2026-10-19T00:00:00Z", "availability_evidence": "tool.txt", "tool_record": "tool.txt", "prompt_file": "prompt.txt", "model_id": None, "model_selection_supported": False},
            "rounds": rounds,
        }]}

    def test_complete_bundle_and_component_edit_can_be_reviewed(self):
        bundle = self.bundle()
        result = audit_reference_figure(self.root, "toy", bundle)
        self.assertEqual(result["status"], "PASS")
        self.write("comparison.md", "Changed comparison can be reviewed directly.")
        self.assertEqual(get_reference_figure_status(self.root, "toy")["status"], "PASS")
        self.assertEqual(audit_reference_figure(self.root, "toy", bundle)["status"], "PASS")

    def test_manuscript_edit_does_not_force_replanning(self):
        bundle = self.bundle()
        self.write("paper.md", "The current manuscript still describes A through M to B.")
        self.assertEqual(audit_reference_figure(self.root, "toy", bundle)["status"], "PASS")

    def test_wrong_physical_aspect_ratio_is_rejected(self):
        # Both 128px sides meet this 10mm x 5mm, 300dpi plan's minimum
        # resolution. Delivering a square would nevertheless stretch the image
        # when printed at the locked 2:1 physical size.
        self.contract["height_mm"] = 5
        bundle = self.bundle()
        with self.assertRaisesRegex(FigureError, "aspect ratio"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_one_agent_cannot_impersonate_all_three_roles(self):
        bundle = self.bundle()
        for review in bundle["outputs"][0]["rounds"][0]["reviews"]:
            review["agent_id"] = "same-agent"
        with self.assertRaisesRegex(FigureError, "distinct agent"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_multi_round_review_required_without_digest_fields(self):
        bundle = self.bundle()
        one = copy.deepcopy(bundle)
        one["outputs"][0]["rounds"] = one["outputs"][0]["rounds"][:1]
        with self.assertRaisesRegex(FigureError, "two three-agent"):
            audit_reference_figure(self.root, "toy", one)
        bundle.pop("plan_sha256", None)
        for round_record in bundle["outputs"][0]["rounds"]:
            for review in round_record["reviews"]:
                review.pop("candidate_sha256", None)
                review.pop("reference_sha256", None)
        self.assertEqual(audit_reference_figure(self.root, "toy", bundle)["status"], "PASS")

    def test_missing_requirement_is_rejected_instead_of_style_simplification(self):
        bundle = self.bundle()
        self.write("logic.json", {"items": [{"id": "different", "present": True, "component_ids": ["m"], "explanation": "Omitted required fact."}]})
        with self.assertRaisesRegex(FigureError, "every locked requirement"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_final_false_detail_check_records_correction_not_pass(self):
        bundle = self.bundle()
        review = next(row for row in bundle["outputs"][0]["rounds"][-1]["reviews"] if row["role"] == "detail")
        review["checks"]["no_blur"] = False
        review["issues"] = ["Module heading is blurred at native size."]
        self.assertEqual(audit_reference_figure(self.root, "toy", bundle)["status"], "CORRECTION_REQUIRED")

    def test_unknown_or_omitted_default_style_is_rejected(self):
        contract = copy.deepcopy(self.contract)
        contract["reference_files"] = []
        self.write("catalog.json", {"styles": [{"id": "toy-style", "verified": True}, {"id": "other", "verified": True}]})
        contract["style_catalog_file"] = "catalog.json"
        contract["styles"][0].update({"verified": True, "source_threads": ["historical-thread"]})
        with self.assertRaisesRegex(FigureError, "every verified historical"):
            plan_reference_figure(self.root, contract)
        other = copy.deepcopy(contract["styles"][0])
        other["id"] = "other"
        contract["styles"].append(other)
        plan = plan_reference_figure(self.root, contract)
        self.assertEqual(len(plan["styles"]), 2)
        self.assertEqual(plan["reference_mode"], "all_verified_historical_styles")
        self.write("catalog.json", {"styles": [{"id": item["id"], "verified": True, "design_contract": item["design_contract"], "reference_hashes": {"original": "0" * 64}} for item in contract["styles"]]})
        self.assertEqual(len(plan_reference_figure(self.root, contract)["styles"]), 2)

    def test_missing_internet_license_and_invented_model_version_rejected(self):
        bundle = self.bundle()
        self.write("internet.json", {"items": [{"id": "icon", "source_url": "https://example.org/icon", "used": True}]})
        with self.assertRaisesRegex(FigureError, "license"):
            audit_reference_figure(self.root, "toy", bundle)
        self.write("internet.json", {"items": [], "empty_reason": "No internet assets used."})
        bundle["outputs"][0]["generation_record"]["model_id"] = "imagined-latest-model"
        with self.assertRaisesRegex(FigureError, "model selector"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_pixel_cli_compares_every_pixel_and_detects_declared_geometry_defects(self):
        geometry = {"boxes": [{"id": "a", "bbox": [10, 10, 50, 50], "text_bbox": [10, 10, 20, 20]}, {"id": "b", "bbox": [30, 30, 70, 70]}], "edges": [{"id": "e", "points": [[1, 1], [3, 3], [5, 3], [7, 7]], "max_bends": 1, "source_anchor": [20, 20]}], "flat_regions": [{"id": "fill", "bbox": [20, 20, 80, 80], "max_channel_range": 0}]}
        self.write("geometry.json", geometry)
        script = Path(__file__).resolve().parents[1] / "scripts/figure_pixel_audit.py"
        run = subprocess.run([sys.executable, str(script), str(self.root / "reference.png"), str(self.root / "candidate.png"), "--output", str(self.root / "cli"), "--geometry", str(self.root / "geometry.json")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["pixel_comparison"]["pixels_examined"], 128 * 128)
        self.assertEqual(report["pixel_comparison"]["changed_pixels"], 41 * 41)
        self.assertEqual({item["type"] for item in report["geometry_findings"]}, {"box_overlap", "text_not_centered", "excessive_bends", "disconnected_anchor", "nonuniform_flat_fill"})

    def test_different_sizes_are_not_silently_resized(self):
        Image.new("RGB", (100, 80), "white").save(self.root / "small.png")
        report = compare(self.root / "reference.png", self.root / "small.png", self.root / "mismatch")
        self.assertFalse(report["resized"])
        self.assertEqual(report["pixel_comparison"]["status"], "SIZE_MISMATCH")

    def test_alpha_only_changes_and_native_crop_are_preserved(self):
        Image.new("RGBA", (2, 2), (15, 30, 45, 0)).save(self.root / "alpha-ref.png")
        Image.new("RGBA", (2, 2), (15, 30, 45, 255)).save(self.root / "alpha-cand.png")
        report = compare(self.root / "alpha-ref.png", self.root / "alpha-cand.png", self.root / "alpha",
                         regions=[{"id": "all", "reference": [0, 0, 2, 2], "candidate": [0, 0, 2, 2]}])
        self.assertEqual(report["pixel_comparison"]["changed_pixels"], 0)
        self.assertEqual(report.get("alpha_comparison", {}).get("changed_pixels"), 4)
        self.assertEqual(report["alpha_comparison"]["mean_absolute_difference"], 255)
        with Image.open(self.root / "alpha/crop-001-reference.png") as crop:
            self.assertEqual(crop.mode, "RGBA")
            self.assertEqual(crop.tobytes(), bytes([15, 30, 45, 0]) * 4)

    def test_alpha_only_crop_tampering_is_rejected(self):
        for name in ("reference.png", "candidate.png"):
            with Image.open(self.root / name) as image:
                rgba = image.convert("RGBA")
            rgba.putalpha(128)
            rgba.save(self.root / name)
        bundle = self.bundle()
        path = self.root / "pixels/crop-001-candidate.png"
        with Image.open(path) as image:
            changed = image.convert("RGBA")
        changed.putalpha(0)
        changed.save(path)
        with self.assertRaisesRegex(FigureError, "crop pixels"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_false_alpha_metrics_are_rejected(self):
        for name, alpha in (("reference.png", 64), ("candidate.png", 128)):
            with Image.open(self.root / name) as image:
                rgba = image.convert("RGBA")
            rgba.putalpha(alpha)
            rgba.save(self.root / name)
        bundle = self.bundle()
        path = self.root / "pixels/pixel-audit.json"
        report = json.loads(path.read_text(encoding="utf8"))
        report["alpha_comparison"] = {"status": "COMPARED", "channels": ["A"],
            "pixels_examined": 128 * 128, "changed_pixels": 0,
            "mean_absolute_difference": 0, "maximum_absolute_difference": 0}
        path.write_text(json.dumps(report), encoding="utf8")
        with self.assertRaisesRegex(FigureError, "alpha recomputation"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_fake_pixel_metrics_and_rescaled_crop_are_rejected(self):
        bundle = self.bundle()
        pixel_path = self.root / "pixels/pixel-audit.json"
        report = json.loads(pixel_path.read_text(encoding="utf-8"))
        report["pixel_comparison"]["changed_pixels"] = 0
        self.write("pixels/pixel-audit.json", report)
        with self.assertRaisesRegex(FigureError, "all-pixel recomputation"):
            audit_reference_figure(self.root, "toy", bundle)
        self.bundle()
        Image.new("RGB", (30, 30), "white").save(self.root / "pixels/crop-001-candidate.png")
        with self.assertRaisesRegex(FigureError, "crop pixels"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_missing_deliverable_or_low_resolution_cannot_pass(self):
        bundle = self.bundle()
        omitted = copy.deepcopy(bundle)
        omitted["outputs"][0]["artifacts"].pop("components_manifest")
        with self.assertRaisesRegex(FigureError, "seven deliverable"):
            audit_reference_figure(self.root, "toy", omitted)
        Image.new("RGB", (64, 64), "white").save(self.root / "candidate.png")
        with self.assertRaisesRegex(FigureError, "insufficient"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_geometry_findings_and_unmapped_component_block_pass(self):
        bundle = self.bundle()
        report = json.loads((self.root / "pixels/pixel-audit.json").read_text(encoding="utf-8"))
        report["geometry_findings"] = [{"type": "box_overlap", "ids": ["a", "b"]}]
        self.write("pixels/pixel-audit.json", report)
        self.assertEqual(audit_reference_figure(self.root, "toy", bundle)["status"], "CORRECTION_REQUIRED")
        self.write("components.json", {"items": [{"id": "m", "file": "candidate.png", "meaning": "Module M"}, {"id": "unexplained", "file": "candidate.png", "meaning": "Unmapped decorative element"}]})
        with self.assertRaisesRegex(FigureError, "every component"):
            audit_reference_figure(self.root, "toy", bundle)

    def test_review_rounds_preserve_failed_history_then_accept_repair(self):
        bundle = self.bundle()
        first = bundle["outputs"][0]["rounds"][0]["reviews"][0]
        first["checks"]["all_requirements_present"] = False
        first["issues"] = ["Earlier round omitted an arrow label; corrected in final."]
        result = audit_reference_figure(self.root, "toy", bundle)
        self.assertEqual(result["status"], "PASS")
        saved = get_reference_figure_status(self.root, "toy")
        self.assertEqual(saved["audits"][0]["bundle"]["outputs"][0]["rounds"][0]["reviews"][0]["issues"], first["issues"])

    def test_cleared_findings_cannot_hide_declared_excessive_turns(self):
        bundle = self.bundle()
        path = self.root / "pixels/pixel-audit.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["geometry"]["edges"] = [{"id": "zigzag", "points": [[1, 1], [8, 1], [8, 8], [12, 8]]}]
        report["geometry_findings"] = []
        self.write("pixels/pixel-audit.json", report)
        self.assertEqual(audit_reference_figure(self.root, "toy", bundle)["status"], "CORRECTION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
