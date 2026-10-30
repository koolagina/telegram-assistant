"""Injected HTTP response only, no real token or network."""
from pathlib import Path
import sys
import unittest
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from telegram_http import TelegramHTTPError
import test_telegram_http as fixtures

class CallbackHTTPTests(unittest.TestCase):
    def setUp(self):self.f=fixtures.HTTPTests();self.f.setUp()
    def test_verified_explicit_write_fixed_ack_endpoint(self):
        client=self.f.verified(writes_enabled=True);self.f.responses.append({'ok':True,'result':True})
        self.assertEqual(client.acknowledge('answerCallbackQuery',{'callback_query_id':'fixture-query'}),{'ok':True,'result':True})
        req=self.f.calls[-1][0];self.assertTrue(req.full_url.endswith('/answerCallbackQuery'));self.assertEqual(json.loads(req.data),{'callback_query_id':'fixture-query'})
    def test_no_text_alert_url_or_arbitrary_method(self):
        client=self.f.verified(writes_enabled=True)
        for payload in ({'callback_query_id':'fixture','text':'Private'},{'callback_query_id':'fixture','url':'https://invalid'},{'callback_query_id':''}):
            with self.assertRaises(TelegramHTTPError):client.acknowledge('answerCallbackQuery',payload)
        with self.assertRaises(TelegramHTTPError):client.acknowledge('sendMessage',{'callback_query_id':'fixture'})
        self.assertEqual(len(self.f.calls),1)
    def test_default_write_disabled(self):
        client=self.f.verified()
        with self.assertRaises(TelegramHTTPError):client.acknowledge('answerCallbackQuery',{'callback_query_id':'fixture'})
        self.assertEqual(len(self.f.calls),1)
