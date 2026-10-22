import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from language_guard_core import (
    analyze_language, finalize_language_review, get_language_status,
    plan_language_review, resolve_language_issues, verify_language_receipt,
)


class ProtectedLanguageLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.protected = 'Mean file coverage is 1.00 at 12500 updates and 0.25 at 25000 updates.'

    def tearDown(self):
        self.temp.cleanup()

    def finalize(self, mixed=False):
        text = self.protected+'\n'
        if mixed:
            text += 'It should be noted that the measured result is bounded.\n'
        (self.root/'draft.md').write_text(text, encoding='utf8')
        plan_language_review(self.root, 'Review the actual archived coverage statement.',
            manuscript_files=['draft.md'], protected_spans=[{
                'text': self.protected,
                'reason': 'The observed fraction describes file coverage rather than robot performance.',
            }])
        analysis = analyze_language(self.root)
        self.assertTrue(any(not item['blocking'] for item in analysis['findings']))
        if mixed:
            self.assertTrue(any(item['blocking'] for item in analysis['findings']))
        resolve_language_issues(self.root, [{
            'issue_id': item['issue_id'],
            'action': 'retain_with_justification' if item['blocking'] else 'preserve',
            'rationale': 'Retain the exact source-supported evidence scope and its original meaning.',
        } for item in analysis['findings']])
        return finalize_language_review(self.root)

    def test_protected_resolution_remains_valid_across_status_and_verify(self):
        receipt = self.finalize()
        state = get_language_status(self.root)
        self.assertEqual(state['status'], 'PASS', state.get('reason'))
        self.assertEqual(verify_language_receipt(self.root)['receipt']['finding_ids'], receipt['finding_ids'])

    def test_mixed_blocking_and_protected_resolutions_remain_valid(self):
        self.finalize(mixed=True)
        self.assertEqual(get_language_status(self.root)['status'], 'PASS')

    def test_protected_resolution_action_is_still_verified(self):
        self.finalize()
        path = self.root/'.research-guard/language-state.json'
        state = json.loads(path.read_text(encoding='utf8'))
        state['resolutions'][0]['action'] = 'retain_with_justification'
        path.write_text(json.dumps(state), encoding='utf8')
        self.assertEqual(get_language_status(self.root)['status'], 'REVIEW_REQUIRED')


if __name__ == '__main__':
    unittest.main()
