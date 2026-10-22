"""Execute subagent delegation regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'subagent-delegation-skillopt'
TEST_ARGUMENTS = ['tests.test_subagent_delegation']


def main() -> int:
    return run_experiment('Subagent delegation', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=900)


if __name__ == "__main__":
    raise SystemExit(main())
