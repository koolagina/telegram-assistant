"""Original-evidence consent registry for the LOCAL fixture workflow.

Calendar reads occur outside SQLite transactions. Publication/source claim are
atomic in the fixture source DB. This does not authenticate real resources or
create a Google claim. Only trusted verified owner interactions may call it.
"""
import copy
from dataclasses import dataclass,asdict,field
import datetime as dt
import json
import re
import secrets
from assistant_access import aware
from consultation_actions import ConsultationActions,Booking,PENDING,AGE,DURATION
from consultation_workflow import ConsultationState,WorkflowError,_bound_encode,_bound_decode
from consultation_executor import BoundPlan,event_revision,MARKER
from consultation_feed import HoldBinding
from material_versions import digest
from consultation_actions import TZ
from consultation_requests import UNAVAILABLE
from report_requests import PreparedReply,ReplyButton,_text,_bounded

@dataclass(frozen=True)
class OwnerReview:
    token: str = field(repr=False)
    booking_id: str
    action: str
    student_label: str = field(repr=False)
    topic: str = field(repr=False)
    starts_at: dt.datetime
    calendar_title: str = field(repr=False)
    expires_at: dt.datetime


def _booking_json(booking):
    data=asdict(booking);data['starts_at']=booking.starts_at.isoformat();return json.dumps(data,sort_keys=True)

def _booking_from_json(payload):
    data=json.loads(payload);data['starts_at']=dt.datetime.fromisoformat(data['starts_at']);return Booking(**data)

