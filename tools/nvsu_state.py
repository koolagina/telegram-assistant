"""Durable local state/checkpoints for the existing NVSU sync algorithm.

Single-writer SQLite state is bound to one explicit Calendar ID. No network is
performed here except through an explicitly supplied adapter during execution.
"""
import contextlib,datetime as dt,fcntl,hashlib,json,os,sqlite3
from pathlib import Path
from nvsu_sync import plan_sync,apply_sync_plan,same,decorated,overlap,event_payload
from nvsu_google import CalendarError

MAX_AGE=dt.timedelta(minutes=15)
def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(value):return hashlib.sha256(encoded(value).encode()).hexdigest()
def moment(value):
    result=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('Timezone required in proof')
    return result

def source_digest(source):return digest(source['week'])
def envelope_id(envelope):return digest({k:v for k,v in envelope.items() if k!='plan_id'})

class StateStore:
    def __init__(self,path,calendar_id):
        if not calendar_id or calendar_id=='primary':raise ValueError('Explicit target required')
        self.path=Path(path).absolute();self.calendar_id=calendar_id
        if self.path.is_symlink() or self.path.parent.is_symlink():raise ValueError('State symlinks are forbidden')
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.parent.stat().st_mode&0o077:raise ValueError('State directory must be private (mode 0700)')
        new=not self.path.exists()
        if new:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        elif self.path.stat().st_mode&0o077:raise ValueError('State file must be private (mode 0600)')
        self.db=sqlite3.connect(self.path,timeout=1)
        try:
            if new:
                self.db.executescript('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE bindings(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE plans(id TEXT PRIMARY KEY,value TEXT); CREATE TABLE operations(plan_id TEXT,number INTEGER,status TEXT,value TEXT,PRIMARY KEY(plan_id,number));')
                with self.db:self.db.executemany('INSERT INTO meta VALUES(?,?)',[('version','1'),('calendar_id',calendar_id)])
            metadata=dict(self.db.execute('SELECT key,value FROM meta'))
            if metadata!={'version':'1','calendar_id':calendar_id}:raise ValueError('State target/schema mismatch; use the correct existing state')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        except Exception:self.db.close();raise
    def __enter__(self):return self
    def __exit__(self,*args):self.db.close()
    @contextlib.contextmanager
    def locked(self):
        path=str(self.path)+'.lock';fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as error:raise ValueError('Another sync is using this state') from error
            yield
        finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
    def bindings(self):return [json.loads(value) for (value,) in self.db.execute('SELECT value FROM bindings ORDER BY key')]
    def _bindings(self,items):
        self.db.execute('DELETE FROM bindings')
        for item in items:
            ownership=item.get('ownership')
            if ownership not in ('created','linked_existing','adopted_verified'):raise ValueError('Unverified legacy ownership; explicit migration required')
            if ownership=='adopted_verified':
                proof=item.get('confirmation',{})
                if proof.get('event_id')!=item.get('event_id') or not proof.get('plan_id') or not proof.get('source_digest') or not proof.get('at'):raise ValueError('Ownership confirmation missing')
            if ownership=='created':
                key=item.get('operation_key')
                if not key:raise ValueError('Creation provenance missing')
                expected='nvsu'+hashlib.sha256((self.calendar_id+'\0'+key).encode()).hexdigest()
                if item.get('event_id') and item['event_id']!=expected:raise ValueError('Created-event ownership mismatch')
            key=item.get('event_id') or 'pending:'+item['operation_key']
            self.db.execute('INSERT INTO bindings VALUES(?,?)',(key,encoded(item)))
    def save_plan(self,envelope):
        id=envelope_id(envelope)
        if envelope.get('plan_id')!=id:raise ValueError('Plan digest mismatch')
        with self.db:self.db.execute('INSERT OR IGNORE INTO plans VALUES(?,?)',(id,encoded(envelope)))
    def stored_plan(self,id):
        row=self.db.execute('SELECT value FROM plans WHERE id=?',(id,)).fetchone()
        return json.loads(row[0]) if row else None
    def operation_status(self,id,number):
        row=self.db.execute('SELECT status FROM operations WHERE plan_id=? AND number=?',(id,number)).fetchone();return row[0] if row else None
    def unresolved(self):
        return list(self.db.execute("SELECT plan_id,number FROM operations WHERE status='APPLYING'"))
    def begin(self,id,number,operation):
        with self.db:self.db.execute('INSERT OR IGNORE INTO operations VALUES(?,?,?,?)',(id,number,'PREPARED',encoded(operation)))
    def applying(self,id,number):
        with self.db:self.db.execute('UPDATE operations SET status=? WHERE plan_id=? AND number=?',('APPLYING',id,number))
    def checkpoint(self,id,number,ledger,completed):
        with self.db:
            self._bindings(ledger)
            if completed:self.db.execute('UPDATE operations SET status=? WHERE plan_id=? AND number=?',('COMMITTED',id,number))

