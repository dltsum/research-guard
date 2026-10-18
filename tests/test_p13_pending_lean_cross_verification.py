"""Independent four-route work must run without inventing a Lean user decision."""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
import dependency_manager
import mcp_server
from paper_audit_core import AuditError, submit_paper_audit

class PendingLeanCrossVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.old_home=os.environ.get('RESEARCH_GUARD_HOME')
        os.environ['RESEARCH_GUARD_HOME']=str(self.root/'dependency-home')
        dependency_manager.register_core(Path(sys.prefix))
        model=self.root/'model.py'
        model.write_text("def evaluate(parameters):\n    return float(parameters['x'])\n",encoding='utf-8')
        self.payload={'applicability':{name:{'status':'required'} for name in ('lean','dimensional','symbolic','constraints','numerical_protocol')},'dimensional_checks':[{'id':'D','source':'Eq1','lhs_units':'meter / second','rhs_units':'kilometer / hour'}],'symbolic_checks':[{'id':'S','source':'Eq2','lhs':'x+x','rhs':'2*x','symbols':[{'name':'x','assumptions':{'real':True}}]}],'constraint_checks':[{'id':'C','source':'Protocol','parameters':[{'name':'x','type':'real'}],'constraints':[{'op':'>=','args':[{'var':'x'},0]},{'op':'<=','args':[{'var':'x'},1]}]}],'numerical_protocol':{'protocol_id':'P','source':'Protocol','model_script':'model.py','model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'entrypoint':'evaluate','parameters':{'x':{'type':'number','minimum':0,'maximum':1}},'constraints':[{'op':'>=','args':[{'var':'x'},0]}],'cases':[{'id':'boundary','kind':'boundary','parameters':{'x':0},'expected':{'finite':True,'value':0,'abs_tolerance':0}},{'id':'limit','kind':'limit','sequence':[{'x':.9},{'x':.99},{'x':1.0}],'expected':{'target':1,'abs_tolerance':0}},{'id':'overflow','kind':'overflow','parameters':{'x':1},'expected':{'finite':True,'maximum':1}}]}}
        mcp_server.dispatch('paper_audit',{'project_root':str(self.root),'action':'plan','request_text':'Verify all five formula routes honestly.','selected_roles':['formal_math_lean','adversarial_logic'],'audit_features':{'formula':True},'selected_by':'main_agent','selection_rationale':'Formal and adversarial roles cover all required formula routes and scientific boundaries.'})

    def tearDown(self):
        if self.old_home is None:os.environ.pop('RESEARCH_GUARD_HOME',None)
        else:os.environ['RESEARCH_GUARD_HOME']=self.old_home
        self.temp.cleanup()

    def execute(self,payload=None):
        return mcp_server.dispatch('paper_audit',{'project_root':str(self.root),'action':'status','verification_action':'cross_verify','verification_manifest':payload or self.payload,'process_timeout_seconds':90})

    def assert_four_pass(self,result):
        self.assertEqual(set(result['results']),{'lean','dimensional','symbolic','constraints','numerical_protocol'})
        for channel in ('dimensional','symbolic','constraints','numerical_protocol'):
            self.assertEqual(result['results'][channel]['status'],'PASS',result)
        self.assertTrue(result['resource_usage'])

    def test_unresolved_real_dependency_choice_runs_four_and_blocks_final(self):
        before=dependency_manager.component_need('lean-mathlib')
        self.assertEqual(before['status'],'USER_DECISION_REQUIRED')
        result=self.execute()
        self.assert_four_pass(result)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['results']['lean']['status'],'NOT_RUN_DEPENDENCY_DECISION_REQUIRED')
        self.assertEqual(dependency_manager.component_need('lean-mathlib')['status'],'USER_DECISION_REQUIRED')
        with self.assertRaisesRegex(AuditError,'Lean formula audit is required'):
            submit_paper_audit(self.root,role_reports=[{'role':role,'findings':['test-only guard check'],'numeric_checks':['test-only route output checked']} for role in ('formal_math_lean','adversarial_logic')],online_checks=[{'claim':'Test-only structured precondition, not live scholarly evidence','url':'https://example.org/test-only','accessed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'source_type':'test fixture','status':'verified'}])

    def test_explicit_not_now_retains_existing_degraded_semantics(self):
        dependency_manager.decline('lean-mathlib')
        result=self.execute()
        self.assert_four_pass(result)
        self.assertEqual(result['status'],'DEGRADED')
        self.assertEqual(result['results']['lean']['status'],'NOT_RUN_BY_USER')

    def test_selected_but_missing_lean_is_not_a_user_opt_out(self):
        # Stub only the dependency inventory state; all four mathematical workers
        # execute normally. No compiler success or worker result is mocked.
        original=dependency_manager.component_need
        with patch.object(dependency_manager,'component_need',side_effect=lambda name: {'status':'INSTALL_INCOMPLETE','choices':[]} if name=='lean-mathlib' else original(name)):
            result=self.execute()
        self.assert_four_pass(result)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['results']['lean']['status'],'NOT_RUN_DEPENDENCY_DECISION_REQUIRED')

    def test_available_compiler_without_manuscript_check_still_blocks(self):
        original=dependency_manager.component_need
        with patch.object(dependency_manager,'component_need',side_effect=lambda name: {'status':'AVAILABLE','choices':[]} if name=='lean-mathlib' else original(name)):
            result=self.execute()
        self.assert_four_pass(result)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['results']['lean']['status'],'NOT_RUN_COMPILATION_REQUIRED')

    def test_pending_lean_cannot_hide_four_route_failures(self):
        payload=copy.deepcopy(self.payload)
        payload['numerical_protocol']['cases'][0]['parameters']['x']=-1
        result=self.execute(payload)
        self.assertEqual(result['status'],'BLOCKED')
        numerical=result['results']['numerical_protocol']
        self.assertEqual(numerical['status'],'FAIL')
        self.assertEqual(numerical['checks'][0]['protocol_legality'][0]['status'],'PROTOCOL_VIOLATION')

    def test_declined_lean_cannot_hide_four_route_failures(self):
        dependency_manager.decline('lean-mathlib')
        payload=copy.deepcopy(self.payload)
        payload['dimensional_checks'][0]['rhs_units']='kilogram'
        result=self.execute(payload)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['results']['dimensional']['status'],'FAIL')
        self.assertEqual(result['results']['lean']['status'],'NOT_RUN_BY_USER')

if __name__=='__main__':unittest.main()
