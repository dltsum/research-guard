from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import (  # noqa: E402
    classify_domain,
    get_gate_status,
    load_state,
    refresh_domain,
    register_method,
    run_novelty_search,
    verify_receipt,
)


def method(**changes):
    value = {
        "title": "Adaptive retrieval for language model agents",
        "problem": "Large language model agents retrieve irrelevant memory during long tasks",
        "mechanism": "A confidence gated graph retrieval policy selects episodic memory",
        "contributions": ["confidence gate", "graph retrieval policy"],
        "evaluation": "Long horizon agent benchmarks",
    }
    value.update(changes)
    return value


class CoreRoundOneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.key = Path(self.temp.name) / "key.bin"
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.key)

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def fixtures(self, root=None):
        selected_root = root or self.root
        state = load_state(selected_root)
        if not state.get("search_plan"):
            refresh_domain(
                selected_root,
                primary_domain="computer_science",
                secondary_domains=[],
                selected_by="main_agent",
                selection_rationale="The main agent selected computer science for this language-agent retrieval method.",
            )
            state = load_state(selected_root)
        return {source: [] for source in state["search_plan"]["required_sources"]}

    def test_computer_science_routes_arxiv_ieee_and_ccf(self):
        profile = classify_domain(
            primary_domain="computer_science", secondary_domains=[], selected_by="main_agent",
            selection_rationale="The main agent selected computer science for transformer database query algorithms.",
        )
        self.assertEqual(profile["primary"], "computer_science")
        self.assertIn("arxiv", profile["required_sources"])
        self.assertIn("dblp", profile["required_sources"])
        self.assertIn("ieee", profile["supplemental_sources"])
        self.assertIn("ccf", profile["index_checks"])

    def test_cross_domain_keeps_medicine_and_computer_science(self):
        profile = classify_domain(
            primary_domain="medicine_life_science", secondary_domains=["computer_science"],
            selected_by="main_agent",
            selection_rationale="The main agent selected medicine and computing for clinical deep-learning diagnosis.",
        )
        self.assertEqual(profile["primary"], "medicine_life_science")
        self.assertIn("computer_science", profile["secondary"])
        self.assertIn("pubmed", profile["required_sources"])
        self.assertIn("arxiv", profile["required_sources"])
        self.assertIn("europe_pmc", profile["required_sources"])

    def test_social_science_routes_ssci_cssci_and_c_journal(self):
        profile = classify_domain(
            primary_domain="social_science", secondary_domains=[], selected_by="main_agent",
            selection_rationale="The main agent selected social science for education policy and governance communication.",
        )
        self.assertEqual(profile["primary"], "social_science")
        self.assertIn("openaire", profile["required_sources"])
        self.assertIn("wos_ssci", profile["supplemental_sources"])
        self.assertIn("cssci", profile["manual_sources"])
        self.assertIn("c_journal", profile["index_checks"])

    def test_registration_is_idempotent_but_changed_method_invalidates(self):
        first = register_method(self.root, method())
        second = register_method(self.root, method())
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(load_state(self.root)["active_method"]["version"], 1)
        fixtures = self.fixtures()
        run_novelty_search(self.root, fixture_sources=fixtures)
        changed = register_method(self.root, method(mechanism="A causal confidence gate selects graph memories"))
        self.assertTrue(changed["changed"])
        state = load_state(self.root)
        self.assertEqual(state["active_method"]["version"], 2)
        self.assertEqual(state["gate"]["status"], "DOMAIN_SELECTION_REQUIRED")
        self.assertIsNone(state["current_receipt"])

    def test_complete_clear_fixture_issues_valid_strict_receipt(self):
        register_method(self.root, method())
        result = run_novelty_search(self.root, fixture_sources=self.fixtures())
        self.assertEqual(result["report"]["gate_status"], "PASS")
        self.assertTrue(verify_receipt(self.root, strict=True)["valid"])

    def test_exact_collision_blocks_gate(self):
        register_method(self.root, method())
        fixtures = self.fixtures()
        fixtures[next(iter(fixtures))] = [{
            "title": method()["title"], "abstract": method()["mechanism"], "doi": "10.1000/collision",
        }]
        result = run_novelty_search(self.root, fixture_sources=fixtures)
        self.assertEqual(result["report"]["gate_status"], "COLLISION_REVIEW_REQUIRED")
        self.assertFalse(verify_receipt(self.root, strict=True)["valid"])

    def test_missing_required_source_fails_closed(self):
        register_method(self.root, method())
        fixtures = self.fixtures()
        fixtures.pop(next(iter(fixtures)))
        result = run_novelty_search(self.root, fixture_sources=fixtures)
        self.assertEqual(result["status"], "ACTION_REQUIRED")
        self.assertTrue(result["required_failed_units"])
        self.assertFalse(result["stop_allowed"])

    def test_method_change_makes_old_receipt_unavailable(self):
        register_method(self.root, method())
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        register_method(self.root, method(problem="Agents retrieve stale and irrelevant memories"))
        verified = verify_receipt(self.root, strict=True)
        self.assertFalse(verified["valid"])
        self.assertIn("No receipt", verified["errors"][0])

    def test_report_tampering_is_detected(self):
        register_method(self.root, method())
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        state = load_state(self.root)
        report_path = self.root / state["latest_report"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["works"].append({"title": "forged"})
        report_path.write_text(json.dumps(report), encoding="utf-8")
        verified = verify_receipt(self.root, strict=True)
        self.assertFalse(verified["valid"])
        self.assertIn("collision report hash mismatch", verified["errors"])

    def test_tracked_method_file_change_invalidates_receipt(self):
        tracked = self.root / "method.md"
        tracked.write_text("confidence gate", encoding="utf-8")
        register_method(self.root, method(method_files=["method.md"]))
        run_novelty_search(self.root, fixture_sources=self.fixtures())
        tracked.write_text("causal confidence gate", encoding="utf-8")
        status = get_gate_status(self.root)
        self.assertEqual(status["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        self.assertIsNone(status["current_receipt"])


if __name__ == "__main__":
    unittest.main()
