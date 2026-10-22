"""Observable I/O and execution counts for the simplified operational paths."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from evidence_kernel import EvidenceRecorder
from reproduction_helpers import replay_saved_search
from research_guard_core import register_method
import research_integrity_core as integrity
import discipline_profile_core as discipline


class RedundancyOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        register_method(self.root, {'title': 'Local pilot', 'problem': 'Measure overhead',
                                    'mechanism': 'Execute once and preserve actual outputs'})

    def tearDown(self):
        self.temporary.cleanup()

    def observe(self, target, action):
        actual_open = Path.open
        modes = []
        def observed_open(path, mode='r', *args, **kwargs):
            if path == target or (path.exists() and path.samefile(target)):
                modes.append(mode)
            return actual_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', observed_open):
            result = action()
        return result, modes

    def test_document_is_parsed_once_without_binary_digest_read(self):
        source = self.root / 'paper.md'
        source.write_text('# Pilot\n\nFour seeds were measured.\n', encoding='utf8')
        result, modes = self.observe(source, lambda: integrity.ingest_document(self.root, 'paper.md', 'pilot'))
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(modes, ['r'])
        self.assertIn('Four seeds', str(result['parsed']['blocks']))

    def test_resume_loads_manifest_once_and_continues_attempt_numbers(self):
        recorder = EvidenceRecorder(self.root, 'resume')
        first = recorder.record_fixture(source='crossref', query_id='q1', query='pilot', payload={'items': []})
        relative, _ = recorder.finalize(method_version=1, method_hash='local', query_plan_hash='plan', query_runs=[])
        resumed, modes = self.observe(self.root / relative, lambda: EvidenceRecorder(self.root, 'resume', resume=True))
        second = resumed.record_fixture(source='crossref', query_id='q1', query='pilot', payload={'items': [1]})
        self.assertEqual(modes, ['r'])
        self.assertNotEqual(first['attempt_id'], second['attempt_id'])
        self.assertEqual(len(resumed.attempts), 2)
        self.assertNotEqual(first['raw_path'], second['raw_path'])
        self.assertTrue((self.root / first['raw_path']).is_file())

    def test_saved_replay_loads_manifest_once(self):
        recorder = EvidenceRecorder(self.root, 'replay')
        recorder.record_fixture(source='crossref', query_id='q1', query='pilot', payload={'items': []})
        relative, _ = recorder.finalize(method_version=1, method_hash='local', query_plan_hash='plan', query_runs=[])
        result, modes = self.observe(self.root / relative, lambda: replay_saved_search(self.root, relative))
        self.assertEqual(modes, ['r'])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['scientific_status'], 'HISTORICAL_EVIDENCE_ONLY')

    def test_reusing_run_id_preserves_earlier_raw_response_without_hashing(self):
        first = EvidenceRecorder(self.root, 'same-run').record_fixture(
            source='crossref', query_id='q1', query='pilot', payload={'items': [1]})
        second = EvidenceRecorder(self.root, 'same-run').record_fixture(
            source='crossref', query_id='q1', query='pilot', payload={'items': [2]})
        self.assertNotEqual(first['raw_path'], second['raw_path'])
        self.assertEqual(json.loads((self.root / first['raw_path']).read_text())['items'], [1])
        self.assertEqual(json.loads((self.root / second['raw_path']).read_text())['items'], [2])

    def test_actual_reproduction_executes_once_and_evaluates_outputs_once(self):
        source = self.root / 'input.txt'
        source.write_text('measured pilot', encoding='utf8')
        code = "from pathlib import Path; Path('output.txt').write_text(Path('input.txt').read_text()); p=Path('count.txt'); p.write_text(p.read_text()+'x' if p.exists() else 'x')"
        plan = {'command': [sys.executable, '-c', code], 'inputs': ['input.txt'], 'outputs': ['output.txt']}
        real_open = Path.open
        binary_reads = []
        def observed_open(path, mode='r', *args, **kwargs):
            if 'b' in mode and ('r' in mode or '+' in mode):
                binary_reads.append(str(path))
            return real_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', observed_open), patch.object(integrity, '_evaluate_expected_checks', wraps=integrity._evaluate_expected_checks) as checks:
            integrity.register_reproducibility_plan(self.root, 'one-run', plan)
            result = integrity.execute_reproducibility(self.root, 'one-run', timeout=20)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual((self.root / 'count.txt').read_text(), 'x')
        self.assertEqual((self.root / 'output.txt').read_text(), 'measured pilot')
        self.assertEqual(checks.call_count, 1)
        self.assertEqual(binary_reads, [])

    def test_profile_status_reads_history_without_implicit_source_validation(self):
        path = discipline._profile_path(self.root, 'local-pilot')
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'schema_version': 1, 'profile_id': 'local-pilot',
            'label': 'Local pilot fixture', 'status': 'PASS', 'profile_hash': 'record-id',
            'initialized_at': '2026-10-22', 'source_runs': [{'evidence_path': 'missing-source.json'}]}), encoding='utf8')
        recorded = discipline.discipline_status(self.root, discipline='local-pilot')
        current = discipline.discipline_status(self.root, discipline='local-pilot', verify=True)
        self.assertEqual(recorded['profiles'][0]['status'], 'PASS')
        self.assertEqual(current['status'], 'INVALID')
        self.assertIn('missing-source.json', current['profiles'][0]['error'])


if __name__ == '__main__':
    unittest.main()
