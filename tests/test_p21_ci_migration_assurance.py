from __future__ import annotations

import json
import hashlib
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
import hydrate_release_payloads  # noqa: E402
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

    @staticmethod
    def _write_payload_fixture(root: Path, *, bad_release_hash: bool = False) -> tuple[Path, Path, Path]:
        root.mkdir(parents=True, exist_ok=True)
        contents = {"runtime.zip": b"runtime-fixture", "tool.exe": b"tool-fixture"}
        payload_manifest = root / "payload-manifest.json"
        payload_value = {
            "schema_version": 1,
            "platform": "windows-x64",
            "payloads": [
                {
                    "name": name,
                    "bytes": len(value),
                    "sha256": hashlib.sha256(value).hexdigest(),
                }
                for name, value in contents.items()
            ],
        }
        payload_manifest.write_text(
            json.dumps(payload_value, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        release_files = [
            {
                "path": f"assets/payloads/{name}",
                "bytes": len(value),
                "sha256": (
                    "0" * 64 if bad_release_hash and name == "runtime.zip"
                    else hashlib.sha256(value).hexdigest()
                ),
            }
            for name, value in contents.items()
        ]
        archive = root / "research-guard-windows-x64-modular.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr("research-guard/RELEASE_MANIFEST.json", json.dumps({
                "schema_version": 1,
                "package": "research-guard",
                "platform": "windows-x64",
                "files": release_files,
            }))
            for name, value in contents.items():
                output.writestr(f"research-guard/assets/payloads/{name}", value)
        bootstrap = root / "payload-bootstrap.json"
        bootstrap.write_text(json.dumps({
            "schema_version": 1,
            "repository": "dltsum/research-guard",
            "release_tag": "v0.7.0",
            "asset_name": "research-guard-windows-x64-modular.zip",
            "asset_bytes": archive.stat().st_size,
            "asset_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "payload_manifest_sha256": hashlib.sha256(payload_manifest.read_bytes()).hexdigest(),
            "source": (
                "https://github.com/dltsum/research-guard/releases/download/"
                "v0.7.0/research-guard-windows-x64-modular.zip"
            ),
        }, indent=2) + "\n", encoding="utf-8")
        return archive, bootstrap, payload_manifest

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

    def test_payload_hydration_cross_checks_archive_release_and_payload_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, bootstrap, payload_manifest = self._write_payload_fixture(root)
            output = root / "payloads"
            result = hydrate_release_payloads.hydrate_from_archive(
                archive, bootstrap, payload_manifest, output,
            )
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["payload_count"], 2)
            self.assertEqual((output / "runtime.zip").read_bytes(), b"runtime-fixture")
            self.assertEqual((output / "tool.exe").read_bytes(), b"tool-fixture")

    def test_payload_hydration_rejects_unpinned_archive_or_release_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, bootstrap, payload_manifest = self._write_payload_fixture(root)
            with archive.open("ab") as output:
                output.write(b"changed")
            with self.assertRaisesRegex(hydrate_release_payloads.PayloadHydrationError, "archive mismatch"):
                hydrate_release_payloads.hydrate_from_archive(
                    archive, bootstrap, payload_manifest, root / "payloads-one",
                )
            archive, bootstrap, payload_manifest = self._write_payload_fixture(
                root / "release-record", bad_release_hash=True,
            )
            with self.assertRaisesRegex(hydrate_release_payloads.PayloadHydrationError, "metadata mismatch"):
                hydrate_release_payloads.hydrate_from_archive(
                    archive, bootstrap, payload_manifest, root / "payloads-two",
                )

    def test_payload_directory_rejects_missing_tampered_and_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive, bootstrap, payload_manifest = self._write_payload_fixture(root)
            output = root / "payloads"
            hydrate_release_payloads.hydrate_from_archive(archive, bootstrap, payload_manifest, output)
            (output / "unexpected.bin").write_bytes(b"unexpected")
            with self.assertRaisesRegex(hydrate_release_payloads.PayloadHydrationError, "extra"):
                hydrate_release_payloads.validate_payload_directory(payload_manifest, output)
            (output / "unexpected.bin").unlink()
            (output / "runtime.zip").write_bytes(b"tampered")
            with self.assertRaisesRegex(hydrate_release_payloads.PayloadHydrationError, "integrity mismatch"):
                hydrate_release_payloads.validate_payload_directory(payload_manifest, output)
            (output / "runtime.zip").unlink()
            with self.assertRaisesRegex(hydrate_release_payloads.PayloadHydrationError, "missing"):
                hydrate_release_payloads.validate_payload_directory(payload_manifest, output)

    def test_ci_builds_installs_then_retains_each_exact_archive(self) -> None:
        workflow = (PLUGIN / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        hydrate = workflow.index("- name: Hydrate audited Windows release payloads")
        build = workflow.index("- name: Build platform migration archive")
        install = workflow.index("- name: Verify isolated platform installation")
        retain = workflow.index("- name: Retain verified migration archive")
        self.assertLess(hydrate, build)
        self.assertLess(build, install)
        self.assertLess(install, retain)
        for token in (
            "scripts/test_isolated_install.py",
            "scripts/hydrate_release_payloads.py",
            "if: runner.os == 'Windows'",
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

    def test_ui_archive_and_checksum_are_retained_as_separate_exact_files(self) -> None:
        workflow = (PLUGIN / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        archive_start = workflow.index("- name: Retain verified optional Research Console archive")
        checksum_start = workflow.index("- name: Retain optional Research Console checksum")
        archive_block = workflow[archive_start:checksum_start]
        checksum_block = workflow[checksum_start:]
        self.assertLess(archive_start, checksum_start)
        for block, name, path in (
            (archive_block, "name: research-guard-ui-addon", "path: dist/research-guard-ui-addon.zip"),
            (checksum_block, "name: research-guard-ui-checksum", "path: dist/SHA256SUMS-ui.txt"),
        ):
            self.assertIn(name, block)
            self.assertIn(path, block)
            self.assertIn("archive: false", block)
            self.assertIn("if-no-files-found: error", block)

    def test_windows_builder_has_a_pre_enumeration_payload_integrity_gate(self) -> None:
        source = (PLUGIN / "scripts" / "build_modular_package.py").read_text(encoding="utf-8")
        preflight = source.index("validate_payload_directory(")
        enumerate_files = source.index('PLUGIN_ROOT.rglob("*")')
        self.assertLess(preflight, enumerate_files)
        for token in (
            "WINDOWS_PAYLOAD_PREFLIGHT_FAILED",
            'platform_target == "windows-x64"',
            'PLUGIN_ROOT / "assets" / "payloads"',
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
