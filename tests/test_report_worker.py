"""Queue processing with real local stores and a mock sender only."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_worker import ReportWorker,WorkerError
from assistant_demo import SyntheticAssistantSession
from report_dispatch import DispatchLedger
from telegram_inbox import TelegramInbox

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.session=SyntheticAssistantSession(self.root);self.session.__enter__();self.addCleanup(self.session.__exit__,None,None,None);self.session.ingest(40)
        self.inbox=TelegramInbox(self.root/'inbox.sqlite3',namespace='synthetic-assistant',bot_id=9001);self.inbox.__enter__();self.addCleanup(self.inbox.__exit__,None,None,None)
        self.ledger=DispatchLedger(self.root/'dispatch.sqlite3',namespace='synthetic-assistant',bot_id=9001);self.ledger.__enter__();self.addCleanup(self.ledger.__exit__,None,None,None)
        self.update={'update_id':1,'message':{'message_id':1,'date':1793160000,'from':{'id':103,'is_bot':False},'chat':{'id':103,'type':'private'},'text':'/progress'}}
        self.inbox.store_batch({'ok':True,'result':[self.update]},expected_offset=0);self.calls=[]
    def send(self,method,payload):
        self.calls.append((method,payload))
        return {'ok':True,'result':{'message_id':1,'chat':{'id':103,'type':'private'},'from':{'id':9001,'is_bot':True}}}
    def worker(self,send=None,reader_factory=None):return ReportWorker(self.inbox,self.ledger,reader_factory=reader_factory or self.session.reader,send=send or self.send)
    def test_disabled_by_default_makes_no_attempt(self):
        with self.assertRaises(WorkerError):self.worker().step()
        self.assertEqual(self.calls,[]);self.assertEqual(len(self.inbox.pending()),1)
    def test_success_marks_queue_once_without_claiming_delivery(self):
        outcome=self.worker().step(dispatch_enabled=True)
        self.assertEqual(outcome[0]['status'],'api_confirmed');self.assertIsNone(outcome[0]['delivered'])
        self.assertEqual(self.worker().step(dispatch_enabled=True),())
        self.assertEqual(len(self.calls),1);self.assertEqual(self.inbox.offset(),2)
    def test_send_confirmed_then_mark_failure_recovery_never_resends(self):
        with patch.object(self.inbox,'mark',side_effect=RuntimeError('mock disk failure')):
            self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['queue_status'],'needs_recovery')
        self.assertEqual(len(self.inbox.pending()),1)
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['queue_status'],'handled')
        self.assertEqual(len(self.calls),1)
    def test_unknown_outcome_is_blocked_not_blindly_replayed(self):
        def unknown(method,payload):self.send(method,payload);raise TimeoutError('mock loss')
        self.assertEqual(self.worker(send=unknown).step(dispatch_enabled=True)[0]['queue_status'],'blocked')
        self.assertEqual(self.worker().step(dispatch_enabled=True),());self.assertEqual(len(self.calls),1)
    def test_non_report_messages_are_deferred_not_discarded(self):
        self.inbox.db.execute('DELETE FROM inbox_updates')
        self.inbox.db.execute("UPDATE inbox_meta SET value='0' WHERE key='next_offset'")
        self.update['message']['text']='/consultations'
        self.inbox.store_batch({'ok':True,'result':[self.update]},expected_offset=0)
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['queue_status'],'deferred')
        self.assertEqual(len(self.inbox.pending()),1);self.assertEqual(self.calls,[])
    def test_revoke_between_route_and_fresh_dispatch_cancels(self):
        calls=[]
        def reader():
            calls.append(1)
            if len(calls)==2:self.session.revoke_student_a()
            return self.session.reader()
        result=self.worker(reader_factory=reader).step(dispatch_enabled=True)
        self.assertEqual(result[0]['status'],'cancelled');self.assertEqual(self.calls,[])
    def test_mismatched_bot_or_project_is_rejected(self):
        other=DispatchLedger(self.root/'other.sqlite3',namespace='other-project',bot_id=9002)
        with other:
            with self.assertRaises(WorkerError):ReportWorker(self.inbox,other,reader_factory=self.session.reader,send=self.send)
    def test_preparation_failure_keeps_queue_without_send(self):
        def broken():raise RuntimeError('private registry detail')
        result=self.worker(reader_factory=broken).step(dispatch_enabled=True)
        self.assertEqual(result[0]['queue_status'],'needs_recovery');self.assertEqual(self.calls,[])
        self.assertEqual(len(self.inbox.pending()),1)

    def test_receipt_recovery_does_not_need_old_user_permission_or_resend(self):
        with patch.object(self.inbox,'mark',side_effect=RuntimeError('mock mark failure')):self.worker().step(dispatch_enabled=True)
        self.session.revoke_student_a()
        def no_reader():raise AssertionError('must recover from durable receipt, not private report')
        result=self.worker(reader_factory=no_reader).step(dispatch_enabled=True)
        self.assertEqual(result[0]['queue_status'],'handled');self.assertEqual(len(self.calls),1)
    def test_same_bot_different_project_cannot_share_worker(self):
        with DispatchLedger(self.root/'other-project.sqlite3',namespace='other-project',bot_id=9001) as other:
            with self.assertRaises(WorkerError):ReportWorker(self.inbox,other,reader_factory=self.session.reader,send=self.send)
