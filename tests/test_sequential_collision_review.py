"""Synthetic regression inputs for review bookkeeping, not live search proof."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import research_guard_core as core
from mcp_server import handle


class SequentialCollisionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(Path(self.temp.name) / "key")
        core.register_method(self.root, {
            "title": "Adaptive causal memory router", "problem": "Agents retrieve stale memories during long tasks",
            "mechanism": "A causal confidence router selects temporal graph memories",
            "contributions": ["temporal graph routing"],
        })
        core.refresh_domain(self.root, primary_domain="computer_science", secondary_domains=[],
                            selected_by="main_agent", selection_rationale="Explicit fixture selection for causal agent memory research.")
        fixtures = {source: [] for source in core.load_state(self.root)["search_plan"]["required_sources"]}
        fixtures[next(iter(fixtures))] = [{
            "title": f"Temporal graph memory routing for agents: prior {i}",
            "abstract": "A confidence router selects temporal graph memories and reduces stale retrieval.",
            "doi": f"10.1000/prior{i}",
        } for i in range(2)]
        self.report = core.run_novelty_search(self.root, fixture_sources=fixtures)["report"]
        self.report_path = core.load_state(self.root)["latest_report"]
        self.ids = [x["collision_id"] for x in self.report["collision_candidates"]]
        self.assertEqual(len(self.ids), 2)

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def review(self, index, **kwargs):
        return core.record_collision_resolution(self.root, collision_id=self.ids[index], decision="needs_review",
            rationale="The available record is metadata only; the full method must be read before deciding whether this is differentiated.", **kwargs)

    def test_two_candidates_can_be_reviewed_without_accepting_the_old_receipt(self):
        self.review(0)
        second = self.review(1)
        self.assertTrue(second["registered"])
        state = core.load_state(self.root)
        self.assertEqual(len(state["collision_resolutions"]), 2)
        self.assertIsNone(state["current_receipt"])
        self.assertIsNone(state["latest_report"])
        self.assertEqual(state["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        self.assertFalse(core.verify_receipt(self.root, strict=True)["valid"])

    def test_legacy_recovery_uses_explicit_signed_report_over_the_real_mcp_handler(self):
        self.review(0)
        state = core.load_state(self.root)
        state.pop("collision_review_report", None)  # The state written by the old implementation.
        core.save_state(self.root, state)
        response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "record_collision_resolution", "arguments": {
                "project_root": str(self.root), "collision_id": self.ids[1], "decision": "needs_review",
                "rationale": "Only metadata is available in this test; further scientific review is necessary before differentiating.",
                "report_path": self.report_path,
            }}})
        self.assertFalse(response["result"]["isError"], response)
        self.assertTrue(response["result"]["structuredContent"]["rerun_required"])

    def test_tampered_signed_receipt_cannot_be_used_for_review(self):
        self.review(0)
        receipt_path = self.root / ".research-guard" / "receipts" / Path(self.report_path).name
        receipt = json.loads(receipt_path.read_text(encoding="utf8"))
        receipt["signature"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt), encoding="utf8")
        with self.assertRaisesRegex(core.GuardError, "signature"):
            self.review(1)

    def test_rehashing_an_edited_report_does_not_forge_its_signed_binding(self):
        self.review(0)
        report_file = self.root / self.report_path
        report = json.loads(report_file.read_text(encoding="utf8"))
        report["collision_candidates"][1]["title"] = "Edited candidate"
        report["report_hash"] = core.digest({k: v for k, v in report.items() if k != "report_hash"})
        report_file.write_text(json.dumps(report), encoding="utf8")
        with self.assertRaisesRegex(core.GuardError, "binding mismatch"):
            self.review(1)

    def test_old_query_plan_cannot_be_recovered_as_a_current_review(self):
        self.review(0)
        state = core.load_state(self.root)
        state["search_plan"]["plan_hash"] = "changed-plan"
        core.save_state(self.root, state)
        with self.assertRaisesRegex(core.GuardError, "query plan"):
            self.review(1, report_path=self.report_path)


if __name__ == "__main__":
    unittest.main()
