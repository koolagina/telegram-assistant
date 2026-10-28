"""Private durable report-ownership index. No public registration endpoint.

Only trusted ingestion may supply links and the same-project result loader.
This does not authenticate students, grant roles or write grades. Completed
report state is committed before the link; interrupted publication retries are
idempotent and never rewrite the first owner. Registry/history backups must be
coordinated by the future runtime; this is not a cross-database transaction.
"""
import contextlib
from dataclasses import astuple
import os
from pathlib import Path
import sqlite3
from assistant_access import identifier
from report_access import ReportLink

class RegistryError(ValueError):
    pass

class ReportRegistry:
    def __init__(self,path,*,namespace):
        if not identifier(namespace):raise RegistryError('Explicit project namespace required')
        path=Path(path).absolute()
        if path.is_symlink() or path.parent.is_symlink():raise RegistryError('State symlinks forbidden')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.parent.stat().st_mode & 0o077:raise RegistryError('Private state directory required')
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        if path.stat().st_mode & 0o077:raise RegistryError('Private state file required')
        self.db=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            tables={row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and tables!={'registry_meta','report_links'}:raise RegistryError('Foreign or incomplete registry')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS registry_meta(key TEXT PRIMARY KEY,value TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS report_links(id TEXT PRIMARY KEY,check_id TEXT UNIQUE,enrollment_id TEXT,student_id TEXT,discipline_id TEXT,group_id TEXT)')
                metadata=dict(self.db.execute('SELECT key,value FROM registry_meta'))
                if not metadata and not tables:
                    self.db.executemany('INSERT INTO registry_meta VALUES(?,?)',[('version','1'),('namespace',namespace)])
                elif metadata!={'version':'1','namespace':namespace}:raise RegistryError('Registry namespace/schema mismatch')
        except Exception:
            self.db.close();raise

    def __enter__(self):return self
    def __exit__(self,*args):self.db.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise

    def register(self,link,*,load_result):
        """Publish only a completed local report, not an accepted assignment."""
        try:
            if type(link) is not ReportLink or not all(identifier(value) for value in astuple(link)):
                raise RegistryError('Invalid trusted ownership link')
            row=load_result(link.check_id)
            if type(row) is not dict or row.get('status')!='done' or type(row.get('result')) is not dict:
                raise RegistryError('Completed report required')
            report=row['result']
            if (report.get('check_id')!=link.check_id or not identifier(row.get('version'))
                    or report.get('material_version')!=row['version']
                    or report.get('status')!='needs_teacher_review' or report.get('credit_written') is not False):
                raise RegistryError('Completed report identity mismatch')
            with self.transaction():
                existing=self.db.execute('SELECT * FROM report_links WHERE id=? OR check_id=?',(link.id,link.check_id)).fetchall()
                if existing:
                    if len(existing)!=1 or tuple(existing[0])!=astuple(link):raise RegistryError('Published ownership is immutable')
                    return
                self.db.execute('INSERT INTO report_links VALUES(?,?,?,?,?,?)',astuple(link))
        except RegistryError:raise
        except Exception:
            raise RegistryError('Report publication failed; review or retry required') from None

    def snapshot(self):
        try:
            links=tuple(ReportLink(*row) for row in self.db.execute('SELECT * FROM report_links ORDER BY id'))
            if any(not all(identifier(value) for value in astuple(link)) for link in links):
                raise RegistryError('Invalid report registry')
            return links
        except Exception:
            raise RegistryError('Report registry unavailable') from None
