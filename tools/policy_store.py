"""Private versioned snapshots of existing AccessPolicy, CAS writes.

Trusted administrative code only. No role-request endpoint, user authentication,
secret storage, automatic owner assignment or source of real account bindings.
Never deserialize a policy snapshot submitted by a student/LLM/public request.
"""
import contextlib
from dataclasses import asdict,fields
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
from assistant_access import (AccessPolicy,Teacher,Student,Binding,Enrollment,TeachingGrant,
                              AcademicReadGrant,Lecture,SubstitutionGrant,identifier)

RECORDS={'teachers':Teacher,'students':Student,'bindings':Binding,'enrollments':Enrollment,
         'teaching_grants':TeachingGrant,'academic_read_grants':AcademicReadGrant,
         'lectures':Lecture,'substitutions':SubstitutionGrant}
DATES=frozenset({'valid_from','valid_until','starts_at','ends_at'})
MAX_PAYLOAD=8*1024*1024

class PolicyStoreError(ValueError):
    pass


def _encode(policy):
    if type(policy) is not AccessPolicy:raise PolicyStoreError('Trusted policy snapshot required')
    result={}
    for name in RECORDS:
        records=[]
        for record in getattr(policy,name).values():
            data=asdict(record)
            for key,value in data.items():
                if key in DATES:data[key]=value.isoformat()
                elif type(value) is frozenset:data[key]=sorted(value)
                elif type(value) is tuple:data[key]=list(value)
            records.append(data)
        result[name]=sorted(records,key=lambda item:json.dumps(item,sort_keys=True))
    payload=json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(payload.encode())>MAX_PAYLOAD:raise PolicyStoreError('Policy snapshot limit exceeded')
    return payload


def _decode(payload):
    if not isinstance(payload,str) or len(payload.encode())>MAX_PAYLOAD:raise PolicyStoreError('Invalid policy snapshot')
    data=json.loads(payload)
    if type(data) is not dict or set(data)!=set(RECORDS):raise PolicyStoreError('Incomplete policy snapshot')
    result={}
    for name,cls in RECORDS.items():
        if type(data[name]) is not list or len(data[name])>10000:raise PolicyStoreError('Invalid policy records')
        records=[]
        for item in data[name]:
            if type(item) is not dict or set(item)!={field.name for field in fields(cls)}:raise PolicyStoreError('Invalid policy record shape')
            item=dict(item)
            for key,value in item.items():
                if key in DATES:
                    if type(value) is not str:raise PolicyStoreError('Invalid policy time')
                    item[key]=dt.datetime.fromisoformat(value)
                elif key in ('capabilities','group_ids'):
                    if type(value) is not list or any(type(x) is not str for x in value) or len(set(value))!=len(value):raise PolicyStoreError('Invalid policy collection')
                    item[key]=frozenset(value) if key=='capabilities' else tuple(value)
            records.append(cls(**item))
        result[name]=tuple(records)
    return AccessPolicy(**result)

class PolicyStore:
    def __init__(self,path,*,namespace):
        if not identifier(namespace):raise PolicyStoreError('Explicit project namespace required')
        path=Path(path).absolute()
        if path.is_symlink() or path.parent.is_symlink():raise PolicyStoreError('State symlinks forbidden')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.parent.stat().st_mode & 0o077:raise PolicyStoreError('Private state directory required')
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        if path.stat().st_mode & 0o077:raise PolicyStoreError('Private state file required')
        self.db=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            tables={row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and tables!={'policy_meta','policy_revisions'}:raise PolicyStoreError('Foreign or incomplete policy state')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS policy_meta(key TEXT PRIMARY KEY,value TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS policy_revisions(revision INTEGER PRIMARY KEY,payload TEXT)')
                metadata=dict(self.db.execute('SELECT key,value FROM policy_meta'))
                if not metadata and not tables:
                    self.db.executemany('INSERT INTO policy_meta VALUES(?,?)',[('version','1'),('namespace',namespace)])
                elif metadata!={'version':'1','namespace':namespace}:raise PolicyStoreError('Policy namespace/schema mismatch')
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
    def load(self):
        try:
            row=self.db.execute('SELECT revision,payload FROM policy_revisions ORDER BY revision DESC LIMIT 1').fetchone()
            if row is None:return 0,AccessPolicy()
            if type(row[0]) is not int or row[0]<1:raise PolicyStoreError('Invalid policy revision')
            return row[0],_decode(row[1])
        except Exception:
            raise PolicyStoreError('Current policy unavailable; no older fallback') from None
    def save(self,policy,*,expected_revision):
        try:
            if type(expected_revision) is not int or not 0<=expected_revision<2**62:raise PolicyStoreError('Explicit current revision required')
            payload=_encode(policy)
            with self.transaction():
                current,_=self.load()
                if current!=expected_revision:raise PolicyStoreError('Policy changed; reload before update')
                self.db.execute('INSERT INTO policy_revisions VALUES(?,?)',(current+1,payload))
                return current+1
        except PolicyStoreError:raise
        except Exception:
            raise PolicyStoreError('Policy snapshot could not be saved') from None
