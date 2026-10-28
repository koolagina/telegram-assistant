"""Owner decision projection from fresh trusted sources; no source mutations.

Source callables/owner identity are trusted server configuration, not request
parameters. Every list/detail rechecks personal.read and academic report scope.
No sending, consultation confirmation, grade writes, snoozing or auto-resolution.
"""
from dataclasses import dataclass,field
import datetime as dt
from zoneinfo import ZoneInfo
from assistant_access import AccessPolicy,identifier,aware
from material_versions import digest

KINDS=('consultation','review','technical')
TZ=ZoneInfo('Asia/Yekaterinburg')
class DecisionError(ValueError):pass

@dataclass(frozen=True)
class DecisionItem:
    category: str
    source_id: str = field(repr=False)
    owner_id: str
    title: str = field(repr=False)
    detail: str = field(repr=False)
    created_at: dt.datetime | None
    due_at: dt.datetime | None
    priority: int
    enrollment: tuple | None = field(default=None,repr=False)
    steps: tuple = ()
    source_version: str = field(default="",repr=False)
    @property
    def identity(self):return digest([self.category,self.owner_id,self.source_id])
    @property
    def reference(self):return digest([self.identity,self.title,self.detail,self.created_at.astimezone(dt.timezone.utc).isoformat() if self.created_at else None,self.due_at.astimezone(dt.timezone.utc).isoformat() if self.due_at else None,self.priority,self.enrollment,self.steps,self.source_version])[:32]

@dataclass(frozen=True)
class DecisionSnapshot:
    items: tuple = field(repr=False)
    observed_at: dt.datetime
    complete: bool = True

@dataclass(frozen=True)
class QueueEntry:
    item: DecisionItem = field(repr=False)
    reference: str
    urgency: str

@dataclass(frozen=True)
class DecisionPage:
    day: str
    items: tuple = field(repr=False)
    counts: dict
    warnings: tuple
    page: int
    next_page: int | None
    @property
    def partial(self):return bool(self.warnings)

class DecisionQueue:
    def __init__(self,*,owner_id,policy_provider,clock,sources,max_age=dt.timedelta(minutes=5)):
        if (not identifier(owner_id) or not callable(policy_provider) or not callable(clock)
                or type(sources) is not dict or set(sources)!=set(KINDS) or not all(callable(x) for x in sources.values())
                or type(max_age) is not dt.timedelta or max_age<=dt.timedelta(0)):
            raise DecisionError('Explicit trusted decision sources required')
        self.owner_id=owner_id;self._policy=policy_provider;self._clock=clock;self.sources=dict(sources);self.max_age=max_age
    def _authorized(self,context):
        policy=self._policy();now=self._clock()
        if type(policy) is not AccessPolicy or not aware(now) or not policy.authorize(context,'personal.read',self.owner_id,now=now).allowed:
            raise DecisionError('Decision queue unavailable')
        return policy,now
    def _visible(self,item,context,policy,now):
        if item.owner_id!=self.owner_id:return False
        if item.category!='review':return True
        if type(item.enrollment) is not tuple or len(item.enrollment)!=4:return False
        enrollment=policy.enrollments.get(item.enrollment[0])
        return (enrollment is not None and (enrollment.id,enrollment.student_id,enrollment.discipline_id,enrollment.group_id)==item.enrollment
                and policy.authorize(context,'student.report',enrollment.id,now=now).allowed)
    def _collect(self,context):
        try:
            policy,now=self._authorized(context);items=[];warnings=[];observed={}
            for kind in KINDS:
                try:
                    snapshot=self.sources[kind](context,policy,now)
                    if (type(snapshot) is not DecisionSnapshot or type(snapshot.items) is not tuple or len(snapshot.items)>10000
                            or type(snapshot.complete) is not bool or not aware(snapshot.observed_at)
                            or not dt.timedelta(0)<=now-snapshot.observed_at<=self.max_age):
                        raise DecisionError('Unverified source snapshot')
                    unique={}
                    for item in snapshot.items:
                        if (type(item) is not DecisionItem or item.category!=kind or not identifier(item.source_id) or not identifier(item.owner_id)
                                or type(item.title) is not str or not item.title.strip() or len(item.title)>1000
                                or type(item.detail) is not str or len(item.detail)>20000
                                or type(item.priority) is not int or not 1<=item.priority<=3
                                or any(value is not None and not aware(value) for value in (item.created_at,item.due_at))
                                or type(item.source_version) is not str
                                or type(item.steps) is not tuple or any(type(x) is not str for x in item.steps)):
                            raise DecisionError('Invalid source item')
                        if item.identity in unique and unique[item.identity]!=item:raise DecisionError('Conflicting source copies')
                        unique[item.identity]=item
                    items.extend(unique.values())
                    observed[kind]=snapshot.observed_at
                    if not snapshot.complete:warnings.append(kind)
                except Exception:warnings.append(kind)  # Never expose exception text/URLs.
            policy,now=self._authorized(context)  # Revocation during source reads.
            expired={kind for kind,stamp in observed.items() if not dt.timedelta(0)<=now-stamp<=self.max_age}
            warnings.extend(expired)
            items=[item for item in items if item.category not in expired]
            entries=[];refs=set()
            for item in items:
                if not self._visible(item,context,policy,now):continue
                if item.reference in refs:raise DecisionError('Ambiguous decision reference')
                refs.add(item.reference)
                urgency='overdue' if item.due_at is not None and item.due_at<now else ('today' if item.due_at is not None and item.due_at.astimezone(TZ).date()==now.astimezone(TZ).date() else 'pending')
                entries.append(QueueEntry(item,item.reference,urgency))
            maximum=dt.datetime.max.replace(tzinfo=dt.timezone.utc)
            entries.sort(key=lambda entry:({'overdue':0,'today':1,'pending':2}[entry.urgency],entry.item.priority,entry.item.due_at or maximum,entry.item.created_at or maximum,entry.item.identity))
            return now,tuple(entries),tuple(sorted(set(warnings)))
        except Exception:raise DecisionError('Decision queue unavailable') from None
    def page(self,context,*,page=1,category=None):
        if type(page) is not int or not 1<=page<=1000000 or category not in (None,)+KINDS:raise DecisionError('Invalid queue view')
        now,entries,warnings=self._collect(context)
        counts={kind:sum(entry.item.category==kind for entry in entries) for kind in KINDS}
        filtered=tuple(entry for entry in entries if category is None or entry.item.category==category)
        start=(page-1)*5
        return DecisionPage(now.astimezone(TZ).date().isoformat(),filtered[start:start+5],counts,warnings,page,page+1 if start+5<len(filtered) else None)
    def detail(self,context,reference):
        _,entries,_=self._collect(context)
        matches=[entry for entry in entries if entry.reference==reference]
        if len(matches)!=1:raise DecisionError('Decision unavailable or changed; refresh queue')
        return matches[0]
