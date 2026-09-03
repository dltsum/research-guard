from __future__ import annotations

import json
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
import install_posix  # noqa: E402
import mcp_launcher  # noqa: E402
import research_guard_core  # noqa: E402
from network_config_core import (  # noqa: E402
    config_path,
    network_environment,
    read_saved_proxy,
    request_routes,
    write_network_config,
)
from resource_guard import memory_snapshot, run_managed_light  # noqa: E402


class CrossPlatformContractTests(unittest.TestCase):
    def test_source_mcp_entrypoint_is_shell_neutral(self) -> None:
        value = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        server = value["mcpServers"]["research-guard"]
        self.assertEqual(server["command"], "python")
        self.assertIn("${PLUGIN_ROOT}/scripts/mcp_launcher.py", server["args"])
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        for event in hooks["hooks"].values():
            for registration in event:
                for hook in registration.get("hooks", []):
                    self.assertIn("hooks/hook.sh", hook["command"])
                    self.assertIn("scripts\\hook.cmd", hook["commandWindows"])
        self.assertTrue((PLUGIN / "hooks" / "hook.sh").is_file())

    def test_dependency_catalog_is_not_host_platform_preset(self) -> None:
        catalog = json.loads((PLUGIN / "assets" / "dependency-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["platform"], "platform-neutral")
        self.assertEqual(set(catalog["platforms"]), {"windows-x64", "linux-x64", "macos-x64", "macos-arm64"})
        payload = json.loads((PLUGIN / "assets" / "payload-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["scope"], "windows-x64-only; ignored by POSIX installers")

    def test_source_mcp_launcher_isolated_from_host_network_and_python_paths(self) -> None:
        with patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://machine-only.invalid:9999",
                "PIP_INDEX_URL": "https://machine-only.invalid/simple",
                "PYTHONPATH": "C:/machine-only/python",
                "RESEARCH_GUARD_HOME": "C:/selected/guard",
            },
            clear=True,
        ):
            child = mcp_launcher._child_environment()
        for name in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
            "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_CONFIG_FILE", "UV_INDEX_URL",
            "PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYTHONSTARTUP",
            "PYTHONEXECUTABLE", "PYTHONIOENCODING", "PYTHONWARNINGS", "PYTHONBREAKPOINT", "PYTHONUTF8",
        ):
            self.assertNotIn(name, child)
        self.assertEqual(child["RESEARCH_GUARD_HOME"], "C:/selected/guard")

    def test_platform_mapping_is_explicit(self) -> None:
        cases = [
            ("Linux", "x86_64", "linux-x64"),
            ("Darwin", "x86_64", "macos-x64"),
            ("Darwin", "arm64", "macos-arm64"),
        ]
        for system, machine, expected in cases:
            with self.subTest(expected=expected), patch("install_posix.platform.system", return_value=system), patch(
                "install_posix.platform.machine", return_value=machine,
            ):
                self.assertEqual(install_posix._host_platform(), expected)

    def test_posix_marketplace_registration_file_is_local_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = install_posix._write_marketplace(root)
            install_posix._write_marketplace(root)
            value = json.loads(path.read_text(encoding="utf-8"))
            records = [item for item in value["plugins"] if item.get("name") == "research-guard"]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["source"], {"source": "local", "path": "./plugins/research-guard"})

    def test_core_runtime_registration_accepts_windows_and_posix_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old_home = os.environ.get("RESEARCH_GUARD_HOME")
            os.environ["RESEARCH_GUARD_HOME"] = str(root / "state")
            try:
                for index, relative in enumerate((Path("python.exe"), Path("Scripts/python.exe"), Path("bin/python"))):
                    runtime = root / f"runtime-{index}"
                    executable = runtime / relative
                    executable.parent.mkdir(parents=True, exist_ok=True)
                    executable.write_text("fixture", encoding="ascii")
                    receipt = dependency_manager.register_core(runtime)
                    self.assertEqual(Path(receipt["executables"]["python"]), executable.resolve())
            finally:
                if old_home is None:
                    os.environ.pop("RESEARCH_GUARD_HOME", None)
                else:
                    os.environ["RESEARCH_GUARD_HOME"] = old_home

    def test_resource_guard_reports_physical_memory_and_owns_a_child(self) -> None:
        snapshot = memory_snapshot()
        self.assertGreater(snapshot["total_physical_bytes"], 0)
        self.assertGreater(snapshot["available_physical_bytes"], 0)
        result = run_managed_light([sys.executable, "-c", "print('cross-platform-pass')"], timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertIn("cross-platform-pass", result.stdout)
        self.assertLessEqual(result.resource_usage["peak_owned_bytes"], result.resource_usage["owned_limit_bytes"])

    def test_network_config_defaults_direct_and_does_not_copy_ambient_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {
                "RESEARCH_GUARD_HOME": temporary,
                "HTTP_PROXY": "http://machine-only.invalid:9999",
                "HTTPS_PROXY": "http://machine-only.invalid:9999",
                "ALL_PROXY": "http://machine-only.invalid:9999",
            },
            clear=True,
        ):
            self.assertIsNone(read_saved_proxy(temporary))
            self.assertEqual(request_routes("https://api.crossref.org/works"), (("foreign-direct", None),))
            self.assertEqual(request_routes("https://www.ccf.org.cn/Academic_Evaluation/CN/"), (("foreign-direct", None),))
            child = network_environment(proxy=None)
            for name in (
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy",
                "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_TRUSTED_HOST", "PIP_NO_INDEX", "PIP_FIND_LINKS",
                "PIP_CONFIG_FILE", "PIP_CERT", "PIP_CLIENT_CERT", "UV_INDEX_URL", "UV_EXTRA_INDEX_URL", "UV_FIND_LINKS",
            ):
                self.assertNotIn(name, child)
            self.assertFalse(config_path(temporary).exists())

    def test_network_config_persists_only_explicit_credential_free_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = write_network_config("https://proxy.example:8443/", temporary)
            self.assertEqual(path, config_path(temporary))
            self.assertEqual(read_saved_proxy(temporary), "https://proxy.example:8443")
            self.assertEqual(request_routes("https://api.crossref.org/works", temporary)[0], ("foreign-proxy", "https://proxy.example:8443"))
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("username", json.dumps(value).casefold())
            self.assertTrue(value["configured"])

    def test_posix_install_choice_prompt_can_be_skipped_or_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            self.assertEqual(install_posix._resolve_foreign_proxy(None, home, interactive=False), (None, True))
            write_network_config(None, home)
            self.assertEqual(install_posix._resolve_foreign_proxy(None, home, interactive=False), (None, False))
            self.assertEqual(install_posix._resolve_foreign_proxy("http://proxy.example:3128", home, interactive=False), ("http://proxy.example:3128", True))

    def test_lean_detection_respects_an_explicit_research_guard_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": temporary}, clear=True
        ), patch.object(dependency_manager, "_validate_lean_runtime", return_value=False) as validate, patch.object(
            dependency_manager.shutil, "which", return_value=None
        ):
            dependency_manager.detect_existing("lean-mathlib")
        candidates = [call.args[0] for call in validate.call_args_list]
        expected = (Path(temporary) / "lean-audit-runtime" / "v4.33.0").resolve()
        self.assertIn(expected, candidates)
        self.assertNotIn(Path.home() / ".research-guard" / "lean-audit-runtime" / "v4.33.0", candidates)

    def test_signing_key_respects_an_explicit_research_guard_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RESEARCH_GUARD_HOME": temporary}, clear=True
        ):
            self.assertEqual(
                research_guard_core._signing_key_path(),
                Path(temporary).resolve() / "signing.key",
            )

    def test_network_clients_have_no_machine_specific_proxy_preset(self) -> None:
        clients = (
            "scripts/research_guard_core.py", "scripts/discipline_profile_core.py",
            "scripts/citation_guard_core.py", "scripts/domain_skill_core.py",
            "scripts/openreview_calibration_core.py", "scripts/venue_evidence_core.py",
            "scripts/hydrate_release_payloads.py", "scripts/hydrate_research_assets.py",
            "scripts/install_posix.py", "scripts/install.ps1", "scripts/install_lean_mathlib.ps1",
        )
        for relative in clients:
            text = (PLUGIN / relative).read_text(encoding="utf-8")
            self.assertNotIn("127.0.0.1:7897", text, relative)
            self.assertNotRegex(text, r"RESEARCH_GUARD_FOREIGN_PROXY\"\s*,\s*\"http://", relative)

    def test_windows_launchers_honor_explicit_runtime_and_install_roots(self) -> None:
        runtime = (PLUGIN / "scripts" / "runtime.cmd").read_text(encoding="utf-8")
        self.assertLess(runtime.index("RESEARCH_GUARD_PYTHON"), runtime.index("USERPROFILE"))
        mcp = (PLUGIN / "scripts" / "mcp.ps1").read_text(encoding="utf-8")
        self.assertLess(mcp.index("RESEARCH_GUARD_PYTHON"), mcp.index("GetFolderPath"))
        installer = (PLUGIN / "scripts" / "install.ps1").read_text(encoding="utf-8")
        self.assertLess(installer.index("$UserRoot"), installer.index("GetFolderPath('UserProfile')"))
        self.assertLess(installer.index("$GuardHome", installer.index("$guardHome =")), installer.index("$env:RESEARCH_GUARD_HOME", installer.index("$guardHome =")))
        self.assertLess(installer.index("$CodexHome"), installer.index("$env:RESEARCH_GUARD_CODEX_ROOT"))
        posix = (PLUGIN / "scripts" / "install_posix.py").read_text(encoding="utf-8")
        self.assertIn('getattr(arguments, "home", None)', posix)
        self.assertIn('"--codex-home"', posix)
        self.assertIn("Write-McpConfig", installer)
        self.assertLess(installer.index("Write-McpConfig"), installer.index("register-core"))
        self.assertIn("$maintenanceUserRoot", installer)
        self.assertIn("RESEARCH_GUARD_PYTHON", installer)

    def test_managed_children_do_not_inherit_host_proxy_or_package_index(self) -> None:
        with patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://machine-only.invalid:9999",
                "HTTPS_PROXY": "http://machine-only.invalid:9999",
                "PIP_INDEX_URL": "https://machine-only.invalid/simple",
                "UV_INDEX_URL": "https://machine-only.invalid/simple",
                "PYTHONPATH": "C:/machine-only/python",
                "PYTHONHOME": "C:/machine-only/home",
            },
            clear=False,
        ):
            completed = run_managed_light([
                sys.executable, "-c",
                "import os; print([os.environ.get(k) for k in ('HTTP_PROXY','HTTPS_PROXY','PIP_INDEX_URL','UV_INDEX_URL','PYTHONPATH','PYTHONHOME','MPLBACKEND','CUDA_VISIBLE_DEVICES')])",
            ], timeout=30)
        self.assertEqual(completed.stdout.strip(), "[None, None, None, None, None, None, 'Agg', '']")

    def test_lean_tool_resolution_has_no_fixed_windows_layout(self) -> None:
        manager = (PLUGIN / "scripts" / "dependency_manager.py").read_text(encoding="utf-8")
        self.assertNotIn('r"C:\\Windows"', manager)
        self.assertIn('shutil.which("pwsh")', manager)

    def test_git_source_routes_override_a_global_proxy_preset(self) -> None:
        class Completed:
            returncode = 0
            stdout = "a" * 40 + "\tHEAD\n"
            stderr = ""

        with patch.object(domain_skill_core, "_registered_git", return_value="git"), patch.object(
            domain_skill_core, "foreign_proxy_for", return_value=None
        ), patch.object(domain_skill_core.subprocess, "run", return_value=Completed()) as run:
            self.assertEqual(domain_skill_core._remote_head("owner/repository"), "a" * 40)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["git", "-c", "http.proxy="])
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)

    def test_ci_install_smoke_does_not_force_one_mirror_on_every_platform(self) -> None:
        for relative in (".github/workflows/ci.yml", ".github/workflows/release.yml"):
            text = (PLUGIN / relative).read_text(encoding="utf-8")
            self.assertNotIn("--pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple", text, relative)
            self.assertIn("--isolated", text, relative)
            self.assertIn("--index-url https://pypi.org/simple", text, relative)

    def test_posix_dependency_child_scrubs_ambient_proxy_and_uses_explicit_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {
                "HTTP_PROXY": "http://machine-only.invalid:9999",
                "HTTPS_PROXY": "http://machine-only.invalid:9999",
                "ALL_PROXY": "http://machine-only.invalid:9999",
            },
            clear=True,
        ), patch.object(install_posix, "_run", return_value=None) as run:
            python = Path(temporary) / "python"
            requirements = Path(temporary) / "requirements.txt"
            requirements.write_text("", encoding="ascii")
            install_posix._install_requirements(python, requirements, "https://pypi.org/simple")
            environment = run.call_args.kwargs["env"]
            self.assertNotIn("machine-only.invalid", json.dumps(environment))
            self.assertNotIn("HTTP_PROXY", environment)
            install_posix._install_requirements(
                python, requirements, "https://pypi.org/simple", foreign_proxy="http://proxy.example:3128"
            )
            proxied_command = run.call_args.args[0]
            proxied_environment = run.call_args.kwargs["env"]
            self.assertIn("--isolated", proxied_command)
            self.assertEqual(proxied_command[proxied_command.index("--proxy") + 1], "http://proxy.example:3128")
            self.assertNotIn("HTTPS_PROXY", proxied_environment)

    def test_posix_dependency_proxy_transport_failure_recovers_direct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            install_posix,
            "_run",
            side_effect=[install_posix.InstallError("ProxyError: failed to establish a new connection"), None],
        ) as run:
            python = Path(temporary) / "python"
            requirements = Path(temporary) / "requirements.txt"
            requirements.write_text("", encoding="ascii")
            receipt: dict[str, object] = {}
            self.assertEqual(
                install_posix._install_requirements(
                    python, requirements, "https://pypi.org/simple",
                    foreign_proxy="http://proxy.example:3128", network_receipt=receipt,
                ),
                "https://pypi.org/simple",
            )
            self.assertEqual(run.call_count, 2)
            self.assertEqual(receipt["network_routes_attempted"], ["foreign-proxy", "foreign-direct-fallback"])
            self.assertEqual(receipt["network_routes_used"], ["foreign-direct-fallback"])
            self.assertEqual(receipt["network_route"], "foreign-direct-fallback")
            self.assertNotIn("--proxy", run.call_args.args[0])

    def test_posix_dependency_semantic_failure_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            install_posix,
            "_run",
            side_effect=install_posix.InstallError("ERROR: No matching distribution found"),
        ) as run:
            python = Path(temporary) / "python"
            requirements = Path(temporary) / "requirements.txt"
            requirements.write_text("", encoding="ascii")
            with self.assertRaises(install_posix.InstallError):
                install_posix._install_requirements(
                    python, requirements, "https://pypi.org/simple",
                    foreign_proxy="http://proxy.example:3128",
                )
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
