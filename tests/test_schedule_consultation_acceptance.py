"""Existing NVSU algorithms + coverage + consultation preview, entirely offline."""
import copy
from dataclasses import replace
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nvsu_source import fetch_week
from nvsu_sync import plan_sync,apply_sync_plan
from consultation_actions import TZ
from consultation_feed import CalendarSnapshot,BusyFeed,FeedError
from teaching_coverage import TeachingCoverageFeed,preview_consultation_slots,teaching_guard_payload,CoverageError
from schedule_consultation_demo import FixtureCalendar,NOW,fixture_handoff

class ScheduleConsultationAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.proof=fetch_week('2026-11-02','9999','Тестовый Преподаватель',fetch=lambda url:(200,'text/html',(Path(__file__).parent/'fixtures/nvsu/next.html').read_bytes()),now=NOW)
        self.memory=FixtureCalendar();self.ledger=[];self.now=NOW
        self.start=NOW.replace(hour=0);self.end=self.start+dt.timedelta(days=7)
        self.feed=TeachingCoverageFeed(teacher_id='teacher',lecturer_id='9999',teacher_name='Тестовый Преподаватель',calendar_id='synthetic-calendar',load_source=lambda date:copy.deepcopy(self.proof),load_calendar=lambda a,b:self.snapshot(),load_bindings=lambda:tuple(copy.deepcopy(self.ledger)),clock=lambda:self.now)
    def snapshot(self):return CalendarSnapshot('synthetic-calendar',tuple(copy.deepcopy(list(self.memory.events.values()))),self.now,self.start,self.end,True)
    def plan(self):return plan_sync(self.proof['week'],list(self.memory.events.values()),self.ledger,requested_date='2026-11-02')
    def import_fixture(self):apply_sync_plan(self.plan(),self.memory,self.ledger)
    def busy(self):return BusyFeed(target_id='synthetic-calendar',teaching_id='synthetic-calendar',teacher_id='teacher',load_target=self.snapshot,load_teaching=self.snapshot,load_verification=lambda:self.feed.assess('2026-11-02').verification,load_bindings=lambda:(),clock=lambda:self.now)()
    def test_initial_import_then_repeat_proves_coverage_without_duplicate_creation(self):
        self.assertEqual(self.feed.assess('2026-11-02').status,'import_required');self.import_fixture();self.import_fixture()
        self.assertEqual(self.memory.created,11);self.assertEqual(self.memory.updated,0);self.assertEqual(self.memory.deleted,0);self.assertTrue(self.busy().teaching_complete)
        for event in self.memory.events.values():self.assertEqual(set(event),{'id','start','end','title','location'})
    def test_changed_class_blocks_readiness_until_same_event_is_updated(self):
        self.import_fixture();ids=set(self.memory.events);old=copy.deepcopy(self.proof['week']['lessons'][0]);self.proof['week']['lessons'][0].update(start='2026-11-02T09:00:00+05:00',end='2026-11-02T09:20:00+05:00')
        # Explicit synthetic next provider version; not a claim to have fetched new real HTML.
        self.proof['raw_sha256']=hashlib.sha256(json.dumps(self.proof['week'],sort_keys=True).encode()).hexdigest()
        self.assertFalse(self.busy().teaching_complete);self.import_fixture();self.assertEqual(set(self.memory.events),ids);self.assertEqual(self.memory.created,11);self.assertEqual(self.memory.updated,1)
        preview=preview_consultation_slots(self.busy(),'2026-11-02',now=self.now);self.assertNotIn('09:00',[v.strftime('%H:%M') for v in preview.starts])
    def test_manual_protected_exact_events_are_verified_without_ownership_or_writes(self):
        self.import_fixture();self.ledger=[]
        for event in self.memory.events.values():event['protected']=True
        before=copy.deepcopy(self.memory.events);r=self.feed.assess('2026-11-02');self.assertEqual(r.status,'verified');self.assertFalse(r.plan['ready']);self.assertEqual(self.memory.events,before);self.assertEqual(self.memory.updated,0)
    def test_changed_calendar_after_sync_preview_is_not_silently_overwritten(self):
        self.import_fixture();self.proof['week']['lessons'][0]['location']='Synthetic new room';plan=self.plan();first=next(iter(self.memory.events));self.memory.events[first]['title']='Manual edit'
        with self.assertRaises(ValueError):apply_sync_plan(plan,self.memory,self.ledger)
        self.assertEqual(self.memory.updated,0)
    def test_partial_import_does_not_produce_even_a_single_bookable_preview(self):
        plan=self.plan();apply_sync_plan(plan,self.memory,self.ledger,operation_hook=lambda index,operation:index==0)
        self.assertEqual(self.memory.created,1);r=self.feed.assess('2026-11-02');self.assertEqual(r.missing,10);self.assertIsNone(teaching_guard_payload(r,owner_chat_id='9001'))
        self.assertEqual(preview_consultation_slots(self.busy(),'2026-11-02',now=self.now).starts,())
    def test_source_failure_cannot_silently_fall_back_to_last_successful_week(self):
        self.import_fixture();self.feed.source=lambda date:(_ for _ in ()).throw(RuntimeError('PRIVATE SOURCE DETAIL'))
        with self.assertRaises(FeedError) as caught:self.busy()
        self.assertNotIn('PRIVATE',str(caught.exception))
    def test_internal_guard_serialization_is_bound_to_coverage_and_confirmed_owner_identity(self):
        self.assertIsNone(teaching_guard_payload(self.feed.assess('2026-11-02'),owner_chat_id='9001'));self.import_fixture();r=self.feed.assess('2026-11-02');p=teaching_guard_payload(r,owner_chat_id='9001');self.assertEqual(p['calendar_id'],'synthetic-calendar');self.assertEqual(p['source_revision'],r.verification.source_revision)
        for owner in ['not-an-id','0','9001\n',2**52]:
            with self.assertRaises(CoverageError):teaching_guard_payload(r,owner_chat_id=owner)
    def test_demo_handoff_never_enables_live_booking_or_apply(self):
        h=fixture_handoff();self.assertEqual(h['mode'],'synthetic_fixture_handoff');self.assertEqual(h['mock_repeat_creates'],0);self.assertFalse(h['coverage']['ready_for_calendar_apply']);self.assertFalse(h['coverage']['live_verified'])
