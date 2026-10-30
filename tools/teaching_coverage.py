"""Read-only bridge from trusted NVSU/Calendar providers to local consultations.

Providers must be authenticated/authorized application wiring, NOT public request
JSON. A 'live' field is not authentication. This module does no HTTP, credentials,
Calendar mutations, booking creation or messaging. Attestations are internal,
short-lived evidence; the caller must still enforce identity and runtime policy.
"""
import copy
from dataclasses import dataclass,field
import datetime as dt
import re
from urllib.parse import urlencode
from assistant_access import aware,identifier
from nvsu_sync import plan_sync,event_payload,same,overlap
from consultation_feed import CalendarSnapshot,TeachingVerification,calendar_revision
from consultation_actions import TZ,AGE,BusySnapshot,BusyEvent,DURATION
from material_versions import digest

class CoverageError(ValueError):pass

def _fresh(stamp,now):
    if not aware(stamp) or not aware(now) or not dt.timedelta(0)<=now-stamp<=AGE:raise CoverageError('Stale or invalid evidence')

def _date(value):
    if type(value) is not str or re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) is None:raise CoverageError('Explicit local date required')
    return dt.date.fromisoformat(value)

@dataclass(frozen=True)
class CoverageAssessment:
    status:str
    lessons:int
    matched:int
    missing:int
    ambiguous:int
    conflicts:int
    verification:TeachingVerification|None=field(default=None,repr=False)
    plan:dict=field(default_factory=dict,repr=False)
    def summary(self):
        counts={}
        for operation in self.plan.get('operations',()):
            key=operation['action'];counts[key]=counts.get(key,0)+1
        return dict(mode='read_only_teaching_coverage',status=self.status,lessons=self.lessons,matched=self.matched,
                    missing=self.missing,ambiguous=self.ambiguous,conflicts=self.conflicts,plan_actions=counts,
                    ready_for_calendar_apply=False,live_verified=False,writes=0,messages_sent=0)

class TeachingCoverageFeed:
    def __init__(self,*,teacher_id,lecturer_id,teacher_name,calendar_id,load_source,load_calendar,clock,load_bindings=lambda:()):
        if (not all(identifier(x) for x in (teacher_id,calendar_id)) or calendar_id.lower()=='primary'
                or type(lecturer_id) is not str or re.fullmatch(r'[1-9][0-9]*',lecturer_id) is None
                or type(teacher_name) is not str or not teacher_name.strip()
                or not all(callable(x) for x in (load_source,load_calendar,clock,load_bindings))):raise CoverageError('Trusted explicit providers required')
        self.teacher_id=teacher_id;self.lecturer_id=lecturer_id;self.teacher_name=teacher_name;self.calendar_id=calendar_id
        self.source=load_source;self.calendar=load_calendar;self.clock=clock;self.bindings=load_bindings
    def assess(self,requested_date):
        try:
            before=self.clock();_fresh(before,before);date=_date(requested_date)
            start=dt.datetime.combine(date-dt.timedelta(days=date.weekday()),dt.time(),TZ);end=start+dt.timedelta(days=7)
            source=copy.deepcopy(self.source(requested_date));calendar=copy.deepcopy(self.calendar(start,end));bindings=copy.deepcopy(self.bindings())
            now=self.clock()
            if not aware(now) or now<before:raise CoverageError('Invalid observation clock')
            keys={'mode','fetched_at','url','raw_sha256','lecturer_id','teacher_name','week'}
            expected_url='https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/'+self.lecturer_id+'//0/?'+urlencode({'date':start.strftime('%d_%m_%Y')})
            if (type(source) is not dict or set(source)!=keys or source['mode'] not in ('live','fixture')
                    or source['lecturer_id']!=self.lecturer_id or source['teacher_name']!=self.teacher_name or source['url']!=expected_url
                    or type(source['raw_sha256']) is not str or re.fullmatch(r'[a-f0-9]{64}',source['raw_sha256']) is None):raise CoverageError('Source identity changed')
            observed=dt.datetime.fromisoformat(source['fetched_at']);_fresh(observed,now)
            if (type(calendar) is not CalendarSnapshot or calendar.calendar_id!=self.calendar_id
                    or calendar.covered_start!=start or calendar.covered_end!=end or calendar.complete is not True):raise CoverageError('Exact complete Calendar week required')
            _fresh(calendar.observed_at,now);revision=calendar_revision(calendar)
            week=source['week']
            if type(week) is not dict or type(week.get('lessons')) is not list or len(week['lessons'])>1000:raise CoverageError('Invalid source week')
            if week.get('status')=='parsed' and not week['lessons']:raise CoverageError('Empty source needs explicit no-schedule evidence')
            if type(bindings) is not tuple or len(bindings)>10000:raise CoverageError('Explicit ownership ledger required')
            plan=plan_sync(week,list(calendar.events),list(bindings),requested_date=requested_date)
            lessons=[]
            for lesson in week['lessons']:
                payload=event_payload(lesson)
                if not any(same(payload,other) for other in lessons):lessons.append(payload)
            matched=missing=ambiguous=conflicts=0
            for i,lesson in enumerate(lessons):
                matches=[event for event in calendar.events if same(event,lesson)]
                if len(matches)==1:matched+=1
                elif not matches:missing+=1
                else:ambiguous+=1
                if any(j!=i and overlap(lesson,other) for j,other in enumerate(lessons)):conflicts+=1
                if len(matches)==1 and any(event['id']!=matches[0]['id'] and overlap(event,lesson) for event in calendar.events):conflicts+=1
            status='review_required' if ambiguous or conflicts else 'import_required' if missing else 'fixture_only' if source['mode']=='fixture' else 'verified'
            verification=None
            final=self.clock()
            if not aware(final) or final<now:raise CoverageError('Invalid observation clock')
            _fresh(observed,final);_fresh(calendar.observed_at,final)
            if status=='verified':
                verification=TeachingVerification(self.teacher_id,self.calendar_id,start,end,final,observed,
                    digest([self.teacher_id,self.lecturer_id,source['raw_sha256'],week]),revision)
            return CoverageAssessment(status,len(lessons),matched,missing,ambiguous,conflicts,verification,plan)
        except Exception:raise CoverageError('Teaching coverage unavailable; verify current sources') from None

