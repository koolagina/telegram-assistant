"""Offline download→Word→trusted validation→version history integration."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from material_pipeline import MaterialProvider, ValidatedRubrics
from material_versions import MaterialCatalog, MaterialError
from material_source import PublicMaterialSource
from test_material_source import Transport


def doc(text):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+text+'</w:t></w:r></w:p></w:body></w:document>')
    return stream.getvalue()

def validated(document):
    return ValidatedRubrics(document.source_sha256,document.parser_version,'test-validator-1',document.review_reasons,
        {'makeup-1':{'kind':'lecture_makeup','number':1,'requirements':list(document.paragraphs)}})

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.t=Transport();self.t.data=doc('30 questions')
        self.source=PublicMaterialSource('https://disk.yandex.ru/d/synthetic','/assignment.docx',transport=self.t)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.catalog=MaterialCatalog(Path(self.temp.name)/'state.db',namespace='test-project')
        self.addCleanup(self.catalog.db.close)
    def provider(self,validator=validated):return MaterialProvider(self.source,validator=validator)
    def prepare(self,provider):return self.catalog.prepare('submission-1','material-1','makeup-1',fetch_current=provider)
    def test_full_pipeline_fresh_update_and_recheck(self):
        provider=self.provider();old=self.prepare(provider)
        self.assertEqual(old.rules['requirements'],['30 questions']);self.assertEqual(old.lecture_number,1)
        self.t.data=doc('40 questions')
        self.assertEqual(self.catalog.finish(old.id,{'review':'synthetic'},fetch_current=provider),'needs_recheck')
        new=self.prepare(provider);self.assertNotEqual(new.version,old.version)
        self.assertEqual(new.rules['requirements'],['40 questions'])
        self.assertEqual(self.catalog.finish(new.id,{'review':'synthetic'},fetch_current=provider),'done')
    def test_completed_history_survives_updates(self):
        provider=self.provider();old=self.prepare(provider)
        self.catalog.finish(old.id,{'review':'old criteria'},fetch_current=provider)
        self.t.data=doc('new criteria');self.prepare(provider)
        self.assertEqual(self.catalog.result(old.id)['result'],{'review':'old criteria'})
    def test_stale_validation_cannot_attach_to_changed_document(self):
        result=validated(__import__('material_docx').extract_docx(self.t.data))
        self.t.data=doc('changed')
        with self.assertRaises(MaterialError):self.prepare(self.provider(lambda _:result))
    def test_all_review_flags_must_be_resolved(self):
        from dataclasses import replace
        with self.assertRaises(MaterialError):self.prepare(self.provider(lambda d:replace(validated(d),resolved_reasons=())))
    def test_parser_and_validator_versions_are_bound(self):
        from dataclasses import replace
        with self.assertRaises(MaterialError):self.prepare(self.provider(lambda d:replace(validated(d),parser_version='wrong')))
        first=self.prepare(self.provider())
        second=self.prepare(self.provider(lambda d:replace(validated(d),validator_version='test-validator-2')))
        self.assertNotEqual(first.version,second.version)
    def test_errors_never_fall_back_or_expose_source(self):
        provider=self.provider();old=self.prepare(provider);self.t.fail=True
        with self.assertRaises(MaterialError) as caught:self.catalog.finish(old.id,{'review':'x'},fetch_current=provider)
        self.assertNotIn('sensitive',str(caught.exception));self.assertEqual(self.catalog.result(old.id)['status'],'pending')
    def test_bad_docx_stops_before_validator(self):
        self.t.data=b'bad archive';calls=[]
        with self.assertRaises(MaterialError):self.prepare(self.provider(lambda d:calls.append(d)))
        self.assertEqual(calls,[])
    def test_invalid_rubric_is_not_persisted(self):
        from dataclasses import replace
        with self.assertRaises(MaterialError):self.prepare(self.provider(lambda d:replace(validated(d),rubrics={'makeup-1':{}})))
        self.assertEqual(self.catalog.db.execute('SELECT count(*) FROM checks').fetchone()[0],0)

    def test_validator_failure_sanitized_and_pending_not_completed(self):
        old=self.prepare(self.provider())
        def failed(_):raise RuntimeError('private student data and signed URL')
        with self.assertRaises(MaterialError) as caught:
            self.catalog.finish(old.id,{'review':'x'},fetch_current=self.provider(failed))
        self.assertNotIn('private',str(caught.exception))
        self.assertEqual(self.catalog.result(old.id)['status'],'pending')
    def test_no_default_validator_or_plain_dict_approval(self):
        with self.assertRaises(MaterialError):MaterialProvider(self.source,validator=None)
        with self.assertRaises(MaterialError):self.prepare(self.provider(lambda _: {'approved':True}))
