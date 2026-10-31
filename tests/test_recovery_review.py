"""Read-only recovery planning from synthetic actual local stores."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recovery_review import review_recovery,RecoveryReviewError
from callback_ack import CallbackAckLedger
import test_academic_worker as fixtures

class RecoveryReviewTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.AcademicWorkerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.ack=CallbackAckLedger(self.f.root/'ack.db',namespace='synthetic-academic',bot_id=9001);self.addCleanup(self.ack.db.close)
    def review(self,**kw):return review_recovery(self.f.inbox,self.f.ledger,callback_ledger=self.ack,**kw)
    def receipt(self,state='api_confirmed',uid=1):
        self.f.ledger.db.execute('INSERT INTO dispatch_attempts VALUES(?,?,?,?,?,?)',(uid,'fixture-attempt',state,'fixture-hash',5 if state=='api_confirmed' else None,403 if state=='api_rejected' else None))
    def test_empty_review_is_not_live_ready(self):
        out=self.review();self.assertTrue(out['complete']);self.assertEqual(out['items'],[])
        self.assertFalse(out['ready_for_apply']);self.assertEqual(out['writes'],0);self.assertEqual(out['messages_sent'],0)
    def test_pending_unattempted_does_not_authorize_send(self):
        self.f.store();item=self.review()['items'][0]
        self.assertIn('route_with_fresh_policy',item['actions']);self.assertNotIn('send',item['actions'])
    def test_confirmed_pending_can_be_reconciled_without_resend(self):
        self.f.store();self.receipt();item=self.review()['items'][0]
        self.assertIn('verify_receipt_then_mark_only',item['actions']);self.assertNotIn('route_with_fresh_policy',item['actions'])
    def test_unknown_never_suggests_retry(self):
        self.f.store();self.receipt('unknown');item=self.review()['items'][0]
        self.assertIn('manual_review_no_resend',item['actions'])
    def test_sending_is_not_assumed_orphan(self):
        self.f.store();self.receipt('sending')
        self.assertIn('verify_active_process_no_takeover',self.review()['items'][0]['actions'])
    def test_receipt_without_inbox_requires_review_not_recreation(self):
        self.receipt()
        self.assertIn('verify_retention_or_missing_inbox',self.review()['items'][0]['actions'])
    def test_conflicting_blocked_confirmed_is_detected(self):
        self.f.store();self.f.inbox.mark(1,status='blocked');self.receipt()
        self.assertIn('queue_receipt_conflict',self.review()['items'][0]['issues'])
    def test_ack_alone_does_not_imply_business_response(self):
        self.f.store();self.ack.db.execute("INSERT INTO callback_attempts VALUES(1,'fixture-query-hash','api_confirmed',NULL)")
        item=self.review()['items'][0]
        self.assertIn('ack_without_business_receipt',item['issues']);self.assertIn('route_with_fresh_policy',item['actions'])
    def test_ack_unknown_visible_after_handled_message(self):
        self.f.store();self.f.inbox.mark(1,status='handled');self.receipt()
        self.ack.db.execute("INSERT INTO callback_attempts VALUES(1,'fixture-query-hash','unknown',NULL)")
        self.assertIn('callback_manual_review_no_retry',self.review()['items'][0]['actions'])
    def test_no_mutation_payload_queries_or_factories(self):
        self.f.store();statements=[]
        for db in (self.f.inbox.db,self.f.ledger.db,self.ack.db):db.set_trace_callback(statements.append)
        before=(self.f.inbox.db.total_changes,self.f.ledger.db.total_changes,self.ack.db.total_changes)
        self.review();self.review()
        self.assertEqual(before,(self.f.inbox.db.total_changes,self.f.ledger.db.total_changes,self.ack.db.total_changes))
        self.assertTrue(all(s.upper().startswith('SELECT ') and 'PAYLOAD' not in s.upper() for s in statements))
        self.assertEqual(self.f.calls,[])
    def test_output_contains_no_raw_ids_hashes_or_paths(self):
        import json
        self.f.store();self.receipt();text=json.dumps(self.review())
        for value in ('fixture-attempt','fixture-hash',str(self.f.root),'enrollment-a','"update_id"','"message_id"'):
            self.assertNotIn(value,text)
    def test_plan_fingerprint_changes_when_receipt_changes(self):
        self.f.store();a=self.review();self.receipt();b=self.review()
        self.assertNotEqual(a['snapshot_hash'],b['snapshot_hash'])
    def test_stable_review_on_unchanged_metadata(self):
        self.f.store();self.assertEqual(self.review(),self.review())
    def test_limit_explicitly_marks_incomplete(self):
        for i in range(3):self.receipt(uid=i)
        out=self.review(limit=2);self.assertFalse(out['complete']);self.assertEqual(len(out['items']),2)
    def test_unknown_phase_and_foreign_namespace_fail_closed(self):
        self.receipt('surprise')
        with self.assertRaises(RecoveryReviewError):self.review()
    def test_invalid_limit_fails_before_read(self):
        for limit in (True,0,-1,1001):
            with self.assertRaises(RecoveryReviewError):self.review(limit=limit)
    def test_invalid_confirmed_metadata_never_suggests_mark(self):
        self.f.store();self.receipt()
        self.f.ledger.db.execute('UPDATE dispatch_attempts SET message_id=NULL')
        item=self.review()['items'][0]
        self.assertIn('receipt_metadata_invalid',item['issues'])
        self.assertNotIn('verify_receipt_then_mark_only',item['actions'])
    def test_completed_consistent_message_needs_no_action(self):
        self.f.store();self.receipt();self.f.inbox.mark(1,status='handled')
        out=self.review();self.assertEqual(out['needs_attention'],0)
        self.assertEqual(out['items'][0]['actions'],[])
    def test_foreign_namespace_fails_closed(self):
        self.f.ledger.db.execute("UPDATE dispatch_meta SET value='foreign' WHERE key='namespace'")
        with self.assertRaises(RecoveryReviewError):self.review()
    def test_actual_mark_failure_plan_and_worker_recovery_without_resend(self):
        from unittest.mock import patch
        self.f.store()
        with patch.object(self.f.inbox,'mark',side_effect=RuntimeError()):self.f.worker().step(dispatch_enabled=True)
        self.assertIn('verify_receipt_then_mark_only',self.review()['items'][0]['actions'])
        self.assertEqual(len(self.f.calls),1)
        self.f.worker().step(dispatch_enabled=True)
        self.assertEqual(self.review()['needs_attention'],0);self.assertEqual(len(self.f.calls),1)
    def test_reference_stable_but_snapshot_changes_on_phase(self):
        self.f.store();before=self.review();self.receipt('unknown');after=self.review()
        self.assertEqual(before['items'][0]['reference'],after['items'][0]['reference'])
        self.assertNotEqual(before['snapshot_hash'],after['snapshot_hash'])
    def test_worker_refuses_corrupt_confirmed_receipt_instead_of_marking_handled(self):
        self.f.store();self.receipt();self.f.ledger.db.execute('UPDATE dispatch_attempts SET message_id=NULL')
        outcome=self.f.worker().step(dispatch_enabled=True)[0]
        self.assertEqual(outcome['queue_status'],'needs_recovery')
        self.assertEqual(len(self.f.inbox.pending()),1);self.assertEqual(self.f.calls,[])
    def test_dispatch_rejected_without_error_code_is_invalid(self):
        from report_dispatch import DispatchError
        self.receipt('api_rejected');self.f.ledger.db.execute('UPDATE dispatch_attempts SET error_code=NULL')
        with self.assertRaises(DispatchError):self.f.ledger.result(1)
    def test_callback_rejected_without_error_code_is_invalid(self):
        from callback_ack import CallbackAckError
        self.ack.db.execute("INSERT INTO callback_attempts VALUES(1,'fixture','api_rejected',NULL)")
        with self.assertRaises(CallbackAckError):self.ack.result(1)
