"""Durable trusted registry snapshots, never self-service role grants."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from policy_store import PolicyStore,PolicyStoreError
from assistant_access import AccessPolicy
import test_assistant_access as fixtures

class PolicyStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'policy.sqlite3'
        self.f=fixtures.PolicyTests();self.f.setUp()
    def store(self,namespace='synthetic'):return PolicyStore(self.path,namespace=namespace)
    def test_empty_state_has_no_automatic_admin_or_confirmed_binding(self):
        with self.store() as store:
            revision,policy=store.load();self.assertEqual(revision,0);self.assertEqual(len(policy.bindings),0)
    def test_all_records_roundtrip_and_restart(self):
        policy=self.f.policy()
        with self.store() as store:self.assertEqual(store.save(policy,expected_revision=0),1)
        with self.store() as store:
            revision,loaded=store.load();self.assertEqual(revision,1)
            self.assertEqual(loaded,policy)
            self.assertTrue(loaded.authorize(self.f.context(),'student.report','enrollment-a',now=fixtures.NOW).allowed)
    def test_revocation_survives_restart_and_stale_writer_fails(self):
        with self.store() as first,self.store() as second:
            first.save(self.f.policy(),expected_revision=0)
            old_revision,old_policy=second.load()
            revoked=self.f.policy(bindings=tuple(replace(b,active=False) for b in self.f.bindings))
            first.save(revoked,expected_revision=1)
            with self.assertRaises(PolicyStoreError):second.save(old_policy,expected_revision=old_revision)
        with self.store() as store:
            revision,policy=store.load();self.assertEqual(revision,2)
            self.assertFalse(policy.authorize(self.f.context(),'student.report','enrollment-a',now=fixtures.NOW).allowed)
    def test_missing_revision_never_overwrites(self):
        with self.store() as store:
            for revision in [True,-1,None]:
                with self.assertRaises(PolicyStoreError):store.save(self.f.policy(),expected_revision=revision)
    def test_unconfirmed_binding_stays_unconfirmed(self):
        with self.store() as store:
            store.save(self.f.policy(bindings=tuple(replace(b,confirmed=False) for b in self.f.bindings)),expected_revision=0)
            self.assertFalse(store.load()[1].authorize(self.f.context(),'student.report','enrollment-a',now=fixtures.NOW).allowed)
    def test_namespace_and_permissions(self):
        with self.store():pass
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        with self.assertRaises(PolicyStoreError):self.store('other')
    def test_corrupt_snapshot_does_not_fall_back_to_older_grants(self):
        with self.store() as store:
            store.save(self.f.policy(),expected_revision=0)
            store.db.execute("UPDATE policy_revisions SET payload='{}' WHERE revision=1")
            with self.assertRaises(PolicyStoreError):store.load()
    def test_full_academic_grants_and_substitutions_preserved(self):
        from assistant_access import AcademicReadGrant,SubstitutionGrant
        policy=self.f.policy(academic_read_grants=(AcademicReadGrant('full','teacher-a',fixtures.START,fixtures.END),),substitutions=(SubstitutionGrant('sub','teacher-a','lecture-b',fixtures.START,fixtures.END),))
        with self.store() as store:
            store.save(policy,expected_revision=0)
            self.assertEqual(store.load()[1],policy)
