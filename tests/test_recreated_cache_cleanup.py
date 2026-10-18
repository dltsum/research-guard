from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mcp_server import dispatch


class RecreatedCacheCleanupTests(unittest.TestCase):
    def test_recreated_cache_is_removed_and_reported_on_second_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); project = base / 'project'; home = base / 'guard'
            cache = project / '.research-guard/cache'
            durable = project / '.research-guard/state.json'
            args = {'action': 'status', 'project_root': str(project), 'maintenance_action': 'clean', 'maintenance_home': str(home)}
            cache.mkdir(parents=True); (cache / 'first.bin').write_bytes(b'first')
            durable.write_text('{}', encoding='utf-8')
            self.assertEqual(dispatch('research_design', args)['bytes_released'], 5)
            cache.mkdir(); (cache / 'second.bin').write_bytes(b'second-generation')
            second = dispatch('research_design', args)
            self.assertEqual(second['status'], 'CLEANED')
            self.assertEqual(second['bytes_released'], len(b'second-generation'))
            self.assertFalse(cache.exists())
            self.assertTrue(durable.is_file())
            self.assertEqual(dispatch('research_design', args)['bytes_released'], 0)

    def test_recreated_cache_dry_run_and_cancel_do_not_hide_it_from_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); project = base / 'project'; home = base / 'guard'
            cache = home / 'cache'
            args = {'action': 'status', 'project_root': str(project), 'maintenance_action': 'clean', 'maintenance_home': str(home)}
            cache.mkdir(parents=True); (cache / 'first').write_bytes(b'x')
            dispatch('research_design', args)
            cache.mkdir(); (cache / 'new').write_bytes(b'new')
            dry = dispatch('research_design', {**args, 'maintenance_dry_run': True})
            self.assertEqual(dry['actions'][0]['status'], 'WOULD_REMOVE')
            cancel = dispatch('research_design', {**args, 'maintenance_cancel': True})
            self.assertEqual(cancel['status'], 'CANCELLED')
            self.assertTrue(cache.is_dir())
            self.assertEqual(dispatch('research_design', args)['bytes_released'], 3)
            self.assertFalse(cache.exists())


if __name__ == '__main__':
    unittest.main()
