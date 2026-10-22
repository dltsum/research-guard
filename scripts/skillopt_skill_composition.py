"""Execute skill composition regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'p26-skill-composition-skillopt'
TEST_ARGUMENTS = ['tests.test_p26_skill_composition', 'tests.test_p25_skill_portability', 'tests.test_p24_frontier_skill_research', 'tests.test_p10_cycle_d_router_mcp']


def main() -> int:
    return run_experiment('Skill composition', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=900)


if __name__ == "__main__":
    raise SystemExit(main())
