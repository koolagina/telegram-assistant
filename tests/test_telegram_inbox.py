"""Atomic store-before-ack protocol with mock polling only."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from telegram_inbox import TelegramInbox,InboxError,poll_once

def batch(*ids):return {'ok':True,'result':[{'update_id':n,'message':{'text':'Synthetic'}} for n in ids]}
class InboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'inbox.sqlite3'
    def inbox(self):return TelegramInbox(self.path,namespace='synthetic',bot_id=9001)
    def test_atomic_payload_and_cursor_survive_restart_before_processing(self):
        with self.inbox() as inbox:inbox.store_batch(batch(5,6),expected_offset=0)
        with self.inbox() as inbox:
            self.assertEqual(inbox.offset(),7);self.assertEqual([row['update_id'] for row in inbox.pending()],[5,6])
    def test_store_failure_cannot_advance_ack_cursor(self):
        with self.inbox() as inbox:
            with patch.object(inbox,'_insert',side_effect=RuntimeError('synthetic disk failure')):
                with self.assertRaises(InboxError):inbox.store_batch(batch(5,6),expected_offset=0)
            self.assertEqual(inbox.offset(),0);self.assertEqual(inbox.pending(),())
    def test_next_poll_acknowledges_only_already_stored_batch(self):
        class Client:
            bot_id=9001
            def __init__(self):self.offsets=[]
            def fetch_updates(self,*,offset):self.offsets.append(offset);return batch(5,6) if offset==0 else batch()
        client=Client()
        with self.inbox() as inbox:poll_once(client,inbox);poll_once(client,inbox)
        self.assertEqual(client.offsets,[0,7])
    def test_failure_or_duplicate_ids_never_advance(self):
        with self.inbox() as inbox:
            for response in [{'ok':False,'error_code':429},batch(1,1),batch(True)]:
                with self.assertRaises(InboxError):inbox.store_batch(response,expected_offset=0)
            self.assertEqual(inbox.offset(),0)
    def test_old_concurrent_fetch_cannot_overwrite_new_cursor(self):
        with self.inbox() as first,self.inbox() as second:
            old=second.offset();first.store_batch(batch(5),expected_offset=0)
            with self.assertRaises(InboxError):second.store_batch(batch(5),expected_offset=old)
            self.assertEqual(second.offset(),6)
    def test_unsupported_payload_is_saved_not_lost(self):
        response={'ok':True,'result':[{'update_id':8,'future_update':{'synthetic':True}}]}
        with self.inbox() as inbox:
            inbox.store_batch(response,expected_offset=0)
            self.assertEqual(inbox.pending()[0]['update']['future_update'],{'synthetic':True})
    def test_mark_is_idempotent_and_no_conflicting_overwrite(self):
        with self.inbox() as inbox:
            inbox.store_batch(batch(1),expected_offset=0)
            inbox.mark(1,status='handled');inbox.mark(1,status='handled')
            self.assertEqual(inbox.pending(),())
            with self.assertRaises(InboxError):inbox.mark(1,status='ignored')
    def test_hash_mismatch_stops_private_payload_read(self):
        with self.inbox() as inbox:
            inbox.store_batch(batch(1),expected_offset=0)
            inbox.db.execute("UPDATE inbox_updates SET payload='{}' WHERE update_id=1")
            with self.assertRaises(InboxError):inbox.pending()
    def test_lower_new_update_id_is_not_guessed_as_reset(self):
        with self.inbox() as inbox:
            inbox.store_batch(batch(100),expected_offset=0)
            with self.assertRaises(InboxError):inbox.store_batch(batch(1),expected_offset=101)
            self.assertEqual(inbox.offset(),101)

    def test_client_for_other_bot_cannot_advance_this_inbox(self):
        calls=[]
        class WrongClient:
            bot_id=9002
            def fetch_updates(self,*,offset):calls.append(offset);return batch()
        with self.inbox() as inbox:
            with self.assertRaises(InboxError):poll_once(WrongClient(),inbox)
            self.assertEqual(inbox.offset(),0)
        self.assertEqual(calls,[])
