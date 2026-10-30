"""Synthetic trusted providers; existing NVSU parser, no real HTTP or Calendar."""
import copy
from dataclasses import replace
import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nvsu_source import fetch_week
from nvsu_sync import event_payload
from consultation_feed import CalendarSnapshot,BusyFeed
from consultation_actions import TZ,BusySnapshot,BusyEvent
from teaching_coverage import TeachingCoverageFeed,CoverageError,preview_consultation_slots
FIXTURES=Path(__file__).parent/'fixtures/nvsu'
NOW=dt.datetime(2026,11,2,8,tzinfo=TZ)
class TeachingCoverageTests(unittest.TestCase):
    def setUp(self):
        self.now=NOW
        self.proof=fetch_week('2026-11-02','9999','Тестовый Преподаватель',fetch=lambda url:(200,'text/html',(FIXTURES/'next.html').read_bytes()),now=NOW)
        self.start=NOW.replace(hour=0);self.end=self.start+dt.timedelta(days=7)
        self.calendar=CalendarSnapshot('synthetic-calendar',tuple(dict(id='lesson-'+str(i),**event_payload(l)) for i,l in enumerate(self.proof['week']['lessons'])),NOW,self.start,self.end,True)
        self.feed=TeachingCoverageFeed(teacher_id='teacher',lecturer_id='9999',teacher_name='Тестовый Преподаватель',calendar_id='synthetic-calendar',load_source=lambda date:copy.deepcopy(self.proof),load_calendar=lambda start,end:self.calendar,clock=lambda:self.now)
    def assess(self):return self.feed.assess('2026-11-02')
    def test_empty_calendar_cannot_authorize_consultations_when_source_has_classes(self):
        self.calendar=replace(self.calendar,events=())
        r=self.assess();self.assertEqual(r.status,'import_required');self.assertIsNone(r.verification);self.assertEqual(r.missing,11)
    def test_exact_calendar_can_prove_coverage_even_if_manual_events_are_protected(self):
        self.calendar=replace(self.calendar,events=tuple(dict(e,protected=True,attendees=[{'email':'synthetic.invalid'}]) for e in self.calendar.events))
        r=self.assess();self.assertEqual(r.status,'verified');self.assertEqual(r.matched,11);self.assertIsNotNone(r.verification);self.assertFalse(r.summary()['ready_for_calendar_apply'])
    def test_coverage_is_bound_to_the_existing_busy_feed_and_excludes_classes(self):
        r=self.assess();busy=BusyFeed(target_id='synthetic-calendar',teaching_id='synthetic-calendar',teacher_id='teacher',load_target=lambda:self.calendar,load_teaching=lambda:self.calendar,load_verification=lambda:r.verification,load_bindings=lambda:(),clock=lambda:self.now)()
        self.assertTrue(busy.teaching_complete)
        preview=preview_consultation_slots(busy,'2026-11-02',now=self.now)
        self.assertEqual(preview.status,'ready');self.assertFalse(preview.live_booking_enabled)
        for start in preview.starts:
            self.assertTrue(all(not(start<dt.datetime.fromisoformat(e['end']) and start+dt.timedelta(minutes=20)>dt.datetime.fromisoformat(e['start'])) for e in self.calendar.events))
    def test_partial_import_requires_remaining_lesson_not_a_free_calendar_assumption(self):
        self.calendar=replace(self.calendar,events=self.calendar.events[:-1]);r=self.assess();self.assertEqual(r.missing,1);self.assertIsNone(r.verification)
    def test_duplicate_calendar_event_is_not_accepted_as_two_independent_classes(self):
        self.calendar=replace(self.calendar,events=self.calendar.events+(dict(self.calendar.events[0],id='duplicate'),));r=self.assess();self.assertEqual(r.status,'review_required');self.assertGreater(r.ambiguous,0)
    def test_multiple_source_groups_still_represent_one_physical_lesson(self):
        duplicate=copy.deepcopy(self.proof['week']['lessons'][0]);duplicate['source_refs']=['lecturer:9999:synthetic-alias'];self.proof['week']['lessons'].append(duplicate)
        r=self.assess();self.assertEqual(r.lessons,11);self.assertEqual(r.status,'verified')
    def test_other_appointment_overlapping_a_class_requires_review(self):
        self.calendar=replace(self.calendar,events=self.calendar.events+(dict(self.calendar.events[0],id='personal-event',title='Synthetic appointment'),));self.assertGreater(self.assess().conflicts,0)
    def test_fixture_label_cannot_issue_teaching_verification(self):
        self.proof['mode']='fixture';r=self.assess();self.assertEqual(r.status,'fixture_only');self.assertIsNone(r.verification)
    def test_explicit_no_schedule_proves_only_that_week_and_keeps_personal_busy_events(self):
        self.now=dt.datetime(2026,10,26,8,tzinfo=TZ);start=self.now.replace(hour=0)
        self.proof=fetch_week('2026-10-26','9999','Тестовый Преподаватель',fetch=lambda url:(200,'text/html',(FIXTURES/'current.html').read_bytes()),now=self.now)
        event=dict(id='personal',start=start.replace(hour=9).isoformat(),end=start.replace(hour=10).isoformat(),title='Synthetic private',location='')
        self.calendar=CalendarSnapshot('synthetic-calendar',(event,),self.now,start,start+dt.timedelta(days=7),True)
        before=copy.deepcopy(self.calendar);r=self.feed.assess('2026-10-26');self.assertEqual(r.lessons,0);self.assertEqual(r.status,'verified');self.assertEqual(self.calendar,before);self.assertEqual(r.plan['operations'],[])
    def test_empty_parsed_table_is_not_equivalent_to_explicit_no_schedule(self):
        self.proof['week']['lessons']=[]
        with self.assertRaises(CoverageError):self.assess()
    def test_source_wrong_week_is_not_reinterpreted_as_current_week(self):
        with self.assertRaises(CoverageError):self.feed.assess('2026-11-09')
    def test_wrong_identity_or_source_proof_never_issues_an_attestation(self):
        for field,value in [('lecturer_id','1234'),('teacher_name','Other'),('url','https://invalid.example/'),('raw_sha256','not-a-hash')]:
            old=copy.deepcopy(self.proof);self.proof[field]=value
            with self.assertRaises(CoverageError):self.assess()
            self.proof=old
    def test_stale_or_future_source_and_stale_calendar_fail_closed(self):
        original=copy.deepcopy(self.proof)
        for stamp in [NOW-dt.timedelta(minutes=6),NOW+dt.timedelta(seconds=1)]:
            self.proof['fetched_at']=stamp.isoformat()
            with self.assertRaises(CoverageError):self.assess()
        self.proof=original;self.calendar=replace(self.calendar,observed_at=NOW-dt.timedelta(minutes=6))
        with self.assertRaises(CoverageError):self.assess()
    def test_wrong_incomplete_or_wrong_range_calendar_fails(self):
        original=self.calendar
        for changed in [replace(original,calendar_id='foreign'),replace(original,complete=False),replace(original,covered_end=original.covered_end-dt.timedelta(days=1))]:
            self.calendar=changed
            with self.assertRaises(CoverageError):self.assess()
    def test_changed_source_discipline_requires_new_calendar_comparison(self):
        self.proof['week']['lessons'][0]['title']='New synthetic discipline';r=self.assess();self.assertEqual(r.status,'import_required');self.assertIsNone(r.verification)
    def test_calendar_change_invalidates_the_existing_busy_attestation(self):
        evidence=self.assess().verification
        self.calendar=replace(self.calendar,events=self.calendar.events+(dict(id='new-busy',start='2026-11-02T09:00:00+05:00',end='2026-11-02T09:20:00+05:00',title='Synthetic private',location=''),))
        busy=BusyFeed(target_id='synthetic-calendar',teaching_id='synthetic-calendar',teacher_id='teacher',load_target=lambda:self.calendar,load_teaching=lambda:self.calendar,load_verification=lambda:evidence,load_bindings=lambda:(),clock=lambda:self.now)()
        self.assertFalse(busy.teaching_complete);self.assertEqual(preview_consultation_slots(busy,'2026-11-02',now=self.now).status,'blocked')
    def test_semantic_source_revision_is_bound_to_bytes_and_week(self):
        first=self.assess().verification.source_revision;self.proof['raw_sha256']='a'*64;self.assertNotEqual(first,self.assess().verification.source_revision)
    def test_read_only_assessment_does_not_mutate_inputs_or_publish_details(self):
        before=copy.deepcopy((self.proof,self.calendar));r=self.assess();self.assertEqual((self.proof,self.calendar),before)
        text=str(r.summary());self.assertNotIn('Тестовый',text);self.assertNotIn('synthetic-calendar',text);self.assertNotIn('Учебный',text);self.assertEqual(r.summary()['writes'],0)

