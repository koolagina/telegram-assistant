"""Calendar synchronization plan and an adapter protocol model.

No Google SDK, credentials, network, or CLI writes. Only event time, discipline and
location may be passed to an adapter. Source ownership lives in an external ledger.
Durable checkpoints and Google transport are supplied separately by nvsu_state
and nvsu_google; this module remains independently testable with memory adapters.
"""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import json
from zoneinfo import ZoneInfo

ZONE=ZoneInfo('Asia/Yekaterinburg')
FIELDS=('start','end','title','location')

def instant(value):
    try:
        value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError,AttributeError) as error:
        raise ValueError('Invalid event time') from error
    if value.tzinfo is None:
        raise ValueError('Timezone required')
    return value

def calendar_payload(event):
    """Normalize existing manual/all-day events without requiring a lesson room."""
    start,end=instant(event.get('start')),instant(event.get('end'))
    if end<=start:raise ValueError('Invalid event interval')
    title,location=event.get('title',''),event.get('location','')
    if not isinstance(title,str) or not isinstance(location,str):raise ValueError('Invalid Calendar text fields')
    return dict(start=start.astimezone(ZONE).isoformat(),end=end.astimezone(ZONE).isoformat(),title=title.strip(),location=location.strip())

def event_payload(event):
    """Only desired lessons require a discipline and room."""
    result=calendar_payload(event)
    if not result['title'] or not result['location']:raise ValueError('Discipline and room required')
    return result

def decorated(event):
    return bool(event.get('protected') or event.get('description') or event.get('attendees'))

def same(a,b):
    return calendar_payload(a)==calendar_payload(b)

def overlap(a,b):
    return instant(a['start'])<instant(b['end']) and instant(a['end'])>instant(b['start'])

def refs(item):
    values=item.get('source_refs')
    if not isinstance(values,list) or not values or any(not isinstance(v,str) or not v for v in values):
        raise ValueError('Source references required')
    return set(values)

def plan_sync(week,existing,bindings,*,requested_date):
    start,end=dt.date.fromisoformat(week['week_start']),dt.date.fromisoformat(week['week_end'])
    date=dt.date.fromisoformat(requested_date)
    if end!=start+dt.timedelta(days=6) or start.weekday()!=0 or not start<=date<=end:
        raise ValueError('Requested date/week mismatch')
    if week.get('status') not in ('parsed','source_reports_no_schedule'):
        raise ValueError('Incomplete or failed source cannot be synchronized')
    if week['status']=='source_reports_no_schedule' and week['lessons']:
        raise ValueError('Conflicting source state')
    lower=dt.datetime.combine(start,dt.time(),ZONE).isoformat()
    upper=dt.datetime.combine(end+dt.timedelta(days=1),dt.time(),ZONE).isoformat()
    scope=dict(start=lower,end=upper)
    targets={}
    for event in existing:
        if not event.get('id') or event['id'] in targets:
            raise ValueError('Missing/duplicate Calendar event ID')
        calendar_payload(event)
        targets[event['id']]=event
    desired=[]
    for lesson in week['lessons']:
        payload=event_payload(lesson)
        if not lower<=payload['start']<payload['end']<=upper:
            raise ValueError('Source lesson outside selected week')
        aliases=refs(lesson)
        identical=next((x for x in desired if same(x,payload)),None)
        if identical:
            identical['source_refs']=sorted(refs(identical)|aliases)
        else:
            desired.append(dict(**payload,source_refs=sorted(aliases)))
    managed={};pending=[]
    for binding in bindings:
        previous=event_payload(binding['last_event']);refs(binding)
        if not lower<=previous['start']<upper:
            continue
        if not binding.get('event_id'):
            pending.append(binding);continue
        if binding['event_id'] in managed:
            raise ValueError('Duplicate ledger ownership')
        managed[binding['event_id']]=binding
    operations=[];remaining=set(range(len(desired)));unmatched=set(managed);matches={}
    # Match unchanged occurrences first, then only a unique source-reference pair.
    # Do not put mutable time/title/room into the only persistent identity.
    for exact in (True,False):
        while True:
            edges={i:[key for key in sorted(unmatched) if (same(desired[i],managed[key]['last_event']) if exact else bool(refs(desired[i])&refs(managed[key])))] for i in sorted(remaining)}
            singles=[(i,keys[0]) for i,keys in edges.items() if len(keys)==1 and sum(keys[0] in other for other in edges.values())==1]
            if not singles:
                break
            for i,key in singles:
                matches[i]=key;remaining.remove(i);unmatched.remove(key)
    blocked=set()
    for i,lesson in enumerate(desired):
        payload=event_payload(lesson)
        base=dict(source_refs=lesson['source_refs'],event=payload)
        conflicting_source=any(j!=i and overlap(lesson,other) for j,other in enumerate(desired))
        unresolved=[key for key in unmatched if refs(lesson)&refs(managed[key])]
        if conflicting_source:
            operations.append(dict(action='review_source_overlap',**base));blocked.update(unresolved)
            if i in matches:blocked.add(matches[i])
            continue
        if any(refs(lesson)&refs(item) for item in pending):
            operations.append(dict(action='review_pending_create',**base));blocked.update(unresolved);continue
        if i in matches:
            key=matches[i];binding=managed[key];current=targets.get(key)
            if current is None:
                operations.append(dict(action='review_missing_target',event_id=key,**base));continue
            if decorated(current) or (not same(current,binding['last_event']) and not same(current,payload)):
                operations.append(dict(action='review_manual_edit',event_id=key,**base));continue
            others=[e for eid,e in targets.items() if eid!=key and overlap(e,payload)]
            if others:
                operations.append(dict(action='review_overlap',event_id=key,**base));continue
            if binding.get('ownership')=='linked_existing' and not same(current,payload):
                operations.append(dict(action='review_ownership',event_id=key,**base));continue
            action='unchanged' if same(current,payload) else 'update'
            operations.append(dict(action=action,event_id=key,before_event=calendar_payload(current),**base))
        elif unresolved:
            blocked.update(unresolved);operations.append(dict(action='review_source_identity',**base))
        else:
            overlaps=[event for event in targets.values() if overlap(event,payload)]
            if len(overlaps)==1 and not decorated(overlaps[0]) and same(overlaps[0],payload) and overlaps[0]['id'] not in managed:
                operations.append(dict(action='bind_existing',event_id=overlaps[0]['id'],before_event=calendar_payload(overlaps[0]),**base))
            elif overlaps:
                blocked.update(event['id'] for event in overlaps if event['id'] in unmatched)
                operations.append(dict(action='review_overlap',**base))
            else:
                # An unlinked old occurrence may have moved. Do not guess a new
                # identity or create beside a likely old manual/imported lesson.
                semantic=[event for event in targets.values() if event.get('title')==payload['title'] and not any(same(event,item) for item in desired)]
                related=[key for key in unmatched if managed[key]['last_event'].get('title')==payload['title']]
                if related:
                    blocked.update(related);operations.append(dict(action='review_source_identity',**base));continue
                if semantic:
                    operations.append(dict(action='review_unlinked_lesson',**base));continue
                key=hashlib.sha256(json.dumps([scope,sorted(refs(lesson)),payload],sort_keys=True).encode()).hexdigest()
                operations.append(dict(action='create',operation_key=key,**base))
    for key in sorted(unmatched-blocked):
        current=targets.get(key);binding=managed[key]
        if current is None:
            operations.append(dict(action='review_missing_target',event_id=key))
        elif binding.get('ownership')=='linked_existing':
            operations.append(dict(action='review_ownership',event_id=key))
        elif decorated(current) or not same(current,binding['last_event']):
            operations.append(dict(action='review_manual_edit',event_id=key))
        else:
            operations.append(dict(action='delete',event_id=key,before_event=calendar_payload(current)))
    if pending and not any(o['action']=='review_pending_create' for o in operations):
        operations.append(dict(action='review_pending_create'))
    return dict(scope=scope,requested_date=requested_date,source_status=week['status'],ready=all(not o['action'].startswith('review') for o in operations),operations=operations)

