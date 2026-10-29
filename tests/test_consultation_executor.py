"""Calendar stage only: real local SQLite, entirely synthetic source/port."""
import copy
from dataclasses import replace
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assistant_demo import synthetic_policy
from decision_demo import DEMO_NOW
from assistant_access import Context
from consultation_actions import Booking,BusyEvent,BusySnapshot,ConsultationActions
from consultation_feed import HEADERS,SheetSnapshot,ConsultationFeed,HoldBinding
from consultation_executor import (ConsultationExecutor,BoundPlan,CalendarRecord,MutationReceipt,MutationRejected,ExecutorError,event_revision)

class FakeCalendar:
    calendar_id='synthetic-calendar'
    writes_enabled=True
    def __init__(self,now,start):
        self.now=now;self.calls=[];self.reads=0;self.error=None;self.after_apply=None;self.before_apply=None
        self.event=CalendarRecord(self.calendar_id,'synthetic-hold','v1',start,start+dt.timedelta(minutes=20),'Synthetic pending','Кабинет 317','Synthetic note',{},False,now)
    def read(self,event_id):self.reads+=1;return copy.deepcopy(self.event)
    def apply(self,request):
        self.calls.append(copy.deepcopy(request))
        if self.before_apply:self.before_apply()
        if self.event is None or self.event.etag!=request['etag']:raise MutationRejected(412)
        if self.error:raise self.error
        if request['method']=='delete':self.event=None
        else:
            self.event=replace(self.event,etag='v2',title=request['title'],location=request['location'],extensions=copy.deepcopy(request['extensions']))
        if self.after_apply:self.after_apply()
        return MutationReceipt(self.calendar_id,request['event_id'],request['method'],request['operation_id'])

