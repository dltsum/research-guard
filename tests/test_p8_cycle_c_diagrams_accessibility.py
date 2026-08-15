from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from p8_fixtures import diagram_spec


class P8CycleCDiagramAccessibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def plan(self):
        from academic_figure_core import plan_academic_figure

        return plan_academic_figure(
            self.root, figure_id="workflow", request_text="Create an editable vector workflow diagram",
            figure_kind="diagram", source_files=[], width_mm=150, height_mm=70,
            formats=["svg", "pdf", "png"], effort="medium",
            selected_roles=["semantic_diagram", "visual_evidence_integrity", "accessibility_export"],
            selected_by="main_agent", selection_rationale="The main agent selected semantic, visual-integrity, and accessibility review.",
        )

    def test_deterministic_diagram_exports_exact_labels(self):
        from academic_figure_core import render_academic_figure

        self.plan()
        first = render_academic_figure(self.root, "workflow", diagram_spec())
        second = render_academic_figure(self.root, "workflow", diagram_spec())
        self.assertEqual(first["spec_sha256"], second["spec_sha256"])
        self.assertNotEqual(first["revision"], second["revision"])
        self.assertEqual(first["outputs"]["svg"]["sha256"], second["outputs"]["svg"]["sha256"])
        self.assertEqual(first["outputs"]["pdf"]["sha256"], second["outputs"]["pdf"]["sha256"])
        self.assertEqual(first["outputs"]["png"]["sha256"], second["outputs"]["png"]["sha256"])
        first_svg = (self.root / first["outputs"]["svg"]["path"]).read_text(encoding="utf-8")
        for label in ("Planner", "Executor", "Verifier", "revise"):
            self.assertIn(label, first_svg)
        self.assertIn("stroke-dasharray", first_svg)

    def test_dangling_edges_duplicate_nodes_and_overlaps_fail(self):
        from academic_figure_core import FigureError, validate_figure_spec

        for mutation, pattern in (
            (lambda s: s["edges"][0].update({"to": "missing"}), "unknown node"),
            (lambda s: s["nodes"].append(dict(s["nodes"][0])), "duplicate node"),
            (lambda s: s["nodes"][1].update({"x": 0.18, "y": 0.5}), "overlap"),
        ):
            bad = diagram_spec()
            mutation(bad)
            with self.assertRaisesRegex(FigureError, pattern):
                validate_figure_spec(bad, planned_kind="diagram")

    def test_accessibility_metadata_and_redundant_edge_styles_are_required(self):
        from academic_figure_core import FigureError, validate_figure_spec

        bad = diagram_spec()
        bad.pop("alt_text")
        with self.assertRaisesRegex(FigureError, "alt_text"):
            validate_figure_spec(bad, planned_kind="diagram")
        bad = diagram_spec()
        bad["style"]["palette"] = "rainbow"
        with self.assertRaisesRegex(FigureError, "palette"):
            validate_figure_spec(bad, planned_kind="diagram")

    def test_export_audit_rejects_rasterized_vector_containers(self):
        from academic_figure_core import audit_academic_figure, render_academic_figure

        self.plan()
        render_academic_figure(self.root, "workflow", diagram_spec())
        audit = audit_academic_figure(self.root, "workflow")
        self.assertEqual(audit["checks"]["svg"]["embedded_rasters"], 0)
        self.assertEqual(audit["checks"]["pdf"]["embedded_rasters"], 0)
        self.assertGreater(audit["checks"]["pdf"]["extracted_text_characters"], 0)


if __name__ == "__main__":
    unittest.main()
