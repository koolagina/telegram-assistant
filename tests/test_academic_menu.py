"""Synthetic identity-bound academic menu, no services or real identities."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from academic_menu import AcademicMenu,MenuEntry,MenuError
from academic_overview import AcademicOverview
from report_access import ReportReader
import test_academic_overview as fixtures

class AcademicMenuTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.OverviewTests();self.f.setUp()
        self.entry=MenuEntry('enrollment-a','Экология','Студент А · Экология')
        self.menu=self.make()
    def make(self,entries=None):
        return AcademicMenu(entries if entries is not None else [self.entry],journal=self.f.j.reader,overview=self.f.service,policy_provider=lambda:self.f.j.policy,clock=lambda:fixtures.review_fixtures.NOW)
    def ctx(self,subject='003'):return self.f.j.context(subject)
    def test_student_selects_course_without_internal_ids(self):
        reply=self.menu.prepare(self.ctx(),'/overview')
        self.assertEqual(reply.status,'prepared');self.assertEqual(reply.buttons[0][0].label,'Экология')
        self.assertNotIn('enrollment-a',reply.text);self.assertNotIn('Студент А',reply.text)
        opened=self.menu.callback(self.ctx(),reply.buttons[0][0].callback_data)
        self.assertEqual(opened.status,'prepared');self.assertIn('Журнал',opened.text)
    def test_teacher_selects_student(self):
        reply=self.menu.prepare(self.ctx('001'),'/student')
        self.assertEqual(reply.buttons[0][0].label,'Студент А · Экология')
        self.assertEqual(self.menu.callback(self.ctx('001'),reply.buttons[0][0].callback_data).status,'prepared')
    def test_student_cannot_request_teacher_menu(self):
        self.assertEqual(self.menu.prepare(self.ctx(),'/student').status,'unavailable')
    def test_foreign_student_sees_no_names_or_journal(self):
        reply=self.menu.prepare(self.ctx('004'),'/overview')
        self.assertEqual(reply.status,'prepared');self.assertEqual(reply.buttons,())
        self.assertNotIn('Экология',reply.text);self.assertEqual(self.f.j.loads,0)
    def test_token_cannot_be_transferred_to_another_student(self):
        token=self.menu.prepare(self.ctx(),'/overview').buttons[0][0].callback_data
        self.assertEqual(self.menu.callback(self.ctx('004'),token).status,'unavailable');self.assertEqual(self.f.j.loads,0)
    def test_revocation_after_menu_blocks_click(self):
        token=self.menu.prepare(self.ctx(),'/overview').buttons[0][0].callback_data
        self.f.j.policy=self.f.j.f.policy(bindings=())
        self.assertEqual(self.menu.callback(self.ctx(),token).status,'unavailable');self.assertEqual(self.f.j.loads,0)
    def test_changed_catalog_invalidates_old_button(self):
        token=self.menu.prepare(self.ctx(),'/overview').buttons[0][0].callback_data
        newer=self.make([replace(self.entry,student_label='Новая дисциплина')])
        self.assertEqual(newer.callback(self.ctx(),token).status,'unavailable')
    def test_repeated_click_is_read_only_same_reply(self):
        token=self.menu.prepare(self.ctx(),'/overview').buttons[0][0].callback_data
        self.assertEqual(self.menu.callback(self.ctx(),token),self.menu.callback(self.ctx(),token))
    def test_invalid_commands_and_callbacks_do_not_load(self):
        for text in ('/overview\n','/student role owner','/overview page 0'):
            self.assertEqual(self.menu.prepare(self.ctx(),text).status,'invalid_request')
        for data in ('acad:x','acad:s:o:'+('a'*32)+':0','x'*65):
            self.assertEqual(self.menu.callback(self.ctx(),data).status,'unavailable')
        self.assertEqual(self.f.j.loads,0)
    def test_duplicate_entries_rejected(self):
        with self.assertRaises(MenuError):self.make([self.entry,self.entry])
    def test_labels_cannot_be_blank_or_unbounded(self):
        for label in ('','x'*121,'\u202e'):
            with self.assertRaises(MenuError):self.make([replace(self.entry,student_label=label)])
    def test_listing_does_not_load_private_payloads(self):
        self.menu.prepare(self.ctx(),'/overview');self.menu.prepare(self.ctx('001'),'/student')
        self.assertEqual(self.f.j.loads,0);self.assertEqual(self.f.r.loads,[])
    def test_no_access_empty_menu_is_not_success(self):
        self.f.j.policy=self.f.j.f.policy(bindings=())
        self.assertEqual(self.make([]).prepare(self.ctx(),'/overview').status,'unavailable')
    def test_callback_limit_and_context_purpose(self):
        token=self.menu.prepare(self.ctx(),'/overview').buttons[0][0].callback_data
        self.assertLessEqual(len(token.encode()),64)
        self.assertEqual(self.menu.callback(self.ctx('001'),token).status,'unavailable')
    def test_paginated_menu_uses_current_authorized_catalog(self):
        from academic_progress import ProgressReader
        records=[];enrollments=[];entries=[]
        for i in range(7):
            eid='enrollment-'+str(i);discipline='course-'+str(i)
            records.append(replace(self.f.j.mapping,enrollment_id=eid,discipline_id=discipline,row=5+i,fields=tuple(replace(f,cell="C"+str(5+i)) for f in self.f.j.mapping.fields)))
            enrollments.append(replace(self.f.j.f.enrollments[0],id=eid,discipline_id=discipline))
            entries.append(MenuEntry(eid,'Дисциплина '+str(i),'Студент · '+str(i)))
        self.f.j.policy=self.f.j.f.policy(enrollments=tuple(enrollments))
        journal=ProgressReader(records,policy_provider=lambda:self.f.j.policy,load_workbook=self.f.j.load,clock=lambda:fixtures.review_fixtures.NOW)
        service=AcademicOverview(journal,self.f.r.reader)
        menu=AcademicMenu(entries,journal=journal,overview=service,policy_provider=lambda:self.f.j.policy,clock=lambda:fixtures.review_fixtures.NOW)
        first=menu.prepare(self.ctx(),'/overview')
        self.assertEqual(len(first.buttons),6)
        second=menu.callback(self.ctx(),first.buttons[-1][0].callback_data)
        self.assertEqual(len(second.buttons),3);self.assertIn('Страница 2',second.text)
        self.assertEqual(self.f.j.loads,0)
    def test_renamed_catalog_does_not_inherit_page_token(self):
        token='acad:s:p:'+self.menu._ref(self.ctx(),'s')+':2'
        newer=self.make([replace(self.entry,teacher_label='Изменённый каталог')])
        self.assertEqual(newer.callback(self.ctx(),token).status,'unavailable')
    def test_review_pages_open_by_buttons_without_typing_ids(self):
        links=[replace(self.f.r.link,id=f'report-{i}',check_id=f'check-{i}') for i in range(7)]
        def load(key):return {**self.f.r.row,'result':{**self.f.r.row['result'],'check_id':key}}
        reader=ReportReader(links,policy_provider=lambda:self.f.j.policy,load_result=load,clock=lambda:fixtures.review_fixtures.NOW)
        service=AcademicOverview(self.f.j.reader,reader)
        menu=AcademicMenu([self.entry],journal=self.f.j.reader,overview=service,policy_provider=lambda:self.f.j.policy,clock=lambda:fixtures.review_fixtures.NOW)
        token=menu.prepare(self.ctx(),'/overview').buttons[0][0].callback_data
        first=menu.callback(self.ctx(),token)
        self.assertEqual(first.buttons[0][0].label,'Следующие работы')
        second=menu.callback(self.ctx(),first.buttons[0][0].callback_data)
        self.assertIn('страница 2',second.text)
        self.assertEqual(second.buttons[0][0].label,'Предыдущие работы')
        self.assertTrue(all(len(b.callback_data.encode())<=64 for row in second.buttons for b in row))
