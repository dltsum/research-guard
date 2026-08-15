from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from venue_evidence_core import (  # noqa: E402
    VenueEvidenceError,
    register_venue_profile,
    resolve_seed_asset,
    verify_venue_receipt,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class P9CycleCProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        evidence = self.root / "evidence"
        evidence.mkdir()
        self.template = evidence / "template.zip"
        self.paper = evidence / "paper.pdf"
        self.policy = evidence / "policy.html"
        shutil.copy2(resolve_seed_asset("templates/neurips/2025/neurips2025.zip"), self.template)
        shutil.copy2(resolve_seed_asset("exemplars/neurips/2025/depth1000.pdf"), self.paper)
        self.policy.write_text("<h1>Official policy</h1><p>Paper Checklist is required.</p>", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def profile(self):
        return {
            "venue": "testconf", "year": 2026, "track": "main", "stage": "submission",
            "policy_url": "https://testconf.example/official/policy",
            "template_url": "https://testconf.example/official/template.zip",
            "verified_at": "2026-08-13T00:00:00Z",
            "assets": [
                {"kind": "policy", "path": "evidence/policy.html", "sha256": sha(self.policy)},
                {"kind": "official_template", "path": "evidence/template.zip", "sha256": sha(self.template)},
            ],
            "required_sections": [{"name": "Paper Checklist", "source_path": "evidence/policy.html", "locator": "Paper Checklist"}],
            "exemplars": [{
                "title": "1000 Layer Networks for Self-Supervised RL",
                "award_url": "https://blog.neurips.cc/2025/11/26/announcing-the-neurips-2025-best-paper-awards/",
                "record_url": "https://proceedings.neurips.cc/paper_files/paper/2025/hash/e74ee34cc0f2d0780f34ee77d8fba25b-Abstract-Conference.html",
                "pdf_url": "https://proceedings.neurips.cc/paper_files/paper/2025/file/e74ee34cc0f2d0780f34ee77d8fba25b-Paper-Conference.pdf",
                "path": "evidence/paper.pdf", "sha256": sha(self.paper),
            }],
        }

    def live_receipts(self, profile):
        urls = [profile["policy_url"], profile["template_url"]]
        for exemplar in profile["exemplars"]:
            urls.extend(exemplar[field] for field in ("award_url", "record_url", "pdf_url"))
        return [{
            "url": url, "final_url": url, "http_status": 200, "content_type": "text/html",
            "route": "test", "verified_at": "2026-08-13T00:00:00+00:00",
        } for url in urls]

    def test_profile_and_receipt_are_asset_hash_bound(self):
        profile = self.profile()
        with patch("venue_evidence_core._online_receipts", return_value=self.live_receipts(profile)):
            registered = register_venue_profile(self.root, profile)
        self.assertEqual(registered["status"], "PASS")
        self.paper.write_bytes(self.paper.read_bytes() + b"tamper")
        self.assertEqual(verify_venue_receipt(self.root)["status"], "RESEARCH_REQUIRED")

    def test_invented_required_section_is_rejected(self):
        profile = self.profile()
        profile["required_sections"][0]["name"] = "Mandatory Quantum Appendix"
        profile["required_sections"][0]["locator"] = "Mandatory Quantum Appendix"
        with self.assertRaises(VenueEvidenceError):
            with patch("venue_evidence_core._online_receipts", return_value=self.live_receipts(profile)):
                register_venue_profile(self.root, profile)

    def test_project_import_requires_live_url_receipts(self):
        profile = self.profile()
        with patch("venue_evidence_core._online_receipts", side_effect=VenueEvidenceError("HTTP 404")):
            with self.assertRaisesRegex(VenueEvidenceError, "HTTP 404"):
                register_venue_profile(self.root, profile)


if __name__ == "__main__":
    unittest.main()
