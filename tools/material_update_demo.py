"""Synthetic DOCX update→PPTX review→protected history; no real resources."""
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import zipfile
from material_pipeline import MaterialProvider,ValidatedRubrics
from material_versions import MaterialCatalog
from assignment_review import read_presentation,review_presentation
from review_demo import synthetic_work
from report_access import ReportReader,ReportLink
from assistant_access import AccessPolicy,Student,Binding,Enrollment,Context

class SyntheticSource:
    minimum=3
    def read(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic minimum '+str(self.minimum)+'</w:t></w:r></w:p></w:body></w:document>')
        return stream.getvalue()


def main():
    source=SyntheticSource()
    def synthetic_validator(document):
        # Exact fixed fixture vocabulary only; this is NOT a semantic validator.
        minimum={'Synthetic minimum 3':3,'Synthetic minimum 4':4}[document.paragraphs[0]]
        return ValidatedRubrics(document.source_sha256,document.parser_version,'synthetic-update-validator',document.review_reasons,
            {'makeup-1':{'kind':'lecture_makeup','number':1,'requirements':list(document.paragraphs),
                         'structural_checks':[{'measure':'slide_count','requirement_index':0,'minimum':minimum}]}})
    provider=MaterialProvider(source,validator=synthetic_validator)
    now=dt.datetime(2026,10,30,10,tzinfo=dt.timezone(dt.timedelta(hours=5)))
    policy=AccessPolicy(students=(Student('fixture-student'),),bindings=(Binding('telegram','103','student','fixture-student',frozenset({'progress.self'}),confirmed=True),),enrollments=(Enrollment('fixture-enrollment','fixture-student','fixture-course','fixture-group',now-dt.timedelta(days=1),now+dt.timedelta(days=1)),))
    context=Context('telegram','103',authenticated=True,private=True)
    with tempfile.TemporaryDirectory() as directory, MaterialCatalog(Path(directory)/'catalog.db',namespace='synthetic-update') as catalog:
        evidence=read_presentation(synthetic_work(3))
        old=catalog.prepare('fixture-submission','fixture-material','makeup-1',fetch_current=provider)
        report=review_presentation(old,evidence);assert catalog.finish(old.id,report,fetch_current=provider)=='done'
        link=ReportLink('fixture-report',old.id,'fixture-enrollment','fixture-student','fixture-course','fixture-group')
        reader=ReportReader([link],policy_provider=lambda:policy,load_result=catalog.result,clock=lambda:now,criteria_provider=catalog.criteria_snapshot)
        before=catalog.result(old.id);assert reader.read(link.id,context)['criteria_state']=='catalog_matches'
        source.minimum=4
        new=catalog.prepare('fixture-submission','fixture-material','makeup-1',fetch_current=provider)
        fresh=review_presentation(new,evidence);assert catalog.finish(new.id,fresh,fetch_current=provider)=='done'
        state=reader.read(link.id,context)['criteria_state']
        unchanged=catalog.result(old.id)==before
        assert state=='catalog_changed' and unchanged and report['requirements'][0]['status']=='met' and fresh['requirements'][0]['status']=='not_met'
        print(json.dumps({'mode':'synthetic_offline','old_observation':report['requirements'][0]['status'],
            'new_observation':fresh['requirements'][0]['status'],'old_report_criteria_state':state,'old_report_unchanged':unchanged,
            'new_version_created':new.version!=old.version,'lecture_mapping_preserved':new.lecture_number==1,
            'credit_written':False,'criteria_live_verified':False,'real_messages_sent':0,'real_journal_writes':0},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
