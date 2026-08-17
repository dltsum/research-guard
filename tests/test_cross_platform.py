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
import install_posix  # noqa: E402
from resource_guard import memory_snapshot, run_managed_light  # noqa: E402


class CrossPlatformContractTests(unittest.TestCase):
    def test_source_mcp_entrypoint_is_shell_neutral(self) -> None:
        value = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
        server = value["mcpServers"]["research-guard"]
        self.assertEqual(server["command"], "python")
        self.assertIn("${PLUGIN_ROOT}/scripts/mcp_launcher.py", server["args"])

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


if __name__ == "__main__":
    unittest.main()
