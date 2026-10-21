from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('demo_media_builder', ROOT / 'docs/demo/build_demo.py')
builder = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(builder)


def collision_png() -> bytes:
    def chunk(name: bytes, payload: bytes) -> bytes:
        return struct.pack('>I', len(payload)) + name + payload + struct.pack('>I', zlib.crc32(name + payload) & 0xffffffff)
    header = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
    for padding in range(6):
        # Legal unknown ancillary chunk with bytes that collide with the
        # host-message text pattern. This PNG must retain exactly these bytes.
        png = header + chunk(b'rgUa', b'\xff' * padding + b'\x80' + bytes(100)) + chunk(b'IDAT', zlib.compress(b'\0\x10\x20\x30\xff')) + chunk(b'IEND', b'')
        if re.search(r'\bgAAAAA[A-Za-z0-9_-]{80,}', base64.b64encode(png).decode('ascii')):
            return png
    raise AssertionError('Fixture must reproduce the real Base64/text pattern collision')


class DemoMediaIntegrityTests(unittest.TestCase):
    def build(self, temporary: str, *, wrong_hash: bool = False) -> tuple[dict, bytes]:
        root = Path(temporary)
        evidence = root / 'evidence'
        repository = root / 'repository'
        output = root / 'output'
        evidence.mkdir()
        (repository / 'assets').mkdir(parents=True)
        png = collision_png()
        source = root / 'actual.png'
        source.write_bytes(png)
        digest = hashlib.sha256(png).hexdigest()
        save = lambda p, v: p.write_text(json.dumps(v), encoding='utf8')
        save(repository / 'assets/feature-components.json', {'components': {'core': {'label': 'Core', 'description': 'test', 'python_requirements': [], 'depends_on': []}}})
        save(evidence / '逐功能队列.json', {'routes': []})
        save(evidence / 'bugs.json', [])
        # A similarly named key in an untrusted dialogue must not bypass
        # credential and opaque-host-message filtering.
        event = {'kind': 'question', 'step_id': '001-core', 'component': 'core',
                 'question': {'media_base64': 'password=private-long-example', 'opaque': 'gAAAAA' + 'A' * 100}}
        (evidence / 'interaction-index.jsonl').write_text(json.dumps(event) + '\n', encoding='utf8')
        save(evidence / 'showcase.json', {'items': [{'component': 'core', 'file': str(source), 'sha256': '0' * 64 if wrong_hash else digest,
              'title': 'Actual PNG', 'caption': 'password=private-caption-example'}]})
        template = root / 'template.html'
        template.write_text('<script id="rg-demo-data" type="application/json">__RG_DEMO_DATA_JSON__</script>', encoding='utf8')
        argv = ['build_demo.py', '--evidence-root', str(evidence), '--repository', str(repository), '--template', str(template), '--output', str(output)]
        with patch.object(sys, 'argv', argv), patch.object(builder.subprocess, 'check_output', return_value='a' * 40), contextlib.redirect_stdout(io.StringIO()):
            builder.main()
        return json.loads((output / 'data.json').read_text(encoding='utf8')), png

    def test_verified_media_bytes_survive_text_redaction_without_exempting_dialogue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data, png = self.build(temporary)
        component = data['components'][0]
        media = component['showcase'][0]
        decoded = base64.b64decode(media['media_base64'], validate=True)
        self.assertEqual(decoded, png)
        self.assertEqual(hashlib.sha256(decoded).hexdigest(), media['sha256'])
        self.assertNotIn('private-caption-example', media['caption'])
        question = component['steps'][0]['question']
        self.assertNotIn('private-long-example', question['media_base64'])
        self.assertEqual(question['opaque'], '[opaque encrypted payload omitted]')

    def test_changed_source_is_rejected_before_media_is_embedded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'Showcase source changed'):
                self.build(temporary, wrong_hash=True)

    def test_generated_text_bytes_are_canonical_lf_for_git_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.build(temporary)
            output = Path(temporary) / 'output'
            for name in ('index.html', 'data.json', 'manifest.json'):
                raw = (output / name).read_bytes()
                self.assertNotIn(b'\r\n', raw, name)
            manifest = json.loads((output / 'manifest.json').read_bytes())
            for name, field in (('index.html', 'html_sha256'), ('data.json', 'data_sha256')):
                raw = (output / name).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest[field])
                self.assertEqual(raw, raw.replace(b'\r\n', b'\n'))

    @unittest.skipUnless(shutil.which('git'), 'Git is required for the actual checkout round trip')
    def test_windows_git_clone_retains_published_manifest_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.build(temporary)
            root = Path(temporary)
            publication = root / 'publication'
            (publication / 'docs/demo').mkdir(parents=True)
            (publication / 'empty-hooks').mkdir()
            (publication / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            for name in ('index.html', 'manifest.json'):
                (publication / 'docs/demo' / name).write_bytes((root / 'output' / name).read_bytes())
            def git(*args: str) -> None:
                command = ['git', '-c', 'core.autocrlf=true', '-c', 'core.safecrlf=false',
                           '-c', 'core.hooksPath=' + str(publication / 'empty-hooks'),
                           '-c', 'user.name=Demo regression', '-c', 'user.email=demo@example.invalid',
                           '-c', 'commit.gpgsign=false', *args]
                subprocess.run(command, cwd=publication, check=True, capture_output=True)
            git('init')
            git('add', '.gitattributes', 'docs/demo/index.html', 'docs/demo/manifest.json')
            git('commit', '-m', 'Actual manifest checkout fixture')
            checkout = root / 'checkout'
            git('clone', '--no-local', '-c', 'core.autocrlf=true', str(publication), str(checkout))
            manifest = json.loads((checkout / 'docs/demo/manifest.json').read_bytes())
            page = (checkout / 'docs/demo/index.html').read_bytes()
            self.assertEqual(hashlib.sha256(page).hexdigest(), manifest['html_sha256'])
            self.assertNotIn(b'\r\n', page)


if __name__ == '__main__':
    unittest.main()
