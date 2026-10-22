"""Execute direction exploration regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'direction-exploration-skillopt'
TEST_ARGUMENTS = ['tests.test_direction_exploration']


def main() -> int:
    return run_experiment('Direction exploration', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=300)


if __name__ == "__main__":
    raise SystemExit(main())
