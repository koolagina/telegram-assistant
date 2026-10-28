"""Draft machine criterion candidates grounded in exact source paragraphs."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from material_criteria import suggest_slide_criterion, CriterionError
from material_drafts import draft_assignments
from material_docx import extract_docx
from test_material_pipeline import doc

def draft(*requirements):
    source=replace(extract_docx(doc('unused')),paragraphs=('ДЗ №3',)+requirements)
    return draft_assignments(source,kind='lecture_makeup',expected_numbers=(3,))

class CriterionTests(unittest.TestCase):
    def test_explicit_minimum_with_verbatim_evidence(self):
        source=draft('Структура курса','Объём: не менее 40 слайдов.','Авторские схемы')
        suggestion=suggest_slide_criterion(source,assignment_number=3)
        self.assertEqual(suggestion.minimum,40)
        self.assertEqual(suggestion.requirement_index,1)
        self.assertEqual(suggestion.paragraph_index,2)
        self.assertEqual(suggestion.quote,'Объём: не менее 40 слайдов.')
        self.assertEqual(suggestion.source_sha256,source.source_sha256)
        self.assertTrue(suggestion.requires_review)
    def test_updates_are_read_from_new_source(self):
        for number in [40,45]:
            result=suggest_slide_criterion(draft(f'Минимум {number} слайдов'),assignment_number=3)
            self.assertEqual(result.minimum,number)
    def test_ambiguous_or_missing_no_heuristic(self):
        for requirements in [('Сделайте 40 слайдов',),('Минимум 40 слайдов','Не менее 45 слайдов'),('Не менее 10 кадров',),('Минимум 0 слайдов',)]:
            with self.assertRaises(CriterionError):suggest_slide_criterion(draft(*requirements),assignment_number=3)
    def test_negation_conditional_and_reference_require_review(self):
        for text in ['Не требуется минимум 40 слайдов','Например: минимум 40 слайдов','Если очно, минимум 40 слайдов']:
            with self.assertRaises(CriterionError):suggest_slide_criterion(draft(text),assignment_number=3)
    def test_unknown_assignment_and_bool_rejected(self):
        for number in [1,True]:
            with self.assertRaises(CriterionError):suggest_slide_criterion(draft('Минимум 40 слайдов'),assignment_number=number)

    def test_explicit_final_sentence_after_assignment_description(self):
        text='Создайте авторскую презентацию. Минимальный объем — 40 слайдов.'
        result=suggest_slide_criterion(draft(text),assignment_number=3)
        self.assertEqual(result.minimum,40)
        self.assertEqual(result.quote,text)