@dataclass(frozen=True)
class SlotPreview:
    status:str
    starts:tuple
    duration_minutes:int=20
    room:str='Кабинет 317'
    live_booking_enabled:bool=False

def preview_consultation_slots(snapshot,requested_date,*,now):
    """Internal preview only. Caller authorizes the user; no holds or sends here."""
    try:
        date=_date(requested_date);_fresh(now,now)
        if type(snapshot) is not BusySnapshot:raise CoverageError('Busy snapshot required')
        if snapshot.complete is not True or snapshot.teaching_complete is not True:return SlotPreview('blocked',())
        _fresh(snapshot.observed_at,now)
        lower=dt.datetime.combine(date,dt.time(9),TZ);upper=dt.datetime.combine(date,dt.time(18),TZ)
        if (not aware(snapshot.covered_start) or not aware(snapshot.covered_end) or snapshot.covered_start>lower or snapshot.covered_end<upper):raise CoverageError('Incomplete busy coverage')
        if type(snapshot.events) is not tuple or len(snapshot.events)>10000:raise CoverageError('Bounded busy events required')
        ids=set()
        for event in snapshot.events:
            if (type(event) is not BusyEvent or not identifier(event.id) or event.id in ids or not aware(event.starts_at)
                    or not aware(event.ends_at) or event.ends_at<=event.starts_at):raise CoverageError('Invalid busy event')
            ids.add(event.id)
        if date.weekday()>4:return SlotPreview('ready',())
        lunch_start=dt.datetime.combine(date,dt.time(11,40),TZ);lunch_end=dt.datetime.combine(date,dt.time(12,20),TZ)
        values=[];start=lower
        while start+DURATION<=upper:
            end=start+DURATION
            if (start>=now+dt.timedelta(minutes=30) and not(start<lunch_end and end>lunch_start)
                    and not any(event.starts_at<end and event.ends_at>start for event in snapshot.events)):values.append(start)
            start+=DURATION
        return SlotPreview('ready',tuple(values))
    except Exception:raise CoverageError('Consultation preview unavailable; verify busy coverage') from None

def teaching_guard_payload(assessment,*,owner_chat_id):
    """Internal adapter contract; never expose an attestation minting endpoint.

    owner_chat_id must come from the confirmed teacher/account registry, not UI
    input. This is serialization, not authentication or a live deployment.
    """
    if type(assessment) is not CoverageAssessment:raise CoverageError('Coverage assessment required')
    if assessment.status!='verified' or type(assessment.verification) is not TeachingVerification:return None
    if type(owner_chat_id) is not str or re.fullmatch(r'[1-9][0-9]{0,15}',owner_chat_id) is None or int(owner_chat_id)>=2**52:raise CoverageError('Confirmed owner binding required')
    v=assessment.verification
    return dict(version=1,owner_chat_id=owner_chat_id,calendar_id=v.calendar_id,covered_start=v.covered_start.isoformat(),covered_end=v.covered_end.isoformat(),
                observed_at=v.observed_at.isoformat(),source_observed_at=v.source_observed_at.isoformat(),source_revision=v.source_revision,calendar_revision=v.calendar_revision)
