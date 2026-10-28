"""Disabled-by-default mock-tested dispatch ledger, no HTTP client.

send/prepare_fresh are trusted runtime adapters, never public request callbacks.
No live sends are authorized by enabling a Python flag. Real use still requires
separate approved resources and a verified transport. No exactly-once delivery
claim: unknown/inflight outcomes block automatic resends and require review.
"""
import contextlib
import os
from pathlib import Path
import sqlite3
import uuid
from assistant_access import identifier
from material_versions import digest
from telegram_report_adapter import TelegramPreparation
from report_requests import PreparedReply,ReplyButton

class DispatchError(ValueError):
    pass


def _id(value,zero=False):return type(value) is int and (0 if zero else 1)<=value<2**52


def _payload(preparation):
    reply=preparation.reply
    if (type(reply) is not PreparedReply or reply.parse_mode is not None or reply.link_preview_disabled is not True
            or not isinstance(reply.text,str) or not reply.text.strip() or len(reply.text.encode('utf-16-le'))//2>4096
            or type(reply.buttons) is not tuple or len(reply.buttons)>8):
        raise DispatchError('Invalid prepared reply')
    rows=[]
    for row in reply.buttons:
        if type(row) is not tuple or not 0<len(row)<=8:raise DispatchError('Invalid keyboard')
        buttons=[]
        for button in row:
            if (type(button) is not ReplyButton or not isinstance(button.label,str) or not button.label.strip()
                    or len(button.label)>64 or not isinstance(button.callback_data,str)
                    or not 1<=len(button.callback_data.encode('utf-8'))<=64):
                raise DispatchError('Invalid keyboard button')
            buttons.append({'text':button.label,'callback_data':button.callback_data})
        rows.append(buttons)
    payload={'chat_id':preparation.chat_id,'text':reply.text,'link_preview_options':{'is_disabled':True}}
    if rows:payload['reply_markup']={'inline_keyboard':rows}
    return payload

class DispatchLedger:
    def __init__(self,path,*,namespace,bot_id):
        if not identifier(namespace) or not _id(bot_id):raise DispatchError('Explicit bot namespace required')
        self.bot_id=bot_id;self.namespace=namespace;path=Path(path).absolute()
        if path.is_symlink() or path.parent.is_symlink():raise DispatchError('State symlinks forbidden')
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if path.parent.stat().st_mode & 0o077:raise DispatchError('Private state directory required')
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        except FileExistsError:pass
        if path.stat().st_mode & 0o077:raise DispatchError('Private state file required')
        self.db=sqlite3.connect(path,timeout=5,isolation_level=None)
        try:
            tables={row[0] for row in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and tables!={'dispatch_meta','dispatch_attempts'}:raise DispatchError('Foreign or incomplete dispatch state')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            with self.transaction():
                self.db.execute('CREATE TABLE IF NOT EXISTS dispatch_meta(key TEXT PRIMARY KEY,value TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS dispatch_attempts(update_id INTEGER PRIMARY KEY,attempt TEXT,phase TEXT,payload_hash TEXT,message_id INTEGER,error_code INTEGER)')
                metadata=dict(self.db.execute('SELECT key,value FROM dispatch_meta'))
                expected={'version':'1','namespace':namespace,'bot_id':str(bot_id)}
                if not metadata and not tables:self.db.executemany('INSERT INTO dispatch_meta VALUES(?,?)',expected.items())
                elif metadata!=expected:raise DispatchError('Dispatch namespace/bot/schema mismatch')
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
    def result(self,update_id):
        if not _id(update_id,zero=True):raise DispatchError('Invalid update identity')
        row=self.db.execute('SELECT phase,message_id,error_code FROM dispatch_attempts WHERE update_id=?',(update_id,)).fetchone()
        if row is None:return {'status':'not_attempted','delivered':None}
        status='inflight_or_unknown' if row[0]=='sending' else row[0]
        return {'status':status,'api_message_id':row[1],'api_error_code':row[2],'delivered':None}
    def _finalize(self,update_id,attempt,phase,message_id,error_code):
        with self.transaction():
            changed=self.db.execute("UPDATE dispatch_attempts SET phase=?,message_id=?,error_code=? WHERE update_id=? AND attempt=? AND phase='sending'",(phase,message_id,error_code,update_id,attempt)).rowcount
            if changed!=1:raise DispatchError('Attempt state changed; review required')
    def attempt(self,update_id,*,prepare_fresh,send,dispatch_enabled=False):
        if dispatch_enabled is not True:raise DispatchError('Dispatch disabled')
        if not _id(update_id,zero=True) or not callable(prepare_fresh) or not callable(send):raise DispatchError('Trusted dispatch adapters required')
        try:
            with self.transaction():
                if self.result(update_id)['status']!='not_attempted':return self.result(update_id)
                # Local-only reauthorization/preparation, not network polling, under claim lock.
                preparation=prepare_fresh()
                if type(preparation) is not TelegramPreparation or not _id(preparation.update_id,zero=True) or preparation.update_id!=update_id or not _id(preparation.chat_id):
                    raise DispatchError('Prepared update/destination mismatch')
                if type(preparation.reply) is not PreparedReply:raise DispatchError('Invalid preparation')
                if preparation.reply.status!='prepared':
                    self.db.execute("INSERT INTO dispatch_attempts VALUES(?,?,'cancelled','',NULL,NULL)",(update_id,uuid.uuid4().hex))
                    return self.result(update_id)
                payload=_payload(preparation);attempt=uuid.uuid4().hex
                self.db.execute("INSERT INTO dispatch_attempts VALUES(?,?,'sending',?,NULL,NULL)",(update_id,attempt,digest(payload)))
            # Claim is durable BEFORE invoking the potentially side-effecting adapter.
            phase='unknown';message_id=None;error_code=None
            try:
                response=send('sendMessage',payload)
                if type(response) is dict and response.get('ok') is False and type(response.get('error_code')) is int and 100<=response['error_code']<=599:
                    phase='api_rejected';error_code=response['error_code']
                elif type(response) is dict and response.get('ok') is True:
                    result=response.get('result')
                    if (type(result) is dict and _id(result.get('message_id'))
                            and type(result.get('chat')) is dict and result['chat'].get('id')==preparation.chat_id
                            and type(result['chat'].get('id')) is int and result['chat'].get('type')=='private'
                            and type(result.get('from')) is dict and result['from'].get('id')==self.bot_id
                            and type(result['from'].get('id')) is int and result['from'].get('is_bot') is True):
                        phase='api_confirmed';message_id=result['message_id']
            except Exception:pass  # No safe knowledge of whether Telegram accepted the request.
            self._finalize(update_id,attempt,phase,message_id,error_code)
            return self.result(update_id)
        except DispatchError:raise
        except Exception:
            raise DispatchError('Dispatch outcome unavailable; do not retry blindly') from None
