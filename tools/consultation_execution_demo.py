"""Calendar-stage demo: synthetic Sheet, fake HTTP session, temporary SQLite.

No real Calendar API, credentials, source writes, messages or installed bot.
Original evidence binding below is explicitly synthetic, not live provisioning.
"""
import copy
import datetime as dt
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from assistant_demo import synthetic_policy
from assistant_access import Context
from decision_demo import DEMO_NOW
from consultation_actions import Booking,BusySnapshot,BusyEvent,ConsultationActions
from consultation_feed import HEADERS,SheetSnapshot,ConsultationFeed,HoldBinding
from consultation_executor import BoundPlan,ConsultationExecutor,event_revision
from consultation_calendar import ConsultationCalendarPort
from nvsu_google import GoogleCalendarAdapter

class FakeResponse:
    def __init__(self,status,data):self.status_code=status;self.data=data
    def json(self):return copy.deepcopy(self.data)

class FakeSession:
    def __init__(self,start):
        self.patches=0
        self.event={'id':'synthetic-hold','etag':'"v1"','summary':'Synthetic pending','location':'Кабинет 317','description':'Synthetic note',
                    'start':{'dateTime':start.isoformat()},'end':{'dateTime':(start+dt.timedelta(minutes=20)).isoformat()}}
    def request(self,method,url,**kwargs):
        path=urlsplit(url).path
        if method=='GET' and path.endswith('/calendars/synthetic-calendar'):
            return FakeResponse(200,{'id':'synthetic-calendar','timeZone':'Asia/Yekaterinburg'})
        if method=='GET' and path.endswith('/events/synthetic-hold'):return FakeResponse(200,self.event)
        if method=='PATCH' and path.endswith('/events/synthetic-hold'):
            if kwargs['headers'].get('If-Match')!=self.event['etag']:return FakeResponse(412,{})
            self.patches+=1;self.event.update(copy.deepcopy(kwargs['json']));self.event['etag']='"v2"'
            raise TimeoutError('synthetic accepted then response lost')
        raise AssertionError('Unexpected fake request')


def run_execution_demo():
    now=DEMO_NOW+dt.timedelta(hours=1);start=now+dt.timedelta(hours=1)
    context=Context('telegram','101',authenticated=True,private=True,sender='101')
    row=('synthetic-request',now,'Synthetic student','103',start.date().isoformat(),start.strftime('%H:%M'),20,'Synthetic topic','Ожидает решения','','synthetic-hold')
    snapshot=SheetSnapshot('synthetic-sheet','Заявки на консультации',HEADERS,(row,),now,True,'Asia/Yekaterinburg')
    source=ConsultationFeed(spreadsheet_id='synthetic-sheet',load_snapshot=lambda:snapshot,clock=lambda:now)
    busy=lambda:BusySnapshot((BusyEvent('synthetic-hold',start,start+dt.timedelta(minutes=20),'synthetic-request'),),now,start.replace(hour=0),start.replace(hour=23),True,True)
    binding=(HoldBinding('synthetic-calendar','synthetic-hold','synthetic-request',start,start+dt.timedelta(minutes=20)),)
    session=FakeSession(start)
    # allow_writes operates only on this local FakeSession, never a Google transport.
    calendar=ConsultationCalendarPort(GoogleCalendarAdapter('synthetic-calendar',session,allow_writes=True),clock=lambda:now)
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        actions=ConsultationActions(root/'actions.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=synthetic_policy,
            clock=lambda:now,calendar_snapshot=busy,student_eligible=lambda *args:True)
        try:
            actions.add(Booking('synthetic-request','student-a',start,'synthetic-hold'))
            original_source=source.snapshot().rows[0].revision;original_event=event_revision(calendar.read('synthetic-hold'))
            intent=actions.preview(context,'synthetic-request','approve');plan=actions.confirm(context,intent.token)
            bound=BoundPlan('synthetic-plan','owner','synthetic-calendar',plan,original_source,original_event,now)
            executor=ConsultationExecutor(root/'execution.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=synthetic_policy,
                clock=lambda:now,load_plan=lambda plan_id:bound,source=source,busy_snapshot=busy,hold_bindings=lambda:binding,calendar=calendar)
            try:
                first=executor.execute(context,bound.id,execution_enabled=True)
                repeated=executor.execute(context,bound.id,execution_enabled=True)
                recovered=executor.reconcile(context,bound.id)
                after=executor.execute(context,bound.id,execution_enabled=True)
                if session.patches!=1 or first['status']!='unknown' or recovered['status']!='calendar_reconciled_present' or recovered!=after:
                    raise RuntimeError('Synthetic Calendar recovery failed')
                return '\n'.join(['# Исполнение календарного этапа — только искусственные данные','',
                    'Первый ответ после принятого mock PATCH: '+first['status']+'.',
                    'Повторный запуск: '+repeated['status']+'; дополнительного PATCH нет.',
                    'Read-only сверка метки и состояния: '+recovered['status']+'.',
                    'Всего mock PATCH: '+str(session.patches)+'; ID события, время и заметка сохранены.',
                    'Статус источника: '+recovered['source_status']+'; уведомления: '+recovered['notifications']+'.',
                    'Реальных HTTP-запросов, событий, изменений таблицы и сообщений: 0.',
                    'Это проверка отдельного календарного этапа, не завершённая Google/Telegram интеграция.'])+'\n'
            finally:executor.close()
        finally:actions.close()

if __name__=='__main__':print(run_execution_demo(),end='')
