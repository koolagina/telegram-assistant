"""Offline initial decision → Calendar uncertainty → CAS/outbox recovery demo.

All source/identity/completeness/consent data are synthetic. Private local source
is SQLite, HTTP is an injected FakeSession, messages are a local mock function.
"""
import datetime as dt
from pathlib import Path
import tempfile
from assistant_access import Context
from assistant_demo import synthetic_policy
from decision_demo import DEMO_NOW
from consultation_actions import Booking,BusyEvent,BusySnapshot,ConsultationActions
from consultation_feed import HoldBinding
from consultation_executor import BoundPlan,ConsultationExecutor,event_revision
from consultation_calendar import ConsultationCalendarPort
from consultation_execution_demo import FakeSession
from consultation_workflow import ConsultationState,ConsultationWorkflow
from nvsu_google import GoogleCalendarAdapter


def run_workflow_demo():
    now=DEMO_NOW+dt.timedelta(hours=1);start=now+dt.timedelta(hours=1)
    context=Context('telegram','101',authenticated=True,private=True,sender='101')
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);state=ConsultationState(root/'source.sqlite3',namespace='synthetic',owner_id='owner',calendar_id='synthetic-calendar',spreadsheet_id='synthetic-sheet',bot_id=9001,policy_provider=synthetic_policy,clock=lambda:now)
        actions=None;executor=None
        try:
            state.seed(('synthetic-request',now,'Synthetic student','103',start.date().isoformat(),start.strftime('%H:%M'),20,'Synthetic topic','Ожидает решения','','synthetic-hold'))
            # TRUE here is an explicitly synthetic verification fixture, not NVSU evidence.
            busy=lambda:BusySnapshot((BusyEvent('synthetic-hold',start,start+dt.timedelta(minutes=20),'synthetic-request'),),now,start.replace(hour=0),start.replace(hour=23),True,True)
            bindings=(HoldBinding('synthetic-calendar','synthetic-hold','synthetic-request',start,start+dt.timedelta(minutes=20)),)
            session=FakeSession(start);port=ConsultationCalendarPort(GoogleCalendarAdapter('synthetic-calendar',session,allow_writes=True),clock=lambda:now)
            actions=ConsultationActions(root/'actions.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=synthetic_policy,clock=lambda:now,calendar_snapshot=busy,student_eligible=lambda *args:True)
            actions.add(Booking('synthetic-request','student-a',start,'synthetic-hold'))
            source_revision=state.feed.snapshot().rows[0].revision;original_event=event_revision(port.read('synthetic-hold'))
            intent=actions.preview(context,'synthetic-request','approve');plan=actions.confirm(context,intent.token)
            bound=BoundPlan('synthetic-plan','owner','synthetic-calendar',plan,source_revision,original_event,now)
            executor=ConsultationExecutor(root/'calendar.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=synthetic_policy,clock=lambda:now,
                load_plan=lambda plan_id:bound,source=state.feed,busy_snapshot=busy,hold_bindings=lambda:bindings,calendar=port)
            workflow=ConsultationWorkflow(state,executor)
            first=workflow.advance(context,bound.id,workflow_enabled=True)
            recovered=workflow.reconcile(context,bound.id,workflow_enabled=True)
            calls=[]
            def mock_send(method,payload):
                calls.append(payload['chat_id'])
                if payload['chat_id']==103:raise TimeoutError('synthetic uncertain student send')
                return {'ok':True,'result':{'message_id':len(calls),'chat':{'id':payload['chat_id'],'type':'private'},'from':{'id':9001,'is_bot':True}}}
            notices=state.notify(context,bound.id,send=mock_send,notifications_enabled=True)
            workflow.advance(context,bound.id,workflow_enabled=True);state.notify(context,bound.id,send=mock_send,notifications_enabled=True)
            if session.patches!=1 or len(calls)!=2 or recovered['stage']!='finalized':raise RuntimeError('Synthetic workflow failed')
            return '\n'.join(['# Завершение консультации — только искусственные данные','',
                'После потери Calendar ответа: '+first['stage']+' / '+first['calendar']+'.',
                'Read-only сверка: '+recovered['calendar']+'; local CAS/status/outbox: '+recovered['stage']+'.',
                'Локальная строка: '+state.snapshot().rows[0][8]+'; Google Таблица не изменялась.',
                'Уведомления: '+', '.join(row['kind']+'='+row['status'] for row in notices)+'.',
                'Mock PATCH: '+str(session.patches)+'; mock отправок уведомлений: '+str(len(calls))+'.',
                'Повтор не создаёт новых событий/операций/отправок. unknown не означает недоставлено.',
                'Все Delivered неизвестны. Реальных HTTP/Google записей/Telegram сообщений: 0.',
                'Local CAS защищает только cooperating SQLite writers, не настоящий Google Sheets.'])+'\n'
        finally:
            if executor is not None:executor.close()
            if actions is not None:actions.close()
            state.close()

if __name__=='__main__':print(run_workflow_demo(),end='')
