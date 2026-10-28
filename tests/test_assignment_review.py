"""Synthetic local pilot: structural observations, never grade/credit."""
import io
from pathlib import Path
import sys
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assignment_review import read_presentation, review_presentation, ReviewError
from material_versions import CheckPlan, encoded

P='http://schemas.openxmlformats.org/presentationml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
def deck(count,hidden=False):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'+''.join(f'<p:sldId id="{256+i}" r:id="rId{i}"/>' for i in range(count))+'</p:sldIdLst></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels',f'<Relationships xmlns="{PKG}">'+''.join(f'<Relationship Id="rId{i}" Type="{R}/slide" Target="slides/slide{i}.xml"/>' for i in range(count))+'</Relationships>')
        for i in range(count):
            show=' show="0"' if hidden and i==0 else ''
            z.writestr(f'ppt/slides/slide{i}.xml',f'<p:sld xmlns:p="{P}" xmlns:a="{A}"{show}><p:cSld><a:t>Slide {i}</a:t></p:cSld></p:sld>')
    return stream.getvalue()

def plan():
    return CheckPlan('check-1','version-1','material-1','makeup-3',encoded({'kind':'lecture_makeup','number':3,'requirements':['At least 40 slides','Original diagrams and conclusions']}))

class ReviewTests(unittest.TestCase):
    def test_count_and_exact_slide_evidence(self):
        evidence=read_presentation(deck(40))
        self.assertEqual(evidence.slide_count,40)
        self.assertEqual(evidence.slides[0].text,'Slide 0')
        self.assertEqual(evidence.slides[0].part,'ppt/slides/slide0.xml')
    def test_threshold_boundary_and_missing_content_not_invented(self):
        for count,status in [(39,'not_met'),(40,'met'),(41,'met')]:
            report=review_presentation(plan(),read_presentation(deck(count)),slide_requirement_index=0,minimum_slides=40)
            self.assertEqual(report['requirements'][0]['status'],status)
            self.assertEqual(report['requirements'][1]['status'],'needs_review')
            self.assertEqual(report['status'],'needs_teacher_review')
            self.assertFalse(report['credit_written'])
            self.assertNotIn('grade',report)
    def test_hidden_slides_do_not_produce_automatic_met(self):
        report=review_presentation(plan(),read_presentation(deck(40,hidden=True)),slide_requirement_index=0,minimum_slides=40)
        self.assertEqual(report['requirements'][0]['status'],'needs_review')
    def test_configuration_must_be_explicit_and_valid(self):
        for index,minimum in [(True,40),(2,40),(0,0),(0,True)]:
            with self.assertRaises(ReviewError):review_presentation(plan(),read_presentation(deck(1)),slide_requirement_index=index,minimum_slides=minimum)
    def test_broken_package_and_no_slides_rejected(self):
        for content in [b'bad',deck(0)]:
            with self.assertRaises(ReviewError):read_presentation(content)
    def test_changed_work_is_bound_to_new_hash(self):
        self.assertNotEqual(read_presentation(deck(39)).sha256,read_presentation(deck(40)).sha256)
    def test_report_carries_check_and_source_versions(self):
        evidence=read_presentation(deck(40))
        report=review_presentation(plan(),evidence,slide_requirement_index=0,minimum_slides=40)
        self.assertEqual(report['check_id'],'check-1');self.assertEqual(report['material_version'],'version-1')
        self.assertEqual(report['submission_sha256'],evidence.sha256)
    def test_slide_text_never_becomes_instruction(self):
        evidence=read_presentation(deck(1))
        self.assertTrue(evidence.requires_content_review)


def rewrite(content,name,transform):
    output=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source,zipfile.ZipFile(output,'w') as target:
        for part in source.namelist():
            data=source.read(part)
            target.writestr(part,transform(data) if part==name else data)
    return output.getvalue()

class PackageSafetyTests(unittest.TestCase):
    def test_external_slide_and_traversal_refused(self):
        for edit in [lambda b:b.replace(b'Target="slides/',b'TargetMode="External" Target="slides/'),lambda b:b.replace(b'slides/slide0.xml',b'slides/../slide0.xml')]:
            with self.assertRaises(ReviewError):read_presentation(rewrite(deck(1),'ppt/_rels/presentation.xml.rels',edit))
    def test_duplicate_slide_target_refused(self):
        with self.assertRaises(ReviewError):read_presentation(rewrite(deck(2),'ppt/_rels/presentation.xml.rels',lambda b:b.replace(b'slide1.xml',b'slide0.xml')))
    def test_dtd_in_slide_refused(self):
        with self.assertRaises(ReviewError):read_presentation(rewrite(deck(1),'ppt/slides/slide0.xml',lambda b:b'<!DOCTYPE x [<!ENTITY y "z">]>'+b))
    def test_archive_expansion_limit(self):
        from unittest.mock import patch
        with patch('assignment_review.MAX_EXPANDED',10):
            with self.assertRaises(ReviewError):read_presentation(deck(1))
    def test_saved_report_still_requires_teacher_review(self):
        import tempfile
        from material_versions import MaterialCatalog,MaterialRead
        with tempfile.TemporaryDirectory() as directory:
            with MaterialCatalog(Path(directory)/'state.db',namespace='synthetic') as catalog:
                source=lambda:MaterialRead(b'synthetic rules',{'makeup-3':plan().rules},'review-test-1')
                current=catalog.prepare('submission-revision-1','material-1','makeup-3',fetch_current=source)
                report=review_presentation(current,read_presentation(deck(40)),slide_requirement_index=0,minimum_slides=40)
                self.assertEqual(catalog.finish(current.id,report,fetch_current=source),'done')
                self.assertEqual(catalog.result(current.id)['result']['status'],'needs_teacher_review')
    def test_configuration_in_result_and_evaluation_identity(self):
        evidence=read_presentation(deck(40))
        first=review_presentation(plan(),evidence,slide_requirement_index=0,minimum_slides=40)
        second=review_presentation(plan(),evidence,slide_requirement_index=0,minimum_slides=41)
        self.assertNotEqual(first['evaluation_key'],second['evaluation_key'])
        self.assertEqual(first['configuration']['minimum_slides'],40)
