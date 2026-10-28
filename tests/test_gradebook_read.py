"""Synthetic XLSX only. No student records, credentials or network access."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from gradebook_read import WorkbookError, read_workbook, main

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def fixture(path, cells='', *, date1904=False, target='worksheets/unusual.xml',
            mode='', merges='', extra=None, styles=None):
    parts = {
        'xl/workbook.xml': f'''<workbook xmlns="{NS}"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
          <workbookPr date1904="{int(date1904)}"/>
          <sheets><sheet name="Do not infer group here" sheetId="17" r:id="rId7"/></sheets>
          </workbook>''',
        'xl/_rels/workbook.xml.rels': f'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId7" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
          Target="{target}" {mode}/></Relationships>''',
        'xl/worksheets/unusual.xml': f'''<worksheet xmlns="{NS}"><cols><col min="29" max="32" hidden="1"/></cols>
          <sheetData>{cells}</sheetData>{merges}</worksheet>''',
        'xl/styles.xml': styles or f'''<styleSheet xmlns="{NS}"><numFmts count="1">
          <numFmt numFmtId="161" formatCode="dd.mm.yyyy"/></numFmts><cellXfs count="2">
          <xf numFmtId="0"/><xf numFmtId="161"/></cellXfs></styleSheet>''',
    }
    parts.update(extra or {})
    with ZipFile(path, 'w') as archive:
        for name, value in parts.items():
            archive.writestr(name, value)


def inline(ref, text):
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic.xlsx'

    def test_relationship_target_and_no_mutation(self):
        fixture(self.path, '<row r="4">' + inline('B4', 'Synthetic Person') + '</row>')
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        book = read_workbook(self.path)
        self.assertEqual(book.sheets[0].part, 'xl/worksheets/unusual.xml')
        self.assertEqual(book.sheets[0].cell('B4').value, 'Synthetic Person')
        self.assertEqual(book.sha256, before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_multiple_group_candidates_not_sheet_name(self):
        fixture(self.path, '<row r="3">' + inline('B3', '9001') + '</row>'
                '<row r="4">' + inline('B4', 'Synthetic Person') + '</row>'
                '<row r="12">' + inline('B12', '9002') + '</row>')
        sheet = read_workbook(self.path).sheets[0]
        self.assertEqual(sheet.layout()['group_candidate_cells'], ['B3', 'B12'])
        self.assertNotIn('student_id', sheet.layout())

    def test_merged_cell_resolves_anchor_without_copying_student_rows(self):
        fixture(self.path, '<row r="3">' + inline('B3', '9001') + '</row>',
                merges='<mergeCells><mergeCell ref="B3:B5"/></mergeCells>')
        sheet = read_workbook(self.path).sheets[0]
        self.assertEqual(sheet.cell('B5').ref, 'B3')
        self.assertEqual(sheet.layout()['group_candidate_cells'], ['B3'])
        self.assertIsNone(sheet.cell('C5'))

    def test_formula_cache_missing_is_not_zero_and_shared_origin_is_preserved(self):
        fixture(self.path, '''<row r="4"><c r="AA4"><f t="shared" si="0" ref="AA4:AA6">SUM(C4:T4)</f><v>57</v></c></row>
          <row r="5"><c r="AA5"><f t="shared" si="0"/><v/></c></row>
          <row r="6"><c r="AA6"><f t="shared" si="0"/><v>0</v></c></row>''')
        sheet = read_workbook(self.path).sheets[0]
        missing = sheet.cell('AA5')
        self.assertTrue(missing.is_formula)
        self.assertIsNone(missing.value)
        self.assertFalse(missing.cache_present)
        self.assertEqual(missing.formula_origin, 'AA4')
        self.assertIsNone(missing.formula)  # Never claim base expression is translated.
        self.assertEqual(sheet.cell('AA6').value, 0)
        self.assertTrue(sheet.cell('AA6').cache_present)

    def test_shared_and_inline_strings_and_error_are_distinct(self):
        fixture(self.path, '''<row r="4"><c r="B4" t="s"><v>0</v></c>'''
                + inline('C4', '*') + '''<c r="D4" t="e"><f>1/0</f><v>#DIV/0!</v></c></row>''',
                extra={'xl/sharedStrings.xml': f'<sst xmlns="{NS}"><si><r><t>Synthetic </t></r><r><t>Person</t></r></si></sst>'})
        sheet = read_workbook(self.path).sheets[0]
        self.assertEqual(sheet.cell('B4').value, 'Synthetic Person')
        self.assertEqual(sheet.cell('C4').value, '*')
        self.assertEqual(sheet.cell('D4').kind, 'error')

    def test_dates_both_epochs_and_fictitious_leap_day(self):
        fixture(self.path, '<row r="1"><c r="C1" s="1"><v>45917</v></c></row>')
        self.assertEqual(read_workbook(self.path).sheets[0].cell('C1').value.isoformat(), '2025-09-17T00:00:00')
        fixture(self.path, '<row r="1"><c r="C1" s="1"><v>0</v></c></row>', date1904=True)
        self.assertEqual(read_workbook(self.path).sheets[0].cell('C1').value.isoformat(), '1904-01-01T00:00:00')
        fixture(self.path, '<row r="1"><c r="C1" s="1"><v>60</v></c></row>')
        cell = read_workbook(self.path).sheets[0].cell('C1')
        self.assertEqual(cell.kind, 'invalid_date')
        self.assertIn('invalid_date', read_workbook(self.path).summary()['warnings'])

    def test_layout_finds_actual_total_column_and_hidden_helpers(self):
        fixture(self.path, '<row r="1">' + inline('Y1', 'Общий балл') + inline('Z1', 'Волшебство')
                + inline('U1', 'Лекции') + '</row><row r="3">'
                + inline('C3', 'А') + inline('D3', 'Т') + inline('E3', 'ДЗ') + '</row>')
        sheet = read_workbook(self.path).sheets[0]
        self.assertEqual(sheet.layout()['total_headers'], ['Y1'])
        self.assertEqual(sheet.layout()['practice_triplets'], [['C3', 'D3', 'E3']])
        self.assertEqual(sheet.hidden_columns, [(29, 32)])

    def test_safe_summary_and_cli_do_not_disclose_values_or_sheet_names(self):
        fixture(self.path, '<row r="4">' + inline('B4', 'Synthetic Person')
                + '<c r="D4"><v>9</v></c></row>')
        book = read_workbook(self.path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main([str(self.path)]), 0)
        for serialized in (json.dumps(book.summary()), output.getvalue(), repr(book), repr(book.sheets[0]), repr(book.sheets[0].cell('B4'))):
            self.assertNotIn('Synthetic Person', serialized)
            self.assertNotIn('Do not infer group here', serialized)
        self.assertEqual(json.loads(output.getvalue())['sheet_count'], 1)

    def test_external_or_traversing_relationship_is_rejected(self):
        for target, mode in [('https://example.invalid/file', 'TargetMode="External"'), ('../../outside.xml', '')]:
            fixture(self.path, target=target, mode=mode)
            with self.assertRaises(WorkbookError):
                read_workbook(self.path)

    def test_dtd_duplicate_coordinates_and_missing_shared_origin_fail_closed(self):
        fixtures = [
            {'extra': {'xl/workbook.xml': '<!DOCTYPE x [<!ENTITY e "x">]><x>&e;</x>'}},
            {'cells': '<row r="4">' + inline('B4', 'one') + inline('B4', 'two') + '</row>'},
            {'cells': '<row r="4"><c r="AA4"><f t="shared" si="99"/><v>1</v></c></row>'},
        ]
        for kwargs in fixtures:
            fixture(self.path, **kwargs)
            with self.assertRaises(WorkbookError):
                read_workbook(self.path)

    def test_size_limits_and_invalid_shared_string_are_rejected(self):
        fixture(self.path, '<row r="4"><c r="B4" t="s"><v>99</v></c></row>')
        with self.assertRaises(WorkbookError):
            read_workbook(self.path)
        fixture(self.path)
        with self.assertRaises(WorkbookError):
            read_workbook(self.path, max_uncompressed=10)

    def test_overlap_merges_and_nonfinite_numbers_rejected(self):
        fixture(self.path, merges='<mergeCells><mergeCell ref="B3:C5"/><mergeCell ref="C4:D6"/></mergeCells>')
        with self.assertRaises(WorkbookError):
            read_workbook(self.path)
        fixture(self.path, '<row r="4"><c r="D4"><v>NaN</v></c></row>')
        with self.assertRaises(WorkbookError):
            read_workbook(self.path)

    def test_excel_leap_boundary_and_fractional_day(self):
        for serial, expected in [(1, '1900-01-01T00:00:00'),
                                 (59, '1900-02-28T00:00:00'),
                                 (61.5, '1900-03-01T12:00:00')]:
            fixture(self.path, f'<row r="1"><c r="C1" s="1"><v>{serial}</v></c></row>')
            self.assertEqual(read_workbook(self.path).sheets[0].cell('C1').value.isoformat(), expected)

    def test_unknown_empty_cell_type_is_not_silently_accepted(self):
        fixture(self.path, '<row r="4"><c r="D4" t="unknown"/></row>')
        with self.assertRaises(WorkbookError):
            read_workbook(self.path)

    def test_merge_does_not_hide_conflicting_real_cell_content(self):
        fixture(self.path, '<row r="3">' + inline('B3', '9001') + '</row>'
                '<row r="4">' + inline('B4', 'Synthetic Person') + '</row>',
                merges='<mergeCells><mergeCell ref="B3:B5"/></mergeCells>')
        with self.assertRaises(WorkbookError):
            read_workbook(self.path)

    def test_unvalidated_sheet_state_cannot_leak_into_safe_summary(self):
        fixture(self.path)
        with ZipFile(self.path) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        parts['xl/workbook.xml'] = parts['xl/workbook.xml'].replace(b'sheetId="17"', b'state="Synthetic Person" sheetId="17"')
        with ZipFile(self.path, 'w') as archive:
            for name, value in parts.items():
                archive.writestr(name, value)
        with self.assertRaises(WorkbookError):
            read_workbook(self.path)


if __name__ == '__main__':
    unittest.main()
