"""Disabled-by-default Calendar stage candidate. Tests use injected fake ports.

No source status writes, notifications, runtime bootstrap or credential loading.
BoundPlan MUST come from a trusted immutable owner-decision registry carrying
ORIGINAL source/event evidence. Old unbound local plans cannot be auto-promoted.
Flags are not permission to use real resources. Reads also require authorization.
"""
import contextlib
import copy
from dataclasses import dataclass,asdict,field
import datetime as dt
import json
import os
from pathlib import Path
import re
import sqlite3
from assistant_access import AccessPolicy,aware,identifier
from consultation_actions import BusySnapshot,BusyEvent,AGE,DURATION,TZ
from consultation_feed import ConsultationFeed,HoldBinding
from material_versions import digest

MARKER='kulagina_consultation_operation'
class ExecutorError(ValueError):pass
class MutationRejected(Exception):
    def __init__(self,code):self.code=code;super().__init__('Calendar mutation rejected')

@dataclass(frozen=True)
class CalendarRecord:
    calendar_id: str = field(repr=False)
    id: str = field(repr=False)
    etag: str = field(repr=False)
    starts_at: dt.datetime
    ends_at: dt.datetime
    title: str = field(repr=False)
    location: str = field(repr=False)
    description: str = field(repr=False)
    extensions: dict = field(repr=False)
    protected: bool
    observed_at: dt.datetime

@dataclass(frozen=True)
class BoundPlan:
    id: str = field(repr=False)
    owner_id: str
    calendar_id: str = field(repr=False)
    plan: dict = field(repr=False)
    source_revision: str = field(repr=False)
    event_revision: str = field(repr=False)
    confirmed_at: dt.datetime
    @property
    def fingerprint(self):return digest([self.id,self.owner_id,self.calendar_id,self.plan,self.source_revision,self.event_revision,_utc(self.confirmed_at)])

@dataclass(frozen=True)
class MutationReceipt:
    calendar_id: str = field(repr=False)
    event_id: str = field(repr=False)
    method: str
    operation_id: str = field(repr=False)


@dataclass(frozen=True)
class ExecutionEvidence:
    plan_id: str = field(repr=False)
    plan_hash: str = field(repr=False)
    calendar_id: str = field(repr=False)
    request: dict = field(repr=False)
    status: str


def _utc(value):return value.astimezone(dt.timezone.utc).isoformat()
def _moment(value):
    if type(value) is not str:raise ExecutorError('Explicit time required')
    result=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if not aware(result):raise ExecutorError('Aware time required')
    return result

def _fresh(value,now):
    if not aware(value) or not aware(now) or not dt.timedelta(0)<=now-value<=AGE:raise ExecutorError('Evidence stale')

def _hex(value):return type(value) is str and re.fullmatch(r'[a-f0-9]{64}',value) is not None

def event_revision(event):
    if (type(event) is not CalendarRecord or not identifier(event.calendar_id) or not identifier(event.id)
            or type(event.etag) is not str or not event.etag or len(event.etag)>512 or any(ord(c)<32 for c in event.etag)
            or not all(aware(x) for x in (event.starts_at,event.ends_at,event.observed_at)) or event.ends_at<=event.starts_at
            or type(event.extensions) is not dict or type(event.protected) is not bool
            or any(type(x) is not str or len(x)>20000 for x in (event.title,event.location,event.description))):raise ExecutorError('Invalid Calendar record')
    data=asdict(event);data.pop('observed_at');data['starts_at']=_utc(event.starts_at);data['ends_at']=_utc(event.ends_at)
    if len(json.dumps(data,allow_nan=False).encode())>100000:raise ExecutorError('Calendar record limit')
    return digest(data)

