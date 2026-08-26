from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


MODULAR = _load("build_modular_development_test", SCRIPTS / "build_modular_package.py")
PUBLIC = _load("build_public_development_test", SCRIPTS / "build_public_package.py")
RUNTIME = _load("repack_runtime_development_test", SCRIPTS / "repack_python_runtime.py")


class DevelopmentBuildModeTests(unittest.TestCase):
    def test_modular_development_reads_source_without_creating_archive(self) -> None:
        source_before = (SCRIPTS / "build_modular_package.py").read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "would-be-archive.zip"
            receipt = MODULAR.build(output, "windows-x64", mode="development")
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["mode"], "development")
        self.assertTrue(receipt["source_tree"])
        self.assertFalse(receipt["archive_created"])
        self.assertFalse(output.exists())
        self.assertEqual(receipt["hashes"], "omitted_in_development_mode")
        self.assertEqual(source_before, (SCRIPTS / "build_modular_package.py").read_bytes())

    def test_public_development_mode_omits_release_hashes_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "would-be-public.zip"
            receipt = PUBLIC.build(output, mode="development")
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["mode"], "development")
        self.assertFalse(receipt["archive_created"])
        self.assertFalse(output.exists())
        self.assertNotIn("sha256", receipt)

    def test_runtime_development_mode_inspects_zip_without_copying_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "runtime.zip"
            output = root / "repacked.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("Lib/site-packages/example.py", "x = 1\n")
                archive.writestr("tests/test_example.py", "assert True\n")
            receipt = RUNTIME.repack(source, output, mode="development")
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["mode"], "development")
        self.assertFalse(receipt["archive_created"])
        self.assertEqual(receipt["entries"], 1)
        self.assertEqual(receipt["hashes"], "omitted_in_development_mode")
        self.assertFalse(output.exists())

    def test_release_mode_still_requires_an_output_path(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "output is required"):
            MODULAR.build(None, "linux-x64")
        with self.assertRaisesRegex(RuntimeError, "output is required"):
            PUBLIC.build(None)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "runtime.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("python.exe", b"fixture")
            with self.assertRaisesRegex(RuntimeError, "output is required"):
                RUNTIME.repack(source, None)

    def test_cli_development_mode_is_json_and_does_not_need_output(self) -> None:
        # Exercise the public entry point without constructing a package.
        import subprocess

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "build_public_package.py"),
                "--mode",
                "development",
            ],
            cwd=PLUGIN,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["status"], "PASS")
        self.assertFalse(receipt["archive_created"])
        self.assertEqual(receipt["hashes"], "omitted_in_development_mode")

        modular = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "build_modular_package.py"),
                "--platform",
                "windows-x64",
                "--mode",
                "development",
            ],
            cwd=PLUGIN,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
        modular_receipt = json.loads(modular.stdout)
        self.assertEqual(modular_receipt["status"], "PASS")
        self.assertFalse(modular_receipt["archive_created"])
        self.assertEqual(modular_receipt["hashes"], "omitted_in_development_mode")


if __name__ == "__main__":
    unittest.main()
