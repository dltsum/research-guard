from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ADDON = Path(__file__).resolve().parents[1]
PLUGIN = ADDON.parents[1]
FAKE_CODEX = Path(__file__).resolve().parent / "fake_codex.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class PackageTests(unittest.TestCase):
    def test_core_package_whitelists_exclude_the_entire_addon_tree(self) -> None:
        modular = load("build_modular_for_ui_test", PLUGIN / "scripts" / "build_modular_package.py")
        public = load("build_public_for_ui_test", PLUGIN / "scripts" / "build_public_package.py")
        relative = Path("addons/research-console/research_console/server.py")
        self.assertFalse(modular._include(relative))
        self.assertFalse(public._include(relative))

    def test_addon_archive_is_deterministic_small_and_contains_no_core_plugin(self) -> None:
        builder = load("build_ui_addon_test", ADDON / "build_addon.py")
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.zip"
            second = Path(temporary) / "second.zip"
            first_receipt = builder.build(first)
            second_receipt = builder.build(second)
            self.assertEqual(first_receipt["sha256"], second_receipt["sha256"])
            self.assertLess(first_receipt["bytes"], 1_000_000)
            self.assertFalse(first_receipt["core_archive_embedded"])
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                self.assertTrue(all(item.compress_type == zipfile.ZIP_STORED for item in archive.infolist()))
                self.assertIn("research-guard-ui-addon/ADDON_MANIFEST.json", names)
                self.assertIn("research-guard-ui-addon/README.zh-CN.md", names)
                self.assertIn("research-guard-ui-addon/research_console/server.py", names)
                self.assertFalse(any("mcp_server.py" in name or "assets/payloads" in name or ".codex-plugin" in name for name in names))
                manifest = json.loads(archive.read("research-guard-ui-addon/ADDON_MANIFEST.json"))
                self.assertEqual(manifest["package"]["maximum_archive_bytes"], 25 * 1024**2)
                self.assertFalse(manifest["security"]["server_transcript_persistence"])

    def test_extracted_addon_installs_versioned_and_idempotently(self) -> None:
        builder = load("build_ui_addon_install_test", ADDON / "build_addon.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "addon.zip"
            builder.build(archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(root / "extract")
            package_root = root / "extract" / "research-guard-ui-addon"
            installer = load("install_ui_addon_test", package_root / "install.py")
            with patch.dict(os.environ, {"FAKE_RESEARCH_GUARD_PLUGIN_ROOT": str(PLUGIN)}):
                receipt = installer.install(
                    package_root=package_root,
                    target_root=root / "installed",
                    command_prefix=(sys.executable, str(FAKE_CODEX)),
                    runtime_candidates=(Path(sys.executable),),
                )
                repeated = installer.install(
                    package_root=package_root,
                    target_root=root / "installed",
                    command_prefix=(sys.executable, str(FAKE_CODEX)),
                    runtime_candidates=(Path(sys.executable),),
                )
            self.assertEqual(receipt["status"], "INSTALLED")
            self.assertEqual(repeated["status"], "ALREADY_INSTALLED")
            target = Path(receipt["target"])
            self.assertTrue((target / "launch.py").is_file())
            pointer = json.loads((root / "installed" / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(pointer["version"], "0.1.0")

    def test_installer_rejects_unregistered_package_files(self) -> None:
        builder = load("build_ui_addon_extra_file_test", ADDON / "build_addon.py")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "addon.zip"
            builder.build(archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(root / "extract")
            package_root = root / "extract" / "research-guard-ui-addon"
            (package_root / "unregistered.txt").write_text("not admitted", encoding="utf-8")
            installer = load("install_ui_addon_extra_file_test", package_root / "install.py")
            with self.assertRaises(installer.InstallError):
                installer._load_and_verify_manifest(package_root)


if __name__ == "__main__":
    unittest.main()
