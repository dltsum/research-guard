from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))
from academic_figure_core import plan_academic_figure, render_academic_figure


class FigureReplanAppendOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="figure-replan-", dir=PLUGIN.parent)
        self.root = Path(self.temp.name)
        (self.root / "data.csv").write_text("step,value\n1,3\n2,2\n", encoding="utf-8")
        self.spec = {
            "kind": "statistical", "chart_type": "line", "data_file": "data.csv",
            "x": "step", "y": "value", "x_label": "Step", "y_label": "Value",
            "claim": "A deterministic append-only lifecycle regression.",
            "alt_text": "Two numeric points used to verify exported revisions are retained.",
            "missing_policy": "error",
            "summary": {"estimator": "mean", "uncertainty": "none", "replicate_unit": "test row"},
        }

    def tearDown(self):
        self.temp.cleanup()

    def plan(self):
        return plan_academic_figure(
            self.root, figure_id="replan", request_text="Retain every previous rendered revision.",
            figure_kind="statistical", source_files=["data.csv"], width_mm=90, height_mm=65,
            selected_roles=["statistical_numeric", "visual_evidence_integrity"],
            selected_by="main_agent", selection_rationale="Check numeric evidence and append-only output integrity.",
        )

    def test_replan_after_source_change_keeps_original_exports(self):
        first_plan = self.plan()
        first = render_academic_figure(self.root, "replan", self.spec)
        before = {p: hashlib.sha256((self.root / p).read_bytes()).hexdigest()
                  for p in (item["path"] for item in first["outputs"].values())}
        (self.root / "data.csv").write_text("step,value\n1,4\n2,1\n", encoding="utf-8")
        second_plan = self.plan()
        self.assertNotEqual(first_plan["plan_sha256"], second_plan["plan_sha256"])
        second = render_academic_figure(self.root, "replan", self.spec)
        self.assertEqual(second["revision"], 2)
        self.assertIn("/v002/", second["outputs"]["png"]["path"])
        self.assertEqual(before, {p: hashlib.sha256((self.root / p).read_bytes()).hexdigest() for p in before})

    def test_interrupted_reserved_revision_is_not_overwritten(self):
        self.plan()
        render_academic_figure(self.root, "replan", self.spec)
        reserved = self.root / "figures/replan/v003"
        reserved.mkdir()
        evidence = reserved / "partial-render.txt"
        evidence.write_text("Retain evidence from an interrupted render.", encoding="utf-8")
        self.plan()
        following = render_academic_figure(self.root, "replan", self.spec)
        self.assertEqual(following["revision"], 4)
        self.assertEqual(evidence.read_text(encoding="utf-8"), "Retain evidence from an interrupted render.")

    def test_numeric_axis_preserves_numerical_point_order(self):
        (self.root / "data.csv").write_text("step,value\n1,3\n10,1\n2,2\n", encoding="utf-8")
        self.plan()
        rendered = render_academic_figure(self.root, "replan", self.spec)
        points = rendered["statistics"]["groups"]
        self.assertEqual([point["x"] for point in points], [1.0, 2.0, 10.0])
        self.assertEqual([point["center"] for point in points], [3.0, 2.0, 1.0])


if __name__ == "__main__":
    unittest.main()
