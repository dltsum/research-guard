"""Real loopback HTTP checks of bounded, hashed, explicitly invoked acquisition.

These tiny unit inputs are not the live acceptance demo or a Git installation.
"""
import hashlib
import http.server
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import dependency_manager as d


class OptionalPayloadAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = b'bounded real HTTP payload unit input\n' * 50
        self.requests = []
        owner = self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(owner.data)
            def log_message(self, *args): pass
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.record = {'name': 'mingit.zip', 'bytes': len(self.data),
                       'sha256': hashlib.sha256(self.data).hexdigest(),
                       'download_url': f'http://127.0.0.1:{self.server.server_port}/payload'}
        self.environment = patch.dict(os.environ, {'RESEARCH_GUARD_HOME': str(self.root / 'private-home')})
        self.plugin = patch.object(d, 'PLUGIN_ROOT', self.root / 'source-without-payloads')
        self.records = patch.object(d, '_payload_records', return_value={'mingit.zip': self.record})
        self.environment.start(); self.plugin.start(); self.records.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.records.stop(); self.plugin.stop(); self.environment.stop(); self.temp.cleanup()

    def test_inventory_truthfully_reports_missing_bytes_without_network(self):
        state = d._payload_availability(['mingit.zip'])
        self.assertEqual(state['bundled_bytes'], 0)
        self.assertEqual(state['missing_payload_download_bytes'], len(self.data))
        self.assertEqual(self.requests, [])

    def test_acquire_only_one_payload_and_reuse_verified_cache(self):
        target = d._acquire_payload('mingit.zip')
        self.assertEqual(target.read_bytes(), self.data)
        self.assertEqual(self.requests, ['/payload'])
        self.assertEqual(d._acquire_payload('mingit.zip'), target)
        self.assertEqual(self.requests, ['/payload'])
        self.assertFalse((d.PLUGIN_ROOT / 'assets/payloads').exists())
        receipts = list((d.dependency_root() / 'receipts').glob('*payload-downloaded*.json'))
        self.assertEqual(len(receipts), 1)
        self.assertFalse(json.loads(receipts[0].read_text())['full_bundle_downloaded'])

    def test_corrupt_download_is_not_committed_and_partial_file_is_removed(self):
        self.record['sha256'] = '0' * 64
        with self.assertRaises(d.DependencyError) as error:
            d._acquire_payload('mingit.zip')
        self.assertEqual(error.exception.code, 'DEPENDENCY_PAYLOAD_HASH_MISMATCH')
        self.assertEqual(list((d.dependency_root() / 'payload-cache').iterdir()), [])

    def test_oversized_download_is_refused_before_commit(self):
        self.record['bytes'] = len(self.data) - 1
        with self.assertRaises(d.DependencyError) as error:
            d._acquire_payload('mingit.zip')
        self.assertEqual(error.exception.code, 'DEPENDENCY_PAYLOAD_HASH_MISMATCH')
        self.assertFalse((d.dependency_root() / 'payload-cache/mingit.zip').exists())

    def test_corrupt_local_cache_is_preserved_without_silent_redownload(self):
        cache = d.dependency_root() / 'payload-cache/mingit.zip'
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b'corrupt')
        with self.assertRaises(d.DependencyError): d._acquire_payload('mingit.zip')
        self.assertEqual(cache.read_bytes(), b'corrupt')
        self.assertEqual(self.requests, [])

    def test_plain_http_remote_or_credential_source_is_refused(self):
        for url in ['http://example.org/payload', 'https://name:password@example.org/payload']:
            with self.subTest(url=url):
                self.record['download_url'] = url
                with self.assertRaises(d.DependencyError) as error: d._acquire_payload('mingit.zip')
                self.assertEqual(error.exception.code, 'DEPENDENCY_PAYLOAD_SOURCE_INVALID')
        self.assertEqual(self.requests, [])

if __name__ == '__main__': unittest.main()
