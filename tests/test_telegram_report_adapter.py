"""Verified-transport adapter exercised with injected offline API responses."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from telegram_report_adapter import TelegramReportAdapter,TelegramAdapterError
from report_access import ReportReader
import test_report_access as fixtures

BOT=9001
def message(sender=103,text='/progress'):
    return {'message_id':11,'date':1793160000,'from':{'id':sender,'is_bot':False,'username':'owner'},'chat':{'id':sender,'type':'private'},'text':text}

def update(sender=103,text='/progress'):
    return {'update_id':1,'message':message(sender,text)}

class TelegramAdapterTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ReportTests();self.f.setUp()
        bindings=tuple(replace(b,subject={'001':'101','002':'102','003':'103','004':'104'}.get(b.subject,b.subject)) for b in self.f.fixture.bindings)
        self.f.policy=self.f.fixture.policy(bindings=bindings)
    def reader(self):return ReportReader([self.f.link],policy_provider=lambda:self.f.policy,load_result=self.f.load,clock=lambda:fixtures.NOW)
    def adapter(self,updates):return TelegramReportAdapter(reader_factory=self.reader,bot_id=BOT,fetch_verified_updates=lambda:{'ok':True,'result':updates})
    def test_private_user_id_comes_from_api_fields_not_username(self):
        prepared=self.adapter([update()]).prepare_batch()
        self.assertEqual(len(prepared),1);self.assertEqual(prepared[0].chat_id,103)
        self.assertEqual(prepared[0].reply.status,'prepared')
        self.assertFalse(hasattr(prepared[0],'delivered'))
    def test_group_sender_mismatch_bot_and_boolean_ids_do_not_load(self):
        for change in ['group','mismatch','bot','boolean']:
            data=update()
            if change=='group':data['message']['chat']['type']='group'
            if change=='mismatch':data['message']['chat']['id']=104
            if change=='bot':data['message']['from']['is_bot']=True
            if change=='boolean':data['message']['from']['id']=True
            self.assertEqual(self.adapter([data]).prepare_batch(),())
        self.assertEqual(self.f.loads,[])
    def test_teacher_identity_cannot_be_supplied_in_text(self):
        replies=self.adapter([update(104,'/report report-a')]).prepare_batch()
        self.assertEqual(replies[0].reply.status,'unavailable')
        self.assertEqual(self.f.loads,[])
    def test_callback_checks_actual_sender_and_message_bot(self):
        opening=self.adapter([update()]).prepare_batch()[0].reply.buttons[0][0].callback_data
        msg=message();msg['from']={'id':BOT,'is_bot':True}
        callback={'update_id':2,'callback_query':{'id':'query-1','from':{'id':103,'is_bot':False},'message':msg,'data':opening}}
        result=self.adapter([callback]).prepare_batch()
        self.assertEqual(result[0].callback_query_id,'query-1');self.assertIn('40 slides',result[0].reply.text)
        callback['callback_query']['message']['from']['id']=9002
        self.assertEqual(self.adapter([callback]).prepare_batch(),())
    def test_foreign_callback_forwarding_denied(self):
        opening=self.adapter([update()]).prepare_batch()[0].reply.buttons[0][0].callback_data
        msg=message(104);msg['from']={'id':BOT,'is_bot':True}
        data={'update_id':2,'callback_query':{'id':'query-2','from':{'id':104,'is_bot':False},'message':msg,'data':opening}}
        self.assertEqual(self.adapter([data]).prepare_batch()[0].reply.status,'unavailable')
    def test_api_failure_duplicate_ids_or_ambiguous_updates_rejected(self):
        for response in [{'ok':False,'result':[]},{'ok':True,'result':[update(),update()]},{'ok':True,'result':[dict(update(),callback_query={})]}]:
            adapter=TelegramReportAdapter(reader_factory=self.reader,bot_id=BOT,fetch_verified_updates=lambda:response)
            with self.assertRaises(TelegramAdapterError):adapter.prepare_batch()
    def test_unsupported_and_edited_messages_are_not_routed(self):
        self.assertEqual(self.adapter([update(text='/start')]).prepare_batch(),())
        self.assertEqual(self.adapter([{'update_id':1,'edited_message':message()}]).prepare_batch(),())
    def test_repeated_poll_rechecks_policy_instead_of_reusing_reply(self):
        adapter=self.adapter([update()]);self.assertEqual(adapter.prepare_batch()[0].reply.status,'prepared')
        self.f.policy=self.f.fixture.policy(bindings=())
        self.assertEqual(adapter.prepare_batch()[0].reply.status,'unavailable')

    def test_edited_and_message_ambiguity_is_rejected(self):
        with self.assertRaises(TelegramAdapterError):self.adapter([dict(update(),edited_message=message())]).prepare_batch()
    def test_inaccessible_or_inline_callback_is_not_routed(self):
        msg=message();msg['from']={'id':BOT,'is_bot':True};msg['date']=0
        query={'id':'q','from':{'id':103,'is_bot':False},'data':'progress:p:1','message':msg}
        self.assertEqual(self.adapter([{'update_id':1,'callback_query':query}]).prepare_batch(),())
        query.pop('message');query['inline_message_id']='inline'
        self.assertEqual(self.adapter([{'update_id':2,'callback_query':query}]).prepare_batch(),())
    def test_untrusted_transport_error_details_not_exposed(self):
        def failed():raise RuntimeError('private token or URL')
        adapter=TelegramReportAdapter(reader_factory=self.reader,bot_id=BOT,fetch_verified_updates=failed)
        with self.assertRaises(TelegramAdapterError) as caught:adapter.prepare_batch()
        self.assertNotIn('private',str(caught.exception))
