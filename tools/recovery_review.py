"""SELECT-only advisory recovery cases for trusted local stores, never repair.

No payload/identity loader, network, reset, retry, mark, claim takeover or sending.
References/fingerprints are navigation and change indicators, NOT credentials,
complete DB integrity proofs or anonymous identifiers. Reinspect before action;
separate SQLite connections are not one atomic snapshot under active workers.
"""
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
from callback_ack import CallbackAckLedger
from material_versions import digest

class RecoveryReviewError(ValueError):
    pass


def _records(db,query,limit,states):
    rows=db.execute(query,(limit+1,)).fetchall()
    records={}
    for row in rows:
        uid=row[0]
        if type(uid) is not int or not 0<=uid<2**52 or row[1] not in states:raise ValueError()
        records[uid]=tuple(row[1:])
    return records,len(rows)<=limit


def _receipt_valid(row,callback=False):
    phase=row[0]
    message=None if callback else row[1]
    error=row[1] if callback else row[2]
    if phase=='api_rejected':return message is None and type(error) is int and 100<=error<=599
    if error is not None:return False
    if phase=='api_confirmed' and not callback:return type(message) is int and 0<message<2**52
    return message is None


def review_recovery(inbox,ledger,*,callback_ledger=None,limit=100):
    """Bounded metadata plan; all actions are fixed labels, never executable.

    Every returned item excludes raw update/message/query IDs and payload hashes.
    complete means the bounded metadata scan is complete, not recovery verified.
    ready_for_apply is always False; no separate apply endpoint exists.
    """
    try:
        if type(limit) is not int or not 1<=limit<=1000:raise ValueError()
        if type(inbox) is not TelegramInbox or type(ledger) is not DispatchLedger:raise ValueError()
        if inbox.namespace!=ledger.namespace or inbox.bot_id!=ledger.bot_id:raise ValueError()
        expected={'version':'1','namespace':inbox.namespace,'bot_id':str(inbox.bot_id)}
        im=dict(inbox.db.execute('SELECT key,value FROM inbox_meta'))
        if {k:v for k,v in im.items() if k!='next_offset'}!=expected:raise ValueError()
        if dict(ledger.db.execute('SELECT key,value FROM dispatch_meta'))!=expected:raise ValueError()
        inbox.offset()
        queue,qcomplete=_records(inbox.db,'SELECT update_id,status FROM inbox_updates ORDER BY update_id LIMIT ?',limit,('pending','handled','ignored','blocked'))
        dispatch,dcomplete=_records(ledger.db,'SELECT update_id,phase,message_id,error_code FROM dispatch_attempts ORDER BY update_id LIMIT ?',limit,('sending','api_confirmed','api_rejected','cancelled','unknown'))
        callbacks={};acomplete=True
        if callback_ledger is not None:
            if type(callback_ledger) is not CallbackAckLedger or callback_ledger.namespace!=inbox.namespace or callback_ledger.bot_id!=inbox.bot_id:raise ValueError()
            if dict(callback_ledger.db.execute('SELECT key,value FROM callback_meta'))!=expected:raise ValueError()
            callbacks,acomplete=_records(callback_ledger.db,'SELECT update_id,phase,error_code FROM callback_attempts ORDER BY update_id LIMIT ?',limit,('sending','api_confirmed','api_rejected','unknown'))
        ids=sorted(set(queue)|set(dispatch)|set(callbacks))
        complete=qcomplete and dcomplete and acomplete and len(ids)<=limit
        selected=ids[:limit]
        metadata=[[uid,queue.get(uid),dispatch.get(uid),callbacks.get(uid)] for uid in selected]
        snapshot=digest([inbox.namespace,inbox.bot_id,complete,metadata]);items=[]
        for uid in selected:
            q=queue.get(uid,('missing',))[0];d=dispatch.get(uid,('not_attempted',))[0];a=callbacks.get(uid,('not_attempted',))[0]
            issues=[];actions=[]
            if q=='missing' and (d!='not_attempted' or a!='not_attempted'):
                issues.append('receipt_without_inbox');actions.append('verify_retention_or_missing_inbox')
            elif q=='pending':
                if d=='not_attempted':actions.append('route_with_fresh_policy')
                elif d in ('api_confirmed','cancelled'):actions.append('verify_receipt_then_mark_only')
                elif d in ('unknown','api_rejected'):actions.append('manual_review_no_resend')
            elif q=='handled' and d in ('unknown','api_rejected','sending'):
                issues.append('queue_receipt_conflict')
            elif q=='blocked' and d in ('api_confirmed','cancelled'):
                issues.append('queue_receipt_conflict')
            elif q=='ignored' and d!='not_attempted':issues.append('queue_receipt_conflict')
            if q=='handled' and d=='not_attempted':
                issues.append('handled_without_dispatch_receipt');actions.append('verify_other_handler_or_retention')
            if d=='sending':actions.append('verify_active_process_no_takeover')
            elif d in ('unknown','api_rejected') and 'manual_review_no_resend' not in actions:actions.append('manual_review_no_resend')
            if a!='not_attempted' and d=='not_attempted':issues.append('ack_without_business_receipt')
            if a=='sending':actions.append('verify_callback_process_no_takeover')
            elif a in ('unknown','api_rejected'):actions.append('callback_manual_review_no_retry')
            if uid in dispatch and not _receipt_valid(dispatch[uid]):
                issues.append('receipt_metadata_invalid')
                actions=[action for action in actions if action not in ('verify_receipt_then_mark_only','route_with_fresh_policy')]
                actions.append('manual_reconcile_no_send')
            if uid in callbacks and not _receipt_valid(callbacks[uid],callback=True):
                issues.append('callback_receipt_metadata_invalid');actions.append('callback_manual_review_no_retry')
            if 'queue_receipt_conflict' in issues:actions.append('manual_reconcile_no_send')
            items.append({'reference':digest([inbox.namespace,inbox.bot_id,uid])[:32],
                'queue_state':q,'dispatch_state':d,'callback_state':a,'issues':sorted(set(issues)),'actions':sorted(set(actions))})
        return {'format_version':1,'mode':'local_metadata_only','complete':complete,'snapshot_hash':snapshot,
                'items':items,'inspected':len(items),'needs_attention':sum(bool(i['issues'] or i['actions']) for i in items),
                'ready_for_apply':False,'live_verified':False,'writes':0,'messages_sent':0,'polling_started':False}
    except Exception:raise RecoveryReviewError('Recovery review unavailable') from None
