"""Local read-only journal projection, not an endpoint or identity resolver.

Mappings and Context MUST come from confirmed server registries, never user/LLM
arguments. A mapping is tied to exact workbook bytes: changed files need reviewed
remapping, not fuzzy name/row matching. No writes, formula calculation, academic
inference, sending or network access. Workbook loader must use gradebook_read.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import re
from assistant_access import AccessPolicy, aware, identifier, live
from gradebook_read import Workbook, position, rectangle, contains

class ProgressError(ValueError):
    pass

@dataclass(frozen=True)
class JournalField:
    id: str
    kind: str
    cell: str = field(repr=False)

@dataclass(frozen=True)
class JournalMap:
    enrollment_id: str
    student_id: str
    discipline_id: str
    group_id: str
    workbook_sha256: str = field(repr=False)
    sheet_index: int
    row: int
    fields: tuple = field(repr=False)

class ProgressReader:
    def __init__(self,mappings,*,policy_provider,load_workbook,clock):
        try:
            if not all(callable(v) for v in (policy_provider,load_workbook,clock)):raise ValueError()
            records={};rows=set()
            for m in mappings:
                if (type(m) is not JournalMap or not all(identifier(v) for v in (m.enrollment_id,m.student_id,m.discipline_id,m.group_id))
                        or re.fullmatch('[a-f0-9]{64}',m.workbook_sha256) is None
                        or type(m.sheet_index) is not int or m.sheet_index<1 or type(m.row) is not int or not 1<=m.row<=1048576
                        or type(m.fields) is not tuple or not 1<=len(m.fields)<=200 or m.enrollment_id in records):raise ValueError()
                row_key=(m.workbook_sha256,m.sheet_index,m.row)
                if row_key in rows:raise ValueError()
                rows.add(row_key);ids=set();cells=set()
                for f in m.fields:
                    if (type(f) is not JournalField or not identifier(f.id) or f.kind not in ('attendance','score','homework','total')
                            or position(f.cell)[0]!=m.row or f.id in ids or f.cell in cells):raise ValueError()
                    ids.add(f.id);cells.add(f.cell)
                records[m.enrollment_id]=m
            self._maps=records;self._policy=policy_provider;self._load=load_workbook;self._clock=clock
        except Exception:raise ProgressError('Invalid trusted journal mapping') from None

    def _authorize(self,m,context,purpose):
        policy=self._policy();now=self._clock()
        if type(policy) is not AccessPolicy or not aware(now):raise ValueError()
        e=policy.enrollments.get(m.enrollment_id)
        if e is None or (e.student_id,e.discipline_id,e.group_id)!=(m.student_id,m.discipline_id,m.group_id):raise ValueError()
        if purpose=='student.report':allowed=policy.authorize(context,purpose,e.id,now=now).allowed
        elif purpose=='progress.self':allowed=live(e,now) and policy.authorize(context,purpose,e.student_id,now=now).allowed
        else:allowed=False
        if not allowed:raise ValueError()

    def read(self,enrollment_id,context,*,purpose):
        """Explicit enrollment ID is checked before loading any journal payload.

        Returns exact recorded literals only; blank is unknown, formula caches
        are withheld even when present. No student names, row numbers or formulas.
        The result is a local snapshot, not proof of live source freshness.
        """
        try:
            m=self._maps[enrollment_id];self._authorize(m,context,purpose)
            book=self._load()
            if type(book) is not Workbook or book.sha256!=m.workbook_sha256:raise ValueError()
            matches=[s for s in book.sheets if s.index==m.sheet_index]
            if len(matches)!=1:raise ValueError()
            sheet=matches[0];entries=[]
            for f in m.fields:
                if any(contains(rectangle(span),position(f.cell)) for span in sheet.merges):raise ValueError()
                cell=sheet.cells.get(f.cell)
                item={'id':f.id,'kind':f.kind}
                if cell is None or (not cell.is_formula and cell.value is None):item['state']='not_recorded'
                elif cell.is_formula:item['state']='formula_unverified'
                elif cell.kind=='error':item['state']='source_error'
                else:
                    value=cell.value
                    if isinstance(value,Decimal):
                        if not value.is_finite():raise ValueError()
                        value=str(value)
                    if type(value) not in (str,int,float,bool) or (type(value) is str and len(value)>1000):raise ValueError()
                    if type(value) is float:
                        import math
                        if not math.isfinite(value):raise ValueError()
                    item.update(state='recorded',value=value)
                entries.append(item)
            self._authorize(m,context,purpose)  # Revoke/binding changes during load.
            return {'entries':entries,'credit_written':False,'source':'local_workbook_snapshot','live_verified':False}
        except Exception:raise ProgressError('Progress unavailable') from None
