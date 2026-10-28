"""Local inline-button callbacks are references, never access credentials."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_requests import prepare_report_reply,prepare_progress_callback
from report_access import ReportReader
import test_report_access as fixtures

class ButtonTests(unittest.TestCase):
    def setUp(self):self.f=fixtures.ReportTests();self.f.setUp()
    def button(self):return prepare_report_reply(self.f.reader,self.f.context('003'),'/progress').buttons[0][0]
    def test_open_button_resolves_own_report(self):
        button=self.button();self.assertLessEqual(len(button.callback_data.encode()),64)
        reply=prepare_progress_callback(self.f.reader,self.f.context('003'),button.callback_data)
        self.assertEqual(reply.status,'prepared');self.assertIn('40 slides',reply.text)
        self.assertEqual(reply.buttons[-1][0].label,'К списку работ')
    def test_forwarded_button_cannot_open_foreign_work(self):
        button=self.button()
        self.assertEqual(prepare_progress_callback(self.f.reader,self.f.context('004'),button.callback_data).status,'unavailable')
    def test_revoked_binding_cannot_reuse_old_button(self):
        button=self.button();self.f.policy=self.f.fixture.policy(bindings=())
        self.assertEqual(prepare_progress_callback(self.f.reader,self.f.context('003'),button.callback_data).status,'unavailable')
    def test_retargeted_link_invalidates_old_reference(self):
        button=self.button()
        reader=ReportReader([replace(self.f.link,check_id='different-check')],policy_provider=lambda:self.f.policy,load_result=self.f.load,clock=lambda:fixtures.NOW)
        self.assertEqual(prepare_progress_callback(reader,self.f.context('003'),button.callback_data).status,'unavailable')
    def test_invalid_or_overlong_callback_never_loads(self):
        for data in ['progress:o:unknown','progress:p:0','progress:p:2 student-b','x'*65]:
            self.assertEqual(prepare_progress_callback(self.f.reader,self.f.context('003'),data).status,'unavailable')
        self.assertEqual(self.f.loads,[])
    def test_navigation_buttons_are_self_scoped(self):
        links=[replace(self.f.link,id=f'r-{i}',check_id=f'c-{i}') for i in range(7)]
        def load(key):return {**self.f.row,'result':{**self.f.row['result'],'check_id':key}}
        reader=ReportReader(links,policy_provider=lambda:self.f.policy,load_result=load,clock=lambda:fixtures.NOW)
        first=prepare_report_reply(reader,self.f.context('003'),'/progress')
        next_button=first.buttons[-1][-1]
        second=prepare_progress_callback(reader,self.f.context('003'),next_button.callback_data)
        self.assertIn('страница 2',second.text)
        self.assertEqual(second.buttons[-1][0].label,'Назад')
    def test_reference_collision_never_selects_first_report(self):
        reader=ReportReader([self.f.link,replace(self.f.link,id='another')],policy_provider=lambda:self.f.policy,load_result=self.f.load,clock=lambda:fixtures.NOW)
        with patch.object(ReportReader,'_reference',return_value='0'*32):
            self.assertEqual(prepare_progress_callback(reader,self.f.context('003'),'progress:o:'+'0'*32).status,'unavailable')
        self.assertEqual(self.f.loads,[])

    def test_long_unicode_report_id_stays_inside_callback_limit(self):
        reader=ReportReader([replace(self.f.link,id='😀'*100)],policy_provider=lambda:self.f.policy,load_result=self.f.load,clock=lambda:fixtures.NOW)
        reply=prepare_report_reply(reader,self.f.context('003'),'/progress')
        button=reply.buttons[0][0]
        self.assertLessEqual(len(button.callback_data.encode('utf-8')),64)
        self.assertEqual(prepare_progress_callback(reader,self.f.context('003'),button.callback_data).status,'prepared')
