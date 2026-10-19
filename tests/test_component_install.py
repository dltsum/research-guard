from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from component_install import ComponentInstallError, dependency_closure, install_components, installation_plan, load_manifest, verify_installation, _clean_env, _runtime_path, _run

class ComponentInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.source=self.base/'source';self.target=self.base/'installed'
        for path,text in {'LICENSE':'fixture license','scripts/core.py':'# stdlib fixture\n','scripts/extra.py':'# unselected code\n','.codex-plugin/plugin.json':'{"name":"fixture","interface":{}}','assets/payloads/unselected-large.bin':'DO NOT COPY'*20000,'skills/literature/SKILL.md':'literature fixture','skills/literature/cache.pdf':'not redistributable PDF','skills/literature/__pycache__/cache.py':'excluded','assets/feature-components.json':'{}'}.items():
            p=self.source/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
        self.manifest={'schema_version':1,'components':{
            'core':{'label':'core','depends_on':[],'modules':['core'],'files':['LICENSE','scripts/core.py','.codex-plugin/plugin.json','assets/feature-components.json'],'python_requirements':[]},
            'literature':{'label':'literature','depends_on':['core'],'modules':[],'files':['skills/literature/'],'python_requirements':[]},
            'figures':{'label':'figures','depends_on':['core'],'modules':['extra'],'files':['scripts/extra.py'],'python_requirements':['numpy==2.4.4']},
            'research':{'label':'research','depends_on':['literature'],'modules':[],'files':[],'python_requirements':[]}},
            'excluded_path_parts':['__pycache__'],'directory_suffix_allowlist':['.py','.md','.json']}
        self.write_manifest()
    def write_manifest(self):
        (self.source/'assets/feature-components.json').write_text(json.dumps(self.manifest),encoding='utf-8')
    def install(self,selected=None,**kwargs):return install_components(self.source,self.target,selected or ['core'],**kwargs)
    def test_no_selection_does_not_create_target_or_call_network(self):
        with patch('component_install._run',side_effect=AssertionError('must not execute')):
            result=install_components(self.source,self.target,[])
        self.assertEqual(result['status'],'SELECTION_REQUIRED');self.assertFalse(self.target.exists());self.assertEqual(result['files'],[])
    def test_dependency_closure_is_explicit_and_topological(self):
        self.assertEqual(dependency_closure(self.manifest,['research']),['core','literature','research'])
        self.assertNotIn('figures',dependency_closure(self.manifest,['research']))
    def test_core_install_omits_unselected_large_payload_and_code(self):
        with patch('component_install._run',side_effect=AssertionError('core must not execute installers')):
            result=self.install()
        self.assertEqual(result['python_dependency_status'],'NOT_REQUIRED_STDLIB')
        self.assertFalse((self.target/'assets/payloads').exists());self.assertFalse((self.target/'scripts/extra.py').exists())
        self.assertFalse((self.target/'skills/literature').exists());self.assertEqual(verify_installation(self.target)['status'],'PASS')
    def test_directory_component_filters_binaries_and_cache(self):
        self.install(['literature'])
        self.assertTrue((self.target/'skills/literature/SKILL.md').is_file())
        self.assertFalse((self.target/'skills/literature/cache.pdf').exists())
        self.assertFalse((self.target/'skills/literature/__pycache__').exists())
    def test_idempotent_reinstall_has_no_copy_no_network_and_preserves_receipt(self):
        self.install();receipt=(self.target/'COMPONENT_INSTALL.json').read_bytes();mtime=(self.target/'scripts/core.py').stat().st_mtime_ns
        with patch('component_install._run',side_effect=AssertionError('must not execute')):result=self.install()
        self.assertEqual(result['status'],'UNCHANGED');self.assertEqual(result['copied_files'],0);self.assertEqual(result['network_operations'],0)
        self.assertEqual((self.target/'COMPONENT_INSTALL.json').read_bytes(),receipt);self.assertEqual((self.target/'scripts/core.py').stat().st_mtime_ns,mtime)
    def test_modified_installed_file_is_rejected_not_overwritten(self):
        self.install();p=self.target/'scripts/core.py';p.write_text('user change',encoding='utf-8')
        self.assertEqual(verify_installation(self.target)['status'],'FAIL')
        with self.assertRaisesRegex(ComponentInstallError,'INTEGRITY_FAILURE'):self.install()
        self.assertEqual(p.read_text(),'user change')
    def test_modified_receipt_is_rejected(self):
        self.install();p=self.target/'COMPONENT_INSTALL.json';d=json.loads(p.read_text());d['resolved_components'].append('figures');p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ComponentInstallError,'RECEIPT_INTEGRITY_FAILURE'):verify_installation(self.target)
    def test_untracked_script_is_not_part_of_verified_package(self):
        self.install();(self.target/'scripts/untracked.py').write_text('# unexpected')
        result=verify_installation(self.target);self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['failures'][0]['reason'],'UNTRACKED_FILE')
    def test_changed_selection_requires_fresh_target(self):
        self.install()
        with self.assertRaisesRegex(ComponentInstallError,'SELECTION_OR_MANIFEST_CHANGED'):self.install(['literature'])
        self.assertFalse((self.target/'skills/literature').exists())
    def test_changed_source_requires_fresh_target(self):
        self.install();(self.source/'scripts/core.py').write_text('# new source')
        with self.assertRaisesRegex(ComponentInstallError,'SOURCE_FILES_CHANGED'):self.install()
    def test_unknown_component_and_dependency_cycle_fail_before_copy(self):
        with self.assertRaisesRegex(ComponentInstallError,'UNKNOWN_COMPONENT'):self.install(['not-real'])
        self.manifest['components']['core']['depends_on']=['research'];self.write_manifest()
        with self.assertRaisesRegex(ComponentInstallError,'DEPENDENCY_CYCLE'):self.install()
        self.assertFalse(self.target.exists())
    def test_unknown_dependency_rejected_by_manifest(self):
        self.manifest['components']['literature']['depends_on']=['absent'];self.write_manifest()
        with self.assertRaisesRegex(ComponentInstallError,'UNKNOWN_DEPENDENCY'):load_manifest(self.source)
    def test_manifest_traversal_rejected_before_copy(self):
        self.manifest['components']['core']['files'].append('../outside');self.write_manifest()
        with self.assertRaisesRegex(ComponentInstallError,'UNSAFE_RELATIVE_PATH'):self.install()
        self.assertFalse(self.target.exists())
    def test_declared_missing_file_rejected_before_copy(self):
        self.manifest['components']['core']['files'].append('missing.txt');self.write_manifest()
        with self.assertRaisesRegex(ComponentInstallError,'COMPONENT_FILE_MISSING'):self.install()
        self.assertFalse(self.target.exists())
    def test_conflicting_requirement_versions_rejected(self):
        self.manifest['components']['literature']['python_requirements']=['numpy==1.0'];self.write_manifest()
        with self.assertRaisesRegex(ComponentInstallError,'REQUIREMENT_CONFLICT'):self.install(['literature','figures'])
    def test_unpinned_or_url_requirement_rejected(self):
        self.manifest['components']['figures']['python_requirements']=['numpy>=2'];self.write_manifest()
        with self.assertRaisesRegex(ComponentInstallError,'UNPINNED_REQUIREMENT'):load_manifest(self.source)
    def test_nonempty_target_preserved(self):
        self.target.mkdir();p=self.target/'user.txt';p.write_text('keep')
        with self.assertRaisesRegex(ComponentInstallError,'TARGET_NOT_EMPTY'):self.install()
        self.assertEqual(p.read_text(),'keep')
    def test_missing_python_dependency_recorded_without_download(self):
        with patch('component_install._run',side_effect=AssertionError('must not run pip')):result=self.install(['figures'])
        self.assertEqual(result['python_dependency_status'],'REQUIRED_NOT_INSTALLED');self.assertEqual(result['network_operations'],0)
        config=json.loads((self.target/'.mcp.json').read_text());self.assertIn('-S',config['mcpServers']['research-guard']['args'])
    def test_selected_mcp_config_uses_direct_bound_interpreter_and_server(self):
        self.install();config=json.loads((self.target/'.mcp.json').read_text())['mcpServers']['research-guard']
        self.assertEqual(config['command'],str(Path(sys.executable).resolve()))
        self.assertEqual(config['args'][-1],str(self.target/'scripts/mcp_server.py'));self.assertIn('-I',config['args']);self.assertIn('-S',config['args'])
    def test_target_inside_source_is_rejected(self):
        with self.assertRaisesRegex(ComponentInstallError,'TARGET_INSIDE_SOURCE'):install_components(self.source,self.source/'nested',['core'])
    def test_cli_relative_target_outside_source_is_installed(self):
        script=Path(__file__).resolve().parents[1]/'scripts/component_install.py'
        run=subprocess.run([sys.executable,'-I',str(script),'--source',str(self.source),'--target','../relative-install','--components','core'],cwd=self.source,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout)
        self.assertEqual(result['status'],'INSTALLED')
        self.assertEqual(Path(result['target']),self.base/'relative-install')
        self.assertEqual(verify_installation(self.base/'relative-install')['status'],'PASS')
    def test_relative_traversal_into_source_is_rejected(self):
        target=self.source/'..'/'source'/'nested'
        with self.assertRaisesRegex(ComponentInstallError,'TARGET_INSIDE_SOURCE'):install_components(self.source,target,['core'])
        self.assertFalse((self.source/'nested').exists())
    def test_clean_environment_removes_ambient_python_pip_and_proxy(self):
        with patch.dict(os.environ,{'PYTHONPATH':'unsafe','PYTHONUSERBASE':'unsafe','PIP_INDEX_URL':'https://unselected.invalid','PIP_CUSTOM':'unsafe','HTTPS_PROXY':'http://unselected.invalid','RG_INSTALL_FIXTURE':'retained'}):
            result=_clean_env()
        self.assertEqual(result['RG_INSTALL_FIXTURE'],'retained')
        self.assertFalse(any(k.upper().startswith(('PYTHON','PIP_')) for k in result))
        self.assertFalse(any(k.upper() in {'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY'} for k in result))
    @unittest.skipUnless(os.name=='nt','Windows long-path runtime regression')
    def test_actual_deep_windows_venv_bootstraps_pip_offline(self):
        import shutil
        # Keep the executable itself below CreateProcess's executable-path cap,
        # while pip's nested license paths exceed classic MAX_PATH.
        target=self.base/('deep-'+'x'*max(40,190-len(str(self.base))))/'runtime'
        runtime=_runtime_path(target/'.venv')
        self.assertTrue(str(runtime).startswith('\\\\?\\'))
        try:
            run=_run([sys.executable,'-I','-X','utf8','-m','venv','--without-pip',str(runtime)],self.base)
            self.assertEqual(run['returncode'],0,run['stderr'])
            python=runtime/'Scripts/python.exe'
            run=_run([str(python),'-I','-X','utf8','-m','ensurepip','--upgrade','--default-pip'],self.base)
            self.assertEqual(run['returncode'],0,run['stdout']+run['stderr'])
            run=_run([str(python),'-I','-c','import importlib.metadata;print(importlib.metadata.version("pip"))'],self.base)
            self.assertEqual(run['returncode'],0,run['stderr'])
            self.assertTrue(run['stdout'].strip())
        finally:
            if runtime.exists():shutil.rmtree(runtime)
    def test_only_selected_python_requirements_are_planned(self):
        result=installation_plan(self.source,['literature']);self.assertEqual(result['python_requirements'],[])
        result=installation_plan(self.source,['figures']);self.assertEqual(result['python_requirements'],['numpy==2.4.4'])
    def test_actual_bare_venv_has_no_third_party_distributions(self):
        self.install(create_venv=True)
        receipt=json.loads((self.target/'COMPONENT_INSTALL.json').read_text())
        python=receipt['interpreter']
        self.assertEqual(str(Path(python).parent.parent).removeprefix('\\\\?\\'),str(self.target/'.venv'))
        run=subprocess.run([python,'-I','-c','import sys,json,importlib.metadata;print(json.dumps({"prefix":sys.prefix,"packages":[d.metadata["Name"] for d in importlib.metadata.distributions()]}))'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout)
        self.assertEqual(str(Path(result['prefix'])).removeprefix('\\\\?\\'),str(self.target/'.venv'))
        self.assertEqual(result['packages'],[])
        self.assertEqual(verify_installation(self.target)['status'],'PASS')
    def test_cli_no_selection_leaves_target_absent(self):
        run=subprocess.run([sys.executable,'-I',str(Path(__file__).resolve().parents[1]/'scripts/component_install.py'),'--source',str(self.source),'--target',str(self.target)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(json.loads(run.stdout)['status'],'SELECTION_REQUIRED');self.assertFalse(self.target.exists())

if __name__=='__main__':unittest.main()
