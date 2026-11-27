"""Validate zero-result and malformed responses from OpenAIRE Graph API v3."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import research_guard_core as core


class OpenAIREEmptyResponseTests(unittest.TestCase):
    searchers = (core.search_openaire, core.search_openaire_projects)

    def test_explicit_zero_with_empty_array_is_a_valid_empty_response(self):
        for search in self.searchers:
            payload = {"header": {"numFound": 0}, "results": []}
            with self.subTest(search=search.__name__), patch.object(core, "_json_request", return_value=payload):
                self.assertEqual(search("paired checkpoint audit", 12, 20), [])

    def test_null_missing_or_untyped_counts_stay_errors(self):
        invalid = (
            {"header": {"numFound": 0}},
            {"header": {"numFound": 0}, "results": None},
            {"header": {}, "results": []},
            {"header": {"numFound": False}, "results": []},
            {"header": {"numFound": -1}, "results": []},
            {"header": {"numFound": "0"}, "results": []},
        )
        for search in self.searchers:
            for payload in invalid:
                with self.subTest(search=search.__name__, payload=payload), patch.object(core, "_json_request", return_value=payload):
                    with self.assertRaises(core.SourcePayloadError):
                        search("paired checkpoint audit", 12, 20)

    def test_malformed_nonempty_and_contradictory_totals_stay_errors(self):
        for search in self.searchers:
            for total, results in ((0, "not an array"), (1, []), (0, [{}]), (1, [False])):
                payload = {"header": {"numFound": total}, "results": results}
                with self.subTest(search=search.__name__, payload=payload), patch.object(core, "_json_request", return_value=payload):
                    with self.assertRaises(core.SourcePayloadError):
                        search("paired checkpoint audit", 12, 20)

    def test_single_publication_record_remains_supported(self):
        record = {"mainTitle": "Checkpoint audit", "pids": [{"scheme": "doi", "value": "10.1000/example"}]}
        payload = {"header": {"numFound": 10}, "results": [record]}
        with patch.object(core, "_json_request", return_value=payload):
            works = core.search_openaire("checkpoint audit", 12, 20)
        self.assertEqual(len(works), 1)
        self.assertEqual(works[0]["title"], "Checkpoint audit")


if __name__ == "__main__":
    unittest.main()
