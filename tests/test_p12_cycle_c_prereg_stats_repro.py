from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from research_guard_core import register_method  # noqa: E402
from resource_guard import (  # noqa: E402
    ORCHESTRATOR_RESERVE_BYTES,
    OWNED_TASK_BUDGET_BYTES,
    WORKER_JOB_LIMIT_BYTES,
)
from research_integrity_core import (  # noqa: E402
    IntegrityError,
    _p_value,
    audit_statistics,
    record_preregistration_deviation,
    register_preregistration,
    register_reproducibility_plan,
    submit_reproducibility_result,
    execute_reproducibility,
    integrity_status,
)


class P12CycleCIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        register_method(self.root, {"title": "Audit", "problem": "validity", "mechanism": "frozen analysis"})

    def tearDown(self):
        self.temp.cleanup()

    def test_preregistration_is_user_owned_and_deviations_are_explicit(self):
        protocol = {
            "research_questions": ["RQ1"], "hypotheses": ["H1"], "outcomes": ["Y"],
            "exclusions": ["invalid"], "sample_size_basis": "power analysis", "analysis_plan": "linear model",
            "missing_data": "multiple imputation", "multiplicity": "Holm", "stopping_rule": "fixed N",
            "random_seed_policy": "record all seeds",
        }
        frozen = register_preregistration(self.root, "pre-v1", protocol, selected_by="user")
        self.assertEqual(frozen["status"], "FROZEN")
        changed = record_preregistration_deviation(self.root, "pre-v1", {
            "changed_field": "analysis_plan", "original": "linear model", "replacement": "robust linear model",
            "reason": "diagnostic failure", "timing": "after diagnostic before outcome inspection", "impact": "sensitivity analysis added",
        }, selected_by="user")
        self.assertEqual(changed["status"], "DEVIATIONS_DECLARED")
        repeated = record_preregistration_deviation(self.root, "pre-v1", {
            "changed_field": "analysis_plan", "original": "linear model", "replacement": "robust linear model",
            "reason": "diagnostic failure", "timing": "after diagnostic before outcome inspection", "impact": "sensitivity analysis added",
        }, selected_by="user")
        self.assertEqual(len(repeated["deviations"]), 1)
        with self.assertRaisesRegex(IntegrityError, "original does not match"):
            record_preregistration_deviation(self.root, "pre-v1", {
                "changed_field": "analysis_plan", "original": "invented baseline", "replacement": "Bayesian model",
                "reason": "diagnostic failure", "timing": "before outcome inspection", "impact": "model changed",
            }, selected_by="user")
        with self.assertRaisesRegex(IntegrityError, "not present"):
            record_preregistration_deviation(self.root, "pre-v1", {
                "changed_field": "undeclared_field", "original": "a", "replacement": "b",
                "reason": "new idea", "timing": "after freeze", "impact": "unknown",
            }, selected_by="user")
        sequential = record_preregistration_deviation(self.root, "pre-v1", {
            "changed_field": "analysis_plan", "original": "robust linear model", "replacement": "Bayesian robust model",
            "reason": "second diagnostic failure", "timing": "before outcome inspection", "impact": "sensitivity expanded",
        }, selected_by="user")
        self.assertEqual(len(sequential["deviations"]), 2)
        invalid_protocol = dict(protocol, hypotheses="H1")
        with self.assertRaisesRegex(IntegrityError, "hypotheses"):
            register_preregistration(self.root, "pre-invalid", invalid_protocol, selected_by="user")

    def test_statistical_recomputation_detects_consistency_and_error(self):
        passed = audit_statistics(self.root, "stats-v1", text="t(10)=2.228, p=.050")
        self.assertEqual(passed["status"], "PASS")
        failed = audit_statistics(self.root, "stats-v2", text="t(10)=2.228, p=.900")
        self.assertEqual(failed["status"], "ISSUES_FOUND")
        self.assertEqual(failed["inconsistency_count"], 1)
        robust = audit_statistics(self.root, "stats-v3", text="none", robustness_cases=[{
            "case_id": "spec-1", "baseline_estimate": 0.5, "alternative_estimate": 0.45,
            "tolerance_abs": 0.1, "baseline_interval": [0.2, 0.8], "alternative_interval": [0.1, 0.7],
        }])
        self.assertEqual(robust["status"], "PASS")
        flipped = audit_statistics(self.root, "stats-v4", text="none", robustness_cases=[{
            "case_id": "spec-2", "baseline_estimate": 0.5, "alternative_estimate": -0.4,
            "tolerance_abs": 1.0,
        }])
        self.assertEqual(flipped["status"], "ISSUES_FOUND")
        self.assertTrue(flipped["robustness_cases"][0]["sign_flip"])
        invalid = audit_statistics(self.root, "stats-v5", text="r(10)=2.0, p=.050")
        self.assertEqual(invalid["status"], "ISSUES_FOUND")
        self.assertEqual(invalid["not_recomputed_count"], 1)
        with self.assertRaises(IntegrityError):
            audit_statistics(self.root, "stats-v6", text="none", robustness_cases=[{
                "case_id": "nonfinite", "baseline_estimate": 1.0,
                "alternative_estimate": float("nan"), "tolerance_abs": 1.0,
            }])

    def test_statistical_distributions_match_frozen_reference_values(self):
        references = (
            (_p_value("z", 1.959963984540054, 1, None), 0.05),
            (_p_value("t", 2.2281388519649385, 10, None), 0.05),
            (_p_value("chi2", 3.841458820694124, 1, None), 0.05),
            (_p_value("F", 4.9646027437307145, 1, 10), 0.05),
            (_p_value("r", 0.575982986442264, 10, None), 0.05),
        )
        for observed, expected in references:
            self.assertAlmostEqual(observed, expected, places=7)

    def test_hash_bound_statistical_and_reproduction_outputs_invalidate_on_drift(self):
        (self.root / "statistics.txt").write_text("t(10)=2.228, p=.050", encoding="utf-8")
        self.assertEqual(audit_statistics(self.root, "stats-file", source_path="statistics.txt")["status"], "PASS")
        (self.root / "statistics.txt").write_text("t(10)=2.228, p=.900", encoding="utf-8")
        self.assertEqual(integrity_status(self.root, "statistical_audits", "stats-file")["status"], "INVALIDATED")

        (self.root / "input.txt").write_text("input", encoding="utf-8")
        (self.root / "expected.txt").write_text("stale", encoding="utf-8")
        (self.root / "stdout.txt").write_text("ok", encoding="utf-8")
        (self.root / "stderr.txt").write_text("", encoding="utf-8")
        plan = {
            "command": [sys.executable, "-c", "print('ok')"], "working_directory": ".",
            "inputs": ["input.txt"], "outputs": ["expected.txt"], "parameters": {"p": 1},
            "seeds": [7], "environment": {"python": sys.version.split()[0]},
            "expected_checks": [{"kind": "output_exists", "path": "expected.txt"}],
        }
        register_reproducibility_plan(self.root, "run-drift", plan, selected_by="user")
        submit_reproducibility_result(self.root, "run-drift", {
            "exit_code": 0, "started_at": "2026-08-13T00:00:00Z", "ended_at": "2026-08-13T00:00:01Z",
            "stdout_sha256": hashlib.sha256((self.root / "stdout.txt").read_bytes()).hexdigest(),
            "stderr_sha256": hashlib.sha256((self.root / "stderr.txt").read_bytes()).hexdigest(),
            "stdout_receipt": "stdout.txt", "stderr_receipt": "stderr.txt",
            "checks": [{"kind": "output_exists", "path": "expected.txt", "passed": True}],
        })
        self.assertEqual(integrity_status(self.root, "reproducibility", "run-drift")["status"], "REVIEW_REQUIRED")
        (self.root / "expected.txt").write_text("changed", encoding="utf-8")
        self.assertEqual(integrity_status(self.root, "reproducibility", "run-drift")["status"], "INVALIDATED")

    def test_only_managed_execution_can_produce_reproduction_pass(self):
        (self.root / "input.txt").write_text("input", encoding="utf-8")
        plan = {
            "command": [sys.executable, "-c", "print('ok')"], "working_directory": ".",
            "inputs": ["input.txt"], "outputs": ["expected.txt"], "parameters": {"p": 1},
            "seeds": [7], "environment": {"python": sys.version.split()[0]},
            "expected_checks": [{"kind": "output_exists", "path": "expected.txt"}],
        }
        register_reproducibility_plan(self.root, "run-managed", plan, selected_by="user")
        completed = type("Completed", (), {
            "stdout": "ok\n", "stderr": "", "returncode": 0,
            "resource_usage": {
                "memory_metric": "aggregate_working_set",
                "peak_worker_bytes": 16 * 1024 * 1024,
                "peak_orchestrator_bytes": 32 * 1024 * 1024,
                "peak_owned_bytes": 48 * 1024 * 1024,
                "worker_limit_bytes": WORKER_JOB_LIMIT_BYTES,
                "orchestrator_limit_bytes": ORCHESTRATOR_RESERVE_BYTES,
                "owned_limit_bytes": OWNED_TASK_BUDGET_BYTES,
            },
        })()
        def managed_run(*_args, **_kwargs):
            (self.root / "expected.txt").write_text("result", encoding="utf-8")
            return completed
        with patch("resource_guard.run_managed", side_effect=managed_run):
            result = execute_reproducibility(self.root, "run-managed")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["execution"]["execution_mode"], "managed")
        self.assertEqual(result["execution"]["resource_usage"]["memory_metric"], "aggregate_working_set")
        self.assertGreaterEqual(result["execution"]["duration_seconds"], 0)

        register_reproducibility_plan(self.root, "run-runtime-drift", {**plan, "outputs": ["new.txt"], "expected_checks": [{"kind": "output_exists", "path": "new.txt"}]}, selected_by="user")
        with patch("research_integrity_core._runtime_fingerprint", return_value={"system": "changed"}), \
             patch("resource_guard.run_managed", side_effect=AssertionError("runtime drift still launched command")):
            with self.assertRaisesRegex(IntegrityError, "runtime fingerprint changed"):
                execute_reproducibility(self.root, "run-runtime-drift")

        register_reproducibility_plan(self.root, "run-stale", plan, selected_by="user")
        with patch("resource_guard.run_managed", side_effect=AssertionError("stale output still launched command")):
            with self.assertRaisesRegex(IntegrityError, "fresh versioned output paths"):
                execute_reproducibility(self.root, "run-stale")

    def test_reproducibility_exit_zero_alone_cannot_pass(self):
        (self.root / "input.txt").write_text("input", encoding="utf-8")
        plan = {
            "command": [sys.executable, "-c", "print('ok')"], "working_directory": ".",
            "inputs": ["input.txt"], "outputs": ["expected.txt"], "parameters": {"p": 1},
            "seeds": [7], "environment": {"python": sys.version.split()[0]},
            "expected_checks": [{"kind": "output_exists", "path": "expected.txt"}],
        }
        register_reproducibility_plan(self.root, "run-v1", plan, selected_by="user")
        (self.root / "stdout.txt").write_text("", encoding="utf-8")
        (self.root / "stderr.txt").write_text("", encoding="utf-8")
        empty_hash = hashlib.sha256((self.root / "stdout.txt").read_bytes()).hexdigest()
        result = submit_reproducibility_result(self.root, "run-v1", {
            "exit_code": 0, "started_at": "2026-08-13T00:00:00Z", "ended_at": "2026-08-13T00:00:01Z",
            "stdout_sha256": empty_hash, "stderr_sha256": empty_hash,
            "stdout_receipt": "stdout.txt", "stderr_receipt": "stderr.txt",
            "checks": [{"kind": "output_exists", "path": "expected.txt", "passed": False}],
        })
        self.assertEqual(result["status"], "FAILED")
        with self.assertRaises(IntegrityError):
            register_reproducibility_plan(self.root, "run-v2", {**plan, "command": "python -c x; rm y"}, selected_by="user")
        with self.assertRaisesRegex(IntegrityError, "array of integers"):
            register_reproducibility_plan(self.root, "run-seed", {**plan, "seeds": ["7"]}, selected_by="user")

    def test_reproducibility_submit_cannot_replace_frozen_checks(self):
        (self.root / "input.txt").write_text("input", encoding="utf-8")
        (self.root / "expected.txt").write_text("wrong", encoding="utf-8")
        (self.root / "stdout.txt").write_text("ok", encoding="utf-8")
        (self.root / "stderr.txt").write_text("", encoding="utf-8")
        wanted = hashlib.sha256(b"correct").hexdigest()
        plan = {
            "command": [sys.executable, "-c", "print('ok')"], "working_directory": ".",
            "inputs": ["input.txt"], "outputs": ["expected.txt"], "parameters": {"p": 1},
            "seeds": [7], "environment": {"python": sys.version.split()[0]},
            "expected_checks": [{"kind": "output_sha256", "path": "expected.txt", "sha256": wanted}],
        }
        register_reproducibility_plan(self.root, "run-forged", plan, selected_by="user")
        with self.assertRaisesRegex(IntegrityError, "frozen expected_checks"):
            submit_reproducibility_result(self.root, "run-forged", {
                "exit_code": 0, "started_at": "2026-08-13T00:00:00Z", "ended_at": "2026-08-13T00:00:01Z",
                "stdout_sha256": hashlib.sha256((self.root / "stdout.txt").read_bytes()).hexdigest(),
                "stderr_sha256": hashlib.sha256((self.root / "stderr.txt").read_bytes()).hexdigest(),
                "stdout_receipt": "stdout.txt", "stderr_receipt": "stderr.txt",
                "checks": [{"kind": "output_exists", "path": "expected.txt", "passed": True}],
            })

    def test_reproducibility_plan_hash_tampering_blocks_managed_launch(self):
        (self.root / "input.txt").write_text("input", encoding="utf-8")
        plan = {
            "command": [sys.executable, "-c", "print('ok')"], "working_directory": ".",
            "inputs": ["input.txt"], "outputs": ["tamper-output.txt"], "parameters": {"p": 1},
            "seeds": [7], "environment": {"python": sys.version.split()[0]},
            "expected_checks": [{"kind": "output_exists", "path": "tamper-output.txt"}],
        }
        register_reproducibility_plan(self.root, "run-plan-tamper", plan, selected_by="user")
        state_path = self.root / ".research-guard" / "research-integrity.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["reproducibility"]["run-plan-tamper"]["parameters"] = {"p": 2}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with patch("resource_guard.run_managed", side_effect=AssertionError("tampered plan still launched")):
            with self.assertRaisesRegex(IntegrityError, "plan hash"):
                execute_reproducibility(self.root, "run-plan-tamper")


if __name__ == "__main__":
    unittest.main()
