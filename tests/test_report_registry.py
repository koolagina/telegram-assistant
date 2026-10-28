"""Private durable ownership links, no identities or remote writes."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_registry import ReportRegistry,RegistryError
from report_access import ReportLink

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'links.sqlite3'
        self.link=ReportLink('report-a','check-a','enrollment-a','student-a','discipline-a','group-a')
    def store(self,namespace='test-project'):return ReportRegistry(self.path,namespace=namespace)
    def result(self,key):return {'status':'done','version':'v1','result':{'check_id':key,'material_version':'v1','status':'needs_teacher_review','credit_written':False}}
    def test_restart_and_idempotent_register(self):
        with self.store() as store:
            store.register(self.link,load_result=self.result);store.register(self.link,load_result=self.result)
        with self.store() as store:self.assertEqual(store.snapshot(),(self.link,))
    def test_owner_cannot_be_replaced_by_retry(self):
        with self.store() as store:
            store.register(self.link,load_result=self.result)
            with self.assertRaises(RegistryError):store.register(replace(self.link,student_id='other'),load_result=self.result)
            self.assertEqual(store.snapshot(),(self.link,))
    def test_same_check_cannot_be_published_under_second_owner(self):
        with self.store() as store:
            store.register(self.link,load_result=self.result)
            with self.assertRaises(RegistryError):store.register(replace(self.link,id='another',student_id='other'),load_result=self.result)
    def test_pending_corrupt_or_failed_result_does_not_publish(self):
        with self.store() as store:
            for result in [{'status':'pending'}, {'status':'done','version':'wrong','result':self.result('check-a')['result']}]:
                with self.assertRaises(RegistryError):store.register(self.link,load_result=lambda _:result)
            self.assertEqual(store.snapshot(),())
    def test_namespace_and_private_permissions(self):
        with self.store():pass
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        with self.assertRaises(RegistryError):self.store('another-project')
    def test_concurrent_connections_cannot_duplicate_or_retarget(self):
        with self.store() as first,self.store() as second:
            first.register(self.link,load_result=self.result);second.register(self.link,load_result=self.result)
            with self.assertRaises(RegistryError):second.register(replace(self.link,check_id='new'),load_result=self.result)
            self.assertEqual(len(first.snapshot()),1)
    def test_loader_exception_is_sanitized(self):
        def failed(_):raise RuntimeError('private file path')
        with self.store() as store:
            with self.assertRaises(RegistryError) as caught:store.register(self.link,load_result=failed)
            self.assertNotIn('private',str(caught.exception))
    def test_foreign_db_and_symlink_rejected(self):
        import sqlite3
        with sqlite3.connect(self.path) as db:db.execute('CREATE TABLE foreign_table(x)')
        self.path.chmod(0o600)
        with self.assertRaises(RegistryError):self.store()
        alias=Path(self.tmp.name)/'alias.sqlite3';alias.symlink_to(self.path)
        with self.assertRaises(RegistryError):ReportRegistry(alias,namespace='test-project')
