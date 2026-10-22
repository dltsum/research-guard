"""Execute resource task planning regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'resource-task-planning-skillopt'
TEST_ARGUMENTS = ['tests.test_resource_task_planning', 'tests.test_resource_guard_parent_memory']


def main() -> int:
    return run_experiment('Resource task planning', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=900)


if __name__ == "__main__":
    raise SystemExit(main())
