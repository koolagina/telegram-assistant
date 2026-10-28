"""Offline owner confirmations: plans only, no Calendar/Telegram writes."""
import datetime as dt
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import test_assistant_access as fixtures
from consultation_actions import ConsultationActions,Booking,BusyEvent,BusySnapshot,ActionError

class ActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=fixtures.PolicyTests();self.f.setUp();self.policy=self.f.policy()
        self.now=dt.datetime(2026,10,29,9,tzinfo=dt.timezone(dt.timedelta(hours=5)))
        # Use policy fixture's own active date, preserving Thursday local hours.
        self.now=fixtures.NOW.astimezone(self.now.tzinfo).replace(hour=9,minute=0,second=0,microsecond=0)
        self.start=self.now+dt.timedelta(hours=1);self.allowed=True;self.calls=0
        self.booking=Booking('request-a','student-a',self.start,'hold-a')
        self.events=(BusyEvent('hold-a',self.start,self.start+dt.timedelta(minutes=20),'request-a'),)
        self.complete=True;self.observed=self.now
        self.path=Path(self.tmp.name)/'actions.sqlite3'
        self.service=self.open();self.addCleanup(self.service.close);self.service.add(self.booking)
    def open(self):return ConsultationActions(self.path,namespace='synthetic',owner_id='teacher-a',policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=self.snapshot,student_eligible=lambda student,now:self.allowed)
    def snapshot(self):
        self.calls+=1
        return BusySnapshot(self.events,self.observed,self.now.replace(hour=0),self.now.replace(hour=23),self.complete,self.complete)
    def context(self,subject='001'):return self.f.context(subject)
    def preview(self,action='approve',start=None):return self.service.preview(self.context(),'request-a',action,proposed_start=start)
    def confirm(self,intent):return self.service.confirm(self.context(),intent.token)
    def test_preview_is_not_decision_and_cancel_has_no_effect(self):
        intent=self.preview();self.assertEqual(self.service.booking('request-a'),self.booking)
        self.assertEqual(self.service.plans(),());self.service.cancel(self.context(),intent.token)
        with self.assertRaises(ActionError):self.confirm(intent)
    def test_approve_updates_same_owned_event_only_in_durable_plan(self):
        result=self.confirm(self.preview())
        self.assertEqual(result['status'],'planned');self.assertEqual(result['calendar']['method'],'update')
        self.assertEqual(result['calendar']['event_id'],'hold-a');self.assertEqual(len(result['notifications']),2)
        self.assertEqual(self.service.booking('request-a').status,'Подтверждена')
        self.assertEqual(len(self.service.plans()),1)
    def test_double_click_restart_and_peer_do_not_duplicate(self):
        intent=self.preview();first=self.confirm(intent)
        peer=self.open();self.addCleanup(peer.close)
        self.assertEqual(peer.confirm(self.context(),intent.token),first)
        self.assertEqual(len(peer.plans()),1)
    def test_competing_intents_are_revision_bound(self):
        first=self.preview();second=self.preview('reject');self.confirm(first)
        with self.assertRaises(ActionError):self.confirm(second)
        self.assertEqual(len(self.service.plans()),1)
    def test_rejection_plans_owned_delete_and_two_notices(self):
        result=self.confirm(self.preview('reject'))
        self.assertEqual(result['calendar']['method'],'delete');self.assertEqual(len(result['notifications']),2)
        self.assertEqual(self.service.booking('request-a').status,'Отклонена')
    def test_proposal_does_not_move_or_release_hold(self):
        result=self.confirm(self.preview('propose',self.start+dt.timedelta(hours=3)))
        current=self.service.booking('request-a')
        self.assertEqual(current.starts_at,self.start);self.assertEqual(current.status,'Ожидает решения')
        self.assertIsNone(result['calendar']);self.assertIn('proposed_start',result)
    def test_student_other_teacher_and_forged_token_denied(self):
        intent=self.preview()
        for subject in ('002','003'):
            with self.assertRaises(ActionError):self.service.confirm(self.context(subject),intent.token)
        with self.assertRaises(ActionError):self.service.confirm(self.context(),'0'*32)
        self.assertEqual(self.service.plans(),())
    def test_revoke_after_preview_denies_even_repeated_confirmation(self):
        intent=self.preview();self.policy=self.f.policy(bindings=())
        with self.assertRaises(ActionError):self.confirm(intent)
        self.assertEqual(self.service.plans(),())
    def test_expired_confirmation_denied(self):
        intent=self.preview();self.now+=dt.timedelta(minutes=5)
        with self.assertRaises(ActionError):self.confirm(intent)
    def test_new_busy_event_after_preview_blocks_confirmation(self):
        intent=self.preview();self.events+=(BusyEvent('lesson',self.start,self.start+dt.timedelta(hours=1)),)
        with self.assertRaises(ActionError):self.confirm(intent)
        self.assertEqual(self.service.plans(),())
    def test_incomplete_stale_or_unowned_calendar_fails_closed(self):
        self.complete=False
        with self.assertRaises(ActionError):self.preview()
        self.complete=True;self.observed=self.now-dt.timedelta(minutes=6)
        with self.assertRaises(ActionError):self.preview()
        self.observed=self.now;self.events=(replace(self.events[0],consultation_id=None),)
        with self.assertRaises(ActionError):self.preview('reject')
    def test_student_access_rechecked_and_revoke_during_snapshot(self):
        intent=self.preview();self.allowed=False
        with self.assertRaises(ActionError):self.confirm(intent)
        self.allowed=True
        original=self.service.calendar_snapshot
        def revoked():
            result=original();self.policy=self.f.policy(bindings=());return result
        self.service.calendar_snapshot=revoked
        with self.assertRaises(ActionError):self.confirm(intent)
        self.assertEqual(self.service.plans(),())
    def test_boundary_rules_and_half_open_conflicts(self):
        for hour,minute in ((8,59),(11,30),(12,0),(17,41)):
            with self.assertRaises(ActionError):self.preview('propose',self.start.replace(hour=hour,minute=minute))
        for hour,minute in ((11,20),(12,20),(17,40)):
            self.preview('propose',self.start.replace(hour=hour,minute=minute))
        with self.assertRaises(ActionError):self.preview('propose',self.now+dt.timedelta(minutes=29))
        self.preview('propose',self.now+dt.timedelta(minutes=30))
        weekend=self.start+dt.timedelta(days=(5-self.start.weekday())%7)
        with self.assertRaises(ActionError):self.preview('propose',weekend)
    def test_transaction_failure_rolls_back_decision_and_plan(self):
        intent=self.preview()
        self.service.db.execute("CREATE TRIGGER fail_plan BEFORE INSERT ON action_plans BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(ActionError):self.confirm(intent)
        self.assertEqual(self.service.booking('request-a'),self.booking);self.assertEqual(self.service.plans(),())
        self.service.db.execute('DROP TRIGGER fail_plan')
        self.confirm(intent);self.assertEqual(len(self.service.plans()),1)
    def test_ambiguous_own_hold_and_foreign_project_rejected(self):
        self.events*=2
        with self.assertRaises(ActionError):self.preview()
        with self.assertRaises(ActionError):ConsultationActions(self.path,namespace='other',owner_id='teacher-a',policy_provider=lambda:self.policy,clock=lambda:self.now,calendar_snapshot=self.snapshot,student_eligible=lambda *args:True)
    def test_student_revoked_during_snapshot_blocks_plan(self):
        intent=self.preview();original=self.service.calendar_snapshot
        def revoke():
            result=original();self.allowed=False;return result
        self.service.calendar_snapshot=revoke
        with self.assertRaises(ActionError):self.confirm(intent)
        self.assertEqual(self.service.plans(),())
    def test_snapshot_read_cannot_extend_confirmation_expiry(self):
        intent=self.preview();original=self.service.calendar_snapshot
        def slow():
            result=original();self.now+=dt.timedelta(minutes=5);return result
        self.service.calendar_snapshot=slow
        with self.assertRaises(ActionError):self.confirm(intent)
        self.assertEqual(self.service.plans(),())
    def test_approval_within_thirty_minutes_is_allowed_but_proposal_is_not(self):
        # Minimum booking lead is not a new owner approval deadline.
        self.now=self.start-dt.timedelta(minutes=15);self.observed=self.now
        self.confirm(self.preview())
    def test_adjacent_busy_event_does_not_block_and_overlapping_one_does(self):
        self.events+=(BusyEvent('before',self.start-dt.timedelta(minutes=20),self.start),BusyEvent('after',self.start+dt.timedelta(minutes=20),self.start+dt.timedelta(hours=1)))
        self.preview()
        self.events+=(BusyEvent('overlap',self.start-dt.timedelta(minutes=1),self.start+dt.timedelta(minutes=1)),)
        with self.assertRaises(ActionError):self.preview()
    def test_existing_success_still_requires_current_owner_access(self):
        intent=self.preview();self.confirm(intent);self.policy=self.f.policy(bindings=())
        with self.assertRaises(ActionError):self.confirm(intent)
    def test_local_store_does_not_import_conflicting_or_naive_fixture(self):
        with self.assertRaises(ActionError):self.service.add(replace(self.booking,student_id='student-b'))
        with self.assertRaises(ActionError):self.service.add(replace(self.booking,starts_at=self.start.replace(tzinfo=None)))
    def test_partial_coverage_and_future_timestamp_rejected(self):
        original=self.service.calendar_snapshot
        self.service.calendar_snapshot=lambda:replace(original(),covered_end=self.start)
        with self.assertRaises(ActionError):self.preview()
        self.service.calendar_snapshot=lambda:replace(original(),observed_at=self.now+dt.timedelta(seconds=1))
        with self.assertRaises(ActionError):self.preview()
    def test_simultaneous_connections_commit_one_plan(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        intent=self.preview();barrier=Barrier(2)
        def run():
            service=self.open()
            try:
                barrier.wait(timeout=5)
                return service.confirm(self.context(),intent.token)
            finally:service.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run) for _ in range(2)]
            results=[future.result(timeout=10) for future in futures]
        self.assertEqual(results[0],results[1]);self.assertEqual(len(self.service.plans()),1)
