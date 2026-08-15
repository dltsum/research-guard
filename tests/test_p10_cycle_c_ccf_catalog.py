from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from ccf_catalog_core import CATEGORY_SOURCES, find_venue, load_catalog  # noqa: E402
from venue_evidence_core import resolve_venue_profile  # noqa: E402


class P10CycleCCCFTests(unittest.TestCase):
    def test_all_ten_official_categories_and_all_a_b_conferences_are_present(self):
        catalog = load_catalog()
        self.assertEqual(len(CATEGORY_SOURCES), 10)
        self.assertEqual(len(catalog["source_assets"]), 10)
        self.assertEqual(catalog["counts"], {"A": 58, "B": 125})
        self.assertEqual(len(catalog["entries"]), 183)
        self.assertTrue(all(entry["ccf_class"] in {"A", "B"} for entry in catalog["entries"]))
        self.assertTrue(all(entry["ccf_record_url"].startswith("https://") for entry in catalog["entries"]))

    def test_catalog_classification_never_authorizes_layout_or_sections(self):
        matches = find_venue("ECCV")
        self.assertTrue(matches)
        self.assertEqual(matches[0]["ccf_class"], "B")
        with tempfile.TemporaryDirectory() as temporary:
            result = resolve_venue_profile(temporary, "ECCV", 2026, "main", "submission")
        self.assertEqual(result["status"], "ONLINE_ACQUISITION_REQUIRED")
        self.assertEqual(result["ccf_catalog_match"]["ccf_class"], "B")
        self.assertNotIn("suggested_sections", result)
        self.assertIn("cannot authorize", result["ccf_boundary"])


if __name__ == "__main__":
    unittest.main()
