"""Documentation editing must not need a hash-refresh ceremony."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from documentation_parity import DocumentationParityError,refresh_hashes,validate_documentation


class DocumentationHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'assets').mkdir()
        (self.root/'guide.md').write_text('# Guide\n',encoding='utf-8')
        (self.root/'guide.zh-CN.md').write_text('# 指南\n',encoding='utf-8')
        self.manifest=self.root/'assets/documentation-parity.json'
        self.manifest.write_text(json.dumps({'pairs':[{'id':'guide','source_path':'guide.md','translation_path':'guide.zh-CN.md'}]}),encoding='utf-8')

    def test_current_repository_documents_are_readable(self):
        result=validate_documentation(ROOT)
        self.assertEqual(result['status'],'PASS')
        self.assertGreaterEqual(result['pair_count'],2)

    def test_normal_edits_and_extra_headings_need_no_refresh(self):
        (self.root/'guide.md').write_text('# Changed guide\n\n## Extra detail\nNew text.\n',encoding='utf-8')
        self.assertEqual(validate_documentation(self.root)['status'],'PASS')

    def test_legacy_refresh_does_not_modify_files(self):
        before=self.manifest.read_bytes()
        self.assertEqual(refresh_hashes(self.root)['status'],'PASS')
        self.assertEqual(self.manifest.read_bytes(),before)

    def test_added_translation_does_not_block_existing_pair(self):
        (self.root/'new.zh-CN.md').write_text('# 新文档',encoding='utf-8')
        self.assertEqual(validate_documentation(self.root)['status'],'PASS')

    def test_missing_link_is_an_actionable_warning(self):
        (self.root/'guide.md').write_text('[Example](missing.md)',encoding='utf-8')
        result=validate_documentation(self.root)
        self.assertEqual(result['status'],'PASS')
        self.assertIn('missing.md',result['warnings'][0])

    def test_missing_or_empty_requested_document_reports_real_problem(self):
        (self.root/'guide.zh-CN.md').unlink()
        with self.assertRaisesRegex(DocumentationParityError,'cannot read'):
            validate_documentation(self.root)
        (self.root/'guide.zh-CN.md').write_text('',encoding='utf-8')
        with self.assertRaisesRegex(DocumentationParityError,'empty'):
            validate_documentation(self.root)

    def test_manifest_path_cannot_escape_the_selected_repository(self):
        self.manifest.write_text(json.dumps({'pairs':[{'source_path':'../outside.md','translation_path':'guide.zh-CN.md'}]}),encoding='utf-8')
        with self.assertRaisesRegex(DocumentationParityError,'escapes'):
            validate_documentation(self.root)


if __name__=='__main__':unittest.main()
