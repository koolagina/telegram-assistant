"""LOCAL fixture CAS/claim + status/outbox workflow. Not a Google Sheet adapter.

Only synthetic rows belong in this SQLite backend. All cooperating local writers
respect claims; this does NOT lock real Sheets/Calendar or arbitrary manual SQL.
Defaults off, no credentials, polling, live bootstrap or implicit sends. A future
real backend must implement equivalent claim/CAS guarantees before live use.
"""
import contextlib
from dataclasses import asdict
import datetime as dt
import json
import os
import secrets
from pathlib import Path
import sqlite3
from assistant_access import AccessPolicy,aware,identifier
from consultation_actions import TZ
from consultation_feed import HEADERS,SHEET_NAME,SheetSnapshot,ConsultationFeed
from consultation_executor import ConsultationExecutor,BoundPlan,ExecutionEvidence
from material_versions import digest
from report_requests import _text,_bounded

class WorkflowError(ValueError):pass


def _id(value):return type(value) is int and 0<value<2**52

def _bound_encode(bound):
    data=asdict(bound);data['confirmed_at']=bound.confirmed_at.isoformat()
    return json.dumps(data,ensure_ascii=False,sort_keys=True,allow_nan=False)

def _bound_decode(payload):
    data=json.loads(payload);data['confirmed_at']=dt.datetime.fromisoformat(data['confirmed_at']);return BoundPlan(**data)

