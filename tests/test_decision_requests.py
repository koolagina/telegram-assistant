"""Read-only decision menu and callbacks with current owner authorization."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from decision_requests import prepare_decision_reply,prepare_decision_callback
import test_decision_queue as fixtures

class RequestTests(unittest.TestCase):
    def setUp(self):self.f=fixtures.DecisionTests();self.f.setUp();self.f.records['consultation']=[self.f.item()]
    def prepare(self,command='/decisions',subject='001'):return prepare_decision_reply(self.f.queue,self.f.context(subject),command)
    def test_menu_counts_buttons_and_plaintext(self):
        reply=self.prepare();self.assertEqual(reply.status,'prepared')
        self.assertIn('Консультации: 1',reply.text);self.assertIsNone(reply.parse_mode)
        self.assertTrue(reply.link_preview_disabled)
        for row in reply.buttons:
            for button in row:self.assertLessEqual(len(button.callback_data.encode()),64)
    def test_open_detail_and_back_without_source_mutation(self):
        page=self.prepare();button=next(b for row in page.buttons for b in row if b.callback_data.startswith('dec:o:'))
        detail=prepare_decision_callback(self.f.queue,self.f.context(),button.callback_data)
        self.assertIn('Synthetic detail',detail.text);self.assertIn('Никакие решения',detail.text)
        self.assertEqual(len(self.f.records['consultation']),1)
        self.assertEqual(prepare_decision_callback(self.f.queue,self.f.context(),detail.buttons[0][0].callback_data).status,'prepared')
    def test_stale_or_forwarded_button_not_authority(self):
        reference=self.f.queue.page(self.f.context()).items[0].reference
        self.assertEqual(prepare_decision_callback(self.f.queue,self.f.context('003'),'dec:o:'+reference).status,'unavailable')
        self.f.records['consultation']=[]
        self.assertEqual(prepare_decision_callback(self.f.queue,self.f.context(),'dec:o:'+reference).status,'unavailable')
    def test_partial_empty_menu_does_not_claim_nothing_to_do(self):
        self.f.records['consultation']=[]
        self.f.queue.sources['review']=lambda *args:(_ for _ in ()).throw(RuntimeError('private URL'))
        reply=self.prepare();self.assertIn('Сводка неполная',reply.text)
        self.assertNotIn('Решений не требуется',reply.text);self.assertNotIn('private',reply.text)
    def test_paging_and_filter(self):
        self.f.records['consultation']=[self.f.item(source=f'r{i}') for i in range(7)]
        second=prepare_decision_callback(self.f.queue,self.f.context(),'dec:p:consultation:2')
        self.assertIn('Страница 2',second.text)
        self.assertEqual(sum(b.callback_data.startswith('dec:o:') for row in second.buttons for b in row),2)
    def test_invalid_callback_or_action_is_not_executed(self):
        for data in ['dec:approve:anything','dec:p:all:0','dec:o:'+'a'*65]:
            self.assertEqual(prepare_decision_callback(self.f.queue,self.f.context(),data).status,'unavailable')
        self.assertEqual(self.prepare('/decisions send all').status,'invalid_request')
