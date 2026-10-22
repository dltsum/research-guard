"""Execute instruction adherence and constructive numerical verification regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'instruction-numerical-skillopt'
TEST_ARGUMENTS = ['discover', '-s', 'tests', '-p', 'test_p22_*.py']


def main() -> int:
    return run_experiment('Instruction adherence and constructive numerical verification', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=600)


if __name__ == "__main__":
    raise SystemExit(main())
