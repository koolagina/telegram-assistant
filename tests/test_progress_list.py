"""Only self reports are resolved; page numbers are not credentials."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_access import ReportReader,ReportAccessError
from report_requests import prepare_report_reply
import test_report_access as fixtures

class ListTests(unittest.TestCase):
    def setUp(self):self.f=fixtures.ReportTests();self.f.setUp()
    def test_bare_progress_resolves_current_student(self):
        reply=prepare_report_reply(self.f.reader,self.f.context('003'),'/progress')
        self.assertEqual(reply.status,'prepared');self.assertIn('/progress report-a',reply.text)
        self.assertNotIn('private reviewer note',reply.text)
    def test_foreign_links_not_loaded_or_counted(self):
        other=replace(self.f.link,id='foreign',check_id='other',enrollment_id='enrollment-b',student_id='student-b',discipline_id='discipline-b',group_id='group-b')
        reader=ReportReader([other,self.f.link],policy_provider=lambda:self.f.policy,load_result=self.f.load,clock=lambda:fixtures.NOW)
        page=reader.list_self(self.f.context('003'))
        self.assertEqual([item['report_id'] for item in page['items']],['report-a'])
        self.assertEqual(self.f.loads,['check-a']);self.assertIsNone(page['next_page'])
    def test_pages_are_self_scoped_and_disjoint(self):
        links=[replace(self.f.link,id=f'report-{i}',check_id=f'check-{i}') for i in range(7)]
        def load(key):return {**self.f.row,'result':{**self.f.row['result'],'check_id':key}}
        reader=ReportReader(links,policy_provider=lambda:self.f.policy,load_result=load,clock=lambda:fixtures.NOW)
        first=reader.list_self(self.f.context('003'));second=reader.list_self(self.f.context('003'),page=2)
        self.assertEqual(len(first['items']),5);self.assertEqual(len(second['items']),2)
        self.assertEqual(first['next_page'],2);self.assertIsNone(second['next_page'])
        self.assertFalse({i['report_id'] for i in first['items']} & {i['report_id'] for i in second['items']})
    def test_teacher_unconfirmed_or_group_chat_cannot_list(self):
        for context in [self.f.context('001'),replace(self.f.context('003'),private=False),replace(self.f.context('003'),authenticated=False)]:
            with self.assertRaises(ReportAccessError):self.f.reader.list_self(context)
        self.assertEqual(self.f.loads,[])
    def test_bad_page_values_do_not_read_payload(self):
        for page in [0,-1,True,1.5,1000001]:
            with self.assertRaises(ReportAccessError):self.f.reader.list_self(self.f.context('003'),page=page)
        self.assertEqual(self.f.loads,[])
    def test_revocation_during_list_returns_no_page(self):
        def load(key):self.f.policy=self.f.fixture.policy(bindings=());return self.f.row
        reader=ReportReader([self.f.link],policy_provider=lambda:self.f.policy,load_result=load,clock=lambda:fixtures.NOW)
        with self.assertRaises(ReportAccessError):reader.list_self(self.f.context('003'))
    def test_empty_page_has_no_foreign_data(self):
        page=self.f.reader.list_self(self.f.context('004'))
        self.assertEqual(page['items'],[]);self.assertEqual(self.f.loads,[])
    def test_explicit_page_command_does_not_accept_identity(self):
        reply=prepare_report_reply(self.f.reader,self.f.context('003'),'/progress page 2')
        self.assertEqual(reply.status,'prepared');self.assertIn('На этой странице нет',reply.text)
        self.assertEqual(prepare_report_reply(self.f.reader,self.f.context('003'),'/progress page 2 student-b').status,'invalid_request')

    def test_pending_own_report_keeps_only_authorized_reference(self):
        self.f.row={'status':'pending','version':'v','result':None}
        page=self.f.reader.list_self(self.f.context('003'))
        self.assertEqual(page['items'],[{'report_id':'report-a','available':False}])
    def test_rebound_account_during_list_does_not_return_previous_students_page(self):
        def load(key):
            bindings=tuple(replace(b,entity_id='student-b') if b.subject=='003' else b for b in self.f.fixture.bindings)
            self.f.policy=self.f.fixture.policy(bindings=bindings)
            return self.f.row
        reader=ReportReader([self.f.link],policy_provider=lambda:self.f.policy,load_result=load,clock=lambda:fixtures.NOW)
        with self.assertRaises(ReportAccessError):reader.list_self(self.f.context('003'))
