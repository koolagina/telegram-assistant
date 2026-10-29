"""Local authoritative fixture/CAS/outbox; no real Sheet or notifications."""
import copy
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import test_consultation_executor as executors
from assistant_demo import synthetic_policy
from assistant_access import Context
from decision_demo import DEMO_NOW
from consultation_actions import Booking,BusyEvent,BusySnapshot,ConsultationActions
from consultation_feed import HoldBinding
from consultation_executor import BoundPlan,ConsultationExecutor,event_revision
from consultation_workflow import ConsultationState,ConsultationWorkflow,WorkflowError

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.now=DEMO_NOW+dt.timedelta(hours=1);self.start=self.now+dt.timedelta(hours=1);self.policy=synthetic_policy();self.calls=[]
        self.ctx=Context('telegram','101',authenticated=True,private=True,sender='101')
        self.state=self.open_state();self.addCleanup(self.state.close)
        self.row=('synthetic-request',self.now,'Synthetic student','103',self.start.date().isoformat(),self.start.strftime('%H:%M'),20,'Synthetic topic','Ожидает решения','','synthetic-hold')
        self.state.seed(self.row)
        self.calendar=executors.FakeCalendar(self.now,self.start)
        self.bindings=(HoldBinding('synthetic-calendar','synthetic-hold','synthetic-request',self.start,self.start+dt.timedelta(minutes=20)),)
        self.actions=ConsultationActions(self.root/'actions.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=self.busy,student_eligible=lambda *args:True);self.addCleanup(self.actions.close)
        self.actions.add(Booking('synthetic-request','student-a',self.start,'synthetic-hold'))
        before=self.state.feed.snapshot().rows[0].revision;original=event_revision(self.calendar.event)
        intent=self.actions.preview(self.ctx,'synthetic-request','approve');plan=self.actions.confirm(self.ctx,intent.token)
        self.bound=BoundPlan('synthetic-plan','owner','synthetic-calendar',plan,before,original,self.now)
        self.executor=ConsultationExecutor(self.root/'calendar.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=lambda:self.policy,clock=lambda:self.now,load_plan=lambda plan_id:self.bound,source=self.state.feed,busy_snapshot=self.busy,hold_bindings=lambda:self.bindings,calendar=self.calendar);self.addCleanup(self.executor.close)
        self.workflow=ConsultationWorkflow(self.state,self.executor)
    def open_state(self):return ConsultationState(self.root/'source.sqlite3',namespace='synthetic',owner_id='owner',calendar_id='synthetic-calendar',spreadsheet_id='synthetic-sheet',bot_id=9001,policy_provider=lambda:self.policy,clock=lambda:self.now)
    def busy(self):return BusySnapshot((BusyEvent('synthetic-hold',self.start,self.start+dt.timedelta(minutes=20),'synthetic-request'),),self.now,self.start.replace(hour=0),self.start.replace(hour=23),True,True)
    def advance(self):return self.workflow.advance(self.ctx,self.bound.id,workflow_enabled=True)
    def send(self,method,payload):
        self.calls.append(copy.deepcopy(payload))
        return {'ok':True,'result':{'message_id':len(self.calls),'chat':{'id':payload['chat_id'],'type':'private'},'from':{'id':9001,'is_bot':True}}}
    def notify(self,send=None):return self.state.notify(self.ctx,self.bound.id,send=send or self.send,notifications_enabled=True)
    def test_default_off_does_not_claim_or_mutate(self):
        with self.assertRaises(WorkflowError):self.workflow.advance(self.ctx,self.bound.id)
        self.assertEqual(self.calendar.calls,[])
        self.assertEqual(self.state.db.execute('SELECT count(*) FROM workflow_claims').fetchone()[0],0)
    def test_calendar_success_finalizes_only_status_reason_and_two_jobs(self):
        result=self.advance();self.assertEqual(result['stage'],'finalized');self.assertEqual(result['source_status'],'Подтверждена')
        row=self.state.snapshot().rows[0]
        for index in range(11):
            if index not in (1,8,9):self.assertEqual(row[index],self.row[index])
        self.assertEqual(row[9],'Подтверждена владельцем');self.assertEqual(len(self.state.notice_status(self.ctx,self.bound.id)),2)
        self.assertEqual(self.calls,[]);self.assertEqual(len(self.calendar.calls),1)
    def test_repeat_and_restart_do_not_repeat_calendar_or_create_jobs(self):
        self.advance();self.advance();peer=self.open_state();self.addCleanup(peer.close)
        self.assertEqual(len(peer.notice_status(self.ctx,self.bound.id)),2)
        self.assertEqual(self.state.db.execute('SELECT count(*) FROM workflow_notices').fetchone()[0],2)
        self.assertEqual(len(self.calendar.calls),1)
    def test_cooperating_writer_cannot_edit_claimed_row(self):
        errors=[]
        def edit():
            try:self.state.edit(self.ctx,self.row[0],self.bound.source_revision,self.row[:7]+('Edited',)+self.row[8:])
            except WorkflowError:errors.append(1)
        self.calendar.before_apply=edit;self.advance()
        self.assertEqual(errors,[1]);self.assertEqual(self.state.snapshot().rows[0][7],'Synthetic topic')
    def test_cas_edit_before_decision_application_invalidates_bound_source(self):
        self.state.edit(self.ctx,self.row[0],self.bound.source_revision,self.row[:7]+('Edited',)+self.row[8:])
        with self.assertRaises(WorkflowError):self.advance()
        self.assertEqual(self.calendar.calls,[])
    def test_unknown_calendar_does_not_finalize_or_enqueue_until_reconciled(self):
        def lost():raise TimeoutError('mock accepted then lost')
        self.calendar.after_apply=lost;self.assertEqual(self.advance()['stage'],'calendar_pending')
        self.assertEqual(self.state.snapshot().rows[0][8],'Ожидает решения');self.assertEqual(self.state.notice_status(self.ctx,self.bound.id),())
        result=self.workflow.reconcile(self.ctx,self.bound.id,workflow_enabled=True)
        self.assertEqual(result['stage'],'finalized');self.assertEqual(len(self.calendar.calls),1)
    def test_finalization_failure_rolls_back_status_and_both_jobs(self):
        self.state.db.execute("CREATE TRIGGER fail_notice BEFORE INSERT ON workflow_notices BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(WorkflowError):self.advance()
        self.assertEqual(self.state.snapshot().rows[0][8],'Ожидает решения');self.assertEqual(self.state.notice_status(self.ctx,self.bound.id),())
        self.state.db.execute('DROP TRIGGER fail_notice');self.assertEqual(self.advance()['stage'],'finalized')
        self.assertEqual(len(self.calendar.calls),1)
    def test_uncoordinated_source_edit_after_calendar_is_not_overwritten(self):
        def edit():
            import json
            row=list(self.state.snapshot().rows[0]);row[7]='Manual edit'
            self.state.db.execute('UPDATE workflow_rows SET payload=? WHERE id=?',(json.dumps(row),row[0]))
        self.calendar.after_apply=edit
        with self.assertRaises(WorkflowError):self.advance()
        self.assertEqual(self.state.snapshot().rows[0][7],'Manual edit');self.assertEqual(self.state.snapshot().rows[0][8],'Ожидает решения')
        self.assertEqual(self.state.notice_status(self.ctx,self.bound.id),())
    def test_one_notification_unknown_does_not_prevent_other(self):
        self.advance()
        def send(method,payload):
            result=self.send(method,payload)
            if payload['chat_id']==103:raise TimeoutError('mock loss')
            return result
        result=self.notify(send)
        self.assertEqual({r['kind']:r['status'] for r in result},{'student':'unknown','owner':'api_confirmed'})
        self.notify();self.assertEqual(len(self.calls),2);self.assertEqual(len(self.calendar.calls),1)
    def test_notice_restart_has_no_duplicate_sends(self):
        self.advance();self.notify();peer=self.open_state();self.addCleanup(peer.close)
        peer.notify(self.ctx,self.bound.id,send=self.send,notifications_enabled=True)
        self.assertEqual(len(self.calls),2)
        self.assertTrue(all(row['delivered'] is None for row in self.state.notice_status(self.ctx,self.bound.id)))
    def test_notice_default_off_and_current_recipient_revocation(self):
        self.advance()
        with self.assertRaises(WorkflowError):self.state.notify(self.ctx,self.bound.id,send=self.send)
        self.policy=synthetic_policy(bindings=tuple(b for b in self.policy.bindings.values() if b.subject!='103'))
        result=self.notify();self.assertEqual({r['kind']:r['status'] for r in result},{'student':'cancelled','owner':'api_confirmed'})
        self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0]['chat_id'],101)
    def test_owner_revoke_denies_private_status_and_notifications(self):
        self.advance();self.policy=synthetic_policy(bindings=())
        with self.assertRaises(WorkflowError):self.notify()
        with self.assertRaises(WorkflowError):self.state.notice_status(self.ctx,self.bound.id)
        self.assertEqual(self.calls,[])
    def test_notification_api_rejection_is_not_delivery_and_not_retried(self):
        self.advance()
        def rejected(method,payload):self.calls.append(copy.deepcopy(payload));return {'ok':False,'error_code':429}
        result=self.notify(rejected);self.assertTrue(all(r['status']=='api_rejected' and r['delivered'] is None for r in result))
        self.notify();self.assertEqual(len(self.calls),2)
    def test_interrupted_student_send_keeps_owner_pending_for_next_pass(self):
        self.advance()
        def stop(method,payload):raise KeyboardInterrupt('mock stop')
        with self.assertRaises(KeyboardInterrupt):self.notify(stop)
        result=self.notify();self.assertEqual({r['kind']:r['status'] for r in result},{'student':'inflight_or_unknown','owner':'api_confirmed'})
        self.assertEqual(len(self.calls),1)
    def test_preserves_custom_decision_note_and_rejected_event_id(self):
        # New fixture before owner confirmation; do not overwrite original evidence.
        import json
        row=list(self.state.snapshot().rows[0]);row[9]='Synthetic existing note'
        self.state.db.execute('UPDATE workflow_rows SET payload=? WHERE id=?',(json.dumps(row),row[0]))
        original=self.bound
        calendar={'method':'delete','event_id':'synthetic-hold','expected_hold':original.plan['calendar']['expected_hold']}
        self.bound=BoundPlan(original.id,original.owner_id,original.calendar_id,dict(original.plan,action='reject',calendar=calendar),self.state.feed.snapshot().rows[0].revision,original.event_revision,original.confirmed_at)
        self.assertEqual(self.advance()['source_status'],'Отклонена')
        row=self.state.snapshot().rows[0];self.assertEqual(row[9],'Synthetic existing note');self.assertEqual(row[10],'synthetic-hold');self.assertIsNone(self.calendar.event)
    def test_notice_receipt_failure_does_not_block_second_recipient_or_retry(self):
        self.advance()
        self.state.db.execute("CREATE TRIGGER fail_student_receipt BEFORE UPDATE ON workflow_notices WHEN OLD.kind='student' AND NEW.phase='api_confirmed' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        result=self.notify();self.assertEqual({r['kind']:r['status'] for r in result},{'student':'needs_recovery','owner':'api_confirmed'})
        self.state.db.execute('DROP TRIGGER fail_student_receipt')
        self.assertEqual({r['kind']:r['status'] for r in self.notify()},{'student':'inflight_or_unknown','owner':'api_confirmed'})
        self.assertEqual(len(self.calls),2);self.assertEqual(len(self.calendar.calls),1)
    def test_parallel_notice_sender_does_not_duplicate_either_recipient(self):
        self.advance();peer=self.open_state();self.addCleanup(peer.close);nested=[]
        def send(method,payload):
            result=self.send(method,payload)
            if payload['chat_id']==103:nested.extend(peer.notify(self.ctx,self.bound.id,send=self.send,notifications_enabled=True))
            return result
        result=self.notify(send)
        self.assertTrue(all(r['status']=='api_confirmed' for r in result));self.assertEqual(len(self.calls),2)
        self.assertEqual({r['kind']:r['status'] for r in nested},{'student':'inflight_or_unknown','owner':'api_confirmed'})
    def test_wrong_bot_ack_is_unknown_for_each_recipient(self):
        self.advance()
        def wrong(method,payload):
            result=self.send(method,payload);result['result']['from']['id']=9002;return result
        self.assertTrue(all(r['status']=='unknown' for r in self.notify(wrong)));self.notify();self.assertEqual(len(self.calls),2)
    def test_subject_rebinding_never_sends_to_new_student_identity(self):
        from dataclasses import replace
        self.advance()
        bindings=tuple(replace(b,entity_id='student-b') if b.subject=='103' else b for b in self.policy.bindings.values())
        self.policy=synthetic_policy(bindings=bindings)
        result=self.notify();self.assertEqual({r['kind']:r['status'] for r in result},{'student':'cancelled','owner':'api_confirmed'})
        self.assertEqual([c['chat_id'] for c in self.calls],[101])
    def test_revoke_during_finalization_rolls_back_source_and_jobs(self):
        self.state.db.create_function('revoke_fixture',0,lambda:(setattr(self,'policy',synthetic_policy(bindings=())) or 1))
        self.state.db.execute('CREATE TRIGGER revoke_on_write AFTER UPDATE ON workflow_rows BEGIN SELECT revoke_fixture(); END')
        with self.assertRaises(WorkflowError):self.advance()
        self.assertEqual(self.state.snapshot().rows[0][8],'Ожидает решения')
        self.state.db.execute('DROP TRIGGER revoke_on_write');self.policy=synthetic_policy()
        self.assertEqual(self.state.notice_status(self.ctx,self.bound.id),());self.advance()
        self.assertEqual(len(self.calendar.calls),1)
    def test_finalization_rejects_mismatched_calendar_evidence(self):
        from dataclasses import replace
        self.state.claim(self.ctx,self.executor.prepare(self.ctx,self.bound.id));self.executor.execute(self.ctx,self.bound.id,execution_enabled=True)
        evidence=self.executor.evidence(self.ctx,self.bound.id)
        with self.assertRaises(WorkflowError):self.state.finalize(self.ctx,replace(evidence,plan_hash='0'*64))
        self.assertEqual(self.state.snapshot().rows[0][8],'Ожидает решения');self.assertEqual(self.state.notice_status(self.ctx,self.bound.id),())
    def test_claim_checks_recipient_against_current_source_policy(self):
        from dataclasses import replace
        self.policy=synthetic_policy(bindings=tuple(replace(b,entity_id='student-b') if b.subject=='103' else b for b in self.policy.bindings.values()))
        with self.assertRaises(WorkflowError):self.state.claim(self.ctx,self.bound)
        self.assertEqual(self.state.db.execute('SELECT count(*) FROM workflow_claims').fetchone()[0],0)
    def test_raw_canonical_row_changes_only_status_and_reason(self):
        before=self.state.snapshot().rows[0];self.advance();after=self.state.snapshot().rows[0]
        self.assertEqual(len(before),11);self.assertEqual(len(after),11)
        self.assertEqual([i for i in range(11) if before[i]!=after[i]],[8,9])
    def test_pending_status_reports_actual_calendar_outcome(self):
        def lost():raise TimeoutError('mock accepted')
        self.calendar.after_apply=lost;self.advance()
        self.assertEqual(self.state.status(self.ctx,self.bound.id)['calendar'],'unknown')
    def test_two_local_cas_writers_cannot_overwrite_each_other(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        def edit(topic):
            peer=self.open_state()
            try:
                barrier.wait(timeout=5)
                try:peer.edit(self.ctx,self.row[0],self.bound.source_revision,self.row[:7]+(topic,)+self.row[8:]);return True
                except WorkflowError:return False
            finally:peer.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(edit,'Synthetic A'),pool.submit(edit,'Synthetic B')]
            results=[f.result(timeout=10) for f in futures]
        self.assertEqual(sorted(results),[False,True]);self.assertEqual(self.calendar.calls,[])
    def test_unverified_success_dictionary_cannot_finalize_source(self):
        self.state.claim(self.ctx,self.executor.prepare(self.ctx,self.bound.id))
        with self.assertRaises(WorkflowError):self.state.finalize(self.ctx,{'status':'calendar_api_confirmed'})
        self.assertEqual(self.state.snapshot().rows[0][8],'Ожидает решения')
        self.assertEqual(self.state.notice_status(self.ctx,self.bound.id),())
    def test_complete_workflow_demo_never_networks_or_duplicates(self):
        from consultation_workflow_demo import run_workflow_demo
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network forbidden')):
            output=run_workflow_demo()
        self.assertIn('Mock PATCH: 1; mock отправок уведомлений: 2',output)
        self.assertIn('student=unknown, owner=api_confirmed',output)
        self.assertIn('Локальная строка: Подтверждена',output)
