"""Aggregate-only synthetic demonstration; no real file, network or identities."""
import datetime as dt
import json
import tempfile
from pathlib import Path
from academic_readiness import inspect_academic_runtime
from callback_ack import CallbackAckLedger
from report_worker import ReportWorker
from report_dispatch import DispatchLedger
from telegram_inbox import TelegramInbox
from decimal import Decimal
from assistant_access import AccessPolicy,Student,Binding,Enrollment,Context
from gradebook_read import Workbook,Sheet,Cell
from academic_progress import ProgressReader,JournalMap,JournalField
from report_access import ReportReader,ReportLink
from academic_menu import AcademicMenu,MenuEntry
from academic_overview import AcademicOverview,OverviewError,prepare_overview_reply

def synthetic_dispatch(*,reviews,service,menu,revoke,policy_snapshot):
    """Temporary actual SQLite stores; send is an in-memory fake only."""
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);calls=[]
        with TelegramInbox(root/'inbox.db',namespace='synthetic-academic',bot_id=9001) as inbox, DispatchLedger(root/'dispatch.db',namespace='synthetic-academic',bot_id=9001) as ledger, CallbackAckLedger(root/'callback.db',namespace='synthetic-academic',bot_id=9001) as callback_ledger:
            ack_calls=[]
            def acknowledge(method,payload):
                assert not callback_ledger.db.in_transaction
                ack_calls.append(method)
                return {'ok':True,'result':True}
            def send(method,payload):
                assert not ledger.db.in_transaction and not inbox.db.in_transaction
                calls.append(method)
                return {'ok':True,'result':{'message_id':len(calls),'chat':{'id':103,'type':'private'},'from':{'id':9001,'is_bot':True}}}
            worker=ReportWorker(inbox,ledger,reader_factory=lambda:reviews,send=send,overview_factory=lambda:service,academic_menu_factory=lambda:menu,callback_ledger=callback_ledger,acknowledge=acknowledge)
            def store(number,text):
                inbox.store_batch({'ok':True,'result':[{'update_id':number,'message':{'message_id':number,'date':1793160000,'from':{'id':103,'is_bot':False},'chat':{'id':103,'type':'private'},'text':text}}]},expected_offset=inbox.offset())
            readiness=inspect_academic_runtime(worker,policy=policy_snapshot(),journal=service._journal,overview=service,menu=menu)
            assert readiness['local_status']=='consistent' and readiness['ready_for_live'] is False
            store(1,'/overview');first=worker.step(dispatch_enabled=True)
            assert first[0]['status']=='api_confirmed' and worker.step(dispatch_enabled=True)==()
            token=menu.prepare(Context('telegram','103',authenticated=True,private=True),'/overview').buttons[0][0].callback_data
            inbox.store_batch({'ok':True,'result':[{'update_id':2,'callback_query':{'id':'fixture-query','from':{'id':103,'is_bot':False},'message':{'message_id':2,'date':1793160000,'from':{'id':9001,'is_bot':True},'chat':{'id':103,'type':'private'}},'data':token}}]},expected_offset=inbox.offset())
            second=worker.step(dispatch_enabled=True)
            assert second[0]['callback_ack']=='api_confirmed' and len(ack_calls)==1
            assert second[0]['status']=='api_confirmed'
            revoke();store(3,'/overview');last=worker.step(dispatch_enabled=True)
            assert last[0]['status']=='cancelled' and len(calls)==2
            after=inspect_academic_runtime(worker,policy=policy_snapshot(),journal=service._journal,overview=service,menu=menu)
            assert after['local_status']=='blocked' and 'confirmed_bindings_missing' in after['blockers']
            return {'mock_api_confirmed':2,'mock_callback_ack':len(ack_calls),'replay_sends':0,'revoked_request_cancelled':True,
                    'readiness_before':'consistent','readiness_after_revocation':'blocked','ready_for_live':False,
                    'delivery_verified':False,'real_messages_sent':0}

def main():
    now=dt.datetime(2026,10,30,10,tzinfo=dt.timezone(dt.timedelta(hours=5)))
    policy=AccessPolicy(students=(Student('synthetic-student'),),bindings=(Binding('telegram','103','student','synthetic-student',frozenset({'progress.self'}),confirmed=True),),enrollments=(Enrollment('synthetic-enrollment','synthetic-student','synthetic-course','synthetic-group',now-dt.timedelta(days=1),now+dt.timedelta(days=1)),))
    book=Workbook('a'*64,False,[Sheet(1,'fixture','fixture',{'C5':Cell('C5','number',Decimal('12')),'D5':Cell('D5','number',Decimal('99'),True,True,'C5+87')},[],[],[],'visible')],[])
    journal=ProgressReader((JournalMap('synthetic-enrollment','synthetic-student','synthetic-course','synthetic-group','a'*64,1,5,(JournalField('assignment-1','score','C5'),JournalField('total','total','D5'))),),policy_provider=lambda:policy,load_workbook=lambda:book,clock=lambda:now)
    row={'status':'done','version':'fixture-version','result':{'check_id':'fixture-check','material_version':'fixture-version','assignment_id':'assignment-1','status':'needs_teacher_review','credit_written':False,'requirements':[{'requirement':'Fixture criterion','status':'needs_review'}]}}
    reviews=ReportReader((ReportLink('fixture-report','fixture-check','synthetic-enrollment','synthetic-student','synthetic-course','synthetic-group'),),policy_provider=lambda:policy,load_result=lambda key:row,clock=lambda:now)
    service=AcademicOverview(journal,reviews);context=Context('telegram','103',authenticated=True,private=True)
    result=service.read('synthetic-enrollment',context,purpose='progress.self')
    reply=prepare_overview_reply(service,context,'/overview synthetic-enrollment')
    menu=AcademicMenu([MenuEntry('synthetic-enrollment','Учебная дисциплина','Искусственный студент · Дисциплина')],journal=journal,overview=service,policy_provider=lambda:policy,clock=lambda:now)
    selection=menu.prepare(context,'/overview')
    opened=menu.callback(context,selection.buttons[0][0].callback_data)
    assert opened.status=='prepared'
    def revoke():
        nonlocal policy
        policy=AccessPolicy()
    dispatch=synthetic_dispatch(reviews=reviews,service=service,menu=menu,revoke=revoke,policy_snapshot=lambda:policy)
    denied=False
    try:service.read('synthetic-enrollment',context,purpose='progress.self')
    except OverviewError:denied=True
    assert reply.status=='prepared' and denied
    output={'mode':'synthetic_offline','dispatch':dispatch,'journal_entries':len(result['journal']['entries']),'reviews':len(result['reviews']['items']),'formula_cache_withheld':result['journal']['entries'][1]['state']=='formula_unverified','revocation_blocks_view':denied,'menu_selection_prepared':opened.status=='prepared','menu_revocation_blocks_click':menu.callback(context,selection.buttons[0][0].callback_data).status=='unavailable','credit_written':False,'live_verified':False,'real_messages_sent':0,'real_journal_writes':0}
    print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
