"""Offline identity-bound journal projections; synthetic workbook only."""
from dataclasses import replace
import datetime as dt
from decimal import Decimal
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from academic_progress import ProgressReader, JournalMap, JournalField, ProgressError
from gradebook_read import Workbook, Sheet, Cell
import test_assistant_access as fixtures

class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PolicyTests();self.f.setUp();self.policy=self.f.policy();self.loads=0
        self.sheet=Sheet(1,'xl/worksheets/sheet.xml','private sheet',{'C5':Cell('C5','number',Decimal('12'))},[],[],[],'visible')
        self.book=Workbook('a'*64,False,[self.sheet],[])
        self.mapping=JournalMap('enrollment-a','student-a','discipline-a','group-a','a'*64,1,5,(JournalField('lecture-1','attendance','C5'),))
        self.reader=self.make()
    def load(self):self.loads+=1;return self.book
    def make(self,mapping=None,loader=None):
        return ProgressReader([mapping or self.mapping],policy_provider=lambda:self.policy,load_workbook=loader or self.load,clock=lambda:fixtures.NOW)
    def context(self,subject='003'):
        return self.f.context(subject)
    def test_self_read_no_internal_coordinates_or_names(self):
        out=self.reader.read('enrollment-a',self.context(),purpose='progress.self')
        self.assertEqual(out['entries'],[{'id':'lecture-1','kind':'attendance','state':'recorded','value':'12'}])
        self.assertNotIn('C5',str(out));self.assertNotIn('private sheet',str(out));self.assertFalse(out['credit_written'])
    def test_foreign_and_missing_identical_denial_before_load(self):
        for target in ('enrollment-a','missing'):
            with self.assertRaisesRegex(ProgressError,'Progress unavailable'):self.reader.read(target,self.context('004'),purpose='progress.self')
        self.assertEqual(self.loads,0)
    def test_teacher_and_scoped_chatgpt(self):
        self.reader.read('enrollment-a',self.context('001'),purpose='student.report')
        c=fixtures.Context('chatgpt','oauth-sub-a',authenticated=True)
        with self.assertRaises(ProgressError):self.reader.read('enrollment-a',c,purpose='student.report')
        self.reader.read('enrollment-a',replace(c,scopes=frozenset({'student.report'})),purpose='student.report')
    def test_wrong_teacher_denied(self):
        with self.assertRaises(ProgressError):self.reader.read('enrollment-a',self.context('002'),purpose='student.report')
        self.assertEqual(self.loads,0)
    def test_revision_change_requires_remapping(self):
        self.book.sha256='b'*64
        with self.assertRaises(ProgressError):self.reader.read('enrollment-a',self.context(),purpose='progress.self')
    def test_revocation_during_load(self):
        def loader():self.policy=self.f.policy(bindings=());return self.book
        with self.assertRaises(ProgressError):self.make(loader=loader).read('enrollment-a',self.context(),purpose='progress.self')
    def test_reused_enrollment_rejected_before_load(self):
        self.policy=self.f.policy(enrollments=(replace(self.f.enrollments[0],student_id='student-b'),self.f.enrollments[1]))
        with self.assertRaises(ProgressError):self.reader.read('enrollment-a',self.context('004'),purpose='progress.self')
        self.assertEqual(self.loads,0)
    def test_formula_cache_never_reported_as_current_grade(self):
        self.sheet.cells['C5']=Cell('C5','number',Decimal('999'),True,True,'SUM(D5:Z5)')
        entry=self.reader.read('enrollment-a',self.context(),purpose='progress.self')['entries'][0]
        self.assertEqual(entry,{'id':'lecture-1','kind':'attendance','state':'formula_unverified'})
    def test_blank_is_not_zero_or_absent(self):
        self.sheet.cells.clear()
        self.assertEqual(self.reader.read('enrollment-a',self.context(),purpose='progress.self')['entries'][0]['state'],'not_recorded')
    def test_merged_cell_cannot_alias_another_row(self):
        self.sheet.merges=['C4:C5']
        with self.assertRaises(ProgressError):self.reader.read('enrollment-a',self.context(),purpose='progress.self')
    def test_duplicate_row_or_enrollment_mapping_rejected(self):
        other=replace(self.mapping,enrollment_id='enrollment-b',student_id='student-b')
        for maps in ([self.mapping,self.mapping],[self.mapping,other]):
            with self.assertRaises(ProgressError):ProgressReader(maps,policy_provider=lambda:self.policy,load_workbook=self.load,clock=lambda:fixtures.NOW)
    def test_wrong_row_or_duplicate_field_rejected(self):
        for fields in ((JournalField('x','score','C6'),),self.mapping.fields*2):
            with self.assertRaises(ProgressError):self.make(replace(self.mapping,fields=fields))
    def test_purpose_is_explicit(self):
        with self.assertRaises(ProgressError):self.reader.read('enrollment-a',self.context('001'),purpose='progress.self')
        self.assertEqual(self.loads,0)
    def test_group_chat_denied_before_load(self):
        with self.assertRaises(ProgressError):self.reader.read('enrollment-a',replace(self.context(),private=False),purpose='progress.self')
        self.assertEqual(self.loads,0)
    def test_loader_errors_sanitized(self):
        def fail():raise RuntimeError('private path and values')
        with self.assertRaisesRegex(ProgressError,'^Progress unavailable$'):self.make(loader=fail).read('enrollment-a',self.context(),purpose='progress.self')
    def test_detached_response_and_no_derived_total(self):
        out=self.reader.read('enrollment-a',self.context(),purpose='progress.self');out['entries'].clear()
        self.assertEqual(len(self.reader.read('enrollment-a',self.context(),purpose='progress.self')['entries']),1)
        self.assertNotIn('total',out)
    def test_actual_xlsx_parser_to_student_and_teacher_projection(self):
        import tempfile
        from test_gradebook_read import fixture
        from gradebook_read import read_workbook
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.xlsx'
            fixture(path,'<row r="5"><c r="C5"><v>12</v></c><c r="D5"><f>C5+1</f><v>13</v></c></row>')
            book=read_workbook(path)
            mapping=replace(self.mapping,workbook_sha256=book.sha256,fields=(JournalField('score-1','score','C5'),JournalField('total','total','D5')))
            reader=self.make(mapping,lambda:read_workbook(path))
            student=reader.read('enrollment-a',self.context(),purpose='progress.self')
            teacher=reader.read('enrollment-a',self.context('001'),purpose='student.report')
            self.assertEqual(student,teacher)
            self.assertEqual(student['entries'][0]['value'],'12')
            self.assertEqual(student['entries'][1]['state'],'formula_unverified')
            fixture(path,'<row r="5"><c r="C5"><v>99</v></c></row>')
            with self.assertRaises(ProgressError):reader.read('enrollment-a',self.context(),purpose='progress.self')
    def test_error_cell_does_not_become_grade(self):
        self.sheet.cells['C5']=Cell('C5','error','#REF!')
        self.assertEqual(self.reader.read('enrollment-a',self.context(),purpose='progress.self')['entries'][0]['state'],'source_error')
    def test_teacher_email_authorization_does_not_send(self):
        context=fixtures.Context('email','verified-recipient',authenticated=True)
        self.assertFalse(self.reader.read('enrollment-a',context,purpose='student.report')['live_verified'])
    def test_full_owner_access_includes_historical_enrollment(self):
        old=replace(self.f.enrollments[0],valid_until=fixtures.NOW-dt.timedelta(seconds=1))
        self.policy=self.f.policy(enrollments=(old,self.f.enrollments[1]),academic_read_grants=(fixtures.AcademicReadGrant('full','teacher-a',fixtures.START,fixtures.END),))
        self.reader.read('enrollment-a',self.context('001'),purpose='student.report')
        with self.assertRaises(ProgressError):self.reader.read('enrollment-a',self.context(),purpose='progress.self')
