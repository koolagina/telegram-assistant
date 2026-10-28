"""Local, read-only XLSX reader. No network, formula execution or save/upload API.

Raw cells can contain personal data: keep the returned objects private. The CLI
prints structural counts and coordinates only, never names, grades or sheet names.
This is not a student identity resolver or an assessment engine.
"""
import argparse
from dataclasses import dataclass, field
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
N = {'m': NS}
MAX_FILE = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024


class WorkbookError(ValueError):
    """Messages never include cell values, filenames, URLs or XML content."""


def position(ref):
    match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', ref or '')
    if not match:
        raise WorkbookError('Invalid cell coordinate')
    col = 0
    for char in match[1]:
        col = col * 26 + ord(char) - 64
    row = int(match[2])
    if col > 16384 or row > 1048576:
        raise WorkbookError('Coordinate outside XLSX bounds')
    return row, col


def rectangle(ref):
    parts = ref.split(':')
    if len(parts) not in (1, 2):
        raise WorkbookError('Invalid cell range')
    a, b = position(parts[0]), position(parts[-1])
    if a[0] > b[0] or a[1] > b[1]:
        raise WorkbookError('Reversed cell range')
    return a, b


def contains(bounds, point):
    a, b = bounds
    return a[0] <= point[0] <= b[0] and a[1] <= point[1] <= b[1]


def rich_text(element):
    return ''.join(t.text or '' for query in ('m:t', 'm:r/m:t') for t in element.findall(query, N))


def date_style(numfmt, formats):
    if numfmt in set(range(14, 23)) | set(range(27, 37)) | set(range(50, 59)):
        return True
    code = formats.get(numfmt, '')
    # Ignore quoted/escaped literals, colours, conditions and elapsed-time fields.
    if re.search(r'\[[hms]+\]', code, re.I):
        return False
    code = re.sub(r'"[^"]*"|\\.|\[[^]]*\]|_.|\*.', '', code)
    return bool(re.search(r'[ymdhis]', code, re.I))


def excel_date(number, date1904):
    if number < 0 or (not date1904 and int(number) == 60):
        raise ValueError('Invalid Excel date')
    # Excel's nonexistent 1900-02-29 must not shift valid earlier dates.
    base = dt.datetime(1904, 1, 1) if date1904 else dt.datetime(1899, 12, 31)
    days = number if date1904 or number < 60 else number - 1
    return base + dt.timedelta(microseconds=int(days * Decimal(86400000000)))


@dataclass
class Cell:
    ref: str
    kind: str
    value: object = field(repr=False)
    is_formula: bool = False
    cache_present: bool = False
    formula: str | None = field(default=None, repr=False)
    formula_origin: str | None = None
    shared_index: str | None = None


@dataclass
class Sheet:
    index: int
    part: str
    name: str = field(repr=False)
    cells: dict = field(repr=False)
    merges: list
    hidden_columns: list
    hidden_rows: list
    state: str

    def cell(self, ref):
        point = position(ref)
        for span in self.merges:
            if contains(rectangle(span), point):
                return self.cells.get(span.split(':')[0])
        return self.cells.get(ref)

    def layout(self):
        """Structural candidates, never inferred student/enrollment assignments."""
        headers = {'общий балл': [], 'волшебство': [], 'лекции': []}
        triplets, groups = [], []
        for ref, cell in self.cells.items():
            row, col = position(ref)
            if cell.is_formula or cell.value is None:
                continue
            text = str(cell.value).strip()
            if row <= 3 and text.lower() in headers:
                headers[text.lower()].append(ref)
            if col in (1, 2) and re.fullmatch(r'(?:гр(?:уппа)?\.?\s*)?[0-9]{4}', text, re.I):
                groups.append(ref)
            if row <= 3 and text == 'А':
                # The observed triplets never cross Z; no arbitrary A1 arithmetic.
                if len(ref.rstrip('0123456789')) == 1 and col <= 24:
                    refs = [chr(64 + col + delta) + str(row) for delta in range(3)]
                    if [self.cells[r].value if r in self.cells else None for r in refs] == ['А', 'Т', 'ДЗ']:
                        triplets.append(refs)
        return dict(total_headers=sorted(headers['общий балл'], key=position),
                    recommendation_headers=sorted(headers['волшебство'], key=position),
                    lecture_headers=sorted(headers['лекции'], key=position),
                    practice_triplets=sorted(triplets, key=lambda x: position(x[0])),
                    group_candidate_cells=sorted(groups, key=position),
                    requires_identity_review=True)


