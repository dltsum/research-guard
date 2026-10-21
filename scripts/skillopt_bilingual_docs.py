"""Execute bilingual documentation health experiments and retain actual results."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import ResourceGuardError, run_managed

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / 'evals' / 'bilingual-documentation-skillopt'
TEST_ARGUMENTS = ['tests.test_documentation_parity', 'tests.test_p10_cycle_e_public_package', 'tests.test_p29_preset_audit']


def _static_contract() -> dict[str, Any]:
    """Preflight actual interfaces; scientific behavior is tested by the child suite."""
    import tempfile
    from documentation_parity import validate_documentation

    documentation = validate_documentation(PLUGIN)
    with tempfile.TemporaryDirectory(prefix='research-guard-doc-health-') as temporary:
        root = Path(temporary)
        (root / 'assets').mkdir()
        (root / 'assets/documentation-parity.json').write_text(json.dumps({'pairs': [
            {'id': 'sample', 'source_path': 'README.md', 'translation_path': 'README.zh-CN.md'},
        ]}), encoding='utf-8')
        source = root / 'README.md'
        source.write_text('# Example\nAn editable document.\n', encoding='utf-8')
        (root / 'README.zh-CN.md').write_text('# 示例\n可修改的文档。\n', encoding='utf-8')
        before = validate_documentation(root)
        source.write_text('# Updated example\nThe normal edit remains readable.\n', encoding='utf-8')
        after = validate_documentation(root)
    checks = {
        'declared documentation files are readable': documentation['status'] == 'PASS',
        'an ordinary source edit remains usable without resealing': before['status'] == after['status'] == 'PASS',
        'the edit check read both sample documents': after['pair_count'] == 1,
    }
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'documentation_report': documentation,
            'scope': 'File readability and a real local edit; translation quality still requires a human reader.'}



def main() -> int:
    parser = argparse.ArgumentParser(description='Bilingual documentation health')
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
