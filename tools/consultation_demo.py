"""Synthetic local two-click flow. No real records, Calendar or Telegram API."""
import datetime as dt
from pathlib import Path
import tempfile
from assistant_access import Context
from assistant_demo import synthetic_policy
from decision_demo import DEMO_NOW
from consultation_actions import Booking,BusyEvent,BusySnapshot,ConsultationActions
from consultation_requests import consultation_card,handle_local_consultation_callback


def run_consultation_demo():
    now=DEMO_NOW+dt.timedelta(hours=1);start=now+dt.timedelta(hours=1)
    context=Context('telegram','101',authenticated=True,private=True)
    hold=BusyEvent('synthetic-hold',start,start+dt.timedelta(minutes=20),'synthetic-request')
    snapshot=BusySnapshot((hold,),now,now.replace(hour=0),now.replace(hour=23),True,True)
    with tempfile.TemporaryDirectory() as directory:
        service=ConsultationActions(Path(directory)/'consultations.sqlite3',namespace='synthetic-consultations',owner_id='owner',
            policy_provider=synthetic_policy,clock=lambda:now,calendar_snapshot=lambda:snapshot,student_eligible=lambda student,at:student=='student-a')
        try:
            service.add(Booking('synthetic-request','student-a',start,'synthetic-hold'))
            card=consultation_card(service,context,'synthetic-request')
            approve=next(b.callback_data for row in card.buttons for b in row if b.callback_data.startswith('con:a:approve:'))
            preview=handle_local_consultation_callback(service,context,approve)
            confirm=next(b.callback_data for row in preview.buttons for b in row if b.callback_data.startswith('con:c:'))
            done=handle_local_consultation_callback(service,context,confirm)
            again=handle_local_consultation_callback(service,context,confirm)
            if done.status!='prepared' or again.status!='prepared' or len(service.plans())!=1:raise RuntimeError('Synthetic flow failed')
            return '\n\n'.join(['# Консультации — искусственные данные',card.text,preview.text,done.text,
                'Повторное нажатие: тот же план, новых операций нет.\nПланов: 1; реальных событий и сообщений: 0.\n'
                'Предложение времени требует отдельного ввода и подтверждения; прежний резерв сохраняется.'])+'\n'
        finally:service.close()

if __name__=='__main__':print(run_consultation_demo(),end='')
