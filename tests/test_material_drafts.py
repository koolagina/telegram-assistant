"""Source-grounded drafts: never approved grades/rubrics."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from material_drafts import draft_assignments, DraftError
from material_docx import extract_docx
from test_material_pipeline import doc

class DraftTests(unittest.TestCase):
    def extract(self,text):return extract_docx(doc(text))
    def test_numbered_sections_preserve_exact_text_and_intro(self):
        from dataclasses import replace
        source=replace(self.extract('unused'),paragraphs=('Old global policy','ДЗ №1','30 questions','40% coverage','ДЗ №2','10 frames'))
        result=draft_assignments(source,kind='lecture_makeup',expected_numbers=(1,2))
        self.assertEqual(result.introduction,('Old global policy',))
        self.assertEqual(result.assignments[0].requirements,('30 questions','40% coverage'))
        self.assertEqual(result.assignments[1].number,2)
        self.assertEqual(result.assignments[0].paragraph_indices,(2,3))
        self.assertEqual(result.source_sha256,source.source_sha256)
        self.assertTrue(result.requires_review)
    def test_missing_duplicate_out_of_order_refused(self):
        from dataclasses import replace
        for paragraphs in [('ДЗ №1','x'),('ДЗ №1','x','ДЗ №1','y'),('ДЗ №2','x','ДЗ №1','y')]:
            source=replace(self.extract('unused'),paragraphs=paragraphs)
            with self.assertRaises(DraftError):draft_assignments(source,kind='lecture_makeup',expected_numbers=(1,2))
    def test_no_guess_from_embedded_mention(self):
        with self.assertRaises(DraftError):draft_assignments(self.extract('Read ДЗ №1 then ДЗ №2'),kind='practice',expected_numbers=(1,2))
    def test_empty_section_and_tables_stop(self):
        from dataclasses import replace
        for source in [self.extract('ДЗ №1'),replace(self.extract('ДЗ №1'),tables=((('hidden criteria',),),))]:
            with self.assertRaises(DraftError):draft_assignments(source,kind='lecture_makeup',expected_numbers=(1,))
    def test_no_threshold_or_approval_inferred(self):
        from dataclasses import replace
        source=replace(self.extract('unused'),paragraphs=('Домашнее задание № 1: Тест','30 вопросов; веса 40/30/30'))
        result=draft_assignments(source,kind='lecture_makeup',expected_numbers=(1,))
        self.assertEqual(result.assignments[0].heading,'Домашнее задание № 1: Тест')
        self.assertFalse(hasattr(result,'pass_threshold'))
        self.assertFalse(hasattr(result,'rubrics'))
