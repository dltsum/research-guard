"""Evidence-preserving research workflows around the actual CiteSpace engine.

Network construction is never reimplemented here. Graph statistics and SVG layout
are explicitly derived from CiteSpace's exported GraphML.
"""
from __future__ import annotations

import csv
import base64
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import time
import uuid
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from mcp.types import ToolAnnotations

B: Any = None
NODE_TYPES = {'Reference', 'Keyword', 'Author', 'Institution', 'Country', 'Cited Author', 'Cited Journal'}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def root():
    return B.TASK_ROOT / 'workflow_runs'


def run_path(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id):
        raise ValueError('Invalid run_id')
    p = root() / run_id
    if not (p / 'manifest.json').is_file():
        raise ValueError('Unknown run_id; prepare a run first')
    return p


def read_manifest(run_id):
    p = run_path(run_id)
    return p, json.loads((p / 'manifest.json').read_text(encoding='utf-8'))


def checkpoint(p, m, event, **data):
    m.update(data)
    m['updated_utc'] = now()
    save(p / 'manifest.json', m)
    with (p / 'events.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'utc': now(), 'event': event, **data}, ensure_ascii=False) + '\n')


def parse_wos(path):
    text = Path(path).read_text(encoding='utf-8-sig', errors='strict')
    records, lines, fields, tag = [], None, {}, None
    for line in text.splitlines():
        if line.startswith('PT '):
            if lines is not None:
                raise ValueError(f'Unterminated WoS record in {Path(path).name}')
            lines, fields, tag = [line], {'PT': line[3:]}, 'PT'
        elif lines is not None:
            if line == 'ER':
                lines.append(line)
                records.append({'fields': fields, 'raw': '\n'.join(lines), 'source_file': str(path)})
                lines, fields, tag = None, {}, None
            else:
                lines.append(line)
                if re.match(r'^[A-Z0-9]{2} ', line):
                    tag = line[:2]
                    fields[tag] = fields.get(tag, '') + ('\n' if tag in fields else '') + line[3:]
                elif line.startswith('   ') and tag:
                    fields[tag] += '\n' + line[3:]
    if lines is not None:
        raise ValueError(f'Unterminated WoS record in {Path(path).name}')
    if not records:
        raise ValueError(f'No complete WoS full records: {Path(path).name}')
    return records


def prepare(title, research_question, data_directory, start_year, end_year, node_type,
            k, rationale, sources, years_per_slice=1, pathfinder=False):
    if not title.strip() or not research_question.strip() or not rationale.strip():
        raise ValueError('Title, research question and analysis rationale are required')
    if any('\n' in s or '\r' in s for s in [title, research_question, rationale]):
        raise ValueError('Use single-line title/question/rationale')
    if node_type not in NODE_TYPES or not 1 <= k <= 25:
        raise ValueError('Unsupported node type or Basic-edition k outside 1..25')
    if not 1900 <= start_year <= end_year <= datetime.now().year:
        raise ValueError('Invalid years, or future year requested')
    if not 1 <= years_per_slice <= 10:
        raise ValueError('years_per_slice must be 1..10')
    source_dir = Path(data_directory).resolve(strict=True)
    files = sorted(source_dir.glob('*.txt'))
    if not files:
        raise ValueError('No .txt WoS full-record exports in data_directory')
    if len(files) > 500 or sum(x.stat().st_size for x in files) > 500 * 1024**2:
        raise ValueError('Dataset exceeds local safety limit: 500 files / 500 MiB')
    receipts = []
    for s in sources:
        if not s.get('title') or not s.get('url') or not s.get('note'):
            raise ValueError('Each research source needs title/url/note')
        if not s['url'].startswith(('https://', 'http://')):
            raise ValueError('Source URLs must be HTTP(S)')
        receipts.append({**s, 'recorded_utc': now(), 'verification': 'agent supplied; consult original URL'})
    selected, seen, removed = [], {}, []
    total, coverage = 0, Counter()
    fingerprints = [{'path': str(f), 'sha256': digest(f), 'bytes': f.stat().st_size} for f in files]
    for f in files:
        for r in parse_wos(f):
            total += 1
            v = r['fields']
            key = v.get('UT') or ('doi:' + v['DI'].lower() if v.get('DI') else 'raw:' + hashlib.sha256(r['raw'].encode()).hexdigest())
            year = v.get('PY', '')
            if not year.isdigit():
                removed.append({'id': key, 'reason': 'missing_or_invalid_year'})
                continue
            if not start_year <= int(year) <= end_year:
                removed.append({'id': key, 'reason': 'outside_year_range', 'year': year})
                continue
            if key in seen:
                if seen[key] != r['raw']:
                    raise ValueError(f'Conflicting duplicate record {key}; resolve source data before analysis')
                removed.append({'id': key, 'reason': 'identical_duplicate'})
                continue
            seen[key] = r['raw']
            r['record_id'] = key
            selected.append(r)
            coverage.update(t for t in ['TI','AB','DE','ID','CR','DI','AU','C1','C3'] if v.get(t))
    if not selected:
        raise ValueError('No eligible records in requested time window')
    required = {'Reference':['CR'], 'Cited Author':['CR'], 'Cited Journal':['CR'], 'Keyword':['DE','ID'], 'Author':['AU'], 'Country':['C1'], 'Institution':['C1','C3']}[node_type]
    if not any(coverage[t] for t in required):
        raise ValueError(f'Missing required fields {required}; cannot construct requested network')
    run_id = datetime.now().strftime('%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex[:8]
    p = root() / run_id
    (p / 'data').mkdir(parents=True, exist_ok=False)
    (p / 'project').mkdir()
    exported = p / 'data' / 'download_records.txt'
    # This is the tagged interchange format name, not a database/provider claim.
    # Preserve the actual incoming headers and hashes in the audit sidecar.
    exported.write_text('FN ISI Export Format\nVR 1.0\n' + '\n\n'.join(r['raw'] for r in selected) + '\n\nEF\n', encoding='utf-8')
    with (p / 'records.jsonl').open('w', encoding='utf-8') as f:
        for r in selected:
            f.write(json.dumps({k:v for k,v in r.items() if k != 'raw'}, ensure_ascii=False) + '\n')
    audit = {'input_records': total, 'included_records': len(selected), 'removed': removed,
             'field_coverage': dict(coverage), 'years': dict(sorted(Counter(r['fields']['PY'] for r in selected).items())),
             'input_files': fingerprints, 'prepared_sha256': digest(exported),
             'input_headers': [{'path': str(f), 'header': f.read_text(encoding='utf-8-sig').splitlines()[0]} for f in files],
             'prepared_format': 'ISI tagged interchange syntax; format compatibility, not database provenance',
             'scope': 'Supplied corpus, not asserted to be an exhaustive database search',
             'current_year_partial': end_year == datetime.now().year}
    save(p / 'data_audit.json', audit)
    save(p / 'sources.json', receipts)
    m = {'schema': 1, 'run_id': run_id, 'title': title, 'project_title': 'MCP-' + run_id,
         'research_question': research_question, 'rationale': rationale, 'created_utc': now(),
         'state': 'prepared', 'source_directory': str(source_dir),
         'spec': {'start_year': start_year, 'end_year': end_year, 'node_type': node_type, 'k': k,
                  'years_per_slice': years_per_slice, 'pathfinder': pathfinder},
         'engine': 'CiteSpace 6.4.R2 Basic', 'corpus_sha256': digest(exported)}
    checkpoint(p, m, 'prepared')
    return {'ok': True, 'run_id': run_id, 'directory': str(p), 'manifest': m,
            'audit': {k:v for k,v in audit.items() if k not in ['removed','input_files']}, 'excluded_count': len(removed)}


def ui(window_title=None):
    driver, window, error = B._get_driver(window_title)
    if not driver:
        raise RuntimeError(error)
    es, _, truncated = B._collect_accessible_elements(driver, 12000)
    if truncated:
        raise RuntimeError('Accessibility tree truncated; no action performed')
    return driver, window, es


def find(es, role, name):
    matches = [e for e,s in es if e.role_en_us == role and (e.name or '').strip() == name]
    if len(matches) != 1:
        raise RuntimeError(f'Expected one {role} {name!r}; found {len(matches)}')
    return matches[0]


def main_ui():
    windows = B._window_records()
    main = [w for w in windows if w['visible'] and w['title'].startswith('CiteSpace 6.4.R2')]
    extra = [w for w in windows if w['visible'] and w not in main]
    if len(main) != 1 or extra:
        raise RuntimeError('Expected only an idle CiteSpace main frame; inspect/close extra windows first: ' + str([w['title'] for w in windows]))
    d,w,es = ui(main[0]['title'])
    if 'enabled' in find(es,'push button','Stop').states_en_us:
        raise RuntimeError('Analysis is already running; will not interrupt or start another')
    return d,w,es


def activate(run_id):
    p,m = read_manifest(run_id)
    if m['state'] not in ['prepared','activated','configured']:
        raise ValueError('Run already submitted; do not replay. Inspect it or create a new run.')
    # A previous workflow's verified result view may still be open. Close only
    # managed, completed views before the next project; never dismiss unknown UI.
    for window in B._window_records():
        if window['visible'] and window['title'].startswith('CiteSpace: Display Merged') and 'Project Home: ' in window['title']:
            prior_project=Path(window['title'].split('Project Home: ',1)[1])
            if prior_project.parent.parent.resolve()==root().resolve():
                finish_view(prior_project.parent.name)
    if B._window_records():
        d,w,es = main_ui()
        checkpoint(p,m,'closing_idle_app',state='prepared')
        # Window-manager Close hides this app's frame but can leave its JVM alive.
        # Use its real File > Exit action so settings are saved and JVM terminates.
        file_menu=find(es,'menu','File')
        exit_items=[e for e in file_menu._generate_all_childs(visible=False) if e.role_en_us=='menu item' and (e.name or '').strip()=='Exit']
        if len(exit_items)!=1 or 'enabled' not in exit_items[0].states_en_us:
            raise RuntimeError('Cannot identify the native File > Exit action')
        exit_items[0].click(simulate=False)
        deadline = time.monotonic()+12
        while B._window_records() and time.monotonic()<deadline:
            time.sleep(.25)
        if B._window_records():
            raise RuntimeError('CiteSpace did not close normally; no registry change made')
        if B._PENDING_LAUNCH is not None:
            try:
                B._PENDING_LAUNCH.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # JAB can retain a background JVM after File > Exit disposed all
                # windows. Retire ONLY our own child, after verified idle + Exit
                # + no surviving CiteSpace windows. Never kill a running analysis.
                if B._PENDING_LAUNCH.pid!=w['process_id'] or B._window_records():
                    raise RuntimeError('Cannot safely retire the old JVM; no second instance launched')
                checkpoint(p,m,'retiring_owned_disposed_jvm',retired_pid=w['process_id'])
                B._PENDING_LAUNCH.terminate()
                B._PENDING_LAUNCH.wait(timeout=10)
        B._DRIVER = B._DRIVER_HWND = None
    registry = Path.home() / 'citespace.projects.txt'
    original = registry.read_bytes() if registry.exists() else b''
    backup = p / ('registry-before-' + uuid.uuid4().hex[:8] + '.txt')
    backup.write_bytes(original)
    old_text = original.decode('utf-8-sig')
    blocks = [b for b in re.split(r'\r?\n\s*\r?\n',old_text.strip()) if b.strip()]
    blocks = [b for b in blocks if not b.startswith('Title:'+m['project_title']+'\n') and not b.startswith('Title:'+m['project_title']+'\r\n')]
    s=m['spec']
    block = '\n'.join(['Title:'+m['project_title'], 'TimeStamp:'+now(), 'ProjectHome:'+str(p/'project'),
                       'DataHome:'+str(p/'data'), 'DataSource:WoS', 'Language:English',
                       'Description:'+m['research_question'], 'Begin:'+str(s['start_year']), 'End:'+str(s['end_year']),
                       'LinkRetainingFactor:2.5','MaxLinksPerNode:10','LookBackYears:5',
                       'MinimumThresholdValue:1.0','LinkWeightModificationRate:1.0E-11'])
    registry.write_text(block+'\n\n'+'\n\n'.join(blocks)+'\n\n',encoding='utf-8')
    checkpoint(p,m,'project_registered',registry_backup=str(backup),state='activated')
    launch = json.loads(B.citespace_launch(confirm_launch=True))
    return {'ok': launch.get('ok',False), 'run_id':run_id, 'startup':launch, 'next':'Configure after main_frame_ready; activation preserves all other projects'}


def settings(es):
    combos=[e for e,s in es if e.role_en_us=='combo box']
    selected=[str(e.get_selected_element().name).strip() for e in combos]
    texts=[str(e.text).strip() for e,s in es if e.role_en_us=='text']
    editable=[e for e,s in es if e.role_en_us=='text' and 'editable' in s]
    return {'combos':selected, 'text':texts[:5],
            'node_types':[(e.name or '').strip() for e,s in es if e.role_en_us=='radio button' and 'checked' in s and (e.name or '').strip() in NODE_TYPES],
            'k':str(editable[0].text).strip() if len(editable)==1 else None,
            'pruning':{(e.name or '').strip():'checked' in s for e,s in es if e.role_en_us=='check box' and (e.name or '').strip() in ['Pathfinder','Minimum Spanning Tree','Pruning sliced networks','Pruning the merged network']}}


def verify_settings(p,m,actual):
    s=m['spec']; c=actual['combos']
    if len(c)!=9 or c[0]!=m['project_title'] or str(p/'project') not in actual['text'] or str(p/'data') not in actual['text']:
        raise RuntimeError('Selected project or paths do not match isolated run')
    if c[2:7] != [str(s['start_year']),'JAN',str(s['end_year']),'DEC',str(s['years_per_slice'])]:
        raise RuntimeError('Time slicing readback differs from requested settings: '+str(c[2:7]))
    if c[7:]!=['Cosine','Within Slices'] or actual['node_types']!=[s['node_type']] or actual['k']!=str(s['k']):
        raise RuntimeError('Node/link/selection settings differ from requested settings: '+str(actual))
    expected={'Pathfinder':s['pathfinder'],'Minimum Spanning Tree':False,'Pruning sliced networks':False,'Pruning the merged network':False}
    if actual['pruning']!=expected:
        raise RuntimeError('Pruning readback differs from requested settings: '+str(actual['pruning']))


def configure(run_id):
    p,m=read_manifest(run_id)
    if m['state'] not in ['activated','configured']:
        raise ValueError('Activate a fresh run before configuration')
    d,w,es=main_ui()
    combos=[e for e,s in es if e.role_en_us=='combo box']
    if len(combos)!=9:
        raise RuntimeError('Unexpected main-frame selector layout')
    combos[0].select(m['project_title'],simulate=False,wait_for_selection=False)
    time.sleep(.3)
    d,w,es=main_ui(); combos=[e for e,s in es if e.role_en_us=='combo box']; s=m['spec']
    for e,v in zip(combos[2:], [str(s['start_year']),'JAN',str(s['end_year']),'DEC',str(s['years_per_slice']),'Cosine','Within Slices']):
        if str(e.get_selected_element().name).strip()!=v:
            e.select(v,simulate=False,wait_for_selection=False)
    for name in sorted(NODE_TYPES):
        e=find(es,'radio button',name)
        if ('checked' in e.states_en_us)!=(name==s['node_type']):
            e.click(simulate=False)
    time.sleep(.2)
    d,w,es=main_ui()
    tabs=[e for e,st in es if e.role_en_us=='page tab list' and e.name in ['g-index','Top N','Top N%']]
    if len(tabs)!=1:
        raise RuntimeError('Cannot identify selection criteria tabs')
    if tabs[0].name!='g-index':
        tabs[0].select('g-index',simulate=False,wait_for_selection=False)
    d,w,es=main_ui()
    editable=[e for e,st in es if e.role_en_us=='text' and 'editable' in st]
    if len(editable)!=1:
        raise RuntimeError('Expected unique g-index field')
    editable[0].send_text(str(s['k']),simulate=False)
    for name,value in [('Pathfinder',s['pathfinder']),('Minimum Spanning Tree',False),('Pruning sliced networks',False),('Pruning the merged network',False)]:
        e=find(es,'check box',name)
        if ('checked' in e.states_en_us)!=value:
            e.click(simulate=False)
    time.sleep(.2)
    d,w,es=main_ui(); actual=settings(es);verify_settings(p,m,actual)
    save(p/'verified_settings.json',{'utc':now(),'window':w,'actual':actual})
    checkpoint(p,m,'settings_verified',state='configured')
    return {'ok':True,'run_id':run_id,'settings':actual}


def start(run_id):
    p,m=read_manifest(run_id)
    if m['state']!='configured':
        raise ValueError('Start requires configured state; submitted runs are never blindly replayed')
    d,w,es=main_ui();verify_settings(p,m,settings(es))
    if digest(p/'data'/'download_records.txt')!=m['corpus_sha256']:
        raise ValueError('Prepared corpus changed after audit')
    go=find(es,'push button','GO!')
    if 'enabled' not in go.states_en_us:
        raise RuntimeError('GO is disabled')
    if list((p/'project').glob('*.graphml')):
        raise RuntimeError('Pre-existing graph outputs in fresh run; refusing ambiguous provenance')
    checkpoint(p,m,'start_reserved',state='submitted',started_epoch=time.time(),started_utc=now(),process_id=w['process_id'])
    go.click(simulate=False)
    return {'ok':True,'run_id':run_id,'state':'submitted','completion_claim':False,'next':'Poll; do not issue another start'}


def poll(run_id, export=False):
    p,m=read_manifest(run_id)
    files=[{'name':f.name,'bytes':f.stat().st_size,'mtime':f.stat().st_mtime} for f in (p/'project').iterdir() if f.is_file()]
    windows=B._window_records()
    if m['state'] in ['submitted','export_requested']:
        for w in windows:
            if w['title']=='Your Options' and w['process_id']==m.get('process_id'):
                d,_,es=ui('Your Options')
                labels='\n'.join(str(e.name or '') for e,s in es if e.role_en_us in ['label','text'])
                if m['project_title'] not in labels:
                    raise RuntimeError('Completion dialog belongs to another project')
                save(p/'completion_dialog.json',{'utc':now(),'labels':labels})
                if export and m['state']=='submitted':
                    target=find(es,'push button','Visualize')
                    checkpoint(p,m,'export_reserved',state='export_requested')
                    target.click(simulate=False)
                return {'ok':True,'state':m['state'],'completion_dialog':labels,'files':files,'next':'Poll for fresh GraphML; Visualize requests CiteSpace export' if export else 'Call poll with export=true'}
        graphs=[f for f in (p/'project').glob('*.graphml') if f.stat().st_size>0 and f.stat().st_mtime>=m.get('started_epoch',float('inf'))]
        if graphs:
            selected=max(graphs,key=lambda f:f.stat().st_mtime)
            signature={'path':selected.name,'bytes':selected.stat().st_size,'sha256':digest(selected)}
            if m.get('observed_graph')==signature:
                parsed=parse_graph(selected)
                checkpoint(p,m,'graph_verified',state='graph_ready',graph=signature,graph_counts={'nodes':len(parsed['nodes']),'edges':len(parsed['edges'])})
            else:
                checkpoint(p,m,'graph_observed',observed_graph=signature)
    return {'ok':True,'run_id':run_id,'state':m['state'],'files':files,'windows':windows,
            'next':'analyze_graph' if m['state'] in ['graph_ready','analyzed','reported'] else 'Inspect visible dialogs or poll; an idle window alone is not completion'}


def parse_graph(path):
    path=Path(path)
    if path.stat().st_size>100*1024**2:
        raise ValueError('GraphML exceeds 100 MiB safety limit')
    raw=path.read_bytes()
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD/entity declarations are not accepted')
    doc=ET.fromstring(raw); ns={'g':'http://graphml.graphdrawing.org/xmlns'}
    keys={(e.get('for','all'),e.get('id')):(e.get('attr.name',e.get('id')),e.get('attr.type','string')) for e in doc.findall('g:key',ns)}
    graphs=doc.findall('g:graph',ns)
    if len(graphs)!=1:
        raise ValueError('Expected exactly one graph')
    graph=graphs[0];directed=graph.get('edgedefault')=='directed'
    def attrs(e,scope):
        out={}
        for v in e.findall('g:data',ns):
            name,kind=keys.get((scope,v.get('key')),keys.get(('all',v.get('key')),(v.get('key'),'string')))
            value=''.join(v.itertext()).strip()
            if kind in ['double','float','int','integer','long'] and value:
                value=float(value)
                if not math.isfinite(value): raise ValueError('Non-finite graph attribute')
                if kind in ['int','integer','long']: value=int(value)
            out[name]=value
        return out
    nodes=[];ids=set()
    for e in graph.findall('g:node',ns):
        if not e.get('id') or e.get('id') in ids: raise ValueError('Missing/duplicate node ID')
        ids.add(e.get('id'));nodes.append({'id':e.get('id'),'attributes':attrs(e,'node')})
    edges=[]
    for e in graph.findall('g:edge',ns):
        if e.get('source') not in ids or e.get('target') not in ids: raise ValueError('Dangling edge endpoint')
        edges.append({'source':e.get('source'),'target':e.get('target'),'attributes':attrs(e,'edge')})
    if not nodes: raise ValueError('Empty network')
    return {'nodes':nodes,'edges':edges,'directed':directed}


def analyze(run_id, limit=20):
    p,m=read_manifest(run_id)
    if m['state'] not in ['graph_ready','analyzed','reported']:
        raise ValueError('Poll and verify a fresh graph first')
    gpath=p/'project'/m['graph']['path']
    if digest(gpath)!=m['graph']['sha256']:
        raise ValueError('Graph changed after verification; start a distinct analysis rather than mixing outputs')
    g=parse_graph(gpath);adj={n['id']:set() for n in g['nodes']};pairs=set();loops=0
    for e in g['edges']:
        a,b=e['source'],e['target']
        if a==b: loops+=1;continue
        adj[a].add(b);adj[b].add(a);pairs.add((a,b) if g['directed'] else tuple(sorted((a,b))))
    remaining=set(adj);components=[]
    while remaining:
        start_id=min(remaining);stack=[start_id];remaining.remove(start_id);members=[]
        while stack:
            a=stack.pop();members.append(a)
            for b in sorted(adj[a]&remaining): remaining.remove(b);stack.append(b)
        components.append(members)
    for n in g['nodes']: n['derived_degree']=len(adj[n['id']])
    ranked=sorted(g['nodes'],key=lambda n:(-float(n['attributes'].get('freq',0) or 0),-n['derived_degree'],n['id']))
    n=len(g['nodes']); denom=n*(n-1) if g['directed'] else n*(n-1)/2
    prior_metrics=json.loads((p/'graph_summary.json').read_text(encoding='utf-8')) if (p/'graph_summary.json').exists() else {}
    metrics={'nodes':n,'exported_edges':len(g['edges']),'unique_nonself_edges':len(pairs),'self_loops':loops,
             'density_derived':len(pairs)/denom if denom else 0,
             'weak_components_derived':len(components),'largest_component_nodes_derived':max(map(len,components)),
             'centrality_values_present':sum('centrality' in x['attributes'] for x in g['nodes']),
             'cluster_labels_present':sum(any(k in x['attributes'] for k in ['cluster','cluster_id']) for x in g['nodes']),
             'Q':None,'silhouette':None,'burst_strength':None,
             'export_completeness':'unverified_against_native_display',
             'export_warning':'Exactly 1000 exported edges: inspect native network count for possible export truncation' if len(g['edges'])==1000 else None,
             'missing_metric_policy':'Not inferred from default configuration zeros, screenshots or missing GraphML attributes'}
    for key in ['native_display_nodes','native_display_edges','native_count_evidence']:
        if key in prior_metrics: metrics[key]=prior_metrics[key]
    if 'native_count_evidence' in prior_metrics:
        metrics['export_completeness']=prior_metrics['export_completeness']
        metrics['export_warning']=prior_metrics.get('export_warning')
    save(p/'graph_parsed.json',g);save(p/'graph_summary.json',metrics)
    with (p/'nodes.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['id','label','frequency','degree_derived','centrality_exported'])
        for x in ranked: writer.writerow([x['id'],x['attributes'].get('label',x['attributes'].get('name','')),x['attributes'].get('freq',''),x['derived_degree'],x['attributes'].get('centrality','')])
    save(p/'ranked_nodes.json',ranked)
    checkpoint(p,m,'graph_analyzed',state='analyzed')
    return {'ok':True,'run_id':run_id,'metrics':metrics,'top_nodes':ranked[:max(1,min(limit,100))],
            'artifacts':{'parsed_graph':str(p/'graph_parsed.json'),'nodes_csv':str(p/'nodes.csv')},
            'interpretation_note':'Frequency is within selected corpus/network, not paper quality or global importance. Components are not thematic clusters.'}


def verify_native_counts(run_id, nodes, edges, evidence_filename):
    p,m=read_manifest(run_id)
    if m['state'] not in ['analyzed','reported']:
        raise ValueError('Analyze exported graph first')
    if Path(evidence_filename).name!=evidence_filename:
        raise ValueError('Use a capture filename within this run')
    f=p/evidence_filename
    if not f.is_file() or not f.name.startswith('native-view-') or f.suffix!='.png':
        raise ValueError('An actual native capture from this run is required')
    if nodes<=0 or edges<0: raise ValueError('Invalid native counts')
    metrics=json.loads((p/'graph_summary.json').read_text(encoding='utf-8'))
    match=metrics['nodes']==nodes and metrics['exported_edges']==edges
    metrics.update(native_display_nodes=nodes,native_display_edges=edges,
                   export_completeness='counts_match_not_edgewise_verified' if match else 'INCOMPLETE_OR_DIFFERENT_FROM_NATIVE',
                   native_count_evidence={'file':f.name,'sha256':digest(f),'method':'Codex visual transcription; inspect image for audit'},
                   export_warning=None if match else 'Native and exported counts differ. Derived graph statistics describe only the exported graph, not the full native network.')
    save(p/'graph_summary.json',metrics);checkpoint(p,m,'native_counts_compared',native_count_match=match)
    return {'ok':True,'counts_match':match,'metrics':metrics}


def neighborhood(run_id, node_id, limit=20):
    p,m=read_manifest(run_id)
    if m['state'] not in ['analyzed','reported'] or not 1<=limit<=100:
        raise ValueError('Analyze first; limit must be 1..100')
    if digest(p/'project'/m['graph']['path'])!=m['graph']['sha256']:
        raise ValueError('Native export changed since analysis')
    graph=json.loads((p/'graph_parsed.json').read_text(encoding='utf-8'))
    nodes={n['id']:n for n in graph['nodes']}
    if node_id not in nodes: raise ValueError('Unknown native node ID')
    edges=[e for e in graph['edges'] if node_id in [e['source'],e['target']]]
    edges.sort(key=lambda e:-float(e['attributes'].get('weight',0) or 0))
    selected=edges[:limit];neighbors={e['target'] if e['source']==node_id else e['source'] for e in selected}
    return {'ok':True,'node':nodes[node_id],'incident_edges':len(edges),'edges':selected,
            'neighbors':[nodes[i] for i in sorted(neighbors)],'truncated':len(edges)>limit,
            'scope':'Verified exported GraphML only; consult graph_summary for native/export completeness. Edge weight is not causal influence.'}


def evidence(run_id, query='', offset=0, limit=10):
    p,m=read_manifest(run_id);out=[];total=0
    if offset<0 or not 1<=limit<=30: raise ValueError('offset>=0 and limit1..30 required')
    for line in (p/'records.jsonl').read_text(encoding='utf-8').splitlines():
        r=json.loads(line)
        if query.casefold().startswith('doi:'):
            matches=r['fields'].get('DI','').casefold()==query[4:].strip().casefold()
        else:
            matches=query.casefold() in json.dumps(r['fields'],ensure_ascii=False).casefold()
        if not matches: continue
        if offset<=total<offset+limit:
            out.append({'record_id':r['record_id'],'fields':{k:v[:12000] for k,v in r['fields'].items() if k in ['TI','AB','AU','PY','DI','DE','ID','SO','UT']}})
        total+=1
    return {'ok':True,'total':total,'offset':offset,'records':out,'next_offset':offset+limit if offset+limit<total else None}


def add_sources(run_id, sources):
    p,m=read_manifest(run_id);path=p/'sources.json';existing=json.loads(path.read_text(encoding='utf-8'))
    for s in sources:
        if not all(s.get(k) for k in ['title','url','note']) or not s['url'].startswith(('https://','http://')):
            raise ValueError('Each source needs title, HTTP(S) URL and an accurate reading note')
    ids=[]
    for s in sources:
        match=next((i for i,x in enumerate(existing) if all(x.get(k)==s.get(k) for k in ['title','url','note'])),None)
        if match is None:
            existing.append({**s,'recorded_utc':now(),'verification':'agent supplied; consult original URL'});match=len(existing)-1
        ids.append('source:'+str(match+1))
    save(path,existing);checkpoint(p,m,'research_sources_added',source_count=len(existing))
    return {'ok':True,'evidence_ids':ids,'sources':existing}


def read_artifact(run_id, filename, offset=0, limit=12000):
    p,m=read_manifest(run_id)
    if Path(filename).name!=filename or filename in ['.','..']:
        raise ValueError('Provide an exact project filename, not a path')
    path=p/'project'/filename
    if path.suffix.lower() not in ['.json','.txt','.csv','.out','.in','.parameters']:
        raise ValueError('Text artifacts only; use analyze_graph for GraphML')
    if not 0<=offset or not 100<=limit<=30000 or path.stat().st_size>50*1024**2:
        raise ValueError('Invalid bounds or text artifact too large')
    text=path.read_text(encoding='utf-8-sig',errors='strict')
    return {'ok':True,'file':filename,'sha256':digest(path),'offset':offset,'content':text[offset:offset+limit],
            'next_offset':offset+limit if offset+limit<len(text) else None,'warning':'Inspect source mapping and semantics before interpreting raw statistics; config defaults are not calculated results'}


def search_literature(query, limit=8, doi=''):
    if not 1<=limit<=20: raise ValueError('limit must be1..20')
    url='https://api.crossref.org/works/' + urllib.parse.quote(doi,safe='') if doi else 'https://api.crossref.org/works?'+urllib.parse.urlencode({'query.bibliographic':query,'rows':limit})
    req=urllib.request.Request(url,headers={'User-Agent':'CiteSpaceResearchMCP/0.2 (bibliographic metadata research)'})
    with urllib.request.urlopen(req,timeout=25) as response:
        data=json.loads(response.read(8*1024**2))
    items=[data['message']] if doi else data['message']['items']
    out=[{'doi':r.get('DOI'),'title':r.get('title',[]),'publisher':r.get('publisher'),'venue':r.get('container-title',[]),
          'published':r.get('published'),'url':r.get('URL'),'abstract':r.get('abstract'),'reference_count':r.get('reference-count'),
          'source':'Crossref metadata; not a full-text reading'} for r in items]
    receipt={'utc':now(),'query':query,'doi':doi,'request_url':url,'results':out}
    folder=root()/'literature_receipts';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(datetime.now().strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.json');save(path,receipt)
    return {'ok':True,**receipt,'receipt_file':str(path),'corpus_warning':'Discovery metadata is NOT a complete citation corpus; use full-record exports for mapping'}


def capture_view(run_id, window_title, close_after=False):
    p,m=read_manifest(run_id)
    if m['state'] not in ['graph_ready','analyzed','reported']:
        raise ValueError('Only verified completed runs may capture/close a result view')
    windows=[w for w in B._window_records() if w['title']==window_title and w['visible'] and w['process_id']==m.get('process_id')]
    if len(windows)!=1: raise ValueError('Expected one exact-title window belonging to this run process')
    w=windows[0]
    if w['window_class']!='SunAwtFrame' or not w['title'].startswith('CiteSpace: Display Merged') or str(p/'project') not in w['title']:
        raise ValueError('Select a result frame, not the main frame or a dialog')
    import ctypes
    import win32gui
    import win32ui
    from PIL import Image
    hwnd=w['hwnd']
    set_dpi=ctypes.windll.user32.SetThreadDpiAwarenessContext
    set_dpi.argtypes=[ctypes.c_void_p];set_dpi.restype=ctypes.c_void_p
    previous_dpi=set_dpi(ctypes.c_void_p(-4))
    if not previous_dpi: raise RuntimeError('Cannot establish native per-monitor DPI capture context')
    r=win32gui.GetWindowRect(hwnd);width,height=r[2]-r[0],r[3]-r[1]
    dc=win32gui.GetWindowDC(hwnd);src=win32ui.CreateDCFromHandle(dc);dest=src.CreateCompatibleDC();bitmap=win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(src,width,height);dest.SelectObject(bitmap)
    image_path=p/('native-view-'+uuid.uuid4().hex[:8]+'.png')
    try:
        if not ctypes.windll.user32.PrintWindow(hwnd,dest.GetSafeHdc(),0): raise RuntimeError('Native window capture failed')
        Image.frombuffer('RGB',(width,height),bitmap.GetBitmapBits(True),'raw','BGRX',0,1).save(image_path)
    finally:
        dest.DeleteDC();src.DeleteDC();win32gui.ReleaseDC(hwnd,dc);win32gui.DeleteObject(bitmap.GetHandle())
        set_dpi(previous_dpi)
    if close_after:
        win32gui.PostMessage(hwnd,0x10,0,0)
        close_deadline=time.monotonic()+5
        while win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd) and time.monotonic()<close_deadline:
            time.sleep(.1)
        if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
            raise RuntimeError('View was captured but close was not confirmed: '+str(B._window_records()))
    checkpoint(p,m,'result_view_captured',native_capture=str(image_path))
    return {'ok':True,'image':str(image_path),'window':w,'closed':close_after,'visual_inspection_required':True}


def finish_view(run_id):
    p,m=read_manifest(run_id)
    if m['state'] not in ['graph_ready','analyzed','reported']:
        raise ValueError('Cannot close unfinished research views')
    windows=B._window_records()
    matching=[w for w in windows if w['visible'] and w['process_id']==m.get('process_id') and w['title'].startswith('CiteSpace: Display Merged') and str(p/'project') in w['title']]
    if len(matching)!=1:
        raise ValueError('Expected one live completed result view')
    result=capture_view(run_id,matching[0]['title'],close_after=True)
    import win32gui
    for window in B._window_records():
        if window['process_id']==m['process_id'] and window['visible'] and window['title']=='Control Panel':
            win32gui.PostMessage(window['hwnd'],0x10,0,0)
    time.sleep(.5)
    result['remaining_windows']=B._window_records()
    return result


def render_report(run_id, sections):
    p,m=read_manifest(run_id)
    if m['state'] not in ['analyzed','reported']: raise ValueError('Analyze the real exported graph before reporting')
    g=json.loads((p/'graph_parsed.json').read_text(encoding='utf-8'));metrics=json.loads((p/'graph_summary.json').read_text(encoding='utf-8'))
    sources=json.loads((p/'sources.json').read_text(encoding='utf-8'));audit=json.loads((p/'data_audit.json').read_text(encoding='utf-8'))
    valid={'graph:summary'}|{'node:'+n['id'] for n in g['nodes']}|{'source:'+str(i+1) for i in range(len(sources))}
    for r in (p/'records.jsonl').read_text(encoding='utf-8').splitlines(): valid.add('record:'+json.loads(r)['record_id'])
    for s in sections:
        if not s.get('heading') or not s.get('text') or not s.get('evidence_ids'): raise ValueError('Each interpretation section needs heading/text/evidence_ids')
        unknown=set(s['evidence_ids'])-valid
        if unknown: raise ValueError('Unknown evidence IDs: '+str(sorted(unknown)))
    if not sections: raise ValueError('Codex must supply evidence-grounded interpretation; numerical summary alone is not a research report')
    ranked=json.loads((p/'ranked_nodes.json').read_text(encoding='utf-8'))
    # Deterministic circular layout; no invented thematic clusters or native-layout claim.
    positions={n['id']:(500+410*math.cos(2*math.pi*i/len(ranked)),500+410*math.sin(2*math.pi*i/len(ranked))) for i,n in enumerate(ranked)}
    svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1060"><rect width="1000" height="1060" fill="white"/>']
    for e in g['edges']:
        a,b=positions[e['source']],positions[e['target']]
        svg.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#4682b4" stroke-opacity=".12"/>')
    for node in ranked:
        x,y=positions[node['id']];label=node['attributes'].get('label',node['id']);r=3+min(8,math.sqrt(float(node['attributes'].get('freq',1) or 1)))
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" fill="#147bd1"><title>{html.escape(str(label))}</title></circle>')
    svg.append('<text x="25" y="1040" font-size="18">CiteSpace GraphML edges; derived circular layout, not a cluster/timeline map.</text></svg>')
    (p/'network.svg').write_text('\n'.join(svg),encoding='utf-8')
    lines=['# '+m['title'],'',m['research_question'],'','## 方法与数据','',
           f"引擎：{m['engine']}；节点类型：{m['spec']['node_type']}；年份：{m['spec']['start_year']}–{m['spec']['end_year']}；切片：{m['spec']['years_per_slice']}年；g-index k={m['spec']['k']}。",
           '',m['rationale'],'',f"输入 {audit['input_records']} 条，按登记规则纳入 {audit['included_records']} 条。分析范围仅限本次提供的数据；当年数据可能尚不完整。",'',
           '## 图谱回读结果','',f"节点 {metrics['nodes']}；边 {metrics['exported_edges']}；根据导出边计算的密度 {metrics['density_derived']:.6f}；连通分量 {metrics['weak_components_derived']}；最大分量 {metrics['largest_component_nodes_derived']} 个节点。",'',
           '![由真实 GraphML 重绘的网络](network.svg)','',
           '图中为真实导出的节点与边，采用确定性环形布局，不是 CiteSpace 原生布局或主题聚类。Q、轮廓值及突现强度未在本次图谱回读中验证，故不填造数值。','',
           '## 高频节点','', '|节点ID|节点|网络内频次|导出图度数|','|---|---|---:|---:|']
    for n in ranked[:20]:
        a=n['attributes'];lines.append('|'+n['id']+'|'+str(a.get('label',a.get('name',''))).replace('|','/')+'|'+str(a.get('freq','未提供'))+'|'+str(n['derived_degree'])+'|')
    lines.extend(['','## 原生图与导出图一致性','',str(metrics.get('export_completeness','未核查')),
                  '', '软件界面节点/边：'+str(metrics.get('native_display_nodes','未读取'))+'/'+str(metrics.get('native_display_edges','未读取'))+
                  '；GraphML 节点/边：'+str(metrics['nodes'])+'/'+str(metrics['exported_edges'])+'。',
                  '',metrics.get('export_warning') or '若计数相同，也不等于已经逐边核对。派生指标仅描述这份导出的 GraphML。'])
    if m.get('native_capture'):
        lines.extend(['','![CiteSpace 原生可视化截图]('+Path(m['native_capture']).name+')'])
    for s in sections:
        lines.extend(['','## '+s['heading'],'',s['text'],'','证据索引：'+', '.join(s['evidence_ids'])])
    lines.extend(['','## 调研资料',''])
    for i,s in enumerate(sources,1): lines.append(f"{i}. [{s['title']}]({s['url']}) — {s['note']}")
    lines.extend(['','## 可复核附件','', 'manifest.json；data_audit.json；verified_settings.json；completion_dialog.json；graph_summary.json；nodes.csv；graph_parsed.json；原生 project/*.graphml；events.jsonl。', '',
                  '解释边界：共现/共被引不是因果关系，频次不是质量；主题名称需回到文献核对。证据ID保证可定位，不自动保证文字推论正确。'])
    report='\n'.join(lines)
    version=datetime.now().strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:4]
    report_dir=p/'reports'/version;report_dir.mkdir(parents=True)
    (report_dir/'report.md').write_text(report,encoding='utf-8');shutil.copy2(p/'network.svg',report_dir/'network.svg')
    if m.get('native_capture'):
        shutil.copy2(m['native_capture'],report_dir/Path(m['native_capture']).name)
    # HTML is standalone, no remote scripts/resources and no browser automation.
    native_html=''
    if m.get('native_capture'):
        encoded=base64.b64encode(Path(m['native_capture']).read_bytes()).decode('ascii')
        native_html='<h2>CiteSpace 原生图</h2><img style="width:100%" src="data:image/png;base64,'+encoded+'">'
    esc=lambda x:html.escape(str(x))
    body='<h1>'+esc(m['title'])+'</h1><p>'+esc(m['research_question'])+'</p>'
    body+='<h2>方法与数据</h2><p>'+esc(m['engine'])+'；'+esc(m['spec']['node_type'])+'；'+str(m['spec']['start_year'])+'—'+str(m['spec']['end_year'])+'；k='+str(m['spec']['k'])+'。</p><p>'+esc(m['rationale'])+'</p>'
    body+='<p>源记录 '+str(audit['input_records'])+' 条，纳入 '+str(audit['included_records'])+' 条；仅描述本次提供的语料，不声称完整覆盖领域。</p>'
    body+='<h2>图谱回读</h2><p>GraphML：'+str(metrics['nodes'])+' 个节点，'+str(metrics['exported_edges'])+' 条边；导出图密度 '+format(metrics['density_derived'],'.6f')+'。</p>'
    body+='<div class="audit"><b>原生图与导出图一致性：</b>'+esc(metrics.get('export_completeness','未核查'))+'<p>原生 N/E：'+esc(metrics.get('native_display_nodes','未读取'))+'/'+esc(metrics.get('native_display_edges','未读取'))+'。'+esc(metrics.get('export_warning') or '计数一致也不等于逐边核查。')+'</p></div>'
    body+=native_html+'<h2>导出图重绘</h2>'+''.join(svg)+'<p>确定性环形布局，不是原生聚类图。Q、轮廓值及突现强度本次未核实，未填造数值。</p>'
    body+='<h2>高频节点</h2><table><tr><th>ID</th><th>节点</th><th>网络内频次</th><th>导出图度数</th></tr>'
    for node in ranked[:20]:
        a=node['attributes'];body+='<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [node['id'],a.get('label',a.get('name','')),a.get('freq','未提供'),node['derived_degree']])+'</tr>'
    body+='</table>'
    for s in sections: body+='<h2>'+esc(s['heading'])+'</h2><p>'+esc(s['text']).replace('\n','<br>')+'</p><p class="evidence">证据索引：'+esc(', '.join(s['evidence_ids']))+'</p>'
    body+='<h2>调研资料</h2><ol>'
    for s in sources: body+='<li><a href="'+esc(s['url'])+'">'+esc(s['title'])+'</a> — '+esc(s['note'])+'</li>'
    body+='</ol><h2>复核说明</h2><p>共现与共被引不是因果关系，频次不是质量。节点/边/指标、数据纳排、界面配置和动作记录均保存在同一运行目录。运行ID：'+esc(run_id)+'</p>'
    (report_dir/'report.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>CiteSpace research report</title><style>body{max-width:1080px;margin:40px auto;padding:0 24px;font:16px/1.75 Arial,"Microsoft YaHei",sans-serif;color:#182637}h1,h2{color:#146ab2}h2{border-bottom:1px solid #ddd;padding-top:24px}svg{max-height:650px;width:100%}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;border:1px solid #ddd;text-align:left}.audit{background:#fff4d8;padding:16px;border-left:4px solid #d89818}.evidence{font-size:13px;color:#667}a{color:#146ab2}</style>'+body+'</html>',encoding='utf-8')
    save(report_dir/'interpretation.json',sections)
    checkpoint(p,m,'report_written',state='reported',latest_report=str(report_dir))
    return {'ok':True,'run_id':run_id,'report_markdown':str(report_dir/'report.md'),'report_html':str(report_dir/'report.html'),'graph_svg':str(report_dir/'network.svg')}


def register_workflow_tools(server, backend):
    global B
    B=backend
    read=ToolAnnotations(readOnlyHint=True,destructiveHint=False,openWorldHint=False)
    write=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=False)

    def result(fn,*a,**kw):
        try:
            with B._LOCK: return B._json(fn(*a,**kw))
        except Exception as e:
            return B._json({'ok':False,'error':f'{type(e).__name__}: {e}','action':'Inspect state; do not replay a submitted run'})

    @server.tool(annotations=write)
    def citespace_prepare_research(title: str, research_question: str, data_directory: str,
                                  start_year: int, end_year: int, node_type: str, k: int,
                                  rationale: str, sources: list[dict[str,str]],
                                  years_per_slice: int=1, pathfinder: bool=False) -> str:
        """Create isolated run from WoS full-record .txt files; audit years/fields/dedup and preserve provenance. Select node_type using research rationale, not a fixed topic. sources require title,url,note. Does not run CiteSpace."""
        return result(prepare,title,research_question,data_directory,start_year,end_year,node_type,k,rationale,sources,years_per_slice,pathfinder)

    @server.tool(annotations=write)
    def citespace_activate_research(run_id: str) -> str:
        """Activate a prepared isolated project. Normally closes ONLY an idle main frame, backs up and prepends native project registry, restarts CiteSpace and handles known startup dialogs. Refuses extra windows/running analysis. Never alters old datasets/results."""
        return result(activate,run_id)

    @server.tool(annotations=write)
    def citespace_configure_research(run_id: str) -> str:
        """Apply project, dates, node type, g-index k, cosine links and pruning via JAB; verify actual control readback and persist settings. No analysis starts."""
        return result(configure,run_id)

    @server.tool(annotations=write)
    def citespace_start_research(run_id: str) -> str:
        """Start once after settings/corpus verification; persist reservation BEFORE GO. Returned submitted status is not completion. Replays are rejected."""
        return result(start,run_id)

    @server.tool(annotations=write)
    def citespace_poll_research(run_id: str, export: bool=False) -> str:
        """Inspect run/files/dialogs. export=true chooses Visualize only in matching Your Options dialog. Two matching graph hash observations plus valid GraphML establish graph_ready. Never retries GO."""
        return result(poll,run_id,export)

    @server.tool(annotations=write)
    def citespace_analyze_graph(run_id: str, limit: int=20) -> str:
        """Parse verified native GraphML, export nodes CSV, derive density/components/degree and return bounded top nodes. Missing cluster/Q/silhouette/burst metrics remain null, not fabricated zeros."""
        return result(analyze,run_id,limit)

    @server.tool(annotations=read)
    def citespace_read_evidence(run_id: str, query: str='', offset: int=0, limit: int=10) -> str:
        """Search audited corpus by title/keyword (all fields), or query='doi:10.x/...' for exact source-paper DOI. Read original title/abstract/keywords/year with pagination, not invented node interpretations."""
        return result(evidence,run_id,query,offset,limit)

    @server.tool(annotations=write)
    def citespace_record_research_sources(run_id: str, sources: list[dict[str,str]]) -> str:
        """Append sources read after graph discovery; requires title,url,note. Stable source:N IDs are returned. Source content is not independently authenticated by this tool."""
        return result(add_sources,run_id,sources)

    @server.tool(annotations=read)
    def citespace_read_research_artifact(run_id: str, filename: str, offset: int=0, limit: int=12000) -> str:
        """Read bounded UTF-8 native project text/JSON/CSV/in/out artifacts with hash. Useful for verifying burst outputs against their input index, not treating signature defaults as actual Q/silhouette."""
        return result(read_artifact,run_id,filename,offset,limit)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False,destructiveHint=False,openWorldHint=True))
    def citespace_search_literature(query: str='', limit: int=8, doi: str='') -> str:
        """Search public Crossref API or resolve exact DOI without browser; save bibliographic receipt. Metadata/abstract discovery only, not exhaustive corpus or a claim of full-text reading."""
        return result(search_literature,query,limit,doi)

    @server.tool(annotations=write)
    def citespace_write_research_report(run_id: str, sections: list[dict[str,Any]]) -> str:
        """Write versioned MD/standalone HTML/SVG with actual graph metrics and Codex interpretation. Each section needs heading,text,evidence_ids (graph:summary, node:ID, record:UT, source:N). Does not invent narrative; return to original papers first."""
        return result(render_report,run_id,sections)

    @server.tool(annotations=read)
    def citespace_research_state(run_id: str) -> str:
        """Read persistent run manifest for interruption recovery. submitted/export_requested must be polled, never blindly restarted."""
        return result(lambda: {'ok':True,'manifest':read_manifest(run_id)[1],'directory':str(run_path(run_id))})

    @server.tool(annotations=write)
    def citespace_capture_research_view(run_id: str, window_title: str, close_after: bool=False) -> str:
        """Capture an exact-title native result frame belonging to a verified run, optionally close that frame normally. Never closes main frame/dialogs. Returns PNG path; inspect image before interpretation."""
        return result(capture_view,run_id,window_title,close_after)

    @server.tool(annotations=write)
    def citespace_verify_native_counts(run_id: str, nodes: int, edges: int, evidence_filename: str) -> str:
        """After Codex visually reads this run's native-view PNG, compare native N/E to exported counts. Persist capture hash and explicit mismatch; does not claim edgewise equivalence."""
        return result(verify_native_counts,run_id,nodes,edges,evidence_filename)

    @server.tool(annotations=read)
    def citespace_graph_neighborhood(run_id: str, node_id: str, limit: int=20) -> str:
        """Read actual incident edges/weights and neighbor node attributes from verified GraphML. Use for relationship-level interpretation, not only frequency ranking. Bounded to100 edges; marks truncation."""
        return result(neighborhood,run_id,node_id,limit)

    @server.tool(annotations=write)
    def citespace_finish_research_view(run_id: str) -> str:
        """Capture and normally close a managed completed result view and its Control Panel, preserving files. Useful before next project. Never closes unknown/unfinished runs or main frame."""
        return result(finish_view,run_id)
