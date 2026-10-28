"""Injected HTTP only. Short fake credential; no real network or secrets."""
import io
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError,URLError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from telegram_http import TelegramHTTP,TelegramHTTPError

class Response:
    status=200
    def __init__(self,data):self.data=json.dumps(data).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.data[:n]

class HTTPTests(unittest.TestCase):
    def setUp(self):self.calls=[];self.responses=[]
    def opened(self,request,timeout):
        self.calls.append((request,timeout));response=self.responses.pop(0)
        if isinstance(response,Exception):raise response
        return Response(response)
    def client(self,**kwargs):return TelegramHTTP('1:fake',bot_id=9001,opener=self.opened,**kwargs)
    def verified(self,**kwargs):
        self.responses.append({'ok':True,'result':{'id':9001,'is_bot':True}})
        client=self.client(network_enabled=True,**kwargs);client.verify_bot();return client
    def test_default_disabled_makes_no_request(self):
        with self.assertRaises(TelegramHTTPError):self.client().verify_bot()
        self.assertEqual(self.calls,[])
    def test_bot_profile_must_match_and_reads_need_verification(self):
        client=self.client(network_enabled=True)
        with self.assertRaises(TelegramHTTPError):client.fetch_updates(offset=1)
        self.responses.append({'ok':True,'result':{'id':9002,'is_bot':True}})
        with self.assertRaises(TelegramHTTPError):client.verify_bot()
    def test_fixed_https_post_no_user_endpoint_and_no_implicit_offset(self):
        client=self.verified();self.responses.append({'ok':True,'result':[]})
        client.fetch_updates(offset=17)
        request,timeout=self.calls[-1]
        self.assertEqual(request.get_method(),'POST');self.assertEqual(timeout,20)
        self.assertEqual(request.full_url,'https://api.telegram.org/bot1:fake/getUpdates')
        body=json.loads(request.data);self.assertEqual(body['offset'],17)
        self.assertEqual(body['allowed_updates'],['message','callback_query'])
    def test_send_disabled_even_after_bot_verification(self):
        client=self.verified()
        with self.assertRaises(TelegramHTTPError):client.send('sendMessage',{'chat_id':103,'text':'x'})
        self.assertEqual(len(self.calls),1)
    def test_known_http_rejection_returns_only_structured_api_response(self):
        client=self.verified(writes_enabled=True)
        body=json.dumps({'ok':False,'error_code':429,'description':'not logged'}).encode()
        self.responses.append(HTTPError('private-url',429,'error',{},io.BytesIO(body)))
        response=client.send('sendMessage',{'chat_id':103,'text':'Synthetic'})
        self.assertFalse(response['ok']);self.assertEqual(response['error_code'],429)
    def test_transport_exception_does_not_expose_credential_or_url(self):
        client=self.verified(writes_enabled=True);self.responses.append(URLError('https://secret-credential'))
        with self.assertRaises(TelegramHTTPError) as caught:client.send('sendMessage',{'chat_id':103,'text':'Synthetic'})
        self.assertNotIn('fake',str(caught.exception));self.assertNotIn('secret',str(caught.exception))
    def test_unsupported_method_and_invalid_offset_do_not_request(self):
        client=self.verified(writes_enabled=True)
        for method in ['deleteWebhook','setWebhook','deleteMessage','https://evil.invalid']:
            with self.assertRaises(TelegramHTTPError):client.send(method,{})
        for offset in [True,-1,None]:
            with self.assertRaises(TelegramHTTPError):client.fetch_updates(offset=offset)
        self.assertEqual(len(self.calls),1)
    def test_invalid_api_result_cannot_authenticate_bot(self):
        for response in [{'ok':False},{'ok':True,'result':{'id':9001,'is_bot':False}},{'ok':True,'result':{'id':True,'is_bot':True}}]:
            self.responses.append(response)
            with self.assertRaises(TelegramHTTPError):self.client(network_enabled=True).verify_bot()
    def test_api_size_is_bounded(self):
        from unittest.mock import patch
        client=self.client(network_enabled=True);self.responses.append({'ok':True,'result':{'id':9001,'is_bot':True}})
        with patch('telegram_http.MAX_RESPONSE',4):
            with self.assertRaises(TelegramHTTPError):client.verify_bot()
    def test_redirects_are_refused(self):
        from telegram_http import NoTelegramRedirect
        with self.assertRaises(TelegramHTTPError):NoTelegramRedirect().redirect_request(None,None,302,'redirect',{},'https://evil.invalid')
