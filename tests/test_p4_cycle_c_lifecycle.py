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

from mcp_server import handle  # noqa: E402
from paper_audit_core import AuditError, get_paper_audit_status, plan_paper_audit, submit_paper_audit  # noqa: E402
from research_design_core import (  # noqa: E402
    DesignError,
    commit_candidate,
    get_research_design_status,
    plan_ideation,
    register_candidates,
)
from research_guard_core import (  # noqa: E402
    declare_method_change,
    get_gate_status,
    load_state,
    refresh_domain,
    register_manual_evidence,
    register_method,
    run_novelty_search,
)
import dependency_manager  # noqa: E402


class P4CycleCLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key = self.root / "signing.key"
        self.old_key = os.environ.get("RESEARCH_GUARD_KEY_FILE")
        self.old_dependency_home = os.environ.get("RESEARCH_GUARD_HOME")
        os.environ["RESEARCH_GUARD_KEY_FILE"] = str(self.key)
        os.environ["RESEARCH_GUARD_HOME"] = str(self.root / "dependency-home")
        dependency_manager.decide([], [])

    def tearDown(self):
        if self.old_key is None:
            os.environ.pop("RESEARCH_GUARD_KEY_FILE", None)
        else:
            os.environ["RESEARCH_GUARD_KEY_FILE"] = self.old_key
        if self.old_dependency_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = self.old_dependency_home
        self.temp.cleanup()

    def method(self, **extra):
        value = {
            "title": "Boundary Router",
            "problem": "distribution shift in neural systems",
            "mechanism": "uncertainty routed transformer",
        }
        value.update(extra)
        return value

    def pass_novelty(self):
        register_method(self.root, self.method())
        refresh_domain(
            self.root,
            primary_domain="computer_science",
            secondary_domains=[],
            selected_by="main_agent",
            selection_rationale="The main agent selected computer science for this neural-system routing method.",
        )
        required = load_state(self.root)["search_plan"]["required_sources"]
        return run_novelty_search(self.root, fixture_sources={source: [] for source in required})

    def hook(self, prompt: str):
        completed = subprocess.run(
            [sys.executable, str(PLUGIN / "hooks" / "guard_hook.py")],
            input=json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": str(self.root), "prompt": prompt}),
            text=True,
            capture_output=True,
            timeout=20,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout) if completed.stdout.strip() else {}

    def test_chinese_loss_function_change_invalidates_pass_immediately(self):
        self.pass_novelty()
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "PASS")
        output = self.hook("把损失函数改为焦点损失，并增加一个正则项")
        self.assertIn("method_change=true exactly when", output["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "PASS")
        declare_method_change(self.root, "Change the loss to focal loss and add a regularizer.")
        status = get_gate_status(self.root)
        self.assertEqual(status["gate"]["status"], "NOVELTY_CHECK_REQUIRED")
        self.assertIsNotNone(status["pending_method_change"])

    def test_non_change_comparison_does_not_invalidate(self):
        self.pass_novelty()
        output = self.hook("We compared two methods in the related work section.")
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "PASS")
        self.assertNotIn("adjustment detected", json.dumps(output))

    def test_manual_evidence_satisfies_only_its_exact_required_source(self):
        register_method(self.root, self.method(required_sources=["ccf", "cssci"]))
        refresh_domain(
            self.root,
            primary_domain="computer_science",
            secondary_domains=[],
            selected_by="main_agent",
            selection_rationale="The main agent selected computer science for the CCF and CSSCI source test.",
        )
        (self.root / "ccf.png").write_bytes(b"official directory capture")
        register_manual_evidence(
            self.root,
            source="ccf",
            purpose="index_membership",
            query="Example Conference",
            status="index_verified",
            evidence_path="ccf.png",
            evidence_url="https://www.ccf.org.cn/Academic_Evaluation/By_category/",
            identifier="Example Conference",
        )
        required = load_state(self.root)["search_plan"]["required_sources"]
        fixtures = {source: [] for source in required if source not in {"ccf", "cssci"}}
        result = run_novelty_search(self.root, fixture_sources=fixtures)
        self.assertEqual(result["status"], "ACTION_REQUIRED")
        progress = json.loads((self.root / result["checkpoint"]).read_text(encoding="utf-8"))
        ccf_units = [item for item in progress["units"] if item["source"] == "ccf"]
        cssci_units = [item for item in progress["units"] if item["source"] == "cssci"]
        self.assertTrue(ccf_units and all(item["status"] == "success" for item in ccf_units))
        self.assertTrue(cssci_units and all(item["status"] == "error" for item in cssci_units))

    def test_mixed_audit_cannot_drop_any_mandatory_verifier(self):
        plan = plan_paper_audit(
            self.root,
            "Review formulas, cited literature, code and experiment results",
            selected_roles=["formal_math_lean", "domain_literature", "code_experiment_integrity"],
            audit_features={"formula": True, "literature": True, "experiment": True},
            selected_by="main_agent",
            selection_rationale="The main agent selected all three mandatory roles for this mixed audit.",
        )
        self.assertEqual(set(plan["selected_roles"]), {
            "formal_math_lean", "domain_literature", "code_experiment_integrity",
        })
        reports = [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "1", "status": "verified"}]}
            for role in plan["selected_roles"]
        ]
        with self.assertRaisesRegex(AuditError, "Lean"):
            submit_paper_audit(
                self.root,
                role_reports=reports,
                online_checks=[{
                    "claim": "current benchmark", "url": "https://example.org/benchmark",
                    "accessed_at": "2026-08-12T00:00:00Z", "source_type": "official", "status": "verified",
                }],
                literature_items=[{"title": "Prior work", "citation_url": "https://doi.org/10.1000/prior"}],
                experiment_check={
                    "evidence_files": ["missing.json"], "data_provenance": "raw",
                    "configuration": "frozen", "seeds": [1], "numeric_recomputation": "done",
                    "dead_code": "checked", "evaluation_scope": "held-out",
                },
            )

    def test_paper_receipt_is_invalidated_when_bound_evidence_changes(self):
        (self.root / "evidence.json").write_text("{}", encoding="utf-8")
        plan = plan_paper_audit(
            self.root,
            "Audit final manuscript",
            evidence_files=["evidence.json"],
            selected_roles=["methodology_statistics", "adversarial_logic"],
            audit_features={},
            selected_by="main_agent",
            selection_rationale="The main agent selected methodology and adversarial roles for evidence lifecycle review.",
        )
        reports = [
            {"role": role, "findings": ["checked"], "numeric_checks": [{"claim": "none", "status": "verified"}]}
            for role in plan["selected_roles"]
        ]
        submit_paper_audit(
            self.root,
            role_reports=reports,
            online_checks=[{
                "claim": "current policy", "url": "https://example.org/policy",
                "accessed_at": "2026-08-12", "source_type": "official", "status": "verified",
            }],
        )
        (self.root / "evidence.json").write_text('{"changed": true}', encoding="utf-8")
        self.assertEqual(get_paper_audit_status(self.root)["status"], "AUDIT_REQUIRED")

    def _design_commit(self):
        plan = plan_ideation(self.root, request_text="probe a failure boundary", problem=self.method()["problem"])
        candidate = {
            "candidate_id": "c1", "title": self.method()["title"], "problem": self.method()["problem"],
            "mechanism": self.method()["mechanism"], "falsifier": "no effect under shift",
            "minimum_viable_experiment": "two-regime comparison", "differentiator": "explicit routing boundary",
            "feasibility": "public benchmark", "lens_id": plan["selected_lens_ids"][0], "prior_work": [],
        }
        register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[candidate])
        return commit_candidate(self.root, candidate_id="c1", selected_by="user", method=self.method())

    def test_design_commit_never_becomes_ready_without_current_novelty_receipt(self):
        committed = self._design_commit()
        self.assertEqual(committed["gate"]["status"], "DOMAIN_SELECTION_REQUIRED")
        status = get_research_design_status(self.root, verify=True)
        self.assertFalse(status["ready"])
        self.assertIn(status["status"], {"HYPOTHESIS_REQUIRED", "NOVELTY_CHECK_REQUIRED"})

    def test_declared_method_change_makes_design_stale(self):
        self._design_commit()
        declare_method_change(self.root, "change the routing mechanism")
        status = get_research_design_status(self.root)
        self.assertEqual(status["status"], "STALE_METHOD")
        self.assertFalse(status["ready"])

    def test_candidate_registration_rejects_automatic_winner_field(self):
        plan = plan_ideation(self.root, request_text="brainstorm", problem="model failure")
        candidate = {
            "candidate_id": "c1", "title": "Candidate", "problem": "model failure",
            "mechanism": "boundary routing", "falsifier": "no boundary effect",
            "minimum_viable_experiment": "two-regime comparison", "differentiator": "explicit boundary",
            "feasibility": "small benchmark", "lens_id": plan["selected_lens_ids"][0],
            "prior_work": [], "winner": True,
        }
        with self.assertRaisesRegex(DesignError, "automatic-ranking"):
            register_candidates(self.root, plan_hash=plan["plan_hash"], candidates=[candidate])

    def test_mcp_method_change_and_design_share_one_canonical_gate(self):
        response = handle({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "register_method", "arguments": {"project_root": str(self.root), "method": self.method()}},
        })
        self.assertFalse(response["result"]["isError"])
        design = handle({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "research_design", "arguments": {
                "action": "plan_ideation", "project_root": str(self.root),
                "request_text": "brainstorm", "problem": "distribution shift in neural systems",
            }},
        })
        self.assertFalse(design["result"]["isError"])
        self.assertEqual(get_gate_status(self.root)["gate"]["status"], "DOMAIN_SELECTION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
