"""Synthetic lecture→code→self attendance via actual local queues, fake API."""
import datetime as dt
import json
from pathlib import Path
import tempfile
from assistant_access import AccessPolicy,Teacher,Student,Binding,Enrollment,Lecture,Context,SubstitutionGrant
from lecture_windows import WindowStore,LectureWindows
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
from report_worker import ReportWorker


def main():
    now=dt.datetime(2026,10,30,10,tzinfo=dt.timezone(dt.timedelta(hours=5)))
    lecture=Lecture('fixture-lecture','fixture-lecturer','fixture-course',('fixture-group',),now-dt.timedelta(minutes=10),now+dt.timedelta(hours=1),verified=True)
    caps=frozenset({'lecture.open','lecture.code.read'})
    policy=AccessPolicy(teachers=(Teacher('fixture-owner'),Teacher('fixture-lecturer')),students=(Student('fixture-student'),),
        bindings=(Binding('telegram','101','teacher','fixture-owner',caps,confirmed=True),Binding('telegram','102','teacher','fixture-lecturer',caps,confirmed=True),Binding('telegram','103','student','fixture-student',frozenset({'attendance.register'}),confirmed=True)),
        enrollments=(Enrollment('fixture-enrollment','fixture-student','fixture-course','fixture-group',now-dt.timedelta(days=1),now+dt.timedelta(days=1)),),lectures=(lecture,),
        substitutions=(SubstitutionGrant('fixture-substitution','fixture-owner','fixture-lecture',now-dt.timedelta(minutes=1),now+dt.timedelta(hours=1)),))
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);calls=[]
        # Fixed fixture key, not a real credential; temporary state is deleted.
        with WindowStore(root/'windows.db',key=bytes(range(32)),namespace='synthetic-lecture') as state, TelegramInbox(root/'inbox.db',namespace='synthetic-lecture',bot_id=9001) as inbox, DispatchLedger(root/'dispatch.db',namespace='synthetic-lecture',bot_id=9001) as ledger:
            service=LectureWindows(state,policy_provider=lambda:policy,clock=lambda:now)
            def send(method,payload):
                calls.append(method)
                return {'ok':True,'result':{'message_id':len(calls),'chat':{'id':payload['chat_id'],'type':'private'},'from':{'id':9001,'is_bot':True}}}
            worker=ReportWorker(inbox,ledger,reader_factory=lambda:None,send=send,lecture_service_factory=lambda:service)
            def enqueue(uid,sender,text):
                inbox.store_batch({'ok':True,'result':[{'update_id':uid,'message':{'message_id':uid,'date':1793160000,'from':{'id':sender,'is_bot':False},'chat':{'id':sender,'type':'private'},'text':text}}]},expected_offset=inbox.offset())
                assert worker.step(dispatch_enabled=True)[0]['status']=='api_confirmed'
            enqueue(1,101,'/lecturecode fixture-lecture')
            window=service.show(Context('telegram','102',authenticated=True,private=True),'fixture-lecture')
            assert int((window.expires_at-window.opened_at).total_seconds())==90
            enqueue(2,103,'/attend fixture-lecture '+window.code)
            enqueue(3,103,'/attend fixture-lecture '+window.code)
            assert state.attendance_count()==1 and worker.step(dispatch_enabled=True)==()
            now=window.expires_at
            expired=service.register_authenticated(Context('telegram','103',authenticated=True,private=True),'fixture-lecture',window.code)
            assert not expired.accepted
            print(json.dumps({'mode':'synthetic_offline','window_seconds':90,'windows_created':state.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],
                'attendance_records':state.attendance_count(),'repeated_attendance_deduplicated':True,'expired_code_rejected':True,
                'owner_substitution_verified':True,'journal_status':'not_synced','mock_api_confirmed':len(calls),
                'real_messages_sent':0,'real_journal_writes':0,'physical_presence_verified':False},indent=2))

if __name__=='__main__':main()
