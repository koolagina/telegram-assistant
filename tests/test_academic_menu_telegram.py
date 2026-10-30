"""Verified-poll mock exercises optional menu routing end to end."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from telegram_report_adapter import TelegramReportAdapter,TelegramAdapterError
import test_academic_menu as fixtures

class MenuTelegramTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.AcademicMenuTests();self.f.setUp()
        self.f.f.j.policy=self.f.f.j.f.policy(bindings=tuple(replace(b,subject={'001':'101','003':'103','004':'104'}.get(b.subject,b.subject)) for b in self.f.f.j.f.bindings))
    def adapter(self,update,enabled=True):
        return TelegramReportAdapter(reader_factory=lambda:self.f.f.r.reader,bot_id=9001,fetch_verified_updates=lambda:{'ok':True,'result':[update]},academic_menu_factory=(lambda:self.f.menu) if enabled else None)
    def message(self,sender=103,text='/overview'):
        return {'update_id':1,'message':{'message_id':1,'date':1793160000,'from':{'id':sender,'is_bot':False},'chat':{'id':sender,'type':'private'},'text':text}}
    def test_menu_click_and_repeat(self):
        reply=self.adapter(self.message()).prepare_batch()[0].reply
        data=reply.buttons[0][0].callback_data
        message=self.message()['message'];message['from']={'id':9001,'is_bot':True}
        query={'update_id':2,'callback_query':{'id':'query','from':{'id':103,'is_bot':False},'message':message,'data':data}}
        first=self.adapter(query).prepare_batch()[0]
        self.assertEqual(first.reply.status,'prepared');self.assertEqual(first.callback_query_id,'query')
        self.assertEqual(first,self.adapter(query).prepare_batch()[0])
        self.f.f.j.policy=self.f.f.j.f.policy(bindings=())
        self.assertEqual(self.adapter(query).prepare_batch()[0].reply.status,'unavailable')
    def test_default_disabled(self):
        self.assertEqual(self.adapter(self.message(),enabled=False).prepare_batch(),())
    def test_group_chat_blocked(self):
        data=self.message();data['message']['chat']['type']='group'
        self.assertEqual(self.adapter(data).prepare_batch(),());self.assertEqual(self.f.f.j.loads,0)
    def test_teacher_menu(self):
        result=self.adapter(self.message(101,'/student')).prepare_batch()[0].reply
        self.assertEqual(result.status,'prepared');self.assertIn('Студент А',result.text)
    def test_invalid_factory_rejected(self):
        with self.assertRaises(TelegramAdapterError):TelegramReportAdapter(reader_factory=lambda:None,bot_id=9001,fetch_verified_updates=lambda:None,academic_menu_factory=True)
