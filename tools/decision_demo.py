"""Offline owner decision demo. All identities/consultations/work are fake.

No live Sheet connector, credentials, scheduling or external send. Fixture status
changes below simulate an independently resolved source; the queue does not
confirm a consultation, accept a work, dismiss an incident or change a grade.
"""
from dataclasses import replace
import datetime as dt
from pathlib import Path
import tempfile
from assistant_demo import SyntheticAssistantSession,NOW
from decision_queue import DecisionQueue
from decision_sources import ConsultationSource,ConsultationRecord,ConsultationBatch,ReviewSource,DispatchSource
from decision_requests import prepare_decision_reply
from assistant_access import Context
from report_dispatch import DispatchLedger
from telegram_report_adapter import TelegramPreparation
from report_requests import PreparedReply

DEMO_NOW=NOW+dt.timedelta(hours=20)


def build_demo_queue(session,ledger,records):
    return DecisionQueue(owner_id='owner',policy_provider=lambda:session.policy,clock=lambda:DEMO_NOW,sources={
        'consultation':ConsultationSource('owner',lambda:ConsultationBatch(tuple(records),DEMO_NOW)),
        'review':ReviewSource('owner',session.registry.snapshot,session.catalog.result),
        'technical':DispatchSource('owner',ledger.attention)})


def run_decision_demo():
    with tempfile.TemporaryDirectory() as directory:
        with SyntheticAssistantSession(Path(directory)) as session,DispatchLedger(Path(directory)/'dispatch.sqlite3',namespace='synthetic-assistant',bot_id=9001) as ledger:
            session.ingest(40)
            records=[ConsultationRecord('demo-request','Ожидает решения',DEMO_NOW+dt.timedelta(hours=1),DEMO_NOW-dt.timedelta(minutes=20),'Учебный пример','Обсудить работу')]
            def uncertain(*args):raise TimeoutError('mock-only, no external call')
            ledger.attempt(900,prepare_fresh=lambda:TelegramPreparation(900,101,PreparedReply('prepared','Synthetic fixture')),send=uncertain,dispatch_enabled=True)
            service=build_demo_queue(session,ledger,records)
            context=Context('telegram','101',authenticated=True,private=True)
            reply=prepare_decision_reply(service,context,'/decisions')
            if reply.status!='prepared':raise RuntimeError('Synthetic decision queue failed')
            before=reply.text
            # Fixture mutation ONLY. No real consultation handler or calendar call.
            records[0]=replace(records[0],status='Подтверждена')
            after=service.page(context)
    return '\n'.join(['# Очередь решений — искусственные данные','',before,'',
        'Кнопки: категории, подробнее, назад/далее при необходимости, обновить.',
        'После изменения источника: консультаций '+str(after.counts['consultation'])+'.',
        'Изменён только тестовый fixture. Никаких реальных подтверждений, писем, оценок или API-вызовов.'])+'\n'

if __name__=='__main__':print(run_decision_demo(),end='')
