"""Google Calendar v3 adapter. Read-only by default; OAuth is loaded lazily.

All tests inject a local session. No credentials, target IDs or tokens are embedded.
Only time, discipline and room are written; stable event IDs carry no visible notes.
"""
import datetime as dt
import hashlib
from urllib.parse import quote
from zoneinfo import ZoneInfo
from nvsu_sync import event_payload,calendar_payload,same,decorated

READ_SCOPE='https://www.googleapis.com/auth/calendar.readonly'
WRITE_SCOPE='https://www.googleapis.com/auth/calendar.events'
class CalendarError(RuntimeError):
    def __init__(self,message,status=None):super().__init__(message);self.status=status

class GoogleCalendarAdapter:
    def __init__(self,calendar_id,session,*,allow_writes=False):
        if not isinstance(calendar_id,str) or not calendar_id or calendar_id.lower()=='primary' or any(ord(c)<33 for c in calendar_id):
            raise ValueError('An explicit Calendar ID is required; primary is forbidden')
        self.calendar_id=calendar_id;self.session=session;self.allow_writes=allow_writes
        self.base='https://www.googleapis.com/calendar/v3/calendars/'+quote(calendar_id,safe='')
        self.etags={};self.metadata=None
    @classmethod
    def from_adc(cls,calendar_id,*,allow_writes=False):
        # Loading credentials does not by itself prove access to the selected calendar.
        try:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as error:
            raise CalendarError('Install requirements-calendar.txt before using live Google reads') from error
        scopes=[READ_SCOPE,WRITE_SCOPE] if allow_writes else [READ_SCOPE]
        credentials,_=google.auth.default(scopes=scopes)
        return cls(calendar_id,AuthorizedSession(credentials),allow_writes=allow_writes)
    def _request(self,method,path='',*,params=None,body=None,headers=None,missing_ok=False):
        try:
            response=self.session.request(method,self.base+path,params=params or {},json=body,headers=headers or {},timeout=20)
        except Exception as error:
            # Do not expose auth objects, response bodies, target URLs or token-bearing errors.
            raise CalendarError('Calendar request failed; outcome may require reconciliation') from None
        code=response.status_code
        if code in (404,410) and missing_ok:return None
        if code not in (200,201,204):raise CalendarError('Calendar HTTP '+str(code),code)
        if code==204:return {}
        try:
            data=response.json()
            if not isinstance(data,dict):raise ValueError()
            return data
        except Exception as error:raise CalendarError('Invalid Calendar JSON response') from error
    def _calendar(self):
        if self.metadata is None:
            data=self._request('GET')
            if data.get('id')!=self.calendar_id or not data.get('timeZone'):raise CalendarError('Calendar identity/timezone not confirmed')
            try:ZoneInfo(data['timeZone'])
            except Exception as error:raise CalendarError('Unsupported Calendar timezone') from error
            self.metadata=data
        return self.metadata
    def _time(self,value):
        if 'date' in value:
            return dt.datetime.combine(dt.date.fromisoformat(value['date']),dt.time(),ZoneInfo(self._calendar()['timeZone'])).isoformat()
        text=value.get('dateTime','');parsed=dt.datetime.fromisoformat(text.replace('Z','+00:00'))
        if parsed.tzinfo is None:
            if not value.get('timeZone'):raise CalendarError('Floating Calendar time without timezone')
            parsed=parsed.replace(tzinfo=ZoneInfo(value['timeZone']))
        return parsed.isoformat()
    def _event(self,data):
        if data.get('status')=='cancelled':return None
        try:
            all_day='date' in data['start'] or 'date' in data['end']
            special=any(data.get(k) for k in ('recurringEventId','recurrence','attachments','conferenceData','extendedProperties','colorId'))
            special=special or data.get('eventType','default')!='default'
            reminders=data.get('reminders',{})
            special=special or bool(reminders.get('overrides')) or data.get('transparency','opaque')!='opaque' or data.get('visibility','default')!='default'
            result=dict(id=data['id'],etag=data.get('etag'),start=self._time(data['start']),end=self._time(data['end']),title=data.get('summary',''),location=data.get('location',''),description=data.get('description',''),attendees=data.get('attendees',[]),protected=bool(all_day or special))
            calendar_payload(result)
        except (KeyError,TypeError,ValueError) as error:raise CalendarError('Incomplete Calendar event; planning stopped') from error
        if result['etag']:self.etags[result['id']]=result['etag']
        return result
    def list_events(self,start,end):
        self._calendar();calendar_payload(dict(start=start,end=end))
        events=[];ids=set();tokens=set();token=None
        for _ in range(1000):
            params=dict(timeMin=start,timeMax=end,singleEvents='true',showDeleted='false',maxResults=2500)
            if token:params['pageToken']=token
            page=self._request('GET','/events',params=params)
            if not isinstance(page.get('items',[]),list):raise CalendarError('Invalid Calendar page')
            for raw in page.get('items',[]):
                event=self._event(raw)
                if event is None:continue
                if event['id'] in ids:raise CalendarError('Duplicate Calendar event across pages')
                ids.add(event['id']);events.append(event)
            token=page.get('nextPageToken')
            if not token:return events
            if token in tokens:raise CalendarError('Repeated Calendar page token')
            tokens.add(token)
        raise CalendarError('Calendar pagination limit exceeded')
    def get_event(self,id):
        data=self._request('GET','/events/'+quote(id,safe=''),missing_ok=True)
        if data is None:self.etags.pop(id,None);return None
        if data.get('id')!=id:raise CalendarError('Calendar event identity mismatch')
        return self._event(data)
    def _write(self):
        if not self.allow_writes:raise CalendarError('Calendar writes are disabled')
    def _body(self,payload):
        event=event_payload(payload)
        return dict(summary=event['title'],location=event['location'],start=dict(dateTime=event['start'],timeZone='Asia/Yekaterinburg'),end=dict(dateTime=event['end'],timeZone='Asia/Yekaterinburg'))
    def event_id(self,key):
        if not isinstance(key,str) or not key:raise ValueError('Stable operation key required')
        return 'nvsu'+hashlib.sha256((self.calendar_id+'\0'+key).encode()).hexdigest()
    def create_event(self,key,payload):
        self._write();id=self.event_id(key);existing=self.get_event(id)
        if existing is not None:
            if decorated(existing) or not same(existing,payload):raise CalendarError('Deterministic event ID collision; review required')
            return id
        body=dict(id=id,**self._body(payload))
        try:result=self._request('POST','/events',params={'sendUpdates':'none'},body=body)
        except CalendarError as error:
            if error.status!=409:raise
            existing=self.get_event(id)
            if existing is None or decorated(existing) or not same(existing,payload):raise CalendarError('Conflicting Calendar insert; review required')
            return id
        if result.get('id')!=id:raise CalendarError('Unexpected Calendar insert identity')
        event=self._event(result)
        if event is None or not same(event,payload):raise CalendarError('Unexpected Calendar insert result')
        return id
    def update_event(self,id,payload):
        self._write()
        if id not in self.etags:self.get_event(id)
        tag=self.etags.get(id)
        if not tag:raise CalendarError('ETag required before Calendar patch')
        result=self._request('PATCH','/events/'+quote(id,safe=''),params={'sendUpdates':'none'},body=self._body(payload),headers={'If-Match':tag})
        if result.get('id')!=id:raise CalendarError('Unexpected Calendar patch identity')
        event=self._event(result)
        if event is None or not same(event,payload):raise CalendarError('Unexpected Calendar patch result')
    def delete_event(self,id):
        self._write()
        if id not in self.etags:
            if self.get_event(id) is None:return
        tag=self.etags.get(id)
        if not tag:raise CalendarError('ETag required before Calendar delete')
        self._request('DELETE','/events/'+quote(id,safe=''),params={'sendUpdates':'none'},headers={'If-Match':tag},missing_ok=True)
        self.etags.pop(id,None)
