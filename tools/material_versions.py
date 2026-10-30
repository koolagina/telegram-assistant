"""Local version/rubric history, not a DOCX parser, watcher or auto-grader.

The trusted fetch_current provider MUST obtain current source bytes and validated
assignment/rubric extraction, never pass a stale cache after network/parser error.
This module enforces refresh-at-prepare/finish, optimistic head checks and durable
version pinning. It never reads a mailbox, writes grades or executes source text.
Real source adapters, authentication and rubric extraction are not connected yet.
"""
import contextlib
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from assistant_access import identifier


class MaterialError(ValueError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


@dataclass(frozen=True)
class MaterialRead:
    document: bytes = field(repr=False)
    rubrics: dict = field(repr=False)
    parser_version: str


@dataclass(frozen=True)
class CheckPlan:
    id: str
    version: str
    material_id: str
    assignment_id: str
    rules_json: str = field(repr=False)

    @property
    def rules(self):
        return json.loads(self.rules_json)

    @property
    def lecture_number(self):
        rules = self.rules
        return rules['number'] if rules['kind'] == 'lecture_makeup' else None


@dataclass(frozen=True)
class CriteriaSnapshot:
    """Local catalog comparison only, never proof of current remote bytes."""
    check_id: str = field(repr=False)
    assignment_id: str
    checked_version: str = field(repr=False)
    catalog_version: str = field(repr=False)
    assignment_present: bool


class MaterialCatalog:
    def __init__(self, path, *, namespace):
        if not identifier(namespace):
            raise MaterialError('Explicit project namespace required')
        self.path = Path(path).absolute()
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise MaterialError('State symlinks forbidden')
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.parent.stat().st_mode & 0o077:
            raise MaterialError('Private state directory required (0700)')
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        if self.path.stat().st_mode & 0o077:
            raise MaterialError('Private state file required (0600)')
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and tables != {'meta', 'heads', 'versions', 'checks'}:
                raise MaterialError('Foreign or incomplete state; review required')
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS heads(material_id TEXT PRIMARY KEY,version TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS versions(material_id TEXT,version TEXT,source_sha256 TEXT,parser_version TEXT,rubrics TEXT,PRIMARY KEY(material_id,version))')
                self.db.execute('CREATE TABLE IF NOT EXISTS checks(id TEXT PRIMARY KEY,material_id TEXT,assignment_id TEXT,version TEXT,status TEXT,result TEXT)')
                metadata = dict(self.db.execute('SELECT key,value FROM meta'))
                if not metadata and not tables:
                    self.db.executemany('INSERT INTO meta VALUES(?,?)', [('version', '1'), ('namespace', namespace)])
                elif metadata != {'version': '1', 'namespace': namespace}:
                    raise MaterialError('State namespace/schema mismatch')
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

    def _head(self, material_id):
        row = self.db.execute('SELECT version FROM heads WHERE material_id=?', (material_id,)).fetchone()
        return row[0] if row else None

    def _fresh(self, material_id, fetch_current):
        expected = self._head(material_id)  # Read before network/parser to detect racing updates.
        try:
            read = fetch_current()
            if (type(read) is not MaterialRead or type(read.document) is not bytes
                    or not 0 < len(read.document) <= 16*1024*1024
                    or not identifier(read.parser_version) or type(read.rubrics) is not dict
                    or not read.rubrics):
                raise MaterialError('Current material/extraction unavailable')
            for key, rules in read.rubrics.items():
                if (not identifier(key) or type(rules) is not dict
                        or rules.get('kind') not in ('practice', 'lecture_makeup')
                        or type(rules.get('number')) is not int or rules['number'] < 1
                        or type(rules.get('requirements')) is not list or not rules['requirements']
                        or any(not isinstance(x, str) or not x.strip() for x in rules['requirements'])):
                    raise MaterialError('Current rubric extraction requires review')
            rules_json = encoded(read.rubrics)  # Freeze provider-owned data; reject NaN/unsupported objects.
            sha = hashlib.sha256(read.document).hexdigest()
            version = digest([sha, read.parser_version, json.loads(rules_json)])
            return expected, version, sha, read.parser_version, rules_json
        except MaterialError:
            raise
        except Exception:
            raise MaterialError('Current source could not be verified; no cached fallback') from None

    def _publish(self, material_id, data):
        expected, version, sha, parser, rules = data
        if self._head(material_id) != expected:
            raise MaterialError('Source head changed during refresh; retry with fresh source')
        self.db.execute('INSERT OR IGNORE INTO versions VALUES(?,?,?,?,?)', (material_id, version, sha, parser, rules))
        self.db.execute('INSERT INTO heads VALUES(?,?) ON CONFLICT(material_id) DO UPDATE SET version=excluded.version', (material_id, version))
        return version, json.loads(rules)

    def prepare(self, submission_id, material_id, assignment_id, *, fetch_current):
        if not all(identifier(value) for value in (submission_id, material_id, assignment_id)):
            raise MaterialError('Stable submission/material/assignment IDs required')
        data = self._fresh(material_id, fetch_current)
        with self.transaction():
            version, rubrics = self._publish(material_id, data)
            if assignment_id not in rubrics:
                # Keep confirmed new head so pending checks cannot finish with removed rules.
                missing = True
            else:
                missing = False
                check_id = digest([submission_id, material_id, assignment_id, version])
                self.db.execute('INSERT OR IGNORE INTO checks VALUES(?,?,?,?,?,NULL)',
                                (check_id, material_id, assignment_id, version, 'pending'))
                plan = CheckPlan(check_id, version, material_id, assignment_id, encoded(rubrics[assignment_id]))
        if missing:
            raise MaterialError('Assignment missing in current material; review required')
        return plan

    def result(self, check_id):
        row = self.db.execute('SELECT * FROM checks WHERE id=?', (check_id,)).fetchone()
        if row is None:
            raise MaterialError('Unknown check')
        return dict(status=row['status'], result=json.loads(row['result']) if row['result'] else None, version=row['version'])

    def criteria_snapshot(self, check_id):
        """SELECT-only immutable check vs latest locally published source head.

        Does not refresh sources, alter history or certify remote freshness.
        Single joined query avoids mixing heads from separate SELECT snapshots.
        """
        try:
            if not identifier(check_id):raise ValueError()
            row=self.db.execute('SELECT c.id,c.assignment_id,c.version,h.version AS current_version,v.rubrics AS current_rules,p.rubrics AS checked_rules FROM checks c JOIN heads h ON h.material_id=c.material_id JOIN versions v ON v.material_id=h.material_id AND v.version=h.version JOIN versions p ON p.material_id=c.material_id AND p.version=c.version WHERE c.id=?',(check_id,)).fetchone()
            if row is None or not all(identifier(row[k]) for k in ('id','assignment_id','version','current_version')):raise ValueError()
            checked=json.loads(row['checked_rules']);current=json.loads(row['current_rules'])
            if type(checked) is not dict or type(current) is not dict or row['assignment_id'] not in checked:raise ValueError()
            return CriteriaSnapshot(row['id'],row['assignment_id'],row['version'],row['current_version'],row['assignment_id'] in current)
        except Exception:raise MaterialError('Local criteria state unavailable') from None

    def finish(self, check_id, result, *, fetch_current):
        if type(result) is not dict or not result:
            raise MaterialError('Nonempty structured check result required')
        try:
            result_json = encoded(result)
        except (ValueError, TypeError):
            raise MaterialError('Invalid check result') from None
        row = self.db.execute('SELECT * FROM checks WHERE id=?', (check_id,)).fetchone()
        if row is None:
            raise MaterialError('Unknown check')
        if row['status'] == 'done':
            if row['result'] != result_json:
                raise MaterialError('Completed result is immutable')
            return 'done'
        data = self._fresh(row['material_id'], fetch_current)
        with self.transaction():
            version, rubrics = self._publish(row['material_id'], data)
            current = self.db.execute('SELECT * FROM checks WHERE id=?', (check_id,)).fetchone()
            if current['status'] == 'done':
                if current['result'] != result_json:
                    raise MaterialError('Completed result is immutable')
                return 'done'
            if current['status'] == 'needs_recheck' or version != row['version'] or row['assignment_id'] not in rubrics:
                self.db.execute("UPDATE checks SET status='needs_recheck',result=NULL WHERE id=?", (check_id,))
                return 'needs_recheck'
            self.db.execute("UPDATE checks SET status='done',result=? WHERE id=?", (result_json, check_id))
            return 'done'