class ConsultationState:
    def __init__(self,path,*,namespace,owner_id,calendar_id,spreadsheet_id,bot_id,policy_provider,clock):
        if (not all(identifier(x) for x in (namespace,owner_id,calendar_id,spreadsheet_id)) or calendar_id.lower()=='primary'
                or not _id(bot_id) or not callable(policy_provider) or not callable(clock)):raise WorkflowError('Explicit local workflow wiring required')
        self.namespace=namespace;self.owner=owner_id;self.calendar_id=calendar_id;self.spreadsheet_id=spreadsheet_id
        self.bot_id=bot_id;self.policy=policy_provider;self.clock=clock
        path=Path(path).absolute()
        if path.is_symlink() or path.parent.is_symlink():raise WorkflowError('State symlinks forbidden')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.parent.stat().st_mode & 0o077:raise WorkflowError('Private directory required')
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        if path.stat().st_mode & 0o077:raise WorkflowError('Private state file required')
        self.db=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            tables={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            base={'workflow_meta','workflow_rows','workflow_claims','workflow_notices'}
            if tables and tables not in (base,base|{'workflow_reviews'}):raise WorkflowError('Foreign state')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS workflow_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS workflow_rows(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS workflow_claims(plan_id TEXT PRIMARY KEY,booking_id TEXT UNIQUE NOT NULL,plan_hash TEXT NOT NULL,bound TEXT NOT NULL,source_revision TEXT NOT NULL,owner_subject TEXT NOT NULL,student_subject TEXT NOT NULL,student_id TEXT NOT NULL,stage TEXT NOT NULL,calendar_status TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS workflow_notices(key TEXT PRIMARY KEY,plan_id TEXT NOT NULL,kind TEXT NOT NULL,entity_id TEXT NOT NULL,subject TEXT NOT NULL,text TEXT NOT NULL,row_revision TEXT NOT NULL,phase TEXT NOT NULL,payload_hash TEXT,message_id INTEGER,error_code INTEGER,UNIQUE(plan_id,kind))')
                expected={'version':'1','namespace':namespace,'owner':owner_id,'calendar':calendar_id,'source':spreadsheet_id,'bot_id':str(bot_id)}
                metadata=dict(self.db.execute('SELECT key,value FROM workflow_meta'))
                if not metadata and not tables:self.db.executemany('INSERT INTO workflow_meta VALUES(?,?)',expected.items())
                elif metadata!=expected:raise WorkflowError('Workflow resource mismatch')
        except Exception:
            self.db.close();raise WorkflowError('Local workflow state unavailable') from None
        self.feed=ConsultationFeed(spreadsheet_id=spreadsheet_id,load_snapshot=self.snapshot,clock=clock)
    def close(self):self.db.close()
    @contextlib.contextmanager
    def transaction(self):
        nested=self.db.in_transaction;name='workflow_'+secrets.token_hex(8)
        self.db.execute('SAVEPOINT '+name if nested else 'BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('RELEASE SAVEPOINT '+name if nested else 'COMMIT')
        except BaseException:
            if nested:
                self.db.execute('ROLLBACK TO SAVEPOINT '+name);self.db.execute('RELEASE SAVEPOINT '+name)
            else:self.db.execute('ROLLBACK')
            raise
    def _auth(self,context):
        policy=self.policy();now=self.clock()
        if type(policy) is not AccessPolicy or not aware(now) or not policy.authorize(context,'personal.read',self.owner,now=now).allowed:raise WorkflowError('Workflow unavailable')
        return policy,now
    def snapshot(self):
        """Trusted private fixture source; no public read endpoint or real export."""
        observed=self.clock()
        rows=tuple(tuple(json.loads(r[0])) for r in self.db.execute('SELECT payload FROM workflow_rows ORDER BY id'))
        return SheetSnapshot(self.spreadsheet_id,SHEET_NAME,HEADERS,rows,observed,True,'Asia/Yekaterinburg')
    def _canonical(self,row):
        sample=SheetSnapshot(self.spreadsheet_id,SHEET_NAME,HEADERS,(tuple(row),),self.clock(),True,'Asia/Yekaterinburg')
        feed=ConsultationFeed(spreadsheet_id=self.spreadsheet_id,load_snapshot=lambda:sample,clock=self.clock)
        item=feed.snapshot().rows[0];record=item.record
        return (record.id,record.created_at.isoformat() if record.created_at else '',record.student_label,item.chat_id,
                record.starts_at.astimezone(TZ).date().isoformat(),record.starts_at.astimezone(TZ).strftime('%H:%M'),20,record.topic,record.status,item.decision,item.event_id or '')
    def seed(self,row):
        """Trusted fixture ingestion only, not a real data import/admin endpoint."""
        try:
            row=self._canonical(row);payload=json.dumps(row,ensure_ascii=False)
            with self.transaction():
                existing=self.db.execute('SELECT payload FROM workflow_rows WHERE id=?',(row[0],)).fetchone()
                if existing is not None and existing[0]!=payload:raise WorkflowError('Conflicting fixture')
                if existing is None:self.db.execute('INSERT INTO workflow_rows VALUES(?,?)',(row[0],payload))
        except Exception:raise WorkflowError('Invalid local source fixture') from None
    def _item(self,booking_id):
        rows=[row for row in self.feed.snapshot().rows if row.record.id==booking_id]
        if len(rows)!=1:raise WorkflowError('Source row unavailable')
        return rows[0]
    def edit(self,context,booking_id,expected_revision,row):
        """Cooperating local writer: CAS + claim exclusion, not real Sheets CAS."""
        self._auth(context)
        try:
            updated=self._canonical(row)
            if updated[0]!=booking_id:raise WorkflowError('Identity cannot change')
            with self.transaction():
                self._auth(context);current=self._item(booking_id)
                if current.revision!=expected_revision or self.db.execute('SELECT 1 FROM workflow_claims WHERE booking_id=?',(booking_id,)).fetchone():raise WorkflowError('Claimed or changed source row')
                self.db.execute('UPDATE workflow_rows SET payload=? WHERE id=?',(json.dumps(updated,ensure_ascii=False),booking_id));self._auth(context)
        except Exception:raise WorkflowError('Source edit rejected') from None
    def claimed(self,context,plan_id):
        self._auth(context);row=self.db.execute('SELECT bound,plan_hash FROM workflow_claims WHERE plan_id=?',(plan_id,)).fetchone()
        if row is None:return None
        bound=_bound_decode(row[0])
        if bound.fingerprint!=row[1]:raise WorkflowError('Claim corrupted')
        self._auth(context);return bound
    def claim(self,context,bound):
        self._auth(context)
        try:
            if type(bound) is not BoundPlan or bound.owner_id!=self.owner or bound.calendar_id!=self.calendar_id:raise WorkflowError('Bound decision required')
            with self.transaction():
                policy,_=self._auth(context);existing=self.claimed(context,bound.id)
                if existing is not None:
                    if existing.fingerprint!=bound.fingerprint:raise WorkflowError('Decision ID reused')
                    return
                booking_id=bound.plan['booking_id'];item=self._item(booking_id)
                if item.revision!=bound.source_revision or item.record.status!='Ожидает решения':raise WorkflowError('Source decision changed')
                student=policy.bindings.get(('telegram',item.chat_id))
                if (student is None or student.role!='student' or student.active is not True or student.confirmed is not True
                        or not policy.students[student.entity_id].active):raise WorkflowError('Student binding unavailable')
                if bound.plan.get('notifications')!=[{'recipient_kind':'student','recipient_id':student.entity_id},{'recipient_kind':'owner','recipient_id':self.owner}]:raise WorkflowError('Decision recipient changed')
                self.db.execute("INSERT INTO workflow_claims VALUES(?,?,?,?,?,?,?,?,'claimed','not_attempted')",(bound.id,booking_id,bound.fingerprint,_bound_encode(bound),bound.source_revision,context.subject,item.chat_id,student.entity_id))
                self._auth(context)
        except Exception:raise WorkflowError('Source claim unavailable') from None
    def note_calendar(self,context,evidence):
        """Persist the observed stage, never an invented source success flag."""
        self._auth(context)
        if type(evidence) is not ExecutionEvidence or evidence.calendar_id!=self.calendar_id:raise WorkflowError('Journal evidence required')
        with self.transaction():
            self._auth(context)
            row=self.db.execute('SELECT plan_hash,stage FROM workflow_claims WHERE plan_id=?',(evidence.plan_id,)).fetchone()
            if row is None or row[0]!=evidence.plan_hash:raise WorkflowError('Calendar evidence mismatch')
            if row[1]!='finalized':self.db.execute('UPDATE workflow_claims SET calendar_status=? WHERE plan_id=?',(evidence.status,evidence.plan_id))
            self._auth(context)
    def finalize(self,context,evidence):
        self._auth(context)
        try:
            if type(evidence) is not ExecutionEvidence or evidence.calendar_id!=self.calendar_id:raise WorkflowError('Calendar journal evidence required')
            with self.transaction():
                self._auth(context)
                claim=self.db.execute('SELECT booking_id,plan_hash,bound,source_revision,owner_subject,student_subject,student_id,stage FROM workflow_claims WHERE plan_id=?',(evidence.plan_id,)).fetchone()
                if claim is None or evidence.plan_hash!=claim[1]:raise WorkflowError('Calendar evidence mismatch')
                bound=_bound_decode(claim[2]);action=bound.plan['action']
                if bound.fingerprint!=claim[1]:raise WorkflowError('Claim evidence corrupted')
                good={'approve':{'calendar_api_confirmed','calendar_reconciled_present'},'reject':{'calendar_api_confirmed','calendar_reconciled_absent'}}
                if (action not in good or evidence.status not in good[action] or evidence.request['event_id']!=bound.plan['calendar']['event_id']
                        or evidence.request['method']!=('update' if action=='approve' else 'delete')):raise WorkflowError('Calendar stage not settled')
                if claim[7]=='finalized':return self.status(context,evidence.plan_id)
                item=self._item(claim[0])
                if (item.revision!=claim[3] or item.record.status!='Ожидает решения' or item.chat_id!=claim[5]
                        or bound.plan['notifications']!=[{'recipient_kind':'student','recipient_id':claim[6]},{'recipient_kind':'owner','recipient_id':self.owner}]
                        or evidence.request['operation_id']!=digest([self.namespace,self.calendar_id,bound.id,bound.fingerprint])):raise WorkflowError('Claimed source changed')
                raw=list(json.loads(self.db.execute('SELECT payload FROM workflow_rows WHERE id=?',(claim[0],)).fetchone()[0]))
                raw[8]='Подтверждена' if action=='approve' else 'Отклонена'
                if not raw[9]:raw[9]='Подтверждена владельцем' if action=='approve' else 'Отклонена преподавателем'
                self.db.execute('UPDATE workflow_rows SET payload=? WHERE id=?',(json.dumps(raw,ensure_ascii=False),claim[0]))
                revision=self._item(claim[0]).revision
                base='Заявка '+_text(claim[0])+': '+raw[8]+'.\n'+item.record.starts_at.astimezone(TZ).strftime('%d.%m.%Y %H:%M')+' · 20 минут · кабинет 317.'
                for kind,entity,subject in (('student',claim[6],claim[5]),('owner',self.owner,claim[4])):
                    text=_bounded(base+('\nСтудент: '+_text(item.record.student_label) if kind=='owner' else '')+'\n'+_text(raw[9]))
                    key=digest([self.namespace,evidence.plan_id,kind,entity])
                    self.db.execute("INSERT INTO workflow_notices VALUES(?,?,?,?,?,?,?,'ready',NULL,NULL,NULL)",(key,evidence.plan_id,kind,entity,subject,text,revision))
                self.db.execute("UPDATE workflow_claims SET stage='finalized',calendar_status=? WHERE plan_id=?",(evidence.status,evidence.plan_id));self._auth(context)
            return self.status(context,evidence.plan_id)
        except Exception:raise WorkflowError('Source finalization unavailable; no Calendar retry') from None
    def status(self,context,plan_id):
        self._auth(context);row=self.db.execute('SELECT stage,calendar_status,booking_id FROM workflow_claims WHERE plan_id=?',(plan_id,)).fetchone()
        if row is None:return {'stage':'not_started','source_status':'not_written','calendar':'not_attempted'}
        result={'stage':row[0],'calendar':row[1],'source_status':self._item(row[2]).record.status}
        self._auth(context);return result
    def _notice_result(self,key):
        row=self.db.execute('SELECT kind,phase,message_id,error_code FROM workflow_notices WHERE key=?',(key,)).fetchone()
        if row is None:raise WorkflowError('Notice unavailable')
        return {'kind':row[0],'status':'inflight_or_unknown' if row[1]=='sending' else row[1],'api_message_id':row[2],'api_error_code':row[3],'delivered':None}
    def notice_status(self,context,plan_id):
        self._auth(context);keys=self.db.execute("SELECT key FROM workflow_notices WHERE plan_id=? ORDER BY CASE kind WHEN 'student' THEN 0 ELSE 1 END",(plan_id,)).fetchall()
        result=tuple(self._notice_result(row[0]) for row in keys);self._auth(context);return result
    def _notice_allowed(self,context,row):
        policy,_=self._auth(context);kind,entity,subject,text,revision,phase,plan_id=row
        claim=self.db.execute('SELECT booking_id,stage FROM workflow_claims WHERE plan_id=?',(plan_id,)).fetchone()
        if claim is None or claim[1]!='finalized' or self._item(claim[0]).revision!=revision:return False
        binding=policy.bindings.get(('telegram',subject));role='student' if kind=='student' else 'teacher'
        entities=policy.students if role=='student' else policy.teachers
        return (binding is not None and binding.role==role and binding.entity_id==entity and binding.confirmed is True
                and binding.active is True and entity in entities and entities[entity].active is True and subject.isascii() and subject.isdecimal() and _id(int(subject)))
    def _notice_finish(self,key,phase,message=None,error=None):
        with self.transaction():
            self.db.execute("UPDATE workflow_notices SET phase=?,message_id=?,error_code=? WHERE key=? AND phase='sending'",(phase,message,error,key))
        return self._notice_result(key)
    def _send_notice(self,context,key,send):
        with self.transaction():
            self._auth(context)
            row=self.db.execute('SELECT kind,entity_id,subject,text,row_revision,phase,plan_id FROM workflow_notices WHERE key=?',(key,)).fetchone()
            if row is None:raise WorkflowError('Notice unavailable')
            if row[5]!='ready':return self._notice_result(key)
            if not self._notice_allowed(context,row):
                self.db.execute("UPDATE workflow_notices SET phase='cancelled' WHERE key=?",(key,));return self._notice_result(key)
            payload={'chat_id':int(row[2]),'text':row[3],'link_preview_options':{'is_disabled':True}}
            self.db.execute("UPDATE workflow_notices SET phase='sending',payload_hash=? WHERE key=?",(digest(payload),key))
        # Durable per-business-key claim before send; NEVER call Calendar here.
        if not self._notice_allowed(context,row):return self._notice_finish(key,'cancelled')
        phase='unknown';message=None;error=None
        try:
            response=send('sendMessage',payload)
            if type(response) is dict and response.get('ok') is False and type(response.get('error_code')) is int and 100<=response['error_code']<=599:
                phase='api_rejected';error=response['error_code']
            elif type(response) is dict and response.get('ok') is True:
                result=response.get('result')
                if (type(result) is dict and _id(result.get('message_id')) and type(result.get('chat')) is dict
                        and type(result['chat'].get('id')) is int and result['chat'].get('id')==payload['chat_id'] and result['chat'].get('type')=='private'
                        and type(result.get('from')) is dict and type(result['from'].get('id')) is int and result['from'].get('id')==self.bot_id and result['from'].get('is_bot') is True):
                    phase='api_confirmed';message=result['message_id']
        except Exception:pass
        return self._notice_finish(key,phase,message,error)
    def notify(self,context,plan_id,*,send,notifications_enabled=False):
        if notifications_enabled is not True or not callable(send):raise WorkflowError('Notifications disabled')
        self._auth(context)
        keys=self.db.execute("SELECT key,kind FROM workflow_notices WHERE plan_id=? ORDER BY CASE kind WHEN 'student' THEN 0 ELSE 1 END",(plan_id,)).fetchall()
        results=[]
        for key,kind in keys:
            self._auth(context)
            try:results.append(self._send_notice(context,key,send))
            except Exception:results.append({'kind':kind,'status':'needs_recovery','delivered':None})
        self._auth(context);return tuple(results)

class ConsultationWorkflow:
    def __init__(self,state,executor):
        if (type(state) is not ConsultationState or type(executor) is not ConsultationExecutor or executor.source is not state.feed
                or executor.owner!=state.owner or executor.namespace!=state.namespace or executor.calendar.calendar_id!=state.calendar_id):raise WorkflowError('Matching local source and Calendar stages required')
        self.state=state;self.executor=executor
    def advance(self,context,plan_id,*,workflow_enabled=False):
        if workflow_enabled is not True or getattr(self.executor.calendar,'writes_enabled',False) is not True:raise WorkflowError('Workflow disabled')
        self.state._auth(context)
        try:
            bound=self.state.claimed(context,plan_id)
            if bound is None:
                bound=self.executor.prepare(context,plan_id);self.state.claim(context,bound)
            elif bound.fingerprint!=self.executor.load_plan(plan_id).fingerprint:raise WorkflowError('Registered decision changed')
            if self.state.status(context,plan_id)['stage']=='finalized':return self.state.status(context,plan_id)
            outcome=self.executor.execute(context,plan_id,execution_enabled=True)
            evidence=self.executor.evidence(context,plan_id);self.state.note_calendar(context,evidence)
            if evidence.status in ('calendar_api_confirmed','calendar_reconciled_present','calendar_reconciled_absent'):
                return self.state.finalize(context,evidence)
            stage='review_required' if outcome['status'] in ('calendar_rejected','blocked_preflight','needs_recovery') else 'calendar_pending'
            return {'stage':stage,'calendar':outcome['status'],'source_status':'not_written'}
        except Exception:raise WorkflowError('Workflow requires recovery; do not retry Calendar blindly') from None
    def reconcile(self,context,plan_id,*,workflow_enabled=False):
        if workflow_enabled is not True:raise WorkflowError('Workflow reconciliation disabled')
        self.state._auth(context)
        try:
            if self.state.claimed(context,plan_id) is None:raise WorkflowError('Source claim missing')
            outcome=self.executor.reconcile(context,plan_id)
            evidence=self.executor.evidence(context,plan_id);self.state.note_calendar(context,evidence)
            if evidence.status in ('calendar_api_confirmed','calendar_reconciled_present','calendar_reconciled_absent'):
                return self.state.finalize(context,evidence)
            stage='review_required' if outcome['status'] in ('calendar_rejected','blocked_preflight','needs_recovery') else 'calendar_pending'
            return {'stage':stage,'calendar':outcome['status'],'source_status':'not_written'}
        except Exception:raise WorkflowError('Workflow reconciliation requires review') from None
