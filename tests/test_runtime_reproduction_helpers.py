"""Small local distribution/ZIP fixtures, separate from real runtime receipts."""
import json
import sys
import tempfile
import unittest
import zipfile
import hashlib
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from extend_python_runtime import extend
from reproduction_helpers import replay_saved_search, runtime_snapshot, verify_runtime, lean_basic_profile, LEAN_BASIC_URL, LEAN_BASIC_SHA256
from paper_audit_core import AuditError, _lean_runtime, run_lean_formula_audit
from repack_python_runtime import repack
from evidence_kernel import EvidenceRecorder


class RuntimeReproductionTests(unittest.TestCase):
    def test_saved_runtime_lock_rejects_version_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "lock.json"
            expected = {"status": "PASS", "python": "unit-build", "platform": "unit-platform", "cache_tag": "unit-tag", "packages": {"psutil": {"status": "PASS", "version": "7.0.0"}}}
            lock.write_text(json.dumps(expected), encoding="utf8")
            with patch("reproduction_helpers.runtime_snapshot", return_value=expected):
                self.assertEqual(verify_runtime("unit-python", lock)["status"], "PASS")
            changed = {**expected, "packages": {"psutil": {"status": "PASS", "version": "6.0.0"}}}
            with patch("reproduction_helpers.runtime_snapshot", return_value=changed):
                receipt = verify_runtime("unit-python", lock)
            self.assertEqual(receipt["status"], "MISMATCH")
            self.assertIn("Package differs: psutil", receipt["differences"])

    def test_basic_profile_accepts_local_binary_without_checksum_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "bin/lean.exe"
            path.parent.mkdir()
            path.write_bytes(b"explicit unit fixture, never executed")
            self.assertTrue(Path(lean_basic_profile(root)["lean_executable"]).samefile(path))
            path.write_bytes(b"updated local unit fixture")
            self.assertTrue(Path(lean_basic_profile(root)["lean_executable"]).samefile(path))

    def test_basic_runtime_must_be_explicit(self):
        with self.assertRaisesRegex(AuditError, "LEAN_BASIC_RUNTIME_REQUIRED"):
            _lean_runtime(None, lean_profile="lean-basic")

    def test_basic_does_not_bypass_mathlib_import_or_placeholder_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "proof.lean"
            source.write_text("import Mathlib\nset_option autoImplicit false\n", encoding="utf8")
            with self.assertRaisesRegex(AuditError, "only the installed Init"):
                run_lean_formula_audit(root, source.name, {}, lean_profile="lean-basic")
            source.write_text("import Init\nset_option autoImplicit false\nexample : True := by sorry\n", encoding="utf8")
            with self.assertRaisesRegex(AuditError, "forbidden Lean"):
                run_lean_formula_audit(root, source.name, {}, lean_profile="lean-basic")
            with self.assertRaisesRegex(AuditError, "importing Mathlib"):
                run_lean_formula_audit(root, source.name, {})

    def test_repack_preserves_psutil_native_extension_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.zip", root / "output.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("Lib/site-packages/psutil/__init__.py", "unit fixture")
                archive.writestr("Lib/site-packages/psutil/_psutil_windows.pyd", b"unit-native-fixture")
                archive.writestr("Lib/site-packages/psutil-7.0.0.dist-info/METADATA", "Name: psutil")
                archive.writestr("Lib/site-packages/psutil/tests/test_fixture.py", "unit test")
            receipt = repack(source, output)
            self.assertEqual(receipt["status"], "PASS")
            with zipfile.ZipFile(output) as archive:
                self.assertIn("Lib/site-packages/psutil/_psutil_windows.pyd", archive.namelist())
                self.assertIn("Lib/site-packages/psutil-7.0.0.dist-info/METADATA", archive.namelist())
                self.assertNotIn("Lib/site-packages/psutil/tests/test_fixture.py", archive.namelist())

    def test_psutil_extension_replaces_old_package_and_metadata_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            (site / "psutil").mkdir(parents=True)
            (site / "psutil/__init__.py").write_text("version='unit-new'", encoding="utf8")
            meta = site / "psutil-7.0.0.dist-info"
            meta.mkdir()
            (meta / "METADATA").write_text("Name: psutil\nVersion: 7.0.0\n", encoding="utf8")
            (meta / "RECORD").write_text("psutil/__init__.py,,\npsutil-7.0.0.dist-info/METADATA,,\npsutil-7.0.0.dist-info/RECORD,,\n", encoding="utf8")
            source = root / "runtime.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("python.exe", b"unit fixture")
                archive.writestr("Lib/site-packages/psutil/__init__.py", "old")
                archive.writestr("Lib/site-packages/psutil-6.0.0.dist-info/METADATA", "old metadata")
            output = root / "new/output.zip"
            receipt = extend(source, site, output, packages=("psutil",))
            self.assertEqual(receipt["added_distributions"], {"psutil": "7.0.0"})
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
                self.assertNotIn("Lib/site-packages/psutil-6.0.0.dist-info/METADATA", archive.namelist())
                self.assertEqual(archive.read("Lib/site-packages/psutil/__init__.py"), b"version='unit-new'")

    def test_missing_requested_distribution_fails_before_creating_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "site").mkdir()
            with zipfile.ZipFile(root / "source.zip", "w"):
                pass
            with self.assertRaisesRegex(ValueError, "unavailable: psutil"):
                extend(root / "source.zip", root / "site", root / "out.zip", packages=("psutil",))
            self.assertFalse((root / "out.zip").exists())

    def test_saved_search_replay_reads_current_files_as_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorder = EvidenceRecorder(root, "local-replay-unit")
            recorder.record_fixture(source="crossref", query_id="q1", query="unit fixture", payload={"items": []})
            relative, manifest = recorder.finalize(method_version=1, method_hash="method", query_plan_hash="plan", query_runs=[])
            replay = replay_saved_search(root, relative)
            self.assertEqual(replay["status"], "PASS")
            self.assertEqual(replay["scientific_status"], "HISTORICAL_EVIDENCE_ONLY")
            raw = root / manifest["attempts"][0]["raw_path"]
            raw.write_text('{"items": [], "note": "revised fixture"}', encoding="utf8")
            self.assertEqual(replay_saved_search(root, relative)["status"], "PASS")

    def test_unknown_runtime_returns_structured_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = runtime_snapshot(Path(directory) / "missing-python")
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("FileNotFoundError", result["error"])


if __name__ == "__main__":
    unittest.main()
