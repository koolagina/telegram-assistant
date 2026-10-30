"""Bounded read-only report/optional owner-decision inbox step. No scheduler or live bootstrap.

Default dispatch and academic routes are disabled. All reader/factory callbacks
run local-only, without network I/O; dispatch preparation runs under the ledger
claim transaction. Preload approved remote sources outside that transaction.
Caller must supply approved trusted runtime
adapters; a flag is not permission to send. Unsupported updates stay pending for
other bot handlers, so this is not a standalone replacement for the whole bot.
"""
from telegram_inbox import TelegramInbox
from report_dispatch import DispatchLedger
from telegram_report_adapter import TelegramReportAdapter

class WorkerError(ValueError):
    pass

FINAL=frozenset({'api_confirmed','api_rejected','cancelled','unknown'})

class ReportWorker:
    def __init__(self,inbox,ledger,*,reader_factory,send,decision_service_factory=None,overview_factory=None,academic_menu_factory=None):
        if (type(inbox) is not TelegramInbox or type(ledger) is not DispatchLedger
                or inbox.bot_id!=ledger.bot_id or inbox.namespace!=ledger.namespace
                or not callable(reader_factory) or not callable(send)):
            raise WorkerError('Matching trusted inbox/dispatch/runtime required')
        if decision_service_factory is not None and not callable(decision_service_factory):raise WorkerError('Invalid decision service factory')
        if any(factory is not None and not callable(factory) for factory in (overview_factory,academic_menu_factory)):raise WorkerError('Invalid academic runtime factory')
        self._overview=overview_factory;self._academic_menu=academic_menu_factory
        self._decisions=decision_service_factory
        self.inbox=inbox;self.ledger=ledger;self._reader=reader_factory;self._send=send

    def step(self,*,dispatch_enabled=False,limit=100):
        if dispatch_enabled is not True:raise WorkerError('Dispatch disabled')
        try:rows=self.inbox.pending(limit=limit)
        except Exception:raise WorkerError('Private inbox unavailable') from None
        results=[]
        for row in rows:
            update_id=row['update_id']
            try:
                outcome=self.ledger.result(update_id)
                if outcome['status']=='not_attempted':
                    adapter=TelegramReportAdapter(reader_factory=self._reader,bot_id=self.inbox.bot_id,decision_service_factory=self._decisions,
                        overview_factory=self._overview,academic_menu_factory=self._academic_menu,
                        fetch_verified_updates=lambda update=row['update']:{'ok':True,'result':[update]})
                    # Route only. Do not reuse this potentially stale reply for sending.
                    if not adapter.prepare_batch():
                        results.append({'update_id':update_id,'status':'not_attempted','queue_status':'deferred','delivered':None})
                        continue
                    def fresh():
                        prepared=adapter.prepare_batch()
                        if len(prepared)!=1:raise WorkerError('Current report preparation unavailable')
                        return prepared[0]
                    outcome=self.ledger.attempt(update_id,prepare_fresh=fresh,send=self._send,dispatch_enabled=True)
                if outcome['status']=='inflight_or_unknown':
                    # It may be an active peer. Do not turn its pending work
                    # into a failed/blocked item without verified orphan state.
                    results.append({'update_id':update_id,'status':outcome['status'],'queue_status':'inflight','delivered':None})
                    continue
                if outcome['status'] not in FINAL:raise WorkerError('Unexpected dispatch state')
                queue_status='handled' if outcome['status'] in ('api_confirmed','cancelled') else 'blocked'
                self.inbox.mark(update_id,status=queue_status)
                results.append({'update_id':update_id,'status':outcome['status'],'queue_status':queue_status,'delivered':None})
            except Exception:
                # A failed mark can leave pending+API-confirmed; next step reads
                # the durable receipt and marks without routing/sending again.
                try:status=self.ledger.result(update_id)['status']
                except Exception:status='unavailable'
                results.append({'update_id':update_id,'status':status,'queue_status':'needs_recovery','delivered':None})
        return tuple(results)
