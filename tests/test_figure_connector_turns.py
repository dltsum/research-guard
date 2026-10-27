"""Actual geometry behavior; no generated-wording assertions."""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from figure_pixel_audit import compare, polyline_bends


class ConnectorTurnsTests(unittest.TestCase):
    def test_straight_samples_and_duplicates_are_not_turns(self):
        self.assertEqual(polyline_bends([[1, 1], [1, 1], [3, 1], [6, 1], [9, 1]]), 0)

    def test_diagonal_collinear_samples_are_not_turns(self):
        self.assertEqual(polyline_bends([[1, 1], [3, 3], [7, 7]]), 0)

    def test_elbow_and_reversal_count(self):
        self.assertEqual(polyline_bends([[1, 1], [3, 1], [3, 4]]), 1)
        self.assertEqual(polyline_bends([[1, 1], [3, 1], [1, 1]]), 1)

    def test_zigzag_is_not_hidden_by_sampling(self):
        self.assertEqual(polyline_bends([[1, 1], [2, 1], [3, 1], [3, 3], [5, 3], [5, 5]]), 3)

    def test_invalid_or_zero_length_path_rejected(self):
        for points in ([], [[1, 1]], [[1, 1], [1, 1]], [[True, 1], [2, 2]], [[1, 1], [float('nan'), 2]]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                polyline_bends(points)

    def findings(self, edge):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (20, 20), "white").save(root / "image.png")
            return compare(root / "image.png", root / "image.png", root / "audit",
                           geometry={"edges": [dict(id="e", **edge)]})["geometry_findings"]

    def test_default_budget_rejects_two_turns(self):
        result = self.findings({"points": [[1, 1], [4, 1], [4, 4], [8, 4]]})
        self.assertEqual(result[0]["type"], "excessive_bends")
        self.assertEqual(result[0]["bends"], 2)

    def test_explicit_straight_budget_accepts_many_collinear_samples(self):
        self.assertEqual(self.findings({"points": [[1, 1], [2, 1], [5, 1]], "max_bends": 0}), [])

    def test_exception_needs_reason_and_does_not_override_count(self):
        edge = {"points": [[1, 1], [4, 1], [4, 4], [8, 4]], "max_bends": 2}
        self.assertEqual(self.findings(edge)[0]["type"], "unjustified_bend_budget")
        edge["routing_reason"] = "Return loop around an occupied node; inspected simpler alternatives."
        self.assertEqual(self.findings(edge), [])
        edge["points"].append([8, 8])
        self.assertEqual(self.findings(edge)[0]["type"], "excessive_bends")

    def test_invalid_budget_rejected(self):
        for value in (-1, 1.5, True, "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.findings({"points": [[1, 1], [4, 1]], "max_bends": value})


if __name__ == "__main__":
    unittest.main()
