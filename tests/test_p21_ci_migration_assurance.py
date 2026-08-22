from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import test_isolated_install  # noqa: E402
import verify_isolated_install  # noqa: E402


class P21CiMigrationAssuranceTests(unittest.TestCase):
    @staticmethod
    def _manifest() -> str:
        return json.dumps({
            "schema_version": 1,
            "package": "research-guard",
            "platform": "linux-x64",
            "runtime_delivery": "system-python-venv",
            "files": [],
        })

    def test_safe_extractor_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "traversal.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("research-guard/RELEASE_MANIFEST.json", self._manifest())
                output.writestr("research-guard/../../escape.txt", "escape")
            with self.assertRaisesRegex(test_isolated_install.IsolatedInstallError, "escapes"):
                test_isolated_install.extract_archive(archive, root / "extract")
            self.assertFalse((root / "escape.txt").exists())

    def test_safe_extractor_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "symlink.zip"
            link = zipfile.ZipInfo("research-guard/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("research-guard/RELEASE_MANIFEST.json", self._manifest())
                output.writestr(link, "target")
            with self.assertRaisesRegex(test_isolated_install.IsolatedInstallError, "symlinks"):
                test_isolated_install.extract_archive(archive, root / "extract")

    def test_safe_extractor_rejects_cross_platform_name_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "collision.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("research-guard/RELEASE_MANIFEST.json", self._manifest())
                output.writestr("research-guard/Case.txt", "one")
                output.writestr("research-guard/case.txt", "two")
            with self.assertRaisesRegex(test_isolated_install.IsolatedInstallError, "duplicate"):
                test_isolated_install.extract_archive(archive, root / "extract")

    def test_safe_extractor_rejects_windows_reserved_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "reserved.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("research-guard/RELEASE_MANIFEST.json", self._manifest())
                output.writestr("research-guard/CON.txt", "unsafe")
            with self.assertRaisesRegex(test_isolated_install.IsolatedInstallError, "cross-platform safe"):
                test_isolated_install.extract_archive(archive, root / "extract")

    def test_installed_python_detection_accepts_windows_and_posix_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, relative in enumerate((Path("python.exe"), Path("Scripts/python.exe"), Path("bin/python"))):
                runtime = root / f"runtime-{index}"
                executable = runtime / relative
                executable.parent.mkdir(parents=True)
                executable.write_text("fixture", encoding="ascii")
                self.assertEqual(verify_isolated_install._installed_python(runtime), executable)
                user_root = root / f"user-{index}"
                installed = user_root / ".research-guard" / "runtime" / "python" / relative
                installed.parent.mkdir(parents=True)
                installed.write_text("fixture", encoding="ascii")
                self.assertEqual(test_isolated_install.installed_python(user_root), installed)

    def test_windows_runner_prefers_pwsh_and_retains_legacy_fallback(self) -> None:
        with patch("test_isolated_install.shutil.which", side_effect=lambda name: {
            "pwsh": "C:/Program Files/PowerShell/7/pwsh.exe",
            "powershell.exe": "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        }.get(name)):
            self.assertEqual(
                test_isolated_install.windows_powershell(),
                "C:/Program Files/PowerShell/7/pwsh.exe",
            )
        with patch("test_isolated_install.shutil.which", side_effect=lambda name: {
            "powershell.exe": "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        }.get(name)):
            self.assertEqual(
                test_isolated_install.windows_powershell(),
                "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            )

    def test_runner_refuses_a_preexisting_test_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "unused.zip"
            archive.write_bytes(b"unused")
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(test_isolated_install.IsolatedInstallError, "must not already exist"):
                test_isolated_install.run_isolated_install(archive, existing)

    def test_ci_builds_installs_then_retains_each_exact_archive(self) -> None:
        workflow = (PLUGIN / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        build = workflow.index("- name: Build platform migration archive")
        install = workflow.index("- name: Verify isolated platform installation")
        retain = workflow.index("- name: Retain verified migration archive")
        self.assertLess(build, install)
        self.assertLess(install, retain)
        for token in (
            "scripts/test_isolated_install.py",
            "dist/research-guard-${{ matrix.platform }}.zip",
            "actions/upload-artifact@v7",
            "archive: false",
            "retention-days: 3",
            "if-no-files-found: error",
            '--pattern "test_p21_*.py"',
        ):
            self.assertIn(token, workflow)
        release = (PLUGIN / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn('--pattern "test_p21_*.py"', release)
        self.assertIn("Verify isolated Linux release archive", release)
        self.assertLess(
            release.index("- name: Build POSIX migration archives"),
            release.index("- name: Verify isolated Linux release archive"),
        )
        self.assertLess(
            release.index("- name: Verify isolated Linux release archive"),
            release.index("- name: Publish GitHub release metadata"),
        )


if __name__ == "__main__":
    unittest.main()
