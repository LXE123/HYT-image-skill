#!/usr/bin/env python3
"""Thursday–Wednesday work periods for Thursday 10:00 meetings; safe archive writes."""
import argparse
from contextlib import contextmanager
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

CONFIG = '.report-config.json'
SKILL = Path(__file__).resolve().parents[1]

def iso(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日期需为 YYYY-MM-DD')
    return date.fromisoformat(value)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def daily_path(root, week, day, session):
    """Keep existing daily files in place when the cutoff changes; never choose conflicting copies."""
    target=week/'daily-reports'/day/(session+'.md')
    existing=sorted(p for p in root.glob(f'week*/daily-reports/{day}/{session}.md')
                    if re.fullmatch(r'week\d+',p.parents[2].name) and p.is_file())
    if len({sha(p) for p in existing})>1:
        raise ValueError('同日同一时段存在不同内容，需先合并，不能重复计入或猜测：'+', '.join(map(str,existing)))
    return target if target in existing or not existing else existing[0]

def config(root):
    c = json.loads((root / CONFIG).read_text(encoding='utf-8'))
    anchor = iso(c.get('anchor_meeting',c.get('first_meeting','')))
    if c.get('version') not in [1,2] or c.get('timezone') != 'Asia/Shanghai' or anchor.weekday() != 3:
        raise ValueError('归档配置不合法，不能自动重置')
    if c.get('version')==2:
        if type(c.get('anchor_week_number')) is not int or c['anchor_week_number']<1:
            raise ValueError('锚点周次需为正整数')
        seen=set()
        for h in c.get('historical_reports',[]):
            if type(h['week_number']) is not int or not 1<=h['week_number']<c['anchor_week_number']:
                raise ValueError('历史周次必须早于锚点周次')
            if h['week_number'] in seen:
                raise ValueError('历史周次重复')
            seen.add(h['week_number'])
            if not iso(h['period_start'])<=iso(h.get('period_end',h['meeting_date']))<=iso(h['meeting_date']):
                raise ValueError('历史报告日期范围不合法')
    return c

def paths(root, c, day, meeting=False):
    anchor=iso(c.get('anchor_meeting',c.get('first_meeting','')))
    anchor_number=c.get('anchor_week_number',1)
    historical=c.get('historical_reports',[])
    match=next((h for h in historical if h['meeting_date']==day.isoformat()),None) if meeting else None
    if not meeting and day<anchor-timedelta(days=7):
        match=next((h for h in sorted(historical,key=lambda x:x['week_number'],reverse=True)
                    if iso(h['period_start'])<=day<=iso(h.get('period_end',h['meeting_date']))),None)
    if match:
        end=iso(match['meeting_date'])
        start=iso(match['period_start'])
        period_end=iso(match.get('period_end',match['meeting_date']))
        number=match['week_number']
    elif c.get('version')==2 and day<anchor-timedelta(days=7):
        raise ValueError('该历史日期尚无已确认归属；不能按节假日前后的自然周补猜')
    else:
        end = day + timedelta(days=(3-day.weekday()) % 7)
        if not meeting and day.weekday()==3:
            end += timedelta(days=7)
        start = end - timedelta(days=7)
        period_end=end-timedelta(days=1)
        number = (end-anchor).days // 7 + anchor_number
    if number < 1:
        raise ValueError('日期早于 week1；旧归档保持原样，需明确历史迁移规则')
    week = root / f'week{number}'
    meeting = week / end.isoformat()
    daily = week / 'daily-reports' / day.isoformat()
    return {'week_number': number, 'week_name': week.name,
            'period_start': start.isoformat(), 'period_end':period_end.isoformat(),'meeting_date': end.isoformat(),
            'week_dir': str(week), 'daily_dir': str(daily), 'meeting_dir': str(meeting),
            'morning': str(daily_path(root,week,day.isoformat(),'上午')), 'afternoon': str(daily_path(root,week,day.isoformat(),'下午')),
            'report_md': str(meeting/'report.md'), 'report_html': str(meeting/'report.html')}

def prepare(p):
    (Path(p['week_dir'])/'daily-reports').mkdir(parents=True, exist_ok=True)
    for i in range((iso(p['period_end'])-iso(p['period_start'])).days+1):
        (Path(p['week_dir'])/'daily-reports'/(iso(p['period_start'])+timedelta(days=i)).isoformat()).mkdir(exist_ok=True)
    Path(p['meeting_dir']).mkdir(exist_ok=True)

@contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    lock = root/'.report-write.lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('另一项归档正在写入；稍后重试。若为中断遗留，先核实再清理锁')
    try:
        yield
    finally:
        lock.rmdir()

def write_bundle(files, replace=False, expected=None):
    expected = expected or {}
    changed, old = {}, {}
    for path, content in files.items():
        original = path.read_bytes() if path.exists() else None
        if original == content:
            continue
        if original is not None:
            if not replace:
                raise ValueError(f'文件已有不同内容，先合并后显式替换：{path}')
            if expected.get(path) != hashlib.sha256(original).hexdigest():
                raise ValueError(f'文件摘要缺失或已变化，重新读取再合并：{path}')
        changed[path], old[path] = content, original
    staged, applied = {}, []
    try:
        for path, content in changed.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.report-', delete=False) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
                staged[path] = Path(f.name)
        for path, temporary in staged.items():
            os.replace(temporary, path)
            applied.append(path)
    except Exception:
        for path in reversed(applied):
            if old[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(old[path])
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
    return [{'path':str(p),'sha256':sha(p),'changed':p in changed} for p in files]

def text(value):
    if not isinstance(value,str) or not value.strip():
        raise ValueError('报告文字字段需为非空字符串')
    return value.strip()

def validate(data):
    if not isinstance(data,dict):
        raise ValueError('报告数据需为 JSON 对象')
    result={'headline':text(data.get('headline'))}
    keys={'work':('title','summary'), 'goals':('title','status','note'),
          'next':('title','text'), 'summary':('title','text')}
    for section, fields in keys.items():
        rows=data.get(section)
        if not isinstance(rows,list) or (not rows and section!='goals'):
            raise ValueError(f'{section} 需为列表，除 goals 外不能为空')
        result[section]=[]
        for row in rows:
            if not isinstance(row,dict):
                raise ValueError(f'{section} 条目需为对象')
            entry={field:text(row.get(field)) for field in fields}
            if section=='work':
                items=row.get('items')
                if not isinstance(items,list) or not items:
                    raise ValueError('每条工作主线需有要点')
                entry['items']=[{'tag':text(x.get('tag')),'text':text(x.get('text'))} for x in items]
            result[section].append(entry)
    return result

def markdown(data,p):
    lines=[f"# 每周工作报告（{p['period_start']}—{p.get('period_end',p['meeting_date'])}）",'',
           f"**周次：** {p['week_name']}  ",f"**周会日期：** {p['meeting_date']}",'',
           '> '+data['headline'],'','## 一、本周工作','']
    for w in data['work']:
        lines += ['### '+w['title'],'',w['summary'],'']
        lines += ['- '+i['text'] for i in w['items']]
        lines += ['']
    if data['goals']:
        lines += ['## 二、上期目标','']
        lines += ['| 目标 | 状态 | 说明 |','| :--- | :--- | :--- |']
        for g in data['goals']:
            cells=[g[k].replace('|','\\|').replace('\n',' ') for k in ('title','status','note')]
            lines += ['| '+' | '.join(cells)+' |']
    lines += ['',('## 三、下阶段重点' if data['goals'] else '## 二、下阶段重点'),'']
    lines += [f"{i}. **{n['title']}：** {n['text']}" for i,n in enumerate(data['next'],1)]
    lines += ['',('## 四、总结' if data['goals'] else '## 三、总结'),'']
    for s in data['summary']:
        lines += [f"**{s['title']}：** {s['text']}",'']
    return '\n'.join(lines).rstrip()+'\n'

def html(data,p):
    payload={**data, 'period_start':p['period_start'],'period_end':p.get('period_end',p['meeting_date']), 'meeting_date':p['meeting_date'], 'week_name':p['week_name']}
    encoded=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(SKILL/'assets/report.html').read_text(encoding='utf-8')
    if template.count('__REPORT_DATA_JSON__') != 1:
        raise ValueError('HTML 模板缺少唯一数据插槽')
    return template.replace('__REPORT_DATA_JSON__',encoded)

def collect(root,c,day):
    p=paths(root,c,day,meeting=True)
    if day.isoformat()!=p['meeting_date']:
        raise ValueError('周会日期必须是周四')
    files,missing=[],[]
    for i in range((iso(p['period_end'])-iso(p['period_start'])).days+1):
        d=(iso(p['period_start'])+timedelta(days=i)).isoformat()
        for session in ['上午','下午']:
            file=daily_path(root,Path(p['week_dir']),d,session)
            item={'date':d,'session':session,'path':str(file)}
            if file.is_file():
                item['sha256']=sha(file)
                files.append(item)
            else:
                missing.append(item)
    candidates=list((root/f"week{p['week_number']-1}").glob('*/report.md'))
    previous=candidates[0] if len(candidates)==1 else None
    return {**p,'files':files,'unrecorded_slots':missing,
            'previous_report':str(previous) if previous and previous.is_file() else None,
            'note':'缺少记录不表示没有工作；不从周报反推或编造日报。'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.home()/'Desktop'/'weekMessage')
    subs=parser.add_subparsers(dest='command',required=True)
    init=subs.add_parser('init'); init.add_argument('--anchor-meeting','--first-meeting',dest='first_meeting',required=True,type=iso)
    init.add_argument('--anchor-week-number',type=int,default=1)
    for name in ['paths','collect','daily','weekly']:
        sub=subs.add_parser(name)
        sub.add_argument('--date',required=True,type=iso)
        if name=='paths':
            sub.add_argument('--meeting',action='store_true',help='按周会日期查询当期报告；周四默认 paths 查询日报的下一期归属')
        if name in ['daily','weekly']:
            sub.add_argument('--replace',action='store_true')
        if name=='daily':
            sub.add_argument('--session',required=True,choices=['上午','下午','am','pm'])
            sub.add_argument('--source',type=Path,required=True)
            sub.add_argument('--expected-sha')
        if name=='weekly':
            sub.add_argument('--data',type=Path,required=True)
            sub.add_argument('--expected-md-sha'); sub.add_argument('--expected-html-sha')
    args=parser.parse_args()
    root=args.root.expanduser().resolve()
    if args.command=='init':
        if args.first_meeting.weekday()!=3:
            raise ValueError('首个周会日期必须是周四')
        if args.anchor_week_number<1:
            raise ValueError('锚点周次需为正整数')
        c=({'version':1,'timezone':'Asia/Shanghai','first_meeting':args.first_meeting.isoformat()}
           if args.anchor_week_number==1 else
           {'version':2,'timezone':'Asia/Shanghai','anchor_meeting':args.first_meeting.isoformat(),
            'anchor_week_number':args.anchor_week_number,'historical_reports':[]})
        with locked(root):
            if (root/CONFIG).exists():
                if config(root)!=c:
                    raise ValueError('归档设置已有不同值，不能隐式改动周次')
            else:
                write_bundle({root/CONFIG:(json.dumps(c,ensure_ascii=False,indent=2)+'\n').encode()})
            p=paths(root,c,args.first_meeting,meeting=True);prepare(p)
        result={**p,'config':str(root/CONFIG)}
    else:
        c=config(root); p=paths(root,c,args.date,meeting=args.command in ['collect','weekly'] or getattr(args,'meeting',False))
        if args.command=='paths':
            result={**p,'sha256':{k:sha(Path(p[k])) for k in ['morning','afternoon','report_md','report_html']}}
        elif args.command=='collect':
            result=collect(root,c,args.date)
        elif args.command=='daily':
            content=args.source.read_text(encoding='utf-8').strip()
            if not content:
                raise ValueError('不能归档空日报')
            target=Path(p['morning' if args.session in ['上午','am'] else 'afternoon'])
            with locked(root):
                prepare(p)
                result=write_bundle({target:(content+'\n').encode()},args.replace,{target:args.expected_sha})
        else:
            if args.date.isoformat()!=p['meeting_date']:
                raise ValueError('周会日期必须是周四')
            data=validate(json.loads(args.data.read_text(encoding='utf-8')))
            md,ht=Path(p['report_md']),Path(p['report_html'])
            with locked(root):
                prepare(p)
                result=write_bundle({md:markdown(data,p).encode(),ht:html(data,p).encode()},args.replace,
                                    {md:args.expected_md_sha,ht:args.expected_html_sha})
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as error:
        print(f'归档失败：{error}',file=sys.stderr)
        sys.exit(1)
