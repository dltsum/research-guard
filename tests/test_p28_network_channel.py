from __future__ import annotations

import os
import ssl
import sys
import tempfile
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from evidence_kernel import EvidenceRecorder, evidence_scope  # noqa: E402
from research_guard_core import (  # noqa: E402
    SourceTransportError,
    _request,
    _request_routes,
)


class _Response(BytesIO):
    status = 200
    headers = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class NetworkChannelTests(unittest.TestCase):
    def test_foreign_route_prefers_proxy_then_explicit_direct_recovery(self):
        with patch.dict(
            os.environ,
            {
                "RESEARCH_GUARD_FOREIGN_PROXY": "http://127.0.0.1:7897",
                "RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK": "",
            },
        ):
            self.assertEqual(
                _request_routes("https://api.crossref.org/works"),
                (
                    ("foreign-proxy", "http://127.0.0.1:7897"),
                    ("foreign-direct-fallback", None),
                ),
            )
            self.assertEqual(
                _request_routes("https://www.ccf.org.cn/Academic_Evaluation/CN/"),
                (("domestic-direct", None),),
            )

    def test_proxy_transport_failure_recovers_direct_and_records_both_routes(self):
        proxy_opener = Mock()
        proxy_opener.open.side_effect = urllib.error.URLError(ssl.SSLEOFError("TLS EOF"))
        direct_opener = Mock()
        direct_opener.open.return_value = _Response(b"{}")
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {
                "RESEARCH_GUARD_FOREIGN_PROXY": "http://127.0.0.1:7897",
                "RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK": "",
            },
        ), patch(
            "research_guard_core.urllib.request.build_opener",
            side_effect=[proxy_opener, direct_opener],
        ) as builder, patch("research_guard_core.time.sleep"):
            recorder = EvidenceRecorder(Path(temporary), "route-fallback")
            with evidence_scope(
                recorder,
                source="crossref",
                query_id="q1",
                query="route recovery",
            ):
                self.assertEqual(_request("https://api.crossref.org/works", timeout=0.01), b"{}")
            self.assertEqual(builder.call_count, 2)
            self.assertEqual([item["route"] for item in recorder.attempts], [
                "foreign-proxy", "foreign-direct-fallback",
            ])
            self.assertEqual(recorder.attempts[0]["outcome"], "error")
            self.assertEqual(recorder.attempts[1]["outcome"], "success")
            self.assertIn("SSLEOFError", recorder.attempts[0]["message"])

    def test_strict_proxy_mode_disables_direct_recovery(self):
        with patch.dict(
            os.environ,
            {
                "RESEARCH_GUARD_FOREIGN_PROXY": "http://127.0.0.1:7897",
                "RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK": "1",
            },
        ):
            self.assertEqual(
                _request_routes("https://api.crossref.org/works"),
                (("foreign-proxy", "http://127.0.0.1:7897"),),
            )

    def test_empty_proxy_configuration_is_explicit_foreign_direct(self):
        with patch.dict(
            os.environ,
            {
                "RESEARCH_GUARD_FOREIGN_PROXY": "",
                "RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK": "",
            },
        ):
            self.assertEqual(
                _request_routes("https://api.crossref.org/works"),
                (("foreign-direct", None),),
            )

    def test_all_routes_fail_with_typed_diagnostic_without_secret_url(self):
        proxy_opener = Mock()
        proxy_opener.open.side_effect = urllib.error.URLError(ConnectionRefusedError())
        direct_opener = Mock()
        direct_opener.open.side_effect = TimeoutError()
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {
                "RESEARCH_GUARD_FOREIGN_PROXY": "http://127.0.0.1:7897",
                "RESEARCH_GUARD_DISABLE_FOREIGN_DIRECT_FALLBACK": "",
            },
        ), patch(
            "research_guard_core.urllib.request.build_opener",
            side_effect=[proxy_opener, direct_opener, direct_opener],
        ), patch("research_guard_core.time.sleep"):
            recorder = EvidenceRecorder(Path(temporary), "route-outage")
            with evidence_scope(
                recorder,
                source="crossref",
                query_id="q1",
                query="route recovery",
            ):
                with self.assertRaises(SourceTransportError) as captured:
                    _request(
                        "https://api.crossref.org/works?token=secret",
                        timeout=0.01,
                    )
            message = str(captured.exception)
            self.assertIn("foreign-proxy=ConnectionRefusedError", message)
            self.assertIn("foreign-direct-fallback=TimeoutError", message)
            self.assertNotIn("secret", message)
            self.assertEqual(
                [item["route"] for item in recorder.attempts],
                ["foreign-proxy", "foreign-direct-fallback", "foreign-direct-fallback"],
            )


if __name__ == "__main__":
    unittest.main()
