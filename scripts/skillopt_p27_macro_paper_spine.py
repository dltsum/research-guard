"""Execute macro paper spine regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'p27-macro-paper-spine'
TEST_ARGUMENTS = ['tests.test_p27_macro_paper_spine']


def main() -> int:
    return run_experiment('Macro paper spine', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=300)


if __name__ == "__main__":
    raise SystemExit(main())