class SlotPreviewTests(unittest.TestCase):
    def setUp(self):
        self.now=NOW;self.snapshot=BusySnapshot((),NOW,NOW.replace(hour=0),NOW.replace(hour=0)+dt.timedelta(days=7),True,True)
    def starts(self,**kwargs):return preview_consultation_slots(self.snapshot,'2026-11-02',now=kwargs.get('now',self.now)).starts
    def test_hours_lunch_twenty_minutes_and_room(self):
        result=preview_consultation_slots(self.snapshot,'2026-11-02',now=self.now);times=[x.strftime('%H:%M') for x in result.starts]
        self.assertEqual(len(times),25);self.assertEqual(times[0],'09:00');self.assertEqual(times[-1],'17:40');self.assertIn('11:20',times);self.assertNotIn('11:40',times);self.assertNotIn('12:00',times);self.assertIn('12:20',times);self.assertEqual(result.room,'Кабинет 317')
    def test_exact_thirty_minute_lead_is_allowed(self):
        self.now=NOW.replace(hour=8,minute=30);self.snapshot=replace(self.snapshot,observed_at=self.now);self.assertEqual(self.starts()[0].strftime('%H:%M'),'09:00')
        self.now+=dt.timedelta(seconds=1);self.assertEqual(self.starts()[0].strftime('%H:%M'),'09:20')
    def test_weekend_offers_nothing(self):self.assertEqual(preview_consultation_slots(self.snapshot,'2026-11-07',now=self.now).starts,())
    def test_missing_teaching_or_calendar_completeness_offers_nothing(self):
        for complete,teaching in [(False,True),(True,False)]:self.assertEqual(preview_consultation_slots(replace(self.snapshot,complete=complete,teaching_complete=teaching),'2026-11-02',now=self.now).starts,())
    def test_busy_event_edges_are_half_open_and_pending_hold_blocks_slot(self):
        event=BusyEvent('pending',NOW.replace(hour=9,minute=20),NOW.replace(hour=9,minute=40),'request')
        self.snapshot=replace(self.snapshot,events=(event,));times=[x.strftime('%H:%M') for x in self.starts()];self.assertIn('09:00',times);self.assertNotIn('09:20',times);self.assertIn('09:40',times)
    def test_stale_or_partial_busy_evidence_is_not_free_time(self):
        for change in [dict(observed_at=NOW-dt.timedelta(minutes=6)),dict(covered_end=NOW.replace(hour=12))]:
            with self.assertRaises(CoverageError):preview_consultation_slots(replace(self.snapshot,**change),'2026-11-02',now=self.now)
    def test_duplicate_busy_identity_is_rejected(self):
        event=BusyEvent('duplicate',NOW.replace(hour=9),NOW.replace(hour=10));self.snapshot=replace(self.snapshot,events=(event,event))
        with self.assertRaises(CoverageError):self.starts()
