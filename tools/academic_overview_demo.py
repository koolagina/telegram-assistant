"""Aggregate-only synthetic demonstration; no real file, network or identities."""
import datetime as dt
import json
from decimal import Decimal
from assistant_access import AccessPolicy,Student,Binding,Enrollment,Context
from gradebook_read import Workbook,Sheet,Cell
from academic_progress import ProgressReader,JournalMap,JournalField
from report_access import ReportReader,ReportLink
from academic_overview import AcademicOverview,OverviewError,prepare_overview_reply

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
    policy=AccessPolicy()
    denied=False
    try:service.read('synthetic-enrollment',context,purpose='progress.self')
    except OverviewError:denied=True
    assert reply.status=='prepared' and denied
    output={'mode':'synthetic_offline','journal_entries':len(result['journal']['entries']),'reviews':len(result['reviews']['items']),'formula_cache_withheld':result['journal']['entries'][1]['state']=='formula_unverified','revocation_blocks_view':denied,'credit_written':False,'live_verified':False,'real_messages_sent':0,'real_journal_writes':0}
    print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
