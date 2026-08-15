from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from venue_evidence_core import (  # noqa: E402
    VenueEvidenceError,
    inspect_paper_pdf,
    inspect_template_archive,
    resolve_seed_asset,
)


class P9CycleBAssetInspectionTests(unittest.TestCase):
    def test_official_template_and_paper_are_inspectable_without_inference(self):
        template = resolve_seed_asset("templates/neurips/2025/neurips2025.zip")
        paper = resolve_seed_asset("exemplars/neurips/2025/depth1000.pdf")
        template_result = inspect_template_archive(template)
        paper_result = inspect_paper_pdf(paper)
        self.assertEqual(template_result["status"], "PASS")
        self.assertTrue(template_result["tex_files"])
        self.assertTrue(template_result["observed_headings"])
        self.assertEqual(template_result["layout_authority"], "official_template_only")
        self.assertEqual(paper_result["status"], "PASS")
        self.assertGreater(paper_result["page_count"], 1)
        self.assertTrue(paper_result["observed_headings"])
        self.assertEqual(paper_result["heading_scope"], "observed_in_this_paper")

    def test_zip_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.tex", "\\section{Invented}")
            with self.assertRaises(VenueEvidenceError):
                inspect_template_archive(path)

    def test_heading_extraction_rejects_body_numbers_and_supports_ieee_roman_sections(self):
        neurips = inspect_paper_pdf(resolve_seed_asset("exemplars/neurips/2025/depth1000.pdf"))
        headings = [item["heading"] for item in neurips["observed_headings"]]
        self.assertIn("1 Introduction", headings)
        self.assertFalse(any(item.startswith("64 network") for item in headings))
        icse = inspect_paper_pdf(resolve_seed_asset("exemplars/icse/2025/rl-test-oracle.pdf"))
        self.assertTrue(any(item["kind"] == "roman_section" and "NTRODUCTION" in item["heading"] for item in icse["observed_headings"]))


if __name__ == "__main__":
    unittest.main()
