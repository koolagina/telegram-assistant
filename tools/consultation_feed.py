"""Read-only normalization of TRUSTED local Sheet/Calendar snapshots.

No credential discovery, live Sheet transport, writes or scheduler. A snapshot
is not authentic merely because it has these fields: trusted collection and
verification are separate server/operator responsibilities. Never accept these
objects/teaching attestations from student commands or public request bodies.
"""
import copy
import json
from dataclasses import dataclass,field,replace
import datetime as dt
import re
from assistant_access import aware,identifier
from consultation_actions import BusyEvent,BusySnapshot,TZ,AGE
from decision_sources import ConsultationRecord,ConsultationBatch
from material_versions import digest

HEADERS=('ID заявки','Дата создания','Студент','Telegram chat ID','Желаемая дата','Желаемое время','Длительность, мин','Тема','Статус','Решение / причина','ID события календаря')
SHEET_NAME='Заявки на консультации'
STATUSES=frozenset({'Ожидает решения','Обработка — требуется сверка при сбое','Подтверждена','Отклонена','Отменена','Создаётся предварительная запись','Отклонение выполняется','Отмена выполняется'})
class FeedError(ValueError):pass

@dataclass(frozen=True)
class SheetSnapshot:
    spreadsheet_id: str = field(repr=False)
    sheet_name: str
    headers: tuple
    rows: tuple = field(repr=False)
    observed_at: dt.datetime
    complete: bool
    timezone: str

@dataclass(frozen=True)
class ConsultationEvidence:
    record: ConsultationRecord = field(repr=False)
    chat_id: str = field(repr=False)
    event_id: str | None = field(repr=False)
    decision: str = field(repr=False)
    revision: str = field(repr=False)

@dataclass(frozen=True)
class ConsultationSnapshot:
    rows: tuple = field(repr=False)
    observed_at: dt.datetime
    complete: bool

@dataclass(frozen=True)
class CalendarSnapshot:
    calendar_id: str = field(repr=False)
    events: tuple = field(repr=False)
    observed_at: dt.datetime
    covered_start: dt.datetime
    covered_end: dt.datetime
    complete: bool

@dataclass(frozen=True)
class TeachingVerification:
    """Trusted attestation of verified import; this module does NOT issue it.

    Bound to teacher, exact calendar snapshot/range, current source version and
    its actual observation time. Empty Calendar/source success alone cannot
    establish this. Real verifier/provisioning remains a separate acceptance task.
    """
    teacher_id: str
    calendar_id: str = field(repr=False)
    covered_start: dt.datetime
    covered_end: dt.datetime
    observed_at: dt.datetime
    source_observed_at: dt.datetime
    source_revision: str = field(repr=False)
    calendar_revision: str = field(repr=False)

@dataclass(frozen=True)
class HoldBinding:
    calendar_id: str = field(repr=False)
    event_id: str = field(repr=False)
    consultation_id: str = field(repr=False)
    starts_at: dt.datetime
    ends_at: dt.datetime


def _utc(value):return value.astimezone(dt.timezone.utc).isoformat()

def _fresh(stamp,now):
    if not aware(stamp) or not aware(now) or not dt.timedelta(0)<=now-stamp<=AGE:raise FeedError('Snapshot stale or invalid')

def _moment(value):
    if type(value) is str:
        value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if not aware(value):raise FeedError('Aware timestamp required')
    return value

def _day(value):
    if type(value) is dt.datetime:return _moment(value).astimezone(TZ).date()
    if type(value) is dt.date:return value
    if type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value,flags=re.ASCII):return dt.date.fromisoformat(value)
    raise FeedError('Explicit date required; numeric Sheets serials are not guessed')

def _time(value):
    if type(value) is dt.datetime:value=_moment(value).astimezone(TZ).time()
    if type(value) is str and re.fullmatch(r'\d{2}:\d{2}',value,flags=re.ASCII):value=dt.time.fromisoformat(value)
    if type(value) is not dt.time or value.tzinfo is not None or value.second or value.microsecond:raise FeedError('Explicit minute time required')
    return value

def _string(value,limit=20000):
    if type(value) is not str or len(value)>limit:raise FeedError('Invalid Sheet cell type/size')
    return value


def decode_sheet_export(payload):
    """Bounded private artifact decode; NOT authentication of its producer."""
    try:
        if type(payload) is not str or len(payload.encode('utf-8'))>2*1024*1024:raise FeedError('Export limit exceeded')
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise FeedError('Ambiguous export')
                result[key]=value
            return result
        data=json.loads(payload,object_pairs_hook=unique)
        expected={'format_version','spreadsheet_id','sheet_name','headers','rows','observed_at','complete','timezone'}
        if (type(data) is not dict or set(data)!=expected or type(data['format_version']) is not int or data['format_version']!=1
                or type(data['headers']) is not list or type(data['rows']) is not list or len(data['rows'])>10000
                or any(type(row) is not list for row in data['rows'])):raise FeedError('Unknown export format')
        return SheetSnapshot(data['spreadsheet_id'],data['sheet_name'],tuple(data['headers']),tuple(tuple(row) for row in data['rows']),
                             _moment(data['observed_at']),data['complete'],data['timezone'])
    except Exception:raise FeedError('Consultation export unavailable; verify source') from None

