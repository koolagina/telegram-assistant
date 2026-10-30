"""Real local catalog + protected report views; synthetic criteria/submissions."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from material_versions import MaterialCatalog,MaterialRead,MaterialError
from report_access import ReportReader,ReportLink,ReportAccessError
from report_requests import prepare_report_reply
import test_report_access as fixtures

class MaterialFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ReportTests();self.f.setUp()
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'catalog.db'
        self.catalog=MaterialCatalog(self.path,namespace='synthetic-freshness');self.addCleanup(self.catalog.db.close)
        self.current=self.source(1);self.plan=self.catalog.prepare('submission','material','makeup-1',fetch_current=lambda:self.current)
        self.report={'check_id':self.plan.id,'material_version':self.plan.version,'assignment_id':'makeup-1','status':'needs_teacher_review','credit_written':False,'requirements':[{'requirement':'Synthetic requirement','status':'needs_review'}]}
        self.catalog.finish(self.plan.id,self.report,fetch_current=lambda:self.current)
        self.link=replace(self.f.link,check_id=self.plan.id)
    def source(self,n):
        return MaterialRead(('synthetic document '+str(n)).encode(),{'makeup-1':{'kind':'lecture_makeup','number':1,'requirements':['Synthetic requirement '+str(n)]}},'synthetic-parser')
    def reader(self,provider=True):
        kw={'criteria_provider':self.catalog.criteria_snapshot} if provider else {}
        return ReportReader([self.link],policy_provider=lambda:self.f.policy,load_result=self.catalog.result,clock=lambda:fixtures.NOW,**kw)
    def read(self):return self.reader().read(self.link.id,self.f.context('003'),purpose='progress.self')
    def update(self):
        self.current=self.source(2);return self.catalog.prepare('new-submission','material','makeup-1',fetch_current=lambda:self.current)
    def test_completed_report_catalog_match_is_not_live_freshness(self):
        out=self.read();self.assertEqual(out['criteria_state'],'catalog_matches');self.assertFalse(out['criteria_live_verified'])
    def test_update_marks_old_report_without_rewriting_history(self):
        before=self.catalog.result(self.plan.id);self.update()
        self.assertEqual(self.read()['criteria_state'],'catalog_changed');self.assertEqual(self.catalog.result(self.plan.id),before)
    def test_new_report_uses_new_criteria_and_old_stays_old(self):
        new=self.update();self.assertNotEqual(new.version,self.plan.version)
        self.assertEqual(new.lecture_number,1);self.assertEqual(new.rules['requirements'],['Synthetic requirement 2'])
        self.assertEqual(self.read()['criteria_state'],'catalog_changed')
    def test_default_provider_does_not_claim_current(self):
        self.assertEqual(self.reader(provider=False).read(self.link.id,self.f.context('003'))['criteria_state'],'not_checked')
    def test_removed_assignment_is_explicit_not_reused(self):
        changed=replace(self.source(2),rubrics={'makeup-2':{'kind':'lecture_makeup','number':2,'requirements':['Other assignment']}})
        with self.assertRaises(MaterialError):self.catalog.prepare('removed','material','makeup-1',fetch_current=lambda:changed)
        self.assertEqual(self.read()['criteria_state'],'assignment_removed')
    def test_source_failure_no_cached_new_check(self):
        def failed():raise RuntimeError('private URL')
        with self.assertRaises(MaterialError):self.catalog.prepare('other','material','makeup-1',fetch_current=failed)
        self.assertEqual(self.catalog.result(self.plan.id)['result'],self.report)
    def test_provider_failure_labels_unavailable_without_exception_leak(self):
        def failed(check):raise RuntimeError('private material path')
        reader=ReportReader([self.link],policy_provider=lambda:self.f.policy,load_result=self.catalog.result,clock=lambda:fixtures.NOW,criteria_provider=failed)
        out=reader.read(self.link.id,self.f.context('003'));self.assertEqual(out['criteria_state'],'unavailable');self.assertNotIn('private',str(out))
    def test_provider_revoke_during_lookup_blocks_output(self):
        def revoke(check):self.f.policy=self.f.fixture.policy(bindings=());return self.catalog.criteria_snapshot(check)
        reader=ReportReader([self.link],policy_provider=lambda:self.f.policy,load_result=self.catalog.result,clock=lambda:fixtures.NOW,criteria_provider=revoke)
        with self.assertRaises(ReportAccessError):reader.read(self.link.id,self.f.context('003'))
    def test_mismatched_snapshot_does_not_label_foreign_report_current(self):
        snap=self.catalog.criteria_snapshot(self.plan.id)
        reader=ReportReader([self.link],policy_provider=lambda:self.f.policy,load_result=self.catalog.result,clock=lambda:fixtures.NOW,criteria_provider=lambda check:replace(snap,check_id='foreign'))
        with self.assertRaises(ReportAccessError):reader.read(self.link.id,self.f.context('003'))
    def test_report_text_warns_about_updated_material(self):
        self.update();reply=prepare_report_reply(self.reader(),self.f.context('003'),'/progress '+self.link.id)
        self.assertEqual(reply.status,'prepared');self.assertIn('обновлены',reply.text)
    def test_snapshot_read_is_select_only_and_no_changes(self):
        statements=[];self.catalog.db.set_trace_callback(statements.append);before=self.catalog.db.total_changes
        self.catalog.criteria_snapshot(self.plan.id)
        self.assertEqual(self.catalog.db.total_changes,before);self.assertTrue(all(s.startswith('SELECT ') for s in statements))
    def test_unknown_check_is_safe_error(self):
        with self.assertRaises(MaterialError):self.catalog.criteria_snapshot('missing')
    def test_update_during_check_cannot_finish_with_old_rules(self):
        plan=self.catalog.prepare('pending-submission','material','makeup-1',fetch_current=lambda:self.current)
        report={**self.report,'check_id':plan.id,'material_version':plan.version}
        self.current=self.source(2)
        self.assertEqual(self.catalog.finish(plan.id,report,fetch_current=lambda:self.current),'needs_recheck')
        self.assertIsNone(self.catalog.result(plan.id)['result'])
    def test_freshness_survives_catalog_restart(self):
        self.update()
        with MaterialCatalog(self.path,namespace='synthetic-freshness') as reopened:
            reader=ReportReader([self.link],policy_provider=lambda:self.f.policy,load_result=reopened.result,clock=lambda:fixtures.NOW,criteria_provider=reopened.criteria_snapshot)
            self.assertEqual(reader.read(self.link.id,self.f.context('003'))['criteria_state'],'catalog_changed')
    def test_foreign_actor_cannot_probe_criteria_provider(self):
        calls=[]
        def provider(check):calls.append(check);return self.catalog.criteria_snapshot(check)
        reader=ReportReader([self.link],policy_provider=lambda:self.f.policy,load_result=self.catalog.result,clock=lambda:fixtures.NOW,criteria_provider=provider)
        with self.assertRaises(ReportAccessError):reader.read(self.link.id,self.f.context('004'))
        self.assertEqual(calls,[])
    def test_docx_pipeline_pptx_report_update_and_history(self):
        from test_material_pipeline import doc,validated
        from material_pipeline import MaterialProvider
        from assignment_review import read_presentation,review_presentation
        from review_demo import synthetic_work
        class Source:
            content=doc('Synthetic criterion A')
            def read(self):return self.content
        source=Source()
        def synthetic_validator(document):
            result=validated(document)
            rules={**result.rubrics['makeup-1'],'structural_checks':[{'measure':'slide_count','requirement_index':0,'minimum':3}]}
            return replace(result,rubrics={'makeup-1':rules})
        provider=MaterialProvider(source,validator=synthetic_validator)
        plan=self.catalog.prepare('pipeline-submission','pipeline-material','makeup-1',fetch_current=provider)
        evidence=read_presentation(synthetic_work(3));report=review_presentation(plan,evidence)
        self.assertEqual(self.catalog.finish(plan.id,report,fetch_current=provider),'done')
        link=replace(self.link,check_id=plan.id)
        reader=ReportReader([link],policy_provider=lambda:self.f.policy,load_result=self.catalog.result,clock=lambda:fixtures.NOW,criteria_provider=self.catalog.criteria_snapshot)
        self.assertEqual(reader.read(link.id,self.f.context('003'))['criteria_state'],'catalog_matches')
        before=self.catalog.result(plan.id)
        source.content=doc('Synthetic criterion B')
        new=self.catalog.prepare('pipeline-submission','pipeline-material','makeup-1',fetch_current=provider)
        self.assertNotEqual(new.version,plan.version);self.assertEqual(new.lecture_number,1)
        self.assertEqual(reader.read(link.id,self.f.context('003'))['criteria_state'],'catalog_changed')
        self.assertEqual(self.catalog.result(plan.id),before)
