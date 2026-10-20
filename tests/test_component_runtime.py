"""Check observable isolation, capability discovery, and omitted routes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import component_runtime as runtime
import mcp_server


class ComponentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patch=patch.object(runtime,'ROOT',self.root);self.patch.start()
    def tearDown(self):
        self.patch.stop();self.temp.cleanup()
    def receipt(self,*groups):
        item={'resolved_components':['core',*groups]}
        item['receipt_sha256']=hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        (self.root/'COMPONENT_INSTALL.json').write_text(json.dumps(item),encoding='utf-8')
    def test_stdio_startup_does_not_import_optional_modules_without_site_packages(self):
        code=f'import sys;sys.path.insert(0,{str(SCRIPTS)!r});import mcp_server,json;print(json.dumps(sorted(sys.modules)))'
        result=subprocess.run([sys.executable,'-I','-S','-c',code],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        modules=json.loads(result.stdout)
        for module in ('numpy','matplotlib','networkx','sympy','yaml','academic_figure_core','language_guard_core','frontier_analysis_core'):
            self.assertNotIn(module,modules)
    def test_core_lists_only_installed_actions_and_rejects_omitted_calls(self):
        self.receipt()
        tools={x['name']:x for x in runtime.available_tools(mcp_server.TOOLS)}
        self.assertNotIn('paper_audit',tools);self.assertNotIn('language_assist',tools)
        properties=tools['research_design']['inputSchema']['properties']
        self.assertIn('instruction_action',properties);self.assertNotIn('metrics_action',properties)
        with self.assertRaisesRegex(runtime.ComponentError,'experiments'):
            mcp_server.dispatch('research_design',{'action':'status','metrics_action':'analyze'})
    def test_foreign_subaction_is_rejected_even_alongside_an_installed_one(self):
        self.receipt('literature')
        with self.assertRaisesRegex(runtime.ComponentError,'figures'):
            runtime.check_call('paper_audit',{'action':'status','citation_action':'verify_format','figure_action':'render'})
    def test_semantic_module_selection_cannot_select_uninstalled_workflow(self):
        self.receipt('literature')
        visible=runtime.filter_modules(mcp_server._all_research_modules())
        self.assertIn('research_novelty',{x['id'] for x in visible['modules']})
        self.assertNotIn('academic_figure',{x['id'] for x in visible['modules']})
        with self.assertRaises(runtime.ComponentError):
            runtime.check_call('select_research_modules',{'selected_modules':['academic_figure']})
    def test_corrupt_receipt_fails_closed(self):
        self.receipt('literature')
        path=self.root/'COMPONENT_INSTALL.json';data=json.loads(path.read_text());data['resolved_components'].append('figures');path.write_text(json.dumps(data))
        with self.assertRaisesRegex(runtime.ComponentError,'RECEIPT_INVALID'):runtime.installed_components()
    def test_formal_only_exposes_and_authorizes_common_audit_lifecycle(self):
        self.receipt('formal')
        runtime.check_call('paper_audit',{'action':'plan'})
        tool=next(t for t in runtime.available_tools(mcp_server.TOOLS) if t['name']=='paper_audit')
        self.assertIn('plan',tool['inputSchema']['properties']['action']['enum'])
    def test_invalid_subaction_cannot_authorize_base_workflow(self):
        self.receipt('literature')
        with self.assertRaisesRegex(runtime.ComponentError,'INVALID_ACTION'):
            mcp_server.dispatch('paper_audit',{'action':'plan','integrity_action':'not_a_valid_action'})
        self.assertFalse((self.root/'.research-guard').exists())
    def test_source_checkout_retains_legacy_api(self):
        self.assertIsNone(runtime.installed_components())
        self.assertEqual(runtime.available_tools(mcp_server.TOOLS),mcp_server.TOOLS)
    def test_native_client_structured_content_always_has_object_shape(self):
        self.receipt('literature')
        result=mcp_server.handle({'jsonrpc':'2.0','id':1,'method':'tools/call',
                                 'params':{'name':'list_sources','arguments':{}}})['result']
        self.assertFalse(result['isError'])
        self.assertIsInstance(result['structuredContent'],dict)
        self.assertIsInstance(result['structuredContent']['items'],list)
        self.assertEqual(json.loads(result['content'][0]['text']),result['structuredContent']['items'])

    def test_selected_dependency_query_reports_actual_optional_probes_without_legacy_core(self):
        self.receipt()
        with patch.dict('os.environ', {'RESEARCH_GUARD_HOME': str(self.root/'private-home')}):
            value=mcp_server.dispatch('research_design', {'action':'status','project_root':str(self.root),
                                                        'dependency_action':'inventory'})
        self.assertIn('components',value)
        optional={item['id']:item for item in value['components']}
        self.assertTrue({'portable-git','tex-basic','lean-mathlib'} <= set(optional))
        self.assertNotIn('core-runtime',optional)
        self.assertIn('available',optional['portable-git']['detected_existing'])
        self.assertEqual(value['installed_components'],['core'])
        self.assertFalse(value['first_load_pending'])

    def test_core_tool_preflight_does_not_probe_optional_host_environments(self):
        self.receipt()
        with patch.object(mcp_server,'_legacy_dependency_inventory',side_effect=AssertionError('unexpected optional probe')):
            result=mcp_server.handle({'jsonrpc':'2.0','id':2,'method':'tools/call',
                                     'params':{'name':'list_research_modules','arguments':{}}})['result']
        self.assertFalse(result['isError'])


if __name__=='__main__':unittest.main()
