"""Small deterministic venue fixtures, never authoritative venue evidence.

The repository intentionally omits downloaded policy/template/paper payloads.
These fixtures test local parsing, routing and receipt lifecycle without silently
depending on ignored downloads or claiming an official source was fetched.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

import venue_evidence_core as venue


class _FixtureDatetime(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 8, 14, tzinfo=dt.timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def _pdf_bytes() -> bytes:
    import io
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')}))
    for lines in (["DETERMINISTIC TEST FIXTURE - NOT AN OFFICIAL PAPER", "Abstract", "1 Introduction", "64 network layers are body text", "I. INTRODUCTION"],
                  ["2 Methods", "II. METHODS", "Fixture content only"]):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(("BT /F1 12 Tf 40 740 Td 20 TL\n" + "\n".join(f"({line}) Tj T*" for line in lines) + "\nET").encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def install_venue_fixtures(testcase) -> Path:
    """Patch only this test's seed/catalog; cleanup restores production globals."""
    temp = tempfile.TemporaryDirectory(prefix='rg-venue-fixture-')
    testcase.addCleanup(temp.cleanup)
    assets = Path(temp.name)
    registry = copy.deepcopy(json.loads(venue.SEED_REGISTRY.read_text(encoding='utf-8')))
    registry['fixture_notice'] = 'Deterministic local test data; no live or official authority verification.'
    pdf = _pdf_bytes()
    # Shared archive paths occur in several profiles; write once, then hash all.
    for profile in registry['profiles']:
        profile['fixture_notice'] = registry['fixture_notice']
        profile['policy_url'] = f"https://venue-fixture.invalid/{profile['venue']}/policy"
        profile['template_url'] = f"https://venue-fixture.invalid/{profile['venue']}/template.zip"
        for asset in profile['assets']:
            target = assets / asset['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix == '.zip':
                if not target.exists():
                    with zipfile.ZipFile(target, 'w') as archive:
                        info = zipfile.ZipInfo('fixture.tex', date_time=(2020, 1, 1, 0, 0, 0))
                        archive.writestr(info, '% TEST FIXTURE, NOT OFFICIAL\n\\documentclass{article}\n\\section{Introduction}\n\\section{Methods}\n')
            else:
                locators = [item['locator'] for item in profile.get('required_sections', [])]
                target.write_text('<h1>DETERMINISTIC TEST FIXTURE - NOT OFFICIAL POLICY</h1>\n' + '\n'.join(locators), encoding='utf-8')
        for exemplar in profile['exemplars']:
            target = assets / exemplar['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pdf)
            exemplar['title'] = 'Deterministic parser fixture, not an official exemplar'
            for field in ('award_url', 'record_url', 'pdf_url'):
                exemplar[field] = f"https://venue-fixture.invalid/{profile['venue']}/{field}"
    for profile in registry['profiles']:
        for item in [*profile['assets'], *profile['exemplars']]:
            item['sha256'] = hashlib.sha256((assets / item['path']).read_bytes()).hexdigest()
    seed = assets / 'registry.json'
    seed.write_text(json.dumps(registry), encoding='utf-8')
    # A fixed validation clock keeps age checks deterministic. Live endpoint
    # receipts in cycle C are explicitly mocked, never asserted as real traffic.
    clock = SimpleNamespace(datetime=_FixtureDatetime, timezone=dt.timezone, timedelta=dt.timedelta)
    for name, value in [('ASSET_ROOT', assets), ('SEED_REGISTRY', seed), ('dt', clock)]:
        patcher = patch.object(venue, name, value)
        patcher.start()
        testcase.addCleanup(patcher.stop)
    return assets
