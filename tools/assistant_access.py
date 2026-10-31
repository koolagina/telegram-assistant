"""Local academic authorization model; no network, credentials or role assignment.

TRUST BOUNDARY: all records come from the server's confirmed identity registry.
Context must be constructed by a trusted, authenticated transport adapter, never
deserialized from Telegram text, OAuth request parameters or LLM tool arguments.
This module does not authenticate Telegram/OAuth/email or verify addresses.

Build/use the current registry snapshot on every request (including cached report
and code retrieval). No decision is a reusable credential or permission to send,
write grades, deploy, or reveal raw workbook data. Persistence/adapters are future
work; no production account is connected by these synthetic models.
"""
from dataclasses import dataclass, field
import datetime as dt
from types import MappingProxyType

ACTIONS = frozenset({'schedule.read', 'student.report', 'progress.self',
                     'personal.read', 'lecture.open', 'lecture.code.read', 'attendance.register'})
API_READS = frozenset({'schedule.read', 'student.report', 'progress.self'})
CHANNELS = frozenset({'telegram', 'chatgpt', 'email'})


class PolicyError(ValueError):
    """Configuration errors do not include identities or resource values."""


@dataclass(frozen=True)
class Teacher:
    id: str
    active: bool = True


@dataclass(frozen=True)
class Student:
    id: str
    active: bool = True


@dataclass(frozen=True)
class Binding:
    channel: str
    subject: str = field(repr=False)
    role: str
    entity_id: str
    capabilities: frozenset
    confirmed: bool = False
    active: bool = True


@dataclass(frozen=True)
class Context:
    channel: str
    subject: str = field(repr=False)
    authenticated: bool = False
    private: bool = False
    sender: str | None = field(default=None, repr=False)
    scopes: frozenset = frozenset()


@dataclass(frozen=True)
class Enrollment:
    id: str
    student_id: str
    discipline_id: str
    group_id: str
    valid_from: dt.datetime
    valid_until: dt.datetime
    active: bool = True


@dataclass(frozen=True)
class TeachingGrant:
    id: str
    teacher_id: str
    discipline_id: str
    group_id: str
    valid_from: dt.datetime
    valid_until: dt.datetime
    active: bool = True


@dataclass(frozen=True)
class AcademicReadGrant:
    """Explicit project-wide academic reading, not owner/write permission."""
    id: str
    teacher_id: str
    valid_from: dt.datetime
    valid_until: dt.datetime
    active: bool = True


@dataclass(frozen=True)
class Lecture:
    id: str
    teacher_id: str
    discipline_id: str
    group_ids: tuple
    starts_at: dt.datetime
    ends_at: dt.datetime
    kind: str = 'lecture'
    status: str = 'confirmed'
    verified: bool = False


@dataclass(frozen=True)
class SubstitutionGrant:
    id: str
    delegate_id: str
    lecture_id: str
    valid_from: dt.datetime
    valid_until: dt.datetime
    active: bool = True


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


DENIED = Decision(False, 'permission_denied')
ALLOWED = Decision(True, 'allowed')


def identifier(value):
    return (isinstance(value, str) and 0 < len(value) <= 200
            and not any(c.isspace() or ord(c) < 32 for c in value))


def aware(value):
    return isinstance(value, dt.datetime) and value.tzinfo is not None and value.utcoffset() is not None


def interval(start, end):
    if not aware(start) or not aware(end) or end <= start:
        raise PolicyError('Invalid validity interval')


def live(record, now):
    return record.active is True and record.valid_from <= now < record.valid_until


def index(records, cls):
    result = {}
    for record in records:
        if type(record) is not cls or not identifier(record.id) or record.id in result:
            raise PolicyError('Invalid or duplicate registry identity')
        if hasattr(record, 'active') and type(record.active) is not bool:
            raise PolicyError('Invalid activation flag')
        result[record.id] = record
    return MappingProxyType(result)


