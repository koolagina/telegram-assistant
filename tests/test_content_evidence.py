"""Synthetic evidence validation, not automated scientific grading."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from content_evidence import Citation,Finding,review_with_findings
from assignment_review import read_presentation,ReviewError
from test_assignment_review import deck,plan

class ContentTests(unittest.TestCase):
    def setUp(self):self.work=read_presentation(deck(40));self.plan=plan()
    def finding(self,**changes):
        base=Finding(self.plan.id,self.plan.version,self.work.sha256,1,'uncertain','Synthetic observation',(Citation('ppt/slides/slide0.xml',0,7,'Slide 0'),))
        return replace(base,**changes)
    def review(self,findings):return review_with_findings(self.plan,self.work,findings,reviewer_version='synthetic-reviewer-1')
    def test_exact_quote_attached_without_auto_acceptance(self):
        report=self.review([self.finding()])
        observation=report['requirements'][1]['content_observation']
        self.assertEqual(observation['citations'][0]['quote'],'Slide 0')
        self.assertEqual(report['requirements'][1]['status'],'needs_review')
        self.assertEqual(report['status'],'needs_teacher_review')
        self.assertFalse(report['credit_written'])
    def test_fabricated_quote_offset_or_part_refused(self):
        for citation in [Citation('ppt/slides/slide0.xml',0,7,'fiction'),Citation('ppt/slides/slide0.xml',1,7,'Slide 0'),Citation('missing.xml',0,7,'Slide 0'),Citation('ppt/slides/slide0.xml',False,7,'Slide 0')]:
            with self.assertRaises(ReviewError):self.review([self.finding(citations=(citation,))])
    def test_changed_work_or_criteria_cannot_reuse_observation(self):
        for change in [dict(check_id='other'),dict(material_version='old'),dict(submission_sha256='0'*64)]:
            with self.assertRaises(ReviewError):self.review([self.finding(**change)])
    def test_ambiguous_and_out_of_scope_findings_refused(self):
        for findings in [[self.finding(),self.finding()],[self.finding(requirement_index=2)],[self.finding(requirement_index=True)]]:
            with self.assertRaises(ReviewError):self.review(findings)
    def test_supported_or_contradicted_requires_evidence(self):
        for stance in ['supported','contradicted']:
            with self.assertRaises(ReviewError):self.review([self.finding(stance=stance,citations=())])
        self.assertEqual(self.review([self.finding(citations=())])['status'],'needs_teacher_review')
    def test_observation_never_changes_structural_status_or_infers_grade(self):
        report=self.review([self.finding(requirement_index=0,stance='contradicted')])
        self.assertEqual(report['requirements'][0]['status'],'met')
        self.assertEqual(report['status'],'needs_teacher_review')
        self.assertNotIn('grade',report)
    def test_versioned_identity_includes_findings(self):
        one=self.review([self.finding()]);two=self.review([self.finding(comment='Other synthetic observation')])
        self.assertNotEqual(one['evaluation_key'],two['evaluation_key'])

    def test_order_of_observations_does_not_change_retry_result(self):
        first=self.finding(requirement_index=0);second=self.finding()
        self.assertEqual(self.review([first,second]),self.review([second,first]))
    def test_saved_local_observation_is_not_an_accepted_work(self):
        import tempfile
        from material_versions import MaterialCatalog,MaterialRead
        with tempfile.TemporaryDirectory() as directory:
            with MaterialCatalog(Path(directory)/'state.db',namespace='synthetic') as catalog:
                source=lambda:MaterialRead(b'synthetic rubric',{'makeup-3':self.plan.rules},'test-review-1')
                current=catalog.prepare('submission-revision-1','material-1','makeup-3',fetch_current=source)
                observation=self.finding(check_id=current.id,material_version=current.version)
                report=review_with_findings(current,self.work,[observation],reviewer_version='test-reviewer-1')
                self.assertEqual(catalog.finish(current.id,report,fetch_current=source),'done')
                saved=catalog.result(current.id)['result']
                self.assertEqual(saved['status'],'needs_teacher_review')
                self.assertEqual(saved['requirements'][1]['content_observation']['status'],'needs_review')
