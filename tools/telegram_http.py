"""Disabled-by-default fixed-origin Telegram Bot API client, mock-tested only.

No environment reads, CLI, retries, webhook changes, offset guessing or logging.
Enabling flags is configuration, NOT user authorization to use real resources.
opener is an injected trusted server test adapter, never a public request value.
Token necessarily appears in the Bot API URL internally: never log requests,
HTTP traces, exception internals, this instance's attributes or response bodies.
"""
import json
import re
from assistant_access import identifier
from urllib.error import HTTPError
from urllib.request import Request,build_opener,HTTPRedirectHandler

MAX_RESPONSE=1024*1024

class TelegramHTTPError(ValueError):
    pass

class NoTelegramRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise TelegramHTTPError('Redirect refused')


def _id(value,zero=False):return type(value) is int and (0 if zero else 1)<=value<2**52

class TelegramHTTP:
    def __init__(self,token,*,bot_id,opener=None,network_enabled=False,writes_enabled=False):
        if (type(token) is not str or len(token)>4096 or re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+',token) is None
                or not _id(bot_id)):
            raise TelegramHTTPError('Explicit valid bot configuration required')
        self._token=token;self._bot_id=bot_id;self._network=network_enabled is True;self._writes=writes_enabled is True
        self._open=opener if opener is not None else build_opener(NoTelegramRedirect()).open
        if not callable(self._open):raise TelegramHTTPError('Invalid trusted transport adapter')
        self._verified=False

    def _call(self,method,payload):
        if not self._network:raise TelegramHTTPError('Network disabled')
        if method not in ('getMe','getUpdates','sendMessage','answerCallbackQuery'):raise TelegramHTTPError('Method refused')
        try:
            body=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')
            if len(body)>MAX_RESPONSE:raise TelegramHTTPError('Request limit exceeded')
            request=Request('https://api.telegram.org/bot'+self._token+'/'+method,data=body,
                            headers={'Content-Type':'application/json','Accept':'application/json'},method='POST')
            try:
                response=self._open(request,timeout=20)
            except HTTPError as error:
                response=error
            with response:
                status=response.code if isinstance(response,HTTPError) else response.status
                raw=response.read(MAX_RESPONSE+1)
            if len(raw)>MAX_RESPONSE:raise TelegramHTTPError('Response limit exceeded')
            result=json.loads(raw)
            if (type(result) is not dict or type(result.get('ok')) is not bool
                    or not (status==200 or 400<=status<=599)):
                raise TelegramHTTPError('Invalid API response')
            if status!=200 and (result['ok'] is not False or result.get('error_code')!=status):
                raise TelegramHTTPError('Unverified API rejection')
            if result['ok'] is False:
                if type(result.get('error_code')) is not int or not 100<=result['error_code']<=599:
                    raise TelegramHTTPError('Invalid API rejection')
                return {'ok':False,'error_code':result['error_code']}
            return result
        except TelegramHTTPError:raise
        except Exception:
            raise TelegramHTTPError('Telegram request failed; outcome may be unknown') from None

    @property
    def bot_id(self):return self._bot_id

    def verify_bot(self):
        self._verified=False
        response=self._call('getMe',{})
        profile=response.get('result')
        if (response.get('ok') is not True or type(profile) is not dict or not _id(profile.get('id'))
                or profile['id']!=self._bot_id or profile.get('is_bot') is not True):
            raise TelegramHTTPError('Configured bot identity not verified')
        self._verified=True

    def fetch_updates(self,*,offset):
        if not self._verified:raise TelegramHTTPError('Verify configured bot before polling')
        if not _id(offset,zero=True):raise TelegramHTTPError('Explicit durable offset required')
        return self._call('getUpdates',{'offset':offset,'limit':100,'timeout':0,'allowed_updates':['message','callback_query']})

    def send(self,method,payload):
        if not self._verified or not self._writes:raise TelegramHTTPError('Verified bot and explicit dispatch configuration required')
        if method!='sendMessage' or type(payload) is not dict or not set(payload)<={'chat_id','text','link_preview_options','reply_markup'}:
            raise TelegramHTTPError('Send method/payload refused')
        try:
            if (not _id(payload.get('chat_id')) or type(payload.get('text')) is not str or not payload['text'].strip()
                    or len(payload['text'].encode('utf-16-le'))//2>4096):
                raise TelegramHTTPError('Invalid private text reply')
            body=dict(payload)
            if 'link_preview_options' in body and body['link_preview_options']!={'is_disabled':True}:
                raise TelegramHTTPError('Link previews must remain disabled')
            body['link_preview_options']={'is_disabled':True}
            return self._call(method,body)
        except TelegramHTTPError:raise
        except Exception:
            raise TelegramHTTPError('Invalid reply request') from None

    def acknowledge(self,method,payload):
        """Explicit technical no-text ACK only; not permission to send reports."""
        if not self._verified or not self._writes:raise TelegramHTTPError('Verified bot and explicit callback configuration required')
        if (method!='answerCallbackQuery' or type(payload) is not dict
                or set(payload)!={'callback_query_id'} or not identifier(payload.get('callback_query_id'))):
            raise TelegramHTTPError('Callback acknowledgement refused')
        return self._call(method,{'callback_query_id':payload['callback_query_id']})