def prepare_envelope(source,events,store,*,requested_date,now=None,target_mode='snapshot'):
    now=now or dt.datetime.now(dt.timezone.utc)
    if target_mode not in ('live','snapshot'):raise ValueError('Explicit target mode required')
    if source.get('mode') not in ('live','fixture'):raise ValueError('Explicit source mode required')
    age=now-moment(source['fetched_at'])
    if age<dt.timedelta(seconds=-60) or age>MAX_AGE:raise ValueError('Source snapshot is stale')
    with store.locked():
        plan=plan_sync(source['week'],events,store.bindings(),requested_date=requested_date)
        if store.unresolved():
            plan['operations'].append(dict(action='review_pending_operation'));plan['ready']=False
        by_id={e['id']:e for e in events}
        for operation in plan['operations']:
            if operation.get('event_id') in by_id:operation['before_etag']=by_id[operation['event_id']].get('etag')
        envelope=dict(version=1,calendar_id=store.calendar_id,target_mode=target_mode,created_at=now.isoformat(),expires_at=(now+MAX_AGE).isoformat(),source=source,source_digest=source_digest(source),plan=plan)
        envelope['plan_id']=envelope_id(envelope);store.save_plan(envelope);return envelope

class JournalAdapter:
    def __init__(self,adapter,store,envelope):self.adapter=adapter;self.store=store;self.envelope=envelope;self.number=None;self.operation=None
    def begin(self,number,operation):
        self.number=number;self.operation=operation
        id=self.envelope['plan_id'];self.store.begin(id,number,operation)
        return self.store.operation_status(id,number)!='COMMITTED'
    def list_events(self,*args):return self.adapter.list_events(*args)
    def get_event(self,id):return self.adapter.get_event(id)
    def _status(self):return self.store.operation_status(self.envelope['plan_id'],self.number)
    def _mark(self):self.store.applying(self.envelope['plan_id'],self.number)
    def create_event(self,key,payload):
        self._mark();return self.adapter.create_event(key,payload)
    def _check(self,id,payload=None):
        actual=self.adapter.get_event(id)
        if actual is None:return None
        if decorated(actual):raise CalendarError('Protected/manual event changed; review required')
        expected=self.operation.get('before_etag')
        if not expected:raise CalendarError('Reviewed ETag required for mutation')
        if actual.get('etag')!=expected:
            if self._status()=='APPLYING' and payload is not None and same(actual,payload):return actual
            raise CalendarError('Calendar changed since reviewed preview')
        if not same(actual,self.operation['before_event']):raise CalendarError('Calendar payload changed since preview')
        return actual
    def update_event(self,id,payload):
        actual=self._check(id,payload)
        if actual is None:raise CalendarError('Update target disappeared')
        if self._status()=='APPLYING' and same(actual,payload):return
        self._mark();self.adapter.update_event(id,payload)
    def delete_event(self,id):
        actual=self._check(id)
        if actual is None:return
        self._mark();self.adapter.delete_event(id)

def execute_plan(envelope,adapter,store,*,source_verifier,now=None):
    """Explicit future application API. No CLI in this task calls this function."""
    now=now or dt.datetime.now(dt.timezone.utc)
    if not adapter.allow_writes:raise CalendarError('Calendar writes are disabled')
    if envelope.get('calendar_id')!=store.calendar_id or adapter.calendar_id!=store.calendar_id:raise ValueError('Execution target mismatch')
    if envelope_id(envelope)!=envelope.get('plan_id') or store.stored_plan(envelope['plan_id'])!=envelope:raise ValueError('Unknown or modified plan')
    if envelope['source'].get('mode')!='live' or envelope.get('target_mode')!='live':raise ValueError('Fixture/offline plans cannot be applied')
    if now>moment(envelope['expires_at']) or now<moment(envelope['created_at'])-dt.timedelta(seconds=60):raise ValueError('Plan expired or clock invalid')
    if not envelope['plan']['ready']:raise ValueError('Manual review is required')
    with store.locked():
        fresh=source_verifier()
        if fresh.get('mode')!='live' or source_digest(fresh)!=envelope['source_digest']:raise ValueError('Source changed after preview')
        age=now-moment(fresh['fetched_at'])
        if age<dt.timedelta(seconds=-60) or age>MAX_AGE:raise ValueError('Source recheck is stale')
        current=adapter.list_events(envelope['plan']['scope']['start'],envelope['plan']['scope']['end'])
        for number,operation in enumerate(envelope['plan']['operations']):
            if store.operation_status(envelope['plan_id'],number)=='COMMITTED':continue
            if operation['action']=='create':
                expected=adapter.event_id(operation['operation_key'])
                if any(overlap(event,operation['event']) and event['id']!=expected for event in current):raise CalendarError('New event appeared after preview')
            elif operation['action'] in ('update','delete'):
                if operation['action']=='update' and any(event['id']!=operation['event_id'] and overlap(event,operation['event']) for event in current):raise CalendarError('New conflict appeared after preview')
                if not operation.get('before_etag'):raise CalendarError('ETag missing in reviewed plan')
                existing=adapter.get_event(operation['event_id'])
                if existing and existing.get('etag')!=operation['before_etag']:
                    applying=store.operation_status(envelope['plan_id'],number)=='APPLYING'
                    if not (applying and operation['action']=='update' and not decorated(existing) and same(existing,operation['event'])):raise CalendarError('Calendar ETag changed after preview')
        ledger=store.bindings();journal=JournalAdapter(adapter,store,envelope)
        apply_sync_plan(envelope['plan'],journal,ledger,operation_hook=journal.begin,checkpoint=lambda number,items,done:store.checkpoint(envelope['plan_id'],number,items,done))
        return dict(plan_id=envelope['plan_id'],committed=sum(store.operation_status(envelope['plan_id'],i)=='COMMITTED' for i in range(len(envelope['plan']['operations']))))


