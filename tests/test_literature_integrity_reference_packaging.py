"""Literature-only users must receive the instructions for their enabled routes."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from component_install import install_components, verify_installation


class LiteratureIntegrityReferencePackagingTests(unittest.TestCase):
    def test_minimal_install_has_discoverable_integrity_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "literature"
            result = install_components(ROOT, target, ["literature"])
            self.assertEqual(result["resolved_components"], ["core", "literature"])
            relative = "skills/paper-audit-guard/references/research-integrity-contracts.md"
            reference = target / relative
            self.assertTrue(reference.is_file(), "Enabled literature integrity routes need their reference")
            self.assertEqual(reference.read_bytes(), (ROOT / relative).read_bytes())
            entry = (target / "skills/research-novelty-guard/SKILL.md").read_text(encoding="utf8")
            self.assertIn("../paper-audit-guard/references/research-integrity-contracts.md", entry)
            self.assertIn('"integrity_action":"status"', reference.read_text(encoding="utf8"))
            self.assertFalse((target / "skills/paper-audit-guard/SKILL.md").exists())
            self.assertFalse((target / "skills/academic-language-guard").exists())
            self.assertEqual(verify_installation(target)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
