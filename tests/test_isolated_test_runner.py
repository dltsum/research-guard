"""Runner fixtures are tiny unittest files, not scientific or environment evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_isolated_tests import run_modules


class IsolatedRunnerTests(unittest.TestCase):
    def test_serial_modules_preserve_real_child_failures_and_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_a.py").write_text("import unittest\nclass A(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n @unittest.skip('explicit fixture')\n def test_skip(self): pass\n", encoding="utf8")
            (tests / "test_b.py").write_text("import unittest\nclass B(unittest.TestCase):\n def test_fail(self): self.assertTrue(False)\n", encoding="utf8")
            result = run_modules(tests, root / "logs")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["counts"], {"tests": 3, "failures": 1, "errors": 0, "skipped": 1})
            self.assertEqual([item["status"] for item in result["modules"]], ["PASS", "FAIL"])
            for module in result["modules"]:
                self.assertTrue(Path(module["stderr_file"]).is_file())
                self.assertEqual(module["command"][-2:], [module["module"], "-v"])
            self.assertEqual(json.loads((root / "logs/isolated-suite.json").read_text())["status"], "FAIL")

    def test_no_matches_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No test modules matched"):
                run_modules(Path(directory), Path(directory) / "out")


if __name__ == "__main__":
    unittest.main()
