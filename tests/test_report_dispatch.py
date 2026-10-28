"""Mock-only dispatch: durable outcomes are not delivery receipts."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_dispatch import DispatchLedger,DispatchError
from telegram_report_adapter import TelegramPreparation
from report_requests import PreparedReply,ReplyButton

BOT=9001
class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'dispatch.sqlite3';self.calls=[]
        self.prep=TelegramPreparation(1,103,PreparedReply('prepared','Synthetic report',buttons=((ReplyButton('Открыть','progress:p:1'),),)))
    def ledger(self,namespace='synthetic-bot'):return DispatchLedger(self.path,namespace=namespace,bot_id=BOT)
    def send(self,method,payload):
        self.calls.append((method,payload))
        return {'ok':True,'result':{'message_id':41,'chat':{'id':103,'type':'private'},'from':{'id':BOT,'is_bot':True}}}
    def test_disabled_by_default_does_not_prepare_or_send(self):
        with self.ledger() as ledger:
            with self.assertRaises(DispatchError):ledger.attempt(1,prepare_fresh=lambda:self.fail('must not prepare'),send=self.send)
            self.assertEqual(self.calls,[])
    def test_api_confirmed_is_not_actual_delivery_and_restart_dedupes(self):
        with self.ledger() as ledger:
            result=ledger.attempt(1,prepare_fresh=lambda:self.prep,send=self.send,dispatch_enabled=True)
            self.assertEqual(result['status'],'api_confirmed');self.assertIsNone(result['delivered'])
        with self.ledger() as ledger:ledger.attempt(1,prepare_fresh=lambda:self.fail('already attempted'),send=self.send,dispatch_enabled=True)
        self.assertEqual(len(self.calls),1)
    def test_payload_has_plaintext_keyboard_and_no_preview(self):
        with self.ledger() as ledger:ledger.attempt(1,prepare_fresh=lambda:self.prep,send=self.send,dispatch_enabled=True)
        method,payload=self.calls[0];self.assertEqual(method,'sendMessage')
        self.assertNotIn('parse_mode',payload);self.assertTrue(payload['link_preview_options']['is_disabled'])
        self.assertEqual(payload['reply_markup']['inline_keyboard'][0][0]['callback_data'],'progress:p:1')
    def test_timeout_never_causes_blind_resend(self):
        def uncertain(*args):self.calls.append(args);raise TimeoutError('private URL')
        with self.ledger() as ledger:
            first=ledger.attempt(1,prepare_fresh=lambda:self.prep,send=uncertain,dispatch_enabled=True)
            self.assertEqual(first['status'],'unknown')
            ledger.attempt(1,prepare_fresh=lambda:self.prep,send=uncertain,dispatch_enabled=True)
        self.assertEqual(len(self.calls),1)
    def test_accepted_then_result_write_fails_no_resend(self):
        with self.ledger() as ledger:
            with patch.object(ledger,'_finalize',side_effect=RuntimeError('simulated storage failure')):
                with self.assertRaises(DispatchError):ledger.attempt(1,prepare_fresh=lambda:self.prep,send=self.send,dispatch_enabled=True)
        with self.ledger() as ledger:
            result=ledger.attempt(1,prepare_fresh=lambda:self.prep,send=self.send,dispatch_enabled=True)
            self.assertEqual(result['status'],'inflight_or_unknown')
        self.assertEqual(len(self.calls),1)
    def test_api_rejection_recorded_without_delivery_or_auto_retry(self):
        with self.ledger() as ledger:
            result=ledger.attempt(1,prepare_fresh=lambda:self.prep,send=lambda *_:{'ok':False,'error_code':429},dispatch_enabled=True)
            self.assertEqual(result['status'],'api_rejected');self.assertIsNone(result['delivered'])
    def test_stale_cached_permission_not_used(self):
        blocked=replace(self.prep,reply=PreparedReply('unavailable','No access'))
        with self.ledger() as ledger:
            result=ledger.attempt(1,prepare_fresh=lambda:blocked,send=self.send,dispatch_enabled=True)
            self.assertEqual(result['status'],'cancelled')
        self.assertEqual(self.calls,[])
    def test_concurrent_worker_cannot_send_same_update(self):
        with self.ledger() as first,self.ledger() as second:
            def send_once(method,payload):
                other=second.attempt(1,prepare_fresh=lambda:self.prep,send=self.send,dispatch_enabled=True)
                self.assertEqual(other['status'],'inflight_or_unknown')
                return self.send(method,payload)
            first.attempt(1,prepare_fresh=lambda:self.prep,send=send_once,dispatch_enabled=True)
        self.assertEqual(len(self.calls),1)
    def test_wrong_destination_or_bot_response_is_unknown(self):
        with self.ledger() as ledger:
            result=ledger.attempt(1,prepare_fresh=lambda:self.prep,send=lambda *_:{'ok':True,'result':{'message_id':1,'chat':{'id':104,'type':'private'},'from':{'id':BOT,'is_bot':True}}},dispatch_enabled=True)
            self.assertEqual(result['status'],'unknown')
    def test_mismatched_update_or_overlong_keyboard_never_calls_sender(self):
        for preparation in [replace(self.prep,update_id=2),replace(self.prep,reply=replace(self.prep.reply,buttons=((ReplyButton('Open','x'*65),),)))]:
            with self.ledger() as ledger:
                with self.assertRaises(DispatchError):ledger.attempt(1,prepare_fresh=lambda:preparation,send=self.send,dispatch_enabled=True)
        self.assertEqual(self.calls,[])
    def test_namespace_bot_binding_and_private_file(self):
        with self.ledger():pass
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        with self.assertRaises(DispatchError):self.ledger('another')
        with self.assertRaises(DispatchError):DispatchLedger(self.path,namespace='synthetic-bot',bot_id=9002)

    def test_boolean_preparation_update_id_is_not_integer_identity(self):
        with self.ledger() as ledger:
            with self.assertRaises(DispatchError):ledger.attempt(1,prepare_fresh=lambda:replace(self.prep,update_id=True),send=self.send,dispatch_enabled=True)
        self.assertEqual(self.calls,[])
    def test_process_interruption_leaves_claim_and_blocks_resend(self):
        def interrupted(*args):self.calls.append(args);raise KeyboardInterrupt('simulated process stop')
        with self.ledger() as ledger:
            with self.assertRaises(KeyboardInterrupt):ledger.attempt(1,prepare_fresh=lambda:self.prep,send=interrupted,dispatch_enabled=True)
        with self.ledger() as ledger:self.assertEqual(ledger.attempt(1,prepare_fresh=lambda:self.prep,send=self.send,dispatch_enabled=True)['status'],'inflight_or_unknown')
        self.assertEqual(len(self.calls),1)
