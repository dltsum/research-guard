import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from language_guard_core import _sentences, plan_language_review, analyze_language


class LanguageDecimalLocationsTests(unittest.TestCase):
    def test_decimal_values_do_not_split_sentences(self):
        text='Mean file coverage is 1.00 and 0.25. The rate is .5.'
        self.assertEqual(_sentences(text), [(1,'Mean file coverage is 1.00 and 0.25.'),(1,'The rate is .5.')])

    def test_actual_protected_decimal_excerpt_retains_physical_line(self):
        statement='Mean file coverage is 1.00 at 12500 updates and 0.25 at 25000 updates.'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'draft.md').write_text('# Results\n\n'+statement+'\n',encoding='utf8')
            plan_language_review(root,'Preserve measured file coverage values and their source location.',
                                 manuscript_files=['draft.md'],protected_spans=[{'text':statement,'reason':'The values quantify file coverage, not policy success.'}])
            result=analyze_language(root)
        issue=next(x for x in result['findings'] if x['category']=='protected_epistemic_qualifier')
        self.assertEqual(issue['line'],3)
        self.assertEqual(issue['excerpt'],statement)

    def test_multiline_protected_span_starts_on_its_actual_line(self):
        statement='Measured coverage\nretains its denominator'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'draft.md').write_text('# Results\n\n'+statement+'\n',encoding='utf8')
            plan_language_review(root,'Preserve the scope of the bound multiline statement.',
                                 manuscript_files=['draft.md'],protected_spans=[{'text':statement,'reason':'Retain the denominator and the original statement.'}])
            result=analyze_language(root)
        issue=next(x for x in result['findings'] if x['category']=='protected_epistemic_qualifier')
        self.assertEqual(issue['line'],3)


if __name__=='__main__': unittest.main()
