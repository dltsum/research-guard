from __future__ import annotations

import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import SourcePayloadError, score_collisions  # noqa: E402


class P0ReleaseRegressionTests(unittest.TestCase):
    def test_string_alias_is_scored_as_a_phrase(self):
        method = {
            "title": "Memory retrieval",
            "problem": "irrelevant memory",
            "mechanism": "confidence gate",
            "aliases": "causal routing",
        }
        [candidate] = score_collisions(
            method,
            [{"title": "Causal routing for memory retrieval", "abstract": "confidence gate"}],
            {"potential": 0.2, "high": 0.8},
        )
        self.assertIn("causal", candidate["shared_terms"])
        self.assertIn("routing", candidate["shared_terms"])

    def test_non_object_identifiers_fail_explicitly(self):
        with self.assertRaisesRegex(SourcePayloadError, "identifiers must be an object"):
            score_collisions(
                {"title": "Method", "problem": "Problem", "mechanism": "Mechanism"},
                [{"title": "Candidate", "identifiers": ["bad-shape"]}],
                {"potential": 0.2, "high": 0.8},
            )


if __name__ == "__main__":
    unittest.main()
