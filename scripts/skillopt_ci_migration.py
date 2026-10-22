"""Execute ci migration and component installation regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'p21-ci-migration-skillopt'
TEST_ARGUMENTS = ['tests.test_p21_ci_migration_assurance', 'tests.test_cross_platform', 'tests.test_p10_cycle_e_public_package', 'tests.test_p11_resource_and_selection']


def main() -> int:
    return run_experiment('CI migration and component installation', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=900)


if __name__ == "__main__":
    raise SystemExit(main())