@dataclass(frozen=True, init=False)
class AccessPolicy:
    teachers: object = field(repr=False)
    students: object = field(repr=False)
    bindings: object = field(repr=False)
    enrollments: object = field(repr=False)
    teaching_grants: object = field(repr=False)
    academic_read_grants: object = field(repr=False)
    lectures: object = field(repr=False)
    substitutions: object = field(repr=False)

    def __init__(self, *, teachers=(), students=(), bindings=(), enrollments=(),
                 teaching_grants=(), lectures=(), substitutions=(), academic_read_grants=()):
        for name, values, cls in [('teachers', teachers, Teacher), ('students', students, Student),
                                  ('enrollments', enrollments, Enrollment),
                                  ('teaching_grants', teaching_grants, TeachingGrant),
                                  ('academic_read_grants', academic_read_grants, AcademicReadGrant),
                                  ('lectures', lectures, Lecture),
                                  ('substitutions', substitutions, SubstitutionGrant)]:
            object.__setattr__(self, name, index(values, cls))
        by_subject = {}
        for binding in bindings:
            if (type(binding) is not Binding or not isinstance(binding.channel, str) or binding.channel not in CHANNELS
                    or not identifier(binding.subject) or not identifier(binding.entity_id)
                    or binding.role not in ('teacher', 'student')
                    or type(binding.capabilities) is not frozenset
                    or not binding.capabilities <= ACTIONS
                    or type(binding.confirmed) is not bool or type(binding.active) is not bool):
                raise PolicyError('Invalid channel binding')
            entity = self.teachers if binding.role == 'teacher' else self.students
            if binding.entity_id not in entity:
                raise PolicyError('Channel binding has no registry identity')
            key = (binding.channel, binding.subject)
            if key in by_subject:
                raise PolicyError('Ambiguous account binding')
            by_subject[key] = binding
        object.__setattr__(self, 'bindings', MappingProxyType(by_subject))
        enrollment_ranges = {}
        for enrollment in self.enrollments.values():
            interval(enrollment.valid_from, enrollment.valid_until)
            if not identifier(enrollment.student_id) or enrollment.student_id not in self.students or not identifier(enrollment.discipline_id) or not identifier(enrollment.group_id):
                raise PolicyError('Invalid enrollment relationship')
            if enrollment.active:
                enrollment_ranges.setdefault((enrollment.student_id, enrollment.discipline_id), []).append(enrollment)
        for records in enrollment_ranges.values():
            ordered = sorted(records, key=lambda record: record.valid_from)
            if any(b.valid_from < a.valid_until for a, b in zip(ordered, ordered[1:])):
                raise PolicyError('Ambiguous overlapping enrollment')
        for grant in self.teaching_grants.values():
            interval(grant.valid_from, grant.valid_until)
            if not identifier(grant.teacher_id) or grant.teacher_id not in self.teachers or not identifier(grant.discipline_id) or not identifier(grant.group_id):
                raise PolicyError('Invalid teaching grant relationship')
        for grant in self.academic_read_grants.values():
            interval(grant.valid_from, grant.valid_until)
            if not identifier(grant.teacher_id) or grant.teacher_id not in self.teachers:
                raise PolicyError('Invalid academic read grant relationship')
        for lecture in self.lectures.values():
            interval(lecture.starts_at, lecture.ends_at)
            if (not identifier(lecture.teacher_id) or lecture.teacher_id not in self.teachers or not identifier(lecture.discipline_id)
                    or type(lecture.group_ids) is not tuple or any(not identifier(g) for g in lecture.group_ids)
                    or len(set(lecture.group_ids)) != len(lecture.group_ids)
                    or type(lecture.verified) is not bool):
                raise PolicyError('Invalid lecture relationship')
        for grant in self.substitutions.values():
            interval(grant.valid_from, grant.valid_until)
            if not identifier(grant.delegate_id) or not identifier(grant.lecture_id) or grant.delegate_id not in self.teachers or grant.lecture_id not in self.lectures:
                raise PolicyError('Invalid substitution relationship')

    def _principal(self, context):
        if (type(context) is not Context or context.authenticated is not True
                or not identifier(context.subject) or not isinstance(context.channel, str) or context.channel not in CHANNELS
                or type(context.scopes) is not frozenset):
            return None
        if context.channel == 'telegram' and (context.private is not True or
                (context.sender is not None and context.sender != context.subject)):
            return None
        binding = self.bindings.get((context.channel, context.subject))
        if binding is None or binding.confirmed is not True or binding.active is not True:
            return None
        entity = (self.teachers if binding.role == 'teacher' else self.students)[binding.entity_id]
        return binding if entity.active is True else None

    def authorize(self, context, action, target_id, *, now):
        """Target is an authoritative registry ID, never a caller-provided record.

        Generic denials are equal for missing and inaccessible resources, so a
        denial is not an oracle for student existence. Recheck on every retrieval.
        """
        if not aware(now) or not isinstance(action, str) or action not in ACTIONS or not identifier(target_id):
            return DENIED
        binding = self._principal(context)
        if binding is None or action not in binding.capabilities:
            return DENIED
        if context.channel == 'chatgpt' and (action not in API_READS or action not in context.scopes):
            return DENIED
        if context.channel == 'email' and action != 'student.report':
            return DENIED  # Authorization to read a report is never permission to send it.
        full_read = binding.role == 'teacher' and any(
            g.teacher_id == binding.entity_id and live(g, now) for g in self.academic_read_grants.values())
        if action == 'schedule.read':
            return ALLOWED if binding.role == 'teacher' and target_id in self.teachers and (binding.entity_id == target_id or full_read) else DENIED
        if action == 'personal.read':
            return ALLOWED if binding.role == 'teacher' and binding.entity_id == target_id else DENIED
        if action in ('progress.self','attendance.register'):
            if action=='attendance.register' and context.channel!='telegram':return DENIED
            if binding.role != 'student' or binding.entity_id != target_id:
                return DENIED
            return ALLOWED if any(e.student_id == target_id and live(e, now) for e in self.enrollments.values()) else DENIED
        if binding.role != 'teacher':
            return DENIED
        if action == 'student.report':
            enrollment = self.enrollments.get(target_id)
            if enrollment is None:
                return DENIED
            if full_read:
                return ALLOWED  # Includes known historical enrollments for academic review.
            if not live(enrollment, now) or not self.students[enrollment.student_id].active:
                return DENIED
            return ALLOWED if any(g.teacher_id == binding.entity_id and live(g, now)
                                  and g.group_id == enrollment.group_id
                                  and g.discipline_id == enrollment.discipline_id
                                  for g in self.teaching_grants.values()) else DENIED
        # Lecture mutations and code retrieval exist only in private Telegram.
        lecture = self.lectures.get(target_id)
        if (context.channel != 'telegram' or lecture is None or lecture.kind != 'lecture'
                or lecture.status != 'confirmed' or lecture.verified is not True
                or not lecture.group_ids or not self.teachers[lecture.teacher_id].active
                or not lecture.starts_at <= now < lecture.ends_at):
            return DENIED
        if action == 'lecture.open' and now + dt.timedelta(seconds=90) > lecture.ends_at:
            return DENIED
        owns = lecture.teacher_id == binding.entity_id
        delegated = any(g.delegate_id == binding.entity_id and g.lecture_id == lecture.id and live(g, now)
                        and (action != 'lecture.open' or now + dt.timedelta(seconds=90) <= g.valid_until)
                        for g in self.substitutions.values())
        return ALLOWED if owns or delegated else DENIED
