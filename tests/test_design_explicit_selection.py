from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import research_design_core as core


class ExplicitDesignSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'project'
        self.reason = 'Main agent explicitly selects these lenses for a bounded historical coverage audit.'

    def plan(self, **updates):
        args = dict(request_text='keyword constraint budget stakeholder tension boundary risk',
                    problem='Audit an existing dataset without choosing a scientific winner.',
                    selected_lens_ids=['structural_analogy', 'abstraction'],
                    design_selected_by='main_agent', design_selection_rationale=self.reason)
        args.update(updates)
        return core.plan_ideation(self.root, **args)

    def commit(self):
        plan = self.plan()
        item = {'candidate_id': 'I1', 'title': 'Coverage census', 'problem': 'Audit coverage',
          'mechanism': 'Join exact source keys', 'falsifier': 'Duplicate keys or hash mismatch',
          'minimum_viable_experiment': 'Recompute the existing CSV census',
          'differentiator': 'Operational replay, not a novel scientific claim', 'feasibility': 'Serial CPU only',
          'lens_id': 'abstraction', 'prior_work': []}
        core.register_candidates(self.root, plan_hash=plan['plan_hash'], candidates=[item])
        core.commit_candidate(self.root, candidate_id='I1', selected_by='user',
                              method={key:item[key] for key in ['title','problem','mechanism']})

    def test_missing_choice_returns_catalog_without_creating_project(self):
        result = core.plan_ideation(self.root, request_text='boundary budget risk', problem='Explicit selection required')
        self.assertEqual(result['status'], 'SELECTION_REQUIRED')
        self.assertIn('structural_analogy', [x['lens_id'] for x in result['available_choices']])
        self.assertFalse(self.root.exists())

    def test_explicit_lenses_override_all_keywords_in_declared_order(self):
        result = self.plan()
        self.assertEqual(result['selected_lens_ids'], ['structural_analogy', 'abstraction'])
        self.assertFalse(result['automatic_lens_selection'])
        self.assertNotIn('match_score', result['selected_lenses'][0])

    def test_invalid_choices_fail_before_state_creation(self):
        for ids in [[], ['abstraction']*2, ['abstraction','unknown'], 'abstraction']:
            with self.subTest(ids=ids), self.assertRaises(core.DesignError):
                self.plan(selected_lens_ids=ids)
        self.assertFalse(self.root.exists())

    def test_single_lens_and_brief_or_omitted_reason_work(self):
        result = self.plan(selected_lens_ids=['abstraction'], design_selected_by='', design_selection_rationale='')
        self.assertEqual(result['selected_lens_ids'], ['abstraction'])
        self.assertEqual(result['selection']['selected_by'], 'main_agent')
        self.assertEqual(self.plan(design_selection_rationale='简明')['selection']['rationale'], '简明')

    def test_unknown_selector_type_is_still_invalid(self):
        for value in ['classifier', [], {}, None]:
            with self.subTest(value=value), self.assertRaises(core.DesignError):
                self.plan(design_selected_by=value)

    def test_selection_metadata_can_be_updated_without_seal_validation(self):
        first = self.plan()
        self.assertEqual(first['plan_hash'], self.plan()['plan_hash'])
        changed = self.plan(design_selection_rationale=self.reason + ' Frozen replay only.')
        self.assertNotEqual(first['plan_hash'], changed['plan_hash'])
        state = json.loads(core.design_state_path(self.root).read_text(encoding='utf8'))
        state['plan']['selection']['selected_by'] = 'user'
        core._save_design(self.root, state)
        self.assertEqual(core.get_research_design_status(self.root)["status"], "CANDIDATE_SELECTION_REQUIRED")

    def test_strategy_also_requires_explicit_selection_without_mutation(self):
        self.commit()
        before = core.design_state_path(self.root).read_bytes()
        pending = core.plan_strategy(self.root, request_text='risk parameters adversity')
        self.assertEqual(pending['status'], 'SELECTION_REQUIRED')
        self.assertEqual(core.design_state_path(self.root).read_bytes(), before)
        chosen = core.plan_strategy(self.root, request_text='risk parameters adversity',
                 selected_strategy_module_ids=['objective', 'inversion'], design_selected_by='main_agent',
                 design_selection_rationale='Main agent explicitly maps objectives and alternative operational questions.')
        self.assertEqual(chosen['selected_module_ids'], ['objective','inversion'])
        self.assertFalse(chosen['automatic_strategy_module_selection'])

    def test_legacy_plan_does_not_require_replanning_for_missing_provenance(self):
        self.plan()
        state = json.loads(core.design_state_path(self.root).read_text(encoding='utf8'))
        state['plan'].pop('selection')
        stable = {key:state['plan'][key] for key in ['request_text','problem_anchor','constraints','selected_lens_ids','effort_cap']}
        state['plan']['plan_hash'] = core.digest(stable)
        core._save_design(self.root, state)
        result = core.get_research_design_status(self.root)
        self.assertEqual(result['status'], 'CANDIDATE_SELECTION_REQUIRED')

    def test_mcp_schema_and_dispatch_accept_explicit_parameters(self):
        import mcp_server
        tool = next(t for t in mcp_server.TOOLS if t['name']=='research_design')
        props = tool['inputSchema']['properties']
        self.assertEqual(props['selected_lens_ids']['minItems'], 1)
        self.assertNotIn('maxItems', props['selected_strategy_module_ids'])
        result = mcp_server.dispatch('research_design', {'action':'plan_ideation','project_root':str(self.root),
              'request_text':'boundary risk', 'problem':'Explicit audit scope',
              'selected_lens_ids':['abstraction','structural_analogy'],
              'design_selected_by':'main_agent','design_selection_rationale':self.reason})
        self.assertEqual(result['selected_lens_ids'], ['abstraction','structural_analogy'])


if __name__ == '__main__':
    unittest.main()
