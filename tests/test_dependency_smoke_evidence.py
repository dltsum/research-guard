"""Evidence retention regressions with a clearly labelled compiler unit double.

The interactive acceptance separately compiles with the actual host TeX binary.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import dependency_manager as d


class SmokeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.exe = self.root/'host/pdflatex'
        self.exe.parent.mkdir(); self.exe.write_bytes(b'compiler unit double')
        self.env = patch.dict(os.environ, {'RESEARCH_GUARD_HOME':str(self.root/'private')})
        self.detect = patch.object(d,'detect_existing',return_value={'available':True,'executables':{'pdflatex':str(self.exe)},'version':'unverified fixture'})
        self.headroom = patch.object(d,'require_start_headroom',return_value={})
        self.env.start(); self.detect.start(); self.headroom.start()
    def tearDown(self):
        self.headroom.stop(); self.detect.stop(); self.env.stop(); self.temp.cleanup()
    def compile_double(self, command, cwd, timeout):
        (cwd/'smoke.pdf').write_bytes(b'explicit unit fixture, not a valid research PDF')
        (cwd/'smoke.log').write_text('fixture compiler native log')
        return subprocess.CompletedProcess(command,0,'fixture compiler banner\ncompiled\n','')
    def test_success_retains_compile_artifacts_and_idempotence_checks_their_hashes(self):
        with patch.object(d,'run_managed',side_effect=self.compile_double) as runner:
            first = d.register_existing('tex-basic')
            verification = first['verification']
            self.assertEqual(verification['status'],'PASS')
            self.assertEqual(first['detected_version'],'fixture compiler banner')
            self.assertTrue(d._smoke_current(first))
            self.assertEqual({Path(a['path']).name for a in verification['artifacts']}, {'smoke.tex','smoke.pdf','smoke.log','stdout.txt','stderr.txt'})
            self.assertTrue(d.register_existing('tex-basic')['idempotent'])
            self.assertEqual(runner.call_count,1)
            Path(next(a['path'] for a in verification['artifacts'] if a['path'].endswith('.pdf'))).write_bytes(b'changed')
            second = d.register_existing('tex-basic')
            self.assertEqual(runner.call_count,2)
            self.assertNotEqual(first['verification']['record_path'],second['verification']['record_path'])
    def test_changed_compiler_invalidates_old_smoke(self):
        with patch.object(d,'run_managed',side_effect=self.compile_double) as runner:
            first=d.register_existing('tex-basic')
            self.exe.write_bytes(b'changed compiler double')
            self.assertFalse(d._smoke_current(first))
            d.register_existing('tex-basic'); self.assertEqual(runner.call_count,2)
    def test_failed_compiler_keeps_failure_evidence_without_install_receipt(self):
        with patch.object(d,'run_managed',return_value=subprocess.CompletedProcess([],1,'fixture failure output','fixture stderr')):
            with self.assertRaises(d.DependencyError):d.register_existing('tex-basic')
        self.assertIsNone(d._component_status('tex-basic'))
        record=next((d.dependency_root()/'verification').glob('*/verification.json'))
        result=json.loads(record.read_text())
        self.assertEqual(result['status'],'FAILED');self.assertEqual(result['returncode'],1)
        self.assertEqual((record.parent/'stdout.txt').read_text(),'fixture failure output')
        self.assertTrue(self.exe.is_file())

if __name__=='__main__':unittest.main()
