"""Readable index of actual recorded reviews; does not run or pass any test."""
from collections import Counter
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import subprocess

base = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence-root', type=Path, default=base / 'outputs/interactive-acceptance')
p.add_argument('--repository', type=Path, default=base / 'work/research-guard')
a = p.parse_args()
out = a.evidence_root.resolve()
queue = json.loads((out / '逐功能队列.json').read_text(encoding='utf8'))
events = [json.loads(line) for line in (out / 'interaction-index.jsonl').read_text(encoding='utf8').splitlines()]
bugs = json.loads((out / 'bugs.json').read_text(encoding='utf8'))
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=a.repository.resolve(), text=True).strip()
reviewed = {e['step_id'] for e in events if e['kind'] == 'parent_check'}
pending = [e['step_id'] for e in events if e['kind'] == 'question' and e['step_id'] not in reviewed]
lines = ['# Research Guard 实际交互验收进度', '',
         f'更新时间：{datetime.now(timezone.utc).isoformat()}。当前源码：`{head}`。', '',
         '主会话每次发出一条自然语言请求；实际执行 agent 返回后，由主会话读取真实回执和产物、写反馈，再进入下一问。表中“有复核记录”不等于功能全部成功，具体状态及事实边界保留在原记录。', '',
         f'- [完整逐句交互记录](<{(out / "完整交互记录.md").as_posix()}>)',
         f'- [真实主端工具与反馈轨迹](<{(out / "transcript/actual-calls-and-feedback.jsonl").as_posix()}>)',
         f'- [逐功能队列与各次结论](<{(out / "逐功能队列.json").as_posix()}>)', '',
         '| 组件 | 路由总数 | 已实际调用并复核 | 待测 | 已跳过 | 已记录状态分布 |',
         '| --- | ---: | ---: | ---: | ---: | --- |']
for component in ('core', 'literature', 'research', 'experiments', 'writing', 'figures', 'formal', 'citespace', 'skill-lab'):
    routes = [r for r in queue['routes'] if r['component'] == component]
    states = Counter(r['state'] for r in routes)
    tested = sum(bool(r.get('attempts')) for r in routes)
    skipped = sum(r['state'].startswith('SKIPPED') for r in routes)
    remain = sum(not r.get('attempts') and not r['state'].startswith('SKIPPED') for r in routes)
    lines.append(f'| {component} | {len(routes)} | {tested} | {remain} | {skipped} | ' + ', '.join(f'{s}: {n}' for s, n in sorted(states.items())) + ' |')
lines += ['', f'当前等待主端复核：{", ".join(pending) or "无"}。', '',
          '两个实际输入为197行实验单元CSV和200行历史场景差值CSV；另有作者全文PDF及派生文本。历史差值不等同绝对episode表现，覆盖审计不构成新训练或独立TEST。', '',
          '查新的78个实际网络单元均已尝试，48成功、30失败；18个必需单元仍受访问或缺少适配器阻断。报告准确记录COVERAGE_INCOMPLETE，未放行新颖性。此项不能列为完整查新成功。', '',
          '学科初始化另有OpenAlex、Crossref、DOAJ三个真实来源成功，20个发现候选；它与上述查新覆盖是不同任务，不能相互替代。', '',
          '当前已确认缺陷及闭环：', '', '| 编号 | 状态 | 修复提交 | 原输入复测 |', '| --- | --- | --- | --- |']
for bug in bugs:
    commit = bug.get('fix_commit') or bug.get('published_commit')
    commit_link = f'[{commit[:12]}](https://github.com/dltsum/research-guard/commit/{commit})' if commit else '未登记提交'
    lines.append(f'| {bug["id"]} | {bug["state"]} | {commit_link} | {bug.get("retest_step", "")} |')
lines += ['', '原失败、主端纠正、修复推送与重新安装记录均保留。待测和外部工具跳过分列；实际调用含正向结果与正确拒绝，须读取逐条反馈，不能据此推断所有候选通过或科学结论成立。', '']
(out / '验收总览.md').write_text('\n'.join(lines), encoding='utf8')
print(json.dumps({'pending_routes': sum(r['state'] == 'PENDING' for r in queue['routes']),
                  'reviewed_steps': len(reviewed), 'pending_questions': pending}, ensure_ascii=False))
