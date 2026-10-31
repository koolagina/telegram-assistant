"""Read-only report/optional owner-decision adapter for VERIFIED polling input.

fetch_verified_updates MUST be trusted server code performing authenticated Bot
API requests over verified TLS to the configured bot. An ok/result JSON body or
this class name does NOT prove origin. Never wire a public body/LLM argument or
unverified webhook to this callable. Actual HTTP/secret/offset/ack/retry/outbox
transport is NOT implemented. No network calls, sends or delivery claims here.
"""
from dataclasses import dataclass,field
import re
from assistant_access import Context,identifier
from decision_requests import prepare_decision_reply,prepare_decision_callback
from lecture_requests import prepare_lecture_reply
from lecture_windows import LectureWindows
from academic_menu import AcademicMenu
from academic_overview import AcademicOverview,prepare_overview_reply
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

def verified_callback_query_id(update,bot_id):
    """Structural identity from an already verified durable polling update.

    Not authentication for arbitrary JSON; no policy reads or private payload.
    Used only after a worker has a terminal business receipt for this update.
    """
    if type(update) is not dict:return None
    query=update.get('callback_query')
    if type(query) is not dict or not _user(query.get('from')) or not identifier(query.get('id')):return None
    sender=query['from']['id'];message=query.get('message')
    if sender==bot_id or not _private_message(message,sender):return None
    if not _user(message.get('from'),bot=True) or message['from']['id']!=bot_id:return None
    return query['id']

class TelegramReportAdapter:
    def __init__(self,*,reader_factory,bot_id,fetch_verified_updates,decision_service_factory=None,overview_factory=None,academic_menu_factory=None,lecture_service_factory=None):
        if not _id(bot_id) or not callable(reader_factory) or not callable(fetch_verified_updates):
            raise TelegramAdapterError('Trusted polling adapters and bot identity required')
        if decision_service_factory is not None and not callable(decision_service_factory):raise TelegramAdapterError('Invalid trusted decision service')
        if overview_factory is not None and not callable(overview_factory):raise TelegramAdapterError('Invalid trusted overview factory')
        if academic_menu_factory is not None and not callable(academic_menu_factory):raise TelegramAdapterError('Invalid trusted academic menu factory')
        if lecture_service_factory is not None and not callable(lecture_service_factory):raise TelegramAdapterError('Invalid trusted lecture service factory')
        self._lecture=lecture_service_factory
        self._academic_menu=academic_menu_factory
        self._overview=overview_factory
        self._decisions=decision_service_factory
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
            if type(text) is not str or re.match(r'^/(progress|report|decisions|overview|student|lecturecode|attend)(?: |$)',text) is None:return None
            context=Context('telegram',str(sender),authenticated=True,private=True,sender=str(sender))
            if text.startswith(('/lecturecode','/attend')):
                if self._lecture is None:return None
                service=self._lecture()
                if type(service) is not LectureWindows:raise TelegramAdapterError('Trusted lecture service required')
                request_id='telegram:'+str(self._bot_id)+':'+str(update['update_id'])
                return TelegramPreparation(update['update_id'],sender,prepare_lecture_reply(service,context,text,request_id=request_id))
            if text.startswith(('/overview','/student')):
                if self._academic_menu is not None and re.fullmatch(r'/(overview|student)(?: page [^ ]+)?',text):
                    menu=self._academic_menu()
                    if type(menu) is not AcademicMenu:raise TelegramAdapterError('Trusted academic menu required')
                    return TelegramPreparation(update['update_id'],sender,menu.prepare(context,text))
                if self._overview is None:return None
                service=self._overview()
                if type(service) is not AcademicOverview:raise TelegramAdapterError('Trusted overview required')
                return TelegramPreparation(update['update_id'],sender,prepare_overview_reply(service,context,text))
            if text.startswith('/decisions'):
                if self._decisions is None:return None
                return TelegramPreparation(update['update_id'],sender,prepare_decision_reply(self._decisions(),context,text))
            reader=self._reader()
            if type(reader) is not ReportReader:raise TelegramAdapterError('Trusted report reader required')
            return TelegramPreparation(update['update_id'],sender,prepare_report_reply(reader,context,text))
        if query is not None:
            if type(query) is not dict or not _user(query.get('from')) or not identifier(query.get('id')):return None
            sender=query['from']['id'];message=query.get('message')
            if sender==self._bot_id or not _private_message(message,sender):return None
            if not _user(message.get('from'),bot=True) or message['from']['id']!=self._bot_id:return None
            data=query.get('data')
            if type(data) is not str or not data.startswith(('progress:','dec:','acad:')):return None
            context=Context('telegram',str(sender),authenticated=True,private=True,sender=str(sender))
            if data.startswith('acad:'):
                if self._academic_menu is None:return None
                menu=self._academic_menu()
                if type(menu) is not AcademicMenu:raise TelegramAdapterError('Trusted academic menu required')
                return TelegramPreparation(update['update_id'],sender,menu.callback(context,data),query['id'])
            if data.startswith('dec:'):
                if self._decisions is None:return None
                return TelegramPreparation(update['update_id'],sender,prepare_decision_callback(self._decisions(),context,data),query['id'])
            reader=self._reader()
            if type(reader) is not ReportReader:raise TelegramAdapterError('Trusted report reader required')
            return TelegramPreparation(update['update_id'],sender,prepare_progress_callback(reader,context,data),query['id'])
        return None
