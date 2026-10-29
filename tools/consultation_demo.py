"""Synthetic local two-click flow. No real records, Calendar or Telegram API."""
import datetime as dt
from pathlib import Path
import tempfile
from assistant_demo import synthetic_policy
from decision_demo import DEMO_NOW
from consultation_actions import Booking,ConsultationActions
from consultation_feed import (HEADERS,SheetSnapshot,ConsultationFeed,CalendarSnapshot,TeachingVerification,HoldBinding,BusyFeed,calendar_revision)
from consultation_worker import ConsultationWorker
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger


def run_consultation_demo():
    now=DEMO_NOW+dt.timedelta(hours=1);start=now+dt.timedelta(hours=1)
    # Explicitly SYNTHETIC source data and verifier evidence, not real import proof.
    row=('synthetic-request',now,'Synthetic student','103',start.date().isoformat(),start.strftime('%H:%M'),20,'Synthetic topic','Ожидает решения','','synthetic-hold')
    exported=SheetSnapshot('synthetic-sheet','Заявки на консультации',HEADERS,(row,),now,True,'Asia/Yekaterinburg')
    feed=ConsultationFeed(spreadsheet_id='synthetic-sheet',load_snapshot=lambda:exported,clock=lambda:now)
    evidence=feed.snapshot().rows[0]
    target=CalendarSnapshot('synthetic-target',({'id':'synthetic-hold','start':start.isoformat(),'end':(start+dt.timedelta(minutes=20)).isoformat()},),now,now.replace(hour=0),now.replace(hour=23),True)
    verification=TeachingVerification('owner','synthetic-target',target.covered_start,target.covered_end,now,now,'synthetic-source',calendar_revision(target))
    bindings=(HoldBinding('synthetic-target','synthetic-hold','synthetic-request',start,start+dt.timedelta(minutes=20)),)
    busy=BusyFeed(target_id='synthetic-target',teaching_id='synthetic-target',teacher_id='owner',load_target=lambda:target,
                  load_teaching=lambda:target,load_verification=lambda:verification,load_bindings=lambda:bindings,clock=lambda:now)
    with tempfile.TemporaryDirectory() as directory:
        service=ConsultationActions(Path(directory)/'consultations.sqlite3',namespace='synthetic-consultations',owner_id='owner',bot_id=9001,
            policy_provider=synthetic_policy,clock=lambda:now,calendar_snapshot=busy,student_eligible=lambda student,at:student=='student-a')
        try:
            # Local fixture ingestion ONLY; the real Sheet is never mirrored here.
            service.add(Booking(evidence.record.id,'student-a',evidence.record.starts_at,evidence.event_id))
            with TelegramInbox(Path(directory)/'inbox.sqlite3',namespace='synthetic-consultations',bot_id=9001) as inbox,DispatchLedger(Path(directory)/'dispatch.sqlite3',namespace='synthetic-consultations',bot_id=9001) as ledger:
                sent=[]
                def mock_send(method,payload):
                    # Injected local function, no TelegramHTTP/client/network.
                    sent.append(payload)
                    return {'ok':True,'result':{'message_id':len(sent),'chat':{'id':101,'type':'private'},'from':{'id':9001,'is_bot':True}}}
                worker=ConsultationWorker(inbox,ledger,service,send=mock_send)
                def process(value,callback=False):
                    update={'update_id':inbox.offset()}
                    message={'message_id':1,'date':1793246400,'chat':{'id':101,'type':'private'}}
                    if callback:
                        message['from']={'id':9001,'is_bot':True}
                        update['callback_query']={'id':'synthetic-callback','from':{'id':101,'is_bot':False},'message':message,'data':value}
                    else:
                        message.update(text=value,**{'from':{'id':101,'is_bot':False}});update['message']=message
                    inbox.store_batch({'ok':True,'result':[update]},expected_offset=inbox.offset())
                    outcome=worker.step(actions_enabled=True,dispatch_enabled=True)
                    if len(outcome)!=1 or outcome[0]['status']!='api_confirmed':raise RuntimeError('Synthetic worker failed')
                    return sent[-1]
                card=process('/consult_request synthetic-request')
                approve=next(b['callback_data'] for row in card['reply_markup']['inline_keyboard'] for b in row if b['callback_data'].startswith('con:a:approve:'))
                preview=process(approve,True)
                confirm=next(b['callback_data'] for row in preview['reply_markup']['inline_keyboard'] for b in row if b['callback_data'].startswith('con:c:'))
                done=process(confirm,True);process(confirm,True)
                if len(service.plans())!=1 or worker.step(actions_enabled=True,dispatch_enabled=True)!=():raise RuntimeError('Synthetic replay failed')
            return '\n\n'.join(['# Консультации — искусственные данные',
                'Источник: проверенный локальный формат 11 колонок; полнота подтверждена только искусственной фикстурой.',
                'Диалог проходит через durable inbox → локальную транзакцию решения/ответа → mock dispatch. Сети нет.',
                card['text'],preview['text'],done['text'],
                'Повторное нажатие: тот же план, новых операций нет.\nПланов: 1; реальных событий и сообщений: 0.\n'
                'Ответы интерфейса проверены только mock sender, это не API/доставка.\n'
                'Предложение времени требует отдельного ввода и подтверждения; прежний резерв сохраняется.'])+'\n'
        finally:service.close()

if __name__=='__main__':print(run_consultation_demo(),end='')
