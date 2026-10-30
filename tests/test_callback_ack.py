"""Synthetic callback acknowledgement; real private SQLite, fake API only."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from callback_ack import CallbackAckLedger,CallbackAckError

class AckTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'ack.db'
        self.ledger=CallbackAckLedger(self.path,namespace='fixture',bot_id=9001);self.addCleanup(self.ledger.db.close);self.calls=[]
    def ack(self,method,payload):
        self.assertFalse(self.ledger.db.in_transaction);self.calls.append((method,payload));return {'ok':True,'result':True}
    def attempt(self,send=None,**kw):return self.ledger.attempt(1,'fixture-query',acknowledge=send or self.ack,enabled=True,**kw)
    def test_confirmed_is_not_message_delivery(self):
        out=self.attempt();self.assertEqual(out['status'],'api_confirmed');self.assertNotIn('delivered',out)
        self.assertEqual(self.calls,[('answerCallbackQuery',{'callback_query_id':'fixture-query'})])
    def test_disabled_by_default(self):
        with self.assertRaises(CallbackAckError):self.ledger.attempt(1,'fixture-query',acknowledge=self.ack)
        self.assertEqual(self.calls,[])
    def test_duplicate_and_restart_do_not_repeat_api(self):
        self.attempt();self.attempt()
        with CallbackAckLedger(self.path,namespace='fixture',bot_id=9001) as ledger:
            self.assertEqual(ledger.attempt(1,'fixture-query',acknowledge=self.ack,enabled=True)['status'],'api_confirmed')
        self.assertEqual(len(self.calls),1)
    def test_unknown_is_not_retried(self):
        def lost(method,payload):self.ack(method,payload);raise TimeoutError()
        self.assertEqual(self.attempt(lost)['status'],'unknown');self.attempt();self.assertEqual(len(self.calls),1)
    def test_rejection_is_recorded_without_retry(self):
        def reject(method,payload):self.calls.append(1);return {'ok':False,'error_code':400}
        self.assertEqual(self.attempt(reject)['status'],'api_rejected');self.attempt();self.assertEqual(len(self.calls),1)
    def test_non_boolean_result_is_unknown(self):
        self.assertEqual(self.attempt(lambda *args:{'ok':True,'result':1})['status'],'unknown')
    def test_same_update_different_query_is_conflict(self):
        self.attempt()
        with self.assertRaises(CallbackAckError):self.ledger.attempt(1,'different',acknowledge=self.ack,enabled=True)
        self.assertEqual(len(self.calls),1)
    def test_parallel_observes_claim_without_api(self):
        nested=[]
        def concurrent(method,payload):nested.append(self.attempt());return self.ack(method,payload)
        self.attempt(concurrent);self.assertEqual(nested[0]['status'],'inflight_or_unknown');self.assertEqual(len(self.calls),1)
    def test_namespace_mismatch(self):
        with self.assertRaises(CallbackAckError):CallbackAckLedger(self.path,namespace='other',bot_id=9001)
    def test_no_raw_query_in_database(self):
        self.attempt()
        self.assertNotIn('fixture-query',str(self.ledger.db.execute('SELECT * FROM callback_attempts').fetchall()))
    def test_invalid_query_does_not_call_api(self):
        for query in ('','x'*201,'with space',True):
            with self.assertRaises(CallbackAckError):self.ledger.attempt(1,query,acknowledge=self.ack,enabled=True)
        self.assertEqual(self.calls,[])
    def test_accepted_ack_then_storage_loss_cannot_repeat(self):
        def closed(method,payload):
            self.ack(method,payload);self.ledger.db.close();return {'ok':True,'result':True}
        with self.assertRaises(CallbackAckError):self.attempt(closed)
        with CallbackAckLedger(self.path,namespace='fixture',bot_id=9001) as ledger:
            self.assertEqual(ledger.attempt(1,'fixture-query',acknowledge=self.ack,enabled=True)['status'],'inflight_or_unknown')
        self.assertEqual(len(self.calls),1)
    def test_same_query_with_different_update_is_conflict(self):
        self.attempt()
        with self.assertRaises(CallbackAckError):self.ledger.attempt(2,'fixture-query',acknowledge=self.ack,enabled=True)
        self.assertEqual(len(self.calls),1)
