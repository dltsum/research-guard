from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from p8_fixtures import PLUGIN, plan_statistical, statistical_spec


class P8CycleEIntegrityHeldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        plan_statistical(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_path_escape_and_symlink_input_fail_closed(self):
        from academic_figure_core import FigureError, plan_academic_figure

        with self.assertRaisesRegex(FigureError, "inside project_root"):
            plan_academic_figure(
                self.root, figure_id="escape", request_text="plot", figure_kind="statistical",
                source_files=["../outside.csv"], width_mm=89, height_mm=60,
            )
        target = self.root / "data" / "training.csv"
        link = self.root / "data" / "linked.csv"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlink creation is unavailable")
        with self.assertRaisesRegex(FigureError, "symlink"):
            plan_academic_figure(
                self.root, figure_id="link", request_text="plot", figure_kind="statistical",
                source_files=["data/linked.csv"], width_mm=89, height_mm=60,
            )

    def test_state_and_manifest_tampering_are_detected(self):
        from academic_figure_core import FigureError, get_academic_figure_status, render_academic_figure

        rendered = render_academic_figure(self.root, "training", statistical_spec())
        manifest = self.root / rendered["outputs"]["manifest"]["path"]
        value = json.loads(manifest.read_text(encoding="utf-8"))
        value["statistics"]["rows_used"] = 1
        manifest.write_text(json.dumps(value), encoding="utf-8")
        status = get_academic_figure_status(self.root, "training")
        self.assertEqual(status["status"], "RENDER_REQUIRED")
        self.assertRegex(status["reason"], "manifest|changed")

    def test_forbidden_visual_encodings_fail(self):
        from academic_figure_core import FigureError, validate_figure_spec

        for key, value, pattern in (
            ("three_dimensional", True, "3D"),
            ("dual_axis", True, "dual"),
            ("excluded_rows", [1, 2], "exclusion"),
        ):
            bad = statistical_spec()
            bad[key] = value
            with self.assertRaisesRegex(FigureError, pattern):
                validate_figure_spec(bad, planned_kind="statistical")

    def test_compact_skill_and_dependency_manifest(self):
        skill = PLUGIN / "skills" / "academic-figure-guard" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertLess(len(text.split()), 320)
        self.assertIn("figure_action", text)
        requirements = (PLUGIN / "scripts" / "requirements-figure.txt").read_text(encoding="utf-8")
        self.assertIn("matplotlib", requirements)
        self.assertIn("pypdf", requirements)
        self.assertNotIn("seaborn", requirements.lower())
        self.assertNotIn("plotly", requirements.lower())

    def test_reproduction_script_does_not_disclose_local_plugin_path(self):
        from academic_figure_core import render_academic_figure

        rendered = render_academic_figure(self.root, "training", statistical_spec())
        script = (self.root / rendered["outputs"]["reproduce"]["path"]).read_text(encoding="utf-8")
        self.assertNotIn("Users/12164", script.replace("\\", "/"))
        self.assertNotIn("plugins/research-guard", script.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
