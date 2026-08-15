from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import sys

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from paper_audit_core import AuditError, plan_paper_audit, run_lean_formula_audit  # noqa: E402


VALID = """import Mathlib
set_option autoImplicit false
-- FORMULA_ID: F1
theorem add_zero_checked (x : ℝ) : x + 0 = x := by
  ring
"""

MANIFEST = {
    "formulas": [{"id": "F1", "source": "Eq. 1", "parameters": ["x"]}],
    "parameters": [{"name": "x", "purpose": "real-valued model input", "used_by": ["F1"]}],
}


class LeanFormulaAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dependency_temp = tempfile.TemporaryDirectory()
        cls.dependency_home = Path(cls.dependency_temp.name) / "dependency-home"
        cls.old_dependency_home = os.environ.get("RESEARCH_GUARD_HOME")
        cls.old_lean_runtime = os.environ.get("RESEARCH_GUARD_LEAN_RUNTIME")
        os.environ["RESEARCH_GUARD_HOME"] = str(cls.dependency_home)
        os.environ["RESEARCH_GUARD_LEAN_RUNTIME"] = str(
            Path.home() / ".research-guard" / "lean-audit-runtime" / "v4.33.0"
        )
        import dependency_manager

        detected = dependency_manager.detect_existing("lean-mathlib")
        cls.assertTrue(
            detected.get("available"),
            "pinned local Lean/Mathlib environment is required for the real compile regression",
        )
        dependency_manager.decide([], ["lean-mathlib"])

    @classmethod
    def tearDownClass(cls):
        if cls.old_dependency_home is None:
            os.environ.pop("RESEARCH_GUARD_HOME", None)
        else:
            os.environ["RESEARCH_GUARD_HOME"] = cls.old_dependency_home
        if cls.old_lean_runtime is None:
            os.environ.pop("RESEARCH_GUARD_LEAN_RUNTIME", None)
        else:
            os.environ["RESEARCH_GUARD_LEAN_RUNTIME"] = cls.old_lean_runtime
        cls.dependency_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        plan_paper_audit(self.root, "Help verify every formula and theorem")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, content=VALID, name="PaperFormulaAudit.lean"):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_real_single_file_lean_compile_passes(self):
        result = run_lean_formula_audit(self.root, str(self.write()), MANIFEST, timeout=360)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["toolchain"], "leanprover/lean4:v4.33.0")

    def test_placeholders_are_rejected_before_compile(self):
        with self.assertRaises(AuditError):
            run_lean_formula_audit(self.root, str(self.write(VALID.replace("by\n  ring", ":= by\n  sorry"))), MANIFEST)

    def test_missing_formula_marker_is_rejected(self):
        bad = {"formulas": MANIFEST["formulas"] + [{"id": "F2", "source": "Eq. 2", "parameters": []}], "parameters": MANIFEST["parameters"]}
        with self.assertRaises(AuditError):
            run_lean_formula_audit(self.root, str(self.write()), bad)

    def test_unused_parameter_is_rejected(self):
        bad = {"formulas": [{"id": "F1", "source": "Eq. 1", "parameters": ["x", "y"]}], "parameters": MANIFEST["parameters"] + [{"name": "y", "purpose": "claimed scale", "used_by": ["F1"]}]}
        with self.assertRaises(AuditError):
            run_lean_formula_audit(self.root, str(self.write()), bad)

    def test_multiple_lean_files_are_rejected(self):
        with self.assertRaises(AuditError):
            run_lean_formula_audit(self.root, [str(self.write()), str(self.write(name="Other.lean"))], MANIFEST)

    def test_confusing_or_illegal_parameter_is_rejected(self):
        bad = {"formulas": [{"id": "F1", "source": "Eq. 1", "parameters": ["O"]}], "parameters": [{"name": "O", "purpose": "ambiguous", "used_by": ["F1"]}]}
        with self.assertRaises(AuditError):
            run_lean_formula_audit(self.root, str(self.write()), bad)


if __name__ == "__main__":
    unittest.main()
