"""Regression excerpts from an actually inspected multi-page IEEE paper."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import venue_evidence_core as venue


class IEEEHeadingSequenceTests(unittest.TestCase):
    def test_spaced_small_caps_and_roman_numeral(self):
        text = 'I . I N T R O D U C T I O N\nI I . R E L AT E D W O R K'
        headings = venue._paper_heading_candidates(text)
        self.assertEqual([h['heading'] for h in headings], text.splitlines())
        self.assertTrue(all(h['kind'] == 'roman_section' for h in headings))

    def test_numbering_continues_across_actual_page_boundaries(self):
        pages = [
            'I . I N T R O D U C T I O N',
            'I I . R E L AT E D W O R K',
            'I I I . R O B O- D M F E AT U R E S\nI V. R O B O- D M D E S I G N\nIV .B) for feature (4) and (5). Finally, Robo-DM is integrated',
            'V. E VA L U AT I O N', '',
            'V I . C O N C L U S I O N\nV I I . A C K N O W L E D G E M E N T',
        ]
        box = SimpleNamespace(width=612, height=792)
        reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda t=t:t, mediabox=box) for t in pages])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'sample.pdf';path.write_bytes(b'%PDF-regression-input')
            with patch.object(venue, 'PdfReader', return_value=reader):
                result=venue.inspect_paper_pdf(path)
        self.assertEqual([h['page'] for h in result['observed_headings']], [1,2,3,3,4,6,6])
        self.assertEqual(len(result['observed_headings']), 7)
        self.assertFalse(any('for feature' in h['heading'] for h in result['observed_headings']))


if __name__ == '__main__': unittest.main()
