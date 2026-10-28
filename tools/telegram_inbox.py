"""Private durable store-before-ack inbox, mock-tested polling protocol.

No scheduler, CLI, webhook change or public payload endpoint. poll_once requires
an already verified trusted client; no real API is called by module import.
Only one coordinated polling owner may use a bot. Never run alongside the live
GAS poller or another independent cursor. Retention/idle reset/failover still need
integration review; this does not guarantee recovery of expired server backlog.
"""
import contextlib
import json
import os
from pathlib import Path
import sqlite3
from assistant_access import identifier
from material_versions import digest

class InboxError(ValueError):
    pass


def _id(value):return type(value) is int and 0<=value<2**52

class TelegramInbox:
    def __init__(self,path,*,namespace,bot_id):
        if not identifier(namespace) or not _id(bot_id) or bot_id==0:raise InboxError('Explicit bot namespace required')
        self.bot_id=bot_id;self.namespace=namespace
        path=Path(path).absolute()
        if path.is_symlink() or path.parent.is_symlink():raise InboxError('State symlinks forbidden')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.parent.stat().st_mode & 0o077:raise InboxError('Private state directory required')
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        if path.stat().st_mode & 0o077:raise InboxError('Private state file required')
        self.db=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            tables={row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and tables!={'inbox_meta','inbox_updates'}:raise InboxError('Foreign or incomplete inbox')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS inbox_meta(key TEXT PRIMARY KEY,value TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS inbox_updates(update_id INTEGER PRIMARY KEY,payload TEXT,payload_hash TEXT,status TEXT)')
                metadata=dict(self.db.execute('SELECT key,value FROM inbox_meta'))
                expected={'version':'1','namespace':namespace,'bot_id':str(bot_id)}
                if not metadata and not tables:
                    self.db.executemany('INSERT INTO inbox_meta VALUES(?,?)',dict(expected,next_offset='0').items())
                elif {k:v for k,v in metadata.items() if k!='next_offset'}!=expected:raise InboxError('Inbox namespace/bot/schema mismatch')
                self.offset()
        except Exception:
            self.db.close();raise
    def __enter__(self):return self
    def __exit__(self,*args):self.db.close()
    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def offset(self):
        try:
            raw=self.db.execute("SELECT value FROM inbox_meta WHERE key='next_offset'").fetchone()[0]
            value=int(raw)
            if not _id(value) or str(value)!=raw:raise InboxError('Invalid durable cursor')
            return value
        except Exception:
            raise InboxError('Durable cursor unavailable') from None
    def _insert(self,update,payload):
        self.db.execute("INSERT INTO inbox_updates VALUES(?,?,?,'pending')",(update['update_id'],payload,digest(update)))
    def store_batch(self,response,*,expected_offset):
        try:
            if (not _id(expected_offset) or type(response) is not dict or response.get('ok') is not True
                    or type(response.get('result')) is not list or len(response['result'])>100):
                raise InboxError('Invalid verified batch')
            encoded=json.dumps(response,ensure_ascii=False,allow_nan=False,separators=(',',':'))
            if len(encoded.encode())>1024*1024:raise InboxError('Verified batch limit exceeded')
            seen=set();updates=response['result']
            for update in updates:
                if (type(update) is not dict or not _id(update.get('update_id'))
                        or update['update_id']<expected_offset or update['update_id'] in seen
                        or len(set(update)-{'update_id'})!=1):
                    raise InboxError('Ambiguous or out-of-scope update; no cursor reset guessing')
                seen.add(update['update_id'])
            next_offset=max(seen)+1 if seen else expected_offset
            if not _id(next_offset):raise InboxError('Cursor limit reached')
            with self.transaction():
                if self.offset()!=expected_offset:raise InboxError('Cursor changed during fetch; reload')
                for update in updates:
                    payload=json.dumps(update,ensure_ascii=False,allow_nan=False,separators=(',',':'))
                    self._insert(update,payload)
                self.db.execute("UPDATE inbox_meta SET value=? WHERE key='next_offset'",(str(next_offset),))
            return {'stored':len(updates),'next_offset':next_offset}
        except InboxError:raise
        except Exception:
            raise InboxError('Batch not confirmed; reload durable cursor') from None
    def pending(self,*,limit=100):
        try:
            if type(limit) is not int or not 1<=limit<=100:raise InboxError('Invalid queue limit')
            result=[]
            for update_id,payload,expected_hash in self.db.execute("SELECT update_id,payload,payload_hash FROM inbox_updates WHERE status='pending' ORDER BY update_id LIMIT ?",(limit,)):
                update=json.loads(payload)
                if type(update) is not dict or update.get('update_id')!=update_id or digest(update)!=expected_hash:
                    raise InboxError('Private inbox payload integrity mismatch')
                result.append({'update_id':update_id,'update':update})
            return tuple(result)
        except Exception:
            raise InboxError('Inbox payload unavailable') from None
    def mark(self,update_id,*,status):
        if not _id(update_id) or status not in ('handled','ignored','blocked'):raise InboxError('Invalid handling outcome')
        with self.transaction():
            row=self.db.execute('SELECT status FROM inbox_updates WHERE update_id=?',(update_id,)).fetchone()
            if row is None or row[0] not in ('pending',status):raise InboxError('Handling outcome conflict')
            self.db.execute('UPDATE inbox_updates SET status=? WHERE update_id=?',(status,update_id))


def poll_once(client,inbox):
    """The offset acknowledges only updates committed by an earlier store_batch.

    No processing/sends occur here. On persistence failure do not invent a new
    cursor or confirm the just-received batch. No automatic retry loop.
    """
    if type(getattr(client,'bot_id',None)) is not int or client.bot_id!=inbox.bot_id:
        raise InboxError('Polling client and inbox bot mismatch')
    offset=inbox.offset()
    try:response=client.fetch_updates(offset=offset)
    except Exception:raise InboxError('Polling failed; durable cursor unchanged') from None
    return inbox.store_batch(response,expected_offset=offset)
