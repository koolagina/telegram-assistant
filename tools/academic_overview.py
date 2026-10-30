"""Offline composition of authorized journal and review views; no sends/API.

Trusted authenticated Context and factories are prerequisites. This does not
add authentication, current-source provenance or a deployed /progress command.
All-or-unavailable: do not reveal half a view on failed authorization/source.
"""
import re
from academic_progress import ProgressReader
from report_access import ReportReader
from report_requests import PreparedReply, _text, _bounded

class OverviewError(ValueError):
    pass

class AcademicOverview:
    def __init__(self,journal,reviews):
        if type(journal) is not ProgressReader or type(reviews) is not ReportReader:
            raise OverviewError('Trusted readers required')
        self._journal=journal;self._reviews=reviews

    def read(self,enrollment_id,context,*,purpose,page=1):
        try:
            if type(page) is not int or not 1<=page<=1000000:raise ValueError()
            identity=self._journal.authorize_enrollment(enrollment_id,context,purpose=purpose)
            journal=self._journal.read(enrollment_id,context,purpose=purpose)
            reviews=self._reviews.list_enrollment(enrollment_id,context,purpose=purpose,expected_identity=identity,page=page)
            # Recheck after the second data source, not only after XLSX load.
            if self._journal.authorize_enrollment(enrollment_id,context,purpose=purpose)!=identity:raise ValueError()
            return {'journal':journal,'reviews':reviews,'credit_written':False,'live_verified':False}
        except Exception:raise OverviewError('Academic overview unavailable') from None


def prepare_overview_reply(service,context,command):
    """Local candidate commands /overview ENROLLMENT and /student ENROLLMENT.

    IDs select a target; they grant no access. Use existing /progress for work
    details. Neither prepared text nor page numbers are authorization credentials.
    Reprepare at actual dispatch using current policy, never send a saved reply.
    """
    if type(command) is not str or len(command)>300:
        return PreparedReply('invalid_request','Укажите /overview ID_обучения или /student ID_обучения.')
    match=re.fullmatch(r'/(overview|student) ([^\s]+)(?: page ([1-9][0-9]{0,5}|1000000))?',command)
    if match is None:
        return PreparedReply('invalid_request','Укажите /overview ID_обучения или /student ID_обучения.')
    try:
        if type(service) is not AcademicOverview:raise OverviewError()
        purpose='progress.self' if match[1]=='overview' else 'student.report'
        result=service.read(match[2],context,purpose=purpose,page=int(match[3] or '1'))
    except OverviewError:
        return PreparedReply('unavailable','Сводка недоступна. Проверьте подтверждение доступа.')
    lines=['Учебная сводка','Локальная копия: актуальность облачного журнала не подтверждена.','','Журнал']
    labels={'attendance':'Посещаемость','score':'Баллы','homework':'Домашняя работа','total':'Записанный итог'}
    states={'not_recorded':'нет записи','formula_unverified':'формула — нужен пересчёт в журнале','source_error':'ошибка исходной ячейки'}
    for item in result['journal']['entries']:
        value=_text(item['value']) if item['state']=='recorded' else states[item['state']]
        lines.append(labels[item['kind']]+' · '+_text(item['id'])+': '+value)
    lines.extend(['','Проверки работ — страница '+str(result['reviews']['page'])])
    for item in result['reviews']['items']:
        report=item['report']
        lines.append(_text(report.get('assignment_id','Работа'))+' — нужна проверка преподавателя')
        lines.append(('/progress ' if purpose=='progress.self' else '/report ')+_text(item['report_id']))
    if not result['reviews']['items']:lines.append('На этой странице нет сохранённых проверок. Это не означает отсутствие задолженности.')
    if result['reviews']['next_page'] is not None:
        lines.append('Далее: /'+match[1]+' '+match[2]+' page '+str(result['reviews']['next_page']))
    lines.extend(['','Баллы не начислены. Отработка автоматически не принята.'])
    return PreparedReply('prepared',_bounded('\n'.join(lines)))
