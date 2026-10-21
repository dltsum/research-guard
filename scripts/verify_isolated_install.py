"""Explicit one-shot installation diagnostic, independent of ordinary startup."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from network_config_core import network_environment


def _run(command: list[str], *, env: dict[str, str], input_text: str | None = None,
         timeout: int = 120) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, input=input_text, text=True, capture_output=True,
                               encoding='utf-8', errors='replace', env=env, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {command[0]}: {(completed.stderr or completed.stdout)[-2000:]}")
    return completed


def _installed_python(runtime: Path) -> Path:
    for candidate in (runtime/'python.exe', runtime/'Scripts/python.exe', runtime/'bin/python'):
        if candidate.is_file():return candidate
    raise RuntimeError(f"installed Python executable is missing below {runtime}")


def verify(user_root: Path) -> dict[str, object]:
    user_root=user_root.resolve()
    plugin=user_root/'plugins/research-guard'
    skill=user_root/'.codex/skills/research-guard'
    runtime=user_root/'.research-guard/runtime/python'
    receipt_path=plugin/'COMPONENT_INSTALL.json'
    selected=json.loads(receipt_path.read_text(encoding='utf-8-sig')) if receipt_path.is_file() else None
    python=Path(selected['interpreter']) if selected else _installed_python(runtime)
    for path in (plugin/'SKILL.md', python, plugin/'scripts/mcp_server.py'):
        if not path.is_file():raise RuntimeError(f"installation is missing {path}")
    env=network_environment(base=dict(os.environ),proxy=None)
    env.update(RESEARCH_GUARD_INSTALL_USER_ROOT=str(user_root),
               RESEARCH_GUARD_HOME=str(user_root/'.research-guard'),
               RESEARCH_GUARD_CODEX_ROOT=str(user_root/'.codex'), PYTHONUTF8='1')
    diagnostic=None
    if selected:
        completed=_run([str(python),'-I','-X','utf8',str(plugin/'scripts/component_install.py'),
                        '--verify','--target',str(plugin)],env=env)
        diagnostic=json.loads(completed.stdout)
    else:
        modules='matplotlib,networkx,numpy,optuna,PIL,pint,pypdf,sympy,z3'
        _run([str(python),'-I','-X','utf8','-c','import '+modules],env=env)
    requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26'}},
              {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}]
    completed=_run([str(python),'-I','-X','utf8',str(plugin/'scripts/mcp_server.py')],
                   env=env,input_text=''.join(json.dumps(item)+'\n' for item in requests))
    responses=[json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    initialized=next((item for item in responses if item.get('id')==1),{})
    listed=next((item for item in responses if item.get('id')==2),{})
    tools=listed.get('result',{}).get('tools')
    if not isinstance(tools,list) or not tools or 'result' not in initialized:
        raise RuntimeError('MCP initialize or tools/list did not return a usable result')
    return {'status':'PASS','user_root':str(user_root),'plugin':str(plugin),'skill':str(skill),
            'python':str(python),'mcp_tools':len(tools),
            'mcp_version':initialized['result']['serverInfo'].get('version'),
            'installation_diagnostic':diagnostic,
            'scope':'File presence, actual dependency imports and MCP startup; not a scientific-result audit.'}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-root',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.user_root),ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
