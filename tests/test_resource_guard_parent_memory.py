"""Exercise real parent RSS, child memory enforcement and timeout behavior."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import resource_guard as guard


class ParentMemoryRegressionTests(unittest.TestCase):
    def test_large_shared_parent_can_run_standard_install_and_lean_children(self):
        # Allocate and touch real resident pages in a separate parent, avoiding
        # a permanent 160 MiB allocation in the rest of the test suite.
        code = f"""
import json, sys
sys.path.insert(0, {str(SCRIPTS)!r})
import resource_guard as guard
resident = bytearray(b'x') * (160 * guard.MIB)
before = guard.current_process_working_set_bytes()
assert before > 128 * guard.MIB, before
assert guard.require_orchestrator_budget(1) > 128 * guard.MIB
command = [sys.executable, '-c', "import time; print('actual-child'); time.sleep(0.08)"]
results = []
for label, runner in [('standard', guard.run_managed), ('install', guard.run_managed_install), ('lean', guard.run_managed_lean)]:
    completed = runner(command, timeout=10)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == 'actual-child', completed.stdout
    usage = completed.resource_usage
    assert usage['orchestrator_limit_enforced'] is False
    assert usage['owned_process_scope'] == 'spawned_process_tree'
    assert usage['peak_owned_bytes'] == usage['peak_worker_bytes']
    results.append({{'profile': label, 'returncode': completed.returncode, 'usage': usage}})
print(json.dumps({{'parent_rss_before_bytes': before, 'old_parent_limit_bytes': 128 * guard.MIB, 'results': results}}))
"""
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", code],
            text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=45,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertGreater(result["parent_rss_before_bytes"], 128 * guard.MIB)
        self.assertEqual(len(result["results"]), 3)
        print("PARENT_RSS_PROBE=" + json.dumps(result, sort_keys=True))

    def test_large_parent_can_finalize_reproduction_and_resource_plan(self):
        # The existing lifecycle test writes real inputs, starts its real
        # managed command and validates both resulting resource records.
        code = f"""
import json, sys
sys.path.insert(0, {str(SCRIPTS.parent / 'tests')!r})
from test_resource_task_planning import ResourceTaskPlanningTests
import resource_guard as guard
resident = bytearray(b'x') * (160 * guard.MIB)
before = guard.current_process_working_set_bytes()
assert before > 128 * guard.MIB, before
case = ResourceTaskPlanningTests('test_round_5_linked_reproducibility_executes_and_records_guard_telemetry')
case.debug()
print(json.dumps({{'parent_rss_before_bytes': before, 'managed_reproduction_and_plan': 'PASS'}}))
"""
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", code],
            text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=45,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertGreater(result["parent_rss_before_bytes"], 128 * guard.MIB)
        self.assertEqual(result["managed_reproduction_and_plan"], "PASS")
        print("MANAGED_RESULT_PROBE=" + json.dumps(result, sort_keys=True))

    def test_actual_child_memory_limit_remains_enforced(self):
        with self.assertRaisesRegex(guard.ResourceGuardError, "RESOURCE_WORKING_SET_ABORT"):
            guard.run_managed(
                [sys.executable, "-c", "import time; resident=bytearray(b'x')*(96*1024**2); time.sleep(10)"],
                timeout=15, maximum_job_bytes=64 * guard.MIB,
            )

    def test_actual_child_timeout_remains_enforced(self):
        with self.assertRaisesRegex(guard.ResourceGuardError, "RESOURCE_TASK_TIMEOUT:"):
            guard.run_managed(
                [sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1,
            )


if __name__ == "__main__":
    unittest.main()
