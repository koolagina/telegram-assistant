"""Real local SQLite, synthetic policy/material/work, network prohibited."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assistant_demo import SyntheticAssistantSession,run_assistant_demo

class AssistantDemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.session=SyntheticAssistantSession(Path(self.tmp.name));self.session.__enter__();self.addCleanup(self.session.__exit__,None,None,None)
    def test_ingest_list_click_restart_and_idempotent_retry(self):
        first=self.session.ingest(40);second=self.session.ingest(40);self.assertEqual(first,second)
        page=self.session.request('student-a','/progress');button=page.buttons[0][0]
        self.session.restart_storage()
        result=self.session.callback('student-a',button.callback_data)
        self.assertEqual(result.status,'prepared');self.assertIn('Минимум 40',result.text)
        self.assertEqual(len(self.session.registry.snapshot()),1)
    def test_forwarding_and_revocation_persist_across_storage_restart(self):
        self.session.ingest(40);button=self.session.request('student-a','/progress').buttons[0][0]
        self.assertEqual(self.session.callback('student-b',button.callback_data).status,'unavailable')
        self.session.revoke_student_a();self.session.restart_storage()
        self.assertEqual(self.session.callback('student-a',button.callback_data).status,'unavailable')
    def test_page_navigation_with_durable_links(self):
        for number in range(39,46):self.session.ingest(number)
        first=self.session.request('student-a','/progress');self.assertEqual(first.buttons[-1][-1].label,'Далее')
        self.assertIn('страница 2',self.session.callback('student-a',first.buttons[-1][-1].callback_data).text)
    def test_interrupted_publication_can_retry_without_duplicate_report(self):
        with patch.object(self.session.registry,'register',side_effect=RuntimeError('simulated crash')):
            with self.assertRaises(RuntimeError):self.session.ingest(40)
        self.assertEqual(self.session.registry.snapshot(),())
        self.session.ingest(40)
        self.assertEqual(len(self.session.registry.snapshot()),1)
        self.assertEqual(self.session.catalog.db.execute('SELECT count(*) FROM checks').fetchone()[0],1)
    def test_demo_stays_offline_and_explicitly_synthetic(self):
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network forbidden')):
            output=run_assistant_demo()
        self.assertIn('искусственные данные',output);self.assertIn('Перезапуск хранилища: пройден',output)
        self.assertIn('Чужая кнопка: доступ закрыт',output)

    def test_revocation_survives_new_session_not_just_storage_reopen(self):
        self.session.ingest(40);button=self.session.request('student-a','/progress').buttons[0][0]
        self.session.revoke_student_a();self.session.__exit__(None,None,None)
        with SyntheticAssistantSession(Path(self.tmp.name)) as restarted:
            self.assertEqual(len(restarted.registry.snapshot()),1)
            self.assertEqual(restarted.callback('student-a',button.callback_data).status,'unavailable')
    def test_accepted_publication_then_timeout_retry_does_not_duplicate(self):
        register=self.session.registry.register
        def accepted_then_timeout(*args,**kwargs):
            register(*args,**kwargs)
            raise TimeoutError('simulated after commit')
        with patch.object(self.session.registry,'register',side_effect=accepted_then_timeout):
            with self.assertRaises(TimeoutError):self.session.ingest(40)
        self.session.ingest(40)
        self.assertEqual(len(self.session.registry.snapshot()),1)
        self.assertEqual(self.session.catalog.db.execute('SELECT count(*) FROM checks').fetchone()[0],1)

    def test_injected_verified_polling_adapter_uses_durable_current_policy(self):
        from telegram_report_adapter import TelegramReportAdapter
        self.session.ingest(40)
        envelope={'ok':True,'result':[{'update_id':1,'message':{'message_id':1,'date':1793160000,'from':{'id':103,'is_bot':False},'chat':{'id':103,'type':'private'},'text':'/progress'}}]}
        adapter=TelegramReportAdapter(reader_factory=self.session.reader,bot_id=9001,fetch_verified_updates=lambda:envelope)
        self.assertEqual(adapter.prepare_batch()[0].reply.status,'prepared')
        self.session.revoke_student_a();self.session.restart_storage()
        self.assertEqual(adapter.prepare_batch()[0].reply.status,'unavailable')
