from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from p8_fixtures import diagram_spec, statistical_spec, write_training_csv


class P8CycleAContractRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        write_training_csv(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_is_hash_bound_bounded_and_high_capped(self):
        from academic_figure_core import plan_academic_figure

        first = plan_academic_figure(
            self.root, figure_id="training", request_text="Plot statistical results with uncertainty",
            figure_kind="statistical", source_files=["data/training.csv"], width_mm=89, height_mm=60,
            formats=["svg", "pdf", "png"], effort="high",
            selected_roles=["statistical_numeric", "visual_evidence_integrity", "accessibility_export"],
            selected_by="main_agent", selection_rationale="The main agent selected the three required statistical figure checks.",
        )
        second = plan_academic_figure(
            self.root, figure_id="training", request_text="Plot statistical results with uncertainty",
            figure_kind="statistical", source_files=["data/training.csv"], width_mm=89, height_mm=60,
            formats=["svg", "pdf", "png"], effort="high",
            selected_roles=["statistical_numeric", "visual_evidence_integrity", "accessibility_export"],
            selected_by="main_agent", selection_rationale="The main agent selected the three required statistical figure checks.",
        )
        self.assertEqual(first["plan_sha256"], second["plan_sha256"])
        self.assertIn(len(first["selected_roles"]), {2, 3})
        self.assertEqual(first["effort"], "high")
        self.assertEqual(first["backend"], "python_matplotlib")
        self.assertFalse(first["automatic_role_selection"])
        self.assertEqual(first["source_files"][0]["path"], "data/training.csv")

    def test_xhigh_and_ai_quantitative_rendering_are_rejected(self):
        from academic_figure_core import FigureError, plan_academic_figure, validate_figure_spec

        with self.assertRaisesRegex(FigureError, "effort"):
            plan_academic_figure(
                self.root, figure_id="bad", request_text="plot", figure_kind="statistical",
                source_files=["data/training.csv"], width_mm=89, height_mm=60, effort="xhigh",
            )
        bad = statistical_spec()
        bad["renderer"] = "image_generation"
        with self.assertRaisesRegex(FigureError, "image generation"):
            validate_figure_spec(bad, planned_kind="statistical")

    def test_no_automatic_ours_highlight_or_hidden_choice(self):
        from academic_figure_core import FigureError, validate_figure_spec

        for key in ("highlight_ours", "recommended_series", "auto_emphasis"):
            bad = statistical_spec()
            bad[key] = "Method A"
            with self.assertRaisesRegex(FigureError, "automatic|forbidden"):
                validate_figure_spec(bad, planned_kind="statistical")
        explicit = statistical_spec()
        explicit["style"]["emphasis_series"] = "Method A"
        explicit["style"]["emphasis_selected_by"] = "user"
        validate_figure_spec(explicit, planned_kind="statistical")

    def test_diagram_contract_does_not_require_an_image_api(self):
        from academic_figure_core import validate_figure_spec

        result = validate_figure_spec(diagram_spec(), planned_kind="diagram")
        self.assertEqual(result["kind"], "diagram")
        self.assertFalse(result["external_image_api"])


if __name__ == "__main__":
    unittest.main()
