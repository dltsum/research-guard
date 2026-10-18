from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from academic_figure_core import FigureError, _prepare_statistical, plan_academic_figure, validate_figure_spec


class StatisticalMissingPolicyDefaultTests(unittest.TestCase):
    def test_omitted_policy_records_error_default_and_still_rejects_missing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data.csv"
            data.write_text("group,value\na,1\na,3\n", encoding="utf-8")
            spec = {"kind": "statistical", "chart_type": "bar", "claim": "Synthetic mean only.",
                    "alt_text": "Two synthetic records are aggregated into one mean bar.",
                    "data_file": "data.csv", "x": "group", "y": "value", "x_label": "Group",
                    "y_label": "Value", "summary": {"estimator": "mean", "uncertainty": "none"}}
            def plan():
                return plan_academic_figure(root, figure_id="default-policy", request_text="Synthetic default-policy test",
                    figure_kind="statistical", source_files=["data.csv"], width_mm=100, height_mm=60,
                    selected_roles=["statistical_numeric", "visual_evidence_integrity"], selected_by="main_agent",
                    selection_rationale="Check statistics and hash-bound input integrity.")
            validate_figure_spec(spec, planned_kind="statistical")
            stats, _ = _prepare_statistical(root, plan(), spec)
            self.assertEqual(stats["missing_policy"], "error")
            self.assertEqual(stats["groups"][0]["center"], 2)
            data.write_text("group,value\na,1\na,\n", encoding="utf-8")
            with self.assertRaises(FigureError):
                _prepare_statistical(root, plan(), spec)


if __name__ == "__main__":
    unittest.main()
