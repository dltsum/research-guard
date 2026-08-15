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

from paper_audit_core import AuditError, _formula_contract, _validate_online_checks  # noqa: E402
from research_design_core import DesignError, _normalize_power, plan_ideation, register_candidates  # noqa: E402
from research_guard_core import (  # noqa: E402
    SourcePayloadError,
    _normalize_work,
    get_gate_status,
    register_method,
    run_novelty_search,
)


class P4CycleDAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.root / "key")

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        self.temp.cleanup()

    def test_doi_url_query_and_fragment_are_not_part_of_identifier(self):
        work = _normalize_work(
            {"title": "Canonical DOI", "doi": "https://doi.org/10.1000/ABC?utm_source=x#fragment"},
            "crossref",
        )
        self.assertEqual(work["doi"], "10.1000/abc")
        self.assertEqual(work["citation_url"], "https://doi.org/10.1000/abc")

    def test_bibliographic_url_rejects_embedded_credentials(self):
        with self.assertRaisesRegex(SourcePayloadError, "credentials"):
            _normalize_work(
                {"title": "Secret URL", "url": "https://user:password@example.org/work"},
                "manual",
            )

    def test_naive_future_online_date_is_rejected(self):
        with self.assertRaisesRegex(AuditError, "future"):
            _validate_online_checks([{
                "claim": "policy", "url": "https://example.org/policy", "accessed_at": "2999-01-01",
                "source_type": "official", "status": "verified",
            }])

    def test_lean_string_mentions_do_not_count_as_parameter_use(self):
        text = """import Mathlib
set_option autoImplicit false
-- FORMULA_ID: f
theorem f (x : Nat) : True := by
  let _ := "x x"
  trivial
"""
        manifest = {
            "formulas": [{"id": "f", "source": "paper.tex:1", "parameters": ["x"]}],
            "parameters": [{"name": "x", "purpose": "input value", "used_by": ["f"]}],
        }
        with self.assertRaisesRegex(AuditError, "not actually used"):
            _formula_contract(text, manifest)

    def test_candidate_text_fields_reject_structured_objects(self):
        plan = plan_ideation(self.root, request_text="brainstorm", problem="model failure")
        candidate = {
            "candidate_id": "c1", "title": "Candidate", "problem": "model failure",
            "mechanism": {"type": "router"}, "falsifier": "no effect",
            "minimum_viable_experiment": "comparison", "differentiator": "boundary",
            "feasibility": "small run", "lens_id": plan["selected_lens_ids"][0], "prior_work": [],
        }
        with self.assertRaisesRegex(DesignError, "string"):
            register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[candidate])

    def test_power_rejects_nonpositive_plain_sample_size(self):
        with self.assertRaisesRegex(DesignError, "positive"):
            _normalize_power({
                "mode": "analytic", "basis": "two-sided test", "target_power_or_precision": "0.8",
                "sample_size": "0", "sensitivity_plan": "vary the effect size",
            })

    def test_english_switch_verb_triggers_collision_rerun(self):
        method = {"title": "Router", "problem": "neural distribution shift", "mechanism": "uncertainty routing"}
        registration = register_method(self.root, method)
        required = registration["state"]["search_plan"]["required_sources"]
        run_novelty_search(self.root, fixture_sources={source: [] for source in required})
        completed = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")],
            input=json.dumps({
                "hook_event_name": "UserPromptSubmit", "cwd": str(self.root),
                "prompt": "Switch the loss function to focal loss.",
            }),
            text=True, capture_output=True, timeout=20, env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "NOVELTY_CHECK_REQUIRED")


if __name__ == "__main__":
    unittest.main()
