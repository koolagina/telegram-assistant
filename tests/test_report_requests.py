"""Local command preparation; no Telegram or email sends."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_requests import prepare_report_reply
import test_report_access as fixtures

class RequestTests(unittest.TestCase):
    def setUp(self):self.f=fixtures.ReportTests();self.f.setUp()
    def prepare(self,text,subject='003'):return prepare_report_reply(self.f.reader,self.f.context(subject),text)
    def test_progress_returns_only_self_summary(self):
        reply=self.prepare('/progress report-a')
        self.assertIn('Нужна проверка преподавателя',reply.text)
        self.assertIn('40 slides',reply.text)
        self.assertNotIn('private reviewer note',reply.text)
        self.assertIsNone(reply.parse_mode);self.assertTrue(reply.link_preview_disabled)
    def test_teacher_report_shows_authorized_observations(self):
        self.assertIn('private reviewer note',self.prepare('/report report-a','001').text)
    def test_wrong_command_role_cannot_expand_or_switch_purpose(self):
        for command,subject in [('/report report-a','003'),('/progress report-a','001')]:
            self.assertEqual(self.prepare(command,subject).status,'unavailable')
    def test_foreign_missing_and_unconfirmed_have_same_reply(self):
        self.assertEqual(self.prepare('/progress report-a','004'),self.prepare('/progress missing','004'))
    def test_revocation_rechecks_every_preparation(self):
        self.assertEqual(self.prepare('/report report-a','001').status,'prepared')
        self.f.policy=self.f.fixture.policy(teaching_grants=())
        self.assertEqual(self.prepare('/report report-a','001').status,'unavailable')
    def test_invalid_commands_do_not_load_payload(self):
        for command in ['/progress page 0','/report x user=teacher','/send report-a','/progress report-a\n/report other']:
            self.assertEqual(self.prepare(command).status,'invalid_request')
        self.assertEqual(self.f.loads,[])
    def test_unicode_limits_and_control_characters(self):
        self.f.row['result']['requirements'][0]['requirement']='😀'*5000+'\u202e\x00'
        reply=self.prepare('/progress report-a')
        self.assertLessEqual(len(reply.text.encode('utf-16-le'))//2,3500)
        self.assertNotIn('\u202e',reply.text);self.assertNotIn('\x00',reply.text)
        self.assertIn('сокращён',reply.text)
    def test_same_request_is_deterministic_but_not_delivery(self):
        reply=self.prepare('/progress report-a')
        self.assertEqual(reply,self.prepare('/progress report-a'))
        self.assertEqual(reply.status,'prepared')
        self.assertFalse(hasattr(reply,'delivered'))

    def test_teacher_command_cannot_survive_role_downgrade_during_load(self):
        from dataclasses import replace
        from report_access import ReportReader
        def load(key):
            bindings=tuple(replace(b,role='student',entity_id='student-a',capabilities=frozenset({'progress.self'})) if b.subject=='001' else b for b in self.f.fixture.bindings)
            self.f.policy=self.f.fixture.policy(bindings=bindings)
            return self.f.row
        self.f.reader=ReportReader([self.f.link],policy_provider=lambda:self.f.policy,load_result=load,clock=lambda:fixtures.NOW)
        self.assertEqual(self.prepare('/report report-a','001').status,'unavailable')
    def test_markup_stays_plain_text_without_implicit_formatting(self):
        self.f.row['result']['requirements'][0]['requirement']='<b>Example</b> [link](https://example.invalid)'
        reply=self.prepare('/progress report-a')
        self.assertIsNone(reply.parse_mode)
        self.assertTrue(reply.link_preview_disabled)
        self.assertIn('<b>Example</b>',reply.text)
