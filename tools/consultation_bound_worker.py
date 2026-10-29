"""LOCAL opt-in evidence-bound consultation worker, fake transports in tests.

Pre-consent Calendar reads are OUTSIDE local action transactions. New bcon
previews use persisted verified-update idempotency keys; confirm/cancel use the
immutable review token. Legacy proposal actions retain core receipt handling.
Fresh UI dispatch callback only checks access; never calls consent/Calendar.
No polling/live bootstrap/automatic notifications or production authorization.
"""
import re
from consultation_worker import _route
from consultation_actions import ActionError
from consultation_consent import ConsultationConsent
from consultation_workflow import ConsultationWorkflow,WorkflowError
from consultation_requests import handle_local_consultation_callback,handle_local_proposal,UNAVAILABLE
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
from telegram_report_adapter import TelegramPreparation
from report_requests import PreparedReply
from material_versions import digest

class BoundConsultationWorker:
    def __init__(self,inbox,ledger,registry,*,workflow=None,send=None):
        if (type(inbox) is not TelegramInbox or type(ledger) is not DispatchLedger or type(registry) is not ConsultationConsent
                or inbox.namespace!=ledger.namespace or inbox.namespace!=registry.state.namespace
                or inbox.bot_id!=ledger.bot_id or inbox.bot_id!=registry.state.bot_id or inbox.bot_id!=registry.actions.bot_id
                or (send is not None and not callable(send))
                or (workflow is not None and (type(workflow) is not ConsultationWorkflow or workflow.state is not registry.state or workflow.executor.calendar is not registry.calendar))):raise WorkflowError('Matching trusted consent runtime required')
        self.inbox=inbox;self.ledger=ledger;self.registry=registry;self.workflow=workflow;self.send=send
    def _process(self,command,uid,update,workflow_enabled):
        context=command.context
        if command.kind=='card':return self.registry.card(context,command.value)
        if command.kind=='callback' and command.value.startswith('bcon:'):
            key=digest([self.inbox.namespace,self.inbox.bot_id,uid,digest(update)])
            reply=self.registry.handle_callback(context,command.value,request_key=key)
            confirm=re.fullmatch(r'bcon:c:([a-f0-9]{32})',command.value)
            if reply.status=='prepared' and confirm and workflow_enabled is True:
                try:
                    result=self.workflow.advance(context,confirm.group(1),workflow_enabled=True)
                    return PreparedReply('prepared','Локальный сценарий: '+result['stage']+'.\nСтатус источника: '+result['source_status']+'.\nУведомления обрабатываются отдельно; реальные ресурсы не подключены.')
                except WorkflowError:
                    return PreparedReply('prepared','Решение сохранено локально; исполнение требует сверки. Не повторяйте календарную запись вслепую. Реальные ресурсы не подключены.')
            return reply
        # Legacy proposal/read-only callbacks still use their existing atomic local receipt.
        def process():
            if command.kind=='proposal':return handle_local_proposal(self.registry.actions,context,command.value)
            return handle_local_consultation_callback(self.registry.actions,context,command.value)
        try:return self.registry.actions.process_update(context,uid,digest(update),process,actions_enabled=True)
        except ActionError:
            self.registry.state._auth(context);raise
    def step(self,*,actions_enabled=False,dispatch_enabled=False,workflow_enabled=False,limit=100):
        if (actions_enabled is not True or (dispatch_enabled is True and not callable(self.send))
                or (workflow_enabled is True and self.workflow is None)):raise WorkflowError('Bound consultation runtime disabled')
        try:rows=self.inbox.pending(limit=limit)
        except Exception:raise WorkflowError('Private inbox unavailable') from None
        results=[]
        for row in rows:
            uid=row['update_id'];command=_route(row['update'],self.inbox.bot_id,extra_prefixes=('bcon:',))
            if command is None:
                results.append({'update_id':uid,'status':'not_attempted','queue_status':'deferred','delivered':None});continue
            try:
                outcome=self.ledger.result(uid)
                if outcome['status']=='not_attempted':
                    try:reply=self._process(command,uid,row['update'],workflow_enabled)
                    except Exception:
                        try:self.registry.state._auth(command.context)
                        except WorkflowError:reply=UNAVAILABLE
                        else:raise
                    if dispatch_enabled is not True:
                        results.append({'update_id':uid,'status':'local_prepared' if reply.status=='prepared' else 'unavailable','queue_status':'reply_ready','delivered':None});continue
                    def fresh():
                        try:self.registry.state._auth(command.context);current=reply
                        except WorkflowError:current=UNAVAILABLE
                        return TelegramPreparation(uid,command.chat_id,current,command.callback_id)
                    outcome=self.ledger.attempt(uid,prepare_fresh=fresh,send=self.send,dispatch_enabled=True)
                if outcome['status']=='inflight_or_unknown':queue='inflight'
                elif outcome['status'] in ('api_confirmed','cancelled','unknown','api_rejected'):
                    queue='handled' if outcome['status'] in ('api_confirmed','cancelled') else 'blocked';self.inbox.mark(uid,status=queue)
                else:raise WorkflowError('Unexpected UI dispatch outcome')
                results.append({'update_id':uid,'status':outcome['status'],'queue_status':queue,'delivered':None})
            except Exception:results.append({'update_id':uid,'status':'unavailable','queue_status':'needs_recovery','delivered':None})
        return tuple(results)
