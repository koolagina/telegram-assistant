"""Consultation-only conditional mutations over existing GoogleCalendarAdapter.

No credentials/bootstrap/new HTTP transport. Tests inject local sessions. Writes
are disabled by the existing adapter by default; flags do not authorize real API
use. This is a port for trusted executor requests, never a public payload API.
"""
import copy
import datetime as dt
import re
from urllib.parse import quote
from nvsu_google import GoogleCalendarAdapter,CalendarError
from assistant_access import aware,identifier
from consultation_actions import AGE
from consultation_executor import CalendarRecord,MutationReceipt,MutationRejected,ExecutorError,MARKER,event_revision

class ConsultationCalendarPort:
    def __init__(self,adapter,*,clock):
        if type(adapter) is not GoogleCalendarAdapter or not callable(clock):raise ExecutorError('Existing verified Calendar adapter required')
        self.adapter=adapter;self.clock=clock;self.calendar_id=adapter.calendar_id
    @property
    def writes_enabled(self):return self.adapter.allow_writes is True
    def read(self,event_id):
        try:
            if not identifier(event_id):raise ExecutorError('Explicit event identity required')
            observed=self.clock()
            if not aware(observed):raise ExecutorError('Aware clock required')
            self.adapter._calendar()  # Existing identity/timezone verification.
            raw=self.adapter._request('GET','/events/'+quote(event_id,safe=''),missing_ok=True)
            final=self.clock()
            if not aware(final) or not dt.timedelta(0)<=final-observed<=AGE:raise ExecutorError('Stale Calendar read')
            if raw is None:return None
            if raw.get('id')!=event_id:raise ExecutorError('Wrong event identity')
            event=self.adapter._event(raw)
            if event is None:return None
            # Own technical properties are expected, not ownership evidence.
            # Complex calendar entities are not safe consultation hold targets.
            protected=(any(raw.get(k) for k in ('recurrence','recurringEventId','attendees','attachments','conferenceData'))
                       or 'date' in raw['start'] or 'date' in raw['end'] or raw.get('eventType','default')!='default')
            record=CalendarRecord(self.calendar_id,event_id,event.get('etag'),dt.datetime.fromisoformat(event['start']),dt.datetime.fromisoformat(event['end']),
                event['title'],event['location'],event['description'],copy.deepcopy(raw.get('extendedProperties',{})),bool(protected),observed)
            event_revision(record);return record
        except Exception:raise ExecutorError('Calendar read unavailable; verify source') from None
    def apply(self,request):
        if not self.writes_enabled:raise ExecutorError('Calendar writes disabled')
        try:
            fields={'calendar_id','method','event_id','etag','operation_id','start','end','title','location','extensions'}
            if (type(request) is not dict or set(request) not in (fields,fields|{'description'}) or request['calendar_id']!=self.calendar_id
                    or request['method'] not in ('update','delete') or not identifier(request['event_id'])
                    or type(request['etag']) is not str or not request['etag'] or len(request['etag'])>512
                    or any(ord(c)<32 for c in request['etag']) or type(request['operation_id']) is not str
                    or re.fullmatch(r'[a-f0-9]{64}',request['operation_id']) is None or type(request['extensions']) is not dict
                    or request['extensions'].get('private',{}).get(MARKER)!=request['operation_id']
                    or request['title']!='Консультация — подтверждена' or request['location']!='Кабинет 317'):
                raise ExecutorError('Invalid conditional operation')
            if 'description' in request and (request['method']!='update' or type(request['description']) is not str or len(request['description'])>20000):raise ExecutorError('Invalid reviewed description')
            start,end=dt.datetime.fromisoformat(request['start']),dt.datetime.fromisoformat(request['end'])
            if not aware(start) or not aware(end) or end-start!=dt.timedelta(minutes=20):raise ExecutorError('Invalid time proof')
            path='/events/'+quote(request['event_id'],safe='');headers={'If-Match':request['etag']};params={'sendUpdates':'none'}
            if request['method']=='delete':
                self.adapter._request('DELETE',path,params=params,headers=headers)
            else:
                # PATCH only chosen fields; no insertion or time/attendee rewrite.
                # Optional description is an exact source-bound bot prefix replacement.
                body={'summary':request['title'],'location':request['location'],'extendedProperties':copy.deepcopy(request['extensions'])}
                if 'description' in request:body['description']=request['description']
                raw=self.adapter._request('PATCH',path,params=params,headers=headers,body=body)
                event=self.adapter._event(raw)
                if (event is None or event['id']!=request['event_id'] or not event.get('etag')
                        or dt.datetime.fromisoformat(event['start'])!=start or dt.datetime.fromisoformat(event['end'])!=end
                        or event['title']!=request['title'] or event['location']!=request['location']
                        or raw.get('extendedProperties')!=request['extensions']
                        or ('description' in request and event['description']!=request['description'])):raise ExecutorError('Unexpected mutation acknowledgement')
            return MutationReceipt(self.calendar_id,request['event_id'],request['method'],request['operation_id'])
        except CalendarError as error:
            if type(error.status) is int and 400<=error.status<=499 and error.status!=408:raise MutationRejected(error.status) from None
            raise ExecutorError('Calendar outcome unknown; reconcile before further action') from None
        except MutationRejected:raise
        except Exception:raise ExecutorError('Calendar operation unavailable or uncertain') from None
