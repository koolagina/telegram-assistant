"""Access policy tests: synthetic IDs only, no services or real accounts."""
from dataclasses import replace
import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from assistant_access import (
    AccessPolicy, Binding, Context, Enrollment, Lecture, Student, Teacher,
    TeachingGrant, SubstitutionGrant, PolicyError,
)

NOW = dt.datetime(2026, 10, 28, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=5)))
START, END = NOW - dt.timedelta(hours=1), NOW + dt.timedelta(hours=1)
READS = frozenset({'schedule.read', 'student.report', 'progress.self', 'personal.read'})
TEACHER_ACTIONS = frozenset({'schedule.read', 'student.report', 'lecture.open', 'lecture.code.read'})


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.teachers = (Teacher('teacher-a'), Teacher('teacher-b'))
        self.students = (Student('student-a'), Student('student-b'))
        self.bindings = (
            Binding('telegram', '001', 'teacher', 'teacher-a', TEACHER_ACTIONS | {'personal.read'}, confirmed=True),
            Binding('telegram', '002', 'teacher', 'teacher-b', TEACHER_ACTIONS, confirmed=True),
            Binding('telegram', '003', 'student', 'student-a', frozenset({'progress.self'}), confirmed=True),
            Binding('telegram', '004', 'student', 'student-b', frozenset({'progress.self'}), confirmed=True),
            Binding('chatgpt', 'oauth-sub-a', 'teacher', 'teacher-a', TEACHER_ACTIONS | {'personal.read'}, confirmed=True),
            Binding('email', 'verified-recipient', 'teacher', 'teacher-a', frozenset({'student.report'}), confirmed=True),
        )
        self.enrollments = (
            Enrollment('enrollment-a', 'student-a', 'discipline-a', 'group-a', START, END),
            Enrollment('enrollment-b', 'student-b', 'discipline-b', 'group-b', START, END),
        )
        self.grants = (TeachingGrant('grant-a', 'teacher-a', 'discipline-a', 'group-a', START, END),
                       TeachingGrant('grant-b', 'teacher-b', 'discipline-b', 'group-b', START, END))
        self.lectures = (
            Lecture('lecture-a', 'teacher-a', 'discipline-a', ('group-a',), START, END, verified=True),
            Lecture('lecture-b', 'teacher-b', 'discipline-b', ('group-b',), START, END, verified=True),
        )
        self.substitutions = ()

    def policy(self, **changes):
        data = dict(teachers=self.teachers, students=self.students, bindings=self.bindings,
                    enrollments=self.enrollments, teaching_grants=self.grants,
                    lectures=self.lectures, substitutions=self.substitutions)
        data.update(changes)
        return AccessPolicy(**data)

    def context(self, subject='001', **changes):
        return replace(Context('telegram', subject, authenticated=True, private=True), **changes)

    def allowed(self, action, target, *, subject='001', policy=None, context=None, now=NOW):
        return (policy or self.policy()).authorize(context or self.context(subject), action, target, now=now).allowed

    def test_both_teachers_read_only_own_schedule(self):
        self.assertTrue(self.allowed('schedule.read', 'teacher-a'))
        self.assertTrue(self.allowed('schedule.read', 'teacher-b', subject='002'))
        self.assertFalse(self.allowed('schedule.read', 'teacher-b'))
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', subject='002'))

    def test_student_progress_is_self_only(self):
        self.assertTrue(self.allowed('progress.self', 'student-a', subject='003'))
        self.assertFalse(self.allowed('progress.self', 'student-b', subject='003'))
        self.assertFalse(self.allowed('student.report', 'enrollment-b', subject='003'))

    def test_teacher_reports_require_exact_group_and_discipline(self):
        self.assertTrue(self.allowed('student.report', 'enrollment-a'))
        self.assertFalse(self.allowed('student.report', 'enrollment-b'))
        self.assertTrue(self.allowed('student.report', 'enrollment-b', subject='002'))
        wrong = replace(self.enrollments[0], discipline_id='discipline-b')
        self.assertFalse(self.allowed('student.report', wrong.id, policy=self.policy(enrollments=(wrong,))))

    def test_explicit_shared_group_grant(self):
        grant = TeachingGrant('grant-shared', 'teacher-b', 'discipline-a', 'group-a', START, END)
        self.assertTrue(self.allowed('student.report', 'enrollment-a', subject='002',
                                    policy=self.policy(teaching_grants=self.grants + (grant,))))

    def test_second_teacher_has_no_owner_or_personal_data_access(self):
        self.assertTrue(self.allowed('personal.read', 'teacher-a'))
        for action, target in [('personal.read', 'teacher-a'), ('personal.read', 'teacher-b'),
                               ('owner.approve', 'teacher-b'), ('journal.write', 'enrollment-b'),
                               ('mail.send', 'enrollment-b')]:
            self.assertFalse(self.allowed(action, target, subject='002'))

    def test_unverified_unknown_and_unauthenticated_fail_closed(self):
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', subject='unknown'))
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', context=self.context(authenticated=False)))
        pending = replace(self.bindings[0], confirmed=False)
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', policy=self.policy(bindings=(pending,))))

    def test_private_chat_and_callback_sender_must_match(self):
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', context=self.context(private=False)))
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', context=self.context(sender='002')))
        self.assertTrue(self.allowed('schedule.read', 'teacher-a', context=self.context(sender='001')))

    def test_binding_revoked_next_check_denies_same_old_context(self):
        old = self.context()
        self.assertTrue(self.allowed('schedule.read', 'teacher-a', context=old))
        revoked = replace(self.bindings[0], active=False)
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', context=old,
                                     policy=self.policy(bindings=(revoked,))))

    def test_inactive_teacher_or_student_cannot_use_confirmed_binding(self):
        self.assertFalse(self.allowed('schedule.read', 'teacher-a',
                                     policy=self.policy(teachers=(Teacher('teacher-a', active=False), self.teachers[1]))))
        inactive = (Student('student-a', active=False), self.students[1])
        self.assertFalse(self.allowed('progress.self', 'student-a', subject='003', policy=self.policy(students=inactive)))
        self.assertFalse(self.allowed('student.report', 'enrollment-a', policy=self.policy(students=inactive)))

    def test_transfer_uses_current_enrollment_not_old_group(self):
        old = replace(self.enrollments[0], valid_until=NOW)
        new = Enrollment('enrollment-new', 'student-a', 'discipline-a', 'group-new', NOW, END)
        policy = self.policy(enrollments=(old, new, self.enrollments[1]))
        self.assertFalse(self.allowed('student.report', 'enrollment-a', policy=policy))
        self.assertFalse(self.allowed('student.report', 'enrollment-new', policy=policy))
        self.assertTrue(self.allowed('progress.self', 'student-a', subject='003', policy=policy))

    def test_expired_grant_and_no_active_enrollment(self):
        expired = replace(self.grants[0], valid_until=NOW)
        self.assertFalse(self.allowed('student.report', 'enrollment-a', policy=self.policy(teaching_grants=(expired,))))
        self.assertFalse(self.allowed('progress.self', 'student-a', subject='003',
                                     policy=self.policy(enrollments=())))

    def test_ids_are_exact_strings_with_leading_zeroes(self):
        self.assertTrue(self.allowed('schedule.read', 'teacher-a', subject='001'))
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', subject='1'))

    def test_duplicate_bindings_and_ids_are_configuration_errors(self):
        for data in [dict(bindings=self.bindings + (self.bindings[0],)),
                     dict(students=self.students + (self.students[0],)),
                     dict(bindings=(replace(self.bindings[0], role='student', entity_id='student-a'), self.bindings[0]))]:
            with self.assertRaises(PolicyError):
                self.policy(**data)

    def test_missing_referenced_identity_and_unknown_role_are_rejected(self):
        for binding in [replace(self.bindings[0], entity_id='missing'),
                        replace(self.bindings[0], role='owner')]:
            with self.assertRaises(PolicyError):
                self.policy(bindings=(binding,))

    def test_context_cannot_supply_role_or_grant(self):
        with self.assertRaises(TypeError):
            Context('telegram', '003', authenticated=True, private=True, role='teacher')
        self.assertFalse(self.allowed('unknown.action', 'student-a'))

    def test_chatgpt_scopes_only_narrow_server_grants(self):
        ctx = Context('chatgpt', 'oauth-sub-a', authenticated=True, scopes=frozenset({'student.report'}))
        self.assertTrue(self.allowed('student.report', 'enrollment-a', context=ctx))
        self.assertFalse(self.allowed('student.report', 'enrollment-b', context=ctx))
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', context=ctx))
        self.assertFalse(self.allowed('lecture.open', 'lecture-a', context=replace(ctx, scopes=TEACHER_ACTIONS)))
        self.assertFalse(self.allowed('personal.read', 'teacher-a', context=replace(ctx, scopes=READS)))

    def test_chatgpt_without_scopes_and_email_without_confirmation_denied(self):
        ctx = Context('chatgpt', 'oauth-sub-a', authenticated=True)
        self.assertFalse(self.allowed('student.report', 'enrollment-a', context=ctx))
        email = Context('email', 'verified-recipient', authenticated=True)
        self.assertTrue(self.allowed('student.report', 'enrollment-a', context=email))
        b = replace(self.bindings[-1], confirmed=False)
        self.assertFalse(self.allowed('student.report', 'enrollment-a', context=email,
                                     policy=self.policy(bindings=(b,))))
        self.assertFalse(self.allowed('mail.send', 'enrollment-a', context=email))

    def test_own_current_lecture_open_and_code_read(self):
        self.assertTrue(self.allowed('lecture.open', 'lecture-a'))
        self.assertTrue(self.allowed('lecture.code.read', 'lecture-a'))
        self.assertTrue(self.allowed('lecture.open', 'lecture-b', subject='002'))
        self.assertFalse(self.allowed('lecture.open', 'lecture-b'))

    def test_substitution_only_explicit_session_and_direction(self):
        grant = SubstitutionGrant('substitution-a', 'teacher-a', 'lecture-b', START, END)
        policy = self.policy(substitutions=(grant,))
        self.assertTrue(self.allowed('lecture.open', 'lecture-b', policy=policy))
        self.assertTrue(self.allowed('lecture.code.read', 'lecture-b', policy=policy))
        self.assertFalse(self.allowed('lecture.open', 'lecture-a', subject='002', policy=policy))
        self.assertFalse(self.allowed('student.report', 'enrollment-b', policy=policy))
        self.assertFalse(self.allowed('personal.read', 'teacher-b', policy=policy))

    def test_substitution_revoked_or_expired_blocks_repeated_code_read(self):
        for grant in [SubstitutionGrant('sub', 'teacher-a', 'lecture-b', START, NOW),
                      SubstitutionGrant('sub', 'teacher-a', 'lecture-b', START, END, active=False)]:
            for action in ['lecture.open', 'lecture.code.read']:
                self.assertFalse(self.allowed(action, 'lecture-b', policy=self.policy(substitutions=(grant,))))

    def test_exam_practice_cancelled_unverified_lecture_denied_even_when_owned(self):
        for change in [dict(kind='зач'), dict(kind='exam'), dict(kind='practice'),
                       dict(kind='unknown'), dict(status='cancelled'), dict(verified=False)]:
            lecture = replace(self.lectures[0], **change)
            self.assertFalse(self.allowed('lecture.open', 'lecture-a', policy=self.policy(lectures=(lecture,))))

    def test_window_must_fit_real_lecture_and_clock_is_timezone_aware(self):
        self.assertFalse(self.allowed('lecture.open', 'lecture-a', now=START-dt.timedelta(microseconds=1)))
        self.assertTrue(self.allowed('lecture.open', 'lecture-a', now=END-dt.timedelta(seconds=90)))
        self.assertFalse(self.allowed('lecture.open', 'lecture-a', now=END-dt.timedelta(seconds=89)))
        self.assertFalse(self.allowed('lecture.code.read', 'lecture-a', now=END))
        self.assertFalse(self.allowed('lecture.open', 'lecture-a', now=NOW.replace(tzinfo=None)))
        self.assertTrue(self.allowed('lecture.open', 'lecture-a', now=NOW.astimezone(dt.timezone.utc)))

    def test_invalid_dates_unknown_fields_and_missing_lecture_groups_fail_closed(self):
        with self.assertRaises(PolicyError):
            self.policy(enrollments=(replace(self.enrollments[0], valid_until=START),))
        lecture = replace(self.lectures[0], group_ids=())
        self.assertFalse(self.allowed('lecture.open', 'lecture-a', policy=self.policy(lectures=(lecture,))))
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', context=self.context(channel='unknown')))

    def test_decision_denial_does_not_disclose_target_existence(self):
        policy = self.policy()
        a = policy.authorize(self.context('003'), 'student.report', 'enrollment-b', now=NOW)
        b = policy.authorize(self.context('003'), 'student.report', 'not-found', now=NOW)
        self.assertEqual(a, b)
        self.assertNotIn('enrollment-b', repr(a))

    def test_new_bindings_and_lectures_are_unconfirmed_by_default(self):
        pending = Binding('telegram', 'pending', 'teacher', 'teacher-a', TEACHER_ACTIONS)
        self.assertFalse(self.allowed('schedule.read', 'teacher-a', subject='pending',
                                     policy=self.policy(bindings=(pending,))))
        lecture = Lecture('new', 'teacher-a', 'discipline-a', ('group-a',), START, END)
        self.assertFalse(self.allowed('lecture.open', 'new', policy=self.policy(lectures=(lecture,))))

    def test_ambiguous_overlapping_enrollments_are_configuration_errors(self):
        other = replace(self.enrollments[0], id='duplicate', group_id='group-other')
        with self.assertRaises(PolicyError):
            self.policy(enrollments=self.enrollments + (other,))
        # Different disciplines are legitimate, not an identity conflict.
        other = replace(other, discipline_id='discipline-other')
        self.assertTrue(self.allowed('progress.self', 'student-a', subject='003',
                                    policy=self.policy(enrollments=self.enrollments + (other,))))

    def test_substitution_must_cover_full_90_second_opening(self):
        short = SubstitutionGrant('short', 'teacher-a', 'lecture-b', START, NOW+dt.timedelta(seconds=89))
        self.assertFalse(self.allowed('lecture.open', 'lecture-b', policy=self.policy(substitutions=(short,))))
        self.assertTrue(self.allowed('lecture.code.read', 'lecture-b', policy=self.policy(substitutions=(short,))))

    def test_malformed_request_parameters_deny_without_type_errors(self):
        for value in [None, 1, [], {}]:
            self.assertFalse(self.allowed(value, 'teacher-a'))
            self.assertFalse(self.allowed('schedule.read', value))
            self.assertFalse(self.allowed('schedule.read', 'teacher-a', context=self.context(channel=value)))

    def test_snapshot_and_permissions_are_immutable(self):
        from dataclasses import FrozenInstanceError
        policy = self.policy()
        with self.assertRaises(TypeError):
            policy.bindings[('telegram', '003')] = self.bindings[0]
        with self.assertRaises(FrozenInstanceError):
            self.bindings[2].role = 'teacher'
        with self.assertRaises(FrozenInstanceError):
            policy.teachers = {}

    def test_registry_cannot_import_mutable_permissions_or_unknown_id_types(self):
        for binding in [replace(self.bindings[0], capabilities=set(TEACHER_ACTIONS)),
                        replace(self.bindings[0], entity_id=[]),
                        replace(self.bindings[0], channel=[])]:
            with self.assertRaises(PolicyError):
                self.policy(bindings=(binding,))


if __name__ == '__main__':
    unittest.main()
