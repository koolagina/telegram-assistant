"""Local synthetic lecture windows: no Telegram, mail, real journal or accounts."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from assistant_access import AccessPolicy, Binding, Context, Enrollment, Lecture, Student, Teacher, SubstitutionGrant
from lecture_windows import WindowStore, LectureWindows, WindowError

NOW = dt.datetime(2026, 10, 28, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=5)))
KEY = bytes(range(32))  # Test-only encryption key, not an environment credential.


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'windows.sqlite3'
        self.now = NOW
        self.lecture = Lecture('lecture-a', 'teacher-b', 'discipline-a', ('group-a',),
                               NOW-dt.timedelta(minutes=10), NOW+dt.timedelta(hours=1), verified=True)
        caps = frozenset({'lecture.open', 'lecture.code.read'})
        self.bindings = (Binding('telegram', '001', 'teacher', 'teacher-a', caps, confirmed=True),
                         Binding('telegram', '002', 'teacher', 'teacher-b', caps, confirmed=True))
        self.grants = (SubstitutionGrant('substitution', 'teacher-a', 'lecture-a',
                                         NOW-dt.timedelta(minutes=10), NOW+dt.timedelta(hours=1)),)
        self.a = Context('telegram', '001', authenticated=True, private=True)
        self.b = Context('telegram', '002', authenticated=True, private=True)

    def policy(self):
        return AccessPolicy(teachers=(Teacher('teacher-a'), Teacher('teacher-b')),
                            students=(Student('student-a'), Student('student-b')),
                            bindings=self.bindings,
                            enrollments=(Enrollment('enrollment-a', 'student-a', 'discipline-a', 'group-a',
                                                    NOW-dt.timedelta(days=1), NOW+dt.timedelta(days=1)),
                                         Enrollment('enrollment-b', 'student-b', 'discipline-a', 'other-group',
                                                    NOW-dt.timedelta(days=1), NOW+dt.timedelta(days=1))),
                            lectures=(self.lecture,), substitutions=self.grants)

    def store(self, key=KEY):
        return WindowStore(self.path, key=key, namespace='synthetic-project')

    def service(self, store):
        return LectureWindows(store, policy_provider=self.policy, clock=lambda: self.now)

    def test_code_shape_and_90_seconds_from_server_open(self):
        with self.store() as store:
            window = self.service(store).open(self.a, 'lecture-a', 'request-1')
            self.assertRegex(window.code, r'^[0-9]{4}$')
            self.assertEqual(window.expires_at-window.opened_at, dt.timedelta(seconds=90))
            self.assertEqual(window.opened_at, NOW)
            self.assertNotIn(window.code, repr(window))

    def test_retry_does_not_extend_or_regenerate(self):
        with self.store() as store:
            service = self.service(store)
            first = service.open(self.a, 'lecture-a', 'request-1')
            self.now += dt.timedelta(seconds=40)
            again = service.open(self.a, 'lecture-a', 'request-1')
            newer_button = service.open(self.a, 'lecture-a', 'request-2')
            self.assertEqual((first.id, first.code, first.expires_at), (again.id, again.code, again.expires_at))
            self.assertEqual(first.id, newer_button.id)
            self.assertEqual(first.expires_at, newer_button.expires_at)

    def test_restart_recovers_accepted_open_after_lost_delivery(self):
        with self.store() as store:
            first = self.service(store).open(self.a, 'lecture-a', 'request-1')
        self.now += dt.timedelta(seconds=20)
        with self.store() as store:
            again = self.service(store).open(self.a, 'lecture-a', 'request-1')
            self.assertEqual(first, again)

    def test_two_teachers_share_one_active_window_and_audit_operator(self):
        with self.store() as store:
            service = self.service(store)
            first = service.open(self.a, 'lecture-a', 'request-a')
            second = service.open(self.b, 'lecture-a', 'request-b')
            self.assertEqual(first.id, second.id)
            audits = store.audit_records()
            self.assertEqual(audits[0]['operator_id'], 'teacher-a')
            self.assertEqual(audits[0]['assigned_teacher_id'], 'teacher-b')
            self.assertEqual(audits[0]['substitution_id'], 'substitution')
            self.assertFalse(any('code' in item for item in audits))

    def test_concurrent_connections_cannot_open_two_windows(self):
        with self.store():
            pass
        def open_window(item):
            with self.store() as store:
                return self.service(store).open(item[0], 'lecture-a', item[1])
        with ThreadPoolExecutor(2) as executor:
            windows = list(executor.map(open_window, [(self.a, 'request-a'), (self.b, 'request-b')]))
        self.assertEqual(windows[0].id, windows[1].id)
        self.assertEqual(windows[0].code, windows[1].code)

    def test_old_button_cannot_open_new_window_after_expiry(self):
        with self.store() as store:
            service = self.service(store)
            service.open(self.a, 'lecture-a', 'old')
            self.now += dt.timedelta(seconds=90)
            with self.assertRaises(WindowError):
                service.open(self.a, 'lecture-a', 'old')

    def test_new_explicit_request_opens_new_code_without_reusing_old_code(self):
        with self.store() as store, patch('lecture_windows.secrets.randbelow', side_effect=[1234, 1234, 5678]):
            service = self.service(store)
            first = service.open(self.a, 'lecture-a', 'first')
            self.now += dt.timedelta(seconds=90)
            second = service.open(self.a, 'lecture-a', 'second')
            self.assertNotEqual(first.id, second.id)
            self.assertNotEqual(first.code, second.code)
            self.assertFalse(service.register('lecture-a', 'student-a', first.code).accepted)

    def test_code_boundary_and_registration_is_not_a_gradebook_write(self):
        with self.store() as store:
            service = self.service(store)
            window = service.open(self.a, 'lecture-a', 'request')
            self.now += dt.timedelta(seconds=89, microseconds=999999)
            result = service.register('lecture-a', 'student-a', window.code)
            self.assertTrue(result.accepted)
            self.assertTrue(result.created)
            self.assertEqual(result.journal_status, 'not_synced')
            self.now = NOW+dt.timedelta(seconds=90)
            self.assertFalse(service.register('lecture-a', 'student-a', window.code).accepted)

    def test_multiple_windows_and_retries_make_one_attendance_fact(self):
        with self.store() as store:
            service = self.service(store)
            first = service.open(self.a, 'lecture-a', 'first')
            self.assertTrue(service.register('lecture-a', 'student-a', first.code).created)
            self.assertFalse(service.register('lecture-a', 'student-a', first.code).created)
            self.now += dt.timedelta(seconds=91)
            second = service.open(self.b, 'lecture-a', 'second')
            again = service.register('lecture-a', 'student-a', second.code)
            self.assertTrue(again.accepted)
            self.assertFalse(again.created)
            self.assertEqual(store.attendance_count(), 1)

    def test_revocation_is_checked_again_before_reveal(self):
        with self.store() as store:
            service = self.service(store)
            service.open(self.a, 'lecture-a', 'request')
            self.grants = ()
            with self.assertRaises(WindowError):
                service.show(self.a, 'lecture-a')
            with self.assertRaises(WindowError):
                service.open(self.a, 'lecture-a', 'request')

    def test_clock_rollback_is_not_treated_as_extended_window(self):
        with self.store() as store:
            service = self.service(store)
            service.open(self.a, 'lecture-a', 'request')
            self.now -= dt.timedelta(seconds=1)
            with self.assertRaises(WindowError):
                service.show(self.a, 'lecture-a')

    def test_wrong_key_namespace_and_public_state_directory_fail_closed(self):
        with self.store():
            pass
        with self.assertRaises(WindowError):
            with self.store(key=b'x'*32):
                pass
        with self.assertRaises(WindowError):
            with WindowStore(self.path, key=KEY, namespace='another-project'):
                pass
        public = Path(self.directory.name) / 'public'
        public.mkdir(mode=0o755)
        public.chmod(0o755)  # Do not let the runner's private umask mask this case.
        with self.assertRaises(WindowError):
            WindowStore(public/'state.sqlite3', key=KEY, namespace='synthetic-project')

    def test_encrypted_code_in_state_and_not_in_audit(self):
        with self.store() as store, patch('lecture_windows.secrets.randbelow', return_value=1234):
            window = self.service(store).open(self.a, 'lecture-a', 'request')
            payload = store.db.execute('SELECT encrypted_code FROM windows').fetchone()[0]
            self.assertNotEqual(payload, window.code.encode())
            for event in store.audit_records():
                self.assertEqual(set(event), {'event', 'window_id', 'lecture_id', 'operator_id',
                                             'assigned_teacher_id', 'substitution_id', 'at'})
                self.assertFalse(any(value == window.code for value in event.values()))

    def test_source_change_requires_review_not_silent_rebinding(self):
        with self.store() as store:
            service = self.service(store)
            window = service.open(self.a, 'lecture-a', 'request')
            self.lecture = replace(self.lecture, group_ids=('changed-group',))
            with self.assertRaises(WindowError):
                service.show(self.a, 'lecture-a')
            self.assertFalse(service.register('lecture-a', 'student-a', window.code).accepted)

    def test_exam_cancellation_and_other_group_do_not_accept_codes(self):
        with self.store() as store:
            service = self.service(store)
            window = service.open(self.a, 'lecture-a', 'request')
            self.assertFalse(service.register('lecture-a', 'student-b', window.code).accepted)
            self.assertFalse(service.register('lecture-a', 'unknown', window.code).accepted)
            for kind in ['зач', 'practice', 'unknown']:
                self.lecture = replace(self.lecture, kind=kind)
                with self.assertRaises(WindowError):
                    service.open(self.b, 'lecture-a', 'new')
                self.assertFalse(service.register('lecture-a', 'student-a', window.code).accepted)

    def test_failed_attempt_rate_limit_persists_after_restart(self):
        with self.store() as store:
            service = self.service(store)
            window = service.open(self.a, 'lecture-a', 'request')
            wrong = '0000' if window.code != '0000' else '0001'
            for _ in range(5):
                self.assertFalse(service.register('lecture-a', 'student-a', wrong).accepted)
        with self.store() as store:
            service = self.service(store)
            self.assertFalse(service.register('lecture-a', 'student-a', window.code).accepted)
            self.now += dt.timedelta(seconds=61)
            self.assertTrue(service.register('lecture-a', 'student-a', window.code).accepted)

    def test_show_requires_existing_unexpired_window_and_no_preview_creates_one(self):
        with self.store() as store:
            service = self.service(store)
            with self.assertRaises(WindowError):
                service.show(self.a, 'lecture-a')
            self.assertEqual(store.db.execute('SELECT count(*) FROM windows').fetchone()[0], 0)
            service.open(self.a, 'lecture-a', 'request')
            self.now += dt.timedelta(seconds=90)
            with self.assertRaises(WindowError):
                service.show(self.a, 'lecture-a')

    def test_namespace_key_and_request_must_be_valid(self):
        with self.assertRaises(WindowError):
            WindowStore(self.path, key=b'short', namespace='synthetic-project')
        with self.store() as store:
            with self.assertRaises(WindowError):
                self.service(store).open(self.a, 'lecture-a', '')

    def test_opening_operator_revoke_blocks_registration_not_just_reveal(self):
        with self.store() as store:
            service = self.service(store)
            window = service.open(self.a, 'lecture-a', 'request')
            self.bindings = (replace(self.bindings[0], active=False), self.bindings[1])
            self.assertFalse(service.register('lecture-a', 'student-a', window.code).accepted)

    def test_revoked_substitution_invalidates_its_active_registration(self):
        with self.store() as store:
            service = self.service(store)
            window = service.open(self.a, 'lecture-a', 'request')
            self.grants = ()
            self.assertFalse(service.register('lecture-a', 'student-a', window.code).accepted)

    def test_tampered_expiry_cannot_extend_encrypted_window(self):
        with self.store() as store:
            service = self.service(store)
            window = service.open(self.a, 'lecture-a', 'request')
            store.db.execute('UPDATE windows SET expires=expires+60000000')
            self.now += dt.timedelta(seconds=100)
            with self.assertRaises(WindowError):
                service.show(self.a, 'lecture-a')
            self.assertFalse(service.register('lecture-a', 'student-a', window.code).accepted)

    def test_retry_near_lecture_end_can_recover_existing_window(self):
        self.lecture = replace(self.lecture, ends_at=NOW+dt.timedelta(seconds=90))
        with self.store() as store:
            service = self.service(store)
            first = service.open(self.a, 'lecture-a', 'request')
            self.now += dt.timedelta(seconds=40)
            self.assertEqual(first, service.open(self.a, 'lecture-a', 'request'))


if __name__ == '__main__':
    unittest.main()
