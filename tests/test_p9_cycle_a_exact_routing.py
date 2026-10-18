from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from venue_evidence_core import list_venue_profiles, resolve_venue_profile  # noqa: E402


from venue_fixture import install_venue_fixtures  # noqa: E402


class P9CycleAExactRoutingTests(unittest.TestCase):
    def setUp(self):
        install_venue_fixtures(self)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_seed_covers_registered_top_venue_families_with_https_sources(self):
        result = list_venue_profiles(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertGreaterEqual(len(result["profiles"]), 10)
        for profile in result["profiles"]:
            self.assertTrue(profile["policy_url"].startswith("https://"))
            self.assertTrue(profile["template_url"].startswith("https://"))
            self.assertTrue(profile["paper_links"])
            self.assertTrue(all(link.startswith("https://") for link in profile["paper_links"]))

    def test_resolution_is_exact_and_emits_hash_bound_receipt(self):
        result = resolve_venue_profile(self.root, "NeurIPS", 2025, "main", "submission")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["profile"]["venue"], "neurips")
        self.assertEqual(result["profile"]["year"], 2025)
        self.assertEqual(result["profile"]["stage"], "submission")
        self.assertRegex(result["receipt_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(result["profile"]["assets_verified"])

    def test_missing_payload_requires_online_acquisition(self):
        # Preserve the clean-checkout failure mode: never authorize missing data.
        with tempfile.TemporaryDirectory() as empty:
            with patch("venue_evidence_core.ASSET_ROOT", Path(empty)):
                result = resolve_venue_profile(self.root, "NeurIPS", 2025, "main", "submission")
        self.assertEqual(result["status"], "ONLINE_ACQUISITION_REQUIRED")
        self.assertNotIn("profile", result)

    def test_missing_year_never_falls_back(self):
        result = resolve_venue_profile(self.root, "NeurIPS", 2024, "main", "submission")
        self.assertEqual(result["status"], "ONLINE_ACQUISITION_REQUIRED")
        self.assertNotIn("profile", result)
        self.assertTrue(result["queries"])
        self.assertTrue(all(item["url"].startswith("https://") for item in result["required_sources"]))


if __name__ == "__main__":
    unittest.main()
