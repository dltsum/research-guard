"""A selected experiment component must include the schema linked by its skill."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from component_install import install_components, verify_installation


class ExperimentDirectionReferencePackagingTests(unittest.TestCase):
    def test_minimal_install_resolves_executable_direction_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "experiments"
            result = install_components(ROOT, target, ["experiments"])
            self.assertEqual(result["resolved_components"],
                             ["core", "literature", "research", "experiments"])
            reference = target / "skills/research-design-guard/references/direction-exploration-contract.md"
            link = "../../../docs/DIRECTION_EXPLORATION.md"
            self.assertIn(link, reference.read_text(encoding="utf8"))
            schema = (reference.parent / link).resolve()
            self.assertTrue(schema.is_file(), "Enabled direction routes need their linked executable schema")
            self.assertEqual(schema.read_bytes(), (ROOT / "docs/DIRECTION_EXPLORATION.md").read_bytes())
            self.assertFalse((target / "skills/academic-language-guard").exists())
            self.assertFalse((target / "skills/academic-figure-guard").exists())
            self.assertEqual(verify_installation(target)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
