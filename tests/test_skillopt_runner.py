from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

from skillopt_runner import run_regression


class SkillOptRunnerTests(unittest.TestCase):
    def _entry(self, root: Path) -> tuple[Path, Path]:
        tests = root / "cases"
        tests.mkdir()
        counter = root / "actual-executions.txt"
        (tests / "test_count.py").write_text(
            "import unittest\nfrom pathlib import Path\n"
            "class CounterTest(unittest.TestCase):\n"
            "    def test_record_actual_execution(self):\n"
            f"        path=Path({str(counter)!r})\n"
            "        with path.open('a',encoding='utf-8') as output: output.write('executed\\n')\n",
            encoding="utf-8",
        )
        entry = root / "entry.py"
        entry.write_text(
            "import sys\nfrom pathlib import Path\n"
            f"sys.path.insert(0,{str(PLUGIN / 'scripts')!r})\n"
            "from skillopt_runner import run_experiment\n"
            f"raise SystemExit(run_experiment('actual execution counter',['discover','-s',{str(tests)!r}],output_root=Path({str(root / 'evidence')!r})))\n",
            encoding="utf-8",
        )
        return entry, counter

    def test_default_runs_once_and_only_explicit_repeats_run_again(self):
        with tempfile.TemporaryDirectory() as temporary:
            entry, counter = self._entry(Path(temporary))
            for extra, expected, total in (([], 1, 1), (["--rounds", "2"], 2, 3)):
                actual = subprocess.run(
                    [sys.executable, "-X", "utf8", str(entry), *extra],
                    capture_output=True, text=True, encoding="utf-8", timeout=30,
                )
                self.assertEqual(actual.returncode, 0, actual.stderr)
                report = json.loads(actual.stdout)
                self.assertEqual(report["round_count"], expected)
                self.assertEqual([item["test_count"] for item in report["rounds"]], [1] * expected)
                self.assertEqual(len(counter.read_text(encoding="utf-8").splitlines()), total)

    def test_invalid_repeat_count_does_not_launch_a_suite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entry, counter = self._entry(root)
            actual = subprocess.run(
                [sys.executable, str(entry), "--rounds", "0"],
                capture_output=True, text=True, encoding="utf-8", timeout=10,
            )
            self.assertEqual(actual.returncode, 2)
            self.assertFalse(counter.exists())
            self.assertFalse((root / "evidence").exists())

    def test_no_discovered_tests_cannot_be_reported_as_a_validated_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = root / "cases"
            cases.mkdir()
            record = run_regression(
                ["discover", "-s", str(cases)], cwd=PLUGIN,
                run_root=root, prefix="empty-suite",
            )
            # Recent unittest versions return 5 for no tests; older ones return 0.
            self.assertIn(record["returncode"], (0, 5))
            self.assertEqual(record["test_count"], 0)
            self.assertEqual(record["status"], "FAIL")

    def test_real_test_failure_and_its_output_are_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = root / "cases"
            cases.mkdir()
            (cases / "test_failure.py").write_text(
                "import unittest\nclass FailureTest(unittest.TestCase):\n"
                "    def test_actual_failure(self): self.fail('actual failure retained')\n",
                encoding="utf-8",
            )
            record = run_regression(
                ["discover", "-s", str(cases)], cwd=PLUGIN,
                run_root=root, prefix="failed-suite",
            )
            self.assertEqual(record["returncode"], 1)
            self.assertEqual(record["status"], "FAIL")
            self.assertEqual(record["test_count"], 1)
            self.assertIn("actual failure retained", Path(record["stderr_log"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
