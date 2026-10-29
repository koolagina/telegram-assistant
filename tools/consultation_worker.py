"""Opt-in LOCAL consultation update worker; external meeting actions absent.

Only an existing private verified TelegramInbox is accepted. Local command
processing and its reply receipt commit atomically in the action sandbox. Actual
UI sends use the separate DispatchLedger; its fresh callback NEVER invokes an
action handler. Both flags default off; enabling them is not permission for real
API calls. No polling, scheduler, callback acknowledgement or live bootstrap.
"""
from dataclasses import dataclass,field
import re
from assistant_access import Context
from consultation_actions import ConsultationActions,ActionError
from consultation_requests import consultation_card,handle_local_proposal,handle_local_consultation_callback,UNAVAILABLE
from material_versions import digest
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
from telegram_report_adapter import TelegramPreparation,_id,_user,_private_message

class ConsultationWorkerError(ValueError):pass

@dataclass(frozen=True)
class LocalCommand:
    context: Context = field(repr=False)
    chat_id: int = field(repr=False)
    kind: str
    value: str = field(repr=False)
    callback_id: str | None = field(default=None,repr=False)


def _route(update,bot_id):
    if (type(update) is not dict or not _id(update.get('update_id'),zero=True)
            or len(set(update)-{'update_id'})!=1):return None
    message=update.get('message');query=update.get('callback_query')
    if message is not None:
        if type(message) is not dict or not _user(message.get('from')):return None
        sender=message['from']['id']
        if sender==bot_id or not _private_message(message,sender):return None
        text=message.get('text')
        if type(text) is not str or len(text)>200:return None
        card=re.fullmatch(r'/consult_request ([^\s]{1,128})',text)
        if card:kind='card';value=card.group(1)
        elif text.startswith('/consult_propose '):kind='proposal';value=text
        else:return None
        context=Context('telegram',str(sender),authenticated=True,private=True,sender=str(sender))
        return LocalCommand(context,sender,kind,value)
    if query is not None:
        if type(query) is not dict or not _user(query.get('from')):return None
        sender=query['from']['id'];message=query.get('message');data=query.get('data');query_id=query.get('id')
        if (sender==bot_id or not _private_message(message,sender) or not _user(message.get('from'),bot=True)
                or message['from']['id']!=bot_id or type(data) is not str or not data.startswith('con:')
                or not data.isascii() or len(data)>64 or type(query_id) is not str or not 1<=len(query_id)<=256):return None
        context=Context('telegram',str(sender),authenticated=True,private=True,sender=str(sender))
        return LocalCommand(context,sender,'callback',data,query_id)
    return None

class ConsultationWorker:
    def __init__(self,inbox,ledger,service,*,send=None):
        if (type(inbox) is not TelegramInbox or type(ledger) is not DispatchLedger or type(service) is not ConsultationActions
                or inbox.bot_id!=ledger.bot_id or inbox.bot_id!=service.bot_id
                or inbox.namespace!=ledger.namespace or inbox.namespace!=service.namespace
                or (send is not None and not callable(send))):
            raise ConsultationWorkerError('Matching trusted inbox/ledger/action store required')
        self.inbox=inbox;self.ledger=ledger;self.service=service;self.send=send
    def _handle(self,command):
        if command.kind=='card':return consultation_card(self.service,command.context,command.value)
        if command.kind=='proposal':return handle_local_proposal(self.service,command.context,command.value)
        return handle_local_consultation_callback(self.service,command.context,command.value)
    def step(self,*,actions_enabled=False,dispatch_enabled=False,limit=100):
        if actions_enabled is not True or (dispatch_enabled is True and not callable(self.send)):
            raise ConsultationWorkerError('Local actions disabled or missing sender')
        try:rows=self.inbox.pending(limit=limit)
        except Exception:raise ConsultationWorkerError('Private inbox unavailable') from None
        results=[]
        for row in rows:
            uid=row['update_id'];command=_route(row['update'],self.inbox.bot_id)
            if command is None:
                results.append({'update_id':uid,'status':'not_attempted','queue_status':'deferred','delivered':None});continue
            try:
                # Recovery of known send receipt needs no old private reply read.
                outcome=self.ledger.result(uid)
                if outcome['status']=='not_attempted':
                    try:
                        reply=self.service.process_update(command.context,uid,digest(row['update']),lambda:self._handle(command),actions_enabled=True)
                    except ActionError:
                        # Distinguish denied access from transient/corrupt local state.
                        try:self.service.check_access(command.context)
                        except ActionError:reply=UNAVAILABLE
                        else:raise
                    if dispatch_enabled is not True:
                        results.append({'update_id':uid,'status':'local_prepared' if reply.status=='prepared' else 'unavailable','queue_status':'reply_ready','delivered':None});continue
                    def fresh():
                        # Read-only under DispatchLedger lock: no handler/plan writes.
                        try:self.service.check_access(command.context);current=reply
                        except ActionError:current=UNAVAILABLE
                        return TelegramPreparation(uid,command.chat_id,current,command.callback_id)
                    outcome=self.ledger.attempt(uid,prepare_fresh=fresh,send=self.send,dispatch_enabled=True)
                if outcome['status']=='inflight_or_unknown':
                    queue='inflight'
                elif outcome['status'] in ('api_confirmed','cancelled','unknown','api_rejected'):
                    queue='handled' if outcome['status'] in ('api_confirmed','cancelled') else 'blocked'
                    self.inbox.mark(uid,status=queue)
                else:raise ConsultationWorkerError('Unexpected dispatch state')
                results.append({'update_id':uid,'status':outcome['status'],'queue_status':queue,'delivered':None})
            except Exception:
                results.append({'update_id':uid,'status':'unavailable','queue_status':'needs_recovery','delivered':None})
        return tuple(results)
