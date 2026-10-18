"""Evidence-bound reference selection and whole-paper logic writing workflow.

The agent researches and writes. This module preserves user constraints and
checks the actual deliverables; it does not generate prose, certify semantic
equivalence, establish venue prestige, or manufacture scientific results.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from language_guard_core import IMAGINED_CRITIC, DISCLAIMER_FIRST, INTERNAL_PROCESS
from writing_logic_verify import LEVELS, safe_file, verify as verify_logic
from evidence_kernel import io_path, _atomic_json


class ReferenceWritingError(ValueError):
    pass


ROLES = {
    'logic': set(LEVELS) | {'outline_unchanged', 'whole_paper_consistent', 'figure_table_functions_match'},
    'defensive': {'no_disclaimer_first', 'no_imagined_critics', 'no_hedge_stacks', 'material_limitations_preserved', 'no_strengthened_claims'},
    'scientific': {'reference_qualifications_verified', 'evidence_supports_claims', 'no_fabricated_results', 'math_symbols_defined', 'no_unexplained_parameters', 'no_data_unjustified_distribution_parameters', 'missing_experiments_explicit', 'figures_tables_supported', 'math_presence_assessed'},
}
ARTIFACTS = {'draft', 'formatted_pdf', 'supplements', 'reference_logic', 'detailed_alignment', 'logic_script', 'alignment_manifest', 'compile_receipt'}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _hash(path: Path) -> str:
    return hashlib.sha256(io_path(path).read_bytes()).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReferenceWritingError(f'{field} must be nonempty text')
    return value.strip()


def _id(value: str) -> str:
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,95}', str(value)):
        raise ReferenceWritingError('Invalid writing_id')
    return value


def _file(root: Path, value: str) -> tuple[str, Path]:
    try:
        path = safe_file(root, _text(value, 'file'))
    except ValueError as exc:
        raise ReferenceWritingError(str(exc)) from exc
    return path.relative_to(root).as_posix(), path


def _https(value: str) -> str:
    url = urlsplit(_text(value, 'source_url'))
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ReferenceWritingError('Primary-record evidence requires a credential-free HTTPS link')
    return value


def _evidence(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ReferenceWritingError('Source evidence must be an object')
    name, path = _file(root, record.get('file', ''))
    if record.get('sha256') is not None and record['sha256'] != _hash(path):
        raise ReferenceWritingError('Source evidence digest does not match its supplied file')
    try:
        checked = dt.datetime.fromisoformat(record.get('checked_at', '').replace('Z', '+00:00'))
    except (ValueError, TypeError) as exc:
        raise ReferenceWritingError('Evidence needs checked_at with a timezone') from exc
    if checked.tzinfo is None or checked > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ReferenceWritingError('Evidence timestamp must be timezone-aware and not in the future')
    return {**record, 'source_url': _https(record.get('source_url', '')), 'locator': _text(record.get('locator'), 'source locator'), 'file': name, 'sha256': _hash(path)}


def _path(root: Path, writing_id: str) -> Path:
    return root / '.research-guard/reference-writing' / (_id(writing_id) + '.json')


def _load(root: Path, writing_id: str) -> dict[str, Any]:
    path = _path(root, writing_id)
    if not path.exists():
        raise ReferenceWritingError('Call reference_writing_action=plan first')
    return json.loads(io_path(path).read_text('utf-8'))


def _save(root: Path, state: dict[str, Any]) -> None:
    path = _path(root, state['writing_id']); path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(path, state)


def plan_reference_writing(root: str | Path, contract: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve(); writing_id = _id(contract.get('writing_id', ''))
    for field in ('request_text', 'research_object', 'research_method', 'research_content'):
        _text(contract.get(field), field)
    # Explicit date resolves the ambiguity between "2025 onwards" and "after 2025".
    try:
        date = dt.date.fromisoformat(contract.get('publication_date_min', ''))
    except (ValueError, TypeError) as exc:
        raise ReferenceWritingError('Set explicit publication_date_min, e.g. 2025-01-01 or 2026-01-01') from exc
    if date.year < 2025:
        raise ReferenceWritingError('The requested recent-reference threshold cannot be older than 2025')
    records = contract.get('experiment_records')
    if not isinstance(records, list) or not records:
        raise ReferenceWritingError('Read and bind experiment records before searching or drafting')
    sources = []
    for name in records:
        relative, path = _file(root, name); sources.append({'file': relative, 'sha256': _hash(path)})
    outline = contract.get('outline')
    if not isinstance(outline, list) or not outline:
        raise ReferenceWritingError('An existing ordered outline is required and cannot be invented during revision')
    ids = [_text(row.get('id'), 'outline id') for row in outline]
    if len(set(ids)) != len(ids):
        raise ReferenceWritingError('Outline IDs must be unique')
    for row in outline:
        _text(row.get('title'), 'outline title')
        if type(row.get('level')) is not int or not 1 <= row['level'] <= 6:
            raise ReferenceWritingError('Outline level must be an integer 1..6')
    revised = contract.get('sections_to_revise', ids)
    if not revised or not set(revised) <= set(ids):
        raise ReferenceWritingError('Revision scope must name existing outline IDs')
    limits = contract.get('draft_word_limits')
    if (not isinstance(limits, list) or len(limits) != 2 or any(type(v) is not int for v in limits)
            or not 1 <= limits[0] <= limits[1]):
        raise ReferenceWritingError('Register an explicit whole-draft integer word budget')
    plan = {**contract, 'experiment_sources': sources, 'sections_to_revise': revised,
            'qualification_rule': 'CAS_ZONE_1_AND_CITATIONS_GT_10_OR_CCF_B_PLUS_BEST_PAPER_NOMINATION_OR_CCF_A_ORAL_PLUS',
            'minimum_reviewers': 3, 'outline_may_change': False, 'semantic_proof_claim_allowed': False}
    plan['plan_sha256'] = _digest(plan)
    existing = _path(root, writing_id)
    history = json.loads(io_path(existing).read_text('utf-8')).get('history', []) if existing.exists() else []
    if existing.exists():
        previous = json.loads(io_path(existing).read_text('utf-8'))
        history.append({k: v for k, v in previous.items() if k != 'history'})
    state = {'writing_id': writing_id, 'plan': plan, 'candidates': [], 'selected_reference': None,
             'submission': None, 'audit': None, 'history': history, 'status': 'REFERENCE_REQUIRED'}
    _save(root, state)
    return {'status': state['status'], 'plan': plan}


def register_writing_reference(root: str | Path, writing_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve(); state = _load(root, writing_id)
    for field in ('paper_id', 'title', 'selection_rationale'):
        _text(candidate.get(field), field)
    _https(candidate.get('primary_url', ''))
    try:
        published = dt.date.fromisoformat(candidate.get('published_on', ''))
    except (ValueError, TypeError) as exc:
        raise ReferenceWritingError('Reference needs its verified actual publication date') from exc
    if published > dt.date.today():
        raise ReferenceWritingError('Future publication dates are not already-published evidence')
    paper_name, paper_path = _file(root, candidate.get('paper_file', ''))
    text_name, text_path = _file(root, candidate.get('text_file', ''))
    text_path.read_text('utf-8')
    similarity = candidate.get('similarity', {})
    if set(similarity) != {'research_object', 'research_method', 'research_content'}:
        raise ReferenceWritingError('Object, method and content similarity must be assessed separately')
    for item in similarity.values():
        for field in ('experiment_anchor', 'paper_anchor', 'explanation'):
            _text(item.get(field), 'similarity.' + field)
    evidence = {key: _evidence(root, item) for key, item in candidate.get('evidence', {}).items()}
    if not {'identity', 'publication_date'} <= set(evidence):
        raise ReferenceWritingError('Bind primary identity and publication-date evidence')
    qualification = candidate.get('qualification', {})
    routes = []
    citations = qualification.get('citation_count')
    if (type(qualification.get('cas_zone')) is int and qualification.get('cas_zone') == 1 and type(citations) is int and citations > 10
            and {'cas_partition', 'citation_count'} <= set(evidence)):
        _text(evidence['cas_partition'].get('edition'), 'CAS partition edition')
        _text(evidence['citation_count'].get('provider'), 'Citation-count provider')
        routes.append('CAS_ZONE_1_CITATIONS_GT_10')
    rank = qualification.get('ccf_rank')
    if (rank in {'A', 'B'} and qualification.get('award') in {
        'best_paper_nominee', 'best_student_paper_nominee', 'best_paper', 'best_student_paper',
    } and {'ccf_rank', 'award'} <= set(evidence)):
        _text(evidence['ccf_rank'].get('edition'), 'CCF list edition')
        routes.append('CCF_B_PLUS_BEST_PAPER_NOMINATION')
    if (rank == 'A' and qualification.get('presentation') in {'oral', 'plenary_oral'}
            and {'ccf_rank', 'presentation'} <= set(evidence)):
        _text(evidence['ccf_rank'].get('edition'), 'CCF list edition')
        routes.append('CCF_A_ORAL_PLUS')
    eligible = published >= dt.date.fromisoformat(state['plan']['publication_date_min']) and bool(routes)
    visual_items = candidate.get('figures_tables')
    if not isinstance(visual_items, list):
        raise ReferenceWritingError('Inventory every reference figure/table; use [] only for an actually visual-free reference')
    visual_ids = [item.get('id') for item in visual_items]
    if any(not i for i in visual_ids) or len(set(visual_ids)) != len(visual_ids):
        raise ReferenceWritingError('Reference figure/table IDs must be distinct')
    for item in visual_items:
        if item.get('kind') not in {'figure', 'table'}:
            raise ReferenceWritingError('Unknown visual item kind')
        for key in ('locator', 'function'):
            _text(item.get(key), 'reference visual ' + key)
    record = {**candidate, 'paper_file': paper_name, 'paper_sha256': _hash(paper_path),
              'text_file': text_name, 'text_sha256': _hash(text_path), 'evidence': evidence,
              'eligible': eligible, 'qualification_routes': routes}
    record['reference_sha256'] = _digest(record)
    state['candidates'].append(record)
    if eligible:
        if state.get('submission'): state.setdefault('submission_history', []).append(state['submission'])
        if state.get('audit'): state.setdefault('audit_history', []).append(state['audit'])
        state['selected_reference'] = record; state['submission'] = None; state['audit'] = None
        state['status'] = 'DRAFT_AND_ALIGNMENT_REQUIRED'
    _save(root, state)
    return {'status': 'ELIGIBLE_RECORDED' if eligible else 'NOT_ELIGIBLE', 'reference': record,
            'boundary': 'Evidence and eligibility fields are checked; the agent must actually read primary records and assess the three similarity dimensions. No rank, award, citation count or oral status is inferred from venue reputation.'}


def _current_sources(root: Path, state: dict[str, Any]) -> list[str]:
    changed = []
    tracked = list(state['plan']['experiment_sources'])
    ref = state.get('selected_reference')
    if ref:
        tracked += [{'file': ref['paper_file'], 'sha256': ref['paper_sha256']},
                    {'file': ref['text_file'], 'sha256': ref['text_sha256']}]
        tracked += list(ref['evidence'].values())
    for item in tracked:
        try:
            if _hash(_file(root, item['file'])[1]) != item['sha256']: changed.append(item['file'])
        except (OSError, ReferenceWritingError): changed.append(item['file'])
    return changed


def submit_reference_writing(root: str | Path, writing_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve(); state = _load(root, writing_id)
    if _current_sources(root, state):
        raise ReferenceWritingError('Sources changed; replan and requalify before drafting')
    reference = state.get('selected_reference')
    if reference is None:
        raise ReferenceWritingError('No qualified, source-bound reference has been selected')
    if bundle.get('plan_sha256') != state['plan']['plan_sha256'] or bundle.get('reference_sha256') != reference['reference_sha256']:
        raise ReferenceWritingError('Bundle must bind the exact plan and selected reference')
    artifacts = bundle.get('artifacts', {})
    missing = sorted(ARTIFACTS - set(artifacts))
    if missing:
        return {'status': 'DELIVERABLES_REQUIRED', 'missing': missing}
    tracked = []
    for name in artifacts.values():
        relative, path = _file(root, name); tracked.append({'file': relative, 'sha256': _hash(path)})
    draft = _file(root, artifacts['draft'])[1].read_text('utf-8')
    headings = [{'level': len(m.group(1)), 'title': m.group(2).strip()} for m in re.finditer(r'^(#{1,6})\s+(.+?)\s*$', draft, re.M)]
    expected = [{k: row[k] for k in ('level', 'title')} for row in state['plan']['outline']]
    if headings != expected:
        raise ReferenceWritingError('Existing outline titles, order and levels must remain exactly unchanged')
    manifest = json.loads(_file(root, artifacts['alignment_manifest'])[1].read_text('utf-8'))
    if manifest.get('draft_text') != artifacts['draft'] or manifest.get('reference_text') != reference['text_file']:
        raise ReferenceWritingError('Logic manifest must bind the actual reference and delivered draft')
    if manifest.get('draft_word_limits') != state['plan']['draft_word_limits']:
        raise ReferenceWritingError('Do not change the frozen whole-draft word budget')
    if manifest.get('protected_tokens', []) != state['plan'].get('protected_tokens', []):
        raise ReferenceWritingError('Do not delete the frozen protected information set')
    if _hash(_file(root, artifacts['logic_script'])[1]) != _hash(Path(__file__).with_name('writing_logic_verify.py')):
        raise ReferenceWritingError('Deliver the actual standalone logic verifier, not a no-op script')
    logic = verify_logic(root, manifest)
    unresolved = list(logic['failures'])
    matched_visuals = bundle.get('figure_table_mapping', [])
    if sorted(item.get('reference_id', '') for item in matched_visuals) != sorted(item['id'] for item in reference['figures_tables']):
        raise ReferenceWritingError('Every reference figure/table needs exactly one functional counterpart')
    for item in matched_visuals:
        _text(item.get('target_id'), 'visual target_id')
        for field in ('function_preserved', 'target_evidence_anchor', 'caption'):
            _text(item.get(field), 'visual mapping ' + field)
        relative, path = _file(root, item.get('file', '')); tracked.append({'file': relative, 'sha256': _hash(path)})
    if len({i['target_id'] for i in matched_visuals}) != len(matched_visuals):
        raise ReferenceWritingError('Figure/table counterparts must have distinct target identities')
    for field in ('whole_paper_change_map', 'claim_evidence', 'supplement_items'):
        if not isinstance(bundle.get(field), list):
            raise ReferenceWritingError(field + ' must be an explicit list')
    if sorted(i.get('section_id', '') for i in bundle['whole_paper_change_map']) != sorted(row['id'] for row in state['plan']['outline']):
        raise ReferenceWritingError('Explain consistency actions or justified no-change for every existing section')
    if not bundle['claim_evidence']:
        raise ReferenceWritingError('Register the draft claims and actual evidence; an empty list is not an audit')
    for item in bundle['whole_paper_change_map']:
        if item.get('section_id') not in {row['id'] for row in state['plan']['outline']}:
            raise ReferenceWritingError('Whole-paper consistency map names an unknown section')
        _text(item.get('explanation'), 'whole-paper consistency explanation')
    for item in bundle['claim_evidence']:
        _text(item.get('claim'), 'claim'); _text(item.get('source_locator'), 'claim evidence locator')
        name, path = _file(root, item.get('file', '')); tracked.append({'file': name, 'sha256': _hash(path)})
    for item in bundle['supplement_items']:
        _text(item.get('reference_logic_gap'), 'supplement gap'); _text(item.get('required_experiment_or_explanation'), 'required supplement')
        if item.get('status') not in {'needed', 'provided'}:
            raise ReferenceWritingError('Supplement status must not invent an already-completed experiment')
    # A real paper-kit compilation is required, not a PDF with a venue-looking title.
    kit = _evidence(root, bundle.get('paper_kit', {}))
    for field in ('venue', 'year', 'track', 'stage'):
        if not kit.get(field): raise ReferenceWritingError('Paper kit needs exact venue/year/track/stage')
    tracked.append({'file': kit['file'], 'sha256': kit['sha256']})
    compile_result = json.loads(_file(root, artifacts['compile_receipt'])[1].read_text('utf-8'))
    tex_name, tex = _file(root, compile_result.get('tex_file', ''))
    pdf = _file(root, artifacts['formatted_pdf'])[1]
    log_name, log = _file(root, compile_result.get('log_file', ''))
    tracked += [{'file': tex_name, 'sha256': _hash(tex)}, {'file': log_name, 'sha256': _hash(log)}]
    if (compile_result.get('status') != 'PASS' or compile_result.get('pdf_file') != artifacts['formatted_pdf']
            or compile_result.get('pdf_sha256') != _hash(pdf) or compile_result.get('tex_sha256') != _hash(tex)
            or compile_result.get('kit_sha256') != kit['sha256'] or not compile_result.get('command')):
        unresolved.append('PAPER_KIT_COMPILATION_REQUIRED')
    if not pdf.read_bytes().startswith(b'%PDF-'):
        raise ReferenceWritingError('Formatted PDF is not an actual PDF file')
    try:
        from pypdf import PdfReader
        if not len(PdfReader(pdf).pages): raise ValueError('empty PDF')
    except Exception as exc:
        raise ReferenceWritingError('Formatted PDF must parse and contain at least one page') from exc
    # Preserve true limitations; only actual defensive presentation patterns are flagged.
    paragraphs = re.split(r'\n\s*\n', draft)
    if any(IMAGINED_CRITIC.search(p) or DISCLAIMER_FIRST.search(p) or INTERNAL_PROCESS.search(p) for p in paragraphs):
        unresolved.append('DEFENSIVE_PROSE_REQUIRES_REVIEW')
    lean_execution = {'status': 'NOT_APPLICABLE_NO_MATHEMATICAL_REASONING'}
    if bundle.get('contains_math') is True:
        lean = bundle.get('lean', {})
        _text(lean.get('availability_evidence'), 'Lean availability evidence file')
        name, path = _file(root, lean['availability_evidence']); tracked.append({'file': name, 'sha256': _hash(path)})
        from dependency_manager import detect_existing, require, DependencyError
        detected = detect_existing('lean-mathlib')
        if lean.get('available') is True:
            name, path = _file(root, lean.get('file', '')); tracked.append({'file': name, 'sha256': _hash(path)})
            if path.suffix != '.lean': raise ReferenceWritingError('One whole-manuscript .lean file is required')
            proof = json.loads(_file(root, lean.get('receipt', ''))[1].read_text('utf-8'))
            if proof.get('status') != 'PASS' or proof.get('lean_sha256') != _hash(path):
                unresolved.append('WHOLE_MANUSCRIPT_LEAN_VERIFICATION_REQUIRED')
            lean_file = path
            command = None
            try:
                registered = require('lean-mathlib')['executables']
                command = [registered['lake'], 'env', 'lean', str(lean_file)]
                lean_cwd = Path(registered['runtime_root'])
            except DependencyError:
                unresolved.append('LEAN_REGISTERED_ENVIRONMENT_REQUIRED')
            if command:
                try:
                    execution = subprocess.run(command, cwd=lean_cwd, capture_output=True,
                                               text=True, encoding='utf-8', errors='replace', timeout=120)
                    lean_execution = {'status': 'PASS' if execution.returncode == 0 else 'FAIL',
                                      'command': command, 'returncode': execution.returncode,
                                      'stdout': execution.stdout, 'stderr': execution.stderr, 'lean_sha256': _hash(lean_file)}
                    if execution.returncode: unresolved.append('WHOLE_MANUSCRIPT_LEAN_COMPILATION_FAILED')
                    if re.search(r'\b(sorry|admit|axiom)\b', lean_file.read_text('utf-8')):
                        unresolved.append('LEAN_UNPROVED_ASSUMPTIONS_REQUIRE_REMOVAL')
                except (OSError, subprocess.TimeoutExpired) as exc:
                    lean_execution = {'status': 'FAIL', 'error': str(exc)}
                    unresolved.append('WHOLE_MANUSCRIPT_LEAN_COMPILATION_FAILED')
            name, path = _file(root, lean['receipt']); tracked.append({'file': name, 'sha256': _hash(path)})
        elif lean.get('available') is False:
            if detected.get('available') or shutil.which('lean'):
                unresolved.append('LEAN_AVAILABLE_BUT_DECLARED_UNAVAILABLE')
            lean_execution = {'status': 'NOT_RUN_UNAVAILABLE', 'conditional_delivery_required': False,
                              'boundary': 'No Lean executable found on the current PATH; preserve the actual environment inventory. This is not a verified theorem.'}
        else:
            unresolved.append('LEAN_AVAILABILITY_NOT_VERIFIED')
    elif bundle.get('contains_math') is not False:
        raise ReferenceWritingError('Declare whether the manuscript contains mathematical reasoning')
    if state.get('submission'): state.setdefault('submission_history', []).append(state['submission'])
    if state.get('audit'): state.setdefault('audit_history', []).append(state['audit'])
    state['submission'] = {'bundle': bundle, 'tracked': tracked, 'logic_result': logic, 'unresolved': unresolved,
                           'lean_execution': lean_execution,
                           'draft_sha256': _hash(_file(root, artifacts['draft'])[1])}
    state['audit'] = None; state['status'] = 'CORRECTION_REQUIRED' if unresolved else 'THREE_AGENT_AUDIT_REQUIRED'
    _save(root, state)
    return {'status': state['status'], 'unresolved': unresolved, 'logic_result': logic,
            'lean_execution': lean_execution,
            'boundary': 'The compilation receipt is a recorded execution attestation; the agent must actually compile the exact kit and inspect the exported PDF. Structural verification is not semantic proof.'}


def audit_reference_writing(root: str | Path, writing_id: str, reviews: list[dict[str, Any]]) -> dict[str, Any]:
    root = Path(root).resolve(); state = _load(root, writing_id)
    if get_reference_writing_status(root, writing_id)['status'] in {'REPLAN_REQUIRED', 'RESUBMIT_REQUIRED'}:
        raise ReferenceWritingError('Current source or delivery evidence changed')
    submission = state.get('submission')
    if not submission: raise ReferenceWritingError('Submit actual writing deliverables before review')
    if not isinstance(reviews, list) or len(reviews) != 3 or {r.get('role') for r in reviews} != set(ROLES):
        raise ReferenceWritingError('Exactly three logic/defensive/scientific agent reviews are required')
    agents = [r.get('agent_id') for r in reviews]
    if any(not a for a in agents) or len(set(agents)) != 3:
        raise ReferenceWritingError('The three reviewers must have distinct actual agent identities')
    tracked = []
    failures = list(submission['unresolved'])
    for review in reviews:
        if (review.get('draft_sha256') != submission['draft_sha256']
                or review.get('reference_sha256') != state['selected_reference']['reference_sha256']):
            raise ReferenceWritingError('Review must bind the exact draft and qualified reference')
        checks = review.get('checks')
        if not isinstance(checks, dict) or set(checks) != ROLES[review['role']] or any(type(v) is not bool for v in checks.values()):
            raise ReferenceWritingError('Review checks must explicitly cover the whole role as booleans')
        if not isinstance(review.get('issues'), list): raise ReferenceWritingError('Keep actual issue lists')
        if not all(checks.values()) or review['issues']: failures.append(review['role'])
        name, path = _file(root, review.get('dialogue_file', '')); tracked.append({'file': name, 'sha256': _hash(path)})
    result = {'status': 'CORRECTION_REQUIRED' if failures else 'PASS', 'unresolved': failures,
              'reviews': reviews, 'tracked': tracked, 'draft_sha256': submission['draft_sha256'],
              'semantic_equivalence_proved': False, 'reference_sha256': state['selected_reference']['reference_sha256']}
    result['receipt_sha256'] = _digest(result)
    if state.get('audit'): state.setdefault('audit_history', []).append(state['audit'])
    state['audit'] = result; state['status'] = result['status']
    _save(root, state); return result


def get_reference_writing_status(root: str | Path, writing_id: str) -> dict[str, Any]:
    root = Path(root).resolve()
    if not _path(root, writing_id).exists(): return {'status': 'NOT_PLANNED', 'writing_id': writing_id}
    state = _load(root, writing_id)
    changed = _current_sources(root, state)
    if changed: return {'status': 'REPLAN_REQUIRED', 'changed_sources': changed}
    for record in [state.get('submission'), state.get('audit')]:
        for item in (record or {}).get('tracked', []):
            try:
                if _hash(_file(root, item['file'])[1]) != item['sha256']: changed.append(item['file'])
            except (OSError, ReferenceWritingError): changed.append(item['file'])
    if changed: return {'status': 'RESUBMIT_REQUIRED', 'changed_evidence': changed}
    return {'status': state['status'], 'writing_id': writing_id, 'plan_sha256': state['plan']['plan_sha256'],
            'candidates': [{'paper_id': c['paper_id'], 'eligible': c['eligible'], 'routes': c['qualification_routes']} for c in state['candidates']],
            'selected_reference': (state.get('selected_reference') or {}).get('paper_id'),
            'unresolved': (state.get('submission') or {}).get('unresolved', []), 'receipt': state.get('audit'),
            'lean_execution': (state.get('submission') or {}).get('lean_execution'),
            'boundary': 'PASS is evidence-bound workflow acceptance with recorded agent attestations, not a theorem of semantic equivalence or scientific truth.'}


def verify_reference_writing(root: str | Path, writing_id: str) -> dict[str, Any]:
    return get_reference_writing_status(root, writing_id)
