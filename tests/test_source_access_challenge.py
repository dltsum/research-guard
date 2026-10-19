"""Semantic JSON-client boundaries; explicit transport payloads, not live API success."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import research_guard_core as core

URL = "https://dblp.org/search/publ/api?q=transformer&h=2&format=json"
CHALLENGE = b'<!doctype html><html><head><title>Making sure you&#39;re not a bot!</title></head><body><script id="anubis_challenge" type="application/json">{}</script></body></html>'


class SourceAccessChallengeTests(unittest.TestCase):
    def read(self, body):
        with patch.object(core, "_request", return_value=body) as transport:
            try:
                return core._json_request(URL)
            finally:
                transport.assert_called_once()

    def test_observed_html_challenge_is_typed_blocking_access_error(self):
        with self.assertRaisesRegex(core.SourceAccessChallengeError, "API search remains blocked") as context:
            self.read(CHALLENGE)
        self.assertIsInstance(context.exception, core.SourceAccessError)

    def test_html_document_variants_and_apostrophe_entities_are_recognized(self):
        for body in [CHALLENGE.replace(b"&#39;", b"&#x27;"),
                     CHALLENGE.replace(b"<!doctype html>", b"\xef\xbb\xbf \n<HTML>", 1),
                     CHALLENGE.replace(b"anubis_challenge", b"anubis_version")]:
            with self.subTest(body=body[:50]), self.assertRaises(core.SourceAccessChallengeError):
                self.read(body)

    def test_valid_json_with_anubis_and_full_html_strings_is_valid_json(self):
        payload = {"note": "Anubis", "page": CHALLENGE.decode(), "result": {"hits": {"@total": "0"}}}
        self.assertEqual(self.read(json.dumps(payload).encode()), payload)

    def test_ordinary_html_stays_payload_error(self):
        with self.assertRaises(core.SourcePayloadError):
            self.read(b"<!doctype html><html><title>Service unavailable</title><p>Try later</p></html>")

    def test_matching_title_without_specific_marker_is_not_a_challenge(self):
        for body in [CHALLENGE.replace(b'anubis_challenge', b'other_script'),
                     b"<!doctype html><html><title>Making sure you're not a bot!</title><p>Anubis manual</p></html>"]:
            with self.subTest(body=body), self.assertRaises(core.SourcePayloadError):
                self.read(body)

    def test_marker_without_matching_title_is_not_a_challenge(self):
        for body in [CHALLENGE.replace(b"Making sure you&#39;re not a bot!", b"Anubis documentation"),
                     CHALLENGE.replace(b"<title>Making sure you&#39;re not a bot!</title>", b"")]:
            with self.subTest(body=body), self.assertRaises(core.SourcePayloadError):
                self.read(body)

    def test_fragment_is_not_an_html_document_challenge(self):
        body = b"<title>Making sure you're not a bot!</title><script id='anubis_challenge'>{}</script>"
        with self.assertRaises(core.SourcePayloadError):
            self.read(body)

    def test_ordinary_malformed_json_stays_payload_error(self):
        with self.assertRaises(core.SourcePayloadError):
            self.read(b'{"Anubis": "Making sure you are not a bot!",')

    def test_invalid_utf8_stays_payload_error(self):
        with self.assertRaises(core.SourcePayloadError):
            self.read(b"\xffinvalid UTF8")

    def test_transport_error_still_propagates_unchanged(self):
        failure = core.SourceTransportError("zenodo.org transport failure via foreign-direct: gaierror")
        with patch.object(core, "_request", side_effect=failure):
            with self.assertRaises(core.SourceTransportError) as context:
                core._json_request("https://zenodo.org/api/records?q=transformer&size=1")
        self.assertIs(context.exception, failure)


if __name__ == "__main__":
    unittest.main()
