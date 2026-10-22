from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_guard_core import verify_index_membership


class CCFMembershipTests(unittest.TestCase):
    def test_exact_venue_uses_bound_official_catalog(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("Do not reread the catalog for a digest")):
            result = verify_index_membership("  icra  ", "CCF")
        self.assertTrue(result["verified"])
        self.assertEqual(result["membership"], "B")
        self.assertEqual(result["status"], "VERIFIED_CATALOG_SNAPSHOT")
        self.assertFalse(result["live_revalidated"])
        self.assertEqual(result["matches"][0]["venue"], "ICRA")
        self.assertTrue(result["matches"][0]["ccf_category_url"].startswith("https://www.ccf.org.cn/"))
        self.assertIn("paper", result["authority_boundary"].lower())

    def test_fuzzy_and_doi_queries_cannot_be_reported_as_members(self):
        for value in ("Robotics", "ICRA 2025", "10.1109/ICRA55743.2025.11127402", "invented-venue"):
            with self.subTest(value=value):
                result = verify_index_membership(value, "ccf")
                self.assertFalse(result["verified"])
                self.assertEqual(result["membership"], "UNKNOWN")
                self.assertEqual(result["status"], "EXACT_VENUE_REQUIRED")

    def test_corrupt_catalog_fails_closed(self):
        with patch("ccf_catalog_core.load_catalog", side_effect=ValueError("catalog entries are malformed")):
            result = verify_index_membership("ICRA", "ccf")
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "CATALOG_UNAVAILABLE")
        self.assertEqual(result["membership"], "UNKNOWN")

    def test_other_indexes_are_not_inferred_from_ccf(self):
        self.assertEqual(verify_index_membership("ICRA", "wos_sci")["status"], "NOT_CONFIGURED")
        self.assertEqual(verify_index_membership("ICRA", "invented")["status"], "NOT_SUPPORTED")


if __name__ == "__main__":
    unittest.main()
