"""Execute writing, ai review and figure quality regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'p17-skillopt'
TEST_ARGUMENTS = ['discover', '-s', 'tests', '-p', 'test_p17_*.py']


def main() -> int:
    return run_experiment('Writing, AI review and figure quality', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=900)


if __name__ == "__main__":
    raise SystemExit(main())