class ConsultationExecutor:
    def __init__(self,path,*,namespace,owner_id,policy_provider,clock,load_plan,source,busy_snapshot,hold_bindings,calendar):
        if (not identifier(namespace) or not identifier(owner_id) or type(source) is not ConsultationFeed
                or not all(callable(x) for x in (policy_provider,clock,load_plan,busy_snapshot,hold_bindings))
                or not identifier(getattr(calendar,'calendar_id',None)) or calendar.calendar_id.lower()=='primary'
                or not callable(getattr(calendar,'read',None)) or not callable(getattr(calendar,'apply',None))):raise ExecutorError('Trusted execution wiring required')
        self.namespace=namespace;self.owner=owner_id;self.policy=policy_provider;self.clock=clock;self.load_plan=load_plan
        self.source=source;self.busy_snapshot=busy_snapshot;self.hold_bindings=hold_bindings;self.calendar=calendar
        path=Path(path).absolute()
        if path.is_symlink() or path.parent.is_symlink():raise ExecutorError('State symlinks forbidden')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.parent.stat().st_mode & 0o077:raise ExecutorError('Private directory required')
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        if path.stat().st_mode & 0o077:raise ExecutorError('Private state file required')
        self.db=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            tables={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and tables!={'calendar_meta','calendar_attempts'}:raise ExecutorError('Foreign state')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS calendar_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS calendar_attempts(plan_id TEXT PRIMARY KEY,plan_hash TEXT NOT NULL,booking_id TEXT UNIQUE NOT NULL,event_id TEXT UNIQUE NOT NULL,request TEXT NOT NULL,request_hash TEXT NOT NULL,phase TEXT NOT NULL)')
                metadata=dict(self.db.execute('SELECT key,value FROM calendar_meta'))
                expected={'version':'1','namespace':namespace,'owner':owner_id,'calendar':calendar.calendar_id,'source':source.spreadsheet_id}
                if not metadata and not tables:self.db.executemany('INSERT INTO calendar_meta VALUES(?,?)',expected.items())
                elif metadata!=expected:raise ExecutorError('Execution namespace/resource mismatch')
        except Exception:
            self.db.close();raise ExecutorError('Calendar journal unavailable') from None
    def close(self):self.db.close()
    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
    def _auth(self,context):
        policy=self.policy();now=self.clock()
        if type(policy) is not AccessPolicy or not aware(now) or not policy.authorize(context,'personal.read',self.owner,now=now).allowed:raise ExecutorError('Calendar execution unavailable')
        return policy,now
    def _row(self,plan_id):
        row=self.db.execute('SELECT request,request_hash,phase FROM calendar_attempts WHERE plan_id=?',(plan_id,)).fetchone()
        if row is not None and digest(row[0])!=row[1]:raise ExecutorError('Execution receipt requires review')
        return row
    def _result(self,plan_id):
        row=self._row(plan_id)
        return {'status':('inflight_or_unknown' if row[2]=='applying' else row[2]) if row else 'not_attempted','source_status':'not_written','notifications':'not_sent'}
    def result(self,context,plan_id):
        self._auth(context);result=self._result(plan_id);self._auth(context);return result
    def prepare(self,context,plan_id):
        """Trusted preflight only; no claim/mutation, separate read authorization."""
        try:return self._preflight(context,plan_id)[0]
        except Exception:raise ExecutorError('Calendar preflight unavailable') from None
    def evidence(self,context,plan_id):
        """Private durable journal evidence, not a caller-supplied success flag."""
        self._auth(context);row=self._row(plan_id)
        if row is None:raise ExecutorError('No Calendar stage evidence')
        plan_hash=self.db.execute('SELECT plan_hash FROM calendar_attempts WHERE plan_id=?',(plan_id,)).fetchone()[0]
        result=ExecutionEvidence(plan_id,plan_hash,self.calendar.calendar_id,json.loads(row[0]),self._result(plan_id)['status'])
        self._auth(context);return result
    def _finish(self,plan_id,phase):
        with self.transaction():
            row=self._row(plan_id)
            if row is None:raise ExecutorError('Missing claim')
            if row[2] not in ('applying','unknown'):return self._result(plan_id)
            self.db.execute('UPDATE calendar_attempts SET phase=? WHERE plan_id=?',(phase,plan_id))
        return self._result(plan_id)
    def _preflight(self,context,plan_id):
        policy,now=self._auth(context);bound=copy.deepcopy(self.load_plan(plan_id))
        if (type(bound) is not BoundPlan or bound.id!=plan_id or bound.owner_id!=self.owner or bound.calendar_id!=self.calendar.calendar_id
                or not _hex(bound.source_revision) or not _hex(bound.event_revision) or not aware(bound.confirmed_at)
                or not dt.timedelta(0)<=now-bound.confirmed_at<AGE or type(bound.plan) is not dict):raise ExecutorError('Original confirmation evidence required')
        plan=bound.plan
        if (set(plan)!={'status','execution','booking_id','expected_revision','action','calendar','notifications'}
                or plan['status']!='planned' or plan['execution']!='not_executed' or not identifier(plan['booking_id'])
                or type(plan['expected_revision']) is not int or plan['expected_revision']<0 or plan['action'] not in ('approve','reject')
                or type(plan['calendar']) is not dict):raise ExecutorError('Unsupported confirmed plan')
        operation=plan['calendar'];method='update' if plan['action']=='approve' else 'delete'
        fields={'method','event_id','expected_hold'}|({'start','end','room','state'} if method=='update' else set())
        if set(operation)!=fields or operation['method']!=method or not identifier(operation['event_id']):raise ExecutorError('Unsupported Calendar operation')
        expected=operation['expected_hold']
        if type(expected) is not dict or set(expected)!={'consultation_id','start','end'} or expected['consultation_id']!=plan['booking_id']:raise ExecutorError('Invalid hold proof')
        start,end=_moment(expected['start']),_moment(expected['end'])
        if end-start!=DURATION:raise ExecutorError('Invalid duration')
        if method=='update':
            if (_moment(operation['start'])!=start or _moment(operation['end'])!=end or operation['room']!='317' or operation['state']!='confirmed'):raise ExecutorError('Moving consultation is not supported')
            local=start.astimezone(TZ);minute=local.hour*60+local.minute
            if start<=now or local.weekday()>4 or local.second or local.microsecond or minute<540 or minute+20>1080 or (minute<740 and minute+20>700):raise ExecutorError('Outside consultation policy')
        snapshot=self.source.snapshot();rows=[row for row in snapshot.rows if row.record.id==plan['booking_id']]
        if not snapshot.complete or len(rows)!=1:raise ExecutorError('Full current source required')
        row=rows[0]
        if (row.revision!=bound.source_revision or row.record.status!='Ожидает решения' or row.event_id!=operation['event_id'] or row.record.starts_at!=start):raise ExecutorError('Original source changed')
        bindings=self.hold_bindings()
        if type(bindings) is not tuple or len(bindings)>10000 or any(type(x) is not HoldBinding for x in bindings):raise ExecutorError('Trusted hold ledger required')
        matching=[b for b in bindings if b.event_id==operation['event_id'] or b.consultation_id==plan['booking_id']]
        if len(matching)!=1 or matching[0]!=HoldBinding(bound.calendar_id,operation['event_id'],plan['booking_id'],start,end):raise ExecutorError('Hold ownership ambiguous')
        busy=self.busy_snapshot()
        if (type(busy) is not BusySnapshot or busy.complete is not True or busy.teaching_complete is not True
                or type(busy.events) is not tuple or len(busy.events)>10000
                or not all(aware(x) for x in (busy.observed_at,busy.covered_start,busy.covered_end))
                or busy.covered_start>start or busy.covered_end<end):raise ExecutorError('Complete current teaching/busy snapshot required')
        seen=set();own=[]
        for event in busy.events:
            if (type(event) is not BusyEvent or not identifier(event.id) or event.id in seen
                    or not aware(event.starts_at) or not aware(event.ends_at) or event.ends_at<=event.starts_at):raise ExecutorError('Ambiguous busy evidence')
            seen.add(event.id)
            if event.id==operation['event_id']:own.append(event)
            elif method=='update' and event.starts_at<end and event.ends_at>start:raise ExecutorError('Slot occupied')
        if len(own)!=1 or own[0].consultation_id!=plan['booking_id'] or own[0].starts_at!=start or own[0].ends_at!=end:raise ExecutorError('Owned hold absent')
        actual=copy.deepcopy(self.calendar.read(operation['event_id']))
        if (event_revision(actual)!=bound.event_revision or actual.calendar_id!=bound.calendar_id or actual.id!=operation['event_id']
                or actual.starts_at!=start or actual.ends_at!=end or actual.protected):raise ExecutorError('Calendar changed or protected')
        # Re-read source after Calendar reads, then reauthorize. No network under SQLite lock.
        self.source.require_revision(plan['booking_id'],bound.source_revision)
        policy,final=self._auth(context)
        if not dt.timedelta(0)<=final-bound.confirmed_at<AGE or final<now:raise ExecutorError('Confirmation expired')
        for stamp in (snapshot.observed_at,busy.observed_at,actual.observed_at):_fresh(stamp,final)
        if method=='update' and start<=final:raise ExecutorError('Slot passed')
        student=policy.bindings.get(('telegram',row.chat_id))
        entity=policy.students.get(student.entity_id) if student is not None else None
        if (student is None or student.role!='student' or student.active is not True or student.confirmed is not True or entity is None or entity.active is not True):raise ExecutorError('Verified current student binding required')
        notices=plan['notifications']
        if notices!=[{'recipient_kind':'student','recipient_id':student.entity_id},{'recipient_kind':'owner','recipient_id':self.owner}]:raise ExecutorError('Recipient changed')
        extensions=copy.deepcopy(actual.extensions)
        private=extensions.setdefault('private',{})
        if type(private) is not dict:raise ExecutorError('Unsupported private event properties')
        if MARKER in private:raise ExecutorError('Previous calendar attempt requires reconciliation')
        operation_id=digest([self.namespace,bound.calendar_id,bound.id,bound.fingerprint])
        private[MARKER]=operation_id
        pending_phrase='предварительная запись, решение преподавателя ещё не получено.'
        old_prefix='Заявка '+plan['booking_id']+'; тема: '+row.record.topic+'; '+pending_phrase
        description=None
        if method=='update':
            if actual.description.startswith(old_prefix):
                description='Заявка '+plan['booking_id']+'; тема: '+row.record.topic+'; подтверждена владельцем.'+actual.description[len(old_prefix):]
            elif pending_phrase in actual.description:raise ExecutorError('Legacy pending description requires review')
        request={'calendar_id':bound.calendar_id,'method':method,'event_id':actual.id,'etag':actual.etag,'operation_id':operation_id,
                 'start':_utc(start),'end':_utc(end),'title':'Консультация — подтверждена','location':'Кабинет 317','extensions':extensions}
        if description is not None:request['description']=description
        return bound,request
    def execute(self,context,plan_id,*,execution_enabled=False):
        if execution_enabled is not True or getattr(self.calendar,'writes_enabled',False) is not True:raise ExecutorError('Calendar execution disabled')
        self._auth(context)
        if not identifier(plan_id):raise ExecutorError('Invalid confirmed plan identity')
        if self._row(plan_id) is not None:return self.result(context,plan_id)
        try:bound,request=self._preflight(context,plan_id)
        except Exception:raise ExecutorError('Calendar preflight failed; refresh and verify') from None
        try:
            with self.transaction():
                if self._row(plan_id) is not None:return self._result(plan_id)
                encoded=json.dumps(request,ensure_ascii=False,sort_keys=True,allow_nan=False)
                self.db.execute("INSERT INTO calendar_attempts VALUES(?,?,?,?,?,?,'applying')",(plan_id,bound.fingerprint,bound.plan['booking_id'],request['event_id'],encoded,digest(encoded)))
        except Exception:raise ExecutorError('Calendar claim unavailable; do not apply') from None
        # Durable claim exists before ANY possible mutation. All reads/mutations outside DB lock.
        try:
            current,checked=self._preflight(context,plan_id)
            if current.fingerprint!=bound.fingerprint or checked!=request:raise ExecutorError('Preflight changed')
        except Exception:
            try:return self._finish(plan_id,'blocked_preflight')
            except Exception:return {'status':'needs_recovery','source_status':'not_written','notifications':'not_sent'}
        # Current gate immediately before the mutation; no action on revoke.
        try:self._auth(context)
        except Exception:
            try:return self._finish(plan_id,'blocked_preflight')
            except Exception:return {'status':'needs_recovery','source_status':'not_written','notifications':'not_sent'}
        phase='unknown'
        try:
            receipt=self.calendar.apply(copy.deepcopy(request))
            if type(receipt) is MutationReceipt and receipt==MutationReceipt(request['calendar_id'],request['event_id'],request['method'],request['operation_id']):phase='calendar_api_confirmed'
        except MutationRejected as error:
            if type(error.code) is int and 400<=error.code<=499 and error.code!=408:phase='calendar_rejected'
        except Exception:pass  # API acceptance is uncertain; no blind retry.
        try:return self._finish(plan_id,phase)
        except Exception:return {'status':'needs_recovery','source_status':'not_written','notifications':'not_sent'}
    def reconcile(self,context,plan_id):
        self._auth(context);row=self._row(plan_id)
        if row is None:raise ExecutorError('No durable attempt to reconcile')
        if row[2] not in ('applying','unknown'):return self.result(context,plan_id)
        try:
            request=json.loads(row[0]);before=self.clock();actual=self.calendar.read(request['event_id']);_,after=self._auth(context)
            if not aware(before) or not dt.timedelta(0)<=after-before<=AGE:raise ExecutorError('Stale reconciliation read')
            if actual is None and request['method']=='delete':return self._finish(plan_id,'calendar_reconciled_absent')
            if actual is not None:
                event_revision(actual);_fresh(actual.observed_at,self.clock())
                if (request['method']=='update' and actual.calendar_id==request['calendar_id'] and actual.id==request['event_id']
                        and _utc(actual.starts_at)==request['start'] and _utc(actual.ends_at)==request['end']
                        and actual.protected is False and actual.title==request['title'] and actual.location==request['location']
                        and actual.extensions==request['extensions']
                        and ('description' not in request or actual.description==request['description'])):return self._finish(plan_id,'calendar_reconciled_present')
            return self.result(context,plan_id)  # Still unknown/active, never reset for retry.
        except Exception:raise ExecutorError('Calendar reconciliation unavailable; review required') from None
