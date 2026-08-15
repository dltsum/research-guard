from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from mcp_server import TOOLS  # noqa: E402
from research_guard_core import (  # noqa: E402
    GuardError,
    load_state,
    record_collision_resolution,
    register_method,
    run_novelty_search,
    verify_receipt,
)


def method(**changes):
    value = {
        "title": "Adaptive causal memory router",
        "problem": "Agents retrieve stale memories during long tasks",
        "mechanism": "A causal confidence router selects temporal graph memories",
        "contributions": ["temporal graph routing"],
    }
    value.update(changes)
    return value


class ResolutionGateRoundThreeTests(unittest.TestCase):
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

    def fixtures(self, title="Temporal graph memory routing for long horizon agents"):
        state = load_state(self.root)
        fixtures = {source: [] for source in state["search_plan"]["required_sources"]}
        fixtures[next(iter(fixtures))] = [{
            "title": title,
            "abstract": "A confidence router selects temporal graph memories and reduces stale retrieval.",
            "doi": "10.1000/prior",
        }]
        return fixtures

    def test_resolution_is_version_bound_and_requires_rerun(self):
        first = run_novelty_search(self.root, fixture_sources=self.fixtures())["report"]
        self.assertEqual(first["gate_status"], "COLLISION_REVIEW_REQUIRED")
        candidate = first["collision_candidates"][0]
        saved = record_collision_resolution(
            self.root,
            collision_id=candidate["collision_id"],
            decision="differentiated",
            rationale="The prior work uses static temporal edges, while this method estimates intervention-specific causal edges online.",
            differentiating_components=["online causal edge estimation", "intervention-specific routing"],
        )
        self.assertTrue(saved["registered"])
        self.assertFalse(verify_receipt(self.root, strict=True)["valid"])
        second = run_novelty_search(self.root, fixture_sources=self.fixtures())["report"]
        self.assertEqual(second["gate_status"], "PASS")
        self.assertEqual(second["collision_candidates"][0]["resolution"]["decision"], "differentiated")
        self.assertTrue(verify_receipt(self.root, strict=True)["valid"])

    def test_exact_title_collision_cannot_be_waived(self):
        report = run_novelty_search(self.root, fixture_sources=self.fixtures(title=method()["title"]))["report"]
        candidate = report["collision_candidates"][0]
        with self.assertRaisesRegex(GuardError, "exact identity"):
            record_collision_resolution(
                self.root, collision_id=candidate["collision_id"], decision="differentiated",
                rationale="This rationale is deliberately long but cannot waive an exact title identity collision.",
                differentiating_components=["claimed distinction"],
            )

    def test_tampered_resolution_is_rejected_and_blocks(self):
        report = run_novelty_search(self.root, fixture_sources=self.fixtures())["report"]
        candidate = report["collision_candidates"][0]
        saved = record_collision_resolution(
            self.root, collision_id=candidate["collision_id"], decision="differentiated",
            rationale="The comparison method does not estimate causal interventions and uses a fixed graph topology throughout evaluation.",
            differentiating_components=["causal interventions"],
        )
        path = self.root / saved["resolution_path"]
        body = json.loads(path.read_text(encoding="utf-8"))
        body["decision"] = "duplicate"
        path.write_text(json.dumps(body), encoding="utf-8")
        report = run_novelty_search(self.root, fixture_sources=self.fixtures())["report"]
        self.assertEqual(report["gate_status"], "COLLISION_REVIEW_REQUIRED")
        self.assertTrue(report["invalid_resolutions"])

    def test_method_change_drops_active_resolutions_but_preserves_history(self):
        report = run_novelty_search(self.root, fixture_sources=self.fixtures())["report"]
        candidate = report["collision_candidates"][0]
        saved = record_collision_resolution(
            self.root, collision_id=candidate["collision_id"], decision="differentiated",
            rationale="The prior system uses fixed graph retrieval whereas the registered method changes graph edges under interventions.",
            differentiating_components=["interventional graph updates"],
        )
        historical = self.root / saved["resolution_path"]
        register_method(self.root, method(mechanism="A causal intervention router rewrites temporal graph edges"))
        self.assertEqual(load_state(self.root)["collision_resolutions"], {})
        self.assertTrue(historical.is_file())

    def test_mcp_exposes_resolution_tool(self):
        self.assertIn("record_collision_resolution", {item["name"] for item in TOOLS})


if __name__ == "__main__":
    unittest.main()