@dataclass
class Workbook:
    sha256: str
    date1904: bool
    sheets: list = field(repr=False)
    warnings: list

    def summary(self):
        """Public-safe structural projection; raw cells remain in memory only."""
        sheets = []
        for sheet in self.sheets:
            formulas = [c for c in sheet.cells.values() if c.is_formula]
            sheets.append(dict(index=sheet.index, cell_count=len(sheet.cells),
                               merge_count=len(sheet.merges), formula_count=len(formulas),
                               missing_formula_cache=sum(not c.cache_present for c in formulas),
                               shared_formula_count=sum(c.shared_index is not None for c in formulas),
                               hidden_column_ranges=sheet.hidden_columns,
                               hidden_row_count=len(sheet.hidden_rows), state=sheet.state,
                               layout=sheet.layout()))
        return dict(sheet_count=len(sheets), date_system='1904' if self.date1904 else '1900',
                    formula_count=sum(s['formula_count'] for s in sheets),
                    missing_formula_cache=sum(s['missing_formula_cache'] for s in sheets),
                    warnings=sorted(set(self.warnings)), sheets=sheets,
                    formulas_evaluated=False, writes_performed=False)


def read_workbook(path, *, max_uncompressed=MAX_EXPANDED):
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE:
            raise WorkbookError('XLSX file size limit exceeded')
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or len(names) > 5000:
                raise WorkbookError('Duplicate or excessive archive entries')
            if sum(i.file_size for i in infos) > max_uncompressed or any(i.file_size > 16 * 1024 * 1024 for i in infos):
                raise WorkbookError('Expanded XLSX size limit exceeded')
            if any(name.startswith('/') or '\\' in name or '..' in PurePosixPath(name).parts for name in names):
                raise WorkbookError('Unsafe archive member path')

            def xml(part):
                text = archive.read(part).decode('utf-8-sig')
                if '\x00' in text or re.search(r'<!\s*(?:DOCTYPE|ENTITY)', text, re.I):
                    raise WorkbookError('DTD/entities or unsupported XML encoding')
                return ET.fromstring(text)

            wb = xml('xl/workbook.xml')
            if wb.tag != '{' + NS + '}workbook':
                raise WorkbookError('Unsupported workbook namespace')
            props = wb.find('m:workbookPr', N)
            epoch = props.get('date1904', '0') if props is not None else '0'
            if epoch not in ('0', '1', 'true', 'false'):
                raise WorkbookError('Invalid workbook date system')
            date1904 = epoch in ('1', 'true')
            relations = {}
            for rel in xml('xl/_rels/workbook.xml.rels').findall('{' + PKG + '}Relationship'):
                if rel.get('Id') in relations:
                    raise WorkbookError('Duplicate relationship identifier')
                relations[rel.get('Id')] = rel
            strings = []
            if 'xl/sharedStrings.xml' in names:
                strings = [rich_text(si) for si in xml('xl/sharedStrings.xml').findall('m:si', N)]
            formats, style_ids = {}, [0]
            if 'xl/styles.xml' in names:
                styles = xml('xl/styles.xml')
                formats = {int(f.get('numFmtId')): f.get('formatCode', '') for f in styles.findall('m:numFmts/m:numFmt', N)}
                style_ids = [int(x.get('numFmtId', '0')) for x in styles.findall('m:cellXfs/m:xf', N)] or [0]
            warnings = ['formula_cache_not_recalculated']
            if any('vbaProject' in name or name.startswith('xl/externalLinks/') for name in names):
                warnings.append('active_or_external_content_not_executed')
            sheets, used_parts, used_ids = [], set(), set()
            for index, entry in enumerate(wb.findall('m:sheets/m:sheet', N), 1):
                state = entry.get('state', 'visible')
                if state not in ('visible', 'hidden', 'veryHidden'):
                    raise WorkbookError('Invalid worksheet visibility')
                rel = relations.get(entry.get('{' + REL + '}id'))
                if rel is None or rel.get('TargetMode') == 'External' or rel.get('Type') != REL + '/worksheet':
                    raise WorkbookError('Missing or external worksheet relationship')
                target = rel.get('Target', '')
                if not target or ':' in target or '\\' in target or '..' in PurePosixPath(target).parts:
                    raise WorkbookError('Unsafe worksheet target')
                part = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/' + target)
                if not part.startswith('xl/') or part in used_parts or entry.get('sheetId') in used_ids:
                    raise WorkbookError('Duplicate or invalid worksheet identity')
                used_parts.add(part)
                used_ids.add(entry.get('sheetId'))
                root = xml(part)
                if root.tag != '{' + NS + '}worksheet':
                    raise WorkbookError('Invalid worksheet root')
                cells, masters = {}, {}
                for row in root.findall('m:sheetData/m:row', N):
                    row_id = int(row.get('r'))
                    for c in row.findall('m:c', N):
                        ref = c.get('r')
                        if position(ref)[0] != row_id or ref in cells:
                            raise WorkbookError('Duplicate or inconsistent cell coordinate')
                        v, f = c.find('m:v', N), c.find('m:f', N)
                        text = v.text if v is not None else None
                        cache = text is not None and text != ''
                        kind, value = c.get('t', 'n'), None
                        if kind not in ('inlineStr', 's', 'str', 'e', 'b', 'd', 'n'):
                            raise WorkbookError('Unsupported cell type')
                        style = int(c.get('s', '0'))
                        if style < 0 or style >= len(style_ids):
                            raise WorkbookError('Unknown cell style')
                        if kind == 'inlineStr':
                            inline = c.find('m:is', N)
                            value = rich_text(inline) if inline is not None else ''
                        elif cache:
                            if kind == 's':
                                offset = int(text)
                                if offset < 0 or offset >= len(strings):
                                    raise WorkbookError('Unknown shared string')
                                value = strings[offset]
                            elif kind in ('str', 'e'):
                                value = text
                            elif kind == 'b':
                                if text not in ('0', '1'):
                                    raise WorkbookError('Invalid boolean value')
                                value = text == '1'
                            elif kind == 'd':
                                value = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
                            elif kind == 'n':
                                value = Decimal(text)
                                if not value.is_finite():
                                    raise WorkbookError('Nonfinite numeric cell')
                                if date_style(style_ids[style], formats):
                                    try:
                                        value, kind = excel_date(value, date1904), 'date'
                                    except (ValueError, OverflowError):
                                        kind = 'invalid_date'
                                        warnings.append('invalid_date')
                            else:
                                raise WorkbookError('Unsupported cell type')
                        kind = {'e': 'error', 'n': 'number', 's': 'string', 'str': 'string', 'inlineStr': 'string', 'b': 'boolean', 'd': 'date'}.get(kind, kind)
                        if kind == 'error':
                            warnings.append('cached_cell_error')
                        cell = Cell(ref, kind, value, f is not None, cache,
                                    f.text if f is not None else None)
                        if f is not None and f.get('t') == 'shared':
                            cell.shared_index = f.get('si')
                            if cell.shared_index is None:
                                raise WorkbookError('Shared formula identifier missing')
                            if f.text:
                                if cell.shared_index in masters:
                                    raise WorkbookError('Duplicate shared formula origin')
                                masters[cell.shared_index] = (ref, rectangle(f.get('ref', ref)))
                        cells[ref] = cell
                for cell in cells.values():
                    if cell.shared_index is not None:
                        origin = masters.get(cell.shared_index)
                        if origin is None or not contains(origin[1], position(cell.ref)):
                            raise WorkbookError('Missing or invalid shared formula origin')
                        cell.formula_origin = origin[0]
                merges = [m.get('ref') for m in root.findall('m:mergeCells/m:mergeCell', N)]
                if len(merges) > 1000:
                    raise WorkbookError('Merge count limit exceeded')
                bounds = []
                for span in merges:
                    rect = rectangle(span)
                    if any(rect[0][0] <= old[1][0] and old[0][0] <= rect[1][0] and rect[0][1] <= old[1][1] and old[0][1] <= rect[1][1] for old in bounds):
                        raise WorkbookError('Overlapping merged ranges')
                    anchor = span.split(':')[0]
                    if any(cell.ref != anchor and contains(rect, position(cell.ref))
                           and (cell.is_formula or cell.value not in (None, '')) for cell in cells.values()):
                        raise WorkbookError('Merged range hides conflicting cell content')
                    bounds.append(rect)
                hidden = [(int(c.get('min')), int(c.get('max'))) for c in root.findall('m:cols/m:col', N) if c.get('hidden') in ('1', 'true')]
                if any(a < 1 or b < a or b > 16384 for a, b in hidden):
                    raise WorkbookError('Invalid hidden column range')
                hidden_rows = [int(r.get('r')) for r in root.findall('m:sheetData/m:row', N) if r.get('hidden') in ('1', 'true')]
                sheets.append(Sheet(index, part, entry.get('name', ''), cells, merges, hidden, hidden_rows, state))
            if not sheets:
                raise WorkbookError('Workbook has no worksheets')
            return Workbook(hashlib.sha256(raw).hexdigest(), date1904, sheets, warnings)
    except WorkbookError:
        raise
    except (OSError, BadZipFile, KeyError, ValueError, TypeError, ET.ParseError, InvalidOperation, RuntimeError, OverflowError):
        raise WorkbookError('Invalid or unsupported XLSX; reading stopped') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xlsx', help='Local XLSX path; structural summary only')
    args = parser.parse_args(argv)
    print(json.dumps(read_workbook(args.xlsx).summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except WorkbookError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
