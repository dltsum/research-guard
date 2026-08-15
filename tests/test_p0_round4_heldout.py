from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import research_guard_core as core  # noqa: E402
from evidence_kernel import EvidenceRecorder, evidence_scope  # noqa: E402


class _Headers:
    def get_content_type(self):
        return "application/json"


class HeldOutRoundFourTests(unittest.TestCase):
    def test_skill_prompt_is_compact_and_defers_detail_to_tools(self):
        text = (PLUGIN / "skills" / "research-novelty-guard" / "SKILL.md").read_text(encoding="utf-8")
        body = text.split("---", 2)[-1]
        self.assertLessEqual(len(body.split()), 800)
        for required in ("register_method", "run_novelty_search", "record_collision_resolution", "verify"):
            self.assertIn(required, body)

    def test_p0_source_capabilities_are_executable(self):
        self.assertTrue({"pmc", "biorxiv", "medrxiv"} <= set(core.SEARCHERS))
        self.assertTrue(callable(core.fetch_opencitations_neighbors))
        self.assertTrue(callable(core.fetch_unpaywall_record))

    def test_rate_limit_attempt_is_typed_and_secret_url_is_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recorder = EvidenceRecorder(root, "heldout-run")
            error = urllib.error.HTTPError(
                "https://example.org/search?apikey=secret&query=graph", 429, "limited", {}, None
            )
            opener = mock.Mock()
            opener.open.side_effect = error
            with evidence_scope(recorder, source="fixture", query_id="q1", query="graph"):
                with mock.patch("urllib.request.build_opener", return_value=opener):
                    with self.assertRaises(core.SourceRateLimitError):
                        core._request("https://example.org/search?apikey=secret&query=graph", timeout=0.01)
            self.assertEqual(len(recorder.attempts), 2)
            self.assertTrue(all(item["error_type"] == "SourceRateLimitError" for item in recorder.attempts))
            encoded = json.dumps(recorder.attempts)
            self.assertNotIn("secret", encoded)
            self.assertIn("%5BREDACTED%5D", encoded)

    def test_search_adapters_reject_error_shaped_http_200_payloads(self):
        with mock.patch("research_guard_core._json_request", return_value={"error": "quota exhausted"}):
            with self.assertRaises(core.SourcePayloadError):
                core.search_semantic_scholar("graph", 2, 2)

    def test_open_access_enrichment_is_explicit_without_credentials(self):
        old = os.environ.pop("UNPAYWALL_EMAIL", None)
        try:
            result = core.fetch_unpaywall_record("10.1000/example", timeout=1)
            self.assertFalse(result["available"])
            self.assertEqual(result["status"], "credential_required")
        finally:
            if old is not None:
                os.environ["UNPAYWALL_EMAIL"] = old


if __name__ == "__main__":
    unittest.main()
