"""Explicit receipt fixtures test binding; native installed workers have separate receipts."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from component_runtime import ComponentError, selected_component_python


def save(root, receipt):
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
                        "python_dependency_status": "INSTALLED", "interpreter": str(self.python)}
        save(self.root, self.receipt)

    def tearDown(self):
        self.temp.cleanup()

    def test_bound_private_interpreter_is_returned(self):
        self.assertEqual(selected_component_python("formal", self.root), self.python)

    def test_no_receipt_preserves_legacy_branch(self):
        (self.root / "COMPONENT_INSTALL.json").unlink()
        self.assertIsNone(selected_component_python("formal", self.root))

    def test_dependency_status_does_not_gate_actual_worker_imports(self):
        self.receipt["python_dependency_status"] = "REQUIRED_NOT_INSTALLED"
        save(self.root, self.receipt)
        self.assertEqual(selected_component_python("formal", self.root),self.python)

    def test_interpreter_update_does_not_require_reinstallation(self):
        self.python.write_bytes(b"changed")
        self.assertEqual(selected_component_python("formal", self.root),self.python)

    def test_configured_existing_python_is_supported(self):
        external = self.root / "host-python.exe"
        external.write_bytes(self.python.read_bytes())
        self.receipt["interpreter"] = str(external)
        save(self.root, self.receipt)
        self.assertEqual(selected_component_python("formal", self.root),external)

    def test_unselected_component_is_rejected_without_digest_gate(self):
        self.receipt["resolved_components"] = ["core"]
        save(self.root, self.receipt)
        with self.assertRaisesRegex(ComponentError, "COMPONENT_NOT_INSTALLED"):
            selected_component_python("formal", self.root)
        self.receipt["resolved_components"]=['core','formal']
        self.receipt["receipt_sha256"] = "obsolete field ignored"
        (self.root / "COMPONENT_INSTALL.json").write_text(json.dumps(self.receipt), encoding="utf8")
        self.assertEqual(selected_component_python("formal", self.root),self.python)

    def test_existing_environment_configuration_is_not_reaudited_per_call(self):
        (self.root / ".venv/pyvenv.cfg").write_text("include-system-site-packages = true\n", encoding="utf8")
        self.assertEqual(selected_component_python("formal", self.root),self.python)

    def test_missing_interpreter_still_reports_an_actionable_error(self):
        self.python.unlink()
        with self.assertRaisesRegex(ComponentError,'executable is missing'):
            selected_component_python('formal',self.root)


if __name__ == "__main__":
    unittest.main()
