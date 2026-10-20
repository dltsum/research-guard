"""Real Windows junction regression in a fully task-owned temporary fixture."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import dependency_manager as d


@unittest.skipUnless(os.name == 'nt', 'Windows NTFS junction behavior')
class CleanReparseBoundaryTests(unittest.TestCase):
    def fixture(self, base):
        home = base/'home'
        project = base/'project'
        external = base/'outside-clean-roots/cache'
        external.mkdir(parents=True)
        marker = external/'preserve.txt'
        marker.write_bytes(b'Owned regression fixture; must not be deleted through a junction.')
        home.mkdir()
        link = project/'.research-guard/linked-outside'
        link.parent.mkdir(parents=True)
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        command = 'New-Item -ItemType Junction -Path ' + quote(link) + ' -Target ' + quote(external.parent) + ' -ErrorAction Stop | Out-Null'
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(getattr(link.lstat(), 'st_file_attributes', 0) & 0x400)
        # Every possible resolved target is inside this explicit test workspace,
        # although the outside marker is outside both requested cleanup roots.
        for path in (home, project, external, link.resolve()):
            path.resolve().relative_to(base.resolve())
        return home, project, link, marker

    def test_size_does_not_traverse_a_junction(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, project, link, marker = self.fixture(Path(temporary))
            self.assertEqual(d._path_size(link), 0)
            self.assertTrue(marker.is_file())

    def test_clean_does_not_recurse_through_a_junction(self):
        with tempfile.TemporaryDirectory() as temporary:
            home, project, link, marker = self.fixture(Path(temporary))
            result = d.clean_state(project, home=home)
            self.assertTrue(marker.is_file(), result)
            self.assertEqual(result['bytes_released'], 0)
            self.assertEqual(result['actions'], [])
