"""Opt-in, stdlib-only installation of explicit Research Guard feature groups.

This installer never invokes the legacy all-in-one installers, copies payloads,
or downloads anything unless --install-python-deps is explicitly supplied.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import urlsplit
import venv

SOURCE_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_NAME = 'COMPONENT_INSTALL.json'
PENDING_NAME = 'COMPONENT_INSTALL.pending.json'

SMOKE_SCRIPT = r'''"""Actual installed MCP stdio smoke, no mocks and no external model."""
import json
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
config=json.loads((root/'.mcp.json').read_text(encoding='utf-8'))['mcpServers']['research-guard']
requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'component-install-smoke','version':'1'}}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}]
run=subprocess.run([config['command'],*config['args']],cwd=root,input=''.join(json.dumps(x)+'\n' for x in requests),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
responses=[]
for line in run.stdout.splitlines():
    try:responses.append(json.loads(line))
    except ValueError:pass
listed=next((x for x in responses if x.get('id')==2),{})
tools=listed.get('result',{}).get('tools')
result={'status':'PASS' if run.returncode==0 and isinstance(tools,list) and bool(tools) else 'FAIL','method':'actual_installed_mcp_stdio','returncode':run.returncode,'requests':requests,'responses':responses,'stderr':run.stderr,'tool_names':[x['name'] for x in tools or []],'boundary':'Tests MCP startup and selected schema only, not scientific acceptance or a Codex model session.'}
print(json.dumps(result,ensure_ascii=False,indent=2))
sys.exit(0 if result['status']=='PASS' else 1)
'''

class ComponentInstallError(RuntimeError):
    pass

def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix='.rg-', suffix='.tmp', dir=path.parent)
    temp = Path(raw)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()

def _relative(value: str) -> str:
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ComponentInstallError(f'UNSAFE_RELATIVE_PATH: {value!r}')
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in {'..', '.'} for x in value.rstrip('/').split('/')):
        raise ComponentInstallError(f'UNSAFE_RELATIVE_PATH: {value!r}')
    return p.as_posix()

def load_manifest(source: Path = SOURCE_ROOT) -> dict[str, Any]:
    path = source / 'assets/feature-components.json'
    try: data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc: raise ComponentInstallError(f'MANIFEST_UNREADABLE: {exc}') from exc
    if data.get('schema_version') != 1 or not isinstance(data.get('components'), dict) or 'core' not in data['components']:
        raise ComponentInstallError('MANIFEST_INVALID: expected schema 1 with core component')
    for key, item in data['components'].items():
        if not re.fullmatch(r'[a-z][a-z0-9-]*', key): raise ComponentInstallError('MANIFEST_INVALID: component identifier')
        for field in ('files', 'depends_on', 'python_requirements', 'modules'):
            if not isinstance(item.get(field), list) or any(not isinstance(x, str) for x in item[field]):
                raise ComponentInstallError(f'MANIFEST_INVALID: {key}.{field}')
        for rel in item['files']: _relative(rel)
        for dependency in item['depends_on']:
            if dependency not in data['components']: raise ComponentInstallError(f'UNKNOWN_DEPENDENCY: {key}->{dependency}')
        for requirement in item['python_requirements']:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.+!-]*', requirement):
                raise ComponentInstallError(f'UNPINNED_REQUIREMENT: {requirement}')
    return data

def dependency_closure(manifest: dict[str, Any], selected: list[str]) -> list[str]:
    components = manifest['components']; done: set[str] = set(); visiting: set[str] = set(); result=[]
    def visit(name: str) -> None:
        if name not in components: raise ComponentInstallError(f'UNKNOWN_COMPONENT: {name}')
        if name in visiting: raise ComponentInstallError(f'DEPENDENCY_CYCLE: {name}')
        if name in done: return
        visiting.add(name)
        for dependency in components[name]['depends_on']: visit(dependency)
        visiting.remove(name);done.add(name);result.append(name)
    if selected:
        visit('core')
        for name in sorted(set(selected)): visit(name)
    return result

def _check_no_links(root: Path, path: Path) -> None:
    try: path.resolve().relative_to(root.resolve())
    except ValueError as exc: raise ComponentInstallError(f'SOURCE_PATH_ESCAPE: {path}') from exc
    rel=path.relative_to(root)
    for candidate in [root, *[root.joinpath(*rel.parts[:i]) for i in range(1,len(rel.parts)+1)]]:
        if candidate.is_symlink() or (hasattr(candidate,'is_junction') and candidate.is_junction()):
            raise ComponentInstallError(f'SYMLINK_OR_JUNCTION_FORBIDDEN: {candidate}')

def installation_plan(source: Path, selected: list[str]) -> dict[str, Any]:
    source=source.resolve();manifest=load_manifest(source);resolved=dependency_closure(manifest, selected)
    if not selected:
        return {'status':'SELECTION_REQUIRED','requested_components':[],'resolved_components':[], 'files':[], 'python_requirements':[], 'network_operations':0}
    files:dict[str,dict[str,Any]]={}; pins:dict[str,str]={}
    excluded=set(manifest.get('excluded_path_parts',[]));allowed=set(manifest.get('directory_suffix_allowlist',[]))
    for component in resolved:
        item=manifest['components'][component]
        for requirement in item['python_requirements']:
            package,version=requirement.split('==');key=package.casefold().replace('_','-')
            if key in pins and pins[key]!=requirement: raise ComponentInstallError(f'REQUIREMENT_CONFLICT: {package}')
            pins[key]=requirement
        for value in item['files']:
            rel=_relative(value);path=source/rel;_check_no_links(source,path)
            if not path.exists(): raise ComponentInstallError(f'COMPONENT_FILE_MISSING: {component}:{rel}')
            paths=sorted(path.rglob('*')) if path.is_dir() else [path]
            for file in paths:
                _check_no_links(source,file)
                if not file.is_file(): continue
                name=file.relative_to(source)
                if any(part in excluded for part in name.parts): continue
                if path.is_dir() and file.suffix.lower() not in allowed: continue
                relative=name.as_posix()
                record=files.setdefault(relative,{'path':relative,'bytes':file.stat().st_size,'sha256':_sha(file),'components':[]})
                record['components'].append(component)
    return {'status':'PLANNED','schema_version':1,'requested_components':sorted(set(selected)), 'resolved_components':resolved,
            'source_manifest_sha256':_sha(source/'assets/feature-components.json'),'files':sorted(files.values(),key=lambda x:x['path']),
            'python_requirements':sorted(pins.values()),'copy_bytes':sum(x['bytes'] for x in files.values()),'network_operations':0}

def _runtime_path(path: Path) -> Path:
    # The installer cannot assume Windows LongPathsEnabled is configured.
    value=str(path.absolute())
    if os.name=='nt' and not value.startswith('\\\\?\\'):
        value=('\\\\?\\UNC\\'+value[2:]) if value.startswith('\\\\') else '\\\\?\\'+value
    return Path(value)

def _package_files(root:Path):
    # Runtime files are verified by runtime identity/package metadata separately.
    # Do not enumerate thousands of pip/venv files or accidentally hit MAX_PATH.
    for directory,dirs,files in os.walk(root):
        dirs[:]=[name for name in dirs if name not in {'.venv','__pycache__'}]
        for name in files:
            yield Path(directory)/name

def _python(venv_path: Path) -> Path:
    return venv_path/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def _clean_env() -> dict[str,str]:
    # Use the repository's audited environment boundary, including under -I.
    script_directory=str(Path(__file__).resolve().parent)
    if script_directory not in sys.path:sys.path.insert(0,script_directory)
    from network_config_core import network_environment
    return {key:value for key,value in network_environment().items() if not key.upper().startswith(('PYTHON','PIP_'))}

def _canonical_target(path:Path) -> Path:
    raw=path.expanduser().absolute()
    # Inspect the original traversal before resolving '..' or following links.
    for candidate in [raw,*raw.parents]:
        if candidate.is_symlink() or (hasattr(candidate,'is_junction') and candidate.is_junction()):
            raise ComponentInstallError(f'SYMLINK_OR_JUNCTION_FORBIDDEN: {candidate}')
    return raw.resolve()

def _run(command:list[str], cwd:Path, timeout:int=600) -> dict[str,Any]:
    started=dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        result=subprocess.run(command,cwd=cwd,env=_clean_env(),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ComponentInstallError(f'INSTALL_COMMAND_FAILED: {exc}') from exc
    return {'argv':command,'cwd':str(cwd),'started_at':started,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}

def _metadata(python:Path) -> dict[str,str]:
    command=[str(python),'-I','-c','import importlib.metadata,json;print(json.dumps({d.metadata["Name"].lower().replace("_","-"):d.version for d in importlib.metadata.distributions()}))']
    run=_run(command,python.parent)
    if run['returncode']!=0: raise ComponentInstallError('RUNTIME_METADATA_FAILED: '+run['stderr'][-1000:])
    return json.loads(run['stdout'])

def verify_installation(target:Path) -> dict[str,Any]:
    target=target.resolve();path=target/RECEIPT_NAME
    try: receipt=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError) as exc: raise ComponentInstallError(f'RECEIPT_UNREADABLE: {exc}') from exc
    stable={k:v for k,v in receipt.items() if k!='receipt_sha256'}
    if _digest(stable)!=receipt.get('receipt_sha256'): raise ComponentInstallError('RECEIPT_INTEGRITY_FAILURE')
    failures=[];expected=set()
    for item in receipt.get('files',[]):
        relative=_relative(item['path']);expected.add(relative);file=target/relative
        _check_no_links(target,file)
        if not file.is_file() or file.stat().st_size!=item['bytes'] or _sha(file)!=item['sha256']:
            failures.append({'path':relative,'reason':'FILE_MISSING_OR_CHANGED'})
    # A new script or asset cannot silently become part of a verified package.
    for file in _package_files(target):
        relative=file.relative_to(target)
        if '.venv' in relative.parts or '__pycache__' in relative.parts or not file.is_file():continue
        if relative.as_posix() not in expected|{RECEIPT_NAME}:
            failures.append({'path':relative.as_posix(),'reason':'UNTRACKED_FILE'})
    runtime=Path(receipt['interpreter']);runtime_status='NOT_CHECKED'
    if not runtime.is_file() or _sha(runtime)!=receipt.get('interpreter_sha256'):
        failures.append({'path':str(runtime),'reason':'INTERPRETER_MISSING_OR_CHANGED'})
    elif receipt['python_dependency_status']=='INSTALLED':
        versions=_metadata(runtime);runtime_status='INSTALLED_VERSIONS_CHECKED'
        for requirement in receipt['python_requirements']:
            package,version=requirement.split('==')
            if versions.get(package.casefold().replace('_','-'))!=version:
                failures.append({'path':package,'reason':'PYTHON_DEPENDENCY_MISSING_OR_CHANGED'})
    else:runtime_status=receipt['python_dependency_status']
    return {'status':'PASS' if not failures else 'FAIL','requested_components':receipt['requested_components'], 'resolved_components':receipt['resolved_components'],
            'checked_files':len(expected),'python_dependency_status':receipt['python_dependency_status'],'runtime_check':runtime_status,'failures':failures,'receipt_sha256':receipt['receipt_sha256']}

def install_components(source:Path,target:Path,selected:list[str],*,install_python_deps:bool=False,create_venv:bool=False,python:Path|None=None,pip_index_url:str='https://pypi.org/simple') -> dict[str,Any]:
    source=source.resolve();target=_canonical_target(target);plan=installation_plan(source,selected)
    if plan['status']=='SELECTION_REQUIRED':return plan
    if target==source or source in target.parents:
        raise ComponentInstallError('TARGET_INSIDE_SOURCE_FORBIDDEN')
    _check_no_links(target.parent,target)
    if (target/RECEIPT_NAME).is_file():
        old=json.loads((target/RECEIPT_NAME).read_text(encoding='utf-8-sig'))
        if old.get('requested_components')!=plan['requested_components'] or old.get('source_manifest_sha256')!=plan['source_manifest_sha256']:
            raise ComponentInstallError('SELECTION_OR_MANIFEST_CHANGED_USE_FRESH_TARGET')
        if install_python_deps and old.get('python_dependency_status')=='REQUIRED_NOT_INSTALLED':
            raise ComponentInstallError('DEPENDENCY_MODE_CHANGED_USE_FRESH_TARGET')
        checked=verify_installation(target)
        if checked['status']!='PASS':raise ComponentInstallError('EXISTING_INSTALL_INTEGRITY_FAILURE: '+json.dumps(checked['failures']))
        expected={x['path']:x['sha256'] for x in plan['files']}
        prior={x['path']:x.get('source_sha256',x['sha256']) for x in old['files'] if x.get('source_file')}
        if expected!=prior:raise ComponentInstallError('SOURCE_FILES_CHANGED_USE_FRESH_TARGET')
        return {'status':'UNCHANGED','target':str(target),'verification':checked,'network_operations':0,'copied_files':0}
    if target.exists() and any(target.iterdir()):raise ComponentInstallError('TARGET_NOT_EMPTY')
    url=urlsplit(pip_index_url)
    if url.scheme!='https' or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise ComponentInstallError('PIP_INDEX_MUST_BE_CREDENTIAL_FREE_HTTPS')
    target.mkdir(parents=True,exist_ok=True);_write(target/PENDING_NAME,{'status':'INSTALLING','plan':plan})
    for item in plan['files']:
        origin=source/item['path'];dest=target/item['path'];dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(origin,dest)
        if _sha(dest)!=item['sha256']:raise ComponentInstallError('SOURCE_CHANGED_DURING_COPY: '+item['path'])
    interpreter=(python or Path(sys.executable)).resolve();requirements=plan['python_requirements'];runs=[];dependency_status='REQUIRED_NOT_INSTALLED' if requirements else 'NOT_REQUIRED_STDLIB'
    if create_venv or (install_python_deps and requirements):
        runtime_root=_runtime_path(target/'.venv')
        command=[str(interpreter),'-I','-X','utf8','-m','venv','--without-pip',str(runtime_root)]
        run=_run(command,target);runs.append(run)
        _write(target/PENDING_NAME,{'status':'INSTALLING','plan':plan,'installation_runs':runs})
        if run['returncode']!=0:raise ComponentInstallError('VENV_CREATION_FAILED: '+run['stderr'][-2000:])
        interpreter=_python(runtime_root).absolute()
        if install_python_deps and requirements:
            # Keep pip bootstrap isolated too, and preserve its actual diagnostics.
            bootstrap=_run([str(interpreter),'-I','-X','utf8','-m','ensurepip','--upgrade','--default-pip'],target)
            runs.append(bootstrap)
            _write(target/PENDING_NAME,{'status':'INSTALLING','plan':plan,'installation_runs':runs})
            if bootstrap['returncode']!=0:
                _write(target/'INSTALL_FAILURE.json',{'status':'PIP_BOOTSTRAP_FAILED','runs':runs})
                raise ComponentInstallError('PIP_BOOTSTRAP_FAILED: '+(bootstrap['stderr'] or bootstrap['stdout'])[-3000:])
    if install_python_deps and requirements:
        pip_report=target/'PYTHON_DEPENDENCY_REPORT.json'
        command=[str(interpreter),'-I','-X','utf8','-m','pip','--isolated','install','--disable-pip-version-check','--no-input','--no-cache-dir','--index-url',pip_index_url,'--report',str(pip_report),*requirements]
        run=_run(command,target,timeout=900);runs.append(run)
        if run['returncode']!=0:
            _write(target/'INSTALL_FAILURE.json',{'status':'DEPENDENCY_INSTALL_FAILED','runs':runs})
            raise ComponentInstallError('DEPENDENCY_INSTALL_FAILED: '+run['stderr'][-2000:])
        dependency_status='INSTALLED'
    args=['-I']
    if dependency_status!='INSTALLED':args+=['-S']
    args+=['-X','utf8',str(target/'scripts/mcp_server.py')]
    _write(target/'.mcp.json',{'mcpServers':{'research-guard':{'command':str(interpreter),'args':args}}})
    # Selected component instructions are discoverable; unselected skill trees do not exist.
    (target/'SKILL.md').write_text('---\nname: research-guard\ndescription: Evidence-bound research components explicitly selected for this installation.\n---\n\n# Research Guard selected components\n\nInstalled: '+', '.join(plan['resolved_components'])+'.\n\nRead the corresponding installed skills only when needed. An uninstalled route must report COMPONENT_NOT_INSTALLED. Component selection never authorizes scientific decisions or optional TeX/Lean downloads.\n\nUse scripts/component_install.py --list to inspect groups; install another combination into a fresh target.\n',encoding='utf-8')
    plugin_path=target/'.codex-plugin/plugin.json'
    if plugin_path.is_file():
        plugin=json.loads(plugin_path.read_text(encoding='utf-8-sig'));plugin['description']='Selected Research Guard components: '+', '.join(plan['resolved_components']);plugin['skills']='./skills/'
        plugin.setdefault('interface',{})['capabilities']=plan['resolved_components']
        plugin['interface']['longDescription']=plugin['description'];plugin['interface']['shortDescription']='Explicitly selected research components with evidence-bound guards.';plugin['interface']['defaultPrompt']=['Read the installed component inventory and use only the selected groups.','Use actual project inputs, inspect tool returns, and preserve explicit failures and evidence.'];_write(plugin_path,plugin)
    (target/'skills').mkdir(exist_ok=True)
    # Even a core-only plugin exposes a minimal installation skill to the host.
    (target/'skills/research-guard-components').mkdir(exist_ok=True)
    shutil.copyfile(target/'SKILL.md',target/'skills/research-guard-components/SKILL.md')
    (target/'tests').mkdir(exist_ok=True)
    (target/'tests/component_smoke.py').write_text(SMOKE_SCRIPT,encoding='utf-8')
    descriptions=load_manifest(source)['components']
    readme="# Selected Research Guard installation\n\n## Input / 输入\n\nThis installation contains only the explicitly selected groups and their declared code dependencies: **{groups}**. Pass a real project_root and actual local source/evidence files to the selected MCP tools. Do not treat synthetic fixtures as manuscript or experimental evidence.\n\n## Steps / 使用步骤\n\n1. Inspect COMPONENT_INSTALL.json and .mcp.json. Register this plugin directory in Codex separately; installation alone does not claim host registration or a new authenticated session.\n2. Read skills/research-guard-components/SKILL.md and the selected feature skill only when needed.\n3. Ask a concrete natural-language question, run the actual selected MCP action, inspect its return and referenced files, and preserve limitations and failures. Unselected routes must report COMPONENT_NOT_INSTALLED.\n4. Run verification with the direct interpreter in .mcp.json: scripts/component_install.py --verify --target <this-directory>.\n\n## Output / 输出\n\nThe installer produces COMPONENT_INSTALL.json (requested/resolved groups and per-file SHA256), a direct bound .mcp.json, selected code/skills, and this guide. Workflow outputs belong in the chosen project's evidence/state directories; this package's installation receipt does not certify scientific results.\n\n## Dependencies / 依赖\n\n{requirements}\n\nDependency state: {dependency_status}. Optional TeX/Lean and the real CiteSpace companion require separate explicit environment decisions. Unselected packages, binary payloads, tests from other components, GUI and reference papers are absent.\n\n## Real test directory / 真实测试目录\n\n`tests/component_smoke.py` is a runnable actual MCP stdio smoke, not a canned receipt. Run it with the bound Python interpreter; it sends initialize and tools/list to this installed server and prints complete requests/responses. It does not start a model session, install dependencies or prove scientific correctness. Installation integrity is checked separately by --verify. The full repository's development suite is intentionally excluded from the lean installation.\n\n## Selected functionality / 已选功能\n\n{details}\n"
    readme=readme.format(groups=', '.join(plan['resolved_components']),requirements=', '.join(requirements) if requirements else 'Python standard library only; no pip or third-party package required.',dependency_status=dependency_status,details='\n'.join('- '+name+': '+descriptions[name].get('description','') for name in plan['resolved_components']))
    (target/'README.md').write_text(readme,encoding='utf-8')
    files=[]
    for file in sorted(_package_files(target)):
        relative=file.relative_to(target)
        if not file.is_file() or '.venv' in relative.parts or relative.as_posix()==PENDING_NAME:continue
        files.append({'path':relative.as_posix(),'bytes':file.stat().st_size,'sha256':_sha(file),'source_file':relative.as_posix() in {x['path'] for x in plan['files']}})
    # Generated plugin metadata deliberately differs from its source template.
    source_files={x['path']:x['sha256'] for x in plan['files']}
    for file in files:
        if file['source_file']:file['source_sha256']=source_files[file['path']]
    receipt={k:v for k,v in plan.items() if k not in {'files','status'}}
    receipt.update({'status':'INSTALLED','installed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'files':files,'interpreter':str(interpreter),'interpreter_sha256':_sha(interpreter),
                    'python_dependency_status':dependency_status,'python_install_requested':install_python_deps,'network_operations_definition':'Number of network-capable pip install commands; HTTP request count is not measured.','runtime_isolated_no_site':dependency_status!='INSTALLED','installation_runs':runs,'network_operations':1 if dependency_status=='INSTALLED' else 0})
    receipt['receipt_sha256']=_digest(receipt);_write(target/RECEIPT_NAME,receipt);(target/PENDING_NAME).unlink()
    return {'status':'INSTALLED','target':str(target),'requested_components':plan['requested_components'],'resolved_components':plan['resolved_components'],'copied_files':len(files),'copy_bytes':sum(x['bytes'] for x in files),'python_requirements':requirements,'python_dependency_status':dependency_status,'receipt':str(target/RECEIPT_NAME),'network_operations':receipt['network_operations']}

def main() -> int:
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='backslashreplace')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=SOURCE_ROOT);p.add_argument('--target',type=Path)
    p.add_argument('--list',action='store_true');p.add_argument('--components',nargs='+',help='Explicit groups, comma- or space-separated. No default selection.')
    p.add_argument('--dry-run',action='store_true');p.add_argument('--verify',action='store_true')
    p.add_argument('--install-python-deps',action='store_true');p.add_argument('--create-venv',action='store_true')
    p.add_argument('--python',type=Path);p.add_argument('--pip-index-url',default='https://pypi.org/simple')
    a=p.parse_args()
    try:
        if a.list:
            m=load_manifest(a.source);result={'status':'AVAILABLE_COMPONENTS','default_components':[], 'components':m['components']}
        elif a.verify:
            if a.target is None:p.error('--verify requires --target')
            result=verify_installation(a.target)
        else:
            selected=[part for group in a.components or [] for part in group.split(',') if part]
            if a.dry_run or not selected:result=installation_plan(a.source,selected)
            else:
                if a.target is None:p.error('--components requires --target unless --dry-run')
                result=install_components(a.source,a.target,selected,install_python_deps=a.install_python_deps,create_venv=a.create_venv,python=a.python,pip_index_url=a.pip_index_url)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 1 if result.get('status')=='FAIL' else 0
    except (ComponentInstallError,OSError,ValueError) as exc:
        print(json.dumps({'status':'ERROR','error_type':type(exc).__name__,'error':str(exc)},ensure_ascii=False,indent=2));return 2

if __name__=='__main__':raise SystemExit(main())
