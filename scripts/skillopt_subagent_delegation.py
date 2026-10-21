"""Execute subagent delegation experiments and retain actual results."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import ResourceGuardError, run_managed

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / 'evals' / 'subagent-delegation-skillopt'
TEST_ARGUMENTS = ['tests.test_subagent_delegation']


def _static_contract() -> dict[str, Any]:
    """Preflight actual interfaces; scientific behavior is tested by the child suite."""
    import llm_delegation_core as core
    from mcp_server import TOOLS

    design = next(tool for tool in TOOLS if tool['name'] == 'research_design')
    actions = design['inputSchema']['properties'].get('delegation_action', {}).get('enum', [])
    policy = json.loads((PLUGIN / 'assets/llm-delegation-policy.json').read_text(encoding='utf-8'))
    checks = {
        'delegation lifecycle is exposed through research_design': {'plan', 'submit', 'status', 'verify'} <= set(actions),
        'delegation lifecycle implementations are callable': all(callable(getattr(core, name, None)) for name in ('plan_llm_assistance', 'submit_llm_assistance', 'llm_assistance_status', 'verify_llm_assistance')),
        'the configured default uses a native subagent': policy.get('default_execution_mode') == 'native_subagent',
        'external provider use is explicit': policy.get('external_api_default_allowed') is False,
    }
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'scope': 'Interface and provider defaults; tests exercise submission, local edits, and safe paths. This script does not itself launch a native subagent.'}



def main() -> int:
    parser = argparse.ArgumentParser(description='Subagent delegation')
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
