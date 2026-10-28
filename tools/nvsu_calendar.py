"""Read-only Google Calendar synchronization preparation CLI.

No apply command is exposed. Actual writes, bot deployment and triggers are not
part of preparation. Live Calendar access requires an explicit --live-read flag.
"""
import argparse,collections,datetime as dt,json,os,sys,tempfile
from pathlib import Path
from nvsu_source import fetch_week
from nvsu_preview import parse_week
from nvsu_google import GoogleCalendarAdapter,CalendarError
from nvsu_state import StateStore,prepare_envelope
from nvsu_sync import ZONE

def save_artifact(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.parent.is_symlink() or path.parent.stat().st_mode&0o077:raise ValueError('Plan directory must be private (0700)')
    if path.exists():raise ValueError('Refusing to overwrite an existing plan file')
    fd,temp=tempfile.mkstemp(prefix='.nvsu-plan-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as output:
            json.dump(value,output,ensure_ascii=False,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
        os.link(temp,path) # Atomic publication without overwriting any user file.
    finally:os.unlink(temp)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date',required=True,help='Concrete requested date, YYYY-MM-DD')
    parser.add_argument('--lecturer-id',required=True)
    parser.add_argument('--teacher-name',required=True)
    parser.add_argument('--calendar-id',default=os.environ.get('ASSISTANT_CALENDAR_ID'))
    parser.add_argument('--state-db',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--fetch-source',action='store_true',help='Fetch and validate the public source now')
    source.add_argument('--html',type=Path,help='Offline/fixture HTML; creates a non-applicable plan')
    target=parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--live-read',action='store_true',help='Explicitly read the selected Calendar through ADC; GET only')
    target.add_argument('--calendar-snapshot',type=Path,help='Explicit local event snapshot; never treated as live evidence')
    args=parser.parse_args(argv)
    if not args.calendar_id:parser.error('Set an explicit --calendar-id or ASSISTANT_CALENDAR_ID; no default Calendar is used')
    if args.output.exists():parser.error('Output already exists; choose a new plan path')
    now=dt.datetime.now(dt.timezone.utc)
    proof=fetch_week(args.date,args.lecturer_id,args.teacher_name,now=now) if args.fetch_source else dict(mode='fixture',fetched_at=now.isoformat(),week=parse_week(args.html.read_text(),args.lecturer_id,args.teacher_name,requested_date=args.date))
    start=dt.date.fromisoformat(proof['week']['week_start']);end=dt.date.fromisoformat(proof['week']['week_end'])+dt.timedelta(days=1)
    lower=dt.datetime.combine(start,dt.time(),ZONE).isoformat();upper=dt.datetime.combine(end,dt.time(),ZONE).isoformat()
    if args.live_read:
        client=GoogleCalendarAdapter.from_adc(args.calendar_id) # Explicit read-only scopes and adapter.
        events=client.list_events(lower,upper)
    else:
        events=json.loads(args.calendar_snapshot.read_text())
        if not isinstance(events,list):raise ValueError('Calendar snapshot must be an explicit list')
    with StateStore(args.state_db,args.calendar_id) as store:
        envelope=prepare_envelope(proof,events,store,requested_date=args.date,now=now,target_mode='live' if args.live_read else 'snapshot')
        save_artifact(args.output,envelope)
    counts=dict(collections.Counter(op['action'] for op in envelope['plan']['operations']))
    print(json.dumps(dict(plan_id=envelope['plan_id'],week_start=proof['week']['week_start'],week_end=proof['week']['week_end'],lessons=len(proof['week']['lessons']),operations=counts,review_required=not envelope['plan']['ready'],source_mode=proof['mode'],target_mode=envelope['target_mode'],writes_performed=False),ensure_ascii=False))
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,CalendarError,OSError) as error:
        # No traceback containing OAuth internals or user-data paths.
        print('Preparation failed: '+(str(error) if isinstance(error,(ValueError,CalendarError)) else 'local file/state access failed'),file=sys.stderr);raise SystemExit(1)
    except Exception:
        print('Preparation failed: authentication or transport setup requires review',file=sys.stderr);raise SystemExit(1)
