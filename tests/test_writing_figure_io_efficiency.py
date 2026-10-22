"""Execute real workflows while counting forwarded file/image reads.

The fixture reviews are explicitly synthetic. IO instrumentation only observes
the real file readers; it never supplies replacement contents or outcomes.
"""
from __future__ import annotations

import collections
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from PIL import Image
import academic_figure_core as figures
import ai_reviewer_robustness_core as reviewers
import math_verification_worker as math_worker
import paper_audit_core as paper
import reference_writing_core as writing
import test_reference_figure_contract as figure_fixtures
import test_reference_writing_contract as writing_fixtures
from test_p13_cycle_a_cross_verification import manifest


class WritingFigureIOEfficiencyTests(unittest.TestCase):
    def evidence(self, name, result):
        directory = os.environ.get('RESEARCH_GUARD_IO_EVIDENCE_DIR')
        if directory:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            (path / (name + '.json')).write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf-8')

    def fixture(self, kind):
        case = kind('runTest')
        case.setUp()
        self.addCleanup(case.tearDown)
        return case

    def count_opens(self, counts):
        original = Path.open

        def observed(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get('mode', 'r')
            if 'r' in mode:
                # io_path uses Windows' extended-length alias for the same
                # on-disk file. Normalize that alias only in the observer.
                key = str(path.resolve())
                if key.startswith('\\\\?\\UNC\\'):
                    key = '\\\\' + key[8:]
                elif key.startswith('\\\\?\\'):
                    key = key[4:]
                counts[key] += 1
            return original(path, *args, **kwargs)

        return patch.object(Path, 'open', observed)

    def test_tracking_source_links_uses_stat_without_reading_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'measurements.csv'
            source.write_text('x,y\n0,1\n', 'utf-8')
            counts = collections.Counter()
            with self.count_opens(counts):
                figure_records = figures._tracked_sources(root, [source.name])
                paper_records = paper._tracked_files(root, [source.name], 'data')
            self.assertEqual(counts[str(source.resolve())], 0)
            self.assertEqual(figure_records[0]['bytes'], source.stat().st_size)
            self.assertEqual(figure_records[0]['path'], source.name)
            self.assertTrue(paper_records)
            self.evidence('source-links', {'source_opens': 0, 'figure': figure_records, 'paper': paper_records})

    def test_ai_reviewer_reads_manuscript_once_for_actual_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'paper.md'
            text = '# Method\nThe observed value is 13.1%.\n'
            source.write_text(text, 'utf-8')
            counts = collections.Counter()
            with self.count_opens(counts):
                records, contents = reviewers._read_manuscripts(root, [source.name])
            self.assertEqual(counts[str(source.resolve())], 1)
            self.assertIn(text, contents)
            self.assertTrue(records)
            self.evidence('review-manuscript', {'source_opens': 1, 'records': records, 'actual_text_present': True})

    def test_writing_audit_loads_state_once_and_preserves_three_roles(self):
        case = self.fixture(writing_fixtures.ReferenceWritingContractTests)
        case.submit()
        reviews = case.reviews()
        state_file = writing._path(case.root, 'synthetic-writing').resolve()
        counts = collections.Counter()
        with self.count_opens(counts):
            result = writing.audit_reference_writing(case.root, 'synthetic-writing', reviews)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(len(result['reviews']), 3)
        self.assertEqual(counts[str(state_file)], 1)
        self.evidence('writing-audit', {'state_reads': 1, 'status': result['status'], 'roles': [row['role'] for row in result['reviews']], 'review_scope': 'synthetic unit fixtures'})

    def test_reference_audit_reuses_candidate_decode_and_component_mapping(self):
        case = self.fixture(figure_fixtures.ReferenceFigureContractTests)
        bundle = case.bundle()
        counts = collections.Counter()
        image_reads = collections.Counter()
        original = Image.open

        def observed_image(path, *args, **kwargs):
            image_reads[str(Path(path).resolve())] += 1
            return original(path, *args, **kwargs)

        with self.count_opens(counts), patch.object(Image, 'open', observed_image):
            result = figures.audit_reference_figure(case.root, 'toy', bundle)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(image_reads[str((case.root / 'candidate.png').resolve())], 1)
        self.assertEqual(counts[str((case.root / 'component-audit.json').resolve())], 1)
        self.assertEqual(result['outputs'][0]['rounds'], 2)
        self.evidence('reference-image-audit', {'candidate_decodes': 1, 'component_audit_reads': 1, 'status': result['status'], 'three_role_rounds': 2, 'pixel_metrics_and_native_crops_checked': True, 'review_scope': 'synthetic unit fixtures'})

    def test_numerical_model_is_read_once_and_reexecuted_after_edit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'model.py'
            source.write_text("def evaluate(parameters):\n    return float(parameters['x'])\n", 'utf-8')
            request = manifest('legacy metadata ignored')
            counts = collections.Counter()
            with self.count_opens(counts):
                first = math_worker._numerical(request, root)
            self.assertEqual(first['status'], 'PASS')
            self.assertEqual(counts[str(source.resolve())], 1)
            source.write_text("def evaluate(parameters):\n    return float(parameters['x']) + 1\n", 'utf-8')
            counts.clear()
            with self.count_opens(counts):
                edited = math_worker._numerical(request, root)
            self.assertEqual(edited['status'], 'FAIL')
            self.assertEqual(edited['checks'][0]['values'], [1.0])
            self.assertEqual(counts[str(source.resolve())], 1)
            self.evidence('numerical-source', {'reads_per_execution': 1, 'first_status': first['status'], 'edited_status': edited['status'], 'edited_actual_value': edited['checks'][0]['values']})
