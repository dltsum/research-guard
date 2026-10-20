"""Regression for the live 2026-10-20 OpenAIRE zero-result response.

These are parser boundary tests, not evidence of a live search succeeding.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import research_guard_core as core


class OpenAIREEmptyResponseTests(unittest.TestCase):
    searchers = (core.search_openaire, core.search_openaire_projects)

    def test_explicit_zero_with_null_results_is_a_valid_empty_response(self):
        # Official projects API returned this shape for all six live queries.
        for search in self.searchers:
            for total in ({"$": "0"}, "0", 0):
                payload = {"response": {"header": {"total": total}, "results": None}}
                with self.subTest(search=search.__name__, total=total), patch.object(core, "_json_request", return_value=payload):
                    self.assertEqual(search("paired checkpoint audit", 12, 20), [])

    def test_null_or_missing_result_without_explicit_zero_stays_an_error(self):
        for search in self.searchers:
            for header in ({}, {"total": {"$": "1"}}, {"total": False}, {"total": "unknown"}):
                for results in (None, {}, {"result": None}):
                    payload = {"response": {"header": header, "results": results}}
                    with self.subTest(search=search.__name__, header=header, results=results), patch.object(core, "_json_request", return_value=payload):
                        with self.assertRaises(core.SourcePayloadError):
                            search("paired checkpoint audit", 12, 20)

    def test_malformed_nonempty_and_contradictory_totals_stay_errors(self):
        for search in self.searchers:
            for total, results in ((0, "not a container"), (1, {"result": []}), (1, {"result": [False]})):
                payload = {"response": {"header": {"total": total}, "results": results}}
                with self.subTest(search=search.__name__, payload=payload), patch.object(core, "_json_request", return_value=payload):
                    with self.assertRaises(core.SourcePayloadError):
                        search("paired checkpoint audit", 12, 20)

    def test_single_publication_record_remains_supported(self):
        record = {"metadata": {"oaf:entity": {"oaf:result": {
            "title": {"$": "Checkpoint audit"}, "pid": {"@classid": "doi", "$": "10.1000/example"},
        }}}}
        payload = {"response": {"header": {"total": {"$": "1"}}, "results": {"result": record}}}
        with patch.object(core, "_json_request", return_value=payload):
            works = core.search_openaire("checkpoint audit", 12, 20)
        self.assertEqual(len(works), 1)
        self.assertEqual(works[0]["title"], "Checkpoint audit")


if __name__ == "__main__":
    unittest.main()
