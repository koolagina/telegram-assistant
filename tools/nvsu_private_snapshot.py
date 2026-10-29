"""Read-only comparison of a redacted manual Calendar snapshot with NVSU.

Hashes reduce incidental disclosure; they are NOT encryption or authentication.
No Google credentials, writes, bindings, state mutation, or applicable plans.
"""
import collections,datetime as dt,hashlib,json,re
from nvsu_sync import plan_sync,instant

HEX=re.compile(r'[0-9a-f]{64}\Z')
def fingerprint(value):return hashlib.sha256(value.strip().encode('utf-8')).hexdigest()
def _hash(value):return isinstance(value,str) and HEX.fullmatch(value) is not None

def decode_chunks(text):
    if not isinstance(text,str) or len(text)>300000:raise ValueError('Snapshot size limit')
    parts={};total=None;digest=None
    for line in text.splitlines():
        # Accept Apps Script log prefixes, but never silently accept a partial set.
        pos=line.find('{')
        if pos<0:continue
        try:chunk=json.loads(line[pos:])
        except (ValueError,TypeError):raise ValueError('Invalid snapshot chunk') from None
        if not isinstance(chunk,dict) or set(chunk)!=set(('kind','index','total','sha256','data')):raise ValueError('Invalid chunk fields')
        i,n=chunk['index'],chunk['total']
        if chunk['kind']!='kulagina_calendar_chunk' or type(n) is not int or not 1<=n<=80 or type(i) is not int or not 0<=i<n or not _hash(chunk['sha256']) or not isinstance(chunk['data'],str) or len(chunk['data'])>3000:raise ValueError('Invalid chunk metadata')
        if total is not None and (n!=total or chunk['sha256']!=digest):raise ValueError('Mixed snapshot chunks')
        if i in parts:raise ValueError('Duplicate snapshot chunk')
        total,digest=n,chunk['sha256'];parts[i]=chunk['data']
    if total is None or set(parts)!=set(range(total)):raise ValueError('Incomplete snapshot chunks')
    data=''.join(parts[i] for i in range(total))
    if hashlib.sha256(data.encode()).hexdigest()!=digest:raise ValueError('Snapshot checksum mismatch')
    try:return json.loads(data)
    except ValueError:raise ValueError('Invalid snapshot JSON') from None

def compare_snapshot(week,snapshot,*,requested_date):
    required={'format_version','purpose','complete','timezone','week_start','week_end','observed_at','calendar_hash','events'}
    if not isinstance(snapshot,dict) or set(snapshot)!=required:raise ValueError('Invalid snapshot fields')
    if type(snapshot['format_version']) is not int or snapshot['format_version']!=1 or snapshot['purpose']!='nvsu_read_only_comparison' or snapshot['complete'] is not True or snapshot['timezone']!='Asia/Yekaterinburg':raise ValueError('Incomplete/unrecognized snapshot')
    if snapshot['week_start']!=week['week_start'] or snapshot['week_end']!=week['week_end'] or not _hash(snapshot['calendar_hash']):raise ValueError('Snapshot scope mismatch')
    instant(snapshot['observed_at'])
    events=snapshot['events']
    if not isinstance(events,list) or len(events)>200:raise ValueError('Invalid event count')
    titles={fingerprint(x['title']):x['title'].strip() for x in week['lessons']}
    rooms={fingerprint(x['location']):x['location'].strip() for x in week['lessons']}
    existing=[];seen=set();unknown=0
    lower=instant(week['week_start']+'T00:00:00+05:00')
    upper=lower+dt.timedelta(days=7)
    for e in events:
        if not isinstance(e,dict) or set(e)!={'id_hash','start','end','title_hash','location_hash','protected'} or any(not _hash(e[k]) for k in ('id_hash','title_hash','location_hash')) or type(e['protected']) is not bool:raise ValueError('Invalid redacted event')
        if e['id_hash'] in seen:raise ValueError('Duplicate snapshot event')
        seen.add(e['id_hash']);start,end=instant(e['start']),instant(e['end'])
        if end<=start or start>=upper or end<=lower:raise ValueError('Event outside selected interval')
        title,room=titles.get(e['title_hash']),rooms.get(e['location_hash'])
        unidentified=title is None or room is None
        unknown+=int(unidentified)
        existing.append(dict(id='snapshot-'+e['id_hash'],start=e['start'],end=e['end'],title=title or '',location=room or '',protected=e['protected'] or unidentified))
    # No ownership inferred from matching text/hashes. Existing planner supplies
    # deduplication/conflict classification only; no ledger or write adapter used.
    plan=plan_sync(week,existing,[],requested_date=requested_date)
    return dict(purpose='nvsu_read_only_comparison',target_mode='redacted_snapshot',
        week_start=week['week_start'],week_end=week['week_end'],observed_at=snapshot['observed_at'],
        lessons=len(week['lessons']),calendar_events=len(existing),unknown_events=unknown,
        operations=dict(collections.Counter(o['action'] for o in plan['operations'])),
        review_required=True,ownership_history_verified=False,ready_for_apply=False,
        teaching_schedule_verified=False,writes_performed=False)

def main(argv=None):
    import argparse,sys
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Compare a private manual snapshot; never apply or authenticate')
    parser.add_argument('--source-proof',required=True,type=Path,help='Private trusted fetch_week JSON artifact')
    parser.add_argument('--snapshot-log',required=True,type=Path,help='Private complete Apps Script chunk log')
    parser.add_argument('--date',required=True)
    args=parser.parse_args(argv)
    try:
        if args.source_proof.stat().st_size>2*1024*1024 or args.snapshot_log.stat().st_size>300000:raise ValueError('Input limit')
        proof=json.loads(args.source_proof.read_text())
        result=compare_snapshot(proof['week'],decode_chunks(args.snapshot_log.read_text()),requested_date=args.date)
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        print('Comparison unavailable: incomplete or invalid local evidence',file=sys.stderr)
        return 1
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0
if __name__=='__main__':raise SystemExit(main())
