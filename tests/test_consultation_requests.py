"""Explicit local UI handler; never run as report dispatch preparation."""
import unittest
import test_consultation_actions as fixtures
from consultation_requests import consultation_card,handle_local_consultation_callback,handle_local_proposal

class MenuTests(unittest.TestCase):
    setUp=fixtures.ActionTests.setUp
    open=fixtures.ActionTests.open
    snapshot=fixtures.ActionTests.snapshot
    context=fixtures.ActionTests.context
    def card(self):return consultation_card(self.service,self.context(),'request-a')
    def button(self,reply,prefix):return next(b.callback_data for row in reply.buttons for b in row if b.callback_data.startswith(prefix))
    def test_card_buttons_and_preview_require_second_click(self):
        card=self.card();self.assertIn('317',card.text)
        preview=handle_local_consultation_callback(self.service,self.context(),self.button(card,'con:a:approve:'))
        self.assertIn('Подтвердить действие',preview.text);self.assertEqual(self.service.plans(),())
        done=handle_local_consultation_callback(self.service,self.context(),self.button(preview,'con:c:'))
        self.assertIn('не выполнены',done.text);self.assertEqual(len(self.service.plans()),1)
    def test_cancel_confirmation_preserves_booking(self):
        preview=handle_local_consultation_callback(self.service,self.context(),self.button(self.card(),'con:a:reject:'))
        handle_local_consultation_callback(self.service,self.context(),self.button(preview,'con:x:'))
        self.assertEqual(self.service.booking('request-a'),self.booking)
        self.assertEqual(handle_local_consultation_callback(self.service,self.context(),self.button(preview,'con:c:')).status,'unavailable')
    def test_proposal_uses_exact_local_time_not_user_timezone(self):
        ref=self.service.reference(self.context(),'request-a')
        local=self.start.replace(hour=14,minute=0)
        reply=handle_local_proposal(self.service,self.context(),'/consult_propose '+ref+' '+local.strftime('%Y-%m-%d %H:%M'))
        self.assertEqual(reply.status,'prepared');self.assertIn('14:00',reply.text)
        result=handle_local_consultation_callback(self.service,self.context(),self.button(reply,'con:c:'))
        self.assertEqual(result.status,'prepared');self.assertIsNone(self.service.plans()[0]['calendar'])
    def test_forwarded_and_changed_reference_denied(self):
        card=self.card();data=self.button(card,'con:a:approve:')
        self.assertEqual(handle_local_consultation_callback(self.service,self.context('003'),data).status,'unavailable')
        preview=handle_local_consultation_callback(self.service,self.context(),data)
        handle_local_consultation_callback(self.service,self.context(),self.button(preview,'con:c:'))
        self.assertEqual(handle_local_consultation_callback(self.service,self.context(),data).status,'unavailable')
    def test_untrusted_payloads_and_invalid_dates_not_executed(self):
        ref=self.service.reference(self.context(),'request-a')
        for data in ('con:c:../x','con:a:delete:'+ref,'con:c:'+'я'*32,'con:c:'+'a'*100):
            self.assertEqual(handle_local_consultation_callback(self.service,self.context(),data).status,'unavailable')
        for date in ('2026-02-30 10:00','2026-10-29 25:00','2026-10-29 10:00+00:00'):
            self.assertEqual(handle_local_proposal(self.service,self.context(),'/consult_propose '+ref+' '+date).status,'unavailable')
        self.assertEqual(self.service.plans(),())
    def test_plain_text_bounded_callbacks_and_no_api_claim(self):
        card=self.card();self.assertIsNone(card.parse_mode);self.assertTrue(card.link_preview_disabled)
        self.assertIn('Локальный',card.text)
        for row in card.buttons:
            for button in row:self.assertLessEqual(len(button.callback_data.encode()),64)
    def test_demo_is_offline_and_has_no_random_tokens_in_artifact(self):
        from unittest.mock import patch
        from consultation_demo import run_consultation_demo
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network forbidden')):
            output=run_consultation_demo()
        self.assertIn('Планов: 1; реальных событий и сообщений: 0',output)
        self.assertNotIn('con:c:',output)
