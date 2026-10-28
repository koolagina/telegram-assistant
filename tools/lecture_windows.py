"""Local lecture window controller, not a Telegram endpoint or gradebook writer.

Inputs come only from trusted transport/identity adapters; registration student_id
must already be resolved against the confirmed registry. The public QR form,
authentication, durable registry, network rate limits and XLSX sync are not here.
The key is supplied by the caller's secure runtime storage, never generated as a
replacement on restart. Test state contains synthetic data only.
"""
import contextlib
from dataclasses import dataclass, field
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from assistant_access import AccessPolicy, aware, identifier, live

UTC = dt.timezone.utc
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
WINDOW_US = 90_000_000


class WindowError(ValueError):
    """Safe error text: no codes, credentials or private identity values."""


def timestamp(value):
    if not aware(value):
        raise WindowError('Timezone-aware server clock required')
    delta = value.astimezone(UTC) - EPOCH
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds


def instant(value):
    return EPOCH + dt.timedelta(microseconds=value)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def source_digest(lecture):
    return hashlib.sha256(encoded([lecture.id, lecture.teacher_id, lecture.discipline_id,
                                   sorted(lecture.group_ids), timestamp(lecture.starts_at),
                                   timestamp(lecture.ends_at), lecture.kind, lecture.status,
                                   lecture.verified])).hexdigest()


@dataclass(frozen=True)
class Window:
    id: str
    lecture_id: str
    opened_at: dt.datetime
    expires_at: dt.datetime
    code: str = field(repr=False)


@dataclass(frozen=True)
class Admission:
    accepted: bool
    created: bool = False
    journal_status: str = 'not_synced'


REJECTED = Admission(False)


