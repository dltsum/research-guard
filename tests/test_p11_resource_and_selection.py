from __future__ import annotations

import json
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import dependency_manager  # noqa: E402
import domain_skill_core  # noqa: E402
import mcp_server  # noqa: E402
import resource_guard  # noqa: E402
import paper_audit_core  # noqa: E402
import run_incremental_tests  # noqa: E402


class P11FirstLoadTests(unittest.TestCase):
    def test_traditional_skill_structure_exists(self):
        for relative in (
            "SKILL.md", "agents/openai.yaml", "scripts/install.ps1", "REQUIREMENTS.md",
            "references/dependencies.md", "assets/dependency-catalog.json",
            "assets/payload-manifest.json", "assets/runtime-distributions.json",
        ):
            self.assertTrue((PLUGIN / relative).is_file(), relative)

    def test_bootstrap_skill_does_not_retry_a_missing_relative_installer(self):
        skill = (PLUGIN / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("RELEASE_MANIFEST.json", skill)
        self.assertIn("scripts/install.ps1", skill)
        self.assertIn("already-registered bootstrap", skill)
        self.assertIn("Do not retry a relative installer", skill)

    def test_offline_runtime_inventory_is_complete(self):
        value = json.loads((PLUGIN / "assets" / "runtime-distributions.json").read_text(encoding="utf-8"))
        distributions = value["distributions"]
        self.assertEqual(len(distributions), 27)
        identities = {(item["name"].casefold(), item["version"]) for item in distributions}
        for expected in (
            ("matplotlib", "3.10.8"), ("numpy", "2.4.4"),
            ("pillow", "11.3.0"), ("pypdf", "6.15.0"),
            ("networkx", "3.6.1"), ("optuna", "4.9.0"),
            ("pint", "0.25.3"), ("sympy", "1.14.0"), ("z3-solver", "5.0.0.0"),
        ):
            self.assertIn(expected, identities)

    def test_bundled_elan_has_exact_upstream_license_texts(self):
        expected = {
            "assets/licenses/elan-v4.2.3-LICENSE-MIT":
                "920d8685aa3276617133e07d67502148a619eb274b3bba58c9b45d718b687831",
            "assets/licenses/elan-v4.2.3-LICENSE-APACHE":
                "8173d5c29b4f956d532781d2b86e4e30f83e6b7878dce18c919451d6ba707c90",
        }
        for relative, digest in expected.items():
            path = PLUGIN / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_optional_installer_contracts_are_pinned(self):
        manager = (PLUGIN / "scripts" / "dependency_manager.py").read_text(encoding="utf-8")
        lean_installer = (PLUGIN / "scripts" / "install_lean_mathlib.ps1").read_text(encoding="utf-8")
        installer = (PLUGIN / "scripts" / "install.ps1").read_text(encoding="utf-8")
        self.assertIn('str(local_installer), "--unattended", "--portable", "--no-registry"', manager)
        self.assertNotIn('f"--portable={destination}"', manager)
        self.assertIn('scope = "leanprover-community"', lean_installer)
        self.assertIn('rev = "v4.33.0"', lean_installer)
        self.assertIn("db584cd6d46c92f209a44c0f1c829460d327499d", lean_installer)
        self.assertIn("from resource_guard import run_managed_light", installer)
        self.assertIn("bounded_core_import_smoke.py", installer)
        self.assertIn("assets\\resource-policy.json", installer)
        self.assertIn("worker_job_limit_bytes", installer)
        self.assertIn("Invoke-OrchestratorCheckpoint", installer)
        self.assertNotIn("Assert-MemoryHeadroom 6", installer)
        self.assertIn("Lean worker plus orchestrator exceeds", installer)
        self.assertIn("aggregate working-set sampling", installer)

    def test_mcp_launcher_avoids_cmd_nested_quote_parsing(self):
        config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["research-guard"]
        self.assertEqual(server["command"], "powershell.exe")
        self.assertEqual(server["args"][-1], "${PLUGIN_ROOT}\\scripts\\mcp.ps1")
        self.assertTrue((PLUGIN / "scripts" / "mcp.ps1").is_file())

    def test_inventory_is_read_only_and_keeps_core_work_available(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": temporary}, clear=False
        ):
            with patch.object(dependency_manager, "_run_version", side_effect=AssertionError("compiler executed")):
                value = dependency_manager.inventory()
            self.assertTrue(value["first_load_pending"])
            self.assertEqual(value["status"], "CORE_READY_OPTIONALS_ON_DEMAND")
            self.assertFalse(value["core_work_blocked"])
            self.assertEqual(value["optional_selection_mode"], "on-demand")
            self.assertEqual(len(value["components"]), 7)
            self.assertEqual(value["required_component_ids"], ["core-runtime"])
            self.assertEqual(len(value["actionable_component_ids"]), 3)
            self.assertEqual(len(value["informational_component_ids"]), 3)
            self.assertFalse((Path(temporary) / "dependencies" / "selection.json").exists())

    def test_declined_component_exposes_stable_degradation(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": temporary}, clear=False
        ):
            dependency_manager.decide([], [])
            with self.assertRaises(dependency_manager.DependencyError) as caught:
                dependency_manager.require("lean-mathlib")
            self.assertEqual(caught.exception.code, "DEPENDENCY_DECLINED")
            guidance = dependency_manager.component_need("lean-mathlib")
            self.assertEqual(guidance["status"], "DEGRADED")
            self.assertTrue(guidance["may_continue_degraded"])
            self.assertIn("NOT_RUN_BY_USER", guidance["degradation"])

    def test_mcp_first_read_only_call_exposes_inventory_and_core_work_continues(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": temporary}, clear=False
        ):
            result = mcp_server.handle({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "list_sources", "arguments": {}},
            })
            self.assertIsNotNone(result)
            content = result["result"]["structuredContent"]
            self.assertFalse(content["selection_required"])
            self.assertTrue(content["core_work_allowed"])
            self.assertTrue(content["dependency_inventory"]["first_load_pending"])
            self.assertTrue(content["sources"])
            self.assertFalse(result["result"]["isError"])
            routed = mcp_server.handle({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "list_research_modules", "arguments": {}},
            })
            self.assertFalse(routed["result"]["isError"])
            self.assertEqual(routed["result"]["structuredContent"]["status"], "MAIN_AGENT_SELECTION_REQUIRED")
            self.assertEqual(routed["result"]["structuredContent"]["selected_modules"], [])

    def test_need_and_not_now_are_machine_actionable_without_installing(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": temporary}, clear=False
        ):
            need = dependency_manager.component_need("tex-basic")
            self.assertEqual(need["status"], "USER_DECISION_REQUIRED")
            self.assertTrue(need["prompt_user"])
            self.assertEqual(need["choices"][-1]["id"], "not_now")
            self.assertFalse((Path(temporary) / "dependencies" / "installed" / "tex-basic").exists())
            declined = dependency_manager.decline("tex-basic")
            self.assertEqual(declined["status"], "DEGRADED")
            self.assertTrue(Path(declined["decision_receipt"]).is_file())

    def test_mcp_dependency_subroute_preserves_extended_tool_surface(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": temporary}, clear=False
        ):
            result = mcp_server.handle({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {
                    "name": "research_design",
                    "arguments": {
                        "action": "status", "project_root": temporary,
                        "dependency_action": "need", "dependency_component": "lean-mathlib",
                    },
                },
            })
            self.assertFalse(result["result"]["isError"])
            self.assertEqual(result["result"]["structuredContent"]["status"], "USER_DECISION_REQUIRED")
            unconfirmed = mcp_server.handle({
                "jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {
                    "name": "research_design",
                    "arguments": {
                        "action": "status", "project_root": temporary,
                        "dependency_action": "not_now", "dependency_component": "lean-mathlib",
                    },
                },
            })
            self.assertTrue(unconfirmed["result"]["isError"])
            self.assertEqual(
                unconfirmed["result"]["structuredContent"]["error"],
                "DEPENDENCY_USER_SELECTION_REQUIRED",
            )
            confirmed = mcp_server.handle({
                "jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {
                    "name": "research_design",
                    "arguments": {
                        "action": "status", "project_root": temporary,
                        "dependency_action": "not_now", "dependency_component": "lean-mathlib",
                        "dependency_selected_by": "user",
                    },
                },
            })
            self.assertFalse(confirmed["result"]["isError"])
            self.assertEqual(confirmed["result"]["structuredContent"]["status"], "DEGRADED")
            self.assertEqual(len(mcp_server.TOOLS), 17)

    def test_declined_git_blocks_staging_before_any_git_process(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": temporary}, clear=False
        ):
            dependency_manager.decline("portable-git")
            with patch.object(domain_skill_core.subprocess, "run", side_effect=AssertionError("git process started")):
                with self.assertRaises(domain_skill_core.DomainSkillError) as caught:
                    domain_skill_core._remote_head("owner/repository")
            self.assertIn("DEPENDENCY_DECLINED", str(caught.exception))

    def test_tex_compile_is_a_subroute_without_expanding_frozen_actions(self):
        paper = next(item for item in mcp_server.TOOLS if item["name"] == "paper_audit")
        properties = paper["inputSchema"]["properties"]
        self.assertEqual(properties["action"]["enum"], ["plan", "lean_check", "submit", "status", "verify"])
        self.assertEqual(properties["verification_action"]["enum"], ["cross_verify"])
        self.assertEqual(properties["review_action"]["enum"], ["calibrate", "status"])
        self.assertEqual(properties["tex_action"]["enum"], ["compile"])

    def test_tex_compile_uses_static_degradation_after_decline(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "home")}, clear=False
        ):
            dependency_manager.decide([], [])
            tex = Path(temporary) / "paper.tex"
            tex.write_text("\\documentclass{article}\\begin{document}x\\end{document}\n", encoding="ascii")
            result = paper_audit_core.compile_tex_document(temporary, tex.name)
            self.assertEqual(result["status"], "DEGRADED")
            self.assertEqual(result["compiler"], "NOT_RUN_BY_USER")
            self.assertIsNone(result["pdf_path"])
            self.assertIn("TeX compilation", result["unverified"])