class ConsultationFeed:
    def __init__(self,*,spreadsheet_id,load_snapshot,clock):
        if not identifier(spreadsheet_id) or not callable(load_snapshot) or not callable(clock):raise FeedError('Trusted Sheet configuration required')
        self.spreadsheet_id=spreadsheet_id;self.load_snapshot=load_snapshot;self.clock=clock
    def snapshot(self):
        try:
            now=self.clock();source=self.load_snapshot()
            if (type(source) is not SheetSnapshot or source.spreadsheet_id!=self.spreadsheet_id or source.sheet_name!=SHEET_NAME
                    or type(source.headers) is not tuple or source.headers!=HEADERS or source.timezone!='Asia/Yekaterinburg'
                    or type(source.rows) is not tuple or len(source.rows)>10000 or type(source.complete) is not bool):
                raise FeedError('Unverified Sheet schema/identity')
            _fresh(source.observed_at,now);rows={}
            for raw in source.rows:
                if type(raw) is not tuple or len(raw)!=11:raise FeedError('Incomplete Sheet row')
                rid,created,label,chat,date,time,duration,topic,status,decision,event=raw
                if not identifier(rid) or status not in STATUSES or type(duration) is not int or duration!=20:raise FeedError('Unknown consultation row')
                label=_string(label,1000);topic=_string(topic);decision=_string(decision)
                if type(chat) is int and 0<chat<2**52:chat=str(chat)
                if type(chat) is not str or not re.fullmatch(r'[0-9]{1,20}',chat) or not 0<int(chat)<2**52:raise FeedError('Explicit private Telegram subject required')
                if event=='':event=None
                if event is not None and not identifier(event):raise FeedError('Invalid event reference')
                created=None if created in ('',None) else _moment(created)
                start=dt.datetime.combine(_day(date),_time(time),TZ)
                record=ConsultationRecord(rid,status,start,created,label,topic)
                revision=digest([source.spreadsheet_id,source.sheet_name,rid,_utc(created) if created else None,label,chat,_utc(start),duration,topic,status,decision,event])
                item=ConsultationEvidence(replace(record,source_version=revision),chat,event,decision,revision)
                if rid in rows and rows[rid]!=item:raise FeedError('Conflicting Sheet rows')
                rows[rid]=item
            _fresh(source.observed_at,self.clock())
            return ConsultationSnapshot(tuple(rows.values()),source.observed_at,source.complete)
        except Exception:raise FeedError('Consultation snapshot unavailable; verify source') from None
    def require_revision(self,booking_id,expected_revision):
        """Trusted read guard for a future preflight, not an authorization grant."""
        snapshot=self.snapshot()
        matches=[row for row in snapshot.rows if row.record.id==booking_id]
        if not snapshot.complete or len(matches)!=1 or matches[0].revision!=expected_revision:
            raise FeedError('Consultation changed or source incomplete')
        return matches[0]
    def batch(self):
        snapshot=self.snapshot()
        return ConsultationBatch(tuple(row.record for row in snapshot.rows),snapshot.observed_at,snapshot.complete)


def _calendar_events(source):
    if (type(source) is not CalendarSnapshot or not identifier(source.calendar_id) or type(source.events) is not tuple
            or len(source.events)>10000 or source.complete is not True
            or not all(aware(x) for x in (source.observed_at,source.covered_start,source.covered_end))
            or source.covered_start>=source.covered_end):raise FeedError('Verified complete Calendar snapshot required')
    items=[];ids=set()
    for raw in source.events:
        if type(raw) is not dict or not identifier(raw.get('id')) or raw['id'] in ids:raise FeedError('Missing/duplicate Calendar identity')
        # Normalized events from existing GoogleCalendarAdapter; not raw API JSON.
        start,end=_moment(raw.get('start')),_moment(raw.get('end'))
        if start>=end:raise FeedError('Invalid Calendar interval')
        ids.add(raw['id'])
        items.append(dict(id=raw['id'],start=_utc(start),end=_utc(end),title=_string(raw.get('title','')),
                          location=_string(raw.get('location','')),etag=raw.get('etag'),protected=raw.get('protected',False),
                          description=_string(raw.get('description','')),attendees=copy.deepcopy(raw.get('attendees',[]))))
    return items


def calendar_revision(source):
    events=_calendar_events(source)
    return digest([source.calendar_id,_utc(source.covered_start),_utc(source.covered_end),sorted(events,key=lambda event:event['id'])])


