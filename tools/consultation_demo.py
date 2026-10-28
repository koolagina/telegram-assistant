"""Synthetic local two-click flow. No real records, Calendar or Telegram API."""
import datetime as dt
from pathlib import Path
import tempfile
from assistant_access import Context
from assistant_demo import synthetic_policy
from decision_demo import DEMO_NOW
from consultation_actions import Booking,ConsultationActions
from consultation_feed import (HEADERS,SheetSnapshot,ConsultationFeed,CalendarSnapshot,TeachingVerification,HoldBinding,BusyFeed,calendar_revision)
from consultation_requests import consultation_card,handle_local_consultation_callback


def run_consultation_demo():
    now=DEMO_NOW+dt.timedelta(hours=1);start=now+dt.timedelta(hours=1)
    context=Context('telegram','101',authenticated=True,private=True)
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
        service=ConsultationActions(Path(directory)/'consultations.sqlite3',namespace='synthetic-consultations',owner_id='owner',
            policy_provider=synthetic_policy,clock=lambda:now,calendar_snapshot=busy,student_eligible=lambda student,at:student=='student-a')
        try:
            # Local fixture ingestion ONLY; the real Sheet is never mirrored here.
            service.add(Booking(evidence.record.id,'student-a',evidence.record.starts_at,evidence.event_id))
            card=consultation_card(service,context,'synthetic-request')
            approve=next(b.callback_data for row in card.buttons for b in row if b.callback_data.startswith('con:a:approve:'))
            preview=handle_local_consultation_callback(service,context,approve)
            confirm=next(b.callback_data for row in preview.buttons for b in row if b.callback_data.startswith('con:c:'))
            done=handle_local_consultation_callback(service,context,confirm)
            again=handle_local_consultation_callback(service,context,confirm)
            if done.status!='prepared' or again.status!='prepared' or len(service.plans())!=1:raise RuntimeError('Synthetic flow failed')
            return '\n\n'.join(['# Консультации — искусственные данные','Источник: проверенный локальный формат 11 колонок; полнота подтверждена только искусственной фикстурой.',card.text,preview.text,done.text,
                'Повторное нажатие: тот же план, новых операций нет.\nПланов: 1; реальных событий и сообщений: 0.\n'
                'Предложение времени требует отдельного ввода и подтверждения; прежний резерв сохраняется.'])+'\n'
        finally:service.close()

if __name__=='__main__':print(run_consultation_demo(),end='')
