"""Owner-only current-source decision queue, synthetic records."""
from dataclasses import replace
import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from decision_queue import DecisionItem,DecisionSnapshot,DecisionQueue,DecisionError
import test_assistant_access as fixtures

class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PolicyTests();self.f.setUp();self.policy=self.f.policy();self.now=fixtures.NOW
        self.records={'consultation':[],'review':[],'technical':[]};self.calls=[]
        self.queue=DecisionQueue(owner_id='teacher-a',policy_provider=lambda:self.policy,clock=lambda:self.now,
            sources={kind:self.provider(kind) for kind in self.records})
    def provider(self,kind):
        def load(context,policy,now):self.calls.append(kind);return DecisionSnapshot(tuple(self.records[kind]),now)
        return load
    def item(self,kind='consultation',source='request-a',**values):
        if kind=='review' and 'enrollment' not in values:values['enrollment']=('enrollment-a','student-a','discipline-a','group-a')
        return DecisionItem(kind,source,'teacher-a','Synthetic title','Synthetic detail',self.now-dt.timedelta(hours=1),None,2,**values)
    def context(self,subject='001'):return self.f.context(subject)
    def test_owner_list_has_three_types_and_no_duplicates(self):
        for kind in self.records:self.records[kind]=[self.item(kind)]
        self.records['consultation']*=2
        page=self.queue.page(self.context());self.assertEqual(len(page.items),3)
        self.assertEqual(page.counts,{'consultation':1,'review':1,'technical':1})
    def test_student_or_other_teacher_denied_before_source_read(self):
        for subject in ['002','003']:
            with self.assertRaises(DecisionError):self.queue.page(self.context(subject))
        self.assertEqual(self.calls,[])
    def test_resolved_source_disappears_and_old_button_is_stale(self):
        self.records['consultation']=[self.item()];reference=self.queue.page(self.context()).items[0].reference
        self.records['consultation']=[]
        with self.assertRaises(DecisionError):self.queue.detail(self.context(),reference)
        self.assertEqual(self.queue.page(self.context()).items,())
    def test_changed_source_invalidates_old_detail_reference(self):
        self.records['consultation']=[self.item()];reference=self.queue.page(self.context()).items[0].reference
        self.records['consultation']=[replace(self.item(),detail='Changed topic')]
        with self.assertRaises(DecisionError):self.queue.detail(self.context(),reference)
    def test_partial_failure_is_visible_without_losing_other_items(self):
        self.records['consultation']=[self.item()]
        def broken(*args):raise RuntimeError('secret URL')
        self.queue.sources['review']=broken
        page=self.queue.page(self.context());self.assertTrue(page.partial);self.assertEqual(len(page.items),1)
        self.assertNotIn('secret',str(page.warnings));self.assertIn('review',page.warnings)
    def test_stale_or_incomplete_snapshot_never_claims_no_decisions(self):
        self.queue.sources['review']=lambda *args:DecisionSnapshot((),self.now-dt.timedelta(hours=1))
        self.assertTrue(self.queue.page(self.context()).partial)
        self.queue.sources['review']=lambda *args:DecisionSnapshot((),self.now,complete=False)
        self.assertTrue(self.queue.page(self.context()).partial)
    def test_due_sort_and_today_are_yekaterinburg_not_host_utc(self):
        self.now=dt.datetime(2026,10,29,0,30,tzinfo=dt.timezone(dt.timedelta(hours=5)))
        self.records['consultation']=[replace(self.item(source='future'),due_at=self.now+dt.timedelta(days=1)),replace(self.item(source='today'),due_at=self.now+dt.timedelta(hours=1)),replace(self.item(source='overdue'),due_at=self.now-dt.timedelta(minutes=1))]
        page=self.queue.page(self.context());self.assertEqual(page.day,'2026-10-29')
        self.assertEqual([x.item.source_id for x in page.items],['overdue','today','future'])
    def test_revocation_during_collection_blocks_return(self):
        def revoked(*args):
            self.policy=self.f.policy(bindings=())
            return DecisionSnapshot((self.item(),),self.now)
        self.queue.sources['consultation']=revoked
        with self.assertRaises(DecisionError):self.queue.page(self.context())
    def test_review_scope_rechecked_and_reused_enrollment_not_exposed(self):
        self.records['review']=[self.item('review',enrollment=('enrollment-b','student-b','discipline-b','group-b'))]
        self.assertEqual(self.queue.page(self.context()).counts['review'],0)
        self.records['review']=[self.item('review',enrollment=('enrollment-a','student-b','discipline-a','group-a'))]
        self.assertEqual(self.queue.page(self.context()).counts['review'],0)
    def test_category_filter_and_pagination_are_current(self):
        self.records['consultation']=[self.item(source=f'req-{i}') for i in range(7)]
        self.assertEqual(len(self.queue.page(self.context()).items),5)
        self.assertEqual(len(self.queue.page(self.context(),page=2).items),2)
        self.assertEqual(self.queue.page(self.context(),category='technical').items,())
    def test_conflicting_same_source_records_mark_incomplete(self):
        self.records['consultation']=[self.item(),replace(self.item(),detail='Conflicting copy')]
        page=self.queue.page(self.context());self.assertTrue(page.partial);self.assertEqual(page.items,())

    def test_sources_that_age_out_during_collection_are_not_shown_as_current(self):
        def delayed(context,policy,now):
            original=now;item=self.item();self.now+=dt.timedelta(minutes=10)
            return DecisionSnapshot((item,),original)
        self.queue.sources['consultation']=delayed
        page=self.queue.page(self.context());self.assertTrue(page.partial)
        self.assertEqual(page.items,())
    def test_reference_does_not_change_for_equivalent_timezone_representation(self):
        first=self.item()
        second=replace(first,created_at=first.created_at.astimezone(dt.timezone.utc))
        self.assertEqual(first.reference,second.reference)
