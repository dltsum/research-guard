import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from math_verification_worker import _symbolic


class SymbolicDomainPreservationTests(unittest.TestCase):
    def check(self, lhs, rhs, assumptions):
        return _symbolic({
            'applicability': {'symbolic': {'status':'required'}},
            'symbolic_checks': [{'id':'domain','source':'Actual interactive domain regression',
                'lhs':lhs,'rhs':rhs,'symbols':[{'name':'x','assumptions':assumptions}]}],
        })['checks'][0]

    def test_cancelled_division_does_not_erase_undefined_real_zero(self):
        result = self.check('x/x','1',{'real':True})
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual(result['domain_exclusions_to_review'],['x'])

    def test_explicit_nonzero_declaration_is_sufficient(self):
        result = self.check('x/x','1',{'real':True,'nonzero':True})
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['domain_exclusions_to_review'],[])

    def test_known_nonzero_constant_is_not_a_domain_exclusion(self):
        result = self.check('x/160','x*Rational(1,160)',{'integer':True,'nonnegative':True})
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['domain_exclusions_to_review'],[])

    def test_uncancelled_denominator_is_not_proved_nonzero_by_realness(self):
        result = self.check('1/x','1/x',{'real':True})
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual(result['domain_exclusions_to_review'],['x'])


if __name__=='__main__':
    unittest.main()
