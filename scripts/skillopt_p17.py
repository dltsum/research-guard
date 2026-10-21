"""Execute writing, ai review and figure quality experiments and retain actual results."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from resource_guard import ResourceGuardError, run_managed

PLUGIN = Path(__file__).resolve().parents[1]
EVIDENCE = PLUGIN / 'evals' / 'p17-skillopt'
TEST_ARGUMENTS = ['discover', '-s', 'tests', '-p', 'test_p17_*.py']


def _static_contract() -> dict[str, Any]:
    """Preflight actual interfaces; scientific behavior is tested by the child suite."""
    import academic_figure_core as figures
    import ai_reviewer_robustness_core as reviews
    import paper_audit_core as papers
    from mcp_server import TOOLS

    paper = next(tool for tool in TOOLS if tool['name'] == 'paper_audit')
    properties = paper['inputSchema']['properties']
    checks = {
        'AI robustness review is exposed through paper_audit': 'ai_robustness' in properties.get('review_action', {}).get('enum', []),
        'figure generation and audit actions are exposed': {'plan', 'render', 'audit', 'visual_review', 'status', 'verify'} <= set(properties.get('figure_action', {}).get('enum', [])),
        'figure generation and audit implementations are callable': all(callable(getattr(figures, name, None)) for name in ('plan_academic_figure', 'render_academic_figure', 'audit_academic_figure', 'record_visual_review', 'verify_academic_figure')),
        'AI review and paper audit implementations are callable': callable(reviews.audit_ai_reviewer_robustness) and callable(papers.plan_paper_audit),
    }
    return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
            'scope': 'Callable review and figure routes; actual reviewer and rendering behavior is exercised by the test suite.'}



def main() -> int:
    parser = argparse.ArgumentParser(description='Writing, AI review and figure quality')
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
