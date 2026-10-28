"""Offline consultation decision sandbox; durable PLANS, no external executor.

This store is NOT the real Sheet or a mirror allowed to overwrite it. Trusted
local fixtures only. No API calls, sends, migrations or automatic plan execution.
A future executor must revalidate rights, source revisions and event ownership;
these plans are not credentials or evidence that any real operation succeeded.
"""
import contextlib
from dataclasses import dataclass,asdict,field,replace
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import sqlite3
from zoneinfo import ZoneInfo
from assistant_access import AccessPolicy,aware,identifier
from material_versions import digest

TZ=ZoneInfo('Asia/Yekaterinburg')
PENDING='Ожидает решения'
AGE=dt.timedelta(minutes=5)
DURATION=dt.timedelta(minutes=20)
class ActionError(ValueError):pass

@dataclass(frozen=True)
class Booking:
    id: str
    student_id: str = field(repr=False)
    starts_at: dt.datetime
    event_id: str = field(repr=False)
    status: str = PENDING
    revision: int = 0

@dataclass(frozen=True)
class BusyEvent:
    id: str
    starts_at: dt.datetime
    ends_at: dt.datetime
    consultation_id: str | None = None  # Trusted ownership ledger, NOT title match.

@dataclass(frozen=True)
class BusySnapshot:
    events: tuple
    observed_at: dt.datetime
    covered_start: dt.datetime
    covered_end: dt.datetime
    complete: bool
    teaching_complete: bool

@dataclass(frozen=True)
class ActionIntent:
    token: str = field(repr=False)
    booking_id: str
    action: str
    starts_at: dt.datetime
    expires_at: dt.datetime


def _encode(booking):
    data=asdict(booking);data['starts_at']=booking.starts_at.isoformat()
    return json.dumps(data,sort_keys=True,ensure_ascii=False)


def _decode(payload):
    data=json.loads(payload);data['starts_at']=dt.datetime.fromisoformat(data['starts_at'])
    return Booking(**data)

