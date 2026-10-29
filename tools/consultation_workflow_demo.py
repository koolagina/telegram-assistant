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
from consultation_executor import ConsultationExecutor
from consultation_consent import ConsultationConsent
from consultation_bound_worker import BoundConsultationWorker
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
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
            actions=ConsultationActions(root/'actions.sqlite3',namespace='synthetic',owner_id='owner',bot_id=9001,policy_provider=synthetic_policy,clock=lambda:now,calendar_snapshot=busy,student_eligible=lambda *args:True)
            actions.add(Booking('synthetic-request','student-a',start,'synthetic-hold'))
            registry=ConsultationConsent(state,actions,port,hold_bindings=lambda:bindings)
            executor=ConsultationExecutor(root/'calendar.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=synthetic_policy,clock=lambda:now,
                load_plan=registry.load_confirmed,source=state.feed,busy_snapshot=busy,hold_bindings=lambda:bindings,calendar=port)
            workflow=ConsultationWorkflow(state,executor)
            with TelegramInbox(root/'inbox.sqlite3',namespace='synthetic',bot_id=9001) as inbox,DispatchLedger(root/'ui.sqlite3',namespace='synthetic',bot_id=9001) as ledger:
                ui=[]
                def mock_ui(method,payload):
                    ui.append(payload)
                    return {'ok':True,'result':{'message_id':len(ui),'chat':{'id':101,'type':'private'},'from':{'id':9001,'is_bot':True}}}
                worker=BoundConsultationWorker(inbox,ledger,registry,workflow=workflow,send=mock_ui)
                def interact(value,callback=False):
                    update={'update_id':inbox.offset()};message={'message_id':1,'date':1793246400,'chat':{'id':101,'type':'private'}}
                    if callback:
                        message['from']={'id':9001,'is_bot':True};update['callback_query']={'id':'synthetic-callback','from':{'id':101,'is_bot':False},'message':message,'data':value}
                    else:message.update(text=value,**{'from':{'id':101,'is_bot':False}});update['message']=message
                    inbox.store_batch({'ok':True,'result':[update]},expected_offset=inbox.offset())
                    result=worker.step(actions_enabled=True,dispatch_enabled=True,workflow_enabled=True)
                    if len(result)!=1 or result[0]['status']!='api_confirmed':raise RuntimeError('Synthetic bound UI failed')
                    return ui[-1]
                def button(payload,prefix):return next(b['callback_data'] for row in payload['reply_markup']['inline_keyboard'] for b in row if b['callback_data'].startswith(prefix))
                card=interact('/consult_request synthetic-request')
                review=interact(button(card,'bcon:a:approve:'),True)
                confirm=button(review,'bcon:c:');interact(confirm,True)
                plan_id=confirm.rsplit(':',1)[1]
                first=workflow.advance(context,plan_id,workflow_enabled=True)
                recovered=workflow.reconcile(context,plan_id,workflow_enabled=True)
                interact(confirm,True)  # Another verified click: same decision, no extra mutation.
            calls=[]
            def mock_send(method,payload):
                calls.append(payload['chat_id'])
                if payload['chat_id']==103:raise TimeoutError('synthetic uncertain student send')
                return {'ok':True,'result':{'message_id':len(calls),'chat':{'id':payload['chat_id'],'type':'private'},'from':{'id':9001,'is_bot':True}}}
            notices=state.notify(context,plan_id,send=mock_send,notifications_enabled=True)
            workflow.advance(context,plan_id,workflow_enabled=True);state.notify(context,plan_id,send=mock_send,notifications_enabled=True)
            if session.patches!=1 or len(calls)!=2 or recovered['stage']!='finalized':raise RuntimeError('Synthetic workflow failed')
            return '\n'.join(['# Завершение консультации — только искусственные данные','',
                'Синтетические Telegram updates: карточка → original review → отдельный confirm → registry/source claim.',
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
