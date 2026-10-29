"""Verified local inbox→original review→consent→workflow, injected senders only."""
from pathlib import Path
import unittest
from unittest.mock import patch
import test_consultation_consent as fixtures
from consultation_actions import ConsultationActions,Booking
from consultation_consent import ConsultationConsent
from consultation_bound_worker import BoundConsultationWorker
from consultation_workflow import ConsultationWorkflow,WorkflowError
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
from assistant_demo import synthetic_policy

class BoundWorkerTests(unittest.TestCase):
    open_state=fixtures.ConsentTests.open_state
    busy=fixtures.ConsentTests.busy
    send=fixtures.ConsentTests.send
    def setUp(self):
        fixtures.ConsentTests.setUp(self)
        self.actions=ConsultationActions(self.root/'bot-actions.sqlite3',namespace='synthetic',owner_id='owner',bot_id=9001,policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=self.busy,student_eligible=lambda *args:True)
        self.addCleanup(self.actions.close);self.actions.add(Booking(self.row[0],'student-a',self.start,'synthetic-hold'))
        self.registry=ConsultationConsent(self.state,self.actions,self.calendar,hold_bindings=lambda:self.bindings)
        self.executor.load_plan=self.registry.load_confirmed;self.workflow=ConsultationWorkflow(self.state,self.executor)
        self.inbox=TelegramInbox(self.root/'inbox.sqlite3',namespace='synthetic',bot_id=9001);self.addCleanup(self.inbox.__exit__,None,None,None)
        self.ledger=DispatchLedger(self.root/'dispatch.sqlite3',namespace='synthetic',bot_id=9001);self.addCleanup(self.ledger.__exit__,None,None,None)
        self.ui=[]
    def sender(self,method,payload):
        self.ui.append(payload)
        return {'ok':True,'result':{'message_id':len(self.ui),'chat':{'id':payload['chat_id'],'type':'private'},'from':{'id':9001,'is_bot':True}}}
    def worker(self,send=None):return BoundConsultationWorker(self.inbox,self.ledger,self.registry,workflow=self.workflow,send=send or self.sender)
    def store(self,data,callback=False,subject=101,bot=9001):
        update={'update_id':self.inbox.offset()};message={'message_id':1,'date':1793246400,'chat':{'id':subject,'type':'private'}}
        if callback:
            message['from']={'id':bot,'is_bot':True};update['callback_query']={'id':'synthetic-query','from':{'id':subject,'is_bot':False},'message':message,'data':data}
        else:message.update(text=data,**{'from':{'id':subject,'is_bot':False}});update['message']=message
        self.inbox.store_batch({'ok':True,'result':[update]},expected_offset=self.inbox.offset())
    def button(self,payload,prefix):return next(b['callback_data'] for row in payload['reply_markup']['inline_keyboard'] for b in row if b['callback_data'].startswith(prefix))
    def review(self):
        self.store('/consult_request '+self.row[0]);self.worker().step(actions_enabled=True,dispatch_enabled=True)
        self.store(self.button(self.ui[-1],'bcon:a:approve:'),True);self.worker().step(actions_enabled=True,dispatch_enabled=True)
        return self.button(self.ui[-1],'bcon:c:')
    def test_default_off_makes_no_draft_or_ui(self):
        self.store('/consult_request '+self.row[0])
        with self.assertRaises(WorkflowError):self.worker().step()
        self.assertEqual(self.ui,[]);self.assertEqual(self.calendar.calls,[])
    def test_owner_sees_original_topic_and_separate_confirmation(self):
        confirm=self.review();self.assertIn('Synthetic topic',self.ui[-1]['text']);self.assertIn('Synthetic student',self.ui[-1]['text'])
        self.assertEqual(self.calendar.calls,[]);self.assertEqual(self.state.snapshot().rows[0][8],'Ожидает решения')
        self.store(confirm,True);self.worker().step(actions_enabled=True,dispatch_enabled=True)
        self.assertEqual(self.calendar.calls,[])  # Workflow flag remains off.
        self.assertEqual(self.state.db.execute("SELECT count(*) FROM workflow_reviews WHERE phase='confirmed'").fetchone()[0],1)
    def test_explicit_mock_workflow_completes_after_button_without_notice_sends(self):
        confirm=self.review();self.store(confirm,True)
        result=self.worker().step(actions_enabled=True,dispatch_enabled=True,workflow_enabled=True)[0]
        self.assertEqual(result['status'],'api_confirmed');self.assertEqual(self.state.snapshot().rows[0][8],'Подтверждена')
        self.assertEqual(len(self.calendar.calls),1);self.assertTrue(all(r['status']=='ready' for r in self.state.notice_status(self.ctx,confirm.rsplit(':',1)[1])))
    def test_prepare_only_replay_creates_one_review(self):
        self.store('/consult_request '+self.row[0]);self.worker().step(actions_enabled=True,dispatch_enabled=True)
        self.store(self.button(self.ui[-1],'bcon:a:approve:'),True)
        self.worker().step(actions_enabled=True);self.worker().step(actions_enabled=True)
        self.assertEqual(self.state.db.execute('SELECT count(*) FROM workflow_reviews').fetchone()[0],1)
    def test_unknown_ui_send_does_not_repeat_consent_or_calendar(self):
        confirm=self.review();self.store(confirm,True)
        def lost(method,payload):self.sender(method,payload);raise TimeoutError('mock UI lost')
        result=self.worker(lost).step(actions_enabled=True,dispatch_enabled=True,workflow_enabled=True)[0]
        self.assertEqual(result['status'],'unknown');self.assertEqual(result['queue_status'],'blocked')
        self.assertEqual(self.worker().step(actions_enabled=True,dispatch_enabled=True,workflow_enabled=True),());self.assertEqual(len(self.calendar.calls),1)
    def test_student_and_foreign_bot_cannot_publish_bound_plan(self):
        confirm=self.review();self.store(confirm,True,subject=103);self.store(confirm,True,bot=9002)
        result=self.worker().step(actions_enabled=True,dispatch_enabled=True,workflow_enabled=True)
        self.assertEqual(result[0]['status'],'cancelled');self.assertEqual(result[1]['queue_status'],'deferred')
        self.assertEqual(self.calendar.calls,[])
    def test_calendar_reads_are_never_under_core_or_source_transaction(self):
        original=self.calendar.read
        def read(event_id):
            self.assertFalse(self.state.db.in_transaction);self.assertFalse(self.actions.db.in_transaction)
            return original(event_id)
        self.calendar.read=read;confirm=self.review();self.store(confirm,True)
        self.worker().step(actions_enabled=True,dispatch_enabled=True,workflow_enabled=True)
        self.assertEqual(len(self.calendar.calls),1)
    def test_mark_failure_recovers_without_consent_or_send(self):
        confirm=self.review();self.store(confirm,True)
        with patch.object(self.inbox,'mark',side_effect=RuntimeError('mock failure')):self.worker().step(actions_enabled=True,dispatch_enabled=True,workflow_enabled=True)
        count=len(self.ui);self.policy=synthetic_policy(bindings=())
        self.assertEqual(self.worker().step(actions_enabled=True,dispatch_enabled=True,workflow_enabled=True)[0]['queue_status'],'handled')
        self.assertEqual(len(self.ui),count);self.assertEqual(len(self.calendar.calls),1)
    def test_foreign_report_command_is_deferred(self):
        self.store('/progress');result=self.worker().step(actions_enabled=True,dispatch_enabled=True)
        self.assertEqual(result[0]['queue_status'],'deferred');self.assertEqual(self.ui,[])
    def test_proposal_menu_remains_available_through_legacy_local_handler(self):
        self.store('/consult_request '+self.row[0]);self.worker().step(actions_enabled=True,dispatch_enabled=True)
        proposal=self.button(self.ui[-1],'con:p:');self.store(proposal,True);self.worker().step(actions_enabled=True,dispatch_enabled=True)
        self.assertIn('/consult_propose',self.ui[-1]['text']);self.assertEqual(self.calendar.calls,[])
