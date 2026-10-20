"""Declared local citations must survive independent replay, including old receipts."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import research_artifact_core as core


class ReviewerBoundEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = {"query_runs": [{"status": "success"}, {"status": "error"}],
                       "a/b": {"~key": 40}, "flag": True}
        self.path = self.root / "source.json"
        self.path.write_text(json.dumps(self.source), encoding="utf8")
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.plan = core.plan_research_artifact(self.root, "reviewer_response", "reply-v1", ["source.json"],
                    {"venue": "Internal", "decision_type": "review", "response_mode": "issues", "length_limit": 500})

    def evidence(self, **updates):
        return {"source_file": "source.json", "sha256": self.sha, "json_pointer": "/query_runs",
                "value": copy.deepcopy(self.source["query_runs"]), "bound_in_response_plan": True, **updates}

    def artifact(self, evidence):
        return {"issues": [{"issue_id": "R1", "reviewer": "internal", "raw_anchor": "Check the run count",
                  "status": "answered", "response": "Recomputed from the local source.", "evidence": [evidence]}]}

    def submit(self, evidence):
        return core.submit_research_artifact(self.root, "reply-v1", self.plan["plan_hash"], self.artifact(evidence))

    def seed_old_receipt(self, evidence):
        artifact = self.artifact(evidence)
        state = core._load(self.root)
        state["artifacts"]["reply-v1"].update(status="PASS", submission={"artifact": artifact,
            "artifact_hash": core._digest(artifact), "checks": {"issues": 1, "delivery_ready": True},
            "submitted_at": "2026-10-19T00:00:00Z"})
        core._save(self.root, state)
        return artifact

    def test_summary_cannot_impersonate_pointer_raw_value(self):
        with self.assertRaisesRegex(core.ArtifactError, "value"):
            self.submit(self.evidence(value={"count": 2, "status_counts": {"success": 1, "error": 1}}))

    def test_exact_escaped_pointer_and_bool_distinction(self):
        good = self.submit(self.evidence(json_pointer="/a~1b/~0key", value=40))
        self.assertEqual(good["checks"]["local_evidence"]["exact_values_checked"], 1)
        with self.assertRaises(core.ArtifactError):
            # Different version avoids append-only rejection masking the evidence check.
            core.plan_research_artifact(self.root, "reviewer_response", "reply-v2", ["source.json"], self.plan["protocol"])
            state = core._load(self.root)
            plan = state["artifacts"]["reply-v2"]
            core.submit_research_artifact(self.root, "reply-v2", plan["plan_hash"],
                                          self.artifact(self.evidence(json_pointer="/flag", value=1)))

    def test_named_derived_count_is_recomputed(self):
        result = self.submit(self.evidence(derive={"operation": "list_status_counts", "status_field": "status"},
                    value={"count": 2, "status_counts": {"success": 1, "error": 1}}))
        self.assertEqual(result["checks"]["local_evidence"]["derived_values_checked"], 1)

    def test_incorrect_derived_count_is_rejected(self):
        with self.assertRaisesRegex(core.ArtifactError, "value"):
            self.submit(self.evidence(derive={"operation": "list_status_counts", "status_field": "status"},
                    value={"count": 3, "status_counts": {"success": 2, "error": 1}}))

    def test_arbitrary_transform_is_rejected(self):
        with self.assertRaisesRegex(core.ArtifactError, "derive"):
            self.submit(self.evidence(derive={"operation": "eval", "code": "len(value)"}, value=2))

    def test_claimed_source_hash_must_match(self):
        with self.assertRaisesRegex(core.ArtifactError, "sha256"):
            self.submit(self.evidence(sha256="0" * 64))

    def test_existing_unplanned_source_is_rejected(self):
        (self.root / "unplanned.json").write_bytes(self.path.read_bytes())
        with self.assertRaisesRegex(core.ArtifactError, "plan"):
            self.submit(self.evidence(source_file="unplanned.json"))

    def test_source_escape_is_rejected(self):
        with self.assertRaisesRegex(core.ArtifactError, "project_root"):
            self.submit(self.evidence(source_file="../outside.json"))

    def test_invalid_pointer_syntax_and_array_indices(self):
        for pointer in ("query_runs", "/bad~2escape", "/bad~", "/query_runs/-1", "/query_runs/00",
                        "/query_runs/2", "/query_runs/-", "/flag/child"):
            with self.subTest(pointer=pointer), self.assertRaises(core.ArtifactError):
                self.submit(self.evidence(json_pointer=pointer, value=1))

    def test_binding_flag_must_be_boolean(self):
        with self.assertRaisesRegex(core.ArtifactError, "boolean"):
            self.submit(self.evidence(bound_in_response_plan="true"))

    def test_legacy_and_explicitly_unbound_items_remain_unverified(self):
        artifact = self.artifact("External prose locator, reviewed manually")
        artifact["issues"][0]["evidence"].append({"execution_locator": "other/process.json", "bound_in_response_plan": False})
        result = core.submit_research_artifact(self.root, "reply-v1", self.plan["plan_hash"], artifact)
        self.assertEqual(result["checks"]["local_evidence"]["unverified_items"], 2)
        self.assertEqual(result["checks"]["local_evidence"]["bound_sources_checked"], 0)

    def test_identical_old_submission_is_revalidated(self):
        bad = self.evidence(value={"count": 2})
        artifact = self.seed_old_receipt(bad)
        with self.assertRaisesRegex(core.ArtifactError, "value"):
            core.submit_research_artifact(self.root, "reply-v1", self.plan["plan_hash"], artifact)

    def test_old_status_and_verify_invalidate_without_rewriting_history(self):
        self.seed_old_receipt(self.evidence(value={"count": 2}))
        original = core._path(self.root).read_bytes()
        for verify in (False, True):
            result = core.research_artifact_status(self.root, "reply-v1", verify=verify)
            self.assertEqual(result["status"], "INVALIDATED")
            self.assertIn("value", result["reason"])
        self.assertEqual(core._path(self.root).read_bytes(), original)

    def test_valid_idempotent_receipt_preserves_submission_time(self):
        first = self.submit(self.evidence())
        original = core._path(self.root).read_bytes()
        again = self.submit(self.evidence())
        self.assertEqual(again["submitted_at"], first["submitted_at"])
        self.assertEqual(again["checks"]["local_evidence"]["exact_values_checked"], 1)
        self.assertEqual(core._path(self.root).read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
