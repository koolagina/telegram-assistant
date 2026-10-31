"""Actual temporary lecture/inbox/dispatch stores; no real account or API."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assistant_access import Binding
from report_worker import ReportWorker
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
import test_lecture_windows as fixtures

class LectureWorkerTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.WindowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.bindings=tuple(replace(b,subject='101' if b.subject=='001' else '102') for b in self.f.bindings)+(Binding('telegram','103','student','student-a',frozenset({'attendance.register'}),confirmed=True),)
        self.store=self.f.store();self.addCleanup(self.store.db.close);self.service=self.f.service(self.store)
        root=Path(self.f.directory.name)
        self.inbox=TelegramInbox(root/'inbox.db',namespace='synthetic-project',bot_id=9001);self.addCleanup(self.inbox.db.close)
        self.ledger=DispatchLedger(root/'dispatch.db',namespace='synthetic-project',bot_id=9001);self.addCleanup(self.ledger.db.close);self.calls=[]
    def enqueue(self,uid,text,sender=102):
        self.inbox.store_batch({'ok':True,'result':[{'update_id':uid,'message':{'message_id':uid,'date':1793160000,'from':{'id':sender,'is_bot':False},'chat':{'id':sender,'type':'private'},'text':text}}]},expected_offset=self.inbox.offset())
    def send(self,method,payload):
        self.calls.append(1)
        return {'ok':True,'result':{'message_id':len(self.calls),'chat':{'id':payload['chat_id'],'type':'private'},'from':{'id':9001,'is_bot':True}}}
    def worker(self,enabled=True,factory=None):
        return ReportWorker(self.inbox,self.ledger,reader_factory=lambda:None,send=self.send,lecture_service_factory=(factory or (lambda:self.service)) if enabled else None)
    def test_lecture_command_repreparation_does_not_create_two_windows(self):
        self.enqueue(1,'/lecturecode lecture-a')
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['status'],'api_confirmed')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],1)
        self.assertEqual(self.worker().step(dispatch_enabled=True),());self.assertEqual(len(self.calls),1)
    def test_attendance_repreparation_records_once(self):
        from assistant_access import Context
        window=self.service.open(Context('telegram','102',authenticated=True,private=True),'lecture-a','initial')
        self.enqueue(1,'/attend lecture-a '+window.code,103)
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['status'],'api_confirmed')
        self.assertEqual(self.store.attendance_count(),1);self.assertEqual(len(self.calls),1)
    def test_feature_disabled_defers_without_opening(self):
        self.enqueue(1,'/lecturecode lecture-a')
        self.assertEqual(self.worker(enabled=False).step(dispatch_enabled=True)[0]['queue_status'],'deferred')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0);self.assertEqual(self.calls,[])
    def test_teacher_revoke_between_route_and_dispatch_no_code_sent(self):
        self.enqueue(1,'/lecturecode lecture-a');calls=[]
        def factory():
            calls.append(1)
            if len(calls)>1:self.f.bindings=tuple(replace(b,active=False) if b.subject=='102' else b for b in self.f.bindings)
            return self.service
        self.assertEqual(self.worker(factory=factory).step(dispatch_enabled=True)[0]['status'],'cancelled')
        self.assertEqual(self.calls,[])
    def test_student_cannot_impersonate_teacher_in_command(self):
        self.enqueue(1,'/lecturecode lecture-a',103)
        self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['status'],'cancelled')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
    def test_request_scope_is_stable_across_worker_restart(self):
        self.enqueue(1,'/lecturecode lecture-a');self.worker().step(dispatch_enabled=True)
        self.enqueue(2,'/lecturecode lecture-a');self.worker().step(dispatch_enabled=True)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],2)
