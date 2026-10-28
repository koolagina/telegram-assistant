"""Read-only projections from normalized consultation, review and ledger data."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import datetime as dt
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from decision_sources import ConsultationRecord,ConsultationBatch,ConsultationSource,ReviewSource,DispatchSource
from report_registry import ReportLink
from report_dispatch import DispatchLedger
import test_assistant_access as fixtures

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PolicyTests();self.f.setUp();self.policy=self.f.policy();self.now=fixtures.NOW
        self.context=self.f.context();self.owner='teacher-a'
    def call(self,source):return source(self.context,self.policy,self.now)
    def consultation(self,status='Ожидает решения'):
        return ConsultationRecord('request-a',status,self.now,self.now,'Synthetic student','Synthetic topic')
    def test_pending_consultations_only_and_source_not_modified(self):
        records=(self.consultation(),replace(self.consultation('Подтверждена'),id='request-b'),replace(self.consultation('Отменена'),id='request-c'))
        snapshot=self.call(ConsultationSource(self.owner,lambda:ConsultationBatch(records,self.now)))
        self.assertEqual(len(snapshot.items),1);self.assertEqual(snapshot.items[0].due_at,self.now)
        self.assertEqual(records[0].status,'Ожидает решения')
    def test_unknown_consultation_status_requires_source_review(self):
        with self.assertRaises(ValueError):self.call(ConsultationSource(self.owner,lambda:ConsultationBatch((self.consultation('Invented status'),),self.now)))
    def test_naive_consultation_time_not_guessed(self):
        with self.assertRaises(ValueError):self.call(ConsultationSource(self.owner,lambda:ConsultationBatch((replace(self.consultation(),starts_at=self.now.replace(tzinfo=None)),),self.now)))
    def links(self):return (ReportLink('report-a','check-a','enrollment-a','student-a','discipline-a','group-a'),ReportLink('report-b','check-b','enrollment-b','student-b','discipline-b','group-b'))
    def row(self,check):return {'status':'done','version':'v1','result':{'check_id':check,'material_version':'v1','assignment_id':'makeup-3','status':'needs_teacher_review','credit_written':False,'requirements':[{'status':'not_met','requirement':'40 slides'}]}}
    def test_review_permission_checked_before_payload_load(self):
        calls=[]
        source=ReviewSource(self.owner,self.links,lambda check:(calls.append(check) or self.row(check)))
        result=self.call(source)
        self.assertEqual(calls,['check-a']);self.assertEqual(len(result.items),1)
        self.assertIn('не выполнен',result.items[0].detail)
    def test_completed_or_pending_review_not_false_decision(self):
        source=ReviewSource(self.owner,lambda:self.links()[:1],lambda _: {'status':'pending','result':None})
        self.assertEqual(self.call(source).items,())
    def test_reused_enrollment_owner_is_not_read(self):
        calls=[];link=replace(self.links()[0],student_id='student-b')
        source=ReviewSource(self.owner,lambda:(link,),lambda check:calls.append(check))
        self.assertEqual(self.call(source).items,());self.assertEqual(calls,[])
    def test_needs_recheck_appears_without_changing_check_state(self):
        row={'status':'needs_recheck','version':'old','result':None}
        result=self.call(ReviewSource(self.owner,lambda:self.links()[:1],lambda _:row))
        self.assertEqual(len(result.items),1);self.assertEqual(row['status'],'needs_recheck')
    def test_dispatch_attention_only_uncertain_or_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with DispatchLedger(Path(directory)/'dispatch.sqlite3',namespace='synthetic',bot_id=9001) as ledger:
                for number,phase in enumerate(['unknown','sending','api_rejected','api_confirmed','cancelled']):
                    ledger.db.execute('INSERT INTO dispatch_attempts VALUES(?,?,?,?,?,?)',(number,'attempt',phase,'hash',None,429 if phase=='api_rejected' else None))
                result=self.call(DispatchSource(self.owner,ledger.attention))
                self.assertEqual(len(result.items),2)
                self.assertEqual(ledger.result(0)['status'],'unknown')

    def test_conflicting_consultation_copies_not_chosen_arbitrarily(self):
        with self.assertRaises(ValueError):self.call(ConsultationSource(self.owner,lambda:ConsultationBatch((self.consultation(),self.consultation('Подтверждена')),self.now)))

    def test_inflight_is_not_a_human_decision_without_orphan_confirmation(self):
        row={'update_id':1,'status':'inflight_or_unknown','api_error_code':None}
        source=DispatchSource(self.owner,lambda:(row,))
        self.assertEqual(self.call(source).items,())
        row['review_required']=True
        self.assertEqual(len(self.call(source).items),1)

    def test_consultation_snapshot_preserves_true_observation_time_not_click_time(self):
        observed=self.now-dt.timedelta(minutes=10)
        source=ConsultationSource(self.owner,lambda:ConsultationBatch((self.consultation(),),observed,complete=False))
        result=self.call(source)
        self.assertEqual(result.observed_at,observed);self.assertFalse(result.complete)
        with self.assertRaises(ValueError):self.call(ConsultationSource(self.owner,lambda:(self.consultation(),)))
