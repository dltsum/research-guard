from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import dependency_manager  # noqa: E402
import mcp_server  # noqa: E402


class InstallAndCleanTests(unittest.TestCase):
    def test_register_core_is_idempotent_and_records_one_component_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ):
            runtime = Path(temporary) / "runtime"
            executable = runtime / "bin" / "python"
            executable.parent.mkdir(parents=True)
            executable.write_text("fixture", encoding="ascii")
            first = dependency_manager.register_core(runtime)
            second = dependency_manager.register_core(runtime)
            self.assertEqual(first["status"], "INSTALLED")
            self.assertTrue(second["idempotent"])
            transaction = Path(temporary) / "guard" / "dependencies" / "transactions" / "core-runtime.json"
            self.assertTrue(transaction.is_file())
            self.assertEqual(json.loads(transaction.read_text(encoding="utf-8"))["status"], "COMMITTED")

    def test_interrupted_selection_is_saved_for_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ), patch.object(dependency_manager, "install", side_effect=KeyboardInterrupt):
            with self.assertRaises(dependency_manager.DependencyError) as caught:
                dependency_manager.decide(["portable-git"], [])
            self.assertEqual(caught.exception.code, "DEPENDENCY_INSTALL_CANCELLED")
            selection = json.loads(
                (Path(temporary) / "guard" / "dependencies" / "selection.json").read_text(encoding="utf-8")
            )
            self.assertEqual(selection["status"], "INTERRUPTED")
            self.assertIn("portable-git", selection["selected"])

    def test_optional_install_reuses_existing_component_without_replacing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ):
            payload = Path(temporary) / "git.zip"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("cmd/git.exe", "fixture")

            class Completed:
                returncode = 0
                stdout = "git"
                stderr = ""

            with patch.object(dependency_manager, "_verified_payload", return_value=payload), patch.object(
                dependency_manager.subprocess, "run", return_value=Completed()
            ):
                first = dependency_manager._install_zip_component("portable-git", "mingit.zip", "cmd/git.exe")
                installed = Path(first["root"]) / "cmd" / "git.exe"
                before = installed.read_bytes()
                second = dependency_manager._install_zip_component("portable-git", "mingit.zip", "cmd/git.exe")
            self.assertEqual(second.get("idempotent"), True)
            self.assertEqual(installed.read_bytes(), before)

    def test_optional_install_restores_previous_tree_when_receipt_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ):
            payload = Path(temporary) / "git.zip"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("cmd/git.exe", "replacement")
            destination = Path(temporary) / "guard" / "dependencies" / "installed" / "portable-git"
            executable = destination / "cmd" / "git.exe"
            executable.parent.mkdir(parents=True)
            executable.write_text("previous", encoding="ascii")
            previous_receipt = {
                "status": "BROKEN", "root": str(destination), "executables": {"git": str(executable)},
            }
            dependency_manager._atomic_json(
                Path(temporary) / "guard" / "dependencies" / "components" / "portable-git.json",
                previous_receipt,
            )

            class Completed:
                returncode = 0
                stdout = "git"
                stderr = ""

            with patch.object(dependency_manager, "_verified_payload", return_value=payload), patch.object(
                dependency_manager.subprocess, "run", return_value=Completed()
            ), patch.object(
                dependency_manager, "_write_component", side_effect=OSError("receipt fixture failure")
            ):
                with self.assertRaises(dependency_manager.DependencyError):
                    dependency_manager._install_zip_component("portable-git", "mingit.zip", "cmd/git.exe")
            self.assertEqual(executable.read_text(encoding="ascii"), "previous")

    def test_cancelled_existing_registration_never_removes_host_tool_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ):
            host_root = Path(temporary) / "host-tools"
            pdflatex = host_root / "pdflatex"
            pdflatex.parent.mkdir(parents=True)
            pdflatex.write_text("fixture", encoding="ascii")
            with patch.object(
                dependency_manager, "detect_existing",
                return_value={"available": True, "executables": {"pdflatex": str(pdflatex)}, "version": "fixture"},
            ), patch.object(dependency_manager, "require_start_headroom", return_value={}), patch.object(
                dependency_manager, "run_managed", side_effect=KeyboardInterrupt,
            ):
                with self.assertRaises(dependency_manager.DependencyError) as caught:
                    dependency_manager.register_existing("tex-basic")
            self.assertEqual(caught.exception.code, "DEPENDENCY_INSTALL_CANCELLED")
            self.assertTrue(pdflatex.exists())

    def test_cancel_command_removes_only_an_incomplete_generated_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ):
            home = Path(temporary) / "guard" / "dependencies"
            target = home / "installed" / "portable-git"
            target.mkdir(parents=True)
            (target / "partial.bin").write_bytes(b"partial")
            dependency_manager._begin_transaction("portable-git", "install", target)
            result = dependency_manager.cancel_install()
            self.assertEqual(result["status"], "CANCELLED")
            self.assertIn("portable-git", result["cancelled_components"])
            self.assertFalse(target.exists())

    def test_clean_removes_generated_paths_but_preserves_state_and_installed_component(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ):
            home = Path(temporary) / "guard"
            project = Path(temporary) / "project"
            runtime = home / "runtime" / "python"
            runtime.mkdir(parents=True)
            (runtime / "python.exe").write_text("fixture", encoding="ascii")
            dependency_manager.register_core(runtime)
            (home / "cache").mkdir(parents=True)
            (home / "cache" / "generated.bin").write_bytes(b"1234")
            (project / ".research-guard" / "sessions").mkdir(parents=True)
            (project / ".research-guard" / "sessions" / "turn.json").write_bytes(b"12345")
            (project / ".research-guard" / "state.json").write_text("{}", encoding="ascii")
            result = dependency_manager.clean_state(project, home=home)
            self.assertEqual(result["status"], "CLEANED")
            self.assertGreaterEqual(result["bytes_released"], 9)
            self.assertFalse((home / "cache").exists())
            self.assertFalse((project / ".research-guard" / "sessions").exists())
            self.assertTrue((project / ".research-guard" / "state.json").exists())
            self.assertTrue((home / "dependencies" / "components" / "core-runtime.json").exists())
            repeated = dependency_manager.clean_state(project, home=home)
            self.assertEqual(repeated["status"], "CLEANED")
            self.assertEqual(repeated["bytes_released"], 0)

    def test_hard_clean_removes_runs_and_dependency_receipts_but_not_installed_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ):
            home = Path(temporary) / "guard"
            project = Path(temporary) / "project"
            runtime = home / "runtime" / "python"
            runtime.mkdir(parents=True)
            (runtime / "python.exe").write_text("fixture", encoding="ascii")
            dependency_manager.register_core(runtime)
            (home / "dependencies" / "receipts" / "old.json").write_text("{}", encoding="ascii")
            (project / ".research-guard" / "runs" / "r1").mkdir(parents=True)
            (project / ".research-guard" / "runs" / "r1" / "raw.bin").write_bytes(b"123")
            result = dependency_manager.clean_state(project, home=home, hard=True)
            self.assertEqual(result["status"], "CLEANED")
            self.assertFalse((project / ".research-guard" / "runs").exists())
            self.assertFalse((home / "dependencies" / "receipts").exists())
            self.assertTrue((home / "dependencies" / "components" / "core-runtime.json").exists())

    def test_researchctl_clean_and_posix_installer_clean_are_available_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "guard"
            project = Path(temporary) / "project"
            (project / ".research-guard" / "cache").mkdir(parents=True)
            (project / ".research-guard" / "cache" / "x").write_bytes(b"x")
            environment = {**os.environ, "RESEARCH_GUARD_HOME": str(home), "PYTHONUTF8": "1"}
            ctl = subprocess.run(
                [
                    sys.executable, str(PLUGIN / "scripts" / "researchctl.py"), "clean",
                    "--project-root", str(project), "--home", str(home),
                ],
                text=True, capture_output=True, env=environment, cwd=PLUGIN, timeout=30,
            )
            self.assertEqual(ctl.returncode, 0, ctl.stderr)
            self.assertEqual(json.loads(ctl.stdout)["status"], "CLEANED")
            self.assertFalse((project / ".research-guard" / "cache").exists())

            (project / ".research-guard" / "sessions").mkdir(parents=True)
            (project / ".research-guard" / "sessions" / "x").write_bytes(b"x")
            (project / "dist").mkdir(parents=True)
            (project / "dist" / "_devcheck-modular-linux.zip").write_bytes(b"devcheck")
            installer = subprocess.run(
                [
                    sys.executable, str(PLUGIN / "scripts" / "install_posix.py"), "clean",
                    "--project-root", str(project), "--home", str(home), "--dry-run",
                ],
                text=True, capture_output=True, env=environment, cwd=PLUGIN, timeout=30,
            )
            self.assertEqual(installer.returncode, 0, installer.stderr)
            self.assertEqual(json.loads(installer.stdout)["status"], "DRY_RUN")
            self.assertTrue((project / ".research-guard" / "sessions").exists())
            cleaned = subprocess.run(
                [sys.executable, str(PLUGIN / "scripts" / "install_posix.py"), "clean", "--project-root", str(project), "--home", str(home)],
                text=True, capture_output=True, env=environment, cwd=PLUGIN, timeout=30,
            )
            self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
            self.assertFalse((project / ".research-guard" / "sessions").exists())
            self.assertFalse((project / "dist" / "_devcheck-modular-linux.zip").exists())

    def test_mcp_lifecycle_subroute_exposes_clean_status_and_install_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": str(Path(temporary) / "guard")}, clear=False
        ):
            project = Path(temporary) / "project"
            cache = project / ".research-guard" / "cache"
            cache.mkdir(parents=True)
            (cache / "probe.bin").write_bytes(b"probe")
            cleaned = mcp_server.handle({
                "jsonrpc": "2.0", "id": 10, "method": "tools/call",
                "params": {"name": "research_design", "arguments": {
                    "action": "status", "project_root": str(project),
                    "maintenance_action": "clean",
                }},
            })
            self.assertFalse(cleaned["result"]["isError"])
            self.assertEqual(cleaned["result"]["structuredContent"]["status"], "CLEANED")
            status = mcp_server.handle({
                "jsonrpc": "2.0", "id": 11, "method": "tools/call",
                "params": {"name": "research_design", "arguments": {
                    "action": "status", "project_root": str(project),
                    "maintenance_action": "status",
                }},
            })
            self.assertFalse(status["result"]["isError"])
            self.assertIn("components", status["result"]["structuredContent"])
            missing_choice = mcp_server.handle({
                "jsonrpc": "2.0", "id": 12, "method": "tools/call",
                "params": {"name": "research_design", "arguments": {
                    "action": "status", "project_root": str(project),
                    "maintenance_action": "update", "dependency_component": "tex-basic",
                }},
            })
            self.assertTrue(missing_choice["result"]["isError"])
            self.assertEqual(missing_choice["result"]["structuredContent"]["error"], "DEPENDENCY_USER_SELECTION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
