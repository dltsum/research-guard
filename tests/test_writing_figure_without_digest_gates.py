"""Real file behavior for writing/figure workflows without digest handshakes.

Generated qualification and reviewer objects are explicitly synthetic fixtures;
their execution tests workflow behavior, not scholarly or native agent quality.
"""
from __future__ import annotations

import copy
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

import academic_figure_core as figures
import ai_reviewer_robustness_core as reviewers
import language_guard_core as language
import math_verification_worker as math_worker
import paper_audit_core as paper
import paper_spine_core as spine
import reference_writing_core as writing
from test_reference_writing_contract import ReferenceWritingContractTests as WritingFixture
from test_reference_figure_contract import ReferenceFigureContractTests as FigureFixture
from test_p13_cycle_a_cross_verification import manifest
from test_p27_macro_paper_spine import MacroPaperSpineTests as SpineFixture


class WorkflowWithoutDigestGatesTests(unittest.TestCase):
    def fixture(self, kind):
        case = kind('runTest')
        case.setUp()
        self.addCleanup(case.tearDown)
        return case

    def test_general_paper_audit_does_not_require_role_selection_ceremony(self):
        with tempfile.TemporaryDirectory() as temporary:
            default = paper.plan_paper_audit(temporary, 'Check the argument.')
            self.assertEqual(default['selected_roles'], ['adversarial_logic'])
            selected = ['adversarial_logic', 'domain_literature', 'methodology_statistics', 'journal_venue_fit']
            explicit = paper.plan_paper_audit(temporary, 'Check the argument.',
                selected_roles=selected + [selected[0]], selected_by='reviewer',
                selection_rationale='Coverage', effort='xhigh')
            self.assertEqual(explicit['selected_roles'], selected)
            self.assertEqual(explicit['effort'], 'xhigh')

    def test_missing_tex_runtime_runs_only_static_source_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'paper.tex').write_text('\\documentclass{article}\n\\begin{document}\nA minimal source.\n\\end{document}\n', 'utf-8')
            # Isolate discovery, without mocking the dependency API or compiler.
            with patch.dict(os.environ, {'RESEARCH_GUARD_HOME': str(root / 'empty-dependencies'),
                                         'RESEARCH_GUARD_TEX': '', 'PATH': ''}):
                result = paper.compile_tex_document(root, 'paper.tex')
            self.assertEqual(result['status'], 'DEGRADED')
            self.assertEqual(result['compiler'], 'NOT_RUN_MISSING_RUNTIME')
            self.assertIsNone(result['pdf_path'])
            self.assertIn('TeX compilation', result['unverified'])

    def test_reference_writing_bundle_and_three_reviews_need_no_digests(self):
        case = self.fixture(WritingFixture)
        bundle = copy.deepcopy(case.bundle)
        bundle.pop('plan_sha256')
        bundle.pop('reference_sha256')
        bundle['artifacts'].pop('compile_receipt')
        result = writing.submit_reference_writing(case.root, 'synthetic-writing', bundle)
        self.assertEqual(result['status'], 'THREE_AGENT_AUDIT_REQUIRED')
        reviews = case.reviews()
        for review in reviews:
            review.pop('draft_sha256')
            review.pop('reference_sha256')
        self.assertEqual(writing.audit_reference_writing(case.root, 'synthetic-writing', reviews)['status'], 'PASS')

    def test_reference_figure_plan_report_and_reviews_need_no_digests(self):
        case = self.fixture(FigureFixture)
        bundle = case.bundle()
        bundle.pop('plan_sha256')
        report_path = case.root/'pixels/pixel-audit.json'
        report = json.loads(report_path.read_text('utf-8'))
        report.pop('reference_sha256', None)
        report.pop('candidate_sha256', None)
        report_path.write_text(json.dumps(report), 'utf-8')
        for review_round in bundle['outputs'][0]['rounds']:
            for review in review_round['reviews']:
                review.pop('candidate_sha256')
                review.pop('reference_sha256')
        self.assertEqual(figures.audit_reference_figure(case.root, 'toy', bundle)['status'], 'PASS')

    def test_reference_figure_failed_information_is_still_correction_required(self):
        case = self.fixture(FigureFixture)
        bundle = case.bundle()
        bundle.pop('plan_sha256')
        review = bundle['outputs'][0]['rounds'][-1]['reviews'][0]
        review['checks']['all_requirements_present'] = False
        review['issues'] = ['SYNTHETIC: missing a requested input label.']
        result = figures.audit_reference_figure(case.root, 'toy', bundle)
        self.assertEqual(result['status'], 'CORRECTION_REQUIRED')

    def test_language_reads_edited_file_without_replanning(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root/'paper.md'
            path.write_text('It should be noted that the result is bounded.\n', 'utf-8')
            language.plan_language_review(root, 'Polish current prose', manuscript_files=[path.name])
            path.write_text('The measured result is bounded.\n', 'utf-8')
            analysis = language.analyze_language(root)
            self.assertEqual(analysis['blocking_count'], 0)
            self.assertEqual(language.finalize_language_review(root)['status'], 'PASS')

    def test_inline_language_uses_stored_or_updated_text_without_replanning(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            language.plan_language_review(root, 'Polish', draft_text='The measurement is 3.')
            self.assertEqual(language.analyze_language(root)['blocking_count'], 0)
            self.assertEqual(language.analyze_language(root, draft_text='The measurement is 4.')['blocking_count'], 0)

    def test_conference_writing_can_start_without_venue_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(language, 'verify_venue_receipt', return_value={'status': 'NOT_FOUND'}):
                result = language.plan_language_review(temporary, 'Draft the methods',
                    draft_text='The study evaluates the registered method.', task_mode='conference_writing',
                    venue='Example venue', venue_year=2026)
            self.assertEqual(result['task_mode'], 'conference_writing')

    def test_paper_spine_register_needs_no_plan_or_method_digest(self):
        case = self.fixture(SpineFixture)
        proposal = case.spine()
        proposal.pop('method_hash')
        result = spine.register_paper_spine(case.root, spine_id='qxy-spine', spine=proposal)
        self.assertEqual(result['spine']['spine_id'], 'qxy-spine')

    def test_numerical_model_executes_current_source_ignoring_optional_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'path-alias').mkdir()
            root = root/'path-alias'/'..'
            source = root/'model.py'
            source.write_text("def evaluate(parameters):\n    return float(parameters['x'])\n", 'utf-8')
            request = manifest('obsolete metadata')
            self.assertEqual(math_worker._numerical(request, root)['status'], 'PASS')
            request['numerical_protocol'].pop('model_sha256')
            self.assertEqual(math_worker._numerical(request, root)['status'], 'PASS')
            source.write_text("def evaluate(parameters):\n    return float(parameters['x']) + 1\n", 'utf-8')
            # No checksum rejection or stale cached execution: the changed
            # model actually runs and fails its original numerical expectation.
            result = math_worker._numerical(request, root)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(result['checks'][0]['values'], [1.0])

    def test_model_sensitivity_accepts_identified_runs_without_digest_fields(self):
        rows = [{'run_id': f'r{i}', 'model_id': f'm{i}', 'score': i+1, 'scale_min': 0, 'scale_max': 5} for i in [1, 2]]
        self.assertEqual(reviewers._model_sensitivity(rows, '')['status'], 'OBSERVED')


# Imported fixture classes are construction helpers, not duplicate test suites.
def load_tests(loader, tests, pattern):
    return loader.loadTestsFromTestCase(WorkflowWithoutDigestGatesTests)
