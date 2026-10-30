"""Synthetic combined journal/review views; no external services."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from academic_overview import AcademicOverview, OverviewError, prepare_overview_reply
from report_access import ReportReader, ReportLink
import test_academic_progress as journal_fixtures
import test_report_access as review_fixtures

class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.j=journal_fixtures.ProgressTests();self.j.setUp()
        self.r=review_fixtures.ReportTests();self.r.setUp()
        self.r.reader=ReportReader([self.r.link],policy_provider=lambda:self.j.policy,load_result=self.r.load,clock=lambda:review_fixtures.NOW)
        self.service=AcademicOverview(self.j.reader,self.r.reader)
    def read(self,subject='003',**kw):
        return self.service.read('enrollment-a',self.j.context(subject),purpose=kw.pop('purpose','progress.self'),**kw)
    def test_combined_sections_preserve_distinct_meaning(self):
        out=self.read();self.assertEqual(out['journal']['entries'][0]['value'],'12')
        self.assertEqual(len(out['reviews']['items']),1);self.assertFalse(out['credit_written'])
        self.assertNotIn('evidence',out['reviews']['items'][0]['report']['requirements'][0])
    def test_foreign_student_denied_before_any_payload(self):
        with self.assertRaises(OverviewError):self.read('004')
        self.assertEqual(self.j.loads,0);self.assertEqual(self.r.loads,[])
    def test_teacher_gets_review_notes(self):
        out=self.read('001',purpose='student.report')
        self.assertIn('content_observation',out['reviews']['items'][0]['report']['requirements'][0])
    def test_wrong_teacher_denied(self):
        with self.assertRaises(OverviewError):self.read('002',purpose='student.report')
    def test_report_registry_identity_mismatch_not_joined(self):
        wrong=replace(self.r.link,student_id='student-b')
        service=AcademicOverview(self.j.reader,ReportReader([wrong],policy_provider=lambda:self.j.policy,load_result=self.r.load,clock=lambda:review_fixtures.NOW))
        with self.assertRaises(OverviewError):service.read('enrollment-a',self.j.context(),purpose='progress.self')
        self.assertEqual(self.r.loads,[])
    def test_revocation_in_report_loader_blocks_whole_view(self):
        def load(key):self.j.policy=self.j.f.policy(bindings=());return self.r.row
        self.service=AcademicOverview(self.j.reader,ReportReader([self.r.link],policy_provider=lambda:self.j.policy,load_result=load,clock=lambda:review_fixtures.NOW))
        with self.assertRaises(OverviewError):self.read()
    def test_stale_journal_does_not_return_partial_view(self):
        self.j.book.sha256='b'*64
        with self.assertRaises(OverviewError):self.read()
        self.assertEqual(self.r.loads,[])
    def test_no_reviews_is_not_no_debt(self):
        self.service=AcademicOverview(self.j.reader,ReportReader([],policy_provider=lambda:self.j.policy,load_result=self.r.load,clock=lambda:review_fixtures.NOW))
        out=self.read();self.assertEqual(out['reviews']['items'],[]);self.assertNotIn('debt',out)
    def test_pagination_five_and_only_selected_payloads(self):
        links=[replace(self.r.link,id=f'report-{i}',check_id=f'check-{i}') for i in range(7)]
        def load(key):
            self.r.loads.append(key)
            return {**self.r.row,'result':{**self.r.row['result'],'check_id':key}}
        self.service=AcademicOverview(self.j.reader,ReportReader(links,policy_provider=lambda:self.j.policy,load_result=load,clock=lambda:review_fixtures.NOW))
        self.assertEqual(len(self.read()['reviews']['items']),5);self.assertEqual(len(self.r.loads),5)
        out=self.read(page=2);self.assertEqual(len(out['reviews']['items']),2);self.assertIsNone(out['reviews']['next_page'])
    def test_invalid_page_does_not_read_journal(self):
        for p in (True,0,-1,1.5,1000001):
            with self.assertRaises(OverviewError):self.read(page=p)
        self.assertEqual(self.j.loads,0)
    def test_prepared_student_reply_plain_text_bounded(self):
        reply=prepare_overview_reply(self.service,self.j.context(),'/overview enrollment-a')
        self.assertEqual(reply.status,'prepared');self.assertIsNone(reply.parse_mode)
        self.assertIn('Журнал',reply.text);self.assertIn('Проверки работ',reply.text)
        self.assertNotIn('private reviewer note',reply.text)
        self.assertLessEqual(len(reply.text.encode('utf-16-le'))//2,3500)
    def test_teacher_command_and_student_cannot_switch_purpose(self):
        self.assertEqual(prepare_overview_reply(self.service,self.j.context('001'),'/student enrollment-a').status,'prepared')
        self.assertEqual(prepare_overview_reply(self.service,self.j.context(),'/student enrollment-a').status,'unavailable')
    def test_invalid_command_no_load(self):
        for cmd in ('/overview','/overview enrollment-a\n','/overview enrollment-a page 0','/overview enrollment-a role teacher'):
            self.assertEqual(prepare_overview_reply(self.service,self.j.context(),cmd).status,'invalid_request')
        self.assertEqual(self.j.loads,0)
    def test_unavailable_uniform(self):
        a=prepare_overview_reply(self.service,self.j.context('004'),'/overview enrollment-a')
        b=prepare_overview_reply(self.service,self.j.context('004'),'/overview unknown')
        self.assertEqual(a,b)
    def test_other_enrollment_reports_excluded_before_load(self):
        other=ReportLink('foreign-report','foreign-check','enrollment-b','student-b','discipline-b','group-b')
        self.service=AcademicOverview(self.j.reader,ReportReader([other,self.r.link],policy_provider=lambda:self.j.policy,load_result=self.r.load,clock=lambda:review_fixtures.NOW))
        self.assertEqual(len(self.read()['reviews']['items']),1);self.assertEqual(self.r.loads,['check-a'])
    def test_corrupt_report_does_not_return_half_view(self):
        self.r.row['result']['credit_written']=True
        with self.assertRaises(OverviewError):self.read()
    def test_literal_text_is_plain_and_bounded(self):
        self.j.sheet.cells['C5'].value='<b>not markup</b>\u202e'+'😀'*800
        out=prepare_overview_reply(self.service,self.j.context(),'/overview enrollment-a')
        self.assertEqual(out.status,'prepared');self.assertIsNone(out.parse_mode)
        self.assertNotIn('\u202e',out.text);self.assertLessEqual(len(out.text.encode('utf-16-le'))//2,3500)
