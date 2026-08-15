from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from venue_evidence_core import get_venue_status, resolve_venue_profile  # noqa: E402


class P9CycleEHeldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_single_exemplar_is_never_called_a_venue_norm(self):
        result = resolve_venue_profile(self.root, "ICLR", 2026, "main", "submission")
        self.assertEqual(result["status"], "PASS")
        narrative = result["profile"]["narrative_evidence"]
        if narrative["exemplar_count"] < 2:
            self.assertEqual(narrative["scope"], "sample_specific")
            self.assertFalse(narrative["venue_norm_authorized"])

    def test_state_tampering_invalidates_venue_receipt(self):
        resolve_venue_profile(self.root, "ACL", 2025, "main", "submission")
        path = self.root / ".research-guard" / "venue-state.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["profile"]["stage"] = "camera_ready"
        path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(get_venue_status(self.root)["status"], "RESEARCH_REQUIRED")

    def test_hook_requires_main_agent_selection_without_keyword_venue_routing(self):
        env = os.environ.copy()
        env["RESEARCH_GUARD_PROJECT_ROOT"] = str(self.root)
        payload = json.dumps({
            "hook_event_name": "UserPromptSubmit", "cwd": str(self.root),
            "prompt": "Help write my CVPR paper outline and narrative",
        })
        run = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")], input=payload,
            text=True, capture_output=True, env=env, check=True,
        )
        self.assertIn("list_research_modules", run.stdout)
        self.assertIn("automatic module routers", run.stdout)
        self.assertNotIn("ONLINE_ACQUISITION_REQUIRED", run.stdout)


if __name__ == "__main__":
    unittest.main()
