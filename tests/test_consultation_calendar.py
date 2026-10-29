"""Existing Google adapter with injected local HTTP session, no live API."""
import copy
import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import test_nvsu_google as google
from nvsu_google import GoogleCalendarAdapter
from consultation_calendar import ConsultationCalendarPort
from consultation_executor import MARKER,MutationReceipt,MutationRejected,ExecutorError
from consultation_actions import TZ

NOW=dt.datetime(2026,10,29,9,tzinfo=TZ)
class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.session=google.FakeSession()
        self.session.events['synthetic-hold']={'id':'synthetic-hold','etag':'"v1"','summary':'Synthetic pending','location':'Кабинет 317','description':'Synthetic note',
            'extendedProperties':{'private':{'existing':'preserved'},'shared':{'existing':'preserved'}},'reminders':{'useDefault':False},
            'start':{'dateTime':'2026-10-29T10:00:00+05:00'},'end':{'dateTime':'2026-10-29T10:20:00+05:00'}}
        self.port=ConsultationCalendarPort(GoogleCalendarAdapter('calendar-test',self.session),clock=lambda:NOW)
    def request(self,method='update'):
        return {'calendar_id':'calendar-test','event_id':'synthetic-hold','method':method,'etag':'"v1"','operation_id':'a'*64,'start':'2026-10-29T05:00:00+00:00','end':'2026-10-29T05:20:00+00:00',
            'title':'Консультация — подтверждена','location':'Кабинет 317','extensions':{'private':{'existing':'preserved',MARKER:'a'*64},'shared':{'existing':'preserved'}}}
    def test_default_disabled_does_not_read_or_write(self):
        with self.assertRaises(ExecutorError):self.port.apply(self.request())
        self.assertEqual(self.session.calls,[])
    def test_read_reuses_existing_transport_and_preserves_event_notes(self):
        record=self.port.read('synthetic-hold')
        self.assertEqual(record.description,'Synthetic note');self.assertEqual(record.extensions['private']['existing'],'preserved')
        self.assertFalse(record.protected);self.assertTrue(all(call[0]=='GET' for call in self.session.calls))
    def test_patch_same_event_with_if_match_no_time_change_or_google_notifications(self):
        before=copy.deepcopy(self.session.events['synthetic-hold']);self.port.adapter.allow_writes=True
        result=self.port.apply(self.request())
        self.assertEqual(result,MutationReceipt('calendar-test','synthetic-hold','update','a'*64))
        method,url,args=self.session.calls[-1];self.assertEqual(method,'PATCH');self.assertEqual(args['headers']['If-Match'],'"v1"');self.assertEqual(args['params']['sendUpdates'],'none')
        self.assertEqual(set(args['json']),{'summary','location','extendedProperties'})
        after=self.session.events['synthetic-hold']
        for key in ('description','start','end','reminders'):self.assertEqual(after[key],before[key])
        self.assertEqual(after['extendedProperties']['shared'],before['extendedProperties']['shared'])
    def test_delete_exact_event_if_match_without_insert(self):
        self.port.adapter.allow_writes=True;result=self.port.apply(self.request('delete'))
        self.assertEqual(result.method,'delete');self.assertNotIn('synthetic-hold',self.session.events)
        method,url,args=self.session.calls[-1];self.assertEqual(method,'DELETE');self.assertEqual(args['headers']['If-Match'],'"v1"')
        self.assertNotIn('POST',[call[0] for call in self.session.calls])
    def test_412_is_definite_rejection_with_no_retry(self):
        self.port.adapter.allow_writes=True;self.session.fail_precondition=True
        with self.assertRaises(MutationRejected) as result:self.port.apply(self.request())
        self.assertEqual(result.exception.code,412);self.assertEqual(len(self.session.calls),1)
    def test_timeout_after_patch_is_uncertain_but_marker_survives(self):
        self.port.adapter.allow_writes=True;self.session.fail_patch=True
        with self.assertRaises(ExecutorError):self.port.apply(self.request())
        self.assertEqual(self.port.read('synthetic-hold').extensions['private'][MARKER],'a'*64)
        self.assertEqual(sum(call[0]=='PATCH' for call in self.session.calls),1)
    def test_wrong_calendar_method_or_headers_fail_before_http(self):
        self.port.adapter.allow_writes=True
        for changes in ({'calendar_id':'foreign'},{'method':'create'},{'etag':'x\r\nInjected: x'},{'operation_id':'invalid'}):
            request=self.request();request.update(changes)
            with self.assertRaises(ExecutorError):self.port.apply(request)
        self.assertEqual(self.session.calls,[])
    def test_all_day_and_recurring_events_are_protected(self):
        event=self.session.events['synthetic-hold'];event['recurringEventId']='synthetic-series'
        self.assertTrue(self.port.read('synthetic-hold').protected)
        event.pop('recurringEventId');event['start']={'date':'2026-10-29'};event['end']={'date':'2026-10-30'}
        self.assertTrue(self.port.read('synthetic-hold').protected)
    def test_missing_read_is_absence_not_an_empty_busy_snapshot(self):
        self.assertIsNone(self.port.read('missing'))

    def test_explicit_reviewed_description_patch_preserves_other_fields(self):
        self.port.adapter.allow_writes=True;request=self.request();request['description']='Synthetic approved prefix\nSynthetic manual note'
        self.assertEqual(self.port.apply(request).method,'update')
        self.assertEqual(self.session.events['synthetic-hold']['description'],request['description'])
        self.assertEqual(self.session.calls[-1][2]['json']['description'],request['description'])
