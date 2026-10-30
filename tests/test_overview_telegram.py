"""Optional local Telegram route; synthetic verified-poll injection only."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from telegram_report_adapter import TelegramReportAdapter, TelegramAdapterError
import test_academic_overview as overview
from academic_overview import AcademicOverview
from report_access import ReportReader

class OverviewTelegramTests(unittest.TestCase):
    def setUp(self):
        self.f=overview.OverviewTests();self.f.setUp()
        self.f.j.policy=self.f.j.f.policy(bindings=tuple(replace(b,subject={'001':'101','003':'103','004':'104'}.get(b.subject,b.subject)) for b in self.f.j.f.bindings))
    def adapter(self,sender=103,text='/overview enrollment-a',enabled=True,group=False):
        msg={'message_id':1,'date':1793160000,'from':{'id':sender,'is_bot':False},'chat':{'id':sender,'type':'group' if group else 'private'},'text':text}
        return TelegramReportAdapter(reader_factory=lambda:self.f.r.reader,bot_id=9001,fetch_verified_updates=lambda:{'ok':True,'result':[{'update_id':1,'message':msg}]},overview_factory=(lambda:self.f.service) if enabled else None)
    def test_optional_route_prepares_without_send(self):
        item=self.adapter().prepare_batch()[0]
        self.assertEqual(item.reply.status,'prepared');self.assertEqual(item.chat_id,103)
    def test_default_route_disabled(self):
        self.assertEqual(self.adapter(enabled=False).prepare_batch(),());self.assertEqual(self.f.j.loads,0)
    def test_foreign_student_denied(self):
        self.assertEqual(self.adapter(sender=104).prepare_batch()[0].reply.status,'unavailable');self.assertEqual(self.f.j.loads,0)
    def test_group_chat_does_not_load(self):
        self.assertEqual(self.adapter(group=True).prepare_batch(),());self.assertEqual(self.f.j.loads,0)
    def test_teacher_command(self):
        self.assertEqual(self.adapter(sender=101,text='/student enrollment-a').prepare_batch()[0].reply.status,'prepared')
    def test_invalid_overview_factory_rejected(self):
        with self.assertRaises(TelegramAdapterError):TelegramReportAdapter(reader_factory=lambda:self.f.r.reader,bot_id=9001,fetch_verified_updates=lambda:{},overview_factory=True)
    def test_existing_progress_command_unchanged(self):
        item=self.adapter(text='/progress').prepare_batch()[0]
        self.assertEqual(item.reply.status,'prepared');self.assertEqual(self.f.j.loads,0)
