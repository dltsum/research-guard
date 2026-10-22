"""Execute active ai reviewer adaptation regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'p18-skillopt'
TEST_ARGUMENTS = ['discover', '-s', 'tests', '-p', 'test_p18_*.py']


def main() -> int:
    return run_experiment('Active AI reviewer adaptation', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=900)


if __name__ == "__main__":
    raise SystemExit(main())