class WindowStore:
    def __init__(self, path, *, key, namespace):
        if type(key) is not bytes or len(key) != 32 or not identifier(namespace):
            raise WindowError('Explicit 32-byte key and project namespace required')
        self.path = Path(path).absolute()
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise WindowError('State symlinks forbidden')
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.parent.stat().st_mode & 0o077:
            raise WindowError('State directory must be private (0700)')
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        if self.path.stat().st_mode & 0o077:
            raise WindowError('State file must be private (0600)')
        self.aes = AESGCM(key)
        self.mac_key = hmac.digest(key, b'lecture-verification-v1', 'sha256')
        self.namespace = namespace
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value BLOB)')
                self.db.execute('CREATE TABLE IF NOT EXISTS windows(id TEXT PRIMARY KEY,lecture_id TEXT,opened INTEGER,expires INTEGER,source TEXT,encrypted_code BLOB,verifier TEXT,operator_id TEXT,assigned_teacher_id TEXT,substitution_id TEXT,opening_binding TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY,lecture_id TEXT,window_id TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS audit(number INTEGER PRIMARY KEY,value TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS attendance(lecture_id TEXT,student_id TEXT,enrollment_id TEXT,window_id TEXT,created INTEGER,PRIMARY KEY(lecture_id,student_id))')
                self.db.execute('CREATE TABLE IF NOT EXISTS attempts(lecture_id TEXT,student_id TEXT,bucket INTEGER,failed INTEGER,PRIMARY KEY(lecture_id,student_id,bucket))')
                meta = dict(self.db.execute('SELECT key,value FROM meta'))
                if not meta:
                    check = self.encrypt(b'lecture-state-v1', b'key-check')
                    self.db.executemany('INSERT INTO meta VALUES(?,?)', [('version', '1'), ('namespace', namespace), ('key_check', check), ('last_clock', '0')])
                else:
                    if meta.get('version') != '1' or meta.get('namespace') != namespace:
                        raise WindowError('State project/schema mismatch')
                    if self.decrypt(meta['key_check'], b'key-check') != b'lecture-state-v1':
                        raise WindowError('State key mismatch')
        except Exception:
            self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def encrypt(self, plaintext, aad):
        nonce = secrets.token_bytes(12)
        return nonce + self.aes.encrypt(nonce, plaintext, self.namespace.encode() + b'\0' + aad)

    def decrypt(self, ciphertext, aad):
        try:
            return self.aes.decrypt(ciphertext[:12], ciphertext[12:], self.namespace.encode() + b'\0' + aad)
        except (InvalidTag, ValueError, TypeError):
            raise WindowError('State key/content could not be verified') from None

    def digest(self, value):
        return hmac.new(self.mac_key, encoded(value), hashlib.sha256).hexdigest()

    def clock(self, now):
        value = timestamp(now)
        last = int(self.db.execute("SELECT value FROM meta WHERE key='last_clock'").fetchone()[0])
        if value < last:
            raise WindowError('Server clock moved backwards; review required')
        self.db.execute("UPDATE meta SET value=? WHERE key='last_clock'", (str(value),))
        return value

    def audit(self, value):
        self.db.execute('INSERT INTO audit(value) VALUES(?)', (encoded(value).decode(),))

    def audit_records(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT value FROM audit ORDER BY number')]

    def attendance_count(self):
        return self.db.execute('SELECT count(*) FROM attendance').fetchone()[0]


class LectureWindows:
    def __init__(self, store, *, policy_provider, clock):
        self.store, self.policy_provider, self.clock = store, policy_provider, clock

    def _authorized(self, context, action, lecture_id, now):
        policy = self.policy_provider()  # MUST load the current trusted registry snapshot.
        if not isinstance(policy, AccessPolicy) or not policy.authorize(context, action, lecture_id, now=now).allowed:
            raise WindowError('Lecture operation unavailable')
        return policy, policy.lectures[lecture_id]

    def _active(self, lecture_id, now_us):
        rows = list(self.store.db.execute('SELECT * FROM windows WHERE lecture_id=? AND opened<=? AND expires>?', (lecture_id, now_us, now_us)))
        if len(rows) > 1:
            raise WindowError('Ambiguous active state; review required')
        return rows[0] if rows else None

    def _window(self, row, lecture):
        if row['source'] != source_digest(lecture):
            raise WindowError('Lecture source changed; review required')
        aad = self._aad(row)
        code = self.store.decrypt(row['encrypted_code'], aad).decode('ascii')
        return Window(row['id'], row['lecture_id'], instant(row['opened']), instant(row['expires']), code)

    def _aad(self, row):
        return encoded([row[k] for k in ('id', 'lecture_id', 'opened', 'expires', 'source',
                                         'verifier', 'operator_id', 'assigned_teacher_id',
                                         'substitution_id', 'opening_binding')])

    def _authority(self, row, policy, lecture, now):
        for binding in policy.bindings.values():
            if (binding.channel == 'telegram' and binding.role == 'teacher'
                    and binding.entity_id == row['operator_id'] and binding.active and binding.confirmed
                    and {'lecture.open', 'lecture.code.read'} <= binding.capabilities
                    and policy.teachers[binding.entity_id].active
                    and self.store.digest([binding.channel, binding.subject]) == row['opening_binding']):
                if binding.entity_id == lecture.teacher_id:
                    return True
                return any(g.id == row['substitution_id'] and g.delegate_id == binding.entity_id
                           and g.lecture_id == lecture.id and live(g, now)
                           for g in policy.substitutions.values())
        return False

    def open(self, context, lecture_id, request_id):
        if not identifier(request_id):
            raise WindowError('Stable request identifier required')
        with self.store.transaction():
            now = self.clock()
            policy, lecture = self._authorized(context, 'lecture.code.read', lecture_id, now)
            binding = policy.bindings[(context.channel, context.subject)]
            if 'lecture.open' not in binding.capabilities:
                raise WindowError('Lecture operation unavailable')
            now_us = self.store.clock(now)
            request_key = self.store.digest([context.channel, context.subject, request_id])
            prior = self.store.db.execute('SELECT * FROM requests WHERE key=?', (request_key,)).fetchone()
            if prior:
                row = self.store.db.execute('SELECT * FROM windows WHERE id=?', (prior['window_id'],)).fetchone()
                if prior['lecture_id'] != lecture_id or row is None or not row['opened'] <= now_us < row['expires']:
                    raise WindowError('Request is no longer active; explicit new action required')
                if not self._authority(row, policy, lecture, now):
                    raise WindowError('Opening authority changed; review required')
                return self._window(row, lecture)
            row = self._active(lecture_id, now_us)
            substitution = next((g.id for g in policy.substitutions.values()
                                 if g.delegate_id == binding.entity_id and g.lecture_id == lecture_id
                                 and live(g, now)), None)
            if row is None:
                if not policy.authorize(context, 'lecture.open', lecture_id, now=now).allowed:
                    raise WindowError('Lecture operation unavailable')
                for _ in range(100):
                    code = f'{secrets.randbelow(10000):04d}'
                    verifier = self.store.digest([lecture_id, code])
                    if not self.store.db.execute('SELECT 1 FROM windows WHERE lecture_id=? AND verifier=?', (lecture_id, verifier)).fetchone():
                        break
                else:
                    raise WindowError('Could not allocate a fresh code')
                window_id = secrets.token_hex(16)
                metadata = dict(id=window_id, lecture_id=lecture_id, opened=now_us, expires=now_us+WINDOW_US,
                                source=source_digest(lecture), verifier=verifier, operator_id=binding.entity_id,
                                assigned_teacher_id=lecture.teacher_id, substitution_id=substitution,
                                opening_binding=self.store.digest([context.channel, context.subject]))
                self.store.db.execute('INSERT INTO windows VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                                      (window_id, lecture_id, now_us, now_us+WINDOW_US, source_digest(lecture),
                                       self.store.encrypt(code.encode(), self._aad(metadata)), verifier,
                                       binding.entity_id, lecture.teacher_id, substitution, metadata['opening_binding']))
                row = self.store.db.execute('SELECT * FROM windows WHERE id=?', (window_id,)).fetchone()
                event = 'window_opened'
            else:
                event = 'window_reused'
                if not self._authority(row, policy, lecture, now):
                    raise WindowError('Opening authority changed; review required')
            window = self._window(row, lecture)
            self.store.db.execute('INSERT INTO requests VALUES(?,?,?)', (request_key, lecture_id, row['id']))
            self.store.audit(dict(event=event, window_id=row['id'], lecture_id=lecture_id,
                                  operator_id=binding.entity_id, assigned_teacher_id=lecture.teacher_id,
                                  substitution_id=substitution, at=now_us))
            return window

    def show(self, context, lecture_id):
        with self.store.transaction():
            now = self.clock()
            policy, lecture = self._authorized(context, 'lecture.code.read', lecture_id, now)
            row = self._active(lecture_id, self.store.clock(now))
            if row is None or not self._authority(row, policy, lecture, now):
                raise WindowError('Lecture operation unavailable')
            return self._window(row, lecture)

    def register(self, lecture_id, student_id, code):
        """Only after trusted academic identity resolution, never raw form IDs.

        Records local attendance only, not physical-presence proof or a journal +.
        Public form still needs independent network/device rate limiting.
        """
        with self.store.transaction():
            now = self.clock()
            now_us = self.store.clock(now)
            policy = self.policy_provider()
            if not isinstance(policy, AccessPolicy) or not identifier(lecture_id) or not identifier(student_id):
                return REJECTED
            lecture, student = policy.lectures.get(lecture_id), policy.students.get(student_id)
            if (lecture is None or student is None or not student.active or lecture.kind != 'lecture'
                    or lecture.status != 'confirmed' or not lecture.verified
                    or not lecture.starts_at <= now < lecture.ends_at or not lecture.group_ids
                    or not policy.teachers[lecture.teacher_id].active):
                return REJECTED
            enrollment = next((e for e in policy.enrollments.values() if e.student_id == student_id
                               and e.discipline_id == lecture.discipline_id and e.group_id in lecture.group_ids
                               and live(e, now)), None)
            row = self._active(lecture_id, now_us)
            if enrollment is None or row is None or not self._authority(row, policy, lecture, now):
                return REJECTED
            try:
                self._window(row, lecture)  # AEAD binds expiry/source/operator; do not trust edited DB fields.
            except WindowError:
                return REJECTED
            bucket = now_us // 60_000_000
            failed = self.store.db.execute('SELECT failed FROM attempts WHERE lecture_id=? AND student_id=? AND bucket=?', (lecture_id, student_id, bucket)).fetchone()
            if failed and failed[0] >= 5:
                return REJECTED
            valid = isinstance(code, str) and len(code) == 4 and code.isascii() and code.isdigit()
            if not valid or not hmac.compare_digest(self.store.digest([lecture_id, code]), row['verifier']):
                self.store.db.execute('INSERT INTO attempts VALUES(?,?,?,1) ON CONFLICT(lecture_id,student_id,bucket) DO UPDATE SET failed=failed+1', (lecture_id, student_id, bucket))
                return REJECTED
            cursor = self.store.db.execute('INSERT OR IGNORE INTO attendance VALUES(?,?,?,?,?)', (lecture_id, student_id, enrollment.id, row['id'], now_us))
            return Admission(True, cursor.rowcount == 1)
