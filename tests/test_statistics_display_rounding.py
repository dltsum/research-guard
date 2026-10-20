"""Numerical regression vectors, including the real 054 reporting failure."""
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from research_guard_core import register_method
from research_integrity_core import audit_statistics


class StatisticDisplayRoundingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        register_method(self.root, {'title': 'Rounding audit', 'problem': 'reported precision',
                                    'mechanism': 'recompute displayed statistics'})

    def tearDown(self):
        self.temp.cleanup()

    def check_report(self, text):
        return audit_statistics(self.root, 'case-v1', text=text)

    def test_actual_twelve_decimal_report_is_compatible(self):
        actual_t = -16.15 / 10.75
        actual_p = 1 - 2 / math.pi * math.atan(abs(actual_t))
        self.assertEqual(f'{actual_p:.12f}', '0.373879030252')
        r = self.check_report(f't(1)={actual_t:.12f}, p={actual_p:.12f}')
        self.assertEqual(r['status'], 'PASS')
        self.assertLessEqual(r['checks'][0]['rounding_p_interval'][0], actual_p)
        self.assertGreaterEqual(r['checks'][0]['rounding_p_interval'][1], actual_p)

    def test_coarse_statistic_and_precise_p_are_compatible(self):
        p = 1 - 2 / math.pi * math.atan(1.5023255813953489)
        self.assertEqual(self.check_report(f't(1)=-1.50, p={p:.6f}')['status'], 'PASS')

    def test_large_discrepancy_is_still_detected(self):
        r = self.check_report('t(1)=-1.50, p=.001000')
        self.assertEqual(r['status'], 'ISSUES_FOUND')
        self.assertEqual(r['decision_error_count'], 1)

    def test_significance_crossing_due_to_rounding_is_ambiguous(self):
        r = self.check_report('t(1)=12.71, p=.050')
        self.assertEqual(r['status'], 'PASS')
        self.assertIsNone(r['checks'][0]['computed_significance'])
        self.assertEqual(r['decision_error_count'], 0)

    def test_two_sided_interval_includes_zero_extremum(self):
        r = self.check_report('t(1)=0.00, p=1.000')
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(r['checks'][0]['rounding_p_interval'][1], 1.0)

    def test_invalid_statistic_is_not_made_valid_by_rounding(self):
        r = self.check_report('r(10)=2.0, p=.050')
        self.assertEqual(r['status'], 'ISSUES_FOUND')
        self.assertEqual(r['not_recomputed_count'], 1)


if __name__ == '__main__':
    unittest.main()
