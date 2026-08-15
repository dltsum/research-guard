from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from p8_fixtures import plan_statistical, statistical_spec, write_training_csv


class P8CycleBStatisticalRenderingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        plan_statistical(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_render_binds_all_rows_statistics_and_vector_outputs(self):
        from academic_figure_core import render_academic_figure

        result = render_academic_figure(self.root, "training", statistical_spec())
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["statistics"]["rows_total"], 8)
        self.assertEqual(result["statistics"]["rows_used"], 8)
        self.assertEqual(result["statistics"]["uncertainty"], "sd")
        self.assertEqual(result["statistics"]["replicate_unit"], "independent seed")
        self.assertEqual(set(result["outputs"]), {"svg", "pdf", "png", "spec", "manifest", "reproduce"})
        for item in result["outputs"].values():
            self.assertTrue((self.root / item["path"]).is_file())
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
        svg = (self.root / result["outputs"]["svg"]["path"]).read_text(encoding="utf-8")
        self.assertIn("<text", svg)
        self.assertNotIn("image/png", svg)

    def test_missing_values_fail_closed_without_explicit_policy(self):
        from academic_figure_core import FigureError, plan_academic_figure, render_academic_figure

        root = self.root / "missing-case"
        write_training_csv(root, missing=True)
        plan_academic_figure(
            root, figure_id="missing", request_text="Plot results", figure_kind="statistical",
            source_files=["data/training.csv"], width_mm=89, height_mm=60,
            selected_roles=["statistical_numeric", "visual_evidence_integrity"],
            selected_by="main_agent", selection_rationale="The main agent selected statistical and visual-integrity review.",
        )
        with self.assertRaisesRegex(FigureError, "missing"):
            render_academic_figure(root, "missing", statistical_spec())
        spec = statistical_spec(missing_policy="gap")
        spec["summary"]["uncertainty"] = "none"
        result = render_academic_figure(root, "missing", spec)
        self.assertEqual(result["statistics"]["missing_y"], 1)
        self.assertEqual(result["statistics"]["rows_used"], 7)

    def test_misleading_axes_and_undefined_uncertainty_are_rejected(self):
        from academic_figure_core import FigureError, validate_figure_spec

        bad = statistical_spec()
        bad["chart_type"] = "bar"
        bad["y_limits"] = [0.5, 0.7]
        with self.assertRaisesRegex(FigureError, "bar baseline"):
            validate_figure_spec(bad, planned_kind="statistical")
        bad = statistical_spec()
        bad["summary"]["replicate_unit"] = ""
        with self.assertRaisesRegex(FigureError, "replicate"):
            validate_figure_spec(bad, planned_kind="statistical")
        bad = statistical_spec()
        bad["y_scale"] = "log"
        bad["missing_policy"] = "drop"
        with self.assertRaisesRegex(FigureError, "missing_policy"):
            validate_figure_spec(bad, planned_kind="statistical")

    def test_raw_estimators_and_predeclared_exclusions_are_not_silently_summarized(self):
        from academic_figure_core import FigureError, render_academic_figure, validate_figure_spec

        bad = statistical_spec()
        bad["summary"] = {"estimator": "raw", "uncertainty": "none", "replicate_unit": "independent seed", "seed": 1}
        with self.assertRaisesRegex(FigureError, "raw"):
            validate_figure_spec(bad, planned_kind="statistical")
        spec = statistical_spec()
        spec["exclusions"] = [{
            "row_numbers": [2], "reason": "Predeclared corrupted acquisition row confirmed before visualization.",
            "predeclared": True, "selected_by": "user",
        }]
        spec["summary"]["uncertainty"] = "none"
        result = render_academic_figure(self.root, "training", spec)
        self.assertEqual(result["statistics"]["rows_excluded"], 1)
        self.assertEqual(result["statistics"]["rows_used"], 7)
        self.assertEqual(result["statistics"]["exclusions"][0]["row_numbers"], [2])

    def test_raw_scatter_is_allowed_and_categorical_bar_values_are_supported(self):
        from academic_figure_core import plan_academic_figure, render_academic_figure, validate_figure_spec

        scatter = statistical_spec()
        scatter["chart_type"] = "scatter"
        scatter["summary"] = {"estimator": "raw", "uncertainty": "none", "replicate_unit": "independent seed", "seed": 1}
        validate_figure_spec(scatter, planned_kind="statistical")
        categorical = self.root / "data" / "categorical.csv"
        categorical.write_text("benchmark,method,seed,score\nA,Baseline,1,0.5\nA,Method A,1,0.6\nB,Baseline,1,0.7\nB,Method A,1,0.8\n", encoding="utf-8")
        plan_academic_figure(
            self.root, figure_id="categorical", request_text="Grouped categorical bar plot",
            figure_kind="statistical", source_files=["data/categorical.csv"], width_mm=89, height_mm=60,
            selected_roles=["statistical_numeric", "visual_evidence_integrity"],
            selected_by="main_agent", selection_rationale="The main agent selected statistical and visual-integrity review.",
        )
        spec = statistical_spec()
        spec.update({"chart_type": "bar", "data_file": "data/categorical.csv", "x": "benchmark"})
        spec["summary"]["uncertainty"] = "none"
        result = render_academic_figure(self.root, "categorical", spec)
        groups = result["statistics"]["groups"]
        self.assertEqual({item["x"] for item in groups}, {"A", "B"})


if __name__ == "__main__":
    unittest.main()
