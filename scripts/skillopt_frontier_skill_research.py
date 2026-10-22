"""Execute frontier skill research regressions once unless repeats are requested."""
from __future__ import annotations

from pathlib import Path

from skillopt_runner import run_experiment

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / "evals" / 'p24-frontier-skillopt'
TEST_ARGUMENTS = ['tests.test_p24_frontier_skill_research', 'tests.test_p10_cycle_b_domain_graph_evolution']


def main() -> int:
    return run_experiment('Frontier Skill research', TEST_ARGUMENTS, output_root=EVIDENCE, timeout=600)


if __name__ == "__main__":
    raise SystemExit(main())
