"""Decision view integration with local stores, typed fake Sheet and mock API."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from decision_demo import build_demo_queue,DEMO_NOW,run_decision_demo
from decision_sources import ConsultationRecord
from assistant_demo import SyntheticAssistantSession
from report_dispatch import DispatchLedger
from telegram_report_adapter import TelegramReportAdapter
from telegram_inbox import TelegramInbox
from report_worker import ReportWorker

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.session=SyntheticAssistantSession(self.root);self.session.__enter__();self.addCleanup(self.session.__exit__,None,None,None);self.session.ingest(40)
        self.ledger=DispatchLedger(self.root/'dispatch.sqlite3',namespace='synthetic-assistant',bot_id=9001);self.ledger.__enter__();self.addCleanup(self.ledger.__exit__,None,None,None)
        self.records=[ConsultationRecord('request-a','Ожидает решения',DEMO_NOW,DEMO_NOW,'Synthetic student','Synthetic topic')]
        self.factory=lambda:build_demo_queue(self.session,self.ledger,self.records)
    def update(self,subject=101):return {'update_id':1,'message':{'message_id':1,'date':1793246400,'from':{'id':subject,'is_bot':False},'chat':{'id':subject,'type':'private'},'text':'/decisions'}}
    def adapter(self,update):return TelegramReportAdapter(reader_factory=self.session.reader,bot_id=9001,fetch_verified_updates=lambda:{'ok':True,'result':[update]},decision_service_factory=self.factory)
    def test_owner_command_and_callback_use_current_sources(self):
        reply=self.adapter(self.update()).prepare_batch()[0].reply
        self.assertIn('Консультации: 1',reply.text);self.assertIn('Проверки работ: 1',reply.text)
        button=next(b for row in reply.buttons for b in row if b.callback_data.startswith('dec:o:'))
        callback={'update_id':2,'callback_query':{'id':'q','from':{'id':101,'is_bot':False},'message':{'message_id':1,'date':1793246400,'chat':{'id':101,'type':'private'},'from':{'id':9001,'is_bot':True}},'data':button.callback_data}}
        self.assertEqual(self.adapter(callback).prepare_batch()[0].reply.status,'prepared')
    def test_student_cannot_open_owner_decisions(self):
        self.assertEqual(self.adapter(self.update(103)).prepare_batch()[0].reply.status,'unavailable')
    def test_opt_in_worker_prepares_decision_menu_only_with_mock_sender(self):
        with TelegramInbox(self.root/'inbox.sqlite3',namespace='synthetic-assistant',bot_id=9001) as inbox:
            inbox.store_batch({'ok':True,'result':[self.update()]},expected_offset=0);calls=[]
            def send(method,payload):
                calls.append(payload)
                return {'ok':True,'result':{'message_id':1,'chat':{'id':101,'type':'private'},'from':{'id':9001,'is_bot':True}}}
            worker=ReportWorker(inbox,self.ledger,reader_factory=self.session.reader,send=send,decision_service_factory=self.factory)
            self.assertEqual(worker.step(dispatch_enabled=True)[0]['status'],'api_confirmed')
            self.assertEqual(len(calls),1);self.assertEqual(calls[0]['chat_id'],101)
    def test_offline_demo_demonstrates_source_resolution_without_writes(self):
        from unittest.mock import patch
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('no network')):output=run_decision_demo()
        self.assertIn('искусственные данные',output)
        self.assertIn('Технические сбои: 1',output)
        self.assertIn('После изменения источника: консультаций 0',output)
