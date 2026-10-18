"""Synthetic structural fixtures; PASS never establishes semantic equivalence."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
from writing_logic_verify import LEVELS, units, verify

TEXT='# Introduction\n\nSynthetic evidence may support a limited claim.\n\n## Method\n\nThe toy protocol uses fixed records.\n'

def full_manifest(reference=TEXT,draft=TEXT):
    """Each reference word/sentence/paragraph is an individual mapped unit."""
    rows=[]
    for level in LEVELS:
        if level in ('between_words','within_sentence','within_paragraph'):
            source_units=units(reference,level);target_units=units(draft,level)
            if len(source_units)!=len(target_units):raise ValueError('Fixture requires matched unit counts')
            for i,(source,target) in enumerate(zip(source_units,target_units)):
                rows.append({'id':level+str(i),'level':level,'reference_span':list(source),'draft_span':list(target),'logic_move':'Synthetic unit correspondence','explanation':'These synthetic units have deliberately matched structure; a human must still assess meaning.'})
        else:
            rows.append({'id':level,'level':level,'reference_span':[0,len(reference)],'draft_span':[0,len(draft)],'logic_move':'Synthetic whole-text structural relation','explanation':'Explicit test fixture; structural coverage does not prove scientific or semantic fidelity.'})
    return {'reference_text':'reference.txt','draft_text':'draft.md','reference_scope':[[0,len(reference)]],'draft_scope':[[0,len(draft)]],'alignments':rows,'reference_edges':[{'source':'section_internal','target':'between_subsections','relation':'precedes'}],'draft_edges':[{'source':'section_internal','target':'between_subsections','relation':'precedes'}],'draft_word_limits':[1,100],'protected_tokens':['may']}

class WritingLogicVerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'reference.txt').write_text(TEXT,encoding='utf-8')
        (self.root/'draft.md').write_text(TEXT,encoding='utf-8')
        self.manifest=full_manifest()
    def tearDown(self):self.temp.cleanup()
    def rejected_or_correction(self,manifest,substring=None):
        try:result=verify(self.root,manifest)
        except (ValueError,KeyError):return
        self.assertNotEqual(result['status'],'PASS',result)
        if substring:self.assertTrue(any(substring in f for f in result['failures']),result)
    def test_full_eleven_level_mapping_passes_without_semantic_proof(self):
        result=verify(self.root,self.manifest)
        self.assertEqual(result['status'],'PASS')
        self.assertFalse(result['semantic_equivalence_proved'])
        self.assertEqual(len(result['coverage']),6)
        self.assertTrue(all(not row['uncovered_offsets'] and row['tokens']>0 for row in result['coverage'].values()))
    def test_cli_executes_actual_verifier_and_writes_receipt(self):
        manifest=self.root/'alignment.json';manifest.write_text(json.dumps(self.manifest),encoding='utf-8')
        output=self.root/'result.json'
        process=subprocess.run([sys.executable,str(REPO/'scripts/writing_logic_verify.py'),str(manifest),'--project-root',str(self.root),'--output',str(output)],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(output.read_text('utf-8'))['status'],'PASS')
    def test_missing_level_rejected(self):
        self.manifest['alignments']=[r for r in self.manifest['alignments'] if r['level']!='long_range_correspondence']
        self.rejected_or_correction(self.manifest)
    def test_missing_single_word_fails_full_coverage(self):
        row=next(r for r in self.manifest['alignments'] if r['level']=='between_words')
        self.manifest['alignments'].remove(row)
        self.rejected_or_correction(self.manifest,'INCOMPLETE_COVERAGE')
    def test_empty_scopes_cannot_vacuously_pass_full_coverage(self):
        self.manifest['reference_scope']=[];self.manifest['draft_scope']=[]
        self.rejected_or_correction(self.manifest)
    def test_shortened_scopes_cannot_replace_a_whole_text_mapping(self):
        self.manifest['reference_scope']=[[0,14]];self.manifest['draft_scope']=[[0,14]]
        self.manifest['alignments']=[r for r in self.manifest['alignments'] if r['level'] not in ('between_words','within_sentence','within_paragraph') or r['reference_span'][1]<=14]
        # Keep every level explicit to isolate coverage from the level-set gate.
        self.rejected_or_correction(self.manifest)
    def test_whole_draft_span_cannot_pretend_to_be_one_word(self):
        for row in self.manifest['alignments']:
            if row['level']=='between_words':row['draft_span']=[0,len(TEXT)]
        self.rejected_or_correction(self.manifest)
    def test_completely_duplicate_word_pairs_rejected(self):
        duplicate=copy.deepcopy(next(r for r in self.manifest['alignments'] if r['level']=='between_words'))
        duplicate['id']='duplicate-word-pair';self.manifest['alignments'].append(duplicate)
        self.rejected_or_correction(self.manifest)
    def test_different_word_counts_can_use_distinct_many_to_one_pairs(self):
        draft=TEXT.replace('Synthetic evidence','Explicit synthetic evidence')
        (self.root/'draft.md').write_text(draft,encoding='utf-8')
        manifest=full_manifest();manifest['draft_scope']=[[0,len(draft)]]
        for row in manifest['alignments']:
            if row['level'] not in ('between_words','within_sentence','within_paragraph'):row['draft_span']=[0,len(draft)]
        for level in ('between_words','within_sentence','within_paragraph'):
            manifest['alignments']=[row for row in manifest['alignments'] if row['level']!=level]
            source=units(TEXT,level);target=units(draft,level)
            for i in range(max(len(source),len(target))):
                manifest['alignments'].append({'id':level+str(i),'level':level,'reference_span':list(source[min(i,len(source)-1)]),'draft_span':list(target[min(i,len(target)-1)]),'logic_move':'Synthetic differing-length mapping','explanation':'Distinct canonical pairs demonstrate structural cardinality support, not semantic adequacy of these arbitrary fixture pairings.'})
        self.assertEqual(verify(self.root,manifest)['status'],'PASS')
    def test_changed_relation_is_detected(self):
        self.manifest['draft_edges'][0]['relation']='contrasts'
        self.rejected_or_correction(self.manifest,'LOGIC_RELATIONS_CHANGED')
    def test_cyclic_precedence_is_detected(self):
        edge={'source':'between_subsections','target':'section_internal','relation':'precedes'}
        self.manifest['reference_edges'].append(edge);self.manifest['draft_edges'].append(copy.deepcopy(edge))
        self.rejected_or_correction(self.manifest,'CYCLIC_PRECEDENCE')
    def test_word_budget_and_protected_information_are_enforced(self):
        self.manifest['draft_word_limits']=[1,2]
        self.rejected_or_correction(self.manifest,'WORD_BUDGET_EXCEEDED')
        self.manifest['draft_word_limits']=[1,100];self.manifest['protected_tokens']=['nonexistent-protected-result']
        self.rejected_or_correction(self.manifest,'PROTECTED_INFORMATION_MISSING')
    def test_invalid_unicode_span_and_external_paths_rejected(self):
        self.manifest['alignments'][0]['draft_span']=[False,2]
        self.rejected_or_correction(self.manifest)
        self.manifest=full_manifest();self.manifest['draft_text']='../outside.md'
        self.rejected_or_correction(self.manifest)

if __name__=='__main__':unittest.main()
