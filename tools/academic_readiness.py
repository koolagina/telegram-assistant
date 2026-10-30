"""Advisory local runtime inspection; never a launch gate or authorization.

Accepts already-open trusted local objects, never credentials, filesystem paths,
public JSON, a network provider or saved user answers. Executes SELECT only on
queue/receipt metadata. Does not call factories/loaders, read update payloads,
query APIs, send, mark, repair or start a worker. No live readiness can be proven
by this function; ready_for_live is always False.
"""
from assistant_access import AccessPolicy
from academic_progress import ProgressReader
from academic_overview import AcademicOverview
from academic_menu import AcademicMenu
from report_worker import ReportWorker

class ReadinessError(ValueError):
    pass

INBOX_STATES=('pending','handled','ignored','blocked')
DISPATCH_STATES=('sending','api_confirmed','api_rejected','cancelled','unknown')


def _counts(db,table,field,allowed):
    # Table/field names are fixed internal constants, never user input.
    result={name:0 for name in allowed}
    for state,count in db.execute(f'SELECT {field},COUNT(*) FROM {table} GROUP BY {field}'):
        if state not in result or type(count) is not int or count<0:raise ValueError()
        result[state]=count
    return result


def inspect_academic_runtime(worker,*,policy,journal,overview,menu):
    """Aggregate consistency of supplied objects, NOT fresh real permissions.

    policy is an authoritative snapshot supplied by trusted code. Binding counts
    are structural, not proof of authentication, grant validity or runtime access.
    Remote OAuth, deployment, source freshness and poll ownership remain unknown.
    Schema v1 metadata is checked on both stores; no state migration occurs.
    """
    try:
        if (type(worker) is not ReportWorker or type(policy) is not AccessPolicy
                or type(journal) is not ProgressReader or type(overview) is not AcademicOverview
                or type(menu) is not AcademicMenu):raise ValueError()
        inbox=worker.inbox;ledger=worker.ledger
        if inbox.namespace!=ledger.namespace or inbox.bot_id!=ledger.bot_id:raise ValueError()
        expected={'version':'1','namespace':inbox.namespace,'bot_id':str(inbox.bot_id)}
        inbox_meta=dict(inbox.db.execute('SELECT key,value FROM inbox_meta'))
        if ({k:v for k,v in inbox_meta.items() if k!='next_offset'}!=expected
                or dict(ledger.db.execute('SELECT key,value FROM dispatch_meta'))!=expected):raise ValueError()
        inbox.offset()  # Validates cursor without outputting it.
        queue=_counts(inbox.db,'inbox_updates','status',INBOX_STATES)
        dispatch=_counts(ledger.db,'dispatch_attempts','phase',DISPATCH_STATES)
        callback={'configured':worker._callback_ledger is not None}
        if worker._callback_ledger is not None:
            ack=worker._callback_ledger
            if dict(ack.db.execute('SELECT key,value FROM callback_meta'))!=expected:raise ValueError()
            callback.update(_counts(ack.db,'callback_attempts','phase',('sending','api_confirmed','api_rejected','unknown')))
        blockers=[];review=[]
        if callback['configured'] and (callback['sending'] or callback['unknown'] or callback['api_rejected']):review.append('callback_outcomes_need_review')
        if worker._overview is None or worker._academic_menu is None:blockers.append('academic_factories_not_configured')
        # Object identity is local wiring evidence; factories are deliberately NOT
        # invoked, so their eventual result still needs integration verification.
        if overview._journal is not journal:blockers.append('overview_journal_mismatch')
        if menu._journal is not journal or menu._overview is not overview:blockers.append('menu_readers_mismatch')
        bindings=sum(b.confirmed is True and b.active is True for b in policy.bindings.values())
        if not bindings:blockers.append('confirmed_bindings_missing')
        if not journal._maps:blockers.append('journal_mappings_missing')
        mapping_conflicts=0
        for m in journal._maps.values():
            e=policy.enrollments.get(m.enrollment_id)
            if e is None or (e.student_id,e.discipline_id,e.group_id)!=(m.student_id,m.discipline_id,m.group_id):mapping_conflicts+=1
        if mapping_conflicts:blockers.append('journal_policy_mismatch')
        catalog_missing=sum(entry.enrollment_id not in journal._maps for entry in menu._entries)
        if catalog_missing:blockers.append('catalog_mapping_missing')
        report_conflicts=0
        for link in overview._reviews._links.values():
            e=policy.enrollments.get(link.enrollment_id)
            if e is None or (e.student_id,e.discipline_id,e.group_id)!=(link.student_id,link.discipline_id,link.group_id):report_conflicts+=1
        if report_conflicts:blockers.append('report_policy_mismatch')
        if dispatch['sending'] or dispatch['unknown'] or dispatch['api_rejected']:review.append('dispatch_outcomes_need_review')
        if queue['blocked']:review.append('blocked_updates_need_review')
        # Bound the cross-store metadata comparison; no raw update data is read.
        pending=inbox.db.execute("SELECT update_id FROM inbox_updates WHERE status='pending' ORDER BY update_id LIMIT 10001").fetchall()
        complete=len(pending)<=10000;pending_final=0
        if complete:
            for (update_id,) in pending:
                row=ledger.db.execute('SELECT phase FROM dispatch_attempts WHERE update_id=?',(update_id,)).fetchone()
                if row is not None and row[0] in ('api_confirmed','api_rejected','cancelled','unknown'):pending_final+=1
        else:
            review.append('pending_receipt_check_incomplete');pending_final=None
        queue.update(pending_with_final_receipt=pending_final,pending_receipt_check_complete=complete)
        # Any such receipt is operational reconciliation work, not permission to
        # resend. Unknown/rejected final receipts still need review, not replay.
        if pending_final:review.append('pending_receipts_need_reconciliation')
        return {
            'format_version':1,'mode':'local_metadata_only',
            'local_status':'blocked' if blockers else ('needs_review' if review else 'consistent'),
            'blockers':sorted(blockers+review),'queue':queue,'dispatch':dispatch,'callback_ack':callback,
            'structure':{'confirmed_active_binding_records':bindings,'journal_mappings':len(journal._maps),
                         'mapping_conflicts':mapping_conflicts,'catalog_entries':len(menu._entries),
                         'catalog_missing_mappings':catalog_missing,'report_links':len(overview._reviews._links),
                         'report_identity_conflicts':report_conflicts},
            'unverified':['authenticated_transport','factory_result_wiring','live_resource_access','source_freshness',
                          'single_poll_owner','deployment_state','bounded_live_acceptance','retention_and_backup'],
            'ready_for_live':False,'live_verified':False,'writes':0,'messages_sent':0,'polling_started':False,
        }
    except Exception:raise ReadinessError('Runtime inspection unavailable') from None
