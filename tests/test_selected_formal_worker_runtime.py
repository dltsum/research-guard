"""Explicit receipt fixtures test binding; native installed workers have separate receipts."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from component_runtime import ComponentError, selected_component_python


def save(root, receipt):
    stable = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    receipt["receipt_sha256"] = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    (root / "COMPONENT_INSTALL.json").write_text(json.dumps(receipt), encoding="utf8")


class SelectedFormalWorkerRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.python = self.root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        self.python.parent.mkdir(parents=True)
        self.python.write_bytes(b"explicit interpreter unit fixture, never executed")
        (self.root / ".venv/pyvenv.cfg").write_text("include-system-site-packages = false\n", encoding="utf8")
        self.receipt = {"status": "INSTALLED", "resolved_components": ["core", "formal"],
                        "python_dependency_status": "INSTALLED", "interpreter": str(self.python),
                        "interpreter_sha256": hashlib.sha256(self.python.read_bytes()).hexdigest()}
        save(self.root, self.receipt)

    def tearDown(self):
        self.temp.cleanup()

    def test_bound_private_interpreter_is_returned(self):
        self.assertEqual(selected_component_python("formal", self.root), self.python)

    def test_no_receipt_preserves_legacy_branch(self):
        (self.root / "COMPONENT_INSTALL.json").unlink()
        self.assertIsNone(selected_component_python("formal", self.root))

    def test_missing_dependencies_do_not_fall_back(self):
        self.receipt["python_dependency_status"] = "REQUIRED_NOT_INSTALLED"
        save(self.root, self.receipt)
        with self.assertRaisesRegex(ComponentError, "not INSTALLED"):
            selected_component_python("formal", self.root)

    def test_changed_interpreter_is_rejected(self):
        self.python.write_bytes(b"changed")
        with self.assertRaisesRegex(ComponentError, "SHA256 differs"):
            selected_component_python("formal", self.root)

    def test_external_interpreter_is_rejected_even_when_hash_matches(self):
        external = self.root / "host-python.exe"
        external.write_bytes(self.python.read_bytes())
        self.receipt["interpreter"] = str(external)
        save(self.root, self.receipt)
        with self.assertRaisesRegex(ComponentError, "bound .venv"):
            selected_component_python("formal", self.root)

    def test_unselected_formal_or_tampered_receipt_is_rejected(self):
        self.receipt["resolved_components"] = ["core"]
        save(self.root, self.receipt)
        with self.assertRaisesRegex(ComponentError, "COMPONENT_NOT_INSTALLED"):
            selected_component_python("formal", self.root)
        self.receipt["status"] = "changed-without-updating-digest"
        (self.root / "COMPONENT_INSTALL.json").write_text(json.dumps(self.receipt), encoding="utf8")
        with self.assertRaisesRegex(ComponentError, "COMPONENT_RECEIPT_INVALID"):
            selected_component_python("formal", self.root)

    def test_system_site_packages_cannot_leak_into_bound_worker(self):
        (self.root / ".venv/pyvenv.cfg").write_text("include-system-site-packages = true\n", encoding="utf8")
        with self.assertRaisesRegex(ComponentError, "disable system site-packages"):
            selected_component_python("formal", self.root)


if __name__ == "__main__":
    unittest.main()
