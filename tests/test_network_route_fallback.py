from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import citation_guard_core  # noqa: E402
import discipline_profile_core  # noqa: E402
import domain_skill_core  # noqa: E402
import hydrate_release_payloads  # noqa: E402
import hydrate_research_assets  # noqa: E402
import openreview_calibration_core  # noqa: E402
import venue_evidence_core  # noqa: E402


class Response(BytesIO):
    status = 200

    def __init__(self, value: bytes):
        super().__init__(value)
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def geturl(self):
        return "https://example.org/final"


class NetworkRouteFallbackTests(unittest.TestCase):
    def test_citation_retries_explicit_proxy_with_direct_route(self):
        proxy = Mock()
        proxy.open.side_effect = URLError("proxy TLS failure")
        item = {
            "DOI": "10.1000/test-doi", "type": "journal-article",
            "author": [{"family": "Doe", "given": "Jane"}],
            "title": ["A verified research record"], "container-title": ["Journal of Tests"],
            "published": {"date-parts": [[2026]]},
        }
        direct = Mock()
        direct.open.return_value = Response(json.dumps({"message": item}).encode("utf-8"))
        routes = [("foreign-proxy", "http://proxy.invalid:9999", proxy), ("foreign-direct-fallback", None, direct)]
        with patch.object(citation_guard_core, "route_openers", return_value=routes):
            result = citation_guard_core.verify_and_format_citation("10.1000/test-doi", "apa")
        self.assertEqual(result["network_route"], "foreign-direct-fallback")
        self.assertEqual(proxy.open.call_count, 1)
        self.assertEqual(direct.open.call_count, 1)

    def test_openreview_records_route_used_after_transport_recovery(self):
        proxy = Mock()
        proxy.open.side_effect = URLError("proxy unavailable")
        direct = Mock()
        direct.open.return_value = Response(json.dumps({
            "notes": [{
                "id": "n1", "forum": "forum-1", "invitation": "Official_Review",
                "content": {"rating": {"value": 6}, "confidence": {"value": 4}},
            }], "count": 1,
        }).encode("utf-8"))
        routes = [("foreign-proxy", "http://proxy.invalid:9999", proxy), ("foreign-direct-fallback", None, direct)]
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            openreview_calibration_core, "route_openers", return_value=routes
        ):
            result = openreview_calibration_core.calibrate_openreview(
                temporary, "calibration-a", forum_ids=["forum-1"], timeout=1,
            )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["network_routes"], ["foreign-direct-fallback"])

    def test_domain_json_and_git_recovery_do_not_stop_at_proxy(self):
        proxy = Mock()
        proxy.open.side_effect = URLError("proxy unavailable")
        direct = Mock()
        direct.open.return_value = Response(b'{"items": []}')
        routes = [("foreign-proxy", "http://proxy.invalid:9999", proxy), ("foreign-direct-fallback", None, direct)]
        with patch.object(domain_skill_core, "route_openers", return_value=routes):
            self.assertEqual(domain_skill_core._json_url("https://api.github.com/search", timeout=1), {"items": []})

        class Completed:
            stdout = ""; stderr = "fatal: unable to access 'https://github.com/owner/repository.git': Could not resolve host"; returncode = 1

        class Success:
            stdout = "a" * 40 + "\tHEAD\n"; stderr = ""; returncode = 0

        with patch.object(domain_skill_core, "request_routes", return_value=[
            ("foreign-proxy", "http://proxy.invalid:9999"), ("foreign-direct-fallback", None),
        ]), patch.object(domain_skill_core, "_registered_git", return_value="git"), patch.object(
            domain_skill_core.subprocess, "run", side_effect=[Completed(), Success()]
        ) as run:
            self.assertEqual(domain_skill_core._remote_head("owner/repository"), "a" * 40)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[-1].args[0][2], "http.proxy=")

    def test_discipline_initializer_uses_shared_proxy_isolated_routes(self):
        proxy = Mock()
        proxy.open.side_effect = URLError("proxy unavailable")
        direct = Mock()
        direct.open.return_value = Response(b'{"results": []}')
        routes = [("foreign-proxy", "http://proxy.invalid:9999", proxy), ("foreign-direct-fallback", None, direct)]
        with patch.object(discipline_profile_core, "route_openers", return_value=routes):
            value, raw = discipline_profile_core._fetch_json("https://api.openalex.org/works", timeout=1)
        self.assertEqual(value, {"results": []})
        self.assertEqual(raw, b'{"results": []}')

    def test_payload_download_records_direct_fallback_and_cleans_partial_file(self):
        content = b"payload"
        proxy = Mock()
        proxy.open.side_effect = URLError("proxy unavailable")
        direct = Mock()
        direct.open.return_value = Response(content)
        routes = [("foreign-proxy", "http://proxy.invalid:9999", proxy), ("foreign-direct-fallback", None, direct)]
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            hydrate_release_payloads, "route_openers", return_value=routes
        ):
            target = Path(temporary) / "archive.zip"
            route = hydrate_release_payloads._download_archive(
                "https://github.com/dltsum/research-guard/releases/download/v0/archive.zip",
                target, len(content), hashlib.sha256(content).hexdigest(),
            )
            self.assertEqual(route, "foreign-direct-fallback")
            self.assertEqual(target.read_bytes(), content)

    def test_ccf_hydration_records_route_used_after_transport_recovery(self):
        proxy = Mock()
        proxy.open.side_effect = URLError("proxy unavailable")
        direct = Mock()
        direct.open.return_value = Response(b"x" * 20_001)
        routes = [("foreign-proxy", "http://proxy.invalid:9999", proxy), ("foreign-direct-fallback", None, direct)]
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            hydrate_research_assets, "ASSET_ROOT", Path(temporary) / "ccf"
        ), patch.object(hydrate_research_assets, "CATEGORY_SOURCES", {"cat": "https://example.org/cat"}), patch.object(
            hydrate_research_assets, "route_openers", return_value=routes
        ), patch.object(hydrate_research_assets, "write_catalog", return_value={"counts": {}, "catalog_sha256": "x"}):
            result = hydrate_research_assets.hydrate_ccf(timeout=1)
        self.assertEqual(result["sources"][0]["route"], "foreign-direct-fallback")

    def test_venue_receipts_record_direct_fallback_for_each_official_url(self):
        def route_factory(_url):
            proxy = Mock()
            proxy.open.side_effect = URLError("proxy unavailable")
            direct = Mock()
            direct.open.return_value = Response(b"ok")
            return [("foreign-proxy", "http://proxy.invalid:9999", proxy), ("foreign-direct-fallback", None, direct)]

        profile = {
            "policy_url": "https://example.org/policy", "template_url": "https://example.org/template",
            "exemplars": [{
                "award_url": "https://example.org/award", "record_url": "https://example.org/record",
                "pdf_url": "https://example.org/paper.pdf",
            }],
        }
        with patch.object(venue_evidence_core, "route_openers", side_effect=route_factory):
            receipts = venue_evidence_core._online_receipts(profile, timeout=1)
        self.assertEqual(len(receipts), 5)
        self.assertTrue(all(item["route"] == "foreign-direct-fallback" for item in receipts))

    def test_lean_powershell_network_steps_have_explicit_route_contract(self):
        script = (PLUGIN / "scripts" / "install_lean_mathlib.ps1").read_text(encoding="utf-8")
        for required in (
            "$networkRoutes", "Set-NetworkRoute", "Test-TransportFailure", "Invoke-NetworkStep",
            "foreign-direct-fallback", "network_routes_attempted", "network_routes_used", "network_route",
        ):
            self.assertIn(required, script)
        self.assertNotIn("127.0.0.1:7897", script)


if __name__ == "__main__":
    unittest.main()
