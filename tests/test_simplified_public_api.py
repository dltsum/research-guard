"""Exercise ordinary MCP requests without digest parameters or receipt setup."""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mcp_server import handle


def digest_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if re.search(r"(?:^|_)(?:hash|sha256|sha512|digest|signature|hmac)$", key):
                yield key
            yield from digest_fields(item)
    elif isinstance(value, list):
        for item in value:
            yield from digest_fields(item)


class SimplifiedPublicAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "notes.json").write_text('{"score": 2}', encoding="utf8")

    def call(self, **args):
        return handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "research_design", "arguments": {"action": "status", "project_root": str(self.root), **args},
        }})["result"]

    def test_discovery_and_experiment_record_need_no_hash_or_extra_protocol(self):
        listed = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]
        self.assertEqual(list(digest_fields(listed)), [])
        planned = self.call(artifact_action="plan", artifact_type="experiment_log", artifact_id="run1", source_files=["notes.json"])
        self.assertFalse(planned["isError"], planned)
        self.assertEqual(list(digest_fields(planned["structuredContent"])), [])
        log = {"materials": ["notes.json"], "parameters": {"source": "recorded input"},
               "measurements": [{"metric": "score", "value": 2, "unit": "count", "source": "notes.json"}],
               "observations": ["The source records two cases."], "anomalies": []}
        submitted = self.call(artifact_action="submit", artifact_id="run1", artifact=log)
        self.assertFalse(submitted["isError"], submitted)
        self.assertEqual(submitted["structuredContent"]["status"], "PASS")
        self.assertEqual(list(digest_fields(submitted["structuredContent"])), [])
        self.assertNotIn('"plan_hash"', submitted["content"][0]["text"])

    def test_edit_and_resubmit_uses_current_evidence_without_replanning(self):
        protocol = {"venue": "testconf", "decision_type": "revision", "response_mode": "point_by_point", "length_limit": "one page"}
        planned = self.call(artifact_action="plan", artifact_type="reviewer_response", artifact_id="reply", source_files=["notes.json"], protocol=protocol)
        self.assertFalse(planned["isError"], planned)
        artifact = {"issues": [{"issue_id": "r1", "reviewer": "reviewer1", "raw_anchor": "How many?", "status": "answered",
                                "response": "Two cases.", "evidence": [{"source_file": "notes.json", "bound_in_response_plan": True,
                                "json_pointer": "/score", "value": 2}]}]}
        self.assertFalse(self.call(artifact_action="submit", artifact_id="reply", artifact=artifact)["isError"])
        (self.root / "notes.json").write_text('{"score": 3}', encoding="utf8")
        bad = self.call(artifact_action="submit", artifact_id="reply", artifact=artifact)
        self.assertTrue(bad["isError"])
        self.assertIn("does not match", bad["structuredContent"]["message"])
        artifact["issues"][0]["response"] = "Three cases."
        artifact["issues"][0]["evidence"][0]["value"] = 3
        good = self.call(artifact_action="submit", artifact_id="reply", artifact=artifact)
        self.assertFalse(good["isError"], good)
        self.assertEqual(good["structuredContent"]["checks"]["local_evidence"]["exact_values_checked"], 1)


if __name__ == "__main__":
    unittest.main()
