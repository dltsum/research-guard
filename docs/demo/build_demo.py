"""Build an offline component demo only from recorded real acceptance evidence.

No agent dispatch, feature execution, invented transcript, or synthetic success.
Raw journals stay local. Published records redact machine paths/credentials and
bind the original source index and tool files with SHA-256 digests.
"""
import argparse
import base64
import collections
import datetime
import hashlib
import json
import re
import subprocess
from pathlib import Path

def load(p):
    return json.loads(p.read_text(encoding='utf8'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-root',required=True,type=Path)
    p.add_argument('--repository',required=True,type=Path)
    p.add_argument('--template',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    index=a.evidence_root/'interaction-index.jsonl'
    events=[json.loads(line) for line in index.read_text(encoding='utf8').splitlines() if line.strip()]
    queue=load(a.evidence_root/'逐功能队列.json')
    bugs=load(a.evidence_root/'bugs.json')
    native_path=a.evidence_root/'native-dialogues.json'
    native_dialogues=load(native_path) if native_path.is_file() else {}
    extra_native_path=a.evidence_root/'extra-native-dialogues.json'
    extra_native=load(extra_native_path) if extra_native_path.is_file() else {}
    for key,value in extra_native.items():
        if key in native_dialogues:
            native_dialogues[key]['agents'].extend(value['agents'])
        else:native_dialogues[key]=value
    catalog=load(a.repository/'assets/feature-components.json')['components']
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.repository,text=True).strip()
    redactions=collections.Counter()
    def clean(value):
        if isinstance(value,dict):
            return {clean(k): ('[credential redacted]' if re.fullmatch(r'(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|authorization|cookie)',k) else clean(v)) for k,v in value.items() if k not in {'private_original_local_only','private_original_sha256'}}
        if isinstance(value,list):return [clean(v) for v in value]
        if isinstance(value,str):
            value,n=re.subn(r'(?i)(?:\\\\\?\\)?C:[\\/]+Users[\\/]+lin(?:[\\/]+Documents[\\/]+Codex)?', '${LOCAL_WORKSPACE}',value)
            redactions['machine_path_replacements']+=n
            # Historical commands may mention another account or a file directly
            # under Users. Keep those measured inputs in the local trace, while
            # making the public transcript portable and safe to copy.
            value,n=re.subn(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"\x27<>]+', '${RECORDED_USER_ROOT}',value)
            redactions['other_recorded_user_root_replacements']+=n
            value,n=re.subn(r'(?i)(?<![\w.-])(?:(?:https?://)(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\])(?::\d{1,5})?|(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\]):\d{1,5})', '${RECORDED_LOCAL_ENDPOINT}',value)
            redactions['recorded_local_endpoint_replacements']+=n
            value,n=re.subn(r'(?i)(\b(?:authorization\s*:\s*bearer|api[_-]?key\s*[=:]|access[_-]?token\s*[=:]|password\s*[=:])\s*)[^\s"\x27,;]{8,}',r'\1[credential redacted]',value)
            redactions['credential_pattern_replacements']+=n
            value=re.sub(r'\bgAAAAA[A-Za-z0-9_-]{80,}={0,2}','[opaque encrypted payload omitted]',value)
            value=re.sub(r'data:(?:image|audio)/[^;,\s]+;base64,[A-Za-z0-9+/=]+','[media binary omitted]',value)
            return value
        return value
    by_step=collections.defaultdict(list)
    for e in events:by_step[e['step_id']].append(e)
    credited=collections.defaultdict(list)
    for r in queue['routes']:
        for attempt in r.get('attempts',[]):credited[attempt['step']].append(r)
    components={key:{'id':key,'name':v['label'],'description':v['description'],
        'requested':key,'resolved':[],'dependency_note':v.get('python_requirements',[]),
        'state':'尚无逐功能记录','routes_total':0,'routes_tested':0,'routes_skipped':0,'steps':[]} for key,v in catalog.items()}
    showcase_path=a.evidence_root/'showcase.json'
    verified_media={}
    if showcase_path.is_file():
        for item in load(showcase_path)['items']:
            path=Path(item['file'])
            if path.suffix.lower() not in {'.png','.pdf'}:raise ValueError('Only actual PNG/PDF showcase artifacts')
            if sha(path)!=item['sha256']:raise ValueError('Showcase source changed: '+str(path))
            public={k:v for k,v in item.items() if k!='file'}
            public.update(filename=path.name,media_type='image/png' if path.suffix.lower()=='.png' else 'application/pdf')
            # Keep verified binary payloads out of text-only redaction. Valid
            # Base64 may contain a sequence resembling an opaque host message.
            verified_media[item['sha256']]=base64.b64encode(path.read_bytes()).decode('ascii')
            components[item['component']].setdefault('showcase',[]).append(public)
    def closure(key):
        result=[]
        for dep in catalog[key]['depends_on']:
            for item in closure(dep):
                if item not in result:result.append(item)
        if key not in result:result.append(key)
        return result
    for key in components:components[key]['resolved']=closure(key)
    all_routes=queue['routes']
    for route in all_routes:
        comp=components[route['component']]
        comp['routes_total']+=1
        comp['routes_tested']+=bool(route.get('attempts'))
        comp['routes_skipped']+=route['state'].startswith('SKIPPED')
    source_files=[]
    def file_record(path):
        if not path.is_file():return None
        record={'name':path.name,'sha256':sha(path),'bytes':path.stat().st_size}
        source_files.append({'relative_to_evidence':path.relative_to(a.evidence_root).as_posix(),**record})
        return record
    def choose_group(q,step,request):
        if q.get('component') in components:return q['component']
        credited_groups={r['component'] for r in credited[step]}
        if len(credited_groups)==1:return next(iter(credited_groups))
        args=request.get('arguments',{}) if isinstance(request,dict) else {}
        name=request.get('name') if isinstance(request,dict) else None
        special=[r['component'] for r in all_routes if r['tool']==name and r['action_field'] not in {None,'action'} and args.get(r['action_field'])==r['action']]
        if special:return special[0]
        installation=str(q.get('installation','')).replace('\\','/').split('/')[-1]
        for key in sorted(components,key=len,reverse=True):
            if installation==key or installation.startswith(key+'-'):return key
        stem=step.split('-',1)[1] if '-' in step else step
        for key in sorted(components,key=len,reverse=True):
            if stem==key or stem.startswith(key+'-'):return key
        if len(credited_groups)>1:return 'core'
        return 'core'
    for q in [e for e in events if e['kind']=='question']:
        step=q['step_id'];rows=by_step[step];directory=a.evidence_root/'steps'/step
        request=load(directory/'request.json') if (directory/'request.json').is_file() else None
        calls=load(directory/'tool-calls.json') if (directory/'tool-calls.json').is_file() else None
        # Early download/install turns predate the stdio wrapper. Preserve their
        # real CLI receipts rather than hiding them behind an index summary.
        cli_receipts=[]
        if calls is None:
            for path in sorted(directory.glob('*.exec-tool.json')):
                cli_receipts.append({'file':path.name,'source_sha256':sha(path),
                    'actual_return':load(path)})
        step_result=load(directory/'step-result.json') if (directory/'step-result.json').is_file() else None
        replies=[e for e in rows if e['kind']=='agent_reply']
        reviews=[e for e in rows if e['kind']=='parent_check']
        reply=replies[-1] if replies else {}
        review=reviews[-1] if reviews else {}
        status=review.get('status','PENDING')
        group=choose_group(q,step,request or {})
        original_evidence={f['path']:f for e in rows for f in e.get('evidence',[]) if isinstance(f,dict) and 'path' in f}
        evidence=[{'name':Path(f['path']).name,'sha256':f.get('sha256'),'bytes':f.get('bytes')} for f in original_evidence.values()]
        for path in [directory/'request.json',directory/'tool-calls.json',directory/'process.json',
                     directory/'step-result.json',*sorted(directory.glob('*.exec-tool.json'))]:
            item=file_record(path)
            if item and not any(x['sha256']==item['sha256'] for x in evidence):evidence.append(item)
        repairs=[{'id':b['id'],'status':b['state'],'commit':b.get('fix_commit') or b.get('published_commit'),
                  'description':b['description']} for b in bugs if step in {b.get('trigger_step'),b.get('retest_step')}]
        execution=reply.get('execution')
        if execution is None and (directory/'process.json').is_file():execution=load(directory/'process.json')
        record={'id':step,'title':step,'at':q.get('recorded_at_utc'),
            'installation':q.get('installation'),'status':status,'kind':'actual_record',
            'route_labels':[r['tool']+'.'+str(r['action_field'])+'='+str(r['action']) for r in credited[step]],
            'question':q.get('question',q.get('request','')),
            'answer':reply.get('answer',reply.get('summary',reply.get('result'))),
            'feedback':review.get('feedback'),'request':request or q.get('intended_route'),
            'result':calls or ({'step_result':step_result,'actual_cli_receipts':cli_receipts}
                              if step_result is not None or cli_receipts else reply.get('result')),
            'execution':execution,
            'evidence':evidence,'repairs':repairs,
            'record_boundary':'Recorded real messages and calls; machine paths/credentials redacted for the public demo. No private reasoning or raw local paper/data file is published.'}
        for pair, dialogue in native_dialogues.items():
            if step.endswith(pair):
                record['native_dialogues']=dialogue
        if any(word in status for word in ('REFUSAL','CORRECTION_REQUIRED','CORRECT_NOVELTY_BLOCK','CANONICAL_BIND_GUARD')):record['display_category']='refusal'
        elif 'REPAIR_REQUIRED' in status or 'BUG_REPRODUCED' in status:record['display_category']='failure'
        elif re.search(r'^\d+[A-Z]+-',step) or 'RETEST' in status:record['display_category']='retest'
        elif status=='PENDING' or any(w in status for w in ['PENDING','UNVERIFIED','GAPS']):record['display_category']='unverified'
        else:record['display_category']='success' if status.startswith('PASS') else 'unverified'
        components[group]['steps'].append(record)
    for key,c in components.items():
        untested=c['routes_total']-c['routes_tested']-c['routes_skipped']
        if c['routes_skipped']:
            c['state']='SKIPPED_EXTERNAL_TOOL_UNAVAILABLE'
            skips=[r['skip'] for r in all_routes if r['component']==key and r.get('skip')]
            c['steps'].append({'id':key+'-explicit-skip','title':'按用户更新的目标跳过不可用工具',
                'at':skips[0]['at_utc'],'status':c['state'],'kind':'skipped','display_category':'skipped',
                'question':None,'answer':None,'request':None,'result':None,'execution':None,
                'feedback':skips[0]['reason'],'evidence':[],
                'route_labels':[r['tool']+'.'+r['action_field']+'='+r['action'] for r in all_routes if r['component']==key],
                'record_boundary':'This is a scope decision, not an executed engine demonstration.'})
        else:c['state']='PENDING: '+str(untested)+'路由待实测' if untested else 'FUNCTION_ROUTES_EXERCISED: 具体结果见逐问反馈'
    data={'title':'Research Guard · 真实交互实验',
        'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':commit,
        'scope_note':'从真实下载、组件选装到逐功能提问：主会话每次发问，执行 agent 调用实际工具，主会话读取返回并反馈。保留失败、修复与重测；页面是已发生记录的交互浏览器。',
        'metrics':{'route_total':len(all_routes),'route_tested':sum(bool(r.get('attempts')) for r in all_routes),
                   'route_skipped':sum(r['state'].startswith('SKIPPED') for r in all_routes),
                   'bugs_fixed':sum(b['state']=='RETESTED_FIXED' for b in bugs)},
        'components':list(components.values()),
        'limitations':['已实测路由包括正向行为与预期拒绝；不等于所有科研结论成立或所有候选通过。',
            '本次实际宿主为 Windows。多个原生 agent 不代表多个操作系统；其他平台不能据此标为已验收。',
            '历史失败和更正保留；安装版本随修复升级，各步骤使用的版本以实际回执为准。',
            '公开页仅发布对话与工具记录的路径/凭据脱敏副本及原件哈希；私有推理、论文原文、原始数据和完整本机轨迹留在本地交付目录。',
            'CiteSpace 未找到可调用的伴随工具/合适旧版引擎，按用户授权跳过，未替换成其他引擎结果。'],
        'provenance':{'source_index_sha256':sha(index),'queue_sha256':sha(a.evidence_root/'逐功能队列.json'),
            'bugs_sha256':sha(a.evidence_root/'bugs.json'),'template_sha256':sha(a.template),
            'native_dialogues_sha256':sha(native_path) if native_path.is_file() else None,
            'extra_native_dialogues_sha256':sha(extra_native_path) if extra_native_path.is_file() else None,
            'showcase_sha256':sha(showcase_path) if showcase_path.is_file() else None,
            'note':'Original evidence digests bind local source bytes; public display strings contain explicit path/credential redactions. A digest alone does not authenticate a host execution.'}}
    sanitized=clean(data)
    # Only these explicitly selected, source-hash-checked artifacts receive
    # binary bytes. Arbitrary transcript keys still undergo ordinary cleaning.
    for component in sanitized['components']:
        for artifact in component.get('showcase',[]):
            artifact['media_base64']=verified_media[artifact['sha256']]
    a.output.mkdir(parents=True,exist_ok=True)
    # Keep the embedded records line-bounded for source audits and review tools;
    # one multi-megabyte JSON line causes avoidable regex scan amplification.
    payload=json.dumps(sanitized,ensure_ascii=False,indent=2).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    template=a.template.read_text(encoding='utf8')
    marker='<script id="rg-demo-data" type="application/json">__RG_DEMO_DATA_JSON__</script>'
    assert template.count(marker)==1
    html=template.replace(marker,'<script id="rg-demo-data" type="application/json">'+payload+'</script>')
    (a.output/'index.html').write_text(html,encoding='utf8')
    (a.output/'data.json').write_text(json.dumps(sanitized,ensure_ascii=False,indent=2),encoding='utf8')
    manifest={'built_at':data['generated_at'],'source_commit':commit,'metrics':data['metrics'],
        'source_index_sha256':sha(index),'queue_sha256':sha(a.evidence_root/'逐功能队列.json'),
        'html_sha256':sha(a.output/'index.html'),'data_sha256':sha(a.output/'data.json'),
        'source_files':source_files,'redaction_counts':dict(redactions),
        'transformation':'No invented messages. Original question, actual answer, parent feedback, request/result, execution and explicit first-answer/worklog evidence; path/credential redaction only. Raw papers/datasets and private reasoning are not read or published by this builder.'}
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'output':str(a.output),'metrics':data['metrics'],'component_steps':{k:len(c['steps']) for k,c in components.items()},'html_bytes':(a.output/'index.html').stat().st_size,'redactions':dict(redactions)},ensure_ascii=False))

if __name__=='__main__':main()
