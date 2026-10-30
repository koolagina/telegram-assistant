"""Separate ACK and business receipts, actual SQLite, fake external calls."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from callback_ack import CallbackAckLedger
from report_worker import ReportWorker,WorkerError
import test_academic_worker as fixtures

class CallbackWorkerTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.AcademicWorkerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.acks=CallbackAckLedger(self.f.root/'ack.db',namespace='synthetic-academic',bot_id=9001);self.addCleanup(self.acks.db.close)
        self.calls=[]
        token=self.f.f.menu.prepare(self.f.f.ctx('103'),'/overview').buttons[0][0].callback_data
        self.f.callback(token)
    def ack(self,method,payload):
        self.assertFalse(self.acks.db.in_transaction);self.calls.append((method,payload));return {'ok':True,'result':True}
    def worker(self,ack=None,send=None):
        return ReportWorker(self.f.inbox,self.f.ledger,reader_factory=lambda:self.f.f.f.r.reader,send=send or self.f.send,academic_menu_factory=lambda:self.f.f.menu,callback_ledger=self.acks,acknowledge=ack or self.ack)
    def test_one_ack_separate_from_one_message(self):
        out=self.worker().step(dispatch_enabled=True)[0]
        self.assertEqual(out['callback_ack'],'api_confirmed');self.assertEqual(out['status'],'api_confirmed');self.assertIsNone(out['delivered'])
        self.assertEqual(len(self.calls),1);self.assertEqual(len(self.f.calls),1)
        self.assertEqual(self.worker().step(dispatch_enabled=True),())
    def test_ack_timeout_does_not_repeat_business_message(self):
        def timeout(method,payload):self.ack(method,payload);raise TimeoutError()
        out=self.worker(ack=timeout).step(dispatch_enabled=True)[0]
        self.assertEqual(out['callback_ack'],'unknown');self.assertEqual(out['status'],'api_confirmed')
        self.worker().step(dispatch_enabled=True);self.assertEqual(len(self.calls),1);self.assertEqual(len(self.f.calls),1)
    def test_denied_stale_click_ack_contains_no_text(self):
        self.f.f.f.j.policy=self.f.f.f.j.f.policy(bindings=())
        out=self.worker().step(dispatch_enabled=True)[0]
        self.assertEqual(out['status'],'cancelled');self.assertEqual(out['callback_ack'],'api_confirmed')
        self.assertEqual(set(self.calls[0][1]),{'callback_query_id'});self.assertEqual(self.f.calls,[])
    def test_mark_failure_recovers_both_receipts_without_repeats(self):
        with patch.object(self.f.inbox,'mark',side_effect=RuntimeError()):self.worker().step(dispatch_enabled=True)
        self.worker().step(dispatch_enabled=True)
        self.assertEqual(len(self.calls),1);self.assertEqual(len(self.f.calls),1)
    def test_ack_storage_failure_keeps_inbox_for_recovery(self):
        with patch.object(self.acks,'attempt',side_effect=RuntimeError()):
            self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['queue_status'],'needs_recovery')
        self.assertEqual(len(self.f.inbox.pending()),1)
        self.worker().step(dispatch_enabled=True)
        self.assertEqual(len(self.calls),1);self.assertEqual(len(self.f.calls),1)
    def test_configuration_must_be_paired_and_matching(self):
        with self.assertRaises(WorkerError):ReportWorker(self.f.inbox,self.f.ledger,reader_factory=lambda:None,send=self.f.send,callback_ledger=self.acks)
        with CallbackAckLedger(self.f.root/'other.db',namespace='foreign',bot_id=9001) as other:
            with self.assertRaises(WorkerError):ReportWorker(self.f.inbox,self.f.ledger,reader_factory=lambda:None,send=self.f.send,callback_ledger=other,acknowledge=self.ack)
    def test_business_unknown_and_ack_are_independent(self):
        def lost(method,payload):self.f.send(method,payload);raise TimeoutError()
        out=self.worker(send=lost).step(dispatch_enabled=True)[0]
        self.assertEqual(out['status'],'unknown');self.assertEqual(out['callback_ack'],'api_confirmed')
        self.assertEqual(len(self.calls),1);self.assertEqual(len(self.f.calls),1)
    def test_structural_query_helper_refuses_group_or_other_bot(self):
        from copy import deepcopy
        from telegram_report_adapter import verified_callback_query_id
        update=self.f.inbox.pending()[0]['update']
        self.assertEqual(verified_callback_query_id(update,9001),'q-1')
        group=deepcopy(update);group['callback_query']['message']['chat']['type']='group'
        other=deepcopy(update);other['callback_query']['message']['from']['id']=9002
        self.assertIsNone(verified_callback_query_id(group,9001));self.assertIsNone(verified_callback_query_id(other,9001))
    def test_readiness_reports_ack_unknown_without_retry(self):
        from academic_readiness import inspect_academic_runtime
        def lost(method,payload):self.ack(method,payload);raise TimeoutError()
        worker=self.worker(ack=lost);worker.step(dispatch_enabled=True)
        out=inspect_academic_runtime(worker,policy=self.f.f.f.j.policy,journal=self.f.f.f.j.reader,overview=self.f.f.f.service,menu=self.f.f.menu)
        self.assertEqual(out['callback_ack']['unknown'],1);self.assertIn('callback_outcomes_need_review',out['blockers'])
        self.assertEqual(len(self.calls),1);self.assertFalse(out['ready_for_live'])
    def test_ack_happens_before_potentially_slow_message_send(self):
        def send(method,payload):
            self.assertEqual(self.acks.result(1)['status'],'api_confirmed')
            return self.f.send(method,payload)
        self.assertEqual(self.worker(send=send).step(dispatch_enabled=True)[0]['status'],'api_confirmed')