class P11ResourceGuardTests(unittest.TestCase):
    def test_owned_task_policy_is_at_most_half_a_gib_and_serial(self):
        policy = resource_guard.RESOURCE_POLICY
        self.assertEqual(policy["owned_task_budget_bytes"], 512 * 1024 ** 2)
        self.assertLessEqual(
            policy["worker_job_limit_bytes"] + policy["orchestrator_reserve_bytes"],
            policy["owned_task_budget_bytes"],
        )
        self.assertEqual(policy["maximum_parallel_workers"], 1)
        self.assertFalse(policy["gpu_allowed"])
        self.assertEqual(resource_guard.WORKER_JOB_LIMIT_BYTES, 384 * 1024 ** 2)
        self.assertEqual(resource_guard.ORCHESTRATOR_RESERVE_BYTES, 128 * 1024 ** 2)
        self.assertEqual(resource_guard.LEAN_WORKER_LIMIT_BYTES, 464 * 1024 ** 2)
        self.assertEqual(resource_guard.LEAN_ORCHESTRATOR_RESERVE_BYTES, 48 * 1024 ** 2)
        self.assertEqual(resource_guard.START_MIN_FREE_BYTES, 768 * 1024 ** 2)
        self.assertEqual(resource_guard.RUN_MIN_FREE_BYTES, 512 * 1024 ** 2)
        self.assertEqual(policy["memory_metric"], "aggregate_working_set")
        self.assertLessEqual(
            policy["lean_worker_limit_bytes"] + policy["lean_orchestrator_reserve_bytes"],
            policy["owned_task_budget_bytes"],
        )
        self.assertLessEqual(policy["sampling_interval_seconds"], 0.01)

    def test_orchestrator_working_set_is_measured(self):
        self.assertGreater(resource_guard.current_process_working_set_bytes(), 0)

    def test_incremental_hash_tracks_only_local_dependency_closure(self):
        target = PLUGIN / "tests" / "test_p0_round1_evidence_kernel.py"
        dependencies = {
            path.relative_to(PLUGIN).as_posix()
            for path in run_incremental_tests._local_dependency_files(target)
        }
        self.assertIn("tests/test_p0_round1_evidence_kernel.py", dependencies)
        self.assertIn("scripts/research_guard_core.py", dependencies)
        self.assertNotIn("tests/test_p8_cycle_b_statistical_rendering.py", dependencies)
        skill_target = PLUGIN / "tests" / "test_p2_round4_claim_heldout.py"
        skill_dependencies = {
            path.relative_to(PLUGIN).as_posix()
            for path in run_incremental_tests._local_dependency_files(skill_target)
        }
        self.assertIn("skills/paper-audit-guard/SKILL.md", skill_dependencies)

    def test_managed_child_forces_single_thread_scientific_runtimes(self):
        with patch.object(resource_guard, "require_start_headroom", return_value={}), \
             patch.object(resource_guard, "memory_snapshot", return_value={"available_physical_bytes": 8 * resource_guard.GIB}), \
             patch.object(resource_guard, "_assign_memory_job", return_value=None):
            completed = resource_guard.run_managed(
                [sys.executable, "-c", "import os; print(os.environ['OPENBLAS_NUM_THREADS'], os.environ['OMP_NUM_THREADS'])"],
                timeout=10,
            )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "1 1")

    def test_low_headroom_prevents_child_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            sentinel = Path(temporary) / "started.txt"
            command = [sys.executable, "-c", f"from pathlib import Path; Path({str(sentinel)!r}).write_text('started')"]
            with self.assertRaises(resource_guard.ResourceGuardError):
                resource_guard.run_managed(
                    command, timeout=10,
                    start_min_free_bytes=resource_guard.memory_snapshot()["total_physical_bytes"] + 1,
                )
            self.assertFalse(sentinel.exists())


if __name__ == "__main__":
    unittest.main()
