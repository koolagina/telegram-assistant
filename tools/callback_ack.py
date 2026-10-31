"""Default-off technical callback ACK ledger; not a message delivery receipt.

Only trusted verified-poll routing may supply update/query identities. No network
client, scheduler or credential loading. A claim is durable before the injected
API call; unknown/inflight never auto-repeat. Separate file, no migration of
existing inbox/dispatch schemas. Acknowledgement contains no text/URL/alert.
"""
import contextlib
import hashlib
import os
from pathlib import Path
import sqlite3
from assistant_access import identifier

class CallbackAckError(ValueError):
    pass

class CallbackAckLedger:
    def __init__(self,path,*,namespace,bot_id):
        if not identifier(namespace) or type(bot_id) is not int or not 0<bot_id<2**52:raise CallbackAckError('Explicit bot namespace required')
        self.namespace=namespace;self.bot_id=bot_id;path=Path(path).absolute()
        if path.is_symlink() or path.parent.is_symlink():raise CallbackAckError('State symlinks forbidden')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.parent.stat().st_mode & 0o077:raise CallbackAckError('Private state directory required')
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        if path.stat().st_mode & 0o077:raise CallbackAckError('Private state file required')
        self.db=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            tables={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and tables!={'callback_meta','callback_attempts'}:raise ValueError()
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS callback_meta(key TEXT PRIMARY KEY,value TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS callback_attempts(update_id INTEGER PRIMARY KEY,query_hash TEXT UNIQUE,phase TEXT,error_code INTEGER)')
                expected={'version':'1','namespace':namespace,'bot_id':str(bot_id)}
                metadata=dict(self.db.execute('SELECT key,value FROM callback_meta'))
                if not metadata and not tables:self.db.executemany('INSERT INTO callback_meta VALUES(?,?)',expected.items())
                elif metadata!=expected:raise ValueError()
        except Exception:
            self.db.close();raise CallbackAckError('Callback state unavailable') from None
    def __enter__(self):return self
    def __exit__(self,*args):self.db.close()
    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:yield;self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
    def result(self,update_id):
        if type(update_id) is not int or not 0<=update_id<2**52:raise CallbackAckError('Invalid callback identity')
        row=self.db.execute('SELECT phase,error_code FROM callback_attempts WHERE update_id=?',(update_id,)).fetchone()
        if row is None:return {'status':'not_attempted'}
        if row[0] not in ('sending','api_confirmed','api_rejected','unknown'):raise CallbackAckError('Invalid callback receipt')
        if row[0]=='api_rejected':
            if type(row[1]) is not int or not 100<=row[1]<=599:raise CallbackAckError('Invalid callback receipt')
        elif row[1] is not None:raise CallbackAckError('Invalid callback receipt')
        return {'status':'inflight_or_unknown' if row[0]=='sending' else row[0],'api_error_code':row[1]}
    def attempt(self,update_id,query_id,*,acknowledge,enabled=False):
        if enabled is not True:raise CallbackAckError('Callback acknowledgement disabled')
        if type(update_id) is not int or not 0<=update_id<2**52 or not identifier(query_id) or not callable(acknowledge):raise CallbackAckError('Invalid trusted callback identity')
        query_hash=hashlib.sha256(query_id.encode()).hexdigest()
        try:
            with self.transaction():
                old=self.db.execute('SELECT update_id,query_hash FROM callback_attempts WHERE update_id=? OR query_hash=?',(update_id,query_hash)).fetchall()
                if old:
                    if len(old)!=1 or tuple(old[0])!=(update_id,query_hash):raise CallbackAckError('Callback identity conflict')
                    return self.result(update_id)
                self.db.execute("INSERT INTO callback_attempts VALUES(?,?,'sending',NULL)",(update_id,query_hash))
            phase='unknown';error=None
            try:
                response=acknowledge('answerCallbackQuery',{'callback_query_id':query_id})
                if type(response) is dict and response.get('ok') is True and response.get('result') is True:phase='api_confirmed'
                elif type(response) is dict and response.get('ok') is False and type(response.get('error_code')) is int and 100<=response['error_code']<=599:
                    phase='api_rejected';error=response['error_code']
            except Exception:pass
            with self.transaction():
                changed=self.db.execute("UPDATE callback_attempts SET phase=?,error_code=? WHERE update_id=? AND query_hash=? AND phase='sending'",(phase,error,update_id,query_hash)).rowcount
                if changed!=1:raise CallbackAckError('Callback receipt changed; review required')
            return self.result(update_id)
        except CallbackAckError:raise
        except Exception:raise CallbackAckError('Callback outcome unavailable; no blind retry') from None