def read_calendar_snapshot(adapter,start,end,*,clock):
    """Explicit read via existing injected adapter; no polling or credential load.

    Real Google reads require separate authorization. Tests inject local adapters.
    Stamp BEFORE the read so a long/paginated request cannot renew stale data.
    """
    try:
        if not aware(start) or not aware(end) or end<=start or not callable(clock):raise FeedError('Invalid requested range')
        observed=clock();_fresh(observed,observed)
        events=adapter.list_events(start.isoformat(),end.isoformat())
        if type(events) is not list:raise FeedError('Invalid Calendar list')
        result=CalendarSnapshot(adapter.calendar_id,tuple(copy.deepcopy(events)),observed,start,end,True)
        _calendar_events(result);_fresh(observed,clock());return result
    except Exception:raise FeedError('Calendar snapshot unavailable; verify source') from None

class BusyFeed:
    def __init__(self,*,target_id,teaching_id,teacher_id,load_target,load_teaching,load_verification,load_bindings,clock):
        if (not all(identifier(x) for x in (target_id,teaching_id,teacher_id))
                or not all(callable(x) for x in (load_target,load_teaching,load_verification,load_bindings,clock))):raise FeedError('Explicit trusted busy sources required')
        self.target_id=target_id;self.teaching_id=teaching_id;self.teacher_id=teacher_id
        self.load_target=load_target;self.load_teaching=load_teaching;self.load_verification=load_verification;self.load_bindings=load_bindings;self.clock=clock
    def _verified(self,evidence,teaching,now):
        try:
            if (type(evidence) is not TeachingVerification or evidence.teacher_id!=self.teacher_id or evidence.calendar_id!=self.teaching_id
                    or not all(aware(x) for x in (evidence.covered_start,evidence.covered_end))
                    or evidence.covered_start>teaching.covered_start or evidence.covered_end<teaching.covered_end
                    or not identifier(evidence.source_revision) or not aware(evidence.observed_at) or not aware(evidence.source_observed_at)
                    or evidence.source_observed_at>evidence.observed_at or evidence.calendar_revision!=calendar_revision(teaching)):
                return False
            _fresh(evidence.observed_at,now);_fresh(evidence.source_observed_at,now)
            return True
        except Exception:return False
    def __call__(self):
        try:
            before=self.clock();target=copy.deepcopy(self.load_target())
            teaching=target if self.target_id==self.teaching_id else copy.deepcopy(self.load_teaching())
            target_events=_calendar_events(target);teaching_events=_calendar_events(teaching)
            if target.calendar_id!=self.target_id or teaching.calendar_id!=self.teaching_id:raise FeedError('Wrong Calendar identity')
            bindings=self.load_bindings();evidence=self.load_verification();now=self.clock()
            if not aware(before) or not aware(now) or now<before:raise FeedError('Invalid observation clock')
            _fresh(target.observed_at,now);_fresh(teaching.observed_at,now)
            if type(bindings) is not tuple or len(bindings)>10000:raise FeedError('Explicit ownership bindings required')
            owned={};requests=set()
            for binding in bindings:
                if (type(binding) is not HoldBinding or binding.calendar_id!=self.target_id
                        or not identifier(binding.event_id) or not identifier(binding.consultation_id)
                        or not aware(binding.starts_at) or not aware(binding.ends_at) or binding.ends_at<=binding.starts_at
                        or binding.event_id in owned or binding.consultation_id in requests):raise FeedError('Ambiguous hold ownership')
                owned[binding.event_id]=binding;requests.add(binding.consultation_id)
            events=[]
            for source,items in ((target,target_events),)+(() if self.target_id==self.teaching_id else ((teaching,teaching_events),)):
                for item in items:
                    start,end=_moment(item['start']),_moment(item['end']);binding=owned.get(item['id']) if source.calendar_id==self.target_id else None
                    if binding is not None and (binding.starts_at!=start or binding.ends_at!=end):raise FeedError('Owned hold changed')
                    event_id=item['id'] if source.calendar_id==self.target_id else 'external:'+digest([source.calendar_id,item['id']])
                    events.append(BusyEvent(event_id,start,end,binding.consultation_id if binding else None))
            covered_start=max(target.covered_start,teaching.covered_start);covered_end=min(target.covered_end,teaching.covered_end)
            if covered_end<=covered_start:raise FeedError('No common verified range')
            # Recheck after normalization/hashing; source age is never renewed.
            final=self.clock()
            if not aware(final) or final<now:raise FeedError('Invalid observation clock')
            _fresh(target.observed_at,final);_fresh(teaching.observed_at,final)
            complete=self._verified(evidence,teaching,final)
            stamps=[target.observed_at,teaching.observed_at]
            if complete:stamps.extend((evidence.observed_at,evidence.source_observed_at))
            return BusySnapshot(tuple(events),min(stamps),covered_start,covered_end,True,complete)
        except Exception:raise FeedError('Busy snapshot unavailable; verify source') from None