class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.now=DEMO_NOW+dt.timedelta(hours=1);self.start=self.now+dt.timedelta(hours=1);self.policy=synthetic_policy()
        self.ctx=Context('telegram','101',authenticated=True,private=True,sender='101')
        self.row=('synthetic-request',self.now,'Synthetic student','103',self.start.date().isoformat(),self.start.strftime('%H:%M'),20,'Synthetic topic','Ожидает решения','','synthetic-hold')
        self.sheet=SheetSnapshot('synthetic-sheet','Заявки на консультации',HEADERS,(self.row,),self.now,True,'Asia/Yekaterinburg')
        self.feed=ConsultationFeed(spreadsheet_id='synthetic-sheet',load_snapshot=lambda:self.sheet,clock=lambda:self.now)
        self.busy_events=(BusyEvent('synthetic-hold',self.start,self.start+dt.timedelta(minutes=20),'synthetic-request'),)
        self.binding=(HoldBinding('synthetic-calendar','synthetic-hold','synthetic-request',self.start,self.start+dt.timedelta(minutes=20)),)
        self.calendar=FakeCalendar(self.now,self.start)
        self.service=ConsultationActions(self.root/'actions.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=self.busy,student_eligible=lambda *args:True);self.addCleanup(self.service.close)
        self.service.add(Booking('synthetic-request','student-a',self.start,'synthetic-hold'))
        self.bound=self.make_bound('approve')
        self.executor=self.open();self.addCleanup(self.executor.close)
    def busy(self):return BusySnapshot(self.busy_events,self.sheet.observed_at,self.start.replace(hour=0),self.start.replace(hour=23),self.sheet.complete,self.sheet.complete)
    def make_bound(self,action):
        # Capture ORIGINAL source/event evidence alongside synthetic owner decision.
        source=self.feed.snapshot().rows[0];event=event_revision(self.calendar.event)
        intent=self.service.preview(self.ctx,'synthetic-request',action)
        plan=self.service.confirm(self.ctx,intent.token)
        return BoundPlan('synthetic-plan','owner','synthetic-calendar',plan,source.revision,event,self.now)
    def open(self):return ConsultationExecutor(self.root/'execution.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=lambda:self.policy,clock=lambda:self.now,load_plan=lambda plan_id:self.bound,source=self.feed,busy_snapshot=self.busy,hold_bindings=lambda:self.binding,calendar=self.calendar)
    def execute(self):return self.executor.execute(self.ctx,'synthetic-plan',execution_enabled=True)
    def rejection(self):
        # Separate synthetic fixture, not overwriting a confirmed real request.
        self.service.db.execute('DELETE FROM action_plans');self.service.db.execute('DELETE FROM action_intents')
        self.service.db.execute('DELETE FROM bookings');self.service.add(Booking('synthetic-request','student-a',self.start,'synthetic-hold'))
        self.bound=self.make_bound('reject')
    def test_default_disabled_reads_and_writes_nothing(self):
        with self.assertRaises(ExecutorError):self.executor.execute(self.ctx,'synthetic-plan')
        self.assertEqual(self.calendar.reads,0);self.assertEqual(self.calendar.calls,[])
    def test_approve_updates_same_event_without_changing_times_or_notes(self):
        before=copy.deepcopy(self.calendar.event);result=self.execute()
        self.assertEqual(result['status'],'calendar_api_confirmed');self.assertEqual(len(self.calendar.calls),1)
        self.assertEqual(self.calendar.event.id,before.id);self.assertEqual(self.calendar.event.starts_at,before.starts_at)
        self.assertEqual(self.calendar.event.description,before.description);self.assertEqual(result['source_status'],'not_written')
        self.assertEqual(result['notifications'],'not_sent');self.assertEqual(self.row[8],'Ожидает решения')
    def test_repeat_and_restart_do_not_repeat_mutation(self):
        first=self.execute();self.assertEqual(self.execute(),first)
        peer=self.open();self.addCleanup(peer.close)
        self.assertEqual(peer.execute(self.ctx,'synthetic-plan',execution_enabled=True),first);self.assertEqual(len(self.calendar.calls),1)
    def test_reject_deletes_only_bound_event(self):
        self.rejection();self.assertEqual(self.execute()['status'],'calendar_api_confirmed')
        self.assertIsNone(self.calendar.event);self.assertEqual(self.calendar.calls[0]['method'],'delete')
    def test_unknown_after_update_reconciles_marker_without_second_write(self):
        def lost():raise TimeoutError('mock accepted then lost')
        self.calendar.after_apply=lost
        self.assertEqual(self.execute()['status'],'unknown');self.assertEqual(self.execute()['status'],'unknown')
        result=self.executor.reconcile(self.ctx,'synthetic-plan')
        self.assertEqual(result['status'],'calendar_reconciled_present');self.assertEqual(len(self.calendar.calls),1)
    def test_unknown_delete_reconciles_absence_not_api_attribution(self):
        self.rejection()
        def lost():raise TimeoutError('mock deleted then lost')
        self.calendar.after_apply=lost;self.assertEqual(self.execute()['status'],'unknown')
        self.assertEqual(self.executor.reconcile(self.ctx,'synthetic-plan')['status'],'calendar_reconciled_absent')
        self.assertEqual(len(self.calendar.calls),1)
    def test_unknown_before_apply_never_resets_or_retries(self):
        self.calendar.error=TimeoutError('mock outcome unknown');self.execute();self.calendar.error=None
        self.assertEqual(self.executor.reconcile(self.ctx,'synthetic-plan')['status'],'unknown')
        self.execute();self.assertEqual(len(self.calendar.calls),1)
    def test_malformed_ack_is_unknown_and_can_be_reconciled(self):
        original=self.calendar.apply
        def malformed(request):original(request);return {'ok':True}
        self.calendar.apply=malformed;self.assertEqual(self.execute()['status'],'unknown')
        self.assertEqual(self.executor.reconcile(self.ctx,'synthetic-plan')['status'],'calendar_reconciled_present')
    def test_precondition_failure_does_not_overwrite_manual_edit(self):
        self.calendar.before_apply=lambda:setattr(self.calendar,'event',replace(self.calendar.event,etag='manual',description='Manual note'))
        self.assertEqual(self.execute()['status'],'calendar_rejected');self.assertEqual(self.calendar.event.description,'Manual note')
        self.execute();self.assertEqual(len(self.calendar.calls),1)
    def test_changed_source_event_or_student_binding_denied_before_claim(self):
        original=self.bound
        self.sheet=replace(self.sheet,rows=(self.row[:7]+('Changed topic',)+self.row[8:],))
        with self.assertRaises(ExecutorError):self.execute()
        self.sheet=replace(self.sheet,rows=(self.row,));self.calendar.event=replace(self.calendar.event,title='Manual title')
        with self.assertRaises(ExecutorError):self.execute()
        self.calendar.event=replace(self.calendar.event,title='Synthetic pending')
        self.policy=synthetic_policy(bindings=tuple(b for b in self.policy.bindings.values() if b.subject!='103'))
        with self.assertRaises(ExecutorError):self.execute()
        self.assertEqual(self.calendar.calls,[])
    def test_owner_student_revoke_and_expired_plan_denied(self):
        with self.assertRaises(ExecutorError):self.executor.execute(Context('telegram','103',authenticated=True,private=True),self.bound.id,execution_enabled=True)
        self.now+=dt.timedelta(minutes=5)
        with self.assertRaises(ExecutorError):self.execute()
        self.assertEqual(self.calendar.calls,[])
    def test_foreign_missing_or_changed_hold_denied(self):
        self.binding=()
        with self.assertRaises(ExecutorError):self.execute()
        self.binding=(HoldBinding('foreign','synthetic-hold','synthetic-request',self.start,self.start+dt.timedelta(minutes=20)),)
        with self.assertRaises(ExecutorError):self.execute()
        self.assertEqual(self.calendar.calls,[])
    def test_busy_conflict_or_incomplete_teaching_denied(self):
        self.busy_events+=(BusyEvent('lesson',self.start,self.start+dt.timedelta(hours=1)),)
        with self.assertRaises(ExecutorError):self.execute()
        self.busy_events=self.busy_events[:1];self.sheet=replace(self.sheet,complete=False)
        with self.assertRaises(ExecutorError):self.execute()
        self.assertEqual(self.calendar.calls,[])
    def test_change_after_claim_is_blocked_without_mutation(self):
        calls=[];original=self.executor.busy_snapshot
        def change():
            calls.append(1)
            if len(calls)==2:self.busy_events+=(BusyEvent('lesson',self.start,self.start+dt.timedelta(hours=1)),)
            return original()
        self.executor.busy_snapshot=change
        self.assertEqual(self.execute()['status'],'blocked_preflight');self.assertEqual(self.calendar.calls,[])
    def test_stop_leaves_durable_inflight_claim_then_readonly_reconciliation(self):
        def stopped():raise KeyboardInterrupt('mock stop after acceptance')
        self.calendar.after_apply=stopped
        with self.assertRaises(KeyboardInterrupt):self.execute()
        self.assertEqual(self.execute()['status'],'inflight_or_unknown');self.assertEqual(len(self.calendar.calls),1)
        self.assertEqual(self.executor.reconcile(self.ctx,self.bound.id)['status'],'calendar_reconciled_present')
    def test_peer_inflight_does_not_duplicate_or_mark_active_as_failed(self):
        nested=[];peer=self.open();self.addCleanup(peer.close)
        self.calendar.before_apply=lambda:nested.append(peer.execute(self.ctx,self.bound.id,execution_enabled=True))
        self.assertEqual(self.execute()['status'],'calendar_api_confirmed')
        self.assertEqual(nested[0]['status'],'inflight_or_unknown');self.assertEqual(len(self.calendar.calls),1)
    def test_receipt_write_failure_preserves_claim_and_uses_reconciliation(self):
        self.executor.db.execute("CREATE TRIGGER fail_finish BEFORE UPDATE ON calendar_attempts WHEN NEW.phase='calendar_api_confirmed' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        self.assertEqual(self.execute()['status'],'needs_recovery');self.assertEqual(len(self.calendar.calls),1)
        self.executor.db.execute('DROP TRIGGER fail_finish')
        self.assertEqual(self.execute()['status'],'inflight_or_unknown')
        self.assertEqual(self.executor.reconcile(self.ctx,self.bound.id)['status'],'calendar_reconciled_present')
    def test_unbound_old_plan_cannot_be_promoted_to_executable(self):
        self.bound=self.bound.plan
        with self.assertRaises(ExecutorError):self.execute()
        self.assertEqual(self.calendar.calls,[])
    def test_proposal_never_becomes_calendar_move(self):
        self.bound=replace(self.bound,plan=dict(self.bound.plan,action='propose',calendar=None))
        with self.assertRaises(ExecutorError):self.execute()
        self.assertEqual(self.calendar.calls,[])
    def test_wrong_operation_marker_or_manual_post_edit_not_reconciled(self):
        def lost():raise TimeoutError('mock accepted')
        self.calendar.after_apply=lost;self.execute()
        self.calendar.event=replace(self.calendar.event,title='Manual title')
        self.assertEqual(self.executor.reconcile(self.ctx,self.bound.id)['status'],'unknown');self.assertEqual(len(self.calendar.calls),1)
    def test_preexisting_attempt_marker_requires_review_even_with_fresh_confirmation(self):
        self.calendar.event=replace(self.calendar.event,extensions={'private':{'kulagina_consultation_operation':'earlier-operation'}})
        self.bound=replace(self.bound,event_revision=event_revision(self.calendar.event))
        with self.assertRaises(ExecutorError):self.execute()
        self.assertEqual(self.calendar.calls,[])
    def test_source_changes_during_calendar_read_denied(self):
        original=self.calendar.read
        def changed(event_id):
            result=original(event_id);self.sheet=replace(self.sheet,rows=(self.row[:7]+('Changed topic',)+self.row[8:],));return result
        self.calendar.read=changed
        with self.assertRaises(ExecutorError):self.execute()
        self.assertEqual(self.calendar.calls,[])
    def test_different_plan_cannot_reclaim_same_request_after_unknown(self):
        self.calendar.error=TimeoutError('mock before accept');self.execute()
        self.bound=replace(self.bound,id='second-plan')
        with self.assertRaises(ExecutorError):self.executor.execute(self.ctx,'second-plan',execution_enabled=True)
        self.assertEqual(len(self.calendar.calls),1)
    def test_revoke_after_claim_does_not_call_calendar_mutation(self):
        calls=[];original=self.executor.load_plan
        def revoked(plan_id):
            calls.append(1)
            if len(calls)==2:self.policy=synthetic_policy(bindings=())
            return original(plan_id)
        self.executor.load_plan=revoked
        self.assertEqual(self.execute()['status'],'blocked_preflight');self.assertEqual(self.calendar.calls,[])
    def test_real_calendar_port_mock_http_timeout_reconciles_without_patch_retry(self):
        import test_nvsu_google as google
        from nvsu_google import GoogleCalendarAdapter
        from consultation_calendar import ConsultationCalendarPort
        class Session(google.FakeSession):
            def request(this,method,url,**kw):
                if url.endswith('/calendars/synthetic-calendar'):
                    this.calls.append((method,url,copy.deepcopy(kw)))
                    return google.Response(200,{'id':'synthetic-calendar','timeZone':'Asia/Yekaterinburg'})
                return super().request(method,url,**kw)
        session=Session();session.events['synthetic-hold']={'id':'synthetic-hold','etag':'v1','summary':'Synthetic pending','location':'Кабинет 317','description':'Synthetic note',
            'start':{'dateTime':self.start.isoformat()},'end':{'dateTime':(self.start+dt.timedelta(minutes=20)).isoformat()}}
        self.calendar=ConsultationCalendarPort(GoogleCalendarAdapter('synthetic-calendar',session,allow_writes=True),clock=lambda:self.now)
        self.bound=replace(self.bound,event_revision=event_revision(self.calendar.read('synthetic-hold')))
        self.executor.close();self.executor=self.open();self.addCleanup(self.executor.close);session.fail_patch=True
        self.assertEqual(self.execute()['status'],'unknown')
        self.assertEqual(self.executor.reconcile(self.ctx,'synthetic-plan')['status'],'calendar_reconciled_present')
        self.assertEqual(sum(method=='PATCH' for method,_,_ in session.calls),1)
    def test_reconciliation_never_reads_calendar_after_owner_revoke(self):
        self.calendar.error=TimeoutError('mock before accept');self.execute();before=self.calendar.reads
        self.policy=synthetic_policy(bindings=())
        with self.assertRaises(ExecutorError):self.executor.reconcile(self.ctx,'synthetic-plan')
        self.assertEqual(self.calendar.reads,before)
    def test_slow_absence_read_does_not_reconcile_using_stale_result(self):
        self.rejection()
        def lost():raise TimeoutError('mock deleted')
        self.calendar.after_apply=lost;self.execute();original=self.calendar.read
        def slow(event_id):
            result=original(event_id);self.now+=dt.timedelta(minutes=6);return result
        self.calendar.read=slow
        with self.assertRaises(ExecutorError):self.executor.reconcile(self.ctx,'synthetic-plan')
        self.assertEqual(self.executor.result(self.ctx,'synthetic-plan')['status'],'unknown')
    def test_blocked_receipt_failure_does_not_allow_unrecorded_retry(self):
        original=self.executor.busy_snapshot;calls=[]
        def changed():
            calls.append(1)
            if len(calls)>1:self.busy_events+=(BusyEvent('lesson',self.start,self.start+dt.timedelta(hours=1)),)
            return original()
        self.executor.busy_snapshot=changed
        self.executor.db.execute("CREATE TRIGGER fail_blocked BEFORE UPDATE ON calendar_attempts WHEN NEW.phase='blocked_preflight' BEGIN SELECT RAISE(ABORT,'private diagnostic'); END")
        self.assertEqual(self.execute()['status'],'needs_recovery');self.assertEqual(self.calendar.calls,[])
        self.assertEqual(self.execute()['status'],'inflight_or_unknown')
    def test_offline_demo_uses_actual_port_but_never_network(self):
        from unittest.mock import patch
        from consultation_execution_demo import run_execution_demo
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network forbidden')):
            output=run_execution_demo()
        self.assertIn('Всего mock PATCH: 1',output);self.assertIn('calendar_reconciled_present',output)
        self.assertIn('Реальных HTTP-запросов, событий, изменений таблицы и сообщений: 0',output)
