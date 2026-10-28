"""Prepare local report replies. Not an enabled bot command or delivery API.

Context/reader come from trusted authentication/registry adapters. Text carries
only an opaque report reference, never identity/role/recipient grants. A transport
must reprepare at actual dispatch and must not treat saved replies as credentials.
"""
from dataclasses import dataclass, field
import re
import unicodedata
from report_access import ReportReader, ReportAccessError

@dataclass(frozen=True)
class PreparedReply:
    status: str
    text: str = field(repr=False)
    parse_mode: None = None
    link_preview_disabled: bool = True


def _text(value):
    return ' '.join(''.join(' ' if c.isspace() else c for c in str(value) if c.isspace() or unicodedata.category(c) not in ('Cc','Cf','Cs')).split())


def _bounded(text):
    suffix='\n… Отчёт сокращён.'
    budget=3500-len(suffix.encode('utf-16-le'))//2
    output=[];used=0
    for character in text:
        units=2 if ord(character)>0xFFFF else 1
        if used+units>budget:return ''.join(output)+suffix
        output.append(character);used+=units
    return text


def prepare_report_reply(reader,context,command):
    if (type(command) is not str or len(command)>300
            or any(c in command for c in ('\r','\n'))):
        return PreparedReply('invalid_request','Укажите /progress ID_отчёта или /report ID_отчёта.')
    list_match=re.fullmatch(r'/progress(?: page ([1-9][0-9]{0,5}|1000000))?',command)
    if list_match is not None:
        try:
            if type(reader) is not ReportReader:raise ReportAccessError('Report unavailable')
            page=reader.list_self(context,page=int(list_match.group(1) or '1'))
        except ReportAccessError:
            return PreparedReply('unavailable','Отчёт недоступен. Проверьте ссылку и подтверждение доступа.')
        lines=['Мои работы — страница '+str(page['page']),'Предварительные результаты, без начисления баллов.','']
        for item in page['items']:
            if item['available']:
                assignment=_text(item['report'].get('assignment_id','Работа'))[:80]
                lines.append(assignment+' — нужна проверка преподавателя')
            else:
                lines.append('Результат пока недоступен')
            lines.append('/progress '+_text(item['report_id']))
        if not page['items']:lines.append('На этой странице нет доступных работ.')
        if page['next_page'] is not None:lines.append('Далее: /progress page '+str(page['next_page']))
        return PreparedReply('prepared',_bounded('\n'.join(lines)))
    match=re.fullmatch(r'/(progress|report) ([^\s]+)',command)
    if match is None:
        return PreparedReply('invalid_request','Укажите /progress ID_отчёта или /report ID_отчёта.')
    purpose='progress.self' if match.group(1)=='progress' else 'student.report'
    try:
        if type(reader) is not ReportReader:raise ReportAccessError('Report unavailable')
        report=reader.read(match.group(2),context,purpose=purpose)
    except ReportAccessError:
        return PreparedReply('unavailable','Отчёт недоступен. Проверьте ссылку и подтверждение доступа.')
    lines=['Результат предварительной проверки','Нужна проверка преподавателя.','']
    labels={'met':'выполнено по проверенному признаку','not_met':'не выполнено по проверенному признаку','needs_review':'нужна проверка'}
    for number,item in enumerate(report['requirements'],1):
        lines.append(f"{number}. {_text(item['requirement'])}: {labels[item['status']]}")
        observation=item.get('content_observation')
        if observation and observation.get('comment'):
            lines.append('   Наблюдение проверяющего (требует проверки): '+_text(observation['comment']))
    lines.extend(['','Баллы не начислены. Отработка автоматически не принята.'])
    return PreparedReply('prepared',_bounded('\n'.join(lines)))