def reconcile_plan(envelope,adapter,store):
    """Resolve only observed completed effects; never issue Calendar writes.

    Source freshness is irrelevant to historical reconciliation, but a fresh
    reviewed plan is still required before any subsequent Calendar mutation.
    Unknown/missing create outcomes remain unresolved rather than being reset.
    """
    if adapter.calendar_id!=store.calendar_id or envelope.get('calendar_id')!=store.calendar_id:raise ValueError('Reconciliation target mismatch')
    if envelope_id(envelope)!=envelope.get('plan_id') or store.stored_plan(envelope['plan_id'])!=envelope:raise ValueError('Unknown or modified plan')
    if envelope.get('target_mode')!='live':raise ValueError('Snapshot evidence cannot reconcile live operations')
    resolved=0;unknown=0
    with store.locked():
        ledger=store.bindings()
        for number,operation in enumerate(envelope['plan']['operations']):
            if store.operation_status(envelope['plan_id'],number)!='APPLYING':continue
            action=operation['action']
            if action not in ('create','update','delete'):unknown+=1;continue
            id=adapter.event_id(operation['operation_key']) if action=='create' else operation['event_id']
            actual=adapter.get_event(id)
            completed=actual is None if action=='delete' else actual is not None and not decorated(actual) and same(actual,operation['event'])
            if not completed:unknown+=1;continue
            if action=='delete':ledger[:]=[item for item in ledger if item.get('event_id')!=id]
            else:
                prior=next((item for item in ledger if item.get('event_id')==id or (action=='create' and item.get('operation_key')==operation['operation_key'])),None)
                if prior is None:unknown+=1;continue
                prior.update(event_id=id,source_refs=operation['source_refs'],last_event=event_payload(operation['event']))
            store.checkpoint(envelope['plan_id'],number,ledger,True);resolved+=1
    return dict(resolved=resolved,unresolved=unknown,calendar_writes=0)

def confirm_existing_binding(envelope,event_id,adapter,store,*,approved,source_verifier,now=None):
    """Explicitly adopt one reviewed manual lesson in LOCAL state only.

    No Calendar mutation is performed. This grants future ownership, so callers
    must obtain specific approval rather than silently adopting exact matches.
    """
    now=now or dt.datetime.now(dt.timezone.utc)
    if approved is not True:raise ValueError('Explicit ownership approval required')
    if adapter.calendar_id!=store.calendar_id or envelope.get('calendar_id')!=store.calendar_id:raise ValueError('Ownership target mismatch')
    if envelope_id(envelope)!=envelope.get('plan_id') or store.stored_plan(envelope['plan_id'])!=envelope:raise ValueError('Unknown or modified plan')
    if envelope.get('target_mode')!='live' or envelope['source'].get('mode')!='live':raise ValueError('Live reviewed evidence required')
    if now>moment(envelope['expires_at']) or now<moment(envelope['created_at'])-dt.timedelta(seconds=60):raise ValueError('Plan expired or clock invalid')
    matches=[op for op in envelope['plan']['operations'] if op['action']=='bind_existing' and op.get('event_id')==event_id]
    if len(matches)!=1:raise ValueError('Unique reviewed binding required')
    operation=matches[0]
    with store.locked():
        fresh=source_verifier();age=now-moment(fresh['fetched_at'])
        if fresh.get('mode')!='live' or source_digest(fresh)!=envelope['source_digest'] or age<dt.timedelta(seconds=-60) or age>MAX_AGE:raise ValueError('Source confirmation changed or stale')
        ledger=store.bindings();items=[item for item in ledger if item.get('event_id')==event_id]
        if len(items)!=1 or items[0].get('ownership')!='linked_existing':raise ValueError('Existing local link required')
        actual=adapter.get_event(event_id)
        if actual is None or decorated(actual) or not same(actual,operation['event']) or not operation.get('before_etag') or actual.get('etag')!=operation['before_etag']:raise ValueError('Calendar event changed; fresh review required')
        items[0].update(ownership='adopted_verified',confirmation=dict(plan_id=envelope['plan_id'],event_id=event_id,source_digest=envelope['source_digest'],at=now.isoformat()))
        with store.db:store._bindings(ledger)
