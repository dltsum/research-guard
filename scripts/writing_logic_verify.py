"""Exact structural/coverage checks for reference-guided writing.

This is not a proof of semantic equivalence or scientific validity. Three actual
agent reviews remain mandatory. Character offsets are Python Unicode offsets;
word units are Latin/number tokens or individual CJK characters, not a claim of
language-independent linguistic segmentation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

LEVELS = (
    'section_internal', 'between_subsections', 'within_subsection',
    'between_paragraphs', 'within_paragraph', 'between_sentences',
    'within_sentence', 'between_words', 'long_range_correspondence',
    'wording_style', 'total_word_count',
)
WORD = re.compile(r'[A-Za-z0-9]+(?:[’\x27-][A-Za-z0-9]+)*|[\u3400-\u9fff]')


def units(text: str, level: str) -> list[tuple[int, int]]:
    if level == 'between_words':
        return [(m.start(), m.end()) for m in WORD.finditer(text)]
    if level == 'within_paragraph':
        return [(m.start(), m.start() + len(m.group().rstrip()))
                for m in re.finditer(r'\S.*?(?=\n\s*\n|\Z)', text, re.S)]
    starts = [0]
    ends = []
    for match in re.finditer(r'[。！？]|[.!?](?=\s|$)|\n', text):
        ends.append(match.end()); starts.append(match.end())
    ends.append(len(text))
    result = []
    for a, b in zip(starts, ends):
        while a < b and text[a].isspace(): a += 1
        while a < b and text[b - 1].isspace(): b -= 1
        if a < b: result.append((a, b))
    return result


def safe_file(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Expected a project-local regular file: {name}')
    return path


def span(value: Any, text: str) -> tuple[int, int]:
    if (not isinstance(value, list) or len(value) != 2
            or any(type(v) is not int for v in value)
            or not 0 <= value[0] < value[1] <= len(text)):
        raise ValueError('Every alignment span needs valid Unicode [start,end) offsets')
    return value[0], value[1]


def verify(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    reference_file = safe_file(root, manifest['reference_text'])
    draft_file = safe_file(root, manifest['draft_text'])
    reference = reference_file.read_text('utf-8')
    draft = draft_file.read_text('utf-8')
    rows = manifest.get('alignments', [])
    if not rows or {row.get('level') for row in rows} != set(LEVELS):
        raise ValueError('Logic alignment must explicitly cover all eleven requested levels')
    ids = [row.get('id') for row in rows]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('Alignment IDs must be nonempty and unique')
    for row in rows:
        span(row.get('reference_span'), reference)
        span(row.get('draft_span'), draft)
        if not str(row.get('logic_move', '')).strip() or not str(row.get('explanation', '')).strip():
            raise ValueError('Every alignment needs its logic move and a specific explanation')
    failures = []
    coverage = {}
    # Whole selected scopes must be covered, rather than a few convenient
    # excerpts being promoted to a word/sentence/paragraph audit.
    for name, text in [('reference', reference), ('draft', draft)]:
        scopes = manifest.get(name + '_scope', [[0, len(text)]])
        if scopes != [[0, len(text)]]:
            raise ValueError('A whole-manuscript audit requires the complete text scope; selected excerpts cannot pass as full coverage')
        bounds = [span(item, text) for item in scopes]
        for level in ('between_words', 'within_sentence', 'within_paragraph'):
            selected_rows = [row for row in rows if row['level'] == level]
            intervals = [span(row[name + '_span'], text) for row in selected_rows]
            canonical_units = set(units(text, level))
            if any(item not in canonical_units for item in intervals):
                failures.append(name + ':' + level + ':NOT_INDIVIDUAL_UNITS')
            pairs = [(tuple(row['reference_span']), tuple(row['draft_span'])) for row in selected_rows]
            if len(set(pairs)) != len(pairs):
                failures.append(name + ':' + level + ':DUPLICATE_MAPPING')
            tokens = [m for m in WORD.finditer(text) if any(a <= m.start() and m.end() <= b for a, b in bounds)]
            missing = [m.start() for m in tokens if not any(a <= m.start() and m.end() <= b for a, b in intervals)]
            coverage[name + ':' + level] = {'tokens': len(tokens), 'uncovered_offsets': missing}
            if missing:
                failures.append(name + ':' + level + ':INCOMPLETE_COVERAGE')
    relations = []
    for key in ('reference_edges', 'draft_edges'):
        edges = manifest.get(key)
        if not isinstance(edges, list):
            raise ValueError('Both explicit logical edge sets are required')
        normalized = []
        for edge in edges:
            if edge.get('source') not in ids or edge.get('target') not in ids or edge.get('relation') not in {
                'supports', 'causes', 'contrasts', 'limits', 'defines', 'precedes', 'refers_to',
            }:
                raise ValueError('Invalid logical relation or unknown alignment node')
            normalized.append((edge['source'], edge['target'], edge['relation']))
        if len(set(normalized)) != len(normalized):
            raise ValueError('Duplicate edges cannot count as extra logical evidence')
        relations.append(set(normalized))
    if relations[0] != relations[1]:
        failures.append('LOGIC_RELATIONS_CHANGED')
    ordered = {i: set() for i in ids}
    for source, target, relation in relations[1]:
        if relation == 'precedes':
            ordered[target].add(source)
    remaining = set(ids)
    while remaining:
        ready = {i for i in remaining if not (ordered[i] & remaining)}
        if not ready:
            failures.append('CYCLIC_PRECEDENCE'); break
        remaining -= ready
    word_counts = {name: len(WORD.findall(text)) for name, text in [('reference', reference), ('draft', draft)]}
    limits = manifest.get('draft_word_limits')
    if (not isinstance(limits, list) or len(limits) != 2
            or any(type(v) is not int for v in limits) or not 0 <= limits[0] <= limits[1]):
        raise ValueError('Explicit integer draft_word_limits are required')
    if not limits[0] <= word_counts['draft'] <= limits[1]:
        failures.append('WORD_BUDGET_EXCEEDED')
    for token in manifest.get('protected_tokens', []):
        if not isinstance(token, str) or token not in draft:
            failures.append('PROTECTED_INFORMATION_MISSING:' + str(token))
    return {
        'status': 'PASS' if not failures else 'CORRECTION_REQUIRED',
        'failures': failures, 'coverage': coverage, 'word_counts': word_counts,
        'draft_file': draft_file.relative_to(root).as_posix(),
        'reference_file': reference_file.relative_to(root).as_posix(),
        'semantic_equivalence_proved': False,
        'boundary': 'Exact registered span coverage, edge-set preservation, acyclic precedence and word limits only; semantic logic, wording fidelity and scientific adequacy require actual independent reviews.',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.project_root, json.loads(args.manifest.read_text('utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
