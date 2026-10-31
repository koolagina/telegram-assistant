"""Trusted local lecture selection, artificial lecture/label/clock only."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from lecture_menu import LectureMenu,LectureLabel,LectureMenuError
import test_lecture_windows as fixtures

class LectureMenuTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.WindowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.store=self.f.store();self.addCleanup(self.store.db.close);self.service=self.f.service(self.store)
        self.label=LectureLabel('lecture-a','Экология','317');self.menu=self.make()
    def make(self,labels=None):return LectureMenu(labels if labels is not None else [self.label],service=self.service)
    def token(self,context=None):return self.menu.prepare(context or self.f.b,'/lectures').buttons[0][0].callback_data
    def test_teacher_selects_current_lecture_without_id(self):
        reply=self.menu.prepare(self.f.b,'/lectures')
        self.assertEqual(reply.status,'prepared');self.assertIn('Экология',reply.text);self.assertNotIn('lecture-a',reply.text)
        opened=self.menu.callback(self.f.b,reply.buttons[0][0].callback_data,request_id='click-1')
        self.assertEqual(opened.status,'prepared');self.assertIn('90 секунд',opened.text)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],1)
    def test_owner_only_via_specific_substitution(self):
        self.assertEqual(self.menu.prepare(self.f.a,'/lectures').buttons[0][0].label,'Экология')
        token=self.token(self.f.a);self.f.grants=()
        self.assertEqual(self.menu.callback(self.f.a,token,request_id='click').status,'unavailable')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
    def test_student_or_group_chat_denied_without_labels(self):
        for context in (replace(self.f.b,subject='103'),replace(self.f.b,private=False),replace(self.f.b,authenticated=False)):
            reply=self.menu.prepare(context,'/lectures');self.assertEqual(reply.status,'unavailable');self.assertNotIn('Экология',reply.text)
    def test_changed_source_invalidates_button(self):
        token=self.token();self.f.lecture=replace(self.f.lecture,ends_at=self.f.lecture.ends_at+fixtures.dt.timedelta(minutes=1))
        self.assertEqual(self.menu.callback(self.f.b,token,request_id='click').status,'unavailable')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
    def test_catalog_change_invalidates_button(self):
        token=self.token();new=self.make([replace(self.label,room='318')])
        self.assertEqual(new.callback(self.f.b,token,request_id='click').status,'unavailable')
    def test_expired_lecture_and_exam_not_shown(self):
        for lecture in (replace(self.f.lecture,kind='exam'),replace(self.f.lecture,verified=False),replace(self.f.lecture,ends_at=self.f.now)):
            self.f.lecture=lecture;reply=self.menu.prepare(self.f.b,'/lectures')
            self.assertEqual(reply.buttons,());self.assertNotIn('Экология',reply.text)
    def test_cross_teacher_button_is_not_transferable(self):
        token=self.token()
        self.assertEqual(self.menu.callback(self.f.a,token,request_id='click').status,'unavailable')
    def test_repeated_click_and_new_click_reuse_without_extension(self):
        token=self.token();first=self.menu.callback(self.f.b,token,request_id='click')
        before=self.store.db.execute('SELECT id,expires FROM windows').fetchall()
        self.f.now+=fixtures.dt.timedelta(seconds=20)
        self.assertEqual(self.menu.callback(self.f.b,token,request_id='click'),first)
        self.assertEqual(self.menu.callback(self.f.b,token,request_id='new-click'),first)
        self.assertEqual([tuple(r) for r in self.store.db.execute('SELECT id,expires FROM windows')],[tuple(r) for r in before])
    def test_old_click_after_window_expiry_does_not_reopen(self):
        token=self.token();self.menu.callback(self.f.b,token,request_id='click');self.f.now+=fixtures.dt.timedelta(seconds=90)
        self.assertEqual(self.menu.callback(self.f.b,token,request_id='click').status,'unavailable')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],1)
    def test_listing_is_read_only_and_code_free(self):
        before=self.store.db.total_changes;reply=self.menu.prepare(self.f.b,'/lectures')
        self.assertEqual(self.store.db.total_changes,before);self.assertNotIn('Код лекции:',reply.text)
    def test_malformed_commands_callbacks_and_labels(self):
        self.assertEqual(self.menu.prepare(self.f.b,'/lectures\n').status,'invalid_request')
        for data in ('lect:x','x'*65):self.assertEqual(self.menu.callback(self.f.b,data,request_id='click').status,'unavailable')
        for labels in ([self.label,self.label],[replace(self.label,title='')]):
            with self.assertRaises(LectureMenuError):self.make(labels)
    def test_source_change_between_selection_and_open_is_blocked(self):
        token=self.token();calls=[];original=self.service.policy_provider
        def provider():
            calls.append(1)
            if len(calls)==2:self.f.lecture=replace(self.f.lecture,starts_at=self.f.lecture.starts_at-fixtures.dt.timedelta(minutes=1))
            return original()
        self.service.policy_provider=provider
        self.assertEqual(self.menu.callback(self.f.b,token,request_id='click').status,'unavailable')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
    def test_pages_and_callback_size(self):
        from assistant_access import AccessPolicy
        policy=self.f.policy();lectures=tuple(replace(self.f.lecture,id='lecture-'+str(i)) for i in range(7))
        self.service.policy_provider=lambda:AccessPolicy(teachers=tuple(policy.teachers.values()),students=tuple(policy.students.values()),bindings=tuple(policy.bindings.values()),lectures=lectures)
        menu=self.make([LectureLabel(l.id,'Дисциплина '+str(i),'317') for i,l in enumerate(lectures)])
        first=menu.prepare(self.f.b,'/lectures');self.assertEqual(len(first.buttons),6)
        second=menu.callback(self.f.b,first.buttons[-1][0].callback_data,request_id='page')
        self.assertIn('Страница 2',second.text);self.assertEqual(len(second.buttons),3)
        self.assertTrue(all(len(b.callback_data.encode())<=64 for row in first.buttons+second.buttons for b in row))
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
    def test_stale_page_uses_current_roles_not_old_permissions(self):
        reply=self.menu.prepare(self.f.b,'/lectures')
        self.f.bindings=tuple(replace(b,active=False) if b.subject=='002' else b for b in self.f.bindings)
        self.assertEqual(self.menu.callback(self.f.b,reply.buttons[0][0].callback_data,request_id='click').status,'unavailable')
    def test_expected_source_guard_is_checked_before_clock_or_window_write(self):
        before=self.store.db.total_changes
        with self.assertRaises(fixtures.WindowError):self.service.open(self.f.b,'lecture-a','request',expected_source='wrong-source')
        self.assertEqual(before,self.store.db.total_changes)
