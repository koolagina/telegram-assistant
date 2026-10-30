"""Actual SQLite inbox/ledger + academic menu/overview; all external I/O mocked."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_worker import ReportWorker,WorkerError
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
from academic_menu import AcademicMenu
import test_academic_menu as fixtures

class AcademicWorkerTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.AcademicMenuTests();self.f.setUp()
        self.f.f.j.policy=self.f.f.j.f.policy(bindings=tuple(replace(b,subject={'001':'101','003':'103','004':'104'}.get(b.subject,b.subject)) for b in self.f.f.j.f.bindings))
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.inbox=TelegramInbox(self.root/'inbox.db',namespace='synthetic-academic',bot_id=9001)
        self.ledger=DispatchLedger(self.root/'dispatch.db',namespace='synthetic-academic',bot_id=9001)
        self.addCleanup(self.inbox.db.close);self.addCleanup(self.ledger.db.close)
        self.calls=[]
    def store(self,text='/overview',sender=103):
        self.inbox.store_batch({'ok':True,'result':[{'update_id':1,'message':{'message_id':1,'date':1793160000,'from':{'id':sender,'is_bot':False},'chat':{'id':sender,'type':'private'},'text':text}}]},expected_offset=0)
    def callback(self,token):
        self.inbox.store_batch({'ok':True,'result':[{'update_id':1,'callback_query':{'id':'q-1','from':{'id':103,'is_bot':False},'message':{'message_id':2,'date':1793160000,'chat':{'id':103,'type':'private'},'from':{'id':9001,'is_bot':True}},'data':token}}]},expected_offset=0)
    def send(self,method,payload):
        self.assertFalse(self.ledger.db.in_transaction)
        self.assertFalse(self.inbox.db.in_transaction)
        self.calls.append((method,payload))
        return {'ok':True,'result':{'message_id':50,'chat':{'id':payload['chat_id'],'type':'private'},'from':{'id':9001,'is_bot':True}}}
    def worker(self,menu=None,overview=None,send=None,enabled=True):
        return ReportWorker(self.inbox,self.ledger,reader_factory=lambda:self.f.f.r.reader,send=send or self.send,academic_menu_factory=(menu or (lambda:self.f.menu)) if enabled else None,overview_factory=(overview or (lambda:self.f.f.service)) if enabled else None)
    def test_menu_queue_dispatch_and_restart_do_not_resend(self):
        self.store();self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['status'],'api_confirmed')
        self.assertEqual(self.worker().step(dispatch_enabled=True),());self.assertEqual(len(self.calls),1)
        self.assertEqual(self.f.f.j.loads,0)
    def test_overview_reads_and_dispatches_via_same_ledger(self):
        self.store('/overview enrollment-a')
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['status'],'api_confirmed')
        self.assertIn('Журнал',self.calls[0][1]['text']);self.assertEqual(len(self.calls),1)
    def test_disabled_dispatch_cannot_send(self):
        self.store()
        with self.assertRaises(WorkerError):self.worker().step()
        self.assertEqual(self.calls,[])
    def test_menu_feature_disabled_defers_to_other_handlers(self):
        self.store();self.assertEqual(self.worker(enabled=False).step(dispatch_enabled=True)[0]['queue_status'],'deferred')
        self.assertEqual(self.calls,[]);self.assertEqual(len(self.inbox.pending()),1)
    def test_revocation_between_route_and_dispatch_cancels(self):
        self.store();attempts=[]
        def factory():
            attempts.append(1)
            if len(attempts)==2:self.f.f.j.policy=self.f.f.j.f.policy(bindings=())
            return self.f.menu
        self.assertEqual(self.worker(menu=factory).step(dispatch_enabled=True)[0]['status'],'cancelled')
        self.assertEqual(self.calls,[])
    def test_fresh_catalog_text_sent_instead_of_saved_route_text(self):
        self.store();attempts=[]
        def factory():
            attempts.append(1)
            return self.f.make([replace(self.f.entry,student_label='Новая дисциплина')]) if len(attempts)>1 else self.f.menu
        self.worker(menu=factory).step(dispatch_enabled=True)
        self.assertIn('Новая дисциплина',self.calls[0][1]['text'])
    def test_changed_catalog_between_callback_route_and_dispatch_cancels(self):
        # The actual polling sender is 103; mint the token for that authenticated context.
        token=self.f.menu.prepare(self.f.ctx('103'),'/overview').buttons[0][0].callback_data
        self.callback(token);attempts=[]
        def factory():
            attempts.append(1)
            return self.f.make([replace(self.f.entry,student_label='Changed')]) if len(attempts)>1 else self.f.menu
        self.assertEqual(self.worker(menu=factory).step(dispatch_enabled=True)[0]['status'],'cancelled')
        self.assertEqual(self.calls,[])
    def test_unknown_send_is_not_replayed(self):
        self.store()
        def lost(method,payload):self.send(method,payload);raise TimeoutError()
        self.assertEqual(self.worker(send=lost).step(dispatch_enabled=True)[0]['status'],'unknown')
        self.assertEqual(self.worker().step(dispatch_enabled=True),());self.assertEqual(len(self.calls),1)
    def test_confirmed_then_mark_failure_recovers_without_policy(self):
        self.store()
        with patch.object(self.inbox,'mark',side_effect=RuntimeError()):self.worker().step(dispatch_enabled=True)
        self.f.f.j.policy=self.f.f.j.f.policy(bindings=())
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['queue_status'],'handled')
        self.assertEqual(len(self.calls),1)
    def test_parallel_step_observes_inflight_without_second_send(self):
        self.store();nested=[]
        def concurrent(method,payload):
            nested.extend(self.worker().step(dispatch_enabled=True));return self.send(method,payload)
        self.worker(send=concurrent).step(dispatch_enabled=True)
        self.assertEqual(nested[0]['queue_status'],'inflight');self.assertEqual(len(self.calls),1)
    def test_stale_journal_before_send_cancels_overview(self):
        self.store('/overview enrollment-a');attempts=[]
        def factory():
            attempts.append(1)
            if len(attempts)==2:self.f.f.j.book.sha256='b'*64
            return self.f.f.service
        self.assertEqual(self.worker(overview=factory).step(dispatch_enabled=True)[0]['status'],'cancelled')
        self.assertEqual(self.calls,[])
    def test_invalid_factories_rejected(self):
        for key in ('overview_factory','academic_menu_factory'):
            with self.assertRaises(WorkerError):ReportWorker(self.inbox,self.ledger,reader_factory=lambda:None,send=self.send,**{key:True})
    def test_restart_reopens_durable_receipt_without_resending(self):
        self.store();self.worker().step(dispatch_enabled=True)
        with TelegramInbox(self.root/'inbox.db',namespace='synthetic-academic',bot_id=9001) as inbox, DispatchLedger(self.root/'dispatch.db',namespace='synthetic-academic',bot_id=9001) as ledger:
            worker=ReportWorker(inbox,ledger,reader_factory=lambda:self.f.f.r.reader,send=self.send,academic_menu_factory=lambda:self.f.menu)
            self.assertEqual(worker.step(dispatch_enabled=True),())
            self.assertEqual(ledger.result(1)['status'],'api_confirmed')
        self.assertEqual(len(self.calls),1)
    def test_accepted_send_then_receipt_failure_is_not_retried(self):
        self.store()
        with patch.object(self.ledger,'_finalize',side_effect=RuntimeError()):
            self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['queue_status'],'needs_recovery')
        result=self.worker().step(dispatch_enabled=True)
        self.assertEqual(result[0]['queue_status'],'inflight');self.assertEqual(len(self.calls),1)
    def test_api_rejection_is_blocked_without_retry(self):
        self.store()
        def reject(method,payload):self.calls.append((method,payload));return {'ok':False,'error_code':403}
        self.assertEqual(self.worker(send=reject).step(dispatch_enabled=True)[0]['status'],'api_rejected')
        self.assertEqual(self.worker().step(dispatch_enabled=True),());self.assertEqual(len(self.calls),1)
    def test_factory_failure_before_claim_does_not_send_or_drop_update(self):
        self.store()
        def fail():raise RuntimeError('private details')
        result=self.worker(menu=fail).step(dispatch_enabled=True)
        self.assertEqual(result[0]['queue_status'],'needs_recovery');self.assertEqual(self.calls,[])
        self.assertEqual(len(self.inbox.pending()),1);self.assertEqual(self.ledger.result(1)['status'],'not_attempted')
    def test_foreign_actor_is_cancelled_without_payload_or_send(self):
        self.store('/overview enrollment-a',sender=104)
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['status'],'cancelled')
        self.assertEqual(self.calls,[]);self.assertEqual(self.f.f.j.loads,0)
    def test_callback_dispatch_uses_current_actor_and_existing_ledger(self):
        token=self.f.menu.prepare(self.f.ctx('103'),'/overview').buttons[0][0].callback_data
        self.callback(token)
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['status'],'api_confirmed')
        self.assertIn('Журнал',self.calls[0][1]['text']);self.assertEqual(self.worker().step(dispatch_enabled=True),())
        self.assertEqual(len(self.calls),1)