def apply_sync_plan(plan,adapter,ledger,*,operation_hook=None,checkpoint=None):
    """Protocol model: all preflight checks precede writes; caller persists ledger.

    This is intentionally not called by the read-only CLI. The repository supplies
    memory adapters in tests and a separately guarded Google adapter.
    """
    if not plan['ready']:
        raise ValueError('Review required before any writes')
    resolutions={}
    current=adapter.list_events(plan['scope']['start'],plan['scope']['end'])
    for index,operation in enumerate(plan['operations']):
        action=operation['action']
        if action=='create':
            overlaps=[e for e in current if overlap(e,operation['event'])]
            if len(overlaps)==1 and not decorated(overlaps[0]) and same(overlaps[0],operation['event']):
                resolutions[index]=overlaps[0]['id']
            elif overlaps:
                raise ValueError('Calendar changed after preview')
        elif 'before_event' in operation:
            actual=adapter.get_event(operation['event_id'])
            if action=='delete' and actual is None:
                continue
            if actual is None or decorated(actual) or (not same(actual,operation['before_event']) and not (action=='update' and same(actual,operation['event']))):
                raise ValueError('Calendar changed after preview')
    for index,operation in enumerate(plan['operations']):
        if operation_hook is not None and operation_hook(index,operation) is False:continue
        action=operation['action']
        if action=='delete':
            adapter.delete_event(operation['event_id'])
            ledger[:]=[item for item in ledger if item.get('event_id')!=operation['event_id']]
            if checkpoint is not None:checkpoint(index,ledger,True)
            continue
        if action=='create':
            pending=next((item for item in ledger if item.get('operation_key')==operation['operation_key']),None)
            if pending is None:
                pending=dict(event_id=None,operation_key=operation['operation_key'],ownership='created',source_refs=operation['source_refs'],last_event=copy.deepcopy(operation['event']))
                ledger.append(pending)
            if checkpoint is not None:checkpoint(index,ledger,False)
            event_id=resolutions.get(index) or adapter.create_event(operation['operation_key'],copy.deepcopy(operation['event']))
            pending['event_id']=event_id
        else:
            event_id=operation['event_id']
            if action=='update' and not same(adapter.get_event(event_id),operation['event']):
                adapter.update_event(event_id,copy.deepcopy(operation['event']))
        binding=dict(event_id=event_id,source_refs=operation['source_refs'],last_event=copy.deepcopy(operation['event']))
        if action=='bind_existing':binding['ownership']='linked_existing'
        elif action=='create':binding['ownership']='created'
        prior=next((item for item in ledger if item.get('event_id')==event_id),None)
        if prior is None:ledger.append(binding)
        else:prior.update(binding)
        if checkpoint is not None:checkpoint(index,ledger,True)
