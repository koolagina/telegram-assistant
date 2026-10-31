"""Synthetic crash boundaries with real temporary SQLite; zero network."""
import json
from pathlib import Path
import tempfile
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
from report_worker import ReportWorker
from telegram_report_adapter import TelegramPreparation
from report_requests import PreparedReply
from recovery_review import review_recovery


def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);calls=[]
        with TelegramInbox(root/'inbox.db',namespace='synthetic-recovery',bot_id=9001) as inbox, DispatchLedger(root/'dispatch.db',namespace='synthetic-recovery',bot_id=9001) as ledger:
            def store(uid):
                inbox.store_batch({'ok':True,'result':[{'update_id':uid,'message':{'message_id':uid,'date':1793160000,'from':{'id':103,'is_bot':False},'chat':{'id':103,'type':'private'},'text':'/overview'}}]},expected_offset=inbox.offset())
            def send(method,payload):
                calls.append(method)
                return {'ok':True,'result':{'message_id':len(calls),'chat':{'id':103,'type':'private'},'from':{'id':9001,'is_bot':True}}}
            def forbidden(*args):raise AssertionError('Receipt recovery must not prepare or send')
            def preparation(uid):return TelegramPreparation(uid,103,PreparedReply('prepared','Synthetic response'))
            store(1)
            ledger.attempt(1,prepare_fresh=lambda:preparation(1),send=send,dispatch_enabled=True)
            # Simulated process stop BEFORE inbox mark; receipt remains durable.
            before=review_recovery(inbox,ledger)
            assert 'verify_receipt_then_mark_only' in before['items'][0]['actions']
            worker=ReportWorker(inbox,ledger,reader_factory=forbidden,send=forbidden)
            assert worker.step(dispatch_enabled=True)[0]['queue_status']=='handled'
            after=review_recovery(inbox,ledger);assert after['needs_attention']==0 and len(calls)==1
            store(2)
            def unknown(method,payload):calls.append(method);raise TimeoutError('Synthetic API outcome loss')
            ledger.attempt(2,prepare_fresh=lambda:preparation(2),send=unknown,dispatch_enabled=True)
            plan=review_recovery(inbox,ledger)
            assert 'manual_review_no_resend' in plan['items'][1]['actions']
            assert worker.step(dispatch_enabled=True)[0]['queue_status']=='blocked' and len(calls)==2
            assert worker.step(dispatch_enabled=True)==()
            print(json.dumps({'mode':'synthetic_offline','mark_only_recovery_verified':True,
                'replay_sends':0,'unknown_preserved_for_manual_review':True,'review_writes':0,
                'ready_for_apply':False,'delivery_verified':False,'real_messages_sent':0,'real_journal_writes':0},indent=2))

if __name__=='__main__':main()
