"""Durable report→verified-source adapter→mock send, no real network."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assistant_demo import SyntheticAssistantSession
from telegram_report_adapter import TelegramReportAdapter
from report_dispatch import DispatchLedger

class DispatchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.session=SyntheticAssistantSession(self.root);self.session.__enter__();self.addCleanup(self.session.__exit__,None,None,None)
        self.session.ingest(40);self.calls=[]
        self.update={'update_id':1,'message':{'message_id':1,'date':1793160000,'from':{'id':103,'is_bot':False},'chat':{'id':103,'type':'private'},'text':'/progress'}}
        self.adapter=TelegramReportAdapter(reader_factory=self.session.reader,bot_id=9001,fetch_verified_updates=lambda:{'ok':True,'result':[self.update]})
    def ledger(self):return DispatchLedger(self.root/'dispatch.sqlite3',namespace='synthetic-assistant',bot_id=9001)
    def fresh(self):return self.adapter.prepare_batch()[0]
    def send(self,method,payload):
        self.calls.append((method,payload))
        return {'ok':True,'result':{'message_id':1,'chat':{'id':103,'type':'private'},'from':{'id':9001,'is_bot':True}}}
    def test_full_pipeline_and_restart_do_not_duplicate_mock_send(self):
        with self.ledger() as ledger:self.assertEqual(ledger.attempt(1,prepare_fresh=self.fresh,send=self.send,dispatch_enabled=True)['status'],'api_confirmed')
        self.session.restart_storage()
        with self.ledger() as ledger:self.assertEqual(ledger.attempt(1,prepare_fresh=self.fresh,send=self.send,dispatch_enabled=True)['status'],'api_confirmed')
        self.assertEqual(len(self.calls),1);self.assertEqual(self.calls[0][1]['chat_id'],103)
    def test_revoke_after_preparation_cancels_dispatch(self):
        cached=self.fresh();self.assertEqual(cached.reply.status,'prepared')
        self.session.revoke_student_a()
        with self.ledger() as ledger:self.assertEqual(ledger.attempt(1,prepare_fresh=self.fresh,send=self.send,dispatch_enabled=True)['status'],'cancelled')
        self.assertEqual(self.calls,[])
    def test_accepted_then_timeout_is_unknown_and_not_replayed(self):
        def timeout(method,payload):self.send(method,payload);raise TimeoutError('accepted but reply lost')
        with self.ledger() as ledger:self.assertEqual(ledger.attempt(1,prepare_fresh=self.fresh,send=timeout,dispatch_enabled=True)['status'],'unknown')
        with self.ledger() as ledger:self.assertEqual(ledger.attempt(1,prepare_fresh=self.fresh,send=self.send,dispatch_enabled=True)['status'],'unknown')
        self.assertEqual(len(self.calls),1)

    def http_pipeline(self,send_response):
        import json
        from telegram_http import TelegramHTTP
        class Response:
            status=200
            def __init__(self,data):self.data=json.dumps(data).encode()
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return self.data[:n]
        queue=[{'ok':True,'result':{'id':9001,'is_bot':True}},{'ok':True,'result':[self.update]},send_response]
        calls=[]
        def opened(request,timeout):
            calls.append(request.get_method())
            item=queue.pop(0)
            if isinstance(item,Exception):raise item
            return Response(item)
        client=TelegramHTTP('1:fake',bot_id=9001,network_enabled=True,writes_enabled=True,opener=opened)
        client.verify_bot();verified_batch=client.fetch_updates(offset=0)
        adapter=TelegramReportAdapter(reader_factory=self.session.reader,bot_id=9001,fetch_verified_updates=lambda:verified_batch)
        return client,adapter,calls
    def test_mock_http_verified_bot_to_dispatch_confirmation(self):
        response={'ok':True,'result':{'message_id':1,'chat':{'id':103,'type':'private'},'from':{'id':9001,'is_bot':True}}}
        client,adapter,calls=self.http_pipeline(response)
        with self.ledger() as ledger:
            result=ledger.attempt(1,prepare_fresh=lambda:adapter.prepare_batch()[0],send=client.send,dispatch_enabled=True)
        self.assertEqual(result['status'],'api_confirmed');self.assertIsNone(result['delivered'])
        self.assertEqual(calls,['POST','POST','POST'])
    def test_mock_http_rejection_is_recorded(self):
        client,adapter,calls=self.http_pipeline({'ok':False,'error_code':429})
        with self.ledger() as ledger:
            result=ledger.attempt(1,prepare_fresh=lambda:adapter.prepare_batch()[0],send=client.send,dispatch_enabled=True)
        self.assertEqual(result['status'],'api_rejected')
    def test_mock_http_timeout_never_triggers_second_request(self):
        client,adapter,calls=self.http_pipeline(TimeoutError('synthetic timeout'))
        with self.ledger() as ledger:
            first=ledger.attempt(1,prepare_fresh=lambda:adapter.prepare_batch()[0],send=client.send,dispatch_enabled=True)
            second=ledger.attempt(1,prepare_fresh=lambda:adapter.prepare_batch()[0],send=client.send,dispatch_enabled=True)
        self.assertEqual(first['status'],'unknown');self.assertEqual(second['status'],'unknown')
        self.assertEqual(len(calls),3)

    def test_durable_inbox_to_report_dispatch_before_next_ack(self):
        from telegram_inbox import TelegramInbox,poll_once
        offsets=[]
        update=self.update
        class Client:
            bot_id=9001
            def fetch_updates(self,*,offset):
                offsets.append(offset)
                return {'ok':True,'result':[update] if offset==0 else []}
        client=Client()
        with TelegramInbox(self.root/'inbox.sqlite3',namespace='synthetic-assistant',bot_id=9001) as inbox:
            poll_once(client,inbox)
            row=inbox.pending()[0]
            adapter=TelegramReportAdapter(reader_factory=self.session.reader,bot_id=9001,fetch_verified_updates=lambda:{'ok':True,'result':[row['update']]})
            with self.ledger() as ledger:
                result=ledger.attempt(row['update_id'],prepare_fresh=lambda:adapter.prepare_batch()[0],send=self.send,dispatch_enabled=True)
            self.assertEqual(result['status'],'api_confirmed')
            inbox.mark(row['update_id'],status='handled')
        with TelegramInbox(self.root/'inbox.sqlite3',namespace='synthetic-assistant',bot_id=9001) as inbox:
            self.assertEqual(inbox.pending(),());poll_once(client,inbox)
        self.assertEqual(offsets,[0,2]);self.assertEqual(len(self.calls),1)
    def test_unknown_dispatch_survives_pending_queue_recovery_without_resend(self):
        from telegram_inbox import TelegramInbox
        with TelegramInbox(self.root/'inbox.sqlite3',namespace='synthetic-assistant',bot_id=9001) as inbox:
            inbox.store_batch({'ok':True,'result':[self.update]},expected_offset=0)
            def uncertain(method,payload):self.send(method,payload);raise TimeoutError('mock loss')
            with self.ledger() as ledger:
                self.assertEqual(ledger.attempt(1,prepare_fresh=self.fresh,send=uncertain,dispatch_enabled=True)['status'],'unknown')
        with TelegramInbox(self.root/'inbox.sqlite3',namespace='synthetic-assistant',bot_id=9001) as inbox,self.ledger() as ledger:
            self.assertEqual(len(inbox.pending()),1)
            self.assertEqual(ledger.attempt(1,prepare_fresh=self.fresh,send=self.send,dispatch_enabled=True)['status'],'unknown')
            inbox.mark(1,status='blocked')
        self.assertEqual(len(self.calls),1)
