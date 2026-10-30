"""Offline NVSU → teaching coverage → slots handoff. Synthetic fixtures ONLY.

Default output is aggregate. --fixture-handoff emits fixed synthetic test data
for the local Apps Script acceptance harness, never live sources or credentials.
"""
import copy
from dataclasses import replace
import datetime as dt
import json
from pathlib import Path
import sys
from nvsu_source import fetch_week
from nvsu_sync import event_payload,plan_sync,apply_sync_plan
from consultation_feed import CalendarSnapshot,BusyFeed
from consultation_actions import TZ
from teaching_coverage import TeachingCoverageFeed,preview_consultation_slots,teaching_guard_payload

class FixtureCalendar:
    """In-memory test port for the EXISTING sync algorithm; never a live adapter."""
    def __init__(self):self.events={};self.keys={};self.created=0;self.updated=0;self.deleted=0
    def list_events(self,start,end):return [copy.deepcopy(e) for e in self.events.values() if e['start']<end and e['end']>start]
    def get_event(self,key):return copy.deepcopy(self.events.get(key))
    def create_event(self,key,payload):
        if key in self.keys:return self.keys[key]
        self.created+=1;event_id='synthetic-lesson-'+str(self.created);self.events[event_id]=dict(id=event_id,**copy.deepcopy(payload));self.keys[key]=event_id;return event_id
    def update_event(self,key,payload):self.updated+=1;self.events[key].update(copy.deepcopy(payload))
    def delete_event(self,key):self.deleted+=1;self.events.pop(key,None)

NOW=dt.datetime(2026,11,2,8,tzinfo=TZ)
def fixture_handoff():
    html=(Path(__file__).resolve().parents[1]/'tests/fixtures/nvsu/next.html').read_bytes()
    proof=fetch_week('2026-11-02','9999','Тестовый Преподаватель',fetch=lambda url:(200,'text/html',html),now=NOW)
    start=NOW.replace(hour=0);end=start+dt.timedelta(days=7)
    memory=FixtureCalendar();ledger=[]
    initial=plan_sync(proof['week'],[],ledger,requested_date='2026-11-02');apply_sync_plan(initial,memory,ledger)
    repeated=plan_sync(proof['week'],list(memory.events.values()),ledger,requested_date='2026-11-02');apply_sync_plan(repeated,memory,ledger)
    if memory.created!=11 or memory.updated or memory.deleted:raise ValueError('Synthetic idempotency failed')
    events=tuple(copy.deepcopy(list(memory.events.values())))
    calendar=CalendarSnapshot('synthetic-calendar',events,NOW,start,end,True)
    feed=TeachingCoverageFeed(teacher_id='synthetic-teacher',lecturer_id='9999',teacher_name='Тестовый Преподаватель',calendar_id=calendar.calendar_id,
        load_source=lambda date:copy.deepcopy(proof),load_calendar=lambda a,b:calendar,clock=lambda:NOW,load_bindings=lambda:tuple(ledger))
    coverage=feed.assess('2026-11-02')
    busy=BusyFeed(target_id=calendar.calendar_id,teaching_id=calendar.calendar_id,teacher_id='synthetic-teacher',load_target=lambda:calendar,
        load_teaching=lambda:calendar,load_verification=lambda:coverage.verification,load_bindings=lambda:(),clock=lambda:NOW)()
    slots=preview_consultation_slots(busy,'2026-11-02',now=NOW)
    return dict(mode='synthetic_fixture_handoff',now=NOW.isoformat(),requested_date='2026-11-02',events=list(events),
                mock_created=memory.created,mock_repeat_creates=sum(op['action']=='create' for op in repeated['operations']),proof=teaching_guard_payload(coverage,owner_chat_id='9001'),slots=[value.isoformat() for value in slots.starts],coverage=coverage.summary())

def main():
    handoff=fixture_handoff()
    if sys.argv[1:]==['--fixture-handoff']:
        print(json.dumps(handoff,ensure_ascii=False));return
    if sys.argv[1:]:raise ValueError('Unsupported demo option')
    print(json.dumps(dict(mode='offline_schedule_consultation_demo',lessons=handoff['coverage']['lessons'],matched=handoff['coverage']['matched'],
        mock_imported=handoff['mock_created'],mock_repeat_creates=handoff['mock_repeat_creates'],preview_slots=len(handoff['slots']),coverage_status=handoff['coverage']['status'],live_booking_enabled=False,real_calendar_writes=0,real_messages_sent=0),ensure_ascii=False,indent=2))
if __name__=='__main__':
    try:main()
    except Exception:print('Offline schedule demo failed; inspect synthetic tests only.',file=sys.stderr);raise SystemExit(1)
