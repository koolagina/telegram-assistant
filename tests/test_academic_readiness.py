"""Read-only runtime inspection, real temporary SQLite and synthetic policy."""
from pathlib import Path
import sys
import unittest
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from academic_readiness import inspect_academic_runtime,ReadinessError
from academic_menu import AcademicMenu
import test_academic_worker as fixtures

class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.AcademicWorkerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def inspect(self,**kw):
        return inspect_academic_runtime(self.f.worker(),policy=self.f.f.f.j.policy,journal=self.f.f.f.j.reader,overview=self.f.f.f.service,menu=self.f.f.menu,**kw)
    def test_locally_consistent_is_never_live_ready(self):
        out=self.inspect()
        self.assertEqual(out['local_status'],'consistent')
        self.assertFalse(out['ready_for_live']);self.assertFalse(out['live_verified'])
        self.assertEqual(out['writes'],0);self.assertEqual(out['messages_sent'],0)
    def test_no_payload_loading_or_sending(self):
        self.f.store();out=self.inspect()
        self.assertEqual(out['queue']['pending'],1)
        self.assertEqual(self.f.calls,[]);self.assertEqual(self.f.f.f.j.loads,0);self.assertEqual(self.f.f.f.r.loads,[])
    def test_summary_has_no_ids_labels_paths_or_secrets(self):
        import json
        value=json.dumps(self.inspect(),ensure_ascii=False)
        for text in ('enrollment-a','student-a','Студент','Экология',str(self.f.root),'103'):
            self.assertNotIn(text,value)
    def test_receipts_unknown_and_sending_require_review(self):
        self.f.ledger.db.execute("INSERT INTO dispatch_attempts VALUES(1,'a','unknown','',NULL,NULL)")
        self.f.ledger.db.execute("INSERT INTO dispatch_attempts VALUES(2,'b','sending','',NULL,NULL)")
        out=self.inspect();self.assertEqual(out['local_status'],'needs_review')
        self.assertEqual(out['dispatch']['unknown'],1);self.assertEqual(out['dispatch']['sending'],1)
        self.assertIn('dispatch_outcomes_need_review',out['blockers'])
    def test_confirmed_receipt_pending_inbox_is_recoverable_not_send(self):
        self.f.store();self.f.ledger.db.execute("INSERT INTO dispatch_attempts VALUES(1,'a','api_confirmed','',5,NULL)")
        out=self.inspect();self.assertEqual(out['queue']['pending_with_final_receipt'],1)
        self.assertEqual(len(self.f.inbox.pending()),1);self.assertEqual(self.f.calls,[])
    def test_schema_corruption_has_sanitized_failure(self):
        self.f.ledger.db.close()
        with self.assertRaisesRegex(ReadinessError,'^Runtime inspection unavailable$'):self.inspect()
    def test_no_active_or_confirmed_identity_blocks_readiness(self):
        policy=self.f.f.f.j.f.policy(bindings=())
        out=inspect_academic_runtime(self.f.worker(),policy=policy,journal=self.f.f.f.j.reader,overview=self.f.f.f.service,menu=self.f.f.menu)
        self.assertIn('confirmed_bindings_missing',out['blockers']);self.assertEqual(out['local_status'],'blocked')
    def test_overview_with_other_journal_detected(self):
        from academic_overview import AcademicOverview
        from academic_progress import ProgressReader
        other=ProgressReader([self.f.f.f.j.mapping],policy_provider=lambda:self.f.f.f.j.policy,load_workbook=self.f.f.f.j.load,clock=lambda:fixtures.fixtures.review_fixtures.NOW)
        overview=AcademicOverview(other,self.f.f.f.r.reader)
        out=inspect_academic_runtime(self.f.worker(),policy=self.f.f.f.j.policy,journal=self.f.f.f.j.reader,overview=overview,menu=self.f.f.menu)
        self.assertIn('overview_journal_mismatch',out['blockers'])
    def test_no_state_mutations_during_inspection(self):
        self.f.store()
        before=(self.f.inbox.db.total_changes,self.f.ledger.db.total_changes,self.f.inbox.offset())
        self.inspect();self.inspect()
        self.assertEqual(before,(self.f.inbox.db.total_changes,self.f.ledger.db.total_changes,self.f.inbox.offset()))
    def test_disabled_factories_reported_without_enabling(self):
        out=inspect_academic_runtime(self.f.worker(enabled=False),policy=self.f.f.f.j.policy,journal=self.f.f.f.j.reader,overview=self.f.f.f.service,menu=self.f.f.menu)
        self.assertIn('academic_factories_not_configured',out['blockers'])
    def test_rejected_dispatch_is_review_not_automatic_retry(self):
        self.f.ledger.db.execute("INSERT INTO dispatch_attempts VALUES(1,'a','api_rejected','',NULL,403)")
        self.assertEqual(self.inspect()['dispatch']['api_rejected'],1)
        self.assertEqual(self.f.ledger.result(1)['status'],'api_rejected')
    def test_unrecognized_state_fails_closed(self):
        self.f.inbox.db.execute("INSERT INTO inbox_updates VALUES(1,'private','hash','surprise')")
        with self.assertRaises(ReadinessError):self.inspect()
    def test_only_select_statements_are_issued(self):
        statements=[]
        self.f.inbox.db.set_trace_callback(statements.append);self.f.ledger.db.set_trace_callback(statements.append)
        self.inspect()
        self.assertTrue(statements)
        self.assertTrue(all(s.lstrip().upper().startswith('SELECT ') for s in statements))
        self.assertTrue(all('PAYLOAD' not in s.upper() for s in statements))
    def test_factories_never_invoked(self):
        def fail():raise AssertionError('factory must not run')
        worker=self.f.worker(menu=fail,overview=fail)
        out=inspect_academic_runtime(worker,policy=self.f.f.f.j.policy,journal=self.f.f.f.j.reader,overview=self.f.f.f.service,menu=self.f.f.menu)
        self.assertEqual(out['local_status'],'consistent');self.assertIn('factory_result_wiring',out['unverified'])
    def test_mapping_identity_conflict_is_blocker(self):
        old=self.f.f.f.j.f.enrollments
        policy=self.f.f.f.j.f.policy(enrollments=(replace(old[0],student_id='student-b'),old[1]))
        out=inspect_academic_runtime(self.f.worker(),policy=policy,journal=self.f.f.f.j.reader,overview=self.f.f.f.service,menu=self.f.f.menu)
        self.assertIn('journal_policy_mismatch',out['blockers']);self.assertIn('report_policy_mismatch',out['blockers'])
        self.assertFalse(out['ready_for_live'])
    def test_namespace_metadata_mutation_fails_closed(self):
        self.f.ledger.db.execute("UPDATE dispatch_meta SET value='foreign' WHERE key='namespace'")
        with self.assertRaises(ReadinessError):self.inspect()
    def test_orphan_catalog_entry_reported_without_names(self):
        entry=replace(self.f.f.entry,enrollment_id='unmapped')
        menu=self.f.f.make([entry])
        out=inspect_academic_runtime(self.f.worker(),policy=self.f.f.f.j.policy,journal=self.f.f.f.j.reader,overview=self.f.f.f.service,menu=menu)
        self.assertIn('catalog_mapping_missing',out['blockers'])
        self.assertEqual(out['structure']['catalog_missing_mappings'],1)
    def test_large_pending_receipt_scan_is_explicitly_incomplete(self):
        self.f.inbox.db.executemany("INSERT INTO inbox_updates VALUES(?, 'not-read', 'not-read', 'pending')",((i,) for i in range(10001)))
        out=self.inspect()
        self.assertFalse(out['queue']['pending_receipt_check_complete'])
        self.assertIsNone(out['queue']['pending_with_final_receipt'])
        self.assertIn('pending_receipt_check_incomplete',out['blockers'])