class ConsultationActions:
    def __init__(self,path,*,namespace,owner_id,policy_provider,clock,calendar_snapshot,student_eligible):
        if (not identifier(namespace) or not identifier(owner_id)
                or not all(callable(x) for x in (policy_provider,clock,calendar_snapshot,student_eligible))):
            raise ActionError('Trusted local configuration required')
        self.owner=owner_id;self.policy=policy_provider;self.clock=clock
        self.calendar_snapshot=calendar_snapshot;self.student_eligible=student_eligible
        path=Path(path).absolute()
        if path.is_symlink() or path.parent.is_symlink():raise ActionError('State symlinks forbidden')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.parent.stat().st_mode & 0o077:raise ActionError('Private state directory required')
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        if path.stat().st_mode & 0o077:raise ActionError('Private state file required')
        self.db=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            tables={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and tables!={'action_meta','bookings','action_intents','action_plans'}:raise ActionError('Foreign state')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS action_meta(id INTEGER PRIMARY KEY, identity TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS bookings(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS action_intents(token TEXT PRIMARY KEY,payload TEXT NOT NULL,state TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS action_plans(token TEXT PRIMARY KEY,payload TEXT NOT NULL)')
                identity=digest([namespace,owner_id,'offline-consultation-plans-v1'])
                row=self.db.execute('SELECT identity FROM action_meta WHERE id=1').fetchone()
                if row is None:self.db.execute('INSERT INTO action_meta VALUES(1,?)',(identity,))
                elif row[0]!=identity:raise ActionError('Foreign project or owner')
        except Exception:
            self.db.close();raise ActionError('Local action store unavailable') from None
    def close(self):self.db.close()
    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def _auth(self,context):
        policy=self.policy();now=self.clock()
        if (type(policy) is not AccessPolicy or not aware(now)
                or not policy.authorize(context,'personal.read',self.owner,now=now).allowed):
            raise ActionError('Consultation action unavailable')
        return now
    def add(self,booking):
        """Trusted fixture ingestion, never a public command or real Sheet import."""
        if (type(booking) is not Booking or not all(identifier(x) for x in (booking.id,booking.student_id,booking.event_id))
                or not aware(booking.starts_at) or booking.status!=PENDING or type(booking.revision) is not int or booking.revision!=0):
            raise ActionError('Explicit pending fixture required')
        with self.transaction():
            row=self.db.execute('SELECT payload FROM bookings WHERE id=?',(booking.id,)).fetchone()
            if row is not None:
                if _decode(row[0])!=booking:raise ActionError('Conflicting fixture')
            else:self.db.execute('INSERT INTO bookings VALUES(?,?)',(booking.id,_encode(booking)))
    def booking(self,booking_id):
        """Private trusted store accessor; not an authorized public view."""
        row=self.db.execute('SELECT payload FROM bookings WHERE id=?',(booking_id,)).fetchone()
        if row is None:raise ActionError('Consultation action unavailable')
        return _decode(row[0])
    def plans(self):
        """Private operator inspection. Never wire this accessor to a student."""
        return tuple(json.loads(r[0]) for r in self.db.execute('SELECT payload FROM action_plans ORDER BY rowid'))
    def reference(self,context,booking_id):
        self._auth(context);booking=self.booking(booking_id)
        self._auth(context)
        return digest([self.owner,_encode(booking)])[:32]
    def resolve(self,context,reference):
        self._auth(context)
        matches=[_decode(r[0]) for r in self.db.execute('SELECT payload FROM bookings')
                 if digest([self.owner,_encode(_decode(r[0]))])[:32]==reference]
        self._auth(context)
        if len(matches)!=1:raise ActionError('Changed consultation reference')
        return matches[0]
    def _check(self,context,booking,action,start):
        now=self._auth(context)
        if booking.status!=PENDING:raise ActionError('Refresh changed consultation')
        if action not in ('approve','reject','propose') or not aware(start):raise ActionError('Invalid action')
        if action!='reject':
            if self.student_eligible(booking.student_id,now) is not True:raise ActionError('Student access unavailable')
            local=start.astimezone(TZ);end=local+DURATION
            minute=local.hour*60+local.minute;to=minute+20
            if (local.second or local.microsecond or start<=now or local.weekday()>4 or minute<540 or to>1080
                    or (minute<740 and to>700) or (action=='propose' and start-now<dt.timedelta(minutes=30))):
                raise ActionError('Time outside consultation policy')
        snapshot=self.calendar_snapshot()  # Trusted LOCAL snapshot only, no network under transaction.
        if (type(snapshot) is not BusySnapshot or type(snapshot.events) is not tuple or len(snapshot.events)>10000
                or snapshot.complete is not True or snapshot.teaching_complete is not True
                or not all(aware(x) for x in (snapshot.observed_at,snapshot.covered_start,snapshot.covered_end))
                or snapshot.covered_start>min(start,booking.starts_at)
                or snapshot.covered_end<max(start,booking.starts_at)+DURATION):
            raise ActionError('Verified complete calendar required')
        ids=set();owned=[]
        for event in snapshot.events:
            if (type(event) is not BusyEvent or not identifier(event.id) or event.id in ids
                    or not aware(event.starts_at) or not aware(event.ends_at) or event.ends_at<=event.starts_at
                    or (event.consultation_id is not None and not identifier(event.consultation_id))):
                raise ActionError('Ambiguous calendar snapshot')
            ids.add(event.id)
            if event.id==booking.event_id:
                if (event.consultation_id!=booking.id or event.starts_at!=booking.starts_at
                        or event.ends_at!=booking.starts_at+DURATION):raise ActionError('Owned hold changed')
                owned.append(event)
            elif action!='reject' and event.starts_at<start+DURATION and event.ends_at>start:
                raise ActionError('Slot is occupied')
        if len(owned)!=1:raise ActionError('Owned hold not verified')
        final=self._auth(context)
        if action!='reject' and self.student_eligible(booking.student_id,final) is not True:
            raise ActionError('Student access changed while checking')
        final=self._auth(context)
        if (not dt.timedelta(0)<=final-snapshot.observed_at<=AGE or final<now
                or (action!='reject' and start<=final)
                or (action=='propose' and start-final<dt.timedelta(minutes=30))):
            raise ActionError('Stale availability')
        return final,owned[0]
    def preview(self,context,booking_id,action,*,proposed_start=None):
        try:
            self._auth(context)
            with self.transaction():
                booking=self.booking(booking_id)
                if action=='propose':start=proposed_start
                else:
                    if proposed_start is not None:raise ActionError('Unexpected proposal')
                    start=booking.starts_at
                now,_=self._check(context,booking,action,start)
                token=secrets.token_hex(16);expires=now+AGE
                data={'booking_id':booking.id,'revision':booking.revision,'action':action,'start':start.isoformat(),'created':now.isoformat(),'expires':expires.isoformat()}
                self.db.execute('INSERT INTO action_intents VALUES(?,?,?)',(token,json.dumps(data),'pending'))
                return ActionIntent(token,booking.id,action,start,expires)
        except Exception:raise ActionError('Consultation action unavailable; refresh and verify sources') from None
    def cancel(self,context,token):
        self._auth(context)
        with self.transaction():self.db.execute("UPDATE action_intents SET state='cancelled' WHERE token=? AND state='pending'",(token,))
    def confirm(self,context,token):
        try:
            now=self._auth(context)
            if type(token) is not str or len(token)!=32:raise ActionError('Invalid intent')
            with self.transaction():
                # Idempotent recovery still requires CURRENT owner access.
                existing=self.db.execute('SELECT payload FROM action_plans WHERE token=?',(token,)).fetchone()
                if existing is not None:return json.loads(existing[0])
                row=self.db.execute('SELECT payload,state FROM action_intents WHERE token=?',(token,)).fetchone()
                if row is None or row[1]!='pending':raise ActionError('Intent unavailable')
                data=json.loads(row[0]);expires=dt.datetime.fromisoformat(data['expires'])
                if not dt.datetime.fromisoformat(data['created'])<=now<expires:raise ActionError('Expired intent')
                booking=self.booking(data['booking_id']);start=dt.datetime.fromisoformat(data['start']);action=data['action']
                if booking.revision!=data['revision']:raise ActionError('Changed consultation')
                final,hold=self._check(context,booking,action,start)
                if final>=expires:raise ActionError('Expired while checking')
                calendar=None
                if action!='propose':
                    calendar={'method':'update' if action=='approve' else 'delete','event_id':booking.event_id,
                              'expected_hold':{'consultation_id':booking.id,'start':hold.starts_at.isoformat(),'end':hold.ends_at.isoformat()}}
                    if action=='approve':calendar.update(start=start.isoformat(),end=(start+DURATION).isoformat(),room='317',state='confirmed')
                plan={'status':'planned','execution':'not_executed','booking_id':booking.id,'expected_revision':booking.revision,
                      'action':action,'calendar':calendar,'notifications':[{'recipient_kind':'student','recipient_id':booking.student_id},{'recipient_kind':'owner','recipient_id':self.owner}]}
                if action=='propose':plan['proposed_start']=start.isoformat()
                status={'approve':'Подтверждена','reject':'Отклонена','propose':PENDING}[action]
                updated=replace(booking,status=status,revision=booking.revision+1)
                self.db.execute('UPDATE bookings SET payload=? WHERE id=?',(_encode(updated),booking.id))
                self.db.execute('INSERT INTO action_plans VALUES(?,?)',(token,json.dumps(plan,ensure_ascii=False)))
                self.db.execute("UPDATE action_intents SET state='planned' WHERE token=?",(token,))
                return plan
        except Exception:raise ActionError('Consultation action unavailable; refresh and verify sources') from None
