import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from dependency_manager import _atomic_json
from evidence_kernel import io_path

class DependencyLongPathTest(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows extended path regression')
    def test_long_receipt_filename_roundtrips_without_leftover_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parent = root / ('n' * (235 - len(str(root)) - 1))
            parent.mkdir()
            target = parent / '20261020T035200-component-existing-registered-12345678.json'
            self.assertGreater(len(str(target)), 260)
            _atomic_json(target, {'status': 'INSTALLED', 'scope': 'existing-git'})
            self.assertEqual(json.loads(io_path(target).read_text(encoding='utf-8'))['status'], 'INSTALLED')
            self.assertEqual([x.name for x in parent.iterdir()], [target.name])
            # TemporaryDirectory's own cleanup uses ordinary Windows paths.
            # Remove only this test's verified file through the long-path API.
            io_path(target).unlink()

if __name__ == '__main__':
    unittest.main()
