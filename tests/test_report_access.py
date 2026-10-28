"""Synthetic report retrieval through current academic policy, no transport."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_access import ReportReader,ReportLink,ReportAccessError
from assistant_access import Context,AcademicReadGrant
import test_assistant_access as fixtures
NOW,START,END=fixtures.NOW,fixtures.START,fixtures.END

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.PolicyTests();self.fixture.setUp();self.policy=self.fixture.policy();self.loads=[]
        self.link=ReportLink('report-a','check-a','enrollment-a','student-a','discipline-a','group-a')
        self.row={'status':'done','version':'version-a','result':{'check_id':'check-a','material_version':'version-a','assignment_id':'makeup-3','status':'needs_teacher_review','credit_written':False,'secret_unexpected':'not for output','requirements':[{'requirement':'40 slides','status':'met','evidence':[{'kind':'slide_count','value':40}],'content_observation':{'comment':'private reviewer note'}}]}}
        self.reader=ReportReader([self.link],policy_provider=lambda:self.policy,load_result=self.load,clock=lambda:NOW)
    def load(self,key):self.loads.append(key);return self.row
    def context(self,subject):return Context('telegram',subject,authenticated=True,private=True)
    def test_student_only_own_report_and_no_internal_notes(self):
        result=self.reader.read('report-a',self.context('003'))
        self.assertEqual(result['status'],'needs_teacher_review')
        self.assertNotIn('secret_unexpected',result)
        self.assertNotIn('content_observation',result['requirements'][0])
        self.assertNotIn('evidence',result['requirements'][0])
        with self.assertRaises(ReportAccessError):self.reader.read('report-a',self.context('004'))
    def test_teacher_exact_teaching_grant_and_unknown_equal_denials(self):
        self.assertEqual(self.reader.read('report-a',self.context('001'))['requirements'][0]['evidence'][0]['value'],40)
        errors=[]
        for report in ['report-a','not-found']:
            with self.assertRaises(ReportAccessError) as caught:self.reader.read(report,self.context('002'))
            errors.append(str(caught.exception))
        self.assertEqual(errors[0],errors[1]);self.assertEqual(len(self.loads),1)
    def test_full_academic_read_for_owner_not_second_teacher(self):
        self.policy=self.fixture.policy(teaching_grants=(),academic_read_grants=(AcademicReadGrant('full','teacher-a',START,END),))
        self.reader.read('report-a',self.context('001'))
        with self.assertRaises(ReportAccessError):self.reader.read('report-a',self.context('002'))
    def test_revocation_blocks_previously_read_report(self):
        self.reader.read('report-a',self.context('001'))
        self.policy=self.fixture.policy(teaching_grants=())
        with self.assertRaises(ReportAccessError):self.reader.read('report-a',self.context('001'))
        self.assertEqual(len(self.loads),1)
    def test_revocation_during_load_blocks_return(self):
        def load(key):self.policy=self.fixture.policy(teaching_grants=());return self.row
        reader=ReportReader([self.link],policy_provider=lambda:self.policy,load_result=load,clock=lambda:NOW)
        with self.assertRaises(ReportAccessError):reader.read('report-a',self.context('001'))
    def test_reused_enrollment_cannot_retarget_old_report(self):
        self.policy=self.fixture.policy(enrollments=(replace(self.fixture.enrollments[0],student_id='student-b'),self.fixture.enrollments[1]))
        with self.assertRaises(ReportAccessError):self.reader.read('report-a',self.context('004'))
        self.assertEqual(self.loads,[])
    def test_group_chat_and_unconfirmed_binding_denied_before_load(self):
        with self.assertRaises(ReportAccessError):self.reader.read('report-a',replace(self.context('001'),private=False))
        self.policy=self.fixture.policy(bindings=tuple(replace(b,confirmed=False) for b in self.fixture.bindings))
        with self.assertRaises(ReportAccessError):self.reader.read('report-a',self.context('001'))
        self.assertEqual(self.loads,[])
    def test_chatgpt_scope_and_confirmed_email_read_only(self):
        context=Context('chatgpt','oauth-sub-a',authenticated=True)
        with self.assertRaises(ReportAccessError):self.reader.read('report-a',context)
        self.reader.read('report-a',replace(context,scopes=frozenset({'student.report'})))
        self.reader.read('report-a',Context('email','verified-recipient',authenticated=True))
    def test_pending_or_mismatched_result_not_disclosed(self):
        for row in [{'status':'pending','version':'version-a','result':None},{**self.row,'version':'other'}]:
            self.row=row
            with self.assertRaises(ReportAccessError):self.reader.read('report-a',self.context('001'))
    def test_projection_does_not_modify_stored_result(self):
        result=self.reader.read('report-a',self.context('001'));result['requirements'][0]['evidence'].clear()
        self.assertEqual(len(self.row['result']['requirements'][0]['evidence']),1)

    def test_role_downgrade_during_load_uses_student_projection(self):
        def load(key):
            bindings=tuple(replace(b,role='student',entity_id='student-a',capabilities=frozenset({'progress.self'})) if b.subject=='001' else b for b in self.fixture.bindings)
            self.policy=self.fixture.policy(bindings=bindings)
            return self.row
        reader=ReportReader([self.link],policy_provider=lambda:self.policy,load_result=load,clock=lambda:NOW)
        result=reader.read('report-a',self.context('001'))
        self.assertNotIn('content_observation',result['requirements'][0])
    def test_historical_report_requires_explicit_full_read(self):
        import datetime as dt
        historical=replace(self.fixture.enrollments[0],valid_until=NOW-dt.timedelta(minutes=1))
        self.policy=self.fixture.policy(enrollments=(historical,self.fixture.enrollments[1]),academic_read_grants=(AcademicReadGrant('full','teacher-a',START,END),))
        self.reader.read('report-a',self.context('001'))
        with self.assertRaises(ReportAccessError):self.reader.read('report-a',self.context('003'))
    def test_loader_exception_is_sanitized(self):
        def failed(key):raise RuntimeError('private data and secret path')
        reader=ReportReader([self.link],policy_provider=lambda:self.policy,load_result=failed,clock=lambda:NOW)
        with self.assertRaises(ReportAccessError) as caught:reader.read('report-a',self.context('001'))
        self.assertEqual(str(caught.exception),'Report unavailable')
