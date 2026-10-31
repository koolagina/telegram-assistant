"""Teacher lecture button through real SQLite queues and mock sends/ACK."""
from pathlib import Path
import sys
import unittest
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from lecture_menu import LectureMenu,LectureLabel
from assistant_access import Context
from report_worker import ReportWorker
from callback_ack import CallbackAckLedger
import test_lecture_worker as fixtures

class LectureMenuWorkerTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.LectureWorkerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.menu=LectureMenu([LectureLabel('lecture-a','Экология','317')],service=self.f.service)
        self.ack=CallbackAckLedger(Path(self.f.f.directory.name)/'ack.db',namespace='synthetic-project',bot_id=9001);self.addCleanup(self.ack.db.close);self.ack_calls=[]
    def acknowledge(self,method,payload):self.ack_calls.append(method);return {'ok':True,'result':True}
    def worker(self,enabled=True):
        return ReportWorker(self.f.inbox,self.f.ledger,reader_factory=lambda:None,send=self.f.send,lecture_menu_factory=(lambda:self.menu) if enabled else None,callback_ledger=self.ack,acknowledge=self.acknowledge)
    def click(self,data,uid=1):
        self.f.inbox.store_batch({'ok':True,'result':[{'update_id':uid,'callback_query':{'id':'query-'+str(uid),'from':{'id':102,'is_bot':False},'message':{'message_id':1,'date':1793160000,'from':{'id':9001,'is_bot':True},'chat':{'id':102,'type':'private'}},'data':data}}]},expected_offset=self.f.inbox.offset())
    def token(self):return self.menu.prepare(Context('telegram','102',authenticated=True,private=True),'/lectures').buttons[0][0].callback_data
    def test_menu_then_click_creates_one_window_and_independent_ack(self):
        self.f.enqueue(1,'/lectures');self.assertEqual(self.worker().step(dispatch_enabled=True)[0]['status'],'api_confirmed')
        self.assertEqual(self.f.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
        self.click(self.token(),2);out=self.worker().step(dispatch_enabled=True)[0]
        self.assertEqual(out['status'],'api_confirmed');self.assertEqual(out['callback_ack'],'api_confirmed')
        self.assertEqual(self.f.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],1)
        self.assertEqual(self.worker().step(dispatch_enabled=True),());self.assertEqual(len(self.f.calls),2);self.assertEqual(len(self.ack_calls),1)
    def test_default_disabled_preserves_update(self):
        self.f.enqueue(1,'/lectures');self.assertEqual(self.worker(enabled=False).step(dispatch_enabled=True)[0]['queue_status'],'deferred')
        self.assertEqual(self.f.calls,[])
    def test_changed_schedule_click_cancels_without_code(self):
        token=self.token();self.f.f.lecture=replace(self.f.f.lecture,verified=False);self.click(token)
        out=self.worker().step(dispatch_enabled=True)[0]
        self.assertEqual(out['status'],'cancelled');self.assertEqual(out['callback_ack'],'api_confirmed')
        self.assertEqual(self.f.calls,[]);self.assertEqual(self.f.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
    def test_foreign_bot_callback_not_routed(self):
        from telegram_report_adapter import TelegramReportAdapter
        update={'update_id':1,'callback_query':{'id':'query','from':{'id':102,'is_bot':False},'message':{'message_id':1,'date':1793160000,'from':{'id':9002,'is_bot':True},'chat':{'id':102,'type':'private'}},'data':self.token()}}
        adapter=TelegramReportAdapter(reader_factory=lambda:None,bot_id=9001,fetch_verified_updates=lambda:{'ok':True,'result':[update]},lecture_menu_factory=lambda:self.menu)
        self.assertEqual(adapter.prepare_batch(),())
    def test_invalid_menu_factory_rejected(self):
        from report_worker import WorkerError
        with self.assertRaises(WorkerError):ReportWorker(self.f.inbox,self.f.ledger,reader_factory=lambda:None,send=self.f.send,lecture_menu_factory=True)
