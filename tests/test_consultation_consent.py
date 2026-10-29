"""Original-evidence review/consent registry; all identities and APIs fake."""
import copy
from dataclasses import replace
import datetime as dt
import json
from pathlib import Path
import unittest
import test_consultation_workflow as workflow_fixtures
from consultation_consent import ConsultationConsent
from consultation_workflow import ConsultationWorkflow,WorkflowError
from consultation_executor import ExecutorError
from material_versions import digest

class ConsentTests(unittest.TestCase):
    def setUp(self):
        workflow_fixtures.WorkflowTests.setUp(self)
        from consultation_actions import ConsultationActions,Booking
        # Fresh pending core fixture; keep the setup's old immutable history intact.
        self.actions=ConsultationActions(self.root/'consent-actions.sqlite3',namespace='synthetic',owner_id='owner',policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=self.busy,student_eligible=lambda *args:True)
        self.addCleanup(self.actions.close);self.actions.add(Booking('synthetic-request','student-a',self.start,'synthetic-hold'))
    open_state=workflow_fixtures.WorkflowTests.open_state
    busy=workflow_fixtures.WorkflowTests.busy
    send=workflow_fixtures.WorkflowTests.send
    def registry(self):return ConsultationConsent(self.state,self.actions,self.calendar,hold_bindings=lambda:self.bindings)
    def preview(self,action='approve',key='synthetic-update'):
        return self.registry().preview(self.ctx,self.row[0],action,request_key=digest(key))
    def test_preview_captures_original_source_event_and_display(self):
        review=self.preview();self.assertEqual(review.student_label,'Synthetic student');self.assertEqual(review.topic,'Synthetic topic')
        self.assertEqual(self.state.claimed(self.ctx,review.token),None)
        with self.assertRaises(WorkflowError):self.registry().load_confirmed(review.token)
        self.assertEqual(self.calendar.calls,[])
    def test_confirm_publishes_bound_plan_and_source_claim_atomically(self):
        review=self.preview();registry=self.registry();bound=registry.confirm(self.ctx,review.token)
        self.assertEqual(bound.source_revision,self.bound.source_revision);self.assertEqual(bound.event_revision,self.bound.event_revision)
        self.assertEqual(registry.load_confirmed(bound.id),bound);self.assertEqual(self.state.claimed(self.ctx,bound.id),bound)
        self.assertEqual(self.calendar.calls,[])
    def test_same_verified_request_returns_same_preview_without_new_intent(self):
        first=self.preview();second=self.preview()
        self.assertEqual(first,second)
        self.assertEqual(self.state.db.execute('SELECT count(*) FROM workflow_reviews').fetchone()[0],1)
        self.assertEqual(self.actions.db.execute('SELECT count(*) FROM action_intents').fetchone()[0],1)
    def test_request_key_cannot_be_retargeted(self):
        self.preview()
        with self.assertRaises(WorkflowError):self.preview('reject')
    def test_changed_topic_event_or_recipient_after_review_denies_confirmation(self):
        review=self.preview()
        self.state.edit(self.ctx,self.row[0],self.bound.source_revision,self.row[:7]+('New topic',)+self.row[8:])
        with self.assertRaises(WorkflowError):self.registry().confirm(self.ctx,review.token)
        self.assertIsNone(self.state.claimed(self.ctx,review.token));self.assertEqual(self.calendar.calls,[])
    def test_manual_event_change_after_review_denies_confirmation(self):
        review=self.preview();self.calendar.event=replace(self.calendar.event,etag='manual',description='Changed note')
        with self.assertRaises(WorkflowError):self.registry().confirm(self.ctx,review.token)
        self.assertIsNone(self.state.claimed(self.ctx,review.token))
    def test_cancel_and_expiry_never_publish_executable_plan(self):
        first=self.preview();self.registry().cancel(self.ctx,first.token)
        with self.assertRaises(WorkflowError):self.registry().confirm(self.ctx,first.token)
        second=self.preview(key='second');self.now+=dt.timedelta(minutes=5)
        with self.assertRaises(WorkflowError):self.registry().confirm(self.ctx,second.token)
        self.assertEqual(self.calendar.calls,[])
    def test_student_or_forwarded_actor_cannot_confirm(self):
        from assistant_access import Context
        review=self.preview()
        with self.assertRaises(WorkflowError):self.registry().confirm(Context('telegram','103',authenticated=True,private=True),review.token)
        self.assertIsNone(self.state.claimed(self.ctx,review.token))
    def test_publication_failure_can_retry_original_decision_without_new_evidence(self):
        review=self.preview();registry=self.registry()
        self.state.db.execute("CREATE TRIGGER fail_publication BEFORE UPDATE ON workflow_reviews WHEN NEW.phase='confirmed' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(WorkflowError):registry.confirm(self.ctx,review.token)
        self.assertIsNone(self.state.claimed(self.ctx,review.token))
        started=self.state.db.execute('SELECT started_at FROM workflow_reviews WHERE token=?',(review.token,)).fetchone()[0]
        self.state.db.execute('DROP TRIGGER fail_publication');self.now+=dt.timedelta(seconds=10)
        bound=registry.confirm(self.ctx,review.token)
        self.assertEqual(bound.confirmed_at,dt.datetime.fromisoformat(started));self.assertEqual(self.calendar.calls,[])
    def test_bound_plan_drives_existing_workflow_and_retry_does_not_read_changed_event(self):
        registry=self.registry();review=self.preview();bound=registry.confirm(self.ctx,review.token)
        self.executor.load_plan=registry.load_confirmed
        result=ConsultationWorkflow(self.state,self.executor).advance(self.ctx,bound.id,workflow_enabled=True)
        self.assertEqual(result['stage'],'finalized')
        self.assertEqual(registry.confirm(self.ctx,review.token),bound);self.assertEqual(len(self.calendar.calls),1)
    def test_corrupt_review_evidence_never_becomes_authorized_plan(self):
        review=self.preview()
        self.state.db.execute("UPDATE workflow_reviews SET event_revision='broken' WHERE token=?",(review.token,))
        with self.assertRaises(WorkflowError):self.registry().confirm(self.ctx,review.token)
        self.assertEqual(self.calendar.calls,[])
    def test_foreign_or_unowned_calendar_event_is_not_reviewable(self):
        self.bindings=()
        with self.assertRaises(WorkflowError):self.preview()
        self.assertEqual(self.state.db.execute('SELECT count(*) FROM workflow_reviews').fetchone()[0],0)
    def test_denied_actor_is_checked_before_private_review_read(self):
        from unittest.mock import patch
        from assistant_access import Context
        registry=self.registry();review=self.preview();student=Context('telegram','103',authenticated=True,private=True)
        with patch.object(registry,'_get',wraps=registry._get) as read:
            with self.assertRaises(WorkflowError):registry.confirm(student,review.token)
            self.assertEqual(read.call_count,0)
            with self.assertRaises(WorkflowError):registry.cancel(student,review.token)
            self.assertEqual(read.call_count,0)
    def test_confirmed_review_survives_state_restart_and_cannot_be_cancelled_as_draft(self):
        registry=self.registry();review=self.preview();bound=registry.confirm(self.ctx,review.token)
        peer=self.open_state();self.addCleanup(peer.close)
        reopened=ConsultationConsent(peer,self.actions,self.calendar,hold_bindings=lambda:self.bindings)
        self.assertEqual(reopened.load_confirmed(bound.id),bound)
        self.assertFalse(reopened.cancel(self.ctx,review.token));self.assertEqual(reopened.load_confirmed(bound.id),bound)
