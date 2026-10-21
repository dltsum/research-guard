from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import test_isolated_install as installation


class IsolatedInstallResourceTests(unittest.TestCase):
    def _stage(self, script: str, *, timeout: float = 10, max_memory_bytes: int | None = None):
        return installation._run_stage(
            [sys.executable, "-X", "utf8", "-c", script],
            cwd=PLUGIN, env=dict(os.environ), timeout=timeout,
            max_memory_bytes=max_memory_bytes,
        )

    @unittest.skipIf(installation.psutil is None, "RSS observation needs psutil")
    def test_default_stage_can_use_more_than_the_old_install_profile(self):
        completed, record = self._stage(
            "import time; data=bytearray(460*1024**2); "
            "data[::4096]=b'x'*len(data[::4096]); "
            "print('installation stage completed', flush=True); time.sleep(0.3)"
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("installation stage completed", completed.stdout)
        usage = record["resource_usage"]
        self.assertGreater(usage["peak_worker_bytes"], 448 * 1024 ** 2)
        self.assertIsNone(usage["memory_limit_bytes"])
        self.assertEqual(usage["memory_limit_source"], "none")

    @unittest.skipIf(installation.psutil is None, "explicit RSS limits need psutil")
    def test_an_explicit_small_memory_limit_still_terminates_the_stage(self):
        started = time.monotonic()
        with self.assertRaisesRegex(installation.IsolatedInstallError, "explicit user memory budget") as caught:
            self._stage(
                "import time; data=bytearray(96*1024**2); "
                "data[::4096]=b'x'*len(data[::4096]); time.sleep(20)",
                max_memory_bytes=64 * 1024 ** 2,
            )
        self.assertLess(time.monotonic() - started, 10)
        usage = caught.exception.stage_record["resource_usage"]
        self.assertEqual(usage["memory_limit_bytes"], 64 * 1024 ** 2)
        self.assertEqual(usage["memory_limit_source"], "user")
        self.assertGreater(usage["peak_worker_bytes"], usage["memory_limit_bytes"])

    @unittest.skipIf(installation.psutil is None, "explicit RSS limits need psutil")
    def test_explicit_limits_are_not_clamped_to_the_old_profile(self):
        _, record = self._stage("print('small actual command')", max_memory_bytes=1024 ** 3)
        self.assertEqual(record["resource_usage"]["memory_limit_bytes"], 1024 ** 3)

    def test_actual_command_failure_and_stderr_are_preserved(self):
        with self.assertRaisesRegex(installation.IsolatedInstallError, "exit code 7") as caught:
            self._stage("import sys; print('actual dependency failure', file=sys.stderr); sys.exit(7)")
        self.assertEqual(caught.exception.stage_record["returncode"], 7)
        self.assertIn("actual dependency failure", caught.exception.stage_record["stderr_tail"])

    def test_stage_timeout_terminates_its_child_process_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            pid_path = Path(temporary) / "child.pid"
            child = (
                "from pathlib import Path; import os,time; "
                f"Path({str(pid_path)!r}).write_text(str(os.getpid())); time.sleep(30)"
            )
            parent = (
                "import subprocess,sys,time; "
                f"subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
            )
            started = time.monotonic()
            with self.assertRaisesRegex(installation.IsolatedInstallError, "stage timeout"):
                self._stage(parent, timeout=2)
            self.assertLess(time.monotonic() - started, 10)
            self.assertTrue(pid_path.is_file(), "the test must start an actual descendant before cancellation")
            if installation.psutil is not None:
                pid = int(pid_path.read_text())
                for _ in range(30):
                    try:
                        process = installation.psutil.Process(pid)
                        if not process.is_running() or process.status() == installation.psutil.STATUS_ZOMBIE:
                            break
                    except installation.psutil.NoSuchProcess:
                        break
                    time.sleep(0.1)
                else:
                    self.fail("the installation descendant survived cancellation")

    def test_default_stage_works_without_optional_telemetry_package(self):
        script = (
            "import json,os,sys; from pathlib import Path; "
            f"sys.path.insert(0,{str(PLUGIN / 'scripts')!r}); "
            "import test_isolated_install as installation; "
            "assert installation.psutil is None; "
            "completed,record=installation._run_stage("
            "[sys.executable,'-S','-c',\"print('no telemetry dependency')\"],"
            f"cwd=Path({str(PLUGIN)!r}),env=dict(os.environ),timeout=5); "
            "print(json.dumps(record))"
        )
        actual = subprocess.run(
            [sys.executable, "-S", "-X", "utf8", "-c", script],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(actual.returncode, 0, actual.stderr)
        record = json.loads(actual.stdout)
        self.assertIsNone(record["resource_usage"]["peak_worker_bytes"])
        self.assertFalse(record["resource_usage"]["memory_observation_available"])


if __name__ == "__main__":
    unittest.main()
