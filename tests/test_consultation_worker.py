"""Atomic local action processing, durable replies and mock dispatch only."""
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assistant_demo import synthetic_policy
from decision_demo import DEMO_NOW
from consultation_actions import ConsultationActions,Booking,BusyEvent,BusySnapshot,ActionError
from consultation_worker import ConsultationWorker,ConsultationWorkerError
from consultation_requests import handle_local_consultation_callback
from assistant_access import Context
from material_versions import digest
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.now=DEMO_NOW+dt.timedelta(hours=1);self.start=self.now+dt.timedelta(hours=1);self.policy=synthetic_policy();self.calls=[]
        self.hold=BusyEvent('synthetic-hold',self.start,self.start+dt.timedelta(minutes=20),'synthetic-request')
        self.service=self.open();self.addCleanup(self.service.close)
        self.service.add(Booking('synthetic-request','student-a',self.start,'synthetic-hold'))
        self.inbox=TelegramInbox(self.root/'inbox.sqlite3',namespace='synthetic',bot_id=9001);self.addCleanup(self.inbox.__exit__,None,None,None)
        self.ledger=DispatchLedger(self.root/'dispatch.sqlite3',namespace='synthetic',bot_id=9001);self.addCleanup(self.ledger.__exit__,None,None,None)
        self.ctx=Context('telegram','101',authenticated=True,private=True,sender='101')
    def open(self):return ConsultationActions(self.root/'actions.sqlite3',namespace='synthetic',owner_id='owner',bot_id=9001,policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=lambda:BusySnapshot((self.hold,),self.now,self.now.replace(hour=0),self.now.replace(hour=23),True,True),student_eligible=lambda *args:True)
    def worker(self,send=None):return ConsultationWorker(self.inbox,self.ledger,self.service,send=send or self.send)
    def send(self,method,payload):
        self.calls.append((method,payload))
        return {'ok':True,'result':{'message_id':1,'chat':{'id':101,'type':'private'},'from':{'id':9001,'is_bot':True}}}
    def update(self,text='/consult_request synthetic-request',subject=101):
        return {'update_id':self.inbox.offset(),'message':{'message_id':1,'date':1793246400,'from':{'id':subject,'is_bot':False},'chat':{'id':subject,'type':'private'},'text':text}}
    def callback(self,data,subject=101,bot=9001):
        return {'update_id':self.inbox.offset(),'callback_query':{'id':'q','from':{'id':subject,'is_bot':False},'message':{'message_id':1,'date':1793246400,'from':{'id':bot,'is_bot':True},'chat':{'id':subject,'type':'private'}},'data':data}}
    def store(self,update):self.inbox.store_batch({'ok':True,'result':[update]},expected_offset=self.inbox.offset())
    def confirmation(self):
        ref=self.service.reference(self.ctx,'synthetic-request')
        preview=handle_local_consultation_callback(self.service,self.ctx,'con:a:approve:'+ref)
        return next(b.callback_data for row in preview.buttons for b in row if b.callback_data.startswith('con:c:'))
    def test_default_off_changes_neither_receipts_nor_dispatch(self):
        self.store(self.update())
        with self.assertRaises(ConsultationWorkerError):self.worker().step()
        self.assertEqual(self.calls,[]);self.assertEqual(self.service.db.execute('SELECT count(*) FROM action_updates').fetchone()[0],0)
    def test_prepare_only_keeps_pending_and_does_not_execute_handler_twice(self):
        ref=self.service.reference(self.ctx,'synthetic-request');self.store(self.callback('con:a:approve:'+ref))
        self.assertEqual(self.worker().step(actions_enabled=True)[0]['queue_status'],'reply_ready')
        self.assertEqual(self.worker().step(actions_enabled=True)[0]['queue_status'],'reply_ready')
        self.assertEqual(self.service.db.execute('SELECT count(*) FROM action_intents').fetchone()[0],1)
        self.assertEqual(len(self.inbox.pending()),1);self.assertEqual(self.calls,[])
    def test_confirm_plan_and_mock_send_are_separate_successes(self):
        self.store(self.callback(self.confirmation()))
        result=self.worker().step(actions_enabled=True,dispatch_enabled=True)[0]
        self.assertEqual(result['status'],'api_confirmed');self.assertEqual(result['queue_status'],'handled');self.assertIsNone(result['delivered'])
        self.assertEqual(len(self.service.plans()),1);self.assertEqual(self.service.plans()[0]['execution'],'not_executed')
        self.assertEqual(len(self.calls),1);self.assertIn('не выполнены',self.calls[0][1]['text'])
    def test_local_receipt_failure_rolls_back_plan_status_and_intent(self):
        data=self.confirmation();self.store(self.callback(data))
        self.service.db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON action_updates BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        self.assertEqual(self.worker().step(actions_enabled=True)[0]['queue_status'],'needs_recovery')
        self.assertEqual(self.service.plans(),());self.assertEqual(self.service.booking('synthetic-request').status,'Ожидает решения')
        self.service.db.execute('DROP TRIGGER fail_receipt')
        self.assertEqual(self.worker().step(actions_enabled=True)[0]['queue_status'],'reply_ready');self.assertEqual(len(self.service.plans()),1)
    def test_restart_recovers_prepared_reply_without_repeating_plan(self):
        self.store(self.callback(self.confirmation()));self.worker().step(actions_enabled=True)
        self.service.close();self.service=self.open();self.addCleanup(self.service.close)
        with patch.object(self.service,'confirm',side_effect=AssertionError('must not run again')):
            self.assertEqual(self.worker().step(actions_enabled=True,dispatch_enabled=True)[0]['status'],'api_confirmed')
        self.assertEqual(len(self.service.plans()),1);self.assertEqual(len(self.calls),1)
    def test_unknown_send_never_repeats_action_or_send(self):
        self.store(self.callback(self.confirmation()))
        def lost(method,payload):self.send(method,payload);raise TimeoutError('mock only')
        self.assertEqual(self.worker(lost).step(actions_enabled=True,dispatch_enabled=True)[0]['queue_status'],'blocked')
        self.assertEqual(self.worker().step(actions_enabled=True,dispatch_enabled=True),())
        self.assertEqual(len(self.calls),1);self.assertEqual(len(self.service.plans()),1)
    def test_mark_failure_recovers_receipt_without_send_or_owner_read(self):
        self.store(self.callback(self.confirmation()))
        with patch.object(self.inbox,'mark',side_effect=RuntimeError('mock disk')):self.worker().step(actions_enabled=True,dispatch_enabled=True)
        self.policy=synthetic_policy(bindings=())
        self.assertEqual(self.worker().step(actions_enabled=True,dispatch_enabled=True)[0]['queue_status'],'handled')
        self.assertEqual(len(self.calls),1)
    def test_student_cannot_make_plan_or_see_owner_card(self):
        self.store(self.callback(self.confirmation(),subject=103))
        self.assertEqual(self.worker().step(actions_enabled=True,dispatch_enabled=True)[0]['status'],'cancelled')
        self.assertEqual(self.service.plans(),());self.assertEqual(self.calls,[])
    def test_revoke_between_local_prepare_and_reply_dispatch_cancels_send(self):
        self.store(self.callback(self.confirmation()));self.worker().step(actions_enabled=True)
        self.policy=synthetic_policy(bindings=())
        self.assertEqual(self.worker().step(actions_enabled=True,dispatch_enabled=True)[0]['status'],'cancelled')
        self.assertEqual(self.calls,[]);self.assertEqual(len(self.service.plans()),1)
    def test_report_and_foreign_bot_callback_are_deferred(self):
        self.store(self.update('/progress'))
        self.store(self.callback(self.confirmation(),bot=9002))
        outcomes=self.worker().step(actions_enabled=True,dispatch_enabled=True)
        self.assertTrue(all(x['queue_status']=='deferred' for x in outcomes));self.assertEqual(self.calls,[])
    def test_inflight_peer_is_not_blocked_or_sent_again(self):
        self.store(self.callback(self.confirmation()));nested=[]
        def send(method,payload):
            nested.extend(self.worker().step(actions_enabled=True,dispatch_enabled=True));return self.send(method,payload)
        self.assertEqual(self.worker(send).step(actions_enabled=True,dispatch_enabled=True)[0]['queue_status'],'handled')
        self.assertEqual(nested[0]['queue_status'],'inflight');self.assertEqual(len(self.calls),1);self.assertEqual(len(self.service.plans()),1)
    def test_changed_input_cannot_reuse_local_receipt(self):
        calls=[]
        from report_requests import PreparedReply
        process=lambda:(calls.append(1) or PreparedReply('prepared','Synthetic'))
        self.service.process_update(self.ctx,1,digest({'a':1}),process,actions_enabled=True)
        with self.assertRaises(ActionError):self.service.process_update(self.ctx,1,digest({'a':2}),process,actions_enabled=True)
        self.assertEqual(calls,[1])
    def test_bot_project_mismatch_denied_before_processing(self):
        other=DispatchLedger(self.root/'other.sqlite3',namespace='other',bot_id=9001);self.addCleanup(other.__exit__,None,None,None)
        with self.assertRaises(ConsultationWorkerError):ConsultationWorker(self.inbox,other,self.service,send=self.send)
    def test_process_stop_before_receipt_rolls_back_all_local_writes(self):
        from report_requests import PreparedReply
        intent=self.service.preview(self.ctx,'synthetic-request','approve')
        def stopped():
            self.service.confirm(self.ctx,intent.token);raise KeyboardInterrupt('mock process stop')
        with self.assertRaises(KeyboardInterrupt):self.service.process_update(self.ctx,1,digest({'x':1}),stopped,actions_enabled=True)
        self.assertEqual(self.service.plans(),());self.assertEqual(self.service.booking('synthetic-request').status,'Ожидает решения')
        self.service.process_update(self.ctx,1,digest({'x':1}),lambda:(self.service.confirm(self.ctx,intent.token) and PreparedReply('prepared','Synthetic')),actions_enabled=True)
        self.assertEqual(len(self.service.plans()),1)
    def test_corrupt_local_reply_never_reexecutes_handler_or_sends(self):
        self.store(self.callback(self.confirmation()));self.worker().step(actions_enabled=True)
        self.service.db.execute("UPDATE action_updates SET reply='corrupt' WHERE update_id=0")
        result=self.worker().step(actions_enabled=True,dispatch_enabled=True)[0]
        self.assertEqual(result['queue_status'],'needs_recovery');self.assertEqual(self.calls,[]);self.assertEqual(len(self.service.plans()),1)
    def test_invalid_reply_rolls_back_plan_in_same_transaction(self):
        from report_requests import PreparedReply
        intent=self.service.preview(self.ctx,'synthetic-request','approve')
        def invalid():
            self.service.confirm(self.ctx,intent.token)
            return PreparedReply('prepared','Synthetic',parse_mode='HTML')
        with self.assertRaises(ActionError):self.service.process_update(self.ctx,1,digest({'x':1}),invalid,actions_enabled=True)
        self.assertEqual(self.service.plans(),());self.assertEqual(self.service.booking('synthetic-request').status,'Ожидает решения')
    def test_revoke_during_processing_rolls_back_plan_and_receipt(self):
        from report_requests import PreparedReply
        intent=self.service.preview(self.ctx,'synthetic-request','approve')
        def revoke():
            self.service.confirm(self.ctx,intent.token);self.policy=synthetic_policy(bindings=())
            return PreparedReply('prepared','Synthetic')
        with self.assertRaises(ActionError):self.service.process_update(self.ctx,1,digest({'x':1}),revoke,actions_enabled=True)
        self.assertEqual(self.service.plans(),());self.assertEqual(self.service.db.execute('SELECT count(*) FROM action_updates').fetchone()[0],0)
    def test_v1_local_schema_upgrade_preserves_existing_plan_and_bindings(self):
        intent=self.service.preview(self.ctx,'synthetic-request','approve');old=self.service.confirm(self.ctx,intent.token)
        # Explicit synthetic v1 fixture: only the old four tables, no bot binding.
        self.service.db.execute('DROP TABLE action_updates');self.service.db.execute('DELETE FROM action_meta WHERE id=2')
        self.service.close();self.service=self.open();self.addCleanup(self.service.close)
        self.assertEqual(self.service.plans(),(old,));self.assertEqual(self.service.confirm(self.ctx,intent.token),old)
        tables={row[0] for row in self.service.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn('action_updates',tables)
    def test_existing_action_store_cannot_be_rebound_to_another_bot(self):
        with self.assertRaises(ActionError):ConsultationActions(self.root/'actions.sqlite3',namespace='synthetic',owner_id='owner',bot_id=9002,policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=lambda:None,student_eligible=lambda *args:True)
        self.store(self.update());self.assertEqual(self.worker().step(actions_enabled=True)[0]['queue_status'],'reply_ready')
    def test_unbound_action_store_cannot_start_worker(self):
        unbound=ConsultationActions(self.root/'unbound.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=lambda:None,student_eligible=lambda *args:True);self.addCleanup(unbound.close)
        with self.assertRaises(ConsultationWorkerError):ConsultationWorker(self.inbox,self.ledger,unbound,send=self.send)
    def test_interrupted_sender_leaves_inflight_without_reprocessing(self):
        self.store(self.callback(self.confirmation()))
        def stopped(*args):raise KeyboardInterrupt('mock process stop')
        with self.assertRaises(KeyboardInterrupt):self.worker(stopped).step(actions_enabled=True,dispatch_enabled=True)
        result=self.worker().step(actions_enabled=True,dispatch_enabled=True)[0]
        self.assertEqual(result['queue_status'],'inflight');self.assertEqual(len(self.service.plans()),1);self.assertEqual(self.calls,[])
    def test_group_wrong_private_chat_and_invalid_bot_user_are_deferred(self):
        for edit in ('group','chat','is_bot'):
            update=self.callback(self.confirmation())
            if edit=='group':update['callback_query']['message']['chat']['type']='group'
            if edit=='chat':update['callback_query']['message']['chat']['id']=103
            if edit=='is_bot':update['callback_query']['from']['is_bot']=True
            self.store(update)
        results=self.worker().step(actions_enabled=True,dispatch_enabled=True)
        self.assertTrue(all(r['queue_status']=='deferred' for r in results));self.assertEqual(self.service.plans(),());self.assertEqual(self.calls,[])
    def test_two_connections_process_same_update_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from report_requests import PreparedReply
        barrier=Barrier(2);calls=[]
        def run():
            service=self.open()
            try:
                barrier.wait(timeout=5)
                def process():
                    calls.append(1);intent=service.preview(self.ctx,'synthetic-request','approve')
                    return PreparedReply('prepared',intent.token)
                return service.process_update(self.ctx,1,digest({'synthetic':1}),process,actions_enabled=True)
            finally:service.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run) for _ in range(2)];results=[f.result(timeout=10) for f in futures]
        self.assertEqual(results[0],results[1]);self.assertEqual(calls,[1]);self.assertEqual(self.service.db.execute('SELECT count(*) FROM action_intents').fetchone()[0],1)
    def test_proposal_message_is_local_only_and_processed_once(self):
        ref=self.service.reference(self.ctx,'synthetic-request')
        self.store(self.update('/consult_propose '+ref+' '+self.start.replace(hour=14).strftime('%Y-%m-%d %H:%M')))
        self.worker().step(actions_enabled=True);self.worker().step(actions_enabled=True)
        self.assertEqual(self.service.db.execute('SELECT count(*) FROM action_intents').fetchone()[0],1)
        self.assertEqual(self.service.plans(),());self.assertEqual(self.calls,[])
