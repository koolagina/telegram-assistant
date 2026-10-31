"""Synthetic lecture storage isolation and authenticated self-attendance."""
from dataclasses import replace
import datetime as dt
from pathlib import Path
import sqlite3
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assistant_access import Binding,Context
from lecture_windows import WindowStore,WindowError,LectureWindows
import test_lecture_windows as fixtures

class LectureHardeningTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.WindowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def bind_student(self,capabilities=frozenset({'attendance.register'})):
        self.f.bindings=self.f.bindings+(Binding('telegram','103','student','student-a',capabilities,confirmed=True),)
        return Context('telegram','103',authenticated=True,private=True)
    def test_foreign_database_rejected_without_adding_tables(self):
        db=sqlite3.connect(self.f.path);db.execute('CREATE TABLE foreign_data(value TEXT)');db.commit();db.close()
        with self.assertRaises(WindowError):self.f.store()
        db=sqlite3.connect(self.f.path)
        self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),[('foreign_data',)]);db.close()
    def test_partial_lecture_database_is_not_silently_completed(self):
        db=sqlite3.connect(self.f.path);db.execute('CREATE TABLE meta(key TEXT PRIMARY KEY,value BLOB)');db.commit();db.close()
        with self.assertRaises(WindowError):self.f.store()
    def test_missing_metadata_not_initialized_as_new_project(self):
        with self.f.store() as store:store.db.execute('DELETE FROM meta')
        with self.assertRaises(WindowError):self.f.store()
    def test_malformed_last_clock_is_safe_configuration_error(self):
        with self.f.store() as store:store.db.execute("UPDATE meta SET value='private malformed clock' WHERE key='last_clock'")
        with self.assertRaisesRegex(WindowError,'^Lecture state unavailable; review required$'):self.f.store()
    def test_student_explicit_capability_and_dedup(self):
        context=self.bind_student()
        with self.f.store() as store:
            service=self.f.service(store);window=service.open(self.f.b,'lecture-a','request')
            first=service.register_authenticated(context,'lecture-a',window.code)
            again=service.register_authenticated(context,'lecture-a',window.code)
            self.assertTrue(first.accepted);self.assertTrue(first.created);self.assertFalse(again.created)
            self.assertEqual(store.attendance_count(),1);self.assertEqual(first.journal_status,'not_synced')
    def test_progress_read_capability_does_not_grant_attendance_write(self):
        context=self.bind_student(frozenset({'progress.self'}))
        with self.f.store() as store:
            service=self.f.service(store);window=service.open(self.f.b,'lecture-a','request')
            self.assertFalse(service.register_authenticated(context,'lecture-a',window.code).accepted)
            self.assertEqual(store.attendance_count(),0)
    def test_group_chat_and_unverified_context_cannot_register(self):
        context=self.bind_student()
        with self.f.store() as store:
            service=self.f.service(store);window=service.open(self.f.b,'lecture-a','request')
            for ctx in (replace(context,private=False),replace(context,authenticated=False),replace(context,sender='104')):
                self.assertFalse(service.register_authenticated(ctx,'lecture-a',window.code).accepted)
            self.assertEqual(store.attendance_count(),0)
    def test_binding_revocation_between_resolution_and_register(self):
        context=self.bind_student();count=[]
        def policy():
            count.append(1)
            if len(count)>1:self.f.bindings=tuple(replace(b,active=False) if b.subject=='103' else b for b in self.f.bindings)
            return self.f.policy()
        with self.f.store() as store:
            window=self.f.service(store).open(self.f.b,'lecture-a','request')
            service=LectureWindows(store,policy_provider=policy,clock=lambda:self.f.now)
            self.assertFalse(service.register_authenticated(context,'lecture-a',window.code).accepted)
            self.assertEqual(store.attendance_count(),0)
    def test_binding_reassigned_during_resolution_cannot_mark_old_student(self):
        context=self.bind_student();count=[]
        def policy():
            count.append(1)
            if len(count)>1:self.f.bindings=tuple(replace(b,entity_id='student-b') if b.subject=='103' else b for b in self.f.bindings)
            return self.f.policy()
        with self.f.store() as store:
            window=self.f.service(store).open(self.f.b,'lecture-a','request')
            service=LectureWindows(store,policy_provider=policy,clock=lambda:self.f.now)
            self.assertFalse(service.register_authenticated(context,'lecture-a',window.code).accepted)
            self.assertEqual(store.attendance_count(),0)
    def test_expiry_exact_boundary_and_code_replay(self):
        context=self.bind_student()
        with self.f.store() as store:
            service=self.f.service(store);window=service.open(self.f.a,'lecture-a','request')
            self.f.now=window.expires_at
            self.assertFalse(service.register_authenticated(context,'lecture-a',window.code).accepted)
            with self.assertRaises(WindowError):service.open(self.f.a,'lecture-a','request')
            self.assertEqual(store.attendance_count(),0)
    def test_revoked_substitution_invalidates_window(self):
        context=self.bind_student()
        with self.f.store() as store:
            service=self.f.service(store);window=service.open(self.f.a,'lecture-a','request');self.f.grants=()
            self.assertFalse(service.register_authenticated(context,'lecture-a',window.code).accepted)
    def test_teacher_identity_cannot_register_as_student(self):
        self.bind_student()
        with self.f.store() as store:
            service=self.f.service(store);window=service.open(self.f.b,'lecture-a','request')
            self.assertFalse(service.register_authenticated(self.f.b,'lecture-a',window.code).accepted)
