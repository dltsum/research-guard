from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import (  # noqa: E402
    SourcePayloadError,
    load_state,
    register_method,
    run_novelty_search,
    search_crossref,
    verify_receipt,
)


def method(**changes):
    value = {
        "title": "Causal graph memory for long horizon agents",
        "problem": "Language model agents retrieve stale episodic memory during long tasks",
        "mechanism": "A causal confidence gate selects graph connected episodic memories",
        "contributions": ["causal retrieval gate", "versioned episodic graph"],
        "datasets": ["long horizon agent benchmark"],
        "evaluation": ["retrieval precision", "task completion"],
    }
    value.update(changes)
    return value


class EvidenceKernelRoundOneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(Path(self.temp.name) / "key.bin")
        register_method(self.root, method())

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def fixtures(self):
        return {source: [] for source in load_state(self.root)["search_plan"]["required_sources"]}

    def test_plan_contains_unique_structured_component_queries(self):
        plan = load_state(self.root)["search_plan"]
        specs = plan["query_specs"]
        self.assertGreaterEqual(len(specs), 6)
        self.assertEqual(len(specs), len({item["query_id"] for item in specs}))
        kinds = {item["kind"] for item in specs}
        self.assertTrue({"exact_title", "problem_mechanism", "mechanism_dataset", "mechanism_evaluation", "survey"} <= kinds)
        self.assertEqual(plan["queries"], [item["text"] for item in specs])

    def test_every_query_is_executed_and_hash_bound_in_evidence_manifest(self):
        result = run_novelty_search(self.root, fixture_sources=self.fixtures())
        report = result["report"]
        plan = load_state(self.root)["search_plan"]
        expected = len(plan["required_sources"]) * len(plan["query_specs"])
        required_runs = [
            item for item in report["query_runs"]
            if item["tier"] in {"required", "extended_required"}
        ]
        self.assertEqual(len(required_runs), expected)
        self.assertTrue(all(item["status"] == "success" for item in required_runs))
        manifest_path = self.root / report["evidence_manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_hash"], report["evidence_manifest_hash"])
        self.assertEqual(manifest["method_hash"], report["method_hash"])
        self.assertEqual(len(manifest["attempts"]), len(report["query_runs"]))
        self.assertTrue(verify_receipt(self.root, strict=True)["valid"])

    def test_raw_evidence_tampering_invalidates_receipt(self):
        report = run_novelty_search(self.root, fixture_sources=self.fixtures())["report"]
        manifest = json.loads((self.root / report["evidence_manifest"]).read_text(encoding="utf-8"))
        attempt = next(item for item in manifest["attempts"] if item.get("raw_path"))
        (self.root / attempt["raw_path"]).write_bytes(b"tampered")
        verified = verify_receipt(self.root, strict=True)
        self.assertFalse(verified["valid"])
        self.assertTrue(any("evidence" in item.lower() for item in verified["errors"]))

    def test_typed_required_query_failure_blocks_coverage(self):
        fixtures = self.fixtures()
        source = next(iter(fixtures))
        fixtures[source] = {"error_type": "SourceRateLimitError", "message": "shared pool throttled", "status_code": 429}
        report = run_novelty_search(self.root, fixture_sources=fixtures)["report"]
        self.assertEqual(report["gate_status"], "COVERAGE_INCOMPLETE")
        self.assertIn(source, report["missing_sources"])
        failures = [item for item in report["query_runs"] if item["source"] == source]
        self.assertEqual(len(failures), len(report["query_specs"]))
        self.assertTrue(all(item["error_type"] == "SourceRateLimitError" for item in failures))

    def test_adapter_rejects_semantically_malformed_success_payload(self):
        with mock.patch("research_guard_core._json_request", return_value={"message": {}}):
            with self.assertRaises(SourcePayloadError):
                search_crossref("graph memory", 2, 2)


if __name__ == "__main__":
    unittest.main()
