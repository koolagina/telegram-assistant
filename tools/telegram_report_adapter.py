"""Reports-only adapter for an injected VERIFIED Telegram polling transport.

fetch_verified_updates MUST be trusted server code performing authenticated Bot
API requests over verified TLS to the configured bot. An ok/result JSON body or
this class name does NOT prove origin. Never wire a public body/LLM argument or
unverified webhook to this callable. Actual HTTP/secret/offset/ack/retry/outbox
transport is NOT implemented. No network calls, sends or delivery claims here.
"""
from dataclasses import dataclass,field
import re
from assistant_access import Context,identifier
from report_access import ReportReader
from report_requests import PreparedReply,prepare_report_reply,prepare_progress_callback

class TelegramAdapterError(ValueError):
    pass

@dataclass(frozen=True)
class TelegramPreparation:
    update_id: int
    chat_id: int = field(repr=False)
    reply: PreparedReply
    callback_query_id: str | None = field(default=None,repr=False)


def _id(value,*,zero=False):
    return type(value) is int and (0 if zero else 1)<=value<2**52


def _user(value,*,bot=False):
    return (type(value) is dict and _id(value.get('id'))
            and value.get('is_bot') is bot)


def _private_message(message,subject):
    if type(message) is not dict or not _id(message.get('message_id')) or not _id(message.get('date')):
        return False
    chat=message.get('chat')
    return type(chat) is dict and chat.get('type')=='private' and _id(chat.get('id')) and chat['id']==subject

class TelegramReportAdapter:
    def __init__(self,*,reader_factory,bot_id,fetch_verified_updates):
        if not _id(bot_id) or not callable(reader_factory) or not callable(fetch_verified_updates):
            raise TelegramAdapterError('Trusted polling adapters and bot identity required')
        self._reader=reader_factory;self._bot_id=bot_id;self._fetch=fetch_verified_updates

    def prepare_batch(self):
        """Read-only preparation; repeated update is NOT a delivery dedupe key."""
        try:
            response=self._fetch()
            if (type(response) is not dict or response.get('ok') is not True
                    or type(response.get('result')) is not list or len(response['result'])>100):
                raise TelegramAdapterError('Invalid verified polling response')
            seen=set()
            # Check envelope ambiguity before reading any private report payload.
            for update in response['result']:
                if (type(update) is not dict or not _id(update.get('update_id'),zero=True)
                        or update['update_id'] in seen
                        or len(set(update)-{'update_id'})!=1):
                    raise TelegramAdapterError('Ambiguous polling update')
                seen.add(update['update_id'])
            prepared=[]
            for update in response['result']:
                item=self._prepare(update)
                if item is not None:prepared.append(item)
            return tuple(prepared)
        except TelegramAdapterError:raise
        except Exception:
            raise TelegramAdapterError('Report preparation failed') from None

    def _prepare(self,update):
        message=update.get('message')
        query=update.get('callback_query')
        if message is not None:
            if type(message) is not dict or not _user(message.get('from')):return None
            sender=message['from']['id']
            if sender==self._bot_id or not _private_message(message,sender):return None
            text=message.get('text')
            if type(text) is not str or re.match(r'^/(progress|report)(?: |$)',text) is None:return None
            context=Context('telegram',str(sender),authenticated=True,private=True,sender=str(sender))
            reader=self._reader()
            if type(reader) is not ReportReader:raise TelegramAdapterError('Trusted report reader required')
            return TelegramPreparation(update['update_id'],sender,prepare_report_reply(reader,context,text))
        if query is not None:
            if type(query) is not dict or not _user(query.get('from')) or not identifier(query.get('id')):return None
            sender=query['from']['id'];message=query.get('message')
            if sender==self._bot_id or not _private_message(message,sender):return None
            if not _user(message.get('from'),bot=True) or message['from']['id']!=self._bot_id:return None
            data=query.get('data')
            if type(data) is not str or not data.startswith('progress:'):return None
            context=Context('telegram',str(sender),authenticated=True,private=True,sender=str(sender))
            reader=self._reader()
            if type(reader) is not ReportReader:raise TelegramAdapterError('Trusted report reader required')
            return TelegramPreparation(update['update_id'],sender,prepare_progress_callback(reader,context,data),query['id'])
        return None
