"""Trusted local snapshots only; synthetic Sheet/Calendar IDs."""
from dataclasses import replace
import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from consultation_feed import (HEADERS,SheetSnapshot,ConsultationFeed,FeedError,CalendarSnapshot,
    TeachingVerification,HoldBinding,BusyFeed,read_calendar_snapshot,calendar_revision)
from consultation_actions import TZ

NOW=dt.datetime(2026,10,29,9,tzinfo=TZ)
START=NOW+dt.timedelta(hours=1)
END=START+dt.timedelta(minutes=20)

class FeedTests(unittest.TestCase):
    def setUp(self):
        self.now=NOW
        self.row=('request-a',NOW,'Synthetic student','00123','2026-10-29','10:00',20,'Synthetic topic','Ожидает решения','','hold-a')
        self.sheet=SheetSnapshot('synthetic-sheet','Заявки на консультации',HEADERS,(self.row,),NOW,True,'Asia/Yekaterinburg')
        self.feed=ConsultationFeed(spreadsheet_id='synthetic-sheet',load_snapshot=lambda:self.sheet,clock=lambda:self.now)
        self.event={'id':'hold-a','start':START.isoformat(),'end':END.isoformat(),'title':'Synthetic','location':'317','etag':'v1'}
        self.target=CalendarSnapshot('synthetic-target',(self.event,),NOW,NOW.replace(hour=0),NOW.replace(hour=23),True)
        self.teaching=CalendarSnapshot('synthetic-teaching',(),NOW,self.target.covered_start,self.target.covered_end,True)
        self.verification=self.verify(self.teaching)
        self.bindings=(HoldBinding('synthetic-target','hold-a','request-a',START,END),)
        self.busy=BusyFeed(target_id='synthetic-target',teaching_id='synthetic-teaching',teacher_id='owner',
            load_target=lambda:self.target,load_teaching=lambda:self.teaching,load_verification=lambda:self.verification,
            load_bindings=lambda:self.bindings,clock=lambda:self.now)
    def verify(self,snapshot):return TeachingVerification('owner',snapshot.calendar_id,snapshot.covered_start,snapshot.covered_end,NOW,NOW,'synthetic-source-revision',calendar_revision(snapshot))
    def test_sheet_roundtrip_preserves_source_timestamp_and_chat_id(self):
        snapshot=self.feed.snapshot();item=snapshot.rows[0]
        self.assertEqual(item.chat_id,'00123');self.assertEqual(item.record.starts_at,START)
        self.assertEqual(self.feed.batch().observed_at,NOW);self.assertEqual(item.event_id,'hold-a')
        self.assertEqual(len(item.revision),64)
    def test_exact_headers_and_source_identity_required(self):
        for sheet in (replace(self.sheet,headers=HEADERS[::-1]),replace(self.sheet,spreadsheet_id='foreign'),replace(self.sheet,sheet_name='other'),replace(self.sheet,timezone='UTC')):
            self.sheet=sheet
            with self.assertRaises(FeedError):self.feed.batch()
    def test_aware_typed_dates_and_time_cells_match_strings(self):
        before=self.feed.snapshot().rows[0]
        row=list(self.row);row[4]=START;row[5]=START.astimezone(dt.timezone.utc)
        self.sheet=replace(self.sheet,rows=(tuple(row),))
        after=self.feed.snapshot().rows[0]
        self.assertEqual(before.record,after.record);self.assertEqual(before.revision,after.revision)
    def test_invalid_date_numeric_serial_or_naive_creation_rejected(self):
        for index,value in ((4,'2026-02-30'),(4,46324),(5,0.5),(5,'25:00'),(1,NOW.replace(tzinfo=None)),(6,True),(6,19),(3,1.5),(8,'Неизвестно')):
            row=list(self.row);row[index]=value;self.sheet=replace(self.sheet,rows=(tuple(row),))
            with self.assertRaises(FeedError):self.feed.batch()
    def test_partial_source_preserved_but_stale_never_restamped(self):
        self.sheet=replace(self.sheet,complete=False)
        self.assertFalse(self.feed.batch().complete)
        self.now=NOW+dt.timedelta(minutes=6)
        with self.assertRaises(FeedError):self.feed.batch()
    def test_duplicate_identical_rows_collapse_conflicting_rows_fail(self):
        self.sheet=replace(self.sheet,rows=(self.row,self.row));self.assertEqual(len(self.feed.batch().records),1)
        second=list(self.row);second[7]='Changed topic';self.sheet=replace(self.sheet,rows=(self.row,tuple(second)))
        with self.assertRaises(FeedError):self.feed.batch()
    def test_revision_changes_for_topic_status_recipient_and_event(self):
        old=self.feed.snapshot().rows[0].revision
        for index,value in ((7,'New topic'),(8,'Подтверждена'),(3,'00456'),(10,'hold-b')):
            row=list(self.row);row[index]=value;self.sheet=replace(self.sheet,rows=(tuple(row),))
            self.assertNotEqual(self.feed.snapshot().rows[0].revision,old)
    def test_incomplete_rows_not_silently_skipped(self):
        self.sheet=replace(self.sheet,rows=(self.row,('broken',)))
        with self.assertRaises(FeedError):self.feed.batch()
    def test_no_event_id_valid_for_in_progress_source_not_owned_booking(self):
        row=list(self.row);row[8]='Создаётся предварительная запись';row[10]='';self.sheet=replace(self.sheet,rows=(tuple(row),))
        self.assertEqual(self.feed.snapshot().rows[0].event_id,None)
    def test_busy_snapshot_uses_original_age_and_exact_hold_binding(self):
        result=self.busy();self.assertTrue(result.teaching_complete);self.assertEqual(result.events[0].consultation_id,'request-a')
        self.assertEqual(result.observed_at,NOW)
    def test_title_or_description_never_proves_ownership(self):
        self.bindings=();self.event['description']='[assistant:CONSULT:request-a]'
        self.assertIsNone(self.busy().events[0].consultation_id)
    def test_changed_owned_event_is_not_adopted(self):
        self.event['start']=(START+dt.timedelta(minutes=1)).isoformat()
        with self.assertRaises(FeedError):self.busy()
    def test_empty_calendar_without_verified_teaching_is_not_complete(self):
        self.verification=None
        result=self.busy();self.assertFalse(result.teaching_complete)
    def test_verification_must_match_teacher_calendar_range_and_revision(self):
        original=self.verification
        for evidence in (replace(original,teacher_id='other'),replace(original,calendar_id='foreign'),replace(original,covered_end=START),replace(original,calendar_revision='0'*64),replace(original,source_observed_at=NOW-dt.timedelta(hours=1))):
            self.verification=evidence
            self.assertFalse(self.busy().teaching_complete)
    def test_same_event_id_in_different_calendars_is_still_busy(self):
        foreign=dict(self.event);self.teaching=replace(self.teaching,events=(foreign,));self.verification=self.verify(self.teaching)
        events=self.busy().events
        self.assertEqual(len(events),2);self.assertEqual(len({e.id for e in events}),2)
        self.assertEqual(sum(e.consultation_id is not None for e in events),1)
    def test_same_calendar_read_once_and_deduplicated(self):
        calls=[];self.busy.teaching_id='synthetic-target';self.busy.load_teaching=lambda:calls.append(1)
        self.verification=self.verify(self.target)
        self.assertEqual(len(self.busy().events),1);self.assertEqual(calls,[])
    def test_incomplete_calendar_snapshot_fails_not_empty(self):
        self.target=replace(self.target,complete=False)
        with self.assertRaises(FeedError):self.busy()
    def test_slow_snapshot_load_ages_out_before_return(self):
        def slow():self.now=NOW+dt.timedelta(minutes=6);return self.teaching
        self.busy.load_teaching=slow
        with self.assertRaises(FeedError):self.busy()
    def test_unrelated_binding_is_not_allowed_to_relabel_event(self):
        self.bindings=(replace(self.bindings[0],calendar_id='foreign'),)
        with self.assertRaises(FeedError):self.busy()
    def test_existing_calendar_adapter_read_only_call(self):
        calls=[]
        class Adapter:
            calendar_id='synthetic-target'
            def list_events(this,start,end):calls.append((start,end));return [dict(self.event)]
        snapshot=read_calendar_snapshot(Adapter(),self.target.covered_start,self.target.covered_end,clock=lambda:NOW)
        self.assertEqual(snapshot.calendar_id,'synthetic-target');self.assertEqual(len(calls),1)
    def test_reader_failure_sanitized_and_no_partial_result(self):
        class Adapter:
            calendar_id='synthetic-target'
            def list_events(this,*args):raise RuntimeError('secret URL')
        with self.assertRaises(FeedError) as error:read_calendar_snapshot(Adapter(),self.target.covered_start,self.target.covered_end,clock=lambda:NOW)
        self.assertNotIn('secret',str(error.exception))
    def test_queue_reference_changes_when_recipient_or_event_changes(self):
        from decision_sources import ConsultationSource
        source=ConsultationSource('owner',self.feed.batch)
        old=source(None,None,NOW).items[0].reference
        for index,value in ((3,'00456'),(10,'hold-b')):
            row=list(self.row);row[index]=value;self.sheet=replace(self.sheet,rows=(tuple(row),))
            self.assertNotEqual(source(None,None,NOW).items[0].reference,old)
    def test_final_clock_check_does_not_return_expired_busy_snapshot(self):
        calls=[]
        def clock():
            calls.append(1)
            return NOW if len(calls)<3 else NOW+dt.timedelta(minutes=6)
        self.busy.clock=clock
        with self.assertRaises(FeedError):self.busy()
    def test_source_revision_guard_rejects_changed_row_and_partial_source(self):
        revision=self.feed.snapshot().rows[0].revision
        self.assertEqual(self.feed.require_revision('request-a',revision).revision,revision)
        row=list(self.row);row[7]='New topic';self.sheet=replace(self.sheet,rows=(tuple(row),))
        with self.assertRaises(FeedError):self.feed.require_revision('request-a',revision)
        self.sheet=replace(self.sheet,rows=(self.row,),complete=False)
        with self.assertRaises(FeedError):self.feed.require_revision('request-a',revision)
    def test_schema_contract_matches_current_gas_candidate(self):
        import ast,re
        code=(Path(__file__).resolve().parents[1]/'src/telegram_assistant_v2_0_5_candidate.gs').read_text()
        headers=ast.literal_eval(re.search(r'consultationHeaders: (\[[^\n]+\])',code).group(1))
        self.assertEqual(tuple(headers),HEADERS)
    def test_verification_cannot_predate_source_it_claims_to_verify(self):
        self.verification=replace(self.verification,source_observed_at=NOW+dt.timedelta(seconds=1))
        self.now=NOW+dt.timedelta(seconds=2)
        self.assertFalse(self.busy().teaching_complete)
    def test_export_json_decode_preserves_contract_and_rejects_duplicates(self):
        import json
        from consultation_feed import decode_sheet_export
        data={'format_version':1,'spreadsheet_id':'synthetic-sheet','sheet_name':self.sheet.sheet_name,'headers':list(HEADERS),'rows':[list(self.row)],'observed_at':NOW.isoformat(),'complete':True,'timezone':'Asia/Yekaterinburg'}
        data['rows'][0][1]=NOW.isoformat()
        payload=json.dumps(data)
        result=decode_sheet_export(payload)
        self.assertEqual(result.rows[0][1],NOW.isoformat())
        self.sheet=result
        self.assertEqual(self.feed.snapshot().rows[0].record.starts_at,START)
        for invalid in (payload[:-1]+',"complete":false}',payload.replace('"format_version": 1','"format_version": true'),payload+'x','x'*3000000):
            with self.assertRaises(FeedError):decode_sheet_export(invalid)
    def test_existing_google_adapter_pagination_all_day_and_recurring_busy(self):
        from nvsu_google import GoogleCalendarAdapter
        import test_nvsu_google as google
        session=google.FakeSession()
        all_day={'id':'holiday','start':{'date':'2026-10-29'},'end':{'date':'2026-10-30'}}
        recurring={'id':'lecture-instance','recurringEventId':'series','start':{'dateTime':START.isoformat()},'end':{'dateTime':END.isoformat()}}
        session.pages=[{'items':[all_day],'nextPageToken':'second'},{'items':[recurring]}]
        adapter=GoogleCalendarAdapter('calendar-test',session)
        snapshot=read_calendar_snapshot(adapter,self.target.covered_start,self.target.covered_end,clock=lambda:NOW)
        self.assertEqual(len(snapshot.events),2);self.assertTrue(all(event['protected'] for event in snapshot.events))
        self.assertTrue(all(call[0]=='GET' for call in session.calls));self.assertEqual(len(session.calls),3)
    def test_existing_adapter_page_failure_never_becomes_empty_free_calendar(self):
        from nvsu_google import GoogleCalendarAdapter
        import test_nvsu_google as google
        session=google.FakeSession();session.pages=[{'items':[dict(id='first',start={'dateTime':START.isoformat()},end={'dateTime':END.isoformat()})],'nextPageToken':'second'},{'items':'broken'}]
        with self.assertRaises(FeedError):read_calendar_snapshot(GoogleCalendarAdapter('calendar-test',session),self.target.covered_start,self.target.covered_end,clock=lambda:NOW)
