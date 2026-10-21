"""Execute resource task planning experiments and retain actual results."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import ResourceGuardError, run_managed

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / 'evals' / 'resource-task-planning-skillopt'
TEST_ARGUMENTS = ['tests.test_resource_task_planning', 'tests.test_resource_guard_parent_memory']


def _static_contract() -> dict[str, Any]:
    """Preflight actual interfaces; scientific behavior is tested by the child suite."""
    import resource_guard
    import resource_task_planner_core as core
    from mcp_server import TOOLS

    design = next(tool for tool in TOOLS if tool['name'] == 'research_design')
    actions = design['inputSchema']['properties'].get('resource_plan_action', {}).get('enum', [])
    inventory = core.inventory_resources(PLUGIN)
    checks = {
        'resource actions are exposed through research_design': {'inventory', 'plan', 'execute', 'record', 'status', 'verify'} <= set(actions),
        'planner lifecycle functions are callable': all(callable(getattr(core, name, None)) for name in ('inventory_resources', 'plan_resource_tasks', 'record_resource_task', 'execute_resource_task', 'resource_task_plan_status', 'verify_resource_task_plan')),
        'managed execution routes are callable': all(callable(getattr(resource_guard, name, None)) for name in ('run_managed', 'run_managed_install', 'run_managed_lean')),
        'actual inventory observes host memory and disk': inventory['memory']['host_total_bytes'] > 0 and inventory['disk']['capacity_bytes'] > 0,
    }
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'scope': 'Actual inventory and callable execution routes; child limits and parent-memory compatibility are tested below.'}



def main() -> int:
    parser = argparse.ArgumentParser(description='Resource task planning')
    parser.add_argument('--rounds', type=int, default=1, help='Number of actual test-suite executions (default: 1)')
    parser.add_argument('--output-root', type=Path, default=EVIDENCE, help='Directory for reports and complete test logs')
    arguments = parser.parse_args()
    if arguments.rounds < 1:
        parser.error('--rounds must be positive')
    evidence = arguments.output_root.expanduser().resolve()
    run_root = evidence / dt.datetime.now(dt.timezone.utc).strftime('run-%Y%m%dT%H%M%S%fZ')
    run_root.mkdir(parents=True)
    command = [sys.executable, '-X', 'utf8', '-m', 'unittest', *TEST_ARGUMENTS, '-v']
    rounds: list[dict[str, Any]] = []
    for index in range(1, arguments.rounds + 1):
        try:
            static = _static_contract()
        except Exception as exc:
            static = {'status': 'FAIL', 'error': f'{type(exc).__name__}: {exc}'}
        try:
            completed = run_managed(command, cwd=PLUGIN, timeout=900)
            stdout, stderr = completed.stdout or '', completed.stderr or ''
            record = {
                'round': index,
                'status': 'PASS' if completed.returncode == 0 and static['status'] == 'PASS' else 'FAIL',
                'static_contract': static,
                'test_returncode': completed.returncode,
                'test_stdout_tail': stdout[-10_000:],
                'test_stderr_tail': stderr[-10_000:],
                'resource_usage': completed.resource_usage,
            }
        except ResourceGuardError as exc:
            stdout, stderr = '', str(exc) + '\n'
            record = {'round': index, 'status': 'FAIL', 'static_contract': static,
                      'test_returncode': None, 'resource_guard_error': str(exc)}
        stdout_path = run_root / f'round-{index:02d}.stdout.log'
        stderr_path = run_root / f'round-{index:02d}.stderr.log'
        stdout_path.write_text(stdout, encoding='utf-8')
        stderr_path.write_text(stderr, encoding='utf-8')
        record.update({'command': command, 'stdout_log': str(stdout_path), 'stderr_log': str(stderr_path)})
        (run_root / f'round-{index:02d}.json').write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
        )
        rounds.append(record)
        if record['status'] != 'PASS':
            break
    report = {
        'schema_version': 2,
        'status': 'PASS' if len(rounds) == arguments.rounds and all(item['status'] == 'PASS' for item in rounds) else 'FAIL',
        'requested_rounds': arguments.rounds,
        'round_count': len(rounds),
        'run_root': str(run_root),
        'evidence_scope': 'Local interface checks and actual regression executions; repeated runs are not independent scientific replication.',
        'rounds': rounds,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    (run_root / 'report.json').write_text(rendered, encoding='utf-8')
    (evidence / 'report.json').write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
