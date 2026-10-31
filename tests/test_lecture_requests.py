"""Local command preparations only, artificial accounts/keys/clock."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from lecture_requests import prepare_lecture_reply
from assistant_access import Binding,Context
import test_lecture_windows as fixtures

class LectureRequestTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.WindowTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.bindings+= (Binding('telegram','103','student','student-a',frozenset({'attendance.register'}),confirmed=True),)
        self.student=Context('telegram','103',authenticated=True,private=True)
        self.store=self.f.store();self.addCleanup(self.store.db.close);self.service=self.f.service(self.store)
    def prepare(self,ctx,command,request='message-1'):
        return prepare_lecture_reply(self.service,ctx,command,request_id=request)
    def test_teacher_and_substitute_can_get_same_window_without_waiting(self):
        a=self.prepare(self.f.a,'/lecturecode lecture-a')
        b=self.prepare(self.f.b,'/lecturecode lecture-a')
        self.assertEqual(a.status,'prepared');self.assertEqual(a.text,b.text)
        self.assertIn('90 секунд',a.text);self.assertIsNone(a.parse_mode)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],1)
    def test_student_registers_self_without_code_in_response(self):
        window=self.service.open(self.f.b,'lecture-a','open')
        command='/attend lecture-a '+window.code
        a=self.prepare(self.student,command);b=self.prepare(self.student,command)
        self.assertEqual(a.status,'prepared');self.assertEqual(a,b)
        self.assertNotIn(window.code,a.text);self.assertIn('журнал',a.text)
        self.assertEqual(self.store.attendance_count(),1)
    def test_student_cannot_get_lecture_code(self):
        self.assertEqual(self.prepare(self.student,'/lecturecode lecture-a').status,'unavailable')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
    def test_unverified_schedule_does_not_open_code(self):
        self.f.lecture=replace(self.f.lecture,verified=False)
        self.assertEqual(self.prepare(self.f.b,'/lecturecode lecture-a').status,'unavailable')
    def test_exams_are_not_lectures(self):
        self.f.lecture=replace(self.f.lecture,kind='exam')
        self.assertEqual(self.prepare(self.f.b,'/lecturecode lecture-a').status,'unavailable')
    def test_bad_syntax_never_opens_window(self):
        for cmd in ('/lecturecode','/lecturecode lecture-a\n','/attend lecture-a 12345','/attend lecture-a 1234 student-b'):
            self.assertEqual(self.prepare(self.f.b,cmd).status,'invalid_request')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],0)
    def test_expired_replay_cannot_create_replacement(self):
        self.prepare(self.f.b,'/lecturecode lecture-a')
        self.f.now+=fixtures.dt.timedelta(seconds=90)
        self.assertEqual(self.prepare(self.f.b,'/lecturecode lecture-a').status,'unavailable')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM windows').fetchone()[0],1)