class ConsultationConsent:
    def __init__(self,state,actions,calendar,*,hold_bindings):
        if (type(state) is not ConsultationState or type(actions) is not ConsultationActions
                or state.owner!=actions.owner or state.namespace!=actions.namespace or state.calendar_id!=getattr(calendar,'calendar_id',None)
                or not callable(getattr(calendar,'read',None)) or not callable(hold_bindings)):raise WorkflowError('Matching local consent wiring required')
        self.state=state;self.actions=actions;self.calendar=calendar;self.hold_bindings=hold_bindings
        with self.state.transaction():
            self.state.db.execute('CREATE TABLE IF NOT EXISTS workflow_reviews(token TEXT PRIMARY KEY,request_key TEXT UNIQUE NOT NULL,booking_id TEXT NOT NULL,action TEXT NOT NULL,actor TEXT NOT NULL,core_token TEXT NOT NULL,source_revision TEXT NOT NULL,event_revision TEXT NOT NULL,booking TEXT NOT NULL,view TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL,started_at TEXT,phase TEXT NOT NULL,bound TEXT,bound_hash TEXT)')
    def _get(self,token):
        row=self.state.db.execute('SELECT token,request_key,booking_id,action,actor,core_token,source_revision,event_revision,booking,view,created_at,expires_at,started_at,phase,bound,bound_hash FROM workflow_reviews WHERE token=?',(token,)).fetchone()
        if row is None:raise WorkflowError('Review unavailable')
        names=('token','request_key','booking_id','action','actor','core_token','source_revision','event_revision','booking','view','created_at','expires_at','started_at','phase','bound','bound_hash')
        return dict(zip(names,row))
    def _view(self,row):
        data=json.loads(row['view'])
        return OwnerReview(row['token'],row['booking_id'],row['action'],data['student_label'],data['topic'],dt.datetime.fromisoformat(data['starts_at']),data['calendar_title'],dt.datetime.fromisoformat(row['expires_at']))
    def _gate(self,context,row=None):
        policy,now=self.state._auth(context);self.actions.check_access(context)
        if row is not None and row['actor']!=context.subject:raise WorkflowError('Review belongs to another authenticated actor')
        return policy,now
    def _capture(self,context,booking,action,*,source_revision=None,expected_event=None):
        policy,now=self._gate(context)
        item=self.state._item(booking.id)
        if (item.record.status!=PENDING or item.event_id!=booking.event_id or item.record.starts_at!=booking.starts_at
                or (source_revision is not None and item.revision!=source_revision)):raise WorkflowError('Reviewed source changed')
        student=policy.bindings.get(('telegram',item.chat_id))
        if (student is None or student.role!='student' or student.entity_id!=booking.student_id or student.active is not True or student.confirmed is not True
                or not policy.students[student.entity_id].active):raise WorkflowError('Reviewed identity changed')
        bindings=self.hold_bindings()
        wanted=HoldBinding(self.state.calendar_id,booking.event_id,booking.id,booking.starts_at,booking.starts_at+DURATION)
        matches=[b for b in bindings if type(b) is HoldBinding and (b.event_id==booking.event_id or b.consultation_id==booking.id)] if type(bindings) is tuple else []
        if len(matches)!=1 or matches[0]!=wanted:raise WorkflowError('Hold ownership not verified')
        actual=copy.deepcopy(self.calendar.read(booking.event_id))  # No SQLite transaction here.
        fingerprint=event_revision(actual)
        if (actual.calendar_id!=self.state.calendar_id or actual.id!=booking.event_id or actual.starts_at!=booking.starts_at
                or actual.ends_at!=booking.starts_at+DURATION or actual.protected
                or MARKER in actual.extensions.get('private',{}) or (expected_event is not None and fingerprint!=expected_event)):
            raise WorkflowError('Reviewed Calendar changed')
        self.actions._check(context,booking,action,booking.starts_at)  # Trusted LOCAL busy provider only.
        self.state.feed.require_revision(booking.id,item.revision)
        _,final=self._gate(context)
        if not aware(actual.observed_at) or not dt.timedelta(0)<=final-actual.observed_at<=AGE or final<now:raise WorkflowError('Review evidence stale')
        return item,actual,fingerprint
    def preview(self,context,booking_id,action,*,request_key):
        try:
            self._gate(context)
            if action not in ('approve','reject') or type(request_key) is not str or len(request_key)!=64 or any(c not in '0123456789abcdef' for c in request_key):raise WorkflowError('Trusted action/update key required')
            existing=self.state.db.execute('SELECT token FROM workflow_reviews WHERE request_key=?',(request_key,)).fetchone()
            if existing is not None:
                row=self._get(existing[0]);self._gate(context,row)
                if row['booking_id']!=booking_id or row['action']!=action:raise WorkflowError('Update key retargeted')
                return self._view(row)
            booking=self.actions.booking(booking_id)
            if booking.status!=PENDING:raise WorkflowError('Local booking already decided')
            item,event,fingerprint=self._capture(context,booking,action)
            with self.state.transaction():
                self._gate(context);self.state.feed.require_revision(booking.id,item.revision)
                raced=self.state.db.execute('SELECT token FROM workflow_reviews WHERE request_key=?',(request_key,)).fetchone()
                if raced is not None:
                    row=self._get(raced[0]);self._gate(context,row)
                    if row['booking_id']!=booking_id or row['action']!=action:raise WorkflowError('Update key conflict')
                    return self._view(row)
                intent=self.actions.preview(context,booking.id,action)
                view={'student_label':item.record.student_label,'topic':item.record.topic,'starts_at':booking.starts_at.isoformat(),'calendar_title':event.title}
                token=secrets.token_hex(16);_,created=self._gate(context)
                self.state.db.execute("INSERT INTO workflow_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL,'draft',NULL,NULL)",(token,request_key,booking.id,action,context.subject,intent.token,item.revision,fingerprint,_booking_json(booking),json.dumps(view,ensure_ascii=False),created.isoformat(),intent.expires_at.isoformat()))
                return OwnerReview(token,booking.id,action,item.record.student_label,item.record.topic,booking.starts_at,event.title,intent.expires_at)
        except Exception:raise WorkflowError('Review unavailable; refresh original source') from None
    def confirm(self,context,token):
        try:
            self._gate(context)
            row=self._get(token);_,now=self._gate(context,row)
            if row['phase']=='confirmed':return self.load_confirmed(token)
            if row['phase'] not in ('draft','confirming') or not dt.datetime.fromisoformat(row['created_at'])<=now<dt.datetime.fromisoformat(row['expires_at']):raise WorkflowError('Review cancelled/expired')
            # First authenticated click timestamp is durable BEFORE local core confirm.
            # It never renews on restart/retry. No Calendar call under this lock.
            with self.state.transaction():
                row=self._get(token);_,now=self._gate(context,row)
                if row['phase']=='confirmed':return self.load_confirmed(token)
                if row['phase'] not in ('draft','confirming') or now>=dt.datetime.fromisoformat(row['expires_at']):raise WorkflowError('Review expired')
                if row['started_at'] is None:self.state.db.execute("UPDATE workflow_reviews SET started_at=?,phase='confirming' WHERE token=?",(now.isoformat(),token))
            row=self._get(token);booking=_booking_from_json(row['booking'])
            self._capture(context,booking,row['action'],source_revision=row['source_revision'],expected_event=row['event_revision'])
            _,now=self._gate(context,row)
            if now>=dt.datetime.fromisoformat(row['expires_at']):raise WorkflowError('Review expired during verification')
            plan=self.actions.confirm(context,row['core_token'])  # LOCAL and idempotent; never Calendar.
            bound=BoundPlan(token,self.state.owner,self.state.calendar_id,plan,row['source_revision'],row['event_revision'],dt.datetime.fromisoformat(row['started_at']))
            with self.state.transaction():
                current=self._get(token);_,now=self._gate(context,current)
                if current['phase']=='confirmed':return self.load_confirmed(token)
                if current['phase']!='confirming' or current['started_at']!=row['started_at'] or now>=dt.datetime.fromisoformat(current['expires_at']):raise WorkflowError('Review no longer confirmable')
                self.state.feed.require_revision(booking.id,row['source_revision'])
                self.state.claim(context,bound)  # Nested savepoint: registry publication + source claim atomic.
                self.state.db.execute("UPDATE workflow_reviews SET phase='confirmed',bound=?,bound_hash=? WHERE token=?",(_bound_encode(bound),bound.fingerprint,token))
                self._gate(context,current)
            return bound
        except Exception:raise WorkflowError('Confirmation unavailable; original review required') from None
    def cancel(self,context,token):
        self._gate(context)
        row=self._get(token);self._gate(context,row)
        with self.state.transaction():
            row=self._get(token);self._gate(context,row)
            if row['phase']=='confirmed':return False
            self.state.db.execute("UPDATE workflow_reviews SET phase='cancelled' WHERE token=?",(token,))
            self.actions.cancel(context,row['core_token']);self._gate(context,row);return True
    def load_confirmed(self,plan_id):
        """Trusted registry loader only. Executor/workflow enforce current auth."""
        row=self._get(plan_id)
        if row['phase']!='confirmed' or row['bound'] is None:raise WorkflowError('Confirmed plan unavailable')
        bound=_bound_decode(row['bound'])
        if bound.id!=plan_id or bound.fingerprint!=row['bound_hash']:raise WorkflowError('Confirmed plan corrupted')
        return bound

    def reference(self,context,booking_id):
        self._gate(context);item=self.state._item(booking_id);booking=self.actions.booking(booking_id)
        self._gate(context)
        return digest([self.state.namespace,self.state.owner,item.revision,_booking_json(booking)])[:32]
    def resolve(self,context,reference):
        self._gate(context);matches=[]
        for item in self.state.feed.snapshot().rows:
            try:
                if self.reference(context,item.record.id)==reference:matches.append(item.record.id)
            except Exception:continue
        self._gate(context)
        if len(matches)!=1:raise WorkflowError('Source reference changed')
        return matches[0]
    def card(self,context,booking_id):
        try:
            self._gate(context);item=self.state._item(booking_id);booking=self.actions.booking(booking_id)
            reference=self.reference(context,booking_id)
            text=('Локальный кандидат — заявка '+_text(booking_id)+'\n'+item.record.starts_at.astimezone(TZ).strftime('%d.%m.%Y %H:%M')
                  +' · 20 минут · кабинет 317\nСтудент: '+_text(item.record.student_label)[:200]+'\nТема: '+_text(item.record.topic)[:1000]
                  +'\nСтатус источника: '+_text(item.record.status)+'\nКаждое решение требует отдельного подтверждения. Реальные ресурсы не подключены.')
            buttons=()
            if item.record.status==PENDING and booking.status==PENDING:
                buttons=((ReplyButton('Подтвердить','bcon:a:approve:'+reference),ReplyButton('Отклонить','bcon:a:reject:'+reference)),
                         (ReplyButton('Предложить время','con:p:'+self.actions.reference(context,booking_id)),))
            self._gate(context);return PreparedReply('prepared',_bounded(text),buttons=buttons)
        except Exception:return UNAVAILABLE
    def handle_callback(self,context,data,*,request_key):
        try:
            self._gate(context)
            if type(data) is not str or not data.isascii() or len(data)>64:raise WorkflowError('Unavailable')
            match=re.fullmatch(r'bcon:a:(approve|reject):([a-f0-9]{32})',data)
            if match:
                review=self.preview(context,self.resolve(context,match.group(2)),match.group(1),request_key=request_key)
                label='Подтвердить консультацию' if review.action=='approve' else 'Отклонить заявку'
                text=('Проверьте и подтвердите действие: '+label+'?\n'+review.starts_at.astimezone(TZ).strftime('%d.%m.%Y %H:%M')
                      +' · кабинет 317\nСтудент: '+_text(review.student_label)[:200]+'\nТема: '+_text(review.topic)[:1000]
                      +'\nСобытие: '+_text(review.calendar_title)[:200]+'\nКнопка действует до '+review.expires_at.astimezone(TZ).strftime('%H:%M')
                      +'.\nФиксируются именно эти исходные данные. Изменение источника потребует нового просмотра.\nЛокальный кандидат; реальные операции отключены.')
                return PreparedReply('prepared',_bounded(text),buttons=((ReplyButton('Да, подтвердить решение','bcon:c:'+review.token),ReplyButton('Назад / отменить','bcon:x:'+review.token)),))
            match=re.fullmatch(r'bcon:([cx]):([a-f0-9]{32})',data)
            if not match:raise WorkflowError('Unavailable')
            if match.group(1)=='x':
                cancelled=self.cancel(context,match.group(2))
                return PreparedReply('prepared','Подтверждение отменено; заявка и резерв не отменяются.' if cancelled else 'Решение уже подтверждено; эта кнопка не отменяет встречу.')
            self.confirm(context,match.group(2))
            return PreparedReply('prepared','Решение подтверждено локально и привязано к исходной строке и событию. Исполнение календарного этапа отдельно; реальные ресурсы не изменены.')
        except Exception:return UNAVAILABLE
