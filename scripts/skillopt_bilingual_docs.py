"""Execute bilingual documentation health regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'bilingual-documentation-skillopt'
TEST_ARGUMENTS = ['tests.test_documentation_parity', 'tests.test_p10_cycle_e_public_package', 'tests.test_p29_preset_audit']


def main() -> int:
    return run_experiment('Bilingual documentation health', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=900)


if __name__ == "__main__":
    raise SystemExit(main())
