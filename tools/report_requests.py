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
class ReplyButton:
    label: str
    callback_data: str = field(repr=False)

@dataclass(frozen=True)
class PreparedReply:
    status: str
    text: str = field(repr=False)
    parse_mode: None = None
    link_preview_disabled: bool = True
    buttons: tuple = ()


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


def criteria_notice(report):
    """No catalog state is proof that the cloud source is current."""
    labels={
        'not_checked':'Актуальность критериев не проверена.',
        'unavailable':'Сведения об актуальности критериев недоступны.',
        'catalog_matches':'Критерии совпадают с последней загруженной версией; свежесть источника не подтверждена.',
        'catalog_changed':'Материалы обновлены после этой проверки. Результат сохранён по прежним критериям; нужна сверка преподавателя.',
        'assignment_removed':'Задания нет в последней загруженной версии. Старый результат сохранён; нужна сверка преподавателя.',
    }
    return labels.get(report.get('criteria_state'),'Актуальность критериев не проверена.')


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
        buttons=[]
        for number,item in enumerate(page['items'],1):
            if item['available']:
                assignment=_text(item['report'].get('assignment_id','Работа'))[:80]
                lines.append(assignment+' — нужна проверка преподавателя')
                lines.append(criteria_notice(item['report']))
            else:
                lines.append('Результат пока недоступен')
            lines.append('/progress '+_text(item['report_id']))
            buttons.append((ReplyButton('Открыть работу '+str(number),'progress:o:'+item['reference']),))
        if not page['items']:lines.append('На этой странице нет доступных работ.')
        if page['next_page'] is not None:lines.append('Далее: /progress page '+str(page['next_page']))
        navigation=[]
        if page['page']>1:navigation.append(ReplyButton('Назад','progress:p:'+str(page['page']-1)))
        if page['next_page'] is not None:navigation.append(ReplyButton('Далее','progress:p:'+str(page['next_page'])))
        if navigation:buttons.append(tuple(navigation))
        return PreparedReply('prepared',_bounded('\n'.join(lines)),buttons=tuple(buttons))
    match=re.fullmatch(r'/(progress|report) ([^\s]+)',command)
    if match is None:
        return PreparedReply('invalid_request','Укажите /progress ID_отчёта или /report ID_отчёта.')
    purpose='progress.self' if match.group(1)=='progress' else 'student.report'
    try:
        if type(reader) is not ReportReader:raise ReportAccessError('Report unavailable')
        report=reader.read(match.group(2),context,purpose=purpose)
    except ReportAccessError:
        return PreparedReply('unavailable','Отчёт недоступен. Проверьте ссылку и подтверждение доступа.')
    lines=['Результат предварительной проверки','Нужна проверка преподавателя.',criteria_notice(report),'']
    labels={'met':'выполнено по проверенному признаку','not_met':'не выполнено по проверенному признаку','needs_review':'нужна проверка'}
    for number,item in enumerate(report['requirements'],1):
        lines.append(f"{number}. {_text(item['requirement'])}: {labels[item['status']]}")
        observation=item.get('content_observation')
        if observation and observation.get('comment'):
            lines.append('   Наблюдение проверяющего (требует проверки): '+_text(observation['comment']))
    lines.extend(['','Баллы не начислены. Отработка автоматически не принята.'])
    buttons=((ReplyButton('К списку работ','progress:p:1'),),) if purpose=='progress.self' else ()
    return PreparedReply('prepared',_bounded('\n'.join(lines)),buttons=buttons)


def prepare_progress_callback(reader,context,data):
    """Resolve short references and reauthorize each click, with no sends."""
    unavailable=PreparedReply('unavailable','Отчёт недоступен. Проверьте ссылку и подтверждение доступа.')
    try:
        if type(reader) is not ReportReader or type(data) is not str or not data.isascii() or len(data)>64:
            return unavailable
        page=re.fullmatch(r'progress:p:([1-9][0-9]{0,5}|1000000)',data)
        if page:return prepare_report_reply(reader,context,'/progress page '+page.group(1))
        opened=re.fullmatch(r'progress:o:([a-f0-9]{32})',data)
        if opened:
            report_id=reader.resolve_progress_reference(opened.group(1),context)
            return prepare_report_reply(reader,context,'/progress '+report_id)
        return unavailable
    except ReportAccessError:
        return unavailable
