"""Compile a private, exact, approved create-only Apps Script handoff.

Uses existing nvsu_sync.plan_sync; does not implement a second timetable parser,
load credentials, contact Google or grant calendar-write authorization.
"""
import datetime as dt,hashlib,json,re
from pathlib import Path
from nvsu_sync import plan_sync,event_payload
from nvsu_private_snapshot import compare_snapshot
from nvsu_state import MAX_AGE,moment

STARTS=['2026-11-09','2026-11-16']
def build_import(proofs,approved_rows,snapshot,*,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    if not isinstance(proofs,list) or len(proofs)!=2 or [p.get('week',{}).get('week_start') for p in proofs]!=STARTS:raise ValueError('Exactly two approved source weeks required')
    if not isinstance(approved_rows,list) or len(approved_rows)!=18:raise ValueError('Original 18 approved payloads required')
    approved={json.dumps(event_payload(x),sort_keys=True) for x in approved_rows}
    if len(approved)!=18:raise ValueError('Duplicate approval payload')
    if snapshot.get('purpose')!='nvsu_read_only_november_comparison' or len(snapshot.get('snapshots',[]))!=4:raise ValueError('Original complete Calendar batch required')
    if [s.get('week_start') for s in snapshot['snapshots']]!=['2026-11-02','2026-11-09','2026-11-16','2026-11-23']:raise ValueError('Original four-week scope required')
    hashes={s.get('calendar_hash') for s in snapshot['snapshots']}
    if len(hashes)!=1 or not re.fullmatch(r'[0-9a-f]{64}',next(iter(hashes)) or ''):raise ValueError('One approved target required')
    sources=[];operations=[]
    for proof in proofs:
        week=proof['week'];d=week['week_start'];date=dt.date.fromisoformat(d)
        url='https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/3648//0/?date='+date.strftime('%d_%m_%Y')
        if proof.get('mode')!='live' or proof.get('lecturer_id')!='3648' or proof.get('url')!=url or not re.fullmatch(r'[0-9a-f]{64}',proof.get('raw_sha256','')):raise ValueError('Verified live NVSU proof required')
        age=now-moment(proof['fetched_at'])
        if age<dt.timedelta(seconds=-60) or age>MAX_AGE:raise ValueError('Fresh source required')
        selected=[s for s in snapshot['snapshots'] if s.get('week_start')==d]
        if len(selected)!=1 or selected[0].get('events')!=[]:raise ValueError('Approved Calendar weeks must have been empty')
        compare_snapshot(week,selected[0],requested_date=d)
        plan=plan_sync(week,[],[],requested_date=d)
        if not plan['ready'] or len(plan['operations'])!=9 or any(o['action']!='create' for o in plan['operations']):raise ValueError('Only 9+9 create operations allowed')
        sources.append(dict(week_start=d,week_end=week['week_end'],url=url,raw_sha256=proof['raw_sha256']))
        for op in plan['operations']:operations.append(dict(week_start=d,operation_key=op['operation_key'],source_refs=op['source_refs'],event=op['event']))
    if {json.dumps(x['event'],sort_keys=True) for x in operations}!=approved:raise ValueError('Source differs from the original approved 18 lessons; review required')
    return dict(format_version=1,purpose='approved_18_lesson_import',approved_at=now.isoformat(),expires_at=(now+dt.timedelta(hours=24)).isoformat(),calendar_hash=next(iter(hashes)),sources=sources,operations=operations)

def render_import(plan):
    raw=json.dumps(plan,ensure_ascii=False,separators=(',',':'));digest=hashlib.sha256(raw.encode()).hexdigest()
    core=(Path(__file__).resolve().parents[1]/'src/tools/nvsu_approved_import.gs').read_text()
    # No global CFG or reusable public endpoint; one manually selected entrypoint.
    wrapper='\nfunction importApprovedKulaginaNvsuLessons() {\n  return kulaginaNvsuApprovedImport_('+json.dumps(raw,ensure_ascii=False)+','+json.dumps(digest)+');\n}\n'
    return core+wrapper
